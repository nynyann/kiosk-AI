# Giao kèo API — Kiosk hướng dẫn thủ tục hành chính

Phiên bản 2.2 — chốt ngày 17/09/2026. **Chốt rồi không đổi tên trường nữa.**

Đổi so với 1.0, **chỉ thêm, không đổi và không bỏ trường nào**, nên giao diện
viết theo 1.0 vẫn chạy nguyên:
- 1.1: thêm `POST /tts`, thêm `tts_ready` và `tts_voice` trong `/health`.
- 1.2: thêm `asr_error` trong `/health`, và `/warmup` nay thử lại được sau khi
  nạp hỏng, trả thêm `error` khi vẫn chưa nạp được.
- 2.0: **luồng từng bước** theo sơ đồ «Bước 1 kiểm tra điều kiện → Bước 2
  chuẩn bị hồ sơ → Bước 3 nộp hồ sơ» — mục 6 và 7 bên dưới. Thêm
  `GET /procedures`, `POST /flow/start`, `/flow/answer`, `/flow/answer-voice`,
  `/flow/next`, `/flow/ask`; thêm `confirm` trong phản hồi của `/answer` và
  `/turn`. Giao diện 2.0 dùng `/turn` chỉ để NHẬN RA thủ tục rồi vào luồng,
  không hiện cả 4 bước một lượt như 1.x nữa. Lên số lớn vì cách dùng đổi hẳn,
  còn trường cũ vẫn nguyên.
- 2.1: nối mô hình ngôn ngữ (FPT AI Marketplace), chỉ thêm trường:
  `/health` thêm `llm_enabled`, `llm_model`; `/answer`, `/turn` thêm
  `via_llm`; `/flow/start` nhận thêm `utterance` và trả `ack`, `prefilled`;
  `/flow/ask` nhận thêm `answers`, `utterance`, `history`, `stage` và trả
  `via_llm`. Không có khoá thì mọi trường mới rỗng và máy chạy như 2.0.
- 2.2: mọi đường dẫn nhận thêm `pronoun` (bác, ông, bà, cô, chú, anh, chị;
  JSON hoặc form tuỳ đường dẫn), máy chủ thay xưng hô trong mọi chuỗi trả
  về, kể cả `speech`. `/answer`, `/turn` trả thêm `candidates` (tối đa 3
  thủ tục có thể là điều bác cần, chắc nhất trước) để giao diện đưa ra cho
  bác chọn. Kho tri thức thêm mục `flow.forms` (cách kê khai từng mục của
  mẫu), mô hình đọc được khi bác hỏi «mẫu này điền thế nào».
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
  "uptime_seconds": 1874.2,
  "tts_ready": true,
  "tts_voice": "vi-VN-HoaiMyNeural",
  "asr_error": null
}
```

`tts_ready = false` nghĩa là máy chủ không đọc thành tiếng được (tắt bằng biến
môi trường, hoặc không có mạng). Giao diện lúc đó tự rơi về giọng của trình
duyệt — xem mục 5.

`asr_ready = false` nghĩa là mô hình chưa nạp xong. Khi đó `asr_error` cho
biết vì sao: `null` là chưa thử nạp lần nào (bình thường, đợi thêm), còn có
chữ là **đã thử và hỏng** — đợi mãi cũng không tự khỏi, phải gọi `POST /warmup`
để thử lại. Đây là chỗ nhìn đầu tiên khi máy chủ chạy mà không nghe được. Lần gọi đầu sau khi máy chủ tỉnh dậy có thể mất 20–60 giây để nạp mô hình.

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

Mã lỗi: `audio_too_long`, `audio_too_large`, `audio_unreadable`, `asr_not_ready`,
`bad_request`, `internal_error`.

`bad_request` (HTTP 422) là khi yêu cầu gửi lên thiếu trường hoặc sai kiểu dữ
liệu. Nó có thêm trường `detail` ghi rõ trường nào sai, bằng tiếng Anh, để gỡ
lỗi. `error` vẫn là câu tiếng Việt hiển thị được cho người dân như mọi lỗi khác.

```json
{ "ok": false, "error": "Máy chưa nhận được câu hỏi của bác. Bác thử lại giúp con.",
  "code": "bad_request", "detail": "audio: Field required" }
```

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

Từ 2.0 có thêm `confirm`: câu ngắn «Cháu hiểu bác cần làm thủ tục X. Đúng
không ạ?» để giao diện đọc ở màn hình xác nhận trước khi gọi `/flow/start`.
Chỉ có khi `handoff = false`.

Từ 2.1 có thêm `via_llm`: `true` khi tra từ khoá dưới ngưỡng nhưng mô hình
ngôn ngữ nhận ra thủ tục. Giao diện nên hỏi lại mềm hơn («Nếu cháu hiểu đúng
thì…»). Không có khoá mô hình thì luôn `false`.

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

## 5. `POST /tts`

Đọc một đoạn chữ thành tiếng Việt.

**Vì sao cần**: Web Speech API của trình duyệt chỉ đọc được thứ tiếng mà HỆ
ĐIỀU HÀNH đã cài giọng. Máy Windows thường chỉ có giọng tiếng Anh, nên dù đã
đặt `lang = "vi-VN"` nó vẫn lấy giọng Mỹ đọc chữ tiếng Việt, bác nghe không ra
chữ nào. Kiosk phải chạy được trên máy bất kỳ nên máy chủ tự sinh tiếng.

**Gửi lên**: JSON

```json
{ "text": "Để xin giấy xác nhận cư trú, bác cần làm ba bước sau." }
```

Truyền chuỗi `speech` mà `/answer` hoặc `/turn` đã trả về. Trường `voice`
không bắt buộc, để trống thì dùng giọng mặc định (`vi-VN-HoaiMyNeural`, nữ);
truyền `vi-VN-NamMinhNeural` nếu muốn giọng nam.

**Nhận về**: file **mp3** (`Content-Type: audio/mpeg`), không phải JSON.

```js
const r = await fetch(BASE + "/tts", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ text: answer.speech })
});
new Audio(URL.createObjectURL(await r.blob())).play();
```

Lỗi thì vẫn trả JSON đúng định dạng chung. Mã lỗi: `tts_disabled`,
`tts_timeout`, `tts_failed`, `text_too_long`, `bad_request`.

**Khi gọi hỏng, giao diện phải rơi về Web Speech API chứ đừng câm.** Thà giọng
chưa chuẩn còn hơn người dân đứng nhìn màn hình không nghe gì.

Máy chủ sinh sẵn tiếng cho mọi câu trong kho ngay lúc khởi động và giữ trong bộ
nhớ đệm, nên lượt hỏi thật gần như trả về tức thì. Lần gọi nguội cho một câu
chưa có sẵn có thể mất tới chục giây.

---

## 6. `GET /procedures`

Danh sách thủ tục trong kho, để vẽ nút chọn ở màn hình chính. Bác không nói
được, hoặc máy nghe không ra, thì bấm chọn vẫn vào được luồng.

```json
{
  "ok": true,
  "procedures": [
    { "id": "tro-cap-huu-tri-xa-hoi", "name": "Trợ cấp hưu trí xã hội",
      "short": "Trợ cấp cho người cao tuổi không có lương hưu" }
  ]
}
```

---

## 7. Luồng từng bước `/flow/*`

Đúng sơ đồ đã vẽ:

```
Bắt đầu → Bước 1. Kiểm tra điều kiện ─┬─ Đáp ứng → Bước 2. Chuẩn bị hồ sơ → Bước 3. Nộp hồ sơ → Kết thúc
                                       └─ Không → giải thích điều kiện chưa đáp ứng, kết luận → Kết thúc
```

**Máy chủ không giữ phiên.** Mỗi lượt giao diện gửi lại `answers` (các câu đã
trả lời ở bước 1) mà máy chủ vừa trả về; máy chủ tính lại từ đầu. Máy chủ
miễn phí khởi động lại giữa chừng cũng không mất trạng thái của bác.

Mọi đường dẫn `/flow/*` trả về cùng một kiểu **FlowState**:

```json
{
  "ok": true,
  "procedure_id": "tro-cap-huu-tri-xa-hoi",
  "procedure_name": "Trợ cấp hưu trí xã hội",
  "stage": "check",
  "step": 1,
  "step_title": "Kiểm tra điều kiện",
  "answers": { "age": "70_74" },
  "intro": "Trước tiên cháu hỏi bác vài câu…",
  "prompt": "Bác có phải là công dân Việt Nam không ạ?",
  "speech": "…câu để đọc thành tiếng…",
  "question": {
    "id": "citizen", "index": 2, "total": 5,
    "text": "Bác có phải là công dân Việt Nam không ạ?",
    "hint": "Bác trả lời «có» hoặc «không», hoặc bấm chọn một ô bên dưới.",
    "options": [ { "value": "yes", "label": "Có, tôi là công dân Việt Nam" },
                 { "value": "no",  "label": "Không phải" } ]
  },
  "verdict": null, "reason": null,
  "suggest_procedure_id": null, "suggest_procedure_name": null,
  "note": null, "documents": [], "notes": [], "tips": [],
  "places": [], "methods": [], "bring": [],
  "agency": null, "processing_time": null, "result": null, "fee": null,
  "source": { "title": "…", "url": "…" },
  "asr": null, "matched": null, "message": null
}
```

Giao diện chỉ cần nhìn `stage` để biết vẽ màn hình nào:

| `stage`   | Bước | Hiện gì | Bác làm gì tiếp |
|-----------|------|---------|-----------------|
| `check`   | 1 | `intro` (chỉ câu đầu), `question.text`, `question.hint` (cách trả lời), nút cho từng `question.options` | bấm chọn → `/flow/answer`, hoặc nói → `/flow/answer-voice` |
| `stop`    | 1 | `title` + `reason`. `verdict` là `ineligible` (chưa đủ điều kiện), `consult` (cần cán bộ xác định) hoặc `redirect` (đây là thủ tục khác, có thể kèm `suggest_procedure_id`) | Làm lại, xem thủ tục gợi ý, hoặc kết thúc |
| `prepare` | 2 | `note` (kết quả bước 1), `prompt`, `documents` (danh sách giấy tờ **theo đúng trường hợp của bác**), `notes` (lưu ý theo lựa chọn), `tips` | hỏi thêm → `/flow/ask`; tiếp tục → `/flow/next` với `stage: "prepare"` |
| `submit`  | 3 | `prompt`, `places`, `methods`, `bring`, `agency`, `processing_time`, `result`, `fee`, `source` | hỏi thêm → `/flow/ask`; kết thúc → `/flow/next` với `stage: "submit"` |
| `done`    | — | `prompt` | về màn hình chính |

`speech` luôn là câu để đọc thành tiếng cho trạng thái đó (đưa vào `/tts`).

### 7.1 `POST /flow/start`

```json
{ "procedure_id": "tro-cap-huu-tri-xa-hoi", "session_id": "kiosk-01-...",
  "utterance": "tôi 76 tuổi, không có lương hưu, sống một mình" }
```

`utterance` (tuỳ chọn, từ 2.1) là câu bác mở đầu, tức `asr.text` của `/turn`.
Máy đọc câu đó để **điền sẵn** các điều kiện bác đã nói rõ và trả thêm:

- `ack`: câu xác nhận đã hiểu («Cháu hiểu rồi ạ, bác 76 tuổi, chưa có lương
  hưu và sống một mình»), đã ghép vào đầu `speech`. Có mô hình ngôn ngữ thì
  câu này theo hoàn cảnh; không có thì «Cháu ghi nhận: …».
- `prefilled`: `[{question_id, question, value, label}]` các câu đã điền
  sẵn. Giao diện hiện cho bác xem và đưa vào thứ tự «Quay lại» để sửa được.
- `answers` đã chứa các giá trị điền sẵn; `question` là câu đầu tiên **còn
  thiếu**. Đủ hết thì trả thẳng `stage = prepare`.

Mã không có trong kho → `404`, `code = procedure_not_found`.

### 7.2 `POST /flow/answer` — bác bấm chọn

```json
{ "procedure_id": "…", "answers": { "age": "70_74" }, "question_id": "citizen", "value": "yes" }
```

Gửi nguyên `answers` của FlowState trước, máy chủ tự gộp thêm câu mới.

### 7.3 `POST /flow/answer-voice` — bác trả lời bằng lời

`multipart/form-data`: `audio` (file), `procedure_id`, `question_id`,
`answers` (chuỗi JSON), `session_id`.

Máy chủ nghe → ánh xạ sang một lựa chọn (đọc số tuổi, cụm từ đặc trưng,
có/không) → như `/flow/answer`. Phản hồi có thêm `asr` và `matched`:
- `matched = true`: đã hiểu, trạng thái tiếp theo.
- `matched = false`: nghe được nhưng không ra lựa chọn nào, hoặc không nghe
  rõ. Trạng thái trả về **là câu hỏi cũ**, kèm `message` để hiện và `speech`
  đọc câu đó, mời bác bấm chọn.

### 7.4 `POST /flow/next` — chuyển bước bằng tay

```json
{ "procedure_id": "…", "answers": { … }, "stage": "prepare" }
```

`stage` là bước ĐANG đứng: `prepare` → trả bước 3; `submit` → trả `done`;
`check` → tính lại bước 1 từ `answers` (dùng cho nút «Quay lại»: giao diện bỏ
câu trả lời cuối rồi gửi lên).

### 7.5 `POST /flow/ask` — hỏi thêm ở bước 2 / bước 3

`multipart/form-data`: `procedure_id`, và **một trong hai** `audio` (file)
hoặc `text` (chuỗi). Từ 2.1 gửi thêm ngữ cảnh phiên (tuỳ chọn, nhưng nên
gửi): `answers` (chuỗi JSON các câu đã trả lời), `utterance` (câu bác mở
đầu), `history` (chuỗi JSON `[{q, a}]` các lượt hỏi thêm trước, tối đa 6),
`stage` (`prepare` hoặc `submit`). Máy dùng để trả lời đúng hoàn cảnh bác,
không hỏi lại. Trả về:

```json
{
  "ok": true,
  "procedure_id": "tro-cap-huu-tri-xa-hoi",
  "question": "mẫu số 01 lấy ở đâu",
  "answer": "Mẫu số 01 ban hành kèm Nghị định 176/2025/NĐ-CP. Bác xin mẫu tại…",
  "speech": "…",
  "matched": true,
  "match_score": 1.0,
  "switch_to": null, "switch_name": null,
  "asr": { … },
  "via_llm": false
}
```

`via_llm = true` khi câu trả lời do mô hình ngôn ngữ viết từ kho tri thức
(câu hỏi diễn đạt khác FAQ, hoặc bác kể thêm hoàn cảnh); `false` là lấy
nguyên văn kho. Thứ tự: FAQ khớp rõ → nguyên văn; thủ tục khác → gợi ý
chuyển; còn lại có mô hình thì mô hình, mô hình bảo ngoài kho hoặc hỏng thì
câu tĩnh.

**Chỉ trả lời từ kho tri thức của thủ tục đang làm** (mục `flow.faq` và các
trường nơi nộp / thời hạn / phí / giấy tờ). Không có thì `matched = false` và
`answer` mời bác hỏi cán bộ — máy không bịa. Nếu câu hỏi khớp rõ với một thủ
tục **khác**, `switch_to` / `switch_name` có giá trị và `answer` hỏi bác có
muốn chuyển không; giao diện hiện nút chuyển.

---

## Chạy máy chủ giả

Kns không phải chờ mô hình. Bật biến môi trường:

```bash
MOCK=1 uvicorn app.main:app --reload
```

Chỉ giả phần **nghe**: `/asr`, `/turn`, `/flow/answer-voice`, `/flow/ask` với
`audio` trả văn bản mẫu xoay vòng (hai câu khớp thủ tục, một câu không khớp,
một lượt không nghe rõ), độ trễ giả 0.4 giây. Kho tri thức và luồng `/flow/*`
chạy **thật** trên `data/kb/`, vì kho không cần mô hình — bấm hết cả 3 bước
trên máy chủ giả là thấy đúng nội dung sẽ lên máy chủ thật.

---

## CORS

Máy chủ đã mở CORS. Trước khi triển khai, sửa `ALLOWED_ORIGINS` trong `app/config.py`
thành đúng tên miền của trang giao diện, không để `*` khi nộp bài.
