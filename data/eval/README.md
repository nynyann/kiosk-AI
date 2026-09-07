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

Tải bằng `python -m eval.prep_public --dataset <tên>`. Ghi lại **đúng phiên bản
và ngày tải** vào mục 4.2, giám khảo hỏi là trả lời được ngay.

| Bộ | HF repo | Dùng để làm gì | Giấy phép |
|---|---|---|---|
| VIVOS | `AILAB-VNUHCM/vivos` | Đọc chuẩn, phòng yên tĩnh, mức nền "điều kiện lý tưởng" | mở |
| FLEURS (vi) | `google/fleurs` | Bộ đa ngôn ngữ, tiện so với tài liệu quốc tế | mở |
| **VietMed** | `leduckhai/VietMed` | **Gần kiosk nhất**, xem mục dưới | MIT |
| **ViMD** | `nguyendv02/ViMD_Dataset` | Có nhãn `region` và tỉnh, bộ duy nhất tách được WER theo vùng miền | CC-BY-NC-ND-4.0 |
| Bud500 | `linhtran92/viet_bud500` | ~500h, đa dạng nhất, đo độ bền chung | auto-gated |
| VLSP2020 100h | `doof-ferb/vlsp2020_vinai_100h` | Bộ chuẩn hay được trích trong bài báo tiếng Việt | mở |
| FPT FOSD | `doof-ferb/fpt_fosd` | ~30h đọc chuẩn | CC-BY-4.0 |

### VietMed đáng chú ý riêng

Tập test: 3.437 câu, 6 giờ, 27 người nói. Nhãn của nó:

```
role:          Doctor 1582 | Podcaster 766 | Host 448 | Lecturer 384 | Patient 80
rec_condition: Podcast 766 | Talkshow 730 | Tel 607 | Consultation 446 |
               Lectures 384 | News 312 | Diagnosis 192
accent:        South West 1164 | South Central Coast 809 | South East 750 |
               North 693 | North Central Coast 21
```

Đây là tiếng nói **tự nhiên**, trong một **lĩnh vực chuyên ngành**, thu ở **điều
kiện thật**. Ba đặc điểm kiosk gặp mà VIVOS/FLEURS đều không có.
`rec_condition = Consultation / Diagnosis` là người dân nói chuyện với cán bộ
chuyên môn về việc của họ, cấu trúc y hệt kiosk chỉ khác lĩnh vực. `Tel` là âm
thanh qua điện thoại, thay được phần nào cho "môi trường ồn".

Và nó cho một câu mạnh để viết vào bài: **y tế tiếng Việt đã có bộ dữ liệu
chuyên ngành riêng, hành chính công thì chưa có bộ nào.** Đó đúng là khoảng
trống nhóm đang lấp.

### Common Voice: đã chuyển khỏi HuggingFace, và nhãn tuổi không dùng được

Common Voice **không còn tải qua `datasets` của HuggingFace**. Giờ phải lấy ở
Mozilla Data Collective, đăng nhập rồi tải thủ công một file `.tar.gz`:

<https://mozilladatacollective.com/datasets> → tìm "Vietnamese"
→ *Common Voice Scripted Speech 26.0 - Vietnamese* (461,86 MB, corpus
`cv-corpus-26.0-2026-06-12`)

Giải nén rồi dựng manifest, chia đều theo nhóm tuổi:

```bash
mkdir -p data/eval/public/cv_raw
tar -xzf <file tải về>.tar.gz -C data/eval/public/cv_raw
python -m eval.prep_public --dataset common_voice --limit 60
```

Đây là bộ tiếng Việt công khai **duy nhất có nhãn tuổi**. Nhưng đọc kỹ bảng
nhân khẩu của nó thì nhãn đó không dùng để kết luận được:

| Nhóm tuổi | Số clip | **Số người nói** |
|---|---|---|
| Twenties | 4.411 | 114 |
| Teens | 3.909 | 12 |
| **Sixties** | **5.044 (24,5%)** | **1** |
| **Seventies** | 840 | **3** |
| Fifties | 5 | 1 |
| Không khai | 5.143 | 288 |

Cột clip trông đẹp, gần 29% thuộc nhóm 60+. Cột người nói mới là sự thật:
**toàn bộ nhóm "sixties" là một người**, cả nhóm 60+ chỉ có bốn người. Đo WER
trên đó rồi viết "WER ở người cao tuổi là X%" là đang đo **một giọng cụ thể**.
Giám khảo nhìn cột speaker là hỏi ngay.

Bảng trên là số của cả bộ, lấy từ thẻ dữ liệu. Mở file ra đếm thì còn khắc
nghiệt hơn:

| File | Nhóm 60+ |
|---|---|
| `test.tsv` (tập test chính thức, 1005 dòng) | **0 clip nhóm sixties**, đúng 1 clip nhóm seventies |
| `validated.tsv` (4875 dòng) | 2816 clip nhóm sixties, nhưng chỉ từ **2 người** |

Nói cách khác, **tập test chính thức của Common Voice tiếng Việt không có người
cao tuổi**. Muốn có clip 60+ thì phải lấy từ `validated.tsv`, và khi đó đang đo
đúng hai giọng. `eval/prep_public.py` vì vậy dùng `validated.tsv` và in số
người nói của từng nhóm mỗi lần chạy, để không ai lỡ tay trích con số đó ra như
thể nó đại diện cho người cao tuổi nói chung.

Nhóm đã thử đo thật để xem chuyện gì xảy ra. PhoWhisper-small trên 60 câu chia
đều hai nhóm tuổi cho ra kết quả **ngược hẳn giả thuyết của bài**:

```
18-44   n=30   WER 16,2%
60+     n=30   WER  4,1%     <- người cao tuổi được nghe ĐÚNG hơn?
```

Tách tiếp theo từng người nói thì rõ ngay vì sao:

```
60+     một người            29 câu    WER  2,7%
60+     một người khác        1 câu    WER 44,4%
18-44   17 người khác nhau   30 câu    WER 0% đến 58,3%
```

Con số "4,1%" chỉ là WER của **một bác cụ thể**, người đã đóng góp 2816 clip
cho Common Voice và gần như chắc chắn có micro tốt cùng cách đọc rất rõ. Nhóm
18-44 thì gồm 17 người với đủ loại thiết bị nên phân tán rộng.

Đây là ví dụ sạch sẽ về **biến gây nhiễu theo người nói**: khi một nhóm chỉ có
một hai người, cột "nhóm tuổi" không còn đo tuổi nữa mà đo đúng mấy người đó.
Đưa ví dụ này vào mục phương pháp thì vừa cho thấy nhóm biết đọc số liệu, vừa
là lý do thuyết phục nhất để phải tự thu tập kiểm thử.

Thêm hai điều: 64,5% câu trong bộ lấy từ *Từ Điển Tiếng Huế* (Bùi Minh Đức,
2001) nên nội dung nghiêng hẳn về phương ngữ Huế; và bảng lĩnh vực văn bản có
`history_law_government` = **0 clip**, tức là không một câu từ vựng hành chính.

**Dùng bộ này cho hai việc thôi:** lấy WER nền tổng thể, và trích đúng bảng trên
vào mục 2.4 làm bằng chứng số cho câu "không bộ công khai nào có thứ ta cần".
Không dùng để kết luận về nhóm 60+.

> Giấy phép Common Voice **cấm re-host và re-share**. File `.tar.gz` đã được
> `.gitignore` loại ra, đừng bao giờ commit nó.

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
