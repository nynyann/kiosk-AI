# Kiosk hướng dẫn thủ tục hành chính bằng giọng nói

Kiosk đặt tại bộ phận một cửa cấp xã, dành cho người cao tuổi. Người dân nói
điều mình cần bằng tiếng Việt tự nhiên, kiosk nhận ra thủ tục rồi dẫn đi đúng
ba bước: kiểm tra điều kiện, chuẩn bị hồ sơ, nộp hồ sơ. Mọi câu kiosk nói đều
lấy từ kho tri thức đã kiểm chứng theo văn bản pháp luật; mô hình ngôn ngữ chỉ
để hiểu hoàn cảnh và diễn đạt, không được thêm thông tin.

- Dùng thử: https://kiosk-thu-tuc-hanh-chinh.onrender.com (máy chủ miễn phí,
  lượt mở đầu chờ khoảng một phút để máy thức dậy; cần cho phép micro).
- Tài liệu kỹ thuật đầy đủ và mọi số đo: [TONG-HOP.md](TONG-HOP.md).
- Giao kèo API: [API_CONTRACT.md](API_CONTRACT.md). Triển khai: [DEPLOY.md](DEPLOY.md).

## Kiosk làm được gì

| | |
|---|---|
| Nghe tiếng Việt | PhoWhisper (VinAI) chạy trên CPU của máy chủ, không gửi tiếng nói ra ngoài |
| Nhận ra thủ tục | Từ câu nói tự nhiên, kể cả câu không có tên thủ tục («tôi già rồi nhà nước có cho đồng nào không»); câu ứng với nhiều thủ tục thì đưa ra cho người dân chọn |
| Dẫn ba bước | Câu đầu là «bác muốn làm gì», rồi hỏi từng điều kiện một, mỗi câu kèm cách trả lời; kết luận có khả năng thuộc diện hay không; hồ sơ theo đúng trường hợp; chọn cách nộp, nơi nộp, lệ phí, thời hạn |
| Hiểu hoàn cảnh | Người dân kể sẵn «tôi 76 tuổi, không có lương hưu» thì máy điền sẵn điều kiện, chỉ hỏi phần còn thiếu |
| Hỏi thêm | Bất kỳ lúc nào ở bước 2, 3; trả lời chỉ từ kho của thủ tục đó, ngoài kho thì nói khéo và mời gặp cán bộ |
| Không bao giờ im | Mọi câu kiosk có thể nói được sinh tiếng sẵn (153 tệp mp3 đi theo mã nguồn), dịch vụ giọng đọc ngoài hỏng thì kiosk vẫn nói |

Sáu thủ tục hiện có: trợ cấp hưu trí xã hội; trợ cấp xã hội hằng tháng; cấp
thẻ bảo hiểm y tế; cấp bản sao trích lục hộ tịch; chứng thực bản sao từ bản
chính; cấp thẻ căn cước.

## Kiến trúc

Một dịch vụ Python (FastAPI) phục vụ luôn trang giao diện và API. Không cơ sở
dữ liệu, không giữ phiên trên máy chủ.

    Trình duyệt (micro, màn hình, loa)
      |  ghi âm webm, gửi lên
      v
    FastAPI
      |-- app/asr.py        PhoWhisper qua faster-whisper, CTranslate2 int8, CPU
      |-- app/normalize.py  chuẩn hoá chữ: số, từ đệm, cụm hành chính hay nghe nhầm
      |-- app/kb.py         nạp kho tri thức, nhận ra thủ tục
      |-- app/flow.py       máy chạy luồng ba bước, không chứa nội dung
      |-- app/llm.py        mô hình ngôn ngữ (FPT AI Marketplace), bị khoá trong kho
      |-- app/tts.py        giọng đọc, đọc mp3 sinh sẵn trước
      v
    data/kb/*.json          sáu thủ tục, chuyển từ bảng Excel đã kiểm chứng
    data/tts/*.mp3          153 câu sinh sẵn
    web/index.html          giao diện kiosk, một tệp, không cần build

Mô hình ngôn ngữ được giữ trong kho bằng một lớp mềm (prompt chỉ chứa kho của
đúng thủ tục đó) và bốn lớp cứng do máy chủ kiểm: giá trị điền sẵn phải là mã
lựa chọn có trong kho kèm bằng chứng trích nguyên văn; thủ tục gợi ý phải là
một trong sáu mã; mọi con số trong câu trả lời phải có trong kho; hỏng hoặc quá
12 giây thì về kho tĩnh. Chi tiết và số đo ở TONG-HOP.md mục 7b.

## Số đo chính

- WER PhoWhisper-small trên 5 bộ dữ liệu công khai: 4,9% đến 28,3%, thấp hơn
  Whisper-small gốc 8 đến 19 điểm, 4/5 bộ có khoảng tin cậy tách rời.
- Mô hình ngôn ngữ gemma-4-31B-it: 0,3 đến 1,1 giây một lượt; 16/18 câu hỏi
  thực tế trả lời đúng từ kho, 0 câu bịa giấy tờ hay con số.
- 70 test tự động, chạy dưới 10 giây, không cần mạng và không cần mô hình.
- Bản triển khai chạy trên máy chủ 512 MB RAM, không GPU, chi phí 0 đồng.

Chưa có: số đo trên người cao tuổi thật. Xem giới hạn ở TONG-HOP.md mục 11.

## Chạy trên máy cá nhân

```bash
git clone https://github.com/nynyann/kiosk-AI.git && cd kiosk-AI
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Cài ffmpeg (trình duyệt gửi webm, mô hình cần wav):

```bash
sudo apt install ffmpeg      # Linux
brew install ffmpeg          # macOS
winget install ffmpeg        # Windows
```

Mô hình PhoWhisper đã chuyển sẵn sang CTranslate2 và công khai trên
HuggingFace (`owmeowmeownyny/PhoWhisper-small-ct2`, `owmeowmeownyny/PhoWhisper-base-ct2`);
lần chạy đầu tự tải về. Muốn tự chuyển thì xem `scripts/convert_phowhisper.sh`.

```bash
uvicorn app.main:app --reload
```

- http://localhost:8000 là giao diện kiosk.
- http://localhost:8000/docs là trang bấm thử từng đường dẫn API.

Muốn có mô hình ngôn ngữ thì điền `FPT_API_KEY` vào `.env` (xem `.env.example`).
Không có khoá, kiosk vẫn chạy đủ ba bước bằng kho tĩnh.

### Chạy nhanh không cần mô hình

```bash
MOCK=1 uvicorn app.main:app --reload
```

Chỉ giả phần nghe (văn bản nhận dạng xoay vòng vài mẫu). Kho tri thức, luồng
ba bước và giọng đọc chạy thật, nên xem được đúng nội dung sẽ lên máy chủ thật.

## Kiểm thử và đo

```bash
pytest -q                                  # 70 test, dưới 10 giây
python scripts/build_tts_cache.py          # sinh lại mp3 sau khi sửa kho tri thức
python -m eval.wer --manifest data/eval/testset.csv --model models/PhoWhisper-small-ct2 --tag PhoWhisper-small
python -m eval.wer --compare results/      # bảng so sánh các mô hình đã đo
```

Sửa kho tri thức: sửa `data/kb/<thủ tục>.json` theo `data/kb/_SCHEMA.md`
(bản gốc Excel ở `data/kb-source/`), chạy `build_tts_cache.py` rồi `pytest`.
Có test bắt file thiếu trường và câu chưa có tiếng.

## Cấu trúc thư mục

| Thư mục | Nội dung |
|---|---|
| `app/` | máy chủ FastAPI và các mô đun nghe, chuẩn hoá, kho, luồng, mô hình ngôn ngữ, giọng đọc |
| `web/` | giao diện kiosk (`index.html`) và tài nguyên (`asset/`) |
| `data/kb/` | kho tri thức sáu thủ tục; `data/kb-source/` bản Excel gốc |
| `data/tts/` | mp3 sinh sẵn cho mọi câu kiosk nói |
| `data/eval/`, `eval/`, `results/` | tập kiểm thử, công cụ đo WER, kết quả đo |
| `tests/` | test tự động |
| `scripts/` | chuyển mô hình, sinh mp3, giữ máy chủ thức |
| `docs/` | phần kỹ thuật của bản đề xuất và hình minh hoạ |

## Giới hạn

Chỉ tiếng Việt, chưa hỗ trợ tiếng dân tộc thiểu số. Sáu thủ tục cấp xã. Chưa
đo với người cao tuổi thật. Phụ thuộc dịch vụ giọng đọc và mô hình ngôn ngữ
bên ngoài cho câu mới, có đường lùi về câu tĩnh. Kiosk chỉ hướng dẫn theo
thông tin đã công bố, không thay cán bộ quyết định hồ sơ.

## Giấy phép và liên hệ

Mã nguồn dùng cho mục đích nghiên cứu và thi. Góp ý gửi về hòm thư ghi trên
trang chủ của kiosk.
