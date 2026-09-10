FROM python:3.11-slim

# ffmpeg bắt buộc: trình duyệt gửi lên webm/opus, phải đổi sang wav 16kHz.
# Thiếu cái này là lỗi "audio_unreadable" mà không hiểu vì sao.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Nướng sẵn mô hình vào ảnh -----------------------------------------------
# Tải lúc BUILD chứ không tải lúc chạy. Nhiều nền tảng miễn phí cho máy chủ ngủ
# khi vắng khách và xoá sạch ổ đĩa mỗi lần ngủ dậy — Render ghi rõ "any changes
# to your web service's filesystem are lost every time the service redeploys,
# restarts, or spins down". Tải lúc chạy thì mỗi lần thức dậy lại kéo về cả
# trăm MB. Nướng vào ảnh thì dựng một lần, ngủ dậy vẫn còn.
#
# Bản triển khai dùng PhoWhisper-BASE chứ không phải small. Đo thật sau khi
# máy chủ trên Render gói Free (512 MB) bị giết giữa lượt nhận dạng thứ hai:
#   small: đỉnh 371 MB, 12,6 giây một câu ở 1 luồng -> tràn bộ nhớ, chết
#   base : đỉnh 189 MB,  1,5 giây một câu ở 1 luồng -> chạy thoải mái
# Máy ở nhà vẫn để small (mặc định trong app/config.py). Số đo WER trong bài
# là của small — đừng lẫn hai cái.
#
# huggingface_hub có sẵn, nó là thứ faster-whisper vốn đã phụ thuộc.
ARG ASR_MODEL_REPO=owmeowmeownyny/PhoWhisper-base-ct2
ARG ASR_MODEL_DIR=models/PhoWhisper-base-ct2
RUN python -c "from huggingface_hub import snapshot_download; \
    snapshot_download('${ASR_MODEL_REPO}', local_dir='/app/${ASR_MODEL_DIR}')"

COPY . .

# ASR_CPU_THREADS=1: container nhìn thấy đủ số nhân của máy vật lý nhưng chỉ
# được cấp một phần nhỏ của một nhân. Để nó tự quyết là sinh cả đống luồng
# giành nhau mẩu CPU đó, vừa chậm vừa tốn thêm bộ nhớ.
ENV MOCK=0 \
    ASR_MODEL=models/PhoWhisper-base-ct2 \
    ASR_MODEL_LABEL=PhoWhisper-base \
    ASR_DEVICE=cpu \
    ASR_COMPUTE_TYPE=int8 \
    ASR_EAGER_LOAD=1 \
    ASR_CPU_THREADS=1

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
