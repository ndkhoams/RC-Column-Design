"""View 3D cho vách (quyết user 2026-10-30; vẽ lại theo ảnh mẫu
"Biểu đồ 3D N–Mx–My").

- Mặt tương tác 3D vẽ bằng mpl_toolkits.mplot3d, cùng
  BiaxialCapacity mà draw_nm_alpha_ax dùng vẽ bao 2D (qua adapter
  wall_chart_inputs) — KHÔNG tính lại solver, cùng họ mặt cho mọi
  loại tiết diện (phẳng, Barbell/T/L/C/U, DXF).
- Khung tọa độ là khung canonical Mx–My của tiết diện (mặt từ
  surface_grid vốn là Mx = M·sinθ, My = M·cosθ): vách phẳng
  Mx = M_out / My = M_in; vách C/U Mx = M_in / My = M_out
  (trục trong MP là y). Điểm A/B, đường cong α đều lấy đúng
  khung này qua adapter nên khớp mặt.
- Hiển thị theo ảnh mẫu: 3 trục qua gốc O, nhãn 2 đầu mỗi trục
  (+Mx/−Mx, +My/−My, +N Nén/−N Kéo) + "O"; mặt wireframe xám
  nhạt mờ; đường cong N–Mα xanh lá tại góc tải; điểm A xanh lá,
  điểm B thoi cam, tia đứt đỏ O–A–B kéo dài ×1.18; legend 5 mục;
  caption "Biểu đồ 3D N–Mx–My" dưới figure.
- Chọn lại góc khác thì tạo lại axes 2D (không vẽ 2D trên
  axes 3D) và trả layout 2D như lúc build ban đầu.
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

_GREEN = "#059669"
_ORANGE = "#F97316"
_RED = "#DC2626"


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
    # Điểm A đúng tọa độ điểm tải thiết kế (khung canonical).
    assert res_ns.Mx_star == full["M_out_d"]
    assert res_ns.My_star == full["M_in_d"]
    assert res_ns.N == full["N"]
    # Điểm A nằm trong biên mặt tại mọi góc (không vượt khả năng).
    assert abs(res_ns.Mx_star) <= float(np.abs(m2g).max()) + 1e-6
    assert abs(res_ns.My_star) <= float(np.abs(m3g).max()) + 1e-6
    # D/C không đổi (không tính lại).
    assert abs(full["dc"] - 0.45907) < 1e-5


def test_wall_3d_surface_c_core():
    """C-core: trục trong MP = y — mặt 3D vẫn cùng khung canonical."""
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


def _rgba(hexcolor):
    from matplotlib.colors import to_rgba
    return to_rgba(hexcolor)


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
        # 1. Nhãn 2 đầu mỗi trục + "O" tại gốc (pane/tick mặc
        # định ẩn).
        _texts = [t.get_text() for t in ax.texts]
        for _s in ("+Mx", "−Mx", "+My", "−My", "+N Nén",
                   "−N Kéo", "O"):
            assert _s in _texts, _texts
        assert len(ax.get_xticks()) == 0
        assert len(ax.get_yticks()) == 0
        assert len(ax.get_zticks()) == 0
        assert ax.get_xlabel() == "" and ax.get_zlabel() == ""
        # 2. Mặt wireframe xám (Line3DCollection), không còn mặt
        # đặc plot_surface (Poly3DCollection).
        from mpl_toolkits.mplot3d.art3d import Line3DCollection
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        assert any(isinstance(c, Line3DCollection)
                   for c in ax.collections)
        assert not any(isinstance(c, Poly3DCollection)
                       for c in ax.collections)
        # 3. Đường cong N–Mα xanh lá + tia đỏ đứt trên axes.
        _line_colors = [ln.get_color() for ln in ax.lines]
        assert _GREEN in _line_colors
        assert _RED in _line_colors
        # 4. Điểm A xanh lá / điểm B thoi cam, đúng tọa độ 2D
        # (chỉ thêm chiều): A = (Mx*, My*, N),
        # B = (Bx, By, BN).
        _, _, res_ns = wall_chart_inputs(full)
        _found_a = _found_b = False
        for _c in ax.collections:
            try:
                _fc = tuple(_c.get_facecolor()[0][:3])
            except Exception:
                continue
            try:
                _xs, _ys, _zs = _c._offsets3d
                _p = (float(_xs[0]), float(_ys[0]),
                      float(_zs[0]))
            except Exception:
                continue
            if _fc == _rgba(_GREEN)[:3]:
                assert _p == (float(res_ns.Mx_star),
                              float(res_ns.My_star),
                              float(res_ns.N)), _p
                _found_a = True
            elif _fc == _rgba(_ORANGE)[:3]:
                assert _p == (float(res_ns.Bx), float(res_ns.By),
                              float(res_ns.BN)), _p
                _found_b = True
        assert _found_a and _found_b
        # 5. Caption + legend đầy đủ.
        _fig = ax.figure
        assert any("Biểu đồ 3D N–Mx–My" in t.get_text()
                   for t in _fig.texts)
        _leg = ax.get_legend()
        assert _leg is not None
        _labels = [t.get_text() for t in _leg.get_texts()]
        for _s in ("Mặt tương tác 3D", "Đường cong N–Mα",
                   "Tia tải O–A–B", "Điểm tải A",
                   "Điểm giới hạn B"):
            assert _s in _labels, _labels
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
