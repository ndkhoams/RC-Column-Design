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


def _gen_boundary(Lw, tw, cover, Lb, db, nL, nT, wd, ws, dia_h=0.0):
    """Chế độ (b): vùng biên đối xứng 2 đầu + thép phân bố thân vách.

    cover: lớp bảo vệ cốt đai c (tới mặt ngoài thép ngang dia_h,
    thống nhất cho mọi nhóm thép). Vùng biên mỗi đầu: nL vị trí dọc
    trong Lb (vị trí đầu tại c + dia_h + db/2 từ mặt đầu vách, vị trí
    cuối tại Lb - (c + dia_h + db/2)) x nT hàng ngang theo tw (hàng
    ngoài tại 2 mặt cách mép c + dia_h + db/2, hàng thêm chia đều ở
    giữa). Thân vách: 2 mặt trong đoạn giữa (Lw - 2*Lb), quy tắc
    bước <= ws như cạnh dài chế độ chu vi.
    Trả về (be_left, be_right, web, runs, extra) với bars (x, y, dia).
    """
    warnings = []
    be_left: List[Tuple[float, float, float]] = []
    be_right: List[Tuple[float, float, float]] = []
    runs = []
    if Lb > 0 and db > 0 and nL > 0 and nT > 0:
        inset_b = cover + dia_h + db / 2.0
        if nL == 1:
            ps = [Lb / 2.0]
        elif Lb - 2.0 * inset_b > 0:
            ps = _linspace(inset_b, Lb - inset_b, nL)
        else:
            warnings.append(
                f"Vùng biên Lb={Lb:.0f}mm ngắn so với c + dia_h + db "
                f"({inset_b:.0f}mm): thanh biên xếp cách nhau 1.1*db "
                "từ mặt đầu vách.")
            ps = [inset_b + k * 1.1 * db for k in range(nL)]
        if nT == 1:
            ys_be = [0.0]
        else:
            ys_be = _linspace(-(tw / 2.0 - inset_b), tw / 2.0 - inset_b, nT)
        for p in ps:
            for yy in ys_be:
                be_left.append((-Lw / 2.0 + p, yy, db))
                be_right.append((Lw / 2.0 - p, yy, db))
        for yy in ys_be:
            runs.append(([-Lw / 2.0 + p for p in ps], db))
            runs.append(([Lw / 2.0 - p for p in ps], db))
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
             "web_a": a, "web_b": b}
    return be_left, be_right, web, runs, extra


def build_wall_section(winp, conc: ConcreteMaterial, steel: SteelMaterial,
                       mesh_step: float = None,
                       nx: int = None, ny: int = None):
    """Dựng Section vách từ WallInput + vật liệu.

    Trả về (sec, meta): meta chứa thống kê bố trí thực (số thanh, bước
    thực, As từng nhóm, lưới fiber) để hiển thị/kiểm chứng — không nơi
    nào được suy lại từ công thức khác.
    """
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
            Lw, tw, cover, Lb, float(winp.be_dia), int(winp.be_nL),
            int(winp.be_nT), float(winp.web_dia), float(winp.web_s),
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
                f"{int(winp.be_nL)} vị trí x {int(winp.be_nT)} hàng, "
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
    Lw, tw = wall_dims(winp)
    Ac = Lw * tw
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
    return {
        "n_bars": len(sec.rebars),
        "summary": " + ".join(parts),
        "As": sec.steel_area,
        "mu": sec.reinforcement_ratio,
        "Ac_m2": Ac / 1e6,
        "Ix_m4": tw * Lw ** 3 / 12.0 / 1e12,
        "Iy_m4": Lw * tw ** 3 / 12.0 / 1e12,
        "sclear_min": meta.get("sclear_min"),
        "smax": meta.get("smax"),
        "s_step_min": meta.get("s_step_min"),
        "zones": zones,
    }
