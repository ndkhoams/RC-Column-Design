"""Hoi quy: diem A / goc alpha EC2 phai dung mo men thiet ke CO DAU.

Loi 2026-10-24: ban tom tat + chi tiet ve A tai (M3_mag, +M2_mag)
(trị khong dau -> lat dau M2, len tren truc, ngoai tia); ban chi tiet
tinh alpha/Malpha/|OA| tu mo men goc (-200/60 -> 286.7°/208.8/1514.5)
trong khi tia kiem tra D/C dung mo men thiet ke (-235.7/64.7 ->
285.4°/244.4/1519.8). GUI ve A bang mo men goc (dung goc phan tu
nhung sai do lon, lech tia 1.3°).
D/C solver khong doi (tinh tu mo men co dau) — chi sua hien thi.
"""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from rc_column.checker import ColumnInput, build_section
from rc_column.ec2_materials import EC2Concrete, EC2Steel
from gui.ec2_mixin import Ec2Mixin
from rc_column.ec2_chart_draw import (
    draw_ec2_m2m3_ax, ec2_signed_design_moments)


def _ec2_full(Mx, My):
    inp = ColumnInput(
        concrete_grade="B25", gamma_b=0.85, steel_grade="CB500-V",
        cx=500.0, cy=750.0, cover=30.0, sw_dia=10.0,
        corner_dia=28.0, edge_t2_count=5, edge_t2_dia=25.0,
        edge_t3_count=3, edge_t3_dia=25.0,
        Lx=10.16, Ly=1.26, psi_x=1.0, psi_y=1.0,
        top_x="ngam_cung", bottom_x="ngam_cung",
        top_y="ngam_cung", bottom_y="ngam_cung",
        N=1500.0, Mx=Mx, My=My, Q2=0.0, Q3=0.0)
    sec = build_section(inp)
    conc = EC2Concrete(fck=20.0)
    steel = EC2Steel(fyk=500.0)
    obj = object.__new__(Ec2Mixin)
    full = Ec2Mixin._ec2_calculate_full(
        obj, sec, conc, steel, inp, 1500.0, Mx, My, 0.0, 0.0,
        method="stiffness", fck=20.0, fyk_sw=500.0,
        phi_ef2=1.21, phi_ef3=1.21)
    return inp, sec, conc, steel, full


def _plotted_A(sec, conc, steel, full, m2s, m3s):
    fig, ax = plt.subplots()
    draw_ec2_m2m3_ax(ax, sec, conc, steel, full, 1500.0, m2s, m3s)
    pts = None
    for coll in ax.collections:
        fc = coll.get_facecolor()
        if len(fc) and abs(fc[0][1] - 0.588) < 0.05 and fc[0][0] < 0.1:
            pts = tuple(coll.get_offsets()[0])
    plt.close(fig)
    return pts


def test_signed_design_moments_user_case():
    inp, sec, conc, steel, full = _ec2_full(-200.0, 60.0)
    m2s, m3s = ec2_signed_design_moments(full, inp)
    assert m2s == math.copysign(full["M2_mag"], -1.0)
    assert m3s == math.copysign(full["M3_mag"], 1.0)
    assert abs(m2s + 235.654594603745) < 1e-9
    assert abs(m3s - 64.725) < 1e-9
    # D/C solver khong doi (moc truoc sua: 0.27632379132964613)
    assert full["dc"] == 0.27632379132964613
    assert abs(full["alpha_deg"] - 285.3581634018401) < 1e-9


def test_plotted_A_below_axis_on_ray():
    inp, sec, conc, steel, full = _ec2_full(-200.0, 60.0)
    m2s, m3s = ec2_signed_design_moments(full, inp)
    A = _plotted_A(sec, conc, steel, full, m2s, m3s)
    assert A is not None
    assert abs(A[0] - 64.725) < 1e-9 and abs(A[1] + 235.654594603745) < 1e-9
    # A tren tia O-B: cung huong (By, Bx)
    assert abs(A[0] * full["Bx"] - A[1] * full["By"]) < 1e-6


def test_detail_cards_use_design_moments():
    from rc_column.ec2_report_v2 import generate_ec2_report_sections_v2
    inp, sec, conc, steel, full = _ec2_full(-200.0, 60.0)
    sections = generate_ec2_report_sections_v2(
        inp, full, full.get("dm", {}), full.get("shear", {}), conc, steel,
        sec)
    s5 = next(s for s in sections if s["num"] == 5)
    s6 = next(s for s in sections if s["num"] == 6)
    c5 = next(c for c in s5["cards"] if "MEd" in c["title"])
    c6a = next(c for c in s6["cards"] if "Điểm nội lực" in c["title"])
    c6g = next(c for c in s6["cards"] if "Góc uốn xiên" in c["title"])
    assert any("MEd2 = -235.7" in l for l in c5["lines"])
    assert any("MEd3 = 64.7" in l for l in c5["lines"])
    assert any("(-235.7, 64.7, 1500.0)" in l for l in c6a["lines"])
    assert any("|OA| = 1519.8" in l for l in c6a["lines"])
    assert any("α = 285.4°" in l for l in c6g["lines"])
    assert any("Mα = 244.4" in l for l in c6g["lines"])


def test_quadrant_signs():
    for Mx, My in ((200.0, -60.0), (-200.0, -60.0), (200.0, 60.0)):
        inp, sec, conc, steel, full = _ec2_full(Mx, My)
        m2s, m3s = ec2_signed_design_moments(full, inp)
        assert (m2s > 0) == (Mx > 0) and (m3s > 0) == (My > 0)
        A = _plotted_A(sec, conc, steel, full, m2s, m3s)
        assert A is not None
        assert (A[0] > 0) == (My > 0) and (A[1] > 0) == (Mx > 0)
