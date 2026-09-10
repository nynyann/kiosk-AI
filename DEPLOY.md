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
| RAM lúc chạy thật | **320–380 MB** | đã nạp model, sau 5 lượt nhận dạng |
| Kích thước model | 250 MB | `models/PhoWhisper-small-ct2/model.bin` |
| Nạp model từ đĩa | 0,5 giây | model nằm sẵn trên máy |
| Nạp model từ HuggingFace | ~40 giây (bản tiny) | bản small lâu hơn, lần đầu thôi |
| Một lượt hỏi–đáp trọn vẹn | 2,1–2,8 giây | gồm cả nhận dạng và tra cứu |
| ffmpeg | bắt buộc | Dockerfile đã cài sẵn |
| Mạng ra ngoài | bắt buộc | phần đọc thành tiếng gọi giọng Edge |

Gói miễn phí 512 MB RAM là **vừa khít, hơi rủi ro**. Có gói 1 GB thì chọn.

---

## Bước 1 — Đưa model lên HuggingFace

Model 250 MB bị `.gitignore` chặn (cố ý), nên không đi theo repo. Máy chủ phải
lấy được nó từ đâu đó. Cách gọn nhất: đẩy lên HuggingFace rồi trỏ tên kho vào
biến `ASR_MODEL` — đã thử và chạy được, `faster-whisper` tự tải về.

Kho **model** trên HuggingFace miễn phí (chỉ phần Spaces mới cần trả tiền).

```bash
pip install huggingface_hub
huggingface-cli login          # dán token lấy ở huggingface.co/settings/tokens
huggingface-cli upload <ten-tai-khoan>/PhoWhisper-small-ct2 models/PhoWhisper-small-ct2 .
```

Rồi trên máy chủ đặt `ASR_MODEL=<ten-tai-khoan>/PhoWhisper-small-ct2`.

**Đừng dùng bản người khác đã convert sẵn** (`diepho/...`, `mad1999/...`).
Nhóm đo WER trên bản mình tự convert; đổi sang bản khác là số đo trong bài
không còn đúng với thứ đang chạy nữa.

---

## Bước 2 — Chọn chỗ đặt

Repo đã có sẵn `Dockerfile` và `.dockerignore`, đẩy vào nền tảng nào nhận
Docker cũng được.

**HuggingFace Spaces giờ KHÔNG còn miễn phí cho bản Docker.** Trang tài liệu
của họ ghi rõ: Gradio và Docker Spaces cần gói trả phí (PRO cho tài khoản cá
nhân), chỉ Static Spaces mới miễn phí. Chỗ này README cũ của nhóm ghi sai, đã
sửa. Nếu ai trong nhóm có sẵn PRO thì vẫn là lựa chọn tốt: 2 vCPU, 16 GB RAM.

Chọn nền tảng khác thì nhìn theo bảng RAM ở trên mà xét. Hạn mức miễn phí của
các nơi thay đổi liên tục, kiểm tra lại lúc đăng ký chứ đừng tin bài viết cũ.

---

## Bước 3 — Đặt biến môi trường

```
MOCK=0
ASR_MODEL=<ten-tai-khoan>/PhoWhisper-small-ct2
ASR_EAGER_LOAD=1
TTS_VOICE=vi-VN-HoaiMyNeural
```

`ASR_EAGER_LOAD=1` bắt nạp model ngay lúc khởi động. Chậm khởi động vài phút
nhưng người bấm đầu tiên không phải chờ. Máy chủ hay ngủ thì để `0` cho nó
tỉnh nhanh, rồi gọi `POST /warmup` trước giờ chấm.

Không cần đặt `ALLOWED_ORIGINS`: giao diện và API cùng một tên miền.

---

## Bước 4 — Kiểm tra sau khi triển khai

```bash
curl https://<dia-chi>/health
```

Phải thấy `asr_ready: true`, `mock: false`, `tts_ready: true`. Nếu `asr_ready`
còn `false` thì model chưa nạp xong, đợi thêm rồi gọi `POST /warmup`.

Sau đó mở `https://<dia-chi>` bằng điện thoại, bấm micro, hỏi thử một câu.
**Phải bấm trên https thì micro mới hiện xin quyền.**

---

## Gửi cho các bạn

Gửi đúng một dòng:

> Mở link này bằng Chrome trên điện thoại rồi bấm nút micro, hỏi thử
> "tôi muốn xin giấy xác nhận cư trú": https://<dia-chi>

Nhắc thêm: hiện kho mới có **1 thủ tục** (xác nhận cư trú), hỏi thủ tục khác
thì máy chuyển sang màn hình mời gặp cán bộ — đúng thiết kế, không phải hỏng.
