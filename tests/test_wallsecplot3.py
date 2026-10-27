"""Tinh chinh hien thi o mat cat vach (user 2026-10-27, anh preview
55b781a d12): "cham thep hoi to, hinh thi hoi nho" — chi doi VE,
khong doi SO.

Do truoc khi sua (render Agg dpi 100, cung dieu kien lat truoc):
- Cham 6.0pt = 8.3px; khoang cach thanh nho nhat theo du lieu la
  ~107 mm (nua canh o nut giao 214 mm) o moi loai da giac; o axes
  bi gioi han chieu cao cua C/U, khoang cach nay chi ~8.3px nen
  ti le cham/khoang cach = 1.00 (cham cham nhau thanh vet).
- Lap khung (datafill): poly 0.71 x 0.36 (T/L/Barbell) va
  0.71 x 0.53 (C/U); rect 0.89 x 0.22 (giu nguyen, da user-verified).

Sua (chi gui/wall_mixin.py):
- WALL_BAR_DIAM_PT 6.0 -> 4.0pt = 5.6px o dpi 100 (11.1px o dpi
  200, 1.4mm vat ly), vien trang 0.8 -> 0.5pt. Muc tieu <=40%
  khoang cach khong dat duoc o co axes C/U neu giu san nhin ro
  ~5px (40% cua 8.3px = 3.3px < san), nen san nhin ro thang:
  cham 4pt + thu span de khoang cach C/U len ~9.5px, ti le con
  0.58 (truoc 1.00). KHONG tro lai Circle ti le that, KHONG
  khoi phuc hook draw_event.
- Don vi dim da giac _unit 0.5 -> 0.35*min(cx,cy), ap DONG BO o
  ca _wall_section_spans va draw_wall_section_ax (moi offset
  dim/truc t3 deu theo _unit nen thu span khong lam dim tran
  span); cot dim trai poly -0.38cx -> -0.34cx. Lap khung poly
  len 0.74 x 0.45 (T/L/Barbell) va 0.74 x 0.62 (C/U). Rect khong
  doi span (test lat truoc khoa fill_h 0.22).
- Gioi han da ghi: o s=100 khoang cach giam mot nua nen cham o
  vung day C/U se cham nhau (ti le ~0.87); s mac dinh 200 moi la
  truong hop thiet ke. Barbell o s!=200 lech web la ton dong cu
  (lat thep) nen test sweep s o day chi khoa T/L/C/U.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
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

_S_EXP = {
    100: {"tee": 86, "ell": 80, "c-core": 148, "u-core": 124},
    150: {"tee": 57, "ell": 54, "c-core": 98, "u-core": 82},
    300: {"tee": 28, "ell": 26, "c-core": 48, "u-core": 40},
}


def _mat():
    return (ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85),
            SteelMaterial(STEEL_GRADES["CB500-V"], 1.0))


def _mk(st, kw, dia=12, s=200):
    w = WallInput(section_type=st, cover=25, dia_h=12, per_dia=dia,
                  per_s=s, sec_sym=True)
    for k, v in kw.items():
        setattr(w, k, v)
    return w


def _render(st, kw, rot=0, s=200):
    conc, steel = _mat()
    sec, meta = build_wall_section(_mk(st, kw, s=s), conc, steel)
    fw, fh = _wall_section_figsize(sec, len(meta.get("dim_segments") or []), rot)
    fig, ax = plt.subplots(figsize=(fw, fh), dpi=100)
    draw_wall_section_ax(ax, sec, meta=meta, rot_deg=rot)
    _wall_section_axes_pos(fig, ax)
    fig.canvas.draw()
    return fig, ax, sec, meta


def _scatter_points(ax):
    pts, sizes = [], set()
    for c in ax.collections:
        if isinstance(c, PathCollection):
            pts.extend([tuple(o) for o in c.get_offsets()])
            sizes.update([round(float(s), 1) for s in c.get_sizes()])
    return pts, sizes


def _min_dist_px(ax, sec):
    pts = np.array([ax.transData.transform((r.x, r.y))
                    for r in sec.rebars])
    dmin = float("inf")
    for i in range(len(pts)):
        d = np.sqrt(((pts[i + 1:] - pts[i]) ** 2).sum(axis=1))
        if len(d):
            dmin = min(dmin, float(d.min()))
    return dmin


@pytest.mark.parametrize("st,kw,exp", _CASES)
def test_marker_smaller_than_before(st, kw, exp):
    """Cham co dinh 4.0pt = 5.6px o dpi 100 (trong khoang 5-6.5px),
    so marker = so thanh, khong Circle thep."""
    fig, ax, sec, meta = _render(st, kw)
    try:
        assert WALL_BAR_DIAM_PT == 4.0
        assert 5.0 <= WALL_BAR_DIAM_PT * 100.0 / 72.0 <= 6.5
        pts, sizes = _scatter_points(ax)
        assert len(pts) == exp, (st, len(pts), exp)
        assert sizes == {WALL_BAR_DIAM_PT ** 2}, (st, sizes)
        import matplotlib.patches as mpatches
        assert [p for p in ax.patches
                if isinstance(p, mpatches.Circle)] == []
    finally:
        plt.close(fig)


@pytest.mark.parametrize("st,kw,exp", _CASES)
def test_marker_does_not_touch_neighbours_at_default_s(st, kw, exp):
    """Ti le cham/khoang cach nho nhat o s200 < 0.65 cho moi loai
    (truoc: C/U = 1.00, cham nhau; sau: C/U 0.58, ell 0.48, cac
    loai khac <= 0.36)."""
    fig, ax, sec, meta = _render(st, kw)
    try:
        diam = WALL_BAR_DIAM_PT * 100.0 / 72.0
        ratio = diam / _min_dist_px(ax, sec)
        assert ratio < 0.65, (st, ratio)
    finally:
        plt.close(fig)


@pytest.mark.parametrize("st,kw,exp", _CASES)
def test_section_fills_frame_more_than_55b781a(st, kw, exp):
    """Lap khung tang so voi 55b781a, rect khong thut: poly
    fill_w >= 0.73 va fill_h >= 0.44 (C/U >= 0.60); rect giu
    0.89 x 0.22 (+-0.02)."""
    conc, steel = _mat()
    sec, meta = build_wall_section(_mk(st, kw), conc, steel)
    xlo, xhi, ylo, yhi = _wall_section_spans(
        sec, len(meta.get("dim_segments") or []), 0)
    fw = sec.cx / (xhi - xlo)
    fh = sec.cy / (yhi - ylo)
    if getattr(sec, "kind", "rect") == "poly":
        assert fw >= 0.73, (st, fw)
        assert fh >= 0.60 if st in ("c-core", "u-core") else fh >= 0.44, \
            (st, fh)
    else:
        assert abs(fw - 0.89) < 0.02 and abs(fh - 0.22) < 0.02, (st, fw, fh)


@pytest.mark.parametrize("st,kw,exp", _CASES)
def test_dim_labels_do_not_overlap(st, kw, exp):
    """Nhan dim khong de nhau qua 4px2 o render Agg (ca 6 loai,
    ke ca sau khi thu cot dim trai poly)."""
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


@pytest.mark.parametrize("rot", [90, 180, 270])
@pytest.mark.parametrize("st,kw,exp", [c for c in _CASES
                                      if c[0] in ("c-core", "u-core",
                                                 "tee", "barbell")])
def test_rotation_keeps_bar_count(st, kw, exp, rot):
    """Xoay 4 goc: so marker khong doi."""
    fig, ax, sec, meta = _render(st, kw, rot=rot)
    try:
        pts, _sizes = _scatter_points(ax)
        assert len(pts) == exp, (st, rot, len(pts))
    finally:
        plt.close(fig)


@pytest.mark.parametrize("s,exp_map", sorted(_S_EXP.items()))
def test_bar_counts_by_spacing_tlcu_unchanged(s, exp_map):
    """So thanh T/L/C/U theo s van khop web (chi doi ve); Barbell
    o s!=200 khong khoa o day (ton dong cu lat thep)."""
    conc, steel = _mat()
    kw_map = {c[0]: c[1] for c in _CASES}
    for st, exp in exp_map.items():
        sec, meta = build_wall_section(_mk(st, kw_map[st], s=s),
                                       conc, steel)
        assert len(sec.rebars) == exp, (s, st, len(sec.rebars), exp)
