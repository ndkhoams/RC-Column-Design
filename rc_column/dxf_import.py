"""Import tiết diện cột bất kỳ từ file DXF (vẽ bằng AutoCAD).

Quy ước bản vẽ (ghi trong hướng dẫn sử dụng):
- Biên bê tông: LWPOLYLINE khép kín, layer "BT"
- Lỗ rỗng:      LWPOLYLINE khép kín, layer "BT_HOLE" (phải nằm trong BT)
- Thép dọc:     CIRCLE, layer "THEP" (tâm = vị trí, bán kính = r thép)

Đơn vị: đọc $INSUNITS (4=mm, 5=cm, 6=m); mặc định mm nếu không rõ.
Hệ tọa độ: tịnh tiến về trọng tâm tiết diện (gốc tại centroid).

Vượt CSiCol ở điểm: import được cả thép (CSiCol chỉ import được shape
bê tông, thép phải vẽ tay).
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

try:
    import ezdxf
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False


# ---------------------------------------------------------------------------
# Hình học polygon
# ---------------------------------------------------------------------------

def polygon_area(verts: List[Tuple[float, float]]) -> float:
    """Diện tích (Shoelace), dương nếu CCW."""
    a = 0.0
    n = len(verts)
    for i in range(n):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def polygon_centroid(verts: List[Tuple[float, float]]) -> Tuple[float, float]:
    """Trọng tâm polygon."""
    a = polygon_area(verts)
    if abs(a) < 1e-12:
        return 0.0, 0.0
    cx = cy = 0.0
    n = len(verts)
    for i in range(n):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    return cx / (6.0 * a), cy / (6.0 * a)


def polygon_moments(verts: List[Tuple[float, float]]
                    ) -> Tuple[float, float, float]:
    """Trả về (A, Ix, Iy) quanh gốc O (Ix = ∫y²dA, Iy = ∫x²dA)."""
    A = Ix = Iy = 0.0
    n = len(verts)
    for i in range(n):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        A += cross
        Ix += cross * (y0 * y0 + y0 * y1 + y1 * y1)
        Iy += cross * (x0 * x0 + x0 * x1 + x1 * x1)
    return A / 2.0, Ix / 12.0, Iy / 12.0


def point_in_polygon(px: float, py: float,
                     verts: List[Tuple[float, float]]) -> bool:
    """Ray-casting even-odd."""
    inside = False
    n = len(verts)
    j = n - 1
    for i in range(n):
        xi, yi = verts[i]
        xj, yj = verts[j]
        if ((yi > py) != (yj > py)) and \
                (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _segments_intersect(p1, p2, p3, p4) -> bool:
    def _ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])
    return (_ccw(p1, p3, p4) != _ccw(p2, p3, p4) and
            _ccw(p1, p2, p3) != _ccw(p1, p2, p4))


def polygon_self_intersects(verts: List[Tuple[float, float]]) -> bool:
    n = len(verts)
    for i in range(n):
        a1, a2 = verts[i], verts[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            b1, b2 = verts[j], verts[(j + 1) % n]
            if _segments_intersect(a1, a2, b1, b2):
                return True
    return False


# ---------------------------------------------------------------------------
# Đọc DXF
# ---------------------------------------------------------------------------

@dataclass
class DxfSection:
    """Kết quả đọc DXF trước khi dựng Section."""
    outlines: List[List[Tuple[float, float]]] = field(default_factory=list)
    holes: List[List[Tuple[float, float]]] = field(default_factory=list)
    rebars: List[Tuple[float, float, float]] = field(default_factory=list)
    # (x, y, dia) theo đơn vị gốc bản vẽ
    unit_scale: float = 1.0  # nhân để ra mm
    warnings: List[str] = field(default_factory=list)


_INCH_MM = 25.4
_INSUNITS_TO_MM = {4: 1.0, 5: 10.0, 6: 1000.0, 8: _INCH_MM, 1: _INCH_MM}


def read_dxf_section(path: str, layer_concrete: str = "BT",
                     layer_hole: str = "BT_HOLE",
                     layer_rebar: str = "THEP",
                     unit_override: Optional[float] = None) -> DxfSection:
    """Đọc tiết diện từ file DXF."""
    if not HAS_EZDXF:
        raise ImportError(
            "Chưa cài thư viện ezdxf.\n"
            "Chạy lệnh sau rồi thử lại:\n"
            "    pip install ezdxf")
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    res = DxfSection()

    # Đơn vị
    try:
        insunits = int(doc.header.get("$INSUNITS", 0))
    except Exception:
        insunits = 0
    scale = _INSUNITS_TO_MM.get(insunits, 1.0)
    if insunits == 0:
        res.warnings.append(
            "Không rõ đơn vị bản vẽ ($INSUNITS=0) — giả thiết mm. "
            "Kiểm tra kích thước ở preview.")
    if unit_override and unit_override > 0:
        scale = unit_override
    res.unit_scale = scale

    def _layer(e) -> str:
        try:
            return str(e.dxf.layer or "").upper()
        except Exception:
            return ""

    LC, LH, LR = layer_concrete.upper(), layer_hole.upper(), layer_rebar.upper()

    for e in msp:
        etype = e.dxftype()
        lay = _layer(e)
        if etype == "LWPOLYLINE" and lay in (LC, LH):
            try:
                pts = [(p[0], p[1]) for p in e.get_points()]
            except Exception:
                continue
            if len(pts) < 3:
                continue
            # Bỏ điểm trùng cuối
            if math.hypot(pts[0][0] - pts[-1][0],
                          pts[0][1] - pts[-1][1]) < 1e-9:
                pts = pts[:-1]
            is_closed = bool(e.closed)
            if not is_closed:
                gap = math.hypot(pts[0][0] - pts[-1][0],
                                 pts[0][1] - pts[-1][1])
                if gap < 1.0:  # tự đóng nếu hở < 1 đơn vị vẽ
                    res.warnings.append(
                        f"Polyline layer {lay} hở {gap:.2f} — tự đóng.")
                else:
                    raise ValueError(
                        f"Polyline layer {lay} không khép kín "
                        f"(hở {gap:.2f}).")
            if polygon_self_intersects(pts):
                raise ValueError(
                    f"Polyline layer {lay} tự cắt nhau.")
            pts_mm = [(x * scale, y * scale) for x, y in pts]
            if lay == LC:
                res.outlines.append(pts_mm)
            else:
                res.holes.append(pts_mm)
        elif etype == "CIRCLE" and lay == LR:
            try:
                cx, cy = float(e.dxf.center[0]), float(e.dxf.center[1])
                r = float(e.dxf.radius)
            except Exception:
                continue
            if r <= 0:
                continue
            res.rebars.append((cx * scale, cy * scale, 2.0 * r * scale))

    if not res.outlines:
        raise ValueError(
            f"Không tìm thấy biên bê tông (LWPOLYLINE kín, layer '{LC}').")
    if not res.rebars:
        res.warnings.append(
            f"Không tìm thấy thép (CIRCLE, layer '{LR}').")

    # Validate: lỗ nằm trong biên, thép nằm trong biên
    for h in res.holes:
        if not any(point_in_polygon(h[0][0], h[0][1], o)
                   for o in res.outlines):
            res.warnings.append("Có lỗ nằm ngoài biên bê tông.")
    for x, y, d in res.rebars:
        if not any(point_in_polygon(x, y, o) for o in res.outlines):
            res.warnings.append(
                f"Thép tại ({x:.0f}, {y:.0f}) nằm ngoài biên — "
                "có thể sai đơn vị; thép này sẽ bị bỏ qua.")

    # Cảnh báo diện tích bất thường
    Ag = sum(abs(polygon_area(o)) for o in res.outlines)
    if Ag < 1e4 or Ag > 1e7:
        res.warnings.append(
            f"Diện tích bê tông {Ag:.0f} mm² bất thường — "
            "kiểm tra đơn vị bản vẽ.")
    return res


# ---------------------------------------------------------------------------
# Dựng Section từ DxfSection
# ---------------------------------------------------------------------------

def build_polygon_section(dxf: DxfSection, concrete, steel,
                          fiber_step: float = 10.0):
    """Sinh fiber lưới đều + dựng Section(kind='poly').

    concrete, steel: material objects (TCVN hoặc ACI đều được —
    Section chỉ lưu tham chiếu).
    """
    from .sections import Section, Fiber, Rebar

    # Trọng tâm (theo outline đầu tiên; nhiều outline thì cộng dồn)
    tot_a = 0.0
    scx = scy = 0.0
    for o in dxf.outlines:
        a = abs(polygon_area(o))
        cx, cy = polygon_centroid(o)
        tot_a += a
        scx += cx * a
        scy += cy * a
    if tot_a <= 0:
        raise ValueError("Diện tích bê tông không dương.")
    ccx, ccy = scx / tot_a, scy / tot_a

    def _shift(verts):
        return [(x - ccx, y - ccy) for x, y in verts]

    outlines = [_shift(o) for o in dxf.outlines]
    holes = [_shift(h) for h in dxf.holes]

    # Bbox để quét lưới
    xs = [x for o in outlines for x, _ in o]
    ys = [y for o in outlines for _, y in o]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)

    fibers: List[Fiber] = []
    s = fiber_step
    y = ymin + s / 2.0
    while y < ymax:
        x = xmin + s / 2.0
        while x < xmax:
            inside = any(point_in_polygon(x, y, o) for o in outlines)
            in_hole = any(point_in_polygon(x, y, h) for h in holes)
            if inside and not in_hole:
                fibers.append(Fiber(x, y, s * s))
            x += s
        y += s

    rebars: List[Rebar] = []
    for x, y, dia in dxf.rebars:
        xr, yr = x - ccx, y - ccy
        if not any(point_in_polygon(xr, yr, o) for o in outlines):
            continue  # bỏ thép ngoài biên (đã cảnh báo)
        rebars.append(Rebar(xr, yr, math.pi * (dia / 2.0) ** 2, dia))

    sec = Section(kind="poly", cx=xmax - xmin, cy=ymax - ymin,
                  fibers=fibers, rebars=rebars,
                  concrete=concrete, steel=steel,
                  poly_verts=outlines, poly_holes=holes)
    return sec


def polygon_gross_props(outlines, holes=None):
    """(Ag, Ix_c, Iy_c) quanh trọng tâm — dùng cho stability/shear."""
    holes = holes or []
    A = Ix = Iy = 0.0
    for o in outlines:
        a, ix, iy = polygon_moments(o)
        A += a
        Ix += ix
        Iy += iy
    for h in holes:
        a, ix, iy = polygon_moments(h)
        A -= abs(a)
        Ix -= abs(ix)
        Iy -= abs(iy)
    A = abs(A)
    if A <= 0:
        return 0.0, 0.0, 0.0
    # centroid đã ở gốc sau _shift → Ix, Iy đã quanh centroid
    return A, abs(Ix), abs(Iy)
