"""Chuẩn hoá văn bản đầu ra của mô hình nhận dạng giọng nói.

Bước 7 trong checklist. Ba việc, chạy theo đúng thứ tự này:

  1. Dọn thô        — bỏ dấu câu thừa, gộp khoảng trắng, hạ chữ thường
  2. Bỏ từ đệm      — "ờ", "à", "thì là", "cái đó"... người cao tuổi nói rất nhiều
  3. Số viết thành chữ -> chữ số  — "hai mươi ba" -> "23"
  4. Sửa cụm hành chính bị nghe nhầm — "cư chú" -> "cư trú"

Hàm chính là `normalize()`. Hàm `explain()` trả về bảng từng bước để làm
bảng so sánh 20 câu trước/sau cho mục 4.3 của bản đề xuất.

Nguyên tắc: chỉ sửa cái CHẮC CHẮN sai. Sửa nhầm một cụm đúng thành cụm khác
còn tệ hơn để nguyên, vì tra cứu sẽ trượt mà không ai biết vì sao.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# 1. Từ đệm
# ---------------------------------------------------------------------------
# Chỉ bỏ khi đứng riêng thành từ, không cắt giữa từ khác.
# Cẩn thận: "à" trong "à ơi" khác "à" đệm, nhưng kiosk không gặp trường hợp đó.
FILLERS = [
    "ờ", "ừ", "à", "ạ à", "ơ", "ê", "hử", "hả",
    "thì là", "là cái", "cái đó là", "cái này là", "nói chung là",
    "tức là cái", "kiểu như là", "thế thì", "mà cái",
]

# Không bao giờ bỏ: "ạ", "dạ", "vâng", "bác", "con", "cô", "chú" — đây là
# từ xưng hô, bỏ đi thì câu mất lễ độ và log đọc lại rất khó hiểu.

# "à" nằm hai chân: đầu câu là từ đệm thật ("à tôi muốn hỏi"), cuối câu là
# tiểu từ xưng hô cùng loại với "ạ" ("bác à", "em à"). Trước đây bỏ cả hai
# nên "bác à" thành "bác", đúng cái lỗi mà ghi chú ngay trên đây dặn tránh.
# Chỉ bỏ khi còn từ khác đứng sau nó.
FINAL_PARTICLES = {"à"}


# ---------------------------------------------------------------------------
# 2. Số viết thành chữ
# ---------------------------------------------------------------------------
UNITS = {
    "không": 0, "một": 1, "mốt": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4,
    "năm": 5, "lăm": 5, "nhăm": 5, "sáu": 6, "bảy": 7, "bẩy": 7,
    "tám": 8, "chín": 9,
}
SCALES = {"mươi": 10, "chục": 10, "trăm": 100, "nghìn": 1000, "ngàn": 1000,
          "triệu": 1_000_000, "tỷ": 1_000_000_000, "tỉ": 1_000_000_000}
NUM_WORDS = set(UNITS) | set(SCALES) | {"linh", "lẻ", "mười"}


def _parse_number_words(words: List[str]) -> int | None:
    """Đọc một dãy từ chỉ số thành giá trị. Trả None nếu không đọc được.

    Xử lý được: "hai mươi ba" 23, "một trăm linh năm" 105,
    "ba nghìn hai trăm" 3200, "mười lăm" 15, "hai mươi mốt" 21.
    """
    total, current = 0, 0
    seen = False
    # Từ vừa đọc có phải một chữ số trần không (không phải "mười", không phải
    # đơn vị "mươi/trăm/nghìn"). Cần biết để từ chối hai chữ số dính nhau,
    # xem ghi chú ở nhánh UNITS bên dưới.
    prev_unit = False
    i = 0
    while i < len(words):
        w = words[i]
        if w == "mười":
            current = current * 10 if current else 10
            seen = True
            # "mười lăm" -> 15
            if i + 1 < len(words) and words[i + 1] in UNITS:
                current += UNITS[words[i + 1]]
                i += 1
            prev_unit = False
        elif w in UNITS:
            # Hai chữ số trần đứng liền nhau thì KHÔNG phải một con số.
            # "bảy năm" là bảy cái năm, không phải 7 rồi 5. Trước đây nhánh
            # này ghi đè current nên "bảy năm" ra 5, "ba năm" ra 5, và
            # "tháng tám năm hai không mười một" ra "tháng 11", nuốt sạch
            # cả hai con số. Gặp ca mơ hồ thì trả None để giữ nguyên chữ,
            # an toàn hơn đoán.
            if prev_unit:
                return None
            current = current + UNITS[w] if current % 10 == 0 and current else UNITS[w]
            seen = True
            prev_unit = True
        elif w in ("linh", "lẻ"):
            prev_unit = False
        elif w in SCALES:
            scale = SCALES[w]
            if scale == 10:
                current = (current or 1) * 10
                # "hai mươi mốt" -> 21
                if i + 1 < len(words) and words[i + 1] in UNITS:
                    current += UNITS[words[i + 1]]
                    i += 1
            elif scale == 100:
                current = (current or 1) * 100
            else:
                total += (current or 1) * scale
                current = 0
            seen = True
            prev_unit = False
        else:
            return None
        i += 1
    return (total + current) if seen else None


def words_to_digits(text: str) -> str:
    """Đổi các cụm chữ số liên tiếp thành chữ số.

    Giữ nguyên khi cụm chỉ có đúng một từ đơn lẻ ngắn ("một", "năm"),
    vì "năm" còn nghĩa là năm tháng và "một" hay đứng trong "một cửa".
    """
    tokens = text.split()
    out: List[str] = []
    i = 0
    while i < len(tokens):
        if tokens[i] in NUM_WORDS:
            j = i
            while j < len(tokens) and tokens[j] in NUM_WORDS:
                j += 1
            chunk = tokens[i:j]
            # cụm 1 từ thì để nguyên, quá mơ hồ
            if len(chunk) >= 2:
                val = _parse_number_words(chunk)
                if val is not None:
                    out.append(str(val))
                    i = j
                    continue
            out.extend(chunk)
            i = j
        else:
            out.append(tokens[i])
            i += 1
    return " ".join(out)


def digits_to_words(text: str) -> str:
    """Chiều ngược lại — dùng cho trường `speech` trước khi đọc thành tiếng.

    Web Speech API đọc "17" thành "mười bảy" khá ổn, nhưng đọc "01/2026" thì
    lộn xộn. Đổi trước cho chắc.
    """
    ones = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]

    def num_to_vi(n: int) -> str:
        if n < 10:
            return ones[n]
        if n < 20:
            tail = "" if n == 10 else (" lăm" if n == 15 else " " + ones[n % 10])
            return "mười" + tail
        if n < 100:
            t, u = divmod(n, 10)
            if u == 0:
                return f"{ones[t]} mươi"
            if u == 1:
                return f"{ones[t]} mươi mốt"
            if u == 5:
                return f"{ones[t]} mươi lăm"
            return f"{ones[t]} mươi {ones[u]}"
        if n < 1000:
            h, r = divmod(n, 100)
            if r == 0:
                return f"{ones[h]} trăm"
            if r < 10:
                return f"{ones[h]} trăm lẻ {ones[r]}"
            return f"{ones[h]} trăm {num_to_vi(r)}"
        if n < 1_000_000:
            k, r = divmod(n, 1000)
            return f"{num_to_vi(k)} nghìn" + (f" {num_to_vi(r)}" if r else "")
        m, r = divmod(n, 1_000_000)
        return f"{num_to_vi(m)} triệu" + (f" {num_to_vi(r)}" if r else "")

    # Tách số dính chữ trước khi đổi: "QH15" -> "QH 15", không thì thành
    # "QHmười lăm" và giọng đọc nuốt mất số.
    text = re.sub(r"(?<=[^\W\d_])(?=\d)", " ", text)
    text = re.sub(r"(?<=\d)(?=[^\W\d_])", " ", text)
    # Số tiền viết kiểu Việt "70.000", "200.000": gộp dấu chấm nghìn trước, không
    # thì đọc thành "bảy mươi. không". Mã thủ tục "1.014027" không khớp mẫu này.
    text = re.sub(r"(?<!\d)\d{1,3}(?:\.\d{3})+(?!\d)", lambda m: m.group().replace(".", ""), text)
    return re.sub(r"\d+", lambda m: num_to_vi(int(m.group())), text)


# ---------------------------------------------------------------------------
# 3. Từ vựng hành chính hay bị nghe nhầm
# ---------------------------------------------------------------------------
# Đây là phần đáng giá nhất của cả file, và cũng là phần cần em bổ sung
# bằng số liệu THẬT: mỗi lần đo WER, ghi lại cụm nào bị nghe nhầm thành gì,
# rồi thêm vào đây. Bảng này chính là "cách vá" trong luận điểm của bài.

# Sửa cứng: cụm nghe nhầm -> cụm đúng. Áp trước, ưu tiên cụm dài.
HARD_FIXES: Dict[str, str] = {
    "cư chú": "cư trú",
    "cư trũ": "cư trú",
    "tạm chú": "tạm trú",
    "tạm chú tạm vắng": "tạm trú tạm vắng",
    "thường chú": "thường trú",
    "hộ tích": "hộ tịch",
    "hộ tịt": "hộ tịch",
    "khai xin": "khai sinh",
    "khai xinh": "khai sinh",
    "căn cước công dâng": "căn cước công dân",
    "căn cuốc công dân": "căn cước công dân",
    "chứng thực chữ khí": "chứng thực chữ ký",
    "sao y bảng chính": "sao y bản chính",
    "bảo hiểm ý tế": "bảo hiểm y tế",
    "hưu chí": "hưu trí",
    "trợ cấp xả hội": "trợ cấp xã hội",
    "một của": "một cửa",
    "uỷ ban nhân dâng": "uỷ ban nhân dân",
    "ủy ban nhân dâng": "uỷ ban nhân dân",
    "công chức tư pháp hộ tích": "công chức tư pháp hộ tịch",
    "giấy chứng nhâm": "giấy chứng nhận",
    "quyền sử dụng đấc": "quyền sử dụng đất",
    "dịch vụ công quấc gia": "dịch vụ công quốc gia",
    "định danh điện tữ": "định danh điện tử",
}

# Danh mục cụm chuẩn để so khớp gần đúng, bắt các lỗi chưa liệt kê ở trên.
CANONICAL_TERMS: List[str] = [
    "xác nhận thông tin về cư trú", "giấy xác nhận cư trú",
    "đăng ký thường trú", "đăng ký tạm trú", "khai báo tạm vắng",
    "căn cước công dân", "thẻ căn cước", "định danh điện tử",
    "đăng ký khai sinh", "đăng ký khai tử", "đăng ký kết hôn",
    "trích lục hộ tịch", "chứng thực chữ ký", "sao y bản chính",
    "bảo hiểm y tế", "trợ cấp xã hội", "chế độ hưu trí",
    "giấy chứng nhận quyền sử dụng đất",
    "cổng dịch vụ công quốc gia", "bộ phận một cửa",
    "uỷ ban nhân dân xã", "công an xã",
]

FUZZY_THRESHOLD = 0.86  # dưới mức này thì không dám sửa

# Ngoài điểm giống của cả cụm, TỪNG TỪ (sau khi bỏ dấu) cũng phải giống từ
# tương ứng trong cụm chuẩn ít nhất ngần này. Không có mức sàn này thì cụm
# "thực căn cước" trong câu "chứng thực căn cước" bị coi là giống "thẻ căn
# cước" tới 86% — vì "căn cước" chiếm phần lớn cụm — và bị sửa thành "chứng
# thẻ căn cước", làm máy tra ra thủ tục làm căn cước thay vì chứng thực.
# Lỗi nghe thật của người cao tuổi chủ yếu là lệch dấu ("thẽ", "cuốc"), bỏ dấu
# xong thì từng từ trùng gần hết, nên mức sàn này không cản việc sửa đúng.
FUZZY_TOKEN_FLOOR = 0.75


def _strip_tones(s: str) -> str:
    """Bỏ dấu để so khớp. Người cao tuổi nói lệch dấu rất nhiều, mô hình
    nghe ra sai dấu là lỗi phổ biến nhất — so khớp không dấu bắt được nó."""
    nfd = unicodedata.normalize("NFD", s)
    no_marks = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", no_marks).replace("đ", "d").replace("Đ", "D")


def fix_admin_terms(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Sửa cụm hành chính. Trả về (văn bản đã sửa, danh sách các chỗ đã sửa)."""
    changes: List[Tuple[str, str]] = []

    # a) sửa cứng, ưu tiên cụm dài trước
    for wrong in sorted(HARD_FIXES, key=len, reverse=True):
        if wrong in text:
            text = text.replace(wrong, HARD_FIXES[wrong])
            changes.append((wrong, HARD_FIXES[wrong]))

    # b) so khớp gần đúng theo cửa sổ trượt n-gram
    tokens = text.split()
    for term in CANONICAL_TERMS:
        n = len(term.split())
        if n < 2 or n > len(tokens):
            continue
        term_flat = _strip_tones(term)
        i = 0
        while i + n <= len(tokens):
            window = " ".join(tokens[i:i + n])
            if window == term:
                i += 1
                continue
            ratio = SequenceMatcher(None, _strip_tones(window), term_flat).ratio()
            # Từ chỉ 1-2 chữ cái ("i"/"y", "ở"/"ỡ") thì so từng từ vô nghĩa —
            # khác một chữ là điểm bằng 0 dù đó đúng là lỗi nghe. Bỏ qua chúng,
            # để điểm cả cụm quyết định như trước.
            tokens_ok = all(
                SequenceMatcher(None, _strip_tones(a), _strip_tones(b)).ratio() >= FUZZY_TOKEN_FLOOR
                for a, b in zip(tokens[i:i + n], term.split())
                if len(_strip_tones(a)) > 2 and len(_strip_tones(b)) > 2
            )
            if ratio >= FUZZY_THRESHOLD and tokens_ok:
                changes.append((window, term))
                tokens[i:i + n] = term.split()
                i += n
            else:
                i += 1
    return " ".join(tokens), changes


# ---------------------------------------------------------------------------
# 4. Ghép lại
# ---------------------------------------------------------------------------
def clean_raw(text: str) -> str:
    text = text.strip().lower()
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[.,!?;:\"'“”‘’…]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def drop_fillers(text: str) -> str:
    # Cụm dài trước, nên "à" (ngắn nhất) luôn xét sau cùng. Lúc đó các từ đệm
    # khác đã bị bỏ, nên "ờ bác à" đã thành "bác à" và "à" đúng là ở cuối.
    for f in sorted(FILLERS, key=len, reverse=True):
        pattern = rf"(?<!\S){re.escape(f)}(?!\S)"
        if f in FINAL_PARTICLES:
            pattern += r"(?=\s+\S)"     # phải còn từ khác đứng sau mới bỏ
        text = re.sub(pattern, " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize(text: str) -> str:
    """Đường chính. Đầu vào là văn bản thô của mô hình, đầu ra đem đi tra cứu."""
    if not text:
        return ""
    t = clean_raw(text)
    t = drop_fillers(t)
    t = words_to_digits(t)
    t, _ = fix_admin_terms(t)
    return t.strip()


def explain(text: str) -> Dict[str, object]:
    """Trả về từng bước để dựng bảng so sánh cho mục 4.3.

    Chạy `python -m app.normalize` để in bảng 20 câu mẫu.
    """
    s0 = text
    s1 = clean_raw(s0)
    s2 = drop_fillers(s1)
    s3 = words_to_digits(s2)
    s4, changes = fix_admin_terms(s3)
    return {
        "raw": s0,
        "cleaned": s1,
        "no_filler": s2,
        "digits": s3,
        "final": s4,
        "term_fixes": changes,
        "changed": s0.strip().lower() != s4,
    }


def for_speech(text: str) -> str:
    """Chuẩn bị chuỗi để đọc thành tiếng: bỏ ký hiệu, số thành chữ, giãn nhịp."""
    t = text.replace("/", " trên ").replace("-", " ")
    t = re.sub(r"\s+", " ", t)
    return digits_to_words(t).strip()


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    SAMPLES = [
        "ờ tôi muốn xin giấy xác nhận cư chú",
        "à cái đó là đăng ký tạm chú phải không cô",
        "tôi cần làm căn cước công dâng cho thằng cháu hai mươi ba tuổi",
        "nói chung là tôi muốn hỏi về bảo hiểm ý tế",
        "cho hỏi sao y bảng chính ở đâu ạ",
        "tôi ở tổ ba mươi lăm muốn đăng ký thường chú",
        "ừ thì là làm khai xinh cho cháu",
        "chứng thực chữ khí mất bao nhiêu tiền",
        "hồ sơ nộp ở bộ phận một của đúng không",
        "tôi muốn hỏi chế độ hưu chí",
    ]
    w = max(len(s) for s in SAMPLES)
    print(f"{'TRƯỚC'.ljust(w)} | SAU")
    print("-" * (w * 2 + 3))
    for s in SAMPLES:
        print(f"{s.ljust(w)} | {normalize(s)}")
