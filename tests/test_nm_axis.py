"""Nét trục ngang N = 0 trên biểu đồ N–Mα — quyết user 2026-10-29.

Hiện trạng trước lát: 4 hàm vẽ N–Mα (cột TCVN/ACI/EC2 + PDF TCVN)
và hàm lồng vẽ lại khi đổi góc xem của TCVN đều KHÔNG có đường
trục riêng tại N = 0 — chỉ có lưới ngang đứt mảnh #E5E7EB lw 0.7
nằm dưới fill (set_axisbelow), giống hệt mọi đường lưới khác nên
sau khi lát b65658fe mở vùng kéo, mức N = 0 nằm giữa biểu đồ mà
vẫn khó thấy. Lát này chỉ thêm nét vẽ, không đổi solver/D/C/ylim.

Test khóa (cột 3 chuẩn + vách qua hàm chung + PDF TCVN):
- đúng 1 đường y = 0 mới: màu #374151, nét liền, lw 1.4, zorder 2.5,
  xdata [0, 1] (axhline = hết bề rộng vùng vẽ);
- zorder 2.5 nằm trên fill (1) nhưng dưới đường bao (3), tia (4),
  điểm A/B (5/6) nên không che chúng;
- pixel tại hàng y = 0 trên canvas thật có màu xám đậm (không chỉ
  assert code gọi axhline, và không bị fill che);
- D/C và giới hạn trục TCVN không đổi so với trước lát.
Biểu đồ M2–M3 KHÔNG thuộc yêu cầu này, không đụng.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from rc_column.checker import ColumnInput, build_section, check_column
from rc_column.chart_draw import draw_nm_alpha_ax
from rc_column.aci_chart_draw import draw_aci_nm_alpha_ax
from rc_column.ec2_chart_draw import draw_ec2_nm_alpha_ax
from rc_column.aci_checker import check_column_aci
from rc_column.ec2_checker import check_column_ec2
from rc_column.aci_materials import ACIConcrete, ACISteel
from rc_column.ec2_materials import EC2Concrete, EC2Steel
from rc_column.pdf_export import interaction_image

_BASE = dict(concrete_grade="B25", gamma_b=0.85, steel_grade="CB400-V",
             cx=400.0, cy=400.0, cover=22.0, corner_dia=20.0,
             edge_t2_count=3, edge_t2_dia=20.0,
             edge_t3_count=3, edge_t3_dia=20.0, Lx=4.0, Ly=4.0,
             top_x="ngam_cung", bottom_x="ngam_cung",
             top_y="ngam_cung", bottom_y="ngam_cung",
             psi_x=0.5, psi_y=0.5)


def _axis_lines(ax):
    return [ln for ln in ax.lines
            if len(ln.get_ydata()) == 2
            and ln.get_ydata()[0] == 0 and ln.get_ydata()[1] == 0
            and ln.get_color() == "#374151"]


def _check_axis(ax):
    found = _axis_lines(ax)
    assert len(found) == 1, [(ln.get_color(), ln.get_linewidth())
                             for ln in ax.lines
                             if len(ln.get_ydata()) == 2
                             and ln.get_ydata()[0] == 0]
    ln = found[0]
    assert ln.get_linewidth() == 1.4, ln.get_linewidth()
    assert ln.get_zorder() == 2.5, ln.get_zorder()
    assert ln.get_linestyle() == "-", ln.get_linestyle()
    assert list(ln.get_xdata()) == [0, 1], ln.get_xdata()
    # Dưới đường bao (zorder 3): đường bao vẽ sau vẫn thấy rõ
    # tại giao điểm với trục.
    assert ax.lines[0].get_zorder() == 3
    assert ln.get_zorder() < ax.lines[0].get_zorder()


def _dark_fraction_at_zero(fig, ax):
    """Tỉ lệ pixel xám đậm trên hàng y = 0 (canvas thật)."""
    fig.canvas.draw()
    w, h = fig.canvas.get_width_height()
    rgba = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].astype(int)
    _, y0d = ax.transData.transform((0, 0))
    ypix = int(round(h - y0d))
    x0p, _ = ax.transData.transform((ax.get_xlim()[0], 0))
    x1p, _ = ax.transData.transform((ax.get_xlim()[1], 0))
    band = rgba[max(0, ypix - 1):ypix + 2, int(x0p):int(x1p)]
    target = np.array([55, 65, 81])  # #374151
    dist = np.sqrt(((band - target) ** 2).sum(axis=2))
    return float((dist < 60).mean())


def _max_dark_row_frac(png_bytes):
    """Hàng có tỉ lệ pixel xám đậm #374151 cao nhất trong PNG."""
    from PIL import Image
    import io
    img = np.array(Image.open(io.BytesIO(png_bytes)).convert("RGB"))
    img = img.astype(int)
    target = np.array([55, 65, 81])  # #374151
    dist = np.sqrt(((img - target) ** 2).sum(axis=2))
    return float((dist < 60).mean(axis=1).max())


def test_nm_axis_all_standards():
    inp = ColumnInput(**_BASE, N=1500.0, Mx=80.0, My=60.0)
    sec = build_section(inp)
    res = check_column(inp, n_angles=24)
    assert abs(res.dc - 0.6140612962169418) < 1e-12, res.dc
    fig, ax = plt.subplots()
    draw_nm_alpha_ax(ax, sec, inp, res, None)
    fig.canvas.draw()
    lo, hi = ax.get_ylim()
    assert lo < 0 < hi  # vùng kéo vẫn mở như lát b65658fe
    assert abs(lo - (-1924.0093991709016)) < 1e-6, lo
    assert abs(hi - 4005.821074611313) < 1e-6, hi
    _check_axis(ax)
    assert _dark_fraction_at_zero(fig, ax) > 0.3
    plt.close(fig)

    conc, steel = ACIConcrete(fc=30.0), ACISteel(fy=420.0)
    ares = check_column_aci(sec, conc, steel, 1500.0, 80.0, 60.0,
                            tied=True)
    fig, ax = plt.subplots()
    draw_aci_nm_alpha_ax(ax, sec, conc, steel, ares,
                         1500.0, 80.0, 60.0, tied=True)
    fig.canvas.draw()
    assert ax.get_ylim()[0] < 0
    _check_axis(ax)
    plt.close(fig)

    econ, esteel = EC2Concrete(fck=30.0), EC2Steel(fyk=500.0)
    eres = check_column_ec2(sec, econ, esteel, 1500.0, 80.0, 60.0)
    fig, ax = plt.subplots()
    draw_ec2_nm_alpha_ax(ax, sec, econ, esteel, eres,
                         1500.0, 80.0, 60.0)
    fig.canvas.draw()
    assert ax.get_ylim()[0] < 0
    _check_axis(ax)
    plt.close(fig)


def test_nm_axis_tcvn_pdf_and_wall():
    # PDF TCVN đi đường riêng (interaction_image), không qua
    # draw_nm_alpha_ax nên khóa bằng pixel trên PNG thật: chỉ nét
    # trục mới là vệt xám đậm #374151 chạy ngang gần hết bề rộng
    # (lưới nhạt, bao xanh lá, tia đỏ đều không đạt ngưỡng này).
    import pytest
    Image = pytest.importorskip("PIL.Image")
    import io
    inp = ColumnInput(**_BASE, N=1500.0, Mx=80.0, My=60.0)
    sec = build_section(inp)
    res = check_column(inp, n_angles=24)
    png = interaction_image(sec, inp, res, width_in=4.0, dpi=100)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert _max_dark_row_frac(png) > 0.5

    # Vách phẳng qua hàm chung của cột: trục phải có, D/C không đổi.
    from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                     ConcreteMaterial, SteelMaterial)
    from rc_column.wall_chart_adapter import wall_chart_inputs
    from rc_column.wall_engine import wall_tcvn_full
    from rc_column.wall_input import WallInput
    from rc_column.wall_pdf_figs import wall_nm_alpha_png
    conc = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
    full = wall_tcvn_full(
        WallInput(), conc, steel,
        loads={"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
               "V_in": 800.0, "V_out": 300.0, "T": 0.0})
    assert abs(full["dc"] - 0.45907) < 1e-5, full["dc"]
    wsec, winp, wres = wall_chart_inputs(full)
    fig, ax = plt.subplots()
    draw_nm_alpha_ax(ax, wsec, winp, wres, None)
    fig.canvas.draw()
    _check_axis(ax)
    assert _dark_fraction_at_zero(fig, ax) > 0.3
    plt.close(fig)
    # PDF vách phẳng dùng cùng hàm qua wall_nm_alpha_png.
    assert _max_dark_row_frac(wall_nm_alpha_png(full)) > 0.5
