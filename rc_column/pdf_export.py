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
                           na_info=None, width_in=3.5, dpi=200) -> bytes:
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
                             na_info=na_info)
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


def surface_3d_image(sec, inp, res, width_in=4.0, dpi=200) -> bytes:
    """Mặt tương tác 3D N-M2-M3."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    import numpy as np
    from .interaction import BiaxialCapacity
    fig = plt.figure(figsize=(width_in, width_in))
    ax = fig.add_subplot(111, projection="3d")
    cap = BiaxialCapacity(sec, model=inp.concrete_model, n_angles=24)
    n_vals, th_vals, mxg, myg = cap.surface_grid(n_n=25, n_angles=48)
    N3, _ = np.meshgrid(n_vals, th_vals, indexing="ij")
    mxg = np.concatenate([mxg, mxg[:, :1]], axis=1)
    myg = np.concatenate([myg, myg[:, :1]], axis=1)
    N3 = np.concatenate([N3, N3[:, :1]], axis=1)
    ax.plot_surface(mxg, myg, N3, alpha=0.7, cmap="viridis",
                    edgecolor="none")
    ax.scatter([res.Mx_star], [res.My_star], [res.N], c="red", s=60,
               label="Điểm tải A")
    ax.set_xlabel("M2 (kN×m)")
    ax.set_ylabel("M3 (kN×m)")
    ax.set_zlabel("N (kN)")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def interaction_images(sec, inp, res, width_in=3.4, dpi=300,
                       small=False) -> tuple:
    """Trả về (png_NM2, png_NM3) — 2 ảnh riêng cho layout lớn."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if small:
        width_in, dpi = 3.2, 100
    from .interaction import FiberSection, uniaxial_curve_fs
    fs = FiberSection(sec)
    out = []
    for th, lab, Ms, Mb in [(0, "N-M2", res.Mx_star, res.Bx),
                             (90, "N-M3", res.My_star, res.By)]:
        fig, ax = plt.subplots(figsize=(width_in, width_in))
        cv = uniaxial_curve_fs(fs, th, inp.concrete_model)
        ax.plot([p[1] for p in cv], [p[0] for p in cv], "b-", lw=1.5)
        ax.plot([-p[1] for p in cv], [p[0] for p in cv], "b-", lw=1.5)
        lim = (res.BN, Mb)
        ax.scatter([Ms], [res.N], c="red", s=80, zorder=5,
                   label="Điểm tải A")
        ax.plot([0, lim[1]], [0, lim[0]], "r--", lw=1.2, alpha=0.8,
                label="Tia tải O-A-B")
        ax.scatter([lim[1]], [lim[0]], c="orange", s=80, zorder=5,
                   label="Điểm giới hạn B")
        ax.set_xlabel("M (kN×m)")
        ax.set_ylabel("N (kN)")
        ax.set_title(f"Biểu đồ tương tác {lab}", fontsize=11)
        ax.legend(fontsize=9)
        ax.grid(True, color="#E5E7EB", linestyle="--", linewidth=0.7, alpha=0.9)
        ax.set_axisbelow(True)
        ax.text(0.5, -0.30, f"Tỉ số an toàn FS = {res.fs:.2f}",
                transform=ax.transAxes, ha="center", fontsize=10,
                color="darkred", weight="bold")
        fig.subplots_adjust(bottom=0.22)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        out.append(buf.getvalue())
    return tuple(out)


# --- Xuất PDF ---
import re as _re

def _math_sub(text: str) -> str:
    """Chuyển ký hiệu toán học _{xx} thành <sub>xx</sub> cho ReportLab."""
    return _re.sub(r"_\{([^}]+)\}", r"<sub>\1</sub>", text)


def _segs_to_flowables(segs, P, st_body, st_h, st_ref, st_dc,
                       st_badge_ok, st_badge_ng):
    """Chuyển segments của 1 mục thành list flowables."""
    out = []
    buf_lines: List[str] = []
    def flush():
        if buf_lines:
            out.append(P("<br/>".join(buf_lines), st_body))
            buf_lines.clear()
    for text, tags in segs:
        t = text.strip("\n")
        if not t:
            continue
        if "sec_title" in tags:
            flush()
            out.append(P(t.replace("● ", ""), st_h))
        elif "sec_ref" in tags:
            out.append(P(t.strip(), st_ref))
        elif "dc" in tags:
            flush()
            out.append(P(t, st_dc))
        elif "ok" in tags:
            flush()
            out.append(P("✓ ĐẠT — D/C ≤ 1.000", st_badge_ok))
        elif "ng" in tags:
            flush()
            out.append(P("✗ KHÔNG ĐẠT — D/C > 1.000", st_badge_ng))
        elif "title" in tags:
            continue
def draw_compression_zone_ax(ax, sec, N_kN: float, M2_kNm: float, M3_kNm: float,
                             Nmax_kN: float = None, title: str = None,
                             na_info: dict = None):
    """Vẽ mặt cắt kiểu VietconSoft (giống tab Kết quả) + tô vùng nén.
    
    na_info: dict từ neutral_axis_at_N (đường trung hòa chính xác từ fiber model).
             Nếu None, dùng ước lượng đơn giản theo hướng mô men.
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
    
    if sec_poly and len(sec_poly) >= 3:
        _corners = list(sec_poly)
        _comp_corners = [(_cx, _cy) for (_cx, _cy) in _corners
                         if _naval(_cx, _cy) >= -1e-9]
        _edges = [(_corners[i], _corners[(i+1)%len(_corners)]) for i in range(len(_corners))]
        _intersects = []
        for (_x1, _y1), (_x2, _y2) in _edges:
            _v1 = _naval(_x1, _y1)
            _v2 = _naval(_x2, _y2)
            if _v1 * _v2 < 0:
                _t = abs(_v1) / (abs(_v1) + abs(_v2))
                _intersects.append((_x1 + _t*(_x2-_x1), _y1 + _t*(_y2-_y1)))
        _poly_pts = _comp_corners + _intersects
        if len(_poly_pts) >= 3:
            _gcx = sum(p[0] for p in _poly_pts)/len(_poly_pts)
            _gcy = sum(p[1] for p in _poly_pts)/len(_poly_pts)
            _poly_pts.sort(key=lambda p: math.atan2(p[1]-_gcy, p[0]-_gcx))
            ax.add_patch(MplPolygon(_poly_pts, closed=True, fill=True,
                                    facecolor="#BFDBFE", edgecolor="#2563EB",
                                    lw=1.5, zorder=3, alpha=0.7))
            if len(_intersects) == 2:
                ax.plot([_intersects[0][0], _intersects[1][0]],
                        [_intersects[0][1], _intersects[1][1]],
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
                        frameon=True, fontsize=7,
                        facecolor="white", edgecolor="#D1D5DB")
        for txt in leg.get_texts():
            txt.set_fontweight("bold")
    
    alen = max(cx, cy) * 0.62
    # Mũi tên trục t2 (xanh lá, ngang), t3 (xanh dương, đứng) - vẽ trên cùng
    # Đặt giới hạn trục để mũi tên không bị cắt
    _lim = max(cx, cy) * 0.85
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
    
    # Không set title bên trong (đã có tiêu đề card bên ngoài)
    # Nhãn trục thành kích thước t2/t3
    if sec.kind == "rect":
        # Cạnh t2 là đứng (cy), cạnh t3 là ngang (cx) theo quy ước app
        ax.set_xlabel(f"t3 = {cx:.0f} mm", fontsize=7, weight="bold")
        ax.set_ylabel(f"t2 = {cy:.0f} mm", fontsize=7, weight="bold")
    elif sec.kind == "circle":
        ax.set_xlabel(f"D = {cx:.0f} mm", fontsize=7, weight="bold")
        ax.set_ylabel(f"D = {cx:.0f} mm", fontsize=7, weight="bold")
    else:
        ax.set_xlabel("Trục 2 (mm)", fontsize=7)
        ax.set_ylabel("Trục 3 (mm)", fontsize=7)
    ax.tick_params(labelsize=7)


def export_summary_pdf(sec, inp, res, filepath: str, case_info=None,
                       sec_img_path=None, shear_info=None):
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
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from collections import Counter
    import os as _os

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
    st_title = ParagraphStyle("t", fontName=FNB, fontSize=14,
                              alignment=TA_CENTER, spaceAfter=8)
    st_sec = ParagraphStyle("sec", fontName=FNB, fontSize=9,
                            spaceBefore=5, spaceAfter=1,
                            textColor=HexColor("#111111"),
                            borderPadding=(0, 0, 2))
    st_cell = ParagraphStyle("c", fontName=FN, fontSize=7, leading=9)
    st_cell_b = ParagraphStyle("cb", fontName=FNB, fontSize=7, leading=9)
    st_hdr = ParagraphStyle("hdr", fontName=FNB, fontSize=7, leading=9,
                             alignment=TA_CENTER)
    st_hdr_left = ParagraphStyle("hdr_left", parent=st_hdr, alignment=TA_LEFT)

    st_lbl = ParagraphStyle("lbl", parent=st_cell, alignment=TA_LEFT)
    st_val = ParagraphStyle("val", parent=st_cell, alignment=TA_LEFT)
    st_val_b = ParagraphStyle("val_b", parent=st_cell_b, alignment=TA_LEFT)
    st_sec_title = ParagraphStyle("sectitle", parent=st_cell_b, alignment=TA_LEFT)
    def _sec_table(title, rows):
        """Bảng 2 cột kiểu Excel: tiêu đề section + các dòng xen kẽ màu."""
        data = [[Paragraph(f"<b>{title}</b>", st_sec_title)]]
        for lbl, val in rows:
            _vs = str(val)
            # Nếu giá trị có thẻ <b>, dùng style in đậm trực tiếp (tránh lỗi font <b>)
            if "<b>" in _vs:
                _vs_clean = _vs.replace("<b>", "").replace("</b>", "")
                data.append([Paragraph(lbl, st_lbl),
                             Paragraph(_vs_clean, st_val_b)])
            else:
                data.append([Paragraph(lbl, st_lbl),
                             Paragraph(_vs, st_val)])
        # colWidths: nhãn 60mm (2 phần), giá trị 30mm (1 phần)
        t = Table(data, colWidths=[60 * mm, 30 * mm], hAlign="LEFT")
        style = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            # Gạch dưới tiêu đề section
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, HexColor("#111111")),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
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

    _story_txt, _label_txt, _combo_txt = "—", "—", "—"
    if case_info:
        _story_txt = str(case_info.get("story", "—"))
        _label_txt = str(case_info.get("label", case_info.get("column", "—")))
        _combo_txt = str(case_info.get("case", case_info.get("combo", "—")))
    _vpos = f"[{_story_txt}]-[{_label_txt}]" if _story_txt != "—" else "—"

    _alpha = _m.degrees(_m.atan2(res.Mx_star, res.My_star)) \
        if abs(res.Mx_star) + abs(res.My_star) > 1e-9 else 0.0
    _ok_txt = "<b>ĐẠT</b>" if res.ok else "<b>KHÔNG ĐẠT</b>"

    # ===== Cột trái: các bảng =====
    left_flow = []

    # THÔNG TIN CHUNG
    left_flow.append(_sec_table("THÔNG TIN CHUNG", [
        ("Tiêu chuẩn", "TCVN 5574:2018"),
        ("Tên cấu kiện", _ck_name or "—"),
    ]))

    # VẬT LIỆU
    _mat_rows = []
    if _cg:
        _mat_rows += [
            ("Bê tông", inp.concrete_grade),
            ("Cường độ chịu nén, R<sub>b</sub>", f"{_cg.Rb:.0f} MPa"),
            ("Mô đun đàn hồi, E<sub>b</sub>", f"{_cg.Eb:.0f} MPa"),
        ]
    if _sg:
        _mat_rows += [
            ("Cốt thép dọc", inp.steel_grade),
            ("Cường độ chịu kéo, R<sub>s</sub>", f"{_sg.Rs:.0f} MPa"),
            ("Mô đun đàn hồi, E<sub>s</sub>", f"{_sg.Es:.0f} MPa"),
        ]
    if _swg:
        _mat_rows += [
            ("Cốt thép đai", inp.sw_steel_grade),
            ("Cường độ chịu cắt, R<sub>sw</sub>", f"{_swg.Rsw:.0f} MPa"),
            ("Mô đun đàn hồi, E<sub>s</sub>", f"{_swg.Es:.0f} MPa"),
        ]
    left_flow.append(_sec_table("VẬT LIỆU", _mat_rows))

    # TIẾT DIỆN
    left_flow.append(_sec_table("TIẾT DIỆN", [
        ("Chiều rộng, t3", f"{_t3:.0f} mm"),
        ("Chiều cao, t2", f"{_t2:.0f} mm"),
        ("Lớp bê tông bảo vệ, c", f"{inp.cover:.0f} mm"),
    ]))

    # BỐ TRÍ CỐT THÉP
    left_flow.append(_sec_table("BỐ TRÍ CỐT THÉP", [
        ("Cốt thép dọc", " + ".join(_parts)),
        ("Hàm lượng thép dọc, μ", f"{_mu*100:.2f}%"),
    ]))

    # NỘI LỰC TÍNH TOÁN (bỏ V2, V3 theo yêu cầu)
    left_flow.append(_sec_table("NỘI LỰC TÍNH TOÁN", [
        ("Vị trí cột", _vpos),
        ("Tổ hợp tính toán", _combo_txt),
        ("Lực dọc, N", f"{res.N:.1f} kN"),
        ("Momen quanh trục 2, M2", f"{res.Mx:.1f} kNm"),
        ("Momen quanh trục 3, M3", f"{res.My:.1f} kNm"),
    ]))

    # KẾT QUẢ TÍNH TOÁN (thêm điểm B để lấp khoảng trống)
    _Mb = _m.hypot(res.Bx, res.By)
    _Ma = _m.hypot(res.Mx_star, res.My_star)
    left_flow.append(_sec_table("KẾT QUẢ TÍNH TOÁN", [
        ("Góc tác dụng mômen, α", f"{_alpha:.1f}°"),
        ("Điểm tải trọng A", ""),
        ("Lực dọc, N", f"{res.N:.1f} kN"),
        ("Mômen tính toán, M2*", f"{res.Mx_star:.1f} kNm"),
        ("Mômen tính toán, M3*", f"{res.My_star:.1f} kNm"),
        ("Mômen tổng, Mα", f"{_Ma:.1f} kNm"),
        ("Điểm giới hạn B", ""),
        ("Lực dọc, Nu", f"{res.BN:.1f} kN"),
        ("Mômen, M2u", f"{res.Bx:.1f} kNm"),
        ("Mômen, M3u", f"{res.By:.1f} kNm"),
        ("Mômen tổng, Mα,u", f"{_Mb:.1f} kNm"),
        ("Tỉ số sử dụng khả năng chịu lực, D/C", f"{res.dc:.3f}"),
        ("Hệ số an toàn, FS", f"{res.fs:.2f}"),
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
                                      fontSize=8, spaceBefore=2, spaceAfter=2)
    right_flow = []
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
            na_info=_cz_na, width_in=2.2, dpi=200)
        right_flow.append(_centered_img(_sec_png, 66))
        right_flow.append(Spacer(1, 2))
        # Biểu đồ N-Mα (có tiêu đề như app, chỉ hiện nửa phải có tải)
        _nm_png = interaction_image(sec, inp, res, width_in=3.2, dpi=150,
                                    small=True, right_half=True)
        right_flow.append(Paragraph(
            f"<b>Biểu đồ tương tác N-Mα</b> (α = {_alpha:.1f}°)",
            st_chart_title))
        right_flow.append(_centered_img(_nm_png, 66))
        right_flow.append(Spacer(1, 2))
        # Biểu đồ M2-M3 (có tiêu đề như app)
        _m2m3_png = m2m3_image(sec, inp, res, width_in=3.2, dpi=150)
        if isinstance(_m2m3_png, bytes):
            right_flow.append(Paragraph(
                f"<b>Mặt cắt M2-M3</b> (N = {res.N:+.1f} kN)",
                st_chart_title))
            right_flow.append(_centered_img(_m2m3_png, 66))
    except Exception as e:
        right_flow.append(Paragraph(f"(Không vẽ được hình: {e})", st_cell))

    # ===== Bảng 2 cột chính =====
    # Tỉ lệ 2:1:3 — nhãn 60mm, giá trị 30mm, hình 90mm
    main_data = [[left_flow, right_flow]]
    t_main = Table(main_data, colWidths=[90 * mm, 90 * mm], hAlign="CENTER")
    t_main.setStyle(TableStyle([
        ("VALIGN", (0, 0), (0, 0), "TOP"),
        ("VALIGN", (1, 0), (1, 0), "BOTTOM"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    story = []
    story.append(Paragraph("KIỂM TRA CỘT BÊ TÔNG CỐT THÉP", st_title))
    story.append(t_main)
    story.append(Spacer(1, 4))

    # ===== KIỂM TRA THÉP ĐAI (full width, giữ ở trang 1) =====
    # Dùng KeepTogether để không bị tách trang
    from reportlab.platypus import KeepTogether
    _sw_story = []
    try:
        from .stirrup import StirrupInput, check_shear
        from .sections import bar_area
        stir_in = StirrupInput(dia=inp.sw_dia, spacing=inp.sw_spacing,
                               legs=inp.sw_legs)
        _sw_txt = (f"{stir_in.legs:.0f}φ{stir_in.dia:.0f} "
                   f"a{stir_in.spacing:.0f}")
        _cols = []
        for Q, b_w, h_dim in ((inp.Q2, _t2, _t3), (inp.Q3, _t3, _t2)):
            h0 = h_dim - inp.cover - inp.sw_dia - 12
            Asw = stir_in.legs * bar_area(stir_in.dia)
            sh = check_shear(abs(Q), b_w, max(h0, 1),
                             _cg.Rb if _cg else 0,
                             _cg.Rbt if _cg else 0,
                             Asw, _swg.Rsw if _swg else 0,
                             stir_in.spacing)
            qsw = (_swg.Rsw * Asw / stir_in.spacing) if _swg else 0
            _cols.append(dict(Q=Q, b=b_w, h0=h0, Asw=Asw, qsw=qsw, sh=sh))
        _r2, _r3 = _cols[0], _cols[1]
        _sw_data = [
            [Paragraph("<b>KIỂM TRA KHẢ NĂNG CHỊU CẮT</b>", st_hdr_left),
             Paragraph("<b>Phương V2</b>", st_hdr),
             Paragraph("<b>Phương V3</b>", st_hdr)],
        ]
        _sw_rows = [
            ("Thép đai bố trí", _sw_txt, _sw_txt),
            ("Lực cắt tính toán, Q",
             f"{_r2['Q']:.1f} kN", f"{_r3['Q']:.1f} kN"),
            ("Kích thước tiết diện, b × h<sub>0</sub>",
             f"{_r2['b']:.0f} × {_r2['h0']:.0f} mm",
             f"{_r3['b']:.0f} × {_r3['h0']:.0f} mm"),
            ("A<sub>sw</sub> = n × φ",
             f"{_r2['Asw']:.0f} mm²", f"{_r3['Asw']:.0f} mm²"),
            ("q<sub>sw</sub> = R<sub>sw</sub> × A<sub>sw</sub>/s",
             f"{_r2['qsw']:.1f} N/mm", f"{_r3['qsw']:.1f} N/mm"),
            ("Độ bền trên dải nén xiên Q ≤ 0.3×R<sub>b</sub>×b×h<sub>0</sub>",
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
        t_sw = Table(_sw_data, colWidths=[90 * mm, 45 * mm, 45 * mm],
                     hAlign="LEFT")
        _sw_style = [
            # Không kẻ GRID — thể hiện như bảng thông tin (xen kẽ màu)
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, HexColor("#111111")),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
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

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=10 * mm, bottomMargin=10 * mm,
                            title="Kết quả kiểm tra cột BTCT")
    doc.build(story)
    return filepath
