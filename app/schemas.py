"""Các kiểu dữ liệu vào/ra. Đây là bản mã hoá của API_CONTRACT.md.

Sửa file này là sửa giao kèo — phải báo Kns trước.
FastAPI tự sinh trang /docs từ đây nên Kns luôn thấy đúng cái đang chạy.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class Segment(BaseModel):
    start: float
    end: float
    text: str
    confidence: float


class AsrResult(BaseModel):
    ok: bool = True
    text: str = Field(..., description="Văn bản đã chuẩn hoá — dùng cái này để tra cứu")
    text_raw: str = Field(..., description="Văn bản thô từ mô hình — giữ để đo WER")
    confidence: float = Field(..., ge=0.0, le=1.0)
    no_speech: bool = False
    duration_seconds: float = 0.0
    latency_seconds: float = 0.0
    segments: List[Segment] = []


class Step(BaseModel):
    order: int
    title: str
    detail: str


class Source(BaseModel):
    title: str
    url: Optional[str] = None


class AnswerRequest(BaseModel):
    text: str
    session_id: Optional[str] = None


class AnswerResult(BaseModel):
    ok: bool = True
    handoff: bool = False
    procedure_id: Optional[str] = None
    procedure_name: Optional[str] = None
    match_score: float = 0.0
    answer: str = ""
    steps: List[Step] = []
    documents: List[str] = []
    where_to_submit: Optional[str] = None
    fee: Optional[str] = None
    processing_time: Optional[str] = None
    source: Optional[Source] = None
    speech: str = ""


class TurnResult(BaseModel):
    ok: bool = True
    asr: AsrResult
    answer: AnswerResult
    total_latency_seconds: float = 0.0


class HealthResult(BaseModel):
    ok: bool = True
    status: str = "ok"
    asr_ready: bool = False
    asr_model: str = ""
    kb_procedures: int = 0
    mock: bool = False
    uptime_seconds: float = 0.0
    # Máy chủ có tự đọc thành tiếng được không. Giao diện xem trường này để
    # quyết định gọi /tts hay rơi về giọng của trình duyệt.
    tts_ready: bool = False
    tts_voice: Optional[str] = None
    # Chỉ có giá trị khi asr_ready = false: câu lỗi lúc nạp mô hình.
    asr_error: Optional[str] = None


class ErrorResult(BaseModel):
    ok: bool = False
    error: str
    code: str = "internal_error"


class TtsRequest(BaseModel):
    """Đầu vào của /tts. `text` là chuỗi `speech` mà /answer hoặc /turn trả về."""
    text: str
    # Để trống thì dùng giọng mặc định trong config. Chỉ truyền khi muốn thử
    # giọng khác, ví dụ đổi sang vi-VN-NamMinhNeural cho giọng nam.
    voice: Optional[str] = None
