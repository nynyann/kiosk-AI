# Tổng hợp giải pháp Kiosk hướng dẫn thủ tục hành chính

Cập nhật ngày 17/09/2026, theo nhánh `main` của repo
`nynyann/kiosk-backend`. Tài liệu bao gồm mọi thông tin kỹ thuật và mọi con
số đã đo để cả nhóm đọc và điền vào bản đề xuất giải pháp. Con số nào là đo
thật thì ghi "đo thật", con số nào chưa có thì ghi "chưa có", không ước lượng -> sẽ quyết định điền hoặc bỏ.

Mục lục

1. Giải pháp là gì
2. Kiến trúc chung
3. Mô hình nhận dạng giọng nói
4. Chuẩn hoá văn bản sau nhận dạng
5. Đọc thành tiếng
6. Kho tri thức 6 thủ tục
7. Luồng hướng dẫn 3 bước (backend)
8. Giao diện kiosk (frontend)
9. Bảng số đo
10. Triển khai
11. Giới hạn trong bài
12. Lịch sử phát triển trên git
13. Việc còn lại và ai làm
14. Gợi ý lấy số nào cho mục nào của bản đề xuất

---

## 1. Giải pháp là gì

Một kiosk đặt tại bộ phận một cửa, nghe người cao tuổi nói nhu cầu bằng lời
thường ("tôi 76 tuổi, không có lương hưu thì được hỗ trợ gì"), nhận ra thủ
tục hành chính tương ứng, rồi hướng dẫn theo từng bước đúng sơ đồ nhóm đã
vẽ:

    Bắt đầu
      -> Bước 1. Kiểm tra điều kiện (kiosk hỏi từng câu: tuổi, công dân,
         lương hưu, trợ cấp BHXH, hộ nghèo ...)
           -> Đáp ứng: Bước 2. Chuẩn bị hồ sơ (giấy tờ theo đúng trường hợp,
              hỏi thêm thì trả lời từ kho tri thức của thủ tục đó)
              -> Bước 3. Nộp hồ sơ (nộp ở đâu, mang gì, cơ quan xử lý,
                 thời hạn) -> Kết thúc
           -> Không đáp ứng: giải thích điều kiện chưa đạt, kết luận
              không đủ điều kiện -> Kết thúc

Toàn bộ nhận dạng giọng nói, tra kho và đọc thành tiếng chạy trên một máy
chủ, không gửi âm thanh ra ngoài, không lưu âm thanh xuống đĩa. Từ 16/09 có
thêm một tầng mô hình ngôn ngữ trên FPT AI Marketplace (trả phí theo lượt,
chỉ gửi văn bản, tắt được), xem mục 7b.

Phạm vi: người cao tuổi và người dân tộc thiểu số nói tiếng Việt (có thể kèm
giọng vùng). Không nhận dạng tiếng dân tộc (Tày, H'Mông, Khmer ...). Người
không nói được vẫn dùng được bằng cách bấm chọn trên màn hình.

---

## 2. Kiến trúc chung

Một dịch vụ duy nhất, viết bằng Python (FastAPI), phục vụ luôn trang giao
diện ở `/` và API ở các đường dẫn còn lại. Không cần build frontend, không
npm, không cơ sở dữ liệu.

    Trình duyệt (kiosk, điện thoại)
      |  ghi âm webm/opus, gửi lên
      v
    FastAPI (app/main.py)
      |-- /turn            nghe -> nhận ra thủ tục
      |-- /flow/*          luồng 3 bước
      |-- /tts             chữ -> mp3 giọng Việt
      |-- /health, /warmup, /procedures, /kb/reload
      |
      |-- app/asr.py       ffmpeg -> wav 16 kHz -> PhoWhisper (CTranslate2)
      |-- app/normalize.py chuẩn hoá văn bản nhận dạng
      |-- app/kb.py        nạp data/kb/*.json, tra cứu thủ tục
      |-- app/flow.py      máy trạng thái bước 1 -> 2 -> 3
      |-- app/llm.py       gọi mô hình ngôn ngữ FPT AI Marketplace, tắt được
      |-- app/tts.py       đọc mp3 từ data/tts/, thiếu mới gọi edge-tts
      |
      v
    data/kb/*.json          6 thủ tục, mỗi thủ tục một file
    data/tts/*.mp3          112 câu đã sinh sẵn tiếng, đi theo repo

Kích thước mã nguồn (đếm ngày 16/09/2026): backend `app/` 2.752 dòng Python,
giao diện `web/index.html` 981 dòng, công cụ đo `eval/` 875 dòng, kịch bản
`scripts/` 3 file, test 4 file với 64 test. Tổng khoảng 5.600 dòng.

Thư viện chính (ghim phiên bản trong `requirements.txt`): fastapi 0.115.6,
uvicorn 0.34.0, faster-whisper 1.1.1, ctranslate2 4.8.2, edge-tts 7.2.8,
httpx 0.28.1 (gọi mô hình ngôn ngữ).

Giao kèo API viết ở `API_CONTRACT.md`, phiên bản 2.2. Mọi phản hồi đều có
trường `ok`; lỗi thì có `error` là câu tiếng Việt hiển thị thẳng cho người
dân được.

---

## 3. Mô hình nhận dạng giọng nói

### Chọn gì

PhoWhisper của VinAI (`vinai/PhoWhisper-small` và `vinai/PhoWhisper-base`),
là Whisper của OpenAI được tinh chỉnh thêm trên 844 giờ tiếng Việt đa vùng
miền. Nhóm tự chuyển sang định dạng CTranslate2, lượng tử hoá int8, chạy
bằng faster-whisper trên CPU, không cần GPU.

Hai bản đã chuyển và đưa lên HuggingFace công khai:

| Bản | Repo | Dung lượng | Dùng ở đâu |
|---|---|---|---|
| PhoWhisper-small | `owmeowmeownyny/PhoWhisper-small-ct2` | 240 MB | máy nhà, hôm chấm, mọi số đo WER |
| PhoWhisper-base | `owmeowmeownyny/PhoWhisper-base-ct2` | 77 MB | bản triển khai trên Render |

Mô hình đối chứng: Whisper-small gốc của OpenAI (bản CTranslate2
`Systran/faster-whisper-small`, 464 MB).

Lý do chọn PhoWhisper thay vì Whisper gốc: đo trên 5 bộ dữ liệu công khai
(bảng ở mục 9), PhoWhisper-small thấp hơn Whisper-small từ 8 đến 19 điểm WER
tuyệt đối, 4 trên 5 bộ có khoảng tin cậy tách rời.

Lý do bản triển khai dùng base chứ không phải small: gói máy chủ miễn phí
512 MB RAM. PhoWhisper-small đỉnh 371 MB, cộng FastAPI và bộ đệm tiếng là
tràn, đã bị giết thật giữa lượt nhận dạng thứ hai. PhoWhisper-base đỉnh
244 MB và nhanh gấp 8 lần ở 1 luồng CPU. Số đo WER trong bài là của small,
link Render chạy base, hai cái không phải một, phải ghi rõ.

### Cách chạy

- Trình duyệt gửi webm/opus, ffmpeg đổi sang wav 16 kHz mono.
- faster-whisper, beam size 5, ngôn ngữ cố định `vi`, compute type int8.
- Điểm tin cậy lấy từ xác suất trung bình của các đoạn; dưới 0,45 coi như
  nghe không rõ, mời nói lại. Xác suất "không có tiếng nói" trên 0,6 coi
  như im lặng.
- Nạp mô hình một lần lúc khởi động (hoặc lười, nạp ở lượt đầu, rồi
  `POST /warmup` để nạp trước). Nạp hỏng thì `/health` nói lý do trong
  `asr_error`, gọi `/warmup` thử lại được.

---

## 4. Chuẩn hoá văn bản sau nhận dạng

`app/normalize.py`, 4 việc theo thứ tự:

1. Dọn thô: bỏ dấu câu thừa, gộp khoảng trắng, hạ chữ thường.
2. Bỏ từ đệm người cao tuổi hay nói: "ờ", "à", "thì là", "nói chung là" ...
   Giữ nguyên từ xưng hô "ạ", "dạ", "bác", "cô", "chú" và tiểu từ cuối câu
   ("bác à").
3. Số viết bằng chữ thành chữ số: "bảy mươi sáu" thành "76". Cẩn thận với
   "ba năm" (ba cái năm, không phải 3 rồi 5).
4. Sửa cụm hành chính bị nghe nhầm: bảng `HARD_FIXES` 38 cụm ("cư chú" thành
   "cư trú", "hộ tích" thành "hộ tịch" ...), cộng so khớp mờ cho các cụm
   gần giống.

Chiều ngược lại `for_speech()` đổi chữ số thành chữ để đọc thành tiếng
("15 giờ" thành "mười lăm giờ", "41/2024/QH15" thành "bốn mươi mốt trên hai
nghìn hai mươi bốn trên QH mười lăm").

Số đo: trên các bộ công khai, chuẩn hoá chỉ giảm WER 0 đến 0,4 điểm (FLEURS
12,4% xuống 12,0%), vì các bộ đó không có từ vựng hành chính. Hai lỗi chuẩn
hoá tìm được nhờ đo thật (nuốt số trong "ba năm", bỏ mất "à" cuối câu) đã
sửa và có test. Mức cải thiện trên tập tự thu có từ vựng hành chính: chưa
có, vì tập tự thu chưa thu (mục 11).

---

## 5. Đọc thành tiếng

Giọng đọc lấy từ edge-tts (giọng neural tiếng Việt của Microsoft Edge,
miễn phí, không cần khoá). Giọng mặc định `vi-VN-HoaiMyNeural` (nữ), tốc độ
chậm hơn gốc 8% cho người già nghe kịp, đổi được bằng biến môi trường.

Vì sao không để trình duyệt tự đọc: Web Speech API chỉ đọc được thứ tiếng
hệ điều hành đã cài giọng, máy Windows ở ta thường chỉ có giọng tiếng Anh
nên đọc chữ Việt bằng giọng Mỹ, không nghe ra. Giọng trình duyệt vẫn giữ
làm đường lùi cuối cùng.

Kho mp3 đi theo repo (thêm ngày 15/09/2026). Dịch vụ của Edge hỏng ngẫu
nhiên với giọng tiếng Việt: đo cùng một câu, cùng giọng, có đợt hỏng 5/6
lần liên tiếp, câu có "!" hoặc "?" hỏng nhiều hơn, có đợt mọi tốc độ khác
mặc định đều hỏng; máy chủ thật vì thế đã lặng hẳn mấy hôm mà log chỉ ghi
`tts_failed`. Mọi câu kiosk nói đều biết trước (sinh từ kho tri thức), nên
`scripts/build_tts_cache.py` sinh mp3 một lần ở máy nhà, thử lại tới khi
đủ, ghi vào `data/tts/` và commit theo repo: 112 file, 11,5 MB. Máy chủ đọc
từ đĩa trước, khởi động xong báo 112/112 câu có sẵn, không cần mạng cho
câu quen. Chỉ câu chưa có mới gọi Edge, lúc đó đổi "!" "?" thành "." và thử
4 lần trong hạn giờ (2 lần giữ tốc độ cấu hình, 2 lần tốc độ mặc định),
được thì ghi luôn xuống đĩa. Sửa kho tri thức xong phải chạy lại kịch bản
và commit cả mp3.

Trình duyệt chặn phát tiếng khi trang chưa có thao tác chạm nào (chính sách
autoplay), nên câu chào lúc mới vào từng bị chặn lặng lẽ. Giao diện có màn
«Chạm vào màn hình để bắt đầu»: chạm một cái là mở khoá tiếng cho cả phiên,
máy chào ngay; trong lúc màn này hiện, giao diện tải sẵn mp3 câu chào (đo:
43 ms từ đĩa) nên chạm là nói liền.

Số đo (đo thật ở trình duyệt):

| Khoản | Số |
|---|---|
| Từ lúc chữ hiện tới lúc có tiếng, không sinh sẵn | 2,5 giây im lặng |
| Cùng khoản, có sinh sẵn lúc khởi động | 0,02 đến 0,3 giây |
| Sinh một câu lúc nguội | 1,6 đến 13,9 giây, có lúc 55,8 giây |
| Sinh cùng câu lần sau | 1 đến 2 giây |
| Số câu sinh sẵn lúc khởi động | khoảng 130 câu cho 6 thủ tục, chạy nền |
| Kho mp3 đi theo repo (`data/tts/`) | sinh một lần ở máy nhà bằng `scripts/build_tts_cache.py`, máy chủ đọc từ đĩa trước, không phụ thuộc mạng cho câu quen |
| Tỷ lệ dịch vụ Edge trả lỗi với giọng Việt, đo 15/09/2026 | có đợt 5/6 lần liên tiếp, là lý do phải có kho mp3 |

---

## 6. Kho tri thức 6 thủ tục

Mỗi thủ tục một file JSON trong `data/kb/`, chuyển từ kho tri thức bản
17/09/2026 của Mian (file Excel `data/kb-source/Kho moi tri thuc 6 thu tuc.xlsx`,
mỗi sheet một thủ tục, ghi mã thủ tục trên Cổng Dịch vụ công, đối tượng, cơ
quan, cách thức, thời hạn, lệ phí, và kịch bản hỏi đáp từng bước). Mỗi file
ghi `verified_by` và `verified_date`. Nguyên tắc: không có nguồn thì không
viết; máy chỉ đọc lại đúng những gì có trong file, không sinh thêm.

| Mã trong repo | Mã thủ tục | Thủ tục | Lệ phí | Thời hạn |
|---|---|---|---|---|
| `tro-cap-huu-tri-xa-hoi` | 1.014027 | Trợ cấp hưu trí xã hội (xin mới, điều chỉnh, thôi hưởng); mức 500.000 đồng một tháng | không | 10 ngày làm việc |
| `tro-cap-xa-hoi-hang-thang` | 1.001776 | Trợ cấp xã hội hằng tháng (xin mới theo 5 nhóm đối tượng, điều chỉnh, thôi hưởng) | không | 10 ngày làm việc |
| `cap-the-bao-hiem-y-te` | 1.014137 | Cấp thẻ BHYT (cấp mới giấy hoặc điện tử, sửa thông tin, hỏi quyền lợi) | không | 05 ngày làm việc |
| `cap-ban-sao-trich-luc-ho-tich` | 2.000635 | Cấp bản sao giấy khai sinh, trích lục hộ tịch | 8.000 đồng một bản | trong ngày, sau 15 giờ thì hôm sau |
| `chung-thuc-ban-sao` | 2.000815 | Chứng thực bản sao từ bản chính | 2.000 đồng một trang cho 2 trang đầu, từ trang 3 là 1.000 đồng, tối đa 200.000 đồng một bản | trong ngày, phức tạp thêm tối đa 02 ngày làm việc |
| `cap-the-can-cuoc` | 2.000200 | Cấp thẻ căn cước: lần đầu, đổi hoặc cập nhật, mất thẻ | lần đầu miễn phí; đổi CCCD sang căn cước 30.000; cấp đổi 50.000; cấp lại 70.000 đồng một thẻ | 07 ngày làm việc |

Mỗi file có hai phần:

- Phần tra cứu: tên, các cách người dân gọi (`aliases`), từ khoá, hồ sơ,
  nơi nộp, phí, thời hạn, nguồn.
- Phần luồng (`flow`): câu hỏi bước 1, câu đầu luôn là «bác muốn làm gì»
  (xin mới, điều chỉnh, thôi hưởng; làm thẻ lần đầu, đổi, mất…) rồi mới tới
  điều kiện; tổng 30 câu hỏi và 31 quy tắc kết luận cho 6 thủ tục; lời dẫn
  bước 2 và bước 3; 16 nút chọn cách nộp ở bước 3 (trực tiếp, trực tuyến,
  bưu chính, mỗi nút một câu máy nói); FAQ. Mục cách kê khai mẫu đã bỏ
  ngày 17/09 vì chưa có mẫu in nào được đối chiếu. Cách viết ghi ở
  `data/kb/_SCHEMA.md`.

Kho bản 17/09 khác bản 11/09 ở chỗ: có mã thủ tục và lệ phí cụ thể; hưu trí
và trợ cấp hằng tháng có thêm nhánh điều chỉnh và thôi hưởng; BHYT thêm
nhánh sửa thông tin và hỏi quyền lợi; căn cước gộp ba trường hợp lần đầu,
đổi, mất vào một thủ tục với lệ phí riêng (trước đây đổi hoặc mất thì máy
chỉ báo «đây là thủ tục khác»); chứng thực hỏi thêm đã có bản photo chưa.

Thủ tục thứ 7 "xác nhận cư trú" viết lúc đầu để chạy thử, chưa kiểm chứng,
đã chuyển sang `data/kb-draft/`, không nạp vào kiosk.

Tra cứu thủ tục từ câu nói: so từ khoá và cụm gọi thông thường, có trọng số,
ngưỡng 0,55. Dưới ngưỡng thì mời gặp cán bộ và đưa danh sách để bấm chọn.
Chỗ này Kim thay bằng so khớp ngữ nghĩa nếu kịp (mục 13).

---

## 7. Luồng hướng dẫn 3 bước (backend)

`app/flow.py` là máy chạy, không chứa câu chữ hành chính nào. Máy chủ không
giữ phiên: giao diện gửi lại các câu đã trả lời mỗi lượt, máy chủ tính lại
từ đầu, nên máy chủ miễn phí khởi động lại giữa chừng cũng không mất trạng
thái của người dân.

Đường dẫn:

| Đường dẫn | Việc |
|---|---|
| `GET /procedures` | danh sách 6 thủ tục |
| `POST /flow/start` | vào bước 1, trả câu hỏi đầu |
| `POST /flow/answer` | người dân bấm chọn một lựa chọn |
| `POST /flow/answer-voice` | người dân trả lời bằng lời, máy ánh xạ sang lựa chọn |
| `POST /flow/next` | sang bước 3, kết thúc, hoặc quay lại câu trước |
| `POST /flow/ask` | hỏi thêm ở bước 2, 3, chỉ trả lời từ kho của thủ tục đó |

Bước 1 rẽ nhánh theo 4 loại kết luận:

- `eligible`: có khả năng thuộc diện, sang bước 2 với hồ sơ đúng trường
  hợp (điều chỉnh trợ cấp thì hồ sơ khác xin mới).
- `ineligible`: giải thích điều kiện nào chưa đạt, không bắt chuẩn bị hồ sơ.
- `consult`: không đủ thông tin, mời gặp cán bộ, máy không đoán.
- `redirect`: thực ra là thủ tục khác (đổi hoặc mất căn cước, đăng ký lại
  khai sinh), nói rõ và gợi ý thủ tục phù hợp nếu kho có.

Trả lời bằng lời ở bước 1: máy đọc số tuổi ("bảy mươi sáu tuổi" thành 76,
"dưới bảy mươi" thành 69), cụm đặc trưng của từng lựa chọn, và có/không (từ
phủ định thắng từ khẳng định để "không có" không thành "có"). Không ánh xạ
được thì giữ nguyên câu hỏi, mời bấm chọn.

Hỏi thêm ở bước 2, 3: tìm trong FAQ của thủ tục (ngưỡng 0,6), nếu câu hỏi
khớp rõ với thủ tục khác thì gợi ý chuyển, rồi mới tới các ý định chung
(nộp ở đâu, bao lâu, phí, mang gì). Không có gì khớp thì nói "chưa có trong
kho, bác hỏi cán bộ", không bịa.

Mọi câu máy có thể nói đều được liệt kê để sinh tiếng sẵn: câu hỏi, và
với kết luận, bước 2, bước 3 thì đi hết mọi đường trả lời có thể xảy ra
(mỗi thủ tục vài chục đường) vì ghi chú và hồ sơ đổi theo lựa chọn.

---

## 7b. Mô hình ngôn ngữ (FPT AI Marketplace), thêm ngày 16/09/2026

Làm theo phản hồi của ban giám khảo ngày 15/09: (1) nhớ ngữ cảnh trong
phiên, (2) hai thành phần nghe và trả lời, (3) thấu cảm khi bác kể hoàn
cảnh, (4) trả lời câu hỏi diễn đạt khác FAQ, (5) luồng demo dài hơn, (6)
tiếng Việt tự nhiên hơn.

Gọi API kiểu OpenAI tại `https://mkp-api.fptcloud.com/chat/completions`,
xác thực bằng khoá `FPT_API_KEY` (tài liệu: github.com/fpt-corp/ai-marketplace).
Mô hình mặc định `gemma-4-31B-it` (chọn sau khi đo, bảng dưới), đổi được
bằng biến `LLM_MODEL`. Hạn giờ 12 giây. Trong các API trên marketplace, nhóm sinh câu trả lời được là các LLM
kể trên; `Vietnamese_Embedding`, `multilingual-e5-large`, `bge-reranker` là
tìm kiếm ngữ nghĩa (chưa dùng, việc của Kim); các `whisper` là nghe (không
dùng vì phải gửi âm thanh ra ngoài).

Bốn chỗ dùng, chỗ nào cũng có đường lùi về kho tĩnh khi không có khoá, hỏng,
hết tiền hay quá hạn giờ:

| Chỗ | Có mô hình | Không có mô hình | Phản hồi số |
|---|---|---|---|
| Bác mở đầu «tôi 76 tuổi, không có lương hưu, sống một mình» | điền sẵn tuổi, lương hưu vào bước 1; nói «Cháu hiểu rồi ạ, bác 76 tuổi, chưa có lương hưu và sống một mình»; chỉ hỏi phần còn thiếu | điền sẵn bằng luật (số tuổi, cụm phủ định rõ), nói «Cháu ghi nhận: …» | 1, 3, 5 |
| Câu nói không khớp từ khoá («tôi già rồi nhà nước có cho đồng nào không») | mô hình chọn trong 6 thủ tục, máy hỏi lại mềm «Nếu cháu hiểu đúng thì…» | chuyển cán bộ, đưa danh sách bấm chọn | 4 |
| Trả lời câu bước 1 bằng lời mà so cụm từ không ra | mô hình ánh xạ sang một lựa chọn có sẵn, không được bịa lựa chọn | mời bấm chọn | 4 |
| Hỏi thêm ở bước 2, 3 diễn đạt khác FAQ, hoặc kể thêm hoàn cảnh | mô hình đọc toàn bộ kho tri thức của thủ tục (kể cả cách kê khai mẫu) + tuổi, lương hưu đã trả lời + các lượt hỏi trước, viết câu trả lời tối đa 3 câu | ý định chung (nộp đâu, bao lâu, phí, mang gì) hoặc mời hỏi cán bộ | 1, 3, 4, 6 |
| Câu ngoài kho, câu máy nghe nhầm thành vô nghĩa, «cháu tên gì» | mô hình viết 1 đến 2 câu tử tế (là máy hướng dẫn nên chỉ giúp về thủ tục này; hỏi cán bộ giúp; mời nói lại), không bịa | câu cứng «Câu này cháu chưa có trong kho» | 6 |
| Câu nói ứng với nhiều thủ tục («tôi muốn xin trợ cấp») | mô hình liệt kê tối đa 3 thủ tục, giao diện hỏi «cần hỗ trợ thủ tục nào trước» | từ khoá đủ điểm thì một thủ tục, không thì danh sách 6 | 5 |

Nguyên lý giới hạn mô hình trong kho (câu hỏi của nhóm 17/09): kiosk KHÔNG
hỏi mô hình «trợ cấp hưu trí là gì» rồi tin câu trả lời. Mỗi lượt, máy chủ
nhét toàn bộ kho tri thức của đúng thủ tục đó vào prompt, kèm câu bác hỏi
và những gì bác đã trả lời, và dặn: chỉ được dùng thông tin trong đây, trả
JSON `{in_kb, answer}`, `in_kb=false` khi kho không có. Đó là lớp mềm (lời
dặn). Trên đó có bốn lớp cứng do máy chủ kiểm, mô hình không vượt được:
(1) điều kiện điền sẵn chỉ nhận đúng mã lựa chọn có trong kho, kèm bằng
chứng trích nguyên văn từ câu bác nói; (2) thủ tục gợi ý chỉ nhận mã có
trong 6 thủ tục; (3) câu trả lời có con số (ngày, tuổi, số mẫu, số nghị
định, mức tiền) mà con số đó không có trong kho thì bỏ cả câu, về câu mời
gặp cán bộ; (4) hỏng, quá 12 giây, hết số dư thì về kho tĩnh. Kết quả: mô
hình chỉ diễn đạt lại kho, không được đưa thêm sự kiện. Không kết luận
«chắc chắn được hưởng». FAQ khớp rõ vẫn lấy nguyên văn kho
(có sẵn tiếng, không tốn lượt gọi). Máy chủ vẫn không giữ phiên: ngữ cảnh
(câu mở đầu, các câu đã trả lời, các lượt hỏi thêm) do giao diện gửi lại
mỗi lượt.

Số đo (đo thật ngày 16/09/2026 trên khoá thật, cùng 8 tác vụ của kiosk):

| Mô hình | Độ trễ mỗi lượt | Điền sẵn từ lời kể | Nhận thủ tục từ câu lạ | Câu ngoài kho | Giá (USD mỗi triệu token vào/ra) | Kết luận |
|---|---|---|---|---|---|---|
| gemma-4-31B-it | 0,3 đến 1,1 giây | đúng phần bác nói, không suy diễn | đúng | trả đúng mã | 0,15 / 0,45 | chọn làm mặc định |
| Saola-Small-32B | 0,2 đến 1,9 giây | điền bừa: tự cho «công dân = có», «BHXH = không» dù bác không nói | không nhận ra | trả lời thay vì báo ngoài kho | 0,13 / 0,15 | không dùng |
| gemma-3-27b-it | 0,3 đến 1,6 giây | đúng | đúng | dài dòng | 0,11 / 0,17 | dự phòng |
| DeepSeek-V4-Flash | 1 đến 11 giây | đúng | không | trả rỗng | 0,14 / 0,28 | chậm, không dùng |
| Qwen3.6-27B | 0,4 đến 2 giây | trả rỗng | trả rỗng | trả rỗng | 0,30 / 3,25 | không dùng |

Sau khi chốt gemma-4-31B-it, chạy 18 câu hỏi thêm thực tế trên máy chủ với
ngữ cảnh bác 76 tuổi, chồng mất, ở một mình, không lương hưu: 16/18 trả lời
đúng từ kho và mở đầu bằng câu xác nhận hoàn cảnh («Cháu hiểu bác đi lại khó
khăn ạ. Bác có thể gửi hồ sơ qua bưu điện…»), 2 câu ngoài kho («giá vàng hôm
nay», «cháu tên gì») mời gặp cán bộ, 0 câu nhắc giấy tờ hay con số không có
trong kho. Độ trễ trung bình 2,9 giây, tối đa 3,2 giây, prompt khoảng 2.500
token vì chứa cả kho tri thức của thủ tục. 5/5 câu nói lạ nhận đúng thủ
tục («cháu ơi bà muốn có cái thẻ đi khám bệnh cho rẻ» ra bảo hiểm y tế,
«photo cái sổ đỏ mang lên xã đóng dấu» ra chứng thực). Chi phí khoảng 0,001
USD một lượt.

Hai lỗi tìm được khi đo và đã sửa: FAQ so khớp theo từ bị lừa bởi «có…
được… không» và bởi mẫu một từ («tiền» khớp «ưu tiên»), nay bỏ từ rỗng và
mẫu dưới 2 từ nội dung chỉ khớp nguyên văn; «cần mang căn cước không» hỏi
giữa lúc làm trợ cấp từng bị gợi ý chuyển sang thủ tục căn cước, nay có mô
hình thì hỏi mô hình trước, chỉ gợi ý chuyển khi mô hình bảo ngoài kho.

Chốt an toàn khi điền sẵn: mô hình phải trích nguyên văn câu bác nói làm
bằng chứng cho từng điều kiện; đoạn trích phải có thật trong câu, không
dùng chung cho hai câu, và phải có từ nội dung trùng với câu hỏi đó. Chốt
này chặn đúng lỗi Saola điền bừa. 16 test với mô hình giả kiểm các đường
đi này, không gọi mạng.

---

Token mỗi lượt (giảm ngày 17/09 theo yêu cầu bớt tốn): prompt trả lời câu
hỏi thêm bỏ bảng câu hỏi và bảng kết luận của bước 1 (chỉ cần khi điền
sẵn), còn khoảng 1.500 token vào, tối đa 220 token ra; nhận thủ tục và hiểu
câu trả lời tự do mỗi lượt dưới 400 token. Test tự động không gọi mạng.

### Kho tri thức có hướng dẫn kê khai không (câu hỏi của nhóm ngày 17/09)

Trước 17/09: không. Kho chỉ ghi «xin mẫu tại quầy, cán bộ hướng dẫn điền»,
nên dù đã có mô hình, hỏi «mẫu số 2 là gì, điền thế nào» thì mô hình chỉ
nói lại được đúng câu đó: mô hình bị ép chỉ dùng kho, kho không có thì nó
không được bịa. Đó là lý do «đã gọi API mà vẫn không trả lời được».

Từ 17/09: thêm mục `flow.forms` cho ba thủ tục có mẫu (Mẫu số 01 trợ cấp
hưu trí xã hội, Mẫu số 2 bảo hiểm y tế, tờ khai trợ cấp xã hội hằng tháng):
xin mẫu ở đâu, điền bằng gì, từng mục của mẫu viết theo cách người dân
hiểu, mắt kém hay không biết chữ thì nhờ cán bộ điền rồi đọc lại. Mô hình
đọc mục này khi trả lời. Các mục mẫu là bản tóm tắt nhóm viết theo Nghị
định, **Mian phải đối chiếu với mẫu in** (trường `forms_note` trong từng
file ghi rõ).

---

## 8. Giao diện kiosk (frontend)

`web/index.html`, một file, không build. Dạng hội thoại: máy nói một câu
bên trái, người dân trả lời một câu bên phải, khung dưới cùng chỉ hiện đúng
việc cần làm lúc đó.

Bản 3 (17/09/2026) theo ý tưởng của nhóm: màn hình chia hai, bên trái là
trợ lý AI (biểu tượng, ô thoại trên đầu hiện câu máy vừa nói kèm hướng dẫn
cách trả lời, dưới là câu bác vừa nói và lịch sử), bên phải là việc bác cần
làm lúc đó. Micro luôn hiện ở góc dưới phải. Nút nào cần bấm tiếp thì nhấp
nháy ánh sáng (nút Bắt đầu, các ô xưng hô, các thủ tục gợi ý, các lựa chọn
bước 1, micro khi tới lượt bác nói, nút sang bước tiếp).

Trình tự màn hình:

0. Trang chủ: thanh menu (Trang chủ, Thủ tục, Hướng dẫn, Góp ý); góc dưới
   trái là hòm thư và số điện thoại góp ý; giữa là nút Bắt đầu (cái chạm
   này mở khoá tiếng, xem mục 5).
1. Máy chào bằng chữ và bằng tiếng: "Xin chào bác! Cháu là máy hướng dẫn
   làm thủ tục hành chính. Bác cần làm gì ạ?" kèm cách nói; micro nhấp nháy.
   Xưng hô để trung tính "bác" cho mọi người (nhóm quyết 17/09). Máy chủ
   vẫn nhận `pronoun` (ông, bà, cô, chú, anh, chị) nếu sau này muốn cho
   chọn, thay vào mọi câu kể cả câu đọc.
2. Bác nói. Máy đưa ra thủ tục nó hiểu ở bên phải: một thủ tục thì hỏi
   "đúng không ạ?", nhiều thủ tục thì hỏi "cần hỗ trợ thủ tục nào trước
   ạ?". Danh sách đủ 6 thủ tục chỉ hiện khi máy không hiểu hoặc bác bấm
   "không nói được".
3. Bác bấm chọn thủ tục.
4. Bước 1: hỏi từng câu, bắt đầu từ tuổi. Mỗi câu kèm dòng hướng dẫn cách
   trả lời ("Bác nói số tuổi, ví dụ tôi bảy mươi sáu tuổi, hoặc bấm chọn
   một ô bên dưới"). Trả lời xong mới hiện câu tiếp. Có nút "Trả lời bằng
   lời", "Nghe lại", "Quay lại câu trước".
5. Kết luận bước 1 (đủ hoặc chưa đủ điều kiện), rồi Bước 2, Bước 3 hiện
   thành thẻ trong bong bóng: danh sách giấy tờ có ô đánh dấu, lưu ý theo
   trường hợp, nơi nộp, cách nộp, cơ quan xử lý, thời hạn, nguồn văn bản.
   Có nút "Hỏi thêm" bằng lời.
6. Kết thúc, tự về màn hình chào sau 15 giây. Không ai chạm gì trong 2 phút
   thì cũng tự về, xoá sạch trạng thái cho người tiếp theo.

Thanh tiến trình 1, 2, 3 ở đầu trang. Chữ to (cỡ chữ thân 1,1 đến 1,45 rem
tuỳ màn hình), nút bấm tối thiểu 68 px, tương phản cao, chạy được khổ điện
thoại 375 px đến màn hình kiosk. Mọi câu máy nói đều được đọc thành tiếng.

Bảng gỡ lỗi ẩn: bấm 3 lần vào chữ "Kiosk thủ tục" để đổi địa chỉ máy chủ.

Ràng buộc kỹ thuật quan trọng: micro chỉ mở được trên https hoặc đúng chữ
`localhost`. Gửi nhau địa chỉ `192.168.x.x` cùng Wi-Fi là micro hỏng (đo
thật: `navigator.mediaDevices` là `undefined`).

---

## 9. Bảng số đo

### 9.1 WER trên bộ dữ liệu công khai (đo thật, PhoWhisper-small so với Whisper-small)

Cả hai chạy cùng cấu hình (CTranslate2 int8, beam 5, CPU), cùng số câu mỗi
bộ, ngày đo 10 đến 11/09/2026. KTC là khoảng tin cậy 95% bootstrap.

| Bộ dữ liệu | n | PhoWhisper-small | KTC 95% | Whisper-small | KTC 95% | Chênh | Kết luận |
|---|---|---|---|---|---|---|---|
| VIVOS | 50 | 4,9% | 2,4 đến 7,9 | 18,1% | 13,7 đến 23,3 | 13,1 điểm | KTC tách rời |
| Common Voice 26.0 | 60 | 10,0% | 6,0 đến 14,8 | 29,2% | 22,4 đến 36,6 | 19,2 điểm | KTC tách rời |
| FLEURS (vi) | 50 | 12,0% | 9,1 đến 15,2 | 21,3% | 17,4 đến 25,9 | 9,3 điểm | KTC tách rời |
| ViMD | 60 | 12,9% | 10,7 đến 15,3 | 27,6% | 23,9 đến 31,3 | 14,6 điểm | KTC tách rời |
| VietMed | 63 | 28,3% | 24,3 đến 32,6 | 36,4% | 32,4 đến 40,4 | 8,0 điểm | KTC chồng nhau, chưa đủ căn cứ nói tốt hơn |

Đọc số này phải kèm ba cảnh báo: các bộ này là người trưởng thành đọc trong
phòng yên tĩnh (trừ VietMed), không có nhãn tuổi dùng được, và không có câu
từ vựng hành chính nào. Nó là mức nền "điều kiện lý tưởng", không thay được
tập tự thu.

### 9.2 WER tách theo nhóm (PhoWhisper-small)

Theo vùng miền, bộ ViMD (bộ duy nhất có nhãn tỉnh):

| Vùng | n | PhoWhisper-small | Whisper-small |
|---|---|---|---|
| Bắc | 20 | 8,0% | 18,9% |
| Nam | 20 | 14,5% | 27,8% |
| Trung | 20 | 16,2% | 36,0% |

Theo điều kiện thu, bộ VietMed (tiếng nói tự nhiên, lĩnh vực y tế):

| Điều kiện | n | PhoWhisper-small | Whisper-small |
|---|---|---|---|
| Podcast | 9 | 14,7% | 18,8% |
| Bản tin | 9 | 18,2% | 33,8% |
| Chẩn đoán (bệnh nhân nói với bác sĩ) | 9 | 24,8% | 33,5% |
| Tư vấn | 9 | 27,1% | 42,1% |
| Qua điện thoại | 9 | 32,6% | 38,6% |
| Talkshow | 9 | 39,1% | 44,9% |
| Bài giảng | 9 | 41,9% | 42,8% |

"Chẩn đoán" và "Tư vấn" là người dân nói chuyện với cán bộ chuyên môn về việc
của mình, cấu trúc giống kiosk nhất chỉ khác lĩnh vực. Đó là con số gần
kiosk nhất đang có: khoảng 25 đến 27% với PhoWhisper-small.

Theo tuổi, bộ Common Voice: nhóm 60+ ra 3,9% (n=30) và nhóm 18 đến 44 ra
16,2% (n=30). KHÔNG được dùng số này để kết luận về người già: toàn bộ nhóm
"Sixties" của Common Voice tiếng Việt là 1 người nói, nhóm "Seventies" là 3
người. Số thấp là vì một người đọc chuẩn, không phải vì mô hình nghe người
già tốt hơn.

### 9.3 Tương quan giữa điểm tin cậy và lỗi

Hệ số tương quan giữa điểm tin cậy mô hình trả về và WER từng câu, âm là
đúng chiều (tin cậy cao thì lỗi thấp): PhoWhisper-small từ -0,25 (Common
Voice) đến -0,58 (VietMed); Whisper-small từ -0,64 đến -0,81. Điểm tin cậy
có dùng được để quyết định mời nói lại, nhưng không mạnh; ngưỡng 0,45 hiện
đặt tay, Kim tính lại bằng hàm chi phí kỳ vọng nếu kịp.

### 9.4 Tốc độ và tài nguyên (đo thật)

| Khoản | Số | Điều kiện |
|---|---|---|
| Một lượt hỏi đáp trọn vẹn (nghe + tra cứu) | 2,1 đến 2,8 giây | máy nhà, PhoWhisper-small, nhiều luồng CPU |
| Nhận dạng một câu, 8 luồng CPU | 5,6 giây | cùng câu, cùng model small |
| Nhận dạng một câu, 2 luồng CPU | 6,7 giây | |
| Nhận dạng một câu, 1 luồng CPU, small | 11,7 đến 12,6 giây | |
| Nhận dạng một câu, 1 luồng CPU, base | 1,5 giây | bản triển khai |
| Nạp model từ đĩa | 0,5 giây | |
| Nạp model từ HuggingFace lần đầu | khoảng 40 giây (bản tiny), lâu hơn với small | chỉ lần đầu, giờ nướng vào ảnh Docker |
| RAM đỉnh, PhoWhisper-small | 371 MB | bị giết thật trên gói 512 MB |
| RAM đỉnh, PhoWhisper-base | 244 MB | |
| RAM lúc chạy thật sau 5 lượt | 320 đến 380 MB | small |
| Kích thước model trên đĩa | small 240 MB, base 77 MB | int8 |
| Trên Render Free (ít hơn 1 nhân CPU) | mỗi câu khoảng 10 đến 15 giây với small; lượt đầu từng mất 130 giây | lý do đổi sang base |

### 9.5 Kiểm thử tự động

70 test, chạy dưới 10 giây, không cần mô hình nhận dạng và không gọi mạng:
12 test giao kèo API, 26 test luồng 3 bước (cả 6 file kho tri thức đủ
trường, rẽ nhánh đúng kho bản 17/09 kể cả ba nhánh căn cước, ánh xạ lời nói
sang lựa chọn, hỏi thêm không bịa, câu chào của giao diện khớp với chuỗi
máy chủ sinh sẵn), 18 test mô hình ngôn ngữ và xưng hô với mô hình giả
(mục 7b), 11 test chuẩn hoá và tính WER.

### 9.6 Con số chưa có

- WER trên tập tự thu (người cao tuổi, từ vựng hành chính, có ồn): chưa
  thu. Mẫu manifest `data/eval/testset.csv` có 10 dòng, chưa có file âm
  thanh. Đây là việc quan trọng nhất còn lại (mục 13).
- Tỷ lệ nhận đúng thủ tục từ câu nói tự nhiên trên người thật: chưa đo.
- Mức cải thiện WER nhờ chuẩn hoá trên từ vựng hành chính: chưa đo, vì phụ
  thuộc tập tự thu.
- Thời gian một người cao tuổi hoàn thành 3 bước trên kiosk: chưa đo.

---

## 10. Triển khai

- Docker, một ảnh, model nướng sẵn vào ảnh lúc build (Render xoá ổ đĩa mỗi
  lần ngủ dậy nên không tải lúc chạy). Kho mp3 `data/tts/` cũng nằm trong
  ảnh vì đi theo repo. `Dockerfile` ghi đè sang
  PhoWhisper-base và `ASR_CPU_THREADS=1`.
- Đặt trên Render gói Free: 512 MB RAM, ít hơn 1 nhân CPU, ngủ sau 15 phút
  vắng khách, thức dậy mất khoảng 1 phút, 750 giờ/tháng. Có
  `scripts/keepalive.py` để giữ máy thức từ hôm nộp tới hôm chấm.
- HuggingFace Spaces bản Docker cần gói trả phí nên không dùng; kho model
  trên HuggingFace thì miễn phí.
- Chỉ một dịch vụ vì giao diện và API cùng tên miền, không vướng CORS,
  không phải ghi địa chỉ máy chủ vào giao diện.
- Hôm chấm chạy trên máy nhà (small, nhanh, đúng model đã đo); link Render
  chỉ để gửi trước cho mọi người xem. Phương án dự phòng: chạy `MOCK=1` để
  ít nhất có link mở được, và quay sẵn video màn hình bản thật.

Lỗi đã gặp thật lúc triển khai (đều đã sửa, ghi trong `DEPLOY.md`):
ctranslate2 4.5.0 không nạp được trên Linux vì cờ executable stack (ghim
4.8.2); tràn RAM với small (đổi base); nạp model hỏng một lần thì hỏng mãi
(giờ `/warmup` thử lại được).

---

## 11. Giới hạn của bài

1. Chỉ nhận dạng tiếng Việt. Người dân tộc nói tiếng mẹ đẻ không được hỗ
   trợ; họ dùng kiosk qua phần chữ trên màn hình và nút bấm chọn, hoặc
   được chuyển cán bộ.
2. Số WER trong bài là trên bộ công khai, điều kiện lý tưởng, không có từ
   vựng hành chính, không có nhãn tuổi dùng được. Tập tự thu chưa có. Gọi
   đúng tên "tập kiểm thử nội bộ" khi có, không gọi là "bộ dữ liệu".
3. Số đo là của PhoWhisper-small; bản chạy trên Render là base, nghe kém
   hơn và chậm hơn vì máy chủ miễn phí.
4. Trên VietMed, hai khoảng tin cậy chồng nhau, chưa đủ căn cứ nói PhoWhisper
   tốt hơn Whisper gốc ở điều kiện tự nhiên.
5. Tra cứu thủ tục bằng từ khoá; câu diễn đạt lạ chỉ nhận ra được khi bật
   mô hình ngôn ngữ (cần khoá trả phí). Chưa dùng embedding ngữ nghĩa.
5b. Tầng mô hình ngôn ngữ đã đo trên khoá thật (mục 7b) nhưng mới trên 18
   câu hỏi và 5 câu nói lạ do nhóm tự đặt, chưa phải người cao tuổi thật.
   Mỗi lượt hỏi thêm mất 2 đến 3 giây và tốn khoảng 0,001 USD; mất mạng
   hoặc hết số dư thì tự lùi về kho tĩnh.
6. Kiosk không kết luận "chắc chắn được hưởng"; luôn nói "có khả năng thuộc
   diện" và cơ quan có thẩm quyền xem xét. Không đủ thông tin thì mời gặp
   cán bộ. Kho tri thức là 6 thủ tục thử nghiệm, không thay cơ sở dữ liệu
   thủ tục hành chính của Nhà nước.
7. Đọc thành tiếng: câu quen đã có mp3 sẵn trong repo, không cần mạng. Câu
   lạ (kho tri thức vừa sửa mà chưa sinh lại) mới cần mạng, và dịch vụ Edge
   hỏng ngẫu nhiên; mất mạng hoặc hỏng thì rơi về giọng trình duyệt, có thể
   không phải giọng Việt. Trình duyệt chặn phát tiếng trước thao tác chạm đầu
   tiên, nên có màn «Chạm vào màn hình để bắt đầu».
8. Không lưu âm thanh; chỉ ghi nhật ký văn bản để cải tiến.

---

## 12. Lịch sử phát triển trên git

Repo `nynyann/kiosk-backend`, nhánh `main`, 29 commit từ 07/09 đến 17/09/2026
(mã commit ghi theo lịch sử hiện tại trên GitHub).

| Commit | Nội dung |
|---|---|
| f034503 | Khởi tạo backend: FastAPI, PhoWhisper, kho tri thức 1 thủ tục, chuẩn hoá, giao kèo API 1.0 |
| a619798 | Sunny: dọn README |
| d489140 | Sửa hai lỗi chuẩn hoá tìm được khi đo WER thật |
| 6e568ee | Bộ công cụ đo trên dữ liệu công khai (VIVOS, FLEURS, VietMed, ViMD, Common Voice) |
| ac422c1 | Ép lỗi kiểm tra dữ liệu về đúng định dạng giao kèo |
| 86203cd | Gộp giao diện vào chung repo, máy chủ phục vụ luôn trang kiosk |
| de8f5cc | Thêm .dockerignore, tách pytest ra requirements-dev |
| 7a0e61a | Máy chủ tự sinh tiếng Việt (edge-tts) thay vì nhờ trình duyệt đọc; API 1.1 |
| 21b7e67 | Sửa câu báo lỗi micro gây hiểu nhầm, thêm hướng dẫn triển khai |
| 391e8fb | Nướng model vào ảnh Docker, viết lại hướng dẫn Render |
| e885bb2 | Nạp mô hình hỏng không còn hỏng vĩnh viễn, /health nói lý do; API 1.2 |
| 34c33b6 | Ghim ctranslate2 4.8.2 vì 4.5.0 không nạp được trên Linux |
| 89625c7 | Bản triển khai đổi sang PhoWhisper-base, ghim 1 luồng CPU |
| a308283 | Lắp 6 thủ tục của Mian vào kho tri thức |
| e95a025 | Luồng 3 bước theo sơ đồ: kiểm tra điều kiện, chuẩn bị hồ sơ, nộp hồ sơ; API 2.0 |
| df008fd | Giao diện thành hội thoại từng bước: chào, hỏi bác cần gì, rồi mới hỏi từng điều kiện |
| 2799258 | Thêm TONG-HOP.md, tài liệu này |
| 19f4da3 | Màn chạm để bắt đầu (mở khoá tiếng), kho mp3 đi theo repo, thử lại khi Edge hỏng |
| 8c70cd7 | Cập nhật TONG-HOP.md theo lần sửa 15/09 |
| 0661e70, 5d7465f, 107a089, fe9d9f5 | Sunny: sửa tài liệu và tên người kiểm chứng kho tri thức |
| ab9c228 | Bỏ cấu hình riêng của máy cá nhân khỏi repo |
| aeab1bf | Nối mô hình ngôn ngữ FPT AI Marketplace theo phản hồi giám khảo: nhớ ngữ cảnh, hiểu hoàn cảnh, trả lời ngoài FAQ, lời tự nhiên; API 2.1; 61 test |
| dcc4308 | Đo 5 mô hình trên khoá thật, chốt gemma-4-31B-it; chốt bằng chứng khi điền sẵn; sửa FAQ khớp bừa; hỏi mô hình trước gợi ý chuyển; config tự đọc .env; 62 test |
| 7af3aa2 | Giao diện bản 3: trang chủ có menu và góp ý, chọn xưng hô, trợ lý AI bên trái, thủ tục gợi ý để chọn, mic luôn hiện và nhấp nháy; xưng hô theo lựa chọn; mô hình tự nói câu ngoài kho; kho thêm cách kê khai mẫu; API 2.2; 64 test |
| b80e0a5 | Xưng hô trung tính «bác», bỏ bước chọn; chốt cứng con số trong câu trả lời phải có trong kho; prompt gọn hơn 40%; 66 test |
| 8487c31 | Lắp kho tri thức bản 17/09 của Mian (Excel 6 sheet) vào 6 file JSON: mã thủ tục, lệ phí, mức trợ cấp, nhánh điều chỉnh và thôi hưởng, căn cước gộp lần đầu, đổi, mất; bước 3 có nút chọn cách nộp; API 2.3; sinh lại kho mp3; 66 test |
| a3d3276 | Bổ sung mã thủ tục hộ tịch 2.000635 và căn cước 2.000200 |
| dbd391b | Sửa kho theo rà soát của Lia: bỏ mọi mục kê khai mẫu; trợ cấp hằng tháng không thuộc nhóm thì chỉ kết luận và chỉ ra một cửa; BHYT bỏ lựa chọn «chưa biết chọn gì»; hộ tịch bỏ hai câu hỏi và lưu ý không có trong kho, hồ sơ không đòi căn cước; chứng thực không hỏi loại giấy, không đẩy sang thủ tục khác; căn cước đổi theo tuổi 25, 40, 60; 67 test |
| 73c1c1d | Máy im ở bước 2: kết luận «đủ điều kiện» từng áp dụng ngay khi chọn mục đích nên bỏ qua câu hỏi riêng của nhánh, và câu bước 2 theo tổ hợp lựa chọn không có sẵn tiếng; nay hỏi hết câu của nhánh rồi mới kết luận, liệt kê tiếng sẵn cho mọi đường trả lời (50 câu kết thúc), tiền «70.000 đồng» đọc thành «bảy mươi nghìn», giao diện thử lại /tts một lần; 69 test |
| (17/09, lần 6) | Câu không ứng với thủ tục nào ở màn «bác cần làm gì» («đúng rồi hướng dẫn tôi từng bước», «cháu tên gì»): mô hình đáp lại rồi lái về hỏi bác cần thủ tục gì, chỉ được nhắc 6 thủ tục, thay câu cứng «cháu chưa được học»; mốc đổi thẻ căn cước 25, 40, 60 (14 là mốc cấp lần đầu); 70 test |

Lần cập nhật 14/09/2026 (e95a025, df008fd) thay đổi gì:

- Trước: nói một câu, máy đổ cả 4 bước và toàn bộ hồ sơ ra một màn hình;
  màn hình chính liệt kê sẵn 6 thủ tục.
- Sau: hội thoại từng bước đúng sơ đồ. Máy chào, hỏi cần gì, xác nhận thủ
  tục, hỏi từng điều kiện một (câu nào cũng kèm cách trả lời), kết luận,
  rồi mới hồ sơ và nộp. Không đáp ứng thì giải thích, không bắt chuẩn bị hồ
  sơ thừa. Người dân trả lời bằng lời hoặc bấm.
- Kho tri thức 6 file thêm phần `flow` (24 câu hỏi, 20 quy tắc kết luận,
  30 FAQ). Thủ tục thứ 7 chưa kiểm chứng đưa ra ngoài.
- Backend thêm 6 đường dẫn `/procedures`, `/flow/*`, không đổi trường cũ.
  Chế độ giả chỉ giả phần nghe, kho và luồng chạy thật.
- Test từ 20 lên 45.

Lần cập nhật 15/09/2026 (56f40dd) thay đổi gì:

- Lỗi báo: máy không nói lời chào khi vào trang. Tìm ra hai nguyên nhân
  chồng nhau: trình duyệt chặn phát tiếng trước thao tác chạm đầu tiên, và
  dịch vụ giọng đọc Edge đang hỏng ngẫu nhiên với giọng tiếng Việt nên máy
  chủ thật thực ra đã lặng toàn bộ, không riêng câu chào.
- Sửa: màn «Chạm vào màn hình để bắt đầu»; kho mp3 112 câu sinh sẵn đi
  theo repo; máy chủ đọc từ đĩa trước, gọi mạng thì thử lại 4 lần.
- Test từ 45 lên 46.

Lần cập nhật 16/09/2026 (nối mô hình ngôn ngữ) thay đổi gì:

- Phản hồi giám khảo 15/09: kiosk phải nhớ ngữ cảnh, hiểu hoàn cảnh bác
  kể, trả lời câu hỏi diễn đạt khác FAQ, lời tự nhiên hơn, luồng demo dài
  hơn. Mọi điểm đều nằm ở tầng «hiểu và trả lời», tầng nghe và kho không đổi.
- Thêm `app/llm.py` gọi FPT AI Marketplace ở 4 chỗ (bảng mục 7b), mỗi chỗ
  có đường lùi về kho tĩnh. Không có khoá thì máy chạy y như trước, chỉ thêm
  điền sẵn bằng luật từ câu bác mở đầu.
- `/flow/start` nhận câu bác mở đầu, trả `ack` (xác nhận đã hiểu) và
  `prefilled` (điều kiện điền sẵn), chỉ hỏi phần còn thiếu; giao diện hiện
  bong bóng «Cháu đã hiểu» và cho «Quay lại» sửa. `/flow/ask` nhận ngữ cảnh
  phiên (các câu đã trả lời, câu mở đầu, các lượt hỏi trước, bước đang đứng).
- Kho tri thức: thêm cụm phủ định rõ («không có lương hưu», «hộ nghèo») cho
  hai thủ tục trợ cấp để luật điền sẵn bắt được.
- Giao kèo API 2.1, chỉ thêm trường. Test từ 46 lên 61.

Lần cập nhật 16/09/2026 (đo trên khoá thật) thay đổi gì:

- Có khoá FPT AI Marketplace. Đo 5 mô hình trên 8 tác vụ của kiosk, chốt
  `gemma-4-31B-it` làm mặc định (bảng mục 7b). Saola-Small-32B bị loại vì
  điền bừa điều kiện và không nhận ra thủ tục từ câu lạ.
- Chốt bằng chứng khi điền sẵn: mô hình phải trích nguyên văn, đoạn trích
  phải có thật, không dùng chung, và nói về đúng chuyện câu hỏi.
- Sửa FAQ khớp bừa theo từ rỗng và mẫu một từ; có mô hình thì hỏi mô hình
  trước, chỉ gợi ý chuyển thủ tục khi mô hình bảo ngoài kho.
- `app/config.py` tự đọc `.env` (trước đây README bảo chép `.env` nhưng
  không có gì đọc file đó). Test từ 61 lên 62.

Lần cập nhật 17/09/2026 (theo phản hồi của Sunny và ý tưởng giao diện mới)
thay đổi gì:

- Lỗi đại từ: nút «Đúng rồi, hướng dẫn cháu nhé» là lời bác bấm mà lại
  xưng cháu; sửa thành lời của bác, và thêm chọn xưng hô (bác, ông, bà, cô,
  chú, anh, chị) áp cho mọi câu máy nói.
- Có mô hình rồi mà câu ngoài kho và câu nghe nhầm («như nàng») vẫn ra
  câu cứng: giờ mô hình tự viết 1 đến 2 câu tử tế trong cùng một lượt gọi
  (trường `in_kb` trong JSON trả về), không bịa.
- Hỏi «mẫu số 2 là gì, điền thế nào» không trả lời được vì kho không có:
  thêm `flow.forms` cho ba thủ tục có mẫu, mô hình đọc được.
- Câu nói ứng với nhiều thủ tục: `/turn` trả `candidates`, giao diện đưa
  ra cho bác chọn thủ tục nào trước.
- Giao diện bản 3 theo ý tưởng của nhóm: trang chủ có menu và góp ý; Bắt
  đầu → chọn xưng hô → trợ lý AI bên trái với ô thoại trên đầu, việc cần
  làm bên phải, mic luôn hiện, nút cần bấm thì nhấp nháy. API 2.2, 64 test.

Lần cập nhật 17/09/2026 (lần 3, kho tri thức mới của Mian) thay đổi gì:

- Mian gửi kho tri thức bản mới dạng Excel 6 sheet, mỗi sheet là kịch bản
  hỏi đáp từng bước của một thủ tục kèm mã thủ tục, đối tượng, cơ quan,
  thời hạn, lệ phí. Chuyển tay toàn bộ vào 6 file `data/kb/*.json`, giữ
  nguyên khung `flow` nên `app/flow.py` không phải sửa logic.
- Nội dung đổi nhiều nhất: câu hỏi đầu tiên của mọi thủ tục là «bác muốn
  làm gì» (xin mới, điều chỉnh, thôi hưởng; làm thẻ lần đầu, đổi, mất…),
  điều kiện chỉ hỏi ở nhánh xin mới. Căn cước không còn đẩy sang «thủ tục
  khác» khi đổi hoặc mất thẻ mà hướng dẫn luôn kèm lệ phí 30.000, 50.000,
  70.000 đồng. Hưu trí có mức 500.000 đồng một tháng và điều kiện lương hưu
  thấp hơn mức chuẩn. Chứng thực có biểu phí theo trang. Từ 24 câu hỏi, 20
  kết luận, 30 FAQ lên 30 câu hỏi, 31 kết luận, 46 FAQ.
- Bước 3 thêm nút chọn cách nộp (trực tiếp, trực tuyến, bưu chính) theo
  kịch bản trong sheet; bấm nút nào máy nói hướng dẫn của cách đó. Trường
  `submit_choices`, API 2.3.
- Kho mp3 sinh lại theo câu mới. Test sửa theo thứ tự câu hỏi mới, vẫn 66.
- Excel gốc để ở `data/kb-source/` để lần sau Mian sửa sheet thì đối chiếu.

---

## 13. Việc còn lại và ai làm

| Việc | Ai | Ở đâu | Mức quan trọng |
|---|---|---|---|
| Thu tập kiểm thử nội bộ: 30 câu, người cao tuổi, từ vựng hành chính, có ồn, ghi đủ nhãn tuổi, giới, vùng, ồn | cả nhóm | `data/eval/README.md` có mẫu và cách ghi | cao nhất, quyết định mục 4 của bài |
| Chạy `eval.wer` trên tập tự thu, ghi WER và tỷ lệ bắt đúng cụm hành chính | Lia | `results/` | cao |
| Bổ sung `HARD_FIXES` từ cụm nghe nhầm thật, chạy `eval.rescore`, ghi chuỗi số cải thiện | Lia | `app/normalize.py` | cao, là nội dung mục 4.3 |
| Đọc lại 30 câu hỏi bước 1 và 31 kết luận trong JSON, đối chiếu với sheet Excel bản 17/09 xem chuyển có sót ý nào | Mian | `data/kb/*.json` mục `flow.check`, `data/kb-source/` | cao |
| Khi có mẫu in đã đối chiếu thì thêm lại mục kê khai mẫu (`flow.forms`) vào kho | Mian | `data/kb/*.json` | vừa, đã bỏ ngày 17/09 vì chưa xác nhận |
| Thay hòm thư và số điện thoại góp ý trên trang chủ bằng của địa phương đặt kiosk | Kns | `web/index.html`, khối `#contact` | vừa |
| Thêm FAQ sau mỗi buổi thử với người thật | Mian | `flow.faq` | vừa |
| Sau mỗi lần sửa kho tri thức: chạy `python scripts/build_tts_cache.py` rồi commit cả `data/tts/` | Lia | `scripts/build_tts_cache.py` | cao, quên là câu mới không có tiếng |
| Đặt `FPT_API_KEY` vào Environment trên Render (máy nhà đã có trong `.env`) | Lia | Render, Environment | cao nhất, không có thì bản trên mạng chạy kho tĩnh |
| Thử tầng mô hình với 3 đến 5 người cao tuổi thật, ghi câu nào trả lời sai hoặc lạnh | cả nhóm | `data/logs/turns.jsonl` có `via_llm` | cao |
| Thay tra cứu từ khoá bằng so khớp ngữ nghĩa (`Vietnamese_Embedding` trên cùng marketplace) | Kim | `app/kb.py`, hàm `score()` | vừa |
| Tính ngưỡng tin cậy bằng hàm chi phí kỳ vọng | Kim | `config.KB_MATCH_THRESHOLD`, `ASR_CONFIDENCE_FLOOR` | vừa |
| Thử với 3 đến 5 người cao tuổi thật, ghi thời gian hoàn thành và chỗ vấp | cả nhóm | | cao |
| Quay video màn hình bản thật để dự phòng hôm chấm | Kns | | vừa |

---

## 14. Gợi ý lấy số nào cho mục nào của bản đề xuất

- Mục tổng quan giải pháp: mục 1 và 2 của tài liệu này, sơ đồ luồng 3
  bước.
- Mục lựa chọn mô hình: bảng 9.1 (5 bộ, chênh 8 đến 19 điểm, 4/5 tách
  rời), lý do CTranslate2 int8 chạy CPU, lý do base trên máy chủ miễn phí.
- Mục đối tượng người cao tuổi và vùng miền: bảng 9.2 (ViMD theo vùng,
  VietMed theo điều kiện thu), kèm cảnh báo Common Voice ở 9.2.
- Mục chuẩn hoá và cải tiến: mục 4, số 0 đến 0,4 điểm trên bộ công khai,
  và chuỗi số trên tập tự thu khi có.
- Mục kho tri thức: bảng mục 6, nguyên tắc không có nguồn thì không viết,
  cấu trúc 9 trường theo tài liệu "kho tri thức" của nhóm.
- Mục thiết kế tương tác cho người cao tuổi: mục 8 (hội thoại từng bước,
  hướng dẫn cách trả lời, bấm hoặc nói, chữ to, nút to, đọc thành tiếng),
  và mục 5 số đo độ trễ tiếng.
- Mục triển khai và chi phí: mục 10 và bảng 9.4 (RAM, tốc độ, gói máy chủ
  miễn phí đủ chạy).
- Mục hạn chế và hướng phát triển: mục 11 và 13, đừng bỏ mục nào.
- Mục kiểm thử: 9.5 (66 test tự động) và 9.6 (những gì chưa đo, nói thật).
- Mục trả lời phản hồi giám khảo: mục 7b, bảng 4 chỗ dùng mô hình ứng với 6
  điểm phản hồi, kèm giới hạn 5b.
