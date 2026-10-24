"""Kiểm chứng tab Chi tiết + PDF vách TCVN (phần 3/4/5 chương trình vách).

- build_wall_detail_sections đọc từ dict wall_tcvn_full: mọi số trong
  thẻ khớp dict kết quả (N–M/cắt/M2–M3 không đổi từng chữ số so với
  mốc hậu cổng η §8.1.2.1.2: mẫu 0.44520, vùng biên 0.35929,
  lát-1 cũ 0.40226; cắt mẫu V=800 -> 0.403).
- Trích dẫn độ mảnh là Mục 10.2.2, không có card/mục nào trích
  "Bảng 30" làm căn cứ.
- Thẻ η trình bày đúng đường tính app ĐÃ CÓ cổng λ > 14 (phương án A
  2026-10-24): phương X mẫu λ = 6.37 → ηx = 1,0, M3* = 210.72;
  phương Y λ = 45.53 giữ ηy theo CT (44) -> M2* = 313.09. Không còn
  khối đối chiếu "app vs quy trình chuẩn" ở phương bị cổng.
- PDF tóm tắt đúng 1 trang; PDF chi tiết xuất được và cùng nguồn số
  với tab (cùng builder).
- (Lịch sử) Harness ηx = 1.0 trước cổng đo D/C mẫu 0.44523 -> 0.44520
  — nay chính là giá trị production sau cổng.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_input import WallInput, wall_from_dict
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_detail import build_wall_detail_sections

_CONC = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
_STEEL = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
_LOADS = {"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
          "V_in": 800.0, "V_out": 0.0, "T": 0.0}
_OLD = {"Lw": 2500, "tw": 350, "h_story": 3300, "h_total": 19800,
        "story_pos": "base", "cover": 25, "l0_out_factor": 1.0,
        "dia_v": 12, "s_v": 200, "layers_v": 2, "dia_h": 12, "s_h": 200,
        "layers_h": 2, "Lb_left": 500, "Lb_right": 500,
        "lb_auto": False, "dia_be": 28, "n_be": 8, "tie_dia_be": 10,
        "tie_s_be": 100, "tie_legs_be": 2, "seismic_class": "special",
        "seismic_on": True, "N": 0, "M_in": 0, "M_out": 0,
        "V_in": 0, "V_out": 0, "T": 0}


def _sample():
    return wall_tcvn_full(WallInput(), _CONC, _STEEL,
                          loads=dict(_LOADS))


def _all_text(sections):
    out = []
    for s in sections:
        out.append(s["title"])
        out.append(s.get("ref", ""))
        for c in s["cards"]:
            out.append(c.get("title", ""))
            out.append(c.get("ref", ""))
            out.extend(c.get("lines", []))
            out.append(c.get("result", ""))
    return "\n".join(out)


def _card_by_title(sections, num, title_sub):
    for s in sections:
        if s["num"] == num:
            for c in s["cards"]:
                if title_sub in c.get("title", ""):
                    return c
    raise AssertionError(f"no card {title_sub} in section {num}")


def test_detail_numbers_match_dict_sample():
    full = _sample()
    assert abs(full["dc"] - 0.44520) <= 1e-5
    assert abs(full["shear_in"]["dc"] - 0.40259) <= 1e-4
    secs = build_wall_detail_sections(full)
    assert [s["num"] for s in secs] == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    txt = _all_text(secs)
    for needle in ["210.72", "313.09", "0.445", "0.403", "1,987.2",
                   "45.53", "6.37", "108.84", "83.33",
                   "5,679.8", "847.71", "2φ12 a200"]:
        assert needle in txt, needle
    # Nhãn app: X = trong MP (e0x = 83.33), Y = ngoài MP (e0y = 108.84)
    cx = _card_by_title(secs, 4, "Phương X")
    cy = _card_by_title(secs, 4, "Phương Y")
    assert "83.33" in cx["result"] and "108.84" in cy["result"]
    # Ghi chú đảo nhãn web có mặt, không đổi nhãn app theo web.
    note = _card_by_title(secs, 4, "Đối chiếu nhãn")
    assert "ĐẢO NGƯỢC" in "\n".join(note["lines"])


def test_detail_slenderness_cites_10_2_2_not_bang30():
    secs = build_wall_detail_sections(_sample())
    sec3 = [s for s in secs if s["num"] == 3][0]
    assert "10.2.2" in sec3["ref"]
    for s in secs:
        assert "Bảng 30" not in s.get("ref", ""), s["ref"]
        for c in s["cards"]:
            assert "Bảng 30" not in c.get("ref", ""), c["ref"]
    # Giới hạn độ mảnh vách 120 theo TCVN 5574:2018 §10.2.2
    # (user chốt 2026-10-24) — không còn phương án 200 treo lơ lửng.
    txt = _all_text(secs)
    assert "ĐANG CHỜ" not in txt
    assert "120 hay 200" not in txt
    assert "theo 200" not in txt
    # Phạm vi chặt hơn: riêng mục 3 không còn bất kỳ chữ "chờ" nào
    # (chữ "đang chờ" còn lại ở mục 9 thuộc câu hỏi Q1 về banner,
    # không phải thẻ độ mảnh — phần việc riêng, không đụng ở đây).
    sec3_txt = _all_text([sec3])
    assert "chờ" not in sec3_txt.lower()
    y_card = _card_by_title(secs, 3, "Phương Y")
    assert "45.53" in y_card["result"] and "≤ 120: ĐẠT" in y_card["result"]
    # Badge ở dải > 120 cũng chỉ nêu 120, không còn nhắc 200.
    from rc_column.wall_detail import _lam_badge
    assert "KHÔNG ĐẠT" in _lam_badge(150.0) and "200" not in _lam_badge(150.0)
    assert "KHÔNG ĐẠT" in _lam_badge(250.0) and "200" not in _lam_badge(250.0)


def test_detail_eta_card_is_honest_app_path():
    # Hậu cổng η §8.1.2.1.2 (phương án A): phương X bị cổng in đúng
    # giá trị áp dụng η = 1,000 + căn cứ, KHÔNG còn khối đối chiếu
    # "app vs quy trình chuẩn"; phương Y (λ > 14) giữ cách trình bày cũ.
    secs = build_wall_detail_sections(_sample())
    x = _card_by_title(secs, 5, "Phương X")
    body = "\n".join(x["lines"])
    assert "210.72" in x["result"] and "1,000" in x["result"]
    assert "8.1.2.1.2" in body and "≤ 14" in body
    assert "211.13" not in x["result"] and "1.002" not in body
    assert "+0.20%" not in body and "Đối chiếu" not in body
    assert "KHÔNG CẦN XÉT" not in body
    y = _card_by_title(secs, 5, "Phương Y")
    assert "313.09" in y["result"] and "45.53" in "\n".join(y["lines"])


def test_detail_milestones_boundary_and_old():
    fb = wall_tcvn_full(WallInput(steel_mode="boundary"), _CONC, _STEEL,
                        loads=dict(_LOADS))
    assert abs(fb["dc"] - 0.35929) <= 1e-5
    txt_b = _all_text(build_wall_detail_sections(fb))
    assert "0.359" in txt_b and "210.72" in txt_b and "305.12" in txt_b
    fo = wall_tcvn_full(wall_from_dict(_OLD), _CONC, _STEEL,
                        loads={"N": 2500.0, "M_in": 3000.0,
                               "M_out": 60.0, "V_in": 0.0,
                               "V_out": 0.0, "T": 0.0})
    assert abs(fo["dc"] - 0.40226) <= 1e-5
    txt_o = _all_text(build_wall_detail_sections(fo))
    assert "0.403" in txt_o or "0.402" in txt_o


def test_eta_x_forced_harness_only():
    """Hậu cổng η §8.1.2.1.2: M_in_d của production ĐÃ BẰNG giá trị
    quy trình chuẩn (ηx = 1.0) — harness cũ (đo lệch +0.20% khi app
    còn nhân ηx = 1.002) nay trở thành kiểm chứng đồng nhất: dựng
    lại tia từ M_in chuẩn phải cho đúng D/C của dict."""
    from rc_column.interaction import BiaxialCapacity
    full = _sample()
    cap = BiaxialCapacity(full["sec"], model=full["model"])
    m_std = abs(full["N"]) * full["e0_in"] / 1000.0
    assert abs(m_std - 210.72) <= 0.01
    assert abs(abs(full["M_in_d"]) - m_std) < 0.01
    r = cap.dc_ratio(full["N"], full["M_out_d"],
                     math.copysign(m_std, full["M_in"]))
    assert abs(r["dc"] - full["dc"]) < 1e-9, (r["dc"], full["dc"])


def _pdf_page_count(path):
    data = open(path, "rb").read()
    # ReportLab: mỗi trang là 1 object "/Type /Page"; cây trang là
    # "/Type /Pages" (chứa chuỗi con "/Type /Page" nên phải trừ ra).
    return data.count(b"/Type /Page") - data.count(b"/Type /Pages")


def _patch_fonts_for_vm():
    """VM Debian: matplotlib không có mpl-data/fonts; PDF cột dùng
    font đó nên test PDF phải mượn font hệ thống khi cần. Trên máy
    user (Windows) font matplotlib có sẵn, patch này không kích hoạt."""
    try:
        from rc_column.pdf_export import _find_font
        _find_font()
        return
    except Exception:
        pass
    import rc_column.pdf_export as pe
    import rc_column.pdf_report_cards as prc
    sys_f = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    sys_b = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if os.path.exists(sys_f):
        pe._find_font = lambda: sys_f
        pe._find_font_bold = lambda: sys_b
        prc._find_font = pe._find_font
        prc._find_font_bold = pe._find_font_bold


def test_wall_pdfs_build_and_summary_is_one_page(tmp_path):
    _patch_fonts_for_vm()
    from rc_column.wall_pdf_report import export_wall_pdf_cards
    from rc_column.wall_pdf_summary import export_wall_summary_pdf
    full = _sample()
    p_sum = str(tmp_path / "wall_sum.pdf")
    p_det = str(tmp_path / "wall_det.pdf")
    export_wall_summary_pdf(full, p_sum, member_name="VACH-MAU")
    export_wall_pdf_cards(full, p_det, member_name="VACH-MAU")
    assert os.path.getsize(p_sum) > 50000
    assert os.path.getsize(p_det) > 50000
    assert _pdf_page_count(p_sum) == 1, _pdf_page_count(p_sum)
    assert _pdf_page_count(p_det) >= 1


def test_wall_summary_rot90_is_one_page(tmp_path):
    """Ca xoay 90° (mặt cắt dọc, ảnh portrait cao) cũng phải vừa
    đúng 1 trang tóm tắt — thang thu có mức sâu cho ca này."""
    _patch_fonts_for_vm()
    from rc_column.wall_pdf_summary import export_wall_summary_pdf
    full = wall_tcvn_full(WallInput(rot_deg=90), _CONC, _STEEL,
                          loads={"N": 2528.65, "M_in": 275.23,
                                 "M_out": 202.86, "V_in": 0.0,
                                 "V_out": 0.0, "T": 0.0})
    assert abs(full["dc"] - 0.44529) <= 1e-3
    p_sum = str(tmp_path / "wall_sum_rot90.pdf")
    export_wall_summary_pdf(full, p_sum, member_name="VACH-MAU")
    assert _pdf_page_count(p_sum) == 1, _pdf_page_count(p_sum)
