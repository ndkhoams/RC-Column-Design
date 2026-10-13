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
    layer: int = 1  # 1: lớp ngoài, 2: lớp trong (kiểu VietconSoft)


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


def _inner_positions(half_len: float, n: int) -> List[float]:
    """n điểm cách đều nằm phía trong đoạn [-half_len, half_len]
    (không trùng 2 đầu — dùng cho thép cạnh, góc đã có thép riêng)."""
    if n <= 0:
        return []
    if n == 1:
        return [0.0]
    return [-half_len + (i + 1) * (2.0 * half_len) / (n + 1)
            for i in range(n)]


def layout_vietconsoft_bars(sec: Section, inp) -> List[Rebar]:
    """Bố trí thép kiểu VietconSoft cho tiết diện chữ nhật.

    Quy ước trục app: cx = t3 (cạnh ngang), cy = t2 (cạnh đứng).
      - "Thép cạnh t2": nằm trên 2 mặt trái/phải (mỗi mặt dài cy = t2).
      - "Thép cạnh t3": nằm trên 2 mặt trên/dưới (mỗi mặt dài cx = t3).
    Lớp 1: 4 thép góc + thép cạnh (không trùng góc).
    Lớp 2 (nếu two_layer): perimeter | concentrated | bundled.
    Mỗi Rebar mang thuộc tính layer (1/2) để vẽ màu khác nhau.
    """
    rebars: List[Rebar] = []
    cx, cy = sec.cx, sec.cy
    cover = float(getattr(inp, "cover", 30.0))

    def add(x: float, y: float, dia: float, layer: int):
        rebars.append(Rebar(x, y, bar_area(dia), dia, layer))

    def off1(dia: float) -> float:
        """Khoảng cách tim thép lớp 1 tới mép."""
        return cover + dia / 2.0

    def off2(d1: float, d2: float) -> float:
        """Khoảng cách tim thép lớp 2 tới mép: cách mặt thép lớp 1
        một khe s = l2_s_layer."""
        s_layer = float(getattr(inp, "l2_s_layer", 30.0))
        return cover + d1 + s_layer + d2 / 2.0

    # ---------------- Lớp 1 ----------------
    cd = float(getattr(inp, "corner_dia", 20.0))
    oc = off1(cd)
    # 4 thép góc
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            add(sx * (cx / 2.0 - oc), sy * (cy / 2.0 - oc), cd, 1)

    n2 = max(0, int(getattr(inp, "edge_t2_count", 3)))
    d2 = float(getattr(inp, "edge_t2_dia", 20.0))
    n3 = max(0, int(getattr(inp, "edge_t3_count", 3)))
    d3 = float(getattr(inp, "edge_t3_dia", 20.0))
    # Thép cạnh t2: 2 mặt trái/phải, phân bố theo y (trừ vị trí góc)
    if n2 > 0:
        o2 = off1(d2)
        for sx in (-1.0, 1.0):
            for y in _inner_positions(cy / 2.0 - oc, n2):
                add(sx * (cx / 2.0 - o2), y, d2, 1)
    # Thép cạnh t3: 2 mặt trên/dưới, phân bố theo x (trừ vị trí góc)
    if n3 > 0:
        o3 = off1(d3)
        for sy in (-1.0, 1.0):
            for x in _inner_positions(cx / 2.0 - oc, n3):
                add(x, sy * (cy / 2.0 - o3), d3, 1)

    # ---------------- Lớp 2 ----------------
    if bool(getattr(inp, "two_layer", False)) and sec.kind == "rect":
        mode = str(getattr(inp, "layer2_mode", "perimeter"))
        if mode == "perimeter":
            l2d2 = float(getattr(inp, "l2_t2_dia", 20.0))
            l2d3 = float(getattr(inp, "l2_t3_dia", 20.0))
            oc2 = off2(cd, l2d3)
            for sx in (-1.0, 1.0):
                for sy in (-1.0, 1.0):
                    add(sx * (cx / 2.0 - oc2), sy * (cy / 2.0 - oc2),
                        l2d3, 2)
            if n2 > 0:
                o2b = off2(d2, l2d2)
                for sx in (-1.0, 1.0):
                    for y in _inner_positions(cy / 2.0 - oc2, n2):
                        add(sx * (cx / 2.0 - o2b), y, l2d2, 2)
            if n3 > 0:
                o3b = off2(d3, l2d3)
                for sy in (-1.0, 1.0):
                    for x in _inner_positions(cx / 2.0 - oc2, n3):
                        add(x, sy * (cy / 2.0 - o3b), l2d3, 2)
        elif mode == "concentrated":
            side = str(getattr(inp, "l2_side", "t2"))
            cnt = max(0, int(getattr(inp, "l2_count", 5)))
            dd = float(getattr(inp, "l2_dia", 25.0))
            if cnt > 0:
                if side == "t2":
                    # thêm mỗi mặt trái/phải
                    ob = off2(d2, dd)
                    for sx in (-1.0, 1.0):
                        for y in _inner_positions(cy / 2.0 - oc, cnt):
                            add(sx * (cx / 2.0 - ob), y, dd, 2)
                else:
                    # thêm mỗi mặt trên/dưới
                    ob = off2(d3, dd)
                    for sy in (-1.0, 1.0):
                        for x in _inner_positions(cx / 2.0 - oc, cnt):
                            add(x, sy * (cy / 2.0 - ob), dd, 2)
        elif mode == "bundled":
            pos = str(getattr(inp, "bundle_pos", "inner"))
            b_edge = max(1, int(getattr(inp, "bundle_size", 2)))
            b_cor = max(1, int(getattr(inp, "bundle_corner", 2)))
            gap = max(0.0, float(getattr(inp, "bundle_gap", 0.0)))

            def bundle_cx(x0: float, y0: float, k: int, dia: float,
                          layer: int, offv: float, horizontal: bool):
                """Xếp k thanh thành cụm quanh (x0, y0) theo phương ngang/dọc."""
                step = dia + gap
                start = -((k - 1) / 2.0) * step
                for i in range(k):
                    d = start + i * step
                    if horizontal:
                        add(x0 + d, y0, dia, layer)
                    else:
                        add(x0, y0 + d, dia, layer)

            # vị trí lớp 1 (để đặt bó)
            if pos == "inner":
                ocb = off2(cd, cd)
                edge_off = lambda d1, d2b: off2(d1, d2b)
                lay = 2
            else:  # "outer": cùng lớp ngoài, xếp cụm quanh vị trí lớp 1
                ocb = oc
                edge_off = lambda d1, d2b: off1(d2b)
                lay = 2
            for sx in (-1.0, 1.0):
                for sy in (-1.0, 1.0):
                    bundle_cx(sx * (cx / 2.0 - ocb), sy * (cy / 2.0 - ocb),
                              b_cor, cd, lay, ocb, True)
            if n2 > 0:
                o2b = edge_off(d2, d2)
                for sx in (-1.0, 1.0):
                    for y in _inner_positions(cy / 2.0 - oc, n2):
                        bundle_cx(sx * (cx / 2.0 - o2b), y,
                                  b_edge, d2, lay, o2b, False)
            if n3 > 0:
                o3b = edge_off(d3, d3)
                for sy in (-1.0, 1.0):
                    for x in _inner_positions(cx / 2.0 - oc, n3):
                        bundle_cx(x, sy * (cy / 2.0 - o3b),
                                  b_edge, d3, lay, o3b, True)

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
