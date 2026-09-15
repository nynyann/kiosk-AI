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
    # true khi thủ tục do mô hình ngôn ngữ nhận ra (tra từ khoá không bắt được).
    via_llm: bool = False
    # Câu ngắn để máy hỏi lại «Cháu hiểu bác cần làm thủ tục X. Đúng không ạ?»
    # trước khi vào luồng từng bước. Giao diện 2.0 đọc câu này thay vì `speech`.
    confirm: str = ""


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
    # Mô hình ngôn ngữ (FPT AI Marketplace) có bật không, và tên mô hình.
    llm_enabled: bool = False
    llm_model: Optional[str] = None


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


# ---------------------------------------------------------------------------
# Luồng theo từng bước (API 2.0). Xem app/flow.py và API_CONTRACT.md mục 7.
# ---------------------------------------------------------------------------
class ProcedureSummary(BaseModel):
    id: str
    name: str
    # Một dòng ngắn để in dưới tên trên nút chọn thủ tục ở màn hình chính.
    short: Optional[str] = None


class ProceduresResult(BaseModel):
    ok: bool = True
    procedures: List[ProcedureSummary] = []


class FlowOption(BaseModel):
    value: str
    label: str


class FlowQuestion(BaseModel):
    id: str
    text: str
    # Hướng dẫn bác trả lời thế nào: «Bác nói số tuổi, ví dụ "tôi bảy mươi sáu
    # tuổi", hoặc bấm chọn bên dưới». Lấy từ `hint` trong file JSON, không có
    # thì máy chủ tự sinh theo kiểu câu hỏi.
    hint: str = ""
    options: List[FlowOption] = []
    # Câu thứ mấy / trong bao nhiêu câu SẼ hỏi theo các câu trả lời hiện có.
    index: int = 1
    total: int = 1


class FlowState(BaseModel):
    """Trạng thái một lượt của luồng. Giao diện chỉ cần nhìn `stage`:

    check   — bước 1, đang hỏi: hiện `question`, bác bấm chọn hoặc nói
    stop    — bước 1 kết luận không đáp ứng: hiện `title` + `reason`
    prepare — bước 2: hiện `documents`, `notes`, `tips`
    submit  — bước 3: hiện `places`, `methods`, `bring`, `agency`, `processing_time`, `result`
    done    — kết thúc
    """
    ok: bool = True
    procedure_id: str
    procedure_name: str = ""
    stage: str
    step: int = 1
    step_title: str = ""
    answers: dict = {}
    title: Optional[str] = None
    prompt: str = ""
    speech: str = ""
    question: Optional[FlowQuestion] = None
    # Lời dẫn của bước 1, chỉ có ở câu hỏi đầu tiên.
    intro: Optional[str] = None
    # Câu máy xác nhận đã hiểu hoàn cảnh bác kể («Cháu hiểu rồi ạ, bác 76 tuổi
    # và chưa có lương hưu»), chỉ có ở /flow/start khi gửi kèm `utterance`.
    ack: Optional[str] = None
    # Những câu điều kiện đã được điền sẵn từ lời bác kể, để giao diện hiện và
    # để «Quay lại» sửa được. Máy chỉ hỏi phần còn thiếu.
    prefilled: List["PrefilledAnswer"] = []
    # Chỉ có khi stage = stop (ineligible | consult | redirect) hoặc prepare (eligible).
    verdict: Optional[str] = None
    reason: Optional[str] = None
    suggest_procedure_id: Optional[str] = None
    suggest_procedure_name: Optional[str] = None
    note: Optional[str] = None
    documents: List[str] = []
    notes: List[str] = []
    tips: List[str] = []
    places: List[str] = []
    methods: List[str] = []
    bring: List[str] = []
    agency: Optional[str] = None
    processing_time: Optional[str] = None
    result: Optional[str] = None
    fee: Optional[str] = None
    source: Optional[Source] = None
    # Chỉ có khi trả lời bằng lời nói (/flow/answer-voice).
    asr: Optional[AsrResult] = None
    # false = nghe được nhưng không ánh xạ ra lựa chọn nào; trạng thái trả về
    # là trạng thái cũ (câu hỏi cũ) để bác bấm chọn.
    matched: Optional[bool] = None
    message: Optional[str] = None


class PrefilledAnswer(BaseModel):
    question_id: str
    question: str
    value: str
    label: str


class FlowStartRequest(BaseModel):
    procedure_id: str
    session_id: Optional[str] = None
    # Câu bác nói lúc mở đầu («tôi 76 tuổi, không có lương hưu…»). Máy đọc để
    # điền sẵn điều kiện và xác nhận đã hiểu, không bắt bác nói lại.
    utterance: Optional[str] = None


class FlowAnswerRequest(BaseModel):
    procedure_id: str
    answers: dict = {}
    question_id: str
    value: str
    session_id: Optional[str] = None


class FlowNextRequest(BaseModel):
    """Chuyển bước bằng tay: từ `prepare` sang bước 3, từ `submit` sang kết thúc."""
    procedure_id: str
    answers: dict = {}
    stage: str
    session_id: Optional[str] = None


class FlowAskResult(BaseModel):
    """Trả lời câu hỏi thêm ở bước 2 / bước 3, chỉ từ kho của thủ tục đó."""
    ok: bool = True
    procedure_id: str
    question: str = ""
    answer: str = ""
    speech: str = ""
    matched: bool = False
    match_score: float = 0.0
    # Câu hỏi có vẻ thuộc thủ tục khác: gợi ý chuyển.
    switch_to: Optional[str] = None
    switch_name: Optional[str] = None
    asr: Optional[AsrResult] = None
    # true khi câu trả lời do mô hình ngôn ngữ viết từ kho tri thức (câu hỏi
    # diễn đạt khác FAQ). false là lấy nguyên văn từ kho.
    via_llm: bool = False
