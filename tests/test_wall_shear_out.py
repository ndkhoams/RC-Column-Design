"""Kiểm chứng cắt NGOÀI mặt phẳng cho vách TCVN (lát 4 — phần 4).

Ánh xạ đã xác minh từ code (không đoán):
- Trong MP: V_in = V2 (Q2 nhập tay / V2 pier — wall_mixin
  _collect_wall_loads + WallInput); b = tw, h0 = Lw - cover - dia_h
  - dia_v/2 (wall_shear.check_wall_shear_in_plane).
- Ngoài MP: V_out = V3 (Q3 nhập tay / V3 pier); b = Lw,
  h0 = tw - cover - dia_v - dia_h/2 (gương hàm trong MP);
  thép ngang MẶC ĐỊNH 2 nhánh × φ(dia_h) @ s_h, cùng cấp thép
  với trong MP, suy trực tiếp từ input thép ngang bổ sung —
  quyết user 2026-10-25, thay thế quyết P4 cũ Qsw = 0 (không có
  thép bổ sung thì Qsw = 0 thật).

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
    """Tính tay độc lập cắt ngoài MP (thép mặc định 2 nhánh),
    số literal §8.1.3. WallInput() mặc định không có
    sw_steel_grade nên Rsw fallback về thép dọc CB500-V (300 MPa);
    qsw = 339.3 < qsw_min96 = 637.5 nên (96) hỏng → Qb theo (97),
    Qb_tt chặn dưới [0,5; 2,5]×Rbt×b×h0 (kink ở C ≈ 491)."""
    Rb, Rbt = 14.45, 1.02
    b, h0 = 2500.0, 307.0  # Lw; tw - cover - dia_v - dia_h/2
    Asw = 2 * math.pi * 12.0 ** 2 / 4.0
    Rsw, s_h = 300.0, 200.0
    qsw = Rsw * Asw / s_h
    sigma = 2528.65 * 1000.0 / (2500.0 * 350.0)
    phi_n = 1.0 + sigma / Rb  # sigma/Rb = 0.2 <= 0.25
    qcap1 = phi_n * 0.3 * Rb * b * h0 / 1000.0
    lo = 0.5 * Rbt * b * h0 / 1000.0
    hi = 2.5 * Rbt * b * h0 / 1000.0
    best = None
    for i in range(11):
        C = h0 + (2.0 * h0 - h0) * i / 10.0
        qb_tt = 4 * 1.5 * h0 * h0 * qsw / C / 1000.0
        qb = phi_n * min(max(qb_tt, lo), hi)
        qsw_c = 0.75 * qsw * C / 1000.0
        tot = qb + qsw_c
        if best is None or tot < best[0]:
            best = (tot, qb, qsw_c, C)
    qcap2, qb_opt, qsw_opt, C_opt = best
    vcap = min(qcap1, qcap2)
    return {"phi_n": phi_n, "Qcap1": qcap1, "Qcap2": qcap2,
            "Qb": qb_opt, "Qsw": qsw_opt, "C_opt": C_opt,
            "V_cap": vcap, "dc": abs(V) / vcap,
            "qsw": qsw, "Asw": Asw}


def test_geometry_mapping_out_of_plane():
    """Ánh xạ: b = Lw, h0 = tw - cover - dia_v - dia_h/2."""
    w = WallInput()  # 2500x350, cover 25, dia_v 12, dia_h 12
    g = wall_shear_geometry_out_of_plane(w)
    assert g["b"] == 2500.0
    assert abs(g["h0"] - (350 - 25 - 12 - 6)) < 1e-9
    assert g["h0"] == 307.0


def test_out_steel_from_horizontal_steel():
    """Thép ngoài MP = 2 nhánh × φ(dia_h) @ s_h, cùng cấp thép
    với trong MP (quyết user 2026-10-25, thay P4 cũ Qsw = 0).
    WallInput() mặc định không có sw_steel_grade nên Rsw fallback
    thép dọc CB500-V (300 MPa); số nhánh ngoài MP CỐ ĐỊNH = 2,
    độc lập với layers_h trong MP."""
    conc, steel = _mats()
    w = WallInput()
    assert w.layers_h == 2 and w.dia_h == 12.0  # thép ngang có thật
    res = check_wall_shear_out_of_plane(w, conc, steel, 300.0, 2528.65)
    p = res["parts"]
    assert p["sw_txt"] == "2φ12 a200"
    assert p["steel_grade"] == "CB500-V" and p["Rsw"] == 300.0
    assert abs(p["Asw"] - 2 * math.pi * 12.0 ** 2 / 4.0) < 1e-9
    assert abs(p["qsw_arr"] - 300.0 * p["Asw"] / 200.0) < 1e-9
    assert p["qb_mode"] == "CT97" and p["cond96_ok"] is False
    assert p["Qsw"] > 0.0 and p["Qb"] > 0.0
    # Đổi layers_h trong MP (2 -> 1) không đổi thép ngoài MP.
    w1 = WallInput(layers_h=1, sw_steel_grade="CB400-V")
    r1 = check_wall_shear_out_of_plane(w1, conc, steel, 300.0, 2528.65)
    assert r1["parts"]["sw_txt"] == "2φ12 a200"
    assert abs(r1["parts"]["Asw"] - p["Asw"]) < 1e-9
    assert r1["parts"]["steel_grade"] == "CB400-V"
    # Đổi dia_h/s_h/cấp trong MP thì ngoài MP đổi theo.
    w2 = WallInput(dia_h=10.0, s_h=150.0, sw_steel_grade="CB500-V")
    r2 = check_wall_shear_out_of_plane(w2, conc, steel, 300.0, 2528.65)
    assert r2["parts"]["sw_txt"] == "2φ10 a150"
    assert abs(r2["parts"]["Asw"] - 2 * math.pi * 10.0 ** 2 / 4.0) < 1e-9


def test_hand_calc():
    """(a) Ca ĐẠT: V_out = 300 kN — từng số hạng khớp tay < 1e-6."""
    conc, steel = _mats()
    res = check_wall_shear_out_of_plane(WallInput(), conc, steel,
                                        300.0, 2528.65)
    h = _hand_out(300.0)
    p = res["parts"]
    for k in ("phi_n", "Qcap1", "Qcap2", "Qb", "Qsw", "C_opt",
              "qsw", "Asw"):
        assert abs(p[k] - h[k]) < 1e-6, (k, p[k], h[k])
    assert abs(res["V_cap"] - h["V_cap"]) < 1e-6
    assert abs(res["dc"] - h["dc"]) < 1e-9
    assert res["ok"] is True and 0 < res["dc"] < 1.0


def test_fail_case():
    """(b) Ca KHÔNG ĐẠT: V_out = 5000 kN vượt cả [Q]1 lẫn [Q]2.
    (98) loại nhóm thép (s_max ≈ 48 mm < s_h = 200 mm) nên Qsw = 0
    sau loại, qb_mode NONE — nhưng ok1 đã sai (5000 > [Q]1) nên
    kết luận KHÔNG ĐẠT vẫn đúng, không phải do (98) tạo ra."""
    conc, steel = _mats()
    res = check_wall_shear_out_of_plane(WallInput(), conc, steel,
                                        5000.0, 2528.65)
    assert res["ok"] is False and res["dc"] > 1.0
    assert res["parts"]["ok1"] is False  # vượt cả dải nén xiên
    assert res["parts"]["ok2"] is False
    assert res["parts"]["cond98_ok"] is False
    assert res["parts"]["qb_mode"] == "NONE"
    assert res["parts"]["Qsw"] == 0.0


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
    _asw90 = 2 * math.pi * 12.0 ** 2 / 4.0
    sh90 = check_shear(300.0, 350.0, 2457.0, conc.Rb, conc.Rbt,
                       _asw90, 300.0, 200.0, direction="out",
                       N=2528.65, A_sec=350.0 * 2500.0,
                       groups=[(_asw90, 200.0)])
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

    MIGRATION COVER: fixture cũ cover 25 (nghĩa mặt thép) -> 13
    (c_đai) để giữ mốc N–M 0.44520; cắt đổi theo h0 mới (trong MP
    Vcap 1987.2 -> 1996.9). Ngoài MP nay theo quyết user
    2026-10-25 (2 nhánh, Rsw fallback thép dọc 300 MPa): Vcap
    617.9 (thay mốc cũ 732.1 thời Qsw = 0).
    """
    conc, steel = _mats()
    _w_mig = WallInput(cover=13.0)
    full = wall_tcvn_full(_w_mig, conc, steel,
                          loads=_web_loads(800.0, 300.0))
    assert abs(full["dc"] - 0.44520) < 5e-5
    assert full["ok"] is True and full["ok_all"] is True
    sh_in = full["shear_in"]
    assert sh_in["ok"] is True
    assert abs(sh_in["V_cap"] - 1996.9) < 0.5
    assert abs(sh_in["dc"] - 800.0 / sh_in["V_cap"]) < 1e-12
    sho = full["shear_out"]
    assert sho["ok"] is True and sho["V_d"] == 300.0
    assert abs(sho["V_cap"] - 617.9) < 0.5
    assert abs(sho["dc"] - 300.0 / sho["V_cap"]) < 1e-12
    assert "shear_out" in full["checks_included"]
    assert "shear_out" not in full["checks_pending"]
    # V_out đổi -> N–M + cắt trong MP giữ nguyên từng chữ số
    full2 = wall_tcvn_full(_w_mig, conc, steel,
                           loads=_web_loads(800.0, 5000.0))
    assert full2["dc"] == full["dc"]
    assert full2["shear_in"] == full["shear_in"]
    assert full2["shear_out"]["ok"] is False
    assert full2["ok_all"] is True  # cắt fail không lật banner N–M
    # Cắt trong MP vẫn độc lập: check trực tiếp khớp dict engine
    direct = check_wall_shear_in_plane(_w_mig, conc, steel,
                                       800.0, 2528.65)
    assert abs(direct["V_cap"] - sh_in["V_cap"]) < 1e-9


def test_detail_builder_out_card():
    """Thẻ chi tiết ngoài MP (cùng builder tab/PDF): đủ số trung
    gian như thẻ trong MP (thép mặc định 2 nhánh, công thức Qb →
    thay số, ĐK (96), Asw/s) + kết luận riêng; thẻ trượt chỉ còn
    trượt. Quyết user 2026-10-25 thay P4 cũ Qsw = 0."""
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
    assert card["ref"] == "§8.1.3 (ánh xạ vách)"
    txt = "\n".join(card["lines"])
    assert "2φ12 a200" in txt
    # Không còn Qsw = 0 dạng kết quả (dòng công thức vẫn chứa
    # "Qsw = 0,75×..." — đó là công thức, không phải kết quả).
    assert "Qsw = 0.0 kN" not in txt and "(Qsw = 0)" not in txt
    assert "không bịa thép" not in txt
    assert "Công thức Qb" in txt and "469.7" in txt
    assert "2500" in txt and "307" in txt  # b × h0
    assert "D/C cắt ngoài MP" in card["result"]
    assert "D/C cắt ngoài MP = 0.504" in card["result"]
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
