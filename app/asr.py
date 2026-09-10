"""Nhận dạng giọng nói. Bước 6 trong checklist.

Nạp PhoWhisper qua faster-whisper, nhận file âm thanh, trả văn bản kèm điểm
tin cậy và thời gian xử lý.

MỘT CÁI BẪY PHẢI BIẾT TRƯỚC
---------------------------
PhoWhisper trên HuggingFace (`vinai/PhoWhisper-small`) là checkpoint định dạng
transformers. faster-whisper chạy trên CTranslate2 nên KHÔNG nạp thẳng được.
Phải chuyển một lần bằng `scripts/convert_phowhisper.sh`, mất khoảng 2 phút.
Nếu bỏ qua bước này, lỗi báo ra rất khó hiểu ("model not found" hoặc lỗi tệp
model.bin), đừng mất buổi tối để mò.

ĐIỂM TIN CẬY LẤY TỪ ĐÂU
-----------------------
faster-whisper trả `avg_logprob` cho mỗi đoạn — log xác suất trung bình của
các token. exp() ra được một số trong khoảng 0–1, đó là điểm tin cậy dùng ở
đây. Nó KHÔNG phải xác suất đúng đã hiệu chuẩn. Trong bản đề xuất phải viết
đúng như vậy, đừng gọi nó là "độ chính xác".

Nếu muốn ăn điểm ở mục 4.3: đo tương quan giữa điểm này và WER thật trên tập
kiểm thử. Nếu tương quan yếu thì tự nó là một phát hiện đáng viết — nghĩa là
máy không tự biết lúc nào mình nghe sai, và đó chính là lý do phải có ngưỡng
chuyển cán bộ.
"""

from __future__ import annotations

import math
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from . import config
from .normalize import normalize
from .schemas import AsrResult, Segment

_model = None
_model_error: Optional[str] = None


class AsrError(Exception):
    def __init__(self, message: str, code: str = "internal_error"):
        super().__init__(message)
        self.message = message
        self.code = code


# ---------------------------------------------------------------------------
def last_error() -> Optional[str]:
    """Vì sao nạp hỏng. Để /health nói được lý do thay vì chỉ báo chưa sẵn sàng."""
    return _model_error


def load_model(retry: bool = False):
    """Nạp mô hình. Gọi nhiều lần cũng chỉ nạp một lần.

    `retry=True` thì thử lại kể cả khi lần trước đã hỏng. Cần cái này vì trước
    đây một lần hỏng là hỏng vĩnh viễn tới lúc khởi động lại máy chủ: /warmup
    gặp `_model_error` đã đặt là trả về ngay trong 0,0 giây mà không thử gì,
    nên không có cách nào cứu ngoài restart. Mà lần hỏng đầu thường chỉ là sự
    cố nhất thời — mạng chập lúc tải model, hoặc máy chủ miễn phí thiếu bộ nhớ
    đúng lúc khởi động.
    """
    global _model, _model_error
    if _model is not None:
        return _model
    if _model_error is not None and not retry:
        return None
    _model_error = None
    try:
        from faster_whisper import WhisperModel
        t0 = time.time()
        _model = WhisperModel(
            config.ASR_MODEL,
            device=config.ASR_DEVICE,
            compute_type=config.ASR_COMPUTE_TYPE,
        )
        print(f"[asr] Đã nạp {config.ASR_MODEL} trong {time.time() - t0:.1f}s")
    except Exception as exc:  # noqa: BLE001
        _model_error = str(exc)
        print(f"[asr] KHÔNG nạp được mô hình: {exc}")
    return _model


def is_ready() -> bool:
    return _model is not None


# ---------------------------------------------------------------------------
def _probe_duration(path: Path) -> float:
    """Đo độ dài file bằng ffprobe. Trả 0.0 nếu không đo được."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=15,
        )
        return float(out.stdout.strip())
    except Exception:  # noqa: BLE001
        return 0.0


def _to_wav16k(src: Path) -> Path:
    """Đổi mọi định dạng về wav 16kHz mono.

    Trình duyệt gửi lên webm/opus. faster-whisper tự gọi được ffmpeg nhưng
    chuyển tay trước thì báo lỗi rõ ràng hơn và đo được độ dài chính xác.
    """
    dst = src.with_suffix(".16k.wav")
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ar", "16000", "-ac", "1",
         "-c:a", "pcm_s16le", str(dst)],
        capture_output=True, timeout=120,
    )
    if proc.returncode != 0 or not dst.exists():
        raise AsrError("Máy không đọc được file âm thanh này.", "audio_unreadable")
    return dst


# ---------------------------------------------------------------------------
def transcribe_file(path: Path, do_normalize: bool = True) -> AsrResult:
    """Đường chính: file âm thanh -> AsrResult."""
    model = load_model()
    if model is None:
        raise AsrError(
            "Mô hình nhận dạng chưa sẵn sàng. Thử lại sau ít giây.", "asr_not_ready"
        )

    wav = _to_wav16k(path)
    duration = _probe_duration(wav)
    if duration > config.MAX_AUDIO_SECONDS:
        raise AsrError(
            f"File âm thanh dài quá {config.MAX_AUDIO_SECONDS:.0f} giây.",
            "audio_too_long",
        )

    t0 = time.time()
    segments, info = model.transcribe(
        str(wav),
        language=config.ASR_LANGUAGE,
        beam_size=config.ASR_BEAM_SIZE,
        vad_filter=True,                       # cắt khoảng lặng, người già ngập ngừng nhiều
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,      # tránh mô hình tự bịa theo đà
    )

    segs, texts, confs, no_speech_probs = [], [], [], []
    for s in segments:
        conf = math.exp(s.avg_logprob) if s.avg_logprob is not None else 0.0
        conf = max(0.0, min(1.0, conf))
        segs.append(Segment(start=s.start, end=s.end, text=s.text.strip(), confidence=round(conf, 3)))
        texts.append(s.text.strip())
        confs.append(conf)
        no_speech_probs.append(getattr(s, "no_speech_prob", 0.0) or 0.0)

    latency = time.time() - t0
    raw = " ".join(texts).strip()

    # Điểm tin cậy toàn câu: bình quân theo độ dài đoạn, không phải bình quân trơn.
    # Một đoạn 5 giây nghe rõ không nên bị một đoạn 0.3 giây kéo tụt.
    if segs:
        total_len = sum(max(s.end - s.start, 0.01) for s in segs) or 1.0
        confidence = sum(c * max(s.end - s.start, 0.01) for c, s in zip(confs, segs)) / total_len
    else:
        confidence = 0.0

    mean_no_speech = sum(no_speech_probs) / len(no_speech_probs) if no_speech_probs else 1.0
    no_speech = (not raw) or mean_no_speech > config.NO_SPEECH_CEILING

    try:
        wav.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass

    return AsrResult(
        text=normalize(raw) if do_normalize else raw,
        text_raw=raw,
        confidence=round(confidence, 3),
        no_speech=no_speech,
        duration_seconds=round(duration or getattr(info, "duration", 0.0), 2),
        latency_seconds=round(latency, 2),
        segments=segs,
    )


def transcribe_bytes(data: bytes, filename: str = "audio.webm",
                     do_normalize: bool = True) -> AsrResult:
    """Bọc cho tiện gọi từ FastAPI. KHÔNG lưu âm thanh — ghi vào thư mục tạm,
    xử lý xong xoá ngay. Cam kết này nằm ở mục 4.5 của bản đề xuất."""
    suffix = Path(filename).suffix or ".webm"
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / f"in{suffix}"
        p.write_bytes(data)
        return transcribe_file(p, do_normalize=do_normalize)
