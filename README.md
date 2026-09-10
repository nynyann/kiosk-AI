# Kiosk hướng dẫn thủ tục hành chính

Cả giao diện lẫn máy chủ nằm chung một repo. Chạy một lệnh là có trọn bộ:
máy chủ FastAPI phục vụ luôn trang kiosk ở `/`, còn API nằm ở `/health`,
`/asr`, `/answer`, `/turn`. Tương ứng bước 1–8 trong sheet «Demo kiosk».

| Phần        | Ở đâu               | Ghi chú                                   |
| ----------- | ------------------- | ----------------------------------------- |
| Giao diện   | `web/index.html`    | Một file HTML, không cần build, không npm |
| Đọc tiếng   | `app/tts.py`        | Máy chủ tự sinh mp3 giọng tiếng Việt      |
| Máy chủ     | `app/`              | FastAPI + PhoWhisper                      |
| Nội dung    | `data/kb/`          | Mỗi thủ tục một file JSON                 |
| Giao kèo API| `API_CONTRACT.md`   | Chốt rồi, đổi phải tăng phiên bản         |
| Triển khai  | `DEPLOY.md`         | Cách đưa lên mạng cho người khác test     |

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
- **Kns** — `web/index.html` và `API_CONTRACT.md`. Muốn xem giao diện chạy thật thì bật máy chủ giả ở phần dưới, khỏi cài mô hình.
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

- http://localhost:8000 — giao diện kiosk.
- http://localhost:8000/docs — trang bấm thử từng đường dẫn API.

Giao diện gọi API cùng địa chỉ với trang đang mở, nên không phải sửa địa chỉ
máy chủ ở đâu cả, kể cả sau khi triển khai lên tên miền thật. Cần trỏ sang máy
chủ khác lúc gỡ lỗi thì thêm `?base=` vào địa chỉ, ví dụ
`http://localhost:8000/?base=https://may-chu-that`, hoặc chạm ba lần vào chữ
«Kiosk thủ tục» để mở bảng gỡ lỗi.

---

## Máy chủ giả — cho Kns làm giao diện

```bash
MOCK=1 uvicorn app.main:app --reload
```

Không nạp mô hình, không cần ffmpeg, khởi động dưới 2 giây. Cả ba đường dẫn
trả dữ liệu mẫu đúng định dạng thật, có độ trễ giả 0.4 giây. Mở
http://localhost:8000 là thấy giao diện chạy đầy đủ trên dữ liệu mẫu đó.

Câu trả lời mẫu xoay vòng, nên gọi vài lần là thấy được cả nhánh trả lời bình
thường, nhánh chuyển cán bộ và nhánh không nghe rõ — thử đủ ba màn hình mà
không phải sửa code.

---

## Đọc thành tiếng

Máy chủ tự sinh file mp3 giọng tiếng Việt (`POST /tts`), giao diện chỉ việc phát.

**Vì sao không để trình duyệt tự đọc.** Web Speech API chỉ đọc được thứ tiếng
mà hệ điều hành đã cài giọng. Máy Windows ở ta thường chỉ có giọng tiếng Anh,
nên dù code đã đặt `lang = "vi-VN"` nó vẫn lấy giọng Mỹ đọc chữ tiếng Việt —
bác nghe không ra chữ nào. Kiosk chạy trên máy nào cũng phải ra tiếng Việt,
không thể bắt mỗi máy đi cài gói giọng trước.

Đổi giọng bằng biến môi trường, không phải sửa code:

```bash
TTS_VOICE=vi-VN-NamMinhNeural   # giọng nam, mặc định là HoaiMy giọng nữ
TTS_RATE=-15%                   # đọc chậm hơn nữa
TTS_ENABLED=0                   # tắt hẳn, quay về giọng trình duyệt
```

**Cần mạng lúc chạy.** Gọi hỏng thì giao diện tự rơi về Web Speech API — thà
giọng chưa chuẩn còn hơn để bác đứng nhìn màn hình không nghe gì.

Lúc khởi động, máy chủ sinh sẵn tiếng cho mọi câu trong kho rồi giữ trong bộ
nhớ đệm, chạy nền nên không làm chậm khởi động. Có đo: không sinh sẵn thì từ
lúc chữ hiện ra tới lúc có tiếng mất **2,5 giây** im lặng; sinh sẵn rồi còn
**0,02–0,3 giây**. Cùng một câu, lần gọi nguội mất tới 13,9 giây còn lần sau
chỉ 1,6 giây — nên hạn giờ lúc hâm nóng (45 giây) để rộng hơn hẳn hạn giờ lúc
đang phục vụ (8 giây), lúc phục vụ thì có người đang đứng chờ.

---

## Kiểm tra trước khi bàn giao

```bash
pip install -r requirements-dev.txt   # một lần, chỉ có pytest
python -m pytest tests/ -q            # 20 test: giao kèo API + đọc tiếng + chuẩn hoá
python -m app.normalize               # in bảng 10 câu trước/sau, ảnh cho mục 4.3
```

Test tự bật chế độ giả nên không cần mô hình, không cần ffmpeg, chạy dưới 2
giây. Từng file cũng chạy thẳng được nếu không muốn cài pytest:
`python tests/test_normalize.py`.

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

**Xem `DEPLOY.md`** — hướng dẫn từng bước, kèm số đo thật (RAM, thời gian nạp
model, độ trễ một lượt) để chọn gói máy chủ cho đúng.

Tóm tắt:

1. Model đã lên HuggingFace rồi: `owmeowmeownyny/PhoWhisper-small-ct2`, công
   khai. `Dockerfile` tự tải về lúc build, không phải làm gì thêm.
2. Trên Render: New → Web Service → nối repo này → **Language: Docker** →
   Instance Type: Free. Không cần đặt biến môi trường nào.
3. Đợi build xong, mở `/health` kiểm tra, rồi mở `/` xem giao diện.

**HuggingFace Spaces bản Docker không dùng được** — cần gói trả phí, chỉ
Static Spaces mới miễn phí. Kho model thì vẫn miễn phí, hai thứ khác nhau.

**Bản triển khai chạy PhoWhisper-base, máy ở nhà chạy small.** Đã thử small
trên Render và nó tràn 512 MB rồi chết giữa lượt thứ hai (đỉnh 371 MB); base
chỉ 244 MB và nhanh gấp 8 lần ở 1 luồng CPU. **Số đo WER trong bài là của
small** — nói rõ chỗ này, đừng để người đọc tưởng hai cái là một.

Hôm chấm nên chạy trên máy nhà cho nhanh và cho đúng model đã đo.

**Micro chỉ chạy trên https**, hoặc trên đúng chữ `localhost`. Gửi nhau địa chỉ
`192.168.x.x` cùng Wi-Fi là nút micro hỏng — đo rồi, `navigator.mediaDevices`
bằng `undefined`. Chi tiết trong `DEPLOY.md`.

Máy chủ cần **320–380 MB RAM** lúc chạy thật (đo sau 5 lượt nhận dạng). Gói
miễn phí 512 MB là vừa khít, có gói 1 GB thì chọn.

Chỉ một dịch vụ duy nhất, vì giao diện và API cùng một tên miền. Cũng vì cùng
tên miền nên trình duyệt không hỏi CORS: để `ALLOWED_ORIGINS` mặc định cũng
không sao. Chỉ khi nào có trang khác ở tên miền khác gọi vào API này thì mới
phải điền tên miền đó.

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
