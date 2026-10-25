"""Panel vach: bo ghi chu GD1 muc 2 + hang L0 muc 4 + text GD1 o
tieu de Bo sung + dropdown P-delta thanh tick (user chot 2026-10-25).

- Chi doi hien thi panel: gia tri mac dinh, khoa JSON, engine va
  tab Ket qua/Chi tiet/PDF khong doi.
- L0 van do engine suy ra tu L/psi luc tinh (wall_engine:
  l0_in = psi_x * Lx_m, l0_out = psi_y * Ly_m), khong doc tu
  widget hien thi nao.
- Tick P-delta map dung 2 gia tri cu: tick = "tcvn", khong tick =
  "none" (WallInput.pd_method); file cu mo len tick dung trang thai.

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


def _all_texts(widget, out):
    try:
        t = widget.cget("text")
        if isinstance(t, str):
            out.append(t)
    except Exception:
        pass
    for ch in widget.winfo_children():
        _all_texts(ch, out)
    return out


def test_gd1_note_widget_removed(wall_app):
    app = wall_app
    assert not hasattr(app, "_lbl_wall_rot_note")
    texts = _all_texts(app.frm_wall, [])
    assert not any("GĐ1 chỉ hỗ trợ" in t for t in texts)
    # Hang xoay van an o vach phang, loai tiet dien khong doi.
    assert not app._lbl_wall_rot.winfo_ismapped()
    assert app.w_cb_sectype.get() == "Vách phẳng chữ nhật"


def test_l0_display_row_removed_but_engine_still_derives(wall_app):
    app = wall_app
    assert not hasattr(app, "w_L0_var_x")
    assert not hasattr(app, "w_L0_var_y")
    texts = _all_texts(app.frm_wall_len, [])
    assert not any("Chiều cao tính toán" in t for t in texts)
    # Cac o nhap L/psi con nguyen, _collect_wall van doc dung chung.
    d = app._collect_wall()
    assert d["Lx_m"] and d["psi_x"] and d["Ly_m"] and d["psi_y"]
    from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                     ConcreteMaterial, SteelMaterial)
    from rc_column.wall_engine import wall_tcvn_full
    from rc_column.wall_input import wall_from_dict
    conc = ConcreteMaterial(CONCRETE_GRADES["B25"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB400-V"], 1.0)
    full = wall_tcvn_full(
        wall_from_dict(d), conc, steel,
        loads={"N": 2500.0, "M_in": 3000.0, "M_out": 60.0,
               "V_in": 800.0, "V_out": 0.0, "T": 0.0})
    sl = full["slend"]
    assert abs(sl["l0_in"] - d["psi_x"] * d["Lx_m"] * 1000.0) < 1e-6
    assert abs(sl["l0_out"] - d["psi_y"] * d["Ly_m"] * 1000.0) < 1e-6


def test_extra_frame_title_has_no_gd1(wall_app):
    app = wall_app
    title = app.frm_wall_extra.cget("text")
    assert "GĐ1" not in title
    assert title == "Thép ngang, đai vùng biên, kháng chấn"


def test_pd_tick_maps_to_both_old_values(wall_app):
    app = wall_app
    # Mac dinh: tick vao (khop mac dinh cu la Xet).
    assert app.w_var_pd.get() is True
    assert app._collect_wall()["pd_method"] == "tcvn"
    assert app.w_chk_pd.cget("text") == "Xét uốn dọc theo TCVN 5574:2018"
    assert not hasattr(app, "w_cb_pd")
    # Khong tick -> "none", tick lai -> "tcvn".
    app.w_var_pd.set(False)
    assert app._collect_wall()["pd_method"] == "none"
    app.w_var_pd.set(True)
    assert app._collect_wall()["pd_method"] == "tcvn"


def test_pd_tick_loads_old_files_correctly(wall_app):
    app = wall_app
    d = dict(app._collect_wall())
    d["pd_method"] = "none"
    app._apply_wall(d)
    assert app.w_var_pd.get() is False
    assert app._collect_wall()["pd_method"] == "none"
    d["pd_method"] = "tcvn"
    app._apply_wall(d)
    assert app.w_var_pd.get() is True
    assert app._collect_wall()["pd_method"] == "tcvn"


def test_pd_tick_both_states_keep_engine_semantics():
    """Tick off phai cho eta = 1 hai phuong (pd_method='none'),
    tick on giu dung cong thuc eta theo lambda (khong phai luc nao
    cung 1) — kiem o muc engine thuan, khong phu thuoc GUI."""
    from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                     ConcreteMaterial, SteelMaterial)
    from rc_column.wall_engine import wall_tcvn_full
    from rc_column.wall_input import WallInput
    conc = ConcreteMaterial(CONCRETE_GRADES["B25"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB400-V"], 1.0)
    loads = {"N": 2500.0, "M_in": 3000.0, "M_out": 60.0,
             "V_in": 800.0, "V_out": 0.0, "T": 0.0}
    kw = dict(Lw=2500.0, tw=350.0, cover=13.0, dia_h=12.0, s_h=200.0,
              layers_h=2, sw_steel_grade="CB400-V",
              steel_mode="boundary", be_Lb=500.0, be_dia=28.0,
              be_n_Lb=4, be_n_tw=0, be_L_out=1, be_L_in=0,
              web_dia=12.0, web_s=200.0,
              # L dai de lambda ngoai mat phang > 14 (cong eta),
              # trong khi lambda trong mat phang van < 14 (eta = 1):
              # dung de kiem chung cong theo tung phuong.
              Lx_m=5.75, Ly_m=5.75, psi_x=1.0, psi_y=1.0)
    off = wall_tcvn_full(WallInput(pd_method="none", **kw),
                         conc, steel, loads=dict(loads))
    assert off["slend"]["pd_method"] == "none"
    assert off["slend"]["factor_in"] == 1.0
    assert off["slend"]["factor_out"] == 1.0
    on = wall_tcvn_full(WallInput(pd_method="tcvn", **kw),
                        conc, steel, loads=dict(loads))
    assert on["slend"]["pd_method"] == "tcvn"
    assert on["slend"]["factor_in"] == 1.0  # lambda_in < 14 -> eta = 1
    assert on["slend"]["factor_out"] > 1.0  # lambda_out > 14 -> eta > 1
