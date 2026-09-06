"""Máy chủ giả. Bước 4 trong checklist.

Bật bằng `MOCK=1`. Trả dữ liệu mẫu cố định, đúng định dạng trong giao kèo,
không nạp mô hình gì cả. Mục đích duy nhất: Kns làm giao diện không phải chờ.

Có độ trễ giả 0.4 giây để Kns thấy được vòng quay chờ của mình có chạy không.

Câu trả lời mẫu xoay vòng theo mỗi lần gọi, để Kns thử được cả nhánh trả lời
bình thường lẫn nhánh chuyển cán bộ mà không phải sửa code.
"""

import time
from itertools import cycle

from .normalize import for_speech
from .schemas import AnswerResult, AsrResult, Segment, Source, Step

MOCK_DELAY = 0.4

_ASR_SAMPLES = cycle([
    ("tôi muốn xin giấy xác nhận cư trú", "ờ tôi muốn xin giấy xác nhận cư chú", 0.87, False),
    ("làm căn cước công dân cần giấy tờ gì", "làm căn cước công dâng cần giấy tờ gì", 0.79, False),
    ("", "", 0.11, True),  # nhánh không nghe rõ
])

_SAMPLE_STEPS = [
    Step(order=1, title="Chuẩn bị giấy tờ",
         detail="Bác mang theo căn cước công dân còn hạn sử dụng."),
    Step(order=2, title="Nộp hồ sơ",
         detail="Bác đến công an xã, hoặc nhờ con cháu nộp trên Cổng dịch vụ công quốc gia."),
    Step(order=3, title="Nhận kết quả",
         detail="Bác nhận giấy xác nhận ngay trong ngày làm việc."),
]

_ANSWERS = cycle([
    AnswerResult(
        handoff=False,
        procedure_id="xac-nhan-cu-tru",
        procedure_name="Xác nhận thông tin về cư trú",
        match_score=0.91,
        answer="Để xác nhận thông tin về cư trú, bác cần làm 3 bước sau.",
        steps=_SAMPLE_STEPS,
        documents=["Căn cước công dân"],
        where_to_submit="Công an xã nơi bác đang ở.",
        fee="Không mất phí.",
        processing_time="Trong ngày làm việc.",
        source=Source(title="Luật Cư trú 2020, Điều 17",
                      url="https://vanban.chinhphu.vn/"),
        speech=for_speech("Để xác nhận thông tin về cư trú, bác cần làm 3 bước sau. "
                          "Bước 1. Chuẩn bị giấy tờ. Bác mang theo căn cước công dân còn hạn."),
    ),
    AnswerResult(
        handoff=True, match_score=0.22,
        answer="Câu này con chưa được học ạ. Con mời bác gặp cán bộ ở quầy số 1.",
        speech=for_speech("Câu này con chưa được học ạ. Con mời bác gặp cán bộ ở quầy số 1."),
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
