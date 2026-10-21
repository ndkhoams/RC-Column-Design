"""Xuất thuyết minh tính toán ra PDF (kèm hình mặt cắt và biểu đồ tương tác)."""

import io
import math
import os
from typing import List, Tuple

# --- Font hỗ trợ tiếng Việt ---
def _mpl_font(name: str):
    """Đường dẫn font DejaVu Sans của matplotlib (có đủ glyph toán học)."""
    import matplotlib, os
    p = os.path.join(os.path.dirname(matplotlib.__file__),
                     "mpl-data", "fonts", "ttf", name)
    if not os.path.exists(p):
        raise FileNotFoundError(f"Không tìm thấy font {name} của matplotlib")
    return p


def _find_font():
    """DejaVu Sans của matplotlib cho toàn bộ thuyết minh."""
    return _mpl_font("DejaVuSans.ttf")


def _find_font_bold():
    return _mpl_font("DejaVuSans-Bold.ttf")


def _fm(x):
    """Định dạng cường độ tra bảng/nhập liệu: in ĐÚNG giá trị thật dùng trong
    tính toán, cắt số 0 thừa ở cuối (14.5 -> '14.5', 350 -> '350',
    1.05 -> '1.05'). Không dùng cho giá trị suy ra bằng phép chia."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(v):
        return "—"
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _fm_m(v_m):
    """Chiều dài theo MÉT: tối đa 3 số thập phân, cắt 0 thừa ở cuối
    (10.16 -> '10.16', 1.26 -> '1.26', 4.64 -> '4.64', 5.8 -> '5.8').
    Chỉ dùng cho hiển thị chiều dài cột/chiều dài tính toán ở mục 5."""
    try:
        v = float(v_m)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(v):
        return "—"
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


# --- Vẽ hình bằng matplotlib, trả về bytes PNG ---
def draw_section_ax(ax, sec, show_dims: bool = True, show_stats: bool = True,
                   legend_y: float = 1.02,
                   dot_scale: float = 1.0,
                    small_dots: bool = False):
    """Vẽ mặt cắt kiểu VietconSoft: nền lưới, khung đen, thép lớp 1 đỏ /
    lớp 2 xanh lá (cỡ chấm theo đường kính), trục t2/t3 tại tâm, dim t3/t2,
    thẻ thống kê bên dưới."""
    ax.set_aspect('equal', adjustable='box')
    import matplotlib.patches as mpatches
    from matplotlib.lines import Line2D
    cx, cy = sec.cx, sec.cy
    # Palette màu theo đường kính (trừ blue/green đã dùng cho trục)
    DIA_COLORS = ["#DC2626", "#9333EA", "#EA580C", "#0891B2",
                  "#BE123C", "#CA8A04", "#0F766E", "#4D7C0F"]
    L2_COLOR = "#F59E0B"  # lớp 2: cam

    # Nền lưới ô vuông nhạt
    ax.set_axisbelow(True)
    ax.grid(True, color="#E8EDF3", linewidth=0.7)
    # Khung cột viền đen đậm, nền xanh-xám rất nhạt
    if sec.kind == "rect":
        ax.add_patch(mpatches.Rectangle(
            (-cx/2, -cy/2), cx, cy, fill=True, facecolor="#F4F7FB",
            edgecolor="black", lw=2.0, zorder=2))
    elif sec.kind == "poly" and getattr(sec, "poly_verts", None):
        from matplotlib.patches import Polygon as MplPolygon
        for verts in sec.poly_verts:
            ax.add_patch(MplPolygon(verts, closed=True, fill=True,
                                    facecolor="#F4F7FB", edgecolor="black",
                                    lw=2.0, zorder=2))
        for verts in getattr(sec, "poly_holes", []):
            ax.add_patch(MplPolygon(verts, closed=True, fill=True,
                                    facecolor="white", edgecolor="black",
                                    lw=1.0, linestyle="--", zorder=3))
    else:
        ax.add_patch(mpatches.Circle(
            (0, 0), cx/2, fill=True, facecolor="#F4F7FB",
            edgecolor="black", lw=2.0, zorder=2))
    # Chấm thép theo (layer, dia)
    groups = {}
    for r in sec.rebars:
        groups.setdefault((r.layer, r.dia), []).append(r)
    legend_handles = []
    # Map dia -> màu (lớp 1); lớp 2 dùng xanh lá
    dias_l1 = sorted(set(d for (ly, d) in groups if ly == 1), reverse=True)
    dia_color = {d: DIA_COLORS[i % len(DIA_COLORS)]
                 for i, d in enumerate(dias_l1)}
    for (layer, dia) in sorted(groups, key=lambda k: (k[0], -k[1])):
        pts = groups[(layer, dia)]
        color = dia_color.get(dia, "#DC2626") if layer == 1 else L2_COLOR
        # Cỡ chấm theo dot_scale (app=1.5, PDF=0.8)
        dot_s = (max(4.0, dia * 0.22 * dot_scale)) ** 2
        # Co vào trong 4% để không chạm viền
        ax.scatter([p.x * 0.96 for p in pts], [p.y * 0.96 for p in pts],
                   s=dot_s, c=color, zorder=4,
                   edgecolors="white", linewidths=0.8)
        legend_handles.append(Line2D(
            [0], [0], marker="o", color="none", markerfacecolor=color,
            markeredgecolor="white", markersize=max(4.0, dia * 0.22 * dot_scale),
            label=f"d{dia:.0f}"))
    # Trục t2/t3 vượt ra khỏi đường bao để thấy text
    alen = max(cx, cy) * 0.62
    # Mũi tên trục t2 (xanh lá, ngang), t3 (xanh dương, đứng) - vẽ trên cùng
    # Đặt giới hạn trục để mũi tên không bị cắt
    _lim = alen * 1.25
    ax.set_xlim(-_lim, _lim)
    ax.set_ylim(-_lim, _lim)
    ax.annotate("", xy=(alen, 0), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color="#16A34A", lw=2.0,
                                shrinkA=0, shrinkB=0),
                zorder=6)
    ax.annotate("", xy=(0, alen), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color="#2563EB", lw=2.0,
                                shrinkA=0, shrinkB=0),
                zorder=6)
    ax.text(alen * 1.02, 0, "t2", fontsize=7, color="#15803D",
            weight="bold", va="center", ha="left", zorder=6)
    ax.text(0, alen * 1.02, "t3", fontsize=7, color="#1D4ED8",
            weight="bold", va="bottom", ha="center", zorder=6)
    # Legend thép: căn giữa-trên, ngay trên đỉnh axes (cao hơn nhãn t3)
    if legend_handles:
        leg = ax.legend(handles=legend_handles, loc="upper center",
                        bbox_to_anchor=(0.5, legend_y),
                        ncol=len(legend_handles),
                        frameon=False, fontsize=8)
        for txt in leg.get_texts():
            txt.set_fontweight("bold")
    # Dim t3 (dưới đáy), t2 (bên trái)
    if show_dims and sec.kind == "rect":
        doff = max(cx, cy) * 0.10
        # đường dim mảnh
        ax.plot([-cx/2, cx/2], [-cy/2 - doff*0.55]*2, color="black", lw=0.8)
        for xx in (-cx/2, cx/2):
            ax.plot([xx, xx], [-cy/2 - doff*0.75, -cy/2 - doff*0.35],
                    color="black", lw=0.8)
        ax.text(0, -cy/2 - doff, f"t3 = {cx:.0f}", fontsize=8,
                weight="bold", ha="center", va="top")
        ax.plot([-cx/2 - doff*0.55]*2, [-cy/2, cy/2], color="black", lw=0.8)
        for yy in (-cy/2, cy/2):
            ax.plot([-cx/2 - doff*0.75, -cx/2 - doff*0.35], [yy, yy],
                    color="black", lw=0.8)
        ax.text(-cx/2 - doff, 0, f"t2 = {cy:.0f}", fontsize=8,
                weight="bold", ha="right", va="center", rotation=90)
    elif show_dims and sec.kind == "circle":
        # Hình tròn: ghi đường kính D; mặt cắt DXF (poly) không ghi
        # vì kích thước bao không có ý nghĩa
        ax.text(0, -cy/2 - max(cx, cy)*0.10, f"D = {cx:.0f}", fontsize=8,
                weight="bold", ha="center", va="top")
    # Thẻ thống kê bên dưới
    if show_stats and sec.rebars:
        from collections import Counter
        cnt = Counter((r.layer, r.dia) for r in sec.rebars)
        compo = " + ".join(
            f"{cnt[k]}d{k[1]:.0f}" for k in sorted(cnt, key=lambda k: (k[0], -k[1])))
        n = len(sec.rebars)
        mu = sec.reinforcement_ratio * 100.0
        stat1 = (f"{n} thanh ({compo})    As = {sec.steel_area:.0f} mm²"
                 f"    μ = {mu:.2f}%")
        try:
            from .sections import clear_spacing as _cs
            ccx, ccy = _cs(sec)
            dias = sorted(set(r.dia for r in sec.rebars))
            d_avg = sum(dias) / len(dias)
            if math.isfinite(ccx):
                stat2 = (f"Khoảng hở: t3 = {ccx:.1f}, t2 = {ccy:.1f} mm"
                         f"    Tim: t3 = {ccx + d_avg:.1f}, t2 = {ccy + d_avg:.1f} mm")
            else:
                stat2 = ""
        except Exception:
            stat2 = ""
        txt = stat1 + ("\n" + stat2 if stat2 else "")
        ax.text(0.5, -0.20, txt, transform=ax.transAxes, fontsize=7.5,
                ha="center", va="top", color="#1F2937",
                bbox=dict(boxstyle="round,pad=0.4", fc="#F9FAFB",
                          ec="#E5E7EB"))
    # Giới hạn trục + tỉ lệ (đủ chỗ cho trục t2/t3 vượt ra)
    m = max(cx, cy) * 0.30
    ax.set_xlim(-cx/2 - m, cx/2 + m)
    # Top đủ chứa legend thép ở alen*1.25 = max*0.775
    ax.set_ylim(-cy/2 - m, max(cy/2 + m * 1.35, max(cx, cy) * 0.85))
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)


def section_image(sec, width_in=3.2, dpi=300, small=False,
                  show_stats=True, legend_y: float = 1.08,
                  dot_scale: float = 0.8) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if small:
        width_in, dpi = 1.3, 200
    # Figure theo đúng tỉ lệ t2/t3 (cao = rộng × cy/cx)
    ratio = sec.cy / sec.cx if sec.cx > 0 else 1.0
    fig, ax = plt.subplots(figsize=(width_in, width_in * ratio))
    draw_section_ax(ax, sec, show_stats=show_stats, legend_y=legend_y,
                    dot_scale=dot_scale)
    ax.grid(True, color="#E5E7EB", linestyle="--", linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    for sp in ax.spines.values():
        sp.set_visible(False)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                pad_inches=0.1)
    plt.close(fig)
    return buf.getvalue()


def compression_zone_image(sec, N_kN: float, M2_kNm: float, M3_kNm: float,
                           na_info=None, width_in=3.5, dpi=300,
                           show_compression: bool = True) -> bytes:
    """Vẽ hình vùng nén (giống app) trả về PNG bytes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .pdf_export import draw_compression_zone_ax
    # Tỉ lệ theo tiết diện để không bị đè chữ
    _cx = getattr(sec, "cx", 500) or 500
    _cy = getattr(sec, "cy", 750) or 750
    _ratio = _cy / _cx if _cx > 0 else 1.0
    fig = plt.Figure(figsize=(width_in, width_in * _ratio), dpi=dpi)
    ax = fig.add_subplot(111)
    draw_compression_zone_ax(ax, sec, N_kN, M2_kNm, M3_kNm,
                             Nmax_kN=abs(N_kN)*2 if N_kN else None,
                             na_info=na_info,
                             show_compression=show_compression)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor="white", pad_inches=0.15)
    plt.close(fig)
    return buf.getvalue()


def _radial_limit(curve, N_load: float, M_load: float):
    """Giao của tia từ gốc qua (N_load, M_load) với đường cong [(N, M)]."""
    best = None
    best_t = 0.0
    for i in range(len(curve) - 1):
        n1, m1 = curve[i]
        n2, m2 = curve[i + 1]
        a11, a12 = N_load, -(n2 - n1)
        a21, a22 = M_load, -(m2 - m1)
        det = a11 * a22 - a12 * a21
        if abs(det) < 1e-12:
            continue
        t = (n1 * a22 - m1 * a12) / det
        s = (a11 * m1 - a21 * n1) / det
        if t > 0 and 0 <= s <= 1 and t > best_t:
            best_t = t
            best = (t * N_load, t * M_load)
    return best


def interaction_image(sec, inp, res, width_in=6.0, dpi=300, small=False,
                      right_half=False, left_half=False) -> bytes:
    """Biểu đồ tương tác N-M tại góc uốn xiên α.
    right_half=True: chỉ hiện nửa phải (M>=0) có đường nội lực.
    left_half=True: chỉ hiện nửa trái (M<=0) có đường nội lực."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import math
    if small:
        width_in, dpi = 4.0, 200
    fig, ax = plt.subplots(figsize=(width_in, width_in))
    from .interaction import FiberSection, uniaxial_curve_fs
    fs = FiberSection(sec)
    alpha_deg = math.degrees(math.atan2(res.Mx_star, res.My_star))
    cv = uniaxial_curve_fs(fs, alpha_deg, inp.concrete_model)
    GREEN, RED, ORANGE = "#059669", "#DC2626", "#F97316"
    BLUE_DASH = "#3B82F6"
    m_pos = [p[1] for p in cv]
    n_pos = [p[0] for p in cv]
    m_neg = [-p[1] for p in cv]
    ax.plot(m_pos, n_pos, color=GREEN, lw=2.0, zorder=3,
            label="Đường bao N-Mα")
    ax.plot(m_neg, n_pos, color=GREEN, lw=2.0, zorder=3)
    ax.fill_betweenx(n_pos, 0, m_pos, color=GREEN, alpha=0.08, zorder=1)
    ax.fill_betweenx(n_pos, m_neg, 0, color=GREEN, alpha=0.08, zorder=1)
    Ma = math.hypot(res.Mx_star, res.My_star)
    Mb = math.hypot(res.Bx, res.By)
    lim = (res.BN, Mb)
    ax.plot([0, lim[1] * 1.18], [0, lim[0] * 1.18], color=RED,
            ls="--", lw=1.5, dashes=(4, 3), zorder=4,
            label="Tia tải O-A-B")
    ax.plot([Ma, Ma], [0, res.N], color=BLUE_DASH, ls="--",
            lw=1.2, dashes=(4, 3), alpha=0.8, zorder=2)
    ax.plot([0, Ma], [res.N, res.N], color=BLUE_DASH, ls="--",
            lw=1.2, dashes=(4, 3), alpha=0.8, zorder=2)
    ax.scatter([lim[1]], [lim[0]], c=ORANGE, marker="D", s=70, zorder=5,
               edgecolors="white", linewidths=1.2)
    ax.scatter([Ma], [res.N], c=GREEN, s=70, zorder=6,
               edgecolors="white", linewidths=1.2)
    ax.text(Ma, res.N, "  A", fontsize=9, color=GREEN,
            weight="bold", va="center", zorder=7)
    ax.text(lim[1], lim[0], "  B", fontsize=9, color=ORANGE,
            weight="bold", va="center", zorder=7)
    ax.set_xlabel("Mα (kN×m)", fontsize=10, fontweight="bold")
    ax.set_ylabel("N (kN)", fontsize=10, fontweight="bold")
    ax.tick_params(labelsize=8)
    # Bỏ textbox α trong hình (đã có trên tiêu đề) — theo yêu cầu user 2026-10-16
    # Chỉ hiện N >= 0 (ẩn vùng chịu kéo)
    ax.set_ylim(bottom=0)
    if right_half:
        # Chỉ hiện nửa phải (M >= 0)
        ax.set_xlim(left=0)
    elif left_half:
        # Chỉ hiện nửa trái (M <= 0)
        ax.set_xlim(right=0)
    # Legend 4 mục như tab Kết quả (dùng Line2D custom)
    from matplotlib.lines import Line2D as _L2D
    _leg = [
        _L2D([0], [0], color=GREEN, lw=2.2, label="Đường bao N-Mα"),
        _L2D([0], [0], color=RED, lw=1.5, ls="--", dashes=(4, 3),
             label="Tia tải O-A-B"),
        _L2D([0], [0], marker="o", color="w", markerfacecolor=GREEN,
             markersize=8, markeredgecolor="white", label="Điểm tải A"),
        _L2D([0], [0], marker="D", color="w", markerfacecolor=ORANGE,
             markersize=7, markeredgecolor="white", label="Điểm giới hạn B"),
    ]
    ax.legend(handles=_leg, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.18), ncol=2, frameon=False)
    ax.grid(True, color="#E5E7EB", linestyle="--", linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    for _sp in ("top", "right"):
        ax.spines[_sp].set_visible(False)
    for _sp in ("left", "bottom"):
        ax.spines[_sp].set_color("#9CA3AF")
    fig.subplots_adjust(bottom=0.25, top=0.93, left=0.12, right=0.95)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    return buf.getvalue()


def m2m3_image(sec, inp, res, width_in=4.0, dpi=300) -> bytes:
    """Biểu đồ tương tác M2-M3 tại N."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(width_in, width_in))
    from .interaction import BiaxialCapacity
    cap = BiaxialCapacity(sec, model=inp.concrete_model, n_angles=24)
    pts = cap.mx_my_curve(res.N)
    BLUE, GREEN, RED, ORANGE = "#2563EB", "#059669", "#DC2626", "#F97316"
    xs = [p[0] for p in pts] + [pts[0][0]]
    ys = [p[1] for p in pts] + [pts[0][1]]
    ax.plot(xs, ys, color=BLUE, lw=2.2, zorder=3)
    ax.fill(xs, ys, color=BLUE, alpha=0.08, zorder=1)
    ax.plot([0, res.Bx * 1.18], [0, res.By * 1.18], color=RED,
            ls="--", lw=1.5, dashes=(4, 3), zorder=4)
    ax.scatter([res.Bx], [res.By], c=ORANGE, marker="D", s=70, zorder=5,
               edgecolors="white", linewidths=1.2)
    ax.scatter([res.Mx_star], [res.My_star], c=GREEN, s=70, zorder=6,
               edgecolors="white", linewidths=1.2)
    ax.text(res.Mx_star, res.My_star, "  A", fontsize=9, color=GREEN,
            weight="bold", va="center", zorder=7)
    ax.text(res.Bx, res.By, "  B", fontsize=9, color=ORANGE,
            weight="bold", va="center", zorder=7)
    ax.axhline(0, color="#6B7280", linewidth=1.0, zorder=2)
    ax.axvline(0, color="#6B7280", linewidth=1.0, zorder=2)
    ax.set_xlabel("M2 (kN×m)", fontsize=10, fontweight="bold")
    ax.set_ylabel("M3 (kN×m)", fontsize=10, fontweight="bold")
    ax.tick_params(labelsize=8)
    from matplotlib.lines import Line2D as _L2D2
    _leg2 = [
        _L2D2([0], [0], color=BLUE, lw=2.2, label="Đường bao M2-M3"),
        _L2D2([0], [0], color=RED, lw=1.5, ls="--", dashes=(4, 3),
              label="Tia tải O-A-B"),
        _L2D2([0], [0], marker="o", color="w", markerfacecolor=GREEN,
              markersize=8, markeredgecolor="white", label="Điểm tải A"),
        _L2D2([0], [0], marker="D", color="w", markerfacecolor=ORANGE,
              markersize=7, markeredgecolor="white", label="Điểm giới hạn B"),
    ]
    ax.legend(handles=_leg2, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.22), ncol=2, frameon=False)
    ax.grid(True, color="#E5E7EB", linestyle="--", linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    ax.set_aspect("equal", adjustable="datalim")
    for _sp in ("top", "right"):
        ax.spines[_sp].set_visible(False)
    for _sp in ("left", "bottom"):
        ax.spines[_sp].set_color("#9CA3AF")
    fig.subplots_adjust(bottom=0.25, top=0.93, left=0.12, right=0.95)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    return buf.getvalue()


# --- Xuất PDF ---
import re as _re
def draw_compression_zone_ax(ax, sec, N_kN: float, M2_kNm: float, M3_kNm: float,
                             Nmax_kN: float = None, title: str = None,
                             na_info: dict = None, show_compression: bool = True):
    """Vẽ mặt cắt kiểu VietconSoft (giống tab Kết quả) + tô vùng nén.

    na_info: dict từ neutral_axis_at_N (đường trung hòa chính xác từ fiber model).
             Nếu None, dùng ước lượng đơn giản theo hướng mô men.
    show_compression: False → chỉ vẽ mặt cắt trơn (KHÔNG tô vùng nén xanh,
             KHÔNG vẽ đường trung hòa đỏ) — dùng cho live preview trước khi CHECK.
             Mọi chi tiết khác (legend, nhãn, mũi tên, màu sắc, font) GIỐNG HỆT
             như khi show_compression=True.
    """
    import math
    import matplotlib.patches as mpatches
    from matplotlib.patches import Polygon as MplPolygon
    from matplotlib.lines import Line2D
    import numpy as np
    
    ax.set_aspect('equal', adjustable='box')
    cx, cy = sec.cx, sec.cy
    DIA_COLORS = ["#DC2626", "#9333EA", "#EA580C", "#0891B2",
                  "#BE123C", "#CA8A04", "#0F766E", "#4D7C0F"]
    L2_COLOR = "#F59E0B"
    
    ax.set_axisbelow(True)
    ax.grid(True, color="#E8EDF3", linewidth=0.7)
    
    sec_poly = []
    if sec.kind == "rect":
        ax.add_patch(mpatches.Rectangle(
            (-cx/2, -cy/2), cx, cy, fill=True, facecolor="#F4F7FB",
            edgecolor="black", lw=2.0, zorder=2))
        sec_poly = [(-cx/2, -cy/2), (cx/2, -cy/2), (cx/2, cy/2), (-cx/2, cy/2)]
    elif sec.kind == "poly" and getattr(sec, "poly_verts", None):
        for verts in sec.poly_verts:
            ax.add_patch(MplPolygon(verts, closed=True, fill=True,
                                    facecolor="#F4F7FB", edgecolor="black",
                                    lw=2.0, zorder=2))
        sec_poly = list(sec.poly_verts[0]) if sec.poly_verts else []
    else:
        ax.add_patch(mpatches.Circle(
            (0, 0), cx/2, fill=True, facecolor="#F4F7FB",
            edgecolor="black", lw=2.0, zorder=2))
        _th = np.linspace(0, 2*np.pi, 64)
        sec_poly = [(cx/2*np.cos(t), cx/2*np.sin(t)) for t in _th]
    
    # --- Xác định đường trung hòa và phía nén ---
    # Nếu có na_info (chính xác từ fiber model), dùng nó; nếu không, ước lượng
    _use_exact = (na_info is not None and na_info.get('found') and
                  na_info.get('yp_na') is not None)
    if _use_exact:
        _na_st = na_info['st']
        _na_ct = na_info['ct']
        _na_yp = na_info['yp_na']
        # Hàm giá trị: val = -x*st + y*ct - yp_na; nén khi val > 0
        def _naval(_x, _y):
            return -_x*_na_st + _y*_na_ct - _na_yp
    else:
        _Mstar = math.hypot(M2_kNm, M3_kNm)
        _alpha = math.atan2(M2_kNm, M3_kNm) if _Mstar > 1e-9 else 0.0
        _dx = math.sin(_alpha)
        _dy = math.cos(_alpha)
        if Nmax_kN and Nmax_kN > 1e-9:
            _c_ratio = min(1.0, max(0.0, abs(N_kN) / Nmax_kN))
        else:
            _c_ratio = 0.5
        _m_factor = min(1.0, _Mstar / 2000.0) if _Mstar > 0 else 0
        _c_ratio = _c_ratio * (1 - 0.3*_m_factor) + 0.15*_m_factor
        _corners_tmp = list(sec_poly) if sec_poly else []
        if _corners_tmp:
            _xs = [p[0] for p in _corners_tmp]
            _ys = [p[1] for p in _corners_tmp]
            _diag = math.hypot(max(_xs)-min(_xs), max(_ys)-min(_ys))
        else:
            _diag = 1.0
        _d = (0.5 - _c_ratio) * _diag * 0.7
        _nx, _ny = -_dx, -_dy
        _px, _py = _d * _nx, _d * _ny
        _threshold = _px * _nx + _py * _ny
        def _naval(_x, _y):
            return _x*_nx + _y*_ny - _threshold
    
    if show_compression and sec_poly and len(sec_poly) >= 3:
        # Cắt đa giác tiết diện theo nửa mặt phẳng nén (Sutherland–Hodgman):
        # giữ nguyên thứ tự đỉnh nên đúng cả với tiết diện LÕM (chữ L, T...)
        # (cách cũ sắp xếp theo góc cực chỉ đúng với đa giác lồi).
        _src = list(sec_poly)
        _poly_pts = []
        for _i in range(len(_src)):
            _cur = _src[_i]
            _prv = _src[_i - 1]
            _vc = _naval(_cur[0], _cur[1])
            _vp = _naval(_prv[0], _prv[1])
            _cur_in = _vc >= -1e-9
            _prv_in = _vp >= -1e-9
            if _cur_in != _prv_in:
                _t = abs(_vp) / (abs(_vp) + abs(_vc))
                _poly_pts.append((_prv[0] + _t * (_cur[0] - _prv[0]),
                                  _prv[1] + _t * (_cur[1] - _prv[1])))
            if _cur_in:
                _poly_pts.append(_cur)
        if len(_poly_pts) >= 3:
            ax.add_patch(MplPolygon(_poly_pts, closed=True, fill=True,
                                    facecolor="#BFDBFE", edgecolor="#2563EB",
                                    lw=1.5, zorder=3, alpha=0.7))
        # Đường trung hòa: nối các cặp giao điểm liên tiếp dọc theo đường
        # trung hòa (đúng cả khi đường cắt tiết diện lõm tạo 4 giao điểm)
        _edges = [(sec_poly[i], sec_poly[(i + 1) % len(sec_poly)])
                  for i in range(len(sec_poly))]
        _intersects = []
        for (_x1, _y1), (_x2, _y2) in _edges:
            _v1 = _naval(_x1, _y1)
            _v2 = _naval(_x2, _y2)
            if _v1 * _v2 < 0:
                _t = abs(_v1) / (abs(_v1) + abs(_v2))
                _intersects.append((_x1 + _t * (_x2 - _x1),
                                    _y1 + _t * (_y2 - _y1)))
        if len(_intersects) >= 2:
            if _use_exact:
                _dxn, _dyn = _na_ct, _na_st
            else:
                _dxn, _dyn = -_ny, _nx
            _intersects.sort(key=lambda p: p[0] * _dxn + p[1] * _dyn)
            for _i in range(0, len(_intersects) - 1, 2):
                ax.plot([_intersects[_i][0], _intersects[_i + 1][0]],
                        [_intersects[_i][1], _intersects[_i + 1][1]],
                        '--', color='#DC2626', linewidth=1.5, zorder=4)
    
    groups = {}
    for r in sec.rebars:
        groups.setdefault((r.layer, r.dia), []).append(r)
    dias_l1 = sorted(set(d for (ly, d) in groups if ly == 1), reverse=True)
    dia_color = {d: DIA_COLORS[i % len(DIA_COLORS)] for i, d in enumerate(dias_l1)}
    legend_handles = []
    for (layer, dia) in sorted(groups, key=lambda k: (k[0], -k[1])):
        pts = groups[(layer, dia)]
        color = dia_color.get(dia, "#DC2626") if layer == 1 else L2_COLOR
        dot_s = (max(4.0, dia * 0.22)) ** 2
        ax.scatter([p.x * 0.96 for p in pts], [p.y * 0.96 for p in pts],
                   s=dot_s, c=color, zorder=5,
                   edgecolors="white", linewidths=0.8)
        legend_handles.append(Line2D(
            [0], [0], marker="o", color="none", markerfacecolor=color,
            markeredgecolor="white", markersize=max(4.0, dia * 0.22),
            label=f"D{dia:.0f}"))
    # Legend thép: bên phải khung
    if legend_handles:
        leg = ax.legend(handles=legend_handles, loc="center left",
                        bbox_to_anchor=(1.02, 0.5),
                        ncol=1,
                        frameon=True, fontsize=8,
                        facecolor="white", edgecolor="#D1D5DB")
        for txt in leg.get_texts():
            txt.set_fontweight("bold")
    
    alen = max(cx, cy) * 0.62
    # Mũi tên trục t2 (xanh lá, ngang), t3 (xanh dương, đứng) - vẽ trên cùng
    # Đặt giới hạn trục để mũi tên không bị cắt
    _lim = max(cx, cy) * 0.70
    ax.set_xlim(-_lim, _lim)
    ax.set_ylim(-_lim, _lim)
    ax.annotate("", xy=(alen, 0), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color="#16A34A", lw=2.0,
                                shrinkA=0, shrinkB=0),
                zorder=6)
    ax.annotate("", xy=(0, alen), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color="#2563EB", lw=2.0,
                                shrinkA=0, shrinkB=0),
                zorder=6)
    ax.text(alen * 1.02, 0, "t2", fontsize=8, color="#15803D",
            weight="bold", va="center", ha="left", zorder=6)
    ax.text(0, alen * 1.02, "t3", fontsize=8, color="#1D4ED8",
            weight="bold", va="bottom", ha="center", zorder=6)
    
    # Không set title bên trong (đã có tiêu đề card bên ngoài)
    # Nhãn trục thành kích thước t2/t3
    if sec.kind == "rect":
        # Cạnh t2 là đứng (cy), cạnh t3 là ngang (cx) theo quy ước app
        # Đặt sát mép mặt cắt (dùng text thay vì xlabel/ylabel)
        ax.text(0, -cy/2 - max(cx,cy)*0.04, f"t3 = {cx:.0f} mm",
                fontsize=8, weight="bold", ha="center", va="top")
        ax.text(-cx/2 - max(cx,cy)*0.04, 0, f"t2 = {cy:.0f} mm",
                fontsize=8, weight="bold", ha="right", va="center",
                rotation=90)
    elif sec.kind == "circle":
        ax.set_xlabel(f"D = {cx:.0f} mm", fontsize=8, weight="bold")
        ax.set_ylabel(f"D = {cx:.0f} mm", fontsize=8, weight="bold")
    else:
        ax.set_xlabel("Trục 2 (mm)", fontsize=8)
        ax.set_ylabel("Trục 3 (mm)", fontsize=8)
    ax.tick_params(labelsize=7)

    # Đơn giản hóa cho PDF: bỏ box, số quanh box; chỉ giữ mặt cắt, mũi tên, tên trục, kích thước, ghi chú thép
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
def _export_summary_pdf_impl(sec, inp, res, filepath: str, case_info=None,
                       sec_img_path=None, shear_info=None,
                       show_compression: bool = True, _level: int = 0):
    """Xuất PDF Kết quả tính toán TCVN 5574:2018 (1 trang A4).

    Layout 2 cột: trái = các bảng thông số, phải = hình vùng nén + 2 biểu đồ.
    Dưới cùng: bảng kiểm tra thép đai full-width.

    Hình mặt cắt là hình VÙNG NÉN (đường trung hòa chính xác từ fiber model),
    giống như hiển thị trên app.
    """
    import math as _m
    import io as _io
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Image, Table, TableStyle)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from collections import Counter
    import os as _os


    # --- Ep 1 trang: muc nen layout theo bac (wrapper chon muc thap
    # nhat cho ra dung 1 trang; muc 0 = le/padding goc, chi thu hep dan).
    _LV = max(0, min(3, int(_level)))
    _PAD = (2.0, 1.2, 0.8, 0.6)[_LV]     # padding doc cac o bang
    _HPAD = (3.0, 2.2, 1.8, 1.5)[_LV]    # padding duoi tieu de section
    _LEAD = (9.0, 9.0, 8.5, 8.5)[_LV]    # leading dong chu 7pt
    _TSP = (8, 4, 3, 2)[_LV]             # spaceAfter tieu de chinh
    _CSP = (2.0, 1.5, 1.0, 1.0)[_LV]     # space quanh tieu de bieu do
    _ISP = (2, 1.5, 1, 1)[_LV]           # spacer giua cac hinh
    _MSP = (4, 3, 2, 2)[_LV]             # spacer truoc bang cat
    _MRG = (8, 8, 7, 6)[_LV]             # le tren/duoi (mm)
    _IW0 = (66.0, 66.0, 62.0, 56.0)[_LV]  # co hinh cot phai theo muc nen (mm)
    # Dan y moi (user chot): MOI hang trong dan y deu la hang bat buoc,
    # khong muc nen nao duoc bo hang nua -> _DROP rong o moi muc.
    _DROP = set()

    # Font
    FN, FNB = "Helvetica", "Helvetica-Bold"
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", _find_font()))
        FN = "DejaVu"
    except Exception:
        pass
    try:
        pdfmetrics.registerFont(TTFont("DejaVuB", _find_font_bold()))
        FNB = "DejaVuB"
    except Exception:
        pass

    # Styles — khớp mẫu Excel
    # --- Dung story theo bo tham so layout (goi lai khi gian trang;
    # chi padding/leading/khoang cach/co hinh thay doi, noi dung
    # chu va so lieu giu nguyen).
    def _mk(_PAD, _HPAD, _LEAD, _TSP, _CSP, _ISP, _MSP, _IW):

        st_title = ParagraphStyle("t", fontName=FNB, fontSize=14,
                                  alignment=TA_CENTER, spaceAfter=_TSP)
        st_sec = ParagraphStyle("sec", fontName=FNB, fontSize=9,
                                spaceBefore=5, spaceAfter=1,
                                textColor=HexColor("#111111"),
                                borderPadding=(0, 0, 2))
        st_cell = ParagraphStyle("c", fontName=FN, fontSize=7, leading=_LEAD)
        st_cell_b = ParagraphStyle("cb", fontName=FNB, fontSize=7, leading=_LEAD)
        st_hdr = ParagraphStyle("hdr", fontName=FNB, fontSize=7, leading=_LEAD,
                                 alignment=TA_CENTER)
        st_hdr_left = ParagraphStyle("hdr_left", parent=st_hdr, alignment=TA_LEFT)

        st_lbl = ParagraphStyle("lbl", parent=st_cell, alignment=TA_LEFT)
        st_val = ParagraphStyle("val", parent=st_cell, alignment=TA_RIGHT)
        st_val_b = ParagraphStyle("val_b", parent=st_cell_b, alignment=TA_RIGHT)
        st_sec_title = ParagraphStyle("sectitle", parent=st_cell_b, alignment=TA_LEFT)
        def _sec_table(title, rows):
            """Bảng 2 cột kiểu Excel: tiêu đề section + các dòng xen kẽ màu."""
            data = [[Paragraph(f"<b>{title}</b>", st_sec_title)]]
            for lbl, val in rows:
                if lbl in _DROP:
                    continue
                _vs = str(val)
                # Nếu giá trị có thẻ <b>, dùng style in đậm trực tiếp (tránh lỗi font <b>)
                if "<b>" in _vs:
                    _vs_clean = _vs.replace("<b>", "").replace("</b>", "")
                    data.append([Paragraph(lbl, st_lbl),
                                 Paragraph(_vs_clean, st_val_b)])
                else:
                    data.append([Paragraph(lbl, st_lbl),
                                 Paragraph(_vs, st_val)])
            # colWidths: nhãn 55mm, giá trị 35mm (đủ cho nhãn tiêu chuẩn
            # dài nhất "EC2 (EN 1992-1-1:2004)" nằm trọn 1 dòng)
            t = Table(data, colWidths=[55 * mm, 35 * mm], hAlign="LEFT")
            style = [
                ("SPAN", (0, 0), (1, 0)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), _PAD),
                ("BOTTOMPADDING", (0, 0), (-1, -1), _PAD),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                # Gạch dưới tiêu đề section
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, HexColor("#111111")),
                ("BOTTOMPADDING", (0, 0), (-1, 0), _HPAD),
            ]
            # Xen kẽ màu nền (trắng / xám nhạt) từ dòng 1
            for i in range(1, len(data)):
                if i % 2 == 0:
                    style.append(("BACKGROUND", (0, i), (-1, i),
                                  HexColor("#F2F2F2")))
            t.setStyle(TableStyle(style))
            return t

        def _img_from_bytes(png_bytes, w_mm):
            """Tạo Image ReportLab từ PNG bytes, giữ tỉ lệ gốc."""
            buf = _io.BytesIO(png_bytes)
            try:
                from PIL import Image as _PIL
                _pil = _PIL.open(buf)
                _pw, _ph = _pil.size
                buf.seek(0)
                h_mm = w_mm * _ph / _pw if _pw > 0 else w_mm
            except Exception:
                h_mm = w_mm
            return Image(buf, width=w_mm * mm, height=h_mm * mm)

        # ===== Chuẩn bị dữ liệu =====
        from .materials import CONCRETE_GRADES, STEEL_GRADES
        _cg = CONCRETE_GRADES.get(inp.concrete_grade)
        _sg = STEEL_GRADES.get(inp.steel_grade)
        _swg = STEEL_GRADES.get(inp.sw_steel_grade)

        _ck_name = ""
        try:
            _fn = getattr(inp, "_filename", "") or ""
            if _fn:
                _ck_name = _os.path.splitext(_os.path.basename(_fn))[0].upper()
        except Exception:
            pass
        if not _ck_name and case_info:
            _ck_name = str(case_info.get("name", "")).upper()

        _t3 = getattr(sec, "cx", inp.cx)
        _t2 = getattr(sec, "cy", inp.cy)
        _cnt = Counter(r.dia for r in sec.rebars)
        _parts = [f"{_cnt[d]}-d{d:.0f}" for d in sorted(_cnt, reverse=True)]
        _mu = getattr(sec, "reinforcement_ratio", 0) or 0

        _story_txt, _label_txt, _combo_txt, _station_txt = "—", "—", "—", "—"
        if case_info:
            _story_txt = str(case_info.get("story", "—"))
            _label_txt = str(case_info.get("label", case_info.get("column", "—")))
            _combo_txt = str(case_info.get("case", case_info.get("combo", "—")))
            _st = case_info.get("station", "—")
            _station_txt = f"{_st:.2f}" if isinstance(_st, (int, float)) else str(_st)
        _vpos = f"[{_story_txt}]-[{_label_txt}]-[{_station_txt}]" if _story_txt != "—" else "—"

        _alpha = _m.degrees(_m.atan2(res.Mx_star, res.My_star)) \
            if abs(res.Mx_star) + abs(res.My_star) > 1e-9 else 0.0
        _ok_txt = "<b>ĐẠT</b>" if res.ok else "<b>KHÔNG ĐẠT</b>"
        # He so chieu dai tinh toan psi: doc tu L0 (engine da tinh) / L goc
        _psi2 = (res.L0x / inp.Lx) if inp.Lx else 0.0
        _psi3 = (res.L0y / inp.Ly) if inp.Ly else 0.0

        # ===== Cột trái: các bảng (dan y user chot 2026-10-21) =====
        left_flow = []

        # THÔNG TIN CHUNG
        left_flow.append(_sec_table("THÔNG TIN CHUNG", [
            ("Tiêu chuẩn", "TCVN 5574:2018"),
            ("Cấu kiện", _ck_name or "—"),
        ]))

        # VẬT LIỆU (Es chi 1 hang o cuoi khoi)
        _mat_rows = []
        if _cg:
            _mat_rows += [
                ("Bê tông", inp.concrete_grade),
                ("Cường độ chịu nén, R<sub>b</sub>", f"{_fm(_cg.Rb)} MPa"),
                ("Mô đun đàn hồi, E<sub>b</sub>", f"{_fm(_cg.Eb)} MPa"),
            ]
        if _sg:
            _mat_rows += [
                ("Cốt thép dọc", inp.steel_grade),
                ("Cường độ chịu kéo, R<sub>s</sub>", f"{_fm(_sg.Rs)} MPa"),
            ]
        if _swg:
            _mat_rows += [
                ("Cốt thép đai", inp.sw_steel_grade),
                ("Cường độ chịu cắt, R<sub>sw</sub>", f"{_fm(_swg.Rsw)} MPa"),
                ("Mô đun đàn hồi, E<sub>s</sub>", f"{_fm(_swg.Es)} MPa"),
            ]
        elif _sg:
            _mat_rows.append(
                ("Mô đun đàn hồi, E<sub>s</sub>", f"{_fm(_sg.Es)} MPa"))
        left_flow.append(_sec_table("VẬT LIỆU", _mat_rows))

        # TIẾT DIỆN (theo loai tiet dien)
        _kind = getattr(sec, "kind", None) or getattr(inp, "section_type", "rect")
        if _kind == "circle":
            _sec_rows = [("Hình tròn, đường kính d", f"{_t3:.0f} mm")]
        elif _kind == "poly":
            _sec_rows = [("Diện tích bê tông, A<sub>c</sub>",
                          f"{sec.gross_area:.0f} mm²")]
        else:
            _sec_rows = [("Hình chữ nhật, t2 × t3",
                          f"{_t2:.0f} × {_t3:.0f} mm")]
        _sec_rows.append(("Lớp bê tông bảo vệ cốt thép dọc, c",
                          f"{inp.cover:.0f} mm"))
        left_flow.append(_sec_table("TIẾT DIỆN", _sec_rows))

        # BỐ TRÍ CỐT THÉP DỌC
        left_flow.append(_sec_table("BỐ TRÍ CỐT THÉP DỌC", [
            ("Số lượng thép", " + ".join(_parts)),
            ("Hàm lượng thép dọc, μ", f"{_mu*100:.2f}%"),
        ]))

        # NỘI LỰC KIỂM TRA (M2, M3 gop 1 hang; V2, V3 o bang cat)
        left_flow.append(_sec_table("NỘI LỰC KIỂM TRA", [
            ("Vị trí cột", _vpos),
            ("Tổ hợp tính toán", _combo_txt),
            ("Lực dọc tính toán, N", f"{res.N:.1f} kN"),
            ("Mômen ban đầu, M2, M3", f"{res.Mx:.1f} / {res.My:.1f} kNm"),
        ]))

        # CHIỀU DÀI TÍNH TOÁN & HIỆU ỨNG UỐN DỌC (doc tu CheckResult —
        # engine da tinh 1 lan: L0, lambda, e0, Ncr, eta; psi = L0/L)
        left_flow.append(_sec_table(
            "CHIỀU DÀI TÍNH TOÁN &amp; HIỆU ỨNG UỐN DỌC", [
                ("Chiều dài cột, L2, L3",
                 f"{_fm_m(inp.Lx)} / {_fm_m(inp.Ly)} m"),
                ("Hệ số chiều dài tính toán, ψ2, ψ3",
                 f"{_psi2:.2f} / {_psi3:.2f}"),
                ("Chiều dài tính toán, L02, L03",
                 f"{_fm_m(res.L0x)} / {_fm_m(res.L0y)} m"),
                ("Độ mảnh cột, λ2, λ3",
                 f"{res.lambda_x:.1f} / {res.lambda_y:.1f}"),
                ("Độ lệch tâm ban đầu, e02, e03",
                 f"{res.e0x:.1f} / {res.e0y:.1f} mm"),
                ("Lực tới hạn Euler, Ncr,2, Ncr,3",
                 f"{res.Ncrx:.1f} / {res.Ncry:.1f} kN"),
                ("Hệ số uốn dọc, η2, η3",
                 f"{res.etax:.3f} / {res.etay:.3f}"),
            ]))

        # KẾT QUẢ KIỂM TRA KHẢ NĂNG CHỊU LỰC
        _Mb = _m.hypot(res.Bx, res.By)
        _Ma = _m.hypot(res.Mx_star, res.My_star)
        left_flow.append(_sec_table("KẾT QUẢ KIỂM TRA KHẢ NĂNG CHỊU LỰC", [
            ("Lực dọc tính toán, N", f"{res.N:.1f} kN"),
            ("Mômen sau uốn dọc, M2*, M3*",
             f"{res.Mx_star:.1f} / {res.My_star:.1f} kNm"),
            (f"Mômen tổng kiểm tra, Mα (α = {_alpha:.1f}°)",
             f"{_Ma:.1f} kNm"),
            ("Lực dọc giới hạn, Nu", f"{res.BN:.1f} kN"),
            ("Mômen giới hạn, Mα,u", f"{_Mb:.1f} kNm"),
            ("Tỉ số sử dụng khả năng chịu lực, D/C (FS)",
             f"{res.dc:.3f} ({res.fs:.2f})"),
            ("Kết luận", _ok_txt),
        ]))

        # ===== Cột phải: hình mặt cắt + 2 biểu đồ (căn giữa) =====
        def _centered_img(png_bytes, w_mm):
            """Bọc Image trong Table 1 ô căn giữa theo chiều ngang."""
            _im = _img_from_bytes(png_bytes, w_mm)
            _t = Table([[_im]], colWidths=[90 * mm], hAlign="CENTER")
            _t.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            return _t

        st_chart_title = ParagraphStyle("ct", parent=st_cell_b, alignment=TA_CENTER,
                                          fontSize=8, spaceBefore=_CSP, spaceAfter=_CSP)
        _blkA, _blkB, _blkC = [], [], []
        try:
            # Hình VÙNG NÉN (giống app) - đường trung hòa chính xác từ fiber model
            _cz_na = None
            try:
                from .interaction import FiberSection, neutral_axis_at_N
                _cz_fs = FiberSection(sec)
                _cz_BN = getattr(res, "BN", inp.N)
                _cz_Bx = getattr(res, "Bx", 0)
                _cz_By = getattr(res, "By", 0)
                _cz_alpha = _m.degrees(_m.atan2(_cz_Bx, _cz_By)) \
                    if abs(_cz_Bx) + abs(_cz_By) > 1e-9 else 0.0
                _cz_na = neutral_axis_at_N(
                    _cz_fs, _cz_BN, _cz_alpha,
                    getattr(inp, "concrete_model", "3line"))
            except Exception:
                _cz_na = None
            _sec_png = compression_zone_image(
                sec, getattr(res, "BN", inp.N),
                getattr(res, "Bx", 0), getattr(res, "By", 0),
                na_info=_cz_na, show_compression=show_compression)
            _blkA.append(_centered_img(_sec_png, _IW))
            # Biểu đồ N-Mα (có tiêu đề như app, chỉ hiện nửa phải có tải)
            _nm_png = interaction_image(sec, inp, res, width_in=3.2, dpi=150,
                                        small=True, right_half=True)
            _blkB.append(Paragraph(
                f"<b>Biểu đồ tương tác N-Mα</b> (α = {_alpha:.1f}°)",
                st_chart_title))
            _blkB.append(_centered_img(_nm_png, _IW))
            # Biểu đồ M2-M3 (có tiêu đề như app)
            _m2m3_png = m2m3_image(sec, inp, res, width_in=3.2, dpi=150)
            if isinstance(_m2m3_png, bytes):
                _blkC.append(Paragraph(
                    f"<b>Mặt cắt M2-M3</b> (N = {res.N:+.1f} kN)",
                    st_chart_title))
                _blkC.append(_centered_img(_m2m3_png, _IW))
        except Exception as e:
            _blkA = [Paragraph(f"(Không vẽ được hình: {e})", st_cell)]
            _blkB, _blkC = [], []
        # --- Neo 3 khoi hinh cot phai: mat cat CAN TREN, M2-M3 CAN
        # DUOI, N-M CAN GIUA: phan chieu cao cot phai con thieu so
        # voi cot trai chia deu vao cac spacer giua cac khoi.
        def _hh(_fl):
            _t = 0.0
            for _f in _fl:
                _w2, _h2 = _f.wrap(90 * mm, 10000)
                _t += _h2
                try:
                    _t += _f.getSpaceBefore() + _f.getSpaceAfter()
                except Exception:
                    pass
            return _t
        _blocks = [_b for _b in (_blkA, _blkB, _blkC) if _b]
        _ngaps = max(0, len(_blocks) - 1)
        _extra = 0.0
        if _ngaps:
            _resid = (_hh(left_flow)
                      - sum(_hh(_b) for _b in _blocks)
                      - _ISP * _ngaps)
            _extra = max(0.0, _resid) / _ngaps
        right_flow = []
        for _i, _b in enumerate(_blocks):
            if _i:
                right_flow.append(Spacer(1, _ISP + _extra))
            right_flow.extend(_b)


        # ===== Bảng 2 cột chính =====
        # Khối trái 90mm (nhãn 55mm + giá trị 35mm), hình 90mm
        main_data = [[left_flow, right_flow]]
        t_main = Table(main_data, colWidths=[90 * mm, 90 * mm], hAlign="CENTER")
        t_main.setStyle(TableStyle([
            ("VALIGN", (0, 0), (0, 0), "TOP"),
            ("VALIGN", (1, 0), (1, 0), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        story = []
        story.append(Paragraph(
            "KIỂM TRA KHẢ NĂNG CHỊU LỰC CỘT BÊ TÔNG CỐT THÉP", st_title))
        story.append(t_main)
        story.append(Spacer(1, _MSP))

        # ===== KIỂM TRA THÉP ĐAI (full width, giữ ở trang 1) =====
        # Dùng KeepTogether để không bị tách trang
        from reportlab.platypus import KeepTogether
        _sw_story = []
        try:
            # NGUYÊN TẮC "tính 1 lần": đọc shear_cols đã tính bởi
            # _tcvn_calculate_full (GUI truyền qua shear_info). Nếu thiếu
            # (gọi trực tiếp không qua GUI) thì tính bằng ĐÚNG hàm dùng chung
            # compute_shear_cols — KHÔNG viết công thức riêng ở đây.
            _cols = shear_info if isinstance(shear_info, dict) else None
            if not (_cols and "2" in _cols and "3" in _cols):
                from .stirrup import compute_shear_cols
                _cols = compute_shear_cols(inp, sec)
            _r2, _r3 = _cols["2"], _cols["3"]
            _sw_data = [
                [Paragraph("<b>KIỂM TRA KHẢ NĂNG CHỊU CẮT</b>", st_hdr_left),
                 Paragraph("<b>Phương V2</b>", st_hdr),
                 Paragraph("<b>Phương V3</b>", st_hdr)],
            ]
            _sw_rows = [
                ("Thép đai bố trí", _r2['sw_txt'], _r3['sw_txt']),
                ("Lực cắt tính toán, Q",
                 f"{_r2['Q']:.1f} kN", f"{_r3['Q']:.1f} kN"),
                ("Kích thước tiết diện, b × h<sub>0</sub>",
                 f"{_r2['b']:.0f} × {_r2['h0']:.0f} mm",
                 f"{_r3['b']:.0f} × {_r3['h0']:.0f} mm"),
                ("A<sub>sw</sub> = n × φ",
                 f"{_r2['Asw']:.0f} mm²", f"{_r3['Asw']:.0f} mm²"),
                ("q<sub>sw</sub> = R<sub>sw</sub> × A<sub>sw</sub>/s",
                 f"{_r2['qsw']:.1f} N/mm", f"{_r3['qsw']:.1f} N/mm"),
                ("Hệ số φ<sub>n</sub> (8.1.3.3.2)",
                 f"{_r2['sh'].phi_n:.3f}", f"{_r3['sh'].phi_n:.3f}"),
                ("Điều kiện (96): q<sub>sw</sub> ≥ 0.25×R<sub>bt</sub>×b",
                 "— (không có đai)" if _r2['sh'].qb_mode == "NONE" else
                 ("Đạt" if _r2['sh'].cond96_ok else "Không đạt → Q<sub>b</sub> theo CT (97)"),
                 "— (không có đai)" if _r3['sh'].qb_mode == "NONE" else
                 ("Đạt" if _r3['sh'].cond96_ok else "Không đạt → Q<sub>b</sub> theo CT (97)")),
                # Hàng s_max + Điều kiện (98): KHÔNG hiển thị ở bản tóm tắt
                # (theo yêu cầu trình bày) — engine vẫn kiểm tra (98) như cũ,
                # Q_sw của nhóm đai vi phạm vẫn bị loại trong số liệu phía dưới.
                ("Độ bền trên dải nén xiên Q ≤ φ<sub>n</sub>×0.3×R<sub>b</sub>×b×h<sub>0</sub>",
                 f"{_r2['sh'].Qcap1:.1f} kN", f"{_r3['sh'].Qcap1:.1f} kN"),
                ("Q<sub>b</sub> = 1.5×R<sub>bt</sub>×b×h<sub>0</sub><sup>2</sup>/C",
                 f"{_r2['sh'].Qb_opt:.1f} kN", f"{_r3['sh'].Qb_opt:.1f} kN"),
                ("Q<sub>sw</sub> = 0.75×q<sub>sw</sub>×C",
                 f"{_r2['sh'].Qsw_opt:.1f} kN", f"{_r3['sh'].Qsw_opt:.1f} kN"),
                ("Chiều dài hình chiếu của vết nứt xiên C",
                 f"{_r2['sh'].C_opt:.0f} mm", f"{_r3['sh'].C_opt:.0f} mm"),
                ("Độ bền trên vết nứt xiên Q ≤ [Q] = Q<sub>b</sub> + Q<sub>sw</sub>",
                 f"{_r2['sh'].Qcap2:.1f} kN", f"{_r3['sh'].Qcap2:.1f} kN"),
                ("Kết luận",
                 "<b>ĐẠT</b>" if _r2['sh'].ok else "<b>KHÔNG ĐẠT</b>",
                 "<b>ĐẠT</b>" if _r3['sh'].ok else "<b>KHÔNG ĐẠT</b>"),
            ]
            for a, b, c in _sw_rows:
                _sw_data.append([Paragraph(a, st_lbl),
                                 Paragraph(b, st_cell_b if "Kết luận" in a else st_cell),
                                 Paragraph(c, st_cell_b if "Kết luận" in a else st_cell)])
            # Căn giữa các cột giá trị
            for i in range(1, len(_sw_data)):
                for j in (1, 2):
                    _sw_data[i][j].style.alignment = TA_CENTER
            # hAlign CENTER co y: bang rong dung khung trang
            # (180mm) nhu bang chinh 2 cot; frame SimpleDocTemplate
            # co padding ngang 6pt nen bang can TRAI bi day vao 6pt
            # so voi bang chinh — can giua de mep trai trung khit.
            t_sw = Table(_sw_data, colWidths=[90 * mm, 45 * mm, 45 * mm],
                         hAlign="CENTER")
            _sw_style = [
                # Không kẻ GRID — thể hiện như bảng thông tin (xen kẽ màu)
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), _PAD),
                ("BOTTOMPADDING", (0, 0), (-1, -1), _PAD),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, HexColor("#111111")),
                ("BOTTOMPADDING", (0, 0), (-1, 0), _HPAD),
            ]
            for i in range(1, len(_sw_data)):
                if i % 2 == 0:
                    _sw_style.append(("BACKGROUND", (0, i), (-1, i),
                                      HexColor("#F2F2F2")))
            t_sw.setStyle(TableStyle(_sw_style))
            _sw_story.append(t_sw)
        except Exception as e:
            _sw_story.append(Paragraph(f"Không tính được thép đai: {e}", st_cell))
        # Giữ toàn bộ bảng thép đai trên cùng 1 trang
        # Dùng KeepTogether với table trực tiếp (không qua list trung gian) để tránh lệch lề
        if len(_sw_story) == 1 and isinstance(_sw_story[0], Table):
            story.append(KeepTogether(_sw_story[0]))
        else:
            story.append(KeepTogether(_sw_story))

        # Do nhanh cac thanh phan (phuc vu phan bo gian trang)
        def _wh(_fl, _wmm):
            _t = 0.0
            for _f in _fl:
                _w2, _h2 = _f.wrap(_wmm * mm, 10000)
                _t += _h2
                try:
                    _t += _f.getSpaceBefore() + _f.getSpaceAfter()
                except Exception:
                    pass
            return _t
        _hl = _wh(left_flow, 90)
        _hr = _wh(right_flow, 90)
        _hs = _wh(_sw_story, 180)
        _rl = sum(len(_t._cellvalues) for _t in left_flow
                  if isinstance(_t, Table))
        _rs = sum(len(_t._cellvalues) for _t in _sw_story
                  if isinstance(_t, Table))
        _hi = 0.0
        for _t in right_flow:
            if isinstance(_t, Table):
                try:
                    _c = _t._cellvalues[0][0]
                    if isinstance(_c, Image):
                        _hi += _c.drawHeight
                except Exception:
                    pass
        return story, (_hl, _hr, _hs, _rl, _rs, _hi)


    # --- Gian lap day trang: do khoang trong day that tu trang thai
    # frame sau build, phan bo vao (a) padding o bang -> (b) khoang
    # cach giua cac khoi -> (c) leading -> (d) co hinh cot phai; moi
    # lever co tran. Chon ban build 1 trang co trong day nho nhat.
    _TARGET = 7.0
    _cands = []

    def _try(_pad, _hpad, _lead, _tsp, _csp, _isp, _msp, _iw,
             _safe=False):
        try:
            _story, _info = _mk(_pad, _hpad, _lead, _tsp, _csp, _isp,
                                _msp, _iw)
            _buf = _io.BytesIO()
            _doc = SimpleDocTemplate(
                _buf, pagesize=A4, leftMargin=15 * mm,
                rightMargin=15 * mm, topMargin=_MRG * mm,
                bottomMargin=_MRG * mm, title="Kết quả kiểm tra cột BTCT")
            _doc.build(_story)
        except Exception:
            if _safe:
                return 99, None, None
            raise
        _pg = getattr(_doc, "page", 1)
        _gap = None
        if _pg == 1:
            try:
                _gap = _doc.frame._y - _doc.frame._y1
            except Exception:
                _gap = None
        _cands.append((_pg, _gap, _buf.getvalue()))
        return _pg, _gap, _info

    def _scaled(_arg, _fac):
        return (_PAD + (_arg[0] - _PAD) * _fac,
                _HPAD + (_arg[1] - _HPAD) * _fac,
                _LEAD + (_arg[2] - _LEAD) * _fac,
                _TSP + (_arg[3] - _TSP) * _fac,
                _CSP + (_arg[4] - _CSP) * _fac,
                _ISP + (_arg[5] - _ISP) * _fac,
                _MSP + (_arg[6] - _MSP) * _fac,
                _IW0 + (_arg[7] - _IW0) * _fac)

    _base = (_PAD, _HPAD, _LEAD, _TSP, _CSP, _ISP, _MSP, _IW0)
    _pg, _gap, _info = _try(*_base)
    if _pg == 1 and _gap is not None and _gap > _TARGET + 1.5:
        _hl, _hr, _hs, _rl, _rs, _hi = _info
        _need = _gap - _TARGET
        _freeL = max(0.0, _hr - _hl)
        _freeR = max(0.0, _hl - _hr)

        def _grow(_e, _free):
            # Tong chieu cao tang khi moi dong bang tang _e; cot chua
            # co dong bang (cot phai) chi tinh phan vuot do duoi kip.
            if _free > 0:
                return _e * _rs + max(0.0, _e * _rl - _free)
            return _e * (_rs + _rl)

        def _solve(_target, _cap, _free):
            if _target <= 0 or _cap <= 0:
                return 0.0
            if _grow(_cap, _free) <= _target:
                return _cap
            if _free > 0:
                _e1 = _target / _rs if _rs > 0 else _cap
                if _e1 * _rl <= _free:
                    return _e1
                return (_target + _free) / max(1, _rs + _rl)
            return _target / max(1, _rs + _rl)

        # (a) Padding doc o bang (tran: moi phia <= 4.0pt)
        _dpad = _solve(_need, 2.0 * max(0.0, 4.0 - _PAD), _freeL) / 2.0
        _rem = _need - _grow(2.0 * _dpad, _freeL)
        # (b) Khoang cach giua cac khoi
        _dmsp = _dtsp = _disp = _dcsp = 0.0
        if _rem > 0:
            _dmsp = min(14.0, _rem)
            _rem -= _dmsp
        if _rem > 0:
            _dtsp = min(6.0, _rem)
            _rem -= _dtsp
        if _rem > 0:
            _disp = min(8.0, (_rem + _freeR) / 2.0)
            _rem -= max(0.0, 2.0 * _disp - _freeR)
            _freeR = max(0.0, _freeR - 2.0 * _disp)
        if _rem > 0:
            _dcsp = min(4.0, (_rem + _freeR) / 4.0)
            _rem -= max(0.0, 4.0 * _dcsp - _freeR)
            _freeR = max(0.0, _freeR - 4.0 * _dcsp)
        # (c) Leading dong chu than bang (tran tong <= 11.5pt)
        _freeL2 = max(0.0, _freeL - 2.0 * _dpad * _rl)
        _dlead = _solve(_rem, max(0.0, 11.5 - _LEAD), _freeL2)
        _rem -= _grow(_dlead, _freeL2)
        # (d) Tang co hinh cot phai (giu nguyen ti le, tran 80mm)
        _iw = _IW0
        if _rem > 0 and _hi > 1:
            _iw = min(80.0, _IW0 * (1.0 + (_rem + _freeR) / _hi))
        # Can bang 2 cot bang chinh: cot phai con thieu so voi cot
        # trai (sau gian dong) thi bu bang spacer/tieu de/co hinh cot
        # phai — mien phi ve tong chieu cao vi cot trai dang cao nhat,
        # chi lap khoang trong trong o ben phai.
        _gL = (2.0 * _dpad + _dlead) * _rl
        _gR = 2.0 * _disp + 4.0 * _dcsp + (_iw / _IW0 - 1.0) * _hi
        _short = (_hl + _gL) - (_hr + _gR)
        if _short > 1.0:
            _add = min(8.0 - _disp, _short / 2.0)
            if _add > 0:
                _disp += _add
                _short -= 2.0 * _add
            if _short > 1.0:
                _add = min(4.0 - _dcsp, _short / 4.0)
                if _add > 0:
                    _dcsp += _add
                    _short -= 4.0 * _add
            if _short > 1.0 and _hi > 1:
                _iw = min(80.0, _iw + _IW0 * _short / _hi)
        _arg = (_PAD + _dpad, _HPAD + _dpad, _LEAD + _dlead,
                _TSP + _dtsp, _CSP + _dcsp, _ISP + _disp,
                _MSP + _dmsp, _iw)
        # Build ban gian + hieu chinh ti le toi da 2 vong
        _pgc, _gapc, _ic = _try(*_arg, _safe=True)
        for _rnd in range(2):
            if _pgc == 99 or _pgc == 1 and _gapc is not None and (
                    2.5 <= _gapc <= 12.0):
                break
            if _pgc != 1:
                _fac = 0.55
            elif _gapc is not None:
                _gain = _gap - _gapc
                if _gain <= 1.0:
                    break
                _fac = max(0.4, min(1.8, (_gap - _TARGET) / _gain))
            else:
                break
            _arg = _scaled(_arg, _fac)
            _pgc, _gapc, _ic = _try(*_arg, _safe=True)
    _ok = [c for c in _cands if c[0] == 1 and c[1] is not None]
    if _ok:
        _ok.sort(key=lambda c: c[1])
        _best = _ok[0]
    elif _cands:
        _best = _cands[0]
    else:
        _best = (1, None, b"")
    if hasattr(filepath, "write"):
        filepath.write(_best[2])
    else:
        with open(filepath, "wb") as _fh:
            _fh.write(_best[2])
    return _best[0]



def export_summary_pdf(sec, inp, res, filepath: str, case_info=None,
                       sec_img_path=None, shear_info=None,
                       show_compression: bool = True):
    """Xuat PDF tom tat TCVN — LUON dung 1 trang A4.

    Thu cac muc nen layout tu nhe den manh (giam le tren/duoi, nen
    padding/leading, thu nho hinh cot phai o muc cao) va lay muc dau
    tien cho ra dung 1 trang. Moi hang theo dan y deu giu nguyen o
    moi muc nen. So lieu/ket luan khong doi.
    """
    import io as _io
    _buf = None
    for _lvl in range(4):
        _buf = _io.BytesIO()
        _pages = _export_summary_pdf_impl(
            sec, inp, res, _buf, case_info=case_info,
            sec_img_path=sec_img_path, shear_info=shear_info,
            show_compression=show_compression, _level=_lvl)
        if _pages <= 1:
            break
    with open(filepath, "wb") as _f:
        _f.write(_buf.getvalue())
    return filepath
