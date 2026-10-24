"""Kiểm chứng tab Chi tiết + PDF vách TCVN (phần 3/4/5 chương trình vách).

- build_wall_detail_sections đọc từ dict wall_tcvn_full: mọi số trong
  thẻ khớp dict kết quả (N–M/cắt/M2–M3 không đổi từng chữ số so với
  mốc: mẫu 0.44523, vùng biên 0.35931, lát-1 cũ 0.40256; cắt mẫu
  V=800 -> 0.403).
- Trích dẫn độ mảnh là Mục 10.2.2, không có card/mục nào trích
  "Bảng 30" làm căn cứ.
- Thẻ η trình bày đúng đường tính app (ηx ≈ 1.002 -> Mx* = 211.13)
  kèm giá trị quy trình chuẩn (ηx = 1.0 -> 210.72), không trình bày
  quy tắc rút gọn λ > 14 của web như quy tắc của app.
- PDF tóm tắt đúng 1 trang; PDF chi tiết xuất được và cùng nguồn số
  với tab (cùng builder).
- Harness ηx = 1.0 (CHỈ đo, không sửa production): D/C mẫu đổi
  0.44523 -> ~0.44520 (không đáng kể ở ca này vì M3* chỉ là thành
  phần nhỏ của Mα).
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
    assert abs(full["dc"] - 0.44523) <= 1e-5
    assert abs(full["shear_in"]["dc"] - 0.40259) <= 1e-4
    secs = build_wall_detail_sections(full)
    assert [s["num"] for s in secs] == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    txt = _all_text(secs)
    for needle in ["211.13", "313.09", "0.445", "0.403", "1,987.2",
                   "45.53", "6.37", "210.72", "108.84", "83.33",
                   "5,679.4", "848.17", "2φ12 a200"]:
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
    # Giới hạn 120 mượn + 200 theo chữ + chờ chốt đều được nêu.
    txt = _all_text(secs)
    assert "ĐANG CHỜ USER CHỐT 120 hay 200" in txt


def test_detail_eta_card_is_honest_app_path():
    secs = build_wall_detail_sections(_sample())
    x = _card_by_title(secs, 5, "Phương X")
    body = "\n".join(x["lines"])
    assert "211.13" in x["result"] and "1.002" in x["result"]
    assert "210.72" in body  # giá trị quy trình chuẩn η = 1,0
    assert "+0.20%" in body
    assert "KHÔNG CẦN XÉT" not in body  # cấm ghi nhãn sai kèm số đã nhân η
    y = _card_by_title(secs, 5, "Phương Y")
    assert "313.09" in y["result"] and "45.53" in "\n".join(y["lines"])


def test_detail_milestones_boundary_and_old():
    fb = wall_tcvn_full(WallInput(steel_mode="boundary"), _CONC, _STEEL,
                        loads=dict(_LOADS))
    assert abs(fb["dc"] - 0.35931) <= 1e-5
    txt_b = _all_text(build_wall_detail_sections(fb))
    assert "0.359" in txt_b and "211.07" in txt_b and "305.12" in txt_b
    fo = wall_tcvn_full(wall_from_dict(_OLD), _CONC, _STEEL,
                        loads={"N": 2500.0, "M_in": 3000.0,
                               "M_out": 60.0, "V_in": 0.0,
                               "V_out": 0.0, "T": 0.0})
    assert abs(fo["dc"] - 0.40256) <= 1e-5
    txt_o = _all_text(build_wall_detail_sections(fo))
    assert "0.403" in txt_o or "0.402" in txt_o


def test_eta_x_forced_harness_only():
    """HARNESS (không sửa production): cùng solver fiber của engine,
    chỉ thay M_in_d bằng giá trị quy trình chuẩn (ηx = 1.0)."""
    from rc_column.interaction import BiaxialCapacity
    full = _sample()
    cap = BiaxialCapacity(full["sec"], model=full["model"])
    m_std = abs(full["N"]) * full["e0_in"] / 1000.0
    assert abs(m_std - 210.72) <= 0.01
    assert abs((abs(full["M_in_d"]) - m_std) / m_std * 100.0
               - 0.20) <= 0.02
    r = cap.dc_ratio(full["N"], full["M_out_d"],
                     math.copysign(m_std, full["M_in"]))
    assert abs(r["dc"] - full["dc"]) < 0.002, (r["dc"], full["dc"])


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
