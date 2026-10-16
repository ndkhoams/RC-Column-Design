"""Test engine EC2 (Eurocode 2).

(a) fcd/fyd tính đúng
(b) điểm nén đúng tâm ≈ Ac·fcd + As·fyd
(c) D/C với tải nhỏ < 1
(d) VRd,c / VRd,max hợp lý
(e) so sánh với ACI cùng tiết diện: cùng bậc độ lớn
"""

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rc_column.ec2_materials import EC2Concrete, EC2Steel
from rc_column.ec2_checker import (
    EC2Capacity, check_column_ec2, ec2_interaction_curve,
    ec2_imperfection, ec2_slenderness_params, ec2_design_moment,
    ec2_shear_check,
)
from rc_column.sections import make_rect_section, layout_rect_bars, bar_area


def make_test_section():
    """Cột 400×400, C30/37, 8d20, cover 40."""
    conc = EC2Concrete(30.0)
    steel = EC2Steel(500.0)
    sec = make_rect_section(400.0, 400.0, None, None)
    layout_rect_bars(sec, 20.0, 3, 3, 40.0)
    return sec, conc, steel


def test_materials():
    conc = EC2Concrete(30.0)
    steel = EC2Steel(500.0)
    assert abs(conc.fcd - 30.0 / 1.5) < 1e-9, f"fcd={conc.fcd}"
    assert abs(conc.fcm - 38.0) < 1e-9
    assert abs(conc.Ecm - 22000 * (3.8) ** 0.3) < 1e-6
    assert abs(conc.eps_cu - 0.0035) < 1e-12
    assert abs(conc.lam - 0.8) < 1e-12 and abs(conc.eta - 1.0) < 1e-12
    assert abs(conc.f_block - conc.fcd) < 1e-12
    assert abs(steel.fyd - 500.0 / 1.15) < 1e-9, f"fyd={steel.fyd}"
    assert abs(steel.Es - 200000.0) < 1e-9
    print("  (a) vật liệu OK: fcd=%.2f MPa, fyd=%.1f MPa, Ecm=%.0f MPa"
          % (conc.fcd, steel.fyd, conc.Ecm))


def test_pure_compression():
    sec, conc, steel = make_test_section()
    cap = EC2Capacity(sec, conc, steel)
    Ag = sec.gross_area
    As = sec.steel_area
    expect = ((Ag - As) * conc.fcd + As * steel.fyd) / 1000.0  # kN
    got = cap.N_Rd_max
    err = abs(got - expect) / expect
    assert err < 0.02, f"N_Rd_max={got:.1f}, expect={expect:.1f}"
    # Điểm đầu đường cong cũng phải khớp
    curve = ec2_interaction_curve(sec, conc, steel, 0.0)
    assert abs(curve[0][0] - expect) / expect < 0.02
    print("  (b) nén đúng tâm OK: N_Rd,max=%.1f kN (kỳ vọng %.1f kN)"
          % (got, expect))


def test_dc_small_load():
    sec, conc, steel = make_test_section()
    res = check_column_ec2(sec, conc, steel, N_kN=500.0,
                           M2_kNm=30.0, M3_kNm=40.0)
    assert 0 < res["dc"] < 1.0, f"dc={res['dc']}"
    assert res["ok"]
    print("  (c) D/C tải nhỏ OK: dc=%.3f, FS=%.2f"
          % (res["dc"], res["fs"]))


def test_dc_overload():
    sec, conc, steel = make_test_section()
    res = check_column_ec2(sec, conc, steel, N_kN=3000.0,
                           M2_kNm=400.0, M3_kNm=500.0)
    assert res["dc"] > 1.0, f"dc={res['dc']}"
    assert not res["ok"]
    print("  (c2) D/C quá tải OK: dc=%.3f -> KHÔNG ĐẠT" % res["dc"])


def test_shear():
    # Cột 400×400, C30/37, d≈340, bw=400
    r = ec2_shear_check(bw_mm=400.0, d_mm=340.0, Ac_mm2=160000.0,
                        fck_MPa=30.0, NEd_kN=1000.0, VEd_kN=150.0,
                        Asl_mm2=1500.0, fyd_MPa=500.0 / 1.15,
                        Asw_s_mm2mm=0.0)
    assert r["VRd_c_kN"] > 50.0, f"VRd,c={r['VRd_c_kN']}"
    assert r["VRd_max_kN"] > r["VRd_c_kN"], \
        f"VRd,max={r['VRd_max_kN']} <= VRd,c={r['VRd_c_kN']}"
    assert r["VRd_max_kN"] < 3000.0, f"VRd,max quá lớn: {r['VRd_max_kN']}"
    assert r["ok"]  # VEd=150 < VRd,c -> không cần đai
    # Vượt VRd,c -> yêu cầu đai
    r2 = ec2_shear_check(bw_mm=400.0, d_mm=340.0, Ac_mm2=160000.0,
                         fck_MPa=30.0, NEd_kN=1000.0, VEd_kN=400.0,
                         Asl_mm2=1500.0, fyd_MPa=500.0 / 1.15,
                         Asw_s_mm2mm=2 * bar_area(8) / 150.0)
    assert r2["Asw_s_req"] > 0
    print("  (d) cắt OK: VRd,c=%.1f kN, VRd,max=%.1f kN, "
          "Asw/s yêu cầu=%.3f mm²/mm"
          % (r["VRd_c_kN"], r["VRd_max_kN"], r2["Asw_s_req"]))


def test_slenderness():
    # Cột 400×400, l0=4m, NEd=1500 kN
    imp = ec2_imperfection(4.0)
    assert abs(imp["alpha_h"] - 1.0) < 1e-9  # 2/sqrt(4)=1
    assert abs(imp["theta_i"] - 1.0 / 200.0) < 1e-12
    assert abs(imp["ei_mm"] - (1 / 200) * 4000 / 2) < 1e-9
    sl = ec2_slenderness_params(NEd_kN=1500.0, M01_kNm=50.0, M02_kNm=80.0,
                                l0_mm=4000.0, i_mm=400 / math.sqrt(12),
                                Ac_mm2=160000.0, As_mm2=2500.0,
                                fcd_MPa=20.0, fyd_MPa=500 / 1.15)
    assert 30.0 < sl["lambda_sl"] < 40.0, f"λ={sl['lambda_sl']}"
    assert sl["lambda_lim"] > 10.0, f"λlim={sl['lambda_lim']}"
    print("  imperfection OK: θi=%.5f, ei=%.1f mm; λ=%.1f, λlim=%.1f"
          % (imp["theta_i"], imp["ei_mm"],
             sl["lambda_sl"], sl["lambda_lim"]))
    # Bậc 2: cột mảnh
    r = ec2_design_moment(NEd_kN=1500.0, M_top_kNm=80.0, M_bot_kNm=50.0,
                          l0_mm=6000.0, i_mm=400 / math.sqrt(12), h_mm=400.0,
                          Ac_mm2=160000.0, As_mm2=2500.0,
                          fcd_MPa=20.0, fyd_MPa=500 / 1.15,
                          Ecm_MPa=33000.0, Ic_mm4=400 * 400 ** 3 / 12,
                          Is_mm4=1e8, Es_MPa=200000.0, fck_MPa=30.0)
    assert r["ok"]
    assert r["MEd"] >= r["Mmin"] - 1e-9
    print("  bậc 2 OK: MEd=%.1f kN·m (M0Ed=%.1f, factor=%.3f), "
          "Mmin=%.1f" % (r["MEd"], r.get("so_M0Ed", 0),
                         r.get("so_factor", 1), r["Mmin"]))
    # Kéo: bỏ qua
    rt = ec2_design_moment(NEd_kN=-200.0, M_top_kNm=80.0, M_bot_kNm=50.0,
                           l0_mm=6000.0, i_mm=115.0, h_mm=400.0,
                           Ac_mm2=160000.0, As_mm2=2500.0,
                           fcd_MPa=20.0, fyd_MPa=435.0,
                           Ecm_MPa=33000.0, Ic_mm4=2.13e9, Is_mm4=1e8,
                           Es_MPa=200000.0, fck_MPa=30.0)
    assert rt["tension"] and not rt["second_order"]
    print("  kéo OK: bỏ qua sai lệch & bậc 2")


def test_vs_aci():
    """So sánh EC2 với ACI cùng tiết diện 400×400, 8d20."""
    from rc_column.aci_materials import ACIConcrete, ACISteel
    from rc_column.aci_checker import check_column_aci
    sec, conc_ec2, steel_ec2 = make_test_section()
    conc_aci = ACIConcrete(30.0)
    steel_aci = ACISteel(420.0)
    N, M2, M3 = 1500.0, 120.0, 200.0
    r_ec2 = check_column_ec2(sec, conc_ec2, steel_ec2, N, M2, M3)
    r_aci = check_column_aci(sec, conc_aci, steel_aci, N, M2, M3, tied=True)
    ratio = r_ec2["dc"] / r_aci["dc"] if r_aci["dc"] > 0 else float("inf")
    # Cùng bậc độ lớn: tỉ số trong khoảng 0.3..3
    assert 0.3 < ratio < 3.0, \
        f"EC2 dc={r_ec2['dc']:.3f}, ACI dc={r_aci['dc']:.3f}, ratio={ratio:.2f}"
    print("  (e) so với ACI OK: EC2 dc=%.3f, ACI dc=%.3f (tỉ số %.2f)"
          % (r_ec2["dc"], r_aci["dc"], ratio))


def test_report_and_pdf(tmpdir="/tmp"):
    """Sinh report sections + 2 PDF (thuyết minh & tóm tắt)."""
    import types
    sec, conc, steel = make_test_section()
    res = check_column_ec2(sec, conc, steel, 1500.0, 120.0, 200.0)
    sl2 = ec2_design_moment(
        NEd_kN=1500.0, M_top_kNm=120.0, M_bot_kNm=120.0, l0_mm=4000.0,
        i_mm=400 / math.sqrt(12), h_mm=400.0, Ac_mm2=160000.0,
        As_mm2=sec.steel_area, fcd_MPa=conc.fcd, fyd_MPa=steel.fyd,
        Ecm_MPa=conc.Ecm, Ic_mm4=400 * 400 ** 3 / 12, Is_mm4=1e8,
        Es_MPa=steel.Es, fck_MPa=conc.fck)
    sl3 = ec2_design_moment(
        NEd_kN=1500.0, M_top_kNm=200.0, M_bot_kNm=200.0, l0_mm=4000.0,
        i_mm=400 / math.sqrt(12), h_mm=400.0, Ac_mm2=160000.0,
        As_mm2=sec.steel_area, fcd_MPa=conc.fcd, fyd_MPa=steel.fyd,
        Ecm_MPa=conc.Ecm, Ic_mm4=400 * 400 ** 3 / 12, Is_mm4=1e8,
        Es_MPa=steel.Es, fck_MPa=conc.fck)
    slend = {"dir2": sl2, "dir3": sl3}
    sh2 = ec2_shear_check(400.0, 340.0, 160000.0, 30.0, 1500.0, 150.0,
                          sec.steel_area / 2, steel.fyd,
                          2 * bar_area(8) / 150.0)
    sh3 = ec2_shear_check(400.0, 340.0, 160000.0, 30.0, 1500.0, 180.0,
                          sec.steel_area / 2, steel.fyd,
                          2 * bar_area(8) / 150.0)
    shear = {"dir2": sh2, "dir3": sh3}

    inp = types.SimpleNamespace(
        N=1500.0, Mx=120.0, My=200.0, Q2=150.0, Q3=180.0,
        cx=400.0, cy=400.0, cover=40.0,
        sw_dia=8.0, sw_spacing=150.0, sw_legs=2,
        Lx=4.0, Ly=4.0, top_x="ngam", bottom_x="ngam",
        top_y="ngam", bottom_y="ngam", psi_x=None, psi_y=None,
        _filename="cot_c1.json")

    from rc_column.ec2_report import generate_ec2_report_sections
    secs = generate_ec2_report_sections(inp, res, slend, shear, conc, steel)
    assert len(secs) == 4, f"số mục={len(secs)}"
    assert secs[0]["num"] == 1 and secs[3]["num"] == 4
    print("  report sections OK: %d mục" % len(secs))

    from rc_column.ec2_pdf_report import export_ec2_pdf_cards
    p1 = os.path.join(tmpdir, "test_ec2_thuyetminh.pdf")
    export_ec2_pdf_cards(inp, res, slend, shear, conc, steel, p1)
    assert os.path.getsize(p1) > 10000, "PDF thuyết minh quá nhỏ"
    print("  PDF thuyết minh OK: %d bytes" % os.path.getsize(p1))

    from rc_column.ec2_pdf_summary import export_ec2_summary_pdf
    p2 = os.path.join(tmpdir, "test_ec2_tomtat.pdf")
    export_ec2_summary_pdf(sec, inp, res, conc, steel, p2,
                           slend_res=slend)
    assert os.path.getsize(p2) > 10000, "PDF tóm tắt quá nhỏ"
    print("  PDF tóm tắt OK: %d bytes" % os.path.getsize(p2))


if __name__ == "__main__":
    print("== Test EC2 ==")
    test_materials()
    test_pure_compression()
    test_dc_small_load()
    test_dc_overload()
    test_shear()
    test_slenderness()
    test_vs_aci()
    test_report_and_pdf()
    print("TẤT CẢ TEST EC2 PASS")
