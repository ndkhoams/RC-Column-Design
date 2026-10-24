"""Panel vung bien 6 o + generator cot doc + migration (2026-10-25).

User chot (thay mo hinh hang ngang 950b4d5):
- LOP = COT DOC theo chieu tw (cot thep tai 1 vi tri thanh cua 2
  hang, xep doc theo Lb: L_out cot ngoai dem TU DAU NGOAI vao,
  L_in cot trong NEO O HANG TRONG CUNG dem DI RA — sua ban
  9eac50e6 dat lop trong ke sau lop ngoai, user chot 2026-10-25).
- "So thanh theo chieu tw" DOI THANH "so thanh O GIUA theo chieu
  tw": n_tw chi dem thep giua (khong tinh 2 hang tren/duoi — thanh
  tren/duoi cua cot TRUNG thanh cua 2 hang nen khong dem them,
  khong sinh trung, khong dedupe).
- Tong/vung = 2*n_Lb + n_tw*(L_out + L_in); L_out + L_in <= n_Lb.
- Quyet dedupe "giu 12" cua mo hinh cu BI THAY THE (mo hinh moi
  khong co vu 12-vs-14 nua; ca (4,3,1,1) nay cho 14 thanh/vung).
Migration: file nghia cu 950b4d5 (be_n_tw tinh ca 2 goc, khong khoa
be_model) -> n_tw_moi = max(n_tw_cu - 2, 0); file da co
be_model="columns" -> dung thang; file tien-950b4d5 qua mapping cu
roi ap tiep quy tac nay.
"""
import math

import pytest

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_input import (WallInput, normalize_wall_dict,
                                  wall_from_dict)
from rc_column.wall_section import build_wall_section

CONC = ConcreteMaterial(CONCRETE_GRADES["B25"], 0.85)
STEEL = SteelMaterial(STEEL_GRADES["CB400-V"], 1.0)
# cover=13, dia_h=12, db=28 -> inset = 39; face = 175 - 39 = 136.
# ps (n_Lb=4) = linspace(39, 461, 4) = [39, 179.667, 320.333, 461].
INSET = 39.0
FACE = 136.0


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


def _xy_set(bars):
    return sorted((round(x, 6), round(y, 6)) for x, y, _d in bars)


@pytest.mark.parametrize("nT", [2, 3, 4])
def test_migration_old_dict_new_meaning(nT):
    """File cu (be_nL/be_nT) -> n_tw_moi = 0, chi con 2 hang x 4.

    nT=2: dung 2 hang cu, cung toa do luoi cu (8 thanh/vung).
    nT=3,4: luoi cu co nT hang — mo hinh moi chi co 2 hang (doi mo
    hinh theo spec, khong phai hoi quy); so thanh moi = 8 moi nT.
    """
    w = wall_from_dict(_old_dict(nT))
    assert (w.be_n_Lb, w.be_n_tw, w.be_L_out, w.be_L_in) == (
        4, 0, 1, nT - 2)
    bl, br = _bars(w)
    assert len(bl) == len(br) == 8
    # Cung luoi voi WallInput khoa moi tuong duong (tung toa do).
    bl2, br2 = _bars(_winp(be_n_Lb=4, be_n_tw=0, be_L_out=1,
                           be_L_in=nT - 2))
    assert bl == bl2 and br == br2
    # 2 hang tai 2 mat (+-136), 4 vi tri Lb moi hang.
    assert _xy_set(bl) == sorted(
        (round(-1250.0 + p, 6), yy)
        for p in (39.0, 179.666667, 320.333333, 461.0)
        for yy in (-FACE, FACE))


def test_migration_950b4d5_file_subtracts_two():
    """File 950b4d5 (co be_n_tw, khong be_model) -> tru 2 goc."""
    d = dict(be_n_Lb=4, be_n_tw=3, be_L_out=2, be_L_in=0)
    w = wall_from_dict(d)
    assert (w.be_n_Lb, w.be_n_tw, w.be_L_out, w.be_L_in) == (
        4, 1, 2, 0)
    bl, _br = _bars(w)
    assert len(bl) == 10  # 2x4 + 1x2 (khong phai 18 cua mo hinh cu)
    # File da co be_model="columns" -> dung thang, khong tru lai.
    d2 = normalize_wall_dict(dict(be_n_Lb=4, be_n_tw=3, be_L_out=2,
                                  be_L_in=0, be_model="columns"))
    assert d2["be_n_tw"] == 3
    d3 = normalize_wall_dict(dict(d2))
    assert d3["be_n_tw"] == 3  # idempotent


def test_user_example_10_bars():
    """VD user: (4,1,2,0) -> 2x4 + 1x2 + 1x0 = 10 thanh/vung."""
    bl, br = _bars(_winp(be_n_Lb=4, be_n_tw=1, be_L_out=2, be_L_in=0))
    assert len(bl) == len(br) == 10
    # 2 cot ngoai = 2 vi tri dau tu dau ngoai (p=39, 179.667),
    # moi cot 1 thanh giua tai y=0; khong trung toa do.
    mids = sorted((round(x + 1250.0, 6), round(y, 6))
                  for x, y, _d in bl if round(y, 6) == 0.0)
    assert mids == [(39.0, 0.0), (179.666667, 0.0)]
    assert len({(round(x, 6), round(y, 6)) for x, y, _d in bl}) == 10
    assert sorted([(-x, y, d) for x, y, d in br]) == sorted(bl)


def test_case_16_bars():
    """(5,2,2,1) -> 2x5 + 2x2 + 2x1 = 16 thanh/vung."""
    bl, br = _bars(_winp(be_n_Lb=5, be_n_tw=2, be_L_out=2, be_L_in=1))
    assert len(bl) == len(br) == 16
    # ps(5) = [39, 144.5, 250, 355.5, 461]; cot ngoai = 2 dau tu dau
    # ngoai (39, 144.5), cot trong = hang trong cung (461, khong
    # phai 250 ke sau ngoai); p=250, 355.5 chi co thep 2 hang.
    # Thanh giua y=+-45.333.
    mids = sorted((round(x + 1250.0, 6), round(y, 6))
                  for x, y, _d in bl
                  if round(y, 6) in (-45.333333, 45.333333))
    assert mids == [(39.0, -45.333333), (39.0, 45.333333),
                    (144.5, -45.333333), (144.5, 45.333333),
                    (461.0, -45.333333), (461.0, 45.333333)]


def test_case_14_supersedes_dedupe():
    """(4,3,1,1) -> 2x4 + 3x1 + 3x1 = 14 thanh/vung.

    Quyet dedupe "giu 12" cua mo hinh cu KHONG con ap dung: mo hinh
    moi khong sinh trung (thanh tren/duoi cua cot trung hang nen
    khong dem them) nen khong co vu 12-vs-14 nua.
    """
    bl, br = _bars(_winp(be_n_Lb=4, be_n_tw=3, be_L_out=1, be_L_in=1))
    assert len(bl) == len(br) == 14
    ys = sorted({round(y, 6) for _x, y, _d in bl})
    assert ys == [-136.0, -68.0, 0.0, 68.0, 136.0]
    # Thanh giua o cot ngoai (p=39) va cot trong = hang trong cung
    # (p=461, khong phai p=179.667 ke sau ngoai); p=179.667 va
    # p=320.333 chi co thep 2 hang.
    mids = sorted((round(x + 1250.0, 6), round(y, 6))
                  for x, y, _d in bl
                  if round(y, 6) in (-68.0, 0.0, 68.0))
    assert mids == [(39.0, -68.0), (39.0, 0.0), (39.0, 68.0),
                    (461.0, -68.0), (461.0, 0.0), (461.0, 68.0)]
    for i, (x1, y1, _d) in enumerate(bl):
        for x2, y2, _e in bl[i + 1:]:
            assert math.hypot(x1 - x2, y1 - y2) >= 1.0 - 1e-9


def test_inner_layers_anchored_at_innermost():
    """Lop trong neo o hang trong cung, dem di ra (user chot
    2026-10-25, sua ban 9eac50e6 dat trong ke sau ngoai).

    (4,2,2,1): ngoai p1, p2 (39, 179.667 tu dau ngoai); trong p4
    (461, trong cung); p3 (320.333) chi co thep 2 hang. Vung phai
    mirror: trong = cot ke bung vach (x = 1250 - 461 = 789, khong
    phai 929.667). (5,2,2,2): ngoai p1, p2; trong p5, p4; p3 chi
    2 hang; tong 2x5 + 2x4 = 18/vung. (4,1,2,0): khong co lop
    trong -> khong doi.
    """
    bl, br = _bars(_winp(be_n_Lb=4, be_n_tw=2, be_L_out=2, be_L_in=1))
    assert len(bl) == len(br) == 14
    # Thanh giua (n_tw=2 -> y=+-45.333) chi o p1, p2, p4.
    mids_l = sorted({round(x + 1250.0, 6) for x, y, _d in bl
                     if abs(round(y, 6)) < 136.0})
    assert mids_l == [39.0, 179.666667, 461.0]
    # p3 (320.333) khong co thanh giua: tai x=-1250+320.333 chi co
    # 2 thanh hang (+-136).
    p3 = sorted(round(y, 6) for x, y, _d in bl
                if round(x + 1250.0, 6) == 320.333333)
    assert p3 == [-136.0, 136.0]
    # Vung phai: trong = cot ke bung vach (x=789); cot x=929.667
    # (mirror cua p3) chi co 2 hang.
    mids_r = sorted({round(x, 6) for x, y, _d in br
                     if abs(round(y, 6)) < 136.0})
    assert mids_r == [789.0, 1070.333333, 1211.0]
    p3r = sorted(round(y, 6) for x, y, _d in br
                 if round(x, 6) == 929.666667)
    assert p3r == [-136.0, 136.0]
    # (5,2,2,2): 18/vung, trong = p5, p4; p3 chi 2 hang.
    bl5, _br5 = _bars(_winp(be_n_Lb=5, be_n_tw=2, be_L_out=2,
                            be_L_in=2))
    assert len(bl5) == 18
    mids5 = sorted({round(x + 1250.0, 6) for x, y, _d in bl5
                    if abs(round(y, 6)) < 136.0})
    assert mids5 == [39.0, 144.5, 355.5, 461.0]
    p3_5 = sorted(round(y, 6) for x, y, _d in bl5
                  if round(x + 1250.0, 6) == 250.0)
    assert p3_5 == [-136.0, 136.0]
    # (4,1,2,0): khong lop trong, khong doi.
    bl0, _br0 = _bars(_winp(be_n_Lb=4, be_n_tw=1, be_L_out=2,
                            be_L_in=0))
    assert len(bl0) == 10


def test_inner_clamp_keeps_outer_wins():
    """Clamp: (n_Lb=4, L_out=3, L_in=2) -> L_in kep con 1, trong
    duy nhat = p4; ngoai p1..p3; tong 2x4 + 2x4 = 16/vung."""
    from rc_column.wall_section import _gen_boundary
    bl, _br, _web, _runs, ex = _gen_boundary(
        2500.0, 350.0, 13.0, 500.0, 28.0, 4, 2, 3, 2, 12.0, 200.0,
        12.0)
    assert (ex["be_layers_out"], ex["be_layers_in"]) == (3, 1)
    assert len(bl) == 16


@pytest.mark.parametrize("kw", [
    dict(be_n_Lb=4, be_n_tw=1, be_L_out=2, be_L_in=0),
    dict(be_n_Lb=4, be_n_tw=3, be_L_out=1, be_L_in=1),
    dict(be_n_Lb=5, be_n_tw=2, be_L_out=2, be_L_in=1),
])
def test_both_ends_identical(kw):
    """Nhap 1 ben -> 2 dau giong het (mirror x -> -x)."""
    bl, br = _bars(_winp(**kw))
    assert sorted([(-x, y, d) for x, y, d in br]) == sorted(bl)


def test_panel_defaults_migration_and_clamps():
    """Panel moi: mac dinh 500/28/4/2/1/0 (nghia moi); load dict cu
    -> map dung; collect -> khoa moi + mirror + be_model; clamp
    gia tri ngoai mien (gom L_out + L_in <= n_Lb)."""
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
        # File cu nT=3 -> (4, 0, 1, 1): n_tw cu 2 tru 2 goc = 0.
        assert (app.w_en_be_nLb.get(), app.w_en_be_nTw.get(),
                app.w_en_be_Lout.get(), app.w_en_be_Lin.get()) == (
            "4", "0", "1", "1")
        d = app._collect_wall()
        assert (d["be_n_Lb"], d["be_n_tw"], d["be_L_out"],
                d["be_L_in"]) == (4, 0, 1, 1)
        assert (d["be_nL"], d["be_nT"], d["be_layout"]) == (4, 2, "chuvi")
        assert d["be_model"] == "columns"
        assert d["n_be"] == 8

        def _se(e, v):
            e.delete(0, "end")
            e.insert(0, str(v))

        # Clamp co ban: n_Lb>=2, n_tw>=0 (duoc 0, khac quy tac cu
        # >=2), L_out>=1, L_in>=0.
        _se(app.w_en_be_nLb, "0")
        _se(app.w_en_be_nTw, "1")
        _se(app.w_en_be_Lout, "0")
        _se(app.w_en_be_Lin, "-5")
        d2 = app._collect_wall()
        assert (d2["be_n_Lb"], d2["be_n_tw"], d2["be_L_out"],
                d2["be_L_in"]) == (2, 1, 1, 0)
        # Clamp quan he: L_out + L_in <= n_Lb.
        _se(app.w_en_be_nLb, "4")
        _se(app.w_en_be_nTw, "2")
        _se(app.w_en_be_Lout, "5")
        _se(app.w_en_be_Lin, "3")
        d3 = app._collect_wall()
        assert (d3["be_n_Lb"], d3["be_n_tw"], d3["be_L_out"],
                d3["be_L_in"]) == (4, 2, 4, 0)
        _se(app.w_en_be_nTw, "-3")
        _se(app.w_en_be_Lout, "2")
        _se(app.w_en_be_Lin, "3")
        d4 = app._collect_wall()
        assert (d4["be_n_Lb"], d4["be_n_tw"], d4["be_L_out"],
                d4["be_L_in"]) == (4, 0, 2, 2)
    finally:
        app.destroy()
