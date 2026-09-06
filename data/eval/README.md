# Tập kiểm thử — cách thu và cách ghi

## Vì sao phải tự thu

Không bộ dữ liệu tiếng Việt công khai nào có đúng thứ ta cần: giọng người cao
tuổi nói **từ vựng hành chính** trong **môi trường ồn**. Các bộ sẵn có đều là
người trưởng thành đọc rõ trong phòng yên tĩnh. Đó chính là lập luận ở mục 2.4
của bản đề xuất, và tập này là bằng chứng cho nó.

Quy mô của ta nhỏ. **Gọi đúng tên: "tập kiểm thử nội bộ", không gọi là "bộ dữ
liệu".** Giám khảo phân biệt được, và nói quá là mất điểm chứ không được điểm.

## Bộ công khai dùng để đối chứng

Chạy mô hình trên các bộ này để có con số nền, rồi so với tập tự thu. Chênh
lệch giữa hai bên chính là hình mở đầu video.

| Bộ | Dùng để làm gì |
|---|---|
| Common Voice tiếng Việt | Có nhãn nhóm tuổi — bộ duy nhất cho phép tách WER theo tuổi mà không phải tự thu |
| VIVOS | Bộ đọc chuẩn, dùng làm mức nền "điều kiện lý tưởng" |
| Bud500 | Quy mô lớn, đa dạng giọng, dùng đối chiếu độ bền chung |
| FLEURS (vi) | Bộ đa ngôn ngữ, tiện trích số so sánh với tài liệu quốc tế |

Tải bằng `datasets` của HuggingFace. Ghi lại **đúng phiên bản và ngày tải** vào
mục 4.2 — giám khảo hỏi là trả lời được ngay.

## Cách thu tập của nhóm

Mục tiêu tối thiểu để bảng số có nghĩa: **5 người × 6 câu = 30 câu**, trong đó
ít nhất 3 người ở nhóm 60+. Nếu liên hệ được xã thì tăng lên 20–30 người.

Với mỗi người:
1. Đưa danh sách 6 câu hỏi, mỗi câu ứng với một thủ tục trong kho.
2. **Đừng bắt đọc theo chữ.** Nói ý ra rồi để bác hỏi bằng lời của bác — cái
   ta cần đo là giọng nói tự nhiên, không phải giọng đọc.
3. Ghi lại **đúng những gì bác nói** vào cột `transcript`, kể cả từ đệm.
4. Thu ở hai môi trường: một lượt trong phòng yên tĩnh, một lượt ở chỗ có
   tiếng ồn thật (sân nhà văn hoá, quạt trần, tiếng người nói).

Ghi bằng điện thoại cũng được. Đổi về wav 16kHz mono trước khi chạy đo:

```bash
ffmpeg -i goc.m4a -ar 16000 -ac 1 audio/s01_c01.wav
```

## Cột trong `testset.csv`

| Cột | Bắt buộc | Giá trị |
|---|---|---|
| `audio_path` | Có | Đường dẫn tương đối từ thư mục này |
| `transcript` | Có | Câu chuẩn, chép đúng lời người nói |
| `speaker_id` | Có | `s01`, `s02`... Cần để không tính trùng một người nhiều lần |
| `age_group` | Có | `18-44`, `45-59`, `60+` |
| `gender` | Không | `nam`, `nữ` |
| `region` | Không | `bắc`, `trung`, `nam` |
| `noise_level` | Có | `yên tĩnh`, `có tiếng ồn`, `rất ồn` |
| `procedure_id` | Có | Mã thủ tục, để đo luôn tra cứu có trúng không |
| `note` | Không | Ghi chú tự do |

## Đồng ý của người tham gia

Trước khi ghi âm, nói rõ ba điều và ghi lại việc đã nói:
1. Ghi âm dùng để đo máy nghe đúng hay sai, phục vụ một bài thi sinh viên.
2. Không công bố file âm thanh, không đăng tên bác ở đâu.
3. Bác đổi ý lúc nào cũng được, nhóm xoá ngay.

Chuẩn bị một tờ giấy đồng ý, xin chữ ký, chụp lại. **Chụp ảnh tờ giấy này đưa
vào mục 4.5 của bản đề xuất** — rất ít nhóm sinh viên làm, và giám khảo nhìn
là biết nhóm nghiêm túc.
