# Backend kiosk hướng dẫn thủ tục hành chính

Phần máy chủ và nhận dạng giọng nói. Tương ứng bước 1–8 trong sheet «Demo kiosk».

Ai cần đọc gì:
- **Kns** — chỉ cần `API_CONTRACT.md` và phần «Máy chủ giả» dưới đây. Không phải cài Python nếu không muốn.
- **Mian** — chỉ cần `data/kb/_SCHEMA.md`.
- **Kim** — `app/kb.py`, chỗ cần thay có ghi rõ trong file.
- **Lia** — hết.

---

## Chạy trên máy cá nhân

```bash
git clone <repo> && cd kiosk-backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

**Cài ffmpeg** — bắt buộc, trình duyệt gửi lên webm mà mô hình cần wav.

```bash
sudo apt install ffmpeg      # Linux
brew install ffmpeg          # macOS
winget install ffmpeg        # Windows
```

Chuyển mô hình PhoWhisper một lần (khoảng 2 phút, cần mạng):

```bash
bash scripts/convert_phowhisper.sh small
```

Chạy:

```bash
uvicorn app.main:app --reload
```

Mở http://localhost:8000/docs để bấm thử.

---

## Máy chủ giả — cho Kns làm giao diện

```bash
MOCK=1 uvicorn app.main:app --reload
```

Không nạp mô hình, không cần ffmpeg, khởi động dưới 2 giây. Cả ba đường dẫn
trả dữ liệu mẫu đúng định dạng thật, có độ trễ giả 0.4 giây.

Câu trả lời mẫu xoay vòng, nên gọi vài lần là thấy được cả nhánh trả lời bình
thường, nhánh chuyển cán bộ và nhánh không nghe rõ — thử đủ ba màn hình mà
không phải sửa code.

---

## Kiểm tra trước khi bàn giao

```bash
python tests/test_normalize.py        # lưới an toàn cho phần chuẩn hoá
python -m app.normalize               # in bảng 10 câu trước/sau, ảnh cho mục 4.3
```

---

## Đo WER

```bash
python -m eval.wer --manifest data/eval/testset.csv \
                   --model models/PhoWhisper-small-ct2 --tag PhoWhisper-small
```

In ra WER tổng kèm khoảng tin cậy, WER tách theo nhóm tuổi và mức ồn, tỷ lệ
bắt đúng từng cụm hành chính, và tương quan giữa điểm tin cậy với lỗi thật.
Kết quả ghi vào `results/<tag>.json`.

Chạy lại với `--model` khác để có bảng so sánh nhiều mô hình cho mục 4.3.
Cách thu tập kiểm thử xem `data/eval/README.md`.

---

## Triển khai

1. Đẩy repo lên GitHub.
2. Tạo dịch vụ Docker mới trên một nền tảng container miễn phí, trỏ vào repo này.
3. Đặt biến môi trường: `ASR_MODEL`, `ALLOWED_ORIGINS` (tên miền trang của Kns), `MOCK=0`.
4. Đợi build xong, mở `/health` kiểm tra.

**Máy chủ miễn phí ngủ sau 15 phút.** Chạy cái này trên máy một bạn trong nhóm
từ hôm nộp đến hôm chấm:

```bash
python scripts/keepalive.py https://dia-chi-may-chu-cua-nhom
```

Trước buổi chấm 10 phút, gọi thêm `POST /warmup` để nạp sẵn mô hình.

**Phương án dự phòng nếu triển khai không kịp:** chạy `MOCK=1` trên máy chủ để
ít nhất có link mở được, chạy bản thật trên máy cá nhân, và **quay sẵn video
màn hình bản thật** phòng khi sập đúng lúc giám khảo mở.

---

## Việc còn lại của phần backend

| Việc                                        | Ai      | Ở đâu                       |
| ------------------------------------------- | ------- | --------------------------- |
| Thay tra cứu từ khoá bằng so khớp ngữ nghĩa | Kim     | `app/kb.py`, hàm `score()`  |
| Tính ngưỡng bằng hàm chi phí kỳ vọng        | Kim     | `config.KB_MATCH_THRESHOLD` |
| Viết 5 file JSON thủ tục còn lại            | Mian    | `data/kb/`                  |
| Thu 30 câu kiểm thử                         | cả nhóm | `data/eval/`                |
| Bổ sung `HARD_FIXES` từ kết quả đo thật     | Lia     | `app/normalize.py`          |

Việc cuối là vòng lặp chính: mỗi lần chạy `eval.wer`, nhìn mục «cụm hành chính
bắt kém nhất», thêm cụm bị nghe nhầm vào `HARD_FIXES`, chạy lại, ghi lại mức
cải thiện. Chuỗi số đó chính là nội dung mục 4.3.
