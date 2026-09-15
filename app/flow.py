"""Luồng hướng dẫn theo từng bước — sơ đồ «Bắt đầu → Bước 1 → Bước 2 → Bước 3 → Kết thúc».

Bước 1. Kiểm tra điều kiện: kiosk hỏi từng câu (tuổi, công dân, lương hưu…),
        người dân bấm chọn hoặc nói. Đáp ứng → Bước 2. Không đáp ứng → giải
        thích điều kiện chưa đáp ứng và kết luận, KHÔNG bắt chuẩn bị hồ sơ thừa.
Bước 2. Chuẩn bị hồ sơ: liệt kê giấy tờ theo đúng trường hợp đã trả lời ở
        bước 1. Người dân hỏi gì thì trả lời từ kho tri thức của thủ tục đó.
Bước 3. Nộp hồ sơ: nơi nộp, cách nộp, giấy tờ mang theo, cơ quan xử lý và
        thời hạn dự kiến.

Máy chủ KHÔNG giữ trạng thái: giao diện gửi lên `answers` (các câu đã trả
lời) mỗi lượt, máy chủ tính lại từ đầu rồi trả về trạng thái tiếp theo. Nhờ
vậy máy chủ miễn phí khởi động lại giữa chừng cũng không mất phiên của bác.

Nội dung câu hỏi, kết luận, hồ sơ nằm hết trong `data/kb/<thủ tục>.json`,
mục `flow` — xem `data/kb/_SCHEMA.md`. File này chỉ là máy chạy, không chứa
một câu chữ hành chính nào.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from . import config
from .normalize import for_speech, normalize
from .schemas import (FlowAskResult, FlowOption, FlowQuestion, FlowState,
                      Source)

# ---------------------------------------------------------------------------
# Câu chữ dùng chung. Ngắn, xưng "cháu" cho khớp với kho tri thức của Mian.
# ---------------------------------------------------------------------------
STEP_TITLES = {1: "Kiểm tra điều kiện", 2: "Chuẩn bị hồ sơ", 3: "Nộp hồ sơ"}

NOT_UNDERSTOOD_TEXT = "Cháu chưa hiểu câu trả lời của bác. Bác bấm chọn một mục trên màn hình giúp cháu ạ."
ASK_FALLBACK_TEXT = ("Câu này cháu chưa có trong kho tri thức của thủ tục này. "
                     "Bác hỏi cán bộ tiếp nhận hồ sơ giúp cháu ạ.")
ASK_NO_SPEECH_TEXT = "Cháu chưa nghe rõ ạ. Bác nói lại giúp cháu một lần nữa."
DONE_TEXT = "Cháu đã hướng dẫn xong thủ tục {name}. Chúc bác làm thủ tục thuận lợi ạ."
# Câu chào ở màn hình đầu. Giao diện (web/index.html) giữ một bản y hệt để
# hiện chữ; đặt ở đây để máy chủ sinh sẵn tiếng lúc khởi động và lưu vào kho
# đĩa. tests/test_flow.py kiểm hai bản có khớp nhau không.
GREETING_TEXTS = [
    "Xin chào bác! Cháu là máy hướng dẫn làm thủ tục hành chính.",
    "Bác cần làm gì ạ?",
    "Bác bấm vào nút micro bên dưới rồi nói, ví dụ: «Tôi 76 tuổi, không có lương hưu thì được hỗ trợ gì?» Nói xong bác bấm «Nói xong rồi».",
]
GREETING_SPEECH = " ".join(GREETING_TEXTS)
# Các câu khác giao diện tự nói (không qua kho tri thức), cũng sinh sẵn.
UI_TEXTS = [
    GREETING_SPEECH,
    "Vậy bác nói lại giúp cháu, bác cần làm gì ạ?",
    "Bác nói lại giúp cháu, bác cần làm gì ạ?",
    "Bác bấm chọn việc bác cần làm trên màn hình ạ.",
]

VERDICT_TITLES = {
    "ineligible": "Chưa đủ điều kiện",
    "consult": "Cần cán bộ xác định",
    "redirect": "Đây là thủ tục khác",
}

# Trả lời có/không bằng lời: câu phủ định xét TRƯỚC câu khẳng định, vì
# "không có" chứa cả "có". Sắp theo độ dài để cụm dài thắng cụm ngắn.
YES_WORDS = ["có", "rồi", "đúng", "vâng", "dạ", "phải", "ừ", "được"]
NO_WORDS = ["không", "chưa", "chả", "chẳng", "đâu có", "không phải", "không có"]


def _spoken(text: str) -> str:
    """Chuẩn bị chuỗi để đọc: bỏ phần trong ngoặc — «(ban hành kèm Nghị định
    176/2025/NĐ-CP)» hữu ích trên màn hình nhưng đọc lên thì dài và rối."""
    t = re.sub(r"\s*\([^)]*\)", "", text or "")
    return for_speech(t)


def _flat(s: str) -> str:
    nfd = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").replace("đ", "d")


def _contains_phrase(haystack_flat: str, phrase: str) -> bool:
    p = _flat(phrase).strip()
    if not p:
        return False
    return re.search(r"(?<!\w)" + re.escape(p) + r"(?!\w)", haystack_flat) is not None


# ---------------------------------------------------------------------------
# Đọc cấu hình luồng từ file thủ tục
# ---------------------------------------------------------------------------
def _flow(proc: dict) -> dict:
    return proc.get("flow") or {}


def _check(proc: dict) -> dict:
    return _flow(proc).get("check") or {}


def _questions(proc: dict) -> List[dict]:
    return _check(proc).get("questions") or []


def _cond_ok(cond: Optional[dict], answers: Dict[str, str]) -> bool:
    """`when` / `ask_if`: mọi khoá phải được trả lời và nằm trong danh sách cho phép."""
    if not cond:
        return True
    for key, allowed in cond.items():
        if isinstance(allowed, str):
            allowed = [allowed]
        if answers.get(key) not in allowed:
            return False
    return True


def _hint_for(q: dict) -> str:
    """Hướng dẫn cách trả lời, theo kiểu câu hỏi. Tài liệu «trực quan» yêu cầu
    kiosk phải nói rõ bác trả lời thế nào rồi mới hỏi tiếp."""
    if q.get("hint"):
        return q["hint"]
    opts = q.get("options", [])
    values = {o.get("value") for o in opts}
    if any(o.get("range") for o in opts):
        return "Bác nói số, ví dụ «tôi bảy mươi sáu tuổi», hoặc bấm chọn một ô bên dưới."
    if values <= {"yes", "no"}:
        return "Bác trả lời «có» hoặc «không», hoặc bấm chọn một ô bên dưới."
    return "Bác nói câu trả lời, hoặc bấm chọn một ô bên dưới."


def _question_model(q: dict, index: int, total: int) -> FlowQuestion:
    return FlowQuestion(
        id=q["id"], text=q.get("text", ""), hint=_hint_for(q), index=index, total=total,
        options=[FlowOption(value=o["value"], label=o.get("label", o["value"]))
                 for o in q.get("options", [])],
    )


def _option_notes(proc: dict, answers: Dict[str, str]) -> List[str]:
    """Ghi chú gắn với từng lựa chọn bác đã chọn — hiện ở bước 2 như «lưu ý
    theo trường hợp của bác»."""
    notes: List[str] = []
    for q in _questions(proc):
        v = answers.get(q["id"])
        if v is None:
            continue
        for o in q.get("options", []):
            if o.get("value") == v and o.get("note"):
                notes.append(o["note"])
    return notes


def _matched_outcome(proc: dict, answers: Dict[str, str]) -> Optional[dict]:
    for o in _check(proc).get("outcomes") or []:
        if o.get("when") and _cond_ok(o["when"], answers):
            return o
    return None


def _next_question(proc: dict, answers: Dict[str, str]) -> Optional[Tuple[dict, int, int]]:
    """Câu hỏi tiếp theo chưa trả lời mà điều kiện `ask_if` thoả. Trả kèm số
    thứ tự / tổng số câu SẼ hỏi theo các câu trả lời hiện có (để vẽ tiến độ)."""
    askable = [q for q in _questions(proc) if _cond_ok(q.get("ask_if"), answers)]
    for i, q in enumerate(askable):
        if q["id"] not in answers:
            return q, i + 1, len(askable)
    return None


def _source(proc: dict) -> Optional[Source]:
    src = proc.get("source") or {}
    return Source(**src) if src.get("title") else None


def _submit_info(proc: dict) -> dict:
    sub = _flow(proc).get("submit") or {}
    return {
        "places": sub.get("places") or ([proc["where_to_submit"]] if proc.get("where_to_submit") else []),
        "methods": sub.get("methods") or [],
        "bring": sub.get("bring") or proc.get("documents") or [],
        "agency": sub.get("agency"),
        "processing_time": proc.get("processing_time"),
        "result": sub.get("result"),
        "fee": proc.get("fee"),
    }


def _base_state(proc: dict, answers: Dict[str, str], stage: str, step: int) -> FlowState:
    return FlowState(
        procedure_id=proc["id"], procedure_name=proc.get("name", ""),
        stage=stage, step=step, step_title=STEP_TITLES.get(step, ""),
        answers=dict(answers), source=_source(proc),
    )


# ---------------------------------------------------------------------------
# Bước 1
# ---------------------------------------------------------------------------
def evaluate(proc: dict, answers: Dict[str, str], first: bool = False) -> FlowState:
    """Từ các câu đã trả lời, quyết định: hỏi tiếp, dừng (không đáp ứng), hay
    sang bước 2. Gọi lại từ đầu mỗi lượt — không có trạng thái ẩn.

    `first=True` là lượt /flow/start: đọc lời dẫn bước 1 kể cả khi vài câu đã
    được điền sẵn từ lời bác kể."""
    outcome = _matched_outcome(proc, answers)

    if outcome and outcome.get("verdict") != "eligible":
        return _stop_state(proc, answers, outcome)

    if outcome is None:
        nxt = _next_question(proc, answers)
        if nxt is not None:
            return _question_state(proc, answers, *nxt, first=first)
        outcome = _check(proc).get("eligible") or {}

    return _prepare_state(proc, answers, outcome)


def _question_state(proc: dict, answers, q: dict, index: int, total: int,
                    first: bool = False) -> FlowState:
    st = _base_state(proc, answers, "check", 1)
    st.question = _question_model(q, index, total)
    # Câu đầu tiên đọc thêm lời dẫn của bước 1 để bác biết mình đang ở đâu.
    intro = _check(proc).get("intro") if (first or not answers) else None
    st.intro = intro
    st.prompt = q.get("text", "")
    parts = [intro, q.get("text", "")]
    opts = q.get("options", [])
    values = {o.get("value") for o in opts}
    # Câu có/không thì không đọc lựa chọn — bác nghe câu hỏi là đủ. Câu nhiều
    # lựa chọn (tuổi, loại giấy) thì đọc để bác biết mà chọn.
    if not values <= {"yes", "no"} and len(opts) > 2:
        labels = [o.get("label", "") for o in opts]
        parts.append("Bác chọn: " + ", ".join(labels[:-1]) + ", hoặc " + labels[-1] + ".")
    # Câu đầu tiên dặn luôn cách trả lời; các câu sau bác đã quen, không nhắc lại.
    if intro:
        parts.append("Bác trả lời bằng lời, hoặc bấm chọn trên màn hình ạ.")
    st.speech = _spoken(" ".join(p for p in parts if p))
    return st


def _stop_state(proc: dict, answers, outcome: dict) -> FlowState:
    from . import kb  # tránh import vòng
    st = _base_state(proc, answers, "stop", 1)
    st.verdict = outcome.get("verdict", "ineligible")
    st.title = VERDICT_TITLES.get(st.verdict, VERDICT_TITLES["ineligible"])
    st.reason = outcome.get("reason", "")
    st.prompt = st.reason
    sug = outcome.get("suggest")
    if sug:
        sp = kb.get(sug)
        if sp:
            st.suggest_procedure_id = sp["id"]
            st.suggest_procedure_name = sp.get("name")
    st.speech = _spoken(st.reason)
    return st


# ---------------------------------------------------------------------------
# Bước 2
# ---------------------------------------------------------------------------
def _prepare_state(proc: dict, answers, outcome: dict) -> FlowState:
    st = _base_state(proc, answers, "prepare", 2)
    st.verdict = "eligible"
    st.title = STEP_TITLES[2]
    st.note = outcome.get("note") or (_check(proc).get("eligible") or {}).get("note")
    st.documents = (outcome.get("documents")
                    or (_check(proc).get("eligible") or {}).get("documents")
                    or proc.get("documents") or [])
    st.notes = _option_notes(proc, answers)
    prep = _flow(proc).get("prepare") or {}
    st.prompt = prep.get("say") or ""
    st.tips = prep.get("tips") or []
    docs_spoken = " ".join(f"{i + 1}. {d}." for i, d in enumerate(st.documents))
    parts = [st.note, st.prompt, f"Giấy tờ cần chuẩn bị: {docs_spoken}" if docs_spoken else ""]
    parts += st.notes
    st.speech = _spoken(" ".join(p for p in parts if p))
    return st


# ---------------------------------------------------------------------------
# Bước 3 và kết thúc
# ---------------------------------------------------------------------------
def submit_state(proc: dict, answers: Dict[str, str]) -> FlowState:
    st = _base_state(proc, answers, "submit", 3)
    st.title = STEP_TITLES[3]
    info = _submit_info(proc)
    st.places, st.methods, st.bring = info["places"], info["methods"], info["bring"]
    st.agency, st.processing_time = info["agency"], info["processing_time"]
    st.result, st.fee = info["result"], info["fee"]
    st.notes = _option_notes(proc, answers)
    sub = _flow(proc).get("submit") or {}
    st.prompt = sub.get("say") or proc.get("where_to_submit") or ""
    bring_spoken = " ".join(f"{i + 1}. {d}." for i, d in enumerate(st.bring))
    parts = [
        st.prompt,
        f"Khi đi bác mang theo: {bring_spoken}" if bring_spoken else "",
        st.agency,
        f"Thời hạn giải quyết: {st.processing_time}" if st.processing_time else "",
        st.result,
    ]
    st.speech = _spoken(" ".join(p for p in parts if p))
    return st


def done_state(proc: dict, answers: Dict[str, str]) -> FlowState:
    st = _base_state(proc, answers, "done", 3)
    st.title = "Kết thúc"
    st.prompt = DONE_TEXT.format(name=proc.get("name", "này").lower())
    st.speech = _spoken(st.prompt)
    return st


# ---------------------------------------------------------------------------
# Trả lời câu hỏi bước 1 bằng lời nói
# ---------------------------------------------------------------------------
def match_option(q: dict, text: str) -> Optional[str]:
    """Ánh xạ câu bác nói sang một lựa chọn. Trả None nếu không chắc.

    Ba nguồn, theo thứ tự ưu tiên:
      1. Con số trong câu rơi vào `range` của lựa chọn ("bảy mươi sáu tuổi" → 76).
      2. Cụm trong `match` hoặc chính nhãn lựa chọn xuất hiện trong câu.
      3. Câu có/không: từ phủ định thắng từ khẳng định.
    Nhiều lựa chọn cùng khớp thì cụm dài hơn thắng — "không có" (phủ định)
    dài hơn "có" (khẳng định).
    """
    t = normalize(text or "")
    tf = _flat(t)
    if not tf.strip():
        return None
    opts = q.get("options", [])

    if any(o.get("range") for o in opts):
        m = re.search(r"\d+", t)
        if m:
            n = int(m.group())
            # "dưới bảy mươi" nghĩa là 69 trở xuống, không phải 70.
            before = t[:m.start()]
            if re.search(r"(dưới|chưa đến|chưa tới|chưa đầy|chưa được|gần)\s*$", before):
                n -= 1
            for o in opts:
                r = o.get("range")
                if r and r[0] <= n <= r[1]:
                    return o["value"]

    best, best_len = None, 0
    for o in opts:
        phrases = list(o.get("match") or []) + [o.get("label", "")]
        if o.get("value") == "yes":
            phrases += YES_WORDS
        elif o.get("value") == "no":
            phrases += NO_WORDS
        for p in phrases:
            if _contains_phrase(tf, p) and len(_flat(p)) > best_len:
                best, best_len = o["value"], len(_flat(p))
    return best


def prefill_by_rules(proc: dict, utterance: str) -> Dict[str, str]:
    """Điền sẵn điều kiện từ câu bác mở đầu, KHÔNG cần mô hình ngôn ngữ.

    Chỉ dùng hai nguồn chắc chắn: con số rơi vào `range` («tôi 76 tuổi») và cụm
    trong `match` của lựa chọn («không có lương hưu»). KHÔNG dùng từ có/không
    chung chung: «tôi có 76 tuổi» mà điền «công dân = có» là điền bừa.
    """
    t = normalize(utterance or "")
    tf = _flat(t)
    out: Dict[str, str] = {}
    if not tf.strip():
        return out
    for q in _questions(proc):
        opts = q.get("options", [])
        if any(o.get("range") for o in opts):
            m = re.search(r"\d+", t)
            if m:
                n = int(m.group())
                if re.search(r"(dưới|chưa đến|chưa tới|chưa đầy|chưa được|gần)\s*$", t[:m.start()]):
                    n -= 1
                for o in opts:
                    r = o.get("range")
                    if r and r[0] <= n <= r[1]:
                        out[q["id"]] = o["value"]
            continue
        best, best_len = None, 0
        for o in opts:
            for p in o.get("match") or []:
                if _contains_phrase(tf, p) and len(_flat(p)) > best_len:
                    best, best_len = o["value"], len(_flat(p))
        if best:
            out[q["id"]] = best
    return out


def prefilled_list(proc: dict, answers: Dict[str, str]) -> List[dict]:
    """Mô tả các câu đã điền sẵn để giao diện hiện cho bác xem và sửa."""
    items = []
    for q in _questions(proc):
        v = answers.get(q["id"])
        if v is None:
            continue
        for o in q.get("options", []):
            if o.get("value") == v:
                items.append({"question_id": q["id"], "question": q.get("text", ""),
                              "value": v, "label": o.get("label", v)})
    return items


def find_question(proc: dict, qid: str) -> Optional[dict]:
    for q in _questions(proc):
        if q["id"] == qid:
            return q
    return None


# ---------------------------------------------------------------------------
# Hỏi thêm ở bước 2 / bước 3
# ---------------------------------------------------------------------------
# Ý định chung, thủ tục nào cũng có: hỏi nơi nộp, thời gian, phí, giấy tờ.
# Tra sau FAQ riêng của thủ tục, vì FAQ riêng cụ thể hơn.
_GENERIC_INTENTS = [
    ("where", ["ở đâu", "nộp đâu", "chỗ nào", "nơi nào", "đến đâu", "nộp ở"]),
    ("time", ["bao lâu", "mấy ngày", "khi nào", "bao giờ", "thời gian", "thời hạn", "lâu không"]),
    ("fee", ["phí", "lệ phí", "bao nhiêu tiền", "mất tiền", "tốn tiền", "miễn phí"]),
    ("docs", ["giấy tờ", "mang gì", "mang theo", "chuẩn bị gì", "hồ sơ gồm", "cần gì"]),
]


def _faq_score(query_flat: str, variant: str) -> float:
    vf = _flat(variant)
    if not vf.strip():
        return 0.0
    if vf in query_flat:
        return 1.0
    v_tokens = set(vf.split())
    q_tokens = set(query_flat.split())
    return len(v_tokens & q_tokens) / len(v_tokens)


def answer_question(proc: dict, text: str) -> FlowAskResult:
    """Trả lời câu hỏi thêm CHỈ từ kho tri thức của thủ tục đang làm.

    Không bịa. Không khớp gì thì mời bác hỏi cán bộ. Nếu câu hỏi lại khớp
    rõ với một thủ tục KHÁC thì gợi ý chuyển, để bác không bị kẹt trong luồng
    sai.
    """
    from . import kb  # tránh import vòng
    q = normalize(text or "")
    qf = _flat(q)
    res = FlowAskResult(procedure_id=proc["id"], question=q)

    if not qf.strip():
        res.matched, res.answer = False, ASK_NO_SPEECH_TEXT
        res.speech = for_speech(res.answer)
        return res

    best_a, best_s = None, 0.0
    for item in _flow(proc).get("faq") or []:
        for variant in item.get("q") or []:
            s = _faq_score(qf, variant)
            if s > best_s:
                best_s, best_a = s, item.get("a")
    if best_a and best_s >= config.FAQ_MATCH_THRESHOLD:
        res.matched, res.answer, res.match_score = True, best_a, round(best_s, 3)
        res.speech = _spoken(res.answer)
        return res

    # Câu hỏi có vẻ thuộc thủ tục khác? Chỉ gợi ý khi khớp rõ, và khớp thủ
    # tục khác hơn hẳn thủ tục đang làm. Xét TRƯỚC ý định chung: "làm căn
    # cước cần giấy tờ gì" hỏi giữa lúc làm trợ cấp thì phải gợi ý chuyển,
    # không được đem giấy tờ của trợ cấp ra trả lời.
    other, s_other = kb.search(q)
    if other and other["id"] != proc["id"] and s_other >= config.KB_MATCH_THRESHOLD \
            and s_other > kb.score(q, proc) + 0.2:
        res.switch_to, res.switch_name = other["id"], other.get("name")
        res.answer = (f"Câu này có vẻ thuộc thủ tục «{other.get('name')}», khác thủ tục bác đang làm. "
                      f"Bác muốn chuyển sang thủ tục đó không ạ?")
        res.speech = for_speech(res.answer)
        return res

    info = _submit_info(proc)
    for intent, phrases in _GENERIC_INTENTS:
        if any(_contains_phrase(qf, p) for p in phrases):
            if intent == "where" and info["places"]:
                ans = "Bác nộp tại: " + "; ".join(info["places"]) + "."
            elif intent == "time" and info["processing_time"]:
                ans = "Thời hạn giải quyết: " + info["processing_time"]
            elif intent == "fee" and info["fee"]:
                ans = info["fee"]
            elif intent == "docs" and info["bring"]:
                ans = "Bác mang theo: " + "; ".join(info["bring"]) + "."
            else:
                continue
            res.matched, res.answer, res.match_score = True, ans, 0.5
            res.speech = _spoken(ans)
            return res

    res.matched, res.answer = False, ASK_FALLBACK_TEXT
    res.speech = for_speech(res.answer)
    return res


# ---------------------------------------------------------------------------
# Mọi câu máy có thể đọc — để sinh sẵn tiếng lúc khởi động
# ---------------------------------------------------------------------------
def all_speech_texts(proc: dict) -> List[str]:
    """Liệt kê mọi chuỗi `speech` mà luồng của một thủ tục có thể trả về.

    Câu hỏi được sinh cả hai kiểu (có lời dẫn / không) vì câu đầu tiên có lời
    dẫn còn các câu sau thì không. Kết luận, bước 2 mặc định, bước 3, kết thúc
    và FAQ đều có. Bước 2 theo từng tổ hợp lựa chọn thì không liệt kê hết —
    bác nào rơi vào đó chịu chậm 1–2 giây một lần, cache giữ cho lần sau.
    """
    texts: List[str] = []
    qs = _questions(proc)
    for i, q in enumerate(qs):
        texts.append(_question_state(proc, {} if i == 0 else {"_": "x"}, q, 1, 1).speech)
    for o in _check(proc).get("outcomes") or []:
        if o.get("verdict") != "eligible":
            texts.append(_stop_state(proc, {}, o).speech)
        else:
            texts.append(_prepare_state(proc, {}, o).speech)
    texts.append(_prepare_state(proc, {}, _check(proc).get("eligible") or {}).speech)
    texts.append(submit_state(proc, {}).speech)
    texts.append(done_state(proc, {}).speech)
    for item in _flow(proc).get("faq") or []:
        if item.get("a"):
            texts.append(_spoken(item["a"]))
    texts += [for_speech(NOT_UNDERSTOOD_TEXT), for_speech(ASK_FALLBACK_TEXT),
              for_speech(ASK_NO_SPEECH_TEXT)]
    return texts
