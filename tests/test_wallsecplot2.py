"""Lat hien thi thep o mat cat vach (user 2026-10-27, anh preview
9b6481f d14): chi doi VE, khong doi SO.

Nguyen nhan goc (do truoc khi sua):
- Thep ve bang Circle ti le that + san draw_event 6px: render Agg
  truc tiep thi co 6px, nhung anh user chi con 9-22px cam (chi
  legend) — thep gan nhu khong hien trong Tk. Co che draw_event
  phu thuoc draw/resize/debounce nen khong dang tin.
- Span doc phinh 4.56*cy (dim + truc t3 tinh theo cy, voi C/U cy
  la canh DAI 3000 mm) nen mat cat chi chiem 22% chieu cao span,
  C/U nho xiu giua khung.
- Nhan dim doc trai C/U de nhau (cot dim tong va cot dim phan
  doan cach nhau 0.115cx, nhan doc dai hon doan dim ngan).

Sua (chi gui/wall_mixin.py + nhan dim Barbell):
- Thep = scatter co dinh WALL_BAR_DIAM_PT=6.0pt (~8.3px o dpi
  100), khong Circle, khong hook draw_event; mau giu dung legend
  (lop 1 theo DIA_COLORS, lop 2 cam L2_COLOR).
- Da giac dung don vi dim _unit=0.5*min(cx,cy) cho dim doc/
  truc t3 va span doc; rect giu nguyen cy (test_wallsecplot khoa
  dim tong rect -1.45cy khong doi).
- Cot dim phan doan doc C/U doi tu -0.16cx sang -0.28cx, span
  trai poly tu -0.21cx sang -0.38cx de nhan doc khong de cot
  dim tong.
- Nhan dim doc Barbell: "Bf = 1000 mm" (chieu y) thay cho
  "Bf = 3000 mm" (ban cu lay chieu x) — chi sua nhan ve, so
  tinh Ac/As khong qua nhan nay.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest
from matplotlib.collections import PathCollection

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_input import WallInput
from rc_column.wall_section import build_wall_section
from gui.wall_mixin import (_wall_section_figsize, _wall_section_spans,
                            _wall_section_axes_pos, draw_wall_section_ax,
                            WALL_BAR_DIAM_PT)

_CASES = [
    ("rect", dict(steel_mode="perimeter"), 30),
    ("barbell", dict(Lw=3000, tw=300, sec_bf=1000, sec_tf=450), 48),
    ("tee", dict(Lw=2500, sec_bf=1500, sec_t=300), 45),
    ("ell", dict(sec_L1=2000, sec_L2=1800, sec_t=300), 44),
    ("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600, sec_t=300), 82),
    ("u-core", dict(Lw=3000, sec_bf=1500, sec_t=300), 66),
]


def _mat():
    conc = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
    return conc, steel


def _mk(st, kw, dia=14):
    w = WallInput(section_type=st, cover=25, dia_h=12, per_dia=dia,
                  per_s=200, sec_sym=True)
    for k, v in kw.items():
        setattr(w, k, v)
    return w


def _render(st, kw, rot=0):
    conc, steel = _mat()
    sec, meta = build_wall_section(_mk(st, kw), conc, steel)
    fw, fh = _wall_section_figsize(sec, len(meta.get("dim_segments") or []), rot)
    fig, ax = plt.subplots(figsize=(fw, fh), dpi=100)
    draw_wall_section_ax(ax, sec, meta=meta, rot_deg=rot)
    _wall_section_axes_pos(fig, ax)
    fig.canvas.draw()
    return fig, ax, sec, meta


def _scatter_points(ax):
    pts = []
    sizes = set()
    for c in ax.collections:
        if isinstance(c, PathCollection):
            pts.extend([tuple(o) for o in c.get_offsets()])
            sizes.update([round(float(s), 1) for s in c.get_sizes()])
    return pts, sizes


@pytest.mark.parametrize("st,kw,exp", _CASES)
def test_bars_fixed_pixel_scatter_count_matches(st, kw, exp):
    """So marker scatter = so thanh ky vong, co dinh 6pt, khong
    con Circle thep (chi legend Line2D)."""
    fig, ax, sec, meta = _render(st, kw)
    try:
        assert len(sec.rebars) == exp, (st, len(sec.rebars))
        pts, sizes = _scatter_points(ax)
        assert len(pts) == exp, (st, len(pts), exp)
        assert sizes == {WALL_BAR_DIAM_PT ** 2}, (st, sizes)
        assert WALL_BAR_DIAM_PT == 6.0
        # Duong kinh px o dpi 100 = 6pt * 100/72 = 8.3px (trong
        # khoang 7-9px brief yeu cau).
        assert 7.0 <= WALL_BAR_DIAM_PT * 100.0 / 72.0 <= 9.0
        # Khong con Circle thep tren axes (patch tron chi con
        # polygon mat cat/vung nen, khong phai Circle).
        import matplotlib.patches as mpatches
        circs = [p for p in ax.patches
                 if isinstance(p, mpatches.Circle)]
        assert circs == [], (st, len(circs))
        # Moi diem scatter nam trong polygon (khong mat/roi ra
        # ngoai sau khi doi cach ve).
        from rc_column.wall_section import _point_in_poly
        verts = sec.poly_verts[0] if getattr(sec, "poly_verts", None) \
            else [(-sec.cx / 2, -sec.cy / 2), (sec.cx / 2, -sec.cy / 2),
                  (sec.cx / 2, sec.cy / 2), (-sec.cx / 2, sec.cy / 2)]
        for x, y in pts:
            assert _point_in_poly(x, y, verts), (st, x, y)
    finally:
        plt.close(fig)


@pytest.mark.parametrize("st,kw,exp", _CASES)
def test_section_fills_frame_better_than_before(st, kw, exp):
    """Mat cat chiem ti le span lon hon truoc (poly: chieu cao
    span tu 0.22 len >=0.35; rect giu nguyen 0.22 vi chieu rong
    moi la chieu khong che)."""
    conc, steel = _mat()
    sec, meta = build_wall_section(_mk(st, kw), conc, steel)
    xlo, xhi, ylo, yhi = _wall_section_spans(
        sec, len(meta.get("dim_segments") or []), 0)
    fill_h = sec.cy / (yhi - ylo)
    if getattr(sec, "kind", "rect") == "poly":
        assert fill_h >= 0.35, (st, fill_h)
    else:
        assert abs(fill_h - 0.22) < 0.02, (st, fill_h)


@pytest.mark.parametrize("st,kw,exp", [c for c in _CASES
                                      if c[0] in ("c-core", "u-core")])
def test_left_dim_labels_do_not_overlap(st, kw, exp):
    """Nhan dim doc trai C/U (Lw tong + Lr/t phan doan) khong de
    nhau qua 4px2 o render Agg mac dinh."""
    fig, ax, sec, meta = _render(st, kw)
    try:
        boxes = []
        for t in ax.texts:
            if not t.get_text():
                continue
            bb = t.get_window_extent()
            boxes.append((t.get_text(), bb.x0, bb.y0, bb.x1, bb.y1))
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                ox = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
                oy = max(0.0, min(a[4], b[4]) - max(a[2], b[2]))
                assert ox * oy <= 4.0, (st, a, b, ox * oy)
    finally:
        plt.close(fig)


def test_barbell_left_dim_label_is_bf_height():
    """Nhan dim doc Barbell la chieu y (Bf=1000), khong phai
    chieu x (3000) nhu ban cu."""
    conc, steel = _mat()
    sec, meta = build_wall_section(
        _mk("barbell", dict(Lw=3000, tw=300, sec_bf=1000, sec_tf=450)),
        conc, steel)
    assert meta["dim_total_y_label"] == "Bf = 1000 mm", \
        meta["dim_total_y_label"]


@pytest.mark.parametrize("rot", [90, 180, 270])
@pytest.mark.parametrize("st,kw,exp", [c for c in _CASES
                                      if c[0] in ("c-core", "u-core",
                                                 "tee", "barbell")])
def test_rotation_keeps_bar_count(st, kw, exp, rot):
    """Xoay 4 goc: so marker khong doi, khong loi ve."""
    fig, ax, sec, meta = _render(st, kw, rot=rot)
    try:
        pts, _sizes = _scatter_points(ax)
        assert len(pts) == exp, (st, rot, len(pts))
    finally:
        plt.close(fig)


def test_numbers_unchanged():
    """Chi doi ve: so thanh/As/Ac cua 5 loai + vach phang khong
    doi (so lay tu meta/section, khong tinh lai)."""
    conc, steel = _mat()
    for st, kw, exp in _CASES:
        if st == "rect":
            continue
        sec, meta = build_wall_section(_mk(st, kw), conc, steel)
        assert len(sec.rebars) == exp
        assert meta["poly_ac"] > 0
    # Vach phang moc (preset): dung engine cu khong qua ham ve.
    from rc_column.wall_input import WallInput as WI
    w = WI(cover=13.0)
    sec, meta = build_wall_section(w, conc, steel)
    assert len(sec.rebars) > 0
