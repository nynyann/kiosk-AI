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
# Số luồng CPU cho ctranslate2. 0 = để nó tự quyết theo số nhân nhìn thấy.
# TRÊN MÁY CHỦ CONTAINER PHẢI ĐẶT TAY, thường là 1. Container nhìn thấy đủ số
# nhân của máy vật lý nhưng chỉ được cấp một phần nhỏ của một nhân, nên nó
# sinh ra cả đống luồng giành nhau mẩu CPU đó, vừa chậm vừa tốn thêm bộ nhớ.
ASR_CPU_THREADS = int(os.getenv("ASR_CPU_THREADS", "0"))
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

# --- Đọc thành tiếng --------------------------------------------------------
# Máy chủ tự sinh mp3 thay vì để trình duyệt đọc. Lý do đầy đủ ở đầu app/tts.py:
# Web Speech API chỉ đọc được thứ tiếng mà hệ điều hành đã cài giọng, mà máy
# Windows thường chỉ có giọng tiếng Anh nên nó lấy giọng Mỹ đọc chữ tiếng Việt.
TTS_ENABLED = os.getenv("TTS_ENABLED", "1") == "1"
# vi-VN-HoaiMyNeural (nữ) hoặc vi-VN-NamMinhNeural (nam).
TTS_VOICE = os.getenv("TTS_VOICE", "vi-VN-HoaiMyNeural")
# Chậm hơn mặc định một chút cho người già nghe kịp. Định dạng của edge-tts là
# phần trăm so với tốc độ gốc, bắt buộc có dấu + hoặc -.
TTS_RATE = os.getenv("TTS_RATE", "-8%")
# Hạn giờ lúc đang phục vụ: người dân đứng trước màn hình chờ, quá mức này thì
# thà bỏ cuộc để giao diện rơi về giọng trình duyệt còn hơn treo im lặng.
TTS_TIMEOUT_SECONDS = float(os.getenv("TTS_TIMEOUT_SECONDS", "8"))
# Hạn giờ lúc hâm nóng lúc khởi động thì rộng rãi hẳn, vì KHÔNG có ai đang chờ.
# Đo thật: cùng một câu, lần gọi nguội mất 13,9 giây (584 ký tự) và tới 55,8
# giây (967 ký tự, sau khi lắp 6 thủ tục của Mian), lần sau chỉ 1-2 giây. Để 45
# giây thì hâm nóng hỏng đúng câu dài nhất. Không phải do độ dài — cắt còn 500
# ký tự vẫn có lúc hỏng sau 3 giây — mà dịch vụ giọng đọc chập chờn lúc nguội.
TTS_PREWARM_TIMEOUT_SECONDS = float(os.getenv("TTS_PREWARM_TIMEOUT_SECONDS", "90"))
# Số lần thử cho mỗi câu lúc hâm nóng. Hỏng nhất thời khá hay gặp.
TTS_PREWARM_ATTEMPTS = int(os.getenv("TTS_PREWARM_ATTEMPTS", "3"))
TTS_MAX_CHARS = int(os.getenv("TTS_MAX_CHARS", "2000"))
# Nội dung lấy từ data/kb/: mỗi thủ tục chừng 20 câu (câu hỏi bước 1, kết
# luận, bước 2, bước 3, FAQ), 6 thủ tục cỡ 120 câu. 256 mục giữ hết, tốn chừng
# vài MB bộ nhớ.
TTS_CACHE_SIZE = int(os.getenv("TTS_CACHE_SIZE", "256"))
# Sinh sẵn tiếng cho mọi câu trong kho ngay lúc khởi động, chạy nền.
TTS_PREWARM = os.getenv("TTS_PREWARM", "1") == "1"

# --- CORS -------------------------------------------------------------------
# TRƯỚC KHI NỘP: thay "*" bằng đúng tên miền trang giao diện của Kns.
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# --- Nhật ký hội thoại ------------------------------------------------------
LOG_TRANSCRIPTS = os.getenv("LOG_TRANSCRIPTS", "1") == "1"
LOG_PATH = Path(os.getenv("LOG_PATH", str(DATA_DIR / "logs" / "turns.jsonl")))
# Không ghi file âm thanh xuống đĩa. Mục 4.5 của bản đề xuất cam kết điều này,
# code phải khớp với cam kết đó.
STORE_AUDIO = False

# Ngưỡng khớp câu hỏi thêm (bước 2, 3) với FAQ của thủ tục đang làm. Tính
# bằng tỷ lệ từ của mẫu câu FAQ xuất hiện trong câu hỏi, 0–1.
FAQ_MATCH_THRESHOLD = float(os.getenv("FAQ_MATCH_THRESHOLD", "0.6"))
