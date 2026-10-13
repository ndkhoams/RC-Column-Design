"""Kiểm tra cấu tạo cốt thép đai cột theo TCVN 5574:2018.

Các điều khoản áp dụng:
- 10.3.4.2: Đường kính đai ≥ 0.25×d_s,max và ≥ 6mm (8mm với B70–B100)
- 10.3.4.4: Bước đai ≤ 15d và ≤ 500mm (400mm với B70–B100);
             nếu hàm lượng thép dọc chịu nén > 1.5% ở một mặt:
             bước đai ≤ 10d và ≤ 300mm (250mm với B70–B100)
- 10.3.4.5: Mỗi thanh dọc (ít nhất cách một thanh) nằm tại vị trí uốn
             của đai; các vị trí uốn cách nhau ≤ 400mm theo chiều rộng mặt bên
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class StirrupInput:
    """Thông số cốt đai do người dùng nhập."""
    dia: float = 8.0        # đường kính đai (mm)
    spacing: float = 200.0  # bước đai (mm)
    legs: int = 2           # số nhánh đai


@dataclass
class StirrupCheck:
    item: str
    required: str
    provided: str
    ok: bool


@dataclass
class StirrupResult:
    ok: bool
    checks: List[StirrupCheck] = field(default_factory=list)
    # Giá trị tính toán để hiển thị
    d_sw_min: float = 0.0   # đường kính tối thiểu yêu cầu
    s_max: float = 0.0      # bước tối đa cho phép


def _is_high_grade(concrete_grade: str) -> bool:
    """Bê tông từ B70 đến B100."""
    try:
        num = int("".join(c for c in concrete_grade if c.isdigit()))
        return 70 <= num <= 100
    except Exception:
        return False


def check_stirrup(sec, stir: StirrupInput,
                  concrete_grade: str = "B25") -> StirrupResult:
    """Kiểm tra cấu tạo cốt đai theo TCVN 5574:2018.

    sec: ColumnSection (có .rebars với .dia, .cx, .cy)
    """
    res = StirrupResult(ok=True, checks=[])
    high = _is_high_grade(concrete_grade)

    # --- 10.3.4.2: Đường kính đai tối thiểu ---
    d_s_max = max((r.dia for r in sec.rebars), default=0)
    d_sw_min = max(0.25 * d_s_max, 8.0 if high else 6.0)
    res.d_sw_min = d_sw_min
    ok_d = stir.dia >= d_sw_min - 1e-9
    res.checks.append(StirrupCheck(
        "Đường kính đai (10.3.4.2)",
        f"≥ max(0.25×{d_s_max:.0f}, {'8' if high else '6'}) = {d_sw_min:.1f} mm",
        f"φ{stir.dia:.0f}",
        ok_d,
    ))
    res.ok &= ok_d

    # --- 10.3.4.4: Bước đai tối đa ---
    d_s_min = min((r.dia for r in sec.rebars), default=0)
    # Hàm lượng thép dọc chịu nén ở một mặt (xấp xỉ: tổng As / Ac)
    # Theo điều khoản: nếu > 1.5% ở MỘT MẶT thì siết chặt
    # Tính gần đúng: As_mặt / (b × h)
    As_total = sum(3.1416 * r.dia ** 2 / 4 for r in sec.rebars)
    Ac = sec.cx * sec.cy
    rho_face = (As_total / 2) / Ac * 100 if Ac > 0 else 0  # xấp xỉ 1 mặt

    if rho_face > 1.5:
        s_lim_d = 10 * d_s_min
        s_lim_abs = 250 if high else 300
        note = f"ρ_mặt ≈ {rho_face:.2f}% > 1.5%"
    else:
        s_lim_d = 15 * d_s_min
        s_lim_abs = 400 if high else 500
        note = f"ρ_mặt ≈ {rho_face:.2f}% ≤ 1.5%"

    s_max = min(s_lim_d, s_lim_abs)
    res.s_max = s_max
    ok_s = stir.spacing <= s_max + 1e-9
    res.checks.append(StirrupCheck(
        f"Bước đai (10.3.4.4) — {note}",
        f"≤ min({s_lim_d:.0f}, {s_lim_abs}) = {s_max:.0f} mm",
        f"{stir.spacing:.0f} mm",
        ok_s,
    ))
    res.ok &= ok_s

    # --- 10.3.4.5: Vị trí uốn đai ---
    # Yêu cầu: mỗi thanh dọc (ít nhất cách một thanh) tại vị trí uốn;
    # các vị trí uốn cách nhau ≤ 400mm theo chiều rộng mặt bên.
    # Kiểm tra đơn giản: số nhánh đai đủ để giữ các thanh
    n_bars = len(sec.rebars)
    # Với đai 2 nhánh: giữ được các thanh ở 4 góc + cạnh (nếu nx, ny ≤ 3)
    # Ước lượng: cần ít nhất ceil(n_bars / 4) vị trí uốn mỗi cạnh...
    # Kiểm tra thực tế: khoảng cách giữa các thanh ngoài cùng ≤ 400mm
    # đã được đảm bảo bởi 10.3.3.3 (400/500mm). Ở đây kiểm tra số nhánh.
    min_legs = 2
    # Nếu mỗi cạnh > 4 thanh, cần thêm nhánh
    nx = getattr(sec, "nx", 3)
    ny = getattr(sec, "ny", 3)
    if nx > 4 or ny > 4:
        min_legs = 4  # cần đai kép hoặc thêm nhánh
    ok_legs = stir.legs >= min_legs
    res.checks.append(StirrupCheck(
        "Cấu tạo nhánh đai (10.3.4.5)",
        f"≥ {min_legs} nhánh (mỗi cạnh ≤ 4 thanh)",
        f"{stir.legs} nhánh",
        ok_legs,
    ))
    res.ok &= ok_legs

    return res
