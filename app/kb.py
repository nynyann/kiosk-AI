"""Kho tri thức 6 thủ tục + tra cứu.

CHIA VIỆC: file này là phần của Kim (bước 9, 10, 11, 12). Lia dựng sẵn khung
để `/answer` và `/turn` chạy được từ hôm nay, Kim thay ruột hàm `search()` và
`build_answer()` mà không phải động vào `main.py`.

Bản tạm này tra cứu bằng từ khoá + so trùng token. Đã đủ đúng cho 6 thủ tục.
Kim thêm so khớp ngữ nghĩa (sentence-transformers) thì chỉ cần sửa `score()`.

Định dạng file JSON xem `data/kb/_SCHEMA.md`.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Dict, List, Tuple

from . import config
from .normalize import for_speech, normalize
from .schemas import AnswerResult, Source, Step

_PROCEDURES: List[dict] = []


def _flat(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").replace("đ", "d")


def load_kb() -> List[dict]:
    """Nạp mọi file .json trong data/kb. Gọi lại được để nạp nóng khi Mian sửa."""
    global _PROCEDURES
    items: List[dict] = []
    if config.KB_DIR.exists():
        for f in sorted(config.KB_DIR.glob("*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                d.setdefault("id", f.stem)
                items.append(d)
            except Exception as exc:  # noqa: BLE001
                print(f"[kb] Hỏng file {f.name}: {exc}")
    _PROCEDURES = items
    print(f"[kb] Đã nạp {len(items)} thủ tục")
    return items


def count() -> int:
    return len(_PROCEDURES)


def get(procedure_id: str) -> dict | None:
    """Một thủ tục theo mã (tên file). None nếu không có."""
    for p in _PROCEDURES:
        if p.get("id") == procedure_id:
            return p
    return None


def summaries() -> List[dict]:
    """Danh sách ngắn để vẽ nút chọn thủ tục ở màn hình chính."""
    return [{"id": p["id"], "name": p.get("name", p["id"]), "short": p.get("short")}
            for p in _PROCEDURES]


# ---------------------------------------------------------------------------
def score(query: str, proc: dict) -> float:
    """Điểm khớp 0–1 giữa câu hỏi và một thủ tục.

    Ba nguồn điểm, cộng có trọng số:
      - từ khoá trong `keywords` xuất hiện trong câu hỏi   (nặng nhất)
      - tên thủ tục và các cách gọi khác trùng token
      - token trùng với phần nội dung

    Kim: chỗ thay thành so khớp ngữ nghĩa là ở đây. Giữ nguyên chữ ký hàm.
    """
    q = _flat(query)
    q_tokens = set(q.split())

    names = [proc.get("name", "")] + proc.get("aliases", [])

    # Cách người dân gọi thủ tục cũng tính như từ khoá. Nếu câu hỏi chứa trọn
    # một cách gọi trong `aliases` thì gần như chắc chắn là thủ tục này —
    # không cho nó rơi xuống dưới ngưỡng chuyển cán bộ.
    phrases = proc.get("keywords", []) + names
    kw_hit = sum(1 for k in phrases if k and _flat(k) in q)
    kw_score = min(kw_hit / 2.0, 1.0)
    exact_phrase = any(k and _flat(k) in q and len(_flat(k).split()) >= 2 for k in names)

    name_score = 0.0
    for n in names:
        n_tokens = set(_flat(n).split())
        if n_tokens:
            name_score = max(name_score, len(n_tokens & q_tokens) / len(n_tokens))

    body = " ".join(
        [proc.get("name", "")]
        + [s.get("title", "") + " " + s.get("detail", "") for s in proc.get("steps", [])]
        + proc.get("documents", [])
    )
    body_tokens = set(_flat(body).split())
    body_score = len(body_tokens & q_tokens) / max(len(q_tokens), 1)

    total = 0.55 * kw_score + 0.35 * name_score + 0.10 * body_score
    if exact_phrase:
        total = max(total, 0.80)
    return round(min(total, 1.0), 3)


def search(query: str) -> Tuple[dict | None, float]:
    """Trả (thủ tục khớp nhất, điểm). Trả (None, 0.0) nếu kho rỗng."""
    if not _PROCEDURES:
        return None, 0.0
    q = normalize(query)
    ranked = sorted(((score(q, p), p) for p in _PROCEDURES), key=lambda x: x[0], reverse=True)
    best_score, best = ranked[0]
    return best, best_score


# ---------------------------------------------------------------------------
HANDOFF_TEXT = "Câu này cháu chưa được học ạ. Cháu mời bác gặp cán bộ ở quầy số 1, hoặc bác bấm chọn một thủ tục trên màn hình."
RETRY_TEXT = "Cháu chưa nghe rõ ạ. Bác nói lại giúp cháu một lần nữa."


def build_answer(query: str, session_id: str | None = None) -> AnswerResult:
    """Sinh câu trả lời từ mẫu câu ghép với nội dung tra cứu được.

    CẤM sinh thông tin không có trong kho. Mọi câu chữ trong `answer` và
    `steps` đều phải lấy nguyên từ file JSON — đây là điều kiện nghiệm thu
    ở bước 11: đọc 20 câu trả lời, không câu nào nhắc tới giấy tờ không có
    trong kho.
    """
    proc, s = search(query)

    if proc is None or s < config.KB_MATCH_THRESHOLD:
        return AnswerResult(
            handoff=True, match_score=s, answer=HANDOFF_TEXT,
            speech=for_speech(HANDOFF_TEXT),
        )

    steps = [
        Step(order=i + 1, title=st.get("title", ""), detail=st.get("detail", ""))
        for i, st in enumerate(proc.get("steps", []))
    ]
    lead = _lead_for(proc, len(steps))
    src = proc.get("source") or {}
    spoken = _spoken_for(proc, steps, lead)

    return AnswerResult(
        handoff=False,
        procedure_id=proc.get("id"),
        procedure_name=proc.get("name"),
        match_score=s,
        answer=lead,
        steps=steps,
        documents=proc.get("documents", []),
        where_to_submit=proc.get("where_to_submit"),
        fee=proc.get("fee"),
        processing_time=proc.get("processing_time"),
        source=Source(**src) if src.get("title") else None,
        speech=for_speech(spoken),
        confirm=for_speech(confirm_text(proc)),
    )


def retry_answer() -> AnswerResult:
    """Trả về khi ASR không nghe ra tiếng. Khác câu chuyển cán bộ."""
    return AnswerResult(handoff=True, match_score=0.0,
                        answer=RETRY_TEXT, speech=for_speech(RETRY_TEXT))


def _lead_for(proc: dict, n_steps: int) -> str:
    return f"Để {proc.get('name', 'làm thủ tục này').lower()}, bác cần làm {n_steps} bước sau."


def _spoken_for(proc: dict, steps, lead: str) -> str:
    spoken = lead + " " + " ".join(
        f"Bước {st.order}. {st.title}. {st.detail}" for st in steps
    )
    if proc.get("where_to_submit"):
        spoken += f" Bác nộp tại {proc['where_to_submit']}"
    return spoken


def confirm_text(proc: dict) -> str:
    """Câu máy nói khi đã nhận ra thủ tục, trước khi vào bước 1."""
    return f"Cháu hiểu bác cần làm thủ tục {proc.get('name', '')}. Đúng không ạ?"


def all_speech_texts() -> List[str]:
    """Mọi chuỗi `speech` mà máy chủ có thể trả về.

    Dùng để sinh sẵn file tiếng lúc khởi động. Gồm câu xác nhận thủ tục, câu
    trả lời một lượt của /answer (giữ cho giao diện cũ), và toàn bộ câu của
    luồng từng bước (câu hỏi, kết luận, bước 2, bước 3, FAQ). Chừng 120 câu
    cho 6 thủ tục, chạy nền nên không làm chậm khởi động.
    """
    from . import flow  # tránh import vòng
    texts = [for_speech(HANDOFF_TEXT), for_speech(RETRY_TEXT)]
    # Giao diện KHÔNG chuẩn hoá câu chào qua for_speech (nó phát nguyên chuỗi
    # của nó), nên ở đây cũng để nguyên để khoá bộ đệm khớp nhau.
    texts += list(flow.UI_TEXTS)
    for proc in _PROCEDURES:
        texts.append(for_speech(confirm_text(proc)))
        texts += flow.all_speech_texts(proc)
        steps = [
            Step(order=i + 1, title=st.get("title", ""), detail=st.get("detail", ""))
            for i, st in enumerate(proc.get("steps", []))
        ]
        texts.append(for_speech(_spoken_for(proc, steps, _lead_for(proc, len(steps)))))
    return texts
