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
HANDOFF_TEXT = "Câu này con chưa được học ạ. Con mời bác gặp cán bộ ở quầy số 1."
RETRY_TEXT = "Con chưa nghe rõ ạ. Bác nói lại giúp con một lần nữa."


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


def all_speech_texts() -> List[str]:
    """Mọi chuỗi `speech` mà máy chủ có thể trả về.

    Dùng để sinh sẵn file tiếng lúc khởi động. Kho chỉ có vài chục thủ tục nên
    danh sách này ngắn, mà đổi lại người dân đầu tiên trong ngày không phải
    ngồi nhìn màn hình im lặng 2-3 giây chờ máy sinh tiếng.
    """
    texts = [for_speech(HANDOFF_TEXT), for_speech(RETRY_TEXT)]
    for proc in _PROCEDURES:
        steps = [
            Step(order=i + 1, title=st.get("title", ""), detail=st.get("detail", ""))
            for i, st in enumerate(proc.get("steps", []))
        ]
        texts.append(for_speech(_spoken_for(proc, steps, _lead_for(proc, len(steps)))))
    return texts
