"""Test quy ước lớp bảo vệ mới (user chốt 2026-10-24).

Ô nhập cover = lớp bảo vệ cốt đai c (tới mặt ngoài cốt đai); engine
tự tính c_dọc = c + d_đai; tâm cốt dọc cách mép = c + d_đai + d_dọc/2.

- Cột: d_đai = sw_dia (đai bao). Vách: d_đai = dia_h thống nhất.
- Migration file cũ (nghĩa tới mặt cốt dọc): c' = c − d_đai, giữ
  nguyên fiber; cắt h0/d tăng đúng d_đai (số cắt cũ bảo thủ hơn).
- Bỏ qua DXF; c' < 0 kẹp 0 + cảnh báo.
"""

import copy
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rc_column.checker import ColumnInput, build_section
from rc_column.cover_migration import (
    cover_long, migrate_column_dict, migrate_wall_dict)
from rc_column.ec2_materials import EC2Concrete, EC2Steel
from rc_column.ec2_pdf_summary import _slenderness_ec2
from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.sections import (layout_circle_bars, layout_rect_bars,
                                layout_vietconsoft_bars,
                                make_circle_section, make_rect_section)
from rc_column.stirrup import compute_shear_cols
from rc_column.wall_input import WallInput, wall_from_dict
from rc_column.wall_section import build_wall_section


# ---------------------------------------------------------------- cột
def test_rect_layout_center_offset():
    """Tim thép chữ nhật cách mép = c + sw_dia + dia/2."""
    sec = make_rect_section(400.0, 400.0, None, None)
    layout_rect_bars(sec, 20.0, 3, 3, 22.0, sw_dia=8.0)
    corner = max(sec.rebars, key=lambda r: abs(r.x) + abs(r.y))
    assert abs(200.0 - abs(corner.x) - 40.0) < 1e-9  # 22+8+10
    assert abs(200.0 - abs(corner.y) - 40.0) < 1e-9
    # Tương thích ngược: test cũ gọi không sw_dia -> như công thức cũ.
    sec0 = make_rect_section(400.0, 400.0, None, None)
    layout_rect_bars(sec0, 20.0, 3, 3, 30.0)
    c0 = max(sec0.rebars, key=lambda r: abs(r.x) + abs(r.y))
    assert abs(200.0 - abs(c0.x) - 40.0) < 1e-9  # 30+0+10


def test_circle_layout_radius():
    """Vòng thép tròn: r = D/2 − c − sw_dia − dia/2."""
    sec = make_circle_section(600.0, None, None)
    layout_circle_bars(sec, 20.0, 8, 22.0, sw_dia=8.0)
    for r in sec.rebars:
        assert abs(math.hypot(r.x, r.y) - 260.0) < 1e-9  # 300-22-8-10


def _viet_inp(**kw):
    base = dict(section_type="rect", cx=400.0, cy=400.0, cover=22.0,
                sw_dia=8.0, corner_dia=20.0,
                edge_t2_count=3, edge_t2_dia=20.0,
                edge_t3_count=3, edge_t3_dia=20.0, two_layer=False)
    base.update(kw)
    return ColumnInput(**base)


def test_vietconsoft_layer1_and_layer2_offsets():
    """Lớp 1: c+sw+d/2; lớp 2 perimeter: c+sw+d1+s+d2/2."""
    sec = build_section(_viet_inp(two_layer=True, layer2_mode="perimeter"))
    l1 = [r for r in sec.rebars if r.layer == 1]
    l2 = [r for r in sec.rebars if r.layer == 2]
    # Góc lớp 1: tim cách mép 22+8+10 = 40.
    assert abs(max(abs(r.x) for r in l1) - 160.0) < 1e-9
    # Góc lớp 2: 22+8+20+30+10 = 90 -> |x| = 110.
    assert abs(max(abs(r.x) for r in l2) - 110.0) < 1e-9


def test_vietconsoft_bundled_outer_follows_layer1():
    """Bundled 'outer' đặt quanh vị trí lớp 1 -> cùng offset lớp 1."""
    sec = build_section(_viet_inp(two_layer=True, layer2_mode="bundled",
                                  bundle_pos="outer", bundle_corner=2,
                                  bundle_gap=0.0))
    # Bó góc: 2 thanh xếp ngang quanh x = ±160 (tim lớp 1), dia 20:
    # x = 160 ± 10 -> max |x| = 170, và tâm bó vẫn tại 160.
    xs = sorted(abs(r.x) for r in sec.rebars if r.layer == 2)
    assert abs(max(xs) - 170.0) < 1e-9


def test_column_migration_preserves_fiber_and_raises_shear_h0():
    """File cũ cover 30/sw 8 -> migration 22: fiber y hệt, h0 +8.

    Tham chiếu "engine cũ" = cùng input nhưng sw_dia=0 (engine cũ
    không cộng đai nên tim = cover + d/2 = 30+10 = 40 — đúng offset
    của input đã migration 22+8+10 = 40).
    """
    ref = _viet_inp(cover=30.0, sw_dia=0.0, cx=600.0, cy=600.0)
    sec_ref = build_section(ref)
    off_ref = sorted({round(300.0 - abs(r.x), 6) for r in sec_ref.rebars})
    mig = _viet_inp(cover=22.0, cx=600.0, cy=600.0)
    sec_mig = build_section(mig)
    off_mig = sorted({round(300.0 - abs(r.x), 6) for r in sec_mig.rebars})
    assert off_ref == off_mig
    # Cắt: công thức không đổi, chỉ đầu vào đổi nghĩa -> h0 + sw_dia.
    old = _viet_inp(cover=30.0, cx=600.0, cy=600.0)
    sec_old = build_section(old)
    h_old = compute_shear_cols(old, sec_old)["2"]["h0"]
    h_mig = compute_shear_cols(mig, sec_mig)["2"]["h0"]
    assert abs(h_old - 550.0) < 1e-9   # 600-30-8-12 (số hạng thép 12 cứng)
    assert abs(h_mig - 558.0) < 1e-9   # 600-22-8-12
    assert abs(h_mig - h_old - 8.0) < 1e-9


# ---------------------------------------------------------------- vách
_CONC = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
_STEEL = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)


def test_wall_perimeter_inset():
    """Chu vi: inset = c + dia_h + d/2 cả 2 trục (mẫu migration 13/12/12)."""
    w = WallInput(cover=13.0, dia_h=12.0)
    sec, _ = build_wall_section(w, _CONC, _STEEL)
    xs = [r.x for r in sec.rebars]
    ys = [r.y for r in sec.rebars]
    assert abs(min(xs) - (-1250.0 + 31.0)) < 1e-9   # 13+12+6
    assert abs(min(ys) - (-175.0 + 31.0)) < 1e-9


def test_wall_boundary_insets():
    """Biên: inset_b = c+dia_h+db/2; thân: g = c+dia_h+wd/2,
    y_v = tw/2 − c − dia_h − wd/2."""
    w = WallInput(steel_mode="boundary", cover=13.0, dia_h=12.0,
                  be_dia=20.0, web_dia=12.0)
    sec, meta = build_wall_section(w, _CONC, _STEEL)
    be = meta["bars_be_left"]
    assert abs(min(p[0] for p in be) - (-1250.0 + 35.0)) < 1e-9  # 13+12+10
    web = meta["bars_web"]
    assert abs(min(p[0] for p in web) - (-750.0 + 31.0)) < 1e-9  # a+g
    assert abs(max(p[1] for p in web) - 144.0) < 1e-9  # 175-13-12-6


def test_wall_legacy_c6_gains_dia_h_c5_unchanged():
    """Legacy: thân theo Lw (C6) cộng dia_h; thép biên C5 giữ nguyên."""
    w = WallInput(steel_mode="legacy", cover=25.0, dia_h=12.0, dia_v=12.0,
                  dia_be=28.0, tie_dia_be=10.0, Lb_left=500.0,
                  Lb_right=500.0, n_be=8, s_v=200.0, layers_v=2)
    sec, meta = build_wall_section(w, _CONC, _STEEL)
    web = meta["bars_web"]
    assert abs(min(p[0] for p in web) - (-750.0 + 43.0)) < 1e-9  # 25+12+6
    assert abs(max(p[1] for p in web) - 132.0) < 1e-9  # 175-25-12-6
    be = meta["bars_be_left"]
    assert abs(max(p[1] for p in be) - 126.0) < 1e-9  # 175-25-10-14 (C5)


# ------------------------------------------------------------ migration
def test_migrate_column_both_keys_and_fallback():
    d, warns = migrate_column_dict({"version": 1, "cover": "30",
                                    "ccover": "30", "sw_dia": "8"})
    assert d["cover"] == 22 and d["ccover"] == 22 and warns == []
    # Thiếu sw_dia -> fallback 8 mm.
    d, _ = migrate_column_dict({"version": 1, "cover": 30})
    assert d["cover"] == 22
    # Đã có dấu mới -> giữ nguyên, không trừ lần 2.
    d, _ = migrate_column_dict({"version": 1, "cover_semantics": "stirrup",
                                "cover": 22, "sw_dia": 8})
    assert d["cover"] == 22
    # Không đổi dict gốc.
    src = {"version": 1, "cover": 30, "sw_dia": 8}
    migrate_column_dict(src)
    assert src["cover"] == 30


def test_migrate_column_dxf_skipped_and_negative_clamped_with_warning():
    d, warns = migrate_column_dict({"version": 1,
                                    "kind": "Tiết diện bất kỳ (DXF)",
                                    "cover": 30, "sw_dia": 8})
    assert d["cover"] == 30 and warns == []
    d, warns = migrate_column_dict({"version": 1, "cover": 15, "sw_dia": 16})
    assert d["cover"] == 0 and len(warns) == 1


def test_migrate_wall_and_negative_clamped_with_warning():
    d, warns = migrate_wall_dict({"cover": 25, "dia_h": 12})
    assert d["cover"] == 13 and warns == []  # preset web 25 -> 13
    d, warns = migrate_wall_dict({"cover": 10, "dia_h": 12})
    assert d["cover"] == 0 and len(warns) == 1
    d, _ = migrate_wall_dict({"cover_semantics": "stirrup", "cover": 13,
                              "dia_h": 12})
    assert d["cover"] == 13


def test_cover_long_values():
    assert cover_long(22.0, 8.0) == 30.0
    assert cover_long(13.0, 12.0) == 25.0


# ------------------------------------------------------- B11 + hiển thị
def test_slenderness_ec2_fallback_counts_sw_dia():
    """B11: d fallback = h − cover − sw_dia − 12 (chứng minh bằng cặp
    (cover, sw_dia) cho cùng d: (40, 8) == (48, 0))."""
    inp = ColumnInput(cx=400.0, cy=400.0, cover=40.0, sw_dia=8.0,
                      N=1500.0, Mx=120.0, My=200.0, Lx=4.0, Ly=4.0,
                      top_x="ngam", bottom_x="ngam",
                      top_y="ngam", bottom_y="ngam")
    sec = build_section(inp)
    conc = EC2Concrete(30.0)
    steel = EC2Steel(500.0)
    r1 = _slenderness_ec2(sec, conc, steel, inp)
    assert r1 and "dir2" in r1 and "dir3" in r1
    inp2 = copy.copy(inp)
    inp2.cover = 48.0
    inp2.sw_dia = 0.0
    r2 = _slenderness_ec2(sec, conc, steel, inp2)
    assert r1 == r2


def test_wall_detail_prints_both_covers():
    """Tab Chi tiết vách in cả c (đai) và c_dọc = c + dia_h."""
    from rc_column.wall_detail import build_wall_detail_sections
    from rc_column.wall_engine import wall_tcvn_full
    w = WallInput(cover=13.0, dia_h=12.0)
    full = wall_tcvn_full(w, _CONC, _STEEL,
                          loads={"N": 2528.65, "M_in": 202.86,
                                 "M_out": 275.23, "V_in": 800.0,
                                 "V_out": 0.0, "T": 0.0})
    txt_parts = []
    for s in build_wall_detail_sections(full):
        txt_parts.append(s["title"])
        for c in s["cards"]:
            txt_parts.append(c.get("title", ""))
            txt_parts.extend(c.get("lines", []))
            txt_parts.append(c.get("result", ""))
    txt = "\n".join(txt_parts)
    assert "Lớp bảo vệ cốt đai, c = 13 mm" in txt
    assert "c_dọc = c + dia_h = 25 mm" in txt


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
    print("TẤT CẢ TEST COVER PASS")
