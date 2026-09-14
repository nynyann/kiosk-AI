"""Chạy: python -m pytest tests/ -q   (hoặc python tests/test_normalize.py)

Đây là lưới an toàn cho bước 7. Mỗi lần thêm một cụm vào HARD_FIXES, thêm
một dòng vào đây. Nếu sau này sửa luật chuẩn hoá mà làm hỏng câu cũ, test đỏ
ngay chứ không phải phát hiện lúc demo trước giám khảo.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.normalize import (digits_to_words, for_speech, normalize,  # noqa: E402
                           words_to_digits)
from eval.wer import term_recall, wer, wer_normalize  # noqa: E402


def test_sua_cum_hanh_chinh():
    assert "cư trú" in normalize("ờ tôi muốn xin giấy xác nhận cư chú")
    assert "căn cước công dân" in normalize("làm căn cước công dâng")
    assert "khai sinh" in normalize("làm khai xinh cho cháu")
    assert "một cửa" in normalize("nộp ở bộ phận một của")
    assert "hưu trí" in normalize("chế độ hưu chí")


def test_bo_tu_dem_nhung_giu_xung_ho():
    out = normalize("ờ à tôi muốn hỏi ạ")
    assert "ờ" not in out.split()
    assert "ạ" in out          # từ xưng hô, không được bỏ
    assert "tôi" in out


def test_so_chu_thanh_chu_so():
    assert words_to_digits("hai mươi ba") == "23"
    assert words_to_digits("một trăm linh năm") == "105"
    assert words_to_digits("hai mươi mốt") == "21"
    assert words_to_digits("mười lăm") == "15"
    assert words_to_digits("ba nghìn hai trăm") == "3200"
    # cụm một từ để nguyên, quá mơ hồ
    assert words_to_digits("năm nay") == "năm nay"


def test_khong_nuot_khoang_thoi_gian():
    """Hai chữ số trần đứng liền nhau thì không phải một con số.

    Phát hiện lúc đo WER trên VIVOS: "nửa vòng trái đất hơn bảy năm" bị biến
    thành "... hơn 5", vì "năm" vừa là 5 vừa là đơn vị thời gian. Cùng cơ chế
    làm "tháng tám năm hai không mười một" thành "tháng 11" trên FLEURS.
    """
    assert words_to_digits("bảy năm") == "bảy năm"
    assert words_to_digits("ba năm") == "ba năm"
    assert words_to_digits("năm năm") == "năm năm"
    # cách đọc từng chữ số cũng mơ hồ, để nguyên còn hơn đoán sai
    assert words_to_digits("hai không mười một") == "hai không mười một"
    assert normalize("tôi ở đây ba năm rồi") == "tôi ở đây ba năm rồi"
    # nhưng số thật thì vẫn phải đổi
    assert words_to_digits("ba mươi sáu") == "36"


def test_giu_tieu_tu_cuoi_cau():
    """"à" cuối câu là tiếng xưng hô, cùng loại với "ạ", không được bỏ."""
    assert normalize("bác à") == "bác à"
    assert normalize("mỗi người một số phận em à") == "mỗi người một số phận em à"
    # nhưng "à" đầu câu vẫn là từ đệm thật
    assert normalize("à tôi muốn hỏi") == "tôi muốn hỏi"
    assert normalize("ờ bác à") == "bác à"


def test_chu_so_thanh_chu_de_doc():
    assert digits_to_words("quầy số 1") == "quầy số một"
    assert digits_to_words("15 ngày") == "mười lăm ngày"
    assert "trên" in for_speech("mẫu 01/CT")
    # Số dính chữ phải tách ra, không thì giọng đọc nuốt mất số: "QH15" từng
    # thành "QHmười lăm". Lộ ra khi đọc nguồn văn bản ở bước 3 của luồng.
    assert digits_to_words("Luật số 41/2024/QH15") == "Luật số bốn mươi mốt/hai nghìn hai mươi bốn/QH mười lăm"


def test_khong_pha_cau_da_dung():
    cau = "tôi muốn đăng ký thường trú tại xã này"
    assert normalize(cau) == cau


def test_wer_co_ban():
    assert wer("tôi muốn xin giấy xác nhận cư trú",
               "tôi muốn xin giấy xác nhận cư trú") == 0.0
    assert 0.0 < wer("tôi muốn xin giấy xác nhận cư trú",
                     "tôi muốn xin giấy xác nhận cư chú") < 0.3


def test_wer_giu_dau_thanh():
    """Bỏ dấu để đo WER là tự làm đẹp số liệu. Phải giữ."""
    assert wer_normalize("cư trú") != wer_normalize("cư chú")


def test_term_recall_bat_dung_cum_hong():
    r = term_recall("tôi muốn xin giấy xác nhận cư trú",
                    "tôi muốn xin giấy xác nhận cư chú")
    assert r["cư trú"] is False      # WER thấp nhưng cụm quan trọng vẫn hỏng
    r2 = term_recall("tôi muốn xin giấy xác nhận cư trú",
                     "à tôi muốn xin cái giấy xác nhận cư trú ạ")
    assert r2["cư trú"] is True      # WER cao hơn nhưng tra cứu vẫn trúng


def test_khong_sua_nham_cum_dung_thanh_cum_chuan_khac():
    """Tìm được khi lắp 6 thủ tục của Mian vào kho.

    "chứng thực căn cước" từng bị sửa thành "chứng thẻ căn cước": cụm "thực căn
    cước" giống "thẻ căn cước" tới 86% vì "căn cước" chiếm phần lớn, nên máy
    tra ra thủ tục LÀM căn cước thay vì CHỨNG THỰC. Giờ từng từ sau khi bỏ dấu
    cũng phải giống từ tương ứng ("thuc" với "the" thì không).
    """
    assert normalize("chứng thực căn cước") == "chứng thực căn cước"
    assert normalize("tôi muốn chứng thực căn cước công dân") == "tôi muốn chứng thực căn cước công dân"
    # Nhưng lỗi lệch dấu thật vẫn phải được sửa như cũ.
    assert normalize("tôi muốn làm thẽ căn cước") == "tôi muốn làm thẻ căn cước"
    assert normalize("căn cuốc công dân") == "căn cước công dân"
    # Và từ 1 chữ như "i"/"y" không bị mức sàn từng từ chặn.
    assert normalize("sao i bản chính") == "sao y bản chính"


if __name__ == "__main__":
    # Console Windows mặc định cp1252, in tiếng Việt là vỡ ngay dòng tổng kết.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    fails = 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok   {name}")
            except AssertionError as e:
                fails += 1
                print(f"  HỎNG {name}  {e}")
    print(f"\n{'Tất cả đều qua.' if not fails else f'{fails} test hỏng.'}")
    sys.exit(1 if fails else 0)
