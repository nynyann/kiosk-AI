# Backend kiosk hướng dẫn thủ tục hành chính

Phần máy chủ và nhận dạng giọng nói. Tương ứng bước 1–8 trong sheet «Demo kiosk».

## Phạm vi hỗ trợ

Đề bài nêu hai đối tượng: người cao tuổi và đồng bào dân tộc thiểu số. Với
nhóm thứ hai có hai tình huống rất khác nhau về kỹ thuật:

  (a) người dân tộc nói TIẾNG VIỆT, có thể kèm accent hoặc tiếng Việt là ngôn
      ngữ thứ hai
  (b) người dân tộc nói TIẾNG MẸ ĐẺ: Tày, Nùng, H'Mông, Mường, Khmer, Ê Đê,
      Ba Na và các tiếng khác

**Bản này chỉ làm theo hướng (a).** Hướng (b) cần một mô hình nhận dạng khác
hẳn cho từng ngôn ngữ ít tài nguyên, không nằm trong tầm của bài tập này, và
không có bộ dữ liệu công khai nào ghi người dân tộc nói tiếng Việt để đo. Nói
rõ giới hạn này trong bài, đừng để người đọc tự hiểu là kiosk nghe được mọi
thứ tiếng.

Người không nói được tiếng Việt vẫn dùng được kiosk qua nhánh chuyển cán bộ đã
có sẵn, và qua phần chữ hiển thị trên màn hình song song với phần đọc thành
tiếng.

---

Ai cần đọc gì:
- **Kns** — chỉ cần `API_CONTRACT.md` và phần «Máy chủ giả» dưới đây. Không phải cài Python nếu không muốn.
- **Mian** — chỉ cần `data/kb/_SCHEMA.md`.
- **Kim** — `app/kb.py`, chỗ cần thay có ghi rõ trong file.

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

**Trên Windows, hoặc nếu không muốn torch chen vào môi trường chính:** dựng một
môi trường riêng chỉ để chuyển đổi. `transformers` và `torch` nặng khoảng 3GB và
hay kéo theo bản `huggingface-hub` khác với bản `faster-whisper` cần.

```bash
python -m venv .venv-tools
.venv-tools/Scripts/python.exe -m pip install "transformers>=4.44" torch ctranslate2 datasets soundfile librosa
.venv-tools/Scripts/ct2-transformers-converter.exe --model vinai/PhoWhisper-small \
  --output_dir models/PhoWhisper-small-ct2 \
  --copy_files tokenizer.json preprocessor_config.json --quantization int8
```

Muốn có mô hình đối chứng để so bảng thì tải Whisper-small. Bản này **đã sẵn
định dạng CTranslate2**, không phải chuyển và không cần torch:

```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-small', local_dir='models/faster-whisper-small')"
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

Chạy lại với `--model` khác rồi in bảng so sánh. Bảng nhóm theo từng bộ dữ liệu,
vì so hai mô hình trên hai bộ khác nhau là so nhầm. Đừng đọc chéo dòng:

```bash
python -m eval.wer --compare results/
```

Cách thu tập kiểm thử xem `data/eval/README.md`.

### Đo trên bộ công khai để có mức nền

Chưa thu được tập của nhóm thì vẫn có số để đối chứng. Lệnh này tải một bộ công
khai về thành manifest đúng định dạng `eval.wer` đọc được:

```bash
python -m eval.prep_public --dataset vivos  --limit 50
python -m eval.prep_public --dataset fleurs --limit 50
python -m eval.wer --manifest data/eval/public/vivos/manifest.csv \
                   --model models/PhoWhisper-small-ct2 --tag PhoWhisper-small_vivos
```

Đọc số từ đây phải kèm ba cảnh báo, ghi sẵn trong `eval/prep_public.py`: hai bộ
này là người trưởng thành **đọc** trong phòng **yên tĩnh**, không có nhãn tuổi,
và không có một câu từ vựng hành chính nào. Nó là mức nền "điều kiện lý tưởng",
không thay được tập tự thu.

**Tải cho nhanh.** Các bộ có âm thanh nặng vài trăm MB tới vài GB. Ba việc dưới
đây làm một lần, sau đó nhanh hơn hẳn:

```bash
pip install hf_transfer                  # tải nhiều luồng thay vì một luồng
export HF_HUB_ENABLE_HF_TRANSFER=1       # Windows: $env:HF_HUB_ENABLE_HF_TRANSFER=1
.venv/Scripts/hf.exe auth login          # chưa đăng nhập thì bị giới hạn tốc độ
```

Trên Windows nên bật thêm **Developer Mode** trong Cài đặt. Không bật thì kho
đệm của HuggingFace phải sao chép file thay vì tạo liên kết, tốn gấp đôi dung
lượng đĩa và thêm một lượt ghi cho mỗi file.

File tải về được đệm lại, nên chạy `prep_public` lần thứ hai cho cùng một bộ
thì không tải lại nữa.

### Sửa chuẩn hoá rồi đo lại, không chạy lại mô hình

Vòng lặp chính ở cuối trang này là "sửa `normalize.py` → đo lại → ghi mức cải
thiện". Phần chạy mô hình không đổi gì giữa các vòng, và `hyp_raw` đã lưu sẵn
trong `results/*.json`, nên chỉ cần tính lại khâu chuẩn hoá:

```bash
python -m eval.rescore
```

Vài giây thay vì vài chục phút. Nó in WER cũ cạnh WER mới của từng lượt đo,
đúng chuỗi số cần cho mục 4.3.

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
bắt kém nhất», thêm cụm bị nghe nhầm vào `HARD_FIXES`, chạy `eval.rescore`, ghi
lại mức cải thiện. Chuỗi số đó chính là nội dung mục 4.3.

**Sửa `normalize.py` thì thêm test vào `tests/test_normalize.py` ngay lượt đó.**
Hai lỗi tìm được lúc đo trên VIVOS/FLEURS đều là lỗi mà 8 test cũ không bắt
được: cụm `<số> + "năm"` bị nuốt thành một chữ số ("ba năm" → "5"), và tiểu từ
"à" cuối câu bị bỏ như từ đệm ("bác à" → "bác"). Cả hai đều lọt vì test cũ chỉ
kiểm cụm số thuần và câu có "ạ". Đo thật là cách duy nhất tìm ra chúng.
