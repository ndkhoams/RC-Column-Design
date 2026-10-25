"""Bo xoay tiet dien cho vach phang (user chot 2026-10-25).

Ly do: ETABS xuat mac dinh truc 2 trung chieu Lw nen vach phang
khong can xoay. Vach phang (loai duy nhat GD1): an hang xoay, ep
rotation = 0 o input builder (_collect_wall) va khi load file cu
(ke ca file luu rot 90). Ghi chu GD1 duoi muc 2 da bo 2026-10-25
nen khong con widget ghi chu nao. Machinery xoay (engine, ham
_rotate_wall, ve rot_deg) giu nguyen cho cac loai vach giai doan sau.
Test GUI skip khi khong co display; test engine chay moi moi truong.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


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


def test_flat_wall_hides_rotation_row(wall_app):
    app = wall_app
    assert app.w_cb_sectype.get() == "Vách phẳng chữ nhật"
    # Panel that su hien (tranh pass vacuo do frame an).
    assert app.w_en_Lw.winfo_ismapped()
    assert not app._lbl_wall_rot.winfo_ismapped()
    assert not app.w_rot_fr.winfo_ismapped()
    # Ghi chu GD1 duoi muc 2 da bo 2026-10-25: khong con widget nay.
    assert not hasattr(app, "_lbl_wall_rot_note")
    assert app._wall_rot_deg == 0
    assert app.w_rot_var.get() == "0°"


def test_collect_forces_rot_0_for_flat(wall_app):
    app = wall_app
    app._wall_rot_deg = 90  # gia trang thai cu con sot
    app.w_rot_var.set("90°")
    assert app._collect_wall()["rot_deg"] == 0


def test_apply_old_rot90_returns_0(wall_app):
    app = wall_app
    d = dict(app._collect_wall())
    d["rot_deg"] = 90  # file cu vach phang luu 90 do
    app._apply_wall(d)
    app.update_idletasks()
    assert app._wall_rot_deg == 0
    assert app.w_rot_var.get() == "0°"
    assert not app._lbl_wall_rot.winfo_ismapped()


def test_engine_rotation_machinery_intact():
    """Engine van hoan doi Lw/tw o rot 90 (khong dung engine)."""
    from rc_column.wall_input import WallInput
    from rc_column.wall_shear import wall_shear_geometry
    w90 = WallInput()
    w90.rot_deg = 90
    assert wall_shear_geometry(w90)["b"] == 2500.0
    w0 = WallInput()
    assert wall_shear_geometry(w0)["b"] == 350.0
