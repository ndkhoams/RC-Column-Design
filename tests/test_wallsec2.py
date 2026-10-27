"""Lat 1 (2026-10-27): 5 tiet dien vach con lai o muc mat cat + thep
+ preview (chua N-M/cat/PDF).

- Hinh hoc: Ac polygon khop Ac web Vietcons trong 0,001 m2 (cac
  quan he suy tu Ac web, ghi ro trong wall_section.py — khong phai
  dinh nghia chu cua web).
- Thep (d12 s200, c 25, dia_h 12): lat 1 chu vi don lech web o
  T/L/C/U; tu lat 3 (2026-10-27, xem test_wallsec3.py) ap o nut
  giao nen so thanh/As trong bang duoi day DA BANG web — test nay
  khoa so moi, khong giu so lech lat 1.
- JSON round-trip + file cu (thieu khoa moi) mo duoc mac dinh
  phang; draw polygon o 4 goc xoay khong loi, dim tong dung nhan.
- Panel (can display, chay duoi Xvfb): o nhap dong theo loai,
  mac dinh web lan dau, chuyen qua lai giu gia tri user.
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
from rc_column.wall_input import (WallInput, wall_from_dict,
                                  wall_to_dict)
from rc_column.wall_section import (_point_in_poly, build_wall_section,
                                    wall_readouts)
from gui.wall_mixin import (_wall_section_figsize, draw_wall_section_ax)

# (loai, kwargs mac dinh web, Ac web m2, so thanh web, As web,
#  so thanh app, As app) — As app = so thanh x 113,097 (d12).
# Tu lat 3: so app = so web ca 5 loai (o nut giao, xem
# test_wallsec3.py); Barbell khong o nen giu nguyen.
_CASES = [
    ("barbell", dict(Lw=3000, tw=300, sec_bf=1000, sec_tf=450),
     1.530, 48, 5429, 48, 5429),
    ("tee", dict(Lw=2500, sec_bf=1500, sec_t=300),
     1.110, 45, 5089, 45, 5089),
    ("ell", dict(sec_L1=2000, sec_L2=1800, sec_t=300),
     1.050, 44, 4976, 44, 4976),
    ("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600, sec_t=300),
     1.800, 82, 9274, 82, 9274),
    ("u-core", dict(Lw=3000, sec_bf=1500, sec_t=300),
     1.620, 66, 7464, 66, 7464),
]


def _mat():
    conc = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
    return conc, steel


def _mk(st, kw, sym=True):
    w = WallInput(section_type=st, cover=25, dia_h=12,
                  per_dia=12, per_s=200, sec_sym=sym)
    for k, v in kw.items():
        setattr(w, k, v)
    return w


@pytest.mark.parametrize("st,kw,ac_web,n_web,as_web,n_app,as_app",
                         _CASES)
def test_poly_ac_matches_web(st, kw, ac_web, n_web, as_web,
                             n_app, as_app):
    conc, steel = _mat()
    sec, meta = build_wall_section(_mk(st, kw), conc, steel)
    assert sec.kind == "poly"
    r = wall_readouts(_mk(st, kw), sec, meta)
    assert abs(r["Ac_m2"] - ac_web) < 0.001, (st, r["Ac_m2"], ac_web)
    assert abs(sec.gross_area / 1e6 - ac_web) < 0.001
    assert abs(sec.concrete_area / 1e6 - ac_web) < 0.001


@pytest.mark.parametrize("st,kw,ac_web,n_web,as_web,n_app,as_app",
                         _CASES)
def test_perimeter_bars_vs_web(st, kw, ac_web, n_web, as_web,
                               n_app, as_app):
    """So thanh/As: tu lat 3 ca 5 loai bang web (o nut giao);
    khong ep spacing — so ra tu dung quy tac chu vi chia doan +
    o nut giao (xem test_wallsec3.py)."""
    conc, steel = _mat()
    sec, meta = build_wall_section(_mk(st, kw), conc, steel)
    assert len(sec.rebars) == n_app, (st, len(sec.rebars), n_app)
    assert abs(sec.steel_area - as_app) < 1.0, (st, sec.steel_area)
    assert n_app == n_web and abs(as_app - as_web) < 1.0
    # Mọi thanh nằm trong polygon (trên đa giác lùi vào trong).
    verts = sec.poly_verts[0]
    for rb in sec.rebars:
        assert _point_in_poly(rb.x, rb.y, verts), (st, rb.x, rb.y)


def test_poly_asym_barbell_and_c():
    conc, steel = _mat()
    w = _mk("barbell", dict(Lw=3000, tw=300, sec_bf=1000,
                            sec_tf=450, sec_bf2=800, sec_tf2=400),
            sym=False)
    sec, meta = build_wall_section(w, conc, steel)
    # Ac = 2150*300 + 450*1000 + 400*800 = 1.415.000 mm2.
    assert abs(sec.gross_area - 1_415_000) < 1.0
    w = _mk("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600,
                           sec_bf2=1200, sec_lr2=500, sec_t=300),
            sym=False)
    sec, meta = build_wall_section(w, conc, steel)
    # 900k + (1200*300) + (900*300) + (300*300) + (200*300) = 1.680k.
    assert abs(sec.gross_area - 1_680_000) < 1.0


def test_json_roundtrip_and_old_file():
    w = _mk("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600,
                           sec_t=300))
    w2 = wall_from_dict(wall_to_dict(w))
    assert w2.section_type == "c-core"
    assert w2.sec_bf == 1500 and w2.sec_lr == 600
    assert w2.sec_t == 300 and w2.sec_sym is True
    # File cu thieu khoa moi -> mac dinh phang, khong vo.
    old = {"Lw": 2500, "tw": 350, "cover": 25}
    w3 = wall_from_dict(old)
    assert w3.section_type == "rect"
    assert w3.sec_bf == 1000 and w3.sec_t == 300


@pytest.mark.parametrize("st,kw,ac_web,n_web,as_web,n_app,as_app",
                         _CASES)
@pytest.mark.parametrize("rot", [0, 90, 180, 270])
def test_poly_draw_all_rotations(st, kw, ac_web, n_web, as_web,
                                 n_app, as_app, rot):
    conc, steel = _mat()
    w = _mk(st, kw)
    w.rot_deg = rot
    sec, meta = build_wall_section(w, conc, steel)
    fw, fh = _wall_section_figsize(sec, len(meta["dim_segments"]), rot)
    fig, ax = plt.subplots(figsize=(fw, fh))
    draw_wall_section_ax(ax, sec, meta=meta, rot_deg=rot)
    fig.canvas.draw()
    labels = [t.get_text() for t in ax.texts]
    assert meta["dim_total_x_label"] in labels, (st, rot, labels)
    assert meta["dim_total_y_label"] in labels, (st, rot, labels)
    # Outline polygon co mat (patch lon nhat = mat cat).
    assert len(ax.patches) >= 1
    plt.close(fig)


def test_rect_unchanged():
    conc, steel = _mat()
    sec, meta = build_wall_section(WallInput(), conc, steel)
    assert sec.kind == "rect" and sec.cx == 2500.0 and sec.cy == 350.0
    assert len(sec.rebars) == 30


# ---------------- Panel (can display) ----------------

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


def _mapped(w):
    try:
        return bool(w.winfo_ismapped())
    except Exception:
        return False


def test_panel_fields_by_type(wall_app):
    from gui.wall_mixin import _SECTYPES
    app = wall_app
    # Vach phang: chi hang chinh Lw/tw, khong hang phu, co dropdown.
    assert app._wall_sec_code() == "rect"
    assert _mapped(app.w_en_Lw) and _mapped(app.w_en_tw)
    assert not _mapped(app.w_en_sec_bf)
    assert _mapped(app.w_cb_steel_mode)
    # Barbell lan dau: mac dinh web + tieu de phu + doi xung.
    app.w_cb_sectype.set(_SECTYPES[1])
    app._on_wall_sectype()
    app.update_idletasks()
    assert app.w_en_Lw.get() == "3000" and app.w_en_tw.get() == "300"
    assert app.w_en_sec_bf.get() == "1000"
    assert app.w_en_sec_tf.get() == "450"
    assert app.w_lbl_sec_sub.cget("text") == "KÍCH THƯỚC HAI ĐẦU"
    assert _mapped(app.w_chk_sec_sym)
    assert _mapped(app.w_cb_steel_mode)  # Barbell giu dropdown
    # Tat doi xung -> hien Bf2/Tf2.
    app.w_var_sec_sym.set(False)
    app._update_wall_sectype_fields()
    app.update_idletasks()
    assert _mapped(app.w_en_sec_bf2) and _mapped(app.w_en_sec_tf2)
    # Tee: an dropdown, an Bf2/Tf2, hien Bf; chuyen qua lai giu
    # gia tri Barbell da sua.
    app.w_en_sec_bf.delete(0, "end")
    app.w_en_sec_bf.insert(0, "1200")
    app.w_cb_sectype.set(_SECTYPES[2])
    app._on_wall_sectype()
    app.update_idletasks()
    assert not _mapped(app.w_cb_steel_mode)
    assert app._collect_wall()["steel_mode"] == "perimeter"
    assert app._collect_wall()["section_type"] == "tee"
    app.w_cb_sectype.set(_SECTYPES[1])
    app._on_wall_sectype()
    app.update_idletasks()
    assert app.w_en_sec_bf.get() == "1200"
    # C: tieu de phu HAI DAU + hang Lr; U: HAI CANH.
    app.w_cb_sectype.set(_SECTYPES[4])
    app._on_wall_sectype()
    app.update_idletasks()
    assert app.w_lbl_sec_sub.cget("text") == "KÍCH THƯỚC HAI ĐẦU"
    assert _mapped(app.w_en_sec_lr)
    app.w_cb_sectype.set(_SECTYPES[5])
    app._on_wall_sectype()
    app.update_idletasks()
    assert app.w_lbl_sec_sub.cget("text") == "KÍCH THƯỚC HAI CÁNH"
    # Ell: L1/L2 + t don.
    app.w_cb_sectype.set(_SECTYPES[3])
    app._on_wall_sectype()
    app.update_idletasks()
    assert app.w_en_sec_L1.get() == "2000"
    assert app.w_en_sec_L2.get() == "1800"
    assert _mapped(app.w_en_sec_t)
