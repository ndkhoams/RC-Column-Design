"""Phần 2/7 — Bỏ banner kết luận chung vách, kết luận riêng dưới
mỗi phần tính toán (giống cột).

Kiểm tra ở tầng builder/PDF (không phụ thuộc Tk): tab Chi tiết và
PDF chi tiết dùng chung builder nên số/kết luận khớp nhau; PDF tóm
tắt kiểm tra qua text trích xuất.

QUY ƯỚC ok_all (đã chốt ở phần này): khóa "ok_all" vẫn giữ trong
dict kết quả (= ok N–M) chỉ để tương thích — KHÔNG còn render
thành banner và KHÔNG được dùng làm kết luận tổng. Cắt fail trong
khi N–M đạt vẫn cho ok_all = True chính là bằng chứng nó không
phải kết luận tổng: kết luận tổng không tồn tại nữa, mỗi phần
kết luận riêng.
"""

import io

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_detail import build_wall_detail_sections
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_input import WallInput
from rc_column.wall_pdf_report import export_wall_pdf_cards
from rc_column.wall_pdf_summary import export_wall_summary_pdf

CONC = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
STEEL = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
LOADS = {"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
         "V_in": 800.0, "V_out": 300.0, "T": 0.0}


def _full(seis=False, loads=None):
    return wall_tcvn_full(WallInput(sw_steel_grade="CB400-V"),
                          CONC, STEEL,
                          loads=dict(loads or LOADS),
                          seismic_shear=seis)


def _text(sections):
    out = []
    for s in sections:
        out.append(f"== {s['num']} {s['title']}")
        for c in s["cards"]:
            out.append(f"[{c.get('title', '')}]")
            out += list(c.get("lines", []))
            if c.get("result"):
                out.append(str(c["result"]))
    return "\n".join(out)


def _sec(sections, num):
    for s in sections:
        if s["num"] == num:
            return s
    raise AssertionError(f"missing section {num}")


def _pdf_text(fn, full):
    try:
        from pypdf import PdfReader
    except Exception:
        from PyPDF2 import PdfReader
    buf = io.BytesIO()
    fn(full, buf, member_name="V1", show_compression=True)
    buf.seek(0)
    r = PdfReader(buf)
    return len(r.pages), "\n".join((p.extract_text() or "")
                                   for p in r.pages)


def test_no_general_conclusion_q1_or_banner_text():
    txt = _text(build_wall_detail_sections(_full()))
    assert "Q1" not in txt
    assert "Kết luận chung" not in txt
    # Từ "banner" chỉ còn trong comment/docstring code, không được
    # xuất hiện trong nội dung render.
    assert "banner" not in txt.lower()
    sec9 = _sec(build_wall_detail_sections(_full()), 9)
    titles = [c["title"] for c in sec9["cards"]]
    assert "Kết luận chung" not in titles
    assert any("phạm vi kết luận" in t.lower() for t in titles)
    assert "Không có kết luận chung" in txt


def test_section3_slenderness_conclusion_last_and_fail():
    secs = build_wall_detail_sections(_full())
    sec3 = _sec(secs, 3)
    last = sec3["cards"][-1]
    assert last["title"] == "Kết luận độ mảnh"
    assert "ĐẠT" in last["result"] and "λ ≤ 120" in last["result"]
    # Độ mảnh fail (đặt λ ngoài MP = 130 trong dict hiển thị;
    # builder chỉ đọc số đã lưu, không tính lại).
    f = _full()
    f["slend"] = dict(f["slend"], lambda_out=130.0)
    sec3b = _sec(build_wall_detail_sections(f), 3)
    lastb = sec3b["cards"][-1]
    assert "KHÔNG ĐẠT" in lastb["result"]
    assert "λy" in "\n".join(lastb["lines"])


def test_section7_m2m3_reinterprets_nm_not_new_conclusion():
    full = _full()
    sec7 = _sec(build_wall_detail_sections(full), 7)
    last = sec7["cards"][-1]
    assert last["title"] == "Diễn giải kết luận M2–M3"
    assert "không phải kiểm tra độc lập" in "\n".join(last["lines"])
    assert "không phải kết luận độc lập" in "\n".join(last["lines"])
    assert "không tự tạo thêm một ĐẠT/KHÔNG ĐẠT mới" in "\n".join(
        last["lines"])
    assert f"{full['dc']:.3f}" in last["result"]
    assert ("ĐẠT" in last["result"]) == bool(full["ok"])
    # N–M fail thì diễn giải cũng KHÔNG ĐẠT cùng D/C (không tạo
    # kết luận mới): dùng ca N lớn làm N–M fail.
    fail = _full(loads={**LOADS, "N": 20000.0})
    assert fail["ok"] is False
    lastf = _sec(build_wall_detail_sections(fail), 7)["cards"][-1]
    assert "KHÔNG ĐẠT" in lastf["result"]
    assert f"{fail['dc']:.3f}" in lastf["result"]


def test_section6_nm_and_section8_shear_and_pending():
    full = _full()
    secs = build_wall_detail_sections(full)
    sec6 = _sec(secs, 6)
    assert sec6["cards"][-1]["result"].startswith("D/C = ")
    assert "ĐẠT" in sec6["cards"][-1]["result"]
    sec8 = _sec(secs, 8)
    titles = [c["title"] for c in sec8["cards"]]
    assert any("Trong mặt phẳng" in t for t in titles)
    assert any("Ngoài mặt phẳng" in t for t in titles)
    # Thẻ cuối mục 8 là trượt mạch ngừng CHƯA KIỂM, không ghi ĐẠT.
    slide = sec8["cards"][-1]
    assert slide["result"] == "CHƯA KIỂM"
    assert "CHƯA KIỂM" in "\n".join(slide["lines"])
    # Mục 9: vùng biên/cấu tạo CHƯA KIỂM, không ghi ĐẠT.
    sec9 = _sec(secs, 9)
    assert sec9["cards"][0]["result"] == "CHƯA KIỂM"


def test_section8_seismic_conditional_sentence():
    seis = _full(seis=True)
    txt = _text(build_wall_detail_sections(seis))
    assert "V_Ed = 1,5 × V2" in txt
    plain = _full(seis=False)
    txt2 = _text(build_wall_detail_sections(plain))
    assert "CHƯA kể phóng đại" in txt2
    # Cắt ngoài MP ghi rõ Qsw = 0 trong cả 2 trường hợp.
    assert "Qsw = 0" in txt and "Qsw = 0" in txt2


def test_ok_all_kept_for_compat_but_not_overall():
    # Cắt fail, N–M đạt: ok_all vẫn True (= ok N–M) — chứng tỏ
    # nó KHÔNG phải kết luận tổng; không code hiển thị nào được
    # dùng nó làm kết luận tổng nữa (grep: chỉ engine ghi, test
    # đọc; gui/pdf đọc full["ok"], không đọc ok_all).
    fail = _full(loads={**LOADS, "V_in": 5000.0, "V_out": 5000.0})
    assert fail["ok"] is True
    assert fail["shear_in"]["ok"] is False
    assert fail["shear_out"]["ok"] is False
    assert fail["ok_all"] is True
    secs = build_wall_detail_sections(fail)
    sec8 = _sec(secs, 8)
    results = [c["result"] for c in sec8["cards"]]
    assert any("KHÔNG ĐẠT" in r for r in results)


def test_pdfs_no_banner_q1_and_conclusions_under_blocks():
    full = _full(seis=True)
    pages, txt = _pdf_text(export_wall_summary_pdf, full)
    assert pages == 1
    assert "Q1" not in txt and "banner" not in txt.lower()
    assert "Kết luận chung" not in txt
    assert "Kết luận N–M" in txt
    assert "Kết luận độ mảnh" in txt
    # Tóm tắt KHÔNG còn caption dưới biểu đồ (ghi chú user
    # 2026-10-25 gạch bỏ cả dòng "Kết luận N–M" dưới N–Mα và
    # caption "Diễn giải M2–M3"): kết luận N–M chỉ còn ở bảng
    # KẾT QUẢ; PDF chi tiết (txt2 dưới đây) vẫn giữ caption.
    assert "Diễn giải M2–M3" not in txt
    assert "cùng kết luận N–M" not in txt
    assert "CHƯA KIỂM" in txt
    pages2, txt2 = _pdf_text(export_wall_pdf_cards, full)
    assert "Q1" not in txt2 and "banner" not in txt2.lower()
    assert "Kết luận chung" not in txt2
    assert "Diễn giải M2–M3" in txt2
    assert "Kết luận độ mảnh" in txt2
    assert "Không có kết luận chung" in txt2
