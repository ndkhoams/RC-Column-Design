"""Lát N–M cho 5 loại tiết diện vách mới (2026-10-27).

Khung tính (ghi ở wall_engine.py, nhánh đa giác):
- Tải N/M hiểu tại trọng tâm tiết diện nguyên; tiết diện dịch về
  trọng tâm ở _build_wall_section_poly nên solver, Ix/Iy, Is, vùng
  nén, biểu đồ cùng khung (không còn khung bbox).
- Trục trong MP: barbell/tee/ell = x (Lw/L1), c-core/u-core = y
  (thân Lw); rot 90/270° hoán đổi trục. Ánh xạ solver: trục 'x' ->
  M_in ↔ My, M_out ↔ Mx (như phẳng); trục 'y' -> M_in ↔ Mx,
  M_out ↔ My. Đây là quy ước ánh xạ của app, không phải điều khoản
  TCVN (TCVN không định nghĩa trong/ngoài MP cho lõi C/U).
- λ = L0/i với i = √(I/A) quanh trọng tâm (không h/√12); cổng
  η λ > 14 TCVN §8.1.2.1.2 giữ nguyên từng phương; ea theo
  §8.1.2.2.4 với c = bề rộng bbox đã xoay theo phương uốn (giả định
  tương đương, phía bảo thủ — chuẩn chỉ viết c cho chữ nhật).
- Cắt cho loại mới đã xong ở lát cắt (C/U ngoài MP vẫn pending —
  xem test_wallshear_poly); PDF cho loại mới vẫn chặn (lát sau).

Kiểm chứng:
(a) vách phẳng + VACH không đổi (0.44520 / 0.463114 / ca ảnh
    0.291393 — cột 0.62488/0.61061/0.45746 do suite cũ khóa).
(b) mỗi loại: thuần nén (D/C ≈ N/Ncap, Ncap = Rb·Ac + Rsc·As),
    thuần uốn 1 phương (D/C ≈ M/Mcap tại N = 0), song trục
    (B nằm trên bao: moment_capacity(BN, α) ≈ |B|, hướng B ≈ α).
(c) xoay 90° + xoay tải theo -> D/C không đổi.
(d) JSON round-trip + detail/shear-rows/draw không crash, cắt
    đã tính (lát cắt) — PDF vẫn chặn ở lát sau.
Thép/Ac đã khóa ở lát thép (48/45/44/82/66) không kiểm lại ở đây
ngoài As dùng cho Ncap (đọc từ sec, không hardcode).
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from rc_column.interaction import BiaxialCapacity
from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_input import (WallInput, wall_from_dict,
                                  wall_to_dict)
from rc_column.wall_section import build_wall_section
from rc_column.wall_detail import build_wall_detail_sections
from gui.wall_mixin import build_wall_shear_rows, draw_wall_section_ax

_CONC = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
_STEEL = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)

# (loại, kwargs mặc định web, N/M song trục)
_CASES = [
    ("barbell", dict(Lw=3000, tw=300, sec_bf=1000, sec_tf=450),
     3000.0, 1500.0, 300.0),
    ("tee", dict(Lw=2500, sec_bf=1500, sec_t=300),
     2000.0, 800.0, 200.0),
    ("ell", dict(sec_L1=2000, sec_L2=1800, sec_t=300),
     2000.0, 700.0, 500.0),
    ("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600, sec_t=300),
     3000.0, 1000.0, 600.0),
    ("u-core", dict(Lw=3000, sec_bf=1500, sec_t=300),
     3000.0, 1200.0, 400.0),
]


def _mk(st, kw, rot=0):
    w = WallInput(section_type=st, cover=28, dia_h=12,
                  per_dia=12, per_s=200, rot_deg=rot)
    for k, v in kw.items():
        setattr(w, k, v)
    return w


def _loads(N, Mi, Mo):
    return {"N": N, "M_in": Mi, "M_out": Mo,
            "V_in": 0.0, "V_out": 0.0, "T": 0.0}


def _dist_to_polyline(px, py, xs, ys):
    best = float("inf")
    for i in range(len(xs) - 1):
        x1, y1, x2, y2 = xs[i], ys[i], xs[i + 1], ys[i + 1]
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - x1) * dx
                                                 + (py - y1) * dy) / L2))
        best = min(best, math.hypot(px - (x1 + t * dx),
                                    py - (y1 + t * dy)))
    return best


def _biaxial_check(full, tol=0.005):
    """B nằm trên bao M2–M3 tại BN (dict m2m3 đã tính 1 lần),
    đúng hướng α (khung solver); D/C tia = Malpha/|B|."""
    m = full["m2m3"]
    bx, by = float(m["B_M2"]), float(m["B_M3"])
    bmag = math.hypot(bx, by)
    assert bmag > 0, "B suy biến"
    # Polyline lưu theo cặp (M3, M2) nên điểm B phải đổi về
    # cùng khung (x = M3, y = M2); dùng (B_M2, B_M3) thẳng sẽ
    # đo sai (lệch 67% ở ca Barbell) dù B đúng trên bao thật.
    d = _dist_to_polyline(by, bx, m["M3"], m["M2"])
    assert d / bmag <= tol, (d, bmag)
    ang = math.degrees(math.atan2(bx, by)) % 360.0
    dd = abs((ang - full["alpha_deg"] + 180.0) % 360.0 - 180.0)
    assert dd <= 1.0, (ang, full["alpha_deg"])
    assert abs(full["dc"] - full["Malpha"] / bmag) <= 0.02, \
        (full["dc"], full["Malpha"] / bmag)


# ---------------- (a) mốc phẳng không đổi ----------------

def test_flat_locks_unchanged():
    f = wall_tcvn_full(WallInput(cover=13.0), _CONC, _STEEL,
                       loads={"N": 2528.65, "M_in": 202.86,
                              "M_out": 275.23, "V_in": 0.0,
                              "V_out": 0.0, "T": 0.0})
    assert abs(f["dc"] - 0.44520104645817127) < 1e-9


def test_vach_lock_unchanged():
    w = WallInput(Lw=2500.0, tw=350.0, cover=13.0, dia_h=12.0,
                  s_h=200.0, layers_h=2, sw_steel_grade="CB400-V",
                  steel_mode="boundary", be_Lb=500.0, be_dia=28.0,
                  be_n_Lb=4, be_n_tw=0, be_L_out=1, be_L_in=0,
                  web_dia=12.0, web_s=200.0,
                  Lx_m=3.3, Ly_m=3.3, psi_x=1.0, psi_y=1.0,
                  seismic_on=True)
    f = wall_tcvn_full(w, ConcreteMaterial(CONCRETE_GRADES["B25"],
                                           0.85),
                       SteelMaterial(STEEL_GRADES["CB400-V"], 1.0),
                       loads={"N": 2500.0, "M_in": 3000.0,
                              "M_out": 60.0, "V_in": 800.0,
                              "V_out": 0.0, "T": 0.0},
                       seismic_shear=True)
    assert abs(f["dc"] - 0.463114) < 0.0005


# ---------------- (b) 3 ca × loại ----------------

def test_poly_pure_compression():
    for st, kw, _N, _Mi, _Mo in _CASES:
        w = _mk(st, kw)
        N = 4000.0
        f = wall_tcvn_full(w, _CONC, _STEEL, loads=_loads(N, 0.0, 0.0))
        ncap = (_CONC.Rb * f["sec"].gross_area
                + _STEEL.Rsc * f["sec"].steel_area) / 1000.0
        assert abs(f["dc"] - N / ncap) <= 0.01, (st, f["dc"], N / ncap)


def test_poly_pure_bending():
    for st, kw, _N, _Mi, _Mo in _CASES:
        w = _mk(st, kw)
        f = wall_tcvn_full(w, _CONC, _STEEL,
                           loads=_loads(0.0, 800.0, 0.0))
        cap = BiaxialCapacity(f["sec"], model="3line", n_angles=24)
        mc = cap.moment_capacity(0.0, f["alpha_deg"])
        assert mc > 0
        assert abs(f["dc"] - 800.0 / mc) <= 0.02, (st, f["dc"], mc)


def test_poly_biaxial_on_envelope():
    for st, kw, N, Mi, Mo in _CASES:
        w = _mk(st, kw)
        f = wall_tcvn_full(w, _CONC, _STEEL, loads=_loads(N, Mi, Mo))
        assert f["m2m3"]["N_level"] == f["BN"]
        # Lát cắt: trong MP mở cả 5 loại; ngoài MP mở trừ C/U
        # (lõi hở pending — xem test_wallshear_poly).
        assert f["shear_in"]["V_cap"] is not None
        if st in ("c-core", "u-core"):
            assert f["shear_out"]["V_cap"] is None
            assert f["checks_included"] == ["N-M", "shear_in"]
        else:
            assert f["shear_out"]["V_cap"] is not None
            assert f["checks_included"] == ["N-M", "shear_in",
                                            "shear_out"]
        _biaxial_check(f)


def test_poly_centroid_frame_and_inertia():
    """Khung trọng tâm: Ix/Iy của section_inertia = meta poly_Ix/
    Iy; thép/fiber không còn ở khung bbox (trừ loại đối xứng)."""
    for st, kw, _N, _Mi, _Mo in _CASES:
        w = _mk(st, kw)
        sec, meta = build_wall_section(w, _CONC, _STEEL)
        from rc_column.checker import section_inertia
        Ix, Iy, _ix, _iy, _Isx, _Isy = section_inertia(sec)
        assert abs(Ix - meta["poly_Ix"]) < 1.0
        assert abs(Iy - meta["poly_Iy"]) < 1.0
        gx, gy = meta["centroid_offset"]
        if st == "barbell":
            assert gx == 0.0 and gy == 0.0
        else:
            assert abs(gx) + abs(gy) > 10.0, (st, gx, gy)


# ---------------- (c) xoay 90° + xoay tải ----------------

def test_poly_rotation_90_invariance():
    # Xoay cứng (tiết diện + vectơ tải) bảo toàn D/C: ở rot 90°,
    # vectơ solver (Mx, My) -> (-My, Mx); đổi ngược ra (M_in,
    # M_out) theo trục của từng loại (x: M_in' = -M_in,
    # M_out' = M_out; y: M_in' = M_in, M_out' = -M_out).
    for st, kw, N, Mi, Mo in _CASES:
        f0 = wall_tcvn_full(_mk(st, kw), _CONC, _STEEL,
                            loads=_loads(N, Mi, Mo))
        axis_x = st in ("barbell", "tee", "ell")
        if axis_x:
            Mi2, Mo2 = -Mi, Mo
        else:
            Mi2, Mo2 = Mi, -Mo
        f1 = wall_tcvn_full(_mk(st, kw, rot=90), _CONC, _STEEL,
                            loads=_loads(N, Mi2, Mo2))
        assert abs(f1["dc"] - f0["dc"]) <= 1e-6 * max(1.0, f0["dc"]), \
            (st, f0["dc"], f1["dc"])


# ---------------- (d) round-trip + hiển thị ----------------

def test_poly_json_roundtrip_and_render():
    for st, kw, N, Mi, Mo in _CASES:
        w = _mk(st, kw)
        d = wall_to_dict(w)
        w2 = wall_from_dict(d)
        assert w2.section_type == st
        f = wall_tcvn_full(w2, _CONC, _STEEL, loads=_loads(N, Mi, Mo))
        # Thẻ chi tiết + bảng cắt đọc dict, không tính lại, không
        # crash; cắt trong MP hiện số cả 5 loại, ngoài MP hiện số
        # trừ C/U (pending lõi hở).
        secs = build_wall_detail_sections(f)
        assert len(secs) >= 7
        rows = build_wall_shear_rows(f)
        assert all(r[1] != "CHƯA KIỂM" for r in rows)
        if st in ("c-core", "u-core"):
            assert all(r[2] == "CHƯA KIỂM" for r in rows)
        else:
            assert all(r[2] != "CHƯA KIỂM" for r in rows)
        fig, ax = plt.subplots(figsize=(5, 5))
        draw_wall_section_ax(ax, f["sec"], meta=f["meta"],
                             na_info=f["na_info"],
                             show_compression=True, rot_deg=0)
        fig.canvas.draw()
        plt.close(fig)
        # Vùng nén (nếu có) vẽ được ở cả rot 90 qua display path.
        fig, ax = plt.subplots(figsize=(5, 5))
        draw_wall_section_ax(ax, f["sec"], meta=f["meta"],
                             na_info=f["na_info"],
                             show_compression=True, rot_deg=90)
        fig.canvas.draw()
        plt.close(fig)


def test_poly_gui_check_tee_xvfb():
    """GUI (skip khi không có display; chạy dưới Xvfb ở CI/local):
    CHECK vách chữ T nhập tay + TCVN hiện tab Kết quả, cắt hiện số
    cả 2 phương (lát cắt)."""
    try:
        import tkinter as tk
        _r = tk.Tk()
        _r.withdraw()
        _r.destroy()
    except Exception:
        import pytest
        pytest.skip("không có display Tk")
    from gui.app import App
    app = App()
    try:
        app.update_idletasks()
        app.cb_member.set("Vách")
        app._toggle_member()
        app.update_idletasks()
        app.w_cb_sectype.set("Vách chữ T")
        app._on_wall_sectype()
        app.update_idletasks()
        # Mặc định app là nguồn ETABS -> CHECK sẽ chặn ở lát 5
        # (kèm popup chặn test); đường này kiểm nhập tay + TCVN.
        app.var_load_mode.set("manual")

        def _set(entry, val):
            entry.delete(0, "end")
            entry.insert(0, str(val))

        _set(app.en_N, 2000)
        _set(app.en_My, 800)
        _set(app.en_Mx, 200)
        _set(app.en_Q2, 0)
        _set(app.en_Q3, 0)
        app._on_check_wall()
        app.update_idletasks()
        full = getattr(app, "_tcvn_wall_full", None)
        assert full is not None
        assert full["winp"].section_type == "tee"
        assert math.isfinite(full["dc"]) and full["dc"] > 0
        # Lát cắt: Tee mở cả 2 phương (V = 0 nên D/C cắt = 0).
        assert full["shear_in"]["V_cap"] is not None
        assert full["shear_out"]["V_cap"] is not None
        assert getattr(app, "_wall_view_active", False) is True
    finally:
        try:
            app.destroy()
        except Exception:
            pass


def test_poly_cu_detail_symbols():
    """C/U: thẻ chi tiết ghi trong MP = M2 (không ghi M3 như phẳng)."""
    w = _mk("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600,
                           sec_t=300))
    f = wall_tcvn_full(w, _CONC, _STEEL,
                       loads=_loads(3000.0, 1000.0, 600.0))
    txt = []
    for s in build_wall_detail_sections(f):
        txt.append(s["title"])
        for c in s["cards"]:
            txt.append(c.get("title", ""))
            txt.extend(c.get("lines", []))
            txt.append(c.get("result", ""))
    joined = "\n".join(txt)
    assert "M2* (trong MP)" in joined
    assert "M3* (ngoài MP)" in joined
    assert "M3* (trong MP)" not in joined
    # Khóa ánh xạ e0 (lỗi đảo e0_in/e0_out ở nhánh trục y đã sửa):
    # C-core rot 0, trục trong MP là y: e0_in phải từ M_in
    # (e1_in = 1000×1000/3000 = 333.33 mm; ea_in = max(3.3m/600,
    # 3000/30, 10) = 100 mm -> e0_in = 333.33), không phải từ M_out.
    assert abs(f["e0_in"] - 333.333) <= 0.01
    assert abs(f["ea_in"] - 100.0) <= 0.01
    assert "e0x = 333.33 mm" in joined
