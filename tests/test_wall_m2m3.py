"""Kiểm chứng biểu đồ M2–M3 vách TCVN (rc_column/wall_m2m3.py).

- wall_tcvn_full chỉ THÊM khóa "m2m3": D/C các ca mốc khớp đúng
  head 4c62af9 (mốc hậu PA-A: mẫu 0.44523, vùng biên 0.35931,
  lát-1 cũ 0.40256, xoay 90° 0.44529).
- Đường bao = lát cắt tại N = BN: điểm B nằm trên polyline (sai số
  tương đối < 0.5%, đo bằng khoảng cách tới polyline thô 360 điểm
  chưa chèn B); polyline khép kín; A/B khớp đúng M_out_d/M_in_d
  và Bx/By của dict kết quả.
- Ánh xạ vách: M2 = M_out_d, M3 = M_in_d; trên hình A = (M_in_d,
  M_out_d), B = (By, Bx).
"""

import math

from rc_column.interaction import BiaxialCapacity
from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_input import WallInput, wall_from_dict
from rc_column.wall_m2m3 import draw_wall_m2m3_ax, wall_m2m3_figure

_CONC = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
_STEEL = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
_LOADS = {"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
          "V_in": 0.0, "V_out": 0.0, "T": 0.0}
_OLD = {"Lw": 2500, "tw": 350, "h_story": 3300, "h_total": 19800,
        "story_pos": "base", "cover": 25, "l0_out_factor": 1.0,
        "dia_v": 12, "s_v": 200, "layers_v": 2, "dia_h": 12, "s_h": 200,
        "layers_h": 2, "Lb_left": 500, "Lb_right": 500, "lb_auto": False,
        "dia_be": 28, "n_be": 8, "tie_dia_be": 10, "tie_s_be": 100,
        "tie_legs_be": 2, "seismic_class": "special", "seismic_on": True,
        "N": 0, "M_in": 0, "M_out": 0, "V_in": 0, "V_out": 0, "T": 0}


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


def _check_case(full, dc_milestone, dc_tol=1e-5):
    assert abs(full["dc"] - dc_milestone) <= dc_tol, \
        (full["dc"], dc_milestone)
    m = full["m2m3"]
    assert abs(m["N_level"] - full["BN"]) < 1e-9
    assert abs(m["A_M2"] - full["M_out_d"]) < 1e-9
    assert abs(m["A_M3"] - full["M_in_d"]) < 1e-9
    assert abs(m["B_M2"] - full["Bx"]) < 1e-9
    assert abs(m["B_M3"] - full["By"]) < 1e-9
    assert len(m["M3"]) == len(m["M2"]) and len(m["M3"]) >= 362
    assert m["M3"][0] == m["M3"][-1] and m["M2"][0] == m["M2"][-1]
    # B trên polyline cuối (đã chèn B) phải đúng từng chữ số thực tế
    d_final = _dist_to_polyline(full["By"], full["Bx"],
                                m["M3"], m["M2"])
    assert d_final <= 1e-9 * max(1.0, math.hypot(full["Bx"],
                                                full["By"])), d_final
    # B trên polyline THÔ 360 điểm (chưa chèn B): < 0.5%
    cap = BiaxialCapacity(full["sec"], model=full["model"])
    xs, ys = [], []
    for k in range(360):
        th = 360.0 * k / 360
        mm = cap.moment_capacity(float(full["BN"]), th)
        rad = math.radians(th)
        xs.append(mm * math.cos(rad))
        ys.append(mm * math.sin(rad))
    xs.append(xs[0])
    ys.append(ys[0])
    d_raw = _dist_to_polyline(full["By"], full["Bx"], xs, ys)
    rel = d_raw / max(math.hypot(full["Bx"], full["By"]), 1e-9)
    assert rel < 0.005, (d_raw, rel)
    return m


def test_wall_m2m3_sample_perimeter():
    full = wall_tcvn_full(WallInput(), _CONC, _STEEL, loads=dict(_LOADS))
    _check_case(full, 0.44523)


def test_wall_m2m3_boundary():
    full = wall_tcvn_full(WallInput(steel_mode="boundary"), _CONC, _STEEL,
                          loads=dict(_LOADS))
    _check_case(full, 0.35931)


def test_wall_m2m3_old_case_and_rot90():
    full = wall_tcvn_full(wall_from_dict(_OLD), _CONC, _STEEL,
                          loads={"N": 2500.0, "M_in": 3000.0,
                                 "M_out": 60.0, "V_in": 0.0,
                                 "V_out": 0.0, "T": 0.0})
    _check_case(full, 0.40256)
    full_r = wall_tcvn_full(WallInput(rot_deg=90), _CONC, _STEEL,
                            loads={"N": 2528.65, "M_in": 275.23,
                                   "M_out": 202.86, "V_in": 0.0,
                                   "V_out": 0.0, "T": 0.0})
    _check_case(full_r, 0.44529, dc_tol=1e-3)


def test_wall_m2m3_figure_shared_draw():
    """Hàm vẽ figure dùng chung cho PDF: vẽ được PNG từ đúng dict
    m2m3 đã lưu (không tính lại), dùng chung draw_wall_m2m3_ax."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    full = wall_tcvn_full(WallInput(), _CONC, _STEEL, loads=dict(_LOADS))
    fig, ax = plt.subplots()
    draw_wall_m2m3_ax(ax, full["m2m3"])
    assert ax.get_xlabel().startswith("M3")
    assert ax.get_ylabel().startswith("M2")
    plt.close(fig)
    png = wall_m2m3_figure(full["m2m3"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 1000
