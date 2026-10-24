"""Biểu đồ vách dùng CHUNG engine hiển thị của cột (phần 1).

- Adapter (`rc_column.wall_chart_adapter`): ánh xạ đúng
  M2 = M_out_d, M3 = M_in_d; BN/Bx/By/N và model giữ nguyên.
- Góc xem: xoay Mx'/My' đúng góc mà Ma/BN/Bx/By/N không đổi;
  render N–Mα tại 0°/90°/180° đổi đường bao nhưng điểm A/B
  (text trên hình) đứng yên.
- Render Agg cả 2 biểu đồ bằng đúng hàm vẽ cột: legend 4 mục
  đặt DƯỚI trục; M2–M3 có title ghi BN; B nằm trên polyline vẽ.
- Ghi chú A/B/O đúng format cột TCVN, khớp số dict, không có
  combo (vách nhập tay chưa có combo).
- PNG PDF: wall_nm_alpha_png + wall_m2m3_figure (nay nhận
  nguyên dict `full`) đều vẽ được qua engine cột.
"""

import math

from rc_column.chart_draw import draw_m2m3_ax, draw_nm_alpha_ax
from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_chart_adapter import (wall_chart_inputs,
                                          wall_chart_notes)
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_input import WallInput
from rc_column.wall_m2m3 import wall_m2m3_figure
from rc_column.wall_pdf_figs import wall_nm_alpha_png

_CONC = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
_STEEL = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
# Ca mẫu tươi preset web: WallInput() mặc định (cover 25 theo
# nghĩa c_đai) + V2 = 800 / V3 = 300; D/C N–M mốc 0.45907.
_LOADS = {"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
          "V_in": 800.0, "V_out": 300.0, "T": 0.0}


def _full():
    return wall_tcvn_full(WallInput(), _CONC, _STEEL,
                          loads=dict(_LOADS))


def _fig_ax():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    return fig, ax, plt


def test_adapter_mapping():
    full = _full()
    assert abs(full["dc"] - 0.45907) < 1e-5, full["dc"]
    sec, inp_ns, res_ns = wall_chart_inputs(full)
    assert sec is full["sec"]
    assert inp_ns.concrete_model == full["model"]
    # Ánh xạ chốt: Mx_star = M_out_d (M2), My_star = M_in_d (M3).
    assert res_ns.Mx_star == full["M_out_d"]
    assert res_ns.My_star == full["M_in_d"]
    assert res_ns.N == full["N"]
    assert res_ns.BN == full["BN"]
    assert res_ns.Bx == full["Bx"]
    assert res_ns.By == full["By"]


def test_view_angle_rotation_keeps_magnitudes():
    full = _full()
    ma = math.hypot(full["M_out_d"], full["M_in_d"])
    for deg in (0.0, 90.0, 180.0, 270.0, 360.0):
        _, _, res = wall_chart_inputs(full, view_angle_deg=deg)
        rad = math.radians(deg)
        assert res.Mx_star == math.sin(rad) * ma or \
            abs(res.Mx_star - ma * math.sin(rad)) < 1e-9
        assert abs(res.My_star - ma * math.cos(rad)) < 1e-9
        assert abs(math.hypot(res.Mx_star, res.My_star) - ma) < 1e-9
        # A/B/D/C giữ nguyên: N, BN, Bx, By không bị xoay.
        assert res.N == full["N"]
        assert res.BN == full["BN"]
        assert res.Bx == full["Bx"]
        assert res.By == full["By"]


def _legend_below_axes(fig, ax):
    fig.canvas.draw()
    leg = ax.get_legend()
    assert leg is not None
    assert len(leg.get_texts()) == 4
    leg_ext = leg.get_window_extent()
    ax_ext = ax.get_window_extent()
    assert leg_ext.y1 <= ax_ext.y0 + 2.0, (leg_ext, ax_ext)
    return [t.get_text() for t in leg.get_texts()]


def test_render_nm_alpha_shared_engine():
    full = _full()
    sec, inp_ns, res_ns = wall_chart_inputs(full)
    fig, ax, plt = _fig_ax()
    draw_nm_alpha_ax(ax, sec, inp_ns, res_ns, None)
    labels = _legend_below_axes(fig, ax)
    assert labels == ["Đường bao N-Mα", "Tia tải O-A-B",
                      "Điểm tải A", "Điểm giới hạn B"]
    assert ax.get_xlabel().startswith("Mα")
    assert ax.get_ylabel().startswith("N")
    # Điểm A/B (text trên hình) đúng số dict.
    texts = {t.get_text().strip(): t.get_position() for t in ax.texts}
    assert texts["A"] == (math.hypot(full["M_out_d"], full["M_in_d"]),
                          full["N"])
    assert texts["B"] == (math.hypot(full["Bx"], full["By"]),
                          full["BN"])
    plt.close(fig)


def test_render_m2m3_shared_engine():
    full = _full()
    sec, inp_ns, res_ns = wall_chart_inputs(full)
    fig, ax, plt = _fig_ax()
    draw_m2m3_ax(ax, sec, inp_ns, res_ns)
    labels = _legend_below_axes(fig, ax)
    assert labels == ["Đường bao M2-M3", "Tia tải O-A-B",
                      "Điểm tải A", "Điểm giới hạn B"]
    assert ax.get_xlabel().startswith("M3")
    assert ax.get_ylabel().startswith("M2")
    assert f"{full['BN']:,.0f}" in ax.get_title()
    # B nằm trên polyline vẽ (đã chèn B đúng góc).
    lines = [ln for ln in ax.lines if len(ln.get_xdata()) > 10]
    assert lines
    xs = list(lines[0].get_xdata())
    ys = list(lines[0].get_ydata())
    assert xs[0] == xs[-1] and ys[0] == ys[-1]
    best = float("inf")
    for i in range(len(xs) - 1):
        x1, y1, x2, y2 = xs[i], ys[i], xs[i + 1], ys[i + 1]
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        t = 0.0 if l2 == 0 else max(0.0, min(1.0, (
            (full["By"] - x1) * dx + (full["Bx"] - y1) * dy) / l2))
        best = min(best, math.hypot(full["By"] - (x1 + t * dx),
                                    full["Bx"] - (y1 + t * dy)))
    rel = best / max(math.hypot(full["Bx"], full["By"]), 1e-9)
    assert rel < 1e-9, (best, rel)
    plt.close(fig)


def test_view_angle_render_envelope_moves_points_stay():
    full = _full()
    envelopes = {}
    for deg in (None, 0.0, 90.0, 180.0):
        sec, inp_ns, res_ns = wall_chart_inputs(
            full, view_angle_deg=deg)
        fig, ax, plt = _fig_ax()
        draw_nm_alpha_ax(ax, sec, inp_ns, res_ns, None)
        fig.canvas.draw()
        # Đường bao là line đầu tiên vẽ (64 mức exact).
        envelopes[deg] = (list(ax.lines[0].get_xdata()),
                          list(ax.lines[0].get_ydata()))
        texts = {t.get_text().strip(): t.get_position()
                 for t in ax.texts}
        # A/B đứng yên ở mọi góc xem.
        assert texts["A"] == (
            math.hypot(full["M_out_d"], full["M_in_d"]), full["N"])
        assert texts["B"] == (math.hypot(full["Bx"], full["By"]),
                              full["BN"])
        plt.close(fig)
    # Đường bao đổi theo góc (không trùng nhau từng điểm).
    base = envelopes[None]
    for deg in (0.0, 90.0, 180.0):
        other = envelopes[deg]
        assert len(other[0]) == len(base[0])
        assert any(abs(a - b) > 1e-6
                   for a, b in zip(other[0], base[0]))


def test_notes_block_matches_dict_no_combo():
    full = _full()
    notes = wall_chart_notes(full)
    assert len(notes) == 3
    (t0, c0), (t1, c1), (t2, c2) = notes
    assert c0 == "#059669" and c1 == "#2563EB" and c2 == "#EA580C"
    assert f"α = {full['alpha_deg']:.1f}°" in t0
    assert f"D/C = {full['dc']:.3f}" in t0 and "ĐẠT" in t0
    assert f"N = {full['N']:+.1f} kN" in t1
    assert f"Mα = {full['Malpha']:.1f}" in t1
    assert f"M2 = {full['M_out_d']:.1f}" in t1
    assert f"M3 = {full['M_in_d']:.1f}" in t1
    # Vách nhập tay chưa có combo: dòng A không kèm "[...]".
    assert "[" not in t1
    assert f"N = {full['BN']:+.1f} kN" in t2
    assert f"M2u = {full['Bx']:.1f}" in t2
    assert f"M3u = {full['By']:.1f}" in t2
    # Trường hợp KHÔNG ĐẠT: dòng 1 đỏ + chữ KHÔNG ĐẠT.
    bad = dict(full)
    bad["ok"] = False
    bad["dc"] = 1.234
    t0b, c0b = wall_chart_notes(bad)[0]
    assert c0b == "#DC2626" and "KHÔNG ĐẠT" in t0b
    assert "D/C = 1.234" in t0b


def test_pdf_pngs_via_shared_engine():
    full = _full()
    png_nm = wall_nm_alpha_png(full)
    assert png_nm[:8] == b"\x89PNG\r\n\x1a\n" and len(png_nm) > 1000
    png_mm = wall_m2m3_figure(full)
    assert png_mm[:8] == b"\x89PNG\r\n\x1a\n" and len(png_mm) > 1000
