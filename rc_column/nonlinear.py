"""Mô hình biến dạng phi tuyến (NDM) - TCVN 5574:2018, Điều 8.1.2.7.

- Tiết diện phẳng sau biến dạng: eps(x,y) = eps0 + kx * y + ky * x
  (nén dương; y hướng lên, x hướng phải).
- Ứng suất từng fiber theo quan hệ sigma-epsilon phi tuyến.
- Tích phân trên tiết diện -> (N, Mx, My).

Đơn vị: lực N (kN), mô men M (kN·m) khi kích thước tính bằng mm
(vì 1 N/mm² × mm² = N; đổi ra kN bằng /1000, mô men /1e6).
"""

import math
from typing import List, Tuple

from .materials import EPS_B2, EPS_S2
from .sections import Section


def section_forces(sec: Section, eps0: float, kx: float, ky: float,
                   concrete_model: str = "3line") -> Tuple[float, float, float]:
    """Tính (N, Mx, My) của tiết diện với trường biến dạng cho trước.

    Trả về N (kN, nén dương), Mx, My (kN·m).
    Mx: mô men quanh trục x (gây uốn trong mặt phẳng y).
    My: mô men quanh trục y.
    """
    conc = sec.concrete
    steel = sec.steel
    N = 0.0      # N (sẽ đổi ra kN)
    Mx = 0.0     # N·mm
    My = 0.0
    for f in sec.fibers:
        eps = eps0 + kx * f.y + ky * f.x
        sig = conc.stress(eps, concrete_model)  # MPa = N/mm²
        N += sig * f.area
        Mx += sig * f.area * f.y
        My += sig * f.area * f.x
    for r in sec.rebars:
        eps = eps0 + kx * r.y + ky * r.x
        sig = steel.stress(eps)
        N += sig * r.area
        Mx += sig * r.area * r.y
        My += sig * r.area * r.x
    return N / 1000.0, Mx / 1e6, My / 1e6


def uniaxial_curve(sec: Section, axis: str = "x",
                   concrete_model: str = "3line",
                   n_points: int = 60) -> List[Tuple[float, float]]:
    """Biểu đồ tương tác N-M một phương (uốn quanh trục axis).

    Quét trục trung hòa: biến dạng bê tông mép nén ngoài cùng đạt EPS_B2,
    thay đổi chiều cao vùng nén từ nén đúng tâm đến kéo đúng tâm.
    Trả về list (N [kN], M [kN·m]).
    """
    pts: List[Tuple[float, float]] = []
    conc = sec.concrete
    steel = sec.steel

    # Nửa kích thước theo phương uốn
    h = sec.cy if axis == "x" else sec.cx  # chiều cao tiết diện theo phương uốn

    # 1) Nén đúng tâm
    eps_c = EPS_B2 * 0.8  # biến dạng nén đều (lấy < eps_b2 để ổn định số)
    N0, _, _ = section_forces(sec, eps_c, 0.0, 0.0, concrete_model)
    pts.append((N0, 0.0))

    # 2) Quét trục trung hòa: c = khoảng cách từ mép nén tới trục trung hòa
    #    eps(y) = eps_cu * (1 - (y_top - y)/c) với y_top = h/2
    n_c = n_points
    for i in range(1, n_c):
        # c từ rất lớn (gần nén đều) đến rất nhỏ (gần uốn thuần) rồi sang kéo
        # dùng tham số t: t=0 -> c=inf, t=1 -> c=h, t>1 -> trục trung hòa ngoài
        t = i / n_c * 2.2  # tới 2.2 để bao cả vùng kéo lệch tâm
        if t < 1e-9:
            continue
        c = h / max(t, 1e-9)
        # eps tại mép trên (y = h/2) = eps_cu
        eps_cu = EPS_B2
        # eps(y) = eps0 + kx*y  -> tại y=h/2: eps_cu; tại y=h/2 - c: 0
        kx = eps_cu / c
        eps0 = eps_cu - kx * (h / 2.0)
        # kiểm tra biến dạng thép không vượt giới hạn
        ok = True
        for r in sec.rebars:
            yy = r.y if axis == "x" else r.x
            if abs(eps0 + kx * yy) > EPS_S2 + 1e-9:
                ok = False
                break
        if not ok:
            continue
        N, Mx, My = section_forces(sec, eps0, kx if axis == "x" else 0.0,
                                   kx if axis == "y" else 0.0, concrete_model)
        M = Mx if axis == "x" else My
        pts.append((N, M))

    # 3) Kéo đúng tâm
    eps_s = min(0.9 * EPS_S2, steel.Rs / steel.Es * 3.0)
    Nt, _, _ = section_forces(sec, -eps_s, 0.0, 0.0, concrete_model)
    pts.append((Nt, 0.0))

    # Sắp xếp theo N giảm dần để tiện nội suy
    pts.sort(key=lambda p: -p[0])
    return pts


def capacity_at_N(curve: List[Tuple[float, float]], N: float) -> float:
    """Nội suy mô men khả năng chịu tại lực dọc N từ đường cong (N, M)."""
    if not curve:
        return 0.0
    # curve đã sort theo N giảm dần
    if N >= curve[0][0]:
        return curve[0][1]
    if N <= curve[-1][0]:
        return curve[-1][1]
    for i in range(len(curve) - 1):
        n1, m1 = curve[i]
        n2, m2 = curve[i + 1]
        if n2 <= N <= n1 and abs(n1 - n2) > 1e-12:
            t = (N - n2) / (n1 - n2)
            return m2 + t * (m1 - m2)
    return 0.0


def rotate_section_forces(sec: Section, theta: float, eps0: float,
                          kappa: float,
                          concrete_model: str = "3line") -> Tuple[float, float, float]:
    """Tính (N, Mx, My) khi uốn xiên: trục trung hòa nghiêng góc theta.

    theta: góc của trục uốn (rad). Thực hiện bằng cách xoay hệ tọa độ:
    uốn trong mặt phẳng (x', y') với y' là phương của mô men.
    Đơn giản: đặt ky, kx sao cho độ cong theo hướng theta.
    """
    # Độ cong theo hướng vuông góc với trục trung hòa
    kx = kappa * math.cos(theta)
    ky = kappa * math.sin(theta)
    return section_forces(sec, eps0, kx, ky, concrete_model)
