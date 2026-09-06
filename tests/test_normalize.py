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


def test_chu_so_thanh_chu_de_doc():
    assert digits_to_words("quầy số 1") == "quầy số một"
    assert digits_to_words("15 ngày") == "mười lăm ngày"
    assert "trên" in for_speech("mẫu 01/CT")


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


if __name__ == "__main__":
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
