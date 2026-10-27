"""Chấm thép THÍCH ỨNG theo mặt cắt ở ô mặt cắt vách
(user 2026-10-27, ảnh preview 8dd839c d12): "nên linh động giảm
kích thước chấm thép xuống để phù hợp với mặt cắt" — chỉ đổi
VẼ, không đổi SỐ.

Vấn đề của chấm cố định 4.0pt (8dd839c): đo đúng điều kiện
Agg figsize của app, chấm 5.6px chiếm 20.8% bề dày 300 mm hiển
thị ở C/U (26.7px) và 58% khoảng cách thanh nhỏ nhất (9.5px),
trong khi ở phẳng chỉ 10.0% bề dày và 23% khoảng cách — một
cỡ cho mọi loại không thể vừa cả hai đầu.

Sửa (chỉ gui/wall_mixin.py + meta bar_branch_t ở
rc_column/wall_section.py, không đổi số):
- Chấm = đĩa Circle theo ĐƠN VỊ DỮ LIỆU, đường kính
  D = min(0.14 × t_nhánh, 0.40 × d_min_theo_dữ_liệu),
  rồi max với 2.5 × dia_max (sàn nhìn rõ; ở s200 không kích
  hoạt). t_nhánh từ meta["bar_branch_t"] (rect: tw;
  Barbell: tw; T/L/C/U: sec_t). Vì axes aspect equal, đường
  kính theo px tự bằng D × (px/mm) ở mọi figure/dpi/resize/
  PDF — KHÔNG cần handler draw_event (điểm yếu đã bỏ ở
  55b781a), KHÔNG quay lại Circle tỉ lệ thật (D = 42 mm ở
  nhánh 300 mm, gấp 3.5 lần d12 thật, nên ở tỉ lệ C/U vẫn
  ~3.7px chứ không ~1px như thời Circle tỉ lệ thật).
- Hướng scatter cỡ điểm tính từ tỉ lệ mm/px tại thời điểm vẽ
  đã LOẠI: cỡ đó đóng băng ở figsize khởi tạo, khi Tk resize
  figure thì tỉ lệ px/mm đổi mà cỡ scatter không đổi theo —
  đúng điểm yếu của cơ chế cũ. Đĩa dữ liệu không có nhược
  điểm này vì transform dữ liệu luôn đi theo axes.
- Kết quả ở mặc định d12 s200 (đo Agg figsize app, dpi 100):
  rect D=49 mm, dot 9.0px, 14% bề dày, 37% khoảng cách;
  Barbell D=42 mm, 5.3px, 14%, 24%; tee 42 mm, 6.0px, 14%,
  39%; ell 42 mm, 4.5px, 14%, 39%; C/U 42 mm, 3.7px, 14%,
  39%. Lấp khung không đổi so với 8dd839c (poly 0.74×0.45,
  C/U 0.74×0.62, rect 0.89×0.22); dim không chồng.
- Giới hạn đã ghi: ở s100, d_min theo dữ liệu giảm một nửa
  nên D bị trần 0.40×d_min kéo xuống (và sàn 2.5×dia có thể
  thắng) — chấm ở vùng dày sẽ sát nhau hơn; s200 là mốc
  thiết kế. PDF dùng chung hàm vẽ nên cũng hưởng đĩa dữ
  liệu, tỉ lệ không đổi theo dpi (px tăng gấp đôi ở dpi 200
  thì tỉ lệ mm/px cũng tăng gấp đôi).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pytest

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_input import WallInput
from rc_column.wall_section import build_wall_section
from gui.wall_mixin import (_wall_section_figsize, _wall_section_spans,
                            _wall_section_axes_pos, draw_wall_section_ax,
                            _wall_bar_dot_diam, WALL_BAR_DOT_FRAC_T,
                            WALL_BAR_DOT_FRAC_SPACING)

_CASES = [
    ("rect", dict(steel_mode="perimeter"), 30, 350.0, 49.0),
    ("barbell", dict(Lw=3000, tw=300, sec_bf=1000, sec_tf=450), 48, 300.0, 42.0),
    ("tee", dict(Lw=2500, sec_bf=1500, sec_t=300), 45, 300.0, 42.0),
    ("ell", dict(sec_L1=2000, sec_L2=1800, sec_t=300), 44, 300.0, 42.0),
    ("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600, sec_t=300), 82, 300.0, 42.0),
    ("u-core", dict(Lw=3000, sec_bf=1500, sec_t=300), 66, 300.0, 42.0),
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


def _render(st, kw, rot=0, s=200, dpi=100):
    conc, steel = _mat()
    sec, meta = build_wall_section(_mk(st, kw, s=s), conc, steel)
    fw, fh = _wall_section_figsize(sec, len(meta.get("dim_segments") or []), rot)
    fig, ax = plt.subplots(figsize=(fw, fh), dpi=dpi)
    draw_wall_section_ax(ax, sec, meta=meta, rot_deg=rot)
    _wall_section_axes_pos(fig, ax)
    fig.canvas.draw()
    return fig, ax, sec, meta


def _scale_px_per_mm(ax):
    p0 = ax.transData.transform((0, 0))
    p1 = ax.transData.transform((100, 0))
    return abs(p1[0] - p0[0]) / 100.0


def _dmin_data(sec):
    rp = np.array([(r.x, r.y) for r in sec.rebars])
    dmin = float("inf")
    for i in range(len(rp)):
        d = np.sqrt(((rp[i + 1:] - rp[i]) ** 2).sum(axis=1))
        if len(d):
            dmin = min(dmin, float(d.min()))
    return dmin


def _dmin_px(ax, sec):
    pts = np.array([ax.transData.transform((r.x, r.y))
                    for r in sec.rebars])
    dmin = float("inf")
    for i in range(len(pts)):
        d = np.sqrt(((pts[i + 1:] - pts[i]) ** 2).sum(axis=1))
        if len(d):
            dmin = min(dmin, float(d.min()))
    return dmin


@pytest.mark.parametrize("st,kw,exp,t_exp,d_exp", _CASES)
def test_dot_diam_formula(st, kw, exp, t_exp, d_exp):
    """D = min(0.14*t_nhánh, 0.40*d_min) với sàn 2.5×dia;
    meta có bar_branch_t đúng; hệ số không hardcode theo loại."""
    fig, ax, sec, meta = _render(st, kw)
    try:
        assert meta["bar_branch_t"] == t_exp, (st, meta.get("bar_branch_t"))
        assert WALL_BAR_DOT_FRAC_T == 0.14
        assert WALL_BAR_DOT_FRAC_SPACING == 0.40
        assert abs(_wall_bar_dot_diam(sec, meta) - d_exp) < 1e-9, \
            (st, _wall_bar_dot_diam(sec, meta))
        assert len(sec.rebars) == exp
    finally:
        plt.close(fig)


@pytest.mark.parametrize("st,kw,exp,t_exp,d_exp", _CASES)
def test_dot_adaptive_ratios_at_app_figsize(st, kw, exp, t_exp, d_exp):
    """Ở figsize app, dpi 100: chấm/bề dày hiển thị ≤ 15%,
    chấm/khoảng cách px nhỏ nhất ≤ 40%, chấm ≥ 3.5px
    (C/U 3.7px là nhỏ nhất, vẫn trên sàn nhìn rõ), số đĩa
    = số thanh, mọi đĩa nằm trong polygon."""
    fig, ax, sec, meta = _render(st, kw)
    try:
        scale = _scale_px_per_mm(ax)
        dot_px = d_exp * scale
        thick_px = t_exp * scale
        assert dot_px / thick_px <= 0.15, (st, dot_px / thick_px)
        assert dot_px / _dmin_px(ax, sec) <= 0.40, \
            (st, dot_px / _dmin_px(ax, sec))
        assert dot_px >= 3.5, (st, dot_px)
        circs = [p for p in ax.patches
                 if isinstance(p, mpatches.Circle)]
        assert len(circs) == exp, (st, len(circs))
        assert all(abs(p.radius * 2.0 - d_exp) < 1e-9 for p in circs)
        from rc_column.wall_section import _point_in_poly
        verts = sec.poly_verts[0] if getattr(sec, "poly_verts", None) \
            else [(-sec.cx / 2, -sec.cy / 2), (sec.cx / 2, -sec.cy / 2),
                  (sec.cx / 2, sec.cy / 2), (-sec.cx / 2, sec.cy / 2)]
        for p in circs:
            assert _point_in_poly(p.center[0], p.center[1], verts), \
                (st, p.center)
    finally:
        plt.close(fig)


@pytest.mark.parametrize("st,kw,exp,t_exp,d_exp", _CASES)
def test_dot_ratio_invariant_with_dpi(st, kw, exp, t_exp, d_exp):
    """Sang dpi 200 (PDF): tỉ lệ chấm/bề dày và chấm/khoảng
    cách không đổi (px tăng gấp đôi thì scale cũng tăng gấp
    đôi) — đĩa dữ liệu tự thích ứng theo dpi."""
    fig, ax, sec, meta = _render(st, kw, dpi=200)
    try:
        scale = _scale_px_per_mm(ax)
        dot_px = d_exp * scale
        assert dot_px / (t_exp * scale) <= 0.15
        assert dot_px / _dmin_px(ax, sec) <= 0.40
    finally:
        plt.close(fig)


@pytest.mark.parametrize("st,kw,exp,t_exp,d_exp", _CASES)
def test_fill_unchanged_from_8dd839c(st, kw, exp, t_exp, d_exp):
    """Hình không nhỏ lại so với 8dd839c: poly 0.74×0.45
    (C/U 0.74×0.62), rect 0.89×0.22."""
    conc, steel = _mat()
    sec, meta = build_wall_section(_mk(st, kw), conc, steel)
    xlo, xhi, ylo, yhi = _wall_section_spans(
        sec, len(meta.get("dim_segments") or []), 0)
    fw = sec.cx / (xhi - xlo)
    fh = sec.cy / (yhi - ylo)
    if getattr(sec, "kind", "rect") == "poly":
        assert abs(fw - 0.74) < 0.02, (st, fw)
        assert abs(fh - (0.62 if st in ("c-core", "u-core") else 0.45)) < 0.02, (st, fh)
    else:
        assert abs(fw - 0.89) < 0.02 and abs(fh - 0.22) < 0.02, (st, fw, fh)


@pytest.mark.parametrize("rot", [90, 180, 270])
@pytest.mark.parametrize("st,kw,exp,t_exp,d_exp",
                         [c for c in _CASES if c[0] != "rect"])
def test_rotation_keeps_disc_count(st, kw, exp, t_exp, d_exp, rot):
    """Xoay 4 góc: số đĩa không đổi, đường kính không đổi."""
    fig, ax, sec, meta = _render(st, kw, rot=rot)
    try:
        circs = [p for p in ax.patches
                 if isinstance(p, mpatches.Circle)]
        assert len(circs) == exp, (st, rot, len(circs))
        assert all(abs(p.radius * 2.0 - d_exp) < 1e-9 for p in circs)
    finally:
        plt.close(fig)


@pytest.mark.parametrize("s,exp_map", sorted(_S_EXP.items()))
def test_bar_counts_by_spacing_unchanged(s, exp_map):
    """Chỉ đổi vẽ: số thanh T/L/C/U theo s vẫn khớp web."""
    kw_map = {c[0]: c[1] for c in _CASES}
    conc, steel = _mat()
    for st, exp in exp_map.items():
        sec, meta = build_wall_section(_mk(st, kw_map[st], s=s),
                                       conc, steel)
        assert len(sec.rebars) == exp, (s, st, len(sec.rebars), exp)


def test_numbers_unchanged():
    """Số không đổi: thép 30/48/45/44/82/66, Ac khớp lát trước."""
    conc, steel = _mat()
    ac_exp = {"barbell": 1530000.0, "tee": 1110000.0, "ell": 1050000.0,
              "c-core": 1800000.0, "u-core": 1620000.0}
    for st, kw, exp, _t, _d in _CASES:
        sec, meta = build_wall_section(_mk(st, kw), conc, steel)
        assert len(sec.rebars) == exp, (st, len(sec.rebars))
        if st != "rect":
            assert abs(meta["poly_ac"] - ac_exp[st]) < 1.0, (st, meta["poly_ac"])
