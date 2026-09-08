"""Máy chủ FastAPI. Bước 5 và bước 8 trong checklist.

Chạy máy cá nhân:
    uvicorn app.main:app --reload

Chạy chế độ giả cho Kns:
    MOCK=1 uvicorn app.main:app --reload

Mở http://localhost:8000/docs để bấm thử từng đường dẫn.
"""

from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config, kb
from .asr import AsrError, is_ready, load_model, transcribe_bytes
from .schemas import (AnswerRequest, AnswerResult, AsrResult, HealthResult,
                      TurnResult)

if config.MOCK:
    from .mock import mock_answer, mock_asr

_started = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    kb.load_kb()
    if not config.MOCK and config.ASR_EAGER_LOAD:
        load_model()
    yield


app = FastAPI(
    title="Kiosk hướng dẫn thủ tục hành chính — API",
    description="Xem API_CONTRACT.md. Bấm thử trực tiếp ở trang này.",
    version="1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _err(message: str, code: str, status: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"ok": False, "error": message, "code": code})


# Câu hiển thị cho người dân khi giao diện gửi lên sai định dạng. Cố ý không
# nói gì về kỹ thuật: người đứng trước kiosk không sửa được lỗi lập trình,
# chỉ cần biết máy chưa nhận được câu hỏi.
BAD_REQUEST_TEXT = "Máy chưa nhận được câu hỏi của bác. Bác thử lại giúp con."


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request,
                                   exc: RequestValidationError) -> JSONResponse:
    """Ép lỗi kiểm tra dữ liệu về đúng định dạng đã cam kết trong giao kèo.

    Mặc định FastAPI trả `{"detail": [...]}`, không có `ok`, không có `error`,
    và `msg` bằng tiếng Anh. Trong khi API_CONTRACT.md hứa MỌI phản hồi đều có
    `ok`, và khi `ok = false` thì `error` là câu tiếng Việt hiển thị thẳng cho
    người dân được. Giao diện làm đúng theo giao kèo mà đọc `data.error` sẽ ra
    `undefined`, và người dân nhìn thấy chữ đó trên màn hình kiosk.

    Phần kỹ thuật không vứt đi, chuyển sang trường `detail` để Kns gỡ lỗi.
    """
    parts = []
    for e in exc.errors():
        # loc thường là ("body", "audio"). Bỏ phần "body" cho gọn.
        field = ".".join(str(x) for x in e.get("loc", ()) if x != "body")
        parts.append(f"{field or '?'}: {e.get('msg', '')}")

    return JSONResponse(
        status_code=422,
        content={"ok": False, "error": BAD_REQUEST_TEXT, "code": "bad_request",
                 "detail": "; ".join(parts)},
    )


def _log_turn(payload: dict) -> None:
    """Nhật ký hội thoại — tính năng số 5 ở mục 3.2, và là dữ liệu để cải tiến.
    Chỉ ghi văn bản, không bao giờ ghi âm thanh."""
    if not config.LOG_TRANSCRIPTS:
        return
    try:
        config.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with config.LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), **payload}, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        print(f"[log] không ghi được: {exc}")


# ---------------------------------------------------------------------------
@app.get("/health", response_model=HealthResult)
def health():
    """Máy chủ còn sống không. Dùng luôn cho việc gọi định kỳ chống ngủ đông."""
    return HealthResult(
        asr_ready=config.MOCK or is_ready(),
        asr_model="mock" if config.MOCK else config.ASR_MODEL_LABEL,
        kb_procedures=kb.count(),
        mock=config.MOCK,
        uptime_seconds=round(time.time() - _started, 1),
    )


@app.post("/warmup")
def warmup():
    """Nạp trước mô hình. Gọi cái này khoảng 5 phút trước giờ giám khảo mở,
    để lần bấm đầu tiên của họ không phải chờ nạp mô hình."""
    if config.MOCK:
        return {"ok": True, "warm": True, "mock": True}
    t0 = time.time()
    load_model()
    return {"ok": True, "warm": is_ready(), "seconds": round(time.time() - t0, 1)}


@app.post("/kb/reload")
def kb_reload():
    """Nạp lại 6 file JSON sau khi Mian sửa nội dung, không phải khởi động lại."""
    return {"ok": True, "procedures": len(kb.load_kb())}


# ---------------------------------------------------------------------------
@app.post("/asr", response_model=AsrResult)
async def asr_endpoint(
    audio: UploadFile = File(..., description="webm / wav / mp3 / m4a / ogg"),
    normalize: bool = Form(True),
):
    if config.MOCK:
        return mock_asr()

    data = await audio.read()
    if len(data) > config.MAX_AUDIO_MB * 1024 * 1024:
        return _err(f"File âm thanh nặng quá {config.MAX_AUDIO_MB:.0f} MB.", "audio_too_large")
    if not data:
        return _err("Không nhận được dữ liệu âm thanh.", "audio_unreadable")

    try:
        return transcribe_bytes(data, audio.filename or "audio.webm", do_normalize=normalize)
    except AsrError as exc:
        return _err(exc.message, exc.code, 503 if exc.code == "asr_not_ready" else 400)
    except Exception as exc:  # noqa: BLE001
        print(f"[asr] lỗi không lường trước: {exc}")
        return _err("Máy đang bận, bác thử lại giúp con.", "internal_error", 500)


@app.post("/answer", response_model=AnswerResult)
def answer_endpoint(req: AnswerRequest):
    if config.MOCK:
        return mock_answer()
    if not req.text.strip():
        return kb.retry_answer()
    result = kb.build_answer(req.text, req.session_id)
    _log_turn({"session": req.session_id, "query": req.text,
               "procedure": result.procedure_id, "score": result.match_score,
               "handoff": result.handoff})
    return result


@app.post("/turn", response_model=TurnResult)
async def turn_endpoint(
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
):
    """Một lượt trọn vẹn: âm thanh vào, hướng dẫn ra. Giao diện dùng đường này."""
    t0 = time.time()

    if config.MOCK:
        a = mock_asr()
        ans = kb.retry_answer() if a.no_speech else mock_answer()
        return TurnResult(asr=a, answer=ans,
                          total_latency_seconds=round(time.time() - t0, 2))

    data = await audio.read()
    if len(data) > config.MAX_AUDIO_MB * 1024 * 1024:
        return _err(f"File âm thanh nặng quá {config.MAX_AUDIO_MB:.0f} MB.", "audio_too_large")

    try:
        a = transcribe_bytes(data, audio.filename or "audio.webm")
    except AsrError as exc:
        return _err(exc.message, exc.code, 503 if exc.code == "asr_not_ready" else 400)
    except Exception as exc:  # noqa: BLE001
        print(f"[turn] lỗi không lường trước: {exc}")
        return _err("Máy đang bận, bác thử lại giúp con.", "internal_error", 500)

    # Nghe không ra tiếng, hoặc nghe được nhưng độ tin cậy quá thấp:
    # mời bác nói lại, KHÔNG chuyển cán bộ vội. Chuyển cán bộ chỉ dành cho
    # trường hợp nghe rõ nhưng không có thủ tục nào khớp.
    if a.no_speech or a.confidence < config.ASR_CONFIDENCE_FLOOR:
        ans = kb.retry_answer()
    else:
        ans = kb.build_answer(a.text, session_id)

    _log_turn({"session": session_id, "raw": a.text_raw, "norm": a.text,
               "asr_conf": a.confidence, "procedure": ans.procedure_id,
               "score": ans.match_score, "handoff": ans.handoff,
               "asr_latency": a.latency_seconds})

    return TurnResult(asr=a, answer=ans,
                      total_latency_seconds=round(time.time() - t0, 2))
