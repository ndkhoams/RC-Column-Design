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

Từ 2026-10-23 (format web Vietcons cho mục 2/3): build_wall_section
rẽ theo winp.steel_mode:
- "perimeter": thép dọc theo CHU VI tiết diện (4 cạnh, 1 lớp theo
  chu vi), mỗi cạnh số khoảng = ceil(chiều_dài_trong/s), bước thực
  = chiều_dài_trong/số_khoảng <= s, thanh góc dùng chung không tính
  trùng; chiều_dài_trong của cạnh = kích thước cạnh - 2*(c + dia_h
  + d/2) (c = lớp bảo vệ cốt đai, tới mặt ngoài thép ngang dia_h).
  Ca mẫu 2500x350, c=13, dia_h=12, d12, s200:
  cạnh dài 13 khoảng x 187.5, cạnh ngắn 2 khoảng x 144 -> 30 thanh.
- "boundary": vùng biên đối xứng 2 đầu: mỗi đầu nL vị trí dọc trong
  Lb x nT hàng ngang theo tw (hàng ngoài tại 2 mặt, hàng thêm nằm
  giữa theo chiều dày); thân vách: thanh trên 2 mặt trong đoạn giữa
  (Lw - 2*Lb) theo cùng quy tắc bước <= s như cạnh dài của chế độ
  chu vi. Lớp bảo vệ c đo tới mặt ngoài thép ngang dia_h (thống nhất
  cho mọi nhóm thép — xem cover_migration về giả định này) ở cả 2
  chế độ mới.
- khác (file cũ chưa qua normalize): generator lát 1 cũ (biên 2 hàng
  kể đai + bụng giữa 2 Lb) — giữ nguyên để tương thích.
Xoay tiết diện (winp.rot_deg): 90/270 hoán đổi vai trò Lw/tw cho cả
dựng hình và tính toán — xem wall_dims.
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
#   bước 15.6mm (nx=160): c lệch -9.1mm, D/C -0.03%, batch 112 ~11.5s
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
    ny = _clamp(int(math.ceil(tw / step)), _NX_MIN, _NY_MAX)
    return nx, ny


def _linspace(a: float, b: float, n: int) -> List[float]:
    if n <= 1:
        return [(a + b) / 2.0]
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def wall_dims(winp):
    """Kích thước hiệu dụng (Lw, tw) sau khi áp góc xoay tiết diện.

    Xoay 90/270 độ: hoán đổi vai trò Lw/tw trong dựng hình và tính
    toán (tiết diện chữ nhật đối xứng nên 0/180 giống nhau hình học).
    CHỈ dùng cho vách phẳng (rect) — các loại mới lát 1 dùng polygon
    canonical riêng (xem _polygon_for_type) và KHÔNG qua hàm này
    (build_wall_section rẽ trước khi gọi wall_dims cho loại mới).
    """
    Lw = float(winp.Lw)
    tw = float(winp.tw)
    try:
        rot = int(getattr(winp, "rot_deg", 0) or 0) % 360
    except Exception:
        rot = 0
    if rot in (90, 270):
        return tw, Lw
    return Lw, tw


# ---------------------------------------------------------------------
# Hình học polygon cho 5 loại mới (lát 1, 2026-10-27)
# ---------------------------------------------------------------------
# Quy ước: polygon ở khung CANONICAL, tâm tại gốc, trục x = trục
# chính của hình vẽ preview (xem từng hàm). Tất cả polygon đều trực
# giao (chỉ cạnh ngang/dọc) nên offset inward và tính diện tích đều
# chính xác bằng công thức đa giác. Các quan hệ hình học dưới đây là
# SUY TỪ Ac web Vietcons (không phải định nghĩa chữ của web — web
# chỉ cho kích thước + Ac/As, không ghi công thức): đã kiểm chứng
# Ac khớp web từng loại trong test (sai số < 0,001 m²):
# - Barbell: Lw = tổng dài, Tf = dài theo vách của đầu mở rộng,
#   Bf = rộng ngang đầu: Ac = (Lw-2*Tf)*tw + 2*Tf*Bf.
# - Tee: cánh Bf*t + thân (Lw-t)*t (Lw = chiều dài thân + t).
# - Ell: L1*t + (L2-t)*t (góc chung t*t tính 1 lần).
# - C-core: thân Lw*t + 2 cánh (Bf-t)*t + 2 hồi (Lr-t)*t — hồi đo
#   từ mặt ngoài cánh vào trong (tổng 600), phần chồng cánh đã
#   trừ t. Bf/Lr đo từ mặt ngoài thân/cánh.
# - U-core: như C nhưng không hồi: Lw*t + 2*(Bf-t)*t.
# Đối xứng: đầu/cánh 1 = đầu trên (C/U) hoặc đầu trái (Barbell);
# đầu 2 = đầu còn lại. Khi sec_sym=True, cặp 2 lấy bằng cặp 1.
def _poly_barbell(winp):
    Lw, tw = float(winp.Lw), float(winp.tw)
    sym = bool(getattr(winp, "sec_sym", True))
    Bf, Tf = float(winp.sec_bf), float(winp.sec_tf)
    Bf2, Tf2 = (Bf, Tf) if sym else (float(winp.sec_bf2),
                                     float(winp.sec_tf2))
    x0, x1 = -Lw / 2.0, Lw / 2.0
    return [
        (x0, -Bf / 2.0), (x0 + Tf, -Bf / 2.0),
        (x0 + Tf, -tw / 2.0), (x1 - Tf2, -tw / 2.0),
        (x1 - Tf2, -Bf2 / 2.0), (x1, -Bf2 / 2.0),
        (x1, Bf2 / 2.0), (x1 - Tf2, Bf2 / 2.0),
        (x1 - Tf2, tw / 2.0), (x0 + Tf, tw / 2.0),
        (x0 + Tf, Bf / 2.0), (x0, Bf / 2.0),
    ]


def _poly_tee(winp):
    Lw, Bf, t = float(winp.Lw), float(winp.sec_bf), float(winp.sec_t)
    x0, x1 = -Lw / 2.0, Lw / 2.0
    return [
        (x0, -Bf / 2.0), (x0 + t, -Bf / 2.0),
        (x0 + t, -t / 2.0), (x1, -t / 2.0),
        (x1, t / 2.0), (x0 + t, t / 2.0),
        (x0 + t, Bf / 2.0), (x0, Bf / 2.0),
    ]


def _poly_ell(winp):
    L1, L2, t = float(winp.sec_L1), float(winp.sec_L2), float(winp.sec_t)
    x0, x1, y0, y1 = -L1 / 2.0, L1 / 2.0, -L2 / 2.0, L2 / 2.0
    return [
        (x0, y0), (x1, y0), (x1, y0 + t),
        (x0 + t, y0 + t), (x0 + t, y1), (x0, y1),
    ]


def _poly_c_core(winp):
    # Khung chưa tâm: thân x in [0, t], y in [-Lw/2, Lw/2]; cánh
    # x in [0, Bf], hồi x in [Bf-t, Bf]. Sau đó tịnh tiến về tâm
    # bbox (x về max(Bf1,Bf2)/2, y về 0) để khớp quy ước gốc tại
    # trọng tâm bbox như các loại khác.
    Lw, t = float(winp.Lw), float(winp.sec_t)
    sym = bool(getattr(winp, "sec_sym", True))
    Bf, Lr = float(winp.sec_bf), float(winp.sec_lr)
    Bf2, Lr2 = (Bf, Lr) if sym else (float(winp.sec_bf2),
                                     float(winp.sec_lr2))
    y0, y1 = -Lw / 2.0, Lw / 2.0
    raw = [
        (0.0, y0), (Bf2, y0), (Bf2, y0 + Lr2),
        (Bf2 - t, y0 + Lr2), (Bf2 - t, y0 + t),
        (t, y0 + t), (t, y1 - t), (Bf - t, y1 - t),
        (Bf - t, y1 - Lr), (Bf, y1 - Lr), (Bf, y1), (0.0, y1),
    ]
    cx = max(Bf, Bf2) / 2.0
    return [(x - cx, y) for x, y in raw]


def _poly_u_core(winp):
    Lw, t = float(winp.Lw), float(winp.sec_t)
    sym = bool(getattr(winp, "sec_sym", True))
    Bf = float(winp.sec_bf)
    Bf2 = Bf if sym else float(winp.sec_bf2)
    y0, y1 = -Lw / 2.0, Lw / 2.0
    raw = [
        (0.0, y0), (Bf2, y0), (Bf2, y0 + t),
        (t, y0 + t), (t, y1 - t), (Bf, y1 - t), (Bf, y1), (0.0, y1),
    ]
    cx = max(Bf, Bf2) / 2.0
    return [(x - cx, y) for x, y in raw]


_POLY_BUILDERS = {
    "barbell": _poly_barbell,
    "tee": _poly_tee,
    "ell": _poly_ell,
    "c-core": _poly_c_core,
    "u-core": _poly_u_core,
}


def _polygon_area_moments(verts):
    """Diện tích + mô men quán tính (Ix = ∫y², Iy = ∫x²) của đa giác
    theo công thức shoelace (tâm tại gốc — polygon đã tâm bbox)."""
    a2 = 0.0
    ix = 0.0
    iy = 0.0
    n = len(verts)
    for i in range(n):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % n]
        cr = x0 * y1 - x1 * y0
        a2 += cr
        ix += cr * (y0 * y0 + y0 * y1 + y1 * y1)
        iy += cr * (x0 * x0 + x0 * x1 + x1 * x1)
    a = abs(a2) / 2.0
    return a, abs(ix) / 12.0, abs(iy) / 12.0


def _point_in_poly(x, y, verts):
    """Ray casting (even-odd) cho đa giác trực giao."""
    inside = False
    n = len(verts)
    for i in range(n):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xin = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xin:
                inside = not inside
    return inside


def _offset_polygon_orthogonal(verts, d):
    """Đa giác lùi vào trong d (chỉ đa giác trực giao): mỗi cạnh
    dịch vào trong theo pháp tuyến trong, giao 2 cạnh kề cho đỉnh
    mới. Trả về cùng thứ tự đỉnh (đã chuẩn hoá CCW nếu cần)."""
    s = sum(verts[i][0] * verts[(i + 1) % len(verts)][1]
            - verts[(i + 1) % len(verts)][0] * verts[i][1]
            for i in range(len(verts)))
    v = list(verts)
    if s < 0:
        v = v[::-1]
    n = len(v)
    out = []
    for i in range(n):
        p_prev, p_cur, p_next = v[i - 1], v[i], v[(i + 1) % n]

        def _inward(a, b):
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy) or 1.0
            return (-dy / L, dx / L)  # trái của cạnh = trong (CCW)

        n1 = _inward(p_prev, p_cur)
        n2 = _inward(p_cur, p_next)
        x = p_cur[0] + d * (n1[0] if n1[0] != 0 else n2[0])
        y = p_cur[1] + d * (n1[1] if n1[1] != 0 else n2[1])
        out.append((x, y))
    return out


def _gen_perimeter_poly(verts, cover, d, s, dia_h=0.0):
    """Thép chu vi tự động cho đa giác (lát 1, chế độ auto của
    T/L/C/U và chế độ perimeter của Barbell): thanh trên đa giác
    lùi vào trong inset = cover + dia_h + d/2, mỗi cạnh số khoảng
    = ceil(chiều_dài/s), bước thực <= s, góc dùng chung (không
    tính trùng) — cùng quy tắc _gen_perimeter của rect, chỉ tổng
    quát hoá từ hình chữ nhật sang đa giác trực giao.
    Trả (bars, extra) với bars = [(x, y, dia)]."""
    if d <= 0 or s <= 0:
        raise ValueError("Thép chu vi: đường kính/khoảng cách phải > 0")
    inset = cover + dia_h + d / 2.0
    iv = _offset_polygon_orthogonal(verts, inset)
    bars = []
    seen = set()
    extra = {"edges": []}
    n = len(iv)
    for i in range(n):
        a, b = iv[i], iv[(i + 1) % n]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L <= 0:
            continue
        ni = max(1, int(math.ceil(L / s)))
        extra["edges"].append((L, ni, L / ni))
        for k in range(ni + 1):
            t = k / ni
            p = (a[0] + (b[0] - a[0]) * t,
                 a[1] + (b[1] - a[1]) * t)
            key = (round(p[0], 6), round(p[1], 6))
            if key not in seen:
                seen.add(key)
                bars.append((p[0], p[1], d))
    return bars, extra


def _poly_dims(winp, verts):
    """Dim cho preview đa giác: (dim_segments x, dim_segments_y,
    nhãn tổng x, nhãn tổng y). dim_segments x theo trục chính,
    dim_segments_y chỉ cho C/U (hồi Lr đo theo trục thân)."""
    st = str(getattr(winp, "section_type", "rect"))
    xs = [p[0] for p in verts]
    ys = [p[1] for p in verts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if st == "barbell":
        Lw, tw = float(winp.Lw), float(winp.tw)
        Tf = float(winp.sec_tf)
        Tf2 = Tf if bool(getattr(winp, "sec_sym", True)) \
            else float(winp.sec_tf2)
        segs = [(x0, x0 + Tf, f"Tf = {Tf:.0f}"),
                (x0 + Tf, x1 - Tf2, f"{Lw - Tf - Tf2:.0f}"),
                (x1 - Tf2, x1, f"Tf = {Tf2:.0f}")]
        return segs, [], f"Lw = {Lw:.0f} mm", \
            f"Bf = {x1 - x0:.0f} mm"
    if st == "tee":
        t = float(winp.sec_t)
        segs = [(x0, x0 + t, f"t = {t:.0f}"),
                (x0 + t, x1, f"{x1 - (x0 + t):.0f}")]
        return segs, [], f"Lw = {float(winp.Lw):.0f} mm", \
            f"Bf = {float(winp.sec_bf):.0f} mm"
    if st == "ell":
        t = float(winp.sec_t)
        segs = [(x0, x0 + t, f"t = {t:.0f}"),
                (x0 + t, x1, f"{x1 - (x0 + t):.0f}")]
        return segs, [], f"L1 = {float(winp.sec_L1):.0f} mm", \
            f"L2 = {float(winp.sec_L2):.0f} mm"
    if st == "c-core":
        t = float(winp.sec_t)
        Lr = float(winp.sec_lr)
        Lr2 = Lr if bool(getattr(winp, "sec_sym", True)) \
            else float(winp.sec_lr2)
        segs = [(x0, x0 + t, f"t = {t:.0f}"),
                (x0 + t, x1 - t, f"{x1 - t - (x0 + t):.0f}"),
                (x1 - t, x1, f"t = {t:.0f}")]
        segs_y = [(y0, y0 + Lr2, f"Lr = {Lr2:.0f}"),
                  (y0 + Lr2, y1 - Lr, f"{y1 - Lr - (y0 + Lr2):.0f}"),
                  (y1 - Lr, y1, f"Lr = {Lr:.0f}")]
        return segs, segs_y, f"Bf = {x1 - x0:.0f} mm", \
            f"Lw = {float(winp.Lw):.0f} mm"
    if st == "u-core":
        t = float(winp.sec_t)
        segs = [(x0, x0 + t, f"t = {t:.0f}"),
                (x0 + t, x1, f"{x1 - (x0 + t):.0f}")]
        segs_y = [(y0, y0 + t, f"t = {t:.0f}"),
                  (y0 + t, y1 - t, f"{y1 - t - (y0 + t):.0f}"),
                  (y1 - t, y1, f"t = {t:.0f}")]
        return segs, segs_y, f"Bf = {x1 - x0:.0f} mm", \
            f"Lw = {float(winp.Lw):.0f} mm"
    return [], [], f"Lw = {x1 - x0:.0f} mm", f"tw = {y1 - y0:.0f} mm"


def _spacing_stats(runs):
    """Thống kê khoảng cách từ các 'run' thanh thẳng hàng.

    runs: list (list vị trí tâm đã sắp xếp, đường kính của run).
    Trả về (smax, s_step_min, sclear_min): bước tâm lớn nhất, bước tâm
    nhỏ nhất, khoảng hở thông thủy nhỏ nhất (bước - đường kính).
    """
    steps = []
    for pos, d in runs:
        pos = sorted(pos)
        for a, b in zip(pos, pos[1:]):
            steps.append((b - a, d))
    if not steps:
        return None, None, None
    return (max(s for s, _ in steps), min(s for s, _ in steps),
            min(s - d for s, d in steps))


def _gen_perimeter(Lw, tw, cover, d, s, dia_h=0.0):
    """Chế độ (a): thép dọc theo chu vi — xem docstring đầu module.

    cover: lớp bảo vệ cốt đai c (tới mặt ngoài thép ngang dia_h);
    inset tới tim thanh = cover + dia_h + d/2, cả 2 trục.
    Trả về (bars, runs, extra): bars = [(x, y, dia)] (layer 2 khi đưa
    vào Section), runs cho thống kê khoảng cách.
    """
    if d <= 0 or s <= 0:
        raise ValueError("Thép chu vi: đường kính/khoảng cách phải > 0")
    inset = cover + dia_h + d / 2.0
    x0, x1 = -Lw / 2.0 + inset, Lw / 2.0 - inset
    y0, y1 = -tw / 2.0 + inset, tw / 2.0 - inset
    if x1 <= x0 or y1 <= y0:
        raise ValueError(
            "Lớp bảo vệ + đường kính quá lớn so với tiết diện "
            f"({Lw:.0f}x{tw:.0f}, c={cover:.0f}, d{d:.0f})")
    len_l = x1 - x0
    len_s = y1 - y0
    n_l = max(1, int(math.ceil(len_l / s)))
    n_s = max(1, int(math.ceil(len_s / s)))
    xs = _linspace(x0, x1, n_l + 1)
    ys = _linspace(y0, y1, n_s + 1)
    bars: List[Tuple[float, float, float]] = []
    for x in xs:
        bars.append((x, y0, d))
        bars.append((x, y1, d))
    for y in ys[1:-1]:
        bars.append((x0, y, d))
        bars.append((x1, y, d))
    runs = [(xs, d), (xs, d), (ys, d), (ys, d)]
    extra = {"step_long": len_l / n_l, "step_short": len_s / n_s}
    return bars, runs, extra


def _gen_boundary(Lw, tw, cover, Lb, db, n_Lb, n_tw, L_out, L_in,
                  wd, ws, dia_h=0.0):
    """Chế độ (b): vùng biên đối xứng 2 đầu + thép phân bố thân vách.

    cover: lớp bảo vệ cốt đai c (tới mặt ngoài thép ngang dia_h,
    thống nhất cho mọi nhóm thép). Vùng biên mỗi đầu, tất cả thanh
    cùng db, không thanh góc riêng (mô hình cột dọc, user chốt
    2026-10-25, thay mô hình hàng ngang 950b4d5):
    - 2 hàng dọc theo Lb (trên + dưới, tại 2 mặt tw cách mép
      c + dia_h + db/2); mỗi hàng có n_Lb thanh cách đều theo Lb
      (thanh đầu tại c + dia_h + db/2 từ mặt đầu vách, thanh cuối
      tại Lb - (c + dia_h + db/2)) — 2 thanh đầu hàng chính là góc,
      đã tính trong n_Lb.
    - LỚP = CỘT DỌC theo chiều tw: mỗi lớp là 1 cột thép tại 1 vị
      trí thanh của 2 hàng, gồm n_tw thanh Ở GIỮA (không tính 2
      hàng trên/dưới — thanh trên/dưới của cột TRÙNG thanh của 2
      hàng nên không đếm thêm, không sinh trùng, không dedupe).
      L_out cột đầu (từ đầu ngoài) = lớp ngoài; L_in cột cuối
      (từ hàng trong cùng đi ra về phía đầu vách) = lớp trong;
      các vị trí hàng còn lại (nếu n_Lb > L_out + L_in) chỉ có
      thép 2 hàng.
      Ràng buộc L_out + L_in <= n_Lb (clamp phòng thủ ở đây, panel
      clamp ở _collect_wall).
    Tổng/vùng = 2*n_Lb + n_tw*(L_out + L_in). Thân vách: 2 mặt
    trong đoạn giữa (Lw - 2*Lb), quy tắc bước <= ws như cạnh dài
    chế độ chu vi.
    Trả về (be_left, be_right, web, runs, extra) với bars (x, y, dia).
    Migration: file nghĩa cũ 950b4d5 (be_n_tw tính cả 2 góc) được
    dịch n_tw_mới = max(n_tw_cũ - 2, 0) ở normalize_wall_dict; file
    tiền-950b4d5 qua mapping cũ rồi áp tiếp quy tắc này (VACH.json
    nT=2 -> n_tw=0 -> đúng 2 hàng x 4 thanh, cùng tọa độ lưới cũ).
    """
    warnings = []
    be_left: List[Tuple[float, float, float]] = []
    be_right: List[Tuple[float, float, float]] = []
    runs = []
    n_Lb = max(1, int(n_Lb))
    n_tw = max(0, int(n_tw))
    L_out = max(0, min(int(L_out), n_Lb))
    L_in = max(0, min(int(L_in), n_Lb - L_out))
    if Lb > 0 and db > 0:
        inset_b = cover + dia_h + db / 2.0
        if n_Lb == 1:
            ps = [Lb / 2.0]
        elif Lb - 2.0 * inset_b > 0:
            ps = _linspace(inset_b, Lb - inset_b, n_Lb)
        else:
            warnings.append(
                f"Vùng biên Lb={Lb:.0f}mm ngắn so với c + dia_h + db "
                f"({inset_b:.0f}mm): thanh biên xếp cách nhau 1.1*db "
                "từ mặt đầu vách.")
            ps = [inset_b + k * 1.1 * db for k in range(n_Lb)]
        face = tw / 2.0 - inset_b
        # 2 hàng dọc Lb (dưới + trên — thứ tự y tăng dần như lưới
        # cũ, để thứ tự thanh trong sec.rebars không đổi khi thép
        # không đổi, tránh lệch vùng nén/PNG ở mức bit).
        for p in ps:
            for yy in (-face, face):
                be_left.append((-Lw / 2.0 + p, yy, db))
                be_right.append((Lw / 2.0 - p, yy, db))
        for yy in (-face, face):
            runs.append(([-Lw / 2.0 + p for p in ps], db))
            runs.append(([Lw / 2.0 - p for p in ps], db))
        # Cột lớp: ps[:L_out] = lớp ngoài (từ đầu ngoài vào);
        # ps[n_Lb-L_in:] = lớp trong (neo ở hàng trong cùng, đếm
        # đi ra về phía đầu vách — user chốt 2026-10-25, khác bản
        # 9eac50e6 đặt lớp trong kề sau lớp ngoài); mỗi cột n_tw
        # thanh giữa (chia đều giữa 2 hàng, không tính 2 hàng).
        # Clamp trên đã đảm bảo L_out + L_in <= n_Lb nên 2 nhóm
        # không bao giờ trùng vị trí.
        if n_tw > 0 and (L_out + L_in) > 0:
            ys_mid = _linspace(-face, face, n_tw + 2)[1:-1]
            for p in ps[:L_out] + ps[n_Lb - L_in:]:
                for yy in ys_mid:
                    be_left.append((-Lw / 2.0 + p, yy, db))
                    be_right.append((Lw / 2.0 - p, yy, db))
            for _side in range(2):
                runs.append((list(ys_mid), db))
    # Thân vách (2 mặt, đoạn giữa 2 vùng biên)
    web: List[Tuple[float, float, float]] = []
    s_web = None
    a = -Lw / 2.0 + (Lb if Lb > 0 else 0.0)
    b = Lw / 2.0 - (Lb if Lb > 0 else 0.0)
    if b - a > 0 and wd > 0 and ws > 0:
        g = cover + dia_h + wd / 2.0
        lo, hi = a + g, b - g
        if hi <= lo:
            xs = [(a + b) / 2.0]
            s_web = float(ws)
        else:
            n_int = max(1, int(math.ceil((hi - lo) / ws)))
            xs = _linspace(lo, hi, n_int + 1)
            s_web = (hi - lo) / n_int
        y_v = tw / 2.0 - cover - dia_h - wd / 2.0
        for x in xs:
            web.append((x, y_v, wd))
            web.append((x, -y_v, wd))
        runs.append((xs, wd))
        runs.append((xs, wd))
    zones = [("Đầu 1", len(be_left), float(db)),
             ("Bụng vách", len(web), float(wd)),
             ("Đầu 2", len(be_right), float(db))]
    extra = {"zones": zones, "s_web_actual": s_web, "warnings": warnings,
             "web_a": a, "web_b": b, "be_rows": 2,
             "be_n_Lb": n_Lb, "be_n_tw_mid": n_tw,
             "be_layers_out": L_out, "be_layers_in": L_in}
    return be_left, be_right, web, runs, extra


def _build_wall_section_poly(winp, conc, steel, mesh_step=None,
                             nx=None, ny=None):
    """Dựng Section kind="poly" cho 5 loại mới (lát 1).

    Thép: chu vi tự động (per_dia/per_s) cho T/L/C/U; Barbell giữ
    dropdown nhưng cả 2 chế độ đều dùng thép chu vi đa giác trong
    lát 1 (vùng biên của Barbell chính là 2 đầu mở rộng — logic
    vùng biên Lb/db kiểu rect chưa ánh xạ sang đầu Barbell, ghi rõ
    ở meta.layout_text; file vẫn lưu đúng steel_mode đã chọn).
    Lưới fiber: ô vuông bước WALL_MESH_STEP, tâm trong đa giác,
    diện tích mỗi fiber chuẩn hoá để tổng = Ac đa giác chính xác.
    """
    from .sections import Fiber, Section
    verts = _POLY_BUILDERS[str(winp.section_type)](winp)
    Ac, Ix, Iy = _polygon_area_moments(verts)
    if Ac <= 0:
        raise ValueError("Kích thước tiết diện đa giác không hợp lệ")
    xs = [p[0] for p in verts]
    ys = [p[1] for p in verts]
    cx, cy = max(xs) - min(xs), max(ys) - min(ys)
    step = WALL_MESH_STEP if mesh_step is None else float(mesh_step)
    fibers = []
    nx_c = int(math.ceil(cx / step))
    ny_c = int(math.ceil(cy / step))
    dx, dy = cx / nx_c, cy / ny_c
    for i in range(nx_c):
        for j in range(ny_c):
            x = min(xs) + (i + 0.5) * dx
            y = min(ys) + (j + 0.5) * dy
            if _point_in_poly(x, y, verts):
                fibers.append(Fiber(x, y, dx * dy))
    fsum = sum(f.area for f in fibers)
    if fsum > 0:
        for f in fibers:
            f.area *= Ac / fsum
    sec = Section(kind="poly", cx=cx, cy=cy, concrete=conc, steel=steel,
                  fibers=fibers, poly_verts=[verts])
    cover = float(winp.cover)
    bars, extra = _gen_perimeter_poly(
        verts, cover, float(winp.per_dia), float(winp.per_s),
        float(winp.dia_h))
    sec.rebars = [Rebar(x, y, bar_area(d), d, 2) for x, y, d in bars]
    segs, segs_y, lab_x, lab_y = _poly_dims(winp, verts)
    mode = str(getattr(winp, "steel_mode", "perimeter") or "perimeter")
    rot = int(getattr(winp, "rot_deg", 0) or 0) % 360
    # Ghi chú Barbell + boundary (xem docstring): thép chu vi đa
    # giác, không dùng be_Lb/be_dia trong lát 1.
    layout = (f"Thép chu vi tự động: {len(bars)} thanh "
              f"d{float(winp.per_dia):.0f} (s nhập "
              f"{float(winp.per_s):.0f} mm, bước thực <= s)")
    if str(winp.section_type) == "barbell" and mode == "boundary":
        layout += (" — chế độ vùng biên của Barbell ở lát 1 dùng "
                   "chung thép chu vi đa giác (2 đầu mở rộng là vùng "
                   "biên); be_Lb/be_dia chưa ánh xạ sang đầu Barbell.")
    meta = {
        "nx": nx_c, "ny": ny_c, "mesh_step_x": dx, "mesh_step_y": dy,
        "steel_mode": "perimeter",
        "steel_mode_input": mode,
        "section_type": str(winp.section_type),
        "Lw_eff": cx, "tw_eff": cy, "rot_deg": rot,
        "n_bars": len(bars), "n_web": len(bars),
        "n_be_left": 0, "n_be_right": 0,
        "s_v_actual": None,
        "As_web": bar_area(float(winp.per_dia)) * len(bars),
        "As_be": 0.0, "As_total": sec.steel_area,
        "mu": sec.reinforcement_ratio,
        "web_a": min(xs), "web_b": max(xs),
        "bars_web": bars, "bars_be_left": [], "bars_be_right": [],
        "warnings": [],
        "zones": [("Chu vi", len(bars), float(winp.per_dia))],
        "smax": None, "s_step_min": None, "sclear_min": None,
        "dim_segments": segs, "dim_segments_y": segs_y,
        "dim_total_x_label": lab_x, "dim_total_y_label": lab_y,
        "poly_ac": Ac, "poly_Ix": Ix, "poly_Iy": Iy,
        "layout_text": layout,
    }
    return sec, meta


def build_wall_section(winp, conc: ConcreteMaterial, steel: SteelMaterial,
                       mesh_step: float = None,
                       nx: int = None, ny: int = None):
    """Dựng Section vách từ WallInput + vật liệu.

    Trả về (sec, meta): meta chứa thống kê bố trí thực (số thanh, bước
    thực, As từng nhóm, lưới fiber) để hiển thị/kiểm chứng — không nơi
    nào được suy lại từ công thức khác.
    """
    # ---- Nhánh đa giác (lát 1): 5 loại mới, chỉ mặt cắt + thép +
    # preview. Engine N–M/cắt của vách dùng công thức Lw/tw chữ nhật
    # (độ mảnh, Ig, b/h0) nên KHÔNG generic cho đa giác — CHECK cho
    # loại mới bị chặn ở GUI (_on_check_wall), không vào nhánh này
    # để tính. Nhánh này chỉ dựng Section kind="poly" để preview/
    # thẻ thép đọc đúng Ac/As; lưới fiber lấy mẫu trong đa giác
    # (diện tích fiber được chuẩn hoá về đúng Ac đa giác).
    _stype = str(getattr(winp, "section_type", "rect") or "rect")
    if _stype in _POLY_BUILDERS:
        return _build_wall_section_poly(winp, conc, steel, mesh_step,
                                        nx, ny)
    Lw, tw = wall_dims(winp)
    if Lw <= 0 or tw <= 0:
        raise ValueError(f"Kích thước vách không hợp lệ: Lw={Lw}, tw={tw}")
    cover = float(winp.cover)

    step = WALL_MESH_STEP if mesh_step is None else float(mesh_step)
    cnx, cny = mesh_counts(Lw, tw, step)
    if nx is None:
        nx = cnx
    if ny is None:
        ny = cny
    sec = make_rect_section(Lw, tw, conc, steel, nx=nx, ny=ny)

    mode = str(getattr(winp, "steel_mode", "boundary") or "boundary")
    base_meta = {"nx": nx, "ny": ny,
                 "mesh_step_x": Lw / nx, "mesh_step_y": tw / ny,
                 "steel_mode": mode, "Lw_eff": Lw, "tw_eff": tw,
                 "rot_deg": int(getattr(winp, "rot_deg", 0) or 0) % 360}

    if mode == "perimeter":
        bars, runs, extra = _gen_perimeter(
            Lw, tw, cover, float(winp.per_dia), float(winp.per_s),
            float(winp.dia_h))
        sec.rebars = [Rebar(x, y, bar_area(d), d, 2) for x, y, d in bars]
        smax, smin, sclear = _spacing_stats(runs)
        a1 = bar_area(float(winp.per_dia))
        meta = dict(base_meta)
        meta.update({
            "n_bars": len(bars), "n_web": len(bars),
            "n_be_left": 0, "n_be_right": 0,
            "s_v_actual": extra["step_long"],
            "As_web": a1 * len(bars), "As_be": 0.0,
            "As_total": sec.steel_area, "mu": sec.reinforcement_ratio,
            "web_a": -Lw / 2.0, "web_b": Lw / 2.0,
            "bars_web": bars, "bars_be_left": [], "bars_be_right": [],
            "warnings": [],
            "zones": [("Chu vi", len(bars), float(winp.per_dia))],
            "smax": smax, "s_step_min": smin, "sclear_min": sclear,
            "dim_segments": [],
            "layout_text":
                f"Thép chu vi: {len(bars)} thanh d{float(winp.per_dia):.0f} "
                f"(cạnh dài bước {extra['step_long']:.1f} mm, cạnh ngắn "
                f"bước {extra['step_short']:.1f} mm, s nhập "
                f"{float(winp.per_s):.0f} mm)",
        })
        return sec, meta

    if mode == "boundary":
        Lb = float(winp.be_Lb)
        be_l, be_r, web, runs, extra = _gen_boundary(
            Lw, tw, cover, Lb, float(winp.be_dia), int(winp.be_n_Lb),
            int(winp.be_n_tw), int(winp.be_L_out), int(winp.be_L_in),
            float(winp.web_dia), float(winp.web_s),
            float(winp.dia_h))
        rebars = [Rebar(x, y, bar_area(d), d, 1) for x, y, d in be_l + be_r]
        rebars += [Rebar(x, y, bar_area(d), d, 2) for x, y, d in web]
        sec.rebars = rebars
        smax, smin, sclear = _spacing_stats(runs)
        meta = dict(base_meta)
        meta.update({
            "n_bars": len(rebars), "n_web": len(web),
            "n_be_left": len(be_l), "n_be_right": len(be_r),
            "s_v_actual": extra["s_web_actual"],
            "As_web": bar_area(float(winp.web_dia)) * len(web),
            "As_be": bar_area(float(winp.be_dia)) * (len(be_l) + len(be_r)),
            "As_total": sec.steel_area, "mu": sec.reinforcement_ratio,
            "web_a": extra["web_a"], "web_b": extra["web_b"],
            "bars_web": web, "bars_be_left": be_l, "bars_be_right": be_r,
            "warnings": extra["warnings"],
            "zones": extra["zones"],
            "smax": smax, "s_step_min": smin, "sclear_min": sclear,
            "dim_segments": (
                [(-Lw / 2.0, -Lw / 2.0 + Lb, f"Lb = {Lb:.0f}"),
                 (-Lw / 2.0 + Lb, Lw / 2.0 - Lb, f"{Lw - 2.0 * Lb:.0f}"),
                 (Lw / 2.0 - Lb, Lw / 2.0, f"Lb = {Lb:.0f}")]
                if Lb > 0 and Lw - 2.0 * Lb > 0 else []),
            "layout_text":
                f"Vùng biên: {len(be_l) + len(be_r)} thanh "
                f"d{float(winp.be_dia):.0f} (mỗi đầu {len(be_l)} = "
                f"2 hàng × {extra['be_n_Lb']} thanh + "
                f"{extra['be_layers_out']} lớp ngoài × "
                f"{extra['be_n_tw_mid']} + "
                f"{extra['be_layers_in']} lớp trong × "
                f"{extra['be_n_tw_mid']}, "
                f"Lb = {Lb:.0f} mm); thân vách: {len(web)} thanh "
                f"d{float(winp.web_dia):.0f} (bước thực "
                f"{extra['s_web_actual'] if extra['s_web_actual'] else 0:.0f} mm)",
        })
        return sec, meta

    # ---- Nhánh legacy (lát 1): biên 2 hàng kể đai + bụng giữa 2 Lb ----
    dia_v = float(winp.dia_v)
    dia_h = float(winp.dia_h)
    dia_be = float(winp.dia_be)
    tie_d = float(winp.tie_dia_be)

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
        # Nhánh legacy C6 theo Lw: cộng dia_h cho đồng nhất với
        # C5-tw (thân theo tw đã có dia_h từ trước). Nhánh legacy
        # C5 (thép biên kể tie_d, thân theo tw kể dia_h) ĐÃ đúng
        # ngữ nghĩa c_đai nên giữ nguyên, không cộng thêm.
        g = cover + dia_h + dia_v / 2.0   # chừa từ mép đoạn bụng (mép vách/zone)
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
    meta = dict(base_meta)
    meta.update({
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
        "zones": [("Đầu 1", len(be_left), float(dia_be)),
                  ("Bụng vách", len(web), float(dia_v)),
                  ("Đầu 2", len(be_right), float(dia_be))],
        "smax": None, "s_step_min": None, "sclear_min": None,
        "dim_segments": [],
        "layout_text": None,
    })
    return sec, meta


def wall_readouts(winp, sec, meta) -> dict:
    """Khối SỐ ĐỌC của mục 3 (format web) từ đúng (sec, meta) đã dựng.

    Ix/Iy theo ký hiệu của web (hình vẽ web: X ngang theo tw, Y đứng
    theo Lw): Ix = tw*Lw^3/12 (quán tính trong mặt phẳng), Iy =
    Lw*tw^3/12. Đơn vị: Ac (m²), Ix/Iy (m⁴), As (mm²), khoảng cách mm.
    """
    if str(getattr(winp, "section_type", "rect")) in _POLY_BUILDERS:
        verts = _POLY_BUILDERS[str(winp.section_type)](winp)
        Ac, Ix, Iy = _polygon_area_moments(verts)
        # (Ix/Iy đa giác tính ở dưới theo công thức đa giác, không
        # qua Lw*tw — xem return ở cuối hàm qua biến _poly_moments.)
        _poly_moments = (Ix, Iy)
    else:
        Lw, tw = wall_dims(winp)
        Ac = Lw * tw
        _poly_moments = None
    # Tóm tắt thép theo đường kính (đường kính lớn trước)
    by_dia = {}
    for r in sec.rebars:
        by_dia[r.dia] = by_dia.get(r.dia, 0) + 1
    parts = [f"{n}d{d:.0f}" for d, n in
             sorted(by_dia.items(), key=lambda kv: -kv[0])]
    zones = []
    for name, n, d in meta.get("zones", []):
        az = bar_area(d) * n if d > 0 else 0.0
        zones.append({"name": name, "n": n, "dia": d, "As": az,
                      "mu": az / Ac if Ac > 0 else 0.0})
    if _poly_moments is not None:
        _ix_m4 = _poly_moments[0] / 1e12
        _iy_m4 = _poly_moments[1] / 1e12
    else:
        _ix_m4 = tw * Lw ** 3 / 12.0 / 1e12
        _iy_m4 = Lw * tw ** 3 / 12.0 / 1e12
    return {
        "n_bars": len(sec.rebars),
        "summary": " + ".join(parts),
        "As": sec.steel_area,
        "mu": sec.reinforcement_ratio,
        "Ac_m2": Ac / 1e6,
        "Ix_m4": _ix_m4,
        "Iy_m4": _iy_m4,
        "sclear_min": meta.get("sclear_min"),
        "smax": meta.get("smax"),
        "s_step_min": meta.get("s_step_min"),
        "zones": zones,
    }
