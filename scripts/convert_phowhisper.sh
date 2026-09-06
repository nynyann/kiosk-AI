#!/usr/bin/env bash
# Chuyển PhoWhisper sang định dạng CTranslate2 cho faster-whisper.
# Chạy MỘT LẦN trên máy có mạng, kết quả nằm trong models/ rồi dùng mãi.
#
#   bash scripts/convert_phowhisper.sh small
#
# Cỡ chọn: tiny | base | small | medium | large
# Cho 14 ngày và máy chủ miễn phí chạy CPU: chọn "small".
# "medium" chính xác hơn nhưng mỗi câu mất 8-15 giây trên CPU, quá chậm cho kiosk.

set -e
SIZE="${1:-small}"
SRC="vinai/PhoWhisper-${SIZE}"
DST="models/PhoWhisper-${SIZE}-ct2"

echo "Cài công cụ chuyển đổi..."
pip install -q "transformers>=4.44" torch ctranslate2

echo "Chuyển ${SRC} -> ${DST}"
ct2-transformers-converter \
  --model "${SRC}" \
  --output_dir "${DST}" \
  --copy_files tokenizer.json preprocessor_config.json \
  --quantization int8

echo ""
echo "Xong. Đặt vào .env:"
echo "  ASR_MODEL=${DST}"
echo "  ASR_MODEL_LABEL=PhoWhisper-${SIZE}"
