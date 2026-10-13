"""Kiểm chứng engine tính toán."""

import math

from rc_column.checker import ColumnInput, build_section, check_column
from rc_column.interaction import BiaxialCapacity, FiberSection, uniaxial_curve_fs
from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES, ConcreteMaterial,
                                 SteelMaterial)
from rc_column.sections import make_rect_section, layout_rect_bars
from rc_column.stability import effective_length, phi_L, LongTermLoads


def test_materials():
    b25 = CONCRETE_GRADES["B25"]
    assert abs(b25.Rb - 14.5) < 1e-9
    cb400 = STEEL_GRADES["CB400-V"]
    assert abs(cb400.Rs - 350.0) < 1e-9
    c = ConcreteMaterial(b25, 1.0)
    assert c.stress(-0.001) == 0.0           # bỏ qua kéo
    assert 0 < c.stress(0.001) < c.Rb        # parabol
    assert abs(c.stress(0.003) - c.Rb) < 1e-9  # chữ nhật
    s = SteelMaterial(cb400, 1.0)
    assert abs(s.stress(0.001) - 2.1e5 * 0.001) < 1e-6
    assert abs(s.stress(0.01) - 350.0) < 1e-9


def test_pure_compression():
    # Nén đúng tâm 400x400 B25 + 8d20 ≈ Rb*Ag + Rsc*As
    inp = ColumnInput(concrete_grade="B25", steel_grade="CB400-V",
                      section_type="rect", cx=400, cy=400,
                      bar_dia=20, nx=3, ny=3, cover=30,
                      N=0, Mx=0, My=0)
    sec = build_section(inp)
    cap = BiaxialCapacity(sec, n_angles=4)
    nmax = cap.curves[0.0][0][0]
    expected = (14.5 * 160000 + 350 * sec.steel_area) / 1000.0
    assert abs(nmax - expected) / expected < 0.05, (nmax, expected)


def test_uniaxial_symmetry():
    # Tiết diện đối xứng: M(θ=0) ≈ M(θ=180)
    inp = ColumnInput(section_type="rect", cx=400, cy=400,
                      bar_dia=20, nx=3, ny=3, cover=30)
    sec = build_section(inp)
    fs = FiberSection(sec)
    c0 = uniaxial_curve_fs(fs, 0.0)
    c180 = uniaxial_curve_fs(fs, 180.0)
    m0 = max(p[1] for p in c0)
    m180 = max(p[1] for p in c180)
    assert abs(m0 - m180) / max(m0, 1e-9) < 0.05, (m0, m180)


def test_biaxial_check_sane():
    inp = ColumnInput(N=1500, Mx=80, My=60)
    res = check_column(inp, n_angles=12)
    assert 0 < res.utilization < 1.0
    assert res.ok
    # tăng tải gấp 3 -> không đạt
    inp2 = ColumnInput(N=1500, Mx=240, My=180)
    res2 = check_column(inp2, n_angles=12)
    assert not res2.ok


def test_circle_section():
    inp = ColumnInput(section_type="circle", cx=500, bar_dia=22,
                      n_bars=10, cover=30, N=2000, Mx=100, My=80)
    res = check_column(inp, n_angles=12)
    assert res.ok and res.utilization > 0


def test_stability():
    assert abs(effective_length(4.0, "khop", "khop") - 4.0) < 1e-9
    assert abs(effective_length(4.0, "ngam", "ngam") - 2.0) < 1e-9
    assert abs(effective_length(4.0, "khop", "khop", psi=0.8) - 3.2) < 1e-9
    assert phi_L(1000, 50, 50, LongTermLoads(False)) == 2.0
    p = phi_L(1000, 100, 0, LongTermLoads(True, 500, 50, 0))
    assert 1.0 <= p <= 2.0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
    print("Tất cả test passed.")
