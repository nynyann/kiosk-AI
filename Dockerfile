FROM python:3.11-slim

# ffmpeg bắt buộc: trình duyệt gửi lên webm/opus, phải đổi sang wav 16kHz.
# Thiếu cái này là lỗi "audio_unreadable" mà không hiểu vì sao.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Mô hình nặng, không đóng vào ảnh. Hai cách:
#  1) Nạp từ HuggingFace lúc chạy: đặt ASR_MODEL=<tên repo ct2 trên HF>
#  2) Gắn ổ đĩa ngoài và chép models/ vào đó
ENV MOCK=0 ASR_DEVICE=cpu ASR_COMPUTE_TYPE=int8 ASR_EAGER_LOAD=0

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
