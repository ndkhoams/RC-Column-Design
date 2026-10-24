"""Canh bao matplotlib 'Ignoring fixed y/x limits...' tren console
khi chay app (user paste 2026-10-24, 3 lan): warning nay la LOG cua
matplotlib (khong phai warnings.warn), phat ra tu
Axes.apply_aspect khi adjustable='datalim' phai viet lai lims co
dinh de giu ti le that. Goc: ti le hop axes khac ti le span (pad
9px o figsize khoi tao; canvas bi keo cao/thap hon need o tab Ket
qua; bbox_inches='tight' o anh PDF) nen MOI lan ve lai lims la
warning 1 lan. Sua: draw_wall_section_ax + fallback PNG dung
adjustable='box' (co hop ve ti le span, khong dung lims) + span
khong phan doan phu day hang DIM tong Lw (nhanh cu -1.21cy lam
nhan Lw tran khoi figure). Test headless (Agg), bat log that.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_input import WallInput
from rc_column.wall_section import build_wall_section
from gui.wall_mixin import (_wall_section_axes_pos, _wall_section_figsize,
                            _wall_section_spans, draw_wall_section_ax)


class _Cap(logging.Handler):
    def __init__(self):
        super().__init__()
        self.msgs = []

    def emit(self, record):
        try:
            msg = record.getMessage()
        except Exception:
            msg = ""
        if "Ignoring fixed" in msg:
            self.msgs.append(msg)


def _sec(mode):
    conc = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
    w = WallInput(sw_steel_grade="CB400-V")
    w.steel_mode = mode
    return build_wall_section(w, conc, steel)


def _draw(mode, figsize, rot):
    sec, meta = _sec(mode)
    nseg = len((meta or {}).get("dim_segments") or [])
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111)
    draw_wall_section_ax(ax, sec, meta=meta, rot_deg=rot)
    _wall_section_axes_pos(fig, ax)
    cap = _Cap()
    root = logging.getLogger()
    root.addHandler(cap)
    try:
        fig.canvas.draw()
    finally:
        root.removeHandler(cap)
    out = {"fig": fig, "ax": ax, "msgs": cap.msgs,
           "span": _wall_section_spans(sec, nseg, rot)}
    return out


def test_aspect_is_box_not_datalim():
    d = _draw("boundary", (5.5, 3.2), 0)
    try:
        assert d["ax"].get_adjustable() == "box"
    finally:
        plt.close(d["fig"])


def test_no_fixed_limits_warning_all_geometries():
    """Moi lan ve lai lims truoc day warning 1 lan; sau sua = 0 o
    moi che do thep, xoay 0/90, home/keo cao/kep thap."""
    for mode in ("perimeter", "boundary"):
        sec, meta = _sec(mode)
        nseg = len((meta or {}).get("dim_segments") or [])
        fw0, fh0 = _wall_section_figsize(sec, nseg, 0)
        fw90, fh90 = _wall_section_figsize(sec, nseg, 90)
        for figsize, rot in (((fw0, fh0), 0), ((fw90, fh90), 90),
                             ((fw0, fh0 * 1.6), 0),
                             ((fw0, fh0 * 0.55), 0)):
            d = _draw(mode, figsize, rot)
            try:
                assert d["msgs"] == [], (mode, figsize, rot, d["msgs"])
                # Lims giu nguyen span (box khong viet lai lims).
                assert d["ax"].get_xlim() == (
                    d["span"][0], d["span"][1])
                assert d["ax"].get_ylim() == (
                    d["span"][2], d["span"][3])
            finally:
                plt.close(d["fig"])


def test_spans_cover_lw_dim_both_modes():
    """Day span phu day chu Lw (-cy/2 - 2.22cy) o ca 2 che do;
    nhanh cu khong phan doan (-1.21cy) lam nhan tran khoi figure."""
    for mode in ("perimeter", "boundary"):
        sec, meta = _sec(mode)
        nseg = len((meta or {}).get("dim_segments") or [])
        cy = float(sec.cy)
        x_lo, x_hi, y_lo, y_hi = _wall_section_spans(sec, nseg, 0)
        assert y_lo == -cy / 2 - 2.29 * cy
        # Ve that: moi text deu trong figure.
        fw, fh = _wall_section_figsize(sec, nseg, 0)
        d = _draw(mode, (fw, fh), 0)
        try:
            fb = d["fig"].bbox
            for t in d["ax"].texts:
                we = t.get_window_extent()
                assert we.y0 >= -0.5 and we.y1 <= fb.height + 0.5 \
                    and we.x0 >= -0.5 and we.x1 <= fb.width + 0.5, \
                    (mode, t.get_text(), we)
        finally:
            plt.close(d["fig"])


def test_wall_pdf_pngs_no_warning():
    """Anh mat cat PDF (duong chinh + fallback) khong warning."""
    from rc_column.wall_engine import wall_tcvn_full
    from rc_column.wall_pdf_figs import (_fallback_section_png,
                                         wall_section_png)
    conc = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
    full = wall_tcvn_full(
        WallInput(sw_steel_grade="CB400-V"), conc, steel,
        loads={"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
               "V_in": 800.0, "V_out": 300.0, "T": 0.0},
        seismic_shear=True)
    sec, meta = _sec("perimeter")
    cap = _Cap()
    root = logging.getLogger()
    root.addHandler(cap)
    try:
        png = wall_section_png(full, width_in=5.5, dpi=200)
        png2 = _fallback_section_png(sec, meta, None, 0, 5.5, 200)
    finally:
        root.removeHandler(cap)
    assert cap.msgs == [], cap.msgs
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 1000
    assert png2[:8] == b"\x89PNG\r\n\x1a\n" and len(png2) > 1000
