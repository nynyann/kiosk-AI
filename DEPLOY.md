# Đưa kiosk lên mạng cho người khác test

Viết ngày 10/09/2026. Mọi con số trong đây là **đo thật trên máy của nhóm**,
không phải ước lượng.

---

## Điều bắt buộc phải biết trước: micro cần HTTPS

Trình duyệt chỉ mở micro cho trang chạy **https**, hoặc mở đúng bằng chữ
`localhost`. Đo thật, mở chính trang này qua địa chỉ mạng nội bộ:

```
http://192.168.1.3:8000  ->  isSecureContext: false
                             navigator.mediaDevices: undefined
```

**Nên cách "cùng Wi-Fi rồi gửi nhau địa chỉ 192.168.x.x" KHÔNG dùng được.**
Mọi thứ khác vẫn chạy (màn hình, tra cứu, đọc thành tiếng), riêng nút micro
báo lỗi. Muốn các bạn test bằng giọng nói thì phải có https thật.

Ba đường có https:
1. Triển khai lên máy chủ — mục dưới đây.
2. Đường hầm tạm (cloudflared, ngrok) — có link https trong vài phút, nhưng
   chỉ sống khi máy mình bật.
3. Bạn nào tự chạy trên máy mình rồi mở `http://localhost:8000` — `localhost`
   được coi là an toàn nên micro chạy bình thường.

---

## Máy chủ cần gì

| Khoản | Đo được | Ghi chú |
|---|---|---|
| RAM lúc chạy thật, bản base | **244 MB** | bản đem triển khai |
| RAM lúc chạy thật, bản small | **371 MB** | quá sát 512 MB, đã bị giết thật |
| Kích thước model | base 76 MB, small 237 MB | |
| Nạp model từ đĩa | 0,5 giây | model nằm sẵn trên máy |
| Nạp model từ HuggingFace | ~40 giây (bản tiny) | bản small lâu hơn, lần đầu thôi |
| Một lượt hỏi–đáp trọn vẹn | 2,1–2,8 giây | gồm cả nhận dạng và tra cứu |
| ffmpeg | bắt buộc | Dockerfile đã cài sẵn |
| Mạng ra ngoài | bắt buộc | phần đọc thành tiếng gọi giọng Edge |

Gói miễn phí 512 MB RAM là **vừa khít, hơi rủi ro**. Có gói 1 GB thì chọn.

---

## Hai model, đừng lẫn

| | Máy ở nhà, hôm chấm | Bản triển khai |
|---|---|---|
| Model | **PhoWhisper-small** | **PhoWhisper-base** |
| Vì sao | nghe chuẩn hơn | nhẹ hơn, small tràn 512 MB rồi chết thật |
| RAM đỉnh | 371 MB | 244 MB |
| Một câu, 1 luồng CPU | 12,6 giây | 1,5 giây |

**Số đo WER trong bài là của small.** Link Render chạy base nên nghe kém hơn
một chút — nói rõ chỗ này trong bài, đừng để người đọc tưởng hai cái là một.

Mặc định trong `app/config.py` vẫn là small nên máy ở nhà không đổi gì.
`Dockerfile` ghi đè sang base cho bản triển khai.

---

## Bước 1 — Model: XONG rồi

Model 250 MB bị `.gitignore` chặn nên không đi theo repo — cố ý, vì GitHub
chặn file trên 100 MB mà `model.bin` nặng 237 MB.

Đã đưa lên đây, công khai, không cần khoá gì để tải:

- **`owmeowmeownyny/PhoWhisper-small-ct2`** — 240 MB, dùng ở máy nhà.
- **`owmeowmeownyny/PhoWhisper-base-ct2`** — 76 MB, `Dockerfile` tải bản này.

Lệnh đã dùng, ghi lại phòng khi cần convert lại rồi đẩy bản mới:

```bash
hf upload owmeowmeownyny/PhoWhisper-small-ct2 models/PhoWhisper-small-ct2 . --no-private
```

Chạy trong thư mục `kiosk-backend` và thay đúng tên tài khoản vào, **không có
dấu ngoặc nhọn** — PowerShell coi `<` là toán tử nên dán nguyên chỗ điền vào
là báo lỗi "The '<' operator is reserved for future use".

**Đừng đổi sang bản người khác đã convert sẵn** (`diepho/...`, `mad1999/...`).
Nhóm đo WER trên bản mình tự convert; đổi model là số đo trong bài không còn
đúng với thứ đang chạy nữa.

---

## Bước 2 — Chỗ đặt

**HuggingFace Spaces bản Docker KHÔNG dùng được.** Tài liệu của họ ghi Gradio
và Docker Spaces cần gói trả phí, chỉ Static Spaces mới miễn phí. Đã kiểm tra
tài khoản `owmeowmeownyny`: `isPro = False`. Kho **model** thì vẫn miễn phí —
hai thứ khác nhau, đừng nhầm.

Dùng **Render** gói Free. Tra ngày 10/09/2026, đây là điều họ ghi:

| Khoản | Gói Free của Render | Nhóm cần |
|---|---|---|
| RAM | **512 MB** | đo được 320–380 MB → vừa khít |
| CPU | **ít hơn 1 nhân** | xem cảnh báo dưới |
| Ngủ khi vắng khách | sau **15 phút** không ai vào | có `scripts/keepalive.py` chống |
| Thức dậy mất | khoảng **1 phút** | Render hiện trang chờ |
| Giờ chạy | 750 giờ/tháng mỗi workspace | một tháng đầy là 720 giờ, đủ |
| Ổ đĩa | **xoá sạch mỗi lần ngủ dậy** | nên model nướng sẵn vào ảnh |
| Docker | dựng thẳng từ Dockerfile trong repo | đặt Language = Docker |

**Cảnh báo về tốc độ.** Đo thật trên cùng một câu, cùng model:

| Số luồng CPU | Thời gian nhận dạng |
|---|---|
| 8 luồng | 5,6 giây |
| 2 luồng | 6,7 giây |
| **1 luồng** | **11,7 giây** |

Render Free cho "ít hơn 1 nhân", nên trên đó mỗi câu hỏi mất khoảng **10–15
giây** chứ không phải 2–3 giây như trên máy nhà. Đủ để các bạn test thử, nhưng
**đừng demo trực tiếp cho giám khảo bằng link này** — hôm chấm chạy trên máy
nhà cho nhanh, link Render chỉ để gửi trước cho mọi người xem.

---

## Bước 3 — Tạo dịch vụ trên Render

1. Vào dashboard Render, **New → Web Service**, nối tới repo
   `nynyann/kiosk-backend`. Repo đang **private** nên phải cho Render quyền
   đọc lúc nối GitHub.
2. **Language: Docker** (chọn tay, kể cả khi trong danh sách có Python).
3. **Instance Type: Free**.
4. Không cần đặt biến môi trường nào cả — `Dockerfile` đã ghi sẵn `MOCK=0`,
   `ASR_MODEL`, `ASR_EAGER_LOAD=1`, và model nướng luôn trong ảnh.

Muốn đổi giọng đọc thì thêm biến `TTS_VOICE=vi-VN-NamMinhNeural`.

Không cần đặt `ALLOWED_ORIGINS`: giao diện và API cùng một tên miền.

**Lần build đầu lâu** — phải cài ffmpeg, cài thư viện, tải 240 MB model. Cứ để
đó, đừng bấm huỷ giữa chừng.

---

## Bước 4 — Kiểm tra sau khi triển khai

```bash
curl https://<dia-chi>/health
```

Phải thấy `asr_ready: true`, `mock: false`, `tts_ready: true`. Nếu `asr_ready`
còn `false` thì model chưa nạp xong, đợi thêm rồi gọi `POST /warmup`.

Sau đó mở địa chỉ Render cấp bằng điện thoại, bấm micro, hỏi thử một câu.
Render cấp sẵn https nên micro chạy được.

**Lần vào đầu tiên sau khi máy chủ ngủ sẽ mất khoảng 1 phút** — Render hiện
trang chờ của họ trước khi tới được giao diện kiosk. Trước giờ cho các bạn
test thì mở link trước vài phút cho nó tỉnh, hoặc chạy:

```bash
python scripts/keepalive.py https://<dia-chi-render>
```

---

## Lỗi đã gặp thật khi triển khai

### `cannot enable executable stack`

```
[asr] KHÔNG nạp được mô hình: libctranslate2-bc15bf3f.so.4.5.0:
      cannot enable executable stack as shared object requires: Invalid argument
```

Máy chủ vẫn sống, `/health` trả về nhanh, nhưng `asr_ready` mãi là `false`.
Thư viện của `ctranslate2` 4.5.0 xin executable stack, nhân Linux mới từ chối.
**Trên Windows không lộ ra**, nên đừng tin "máy em chạy tốt mà".

Sửa: `requirements.txt` đã ghim `ctranslate2==4.8.2`. Đừng hạ xuống.

Cách tự kiểm nếu sau này gặp lại — đọc cờ `PT_GNU_STACK` trong file `.so`:

| Bản | PT_GNU_STACK | |
|---|---|---|
| 4.5.0 | 7 = RWX | có executable stack, hỏng |
| 4.8.2 | 6 = RW | chạy được |

Nguồn: OpenNMT/CTranslate2 issue #1849, sửa ở PR #1852, có từ bản 4.6.

### Máy chủ chạy được một lượt rồi trả 502, `uptime` tụt về 0

Hết bộ nhớ. Gặp thật: lượt nhận dạng đầu mất **130 giây** rồi lượt thứ hai
làm dịch vụ chết và tự khởi động lại. Nguyên nhân là chạy PhoWhisper-**small**
với đỉnh 371 MB trên gói 512 MB — cộng FastAPI và bộ đệm tiếng là tràn.

**Trả $7/tháng KHÔNG cứu được**: gói Starter cũng đúng 512 MB RAM, chỉ hơn ở
chỗ 0,5 nhân CPU và không bị ngủ.

Sửa bằng cách đổi sang PhoWhisper-**base** và đặt `ASR_CPU_THREADS=1` —
`Dockerfile` đã ghi sẵn cả hai.

### `asr_ready: false` mà không biết vì sao

Nhìn trường `asr_error` trong `/health`: `null` là chưa thử nạp lần nào, đợi
thêm; có chữ là đã thử và hỏng. Hỏng rồi thì gọi `POST /warmup` để thử lại,
nó trả kèm câu lỗi.

---

## Gửi cho các bạn

Gửi đúng mấy dòng này:

> Mở link bằng Chrome trên điện thoại, bấm nút micro rồi hỏi
> "tôi muốn xin giấy xác nhận cư trú".
> Lần đầu vào có thể chờ 1 phút cho máy chủ tỉnh, và mỗi câu hỏi máy nghĩ
> vài giây vì đang chạy trên máy chủ miễn phí.
> Link: https://<dia-chi-render>

Nhắc thêm: hiện kho mới có **1 thủ tục** (xác nhận cư trú), hỏi thủ tục khác
thì máy chuyển sang màn hình mời gặp cán bộ — đúng thiết kế, không phải hỏng.
