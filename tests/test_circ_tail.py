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
- TCVN tron 812.8 8xd25 B25/CB300-V: N_min -269.6, cap0 337.24,
  dc = 0.19460 / 0.48845 / 1.86789; tai keo nong (-100,100,100)
  dc = 0.50538 (giao that, closure +0.00%).
  LUU Y: dc(-500,100,100) = 1.86789 la GIA TRI BIEN LUOI (cliff),
  KHONG phai giao that — tia that van nam trong tai san luoi
  (f = +184 tai BN) nen giao that sau hon san (-269.6), dc that
  < 1.56 (chan tren tu san ho thep + chan duoi tu keo thuan 0.49);
  gia tri bien nay BAO THU (dc cao hon that). Gioi han cua ho
  trang thai eps_cu co dinh + gioi han dut EPS_S2 = 0.025 (na
  khong nho hon ~109mm) — muon dc that cho tai keo sau TCVN can
  ho trang thai moi (mep nen < eps_cu), viec rieng, khong lam
  trong dot "sua ngay" nay. Test ghim dung so hien tai de doi
  thay doi hanh vi sau nay bi phat hien.
- EC2 tron 812.8 8xd25 C25/B400: N_min -1342.0, cap0 443.94,
  dc = 0.16328 / 0.40905 / 0.6524 (gia tri cu 4.4634 la artifact cat cut).
- EC2 tron 812.8 8xd16 C25/B400 (truoc fix: N_min +366.9, dc = inf):
  sau fix N_min < 0, cap0 > 0, dc huu han.
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
                    ((-500, 100, 100), 1.86789)])


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
