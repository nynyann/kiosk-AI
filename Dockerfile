FROM python:3.11-slim

# ffmpeg bắt buộc: trình duyệt gửi lên webm/opus, phải đổi sang wav 16kHz.
# Thiếu cái này là lỗi "audio_unreadable" mà không hiểu vì sao.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Nướng sẵn mô hình vào ảnh -----------------------------------------------
# Tải lúc BUILD chứ không tải lúc chạy. Lý do: nhiều nền tảng miễn phí cho máy
# chủ ngủ khi vắng khách, và ổ đĩa bị xoá sạch mỗi lần ngủ dậy — Render ghi rõ
# "any changes to your web service's filesystem are lost every time the service
# redeploys, restarts, or spins down". Tải lúc chạy thì cứ mỗi lần thức dậy nó
# lại kéo về 240 MB, người bấm đầu tiên ngồi chờ dài cổ. Nướng vào ảnh thì ảnh
# dựng một lần, ngủ dậy vẫn còn nguyên.
#
# huggingface_hub có sẵn, nó là thứ faster-whisper vốn đã phụ thuộc.
ARG ASR_MODEL_REPO=owmeowmeownyny/PhoWhisper-small-ct2
ARG ASR_MODEL_DIR=models/PhoWhisper-small-ct2
RUN python -c "from huggingface_hub import snapshot_download; \
    snapshot_download('${ASR_MODEL_REPO}', local_dir='/app/${ASR_MODEL_DIR}')"

COPY . .

ENV MOCK=0 \
    ASR_MODEL=models/PhoWhisper-small-ct2 \
    ASR_DEVICE=cpu \
    ASR_COMPUTE_TYPE=int8 \
    ASR_EAGER_LOAD=1

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
