"""Kiểm chứng biểu đồ M2–M3 của CỘT vẽ tại N = BN (phần 7/7).

Trước sửa, đường bao vẽ tại N tải trong khi điểm B nằm ở BN trên
tia D/C nên B lệch khỏi bao tới ~93% ở ca tham chiếu (N=600,
Mx=My=20 trên tiết diện GUI mặc định: đo 93.50% trên polyline
24 điểm tại N tải). Nay bao vẽ tại N = BN — cùng định nghĩa như
vách (`rc_column/wall_m2m3.py`): `moment_capacity(BN, α) = |B|`.

- Chỉ đổi HIỂN THỊ: D/C không đổi (ca GUI mặc định TCVN giữ
  0.61406; mọi số khác lấy từ dict kết quả đã tính, không tính lại).
- Điểm A vẫn là mô men thiết kế ở N tải nên có thể không còn nằm
  trên bao mới — đúng bản chất, test chỉ khẳng định A không đổi
  tọa độ so với trước (không khẳng định A nằm trên bao).
- B được chèn đúng góc α vào polyline (như vách) nên B nằm đúng
  trên polyline vẽ (0%) dù lưới quét chỉ 15°; đồng thời B nằm trên
  contour thô 360 điểm tại BN trong dung sai < 0.5% (chuẩn cổng vách).
- Áp cho cả 3 chuẩn, cả tab Kết quả (hàm vẽ) lẫn PDF (hàm *_image
  dùng chung hàm vẽ đó).
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from rc_column.checker import ColumnInput, build_section, check_column
from rc_column.chart_draw import draw_m2m3_ax
from rc_column.aci_chart_draw import draw_aci_m2m3_ax, aci_m2m3_image
from rc_column.ec2_chart_draw import draw_ec2_m2m3_ax, ec2_m2m3_image
from rc_column.aci_checker import check_column_aci
from rc_column.ec2_checker import check_column_ec2
from rc_column.aci_materials import ACIConcrete, ACISteel
from rc_column.ec2_materials import EC2Concrete, EC2Steel
from rc_column.interaction import BiaxialCapacity
from rc_column.pdf_export import m2m3_image

_BASE = dict(concrete_grade="B25", gamma_b=0.85, steel_grade="CB400-V",
             cx=400.0, cy=400.0, cover=22.0,  # MIGRATION COVER: fixture cũ 30 - sw_dia 8
             corner_dia=20.0,
             edge_t2_count=3, edge_t2_dia=20.0,
             edge_t3_count=3, edge_t3_dia=20.0, Lx=4.0, Ly=4.0,
             top_x="ngam_cung", bottom_x="ngam_cung",
             top_y="ngam_cung", bottom_y="ngam_cung",
             psi_x=0.5, psi_y=0.5)


def _dist_to_polyline(px, py, xs, ys):
    best = float("inf")
    for i in range(len(xs) - 1):
        x1, y1, x2, y2 = xs[i], ys[i], xs[i + 1], ys[i + 1]
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - x1) * dx
                                                 + (py - y1) * dy) / L2))
        best = min(best, math.hypot(px - (x1 + t * dx),
                                    py - (y1 + t * dy)))
    return best


def _drawn_polyline(draw_fn):
    """Trích polyline bao + tiêu đề từ figure thật (không chỉ kiểm
    giá trị hàm): đường bao là Line2D dài nhất trên axes."""
    fig, ax = plt.subplots()
    draw_fn(ax)
    lines = [ln for ln in ax.lines if len(ln.get_xdata()) > 10]
    assert lines, "không tìm thấy polyline bao trên figure"
    xs = list(lines[0].get_xdata())
    ys = list(lines[0].get_ydata())
    title = ax.get_title()
    plt.close(fig)
    return xs, ys, title


def _check_b_on_envelope(bx, by, xs, ys, title, bn):
    mag = math.hypot(bx, by)
    d = _dist_to_polyline(by, bx, xs, ys)
    assert d / max(mag, 1e-9) < 0.005, (d, mag)
    assert xs[0] == xs[-1] and ys[0] == ys[-1], "polyline phải khép kín"
    assert f"{bn:,.0f}" in title, (title, bn)


def _check_raw_360_at_bn(sec, model, bn, bx, by):
    """B trên contour thô 360 điểm tại BN (không chèn B): < 0.5%."""
    cap = BiaxialCapacity(sec, model=model)
    xs, ys = [], []
    for k in range(360):
        m = cap.moment_capacity(float(bn), 360.0 * k / 360)
        rad = math.radians(360.0 * k / 360)
        xs.append(m * math.cos(rad))
        ys.append(m * math.sin(rad))
    xs.append(xs[0])
    ys.append(ys[0])
    d = _dist_to_polyline(by, bx, xs, ys)
    assert d / max(math.hypot(bx, by), 1e-9) < 0.005, (d, bx, by)


def test_tcvn_m2m3_at_bn_gui_default():
    inp = ColumnInput(**_BASE, N=1500.0, Mx=80.0, My=60.0)
    sec = build_section(inp)
    res = check_column(inp, n_angles=24)
    assert abs(res.dc - 0.6140612962169418) < 1e-12, res.dc
    xs, ys, title = _drawn_polyline(
        lambda ax: draw_m2m3_ax(ax, sec, inp, res))
    _check_b_on_envelope(res.Bx, res.By, xs, ys, title, res.BN)
    _check_raw_360_at_bn(sec, inp.concrete_model, res.BN, res.Bx, res.By)
    # Đối chứng hành vi cũ: tại N tải, B lệch 40.36% (không còn là bao vẽ).
    pts_n = BiaxialCapacity(sec, model=inp.concrete_model).mx_my_curve(
        float(res.N), n_angles=24)
    d_old = _dist_to_polyline(res.By, res.Bx,
                              [p[1] for p in pts_n], [p[0] for p in pts_n])
    assert 0.40 < d_old / math.hypot(res.Bx, res.By) < 0.41, d_old
    # PDF TCVN dùng chung hàm vẽ: ảnh xuất được, tiêu đề trong hình
    # được kiểm qua figure (hàm vẽ đã kiểm ở trên).
    png = m2m3_image(sec, inp, res, width_in=3.0, dpi=100)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 1000


def test_tcvn_m2m3_at_bn_reference_93pct():
    """Ca tham chiếu: trước sửa B lệch 93.50% khỏi bao tại N tải."""
    inp = ColumnInput(**_BASE, N=600.0, Mx=20.0, My=20.0)
    sec = build_section(inp)
    res = check_column(inp, n_angles=24)
    xs, ys, title = _drawn_polyline(
        lambda ax: draw_m2m3_ax(ax, sec, inp, res))
    _check_b_on_envelope(res.Bx, res.By, xs, ys, title, res.BN)
    _check_raw_360_at_bn(sec, inp.concrete_model, res.BN, res.Bx, res.By)
    pts_n = BiaxialCapacity(sec, model=inp.concrete_model).mx_my_curve(
        float(res.N), n_angles=24)
    d_old = _dist_to_polyline(res.By, res.Bx,
                              [p[1] for p in pts_n], [p[0] for p in pts_n])
    assert 0.93 < d_old / math.hypot(res.Bx, res.By) < 0.94, d_old
    # A không đổi: điểm A trên figure vẫn đúng mô men thiết kế ở
    # N tải (My_star, Mx_star) — chỉ đường bao đổi mức N.
    fig, ax = plt.subplots()
    draw_m2m3_ax(ax, sec, inp, res)
    # collections: [0] = B (vẽ trước), [1] = A (vẽ sau).
    a_xy = ax.collections[1].get_offsets()[0]
    plt.close(fig)
    assert abs(a_xy[0] - res.My_star) < 1e-9, (a_xy, res.My_star)
    assert abs(a_xy[1] - res.Mx_star) < 1e-9, (a_xy, res.Mx_star)


def test_aci_m2m3_at_bn():
    inp = ColumnInput(**_BASE, N=1500.0, Mx=80.0, My=60.0)
    sec = build_section(inp)
    conc, steel = ACIConcrete(fc=30.0), ACISteel(fy=420.0)
    res = check_column_aci(sec, conc, steel, 1500.0, 80.0, 60.0, tied=True)
    xs, ys, title = _drawn_polyline(
        lambda ax: draw_aci_m2m3_ax(ax, sec, conc, steel, res,
                                    1500.0, 80.0, 60.0, tied=True))
    _check_b_on_envelope(res["Bx"], res["By"], xs, ys, title, res["BN"])
    png = aci_m2m3_image(sec, conc, steel, res, 1500.0, 80.0, 60.0,
                         tied=True, width_in=3.0, dpi=100)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 1000


def test_ec2_m2m3_at_bn():
    inp = ColumnInput(**_BASE, N=1500.0, Mx=80.0, My=60.0)
    sec = build_section(inp)
    conc, steel = EC2Concrete(fck=30.0), EC2Steel(fyk=500.0)
    res = check_column_ec2(sec, conc, steel, 1500.0, 80.0, 60.0)
    xs, ys, title = _drawn_polyline(
        lambda ax: draw_ec2_m2m3_ax(ax, sec, conc, steel, res,
                                    1500.0, 80.0, 60.0))
    _check_b_on_envelope(res["Bx"], res["By"], xs, ys, title, res["BN"])
    png = ec2_m2m3_image(sec, conc, steel, res, 1500.0, 80.0, 60.0,
                         width_in=3.0, dpi=100)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 1000
