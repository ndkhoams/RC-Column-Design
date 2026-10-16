"""Kiểm tra cột BTCT theo ACI 318-19.

Bao gồm:
- Biểu đồ tương tác P-M dùng fiber với khối ứng suất chữ nhật ACI
  (eps_cu = 0.003, ứng suất 0.85*f'c, a = beta1*c) và hệ số phi theo
  biến dạng thép chịu kéo ngoài cùng (ACI 21.2.2).
- Hệ số phóng đại mô men cho cột mảnh: delta_ns (ACI 6.6.4.5).
- Kiểm tra cắt theo ACI 22.5.5.1.

Đơn vị: mm, MPa, kN, kN.m (giống interaction.py). Nén dương.
"""

import math
from typing import Dict, List, Tuple

import numpy as np

from .aci_materials import (ACIConcrete, ACISteel, PHI_SPIRAL, PHI_TIED,
                            max_axial_phi, phi_factor)
from .sections import Section


# ---------------------------------------------------------------------------
# Ứng suất thép (quy ước nén dương để cộng lực với bê tông)
# ---------------------------------------------------------------------------
def _aci_steel_stress(eps_cpos: float, steel: ACISteel) -> float:
    """Ứng suất thép (MPa), nén dương.

    eps_cpos: biến dạng, nén dương.
    """
    ey = steel.eps_y
    if eps_cpos >= 0.0:
        return min(steel.Es * eps_cpos, steel.fy)
    return -min(steel.Es * (-eps_cpos), steel.fy)


# ---------------------------------------------------------------------------
# 1. Đường cong tương tác P-M (danh nghĩa) theo ACI 318-19
# ---------------------------------------------------------------------------
def aci_interaction_curve(sec: Section, conc: ACIConcrete, steel: ACISteel,
                          theta_deg: float, n_points: int = 48,
                          tied: bool = True) -> List[Tuple[float, float, float, float]]:
    """Đường cong tương tác (N, M) danh nghĩa theo ACI 318-19.

    Phương pháp fiber như interaction.uniaxial_curve_fs nhưng bê tông dùng
    khối ứng suất chữ nhật tương đương: eps_cu = 0.003 tại mép nén,
    a = beta1*c, ứng suất 0.85*f'c trong vùng khối chữ nhật (ACI 22.2.2.4).

    Trả về list (N_kN, M_kNm, eps_t, phi) sắp theo N giảm dần, trong đó
    N, M là DANH NGHĨA (chưa nhân phi); eps_t là biến dạng kéo lớn nhất
    của thép (số dương, độ lớn); phi là hệ số giảm cường độ tại điểm đó.
    """
    # Quy ước góc kiểu ETABS: α đo từ trục M3 (α=0° → thuần M3/My,
    # α=90° → thuần M2/Mx), tức hướng mô men (M2, M3) = (sin α, cos α).
    th = math.radians(90.0 - theta_deg)
    ct, st = math.cos(th), math.sin(th)
    fx = np.array([f.x for f in sec.fibers], dtype=float)
    fy = np.array([f.y for f in sec.fibers], dtype=float)
    fa = np.array([f.area for f in sec.fibers], dtype=float)
    rx = np.array([r.x for r in sec.rebars], dtype=float)
    ry = np.array([r.y for r in sec.rebars], dtype=float)
    ra = np.array([r.area for r in sec.rebars], dtype=float)

    if not fx.size:
        return [(0.0, 0.0, 0.0, 0.90)]

    # Tọa độ xoay: uốn quanh trục x' -> biến dạng theo y'
    yp_f = -fx * st + fy * ct
    yp_r = -rx * st + ry * ct if ra.size else np.array([])

    y_top = float(np.max(yp_f))
    y_bot = float(np.min(yp_f))
    h = y_top - y_bot
    if h <= 0:
        return [(0.0, 0.0, 0.0, 0.90)]

    eps_cu = conc.eps_cu          # 0.003
    b1 = conc.beta1               # hệ số khối ứng suất
    f_block = conc.f_block        # 0.85*f'c (MPa)
    eps_y = steel.eps_y

    pts: List[Tuple[float, float, float, float]] = []

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
                # Chiều sâu trục trung hòa từ mép nén: c = eps_top / kx
                c = eps_top / kx_p
                a_blk = b1 * c
                dist = y_top - yp_f  # khoảng cách từ mép nén
                in_block = dist <= a_blk + 1e-9
                sf = np.where(in_block, f_block, 0.0)
            er = eps0 + kx_p * yp_r if yp_r.size else yp_r

        Nf = float(np.sum(sf * fa))
        Mf = float(np.sum(sf * fa * yp_f))
        if ra.size:
            sr = np.array([_aci_steel_stress(e, steel) for e in er])
            # Thép trong khối nén đã chiếm chỗ bê tông -> dùng ứng suất
            # thực (net): fs - 0.85f'c (theo cách tính tay SP: trừ 0.85f'c
            # khỏi fs' trước khi tính Cs). Chỉ áp cho thanh chịu nén.
            if yp_r.size and a_blk > 0.0:
                dist_r = y_top - yp_r
                in_blk_r = dist_r <= a_blk + 1e-9
                sr = np.where(in_blk_r & (sr > 0.0), sr - f_block, sr)
            # eps_t: biến dạng kéo lớn nhất của thép (độ lớn, số dương)
            eps_t = float(np.max(-er))
            Nr = float(np.sum(sr * ra))
            Mr = float(np.sum(sr * ra * yp_r))
        else:
            Nr = Mr = 0.0
            eps_t = 0.0

        N_nom = (Nf + Nr) / 1000.0       # kN, nén dương
        M_nom = abs(Mf + Mr) / 1e6       # kN.m
        phi = phi_factor(max(eps_t, 0.0), eps_y, tied)
        pts.append((N_nom, M_nom, eps_t, phi))

    # Nén đúng tâm (biến dạng đều = eps_cu)
    add_point(eps_cu, 0.0)

    # Quét: giữ mép nén đạt eps_cu, mép kia giảm dần về kéo
    eps_s_max = max(0.01, 10.0 * eps_y)
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
    clean: List[Tuple[float, float, float, float]] = []
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


# ---------------------------------------------------------------------------
# Lớp khả năng chịu lực ACI (mặt tương tác 3D đã giảm phi)
# ---------------------------------------------------------------------------
class ACICapacity:
    """Khả năng chịu nén uốn xiên theo ACI 318-19 (mặt 3D đã nhân phi).

    Mỗi góc quét một đường cong danh nghĩa, nhân phi theo từng điểm,
    cắt đỉnh ở phi*Pn,max (ACI 22.4.2.2).
    """

    def __init__(self, sec: Section, conc: ACIConcrete, steel: ACISteel,
                 tied: bool = True, n_angles: int = 24, n_points: int = 48):
        self.sec = sec
        self.conc = conc
        self.steel = steel
        self.tied = tied
        self.phi_c = PHI_TIED if tied else PHI_SPIRAL

        # Pn danh nghĩa lớn nhất (nén đúng tâm): Po = 0.85f'c(Ag-Ast) + fy*Ast
        Ag = sec.gross_area
        Ast = sec.steel_area
        Po_nom = (0.85 * conc.fc * (Ag - Ast) + steel.fy * Ast) / 1000.0  # kN
        # Đỉnh thiết kế: 0.80/0.85 * phi_c * Po (ACI 22.4.2.2)
        self.N_cap = max_axial_phi(tied) * self.phi_c * Po_nom
        self.Po_nom = Po_nom

        self.angles: List[float] = []
        # theta -> list (Nd, Md, eps_t) đã nhân phi, sắp N giảm dần
        self.design_curves: Dict[float, List[Tuple[float, float, float]]] = {}
        step = 360.0 / n_angles
        for k in range(n_angles):
            th = k * step
            self.angles.append(th)
            nom = aci_interaction_curve(sec, conc, steel, th, n_points, tied)
            dsgn: List[Tuple[float, float, float]] = []
            for (Nn, Mn, eps_t, phi) in nom:
                Nd, Md = phi * Nn, phi * Mn
                # Cắt đỉnh ở N_cap
                if Nd > self.N_cap:
                    Nd = self.N_cap
                dsgn.append((Nd, Md, eps_t))
            dsgn.sort(key=lambda p: -p[0])
            # Loại trùng sau khi cắt đỉnh
            clean: List[Tuple[float, float, float]] = []
            for p in dsgn:
                if (not clean or abs(p[0] - clean[-1][0]) > 1e-6
                        or abs(p[1] - clean[-1][1]) > 1e-6):
                    clean.append(p)
            self.design_curves[th] = clean

    def _curve_at(self, phi_deg: float) -> List[Tuple[float, float, float]]:
        """Đường cong thiết kế tại góc gần nhất (xử lý wrap-around)."""
        def _adiff(a, b):
            d = abs(a - b) % 360.0
            return min(d, 360.0 - d)
        th = min(self.angles, key=lambda a: _adiff(a, phi_deg))
        return self.design_curves[th]

    def moment_capacity(self, N: float, phi_deg: float) -> float:
        """Khả năng chịu mô men thiết kế (kN.m) tại N (kN)."""
        if N > self.N_cap:
            return 0.0
        return _interp_on_curve(self._curve_at(phi_deg), N, 1)

    def eps_t_at(self, N: float, phi_deg: float) -> float:
        """Biến dạng kéo thép tại điểm có N trên đường cong thiết kế."""
        if N > self.N_cap:
            return 0.0
        return _interp_on_curve(self._curve_at(phi_deg), N, 2)

    def dc_ratio(self, N: float, Mx: float, My: float,
                 n_iter: int = 60) -> dict:
        """Tỷ số D/C theo phương pháp tia 3D trên mặt thiết kế (đã nhân phi).

        Tìm lam_max sao cho lam*(N, Mx, My) nằm trên mặt tương tác.
        D/C = 1/lam_max.
        """
        Mstar = math.hypot(Mx, My)
        if Mstar < 1e-12 and abs(N) < 1e-12:
            return {"dc": 0.0, "lambda_max": float("inf"),
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": True,
                    "phi": 0.90, "eps_t": 0.0}
        phi_deg = math.degrees(math.atan2(Mx, My)) if Mstar > 1e-12 else 0.0

        def f(lam: float) -> float:
            return self.moment_capacity(lam * N, phi_deg) - lam * Mstar

        if f(0.0) <= 1e-12:
            return {"dc": float("inf"), "lambda_max": 0.0,
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": False,
                    "phi": self.phi_c, "eps_t": 0.0}
        lo, hi = 0.0, 1.0
        while f(hi) > 0 and hi < 1e7:
            hi *= 2.0
        if hi >= 1e7:
            return {"dc": 0.0, "lambda_max": float("inf"),
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": True,
                    "phi": 0.90, "eps_t": 0.01}
        for _ in range(n_iter):
            mid = 0.5 * (lo + hi)
            if f(mid) > 0:
                lo = mid
            else:
                hi = mid
        lam = 0.5 * (lo + hi)
        dc = 1.0 / lam if lam > 1e-12 else float("inf")
        BN = lam * N
        eps_t = self.eps_t_at(BN, phi_deg)
        phi_lim = phi_factor(max(eps_t, 0.0), self.steel.eps_y, self.tied)
        return {"dc": dc, "lambda_max": lam,
                "Bx": lam * Mx, "By": lam * My, "BN": BN,
                "ok": dc <= 1.0, "phi": phi_lim, "eps_t": eps_t}


# ---------------------------------------------------------------------------
# 2. Hệ số phóng đại mô men cho cột mảnh (ACI 6.6.4.5)
# ---------------------------------------------------------------------------
def moment_magnification(Pu_kN: float, M1_kNm: float, M2_kNm: float,
                         lu_mm: float, k: float, Ec_MPa: float, Ig_mm4: float,
                         beta_dns: float, Cm_input: float = None) -> dict:
    """Hệ số phóng đại mô men delta_ns cho cột mảnh (ACI 6.6.4.5.2).

    Pu_kN: lực dọc tính toán (kN, nén dương).
    M1, M2: mô men 2 đầu cột (kN.m), M2 là mô men lớn hơn (trị tuyệt đối).
        M1/M2 âm khi uốn cong một chiều (single curvature).
    lu_mm: chiều dài không giằng theo phương đang xét.
    k: hệ số chiều dài hữu hiệu.
    Ec_MPa, Ig_mm4: mô đun đàn hồi và mô men quán tính nguyên.
    beta_dns: tỷ số tải trọng dọc thường xuyên / tổng tải trọng (0..1).
    Cm_input: ghi đè Cm nếu có.

    Trả về dict {delta_ns, Pc_kN, Cm, ok, reason}.
    """
    if abs(M2_kNm) > 1e-12:
        ratio = M1_kNm / M2_kNm
    else:
        ratio = 0.0
    Cm = Cm_input if Cm_input is not None else 0.6 - 0.4 * ratio

    # EI hiệu dụng (ACI 6.6.4.4.4a): EI = 0.4*Ec*Ig/(1+beta_dns)
    EI_eff = 0.4 * Ec_MPa * Ig_mm4 / (1.0 + beta_dns)  # N.mm2
    klu = k * lu_mm
    if klu <= 0:
        return {"delta_ns": 1.0, "Pc_kN": float("inf"), "Cm": Cm,
                "ok": True, "reason": "klu <= 0"}
    Pc_N = math.pi ** 2 * EI_eff / (klu ** 2)  # N (Euler)
    Pc_kN = Pc_N / 1000.0
    Pu_N = Pu_kN * 1000.0

    denom = 1.0 - Pu_N / (0.75 * Pc_N)
    if denom <= 0:
        return {"delta_ns": float("inf"), "Pc_kN": Pc_kN, "Cm": Cm,
                "ok": False, "reason": "Pu >= 0.75*Pc: cột quá mảnh (ACI 6.6.4.5.2)"}
    delta_ns = Cm / denom
    delta_ns = max(delta_ns, 1.0)
    return {"delta_ns": delta_ns, "Pc_kN": Pc_kN, "Cm": Cm,
            "ok": True, "reason": ""}


# ---------------------------------------------------------------------------
# 2b. Hệ số phóng đại mô men sway delta_s (ACI 6.6.4.6.2a)
# ---------------------------------------------------------------------------
def sway_magnification(Q: float = None, sum_Pu_kN: float = None,
                       delta_o_mm: float = None, Vus_kN: float = None,
                       lc_mm: float = None) -> dict:
    """Hệ số phóng đại mô men cho khung sway (ACI 6.6.4.6.2a).

    δs = 1 / (1 - Q) ≥ 1.0
    Q = ΣPu · Δo / (Vus · lc) — chỉ số ổn định tầng.

    Có thể truyền trực tiếp Q, hoặc truyền 4 thông số để tự tính Q:
    - sum_Pu_kN: tổng tải dọc tính toán của tầng (kN)
    - delta_o_mm: chuyển vị lệch tầng bậc 1 (mm)
    - Vus_kN: tổng lực cắt tầng (kN)
    - lc_mm: chiều cao tầng (mm)

    Trả về dict {delta_s, Q, ok, reason}.
    """
    if Q is None:
        if None in (sum_Pu_kN, delta_o_mm, Vus_kN, lc_mm):
            return {"delta_s": 1.0, "Q": 0.0, "ok": True,
                    "reason": "Thiếu thông số Q — bỏ qua sway (δs=1.0)"}
        if Vus_kN == 0 or lc_mm == 0:
            return {"delta_s": 1.0, "Q": 0.0, "ok": True,
                    "reason": "Vus=0 hoặc lc=0 — bỏ qua sway"}
        Q = (sum_Pu_kN * delta_o_mm) / (Vus_kN * lc_mm)
    if Q < 0:
        Q = 0.0
    if Q >= 1.0:
        return {"delta_s": float("inf"), "Q": Q, "ok": False,
                "reason": "Q ≥ 1.0: khung không ổn định, cần phân tích bậc 2"}
    delta_s = 1.0 / (1.0 - Q)
    delta_s = max(delta_s, 1.0)
    return {"delta_s": delta_s, "Q": Q, "ok": True, "reason": ""}


# ---------------------------------------------------------------------------
# 3. Kiểm tra cắt theo ACI 22.5.5.1
# ---------------------------------------------------------------------------
_PSI_PER_MPA = 145.038
_IN2_PER_MM2 = 1.0 / 645.16
_LBF_PER_KN = 224.809


def aci_shear_check(Acv_mm2: float, Ag_mm2: float, fc_MPa: float, Nu_kN: float,
                    Vu_kN: float, Av_mm2: float, fyt_MPa: float, s_mm: float,
                    d_mm: float, lambda_: float = 1.0,
                    has_min_shear: bool = True,
                    rho_w: float = 0.015) -> dict:
    """Kiểm tra khả năng chịu cắt theo ACI 22.5.5.1.

    Acv_mm2: diện tích chịu cắt hiệu dụng (= b*d với tiết diện chữ nhật).
    Ag_mm2: diện tích nguyên của tiết diện.
    fc_MPa: f'c (MPa). Nu_kN: lực dọc tính toán (nén dương).
    Vu_kN: lực cắt tính toán (kN).
    Av_mm2: diện tích một bộ đai (2 nhánh), fyt_MPa: fy của đai,
        s_mm: khoảng cách đai, d_mm: chiều cao hữu hiệu.
    lambda_: hệ số bê tông nhẹ (1.0 bê tông thường).
    has_min_shear: True nếu có tối thiểu cốt đai (Av >= Av,min).
    rho_w: hàm lượng thép dọc chịu kéo As/(b*d) cho công thức Vc.

    Trả về dict {Vc_kN, Vs_kN, phi_Vn_kN, ok, Av_s_req, phi}.
    """
    fc_psi = fc_MPa * _PSI_PER_MPA
    Acv_in2 = Acv_mm2 * _IN2_PER_MM2
    Ag_in2 = Ag_mm2 * _IN2_PER_MM2
    Nu_lbf = Nu_kN * _LBF_PER_KN  # nén dương
    d_in = d_mm / 25.4

    # Số hạng Nu/(6*Ag) đổi ra psi, nén dương, chặn trên 0.05*f'c
    if Ag_in2 > 0:
        nu_term = Nu_lbf / (6.0 * Ag_in2)
    else:
        nu_term = 0.0
    nu_term = min(nu_term, 0.05 * fc_psi)

    sqrt_fc = math.sqrt(max(fc_psi, 0.0))
    # Hệ số kích thước (ACI 22.5.5.1.3)
    lambda_s = math.sqrt(2.0 / (1.0 + d_in / 10.0)) if d_in > 0 else 1.0
    lambda_s = min(lambda_s, 1.0)

    term_a = 2.0 * lambda_ * sqrt_fc + nu_term
    term_b = (8.0 * lambda_s * lambda_ * (max(rho_w, 0.0) ** (1.0 / 3.0))
              * sqrt_fc + nu_term)
    if has_min_shear:
        vc_lbf = max(term_a, term_b) * Acv_in2
    else:
        vc_lbf = term_b * Acv_in2

    # Giới hạn: 0 <= Vc <= 5*lambda*sqrt(f'c)*Acv
    vc_lbf = max(0.0, min(vc_lbf, 5.0 * lambda_ * sqrt_fc * Acv_in2))
    Vc_kN = vc_lbf / _LBF_PER_KN

    # Vs = Av*fyt*d/s
    if s_mm > 0 and Av_mm2 > 0:
        Vs_kN = Av_mm2 * fyt_MPa * d_mm / s_mm / 1000.0
    else:
        Vs_kN = 0.0

    # ACI 22.5.1.2: Vs ≤ 8·λs·λ·√f'c·bw·d
    if d_mm > 0 and Acv_mm2 > 0:
        bw_in = (Acv_mm2 / d_mm) / 25.4  # bw = Acv/d
        Vs_max_lbf = 8.0 * lambda_s * lambda_ * sqrt_fc * bw_in * d_in
        Vs_kN = min(Vs_kN, Vs_max_lbf / _LBF_PER_KN)

    phi = 0.75  # hệ số phi cho cắt (ACI 21.2.1)
    phi_Vn_kN = phi * (Vc_kN + Vs_kN)
    ok = phi_Vn_kN >= Vu_kN

    # Av/s yêu cầu (mm2/mm) nếu thiếu
    if Vu_kN > phi * Vc_kN and fyt_MPa > 0 and d_mm > 0:
        Vs_req_kN = Vu_kN / phi - Vc_kN
        Av_s_req = (Vs_req_kN * 1000.0) / (fyt_MPa * d_mm)
    else:
        Av_s_req = 0.0

    return {"Vc_kN": Vc_kN, "Vs_kN": Vs_kN, "phi_Vn_kN": phi_Vn_kN,
            "phi": phi, "ok": ok, "Av_s_req": Av_s_req,
            "lambda_s": lambda_s}


# ---------------------------------------------------------------------------
# 4. Kiểm tra cột tổng hợp theo ACI 318-19
# ---------------------------------------------------------------------------
def check_column_aci(sec: Section, conc: ACIConcrete, steel: ACISteel,
                     N_kN: float, M2_kNm: float, M3_kNm: float,
                     tied: bool = True, n_angles: int = 24) -> dict:
    """Kiểm tra khả năng chịu nén uốn xiên của cột theo ACI 318-19.

    sec: tiết diện (đã bố trí thép, hệ tọa độ x ngang / y đứng).
    N_kN: lực dọc tính toán (nén dương).
    M2_kNm, M3_kNm: mô men tính toán theo trục 2, 3 (ánh xạ Mx=M2, My=M3).
    tied: True = cột đai rời (phi_c=0.65), False = đai xoắn (0.75).

    Trả về dict {dc, fs, phi, ok, lambda_max, Bx, By, BN, Nn, Mn, eps_t}.
    """
    cap = ACICapacity(sec, conc, steel, tied=tied, n_angles=n_angles)
    # Ánh xạ: Mx = M2, My = M3 (cùng quy ước với interaction.py)
    r = cap.dc_ratio(N_kN, M2_kNm, M3_kNm)
    dc = r["dc"]
    fs = 1.0 / dc if dc > 1e-12 else float("inf")

    # Khả năng danh nghĩa tại điểm giới hạn B (để thuyết minh)
    phi_deg = math.degrees(math.atan2(r["Bx"], r["By"])) if (
        abs(r["Bx"]) > 1e-12 or abs(r["By"]) > 1e-12) else 0.0
    # Nội suy Nn, Mn danh nghĩa tại BN từ đường cong danh nghĩa
    nom = aci_interaction_curve(
        sec, conc, steel,
        min(cap.angles, key=lambda a: abs(a - phi_deg)),
        n_points=48, tied=tied)
    # Tính đúng: nội suy M danh nghĩa tại BN
    Mn_nom = _interp_on_curve([(p[0], p[1]) for p in nom], r["BN"], 1)
    # N danh nghĩa tại B: BN_thiết_kế / phi (gần đúng)
    phi_b = r["phi"] if r["phi"] > 1e-12 else 1.0
    Nn_b = r["BN"] / phi_b

    return {"dc": dc, "fs": fs, "phi": r["phi"], "ok": r["ok"],
            "lambda_max": r["lambda_max"],
            "Bx": r["Bx"], "By": r["By"], "BN": r["BN"],
            "Nn": Nn_b, "Mn": Mn_nom, "eps_t": r["eps_t"],
            "N_cap": cap.N_cap, "Po_nom": cap.Po_nom}
