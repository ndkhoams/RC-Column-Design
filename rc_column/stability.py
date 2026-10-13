"""Ổn định cột: chiều dài tính toán, độ mảnh, hệ số phi_L (TCVN 5574:2018).

- L0 = psi * L (psi: hệ số theo liên kết 2 đầu).
- TCVN 5574:2018 Điều 8.1.15-8.1.17: kể đến uốn dọc (hiệu ứng bậc 2).
- phi_L theo công thức (48): 1.0 <= phi_L <= 2.0, tính từ thành phần dài hạn;
  nếu không khai báo tải dài hạn -> lấy 2.0 (thiên về an toàn).
"""

import math
from dataclasses import dataclass


# Hệ số psi theo điều kiện biên (tham khảo TCVN 5574:2018 Bảng 31 / phụ lục)
# key: (liên kết trên, liên kết dưới)
# Hệ số ψ đơn cho từng loại liên kết (khi 2 đầu giống nhau)
PSI_SINGLE = {
    "ngam_cung": 0.5,
    "ngam_nua_cung": 0.8,
    "khop": 1.0,
    "khop_han_che": 1.2,
    "ngam_han_che": 1.5,
    "tu_do": 2.0,
}

PSI_TABLE = {
    ("ngam_cung", "ngam_cung"): 0.5,
    ("ngam_cung", "ngam_nua_cung"): 0.65,
    ("ngam_cung", "khop"): 0.7,
    ("ngam_nua_cung", "ngam_nua_cung"): 0.8,
    ("ngam_nua_cung", "khop"): 0.9,
    ("khop", "khop"): 1.0,
    ("ngam_cung", "tu_do"): 2.0,
    ("ngam_nua_cung", "tu_do"): 2.0,
    ("khop", "tu_do"): 2.0,
    # Di động hạn chế: nội suy giữa các giá trị chuẩn
    ("khop_han_che", "khop_han_che"): 1.2,
    ("ngam_han_che", "ngam_han_che"): 1.5,
    ("ngam_han_che", "khop_han_che"): 1.35,
}

BOUNDARY_NAMES = {
    "ngam_nua_cung": "Ngàm nửa cứng",
    "ngam_cung": "Ngàm cứng",
    "khop": "Khớp",
    "tu_do": "Tự do",
    "khop_han_che": "Khớp di động hạn chế",
    "ngam_han_che": "Ngàm di động hạn chế",
}

# Alias tương thích ngược: "ngam" cũ -> "ngam_cung"
BOUNDARY_ALIASES = {"ngam": "ngam_cung"}


def _norm_bkey(k: str) -> str:
    return BOUNDARY_ALIASES.get(k, k)


def effective_length(L: float, top: str, bottom: str, psi: float = None) -> float:
    """Chiều dài tính toán L0 (m). Ưu tiên psi do người dùng nhập."""
    if psi is not None and psi > 0:
        return psi * L
    top, bottom = _norm_bkey(top), _norm_bkey(bottom)
    key = (top, bottom)
    p = PSI_TABLE.get(key, PSI_TABLE.get((bottom, top), 1.0))
    return p * L


def slenderness(L0: float, h: float) -> float:
    """Độ mảnh lambda = L0 / i; với tiết diện chữ nhật i = h/sqrt(12).

    L0 (m), h (mm) -> đổi h ra m.
    """
    i = (h / 1000.0) / math.sqrt(12.0)
    return L0 / i if i > 0 else float("inf")


@dataclass
class LongTermLoads:
    has_data: bool = False
    N_lt: float = 0.0
    Mx_lt: float = 0.0
    My_lt: float = 0.0


def phi_L(N: float, Mx: float, My: float, lt: LongTermLoads) -> float:
    """Hệ số phi_L theo công thức (48), TCVN 5574:2018.

    1.0 <= phi_L <= 2.0. Nếu không có số liệu dài hạn -> 2.0.
    Công thức (48): phi_L = 1 + M_lt / M_tot (dạng rút gọn thực hành),
    trong đó M là mô men tổng hợp; chặn trên 2.0, dưới 1.0.
    """
    if not lt.has_data:
        return 2.0
    M_tot = math.hypot(Mx, My)
    M_lt = math.hypot(lt.Mx_lt, lt.My_lt)
    if M_tot <= 1e-12:
        # chỉ có lực dọc: dùng tỉ số N
        r = abs(lt.N_lt) / max(abs(N), 1e-12)
    else:
        r = M_lt / M_tot
    r = min(max(r, 0.0), 1.0)
    return min(2.0, max(1.0, 1.0 + r))


def magnified_moment(M: float, N: float, L0: float, EI: float) -> float:
    """Mô men kể đến uốn dọc (khuếch đại): M* = M / (1 - N/Ncr).

    N (kN), L0 (m), EI (kN·m²). Ncr = pi²·EI / L0².
    """
    if EI <= 0 or L0 <= 0:
        return M
    Ncr = math.pi ** 2 * EI / (L0 ** 2)
    if abs(N) >= 0.9 * Ncr:
        return M * 10.0  # mất ổn định
    return M / (1.0 - abs(N) / Ncr)


# ---------------------------------------------------------------------------
# Độ lệch tâm & hiệu ứng uốn dọc (TCVN 5574:2018 Mục 8.1.2)
# ---------------------------------------------------------------------------
@dataclass
class EccentricityResult:
    e1x: float; e1y: float      # độ lệch tâm tĩnh học (mm)
    eax: float; eay: float      # độ lệch tâm ngẫu nhiên (mm)
    e0x: float; e0y: float      # độ lệch tâm ban đầu (mm)


def eccentricities(N: float, Mx: float, My: float,
                   Lx: float, Ly: float, cx: float, cy: float) -> EccentricityResult:
    """Độ lệch tâm theo Mục 8.1.2.2.4.

    N (kN), M (kN·m), L (m), c (mm). Trả về mm.
    e1x = |My|/N; e1y = |Mx|/N
    ea = max(L/600, c/30, 10mm)
    e0 = max(e1, ea)
    """
    e1x = abs(My) * 1e6 / max(abs(N) * 1000.0, 1e-12) if abs(N) > 1e-12 else 0.0
    e1y = abs(Mx) * 1e6 / max(abs(N) * 1000.0, 1e-12) if abs(N) > 1e-12 else 0.0
    eax = max(Lx * 1000.0 / 600.0, cx / 30.0, 10.0)
    eay = max(Ly * 1000.0 / 600.0, cy / 30.0, 10.0)
    return EccentricityResult(e1x, e1y, eax, eay,
                              max(e1x, eax), max(e1y, eay))


@dataclass
class BucklingResult:
    delta_ex: float; delta_ey: float  # độ lệch tâm tương đối
    kbx: float; kby: float            # hệ số độ cứng bê tông
    Dx: float; Dy: float              # độ cứng chống uốn (kN·m²)
    Ncrx: float; Ncry: float          # lực tới hạn Euler (kN)
    etax: float; etay: float          # hệ số uốn dọc η
    Mx_star: float; My_star: float    # mô men đã phóng đại (kN·m)


def buckling_factors(e0x: float, e0y: float, cx: float, cy: float,
                     phiL: float, Eb: float, Ix: float, Iy: float,
                     Isx: float, Isy: float, L0x: float, L0y: float,
                     N: float, Mx: float, My: float) -> BucklingResult:
    """Tính hệ số uốn dọc theo CT (44)-(48).

    Eb (MPa), I (mm⁴), L0 (m), N (kN), M (kN·m).
    δe = e0/h ∈ [0.15, 1.5]; kb = 0.15/[φL·(0.3+δe)]
    D = kb·Eb·Ib + ks·Es·Is (ks=0.7); Ncr = π²·D/L0²; η = 1/(1-N/Ncr)
    """
    # δe: e0y cho phương X (uốn trong mặt phẳng y), e0x cho phương Y
    d_ex = min(max(e0y / max(cy, 1e-9), 0.15), 1.5)
    d_ey = min(max(e0x / max(cx, 1e-9), 0.15), 1.5)
    kbx = 0.15 / (phiL * (0.3 + d_ex))
    kby = 0.15 / (phiL * (0.3 + d_ey))
    Es = 2.0e5  # MPa
    ks = 0.7
    # Đổi đơn vị: Eb(MPa=N/mm²)·I(mm⁴) = N·mm² → kN·m²: /1e9
    Dx = (kbx * Eb * Ix + ks * Es * Isx) / 1e9
    Dy = (kby * Eb * Iy + ks * Es * Isy) / 1e9
    Ncrx = math.pi ** 2 * Dx / max(L0x, 1e-9) ** 2
    Ncry = math.pi ** 2 * Dy / max(L0y, 1e-9) ** 2
    etax = 1.0 / (1.0 - abs(N) / Ncrx) if Ncrx > abs(N) else 10.0
    etay = 1.0 / (1.0 - abs(N) / Ncry) if Ncry > abs(N) else 10.0
    return BucklingResult(d_ex, d_ey, kbx, kby, Dx, Dy, Ncrx, Ncry,
                          etax, etay, etax * Mx, etay * My)
