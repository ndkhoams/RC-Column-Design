"""Kiểm tra cột BTCT theo Eurocode 2 (EN 1992-1-1).

Bao gồm:
- Biểu đồ tương tác P-M dùng fiber với khối ứng suất chữ nhật EC2
  (εcu2 = 0.0035, ứng suất η·fcd, a = λ·x; η = 1.0, λ = 0.8 với
  fck ≤ 50 MPa) và thép đàn-dẻo giới hạn ở ±fyd.
- Sai lệch thi công (độ nghiêng θi) và độ lệch tâm tối thiểu emin.
- Độ mảnh: λ = l0/i so với λlim = 20·A·B·C/√n.
- Hiệu ứng bậc 2: phương pháp độ cứng danh nghĩa (mặc định) hoặc
  độ cong danh nghĩa (tùy chọn).
- Kiểm tra cắt: VRd,c và VRd,max (công thức EC2 6.2).

Đơn vị: mm, MPa, kN, kN.m (giống aci_checker). Nén dương.
Hệ số riêng phần vật liệu đã nằm trong fcd/fyd nên đường cong
tương tác là đường cong thiết kế (không nhân thêm φ như ACI).
"""

import math
from typing import Dict, List, Tuple

import numpy as np

from .ec2_materials import EC2Concrete, EC2Steel, GAMMA_C, GAMMA_CE
from .sections import Section


# ---------------------------------------------------------------------------
# Ứng suất thép (quy ước nén dương để cộng lực với bê tông)
# ---------------------------------------------------------------------------
def _ec2_steel_stress(eps_cpos: float, steel: EC2Steel) -> float:
    """Ứng suất thép (MPa), nén dương, giới hạn ở ±fyd."""
    fyd = steel.fyd
    if eps_cpos >= 0.0:
        return min(steel.Es * eps_cpos, fyd)
    return -min(steel.Es * (-eps_cpos), fyd)


# ---------------------------------------------------------------------------
# 1. Đường cong tương tác P-M (thiết kế) theo EC2
# ---------------------------------------------------------------------------
def ec2_interaction_curve(sec: Section, conc: EC2Concrete, steel: EC2Steel,
                          theta_deg: float,
                          n_points: int = 48) -> List[Tuple[float, float]]:
    """Đường cong tương tác (N, M) thiết kế theo EC2.

    Phương pháp fiber như aci_interaction_curve nhưng bê tông dùng
    khối ứng suất chữ nhật EC2: εcu2 = 0.0035 tại mép nén,
    a = λ·x (λ = 0.8), ứng suất η·fcd (η = 1.0) trong vùng khối
    chữ nhật. Thép: ứng suất đàn-dẻo giới hạn ở ±fyd; thép nằm
    trong khối nén dùng ứng suất thực (net): fs − η·fcd
    (trừ phần bê tông bị thép chiếm chỗ).

    Trả về list (N_kN, M_kNm) sắp theo N giảm dần (nén dương).
    """
    # Quy ước góc kiểu ETABS: α đo từ trục M3 (α=0° → thuần M3,
    # α=90° → thuần M2), tức hướng mô men (M2, M3) = (sin α, cos α).
    th = math.radians(90.0 - theta_deg)
    ct, st = math.cos(th), math.sin(th)
    fx = np.array([f.x for f in sec.fibers], dtype=float)
    fy = np.array([f.y for f in sec.fibers], dtype=float)
    fa = np.array([f.area for f in sec.fibers], dtype=float)
    rx = np.array([r.x for r in sec.rebars], dtype=float)
    ry = np.array([r.y for r in sec.rebars], dtype=float)
    ra = np.array([r.area for r in sec.rebars], dtype=float)

    if not fx.size:
        return [(0.0, 0.0)]

    # Tọa độ xoay: uốn quanh trục x' -> biến dạng theo y'
    yp_f = -fx * st + fy * ct
    yp_r = -rx * st + ry * ct if ra.size else np.array([])

    y_top = float(np.max(yp_f))
    y_bot = float(np.min(yp_f))
    h = y_top - y_bot
    if h <= 0:
        return [(0.0, 0.0)]

    eps_cu = conc.eps_cu        # 0.0035
    lam = conc.lam              # 0.8
    f_block = conc.f_block      # η·fcd (MPa)
    eps_yd = steel.eps_yd

    pts: List[Tuple[float, float]] = []

    def add_point(eps0: float, kx_p: float):
        """Một điểm trên đường cong. eps(y') = eps0 + kx_p*y', nén dương."""
        eps_top = eps0 + kx_p * y_top
        if abs(kx_p) < 1e-12:
            # Biến dạng đều
            if eps_top >= 0:
                sf = np.full_like(yp_f, f_block)
                a_blk = h  # toàn tiết diện nằm trong khối nén
            else:
                sf = np.zeros_like(yp_f)
                a_blk = 0.0
            er = np.full_like(yp_r, eps_top) if yp_r.size else yp_r
        else:
            if eps_top <= 0:
                # Không có vùng nén -> bê tông không chịu lực
                sf = np.zeros_like(yp_f)
                a_blk = 0.0
            else:
                # Chiều sâu trục trung hòa từ mép nén: x = eps_top / kx
                x = eps_top / kx_p
                a_blk = lam * x
                dist = y_top - yp_f  # khoảng cách từ mép nén
                in_block = dist <= a_blk + 1e-9
                sf = np.where(in_block, f_block, 0.0)
            er = eps0 + kx_p * yp_r if yp_r.size else yp_r

        Nf = float(np.sum(sf * fa))
        Mf = float(np.sum(sf * fa * yp_f))
        if ra.size:
            sr = np.array([_ec2_steel_stress(e, steel) for e in er])
            # Thép trong khối nén đã chiếm chỗ bê tông -> dùng ứng suất
            # thực (net): fs − η·fcd. Chỉ áp cho thanh chịu nén.
            if yp_r.size and a_blk > 0.0:
                dist_r = y_top - yp_r
                in_blk_r = dist_r <= a_blk + 1e-9
                sr = np.where(in_blk_r & (sr > 0.0), sr - f_block, sr)
            Nr = float(np.sum(sr * ra))
            Mr = float(np.sum(sr * ra * yp_r))
        else:
            Nr = Mr = 0.0

        N_d = (Nf + Nr) / 1000.0       # kN, nén dương
        M_d = abs(Mf + Mr) / 1e6       # kN.m
        pts.append((N_d, M_d))

    # Nén đúng tâm (biến dạng đều = εcu2)
    add_point(eps_cu, 0.0)

    # Quét: giữ mép nén đạt εcu2, mép kia giảm dần về kéo
    eps_s_max = max(0.01, 10.0 * eps_yd)
    for i in range(1, n_points):
        frac = i / n_points
        f2 = frac ** 0.8  # dày hơn gần vùng chuyển tiếp
        eps_bot = eps_cu - f2 * (eps_cu + eps_s_max)
        kx_p = (eps_cu - eps_bot) / h
        eps0 = eps_cu - kx_p * y_top
        add_point(eps0, kx_p)

    # Kéo đúng tâm
    add_point(-eps_s_max, 0.0)

    # Sắp theo N giảm dần, loại điểm trùng
    pts.sort(key=lambda p: -p[0])
    clean: List[Tuple[float, float]] = []
    for p in pts:
        if (not clean or abs(p[0] - clean[-1][0]) > 1e-6
                or abs(p[1] - clean[-1][1]) > 1e-6):
            clean.append(p)
    return clean


def _interp_on_curve(curve: List[Tuple], N: float, idx: int) -> float:
    """Nội suy tuyến tính giá trị tại cột idx theo N (curve sắp N giảm dần)."""
    if not curve:
        return 0.0
    if N >= curve[0][0]:
        return curve[0][idx]
    if N <= curve[-1][0]:
        return curve[-1][idx]
    for i in range(len(curve) - 1):
        n1 = curve[i][0]
        n2 = curve[i + 1][0]
        if n2 <= N <= n1 and abs(n1 - n2) > 1e-12:
            t = (N - n2) / (n1 - n2)
            return curve[i + 1][idx] + t * (curve[i][idx] - curve[i + 1][idx])
    return 0.0


def ec2_balanced_point(sec: Section, conc: EC2Concrete, steel: EC2Steel,
                       theta_deg: float = 0.0,
                       n_points: int = 96) -> Tuple[float, float]:
    """Điểm cân bằng: (N_bal_kN, M_bal_kNm) tại mô men lớn nhất
    trên đường cong P-M (dùng cho Kr của phương pháp độ cong danh nghĩa)."""
    curve = ec2_interaction_curve(sec, conc, steel, theta_deg,
                                  n_points=n_points)
    if not curve:
        return (0.0, 0.0)
    p = max(curve, key=lambda t: t[1])
    return (p[0], p[1])


# ---------------------------------------------------------------------------
# Lớp khả năng chịu lực EC2 (mặt tương tác 3D thiết kế)
# ---------------------------------------------------------------------------
class EC2Capacity:
    """Khả năng chịu nén uốn xiên theo EC2 (mặt 3D thiết kế).

    Mỗi góc quét một đường cong thiết kế (hệ số riêng phần đã nằm
    trong fcd/fyd). Không có cắt đỉnh kiểu ACI 22.4.2.2.
    """

    def __init__(self, sec: Section, conc: EC2Concrete, steel: EC2Steel,
                 n_angles: int = 24, n_points: int = 48):
        self.sec = sec
        self.conc = conc
        self.steel = steel

        # N_Rd nén đúng tâm: (Ac − As)·fcd + As·fyd (điểm đầu đường cong)
        Ag = sec.gross_area
        Ast = sec.steel_area
        self.N_Rd_max = ((Ag - Ast) * conc.fcd + Ast * steel.fyd) / 1000.0  # kN

        self.angles: List[float] = []
        # theta -> list (N, M) thiết kế, sắp N giảm dần
        self.design_curves: Dict[float, List[Tuple[float, float]]] = {}
        step = 360.0 / n_angles
        for k in range(n_angles):
            th = k * step
            self.angles.append(th)
            self.design_curves[th] = ec2_interaction_curve(
                sec, conc, steel, th, n_points=n_points)

    def _curve_at(self, phi_deg: float) -> List[Tuple[float, float]]:
        """Đường cong thiết kế tại góc gần nhất (xử lý wrap-around)."""
        def _adiff(a, b):
            d = abs(a - b) % 360.0
            return min(d, 360.0 - d)
        th = min(self.angles, key=lambda a: _adiff(a, phi_deg))
        return self.design_curves[th]

    def moment_capacity(self, N: float, phi_deg: float) -> float:
        """Khả năng chịu mô men thiết kế (kN.m) tại N (kN)."""
        return _interp_on_curve(self._curve_at(phi_deg), N, 1)

    def surface_grid(self, n_n: int = 25, n_angles: int = 36):
        """Lưới mặt tương tác 3D (N, M2, M3) để vẽ.

        Trả về (N_vals, Theta_vals, M2_grid, M3_grid).
        """
        import numpy as np
        import math
        n_min = min(min(p[0] for p in c) for c in self.design_curves.values())
        n_max = max(max(p[0] for p in c) for c in self.design_curves.values())
        n_vals = np.linspace(n_min, n_max, n_n)
        th_vals = np.linspace(0, 360, n_angles, endpoint=False)
        m2_grid = np.zeros((n_n, n_angles))
        m3_grid = np.zeros((n_n, n_angles))
        for i, nn in enumerate(n_vals):
            for j, th in enumerate(th_vals):
                curve = self._curve_at(th)
                m = _interp_on_curve(curve, nn, 1)
                rad = math.radians(th)
                m2_grid[i, j] = m * math.sin(rad)
                m3_grid[i, j] = m * math.cos(rad)
        return n_vals, th_vals, m2_grid, m3_grid

    def dc_ratio(self, N: float, Mx: float, My: float,
                 n_iter: int = 60) -> dict:
        """Tỷ số D/C theo phương pháp tia 3D trên mặt thiết kế.

        Tìm lam_max sao cho lam*(N, Mx, My) nằm trên mặt tương tác.
        D/C = 1/lam_max. Làm kết luận ĐẠT/KHÔNG ĐẠT.
        """
        Mstar = math.hypot(Mx, My)
        if Mstar < 1e-12 and abs(N) < 1e-12:
            return {"dc": 0.0, "lambda_max": float("inf"),
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": True}
        phi_deg = math.degrees(math.atan2(Mx, My)) if Mstar > 1e-12 else 0.0

        def f(lam: float) -> float:
            return self.moment_capacity(lam * N, phi_deg) - lam * Mstar

        if f(0.0) <= 1e-12:
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
        BN = lam * N
        return {"dc": dc, "lambda_max": lam,
                "Bx": lam * Mx, "By": lam * My, "BN": BN,
                "ok": dc <= 1.0}


# ---------------------------------------------------------------------------
# 2. Sai lệch thi công, độ mảnh và hiệu ứng bậc 2 (EC2 5.2, 5.8)
# ---------------------------------------------------------------------------
PHI_EF = 1.21  # hệ số từ biến hiệu dụng (mặc định)


def ec2_imperfection(l0_m: float, alpha_m: float = 1.0) -> dict:
    """Độ nghiêng do sai lệch thi công (EC2 5.2).

    θi = θ0·αh·αm; θ0 = 1/200; αh = 2/√l (2/3 ≤ αh ≤ 1, l tính bằng m);
    αm = 1.0 cho cấu kiện độc lập.
    ei = θi·l0/2 (độ lệch tâm do nghiêng).
    """
    l = max(l0_m, 1e-9)
    alpha_h = 2.0 / math.sqrt(l)
    alpha_h = max(2.0 / 3.0, min(1.0, alpha_h))
    theta_i = (1.0 / 200.0) * alpha_h * alpha_m
    ei_mm = theta_i * (l0_m * 1000.0) / 2.0
    return {"theta_i": theta_i, "alpha_h": alpha_h, "alpha_m": alpha_m,
            "ei_mm": ei_mm}


def ec2_min_eccentricity(h_mm: float) -> float:
    """Độ lệch tâm tối thiểu: emin = max(h/30, 20 mm) (EC2 6.1(4))."""
    return max(h_mm / 30.0, 20.0)


def ec2_slenderness_params(NEd_kN: float, M01_kNm: float, M02_kNm: float,
                           l0_mm: float, i_mm: float,
                           Ac_mm2: float, As_mm2: float,
                           fcd_MPa: float, fyd_MPa: float,
                           unbraced: bool = False) -> dict:
    """Các thông số độ mảnh (EC2 5.8.3).

    M01, M02: mô men bậc 1 ở 2 đầu (đã cộng sai lệch thi công),
    |M02| ≥ |M01| (trị tuyệt đối).
    Trả về {lambda_sl, n, omega, A, B, C, rm, lambda_lim, slender}.
    """
    lambda_sl = (l0_mm / i_mm) if i_mm > 0 else float("inf")
    n = (NEd_kN * 1000.0) / (Ac_mm2 * fcd_MPa) if Ac_mm2 * fcd_MPa > 0 else 0.0
    omega = (As_mm2 * fyd_MPa) / (Ac_mm2 * fcd_MPa) \
        if Ac_mm2 * fcd_MPa > 0 else 0.0
    A = 1.0 / (1.0 + 0.2 * PHI_EF)
    B = math.sqrt(1.0 + 2.0 * omega)
    a1 = abs(M01_kNm)
    a2 = abs(M02_kNm)
    if a2 < 1e-12:
        rm = 1.0
    else:
        rm = min(a1, a2) / a2
    if unbraced:
        # Cấu kiện không giằng (cột độc lập): C = 0.7
        C = 0.7
        rm = 1.0
    else:
        C = 1.7 - rm
    if n > 1e-12:
        lambda_lim = 20.0 * A * B * C / math.sqrt(n)
    else:
        lambda_lim = float("inf")
    return {"lambda_sl": lambda_sl, "n": n, "omega": omega,
            "A": A, "B": B, "C": C, "rm": rm,
            "lambda_lim": lambda_lim,
            "slender": lambda_sl >= lambda_lim}


def ec2_second_order_stiffness(NEd_kN: float, M01_kNm: float, M02_kNm: float,
                               l0_mm: float, Ecm_MPa: float, Ic_mm4: float,
                               Is_mm4: float, Es_MPa: float,
                               fck_MPa: float, n_rel: float,
                               lambda_sl: float,
                               const_moment: bool = True) -> dict:
    """Hiệu ứng bậc 2 bằng phương pháp độ cứng danh nghĩa (EC2 5.8.7).

    MEd = M0Ed·factor; M0Ed = 0.6·M02 + 0.4·M01 ≥ 0.4·M02
    (M01, M02 là trị tuyệt đối đã cộng sai lệch, |M02| ≥ |M01|).
    factor = 1 + β/(NB/NEd − 1); β = π²/c0
    (c0 = 8 nếu mô men bậc 1 không đổi, ngược lại c0 = π²).
    NB = π²·EI/l0²; EI = Kc·Ecd·Ic + Ks·Es·Is;
    Ecd = Ecm/γcE (γcE = 1.2); Ks = 1.0;
    Kc = k1·k2/(1+φef); k1 = √(fck/20); k2 = n·λ/170 ≤ 0.20.

    Trả về {M0Ed, EI_Nmm2, NB_kN, beta, factor, MEd, ok, reason}.

    M01, M02: mô men đầu cột CÓ DẤU (dương/âm theo chiều uốn);
    EC2 5.8.8.2: M0Ed = 0.6·M02 + 0.4·M01 ≥ 0.4·M02 (giữ dấu để
    xét đúng uốn cong kép, khi M01 ngược dấu M02).
    """
    # M0Ed có dấu theo EC2 5.8.8.2 (m2: đầu có |M| lớn hơn)
    m1, m2 = M01_kNm, M02_kNm
    if abs(m2) < abs(m1):
        m1, m2 = m2, m1
    M0Ed = 0.6 * m2 + 0.4 * m1
    if m2 >= 0:
        M0Ed = max(M0Ed, 0.4 * m2)
    else:
        M0Ed = min(M0Ed, 0.4 * m2)

    Ecd = Ecm_MPa / GAMMA_CE
    k1 = math.sqrt(max(fck_MPa, 0.0) / 20.0)
    k2 = min(n_rel * lambda_sl / 170.0, 0.20)
    Kc = k1 * k2 / (1.0 + PHI_EF)
    Ks = 1.0
    EI = Kc * Ecd * Ic_mm4 + Ks * Es_MPa * Is_mm4  # N.mm²

    if l0_mm <= 0:
        return {"M0Ed": M0Ed, "EI_Nmm2": EI, "NB_kN": float("inf"),
                "beta": 0.0, "factor": 1.0, "MEd": M0Ed,
                "ok": True, "reason": "l0 ≤ 0"}
    NB_N = math.pi ** 2 * EI / (l0_mm ** 2)  # N
    NB_kN = NB_N / 1000.0
    if NB_kN <= NEd_kN:
        return {"M0Ed": M0Ed, "EI_Nmm2": EI, "NB_kN": NB_kN,
                "beta": 0.0, "factor": float("inf"), "MEd": float("inf"),
                "ok": False,
                "reason": "NB ≤ NEd: cột quá mảnh, cần tăng tiết diện"}
    c0 = 8.0 if const_moment else math.pi ** 2
    beta = math.pi ** 2 / c0
    factor = 1.0 + beta / (NB_kN / NEd_kN - 1.0)
    factor = max(factor, 1.0)
    MEd = M0Ed * factor
    # Thiết kế cần độ lớn mô men (tiết diện đối xứng); giữ M0Ed có dấu để thuyết minh
    return {"M0Ed": M0Ed, "EI_Nmm2": EI, "NB_kN": NB_kN,
            "beta": beta, "c0": c0, "k1": k1, "k2": k2, "Kc": Kc,
            "factor": factor, "MEd": abs(MEd), "ok": True, "reason": ""}


def ec2_second_order_curvature(NEd_kN: float, M01_kNm: float, M02_kNm: float,
                               l0_mm: float, fck_MPa: float,
                               eps_yd: float, d_mm: float,
                               n_rel: float, nu: float, n_bal: float,
                               lambda_sl: float, c_curv: float = 10.0) -> dict:
    """Hiệu ứng bậc 2 bằng phương pháp độ cong danh nghĩa (EC2 5.8.8).

    MEd = M0Ed + M2; M2 = NEd·e2; e2 = (1/r)·l0²/c (c = 10).
    1/r = Kr·Kφ·1/r0; 1/r0 = εyd/(0.45·d);
    Kr = (nu − n)/(nu − nbal) ≤ 1.0; nu = 1 + ω;
    Kφ = 1 + β·φef ≥ 1; β = 0.35 + fck/200 − λ/150.

    Trả về {M0Ed, e2_mm, M2, Kr, Kphi, MEd, ok}.

    M01, M02: mô men đầu cột CÓ DẤU; M0Ed tính có dấu theo EC2 5.8.8.2
    (xét đúng uốn cong kép).
    """
    m1, m2 = M01_kNm, M02_kNm
    if abs(m2) < abs(m1):
        m1, m2 = m2, m1
    M0Ed = 0.6 * m2 + 0.4 * m1
    if m2 >= 0:
        M0Ed = max(M0Ed, 0.4 * m2)
    else:
        M0Ed = min(M0Ed, 0.4 * m2)

    r0_inv = eps_yd / (0.45 * d_mm) if d_mm > 0 else 0.0  # 1/mm
    denom = nu - n_bal
    if abs(denom) < 1e-12:
        Kr = 1.0
    else:
        Kr = (nu - n_rel) / denom
    Kr = max(0.0, min(1.0, Kr))
    beta = 0.35 + fck_MPa / 200.0 - lambda_sl / 150.0
    Kphi = max(1.0, 1.0 + beta * PHI_EF)
    r_inv = Kr * Kphi * r0_inv  # 1/mm
    e2_mm = r_inv * l0_mm ** 2 / c_curv
    M2 = NEd_kN * e2_mm / 1000.0  # kN.m
    MEd = M0Ed + M2
    # Thiết kế cần độ lớn mô men (tiết diện đối xứng); giữ M0Ed có dấu để thuyết minh
    return {"M0Ed": M0Ed, "r0_inv": r0_inv, "Kr": Kr, "Kphi": Kphi,
            "beta": beta, "e2_mm": e2_mm, "M2": M2, "MEd": abs(MEd),
            "ok": True, "reason": ""}


def ec2_design_moment(NEd_kN: float, M_top_kNm: float, M_bot_kNm: float,
                      l0_mm: float, i_mm: float, h_mm: float,
                      Ac_mm2: float, As_mm2: float,
                      fcd_MPa: float, fyd_MPa: float,
                      Ecm_MPa: float, Ic_mm4: float, Is_mm4: float,
                      Es_MPa: float, fck_MPa: float,
                      unbraced: bool = False,
                      method: str = "stiffness",
                      d_mm: float = 0.0, eps_yd: float = 0.0,
                      n_bal: float = 0.0,
                      const_moment: bool = True) -> dict:
    """Mô men thiết kế một phương theo EC2 (đã gồm sai lệch, emin, bậc 2).

    - NEd > 0 (nén): cộng mô men do sai lệch thi công M_imp = NEd·ei
      vào cả 2 đầu (lấy trị tuyệt đối, hướng bất lợi nhất).
    - Mmin = NEd·emin; emin = max(h/30, 20 mm).
    - NEd ≤ 0 (kéo): bỏ qua sai lệch, emin và bậc 2.
    - Nếu λ < λlim: không tính bậc 2.
    - Mô men thiết kế nhịp: max(MEd_tính, Mmin);
      tại đầu cột: max(|M_đầu_phân_tích|, Mmin).

    Trả về dict đầy đủ các thông số trung gian để thuyết minh.
    """
    out: Dict = {"NEd_kN": NEd_kN}
    if NEd_kN <= 1e-12:
        # Chịu kéo (hoặc N ≈ 0): bỏ qua sai lệch & bậc 2
        Mend = max(abs(M_top_kNm), abs(M_bot_kNm))
        out.update({
            "tension": True, "second_order": False,
            "theta_i": 0.0, "ei_mm": 0.0, "M_imp": 0.0,
            "emin_mm": 0.0, "Mmin": 0.0,
            "lambda_sl": 0.0, "lambda_lim": float("inf"),
            "M0Ed": Mend, "MEd_calc": Mend, "MEd": Mend,
            "MEd_end": Mend, "ok": True,
            "reason": "NEd kéo: bỏ qua sai lệch, emin và bậc 2",
        })
        return out

    # 1. Sai lệch thi công
    imp = ec2_imperfection(l0_mm / 1000.0)
    ei_mm = imp["ei_mm"]
    M_imp = NEd_kN * ei_mm / 1000.0  # kN.m
    # Cộng vào cả 2 đầu theo trị tuyệt đối (hướng bất lợi nhất)
    a_top = abs(M_top_kNm) + M_imp
    a_bot = abs(M_bot_kNm) + M_imp
    M02 = max(a_top, a_bot)
    M01 = min(a_top, a_bot)

    # 2. Độ lệch tâm tối thiểu
    emin_mm = ec2_min_eccentricity(h_mm)
    Mmin = NEd_kN * emin_mm / 1000.0  # kN.m

    # 3. Độ mảnh
    sl = ec2_slenderness_params(NEd_kN, M01, M02, l0_mm, i_mm,
                                Ac_mm2, As_mm2, fcd_MPa, fyd_MPa,
                                unbraced=unbraced)
    out.update({
        "tension": False,
        "theta_i": imp["theta_i"], "alpha_h": imp["alpha_h"],
        "ei_mm": ei_mm, "M_imp": M_imp,
        "M01_imp": M01, "M02_imp": M02,
        "emin_mm": emin_mm, "Mmin": Mmin,
        "lambda_sl": sl["lambda_sl"], "lambda_lim": sl["lambda_lim"],
        "n_rel": sl["n"], "omega": sl["omega"],
        "A_cf": sl["A"], "B_cf": sl["B"], "C_cf": sl["C"],
        "rm": sl["rm"], "slender": sl["slender"],
    })

    if not sl["slender"]:
        MEd_calc = M02
        out.update({
            "second_order": False, "method": method,
            "M0Ed": M02, "factor": 1.0, "MEd_calc": MEd_calc,
            "MEd": max(MEd_calc, Mmin),
            "MEd_end": max(M02, Mmin),
            "ok": True,
            "reason": f"λ = {sl['lambda_sl']:.1f} < λlim = "
                      f"{sl['lambda_lim']:.1f}: bỏ qua bậc 2",
        })
        return out

    # 4. Hiệu ứng bậc 2
    out["second_order"] = True
    out["method"] = method
    if method == "curvature":
        nu = 1.0 + sl["omega"]
        so = ec2_second_order_curvature(
            NEd_kN, M01, M02, l0_mm, fck_MPa, eps_yd, d_mm,
            sl["n"], nu, n_bal, sl["lambda_sl"])
        out.update({f"so_{k}": v for k, v in so.items()})
        MEd_calc = so["MEd"]
    else:
        so = ec2_second_order_stiffness(
            NEd_kN, M01, M02, l0_mm, Ecm_MPa, Ic_mm4, Is_mm4,
            Es_MPa, fck_MPa, sl["n"], sl["lambda_sl"],
            const_moment=const_moment)
        out.update({f"so_{k}": v for k, v in so.items()})
        MEd_calc = so["MEd"]
        if not so.get("ok", True):
            out.update({
                "MEd_calc": float("inf"), "MEd": float("inf"),
                "MEd_end": max(M02, Mmin), "ok": False,
            })
            return out

    out.update({
        "MEd_calc": MEd_calc,
        "MEd": max(MEd_calc, Mmin),
        "MEd_end": max(M02, Mmin),
        "ok": True, "reason": "",
    })
    return out


# ---------------------------------------------------------------------------
# 3. Kiểm tra cắt theo EC2 (6.2)
# ---------------------------------------------------------------------------
def ec2_shear_check(bw_mm: float, d_mm: float, Ac_mm2: float,
                    fck_MPa: float, NEd_kN: float, VEd_kN: float,
                    Asl_mm2: float, fyd_MPa: float,
                    Asw_s_mm2mm: float = 0.0,
                    theta_deg: float = 45.0) -> dict:
    """Kiểm tra khả năng chịu cắt theo EC2 6.2.

    bw_mm: chiều rộng chịu cắt; d_mm: chiều cao hữu hiệu;
    Ac_mm2: diện tích tiết diện; fck_MPa; NEd_kN (nén dương);
    VEd_kN: lực cắt tính toán; Asl_mm2: diện tích thép dọc chịu kéo
    neo qua gối (ρl = Asl/(bw·d) ≤ 0.02); fyd_MPa;
    Asw_s_mm2mm: Asw/s của đai đã bố trí (mm²/mm), 0 nếu không có;
    theta_deg: góc thanh chống nén (mặc định 45°).

    VRd,c = [CRd,c·k·(100·ρl·fck)^(1/3) + k1·σcp]·bw·d
            ≥ (vmin + k1·σcp)·bw·d
    VRd,max = αcw·bw·z·ν1·fcd/(cotθ + tanθ)
    Asw/s yêu cầu = VEd/(z·fyd·cotθ) khi VEd > VRd,c.

    Trả về {VRd_c_kN, VRd_max_kN, VRd_s_kN, VRd_kN, ok, Asw_s_req, ...}.
    """
    fcd = fck_MPa / GAMMA_C
    CRd_c = 0.18 / GAMMA_C   # 0.12
    k1 = 0.15

    k = 1.0 + math.sqrt(200.0 / d_mm) if d_mm > 0 else 2.0
    k = min(k, 2.0)
    rho_l = min(Asl_mm2 / (bw_mm * d_mm), 0.02) if bw_mm * d_mm > 0 else 0.0
    sigma_cp = (NEd_kN * 1000.0) / Ac_mm2 if Ac_mm2 > 0 else 0.0  # MPa
    sigma_cp = min(sigma_cp, 0.2 * fcd)

    vrd_c = (CRd_c * k * (100.0 * rho_l * fck_MPa) ** (1.0 / 3.0)
             + k1 * sigma_cp) * bw_mm * d_mm / 1000.0  # kN
    vmin = 0.035 * k ** 1.5 * math.sqrt(max(fck_MPa, 0.0))
    vrd_c_min = (vmin + k1 * sigma_cp) * bw_mm * d_mm / 1000.0
    VRd_c = max(vrd_c, vrd_c_min, 0.0)

    # VRd,max với θ = 45°: cotθ + tanθ = 2
    th = math.radians(theta_deg)
    cot = 1.0 / math.tan(th) if abs(math.tan(th)) > 1e-12 else 1.0
    nu1 = 0.6 * (1.0 - fck_MPa / 250.0)
    z = 0.9 * d_mm
    alpha_cw = 1.0  # không ứng suất nén trước
    VRd_max = alpha_cw * bw_mm * z * nu1 * fcd / (cot + math.tan(th)) \
        / 1000.0  # kN
    VRd_max = max(VRd_max, 0.0)

    if VEd_kN > VRd_max:
        return {"VRd_c_kN": VRd_c, "VRd_max_kN": VRd_max,
                "VRd_s_kN": 0.0, "VRd_kN": VRd_max,
                "ok": False, "Asw_s_req": float("inf"),
                "k": k, "rho_l": rho_l, "sigma_cp": sigma_cp,
                "vmin": vmin, "z_mm": z, "bw_mm": bw_mm, "d_mm": d_mm,
                "reason": "VEd > VRd,max: vượt khả năng thanh chống nén"}

    if VEd_kN <= VRd_c:
        # Không cần tính toán cốt đai
        return {"VRd_c_kN": VRd_c, "VRd_max_kN": VRd_max,
                "VRd_s_kN": 0.0, "VRd_kN": VRd_c,
                "ok": True, "Asw_s_req": 0.0,
                "k": k, "rho_l": rho_l, "sigma_cp": sigma_cp,
                "vmin": vmin, "z_mm": z, "bw_mm": bw_mm, "d_mm": d_mm,
                "reason": ""}

    # Cần cốt đai: Asw/s yêu cầu
    Asw_s_req = (VEd_kN * 1000.0) / (z * fyd_MPa * cot) \
        if z * fyd_MPa * cot > 0 else float("inf")
    VRd_s = Asw_s_mm2mm * z * fyd_MPa * cot / 1000.0  # kN
    VRd = min(VRd_s, VRd_max)
    ok = VRd >= VEd_kN
    return {"VRd_c_kN": VRd_c, "VRd_max_kN": VRd_max,
            "VRd_s_kN": VRd_s, "VRd_kN": VRd,
            "ok": ok, "Asw_s_req": Asw_s_req,
            "k": k, "rho_l": rho_l, "sigma_cp": sigma_cp,
            "vmin": vmin, "z_mm": z,
            "reason": "" if ok else "Thiếu cốt đai chịu cắt", "bw_mm": bw_mm, "d_mm": d_mm}


# ---------------------------------------------------------------------------
# 4. Kiểm tra cột tổng hợp theo EC2
# ---------------------------------------------------------------------------
def check_column_ec2(sec: Section, conc: EC2Concrete, steel: EC2Steel,
                     N_kN: float, M2_kNm: float, M3_kNm: float,
                     n_angles: int = 24) -> dict:
    """Kiểm tra khả năng chịu nén uốn xiên của cột theo EC2.

    sec: tiết diện (đã bố trí thép, hệ tọa độ x ngang / y đứng).
    N_kN: lực dọc thiết kế NEd (nén dương).
    M2_kNm, M3_kNm: mô men thiết kế MEd2, MEd3
    (đã gồm sai lệch, emin và bậc 2).

    Trả về dict {dc, fs, ok, lambda_max, Bx, By, BN, N_Rd_max, N_bal}.
    """
    cap = EC2Capacity(sec, conc, steel, n_angles=n_angles)
    # Ánh xạ: Mx = M2, My = M3 (cùng quy ước với aci_checker)
    r = cap.dc_ratio(N_kN, M2_kNm, M3_kNm)
    dc = r["dc"]
    fs = 1.0 / dc if dc > 1e-12 else float("inf")

    # Điểm cân bằng (để thuyết minh / dùng cho Kr)
    phi_deg = math.degrees(math.atan2(r["Bx"], r["By"])) if (
        abs(r["Bx"]) > 1e-12 or abs(r["By"]) > 1e-12) else 0.0
    N_bal, M_bal = ec2_balanced_point(
        sec, conc, steel,
        min(cap.angles, key=lambda a: abs((a - phi_deg + 180) % 360 - 180)))

    return {"dc": dc, "fs": fs, "ok": r["ok"],
            "lambda_max": r["lambda_max"],
            "Bx": r["Bx"], "By": r["By"], "BN": r["BN"],
            "N_Rd_max": cap.N_Rd_max,
            "N_bal": N_bal, "M_bal": M_bal}
