"""Chạy: python tests/test_api.py   (hoặc python -m pytest tests/ -q)

Lưới an toàn cho giao kèo API. Chạy ở chế độ giả nên không cần mô hình, không
cần ffmpeg, chạy xong trong vài giây.

Điều kiện nghiệm thu quan trọng nhất ở đây: MỌI phản hồi đều có trường `ok`, và
khi `ok = false` thì `error` là câu tiếng Việt hiển thị thẳng cho người dân
được. Đó là dòng đầu của API_CONTRACT.md, và Kns viết giao diện dựa vào nó.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Phải bật chế độ giả TRƯỚC khi import app, vì app đọc config lúc nạp module.
os.environ["MOCK"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def _is_vietnamese(s: str) -> bool:
    """Câu lỗi phải là tiếng Việt, không phải thông báo tiếng Anh của FastAPI."""
    return any(c in s for c in "ăâđêôơưàáảãạèéẻẽẹìíỉĩịòóỏõọùúủũụỳýỷỹỵ")


def test_health_co_du_truong():
    d = client.get("/health").json()
    assert d["ok"] is True
    assert d["mock"] is True
    assert "asr_ready" in d and "kb_procedures" in d


def test_thieu_truong_audio_van_dung_giao_keo():
    """Lỗi 422 phải có `ok` và `error`, không phải {"detail": [...]} của FastAPI.

    Trước khi sửa, FastAPI trả {"detail":[{"msg":"Field required",...}]}. Giao
    diện đọc data.error theo giao kèo sẽ ra undefined, và người dân nhìn thấy
    chữ "undefined" trên màn hình kiosk.
    """
    r = client.post("/asr")               # cố ý không gửi file
    d = r.json()
    assert r.status_code == 422
    assert d["ok"] is False
    assert d["code"] == "bad_request"
    assert _is_vietnamese(d["error"])
    assert "audio" in d["detail"]         # phần kỹ thuật vẫn giữ cho Kns


def test_sai_kieu_du_lieu_van_dung_giao_keo():
    r = client.post("/answer", json={"text": 123})
    d = r.json()
    assert r.status_code == 422
    assert d["ok"] is False
    assert _is_vietnamese(d["error"])
    assert "text" in d["detail"]


def test_answer_tra_du_truong():
    d = client.post("/answer", json={"text": "tôi muốn xin giấy xác nhận cư trú"}).json()
    assert d["ok"] is True
    assert "handoff" in d and "speech" in d and "match_score" in d


def test_turn_gop_ca_hai_phan():
    d = client.post("/turn", files={"audio": ("a.webm", b"x", "audio/webm")}).json()
    assert d["ok"] is True
    assert "asr" in d and "answer" in d
    assert 0.0 <= d["asr"]["confidence"] <= 1.0


if __name__ == "__main__":
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
