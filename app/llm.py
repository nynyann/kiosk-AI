"""Gọi mô hình ngôn ngữ lớn trên FPT AI Marketplace để kiosk hiểu hoàn cảnh và
trả lời tự nhiên hơn, theo phản hồi của ban giám khảo (15/09/2026):

  1. Nhớ ngữ cảnh trong cùng phiên: tuổi, lương hưu, hoàn cảnh bác đã kể
     được đưa vào mọi lần gọi, không bắt bác nói lại.
  2. Thấu cảm: bác kể hoàn cảnh thì máy xác nhận đã hiểu rồi mới hướng dẫn.
  3. Câu hỏi diễn đạt khác FAQ: mô hình đọc kho tri thức của thủ tục đó rồi
     trả lời, KHÔNG được bịa ngoài kho.
  4. Lời tiếng Việt tự nhiên hơn.

API kiểu OpenAI: POST {FPT_BASE_URL}/chat/completions, Authorization: Bearer.
Tài liệu: https://github.com/fpt-corp/ai-marketplace

KHÔNG có khoá (FPT_API_KEY trống) thì mọi hàm ở đây trả None và máy chủ chạy
y như trước bằng kho tri thức tĩnh. Có khoá mà gọi hỏng (hết tiền, mất mạng,
quá hạn giờ) cũng vậy: kiosk không bao giờ im hay treo vì mô hình.

Nguyên tắc không đổi so với bản tĩnh: mô hình chỉ được nói những gì có trong
đoạn kho tri thức đưa vào prompt. Câu nào ngoài kho thì nó phải trả đúng mã
KHONG_CO_TRONG_KHO để máy chủ thay bằng câu mời gặp cán bộ. Kiosk không kết
luận "chắc chắn được hưởng".
"""

from __future__ import annotations

import json
import re
import time
from typing import Dict, List, Optional

import httpx

from . import config

# Mã mô hình phải trả khi câu hỏi không có trong kho. Chọn chuỗi không thể
# xuất hiện tự nhiên trong câu tiếng Việt.
NOT_IN_KB = "KHONG_CO_TRONG_KHO"

_stats = {"calls": 0, "ok": 0, "failed": 0, "last_error": None, "last_latency": None}


def enabled() -> bool:
    return bool(config.FPT_API_KEY)


def stats() -> dict:
    return {"enabled": enabled(), "model": config.LLM_MODEL if enabled() else None, **_stats}


# ---------------------------------------------------------------------------
# Gọi thô
# ---------------------------------------------------------------------------
async def chat(messages: List[dict], *, max_tokens: int = 300, temperature: float = 0.2,
               timeout: Optional[float] = None) -> Optional[str]:
    """Một lượt chat. Trả None khi tắt hoặc hỏng, không ném lỗi ra ngoài."""
    if not enabled():
        return None
    _stats["calls"] += 1
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=timeout or config.LLM_TIMEOUT_SECONDS) as client:
            r = await client.post(
                f"{config.FPT_BASE_URL.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {config.FPT_API_KEY}",
                         "Content-Type": "application/json"},
                json={"model": config.LLM_MODEL, "messages": messages,
                      "max_tokens": max_tokens, "temperature": temperature, "stream": False},
            )
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        text = (data["choices"][0]["message"]["content"] or "").strip()
        # Vài mô hình (Qwen, DeepSeek) chèn đoạn suy nghĩ <think>…</think>.
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
        _stats["ok"] += 1
        _stats["last_latency"] = round(time.time() - t0, 2)
        return text or None
    except Exception as exc:  # noqa: BLE001
        _stats["failed"] += 1
        _stats["last_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        print(f"[llm] hỏng sau {time.time() - t0:.1f}s: {_stats['last_error']}")
        return None


def _flat_text(s: str) -> str:
    """Bỏ dấu, hạ chữ thường, gộp khoảng trắng: so «bảy mươi sáu tuổi» với
    «Bảy Mươi Sáu Tuổi» mà mô hình hay viết hoa lại."""
    import unicodedata
    nfd = unicodedata.normalize("NFD", (s or "").lower())
    t = "".join(c for c in nfd if unicodedata.category(c) != "Mn").replace("đ", "d")
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()


# Từ không mang nội dung, bỏ khi so bằng chứng với câu hỏi.
_STOP = set("toi bac chau co khong phai la a dang hien nay nam bao nhieu gi thi ma va hay hoac cua o roi da se den tu".split())


def _topic_words(q: dict) -> set:
    """Từ nội dung của một câu hỏi: lấy từ câu hỏi, nhãn và cụm gợi ý của các
    lựa chọn. Dùng để kiểm bằng chứng mô hình trích có nói về chuyện đó không."""
    words = set(_flat_text(q.get("text", "")).split())
    for o in q.get("options", []):
        words |= set(_flat_text(o.get("label", "")).split())
        for m in o.get("match") or []:
            words |= set(_flat_text(m).split())
    return {w for w in words if len(w) > 1 and w not in _STOP}


def _json_block(text: str) -> Optional[dict]:
    """Lấy khối JSON đầu tiên trong câu trả lời, kể cả khi mô hình bọc ```json."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return None
    try:
        out = json.loads(m.group())
        return out if isinstance(out, dict) else None
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Ngữ cảnh: kho tri thức của một thủ tục + những gì bác đã kể
# ---------------------------------------------------------------------------
STYLE = ("Bạn là kiosk hướng dẫn thủ tục hành chính đặt tại bộ phận một cửa, nói chuyện với "
         "người cao tuổi. Xưng \"cháu\", gọi người dân là \"bác\". Nói tiếng Việt tự nhiên, ấm áp, "
         "ngắn gọn, mỗi câu trả lời tối đa 3 câu, không dùng từ chuyên ngành khi có từ thường. "
         "Không bao giờ kết luận \"chắc chắn được hưởng\"; dùng \"có khả năng thuộc diện\" và nói "
         "cơ quan có thẩm quyền sẽ xem xét.")


def kb_context(proc: dict) -> str:
    """Toàn bộ nội dung kho tri thức của một thủ tục, viết phẳng để đưa vào prompt."""
    fl = proc.get("flow") or {}
    ck = fl.get("check") or {}
    lines = [f"THỦ TỤC: {proc.get('name')}"]
    if ck.get("questions"):
        lines.append("ĐIỀU KIỆN, HỎI THEO THỨ TỰ:")
        for q in ck["questions"]:
            opts = "; ".join(f"{o['value']} = {o.get('label')}" for o in q.get("options", []))
            lines.append(f"- [{q['id']}] {q.get('text')} Lựa chọn: {opts}")
    if ck.get("outcomes"):
        lines.append("KẾT LUẬN THEO CÂU TRẢ LỜI:")
        for o in ck["outcomes"]:
            lines.append(f"- khi {json.dumps(o.get('when'), ensure_ascii=False)} → {o.get('verdict')}: {o.get('reason') or o.get('note') or ''}")
    if (ck.get("eligible") or {}).get("note"):
        lines.append(f"- đủ điều kiện: {ck['eligible']['note']}")
    lines.append("HỒ SƠ: " + "; ".join(proc.get("documents") or []))
    prep = fl.get("prepare") or {}
    if prep.get("say"):
        lines.append("CHUẨN BỊ: " + prep["say"])
    for t in prep.get("tips") or []:
        lines.append("- " + t)
    sub = fl.get("submit") or {}
    lines.append("NƠI NỘP: " + "; ".join(sub.get("places") or [proc.get("where_to_submit") or ""]))
    if sub.get("methods"):
        lines.append("CÁCH NỘP: " + "; ".join(sub["methods"]))
    if sub.get("agency"):
        lines.append("CƠ QUAN XỬ LÝ: " + sub["agency"])
    lines.append(f"THỜI HẠN: {proc.get('processing_time')}")
    lines.append(f"PHÍ: {proc.get('fee')}")
    if sub.get("result"):
        lines.append("KẾT QUẢ: " + sub["result"])
    if fl.get("faq"):
        lines.append("CÂU HỎI THƯỜNG GẶP:")
        for item in fl["faq"]:
            lines.append(f"- Hỏi: {(item.get('q') or [''])[0]} → Đáp: {item.get('a')}")
    src = proc.get("source") or {}
    if src.get("title"):
        lines.append("NGUỒN: " + src["title"])
    return "\n".join(lines)


def citizen_context(proc: dict, answers: Dict[str, str], utterance: str = "",
                    history: Optional[List[dict]] = None, stage: str = "") -> str:
    """Những gì bác đã nói trong phiên này, để mô hình không hỏi lại."""
    lines = []
    if utterance:
        lines.append(f"Bác mở đầu bằng câu: «{utterance}»")
    ck = (proc.get("flow") or {}).get("check") or {}
    label = {}
    for q in ck.get("questions") or []:
        for o in q.get("options", []):
            label[(q["id"], o["value"])] = (q.get("text"), o.get("label"))
    for k, v in (answers or {}).items():
        qt, lb = label.get((k, v), (k, v))
        lines.append(f"Đã trả lời «{qt}» → {lb}")
    for h in history or []:
        if h.get("q"):
            lines.append(f"Bác đã hỏi thêm: «{h['q']}» và cháu đã trả lời: «{h.get('a', '')}»")
    if stage:
        lines.append({"check": "Đang ở bước 1, kiểm tra điều kiện.",
                      "prepare": "Đang ở bước 2, chuẩn bị hồ sơ.",
                      "submit": "Đang ở bước 3, nộp hồ sơ."}.get(stage, ""))
    return "\n".join(l for l in lines if l) or "Bác chưa cung cấp gì thêm."


# ---------------------------------------------------------------------------
# 1. Từ câu bác kể, điền sẵn các điều kiện + câu xác nhận đã hiểu
# ---------------------------------------------------------------------------
async def prefill_from_utterance(proc: dict, utterance: str) -> Optional[dict]:
    """Trả {"answers": {qid: value}, "ack": "câu xác nhận"} hoặc None.

    Chỉ điền câu nào bác nói RÕ; không suy đoán. Máy chủ vẫn hỏi phần còn
    thiếu. `ack` là câu máy nói để bác biết mình đã được hiểu, ví dụ «Cháu
    hiểu rồi ạ, bác 76 tuổi và chưa có lương hưu».
    """
    if not enabled() or not (utterance or "").strip():
        return None
    ck = (proc.get("flow") or {}).get("check") or {}
    qs = ck.get("questions") or []
    if not qs:
        return None
    valid = {q["id"]: [o["value"] for o in q.get("options", [])] for q in qs}
    prompt = (
        f"{kb_context(proc)}\n\n"
        f"Người dân vừa nói: «{utterance}»\n\n"
        "Nhiệm vụ: với từng câu hỏi điều kiện ở trên, nếu câu người dân nói CHO BIẾT RÕ câu trả lời "
        "thì ghi giá trị lựa chọn tương ứng kèm đoạn TRÍCH NGUYÊN VĂN trong câu người dân làm bằng chứng; "
        "không có đoạn nào nói rõ thì bỏ qua, KHÔNG suy đoán (ví dụ bác không nói gì về quốc tịch thì "
        "không điền công dân). "
        "Rồi viết một câu ngắn, ấm áp, xác nhận cháu đã hiểu hoàn cảnh bác vừa kể (nhắc lại đúng những "
        "gì bác nói, không thêm), không hứa hẹn kết quả.\n"
        "Trả lời DUY NHẤT một JSON: {\"answers\": {\"<id câu hỏi>\": \"<value>\"}, "
        "\"evidence\": {\"<id câu hỏi>\": \"<trích nguyên văn>\"}, \"ack\": \"<câu xác nhận>\"}"
    )
    text = await chat([{"role": "system", "content": STYLE}, {"role": "user", "content": prompt}],
                      max_tokens=350, temperature=0.1)
    data = _json_block(text or "")
    if not data:
        return None
    # Chốt an toàn: mỗi câu điền sẵn phải có bằng chứng là một đoạn CÓ THẬT
    # trong câu bác nói, và hai câu không được dùng chung một bằng chứng. Đo
    # 16/09: Saola tự điền «công dân = có», «BHXH = không» dù bác không nói;
    # chốt này chặn đúng kiểu đó.
    uf = _flat_text(utterance)
    evidence = data.get("evidence") or {}
    topic = {q["id"]: _topic_words(q) for q in qs}
    used = set()
    answers = {}
    for k, v in (data.get("answers") or {}).items():
        ev = _flat_text(str(evidence.get(k) or ""))
        if not (k in valid and v in valid[k] and ev and ev in uf and ev not in used):
            continue
        # Bằng chứng phải nói về đúng chuyện câu hỏi hỏi: «sống một mình» không
        # phải bằng chứng cho «công dân Việt Nam» (Saola từng trả đúng thế).
        if not (set(ev.split()) & topic[k]):
            continue
        answers[k] = v
        used.add(ev)
    ack = str(data.get("ack") or "").strip()
    if not answers and not ack:
        return None
    return {"answers": answers, "ack": ack}


# ---------------------------------------------------------------------------
# 2. Nhận ra thủ tục khi tra từ khoá không bắt được
# ---------------------------------------------------------------------------
async def pick_procedure(utterance: str, procedures: List[dict]) -> Optional[str]:
    """Trả mã thủ tục hoặc None. Dùng khi kb.search dưới ngưỡng, để câu diễn
    đạt lạ («tôi già rồi nhà nước có cho tiền không») vẫn vào được luồng."""
    if not enabled() or not (utterance or "").strip():
        return None
    menu = "\n".join(f"- {p['id']}: {p.get('name')} ({p.get('short') or ''}). Người dân hay gọi: "
                     + "; ".join((p.get("aliases") or [])[:6]) for p in procedures)
    prompt = (
        f"Danh sách thủ tục kiosk hỗ trợ:\n{menu}\n\n"
        f"Người dân nói: «{utterance}»\n\n"
        "Người dân đang cần thủ tục nào? Chỉ chọn khi khá chắc; không rõ hoặc không thuộc danh sách "
        "thì trả \"none\". Trả lời DUY NHẤT một JSON: {\"procedure_id\": \"<id hoặc none>\"}"
    )
    text = await chat([{"role": "system", "content": STYLE}, {"role": "user", "content": prompt}],
                      max_tokens=60, temperature=0.0)
    data = _json_block(text or "")
    pid = (data or {}).get("procedure_id")
    ids = {p["id"] for p in procedures}
    return pid if pid in ids else None


# ---------------------------------------------------------------------------
# 3. Hiểu câu trả lời tự do ở bước 1
# ---------------------------------------------------------------------------
async def classify_answer(q: dict, utterance: str, answers: Dict[str, str]) -> Optional[str]:
    """Ánh xạ câu bác nói sang một lựa chọn của câu hỏi, khi so cụm từ không ra.
    Trả value hoặc None (không chắc)."""
    if not enabled() or not (utterance or "").strip():
        return None
    opts = "; ".join(f"{o['value']} = {o.get('label')}" for o in q.get("options", []))
    prompt = (
        f"Kiosk hỏi: «{q.get('text')}»\nCác lựa chọn: {opts}\n"
        f"Người dân trả lời: «{utterance}»\n\n"
        "Câu trả lời ứng với lựa chọn nào? Không rõ thì trả \"none\". "
        "Trả lời DUY NHẤT một JSON: {\"value\": \"<value hoặc none>\"}"
    )
    text = await chat([{"role": "system", "content": STYLE}, {"role": "user", "content": prompt}],
                      max_tokens=40, temperature=0.0)
    data = _json_block(text or "")
    v = (data or {}).get("value")
    return v if v in {o["value"] for o in q.get("options", [])} else None


# ---------------------------------------------------------------------------
# 4. Trả lời câu hỏi thêm, chỉ từ kho tri thức của thủ tục
# ---------------------------------------------------------------------------
async def answer_from_kb(proc: dict, question: str, answers: Dict[str, str],
                         utterance: str = "", history: Optional[List[dict]] = None,
                         stage: str = "") -> Optional[str]:
    """Trả câu trả lời, hoặc NOT_IN_KB nếu mô hình bảo ngoài kho, hoặc None nếu hỏng."""
    if not enabled() or not (question or "").strip():
        return None
    prompt = (
        f"KHO TRI THỨC (chỉ được dùng thông tin trong đây):\n{kb_context(proc)}\n\n"
        f"NGỮ CẢNH PHIÊN NÀY:\n{citizen_context(proc, answers, utterance, history, stage)}\n\n"
        f"Bác hỏi: «{question}»\n\n"
        "Trả lời bác bằng lời tự nhiên, tối đa 3 câu, dựa ĐÚNG vào kho tri thức và ngữ cảnh ở trên; "
        "nếu bác kể thêm hoàn cảnh (mắt kém, chân yếu, ở xa, con cháu giúp) thì xác nhận đã hiểu rồi "
        "chỉ ra phần nào trong kho giúp được bác (ví dụ cách nộp qua bưu điện, trực tuyến, nhờ cán bộ "
        "hướng dẫn điền). Kho có thông tin liên quan gần thì cứ dùng, không cần khớp từng chữ. "
        "Tuyệt đối không thêm giấy tờ, điều kiện, con số hay mức tiền không có trong kho. "
        f"Chỉ khi câu hỏi hoàn toàn không liên quan tới thủ tục này, hoặc kho không có gì gần với "
        f"điều bác hỏi, mới trả đúng chuỗi {NOT_IN_KB}."
    )
    text = await chat([{"role": "system", "content": STYLE}, {"role": "user", "content": prompt}],
                      max_tokens=260, temperature=0.3)
    if text is None:
        return None
    if NOT_IN_KB in text:
        return NOT_IN_KB
    return text.strip().strip('"')
