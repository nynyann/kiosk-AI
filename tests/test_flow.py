"""Chạy: python -m pytest tests/test_flow.py -q

Lưới an toàn cho luồng từng bước (API 2.0): bước 1 hỏi đúng thứ tự, rẽ nhánh
đúng theo sơ đồ (đáp ứng → bước 2, không → giải thích rồi kết luận), bước 3
có đủ nơi nộp và thời hạn, hỏi thêm chỉ trả lời từ kho của thủ tục đó.

Chạy ở chế độ giả nên không cần mô hình. Kho tri thức là kho THẬT trong
data/kb/, nên test này cũng bắt được file JSON nào viết thiếu trường.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["MOCK"] = "1"
# Test không bao giờ gọi mô hình thật: ghi đè khoá thành rỗng TRƯỚC khi
# config đọc .env (config chỉ điền biến chưa có).
os.environ["FPT_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app import flow, kb  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
kb.load_kb()

HUU_TRI = "tro-cap-huu-tri-xa-hoi"


def _answer(pid, answers, qid, value):
    r = client.post("/flow/answer", json={"procedure_id": pid, "answers": answers,
                                          "question_id": qid, "value": value})
    assert r.status_code == 200, r.text
    return r.json()


# --- Kho tri thức phải có đủ phần luồng cho cả 6 thủ tục ---------------------
def test_moi_thu_tuc_deu_co_luong_ba_buoc():
    ids = {p["id"] for p in kb.summaries()}
    assert len(ids) == 6
    for pid in ids:
        proc = kb.get(pid)
        fl = proc.get("flow") or {}
        assert fl.get("check", {}).get("questions"), pid
        assert fl.get("prepare", {}).get("say"), pid
        assert fl.get("submit", {}).get("places"), pid
        assert proc.get("processing_time"), pid
        for q in fl["check"]["questions"]:
            assert q.get("id") and q.get("text") and len(q.get("options", [])) >= 2, (pid, q)
            for o in q["options"]:
                assert o.get("value") and o.get("label"), (pid, q["id"])
        for o in fl["check"].get("outcomes", []):
            assert o.get("when") and o.get("verdict") in ("ineligible", "consult", "redirect", "eligible"), (pid, o)
            assert o.get("verdict") == "eligible" or o.get("reason"), (pid, o)
            if o.get("suggest"):
                assert kb.get(o["suggest"]), (pid, o["suggest"])


def test_danh_sach_thu_tuc():
    d = client.get("/procedures").json()
    assert d["ok"] and len(d["procedures"]) == 6
    assert all(p["id"] and p["name"] for p in d["procedures"])


# --- Bước 1: hỏi đúng thứ tự trong kho (mục đích → tuổi → công dân → lương hưu → BHXH → hộ nghèo)
def test_bat_dau_hoi_cau_dau_tien_kem_loi_dan():
    st = client.post("/flow/start", json={"procedure_id": HUU_TRI}).json()
    assert st["ok"] and st["stage"] == "check" and st["step"] == 1
    assert st["question"]["id"] == "purpose"
    assert "cháu hỏi bác" in st["speech"].lower()
    assert st["answers"] == {}


def test_dap_ung_dieu_kien_thi_sang_buoc_2():
    st = client.post("/flow/start", json={"procedure_id": HUU_TRI}).json()
    order = []
    for qid, v in [("purpose", "new"), ("age", "ge75"), ("citizen", "yes"), ("pension", "no"), ("bhxh", "no")]:
        assert st["question"]["id"] == qid
        order.append(qid)
        st = _answer(HUU_TRI, st["answers"], qid, v)
    # Từ 75 trở lên thì KHÔNG hỏi hộ nghèo.
    assert st["stage"] == "prepare" and st["step"] == 2 and st["verdict"] == "eligible"
    assert st["documents"] and st["note"]
    assert "có khả năng" in st["note"]           # không kết luận "chắc chắn được hưởng"
    assert st["answers"] == {"purpose": "new", "age": "ge75", "citizen": "yes", "pension": "no", "bhxh": "no"}


def test_70_den_75_thi_hoi_them_ho_ngheo():
    st = client.post("/flow/start", json={"procedure_id": HUU_TRI}).json()
    for qid, v in [("purpose", "new"), ("age", "70_74"), ("citizen", "yes"), ("pension", "no"), ("bhxh", "no")]:
        st = _answer(HUU_TRI, st["answers"], qid, v)
    assert st["stage"] == "check" and st["question"]["id"] == "poor"
    assert st["question"]["index"] == 6 and st["question"]["total"] == 6
    st = _answer(HUU_TRI, st["answers"], "poor", "no")
    assert st["stage"] == "stop" and st["verdict"] == "ineligible"
    assert "hộ nghèo" in st["reason"]


def test_khong_dap_ung_thi_dung_ngay_va_giai_thich():
    st = _answer(HUU_TRI, {"purpose": "new"}, "age", "lt70")
    assert st["stage"] == "stop" and st["verdict"] == "ineligible"
    assert st["title"] == "Chưa đủ điều kiện"
    assert st["reason"] and st["speech"]
    assert st["question"] is None


def test_khong_ro_thi_moi_gap_can_bo_chu_khong_ket_luan():
    answers = {"purpose": "new", "age": "70_74", "citizen": "yes", "pension": "no", "bhxh": "no"}
    st = _answer(HUU_TRI, answers, "poor", "unsure")
    assert st["stage"] == "stop" and st["verdict"] == "consult"


def test_khong_co_ban_chinh_thi_ket_luan_khong_goi_y_thu_tuc_khac():
    """Feedback 17/09: chứng thực không hỏi loại giấy, không đẩy sang thủ tục
    khác; không có bản chính thì kết luận theo đúng câu trong kho."""
    st = _answer("chung-thuc-ban-sao", {}, "original", "no")
    assert st["stage"] == "stop" and st["verdict"] == "ineligible"
    assert st["suggest_procedure_id"] is None
    assert "bản chính để đối chiếu" in st["reason"]


def test_khong_thuoc_nhom_thi_chi_ket_luan_va_chi_ra_mot_cua():
    st = _answer("tro-cap-xa-hoi-hang-thang", {"purpose": "new"}, "group", "none")
    assert st["stage"] == "stop" and st["verdict"] == "ineligible"
    assert st["suggest_procedure_id"] is None
    assert "một cửa" in st["reason"] and "hưu trí" not in st["reason"]


def test_can_cuoc_mat_the_thi_huong_dan_cap_lai_kem_le_phi():
    """Kho mới gộp 6A/6B/6C vào một thủ tục: mất thẻ vẫn đi tiếp bước 2, 3,
    kèm lệ phí cấp lại 70.000 đồng chứ không đẩy sang thủ tục khác."""
    st = _answer("cap-the-can-cuoc", {"purpose": "lost"}, "eid", "no")
    assert st["stage"] == "prepare" and st["verdict"] == "eligible"
    assert "cấp lại" in st["note"] and "70.000" in st["note"]
    st = _answer("cap-the-can-cuoc", {"purpose": "first"}, "in_db", "yes")
    assert st["stage"] == "prepare" and "miễn phí" in st["note"]
    st = _answer("cap-the-can-cuoc", {"purpose": "change"}, "reason", "age")
    assert st["stage"] == "prepare" and "50.000" in st["note"]


def test_dieu_chinh_tro_cap_thi_ho_so_khac_voi_xin_moi():
    moi = _answer("tro-cap-xa-hoi-hang-thang", {"purpose": "new"}, "group", "elderly")
    assert moi["stage"] == "prepare"
    dc = _answer("tro-cap-xa-hoi-hang-thang", {"purpose": "adjust"}, "change_kind", "info")
    assert dc["stage"] == "prepare"
    assert dc["documents"] != moi["documents"]
    assert any("điều chỉnh" in d.lower() for d in dc["documents"])


def test_ghi_chu_theo_lua_chon_hien_o_buoc_2():
    st = _answer("cap-the-bao-hiem-y-te", {"need": "new", "changed": "no"}, "format", "e")
    assert st["stage"] == "prepare"
    assert any("điện tử" in n for n in st["notes"])


# --- Bước 3 và kết thúc ------------------------------------------------------
def test_buoc_3_co_noi_nop_giay_to_thoi_han():
    answers = {"age": "ge75", "citizen": "yes", "pension": "no", "bhxh": "no"}
    st = client.post("/flow/next", json={"procedure_id": HUU_TRI, "answers": answers,
                                         "stage": "prepare"}).json()
    assert st["stage"] == "submit" and st["step"] == 3
    assert st["places"] and st["bring"] and st["processing_time"] and st["agency"]
    assert "mang theo" in st["speech"].lower()
    done = client.post("/flow/next", json={"procedure_id": HUU_TRI, "answers": answers,
                                           "stage": "submit"}).json()
    assert done["stage"] == "done" and "thuận lợi" in done["speech"]


def test_ma_thu_tuc_sai_tra_loi_dung_giao_keo():
    r = client.post("/flow/start", json={"procedure_id": "khong-co"})
    d = r.json()
    assert r.status_code == 404 and d["ok"] is False and d["code"] == "procedure_not_found"
    assert "bác" in d["error"].lower()


def test_cau_hoi_sai_ma_tra_loi_dung_giao_keo():
    r = client.post("/flow/answer", json={"procedure_id": HUU_TRI, "answers": {},
                                          "question_id": "khong-co", "value": "x"})
    assert r.status_code == 400 and r.json()["ok"] is False


# --- Trả lời bằng lời nói ----------------------------------------------------
def test_anh_xa_loi_noi_sang_lua_chon():
    p = kb.get(HUU_TRI)
    q = flow.find_question(p, "age")
    assert flow.match_option(q, "tôi bảy mươi sáu tuổi") == "ge75"
    assert flow.match_option(q, "năm nay tôi bảy mươi hai") == "70_74"
    assert flow.match_option(q, "dưới bảy mươi") == "lt70"
    assert flow.match_option(q, "tôi không nhớ") is None
    q = flow.find_question(p, "pension")
    assert flow.match_option(q, "không tôi không có lương hưu") == "no"
    assert flow.match_option(q, "có đang nhận") == "yes"
    assert flow.match_option(q, "dạ chưa") == "no"
    q = flow.find_question(kb.get("cap-the-can-cuoc"), "purpose")
    assert flow.match_option(q, "tôi chưa có thẻ") == "first"
    assert flow.match_option(q, "tôi làm mất thẻ rồi") == "lost"
    assert flow.match_option(q, "thẻ hết hạn muốn đổi") == "change"


def test_answer_voice_khong_hieu_thi_giu_nguyen_cau_hoi():
    # Chế độ giả: câu ASR mẫu xoay vòng, không câu nào là câu trả lời tuổi.
    # Gửi hai lần để chắc chắn gặp mẫu "không nghe rõ" hoặc mẫu không khớp.
    for _ in range(3):
        r = client.post("/flow/answer-voice",
                        files={"audio": ("a.webm", b"x", "audio/webm")},
                        data={"procedure_id": HUU_TRI, "question_id": "citizen",
                              "answers": '{"purpose": "new", "age": "ge75"}'})
        d = r.json()
        assert r.status_code == 200 and d["ok"]
        assert "asr" in d and d["matched"] in (True, False)
        if not d["matched"]:
            assert d["stage"] == "check" and d["question"]["id"] == "citizen"
            assert d["message"] and d["answers"] == {"purpose": "new", "age": "ge75"}


# --- Hỏi thêm ở bước 2 / 3 ---------------------------------------------------
def test_hoi_them_tra_loi_tu_faq_cua_thu_tuc():
    d = client.post("/flow/ask", data={"procedure_id": HUU_TRI, "text": "mẫu số 01 lấy ở đâu"}).json()
    assert d["ok"] and d["matched"] and "Mẫu số 01" in d["answer"]
    assert d["speech"]


def test_hoi_them_y_dinh_chung_noi_nop_thoi_gian():
    d = client.post("/flow/ask", data={"procedure_id": HUU_TRI, "text": "nộp ở đâu"}).json()
    assert d["matched"] and "Uỷ ban nhân dân cấp xã" in d["answer"]
    d = client.post("/flow/ask", data={"procedure_id": HUU_TRI, "text": "bao lâu thì xong"}).json()
    assert d["matched"] and "10 ngày" in d["answer"]


def test_hoi_them_khong_co_thi_moi_hoi_can_bo_khong_bia():
    d = client.post("/flow/ask", data={"procedure_id": HUU_TRI, "text": "trời hôm nay đẹp quá"}).json()
    assert d["ok"] and d["matched"] is False
    assert "cán bộ" in d["answer"]


def test_hoi_them_thuoc_thu_tuc_khac_thi_goi_y_chuyen():
    d = client.post("/flow/ask", data={"procedure_id": HUU_TRI, "text": "tôi muốn làm căn cước công dân"}).json()
    assert d["switch_to"] == "cap-the-can-cuoc" and d["switch_name"]


def test_hoi_them_ve_thu_tuc_khac_kem_y_dinh_chung_van_goi_y_chuyen():
    """"làm căn cước cần giấy tờ gì" hỏi giữa lúc làm trợ cấp: phải gợi ý
    chuyển, không được đem giấy tờ của trợ cấp ra trả lời vì thấy chữ "giấy tờ"."""
    d = client.post("/flow/ask", data={"procedure_id": HUU_TRI, "text": "làm căn cước công dân cần giấy tờ gì"}).json()
    assert d["switch_to"] == "cap-the-can-cuoc"
    assert "Mẫu số 01" not in d["answer"]


def test_cau_hoi_buoc_1_co_huong_dan_cach_tra_loi():
    st = client.post("/flow/start", json={"procedure_id": HUU_TRI}).json()
    assert "bấm chọn" in st["question"]["hint"]
    assert "trả lời bằng lời" in st["speech"].lower()  # câu đầu dặn cách trả lời
    st = _answer(HUU_TRI, {}, "purpose", "new")
    assert "ví dụ" in st["question"]["hint"]          # câu hỏi tuổi: gợi ý nói số
    st = _answer(HUU_TRI, {"purpose": "new"}, "age", "ge75")
    assert "«có» hoặc «không»" in st["question"]["hint"]


def test_hoi_them_thieu_ca_audio_lan_text():
    r = client.post("/flow/ask", data={"procedure_id": HUU_TRI})
    assert r.status_code == 400 and r.json()["ok"] is False


def test_cau_chao_cua_giao_dien_khop_voi_may_chu():
    """Máy chủ sinh sẵn tiếng cho câu chào theo flow.GREETING_TEXTS; giao diện
    hiện và phát đúng chuỗi đó. Lệch một chữ là câu chào không có sẵn tiếng,
    phải gọi ra mạng lúc bác vừa chạm màn hình."""
    html = (Path(__file__).resolve().parent.parent / "web" / "index.html").read_text(encoding="utf-8")
    for t in flow.GREETING_TEXTS:
        assert t in html, t
    assert flow.GREETING_SPEECH in kb.all_speech_texts()


def test_moi_cau_may_doc_deu_duoc_liet_ke_de_sinh_san():
    texts = kb.all_speech_texts()
    assert len(texts) > 60
    assert all(isinstance(t, str) and t for t in texts)
    # Câu đọc không còn phần trong ngoặc — dài và rối khi đọc.
    assert not any("(" in t for t in texts)


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
