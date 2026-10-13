"""Điều phối kiểm tra cột BTCT: vật liệu -> tiết diện -> ổn định -> NDM -> kết quả."""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .materials import (CONCRETE_GRADES, STEEL_GRADES, ConcreteMaterial,
                        SteelMaterial)
from .sections import (Section, bar_area, clear_spacing, layout_circle_bars,
                       layout_custom_bars, layout_rect_bars,
                       make_circle_section, make_rect_section)
from .interaction import BiaxialCapacity
from .stability import (LongTermLoads, effective_length, phi_L, slenderness)


@dataclass
class ColumnInput:
    # Vật liệu
    concrete_grade: str = "B25"
    gamma_b: float = 1.0
    steel_grade: str = "CB400-V"
    gamma_s: float = 1.0
    concrete_model: str = "3line"  # "3line" | "2line"
    # Tiết diện
    section_type: str = "rect"     # "rect" | "circle"
    cx: float = 400.0              # mm (rect: cạnh x; circle: đường kính)
    cy: float = 400.0              # mm
    # Cốt thép
    rebar_mode: str = "auto"       # "auto" | "custom"
    bar_dia: float = 20.0
    n_bars: int = 8                # cho tròn / auto
    nx: int = 3                    # số thanh mỗi cạnh (chữ nhật)
    ny: int = 3
    cover: float = 30.0
    custom_bars: List[Tuple[float, float, float]] = field(default_factory=list)
    # Ổn định
    Lx: float = 4.0                # m
    Ly: float = 4.0
    top_x: str = "khop"; bottom_x: str = "khop"
    top_y: str = "khop"; bottom_y: str = "khop"
    psi_x: Optional[float] = None
    psi_y: Optional[float] = None
    # Nội lực
    N: float = 1000.0              # kN (nén dương)
    Mx: float = 50.0               # kN·m
    My: float = 50.0               # kN·m
    long_term: LongTermLoads = field(default_factory=LongTermLoads)


@dataclass
class CheckResult:
    ok: bool
    utilization: float
    N: float; Mx: float; My: float
    M_resultant: float
    M_capacity: float
    phi_L: float
    L0x: float; L0y: float
    lambda_x: float; lambda_y: float
    steel_area: float
    reinforcement_ratio: float
    clear_cx: float; clear_cy: float
    details: List[str] = field(default_factory=list)


def build_section(inp: ColumnInput) -> Section:
    conc = ConcreteMaterial(CONCRETE_GRADES[inp.concrete_grade], inp.gamma_b)
    steel = SteelMaterial(STEEL_GRADES[inp.steel_grade], inp.gamma_s)
    if inp.section_type == "rect":
        sec = make_rect_section(inp.cx, inp.cy, conc, steel)
        if inp.rebar_mode == "custom" and inp.custom_bars:
            layout_custom_bars(sec, inp.custom_bars)
        else:
            layout_rect_bars(sec, inp.bar_dia, inp.nx, inp.ny, inp.cover)
    else:
        sec = make_circle_section(inp.cx, conc, steel)
        if inp.rebar_mode == "custom" and inp.custom_bars:
            layout_custom_bars(sec, inp.custom_bars)
        else:
            layout_circle_bars(sec, inp.bar_dia, inp.n_bars, inp.cover)
    return sec


def check_column(inp: ColumnInput, n_angles: int = 24) -> CheckResult:
    details: List[str] = []
    sec = build_section(inp)

    L0x = effective_length(inp.Lx, inp.top_x, inp.bottom_x, inp.psi_x)
    L0y = effective_length(inp.Ly, inp.top_y, inp.bottom_y, inp.psi_y)
    lam_x = slenderness(L0x, inp.cx)
    lam_y = slenderness(L0y, inp.cy)
    details.append(f"L0x = {L0x:.2f} m, L0y = {L0y:.2f} m")
    details.append(f"Độ mảnh λx = {lam_x:.1f}, λy = {lam_y:.1f}")

    phi = phi_L(inp.N, inp.Mx, inp.My, inp.long_term)
    details.append(f"Hệ số φL = {phi:.2f}")

    # Phân tích NDM
    cap = BiaxialCapacity(sec, model=inp.concrete_model, n_angles=n_angles)
    r = cap.check(inp.N, inp.Mx, inp.My)
    details.append(
        f"Momen tổng hợp M = {r['M_resultant']:.1f} kN·m, "
        f"khả năng chịu M = {r['M_capacity']:.1f} kN·m"
    )
    details.append(f"Hệ số sử dụng = {r['utilization']:.3f}")

    mu = sec.reinforcement_ratio
    details.append(f"Hàm lượng cốt thép μ = {mu*100:.2f}%")
    ccx, ccy = clear_spacing(sec)
    if math.isfinite(ccx):
        details.append(f"Khoảng hở thông thủy: {ccx:.1f} / {ccy:.1f} mm")

    return CheckResult(
        ok=r["ok"], utilization=r["utilization"],
        N=inp.N, Mx=inp.Mx, My=inp.My,
        M_resultant=r["M_resultant"], M_capacity=r["M_capacity"],
        phi_L=phi, L0x=L0x, L0y=L0y, lambda_x=lam_x, lambda_y=lam_y,
        steel_area=sec.steel_area, reinforcement_ratio=mu,
        clear_cx=ccx, clear_cy=ccy, details=details,
    )
