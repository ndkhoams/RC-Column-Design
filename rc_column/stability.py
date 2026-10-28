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
    # η bị kẹp ở 10,0 vì Ncr ≤ |N| VÀ cổng λ > 14 đã cho η đó đi
    # vào tính (2026-10-28, quyết sau đối chiếu BXD QĐ 862):
    # giá trị kẹp không phải giá trị vật lý — đầu gọi phải hiển
    # thị cảnh báo kèm Ncr/N. Khi λ ≤ 14 (η = 1,0) cờ này False
    # vì η kẹp không được dùng.
    eta_clamped_x: bool = False
    eta_clamped_y: bool = False


def phi_l_dir(N: float, M: float, N_lt: float, M_lt: float,
              h_mm: float, a_mm: float, has_data: bool = True) -> float:
    """Hệ số φl theo từng phương, theo Hướng dẫn BXD §5.1.2
    công thức (5-31) và cách tính của ví dụ §7:
    φl = 1 + M1l/M1, kẹp [1, 2], trong đó M1/M1l là mô men đối
    với trọng tâm thanh thép chịu kéo nhiều nhất (hoặc chịu nén
    ít nhất khi toàn tiết diện chịu nén) do toàn bộ tải trọng /
    do tải dài hạn. Với tiết diện đối xứng, khoảng cách từ trọng
    tâm tiết diện tới trọng tâm thép đó là (h0 − a')/2 = (h − 2a)/2
    (h0 = h − a, a' = a), nên M1 = |M| + |N|·(h − 2a)/2000 (kN·m,
    N kN, h/a mm) và M1l tương tự với tải dài hạn.
    GIẢ ĐỊNH của app cho vách: a = khoảng cách từ mép tới lớp
    thép dọc ngoài cùng = cover_đai + dia_h + dia_dọc/2 (xem
    wall_engine._wall_phi_l_dir); với thép vùng biên tập trung
    nhiều lớp thì đây là xấp xỉ lớp ngoài cùng, không phải trọng
    tâm của cả nhóm thép vùng biên như ví dụ §7 (a = 79 mm).
    Không có dữ liệu dài hạn (has_data False) → 2,0 (giới hạn
    trên, thiên an toàn), đúng hành vi cũ của app.
    """
    if not has_data:
        return 2.0
    lever = float(h_mm) - 2.0 * float(a_mm)
    if lever <= 0.0:
        return 2.0
    M1 = abs(M) + abs(N) * lever / 2000.0
    M1l = abs(M_lt) + abs(N_lt) * lever / 2000.0
    if M1 <= 1e-12:
        return 2.0
    return min(2.0, max(1.0, 1.0 + M1l / M1))


# Ngưỡng cổng η — TCVN 5574:2018 §8.1.2.1.2: chỉ kể đến ảnh hưởng
# uốn dọc bằng cách nhân e0 với η (CT (44)) khi độ mảnh L0/i > 14.
# Dưới ngưỡng (kể cả λ = 14 đúng bằng) η = 1.0 — nghiêm ngặt ">".
ETA_SLENDERNESS_LIMIT = 14.0


def buckling_factors(e0x: float, e0y: float, cx: float, cy: float,
                     phiL: float, Eb: float, Ix: float, Iy: float,
                     Isx: float, Isy: float, L0x: float, L0y: float,
                     N: float, Mx: float, My: float,
                     lambda_x: float = None,
                     lambda_y: float = None,
                     phiLx: float = None, phiLy: float = None) -> BucklingResult:
    """Tính hệ số uốn dọc theo CT (44)-(48) + cổng λ §8.1.2.1.2.

    Eb (MPa), I (mm⁴), L0 (m), N (kN), M (kN·m).
    δe = e0/h ∈ [0.15, 1.5]; kb = 0.15/[φL·(0.3+δe)]
    D = kb·Eb·Ib + ks·Es·Is (ks=0.7); Ncr = π²·D/L0²; η = 1/(1-N/Ncr)
    CỔNG (mỗi phương độc lập, áp cho cả cột lẫn vách — cùng hàm này):
    η của phương nào chỉ được nhân khi λ của phương đó > 14
    (TCVN 5574:2018 §8.1.2.1.2); λ ≤ 14 → η = 1.0 cho phương đó,
    M* = M. Cổng CHỈ gạt hệ số η nhân vào và M*: Ncr, D, kb, δe
    không đổi (Ncr là đặc trưng tiết diện, vẫn hiển thị đầy đủ).
    lambda_x/lambda_y: độ mảnh λ = L0/i của khe "x"/"y" do đầu gọi
    tính (cột: L0·1000/i từ section_inertia — khớp đúng λ mà §3
    thuyết minh in; vách: lam_out/lam_in). Không truyền thì fallback
    slenderness(L0x, cy) / slenderness(L0y, cx) — đúng tuyệt đối
    với tiết diện chữ nhật/tròn (i = h/√12).
    phiLx/phiLy (2026-10-28, cho vách nhập tải dài hạn theo từng
    phương): khi cho, khe x dùng phiLx, khe y dùng phiLy; không
    cho thì cả 2 khe dùng phiL như cũ (cột giữ nguyên hành vi).
    Khi Ncr ≤ |N| thì η thô bị kẹp ở 10,0 (giá trị tùy tiện, không
    có trong chuẩn — xem eta_clamped_*): cờ kẹp chỉ bật khi η kẹp
    đó thật sự được áp (λ > 14), để thuyết minh cảnh báo đúng.
    """
    # δe: e0y cho phương X (uốn trong mặt phẳng y), e0x cho phương Y
    d_ex = min(max(e0y / max(cy, 1e-9), 0.15), 1.5)
    d_ey = min(max(e0x / max(cx, 1e-9), 0.15), 1.5)
    _plx = phiL if phiLx is None else phiLx
    _ply = phiL if phiLy is None else phiLy
    kbx = 0.15 / (_plx * (0.3 + d_ex))
    kby = 0.15 / (_ply * (0.3 + d_ey))
    Es = 2.0e5  # MPa
    ks = 0.7
    # Đổi đơn vị: Eb(MPa=N/mm²)·I(mm⁴) = N·mm² → kN·m²: /1e9
    Dx = (kbx * Eb * Ix + ks * Es * Isx) / 1e9
    Dy = (kby * Eb * Iy + ks * Es * Isy) / 1e9
    Ncrx = math.pi ** 2 * Dx / max(L0x, 1e-9) ** 2
    Ncry = math.pi ** 2 * Dy / max(L0y, 1e-9) ** 2
    if lambda_x is None:
        lambda_x = slenderness(L0x, cy)
    if lambda_y is None:
        lambda_y = slenderness(L0y, cx)
    raw_etax = 1.0 / (1.0 - abs(N) / Ncrx) if Ncrx > abs(N) else 10.0
    raw_etay = 1.0 / (1.0 - abs(N) / Ncry) if Ncry > abs(N) else 10.0
    # Cổng §8.1.2.1.2 — nghiêm ngặt ">": λ = 14 đúng bằng → η = 1.0.
    etax = raw_etax if lambda_x > ETA_SLENDERNESS_LIMIT else 1.0
    etay = raw_etay if lambda_y > ETA_SLENDERNESS_LIMIT else 1.0
    return BucklingResult(d_ex, d_ey, kbx, kby, Dx, Dy, Ncrx, Ncry,
                          etax, etay, etax * Mx, etay * My,
                          eta_clamped_x=(raw_etax == 10.0
                                         and lambda_x
                                         > ETA_SLENDERNESS_LIMIT),
                          eta_clamped_y=(raw_etay == 10.0
                                         and lambda_y
                                         > ETA_SLENDERNESS_LIMIT))


def design_moment(N: float, M: float, e0_mm: float, eta: float,
                  floor_sign: float = 1.0) -> float:
    """Mô men thiết kế theo sàn lệch tâm, TCVN 5574:2018 §8.1.2.2.4
    (e0 = max(e1, ea)) + §8.1.2.1.2 (cổng η) + CT (44)–(48).

    M* = sign·N·e0·η / 1000 (N kN, e0 mm → kN·m). Chỉ gọi khi N > 0
    (N ≤ 0: đầu gọi giữ mô men gốc, không dựng mô men từ sàn).
    Dấu: M ≠ 0 → dấu của M gốc; M = 0 → floor_sign (dấu sàn).
    Khi e1 ≥ ea thì N·e0 = |M| nên công thức này trùng hệt η·M
    (không đổi ca thường); nó chỉ chạm các trường hợp e1 < ea,
    kể cả M gốc = 0. Sàn ea KHÔNG phải bao bảo thủ theo D/C ở
    tiết diện không đối xứng: xoay tia tải sang góc khỏe hơn có
    thể làm D/C giảm (vd vách L thuần ngoài MP).
    """
    if M != 0.0:
        return math.copysign(N * e0_mm * eta / 1000.0, M)
    return floor_sign * N * e0_mm * eta / 1000.0
