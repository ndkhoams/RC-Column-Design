"""Dựng tiết diện vách chữ nhật đặc (chế độ Vách, GĐ1 — lát 1).

Quy ước trục (khớp §5.1 bản thiết kế): Section(kind="rect", cx=Lw,
cy=tw) — trục x dọc theo chiều dài vách Lw (hướng t3 của app), trục y
theo chiều dày tw (hướng t2). Nội lực ánh xạ khi gọi solver:
M_in (trong mặt phẳng) <-> My (M3), M_out (ngoài mặt phẳng) <-> Mx (M2).

Thép đứng phân bố chỉ đặt ở phần bụng giữa 2 vùng biên; thép biên tập
trung đặt trong Lb mỗi đầu; thép NGANG phân bố KHÔNG vào tiết diện
N–M (chỉ dùng cho cắt + cấu tạo ở các lát sau) — ghi rõ để tránh hiểu
nhầm "thiếu thép" khi xem danh sách thanh.

Bước lưới fiber: xem WALL_MESH_STEP — chốt bằng số đo ở lát 1
(bảng quét lưới trong báo cáo lát 1): sai số c_neutral và D/C so với
lưới mịn nhất + thời gian tính/batch.
"""

import math
from typing import List, Tuple

from .materials import ConcreteMaterial, SteelMaterial
from .sections import Rebar, Section, bar_area, make_rect_section

# Bước lưới fiber mặc định (mm) cho tiết diện vách — CHỐT BẰNG SỐ ĐO
# ở lát 1 (gate_mesh, ca chuẩn 2500x350, tổ hợp N=2500/M_in=3000/
# M_out=60, chuẩn = lưới 400x56 bước 6.25mm: c=856.9mm, D/C=0.42789):
#   bước 62.5mm (nx=40):  c lệch -52.5mm, D/C -0.55%, batch 112 ~7.5s
#   bước 25mm  (nx=100):  c lệch -18.4mm, D/C -0.24%, batch 112 ~9.0s
#   bước 15.6mm (nx=160): c lệch  -9.1mm, D/C -0.03%, batch 112 ~11.5s
# Chọn 25mm: D/C sai <=0.25% (mọi bước đều <=0.6%), sai số c -18mm
# chỉ gây lệch ~9mm cho Lb_req = max(c-0.1Lw, c/2) ở lát 3 (không
# đáng kể so với làm tròn cấu tạo); mịn hơn chỉ giảm nửa sai số c
# trong khi số fiber x2.6 và thời gian dựng engine x3.4.
WALL_MESH_STEP = 25.0

# Trần số ô lưới (theo §5.1 thiết kế): nx theo Lw, ny theo tw
_NX_MIN, _NX_MAX = 40, 160
_NY_MIN, _NY_MAX = 8, 24


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def mesh_counts(Lw: float, tw: float, step: float = WALL_MESH_STEP):
    """Số ô lưới (nx, ny) từ bước lưới yêu cầu (mm)."""
    nx = _clamp(int(math.ceil(Lw / step)), _NX_MIN, _NX_MAX)
    ny = _clamp(int(math.ceil(tw / step)), _NY_MIN, _NY_MAX)
    return nx, ny


def _linspace(a: float, b: float, n: int) -> List[float]:
    if n <= 1:
        return [(a + b) / 2.0]
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def build_wall_section(winp, conc: ConcreteMaterial, steel: SteelMaterial,
                       mesh_step: float = None,
                       nx: int = None, ny: int = None):
    """Dựng Section vách từ WallInput + vật liệu.

    Trả về (sec, meta): meta chứa thống kê bố trí thực (số thanh, bước
    thực, As từng nhóm, lưới fiber) để hiển thị/kiểm chứng — không nơi
    nào được suy lại từ công thức khác.
    """
    Lw = float(winp.Lw)
    tw = float(winp.tw)
    if Lw <= 0 or tw <= 0:
        raise ValueError(f"Kích thước vách không hợp lệ: Lw={Lw}, tw={tw}")
    cover = float(winp.cover)
    dia_v = float(winp.dia_v)
    dia_h = float(winp.dia_h)
    dia_be = float(winp.dia_be)
    tie_d = float(winp.tie_dia_be)

    step = WALL_MESH_STEP if mesh_step is None else float(mesh_step)
    cnx, cny = mesh_counts(Lw, tw, step)
    if nx is None:
        nx = cnx
    if ny is None:
        ny = cny
    sec = make_rect_section(Lw, tw, conc, steel, nx=nx, ny=ny)

    rebars: List[Rebar] = []
    warnings: List[str] = []

    # ---- Thép biên tập trung (layer=1) ----
    # Hàng thép biên: 2 hàng theo tw, tim cách mép ngoài đoạn
    # cover + đai biên + dia_be/2 (giống tim thép góc cột kể đai).
    y_be = tw / 2.0 - cover - tie_d - dia_be / 2.0
    n_be = int(winp.n_be)
    be_left: List[Tuple[float, float, float]] = []
    be_right: List[Tuple[float, float, float]] = []
    for side, Lb, acc in ((+1.0, float(winp.Lb_right), be_right),
                          (-1.0, float(winp.Lb_left), be_left)):
        if Lb <= 0 or n_be <= 0 or dia_be <= 0:
            continue
        # Vị trí tim thanh theo x đo từ mép đầu vách vào trong:
        # thanh góc tại cover + tie + dia/2; thanh trong cùng cách mép
        # trong của vùng biên tie + dia/2.
        d_corner = cover + tie_d + dia_be / 2.0
        d_inner = Lb - tie_d - dia_be / 2.0
        if d_inner < d_corner:
            warnings.append(
                "Vùng biên ngắn hơn chiều dài tối thiểu cho 1 thanh biên "
                f"(Lb={Lb:.0f}mm): thép biên xếp chồng vào trong từ mép.")
            d_inner = d_corner
        n_top = (n_be + 1) // 2
        n_bot = n_be // 2
        for n_row, yy in ((n_top, y_be), (n_bot, -y_be)):
            if n_row <= 0:
                continue
            if n_row == 1:
                ds = [d_corner]
            elif d_inner > d_corner:
                ds = _linspace(d_corner, d_inner, n_row)
            else:
                # Vùng biên quá ngắn: xếp các thanh cách nhau 1.1*dia vào
                # phía trong (có thể vượt Lb) — đã cảnh báo ở trên.
                ds = [d_corner + k * 1.1 * dia_be for k in range(n_row)]
            for d in ds:
                x = side * (Lw / 2.0 - d)
                acc.append((x, yy, dia_be))
                rebars.append(Rebar(x, yy, bar_area(dia_be), dia_be, 1))

    # ---- Thép đứng phân bố ở phần bụng (layer=2) ----
    a = -Lw / 2.0 + float(winp.Lb_left)    # mép trong vùng biên trái
    b = Lw / 2.0 - float(winp.Lb_right)    # mép trong vùng biên phải
    web: List[Tuple[float, float, float]] = []
    s_actual = None
    if b - a > 0 and dia_v > 0 and float(winp.s_v) > 0:
        g = cover + dia_v / 2.0   # chừa từ mép đoạn bụng (mép vách/zone)
        lo, hi = a + g, b - g
        if hi <= lo:
            xs = [(a + b) / 2.0]
            s_actual = float(winp.s_v)
        else:
            n_int = max(1, int(math.ceil((hi - lo) / float(winp.s_v))))
            xs = _linspace(lo, hi, n_int + 1)
            s_actual = (hi - lo) / n_int
        if int(winp.layers_v) == 2:
            y_v = tw / 2.0 - cover - dia_h - dia_v / 2.0
            ys = [y_v, -y_v]
        else:
            ys = [0.0]
        for x in xs:
            for yy in ys:
                web.append((x, yy, dia_v))
                rebars.append(Rebar(x, yy, bar_area(dia_v), dia_v, 2))

    sec.rebars = rebars

    a_be = bar_area(dia_be) if dia_be > 0 else 0.0
    a_v = bar_area(dia_v) if dia_v > 0 else 0.0
    meta = {
        "nx": nx, "ny": ny,
        "mesh_step_x": Lw / nx, "mesh_step_y": tw / ny,
        "n_bars": len(rebars),
        "n_web": len(web), "n_be_left": len(be_left),
        "n_be_right": len(be_right),
        "s_v_actual": s_actual,
        "As_web": a_v * len(web),
        "As_be": a_be * (len(be_left) + len(be_right)),
        "As_total": sec.steel_area,
        "mu": sec.reinforcement_ratio,
        "web_a": a, "web_b": b,
        "bars_web": web, "bars_be_left": be_left,
        "bars_be_right": be_right,
        "warnings": warnings,
    }
    return sec, meta
