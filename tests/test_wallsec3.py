"""Lat 3 (2026-10-27): o nut giao cho thep doc T/L/C/U.

Quy tac (suy tu du lieu web Vietcons, khong phai cong thuc web
cong bo; da kiem chung khop bang web theo s va theo kich thuoc):
- Moi doan giao = 1 o = giao cua 2 dai lui trong, canh o =
  t - 2*inset (app inset = c_dai + dia_h + d/2; vd T t=300,
  inset 43 -> canh o 214 mm, KHONG hardcode 238 mm cua web vi
  web lui c + d/2 = 31 mm).
- Chu vi chia doan tai bien o (moi doan chia rieng bang
  ceil(len/s)); moi canh o chia ceil(len/s) khoang, thanh trung
  gian GIU ca khi nam trong tiet dien; trung toa do chi tinh 1.
- Barbell KHONG co o (giu nguyen lat 1); vach phang khong doi.
- CHECK N-M/cat cho loai moi van CHAN nhu lat 1 (lat nay chi
  sua thep) — test nay khong mo CHECK.

Luu y cover: o nhap app la c_dai (toi mat ngoai cot dai), web
la c toi thep doc. Nen hang cover cua bang web chi tuong duong
khi inset bang nhau: app cover 28 (inset 46) = web cover 40
(inset 46) -> T 45 / C 82. App cover 40 (inset 58) cho T 38 /
C 68 theo DUNG quy tac (canh o 184 mm, ceil 1 khoang) — day
khong phai lech web, ma la he qua cua quy uoc cover app.
Test khoa ca 2 truong hop de khong ai "sua" ve 45/82 bang cach
pha quy uoc cover.

Khong bao gom bang s cua Barbell: Barbell ngoai pham vi lat
nay va quy tac lam tron canh dai cua web o s != 200 (vd canh
938 mm o s=150 web dung 6 khoang, khong phai ceil 7) chua duoc
xac dinh — khong doi Barbell de ep bang do.
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
from rc_column.wall_section import (_node_boxes_poly,
                                    _point_in_poly, build_wall_section,
                                    wall_readouts)
from gui.wall_mixin import (_wall_section_figsize, draw_wall_section_ax)

# (loai, kwargs mac dinh, so thanh web theo s, As web s200, mu web)
_S = [
    ("tee", dict(Lw=2500, sec_bf=1500, sec_t=300),
     {100: 86, 150: 57, 200: 45, 300: 28}, 5089, 0.0046),
    ("ell", dict(sec_L1=2000, sec_L2=1800, sec_t=300),
     {100: 80, 150: 54, 200: 44, 300: 26}, 4976, 0.0047),
    ("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600, sec_t=300),
     {100: 148, 150: 98, 200: 82, 300: 48}, 9274, 0.0052),
    ("u-core", dict(Lw=3000, sec_bf=1500, sec_t=300),
     {100: 124, 150: 82, 200: 66, 300: 40}, 7464, 0.0046),
]

# (loai, kwargs mac dinh, (thuoc tinh, gia tri moi, so thanh web))
_VARS = [
    ("tee", dict(Lw=2500, sec_bf=1500, sec_t=300),
     [("sec_bf", 2000, 53), ("Lw", 3000, 51), ("sec_t", 400, 45)]),
    ("ell", dict(sec_L1=2000, sec_L2=1800, sec_t=300),
     [("sec_L1", 2500, 48), ("sec_L2", 2200, 48)]),
    ("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600, sec_t=300),
     [("sec_bf", 2000, 94), ("sec_lr", 900, 86)]),
    ("u-core", dict(Lw=3000, sec_bf=1500, sec_t=300),
     [("sec_bf", 2000, 78), ("Lw", 3500, 70)]),
]


def _mat():
    conc = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
    return conc, steel


def _mk(st, kw, s=200, cover=25, sym=True):
    w = WallInput(section_type=st, cover=cover, dia_h=12,
                  per_dia=12, per_s=s, sec_sym=sym)
    for k, v in kw.items():
        setattr(w, k, v)
    return w


def _pts(sec):
    return {(round(r.x, 6), round(r.y, 6)) for r in sec.rebars}


@pytest.mark.parametrize("st,kw,by_s,as_web,mu_web", _S)
@pytest.mark.parametrize("s", [100, 150, 200, 300])
def test_node_box_counts_by_spacing(st, kw, by_s, as_web, mu_web, s):
    """So thanh theo s khop web ca 4 muc s (ceil cho ca chu vi
    chia doan va canh o — khong dung round/floor)."""
    conc, steel = _mat()
    sec, meta = build_wall_section(_mk(st, kw, s=s), conc, steel)
    assert len(sec.rebars) == by_s[s], (st, s, len(sec.rebars))
    if s == 200:
        assert abs(sec.steel_area - as_web) < 1.0
        r = wall_readouts(_mk(st, kw, s=s), sec, meta)
        assert abs(r["mu"] - mu_web) < 0.0002, (st, r["mu"])
    # Khong trung toa do; moi thanh nam trong polygon goc.
    assert len(_pts(sec)) == len(sec.rebars)
    verts = sec.poly_verts[0]
    for rb in sec.rebars:
        assert _point_in_poly(rb.x, rb.y, verts), (st, s, rb.x, rb.y)


@pytest.mark.parametrize("st,kw,vs", _VARS)
def test_node_box_counts_by_dimension(st, kw, vs):
    """Doi 1 kich thuoc o s=200: so thanh tang chu yeu do chu vi
    dai hon, so thanh gia cuong moi o khong doi."""
    conc, steel = _mat()
    for attr, val, n_web in vs:
        w = _mk(st, kw)
        setattr(w, attr, val)
        sec, meta = build_wall_section(w, conc, steel)
        assert len(sec.rebars) == n_web, (st, attr, val,
                                          len(sec.rebars))


def test_node_box_geometry_and_positions():
    """So o + toa do o: T 1 o, L 1 o, C 4 o, U 2 o, Barbell 0 o.
    Canh o app = t - 2*inset = 214 mm (khong phai 238 mm web)."""
    conc, steel = _mat()
    cases = [
        ("tee", dict(Lw=2500, sec_bf=1500, sec_t=300),
         [(-1207.0, -993.0, -107.0, 107.0)]),
        ("ell", dict(sec_L1=2000, sec_L2=1800, sec_t=300),
         [(-957.0, -743.0, -857.0, -643.0)]),
        ("u-core", dict(Lw=3000, sec_bf=1500, sec_t=300),
         [(-707.0, -493.0, -1457.0, -1243.0),
          (-707.0, -493.0, 1243.0, 1457.0)]),
        ("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600, sec_t=300),
         [(-707.0, -493.0, -1457.0, -1243.0),
          (-707.0, -493.0, 1243.0, 1457.0),
          (493.0, 707.0, -1457.0, -1243.0),
          (493.0, 707.0, 1243.0, 1457.0)]),
    ]
    for st, kw, boxes in cases:
        w = _mk(st, kw)
        assert _node_boxes_poly(w, 43.0) == boxes, (st, _node_boxes_poly(w, 43.0))
        sec, meta = build_wall_section(w, conc, steel)
        assert meta["node_boxes"] == boxes
        assert meta["n_node_extra"] == len(sec.rebars) - meta["n_perimeter_only"]
    # Barbell: khong o, so thanh khong doi lat 1.
    w = _mk("barbell", dict(Lw=3000, tw=300, sec_bf=1000, sec_tf=450))
    assert _node_boxes_poly(w, 43.0) == []
    sec, meta = build_wall_section(w, conc, steel)
    assert meta["node_boxes"] == [] and len(sec.rebars) == 48


def test_tee_box_intermediates_present_at_s200_absent_at_s300():
    """O T s200: 4 thanh trung gian o ton tai (2 tren canh ngang
    o, 1 tren canh dung trai, 1 tren canh dung phai — ca 4 nam
    trong tiet dien, khong nam tren chu vi). O s300: canh o
    214 mm chi 1 khoang -> khong con trung gian, nhung 2 goc
    trong (-1207, +/-107) van ton tai."""
    conc, steel = _mat()
    kw = dict(Lw=2500, sec_bf=1500, sec_t=300)
    # Lát N–M (2026-10-27): thép dịch về khung trọng tâm nên
    # tọa độ tuyệt đối = tọa độ bbox cũ trừ centroid_offset
    # (Tee: gx = -356.757, gy = 0); số thanh/vị trí tương đối
    # không đổi, chỉ đổi khung. Điểm kỳ vọng tính từ offset
    # của meta thay vì hardcode khung mới.
    sec, meta = build_wall_section(_mk("tee", kw, s=200), conc, steel)
    _gx, _gy = meta["centroid_offset"]

    def _sh(p):
        return (round(p[0] - _gx, 6), round(p[1] - _gy, 6))

    pts = _pts(sec)
    for p in [(-1100.0, 107.0), (-1100.0, -107.0),
              (-1207.0, 0.0), (-993.0, 0.0),
              (-1207.0, 107.0), (-1207.0, -107.0)]:
        assert _sh(p) in pts, ("s200 thieu thanh o", p, _sh(p))
    sec, meta = build_wall_section(_mk("tee", kw, s=300), conc, steel)
    _gx, _gy = meta["centroid_offset"]
    pts = _pts(sec)
    for p in [(-1100.0, 107.0), (-1100.0, -107.0),
              (-1207.0, 0.0), (-993.0, 0.0)]:
        assert _sh(p) not in pts, ("s300 con trung gian o", p)
    for p in [(-1207.0, 107.0), (-1207.0, -107.0)]:
        assert _sh(p) in pts, ("s300 thieu goc trong o", p)


def test_cover_equivalence_web_vs_app():
    """App cover 28 (inset 46) = web cover 40 -> T 45 / C 82.
    App cover 40 (inset 58) -> T 38 / C 68 theo dung quy tac
    (khong phai lech web — xem docstring dau file)."""
    conc, steel = _mat()
    for st, kw, n28, n40 in [
            ("tee", dict(Lw=2500, sec_bf=1500, sec_t=300), 45, 38),
            ("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600, sec_t=300),
             82, 68)]:
        sec, _ = build_wall_section(_mk(st, kw, cover=28), conc, steel)
        assert len(sec.rebars) == n28, (st, "cover28", len(sec.rebars))
        sec, _ = build_wall_section(_mk(st, kw, cover=40), conc, steel)
        assert len(sec.rebars) == n40, (st, "cover40", len(sec.rebars))


def test_asymmetric_c_return_box_uses_side2():
    """C khong doi xung: o hoi duoi dung Bf2/Lr2 (cx = max/2)."""
    conc, steel = _mat()
    w = _mk("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600, sec_t=300),
            sym=False)
    w.sec_bf2 = 1200
    w.sec_lr2 = 500
    sec, meta = build_wall_section(w, conc, steel)
    assert len(meta["node_boxes"]) == 4
    # O hoi duoi: [1200-300-750+43, 1200-750-43] x [y0+43, y0+300-43].
    assert (193.0, 407.0, -1457.0, -1243.0) in meta["node_boxes"]
    assert len(_pts(sec)) == len(sec.rebars)


def test_poly_draw_with_node_boxes():
    """Ve preview T/C co o nut giao (Agg): khong loi, nhan dim
    tong dung, so thanh dung so da khoa."""
    conc, steel = _mat()
    for st, kw, n in [("tee", dict(Lw=2500, sec_bf=1500, sec_t=300), 45),
                      ("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600,
                                      sec_t=300), 82)]:
        w = _mk(st, kw)
        sec, meta = build_wall_section(w, conc, steel)
        assert len(sec.rebars) == n
        fw, fh = _wall_section_figsize(sec, len(meta["dim_segments"]), 0)
        fig, ax = plt.subplots(figsize=(fw, fh))
        draw_wall_section_ax(ax, sec, meta=meta, rot_deg=0)
        fig.canvas.draw()
        labels = [t.get_text() for t in ax.texts]
        assert meta["dim_total_x_label"] in labels
        assert meta["dim_total_y_label"] in labels
        plt.close(fig)
