"""View 3D cho vách (quyết user 2026-10-30): dropdown "Góc xem" của
biểu đồ N–Mα vách có thêm "3D" như bên cột.

- Mặt tương tác 3D (N–M2–M3) vẽ bằng mpl_toolkits.mplot3d, cùng
  BiaxialCapacity mà draw_nm_alpha_ax dùng vẽ bao 2D (qua adapter
  wall_chart_inputs) — KHÔNG tính lại solver, cùng họ mặt cho mọi
  loại tiết diện (phẳng, Barbell/T/L/C/U, DXF).
- Trục theo đúng khung solver của vách như biểu đồ 2D
  (M2 = M_out, M3 = M_in); điểm A đỏ = điểm tải thiết kế.
- Chọn lại góc khác thì tạo lại axes 2D (không vẽ 2D trên axes 3D).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math

import pytest

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_chart_adapter import wall_chart_inputs
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_input import WallInput

_CONC = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
_STEEL = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
_LOADS = {"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
          "V_in": 800.0, "V_out": 300.0, "T": 0.0}


def _full_flat():
    return wall_tcvn_full(WallInput(), _CONC, _STEEL,
                          loads=dict(_LOADS))


def _full_c():
    w = WallInput(section_type="c-core", Lw=3000.0, sec_bf=1500.0,
                  sec_lr=600.0)
    return wall_tcvn_full(
        w, _CONC, _STEEL,
        loads={"N": 2000.0, "M_in": 800.0, "M_out": 200.0,
               "V_in": 0.0, "V_out": 0.0, "T": 0.0})


def _surface(full):
    """Đúng pipeline mà _draw_wall_3d_interaction dùng (Agg)."""
    import matplotlib
    matplotlib.use("Agg")
    import numpy as np
    from rc_column.interaction import BiaxialCapacity
    sec, inp_ns, res_ns = wall_chart_inputs(full)
    cap = BiaxialCapacity(sec, model=inp_ns.concrete_model,
                          n_angles=24)
    n_vals, th_vals, m2_grid, m3_grid = cap.surface_grid(
        n_n=25, n_angles=36)
    return n_vals, th_vals, m2_grid, m3_grid, res_ns, np


def test_wall_3d_surface_flat():
    full = _full_flat()
    assert abs(full["dc"] - 0.45907) < 1e-5, full["dc"]
    n_vals, th_vals, m2g, m3g, res_ns, np = _surface(full)
    assert m2g.shape == (25, 36) and m3g.shape == (25, 36)
    assert len(n_vals) == 25 and len(th_vals) == 36
    # Mặt phủ cả nén lẫn kéo (N_min < 0 < N_max).
    assert float(n_vals[0]) < 0 < float(n_vals[-1])
    # Điểm A đúng tọa độ điểm tải thiết kế (khung solver vách).
    assert res_ns.Mx_star == full["M_out_d"]
    assert res_ns.My_star == full["M_in_d"]
    assert res_ns.N == full["N"]
    # Điểm A nằm trong biên mặt tại mọi góc (không vượt khả năng).
    assert abs(res_ns.Mx_star) <= float(np.abs(m2g).max()) + 1e-6
    assert abs(res_ns.My_star) <= float(np.abs(m3g).max()) + 1e-6
    # D/C không đổi (không tính lại).
    assert abs(full["dc"] - 0.45907) < 1e-5


def test_wall_3d_surface_c_core():
    """C-core: trục trong MP = y — mặt 3D vẫn cùng khung solver."""
    full = _full_c()
    assert math.isfinite(full["dc"]) and full["dc"] > 0
    n_vals, th_vals, m2g, m3g, res_ns, np = _surface(full)
    assert m2g.shape == (25, 36)
    assert float(n_vals[0]) < 0 < float(n_vals[-1])
    # Adapter đa giác dùng Mx_d/My_d (khung canonical), không phải
    # M_out_d/M_in_d vật lý — điểm A phải khớp đúng khung đó.
    assert res_ns.Mx_star == float(full.get("Mx_d", full["M_out_d"]))
    assert res_ns.My_star == float(full.get("My_d", full["M_in_d"]))


def _needs_display():
    try:
        import tkinter as tk
        _r = tk.Tk()
        _r.withdraw()
        _r.destroy()
    except Exception:
        pytest.skip("không có display Tk")


def _wall_app():
    _needs_display()
    from gui.app import App
    app = App()
    app.update_idletasks()
    app.cb_member.set("Vách")
    app._toggle_member()
    app.update_idletasks()
    app.var_load_mode.set("manual")

    def _set(entry, val):
        entry.delete(0, "end")
        entry.insert(0, str(val))

    _set(app.en_N, 2528.65)
    _set(app.en_My, 202.86)
    _set(app.en_Mx, 275.23)
    _set(app.en_Q2, 800)
    _set(app.en_Q3, 300)
    app._on_check_wall()
    app.update_idletasks()
    return app


def test_wall_3d_option_and_render():
    app = _wall_app()
    try:
        full = getattr(app, "_tcvn_wall_full", None)
        assert full is not None
        dc0 = float(full["dc"])
        cb = getattr(app, "_wall_nm_cb", None)
        assert cb is not None
        assert "3D" in list(cb["values"])
        # Chọn 3D -> axes 3d, không traceback.
        cb.set("3D")
        app._on_wall_nm_angle_changed()
        app.update_idletasks()
        ax = getattr(app, "_wall_nm_ax", None)
        assert ax is not None
        assert getattr(ax, "name", "") == "3d"
        assert ax.get_xlabel() == "M2 (kN·m)"
        assert ax.get_ylabel() == "M3 (kN·m)"
        assert ax.get_zlabel() == "N (kN)"
        # Quay lại góc tải -> tạo lại axes 2D, không vẽ 2D trên
        # axes 3D.
        cb.set("α (góc tải)")
        app._on_wall_nm_angle_changed()
        app.update_idletasks()
        ax2 = getattr(app, "_wall_nm_ax", None)
        assert ax2 is not None
        assert getattr(ax2, "name", "") != "3d"
        # D/C và dict kết quả không đổi.
        assert abs(float(full["dc"]) - dc0) < 1e-12
    finally:
        try:
            app.destroy()
        except Exception:
            pass
