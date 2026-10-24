"""Kiểm chứng cắt vách TCVN (lát 4 — phần 2 chương trình vách).

Ca chuẩn: vách 2500x350, cover 25, thép ngang 2φ12 a200, B30 γb=0.85,
thép dọc CB500-V γs=1.0 (Rsw = 300 MPa theo cấp thép dọc), N = 2528.65 kN
— cùng ca mẫu web của chế độ Vách (chỉ khác lực cắt V_in do web không
cho V). Các test này kiểm ánh xạ + cổng, KHÔNG thay số tay: bảng kiểm
tay độc lập (tính tay ngoài engine, từng số hạng) nằm ở
wallnext_work/shear_work/handcheck_wall_shear.py.
"""

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.sections import bar_area
from rc_column.stirrup import check_shear
from rc_column.wall_input import WallInput
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_shear import (check_wall_shear_in_plane,
                                  wall_shear_geometry)


def _mats():
    conc = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
    return conc, steel


def _web_loads(V_in):
    return {"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
            "V_in": V_in, "V_out": 0.0, "T": 0.0}


def test_geometry_mapping():
    """Ánh xạ: b = tw, h0 = Lw - cover - dia_h - dia_v/2."""
    w = WallInput()  # 2500x350, cover 25 (nay là c_đai), dia_h 12, dia_v 12
    g = wall_shear_geometry(w)
    assert g["b"] == 350.0
    assert abs(g["h0"] - (2500 - 25 - 12 - 6)) < 1e-9
    # Xoay 90°: Lw/tw hiệu dụng hoán đổi -> b = 2500, h0 theo 350
    w90 = WallInput()
    w90.rot_deg = 90
    g90 = wall_shear_geometry(w90)
    assert g90["b"] == 2500.0
    assert abs(g90["h0"] - (350 - 25 - 12 - 6)) < 1e-9


def test_migrated_old_file_shear_h0_grows_by_dia_h():
    """File cũ cover 25 (nghĩa mặt thép) -> migration 13 (c_đai):
    h0 cắt TĂNG đúng dia_h 12 (2457 -> 2469) — số cắt cũ bảo thủ hơn;
    đồng thời inset fiber giữ nguyên (25+6 = 13+12+6 = 31).
    (Số 2457 của test_geometry_mapping giữ nguyên vì WallInput() mới
    với cover 25 nay đã mang nghĩa c_đai, không còn là fixture cũ.)"""
    from rc_column.cover_migration import migrate_wall_dict
    from rc_column.wall_input import wall_from_dict
    from rc_column.wall_section import build_wall_section
    old = {"cover": 25, "dia_h": 12, "Lw": 2500, "tw": 350,
           "steel_mode": "perimeter", "per_dia": 12, "per_s": 200}
    mig, warns = migrate_wall_dict(old)
    assert mig["cover"] == 13 and warns == []
    g = wall_shear_geometry(wall_from_dict(mig))
    assert abs(g["h0"] - 2469.0) < 1e-9  # 2500-13-12-6
    sec, _ = build_wall_section(wall_from_dict(mig), *_mats())
    assert abs(min(r.x for r in sec.rebars) - (-1250.0 + 31.0)) < 1e-9


def test_qsw_from_distributed_steel():
    """qsw = Rsw x (layers_h x Ah) / s_h; khớp check_shear trực tiếp."""
    conc, steel = _mats()
    w = WallInput()
    res = check_wall_shear_in_plane(w, conc, steel, 800.0, 2528.65)
    p = res["parts"]
    assert abs(p["Asw"] - 2 * bar_area(12.0)) < 1e-9
    assert abs(p["qsw_arr"] - 300.0 * p["Asw"] / 200.0) < 1e-9
    assert abs(p["qsw"] - p["qsw_arr"]) < 1e-9  # (98) thỏa ở V=800
    # Đối chiếu trực tiếp với check_shear của cột cùng tham số
    sh = check_shear(800.0, 350.0, 2457.0, conc.Rb, conc.Rbt,
                     p["Asw"], 300.0, 200.0, direction="in",
                     N=2528.65, A_sec=2500.0 * 350.0,
                     groups=[(p["Asw"], 200.0)])
    assert abs(res["V_cap"] - min(sh.Qcap1, sh.Qcap2)) < 1e-9
    assert abs(p["Qb"] - sh.Qb_opt) < 1e-9
    assert abs(p["Qsw"] - sh.Qsw_opt) < 1e-9
    assert abs(p["C_opt"] - sh.C_opt) < 1e-9
    assert res["ok"] is True


def test_pass_case():
    """Ca ĐẠT: V_in = 800 kN < V_cap (ca mẫu web + V minh hoạ)."""
    conc, steel = _mats()
    res = check_wall_shear_in_plane(WallInput(), conc, steel,
                                    800.0, 2528.65)
    assert res["ok"] is True
    assert res["V_cap"] > 800.0
    assert 0 < res["dc"] < 1.0
    assert abs(res["dc"] - 800.0 / res["V_cap"]) < 1e-12


def test_fail_case():
    """Ca KHÔNG ĐẠT: V_in = 5000 kN vượt cả [Q]1 lẫn [Q]2 (đai vẫn kể)."""
    conc, steel = _mats()
    res = check_wall_shear_in_plane(WallInput(), conc, steel,
                                    5000.0, 2528.65)
    assert res["parts"]["cond98_ok"] is True  # fail thật, không do (98)
    assert res["ok"] is False
    assert res["dc"] > 1.0


def test_no_horizontal_steel():
    """Không thép ngang: Qsw = 0, vẫn tính được Qb (chế độ NONE)."""
    conc, steel = _mats()
    w = WallInput()
    w.layers_h = 0
    res = check_wall_shear_in_plane(w, conc, steel, 500.0, 2528.65)
    assert res["parts"]["qsw"] == 0.0
    assert res["parts"]["Qsw"] == 0.0
    assert res["parts"]["qb_mode"] == "NONE"
    assert res["V_cap"] == min(res["parts"]["Qcap1"],
                               res["parts"]["Qcap2"])


def test_cond98_drops_steel():
    """ĐK (98): s_h = 3000 > s_max ở V = 800 -> thép ngang bị loại."""
    conc, steel = _mats()
    w = WallInput()
    w.s_h = 3000.0
    res = check_wall_shear_in_plane(w, conc, steel, 800.0, 2528.65)
    assert res["parts"]["cond98_ok"] is False
    assert res["parts"]["qsw"] == 0.0
    assert res["parts"]["Qsw"] == 0.0
    assert res["parts"]["dropped98"] == [(res["parts"]["Asw"], 3000.0)]


def test_engine_integration_nm_unchanged():
    """wall_tcvn_full: shear_in điền đủ, N–M giữ nguyên từng chữ số,
    checks_included/pending cập nhật, ok_all vẫn = ok N–M."""
    conc, steel = _mats()
    # MIGRATION COVER: fixture cũ cover 25 (nghĩa mặt thép) -> 13
    # (c_đai) để giữ mốc N-M 0.44520...; cắt theo đó h0 2469, Vcap mới.
    _w_mig = WallInput(); _w_mig.cover = 13.0
    full = wall_tcvn_full(_w_mig, conc, steel,
                          loads=_web_loads(800.0))
    assert abs(full["dc"] - 0.44520104645817127) < 1e-12
    assert full["ok"] is True and full["ok_all"] is True
    sh = full["shear_in"]
    assert sh["ok"] is True and sh["V_cap"] > 800.0
    assert "shear_in" in full["checks_included"]
    assert "shear_in" not in full["checks_pending"]
    assert "sliding" in full["checks_pending"]  # trượt vẫn pending
    assert full["sliding"]["ok"] is None
    # V_in đổi -> N–M không đổi, chỉ cắt đổi
    full0 = wall_tcvn_full(_w_mig, conc, steel,
                           loads=_web_loads(0.0))
    assert full0["dc"] == full["dc"]
    assert full0["shear_in"]["dc"] == 0.0


def test_engine_shear_fail_does_not_flip_nm():
    """Cắt KHÔNG ĐẠT nhưng N–M ĐẠT: banner/ok_all vẫn ĐẠT (N–M)."""
    conc, steel = _mats()
    full = wall_tcvn_full(WallInput(), conc, steel,
                          loads=_web_loads(5000.0))
    assert full["ok"] is True and full["ok_all"] is True
    assert full["shear_in"]["ok"] is False


# ---- Phần 3/7: ô cấp thép ngang RIÊNG của vách (sw_steel_grade) ----

def _sw400():
    return SteelMaterial(STEEL_GRADES["CB400-V"], 1.0)


def test_sw_grade_explicit_via_winp():
    """Khóa mới trong WallInput: sw_steel_grade="CB400-V" với thép dọc
    CB500-V -> Rsw = 280 (không phải 300), qsw theo 280, khớp
    check_shear trực tiếp với Rsw = 280; N–M không đổi.

    MIGRATION COVER: fixture cũ cover 25 (nghĩa mặt thép) -> 13
    (c_đai) để giữ mốc N–M 0.44520; h0 cắt trực tiếp 2457 -> 2469,
    Vcap CB400-V 1920.5 (h0 cũ, GUI preset) -> 1929.8 (h0 mới).
    """
    conc, steel = _mats()
    w = WallInput(sw_steel_grade="CB400-V", cover=13.0)
    res = check_wall_shear_in_plane(w, conc, steel, 800.0, 2528.65)
    p = res["parts"]
    assert p["Rsw"] == 280.0
    assert p["steel_grade"] == "CB400-V"
    assert p["sw_steel_grade"] == "CB400-V"
    assert p["steel_grade_long"] == "CB500-V"
    assert abs(p["qsw_arr"] - 280.0 * p["Asw"] / 200.0) < 1e-9
    sh = check_shear(800.0, 350.0, 2469.0, conc.Rb, conc.Rbt,
                     p["Asw"], 280.0, 200.0, direction="in",
                     N=2528.65, A_sec=2500.0 * 350.0,
                     groups=[(p["Asw"], 200.0)])
    assert abs(res["V_cap"] - min(sh.Qcap1, sh.Qcap2)) < 1e-9
    assert res["V_cap"] < 1996.8599465297955  # Rsw thấp hơn -> Vcap thấp hơn
    full = wall_tcvn_full(WallInput(sw_steel_grade="CB400-V",
                                    cover=13.0),
                          conc, steel, loads=_web_loads(800.0))
    assert abs(full["dc"] - 0.44520104645817127) < 1e-12  # N–M không đổi
    assert full["shear_in"]["V_cap"] == res["V_cap"]


def test_sw_grade_explicit_via_steel_sw_param():
    """Tham số steel_sw của wall_shear/wall_engine (đường GUI dùng):
    truyền CB400-V -> Rsw = 280, và thắng cả cấp ghi trong winp."""
    conc, steel = _mats()
    res = check_wall_shear_in_plane(WallInput(), conc, steel,
                                    800.0, 2528.65, steel_sw=_sw400())
    assert res["parts"]["Rsw"] == 280.0
    assert res["parts"]["steel_grade"] == "CB400-V"
    w = WallInput(sw_steel_grade="CB300-V")
    full = wall_tcvn_full(w, conc, steel, loads=_web_loads(800.0),
                          steel_sw=_sw400())
    assert full["shear_in"]["parts"]["Rsw"] == 280.0
    assert full["shear_in"]["parts"]["steel_grade"] == "CB400-V"


def test_old_wall_dict_fallback_to_longitudinal():
    """TƯƠNG THÍCH NGƯỢC: dict vách cũ KHÔNG có sw_steel_grade ->
    wall_from_dict giữ None, engine fallback thép dọc CB500-V, số cắt
    cũ tái hiện TỪNG CHỮ SỐ (Vcap 1987.1546733996383, D/C 0.40259)."""
    from rc_column.wall_input import wall_from_dict, wall_to_dict
    conc, steel = _mats()
    old = {"Lw": 2500, "tw": 350, "cover": 25, "dia_h": 12, "s_h": 200,
           "layers_h": 2}
    w = wall_from_dict(old)
    assert w.sw_steel_grade is None
    assert "sw_steel_grade" not in old  # normalize KHÔNG điền khóa mới
    res = check_wall_shear_in_plane(w, conc, steel, 800.0, 2528.65)
    assert res["parts"]["Rsw"] == 300.0
    assert res["parts"]["steel_grade"] == "CB500-V"
    assert res["V_cap"] == 1987.1546733996383
    assert abs(res["dc"] - 0.4025856722221599) < 1e-12
    full = wall_tcvn_full(w, conc, steel, loads=_web_loads(800.0))
    assert full["shear_in"]["V_cap"] == 1987.1546733996383
    # Round-trip dict cũ: khóa mới có mặt với giá trị None (= chưa đặt),
    # mở lại vẫn fallback — không tự biến thành CB400-V.
    assert wall_to_dict(w)["sw_steel_grade"] is None
    assert wall_from_dict(wall_to_dict(w)).sw_steel_grade is None


def test_new_wall_dict_roundtrip():
    """File mới có khóa sw_steel_grade -> mở lên dùng đúng cấp đó,
    wall_to_dict giữ nguyên khóa."""
    from rc_column.wall_input import wall_from_dict, wall_to_dict
    conc, steel = _mats()
    d = {"Lw": 2500, "tw": 350, "cover": 25, "dia_h": 12, "s_h": 200,
         "layers_h": 2, "sw_steel_grade": "CB400-V"}
    w = wall_from_dict(d)
    assert w.sw_steel_grade == "CB400-V"
    assert wall_to_dict(w)["sw_steel_grade"] == "CB400-V"
    full = wall_tcvn_full(w, conc, steel, loads=_web_loads(800.0))
    assert full["shear_in"]["parts"]["Rsw"] == 280.0
    assert full["shear_in"]["parts"]["steel_grade"] == "CB400-V"
    # Đổi sang cấp khác -> số cắt đổi theo đúng Rsw của cấp đó.
    w2 = wall_from_dict(dict(d, sw_steel_grade="CB300-V"))
    full2 = wall_tcvn_full(w2, conc, steel, loads=_web_loads(800.0))
    assert full2["shear_in"]["parts"]["Rsw"] == 215.0
    assert full2["shear_in"]["V_cap"] < full["shear_in"]["V_cap"]


def test_invalid_sw_grade_falls_back():
    """Cấp lạ trong winp -> fallback thép dọc ở cả 2 tầng (wall_shear
    trực tiếp lẫn wall_engine), không crash, không tự đoán cấp khác."""
    conc, steel = _mats()
    w = WallInput(sw_steel_grade="KHONG-CO-CAP")
    res = check_wall_shear_in_plane(w, conc, steel, 800.0, 2528.65)
    assert res["parts"]["Rsw"] == 300.0
    full = wall_tcvn_full(w, conc, steel, loads=_web_loads(800.0))
    assert full["shear_in"]["parts"]["Rsw"] == 300.0
    assert full["shear_in"]["parts"]["steel_grade"] == "CB500-V"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
    print("TẤT CẢ TEST CẮT VÁCH PASS")
