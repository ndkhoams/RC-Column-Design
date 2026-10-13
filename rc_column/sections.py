"""Tiết diện cột: hình chữ nhật / tròn, lưới fiber bê tông, bố trí cốt thép.

Hệ tọa độ: gốc tại trọng tâm tiết diện, trục x ngang, trục y đứng.
Đơn vị: mm cho kích thước, mm² cho diện tích.
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple

from .materials import ConcreteMaterial, SteelMaterial


@dataclass
class Fiber:
    """Một fiber bê tông (hình chữ nhật nhỏ)."""
    x: float      # tọa độ trọng tâm
    y: float
    area: float   # diện tích


@dataclass
class Rebar:
    """Một thanh thép (điểm)."""
    x: float
    y: float
    area: float
    dia: float = 0.0


@dataclass
class Section:
    kind: str  # "rect" | "circle"
    # rect: cx, cy là kích thước; circle: cx = cy = đường kính
    cx: float
    cy: float
    fibers: List[Fiber] = field(default_factory=list)
    rebars: List[Rebar] = field(default_factory=list)
    concrete: ConcreteMaterial = None
    steel: SteelMaterial = None

    @property
    def concrete_area(self) -> float:
        return sum(f.area for f in self.fibers)

    @property
    def steel_area(self) -> float:
        return sum(r.area for r in self.rebars)

    @property
    def gross_area(self) -> float:
        if self.kind == "rect":
            return self.cx * self.cy
        return math.pi * (self.cx / 2.0) ** 2

    @property
    def reinforcement_ratio(self) -> float:
        ag = self.gross_area
        return self.steel_area / ag if ag > 0 else 0.0


def make_rect_section(cx: float, cy: float,
                      concrete: ConcreteMaterial,
                      steel: SteelMaterial,
                      nx: int = 40, ny: int = 40) -> Section:
    """Tiết diện chữ nhật chia lưới fiber nx × ny."""
    sec = Section(kind="rect", cx=cx, cy=cy, concrete=concrete, steel=steel)
    dx, dy = cx / nx, cy / ny
    for i in range(nx):
        for j in range(ny):
            x = -cx / 2.0 + (i + 0.5) * dx
            y = -cy / 2.0 + (j + 0.5) * dy
            sec.fibers.append(Fiber(x, y, dx * dy))
    return sec


def make_circle_section(d: float,
                        concrete: ConcreteMaterial,
                        steel: SteelMaterial,
                        n: int = 48) -> Section:
    """Tiết diện tròn đường kính d, chia lưới vuông n × n, giữ fiber trong hình tròn."""
    sec = Section(kind="circle", cx=d, cy=d, concrete=concrete, steel=steel)
    r = d / 2.0
    dx = dy = d / n
    for i in range(n):
        for j in range(n):
            x = -r + (i + 0.5) * dx
            y = -r + (j + 0.5) * dy
            if x * x + y * y <= r * r:
                sec.fibers.append(Fiber(x, y, dx * dy))
    return sec


# ---------------------------------------------------------------------------
# Bố trí cốt thép
# ---------------------------------------------------------------------------
def bar_area(dia: float) -> float:
    return math.pi * dia * dia / 4.0


def layout_rect_bars(sec: Section, dia: float, nx: int, ny: int,
                     cover: float) -> List[Rebar]:
    """Bố trí thép đều theo chu vi tiết diện chữ nhật.

    dia: đường kính thanh; nx, ny: số thanh mỗi cạnh (góc tính 1 lần);
    cover: lớp bảo vệ (tới tim thép = cover + dia/2).
    """
    rebars: List[Rebar] = []
    a = bar_area(dia)
    cx, cy = sec.cx, sec.cy
    ox, oy = dia / 2.0 + cover, dia / 2.0 + cover  # khoảng cách tim tới mép
    xs = [ox + i * (cx - 2 * ox) / max(1, nx - 1) for i in range(nx)] if nx > 1 else [0.0]
    ys = [oy + j * (cy - 2 * oy) / max(1, ny - 1) for j in range(ny)] if ny > 1 else [0.0]
    pts = set()
    for x in xs:
        pts.add((round(x - cx / 2.0, 6), round(cy / 2.0 - oy, 6)))
        pts.add((round(x - cx / 2.0, 6), round(-cy / 2.0 + oy, 6)))
    for y in ys:
        pts.add((round(cx / 2.0 - ox, 6), round(y - cy / 2.0, 6)))
        pts.add((round(-cx / 2.0 + ox, 6), round(y - cy / 2.0, 6)))
    for (x, y) in sorted(pts):
        rebars.append(Rebar(x, y, a, dia))
    sec.rebars = rebars
    return rebars


def layout_circle_bars(sec: Section, dia: float, n_bars: int,
                       cover: float) -> List[Rebar]:
    """Bố trí n_bars thanh đều trên đường tròn."""
    rebars: List[Rebar] = []
    a = bar_area(dia)
    r = sec.cx / 2.0 - cover - dia / 2.0
    for k in range(n_bars):
        ang = 2.0 * math.pi * k / n_bars
        rebars.append(Rebar(r * math.cos(ang), r * math.sin(ang), a, dia))
    sec.rebars = rebars
    return rebars


def layout_custom_bars(sec: Section, bars: List[Tuple[float, float, float]]) -> List[Rebar]:
    """Bố trí tự do: list (x, y, dia)."""
    rebars = [Rebar(x, y, bar_area(d), d) for (x, y, d) in bars]
    sec.rebars = rebars
    return rebars


def clear_spacing(sec: Section) -> Tuple[float, float]:
    """Khoảng hở thông thủy nhỏ nhất giữa các thanh (mm).

    Trả về (min_theo_x, min_theo_y): khoảng hở nhỏ nhất đo theo phương x
    (giữa các cặp thanh gần nhau theo x) và theo phương y.
    """
    if len(sec.rebars) < 2:
        return (float("inf"), float("inf"))
    min_cx, min_cy = float("inf"), float("inf")
    rs = sec.rebars
    for i in range(len(rs)):
        for j in range(i + 1, len(rs)):
            dxc = abs(rs[i].x - rs[j].x)
            dyc = abs(rs[i].y - rs[j].y)
            davg = (rs[i].dia + rs[j].dia) / 2.0
            # chỉ xét cặp "kề nhau" theo từng phương (khoảng tim <= 1.5*d)
            if dyc <= davg * 1.5 + 1.0:
                clear = dxc - davg
                if clear < min_cx:
                    min_cx = clear
            if dxc <= davg * 1.5 + 1.0:
                clear = dyc - davg
                if clear < min_cy:
                    min_cy = clear
    inf = float("inf")
    return (max(0.0, min_cx) if min_cx != inf else inf,
            max(0.0, min_cy) if min_cy != inf else inf)
