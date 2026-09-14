"""Máy chủ giả. Bước 4 trong checklist.

Bật bằng `MOCK=1`. Trả dữ liệu mẫu cố định, đúng định dạng trong giao kèo,
không nạp mô hình gì cả. Mục đích duy nhất: Kns làm giao diện không phải chờ.

Có độ trễ giả 0.4 giây để Kns thấy được vòng quay chờ của mình có chạy không.

Chỉ giả phần NGHE. Phần tra kho và luồng từng bước chạy trên kho thật trong
data/kb/, vì kho không cần mô hình. `mock_answer()` giữ lại cho ai cần một
AnswerResult mẫu cố định, main.py không dùng nữa.
"""

import time
from itertools import cycle

from .normalize import for_speech
from .schemas import AnswerResult, AsrResult, Segment, Source, Step

MOCK_DELAY = 0.4

# Xoay vòng 4 mẫu: hai câu khớp thủ tục (xác nhận → vào luồng), một câu
# không khớp gì (chuyển cán bộ / chọn tay), một lượt không nghe rõ (nói lại).
_ASR_SAMPLES = cycle([
    ("tôi hơn 75 tuổi có được nhận trợ cấp không", "ờ tôi hơn bảy mươi lăm tuổi có được nhận chợ cấp không", 0.87, False),
    ("làm căn cước công dân cần giấy tờ gì", "làm căn cước công dâng cần giấy tờ gì", 0.79, False),
    ("hôm nay trời đẹp quá", "hôm nay trời đẹp quá", 0.81, False),
    ("", "", 0.11, True),  # nhánh không nghe rõ
])

_SAMPLE_STEPS = [
    Step(order=1, title="Kiểm tra điều kiện",
         detail="Bác từ đủ 75 tuổi trở lên và không đang nhận lương hưu."),
    Step(order=2, title="Chuẩn bị hồ sơ",
         detail="Bác điền Văn bản đề nghị theo Mẫu số 01."),
    Step(order=3, title="Nộp hồ sơ",
         detail="Bác nộp tại Trung tâm Phục vụ hành chính công cấp xã."),
]

_ANSWERS = cycle([
    AnswerResult(
        handoff=False,
        # Mã thủ tục phải có thật trong data/kb/, vì giao diện sẽ gọi
        # /flow/start với mã này — luồng từng bước chạy trên kho thật kể cả
        # ở chế độ giả, chỉ có phần nghe là giả.
        procedure_id="tro-cap-huu-tri-xa-hoi",
        procedure_name="Trợ cấp hưu trí xã hội",
        match_score=0.91,
        answer="Để hưởng trợ cấp hưu trí xã hội, bác cần làm 3 bước sau.",
        steps=_SAMPLE_STEPS,
        documents=["Văn bản đề nghị theo Mẫu số 01"],
        where_to_submit="Trung tâm Phục vụ hành chính công cấp xã nơi bác cư trú.",
        fee="Bác hỏi cán bộ để biết có mất phí không.",
        processing_time="10 ngày làm việc.",
        source=Source(title="Điều 21 Luật Bảo hiểm xã hội số 41/2024/QH15",
                      url="https://dichvucong.gov.vn/"),
        speech=for_speech("Để hưởng trợ cấp hưu trí xã hội, bác cần làm 3 bước sau. "
                          "Bước 1. Kiểm tra điều kiện."),
        confirm=for_speech("Cháu hiểu bác cần làm thủ tục Trợ cấp hưu trí xã hội. Đúng không ạ?"),
    ),
    AnswerResult(
        handoff=True, match_score=0.22,
        answer="Câu này cháu chưa được học ạ. Cháu mời bác gặp cán bộ ở quầy số 1, hoặc bác bấm chọn một thủ tục trên màn hình.",
        speech=for_speech("Câu này cháu chưa được học ạ. Cháu mời bác gặp cán bộ ở quầy số 1, hoặc bác bấm chọn một thủ tục trên màn hình."),
    ),
])


def mock_asr() -> AsrResult:
    time.sleep(MOCK_DELAY)
    text, raw, conf, no_speech = next(_ASR_SAMPLES)
    return AsrResult(
        text=text, text_raw=raw, confidence=conf, no_speech=no_speech,
        duration_seconds=3.4, latency_seconds=MOCK_DELAY,
        segments=[Segment(start=0.0, end=3.4, text=text, confidence=conf)] if text else [],
    )


def mock_answer() -> AnswerResult:
    time.sleep(MOCK_DELAY / 2)
    return next(_ANSWERS)
