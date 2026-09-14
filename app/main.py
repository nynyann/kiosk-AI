"""Máy chủ FastAPI. Bước 5 và bước 8 trong checklist.

Từ API 2.0 có thêm luồng từng bước (/procedures, /flow/*) — xem app/flow.py.

Chạy máy cá nhân:
    uvicorn app.main:app --reload

Chạy chế độ giả cho Kns:
    MOCK=1 uvicorn app.main:app --reload

Mở http://localhost:8000/docs để bấm thử từng đường dẫn.
"""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import config, flow, kb, tts
from .asr import AsrError, is_ready, last_error, load_model, transcribe_bytes
from .schemas import (AnswerRequest, AnswerResult, AsrResult, FlowAnswerRequest,
                      FlowAskResult, FlowNextRequest, FlowStartRequest, FlowState,
                      HealthResult, ProceduresResult, TtsRequest, TurnResult)

if config.MOCK:
    from .mock import mock_asr

_started = time.time()


async def _prewarm_tts() -> None:
    """Sinh sẵn file tiếng cho mọi câu trả lời có trong kho.

    Không sinh sẵn thì người đầu tiên hỏi mỗi thủ tục phải nhìn màn hình im
    lặng khoảng 2,5 giây trong lúc máy gọi ra ngoài lấy tiếng — đo được ở
    trình duyệt. Sau khi có sẵn, lấy từ bộ đệm chỉ mất vài mili-giây.

    Chạy nền, KHÔNG chặn lúc khởi động: mất mạng thì máy chủ vẫn phải lên,
    cùng lắm là câu đầu chậm như cũ.
    """
    texts = list(dict.fromkeys(t for t in kb.all_speech_texts() if t))

    ok = 0
    for text in texts:
        # Thử lại vài lần: dịch vụ giọng đọc lúc nguội hay hỏng nhất thời
        # (NoAudioReceived sau vài giây) hoặc chậm bất thường, mà hỏng ở đây
        # thì lượt hỏi thật phải chờ sinh lại từ đầu.
        for lan in range(1, config.TTS_PREWARM_ATTEMPTS + 1):
            try:
                await tts.synthesize(text, timeout=config.TTS_PREWARM_TIMEOUT_SECONDS)
                ok += 1
                break
            except tts.TtsError as exc:
                if lan == config.TTS_PREWARM_ATTEMPTS:
                    print(f"[tts] chưa sinh sẵn được một câu ({exc.code}): {text[:40]}…")
    print(f"[tts] đã sinh sẵn {ok}/{len(texts)} câu, giọng {config.TTS_VOICE}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    kb.load_kb()
    if not config.MOCK and config.ASR_EAGER_LOAD:
        load_model()
    warm_task = None
    if config.TTS_ENABLED and config.TTS_PREWARM:
        warm_task = asyncio.create_task(_prewarm_tts())
    yield
    if warm_task and not warm_task.done():
        warm_task.cancel()


app = FastAPI(
    title="Kiosk hướng dẫn thủ tục hành chính — API",
    description="Xem API_CONTRACT.md. Bấm thử trực tiếp ở trang này.",
    version="2.0",
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
BAD_REQUEST_TEXT = "Máy chưa nhận được câu hỏi của bác. Bác thử lại giúp cháu."


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
        # Nói luôn vì sao chưa sẵn sàng. Không có trường này thì đứng trước
        # `asr_ready: false` chỉ biết đoán, mà log máy chủ thì không phải ai
        # trong nhóm cũng mở được.
        asr_error=None if (config.MOCK or is_ready()) else last_error(),
        kb_procedures=kb.count(),
        mock=config.MOCK,
        uptime_seconds=round(time.time() - _started, 1),
        tts_ready=config.TTS_ENABLED,
        tts_voice=config.TTS_VOICE if config.TTS_ENABLED else None,
    )


@app.post("/warmup")
def warmup():
    """Nạp trước mô hình. Gọi cái này khoảng 5 phút trước giờ giám khảo mở,
    để lần bấm đầu tiên của họ không phải chờ nạp mô hình."""
    if config.MOCK:
        return {"ok": True, "warm": True, "mock": True}
    t0 = time.time()
    # retry=True: gọi tay /warmup là cố ý muốn thử lại, kể cả lần trước đã hỏng.
    load_model(retry=True)
    out = {"ok": True, "warm": is_ready(), "seconds": round(time.time() - t0, 1)}
    if not is_ready():
        out["error"] = last_error() or "không rõ lý do"
    return out


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
        return _err("Máy đang bận, bác thử lại giúp cháu.", "internal_error", 500)


@app.post("/answer", response_model=AnswerResult)
def answer_endpoint(req: AnswerRequest):
    # Chế độ giả chỉ giả phần NGHE; kho tri thức không cần mô hình nên tra
    # thật luôn, để giao diện demo thấy đúng thủ tục ứng với câu đã "nghe".
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
        ans = kb.retry_answer() if a.no_speech else kb.build_answer(a.text, session_id)
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
        return _err("Máy đang bận, bác thử lại giúp cháu.", "internal_error", 500)

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


# --- Luồng từng bước (API 2.0) ---------------------------------------------
# Bước 1 kiểm tra điều kiện → bước 2 chuẩn bị hồ sơ → bước 3 nộp hồ sơ.
# Máy chủ không giữ phiên: giao diện gửi lại `answers` mỗi lượt. Nội dung
# hỏi/đáp nằm trong data/kb/*.json mục `flow`, máy chạy ở app/flow.py.

def _proc_or_err(procedure_id: str):
    proc = kb.get(procedure_id)
    if proc is None:
        return None, _err("Cháu chưa có thủ tục này trong kho. Bác chọn thủ tục khác giúp cháu.",
                          "procedure_not_found", 404)
    return proc, None


def _clean_answers(answers) -> dict:
    """Chỉ nhận cặp chuỗi → chuỗi, bỏ rác nếu giao diện gửi sai kiểu."""
    if not isinstance(answers, dict):
        return {}
    return {str(k): str(v) for k, v in answers.items() if v is not None}


async def _read_audio(audio: UploadFile):
    """Đọc và nhận dạng một file âm thanh. Trả (AsrResult, None) hoặc (None, lỗi)."""
    if config.MOCK:
        return mock_asr(), None
    data = await audio.read()
    if len(data) > config.MAX_AUDIO_MB * 1024 * 1024:
        return None, _err(f"File âm thanh nặng quá {config.MAX_AUDIO_MB:.0f} MB.", "audio_too_large")
    if not data:
        return None, _err("Không nhận được dữ liệu âm thanh.", "audio_unreadable")
    try:
        return transcribe_bytes(data, audio.filename or "audio.webm"), None
    except AsrError as exc:
        return None, _err(exc.message, exc.code, 503 if exc.code == "asr_not_ready" else 400)
    except Exception as exc:  # noqa: BLE001
        print(f"[flow] lỗi không lường trước: {exc}")
        return None, _err("Máy đang bận, bác thử lại giúp cháu.", "internal_error", 500)


@app.get("/procedures", response_model=ProceduresResult)
def procedures():
    """Danh sách thủ tục để vẽ nút chọn ở màn hình chính. Bác không nói được
    hoặc máy nghe không ra thì vẫn bấm chọn được."""
    return ProceduresResult(procedures=kb.summaries())


@app.post("/flow/start", response_model=FlowState)
def flow_start(req: FlowStartRequest):
    """Vào bước 1 của một thủ tục. Trả câu hỏi đầu tiên (hoặc thẳng bước 2
    nếu thủ tục không có câu hỏi điều kiện)."""
    proc, err = _proc_or_err(req.procedure_id)
    if err:
        return err
    st = flow.evaluate(proc, {})
    _log_turn({"session": req.session_id, "flow": "start", "procedure": proc["id"]})
    return st


@app.post("/flow/answer", response_model=FlowState)
def flow_answer(req: FlowAnswerRequest):
    """Bác bấm chọn một lựa chọn. Gộp vào `answers` rồi tính trạng thái tiếp."""
    proc, err = _proc_or_err(req.procedure_id)
    if err:
        return err
    if flow.find_question(proc, req.question_id) is None:
        return _err(BAD_REQUEST_TEXT, "bad_request", 400)
    answers = _clean_answers(req.answers)
    answers[req.question_id] = req.value
    st = flow.evaluate(proc, answers)
    _log_turn({"session": req.session_id, "flow": "answer", "procedure": proc["id"],
               "question": req.question_id, "value": req.value, "stage": st.stage,
               "verdict": st.verdict})
    return st


@app.post("/flow/answer-voice", response_model=FlowState)
async def flow_answer_voice(
    audio: UploadFile = File(...),
    procedure_id: str = Form(...),
    question_id: str = Form(...),
    answers: str = Form("{}"),
    session_id: Optional[str] = Form(None),
):
    """Bác trả lời câu hỏi bước 1 bằng lời. Nghe → ánh xạ sang lựa chọn →
    như /flow/answer. Không ánh xạ được thì trả lại câu hỏi cũ với
    `matched = false` để bác bấm chọn."""
    proc, err = _proc_or_err(procedure_id)
    if err:
        return err
    q = flow.find_question(proc, question_id)
    if q is None:
        return _err(BAD_REQUEST_TEXT, "bad_request", 400)
    try:
        prev = json.loads(answers or "{}")
    except ValueError:
        prev = {}
    prev = _clean_answers(prev)

    a, err = await _read_audio(audio)
    if err:
        return err

    value = None
    if not a.no_speech and a.confidence >= config.ASR_CONFIDENCE_FLOOR:
        value = flow.match_option(q, a.text)

    if value is None:
        # Giữ nguyên câu hỏi, chỉ báo là chưa hiểu.
        st = flow.evaluate(proc, prev)
        st.asr, st.matched = a, False
        st.message = kb.RETRY_TEXT if a.no_speech else flow.NOT_UNDERSTOOD_TEXT
        st.speech = flow.for_speech(st.message)
    else:
        prev[question_id] = value
        st = flow.evaluate(proc, prev)
        st.asr, st.matched = a, True

    _log_turn({"session": session_id, "flow": "answer-voice", "procedure": proc["id"],
               "question": question_id, "raw": a.text_raw, "norm": a.text,
               "asr_conf": a.confidence, "value": value, "stage": st.stage})
    return st


@app.post("/flow/next", response_model=FlowState)
def flow_next(req: FlowNextRequest):
    """Bác bấm «Tiếp tục»: từ bước 2 sang bước 3, từ bước 3 sang kết thúc.
    `stage = "check"` thì tính lại bước 1 từ `answers` — dùng cho nút «Quay
    lại» (giao diện bỏ câu trả lời cuối rồi gửi lên)."""
    proc, err = _proc_or_err(req.procedure_id)
    if err:
        return err
    answers = _clean_answers(req.answers)
    if req.stage == "check":
        st = flow.evaluate(proc, answers)
    elif req.stage == "prepare":
        st = flow.submit_state(proc, answers)
    elif req.stage == "submit":
        st = flow.done_state(proc, answers)
    else:
        return _err(BAD_REQUEST_TEXT, "bad_request", 400)
    _log_turn({"session": req.session_id, "flow": "next", "procedure": proc["id"],
               "from": req.stage, "stage": st.stage})
    return st


@app.post("/flow/ask", response_model=FlowAskResult)
async def flow_ask(
    procedure_id: str = Form(...),
    audio: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
):
    """Hỏi thêm trong bước 2 / bước 3. Gửi `audio` (nói) hoặc `text` (gõ).
    Chỉ trả lời từ kho tri thức của thủ tục đang làm; không có thì mời hỏi
    cán bộ, và gợi ý chuyển nếu câu hỏi thuộc thủ tục khác."""
    proc, err = _proc_or_err(procedure_id)
    if err:
        return err

    a: Optional[AsrResult] = None
    if audio is not None:
        a, err = await _read_audio(audio)
        if err:
            return err
        text = "" if (a.no_speech or a.confidence < config.ASR_CONFIDENCE_FLOOR) else a.text
    elif text is None:
        return _err(BAD_REQUEST_TEXT, "bad_request", 400)

    res = flow.answer_question(proc, text)
    res.asr = a
    _log_turn({"session": session_id, "flow": "ask", "procedure": proc["id"],
               "query": res.question, "matched": res.matched, "score": res.match_score,
               "switch_to": res.switch_to})
    return res


# ---------------------------------------------------------------------------
@app.post("/tts")
async def tts_endpoint(req: TtsRequest):
    """Đọc một đoạn chữ thành tiếng Việt, trả về mp3.

    Giao diện gọi cái này với chuỗi `speech` mà /answer và /turn đã trả về.
    Không gộp sẵn mp3 vào phản hồi /turn vì hai lý do: nhồi mp3 base64 vào JSON
    làm phản hồi phình gấp mấy lần, và màn hình chữ hiện được ngay trong lúc
    tiếng còn đang sinh — người dân đọc trước, nghe sau, không phải chờ cả hai.
    """
    if not config.TTS_ENABLED:
        return _err("Máy chủ đang tắt phần đọc thành tiếng.", "tts_disabled", 503)
    try:
        audio = await tts.synthesize(req.text, req.voice)
    except tts.TtsError as exc:
        return _err(exc.message, exc.code,
                    400 if exc.code in ("bad_request", "text_too_long") else 503)

    # Cho trình duyệt giữ lại: cùng một câu trả lời thì cùng một file tiếng.
    return Response(content=audio, media_type="audio/mpeg",
                    headers={"Cache-Control": "public, max-age=86400"})


# --- Giao diện kiosk --------------------------------------------------------
# Chính máy chủ này phục vụ luôn trang kiosk ở "/". Nhờ vậy giao diện và API
# nằm cùng một origin: không vướng CORS, giao diện không phải ghi cứng địa chỉ
# máy chủ, và lúc triển khai chỉ có một dịch vụ phải dựng thay vì hai.
#
# Mount đặt ở CUỐI file, sau khi đã khai báo hết các đường dẫn API. FastAPI dò
# route theo thứ tự khai báo, nên /health /asr /answer /turn /docs /openapi.json
# vẫn được khớp trước; chỉ những đường dẫn còn lại mới rơi vào thư mục web/.
#
# html=True để "/" trả về index.html.
WEB_DIR = config.BASE_DIR / "web"
if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
else:
    print(f"[main] không thấy thư mục {WEB_DIR}, chỉ chạy API, không có giao diện.")
