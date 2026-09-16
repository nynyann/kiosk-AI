"""Chạy: python -m pytest tests/test_llm.py -q

Kiểm phần nối với mô hình ngôn ngữ (app/llm.py) mà KHÔNG gọi ra mạng: thay
`llm.chat` bằng hàm giả trả câu cố định. Kiểm ba điều:

  1. Không có khoá thì mọi thứ y như bản tĩnh (46 test cũ đã kiểm), và các hàm
     llm.* trả None chứ không ném lỗi.
  2. Có mô hình: điền sẵn điều kiện từ lời bác kể, xác nhận đã hiểu, nhận ra
     thủ tục khi từ khoá không bắt được, hiểu câu trả lời tự do, trả lời câu
     hỏi thêm bằng lời tự nhiên.
  3. Mô hình trả rác, trả "ngoài kho", hoặc hỏng thì máy chủ lùi về câu tĩnh,
     không bao giờ điền bừa một giá trị không có trong lựa chọn.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["MOCK"] = "1"
# Test không bao giờ gọi mô hình thật: ghi đè khoá thành rỗng TRƯỚC khi
# config đọc .env (config chỉ điền biến chưa có).
os.environ["FPT_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import config, flow, kb, llm  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
kb.load_kb()
HUU_TRI = "tro-cap-huu-tri-xa-hoi"


@pytest.fixture
def fake_llm(monkeypatch):
    """Bật mô hình giả. Dùng: fake_llm(reply) hoặc fake_llm(lambda messages: ...)."""
    calls = []

    def _install(reply):
        async def chat(messages, **kw):
            calls.append(messages)
            return reply(messages) if callable(reply) else reply
        monkeypatch.setattr(config, "FPT_API_KEY", "khoa-gia")
        monkeypatch.setattr(llm, "chat", chat)
        return calls
    return _install


# --- 1. Không có khoá ---------------------------------------------------------
def test_khong_co_khoa_thi_tat_va_khong_nem_loi():
    import asyncio
    assert config.FPT_API_KEY == ""
    assert llm.enabled() is False
    proc = kb.get(HUU_TRI)
    assert asyncio.run(llm.prefill_from_utterance(proc, "tôi 76 tuổi")) is None
    assert asyncio.run(llm.pick_procedure("tôi già rồi", kb.procedures())) is None
    assert asyncio.run(llm.answer_from_kb(proc, "phí bao nhiêu", {})) is None
    d = client.get("/health").json()
    assert d["llm_enabled"] is False and d["llm_model"] is None


def test_khong_co_khoa_van_dien_san_bang_luat():
    st = client.post("/flow/start", json={"procedure_id": HUU_TRI,
                                          "utterance": "tôi bảy mươi sáu tuổi, không có lương hưu"}).json()
    assert st["answers"] == {"age": "ge75", "pension": "no"}
    assert st["question"]["id"] == "citizen"          # chỉ hỏi phần còn thiếu
    assert st["intro"]                                  # vẫn có lời dẫn bước 1
    assert st["ack"].startswith("Cháu ghi nhận")
    assert [x["question_id"] for x in st["prefilled"]] == ["age", "pension"]


def test_dien_san_bang_luat_khong_dung_co_khong_chung_chung():
    # «có» trong «tôi có 76 tuổi» KHÔNG được thành «công dân = có».
    assert flow.prefill_by_rules(kb.get(HUU_TRI), "tôi có 76 tuổi") == {"age": "ge75"}
    assert flow.prefill_by_rules(kb.get(HUU_TRI), "xin chào") == {}


# --- 2. Có mô hình ------------------------------------------------------------
def test_dien_san_va_xac_nhan_da_hieu_bang_mo_hinh(fake_llm):
    fake_llm('{"answers": {"age": "ge75", "pension": "no", "citizen": "yes"}, '
             '"evidence": {"age": "76 tuổi", "pension": "chưa có lương hưu", "citizen": "người Việt"}, '
             '"ack": "Cháu hiểu rồi ạ, bác 76 tuổi, chưa có lương hưu và đang sống một mình."}')
    st = client.post("/flow/start", json={"procedure_id": HUU_TRI,
                                          "utterance": "tôi 76 tuổi sống một mình chưa có lương hưu, người Việt"}).json()
    assert st["answers"] == {"age": "ge75", "pension": "no", "citizen": "yes"}
    assert st["question"]["id"] == "bhxh"
    assert st["ack"].startswith("Cháu hiểu rồi ạ")
    assert st["speech"].startswith("Cháu hiểu rồi ạ")   # đọc câu xác nhận trước câu hỏi
    assert len(st["prefilled"]) == 3


def test_mo_hinh_dien_ma_khong_co_bang_chung_thi_bo(fake_llm):
    """Saola từng tự điền «công dân = có», «BHXH = không» dù bác không nói.
    Bằng chứng phải là đoạn có thật trong câu bác nói, và không dùng chung."""
    fake_llm('{"answers": {"age": "ge75", "citizen": "yes", "bhxh": "no", "pension": "no"}, '
             '"evidence": {"age": "76 tuổi", "citizen": "", "bhxh": "không có lương hưu", "pension": "không có lương hưu"}, '
             '"ack": "Cháu hiểu rồi ạ."}')
    st = client.post("/flow/start", json={"procedure_id": HUU_TRI,
                                          "utterance": "tôi 76 tuổi không có lương hưu"}).json()
    # citizen: không bằng chứng; bhxh: dùng chung bằng chứng với câu trước nó.
    assert st["answers"] == {"age": "ge75", "bhxh": "no"} or st["answers"] == {"age": "ge75", "pension": "no"}
    assert "citizen" not in st["answers"]
    assert not ("bhxh" in st["answers"] and "pension" in st["answers"])


def test_mo_hinh_khong_duoc_dien_gia_tri_ngoai_lua_chon(fake_llm):
    fake_llm('{"answers": {"age": "76", "pension": "no", "bua": "x"}, '
             '"evidence": {"age": "76 tuổi", "pension": "không có lương hưu", "bua": "76"}, "ack": "Cháu hiểu rồi ạ."}')
    st = client.post("/flow/start", json={"procedure_id": HUU_TRI, "utterance": "tôi 76 tuổi không có lương hưu"}).json()
    assert st["answers"] == {"pension": "no"}          # "76" và "bua" bị bỏ


def test_mo_hinh_tra_rac_thi_lui_ve_luat(fake_llm):
    fake_llm("xin lỗi tôi không hiểu")
    st = client.post("/flow/start", json={"procedure_id": HUU_TRI, "utterance": "tôi 76 tuổi"}).json()
    assert st["answers"] == {"age": "ge75"} and st["ack"].startswith("Cháu ghi nhận")


def test_nhan_ra_thu_tuc_khi_tu_khoa_khong_bat_duoc(fake_llm):
    calls = fake_llm('{"procedure_id": "tro-cap-huu-tri-xa-hoi"}')
    d = client.post("/answer", json={"text": "tôi già rồi nhà nước có cho đồng nào không"}).json()
    assert d["handoff"] is False and d["procedure_id"] == HUU_TRI and d["via_llm"] is True
    assert d["confirm"]
    assert "Trợ cấp hưu trí xã hội" in calls[0][-1]["content"]   # danh sách thủ tục có trong prompt


def test_mo_hinh_tra_none_thi_van_chuyen_can_bo(fake_llm):
    fake_llm('{"procedure_id": "none"}')
    d = client.post("/answer", json={"text": "hôm nay trời đẹp quá"}).json()
    assert d["handoff"] is True and d["via_llm"] is False


def test_tu_khoa_bat_duoc_thi_khong_goi_mo_hinh(fake_llm):
    calls = fake_llm('{"procedure_id": "cap-the-can-cuoc"}')
    d = client.post("/answer", json={"text": "tôi muốn xin trợ cấp hưu trí xã hội"}).json()
    assert d["procedure_id"] == HUU_TRI and d["via_llm"] is False
    assert calls == []


def test_hieu_cau_tra_loi_tu_do_o_buoc_1(fake_llm):
    fake_llm('{"value": "yes"}')
    # Mẫu ASR giả đầu tiên là câu không khớp lựa chọn nào của "citizen" bằng
    # cụm từ; mô hình giả bảo là "yes".
    import app.mock as mock
    from itertools import cycle
    mock._ASR_SAMPLES = cycle([("dạ cháu nó bảo tôi quốc tịch mình đấy", "…", 0.9, False)])
    r = client.post("/flow/answer-voice", files={"audio": ("a.webm", b"x", "audio/webm")},
                    data={"procedure_id": HUU_TRI, "question_id": "citizen", "answers": '{"age": "ge75"}'})
    d = r.json()
    assert d["matched"] is True and d["answers"] == {"age": "ge75", "citizen": "yes"}
    assert d["question"]["id"] == "pension"


def test_hoi_them_dien_dat_khac_faq_thi_mo_hinh_tra_loi_tu_kho(fake_llm):
    calls = fake_llm("Dạ, bác không phải mang sổ hộ khẩu đâu ạ, cán bộ tra trên hệ thống rồi.")
    d = client.post("/flow/ask", data={"procedure_id": HUU_TRI, "text": "nhà tôi mất sổ rồi thì có sao không",
                                       "answers": '{"age": "ge75", "pension": "no"}',
                                       "utterance": "tôi 76 tuổi", "stage": "prepare",
                                       "history": '[{"q": "phí bao nhiêu", "a": "hỏi cán bộ"}]'}).json()
    assert d["matched"] is True and d["via_llm"] is True
    assert d["answer"].startswith("Dạ, bác không phải mang sổ")
    prompt = calls[0][-1]["content"]
    assert "KHO TRI THỨC" in prompt and "Mẫu số 01" in prompt        # kho tri thức nằm trong prompt
    assert "Từ 75 tuổi trở lên" in prompt and "tôi 76 tuổi" in prompt  # ngữ cảnh phiên nằm trong prompt
    assert "phí bao nhiêu" in prompt


def test_faq_khop_ro_thi_lay_nguyen_van_khong_goi_mo_hinh(fake_llm):
    calls = fake_llm("câu này không được dùng")
    d = client.post("/flow/ask", data={"procedure_id": HUU_TRI, "text": "mẫu số 01 lấy ở đâu"}).json()
    assert d["matched"] and d["via_llm"] is False and "Mẫu số 01" in d["answer"]
    assert calls == []


def test_mo_hinh_bao_ngoai_kho_thi_moi_gap_can_bo(fake_llm):
    fake_llm(llm.NOT_IN_KB)
    d = client.post("/flow/ask", data={"procedure_id": HUU_TRI, "text": "trời hôm nay đẹp quá"}).json()
    assert d["matched"] is False and d["via_llm"] is False and "cán bộ" in d["answer"]


def test_thu_tuc_khac_thi_hoi_mo_hinh_truoc_ngoai_kho_moi_goi_y_chuyen(fake_llm):
    """«cần mang căn cước không» hỏi giữa lúc làm trợ cấp là hỏi về trợ cấp:
    mô hình trả lời được thì KHÔNG gợi ý chuyển. Câu thật sự về thủ tục khác
    thì mô hình bảo ngoài kho, lúc đó mới gợi ý chuyển."""
    calls = fake_llm("Dạ, bác chỉ mang căn cước công dân để cán bộ đối chiếu khi được yêu cầu thôi ạ.")
    d = client.post("/flow/ask", data={"procedure_id": HUU_TRI, "text": "cần mang căn cước không"}).json()
    assert d["via_llm"] is True and d["switch_to"] is None and len(calls) == 1
    fake_llm(llm.NOT_IN_KB)
    d = client.post("/flow/ask", data={"procedure_id": HUU_TRI, "text": "làm căn cước công dân cần giấy tờ gì"}).json()
    assert d["switch_to"] == "cap-the-can-cuoc" and d["via_llm"] is False


# --- 3. Kho tri thức phẳng cho prompt -----------------------------------------
def test_kb_context_du_moi_phan():
    t = llm.kb_context(kb.get(HUU_TRI))
    for phan in ["THỦ TỤC:", "ĐIỀU KIỆN", "KẾT LUẬN", "HỒ SƠ:", "NƠI NỘP:", "THỜI HẠN:", "CÂU HỎI THƯỜNG GẶP", "NGUỒN:"]:
        assert phan in t, phan
    assert "10 ngày làm việc" in t
