"""3 việc nhỏ gộp 1 push — quyết user 2026-10-25 (runtime test head ab0f5160).

A. Tiêu đề frame bổ sung panel vách chỉ còn
   "Thép ngang, đai vùng biên, kháng chấn" (bỏ "Bổ sung —").
B. Tiêu đề trong axes của biểu đồ M2–M3 KHÔNG còn (rỗng) ở cả app
   và PDF — header ngoài "Mặt cắt M2–M3" + chip N xanh vẫn giữ,
   bao vẫn vẽ tại N = BN, số tính không đổi. Các hàm vẽ live là
   chart_draw / aci / ec2 (dùng chung cho GUI + PDF ACI/EC2/vách)
   và pdf_export.m2m3_image (PDF cột TCVN); _m2m3_ax chết trong
   tcvn_mixin cũng đã bỏ title theo quét lớp lỗi (không có caller
   live, chỉ kiểm bằng grep trong gate, không test ở đây).
C. (Cập nhật lát 1, 2026-10-27) _on_wall_sectype KHÔNG còn popup
   chặn/reset: chọn loại mới chuyển panel sang loại đó (mặt cắt +
   thép + preview); CHECK loại mới chặn riêng ở _on_check_wall.

Test GUI skip khi không có display; test Agg/engine chạy mọi môi trường.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest


def _title(draw_fn):
    fig, ax = plt.subplots()
    draw_fn(ax)
    title = ax.get_title()
    plt.close(fig)
    return title


def test_m2m3_axes_title_empty_all_standards_and_wall():
    """B: title axes M2–M3 rỗng ở TCVN/ACI/EC2/vách, D/C không đổi."""
    from rc_column.checker import ColumnInput, build_section, check_column
    from rc_column.chart_draw import draw_m2m3_ax
    from rc_column.aci_chart_draw import draw_aci_m2m3_ax
    from rc_column.aci_checker import check_column_aci
    from rc_column.aci_materials import ACIConcrete, ACISteel
    from rc_column.ec2_chart_draw import draw_ec2_m2m3_ax
    from rc_column.ec2_checker import check_column_ec2
    from rc_column.ec2_materials import EC2Concrete, EC2Steel

    base = dict(concrete_grade="B25", gamma_b=0.85, steel_grade="CB400-V",
                cx=400.0, cy=400.0, cover=22.0, corner_dia=20.0,
                edge_t2_count=3, edge_t2_dia=20.0,
                edge_t3_count=3, edge_t3_dia=20.0, Lx=4.0, Ly=4.0,
                top_x="ngam_cung", bottom_x="ngam_cung",
                top_y="ngam_cung", bottom_y="ngam_cung",
                psi_x=0.5, psi_y=0.5)
    inp = ColumnInput(**base, N=1500.0, Mx=80.0, My=60.0)
    sec = build_section(inp)
    res = check_column(inp, n_angles=24)
    assert abs(res.dc - 0.6140612962169418) < 1e-12, res.dc
    assert _title(lambda ax: draw_m2m3_ax(ax, sec, inp, res)) == ""
    conc, steel = ACIConcrete(fc=30.0), ACISteel(fy=420.0)
    ares = check_column_aci(sec, conc, steel, 1500.0, 80.0, 60.0, tied=True)
    assert _title(lambda ax: draw_aci_m2m3_ax(
        ax, sec, conc, steel, ares, 1500.0, 80.0, 60.0, tied=True)) == ""
    conc2, steel2 = EC2Concrete(fck=30.0), EC2Steel(fyk=500.0)
    eres = check_column_ec2(sec, conc2, steel2, 1500.0, 80.0, 60.0)
    assert _title(lambda ax: draw_ec2_m2m3_ax(
        ax, sec, conc2, steel2, eres, 1500.0, 80.0, 60.0)) == ""

    # Vách dùng chung hàm vẽ cột; D/C vách không đổi.
    from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                     ConcreteMaterial, SteelMaterial)
    from rc_column.wall_engine import wall_tcvn_full
    from rc_column.wall_input import WallInput
    from rc_column.wall_chart_adapter import wall_chart_inputs
    concw = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
    steelw = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
    full = wall_tcvn_full(
        WallInput(cover=13.0), concw, steelw,
        loads={"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
               "V_in": 0.0, "V_out": 0.0, "T": 0.0})
    secw, inpw, resw = wall_chart_inputs(full)
    assert _title(lambda ax: draw_m2m3_ax(ax, secw, inpw, resw)) == ""
    # Mốc này là ca WallInput mặc định (cover 13), đã đo y hệt trên cây
    # pristine ab0f5160 — chỉ đổi hiển thị, không đổi số tính.
    assert abs(float(full["dc"]) - 0.44520104645817127) < 1e-12, full["dc"]


def test_pdf_m2m3_image_still_renders():
    """B (PDF TCVN): m2m3_image vẫn render PNG hợp lệ sau khi bỏ title."""
    from rc_column.checker import ColumnInput, build_section, check_column
    from rc_column.pdf_export import m2m3_image
    base = dict(concrete_grade="B25", gamma_b=0.85, steel_grade="CB400-V",
                cx=400.0, cy=400.0, cover=22.0, corner_dia=20.0,
                edge_t2_count=3, edge_t2_dia=20.0,
                edge_t3_count=3, edge_t3_dia=20.0, Lx=4.0, Ly=4.0,
                top_x="ngam_cung", bottom_x="ngam_cung",
                top_y="ngam_cung", bottom_y="ngam_cung",
                psi_x=0.5, psi_y=0.5)
    inp = ColumnInput(**base, N=1500.0, Mx=80.0, My=60.0)
    sec = build_section(inp)
    res = check_column(inp, n_angles=24)
    png = m2m3_image(sec, inp, res)
    assert isinstance(png, bytes) and png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000


def _has_display():
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.destroy()
        return True
    except Exception:
        return False


@pytest.fixture
def wall_app():
    if not _has_display():
        pytest.skip("không có display Tk")
    from gui.app import App
    app = App()
    app.update_idletasks()
    app.cb_member.set("Vách")
    app._toggle_member()
    app.update_idletasks()
    yield app
    try:
        app.destroy()
    except Exception:
        pass


def test_extra_frame_title_exact(wall_app):
    """A: tiêu đề frame chỉ còn đúng chuỗi mới, không còn 'Bổ sung'."""
    title = wall_app.frm_wall_extra.cget("text")
    assert title == "Thép ngang, đai vùng biên, kháng chấn"
    assert "Bổ sung" not in title


def test_sectype_popup_has_no_gd1(wall_app):
    """C (cập nhật lát 1, 2026-10-27): chọn loại tiết diện khác KHÔNG
    còn popup chặn, KHÔNG reset về vách phẳng — panel chuyển sang
    loại mới (mặt cắt + thép + preview); CHECK mới chặn với thông
    báo đúng nghĩa (kiểm ở test_wallsec2 / _on_check_wall)."""
    import gui.wall_mixin as wm
    from gui.wall_mixin import _SECTYPES
    app = wall_app
    captured = {}

    def fake_showinfo(title, message, **kw):
        captured["title"] = title
        captured["message"] = message

    orig = wm.messagebox.showinfo
    wm.messagebox.showinfo = fake_showinfo
    try:
        app.w_cb_sectype.set(_SECTYPES[1])
        app._on_wall_sectype()
    finally:
        wm.messagebox.showinfo = orig
    assert not captured, "lát 1: chọn loại mới không còn popup chặn"
    assert app.w_cb_sectype.get() == _SECTYPES[1]
    assert app._wall_sec_code() == "barbell"
    assert app.w_en_sec_bf.get() == "1000"


def test_wallfollow2_0806_pdf_caption_has_bn_and_ved_comma():
    """Quyết user 2026-10-25 08:06 (gộp cùng push wallfollow2):
    (1) Caption PDF tóm tắt vách có lại "(N = BN kN)" đúng format cũ
    trước 39dc9a0 (N_level = BN, khớp chip N GUI); tiêu đề axes vẫn
    rỗng (việc B, kiểm ở test khác). (2) Hậu tố Ved một ngoặc duy
    nhất ngăn cách bằng dấu phẩy, cả ca DCM bật VACH/CA1; ca DCM
    tắt trơn, không trích dẫn. Số tính không đổi, vẫn 1 trang."""
    import io
    from rc_column.wall_pdf_summary import export_wall_summary_pdf
    from tests.test_wallpdf_align import _full, _full_ca1, _full_nodcm, _txt_of
    for full, member in ((_full(), "VACH"), (_full_ca1(), "CA1")):
        txt = _txt_of(full, member)
        n_level = float(full["m2m3"]["N_level"])
        assert f"(N = {n_level:,.0f} kN)" in txt, txt
        assert "Mặt cắt M2–M3 (tại N" not in txt
        v_d = float(full["shear_in"]["V_d"])
        assert (f"{v_d:.1f} kN (1.5 Ved, "
                f"TCVN 9386-1:2025 §5.4.2.4(7))") in txt
        assert "(1.5 Ved) (TCVN" not in txt
        assert "0.0 kN (không phóng đại)" in txt or \
            "kN (không phóng đại)" in txt
        buf = io.BytesIO()
        export_wall_summary_pdf(full, buf, member_name=member,
                                show_compression=True)
        buf.seek(0)
        import fitz
        doc = fitz.open(stream=buf.getvalue(), filetype="pdf")
        assert doc.page_count == 1
    # DCM tắt: giá trị trơn, không hậu tố, không trích dẫn.
    txt_off = _txt_of(_full_nodcm(), "VACH")
    tail_off = txt_off.split("KIỂM TRA KHẢ NĂNG CHỊU CẮT", 1)[1]
    assert "800.0 kN" in tail_off
    assert "(1.5 Ved" not in tail_off
    assert "TCVN 9386-1:2025" not in tail_off


def test_wallfollow2_0806_gui_shear_row_matches_pdf():
    """Quyết 08:06 mục 3: hàng cắt GUI (tab Kết quả vách, builder
    build_wall_shear_rows) khớp PDF — nhãn "Lực cắt tính toán,
    V2 / V3", giá trị trong MP có hậu tố "(1.5 Ved, TCVN …)"
    khi DCM bật (kể cả V = 0), trơn khi DCM tắt, ngoài MP vẫn
    "(không phóng đại)". Tab/thẻ Chi tiết dùng builder riêng
    (wall_detail.py) nên không đổi ở đây."""
    from gui.wall_mixin import build_wall_shear_rows
    from tests.test_wallpdf_align import _full, _full_ca1, _full_nodcm
    for full, v_in_exp in ((_full(), "1200.0 kN"),
                           (_full_ca1(), "0.0 kN")):
        rows = build_wall_shear_rows(full)
        row = [r for r in rows if r[0] == "Lực cắt tính toán, V2 / V3"]
        assert len(row) == 1
        assert row[0][1] == (f"{v_in_exp} (1.5 Ved, "
                             f"TCVN 9386-1:2025 §5.4.2.4(7))")
        assert row[0][2].endswith("(không phóng đại)")
        assert "×1.5 DCM" not in row[0][0]
    rows_off = build_wall_shear_rows(_full_nodcm())
    row_off = [r for r in rows_off
               if r[0] == "Lực cắt tính toán, V2 / V3"][0]
    assert row_off[1] == "800.0 kN"
    assert "(1.5 Ved" not in row_off[1]
