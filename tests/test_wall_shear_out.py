"""Kiểm chứng cắt NGOÀI mặt phẳng cho vách TCVN (lát 4 — phần 4).

Ánh xạ đã xác minh từ code (không đoán):
- Trong MP: V_in = V2 (Q2 nhập tay / V2 pier — wall_mixin
  _collect_wall_loads + WallInput); b = tw, h0 = Lw - cover - dia_h
  - dia_v/2 (wall_shear.check_wall_shear_in_plane).
- Ngoài MP: V_out = V3 (Q3 nhập tay / V3 pier); b = Lw,
  h0 = tw - cover - dia_v - dia_h/2 (gương hàm trong MP);
  Qsw = 0 vì chưa có ô nhập giằng xuyên dày (không bịa thép).

Ca chuẩn: vách 2500x350, cover 25, thép ngang 2φ12 a200, B30
γb = 0.85 (Rb = 14.45, Rbt = 1.02), thép dọc CB500-V γs = 1.0,
N = 2528.65 kN — cùng ca mẫu web của chế độ Vách. Kiểm tay độc
lập (số literal, không qua check_shear) ở test_hand_calc.
"""

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.stirrup import check_shear
from rc_column.wall_detail import build_wall_detail_sections
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_input import WallInput
from rc_column.wall_shear import (
    check_wall_shear_in_plane, check_wall_shear_out_of_plane,
    wall_shear_geometry, wall_shear_geometry_out_of_plane)


def _mats():
    conc = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
    return conc, steel


def _web_loads(V_in, V_out):
    return {"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
            "V_in": V_in, "V_out": V_out, "T": 0.0}


def _hand_out(V):
    """Tính tay độc lập cắt ngoài MP (Qsw = 0), số literal §8.1.3."""
    Rb, Rbt = 14.45, 1.02
    b, h0 = 2500.0, 307.0  # Lw; tw - cover - dia_v - dia_h/2
    sigma = 2528.65 * 1000.0 / (2500.0 * 350.0)
    phi_n = 1.0 + sigma / Rb  # sigma/Rb = 0.2 <= 0.25
    qcap1 = phi_n * 0.3 * Rb * b * h0 / 1000.0
    lo = 0.5 * Rbt * b * h0 / 1000.0
    hi = 2.5 * Rbt * b * h0 / 1000.0
    best = None
    for i in range(11):
        C = h0 + (2.0 * h0 - h0) * i / 10.0
        qb_tt = 1.5 * Rbt * b * h0 * h0 / C / 1000.0
        qb = phi_n * min(max(qb_tt, lo), hi)
        if best is None or qb < best[0]:
            best = (qb, C)
    qcap2, C_opt = best[0], best[1]
    vcap = min(qcap1, qcap2)
    return {"phi_n": phi_n, "Qcap1": qcap1, "Qcap2": qcap2,
            "Qb": qcap2, "Qsw": 0.0, "C_opt": C_opt,
            "V_cap": vcap, "dc": abs(V) / vcap}


def test_geometry_mapping_out_of_plane():
    """Ánh xạ: b = Lw, h0 = tw - cover - dia_v - dia_h/2."""
    w = WallInput()  # 2500x350, cover 25, dia_v 12, dia_h 12
    g = wall_shear_geometry_out_of_plane(w)
    assert g["b"] == 2500.0
    assert abs(g["h0"] - (350 - 25 - 12 - 6)) < 1e-9
    assert g["h0"] == 307.0


def test_qsw_zero_despite_horizontal_steel():
    """Thép ngang phân bố vẫn có nhưng KHÔNG sinh qsw ngoài MP."""
    conc, steel = _mats()
    w = WallInput()
    assert w.layers_h == 2 and w.dia_h == 12.0  # thép ngang có thật
    res = check_wall_shear_out_of_plane(w, conc, steel, 300.0, 2528.65)
    p = res["parts"]
    assert p["Asw"] == 0.0 and p["qsw_arr"] == 0.0 and p["qsw"] == 0.0
    assert p["Qsw"] == 0.0 and p["qb_mode"] == "NONE"
    assert p["sw_txt"] == "không có giằng xuyên dày (Qsw = 0)"
    assert p["cond98_ok"] is True  # không nhóm nào để (98) loại


def test_hand_calc():
    """(a) Ca ĐẠT: V_out = 300 kN — từng số hạng khớp tay < 1e-6."""
    conc, steel = _mats()
    res = check_wall_shear_out_of_plane(WallInput(), conc, steel,
                                        300.0, 2528.65)
    h = _hand_out(300.0)
    p = res["parts"]
    for k in ("phi_n", "Qcap1", "Qcap2", "Qb", "Qsw", "C_opt"):
        assert abs(p[k] - h[k]) < 1e-6, (k, p[k], h[k])
    assert abs(res["V_cap"] - h["V_cap"]) < 1e-6
    assert abs(res["dc"] - h["dc"]) < 1e-9
    assert res["ok"] is True and 0 < res["dc"] < 1.0


def test_fail_case():
    """(b) Ca KHÔNG ĐẠT: V_out = 5000 kN vượt cả [Q]1 lẫn [Q]2."""
    conc, steel = _mats()
    res = check_wall_shear_out_of_plane(WallInput(), conc, steel,
                                        5000.0, 2528.65)
    assert res["ok"] is False and res["dc"] > 1.0
    assert res["parts"]["ok1"] is False  # vượt cả dải nén xiên
    assert res["parts"]["ok2"] is False
    # Fail thật, không do (98)/(96): không có thép để loại/kích (97).
    assert res["parts"]["cond98_ok"] is True
    assert res["parts"]["qb_mode"] == "NONE"


def test_rotation_swaps_effective_dims():
    """(c) Xoay 90°: hình học ngoài MP hoán đổi đúng qua wall_dims.

    Ngoài MP ở 90° có cùng (b, h0) với trong MP ở 0° (và ngược
    lại) — tức xoay vách đổi vai trò 2 phương đúng chiều; Vcap
    khớp trực tiếp check_shear tại kích thước đã hoán đổi.
    """
    conc, steel = _mats()
    w0, w90 = WallInput(), WallInput()
    w90.rot_deg = 90
    g_out0 = wall_shear_geometry_out_of_plane(w0)
    g_out90 = wall_shear_geometry_out_of_plane(w90)
    g_in0 = wall_shear_geometry(w0)
    g_in90 = wall_shear_geometry(w90)
    assert (g_out0["b"], g_out0["h0"]) == (g_in90["b"], g_in90["h0"])
    assert (g_out90["b"], g_out90["h0"]) == (g_in0["b"], g_in0["h0"])
    assert (g_out90["b"], g_out90["h0"]) == (350.0, 2457.0)
    r90 = check_wall_shear_out_of_plane(w90, conc, steel, 300.0, 2528.65)
    sh90 = check_shear(300.0, 350.0, 2457.0, conc.Rb, conc.Rbt,
                       0.0, 0.0, 0.0, direction="out", N=2528.65,
                       A_sec=350.0 * 2500.0, groups=[])
    assert abs(r90["V_cap"] - min(sh90.Qcap1, sh90.Qcap2)) < 1e-9
    assert abs(r90["parts"]["Qb"] - sh90.Qb_opt) < 1e-9
    assert r90["ok"] is True


def test_zero_shear():
    """(d) Không có V_out: D/C = 0, không crash, không bịa số."""
    conc, steel = _mats()
    res = check_wall_shear_out_of_plane(WallInput(), conc, steel,
                                        0.0, 2528.65)
    assert res["dc"] == 0.0 and res["ok"] is True
    assert res["V_cap"] > 0.0 and res["V_d"] == 0.0
    full = wall_tcvn_full(WallInput(), conc, steel,
                          loads=_web_loads(800.0, 0.0))
    assert full["shear_out"]["dc"] == 0.0
    assert full["shear_out"]["ok"] is True
    assert full["shear_out"]["V_d"] == 0.0


def test_engine_integration_nm_and_inplane_unchanged():
    """wall_tcvn_full: shear_out điền đủ; N–M + cắt trong MP không đổi.

    V_out đổi chỉ đổi shear_out; ok_all vẫn = ok N–M (banner thuộc
    phần khác, phần này không đổi); shear_out vào checks_included.
    """
    conc, steel = _mats()
    full = wall_tcvn_full(WallInput(), conc, steel,
                          loads=_web_loads(800.0, 300.0))
    assert abs(full["dc"] - 0.44520) < 5e-5
    assert full["ok"] is True and full["ok_all"] is True
    sh_in = full["shear_in"]
    assert sh_in["ok"] is True
    assert abs(sh_in["V_cap"] - 1987.2) < 0.5
    assert abs(sh_in["dc"] - 800.0 / sh_in["V_cap"]) < 1e-12
    sho = full["shear_out"]
    assert sho["ok"] is True and sho["V_d"] == 300.0
    assert abs(sho["V_cap"] - 704.6) < 0.5
    assert abs(sho["dc"] - 300.0 / sho["V_cap"]) < 1e-12
    assert "shear_out" in full["checks_included"]
    assert "shear_out" not in full["checks_pending"]
    # V_out đổi -> N–M + cắt trong MP giữ nguyên từng chữ số
    full2 = wall_tcvn_full(WallInput(), conc, steel,
                           loads=_web_loads(800.0, 5000.0))
    assert full2["dc"] == full["dc"]
    assert full2["shear_in"] == full["shear_in"]
    assert full2["shear_out"]["ok"] is False
    assert full2["ok_all"] is True  # cắt fail không lật banner N–M
    # Cắt trong MP vẫn độc lập: check trực tiếp khớp dict engine
    direct = check_wall_shear_in_plane(WallInput(), conc, steel,
                                       800.0, 2528.65)
    assert abs(direct["V_cap"] - sh_in["V_cap"]) < 1e-9


def test_detail_builder_out_card():
    """Thẻ chi tiết ngoài MP (cùng builder tab/PDF): đủ công thức,
    Qsw = 0 ghi rõ, kết luận riêng; thẻ trượt chỉ còn trượt."""
    conc, steel = _mats()
    full = wall_tcvn_full(WallInput(), conc, steel,
                          loads=_web_loads(800.0, 300.0))
    secs = build_wall_detail_sections(full)
    sec8 = [s for s in secs if s["num"] == 8][0]
    titles = [c["title"] for c in sec8["cards"]]
    assert "Kiểm tra cắt — Ngoài mặt phẳng (V3)" in titles
    assert "Cắt ngoài mặt phẳng & trượt mạch ngừng" not in titles
    assert "Trượt mạch ngừng chân vách" in titles
    card = [c for c in sec8["cards"]
            if c["title"] == "Kiểm tra cắt — Ngoài mặt phẳng (V3)"][0]
    txt = "\n".join(card["lines"])
    assert "Qsw = 0" in txt and "không bịa thép" in txt
    assert "2500" in txt and "307" in txt  # b × h0
    assert "D/C cắt ngoài MP" in card["result"]
    assert "ĐẠT" in card["result"]
    slide = [c for c in sec8["cards"]
             if c["title"] == "Trượt mạch ngừng chân vách"][0]
    assert slide["result"] == "CHƯA KIỂM"
    assert "V3" not in "\n".join(slide["lines"])


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
    print("TẤT CẢ TEST CẮT NGOÀI MP PASS")
