"""Cấu hình tập trung. Mọi thứ đọc từ biến môi trường, có sẵn giá trị mặc định chạy được ngay."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
KB_DIR = DATA_DIR / "kb"

# --- Chế độ chạy ------------------------------------------------------------
# MOCK=1  -> máy chủ giả, trả dữ liệu mẫu cố định, không nạp mô hình.
#            Dùng cho Kns làm giao diện và cho lần triển khai đầu tiên.
MOCK = os.getenv("MOCK", "0") == "1"

# --- Nhận dạng giọng nói ----------------------------------------------------
# PhoWhisper bản gốc trên HuggingFace là định dạng transformers.
# faster-whisper KHÔNG nạp thẳng được, phải chuyển sang CTranslate2 trước.
# Xem scripts/convert_phowhisper.sh. Sau khi chuyển, trỏ đường dẫn vào đây.
ASR_MODEL = os.getenv("ASR_MODEL", "models/PhoWhisper-small-ct2")
ASR_MODEL_LABEL = os.getenv("ASR_MODEL_LABEL", "PhoWhisper-small")
ASR_DEVICE = os.getenv("ASR_DEVICE", "cpu")           # cpu | cuda
ASR_COMPUTE_TYPE = os.getenv("ASR_COMPUTE_TYPE", "int8")  # int8 cho CPU, float16 cho GPU
ASR_BEAM_SIZE = int(os.getenv("ASR_BEAM_SIZE", "5"))
ASR_LANGUAGE = "vi"

# Nạp mô hình ngay khi máy chủ khởi động hay đợi lần gọi đầu.
# Trên máy chủ miễn phí nên để "0" cho nó khởi động nhanh, rồi gọi /warmup.
ASR_EAGER_LOAD = os.getenv("ASR_EAGER_LOAD", "0") == "1"

# --- Giới hạn đầu vào -------------------------------------------------------
MAX_AUDIO_MB = float(os.getenv("MAX_AUDIO_MB", "25"))
MAX_AUDIO_SECONDS = float(os.getenv("MAX_AUDIO_SECONDS", "60"))

# --- Ngưỡng ----------------------------------------------------------------
# Ngưỡng ASR: dưới mức này coi như nghe không rõ, mời bác nói lại.
ASR_CONFIDENCE_FLOOR = float(os.getenv("ASR_CONFIDENCE_FLOOR", "0.45"))
# Ngưỡng no_speech của Whisper: trên mức này coi như không có tiếng nói.
NO_SPEECH_CEILING = float(os.getenv("NO_SPEECH_CEILING", "0.6"))
# Ngưỡng tra cứu: Kim tính lại bằng hàm chi phí kỳ vọng ở bước 12, tạm để đây.
KB_MATCH_THRESHOLD = float(os.getenv("KB_MATCH_THRESHOLD", "0.55"))

# --- CORS -------------------------------------------------------------------
# TRƯỚC KHI NỘP: thay "*" bằng đúng tên miền trang giao diện của Kns.
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# --- Nhật ký hội thoại ------------------------------------------------------
LOG_TRANSCRIPTS = os.getenv("LOG_TRANSCRIPTS", "1") == "1"
LOG_PATH = Path(os.getenv("LOG_PATH", str(DATA_DIR / "logs" / "turns.jsonl")))
# Không ghi file âm thanh xuống đĩa. Mục 4.5 của bản đề xuất cam kết điều này,
# code phải khớp với cam kết đó.
STORE_AUDIO = False
