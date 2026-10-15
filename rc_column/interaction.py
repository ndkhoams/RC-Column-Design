"""Biểu đồ tương tác và kiểm tra nén uốn xiên (N + Mx + My) bằng NDM.

Phương pháp:
- Rời rạc tiết diện thành fiber (numpy, vector hóa).
- Với mỗi góc uốn theta: xoay hệ tọa độ, phân tích một phương (quét trục
  trung hòa với biến dạng bê tông mép nén đạt eps_cu) -> đường cong (N, M).
- Kiểm tra (N, Mx, My): tính M = sqrt(Mx²+My²), phi = atan2(Mx, My)  # quy ước ETABS: đo từ trục M3,
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

    Quy ước góc kiểu ETABS: theta đo từ trục M3 (theta=0° → thuần M3/My,
    theta=90° → thuần M2/Mx), tức hướng mô men (M2, M3) = (sin theta, cos theta).
    Thực hiện bằng cách xoay tọa độ fiber rồi phân tích một phương.
    Trả về list (N [kN], M [kN·m]) sắp theo N giảm dần.
    """
    th = math.radians(90.0 - theta_deg)
    ct, st = math.cos(th), math.sin(th)
    # Tọa độ xoay: x' = x ct + y st ; y' = -x st + y ct
    # Uốn quanh trục x' -> biến dạng theo y'
    yp_f = -fs.fx * st + fs.fy * ct
    yp_r = -fs.rx * st + fs.ry * ct if fs.ra.size else np.array([])

    h = float(np.max(yp_f) - np.min(yp_f)) if yp_f.size else 0.0
    if h <= 0:
        return [(0.0, 0.0)]
    y_top = float(np.max(yp_f))
    y_bot = float(np.min(yp_f))
    eps_cu = EPS_B2
    pts: List[Tuple[float, float]] = []

    def add_point(eps0: float, kx_p: float):
        # kiểm tra biến dạng thép
        if yp_r.size:
            er = eps0 + kx_p * yp_r
            if np.any(np.abs(er) > EPS_S2 + 1e-9):
                return
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

    # Nén đúng tâm (biến dạng đều = eps_cu)
    add_point(eps_cu, 0.0)

    # Quét: giữ mép nén đạt eps_cu, biến dạng mép kia (eps_bot) giảm dần
    # từ eps_cu về -eps_s_max. Tham số hóa đều theo eps_bot để đường cong mượt.
    eps_s_max = min(0.9 * EPS_S2, 10.0 * fs.eps_y)
    for i in range(1, n_points):
        frac = i / n_points
        # phân bố dày hơn gần vùng chuyển tiếp (dùng frac^0.8)
        f2 = frac ** 0.8
        eps_bot = eps_cu - f2 * (eps_cu + eps_s_max)
        kx_p = (eps_cu - eps_bot) / h
        eps0 = eps_cu - kx_p * y_top
        add_point(eps0, kx_p)

    # Kéo đúng tâm
    add_point(-eps_s_max, 0.0)

    # Loại bỏ điểm trùng lặp gần nhau để đường cong sạch
    pts.sort(key=lambda p: -p[0])
    clean: List[Tuple[float, float]] = []
    for p in pts:
        if not clean or (abs(p[0] - clean[-1][0]) > 1e-6
                         or abs(p[1] - clean[-1][1]) > 1e-6):
            clean.append(p)
    return clean


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

    def mx_my_curve(self, N: float, n_angles: int = 72) -> List[Tuple[float, float]]:
        """Đường cong tương tác Mx-My tại lực dọc N cho trước.

        Trả về list (Mx, My) khép kín.
        """
        pts: List[Tuple[float, float]] = []
        for k in range(n_angles):
            th = 360.0 * k / n_angles
            m = self.moment_capacity(N, th)
            rad = math.radians(th)
            pts.append((m * math.sin(rad), m * math.cos(rad)))  # quy ước ETABS: M2=M sinθ, M3=M cosθ
        pts.append(pts[0])
        return pts

    def surface_grid(self, n_n: int = 25, n_angles: int = 48):
        """Lưới mặt tương tác 3D (N, Mx, My) để vẽ.

        Trả về (N_vals, Theta_vals, Mx_grid, My_grid).
        """
        # biên N: từ kéo max đến nén max (lấy từ đường cong θ=0)
        curve0 = self.curves[self.angles[0]]
        n_min = curve0[-1][0]
        n_max = curve0[0][0]
        n_vals = np.linspace(n_min, n_max, n_n)
        th_vals = np.linspace(0, 360, n_angles, endpoint=False)
        mx_grid = np.zeros((n_n, n_angles))
        my_grid = np.zeros((n_n, n_angles))
        for i, nn in enumerate(n_vals):
            for j, th in enumerate(th_vals):
                m = self.moment_capacity(float(nn), float(th))
                rad = math.radians(th)
                mx_grid[i, j] = m * math.sin(rad)  # M2
                my_grid[i, j] = m * math.cos(rad)  # M3
        return n_vals, th_vals, mx_grid, my_grid

    def dc_ratio(self, N: float, Mx: float, My: float,
                 n_iter: int = 60) -> dict:
        """Tỷ số D/C theo phương pháp tia 3D.

        Tìm λ_max sao cho λ·(N, Mx, My) nằm trên mặt tương tác.
        D/C = 1/λ_max. Trả về dict {dc, lambda_max, Bx, By, BN, ok}.
        """
        Mstar = math.hypot(Mx, My)
        if Mstar < 1e-12 and abs(N) < 1e-12:
            return {"dc": 0.0, "lambda_max": float("inf"),
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": True}
        phi = math.degrees(math.atan2(Mx, My)) if Mstar > 1e-12 else 0.0

        def f(lam: float) -> float:
            return self.moment_capacity(lam * N, phi) - lam * Mstar

        flo = f(0.0)
        if flo <= 1e-12:
            # ngay tại gốc đã vượt khả năng (trường hợp suy biến)
            return {"dc": float("inf"), "lambda_max": 0.0,
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": False}
        lo, hi = 0.0, 1.0
        while f(hi) > 0 and hi < 1e7:
            hi *= 2.0
        if hi >= 1e7:
            return {"dc": 0.0, "lambda_max": float("inf"),
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": True}
        for _ in range(n_iter):
            mid = 0.5 * (lo + hi)
            if f(mid) > 0:
                lo = mid
            else:
                hi = mid
        lam = 0.5 * (lo + hi)
        dc = 1.0 / lam if lam > 1e-12 else float("inf")
        return {"dc": dc, "lambda_max": lam,
                "Bx": lam * Mx, "By": lam * My, "BN": lam * N,
                "ok": dc <= 1.0}

    def check(self, N: float, Mx: float, My: float) -> dict:
        """Kiểm tra (N kN, Mx, My kN·m). Trả về dict kết quả."""
        M = math.hypot(Mx, My)
        phi = math.degrees(math.atan2(Mx, My)) if M > 1e-12 else 0.0
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
