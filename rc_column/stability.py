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
PSI_TABLE = {
    ("ngam", "ngam"): 0.5,
    ("ngam", "khop"): 0.7,
    ("khop", "khop"): 1.0,
    ("ngam", "tu_do"): 2.0,
    ("khop", "tu_do"): 2.0,
}

BOUNDARY_NAMES = {
    "ngam": "Ngàm",
    "khop": "Khớp",
    "tu_do": "Tự do",
}


def effective_length(L: float, top: str, bottom: str, psi: float = None) -> float:
    """Chiều dài tính toán L0 (m). Ưu tiên psi do người dùng nhập."""
    if psi is not None and psi > 0:
        return psi * L
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
