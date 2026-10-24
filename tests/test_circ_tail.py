"""Hoi quy: luoi exact phai voi toi N = 0 va mien keo (fix D/C = inf o
cot tron it thep/fy thap — truoc fix, _ACIExact co N_min > 0 vi
eps_far chi toi -10*eps_y).

Ca do (so sau fix, cay 12346f1e + tail):
- ACI 5.2 (812.8, 8x#8, fy 275.79): N_min -982.0, cap0 350.67,
  dc(1000,100,100)=0.19085, dc(3000,200,200)=0.47564, dc(-500,100,100)=0.87935
- ACI 2.2 (914.4, 12x#9, fy 275.79): N_min -1889.6, cap0 725.81,
  dc(1000,100,100)=0.13456, dc(3000,200,200)=0.34702, dc(-500,100,100)=0.44241
- ACI tron nhieu thep (914, 20x#9, fy 420): cap0 KHONG DOI 1652.44,
  dc vung nen KHONG DOI (0.11405 / 0.29629); dc tai keo -500 = 0.17704
  (gia tri cu 0.19522 la artifact cat cut: tia cu cham tran N_min cu).
- TCVN tron 812.8 8xd25 B25/CB300-V: N_min -1021.0 (= keo thuan
  -As*Rs), cap0 337.24, dc = 0.19460 / 0.48845 / 0.87252;
  tai keo nong (-100,100,100) dc = 0.50538 (khong doi).
  LICH SU: truoc ho keo sau, dc(-500,100,100) = 1.86789 la GIA
  TRI BIEN LUOI (cliff), KHONG phai giao that — tia that van nam
  trong tai san luoi cu (-269.6, f = +184 tai BN) nen giao that
  sau hon san, dc that < 1.56. Ho keo sau (2026-10-24, xem
  test_tcvn_circle_deep_tension_family) noi sau diem noi
  (eps_cu, -0.9*EPS_S2): giu mep keo o san cu, ha mep nen
  eps_top tu eps_cu ve -0.01 toi keo thuan; dc(-500,100,100)
  moi = 0.87252 la GIAO THAT (closure fast +0.000%, fine
  +0.008% tai BN = -573.05). Test ghim so moi nay.
- EC2 tron 812.8 8xd25 C25/B400: N_min -1342.0, cap0 443.94,
  dc = 0.16328 / 0.40905 / 0.6524 (gia tri cu 4.4634 la artifact cat cut).
- EC2 tron 812.8 8xd16 C25/B400 (truoc fix: N_min +366.9, dc = inf):
  sau fix N_min < 0, cap0 > 0, dc huu han.

LICH SU (ho keo sau ACI/EC2, 2026-10-24, xem
test_aci_ec2_deep_tension_family): sau fix duoi luoi, ACI/EC2 van
con khe ho toi keo thuan thiet ke (5.2: N_min -982.0 vs keo thuan
thiet ke -0.9*As*fy = -1006.2; EC2 8xd25: -1342.0 vs -As*fyd =
-1365.9) nen tia cuc doan sat keo thuan bi ket san: ACI
(-1100,5,5) closure +43.4%, EC2 (-1360,5,5) capacity 0 tai san.
Ho keo sau noi sau diem noi (eps_cu, -0.20) — giu mep keo o san
cu, ha mep nen eps_top tu eps_cu ve -0.01 (cung buoc nhu ho
TCVN): N_min ve dung keo thuan thiet ke; 2 tia cuc doan ve giao
that (closure 0.000%). DAC BIET khoi chu nhat ACI/EC2: N(eps_top)
la ham bac thang theo na (fiber vao/ra nguyen con) nen chat doi
eps_top thuan tuy ket o mep buoc nhay — _deep_state_at_N noi suy
tuyen tinh qua buoc nhay (dung quy uoc day cung cua luoi fast)
nen fast-fine dong thuan trong mien sau.
"""

from rc_column.aci_materials import ACIConcrete, ACISteel
from rc_column.aci_checker import ACICapacity
from rc_column.ec2_checker import EC2Concrete, EC2Steel, EC2Capacity
from rc_column.interaction import BiaxialCapacity
from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.sections import (layout_circle_bars, layout_rect_bars,
                                make_circle_section, make_rect_section)


def _aci_circle(dia, bar_dia, n, fc=27.579, fy=275.79, cover=30.1):
    conc = ACIConcrete(fc)
    steel = ACISteel(fy)
    sec = make_circle_section(dia, conc, steel)
    layout_circle_bars(sec, bar_dia, n, cover, 8.0)
    return ACICapacity(sec, conc, steel, tied=True)


def _check_dc(cap, cases):
    for (N, Mx, My), expect in cases:
        dc = cap.dc_ratio(N, Mx, My)["dc"]
        assert dc == dc and dc != float("inf"), (N, Mx, My, dc)
        assert abs(dc - expect) < 2e-3, (N, Mx, My, dc, expect)


def test_aci_circle_low_steel_dc_finite():
    cap52 = _aci_circle(812.8, 25.4, 8)
    assert cap52._exact.N_min < 0, cap52._exact.N_min
    assert cap52.moment_capacity(0.0, 0.0) > 0
    _check_dc(cap52, [((1000, 100, 100), 0.19085),
                      ((3000, 200, 200), 0.47564),
                      ((-500, 100, 100), 0.87935)])
    cap22 = _aci_circle(914.4, 28.65, 12)
    assert cap22._exact.N_min < 0, cap22._exact.N_min
    assert cap22.moment_capacity(0.0, 0.0) > 0
    _check_dc(cap22, [((1000, 100, 100), 0.13456),
                      ((3000, 200, 200), 0.34702),
                      ((-500, 100, 100), 0.44241)])


def test_aci_circle_heavy_compression_unchanged_tension_corrected():
    capH = _aci_circle(914.0, 28.65, 20, fy=420.0)
    assert abs(capH.moment_capacity(0.0, 0.0) - 1652.44) < 1.0
    _check_dc(capH, [((1000, 100, 100), 0.11405),
                     ((3000, 200, 200), 0.29629),
                     ((-500, 100, 100), 0.17704)])


def test_tcvn_circle_low_steel_dc_finite():
    conc = ConcreteMaterial(CONCRETE_GRADES["B25"], 1.0)
    steel = SteelMaterial(STEEL_GRADES["CB300-V"], 1.0)
    sec = make_circle_section(812.8, conc, steel)
    layout_circle_bars(sec, 25.0, 8, 30.0, 8.0)
    cap = BiaxialCapacity(sec)
    assert cap._exact.N_min < 0, cap._exact.N_min
    assert cap.moment_capacity(0.0, 0.0) > 0
    _check_dc(cap, [((1000, 100, 100), 0.19460),
                    ((3000, 200, 200), 0.48845),
                    ((-100, 100, 100), 0.50538),
                    ((-500, 100, 100), 0.87252)])


def _tcvn_circle_cap():
    conc = ConcreteMaterial(CONCRETE_GRADES["B25"], 1.0)
    steel = SteelMaterial(STEEL_GRADES["CB300-V"], 1.0)
    sec = make_circle_section(812.8, conc, steel)
    layout_circle_bars(sec, 25.0, 8, 30.0, 8.0)
    return BiaxialCapacity(sec)


def test_tcvn_circle_deep_tension_family():
    """Ho keo sau TCVN (noi sau diem noi (eps_cu, -0.9*EPS_S2)):
    - N_min ve dung keo thuan -As*Rs = -1021.0 kN (truoc: -269.6);
    - capacity lien tuc qua diem noi cu (-269.6): khong vach ve 0,
      khong nhay (cap(-280) nam giua cap(-269.6) va cap(-300));
    - fast-fine dong thuan trong mien keo sau (< 1%);
    - dc(-500,100,100) la giao that: closure tai BN ~ 0%."""
    import math
    cap = _tcvn_circle_cap()
    assert abs(cap._exact.N_min - (-1021.02)) < 1.0, cap._exact.N_min
    c_j = cap.moment_capacity(-269.6, 45.0)
    c_a = cap.moment_capacity(-260.0, 45.0)
    c_b = cap.moment_capacity(-280.0, 45.0)
    assert c_a > c_j > c_b > 0, (c_a, c_j, c_b)
    assert abs(c_j - 259.63) < 1.0, c_j
    for N in (-400.0, -600.0, -900.0):
        f = cap.moment_capacity(N, 45.0)
        e = cap.exact_capacity(N, 45.0)
        assert abs(f - e) / e < 0.01, (N, f, e)
    r = cap.dc_ratio(-500, 100, 100)
    assert abs(r["dc"] - 0.87252) < 2e-3, r["dc"]
    lam = 1.0 / r["dc"]
    BN = lam * (-500.0)
    Bmag = lam * math.hypot(100.0, 100.0)
    capB = cap.moment_capacity(BN, 45.0)
    assert abs(capB - Bmag) / Bmag < 0.005, (BN, capB, Bmag)
    # Diem bien fine o mien keo sau phai thuoc ho moi
    # (eps_top < eps_cu) va tai dung duoc mat phang bien dang.
    b = cap._exact.boundary_fine(BN, 45.0)
    assert b is not None and b["eps_top"] < 0.0035, b
    from rc_column.interaction import FiberSection, neutral_axis_at_N
    na = neutral_axis_at_N(FiberSection(cap.fs.sec), BN, 45.0)
    assert na["found"], na
    _g = math.radians(na["gamma_deg"])
    _N, _Mx, _My = FiberSection(cap.fs.sec).forces(
        na["eps0"], na["kx_p"] * math.sin(_g),
        na["kx_p"] * math.cos(_g), "3line")
    assert abs(_N - BN) < 1.0, (_N, BN)
    assert abs(_Mx - lam * 100.0) < 1.0, (_Mx, lam * 100.0)


def test_tcvn_rect_deep_tension_reaches_pure_tension():
    """Tiet dien chu nhat cung ve toi keo thuan (khong rieng tron):
    600x600, thep chu vi d20 (3x3 chu vi = 8 thanh, CB400-V,
    Rs = 350): keo thuan = -8*314.16*350/1000 = -879.6 kN;
    tia keo sau (-800, 50, 50) phai co giao that (closure < 0.5%)."""
    import math
    conc = ConcreteMaterial(CONCRETE_GRADES["B25"], 1.0)
    steel = SteelMaterial(STEEL_GRADES["CB400-V"], 1.0)
    sec = make_rect_section(600.0, 600.0, conc, steel)
    layout_rect_bars(sec, 20.0, 3, 3, 30.0, 8.0)
    cap = BiaxialCapacity(sec)
    n_bar = len(sec.rebars)
    pure = -n_bar * (math.pi * 20.0 ** 2 / 4.0) * 350.0 / 1000.0
    assert abs(cap._exact.N_min - pure) < 2.0, (cap._exact.N_min, pure)
    r = cap.dc_ratio(-800, 50, 50)
    assert r["dc"] == r["dc"] and r["dc"] != float("inf"), r
    lam = 1.0 / r["dc"]
    BN = lam * (-800.0)
    Bmag = lam * math.hypot(50.0, 50.0)
    alpha = math.degrees(math.atan2(50.0, 50.0))
    capB = cap.moment_capacity(BN, alpha)
    assert abs(capB - Bmag) / Bmag < 0.005, (BN, capB, Bmag)


def test_aci_ec2_deep_tension_family():
    """Ho keo sau ACI/EC2 (noi sau diem noi (eps_cu, -0.20)):
    - N_min ve dung keo thuan THIET KE: ACI 5.2 -1006.2
      (-0.9*As*fy), ACI 2.2 -1920.2, EC2 8xd25 -1365.9 (-As*fyd),
      EC2 8xd16 -559.5 (truoc: -982.0 / -1889.6 / -1342.0 / -535.6);
    - capacity lien tuc qua diem noi, khong vach ve 0;
    - fast-fine dong thuan trong mien keo sau (< 1%);
    - 2 tia cuc doan ve giao that: ACI (-1100,5,5) dc 1.11105
      (truoc 1.12020 ket san, closure +43.4%), EC2 (-1360,5,5)
      dc 1.00877 (truoc 1.01340, capacity 0 tai san);
    - diem bien fine o mien sau thuoc ho moi (eps_top < eps_cu)
      va neutral_axis tai dung duoc mat phang (eps_top, kappa)."""
    import math
    # --- ACI 5.2 ---
    cap52 = _aci_circle(812.8, 25.4, 8)
    assert abs(cap52._exact.N_min - (-1006.16)) < 1.0, cap52._exact.N_min
    c_a = cap52.moment_capacity(-950.0, 45.0)
    c_j = cap52.moment_capacity(-980.0, 45.0)
    c_b = cap52.moment_capacity(-1000.0, 45.0)
    assert c_a > c_j > c_b > 0, (c_a, c_j, c_b)
    for N in (-980.0, -1000.0, -1005.0):
        f = cap52.moment_capacity(N, 45.0)
        e = cap52.exact_capacity(N, 45.0)
        assert abs(f - e) / e < 0.01, (N, f, e)
    r = cap52.dc_ratio(-1100, 5, 5)
    assert abs(r["dc"] - 1.11105) < 2e-3, r["dc"]
    lam = 1.0 / r["dc"]
    BN = lam * (-1100.0)
    Bmag = lam * math.hypot(5.0, 5.0)
    alpha = math.degrees(math.atan2(5.0, 5.0))
    capB = cap52.moment_capacity(BN, alpha)
    assert abs(capB - Bmag) / Bmag < 0.005, (BN, capB, Bmag)
    capF = cap52.exact_capacity(BN, alpha)
    assert abs(capF - Bmag) / Bmag < 0.01, (BN, capF, Bmag)
    b = cap52._exact.boundary_fine(BN, alpha)
    assert b is not None and b["eps_top"] < 0.003, b
    from rc_column.aci_checker import aci_neutral_axis_at_N
    concA = ACIConcrete(27.579)
    steelA = ACISteel(275.79)
    secA = make_circle_section(812.8, concA, steelA)
    layout_circle_bars(secA, 25.4, 8, 30.1, 8.0)
    na = aci_neutral_axis_at_N(secA, concA, steelA, BN, alpha)
    # Truc trung hoa o mep (yp_na ~= y_top trong sai so float) hoac
    # ngoai tiet dien -> khong co vung nen nhin thay.
    assert na["found"] and na["yp_na"] >= na["y_top"] - 1e-6, na
    assert abs(na["eps0"] - (b["eps_top"] - b["kappa"] * b["s_max"])) < 1e-9
    # --- ACI 2.2 ---
    cap22 = _aci_circle(914.4, 28.65, 12)
    assert abs(cap22._exact.N_min - (-1920.2)) < 1.0, cap22._exact.N_min
    f = cap22.moment_capacity(-1900.0, 45.0)
    e = cap22.exact_capacity(-1900.0, 45.0)
    assert abs(f - e) / e < 0.01, (-1900.0, f, e)
    # --- EC2 8xd25 ---
    concE = EC2Concrete(25.0)
    steelE = EC2Steel(400.0)
    secE = make_circle_section(812.8, concE, steelE)
    layout_circle_bars(secE, 25.0, 8, 30.0, 8.0)
    capE = EC2Capacity(secE, concE, steelE)
    assert abs(capE._exact.N_min - (-1365.9)) < 1.0, capE._exact.N_min
    c_a = capE.moment_capacity(-1330.0, 45.0)
    c_b = capE.moment_capacity(-1350.0, 45.0)
    assert c_a > c_b > 0, (c_a, c_b)
    f = capE.moment_capacity(-1350.0, 45.0)
    e = capE.exact_capacity(-1350.0, 45.0)
    assert abs(f - e) / e < 0.01, (-1350.0, f, e)
    rE = capE.dc_ratio(-1360, 5, 5)
    assert abs(rE["dc"] - 1.00877) < 2e-3, rE["dc"]
    lamE = 1.0 / rE["dc"]
    BNE = lamE * (-1360.0)
    BmagE = lamE * math.hypot(5.0, 5.0)
    capBE = capE.moment_capacity(BNE, alpha)
    assert abs(capBE - BmagE) / BmagE < 0.005, (BNE, capBE, BmagE)
    capFE = capE.exact_capacity(BNE, alpha)
    assert abs(capFE - BmagE) / BmagE < 0.01, (BNE, capFE, BmagE)
    bE = capE._exact.boundary_fine(BNE, alpha)
    assert bE is not None and bE["eps_top"] < 0.0035, bE
    from rc_column.ec2_checker import ec2_neutral_axis_at_N
    naE = ec2_neutral_axis_at_N(secE, concE, steelE, BNE, alpha)
    assert naE["found"] and naE["yp_na"] >= naE["y_top"] - 1e-6, naE
    assert abs(naE["eps0"] - (bE["eps_top"] - bE["kappa"] * bE["s_max"])) < 1e-9
    # --- EC2 8xd16 ---
    sec16 = make_circle_section(812.8, concE, steelE)
    layout_circle_bars(sec16, 16.0, 8, 30.0, 8.0)
    cap16 = EC2Capacity(sec16, concE, steelE)
    assert abs(cap16._exact.N_min - (-559.5)) < 1.0, cap16._exact.N_min


def test_aci_rect_scalar_fallback_deep_tension():
    """Duong scalar fallback (>3000 fiber) cung co ho keo sau: chu
    nhat 600x600, luoi 60x60 = 3600 fiber, 12xd25 chu vi, fy 275.79:
    N_min ve dung keo thuan thiet ke -0.9*As*fy = -1462.08 kN;
    tia keo sau co giao that (closure fast 0.000%; fine < 5% —
    chu nhat co do lech fine san ~3.5% ca o mien cu do buoc
    gamma/luoi fiber, khong rieng mien sau)."""
    import math
    concA = ACIConcrete(27.579)
    steelA = ACISteel(275.79)
    secR = make_rect_section(600.0, 600.0, concA, steelA, nx=60, ny=60)
    layout_rect_bars(secR, 25.0, 4, 4, 30.0, 8.0)
    assert len(secR.fibers) > 3000, len(secR.fibers)
    capR = ACICapacity(secR, concA, steelA, tied=True)
    pureR = -0.9 * sum(rb.area for rb in secR.rebars) * 275.79 / 1000.0
    assert abs(capR._exact.N_min - pureR) < 1.0, (capR._exact.N_min, pureR)
    r = capR.dc_ratio(pureR * 1.05, 5, 5)
    assert abs(r["dc"] - 1.06194) < 2e-3, r["dc"]
    lam = 1.0 / r["dc"]
    BN = lam * pureR * 1.05
    Bmag = lam * math.hypot(5.0, 5.0)
    alpha = math.degrees(math.atan2(5.0, 5.0))
    capB = capR.moment_capacity(BN, alpha)
    assert abs(capB - Bmag) / Bmag < 0.005, (BN, capB, Bmag)
    capF = capR.exact_capacity(BN, alpha)
    assert abs(capF - Bmag) / Bmag < 0.05, (BN, capF, Bmag)


def test_ec2_circle_low_steel_dc_finite():
    conc = EC2Concrete(25.0)
    steel = EC2Steel(400.0)
    sec = make_circle_section(812.8, conc, steel)
    layout_circle_bars(sec, 25.0, 8, 30.0, 8.0)
    cap = EC2Capacity(sec, conc, steel)
    assert cap._exact.N_min < 0, cap._exact.N_min
    assert cap.moment_capacity(0.0, 0.0) > 0
    _check_dc(cap, [((1000, 100, 100), 0.16328),
                    ((3000, 200, 200), 0.40905),
                    ((-500, 100, 100), 0.6524)])
    sec16 = make_circle_section(812.8, conc, steel)
    layout_circle_bars(sec16, 16.0, 8, 30.0, 8.0)
    cap16 = EC2Capacity(sec16, conc, steel)
    assert cap16._exact.N_min < 0, cap16._exact.N_min
    assert cap16.moment_capacity(0.0, 0.0) > 0
    # Ca keo (-500) cua d16 co BN = -318.3, tren san -535.6 -> giao
    # that, closure +0.00% (khac ca TCVN -500 la bien luoi).
    _check_dc(cap16, [((1000, 100, 100), 0.18036),
                      ((-500, 100, 100), 1.57063)])
