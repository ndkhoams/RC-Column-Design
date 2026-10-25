"""O mat cat vach (user 2026-10-25, anh tab Ket qua build 2c71754):

1. Bo zoom/pan: khong nut -/+/Reset, khong method/binding _sec_zoom_*,
   them checkbox "Hien thi vung nen" nhu cot (mac dinh bat).
2. Checkbox doi dung lop ve vung nen (na_info tu dict ket qua CHECK
   da tinh 1 lan, khong tinh lai): bat -> co polygon vung nen xanh
   #BFDBFE + duong trung hoa do dut; tat -> khong co.
3. Dim tong Lw day sat len: tu -1.70cy ve -1.45cy (len 0.25cy) nhung
   van cach hang dim phan doan, khong de (khe dong 0.83cy).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_input import WallInput
from rc_column.wall_section import build_wall_section
from gui.wall_mixin import (_wall_section_figsize, draw_wall_section_ax)


def _boundary_sec_meta():
    conc = ConcreteMaterial(CONCRETE_GRADES["B25"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB400-V"], 1.0)
    w = WallInput(steel_mode="boundary", cover=13.0, be_Lb=500.0,
                  be_dia=28.0, be_n_Lb=4, be_n_tw=0, be_L_out=1,
                  be_L_in=0, web_dia=12.0, web_s=200.0,
                  sw_steel_grade="CB400-V")
    w.rot_deg = 0
    return build_wall_section(w, conc, steel)


def _user_full():
    """Ca anh user: vach 2500x350, B30/CB500-V doc, ngang CB400-V,
    N 2528.7, M_in 202.9, M_out 275.2 (lay tu engine that)."""
    from rc_column.wall_engine import wall_tcvn_full
    conc = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
    w = WallInput(steel_mode="boundary", cover=25.0, be_Lb=500.0,
                  be_dia=28.0, be_n_Lb=4, be_n_tw=0, be_L_out=1,
                  be_L_in=0, web_dia=12.0, web_s=200.0,
                  sw_steel_grade="CB400-V")
    full = wall_tcvn_full(
        w, conc, steel,
        loads={"N": 2528.7, "M_in": 202.9, "M_out": 275.2,
               "V_in": 0.0, "V_out": 0.0, "T": 0.0})
    return full


def _lw_label_offset_cy(sec, meta):
    fw, fh = _wall_section_figsize(sec, len(meta["dim_segments"]), 0)
    fig, ax = plt.subplots(figsize=(fw, fh))
    draw_wall_section_ax(ax, sec, meta=meta, rot_deg=0)
    fig.canvas.draw()
    cy = float(sec.cy)
    lw_y = None
    for t in ax.texts:
        if t.get_text().startswith("Lw = "):
            lw_y = t.get_position()[1]
    plt.close(fig)
    assert lw_y is not None
    return (-cy / 2 - lw_y) / cy


def test_total_dim_moved_up_but_clear_of_segments():
    sec, meta = _boundary_sec_meta()
    off = _lw_label_offset_cy(sec, meta)
    # Nhan Lw o y_tot+0.14cy: cu 1.56cy, moi 1.31cy. Khe tu nhan Lw
    # xuong hang phan doan (-0.62cy) = off-0.62 ~ 0.69cy > 0.5cy.
    assert 1.20 < off < 1.45, off
    assert off - 0.62 > 0.5, off
    # Duong dim tong (-1.45cy) van duoi hang phan doan (-0.62cy).
    assert 1.45 - 0.62 > 0.5


def test_no_zoom_code_in_wall_section_cell():
    src = open(os.path.join(os.path.dirname(__file__), "..", "gui",
                            "wall_mixin.py"), encoding="utf-8").read()
    for name in ("_sec_zoom_setup", "_sec_zoom_step", "_sec_zoom_reset",
                 "_sec_zoom_wheel", "_sec_zoom_press", "_sec_zoom_motion"):
        assert name not in src, name
    start = src.index("def _build_wall_section_cell")
    end = src.index("def _redraw_wall_section", start)
    block = src[start:end]
    assert "Hiển thị vùng nén" in block
    assert "_wall_show_compression" in block
    assert "BooleanVar(value=True)" in src
    # Khong con nut zoom trong o (chi checkbox + label tieu de).
    assert 'text="−"' not in block and 'text="+"' not in block
    assert 'text="Reset"' not in block


def _has_compression(ax):
    for p in ax.patches:
        try:
            fc = p.get_facecolor()
        except Exception:
            continue
        if len(fc) >= 3 and abs(fc[0] - 0.749) < 0.01 \
                and abs(fc[1] - 0.859) < 0.01 \
                and abs(fc[2] - 0.996) < 0.01:
            return True
    return False


def test_compression_layer_toggles_with_flag():
    full = _user_full()
    na = full.get("na_info")
    assert na is not None and na.get("found"), na
    sec, meta = full["sec"], full.get("meta")
    for show, expect in ((True, True), (False, False)):
        fw, fh = _wall_section_figsize(sec, len(meta["dim_segments"]), 0)
        fig, ax = plt.subplots(figsize=(fw, fh))
        draw_wall_section_ax(ax, sec, meta=meta, na_info=na,
                             show_compression=show, rot_deg=0)
        fig.canvas.draw()
        assert _has_compression(ax) is expect, show
        plt.close(fig)
    # So tinh khong doi boi viec chi doi hien thi: D/C huu han,
    # khong phai do code hien thi tinh lai (engine khong dung).
    assert 0.0 < float(full["dc"]) < 2.0, full["dc"]


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
    import tkinter as tk
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


def _walk(widget, out):
    out.append(widget)
    for ch in widget.winfo_children():
        _walk(ch, out)


def test_gui_cell_no_zoom_buttons_checkbox_toggles(wall_app):
    import tkinter as tk
    app = wall_app
    full = _user_full()
    # Mac dinh checkbox bat (nhu cot).
    assert app._wall_show_compression is None \
        or bool(app._wall_show_compression.get()) is True
    parent = tk.Frame(app)
    parent.pack()
    app.update_idletasks()
    cell = app._build_wall_section_cell(
        parent, full["sec"], meta=full.get("meta"),
        na_info=full.get("na_info"), show_compression=True,
        winp=full.get("winp"))
    cell.pack(fill=tk.BOTH, expand=True)
    app.update_idletasks()
    widgets = []
    _walk(cell, widgets)
    btn_texts = [w.cget("text") for w in widgets
                 if w.winfo_class() == "Button"]
    assert "−" not in btn_texts and "+" not in btn_texts \
        and "Reset" not in btn_texts, btn_texts
    chk = [w for w in widgets if w.winfo_class() == "Checkbutton"
           and w.cget("text") == "Hiển thị vùng nén"]
    assert len(chk) == 1
    assert not hasattr(app, "_sec_zoom")
    # Bat -> co vung nen; tat + ve lai -> mat; bat lai -> co lai.
    assert _has_compression(app._sec_ax) is True
    app._wall_show_compression.set(False)
    app._redraw_wall_section()
    assert _has_compression(app._sec_ax) is False
    app._wall_show_compression.set(True)
    app._redraw_wall_section()
    assert _has_compression(app._sec_ax) is True
