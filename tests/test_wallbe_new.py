"""Panel vung bien 6 o moi + generator moi + migration (2026-10-25).

User chot: 6 o nhap (Lb, db chung, so thanh Lb/tw tinh ca 2 goc,
lop tw ngoai tinh MOI MAT, lop tw trong la tong o giua); nhap 1 ben
ap y het 2 dau; R = 2*L_out + L_in hang doc Lb + moi dau ngan
(n_tw - 2) thanh moi, dedupe trung < 1 mm.
Migration file cu: n_Lb = nL, n_tw = 2, L_out = 1, L_in = nT - 2
(thep cu khong doi).
"""
import math

import pytest

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_input import WallInput, wall_from_dict
from rc_column.wall_section import build_wall_section

CONC = ConcreteMaterial(CONCRETE_GRADES["B25"], 0.85)
STEEL = SteelMaterial(STEEL_GRADES["CB400-V"], 1.0)


def _winp(**kw):
    base = dict(Lw=2500.0, tw=350.0, cover=13.0, dia_h=12.0,
                steel_mode="boundary", be_Lb=500.0, be_dia=28.0,
                web_dia=12.0, web_s=200.0)
    base.update(kw)
    return WallInput(**base)


def _bars(w):
    _sec, meta = build_wall_section(w, CONC, STEEL)
    return meta["bars_be_left"], meta["bars_be_right"]


def _old_dict(nT):
    return dict(Lw=2500.0, tw=350.0, cover=13.0, dia_h=12.0,
                steel_mode="boundary", be_layout="grid", be_Lb=500.0,
                be_dia=28.0, be_nL=4, be_nT=nT, web_dia=12.0,
                web_s=200.0)


@pytest.mark.parametrize("nT", [2, 3, 4])
def test_migration_old_dict_keeps_old_bars(nT):
    """File cu (be_nL/be_nT/be_layout) -> dung luoi cu, khong doi thep."""
    w = wall_from_dict(_old_dict(nT))
    assert (w.be_n_Lb, w.be_n_tw, w.be_L_out, w.be_L_in) == (
        4, 2, 1, nT - 2)
    bl, br = _bars(w)
    assert len(bl) == len(br) == 4 * nT
    # Cung luoi voi WallInput khoa moi tuong duong (tung toa do).
    bl2, br2 = _bars(_winp(be_n_Lb=4, be_n_tw=2, be_L_out=1,
                           be_L_in=nT - 2))
    assert bl == bl2 and br == br2


def test_new_case_b_dedupe_middle_row():
    """4/3/1/1: R=3; 14 vi tri nhung 2 thanh tw trung thanh dau hang
    giua -> dedupe -> 12 thanh duy nhat/vung."""
    bl, br = _bars(_winp(be_n_Lb=4, be_n_tw=3, be_L_out=1, be_L_in=1))
    assert len(bl) == len(br) == 12
    ys = sorted({round(y, 6) for _x, y, _d in bl})
    assert ys == [-136.0, 0.0, 136.0]
    # Khong con 2 vi tri trung (khoang cach cap doi >= 1 mm).
    for i, (x1, y1, _d) in enumerate(bl):
        for x2, y2, _e in bl[i + 1:]:
            assert math.hypot(x1 - x2, y1 - y2) >= 1.0 - 1e-9


def test_new_case_c_29_bars_and_tw_positions():
    """5/4/2/1: R=5, 29 thanh/vung, thanh tw trong o +-face/3."""
    bl, br = _bars(_winp(be_n_Lb=5, be_n_tw=4, be_L_out=2, be_L_in=1))
    assert len(bl) == len(br) == 29
    ys = sorted({round(y, 6) for _x, y, _d in bl})
    assert ys == [-136.0, -68.0, -45.333333, 0.0, 45.333333, 68.0, 136.0]
    # Thanh tw o ca 2 dau ngan (x tuong doi 39 va 461), y trong.
    tw_bars = [(round(x + 1250.0, 6), round(y, 6))
               for x, y, _d in bl if round(y, 6) in (-45.333333, 45.333333)]
    assert sorted(tw_bars) == [(39.0, -45.333333), (39.0, 45.333333),
                               (461.0, -45.333333), (461.0, 45.333333)]


@pytest.mark.parametrize("kw", [
    dict(be_n_Lb=4, be_n_tw=2, be_L_out=1, be_L_in=0),
    dict(be_n_Lb=4, be_n_tw=3, be_L_out=1, be_L_in=1),
    dict(be_n_Lb=5, be_n_tw=4, be_L_out=2, be_L_in=1),
])
def test_both_ends_identical(kw):
    """Nhap 1 ben -> 2 dau giong het (mirror x -> -x)."""
    bl, br = _bars(_winp(**kw))
    assert sorted([(-x, y, d) for x, y, d in br]) == sorted(bl)


def test_panel_defaults_migration_and_clamps():
    """Panel moi: mac dinh 500/28/4/2/1/0; load dict cu -> map dung;
    collect -> khoa moi + mirror; clamp gia tri ngoai mien."""
    from gui.app import App

    app = App()
    try:
        app.update_idletasks()
        app.cb_member.set("Vách")
        app._toggle_member()
        app.update_idletasks()
        for old in ("w_en_be_nL", "w_cb_be_nT", "w_var_be_layout"):
            assert not hasattr(app, old)
        assert app.w_en_be_Lb.get() == "500"
        assert app.w_cb_be_dia.get() == "28"
        assert (app.w_en_be_nLb.get(), app.w_en_be_nTw.get(),
                app.w_en_be_Lout.get(), app.w_en_be_Lin.get()) == (
            "4", "2", "1", "0")
        app.w_cb_steel_mode.set("Tập trung vùng biên")
        app._on_wall_steel_mode()
        app.update_idletasks()
        app._apply_wall(_old_dict(3))
        app.update_idletasks()
        assert (app.w_en_be_nLb.get(), app.w_en_be_nTw.get(),
                app.w_en_be_Lout.get(), app.w_en_be_Lin.get()) == (
            "4", "2", "1", "1")
        d = app._collect_wall()
        assert (d["be_n_Lb"], d["be_n_tw"], d["be_L_out"],
                d["be_L_in"]) == (4, 2, 1, 1)
        assert (d["be_nL"], d["be_nT"], d["be_layout"]) == (4, 3, "chuvi")

        def _se(e, v):
            e.delete(0, "end")
            e.insert(0, str(v))

        _se(app.w_en_be_nLb, "0")
        _se(app.w_en_be_nTw, "1")
        _se(app.w_en_be_Lout, "0")
        _se(app.w_en_be_Lin, "-5")
        d2 = app._collect_wall()
        assert (d2["be_n_Lb"], d2["be_n_tw"], d2["be_L_out"],
                d2["be_L_in"]) == (2, 2, 1, 0)
    finally:
        app.destroy()
