"""Lát cắt cho 5 loại tiết diện vách mới (2026-10-27).

Ánh xạ (giả định tương đương — TCVN 5574:2018 §8.1.3 chỉ viết cho
tiết diện chữ nhật, xem wall_shear.wall_shear_geometry_poly):
- b = bề dày nhánh mỏng nhất (tw Barbell, sec_t T/L/C/U), cả 2 phương.
- h0 trong MP = E_thân − cover − dia_h − per_dia/2;
  h0 ngoài MP = E_ngang − cover − per_dia − dia_h/2.
- Thép ngang: trong MP layers_h×φ(dia_h) @ s_h; ngoài MP 2×φ(dia_h)
  @ s_h (quyết 2026-10-25 cho phẳng, giữ nguyên).
- C/U ngoài MP PENDING (lõi hở, 2 cánh rời — không có 1 hình chữ
  nhật (b,h0) bảo thủ cho cả [Q]1 và [Q]2).
- Xoay 90° (khung V2/V3 cố định như phẳng): Vcap hoán đổi khi hoán
  đổi V2/V3; khớp chính xác khi dia_h = per_dia và layers_h = 2
  (mặc định của fixture dưới đây; cùng giới hạn như phẳng).

Kiểm chứng:
(a) bảng b/h0/thép ngang từng loại × từng phương;
(b) V=0 ([Q]>0, D/C=0) và V lớn kiểm tay độc lập từ Qb+Qsw tại C_opt
    theo (88)/(90)/(97) (không gọi lại check_shear cho Qcap);
(c) DCM: trong MP ×1,5, ngoài MP không nhân; hậu tố Ved ở bảng GUI;
(d) xoay 90° + hoán đổi V2/V3 → Vcap hoán đổi;
(e) phẳng không đổi: ca ảnh trong MP 1920,5 / ngoài MP 579,1;
(f) JSON round-trip + bảng cắt/thẻ chi tiết đọc dict, không tính lại.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.sections import bar_area
from rc_column.wall_detail import build_wall_detail_sections
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_input import (WallInput, wall_from_dict,
                                  wall_to_dict)
from rc_column.wall_shear import wall_shear_geometry_poly
from gui.wall_mixin import build_wall_shear_rows, wall_qb_formula_note

_CONC = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
_STEEL = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)

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

# (E_thân, E_ngang, h0 trong MP, h0 ngoài MP) — cover 28, dia_h 12,
# per_dia 12: h0 = E − 28 − 12 − 6 ở cả 2 phương (2 dia bằng nhau).
_GEOM = {
    "barbell": (3000.0, 1000.0, 2954.0, 954.0),
    "tee": (2500.0, 1500.0, 2454.0, 1454.0),
    "ell": (2000.0, 1800.0, 1954.0, 1754.0),
    "c-core": (3000.0, 1500.0, 2954.0, None),
    "u-core": (3000.0, 1500.0, 2954.0, None),
}


def _mk(st, kw, rot=0):
    w = WallInput(section_type=st, cover=28, dia_h=12,
                  per_dia=12, per_s=200, rot_deg=rot)
    for k, v in kw.items():
        setattr(w, k, v)
    return w


def _loads(N, Mi, Mo, Vi, Vo):
    return {"N": N, "M_in": Mi, "M_out": Mo,
            "V_in": Vi, "V_out": Vo, "T": 0.0}


def _full(st, kw, N, Mi, Mo, Vi, Vo, seis=False, rot=0):
    return wall_tcvn_full(_mk(st, kw, rot=rot), _CONC, _STEEL,
                          loads=_loads(N, Mi, Mo, Vi, Vo),
                          seismic_shear=seis)


def _handcheck(sh_dict, conc, N, V):
    """Kiểm tay độc lập: từ parts + C_opt, tính lại [Q]1/[Q]2/D/C
    bằng đúng công thức (88)/(90)/(97) + chặn Qb — không gọi
    check_shear. Sai số cho phép 0,1 kN (làm tròn 1 chữ số thập phân
    của Qb/Qsw trong parts không dùng ở đây — dùng C_opt/qsw thô)."""
    p = sh_dict["parts"]
    b, h0 = float(p["b"]), float(p["h0"])
    qsw = float(p["qsw"])
    c_opt = float(p["C_opt"])
    # φn lấy từ parts (đã tính từ N/A_sec đa giác trong engine);
    # kiểm tay ở đây chỉ tính lại [Q]1/[Q]2 từ φn đó, không gọi
    # lại check_shear — φn theo §8.1.3.3.2 đã khóa ở test cột.
    phi_n = float(p["phi_n"])
    qcap1 = phi_n * 0.3 * conc.Rb * b * h0 / 1000.0
    qmin = 0.5 * conc.Rbt * b * h0 / 1000.0
    qmax = 2.5 * conc.Rbt * b * h0 / 1000.0
    if p["qb_mode"] == "CT97":
        qb_tt = 4 * 1.5 * h0 * h0 * qsw / c_opt / 1000.0
    else:
        qb_tt = 1.5 * conc.Rbt * b * h0 * h0 / c_opt / 1000.0
    qb = phi_n * min(max(qb_tt, qmin), qmax)
    qsw_cap = 0.75 * qsw * c_opt / 1000.0
    qcap2 = qb + qsw_cap
    vcap = min(qcap1, qcap2)
    assert abs(qcap1 - float(p["Qcap1"])) < 0.1, (qcap1, p["Qcap1"])
    assert abs(qb - float(p["Qb"])) < 0.1, (qb, p["Qb"])
    assert abs(qsw_cap - float(p["Qsw"])) < 0.1, (qsw_cap, p["Qsw"])
    assert abs(qcap2 - float(p["Qcap2"])) < 0.1, (qcap2, p["Qcap2"])
    assert abs(vcap - float(sh_dict["V_cap"])) < 0.1, \
        (vcap, sh_dict["V_cap"])
    assert abs(abs(V) / vcap - float(sh_dict["dc"])) < 1e-3, \
        (abs(V) / vcap, sh_dict["dc"])


# ---------------- (a) bảng hình học ----------------

def test_poly_shear_geometry_table():
    for st, kw, _N, _Mi, _Mo in _CASES:
        g = wall_shear_geometry_poly(_mk(st, kw))
        e_stem, e_trans, h0_in, h0_out = _GEOM[st]
        assert g["geom_in"]["b"] == 300.0, st
        assert g["geom_in"]["E_depth"] == e_stem, st
        assert abs(g["geom_in"]["h0"] - h0_in) < 1e-9, st
        assert abs(g["geom_in"]["Asw"] - 2 * bar_area(12.0)) < 1e-9, st
        assert g["geom_in"]["branches"] == 2, st
        if h0_out is None:
            assert g["geom_out"] is None, st
            assert "lõi hở" in g["pending_out"] or "2 cánh" in \
                g["pending_out"], g["pending_out"]
        else:
            assert g["geom_out"]["b"] == 300.0, st
            assert g["geom_out"]["E_depth"] == e_trans, st
            assert abs(g["geom_out"]["h0"] - h0_out) < 1e-9, st
            assert abs(g["geom_out"]["Asw"]
                       - 2 * bar_area(12.0)) < 1e-9, st
            assert g["pending_out"] is None, st


# ---------------- (b) V=0 và V lớn kiểm tay ----------------

def test_poly_shear_v0_and_large_handcheck():
    for st, kw, N, Mi, Mo in _CASES:
        f0 = _full(st, kw, N, Mi, Mo, 0.0, 0.0)
        assert f0["shear_in"]["V_cap"] > 0
        assert f0["shear_in"]["dc"] == 0.0
        assert f0["shear_in"]["ok"] is True
        if st in ("c-core", "u-core"):
            assert f0["shear_out"]["V_cap"] is None
            assert f0["shear_out"]["ok"] is None
        else:
            assert f0["shear_out"]["V_cap"] > 0
            assert f0["shear_out"]["dc"] == 0.0
        # V lớn: trong MP 1500 kN, ngoài MP 800 kN (Barbell ngoài
        # MP 800 > Vcap 695 → KHÔNG ĐẠT nhưng vẫn kiểm tay được;
        # (98) vẫn thỏa ở cả 2 phương với các V này: s_max nhỏ
        # nhất là Barbell ngoài MP 348 mm > s_h 200 mm).
        f = _full(st, kw, N, Mi, Mo, 1500.0, 800.0)
        _handcheck(f["shear_in"], _CONC, N, 1500.0)
        if st not in ("c-core", "u-core"):
            _handcheck(f["shear_out"], _CONC, N, 800.0)
        # D/C N–M không đổi theo V (cắt độc lập với N–M).
        assert abs(f["dc"] - f0["dc"]) < 1e-12, st


def test_poly_shear_no_horizontal_steel_in_plane():
    """layers_h = 0 → trong MP Qsw = 0, vẫn tính được Qb (NONE)."""
    w = _mk("tee", dict(Lw=2500, sec_bf=1500, sec_t=300))
    w.layers_h = 0
    f = wall_tcvn_full(w, _CONC, _STEEL,
                       loads=_loads(2000.0, 800.0, 200.0, 500.0, 0.0))
    assert f["shear_in"]["parts"]["Asw"] == 0.0
    assert f["shear_in"]["parts"]["Qsw"] == 0.0
    assert f["shear_in"]["V_cap"] > 0


# ---------------- (c) DCM ----------------

def test_poly_shear_dcm_only_in_plane():
    for st, kw, N, Mi, Mo in _CASES:
        f0 = _full(st, kw, N, Mi, Mo, 800.0, 300.0)
        f1 = _full(st, kw, N, Mi, Mo, 800.0, 300.0, seis=True)
        si0, si1 = f0["shear_in"], f1["shear_in"]
        assert si1["V_d"] == 1200.0, st
        assert si1["seismic_applied"] is True, st
        assert abs(si1["V_cap"] - si0["V_cap"]) < 1e-9, st
        assert abs(si1["dc"] - 1200.0 / si0["V_cap"]) < 1e-9, st
        so1 = f1["shear_out"]
        if st not in ("c-core", "u-core"):
            assert so1["V_d"] == 300.0, st
            assert abs(so1["V_cap"]
                       - f0["shear_out"]["V_cap"]) < 1e-9, st
        rows = build_wall_shear_rows(f1)
        _row = {lab: (a, b) for lab, a, b in rows}
        assert "(1.5 Ved, TCVN 9386-1:2025 §5.4.2.4(7))" in \
            _row["Lực cắt tính toán, V2 / V3"][0], st
        if st in ("c-core", "u-core"):
            assert _row["Lực cắt tính toán, V2 / V3"][1] == \
                "CHƯA KIỂM", st
        else:
            assert "(không phóng đại)" in \
                _row["Lực cắt tính toán, V2 / V3"][1], st
        rows0 = build_wall_shear_rows(f0)
        _row0 = {lab: (a, b) for lab, a, b in rows0}
        assert "(1.5 Ved" not in _row0["Lực cắt tính toán, V2 / V3"][0]


# ---------------- (d) xoay 90° + hoán đổi V2/V3 ----------------

def test_poly_shear_rotation_90_swap():
    for st, kw, N, Mi, Mo in _CASES:
        f0 = _full(st, kw, N, Mi, Mo, 800.0, 300.0)
        # Xoay 90° + hoán đổi V2/V3: V_in' = 300 (hướng ngang cũ),
        # V_out' = 800 (hướng thân cũ). N/M giữ nguyên (cắt không
        # phụ thuộc M; N cho φn giữ nguyên) nên Vcap hoán đổi đúng.
        f1 = _full(st, kw, N, Mi, Mo, 300.0, 800.0, rot=90)
        if st in ("c-core", "u-core"):
            # Hướng ngang vật lý pending → ở rot 90 nó nằm ở cột
            # trong MP; cột ngoài MP mở bằng Vcap thân cũ.
            assert f1["shear_in"]["V_cap"] is None, st
            assert abs(f1["shear_out"]["V_cap"]
                       - f0["shear_in"]["V_cap"]) < 1e-6, st
        else:
            assert abs(f1["shear_in"]["V_cap"]
                       - f0["shear_out"]["V_cap"]) < 1e-6, st
            assert abs(f1["shear_out"]["V_cap"]
                       - f0["shear_in"]["V_cap"]) < 1e-6, st


# ---------------- (e) phẳng không đổi ----------------

def test_flat_shear_locks_unchanged():
    w = WallInput(sw_steel_grade="CB400-V")
    f = wall_tcvn_full(w, _CONC, _STEEL,
                       loads={"N": 2528.65, "M_in": 202.86,
                              "M_out": 275.23, "V_in": 800.0,
                              "V_out": 300.0, "T": 0.0})
    assert abs(f["shear_in"]["V_cap"] - 1920.5) < 0.05
    assert abs(f["shear_out"]["V_cap"] - 579.1) < 0.05
    assert abs(f["dc"] - 0.45907) < 0.0005
    # Mốc N–M phẳng của lát N–M (cover 13, V = 0).
    f2 = wall_tcvn_full(WallInput(cover=13.0), _CONC, _STEEL,
                        loads={"N": 2528.65, "M_in": 202.86,
                               "M_out": 275.23, "V_in": 0.0,
                               "V_out": 0.0, "T": 0.0})
    assert abs(f2["dc"] - 0.44520104645817127) < 1e-9


# ---------------- (f) hiển thị + round-trip ----------------

def test_poly_shear_detail_rows_and_roundtrip():
    for st, kw, N, Mi, Mo in _CASES:
        f = _full(st, kw, N, Mi, Mo, 800.0, 300.0)
        rows = build_wall_shear_rows(f)
        _row = {lab: (a, b) for lab, a, b in rows}
        assert _row["Kết luận"][0] != "CHƯA KIỂM", st
        assert "×" in _row["Kích thước tiết diện, bw × d"][0], st
        if st in ("c-core", "u-core"):
            assert _row["Kết luận"][1] == "CHƯA KIỂM", st
        else:
            assert _row["Kết luận"][1] != "CHƯA KIỂM", st
        # Ghi chú Qb: phương mở có thay số, phương pending ghi rõ.
        note = wall_qb_formula_note(f)
        assert "Trong MP:" in note and "§8.1.3" in note, st
        if st in ("c-core", "u-core"):
            assert "Ngoài MP: CHƯA KIỂM" in note, st
        secs = build_wall_detail_sections(f)
        joined = "\n".join(
            [s["title"] for s in secs]
            + [c.get("title", "") for s in secs for c in s["cards"]]
            + [ln for s in secs for c in s["cards"]
               for ln in c.get("lines", [])]
            + [c.get("result", "") for s in secs for c in s["cards"]])
        assert "GIẢ ĐỊNH TƯƠNG ĐƯƠNG" in joined, st
        if st in ("c-core", "u-core"):
            assert "lõi hở" in joined, st
        # JSON round-trip: Vcap không đổi.
        w2 = wall_from_dict(wall_to_dict(_mk(st, kw)))
        f2 = wall_tcvn_full(w2, _CONC, _STEEL,
                            loads=_loads(N, Mi, Mo, 800.0, 300.0))
        assert abs(f2["shear_in"]["V_cap"]
                   - f["shear_in"]["V_cap"]) < 1e-9, st
        if st not in ("c-core", "u-core"):
            assert abs(f2["shear_out"]["V_cap"]
                       - f["shear_out"]["V_cap"]) < 1e-9, st
        else:
            assert f2["shear_out"]["V_cap"] is None, st
