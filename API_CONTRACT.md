# Giao kèo API — Kiosk hướng dẫn thủ tục hành chính

Phiên bản 1.0 — chốt ngày 06/09/2026. **Chốt rồi không đổi tên trường nữa.**
Nếu buộc phải đổi, tăng số phiên bản và báo trong nhóm chat trước khi đẩy code.

Địa chỉ máy chủ:
- Máy cá nhân: `http://localhost:8000`
- Máy chủ thật: điền vào đây sau khi triển khai xong

Trang thử API tự động: `GET /docs` — Kns bấm thử trực tiếp trên trình duyệt, không cần Postman.

---

## Quy ước chung

- Mọi phản hồi đều là JSON, mã hoá UTF-8.
- Mọi phản hồi đều có trường `ok` (bool). Nếu `ok = false` thì có thêm `error` (chuỗi tiếng Việt hiển thị được thẳng cho người dân).
- Thời gian tính bằng **giây**, số thực.
- Điểm tin cậy `confidence` luôn nằm trong khoảng 0.0 đến 1.0.

---

## 1. `GET /health`

Kiểm tra máy chủ còn sống. Dùng cho cả việc gọi định kỳ chống ngủ đông.

Phản hồi:

```json
{
  "ok": true,
  "status": "ok",
  "asr_ready": true,
  "asr_model": "PhoWhisper-small",
  "kb_procedures": 6,
  "mock": false,
  "uptime_seconds": 1874.2
}
```

`asr_ready = false` nghĩa là mô hình chưa nạp xong. Lần gọi đầu sau khi máy chủ tỉnh dậy có thể mất 20–60 giây để nạp mô hình.

---

## 2. `POST /asr`

Gửi âm thanh, nhận văn bản.

**Gửi lên**: `multipart/form-data`

| Trường | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `audio` | file | Có | webm / wav / mp3 / m4a / ogg. Tối đa 25 MB, tối đa 60 giây. |
| `normalize` | bool | Không | Mặc định `true`. Đặt `false` để lấy văn bản thô, chỉ dùng khi đo WER. |

Ví dụ gọi từ giao diện:

```js
const fd = new FormData();
fd.append("audio", blob, "cauhoi.webm");
const r = await fetch(BASE + "/asr", { method: "POST", body: fd });
const data = await r.json();
```

**Nhận về**:

```json
{
  "ok": true,
  "text": "tôi muốn xin giấy xác nhận cư trú",
  "text_raw": "ờ tôi muốn xin giấy xác nhận cư chú",
  "confidence": 0.87,
  "no_speech": false,
  "duration_seconds": 3.4,
  "latency_seconds": 2.1,
  "segments": [
    { "start": 0.0, "end": 3.4, "text": "tôi muốn xin giấy xác nhận cư trú", "confidence": 0.87 }
  ]
}
```

- `text` — văn bản đã chuẩn hoá, **đây là cái đem đi tra cứu và hiển thị**.
- `text_raw` — văn bản thô từ mô hình, giữ lại để đo WER và làm bảng so sánh trước/sau ở mục 4.3.
- `no_speech = true` — không nghe thấy tiếng nói. Giao diện hiện "Máy chưa nghe rõ, bác nói lại giúp con".

Lỗi thường gặp:

```json
{ "ok": false, "error": "File âm thanh dài quá 60 giây.", "code": "audio_too_long" }
```

Mã lỗi: `audio_too_long`, `audio_too_large`, `audio_unreadable`, `asr_not_ready`, `internal_error`.

---

## 3. `POST /answer`

Gửi câu hỏi bằng chữ, nhận hướng dẫn.

**Gửi lên**: JSON

```json
{ "text": "tôi muốn xin giấy xác nhận cư trú", "session_id": "kiosk-01-1725500000" }
```

`session_id` không bắt buộc, dùng để ghi nhật ký hội thoại.

**Nhận về**:

```json
{
  "ok": true,
  "handoff": false,
  "procedure_id": "xac-nhan-cu-tru",
  "procedure_name": "Xác nhận thông tin về cư trú",
  "match_score": 0.91,
  "answer": "Để xin giấy xác nhận cư trú, bác cần làm 3 bước sau.",
  "steps": [
    { "order": 1, "title": "Chuẩn bị giấy tờ", "detail": "Bác mang theo căn cước công dân còn hạn." }
  ],
  "documents": ["Căn cước công dân"],
  "where_to_submit": "Công an xã nơi bác đang ở, hoặc Cổng dịch vụ công quốc gia.",
  "fee": "Không mất phí.",
  "processing_time": "Trong ngày làm việc.",
  "source": {
    "title": "Luật Cư trú 2020, Điều 17",
    "url": "https://..."
  },
  "speech": "Để xin giấy xác nhận cư trú, bác cần làm ba bước sau. Bước một, chuẩn bị giấy tờ..."
}
```

- `speech` — bản đọc thành tiếng, đã bỏ ký hiệu và viết số thành chữ. Kns đưa thẳng chuỗi này cho Web Speech API.
- `handoff = true` — điểm khớp dưới ngưỡng, máy không dám trả lời:

```json
{
  "ok": true,
  "handoff": true,
  "match_score": 0.22,
  "answer": "Câu này con chưa được học ạ. Con mời bác gặp cán bộ ở quầy số 1.",
  "speech": "Câu này con chưa được học ạ. Con mời bác gặp cán bộ ở quầy số một.",
  "steps": [],
  "source": null
}
```

**Khi `handoff = true`, giao diện phải chuyển sang màn hình chuyển cán bộ.** Đây là điều kiện nghiệm thu ở bước 8 trong checklist.

---

## 4. `POST /turn`

Gộp `/asr` và `/answer` thành một lượt. Đây là đường dẫn giao diện dùng chính, hai đường trên chỉ để gỡ lỗi và đo đạc.

**Gửi lên**: `multipart/form-data`, trường `audio` (giống `/asr`), thêm `session_id` (không bắt buộc).

**Nhận về**: gộp nguyên hai phản hồi trên:

```json
{
  "ok": true,
  "asr": { "text": "...", "text_raw": "...", "confidence": 0.87, "no_speech": false, "latency_seconds": 2.1 },
  "answer": { "handoff": false, "procedure_name": "...", "steps": [], "speech": "...", "source": {} },
  "total_latency_seconds": 2.6
}
```

Nếu ASR nghe không ra tiếng (`no_speech = true`) thì `answer` trả về `handoff = true` với câu mời nói lại, **không** phải câu chuyển cán bộ.

---

## Chạy máy chủ giả

Kns không phải chờ mô hình. Bật biến môi trường:

```bash
MOCK=1 uvicorn app.main:app --reload
```

Cả ba đường dẫn trả dữ liệu mẫu cố định, đúng định dạng trên, độ trễ giả 0.4 giây.
Khi máy chủ thật xong, Kns chỉ đổi hằng số `BASE` trong giao diện, không sửa gì khác.

---

## CORS

Máy chủ đã mở CORS. Trước khi triển khai, sửa `ALLOWED_ORIGINS` trong `app/config.py`
thành đúng tên miền của trang giao diện, không để `*` khi nộp bài.
