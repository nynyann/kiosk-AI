# Cách viết file thủ tục — hướng dẫn cho Mian

Mỗi thủ tục một file `.json` trong thư mục này. **Tên file chính là mã thủ tục**,
viết không dấu, nối bằng gạch ngang: `xac-nhan-cu-tru.json`.

Chép file `xac-nhan-cu-tru.json` ra rồi sửa nội dung, đừng viết lại từ đầu.

Sau khi sửa xong, gọi `POST /kb/reload` là máy chủ nạp lại ngay, không phải
khởi động lại. Nếu file sai cú pháp JSON, máy chủ in cảnh báo ra màn hình và
**bỏ qua file đó** — nhớ nhìn màn hình sau khi sửa.

## Các trường

| Trường | Bắt buộc | Ý nghĩa |
|---|---|---|
| `name` | Có | Tên thủ tục đúng như trong văn bản pháp luật |
| `aliases` | Có | Cách người dân thật sự gọi thủ tục này. **Viết càng nhiều càng tốt** — đây là thứ quyết định máy có tìm ra hay không |
| `keywords` | Có | 4–6 cụm ngắn đặc trưng. Đừng cho cụm chung chung như "giấy tờ", "thủ tục" |
| `steps` | Có | Các bước, mỗi bước có `title` (3–5 chữ) và `detail` (1–2 câu) |
| `documents` | Có | Giấy tờ cần mang. Ghi rõ từng loại, ghi luôn cả điều kiện nếu có |
| `where_to_submit` | Có | Nộp ở đâu |
| `fee` | Có | Ghi rõ "Không mất phí" nếu miễn phí, đừng để trống |
| `processing_time` | Có | Bao lâu có kết quả |
| `validity` | Không | Kết quả có hạn không |
| `common_questions` | Không | Câu người dân hay hỏi thêm — dùng để mở rộng tra cứu sau |
| `source` | **Có** | Tên văn bản và đường dẫn. **Không có nguồn thì không đưa vào kho** |
| `verified_by` | **Có** | Tên người đã đối chiếu văn bản gốc |
| `verified_date` | **Có** | Ngày đối chiếu, dạng `2026-09-10` |

## Ba quy tắc không được phá

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
còn dòng chữ "CHƯA KIỂM CHỨNG".
