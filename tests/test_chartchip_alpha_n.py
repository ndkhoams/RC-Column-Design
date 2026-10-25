"""Chip α / chip N trên tab Kết quả — quyết user 2026-10-25.

- Biểu đồ N–Mα: chip "α = …°" (1 chữ số thập phân) hiển thị ở cả
  cột (3 chuẩn, đã có) và vách (trước đây vách chưa có chip này ở
  header — nay thêm, góc tải từ dict kết quả full["alpha_deg"]).
- Biểu đồ M2–M3: GIỮ chip N xanh ở header (BN, định dạng cột
  "N = … kN"), CHỈ XÓA hậu tố "(tại N = … kN)" trong tiêu đề axes
  của cả 3 hàm vẽ dùng chung (TCVN/ACI/EC2). Bao vẫn vẽ tại N = BN
  (chứng minh bằng B nằm trên polyline, không bằng tiêu đề nữa).
- Đính chính 07:26 thay phần bỏ chip trong brief trước: chip N
  KHÔNG xóa. Test này khóa cả hai điểm riêng biệt đó.
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
from rc_column.aci_chart_draw import draw_aci_m2m3_ax
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


def _title(draw_fn):
    fig, ax = plt.subplots()
    draw_fn(ax)
    title = ax.get_title()
    plt.close(fig)
    return title


def test_m2m3_axes_titles_have_no_n_suffix_all_standards():
    """Tiêu đề axes M2–M3 chỉ còn "M2–M3" ở cả 3 chuẩn cột."""
    inp = ColumnInput(**_BASE, N=1500.0, Mx=80.0, My=60.0)
    sec = build_section(inp)
    res = check_column(inp, n_angles=24)
    # Số tính không đổi so với mốc trước sửa.
    assert abs(res.dc - 0.6140612962169418) < 1e-12, res.dc
    assert _title(lambda ax: draw_m2m3_ax(ax, sec, inp, res)) == "M2–M3"
    conc, steel = ACIConcrete(fc=30.0), ACISteel(fy=420.0)
    ares = check_column_aci(sec, conc, steel, 1500.0, 80.0, 60.0,
                            tied=True)
    assert _title(lambda ax: draw_aci_m2m3_ax(
        ax, sec, conc, steel, ares, 1500.0, 80.0, 60.0,
        tied=True)) == "M2–M3"
    from rc_column.ec2_chart_draw import draw_ec2_m2m3_ax
    conc2, steel2 = EC2Concrete(fck=30.0), EC2Steel(fyk=500.0)
    eres = check_column_ec2(sec, conc2, steel2, 1500.0, 80.0, 60.0)
    assert _title(lambda ax: draw_ec2_m2m3_ax(
        ax, sec, conc2, steel2, eres, 1500.0, 80.0, 60.0)) == "M2–M3"


def test_wall_m2m3_axes_title_and_chip_sources():
    """Vách dùng chung hàm vẽ cột nên tiêu đề cũng chỉ còn "M2–M3";
    nguồn chip vách (α tải, BN) vẫn có trong dict kết quả."""
    from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                     ConcreteMaterial, SteelMaterial)
    from rc_column.wall_engine import wall_tcvn_full
    from rc_column.wall_input import WallInput
    from rc_column.wall_chart_adapter import wall_chart_inputs
    conc = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
    loads = {"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
             "V_in": 0.0, "V_out": 0.0, "T": 0.0}
    full = wall_tcvn_full(WallInput(cover=13.0), conc, steel,
                          loads=dict(loads))
    sec, inp_ns, res_ns = wall_chart_inputs(full)
    assert _title(lambda ax: draw_m2m3_ax(ax, sec, inp_ns, res_ns)) \
        == "M2–M3"
    # Nguồn chip: α tải và BN đều hữu hạn, lấy từ dict đã tính.
    assert math.isfinite(float(full["alpha_deg"]))
    assert math.isfinite(float(full["BN"])) and full["BN"] != 0


def test_gui_headers_keep_n_chip_and_wall_has_both_chips():
    """Mức source GUI: chip N vẫn còn ở cột, vách nay có cả 2 chip."""
    root = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(root, "gui", "result_renderer.py"),
              encoding="utf-8") as f:
        renderer = f.read()
    # Renderer chung vẫn vẽ chip N (không bị gỡ theo brief cũ).
    assert 'config.get("m2m3_n_text")' in renderer
    assert 'config.get("nm_alpha_text")' in renderer
    with open(os.path.join(root, "gui", "wall_mixin.py"),
              encoding="utf-8") as f:
        wall = f.read()
    # Chip α vách: góc tải từ full["alpha_deg"], format 1 thập phân.
    assert "α = {float(full['alpha_deg']):.1f}°" in wall
    # Chip N vách: BN, format y hệt cột ("N = … kN", dấu +).
    assert "N = {float(full['BN']):+.1f} kN" in wall
    with open(os.path.join(root, "gui", "tcvn_mixin.py"),
              encoding="utf-8") as f:
        tcvn = f.read()
    # Header M2–M3 cũ của TCVN vẫn giữ chip N (BN).
    assert "N = {getattr(res, 'BN', res.N):+.1f} kN" in tcvn
    for name in ("rc_column/chart_draw.py",
                 "rc_column/aci_chart_draw.py",
                 "rc_column/ec2_chart_draw.py"):
        with open(os.path.join(root, name), encoding="utf-8") as f:
            src = f.read()
        # Chỉ kiểm dòng set_title thật (comment giải thích việc bỏ
        # hậu tố được phép nhắc tới "(tại N").
        for line in src.splitlines():
            if "set_title" in line:
                assert "(tại N" not in line, (name, line)
