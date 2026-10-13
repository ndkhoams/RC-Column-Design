"""Biểu đồ tương tác và kiểm tra nén uốn xiên (N + Mx + My) bằng NDM.

Phương pháp:
- Rời rạc tiết diện thành fiber (numpy, vector hóa).
- Với mỗi góc uốn theta: xoay hệ tọa độ, phân tích một phương (quét trục
  trung hòa với biến dạng bê tông mép nén đạt eps_cu) -> đường cong (N, M).
- Kiểm tra (N, Mx, My): tính M = sqrt(Mx²+My²), phi = atan2(My, Mx),
  nội suy khả năng chịu từ các đường cong theo góc -> hệ số sử dụng.

Đơn vị: N (kN), M (kN·m), kích thước (mm).
"""

import math
from typing import Dict, List, Tuple

import numpy as np

from .materials import EPS_B2, EPS_S2
from .sections import Section


class FiberSection:
    """Tiết diện dạng mảng numpy để tính nhanh."""

    def __init__(self, sec: Section):
        self.sec = sec
        self.fx = np.array([f.x for f in sec.fibers], dtype=float)
        self.fy = np.array([f.y for f in sec.fibers], dtype=float)
        self.fa = np.array([f.area for f in sec.fibers], dtype=float)
        self.rx = np.array([r.x for r in sec.rebars], dtype=float)
        self.ry = np.array([r.y for r in sec.rebars], dtype=float)
        self.ra = np.array([r.area for r in sec.rebars], dtype=float)
        self.conc = sec.concrete
        self.steel = sec.steel
        self.Rb = sec.concrete.Rb
        self.Eb = sec.concrete.Eb
        self.Rs = sec.steel.Rs
        self.Rsc = sec.steel.Rsc
        self.Es = sec.steel.Es
        self.eps_y = self.Rs / self.Es

    def concrete_stress(self, eps: np.ndarray, model: str) -> np.ndarray:
        sig = np.zeros_like(eps)
        c = eps > 0
        e = eps[c]
        if model == "3line":
            e1 = 0.002
            e2 = EPS_B2
            eta = np.minimum(e / e1, 1.0)
            par = self.Rb * (2.0 * eta - eta * eta)
            sig[c] = np.where(e <= e2, np.where(e <= e1, par, self.Rb), 0.0)
        else:
            e0 = self.Rb / self.Eb
            sig[c] = np.where(e <= e0, self.Eb * e,
                              np.where(e <= EPS_B2, self.Rb, 0.0))
        return sig

    def steel_stress(self, eps: np.ndarray) -> np.ndarray:
        sig = np.zeros_like(eps)
        ey = self.eps_y
        el = np.abs(eps) <= ey
        sig[el] = self.Es * eps[el]
        pl = (~el) & (np.abs(eps) <= EPS_S2)
        sig[pl] = np.where(eps[pl] > 0, self.Rs, -self.Rsc)
        return sig

    def forces(self, eps0: float, kx: float, ky: float,
               model: str = "3line") -> Tuple[float, float, float]:
        """(N kN, Mx kN·m, My kN·m). Nén dương."""
        ef = eps0 + kx * self.fy + ky * self.fx
        sf = self.concrete_stress(ef, model)
        Nf = np.sum(sf * self.fa)
        Mxf = np.sum(sf * self.fa * self.fy)
        Myf = np.sum(sf * self.fa * self.fx)
        if self.ra.size:
            er = eps0 + kx * self.ry + ky * self.rx
            sr = self.steel_stress(er)
            Nr = np.sum(sr * self.ra)
            Mxr = np.sum(sr * self.ra * self.ry)
            Myr = np.sum(sr * self.ra * self.rx)
        else:
            Nr = Mxr = Myr = 0.0
        return (Nf + Nr) / 1000.0, (Mxf + Mxr) / 1e6, (Myf + Myr) / 1e6


def uniaxial_curve_fs(fs: FiberSection, theta_deg: float,
                      model: str = "3line",
                      n_points: int = 48) -> List[Tuple[float, float]]:
    """Đường cong (N, M) khi uốn với vectơ mô men nghiêng góc theta (độ).

    Thực hiện bằng cách xoay tọa độ fiber rồi phân tích một phương.
    Trả về list (N [kN], M [kN·m]) sắp theo N giảm dần.
    """
    th = math.radians(theta_deg)
    ct, st = math.cos(th), math.sin(th)
    # Tọa độ xoay: x' = x ct + y st ; y' = -x st + y ct
    # Uốn quanh trục x' -> biến dạng theo y'
    yp_f = -fs.fx * st + fs.fy * ct
    yp_r = -fs.rx * st + fs.ry * ct if fs.ra.size else np.array([])

    h = float(np.max(yp_f) - np.min(yp_f)) if yp_f.size else 0.0
    if h <= 0:
        return [(0.0, 0.0)]
    y_top = float(np.max(yp_f))
    eps_cu = EPS_B2
    pts: List[Tuple[float, float]] = []

    # Nén đúng tâm
    eps_c = EPS_B2 * 0.8
    ef = np.full_like(yp_f, eps_c)
    sf = fs.concrete_stress(ef, model)
    N0 = (np.sum(sf * fs.fa)) / 1000.0
    if fs.ra.size:
        sr = fs.steel_stress(np.full_like(yp_r, eps_c))
        N0 += np.sum(sr * fs.ra) / 1000.0
    pts.append((N0, 0.0))

    for i in range(1, n_points):
        t = i / n_points * 2.4
        c = h / max(t, 1e-9)
        kx_p = eps_cu / c          # độ cong trong hệ xoay
        eps0 = eps_cu - kx_p * y_top
        # kiểm tra biến dạng thép
        if yp_r.size:
            er = eps0 + kx_p * yp_r
            if np.any(np.abs(er) > EPS_S2 + 1e-9):
                continue
        ef = eps0 + kx_p * yp_f
        sf = fs.concrete_stress(ef, model)
        Nf = np.sum(sf * fs.fa)
        Mf = np.sum(sf * fs.fa * yp_f)
        if fs.ra.size:
            er = eps0 + kx_p * yp_r
            sr = fs.steel_stress(er)
            Nr = np.sum(sr * fs.ra)
            Mr = np.sum(sr * fs.ra * yp_r)
        else:
            Nr = Mr = 0.0
        pts.append(((Nf + Nr) / 1000.0, abs(Mf + Mr) / 1e6))

    # Kéo đúng tâm
    eps_s = min(0.9 * EPS_S2, 3.0 * fs.eps_y)
    ef = np.full_like(yp_f, -eps_s)
    sf = fs.concrete_stress(ef, model)  # = 0 (bỏ qua kéo)
    Nt = np.sum(sf * fs.fa) / 1000.0
    if fs.ra.size:
        sr = fs.steel_stress(np.full_like(yp_r, -eps_s))
        Nt += np.sum(sr * fs.ra) / 1000.0
    pts.append((Nt, 0.0))

    pts.sort(key=lambda p: -p[0])
    return pts


def capacity_at_N(curve: List[Tuple[float, float]], N: float) -> float:
    if not curve:
        return 0.0
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


class BiaxialCapacity:
    """Khả năng chịu nén uốn xiên của tiết diện (mặt tương tác 3D rời rạc)."""

    def __init__(self, sec: Section, model: str = "3line",
                 n_angles: int = 24, n_points: int = 48):
        self.fs = FiberSection(sec)
        self.model = model
        self.angles: List[float] = []
        self.curves: Dict[float, List[Tuple[float, float]]] = {}
        step = 360.0 / n_angles
        for k in range(n_angles):
            th = k * step
            self.angles.append(th)
            self.curves[th] = uniaxial_curve_fs(self.fs, th, model, n_points)

    def moment_capacity(self, N: float, phi_deg: float) -> float:
        """Mô men khả năng chịu tại (N, hướng phi độ)."""
        phi = phi_deg % 360.0
        angs = self.angles
        # tìm 2 góc kẹp
        for i in range(len(angs)):
            a1 = angs[i]
            a2 = angs[(i + 1) % len(angs)]
            # xử lý vòng 360
            b1, b2, bp = a1, a2, phi
            if b2 <= b1:
                b2 += 360.0
            if bp < b1:
                bp += 360.0
            if b1 <= bp <= b2:
                m1 = capacity_at_N(self.curves[a1], N)
                m2 = capacity_at_N(self.curves[a2 % 360.0 if (i + 1) < len(angs) else angs[0]], N)
                t = (bp - b1) / max(b2 - b1, 1e-12)
                return m1 + t * (m2 - m1)
        # fallback: góc gần nhất
        best = min(angs, key=lambda a: abs((a - phi + 180) % 360 - 180))
        return capacity_at_N(self.curves[best], N)

    def check(self, N: float, Mx: float, My: float) -> dict:
        """Kiểm tra (N kN, Mx, My kN·m). Trả về dict kết quả."""
        M = math.hypot(Mx, My)
        phi = math.degrees(math.atan2(My, Mx)) if M > 1e-12 else 0.0
        Mcap = self.moment_capacity(N, phi)
        util = M / Mcap if Mcap > 1e-12 else (float("inf") if M > 1e-12 else 0.0)
        # khả năng chịu dọc trục
        Nmax = self.curves[0.0][0][0] if self.curves else 0.0
        return {
            "N": N, "Mx": Mx, "My": My,
            "M_resultant": M, "phi_deg": phi,
            "M_capacity": Mcap,
            "utilization": util,
            "ok": util <= 1.0,
            "N_max": Nmax,
        }
