"""Biểu đồ N–M hiển thị nốt phần N < 0 (kéo) — quyết user 2026-10-29.

Trước đây mọi hàm vẽ N–M đều set_ylim(bottom=0) nên ẩn vùng kéo
dù solver đã sinh đường cong tới kéo thuần. Lát này chỉ đổi hiển
thị (giữ nửa có tải Mα >= 0), không đổi solver/D/C. Test khóa:
trục y phải mở xuống dưới 0 và điểm cuối đường cong phải là
kéo thuần (M = 0 tại N_min).
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from rc_column.checker import ColumnInput, build_section, check_column
from rc_column.chart_draw import draw_nm_alpha_ax
from rc_column.aci_chart_draw import draw_aci_nm_alpha_ax
from rc_column.ec2_chart_draw import draw_ec2_nm_alpha_ax
from rc_column.aci_checker import check_column_aci
from rc_column.ec2_checker import check_column_ec2
from rc_column.aci_materials import ACIConcrete, ACISteel
from rc_column.ec2_materials import EC2Concrete, EC2Steel

_BASE = dict(concrete_grade="B25", gamma_b=0.85, steel_grade="CB400-V",
             cx=400.0, cy=400.0, cover=22.0, corner_dia=20.0,
             edge_t2_count=3, edge_t2_dia=20.0,
             edge_t3_count=3, edge_t3_dia=20.0, Lx=4.0, Ly=4.0,
             top_x="ngam_cung", bottom_x="ngam_cung",
             top_y="ngam_cung", bottom_y="ngam_cung",
             psi_x=0.5, psi_y=0.5)


def _ylim(draw_fn):
    fig, ax = plt.subplots()
    draw_fn(ax)
    fig.canvas.draw()
    lo, hi = ax.get_ylim()
    ys = list(ax.lines[0].get_ydata())
    xs = list(ax.lines[0].get_xdata())
    plt.close(fig)
    return lo, min(ys), xs[ys.index(min(ys))], ax.get_xlim()[0]


def test_nm_shows_negative_n_all_standards():
    inp = ColumnInput(**_BASE, N=1500.0, Mx=80.0, My=60.0)
    sec = build_section(inp)
    res = check_column(inp, n_angles=24)
    assert abs(res.dc - 0.6140612962169418) < 1e-12, res.dc
    lo, nmin, m_at_min, x0 = _ylim(
        lambda ax: draw_nm_alpha_ax(ax, sec, inp, res, None))
    assert lo < 0 and nmin < 0 and abs(m_at_min) < 1e-6 and x0 == 0.0
    conc, steel = ACIConcrete(fc=30.0), ACISteel(fy=420.0)
    ares = check_column_aci(sec, conc, steel, 1500.0, 80.0, 60.0,
                            tied=True)
    lo, nmin, m_at_min, x0 = _ylim(
        lambda ax: draw_aci_nm_alpha_ax(ax, sec, conc, steel, ares,
                                        1500.0, 80.0, 60.0, tied=True))
    assert lo < 0 and nmin < 0 and abs(m_at_min) < 1e-6 and x0 == 0.0
    econ, esteel = EC2Concrete(fck=30.0), EC2Steel(fyk=500.0)
    eres = check_column_ec2(sec, econ, esteel, 1500.0, 80.0, 60.0)
    lo, nmin, m_at_min, x0 = _ylim(
        lambda ax: draw_ec2_nm_alpha_ax(ax, sec, econ, esteel, eres,
                                        1500.0, 80.0, 60.0))
    assert lo < 0 and nmin < 0 and abs(m_at_min) < 1e-6 and x0 == 0.0
