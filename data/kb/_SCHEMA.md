# Cách viết file thủ tục json (save lại sau nếu cần bổ sung thủ tục)

Mỗi thủ tục một file `.json` trong thư mục này. **Tên file chính là mã thủ tục**,
viết không dấu, nối bằng gạch ngang: `xac-nhan-cu-tru.json`.

Chép file `tro-cap-huu-tri-xa-hoi.json` ra rồi sửa nội dung, đừng viết lại từ
đầu. (`../kb-draft/xac-nhan-cu-tru.json` là bản nháp chưa kiểm chứng, không
được nạp vào kiosk — muốn đưa vào thì kiểm chứng xong chuyển sang đây.)

Sau khi sửa xong, gọi `POST /kb/reload` là máy chủ nạp lại ngay, không phải
khởi động lại. Nếu file sai cú pháp JSON, máy chủ in cảnh báo ra màn hình và
**bỏ qua file đó** — nhớ nhìn màn hình sau khi sửa.

## Các trường

| Trường | Bắt buộc | Ý nghĩa |
|---|---|---|
| `name` | Có | Tên thủ tục đúng như trong văn bản pháp luật |
| `short` | Có | Một dòng ngắn dưới tên trên nút chọn ở màn hình chính, viết theo cách người dân gọi |
| `aliases` | Có | Cách người dân thật sự gọi thủ tục này. **Viết càng nhiều càng tốt** — đây là thứ quyết định máy có tìm ra hay không |
| `keywords` | Có | 4–6 cụm ngắn đặc trưng. Đừng cho cụm chung chung như "giấy tờ", "thủ tục" |
| `steps` | Có | Các bước, mỗi bước có `title` (3–5 chữ) và `detail` (1–2 câu) |
| `documents` | Có | Giấy tờ cần mang. Ghi rõ từng loại, ghi luôn cả điều kiện nếu có |
| `where_to_submit` | Có | Nộp ở đâu |
| `fee` | Có | Ghi rõ "Không mất phí" nếu miễn phí, đừng để trống |
| `processing_time` | Có | Bao lâu có kết quả |
| `validity` | Không | Kết quả có hạn không |
| `common_questions` | Không | Câu người dân hay hỏi thêm — dùng để mở rộng tra cứu sau |
| `flow` | **Có** | Luồng 3 bước theo sơ đồ — xem mục riêng bên dưới. Không có thì kiosk bỏ qua bước 1 và hiện thẳng hồ sơ |
| `source` | **Có** | Tên văn bản và đường dẫn. **Không có nguồn thì không đưa vào kho** |
| `verified_by` | **Có** | Tên người đã đối chiếu văn bản gốc |
| `verified_date` | **Có** | Ngày đối chiếu, dạng `2026-09-10` |

## Mục `flow` — luồng 3 bước

Đây là phần kiosk dùng nhiều nhất. Cấu trúc:

```json
"flow": {
  "check": {
    "intro": "Trước tiên cháu hỏi bác vài câu…",
    "questions": [
      {
        "id": "age",
        "text": "Bác năm nay bao nhiêu tuổi ạ?",
        "hint": "(tuỳ chọn) cách trả lời; bỏ trống thì máy tự sinh theo kiểu câu hỏi",
        "ask_if": { "purpose": ["new"] },
        "options": [
          { "value": "lt70",  "label": "Dưới 70 tuổi", "range": [0, 69], "match": ["dưới 70"] },
          { "value": "ge75",  "label": "Từ 75 tuổi trở lên", "range": [75, 200],
            "note": "Lưu ý hiện ở bước 2 nếu bác chọn mục này" }
        ]
      }
    ],
    "outcomes": [
      { "when": { "age": ["lt70"] }, "verdict": "ineligible", "reason": "Vì sao chưa đủ điều kiện…" },
      { "when": { "poor": ["unsure"] }, "verdict": "consult", "reason": "Cháu chưa đủ thông tin, bác hỏi cán bộ…" },
      { "when": { "kind": ["reregister"] }, "verdict": "redirect", "reason": "Đây là thủ tục khác…", "suggest": "ma-thu-tuc-khac" },
      { "when": { "purpose": ["adjust"] }, "verdict": "eligible", "note": "…", "documents": ["hồ sơ riêng cho trường hợp này"] }
    ],
    "eligible": { "note": "Theo thông tin bác cung cấp, bác có khả năng thuộc diện…", "documents": ["(tuỳ chọn) ghi đè documents"] }
  },
  "prepare": { "say": "Câu kiosk nói ở bước 2", "tips": ["thông tin thêm"] },
  "submit": {
    "say": "Câu kiosk nói ở bước 3",
    "places": ["nộp ở đâu"], "methods": ["trực tiếp", "bưu điện", "trực tuyến"],
    "choices": [ { "label": "Nộp trực tiếp", "say": "Câu máy nói khi bác chọn cách này" } ],
    "bring": ["giấy tờ mang theo"], "agency": "cơ quan xử lý làm gì", "result": "bác nhận được gì"
  },
  "faq": [ { "q": ["các cách hỏi", "…"], "a": "câu trả lời lấy từ văn bản" } ],
  "forms": [
    { "name": "Mẫu số 01 (…)", "how": "xin ở đâu, điền bằng gì, mắt kém thì nhờ ai",
      "fields": ["từng mục của mẫu, viết theo cách người dân hiểu"],
      "note": "mẫu in tại nơi nộp là bản chính thức" }
  ]
}
```

`forms`: cách kê khai mẫu. Người dân hỏi «mẫu số 2 là gì, điền thế nào» rất
nhiều; không có mục này thì mô hình chỉ biết «xin mẫu ở quầy». Ghi từng
mục của mẫu ở mức bác cần biết trước khi đến, đối chiếu với mẫu in kèm
Nghị định. Ba thủ tục có mẫu (hưu trí, xã hội hằng tháng, bảo hiểm y tế) đã
có bản nháp, trường `forms_note` ghi ai cần kiểm chứng.

Máy chạy thế này, mỗi lượt tính lại từ đầu:

1. Duyệt `outcomes` theo thứ tự. Mục nào có **mọi** khoá trong `when` đã được
   trả lời và giá trị nằm trong danh sách thì **dừng ngay ở đó** — nên viết
   điều kiện loại trừ (không phải công dân, dưới tuổi) ở trên.
2. Không mục nào khớp → hỏi câu tiếp theo chưa trả lời mà `ask_if` thoả
   (`ask_if` bỏ trống là luôn hỏi).
3. Hết câu → vào bước 2 với `eligible.note`.

`verdict`: `ineligible` (chưa đủ điều kiện), `consult` (không đủ thông tin,
mời gặp cán bộ — **đừng đoán**), `redirect` (thực ra là thủ tục khác; có
`suggest` thì kiosk hiện nút chuyển sang thủ tục đó), `eligible` (đủ, kèm
`note` và `documents` riêng cho trường hợp này).

`options[].match`: các cụm người dân hay nói để máy hiểu khi bác trả lời bằng
lời. `value` là `yes`/`no` thì máy tự hiểu có/không, không cần ghi. Câu hỏi
số (tuổi, số bản) thì ghi `range` `[thấp, cao]`, máy đọc số trong câu.

`faq`: bác bấm «Hỏi thêm» ở bước 2, 3 thì máy tìm ở đây trước. Mỗi câu ghi
càng nhiều cách hỏi càng tốt. Không có thì máy nói «chưa có trong kho, bác hỏi
cán bộ» — **máy không bịa**, nên câu nào hay bị hỏi thì thêm vào đây.

## Ba quy tắc bắt buộc

1. **Không có nguồn thì không viết.** Mọi câu trong `steps` và `documents`
   phải truy được về văn bản trong `source`. Máy chỉ đọc lại đúng cái ta viết
   ở đây, nên ta viết sai là máy nói sai với người dân.

2. **Viết như đang nói với một bác 70 tuổi.** Xưng "bác", tránh từ chuyên
   ngành. "Xuất trình giấy tờ tuỳ thân hợp lệ" đổi thành "bác mang theo căn
   cước công dân còn hạn".

3. **Không hứa cái mình không chắc.** Nếu văn bản không nói rõ thời hạn thì
   viết "bác nên hỏi cán bộ để biết hạn cụ thể", đừng đoán một con số.

## Nghiệm thu (bước 9 trong checklist)

Đọc bằng mắt cả 6 file, mỗi file đủ mọi trường bắt buộc, `verified_by` không
còn dòng chữ "CHƯA KIỂM CHỨNG". Rồi chạy `python -m pytest tests/test_flow.py
-q`: test đầu tiên kiểm tra cả 6 file có đủ `flow.check.questions`,
`flow.prepare.say`, `flow.submit.places`, và mọi `suggest` trỏ tới thủ tục có
thật.
