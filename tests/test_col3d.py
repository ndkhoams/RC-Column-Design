"""View 3D cột theo style ảnh mẫu "Biểu đồ 3D N–Mx–My" của vách
(quyết user 2026-10-30).

- Helper `gui/col3d_view.py::draw_col3d_interaction` vẽ đúng style
  chuẩn (b7b9c31): 3 trục qua gốc O (pane/tick ẩn), nhãn 2 đầu mỗi
  trục +M2/−M2, +M3/−M3, +N Nén/−N Kéo + "O" (#4B5563, ngoài biên
  mặt 10%, dấu − là U+2212); mặt wireframe xám nhạt #9CA3AF
  alpha 0.5 rstride=2/cstride=3 (không còn mặt đặc plot_surface);
  đường cong N–Mα xanh lá #059669 tại góc tải; điểm A chấm xanh lá,
  điểm B thoi cam #F97316; tia đứt đỏ #DC2626 O–A–B kéo dài qua B
  ×1.18 (như 2D); legend 5 mục 2 hàng; caption "Biểu đồ 3D N–M2–M3".
- Khung cột: x = M2, y = M3, z = N (nhất quán với 2D của cột:
  hoành M3, tung M2). α = atan2(M2*, M3*) suy từ mô men thiết kế —
  KHÔNG hardcode đảo khung. Ánh xạ (Mα, N) → 3D:
  (M·sinθ, M·cosθ, N) — cùng frame mà surface_grid của cả 3 chuẩn
  dùng (x = M2 = M·sinθ, y = M3 = M·cosθ).
- KHÔNG tính lại solver: A/B lấy từ dict kết quả đã lưu — A/B 3D
  khớp số 2D từng chữ số; D/C không đổi.
- View 3D của vách giữ nguyên b7b9c31 (không chạm).
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import matplotlib

matplotlib.use("Agg")

from rc_column.checker import ColumnInput, build_section, check_column
from rc_column.interaction import BiaxialCapacity
from rc_column.aci_checker import (ACICapacity, check_column_aci,
                                   moment_magnification)
from rc_column.aci_materials import ACIConcrete, ACISteel
from rc_column.ec2_checker import EC2Capacity, check_column_ec2
from rc_column.ec2_materials import EC2Concrete, EC2Steel
from rc_column.ec2_chart_draw import ec2_signed_design_moments

_GREEN = "#059669"
_ORANGE = "#F97316"
_RED = "#DC2626"

_BASE = dict(concrete_grade="B25", gamma_b=0.85, steel_grade="CB400-V",
             cx=400.0, cy=400.0, cover=22.0,
             corner_dia=20.0,
             edge_t2_count=3, edge_t2_dia=20.0,
             edge_t3_count=3, edge_t3_dia=20.0, Lx=4.0, Ly=4.0,
             top_x="ngam_cung", bottom_x="ngam_cung",
             top_y="ngam_cung", bottom_y="ngam_cung",
             psi_x=0.5, psi_y=0.5)


def _rgba(hexcolor):
    from matplotlib.colors import to_rgba
    return to_rgba(hexcolor)


# ------------------------------------------------------------------
# 1. Khung lưới surface_grid của cả 3 chuẩn: x = M2, y = M3
# ------------------------------------------------------------------
def test_col3d_surface_frame_tcvn():
    inp = ColumnInput(**_BASE, N=1500.0, Mx=80.0, My=60.0)
    sec = build_section(inp)
    cap = BiaxialCapacity(sec, model=inp.concrete_model, n_angles=24)
    n_vals, th_vals, m2g, m3g = cap.surface_grid(n_n=25, n_angles=36)
    assert m2g.shape == (25, 36) and m3g.shape == (25, 36)
    assert float(n_vals[0]) < 0 < float(n_vals[-1])
    # θ = 90° → j = 9: x = M·sin90° = M, y = M·cos90° ≈ 0.
    i = 12
    m90 = cap.moment_capacity(float(n_vals[i]), 90.0)
    assert abs(float(m2g[i, 9]) - m90) < 1e-6
    assert abs(float(m3g[i, 9])) < 1e-6
    # θ = 0° → j = 0: x ≈ 0, y = M.
    m0 = cap.moment_capacity(float(n_vals[i]), 0.0)
    assert abs(float(m2g[i, 0])) < 1e-6
    assert abs(float(m3g[i, 0]) - m0) < 1e-6


def test_col3d_surface_frame_aci_ec2():
    inp = ColumnInput(**_BASE, N=1500.0, Mx=80.0, My=60.0)
    sec = build_section(inp)
    for cap in (ACICapacity(sec, ACIConcrete(fc=30.0), ACISteel(fy=420.0),
                            tied=True, n_angles=24),
                EC2Capacity(sec, EC2Concrete(30.0), EC2Steel(500.0),
                            n_angles=24)):
        n_vals, th_vals, m2g, m3g = cap.surface_grid(n_n=25,
                                                    n_angles=36)
        assert m2g.shape == (25, 36)
        i = 12
        m90 = cap.moment_capacity(float(n_vals[i]), 90.0)
        assert abs(float(m2g[i, 9]) - m90) < 1e-6
        assert abs(float(m3g[i, 9])) < 1e-6


# ------------------------------------------------------------------
# 2. Render thật dưới Xvfb cho cả 3 chuẩn
# ------------------------------------------------------------------
try:
    import tkinter as tk
    _r = tk.Tk()
    _r.withdraw()
    _r.destroy()
    _HAS_DISPLAY = True
except Exception:
    _HAS_DISPLAY = False

pytestmark_gui = pytest.mark.skipif(
    not _HAS_DISPLAY, reason="không có display Tk")

_COL_JSON = {
    "member_name": "C1",
    "member_type": "column",
    "concrete": "B30",
    "steel": "CB500-V",
    "kind": "Chữ nhật",
    "cx": "400",
    "cy": "400",
    "cover": "28",
    "corner_dia": "25",
    "e2n": "2",
    "e2d": "20",
    "e3n": "2",
    "e3d": "20",
    "load_mode": "manual",
    "N": "2000",
    "Mx": "100",
    "My": "80",
    "Q2": "50",
    "Q3": "30",
}


def _mkapp(code, tmp_path):
    from unittest import mock
    from gui.app import App
    app = App()
    app.update_idletasks()
    d = dict(_COL_JSON, code=code)
    p = str(tmp_path / "c.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f)
    with mock.patch("tkinter.filedialog.askopenfilename",
                    return_value=p):
        app.on_load_data()
    app.update_idletasks()
    app.on_check()
    app.update_idletasks()
    return app


def _cap_for(app, std):
    """Capacity class đúng chuẩn từ object đã lưu (không tính lại)."""
    if std == "TCVN":
        return BiaxialCapacity(app._last_sec,
                               model=app._last_inp.concrete_model,
                               n_angles=24)
    if std == "ACI":
        return ACICapacity(app._aci_sec, app._aci_conc, app._aci_steel,
                           tied=app._aci_tied, n_angles=24)
    return EC2Capacity(app._ec2_sec, app._ec2_conc, app._ec2_steel,
                       n_angles=24)


def _expected_ab(app, std):
    """A/B đúng số 2D từng chữ số cho từng chuẩn."""
    if std == "TCVN":
        res = app._last_res
        A = (float(res.Mx_star), float(res.My_star), float(res.N))
        B = (float(res.Bx), float(res.By), float(res.BN))
        dc = float(res.dc)
    elif std == "ACI":
        inp = app._aci_inp
        mm = getattr(app, "_aci_mm", None) or {}
        m2 = float(mm.get("Mc2", inp.Mx))
        m3 = float(mm.get("Mc3", inp.My))
        A = (m2, m3, float(inp.N))
        r = app._aci_res
        B = (float(r.get("Bx", 0) or 0), float(r.get("By", 0) or 0),
             float(r.get("BN", 0) or 0))
        dc = float(r["dc"])
    else:
        inp = app._ec2_inp
        r = app._ec2_res
        m2, m3 = ec2_signed_design_moments(r, inp)
        A = (float(m2), float(m3), float(inp.N))
        B = (float(r.get("Bx", 0) or 0), float(r.get("By", 0) or 0),
             float(r.get("BN", 0) or 0))
        dc = float(r["dc"])
    return A, B, dc


@pytest.mark.skipif(not _HAS_DISPLAY, reason="không có display Tk")
@pytest.mark.parametrize(
    "std,code,handler,figattr,takes_sel,restore_ax",
    [("TCVN", "TCVN 5574:2018", "_on_nm_angle_changed", "_nm_fig",
       False, "_nm_fig"),
     ("ACI", "ACI 318-19", "_on_aci_angle_unified", "_aci_nm_fig",
       True, "_nm_ax"),
     ("EC2", "EC2 (EN 1992-1-1:2004)", "_on_ec2_angle_unified",
       "_ec2_nm_fig", True, "_nm_ax")])
def test_col3d_style_and_render(std, code, handler, figattr, takes_sel,
                                restore_ax, tmp_path):
    from mpl_toolkits.mplot3d.art3d import (Line3DCollection,
                                            Poly3DCollection)
    app = _mkapp(code, tmp_path)

    def _select(sel):
        # Cùng đường gọi như user chọn trong dropdown "Góc xem:":
        # TCVN: _redraw_old (_nm_angle_cb + _on_nm_angle_changed);
        # ACI/EC2: unified renderer (app._nm_angle_cb +
        # _on_aci/ec2_angle_unified(sel)).
        combo = getattr(app, "_nm_angle_cb")
        assert "3D" in list(combo["values"])
        combo.set(sel)
        fn = getattr(app, handler)
        if takes_sel:
            fn(sel)
        else:
            fn()

    try:
        A, B, dc0 = _expected_ab(app, std)
        _select("3D")
        app.update_idletasks()
        ax = getattr(app, figattr).axes[0]
        assert getattr(ax, "name", "") == "3d"
        # 1. Nhãn 2 đầu mỗi trục + "O" (pane/tick mặc định ẩn).
        _texts = [t.get_text() for t in ax.texts]
        for _s in ("+M2", "−M2", "+M3", "−M3", "+N Nén",
                   "−N Kéo", "O"):
            assert _s in _texts, (std, _texts)
        assert len(ax.get_xticks()) == 0
        assert len(ax.get_yticks()) == 0
        assert len(ax.get_zticks()) == 0
        assert ax.get_xlabel() == "" and ax.get_ylabel() == ""
        assert ax.get_zlabel() == ""
        # 2. Mặt wireframe xám (Line3DCollection), không còn mặt
        # đặc plot_surface (Poly3DCollection).
        assert any(isinstance(c, Line3DCollection)
                   for c in ax.collections)
        assert not any(isinstance(c, Poly3DCollection)
                       for c in ax.collections)
        # 3. Đường cong N–Mα xanh lá + tia đỏ đứt trên axes.
        _line_colors = [ln.get_color() for ln in ax.lines]
        assert _GREEN in _line_colors, (std, _line_colors)
        assert _RED in _line_colors, (std, _line_colors)
        # 4. Điểm A xanh lá / điểm B thoi cam, đúng tọa độ 2D
        # từng chữ số (chỉ thêm chiều N).
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
                assert _p == A, (std, _p, A)
                _found_a = True
            elif _fc == _rgba(_ORANGE)[:3]:
                assert _p == B, (std, _p, B)
                _found_b = True
        assert _found_a and _found_b, std
        # Đường cong α đi qua đúng B: (i) hàm moment_capacity tại
        # BN cho đúng độ lớn |B| — B nằm trên tia D/C nên đây là
        # đẳng thức của solver (moment_capacity(BN, θ) = |B|);
        # (ii) polyline vẽ (64 mẫu N) đi gần B trong dung sai lấy
        # mẫu (B có thể rơi giữa 2 mẫu N).
        _theta = math.degrees(math.atan2(A[0], A[1])) \
            if abs(A[0]) + abs(A[1]) > 1e-9 else 0.0
        _cap = _cap_for(app, std)
        _Mb_drawn = _cap.moment_capacity(float(B[2]), _theta)
        _Mb = math.hypot(B[0], B[1])
        assert abs(_Mb_drawn - _Mb) / max(_Mb, 1e-9) < 0.005, \
            (std, _Mb_drawn, _Mb)
        _curve = next(ln for ln in ax.lines
                      if ln.get_color() == _GREEN)
        _cx, _cy, _cz = _curve.get_data_3d()
        _dmin = min(math.hypot(x - B[0], y - B[1], z - B[2])
                    for x, y, z in zip(_cx, _cy, _cz))
        assert _dmin / max(math.hypot(*B), 1e-9) < 0.02, (std, _dmin)
        # 5. Caption + legend đầy đủ.
        _fig = ax.figure
        assert any("Biểu đồ 3D N–M2–M3" in t.get_text()
                   for t in _fig.texts), std
        assert not any("Mx" in t.get_text() or "My" in t.get_text()
                       for t in _fig.texts), std
        _leg = ax.get_legend()
        assert _leg is not None, std
        _labels = [t.get_text() for t in _leg.get_texts()]
        for _s in ("Mặt tương tác 3D", "Đường cong N–Mα",
                   "Tia tải O–A–B", "Điểm tải A",
                   "Điểm giới hạn B"):
            assert _s in _labels, (std, _labels)
        # 6. Quay lại góc tải -> axes 2D, D/C không đổi.
        # (ACI/EC2: _restore_2d_* tạo figure 2D mới và lưu vào
        # app._nm_ax — app._aci/ec2_nm_fig vẫn trỏ figure 3D cũ.)
        _select("α (góc tải)")
        app.update_idletasks()
        if restore_ax == "_nm_ax":
            ax2 = getattr(app, "_nm_ax")
        else:
            ax2 = getattr(app, restore_ax).axes[0]
        assert getattr(ax2, "name", "") != "3d", std
        _, _, dc1 = _expected_ab(app, std)
        assert dc1 == dc0, (std, dc0, dc1)
    finally:
        try:
            app.destroy()
        except Exception:
            pass


@pytest.mark.skipif(not _HAS_DISPLAY, reason="không có display Tk")
def test_col3d_dc_regression(tmp_path):
    """D/C từng chuẩn không đổi qua thao tác chọn 3D/quay lại 2D."""
    for std, code in (("TCVN", "TCVN 5574:2018"),
                      ("ACI", "ACI 318-19"),
                      ("EC2", "EC2 (EN 1992-1-1:2004)")):
        app = _mkapp(code, tmp_path)
        try:
            A, B, dc0 = _expected_ab(app, std)
            assert math.isfinite(dc0) and dc0 > 0, (std, dc0)
        finally:
            try:
                app.destroy()
            except Exception:
                pass
