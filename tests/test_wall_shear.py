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
    w = WallInput()  # 2500x350, cover 25, dia_h 12, dia_v 12
    g = wall_shear_geometry(w)
    assert g["b"] == 350.0
    assert abs(g["h0"] - (2500 - 25 - 12 - 6)) < 1e-9
    # Xoay 90°: Lw/tw hiệu dụng hoán đổi -> b = 2500, h0 theo 350
    w90 = WallInput()
    w90.rot_deg = 90
    g90 = wall_shear_geometry(w90)
    assert g90["b"] == 2500.0
    assert abs(g90["h0"] - (350 - 25 - 12 - 6)) < 1e-9


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
    full = wall_tcvn_full(WallInput(), conc, steel,
                          loads=_web_loads(800.0))
    assert abs(full["dc"] - 0.4452331146674462) < 1e-12
    assert full["ok"] is True and full["ok_all"] is True
    sh = full["shear_in"]
    assert sh["ok"] is True and sh["V_cap"] > 800.0
    assert "shear_in" in full["checks_included"]
    assert "shear_in" not in full["checks_pending"]
    assert "sliding" in full["checks_pending"]  # trượt vẫn pending
    assert full["sliding"]["ok"] is None
    # V_in đổi -> N–M không đổi, chỉ cắt đổi
    full0 = wall_tcvn_full(WallInput(), conc, steel,
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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
    print("TẤT CẢ TEST CẮT VÁCH PASS")
