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
                    small_dots: bool = False):
    """Vẽ mặt cắt kiểu VietconSoft: nền lưới, khung đen, thép lớp 1 đỏ /
    lớp 2 xanh lá (cỡ chấm theo đường kính), trục t2/t3 tại tâm, dim t3/t2,
    thẻ thống kê bên dưới."""
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
        # Cỡ chấm bằng chấm legend diễn giải
        dot_s = (max(5.0, dia * 0.32)) ** 2
        # Co vào trong 4% để không chạm viền
        ax.scatter([p.x * 0.96 for p in pts], [p.y * 0.96 for p in pts],
                   s=dot_s, c=color, zorder=4,
                   edgecolors="white", linewidths=0.8)
        legend_handles.append(Line2D(
            [0], [0], marker="o", color="none", markerfacecolor=color,
            markeredgecolor="white", markersize=max(5.0, dia * 0.32),
            label=f"d{dia:.0f}"))
    if legend_handles:
        leg = ax.legend(handles=legend_handles, loc="upper center",
                        bbox_to_anchor=(0.5, 0.985), ncol=len(legend_handles),
                        frameon=False, fontsize=8)
        for txt in leg.get_texts():
            txt.set_fontweight("bold")
    # Trục t2/t3 vượt ra khỏi đường bao để thấy text
    alen = max(cx, cy) * 0.62
    ax.annotate("", xy=(alen, 0), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color="#16A34A", lw=1.6))
    ax.annotate("", xy=(0, alen), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color="#2563EB", lw=1.6))
    ax.text(alen * 1.08, 0, "t2", fontsize=9, color="#15803D",
            weight="bold", va="center", ha="left")
    ax.text(0, alen * 1.08, "t3", fontsize=9, color="#1D4ED8",
            weight="bold", va="bottom", ha="center")
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
    elif show_dims:
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
    ax.set_ylim(-cy/2 - m, cy/2 + m * 1.35)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)


def section_image(sec, width_in=3.2, dpi=300, small=False,
                  show_stats=True) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if small:
        width_in, dpi = 1.3, 200
    # Figure theo đúng tỉ lệ t2/t3 (cao = rộng × cy/cx)
    ratio = sec.cy / sec.cx if sec.cx > 0 else 1.0
    fig, ax = plt.subplots(figsize=(width_in, width_in * ratio))
    draw_section_ax(ax, sec, show_stats=show_stats)
    ax.grid(True, color="#E5E7EB", linestyle="--", linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    for sp in ax.spines.values():
        sp.set_visible(False)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                pad_inches=0.1)
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
                      right_half=False) -> bytes:
    """Biểu đồ tương tác N-M tại góc uốn xiên α.
    right_half=True: chỉ hiện nửa phải (M>=0) có đường nội lực."""
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
    ax.scatter([lim[1]], [lim[0]], c=ORANGE, s=70, zorder=5,
               edgecolors="white", linewidths=1.2)
    ax.scatter([Ma], [res.N], c=GREEN, s=70, zorder=6,
               edgecolors="white", linewidths=1.2)
    ax.text(Ma, res.N, "  A", fontsize=9, color=GREEN,
            weight="bold", va="center", zorder=7)
    ax.text(lim[1], lim[0], "  B", fontsize=9, color=ORANGE,
            weight="bold", va="center", zorder=7)
    ax.set_xlabel("Mα (kN·m)", fontsize=10, fontweight="bold")
    ax.set_ylabel("N (kN)", fontsize=10, fontweight="bold")
    ax.tick_params(labelsize=8)
    ax.text(0.05, 0.95, f"α = {alpha_deg:.1f}°",
            transform=ax.transAxes, fontsize=8, color="#4B5563",
            va="top", ha="left",
            bbox=dict(boxstyle="round,pad=0.3", fc="white",
                      ec="#E5E7EB", alpha=0.9))
    if right_half:
        # Chỉ hiện nửa phải (M >= 0)
        ax.set_xlim(left=0)
    # Legend 4 mục như tab Kết quả (dùng Line2D custom)
    from matplotlib.lines import Line2D as _L2D
    _leg = [
        _L2D([0], [0], color=GREEN, lw=2.2, label="Đường bao N-Mα"),
        _L2D([0], [0], marker="o", color="w", markerfacecolor=GREEN,
             markersize=8, markeredgecolor="white", label="Điểm tải A"),
        _L2D([0], [0], marker="D", color="w", markerfacecolor=ORANGE,
             markersize=7, markeredgecolor="white", label="Điểm giới hạn B"),
        _L2D([0], [0], color=RED, lw=1.5, ls="--", dashes=(4, 3),
             label="Tia tải O-A-B"),
    ]
    ax.legend(handles=_leg, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.18), ncol=4, frameon=False)
    ax.grid(True, color="#E5E7EB", linestyle="--", linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    for _sp in ("top", "right"):
        ax.spines[_sp].set_visible(False)
    for _sp in ("left", "bottom"):
        ax.spines[_sp].set_color("#9CA3AF")
    fig.subplots_adjust(bottom=0.32)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi)
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
    ax.scatter([res.Bx], [res.By], c=ORANGE, s=70, zorder=5,
               edgecolors="white", linewidths=1.2)
    ax.scatter([res.Mx_star], [res.My_star], c=GREEN, s=70, zorder=6,
               edgecolors="white", linewidths=1.2)
    ax.text(res.Mx_star, res.My_star, "  A", fontsize=9, color=GREEN,
            weight="bold", va="center", zorder=7)
    ax.text(res.Bx, res.By, "  B", fontsize=9, color=ORANGE,
            weight="bold", va="center", zorder=7)
    ax.axhline(0, color="#6B7280", linewidth=1.0, zorder=2)
    ax.axvline(0, color="#6B7280", linewidth=1.0, zorder=2)
    ax.set_xlabel("M2 (kN·m)", fontsize=10, fontweight="bold")
    ax.set_ylabel("M3 (kN·m)", fontsize=10, fontweight="bold")
    ax.tick_params(labelsize=8)
    from matplotlib.lines import Line2D as _L2D2
    _leg2 = [
        _L2D2([0], [0], color=BLUE, lw=2.2, label="Đường bao M2-M3"),
        _L2D2([0], [0], marker="o", color="w", markerfacecolor=GREEN,
              markersize=8, markeredgecolor="white", label="Điểm tải A"),
        _L2D2([0], [0], marker="D", color="w", markerfacecolor=ORANGE,
              markersize=7, markeredgecolor="white", label="Điểm giới hạn B"),
        _L2D2([0], [0], color=RED, lw=1.5, ls="--", dashes=(4, 3),
              label="Tia tải O-A-B"),
    ]
    ax.legend(handles=_leg2, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.22), ncol=4, frameon=False)
    ax.grid(True, color="#E5E7EB", linestyle="--", linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    ax.set_aspect("equal", adjustable="datalim")
    for _sp in ("top", "right"):
        ax.spines[_sp].set_visible(False)
    for _sp in ("left", "bottom"):
        ax.spines[_sp].set_color("#9CA3AF")
    fig.subplots_adjust(bottom=0.32)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi)
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
    ax.set_xlabel("M2 (kN·m)")
    ax.set_ylabel("M3 (kN·m)")
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
        ax.set_xlabel("M (kN·m)")
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
        else:
            buf_lines.append(_math_sub(t.replace("\n", "<br/>")))
    flush()
    return out


def export_pdf(inp, res, filepath: str, batch_rows=None, case_info=None,
               shear_info=None):
    """Xuất thuyết minh ra file PDF (bố cục giống trong phần mềm).
    batch_rows: list (force, result) cho mục 8 (tùy chọn).
    case_info: dict {case, station, N, M2, M3} cho tổ hợp tính toán.
    shear_info: dict {q2: {...}, q3: {...}} cho lực cắt."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Image, Table, TableStyle, KeepTogether)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

    font_path = _find_font()
    bold_path = _find_font_bold()
    if not font_path:
        raise RuntimeError("Không tìm thấy font hỗ trợ tiếng Việt.")
    pdfmetrics.registerFont(TTFont("VN", font_path))
    pdfmetrics.registerFont(TTFont("VN-Bold", bold_path or font_path))

    sec = __import__("rc_column.checker", fromlist=["build_section"]).build_section(inp)

    SLATE = HexColor("#0f172a")
    GRAY = HexColor("#64748b")
    GREEN_BG = HexColor("#d1fae5")
    GREEN_TX = HexColor("#065f46")
    RED_BG = HexColor("#fee2e2")
    RED_TX = HexColor("#991b1b")
    DC_GREEN = HexColor("#059669")

    st_title = ParagraphStyle("title", fontName="VN-Bold", fontSize=14,
                              textColor=SLATE, alignment=TA_CENTER, spaceAfter=4)
    st_sub = ParagraphStyle("sub", fontName="VN", fontSize=9,
                            textColor=GRAY, alignment=TA_CENTER, spaceAfter=8)
    st_h = ParagraphStyle("h", fontName="VN-Bold", fontSize=11,
                          textColor=SLATE, spaceBefore=6, spaceAfter=1)
    st_ref = ParagraphStyle("ref", fontName="VN", fontSize=8,
                            textColor=GRAY, spaceAfter=6)
    st_body = ParagraphStyle("body", fontName="VN", fontSize=9.5,
                             textColor=SLATE, leading=14, spaceAfter=1,
                             alignment=TA_JUSTIFY)
    st_cap = ParagraphStyle("cap", fontName="VN", fontSize=8,
                            textColor=GRAY, alignment=TA_CENTER, spaceBefore=4)
    st_dc = ParagraphStyle("dc", fontName="VN-Bold", fontSize=10,
                           leading=14, textColor=DC_GREEN, alignment=TA_CENTER,
                           spaceBefore=8, spaceAfter=6)
    st_badge_ok = ParagraphStyle("bok", fontName="VN-Bold", fontSize=10,
                                 textColor=GREEN_TX, backColor=GREEN_BG,
                                 alignment=TA_CENTER, borderPadding=6,
                                 spaceBefore=6)
    st_badge_ng = ParagraphStyle("bng", fontName="VN-Bold", fontSize=10,
                                 textColor=RED_TX, backColor=RED_BG,
                                 alignment=TA_CENTER, borderPadding=8,
                                 spaceBefore=8)

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    S: list = []
    P = Paragraph
    cvt = lambda segs: _segs_to_flowables(
        segs, P, st_body, st_h, st_ref, st_dc, st_badge_ok, st_badge_ng)

    S.append(P("THUYẾT MINH TÍNH TOÁN KIỂM TRA CỘT BTCT", st_title))
    S.append(P("Tiêu chuẩn: TCVN 5574:2018 — Mô hình biến dạng phi tuyến "
               "(Điều 8.1.2.7)", st_sub))

    from .report import generate_report_sections
    sections = generate_report_sections(inp, res, batch_rows=batch_rows,
                                        case_info=case_info,
                                        shear_info=shear_info)

    # Ảnh cho mục 2 (cột phải) và mục 6 (2 biểu đồ lớn full-width)
    img_side = {}
    try:
        _w = 50*mm
        _h = _w * (sec.cy / sec.cx) if sec.cx > 0 else _w
        img_side[2] = Image(io.BytesIO(section_image(sec, small=True)),
                            width=_w, height=_h)
    except Exception:
        pass
    img_m6 = []
    try:
        from .pdf_export import m2m3_image  # noqa
        # N-M full (trái) như tab Tóm tắt, M2-M3 (phải)
        png_nm = interaction_image(sec, inp, res, width_in=4.0)
        png_m2m3 = m2m3_image(sec, inp, res, width_in=4.0)
        # Giữ tỉ lệ gốc: đọc kích thước PNG rồi tính height theo width
        from PIL import Image as _PIL
        def _img_keep_ratio(png_bytes, w_mm):
            _pil = _PIL.open(io.BytesIO(png_bytes))
            _pw, _ph = _pil.size
            _h = w_mm * _ph / _pw if _pw > 0 else w_mm * 0.75
            return Image(io.BytesIO(png_bytes), width=w_mm*mm, height=_h*mm)
        img_m6 = [_img_keep_ratio(png_nm, 85),
                  _img_keep_ratio(png_m2m3, 85)]
    except Exception:
        pass
    captions = {2: "Hình 1. Mặt cắt cột và bố trí cốt thép"}

    # Gộp text mục 2+3 để hiển thị chung với ảnh bên phải
    flows_2 = cvt(sections[2]["segs"]) if 2 in sections else []
    flows_3 = cvt(sections[3]["segs"]) if 3 in sections else []
    flows_23 = flows_2 + flows_3

    for num in sorted(sections.keys()):
        info = sections[num]
        flows = cvt(info["segs"])
        if num == 2 and img_side.get(2) is not None:
            # Mục 2+3: text 2 mục bên trái, hình mặt cắt bên phải
            right_col = [img_side[2], P(captions[2], st_cap)]
            tbl = Table([[flows_23, right_col]],
                        colWidths=[108*mm, 68*mm])
            tbl.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
            ]))
            S.append(KeepTogether(tbl))
            S.append(Spacer(1, 1))
        elif num == 3:
            # Đã gộp vào mục 2, bỏ qua
            continue
        elif num == 6 and img_m6:
            from reportlab.platypus import PageBreak
            S.append(PageBreak())
            # Mục 6: text full-width, 2 biểu đồ cạnh nhau
            # (M2-M3 trái, N-M nửa phải có đường nội lực)
            S.extend(flows)
            S.append(Spacer(1, 4))
            tbl6 = Table([[
                [img_m6[0], P("Biểu đồ N-M (góc α)", st_cap)],
                [img_m6[1], P("Biểu đồ M2-M3 (tại N)", st_cap)],
            ]], colWidths=[88*mm, 88*mm])
            tbl6.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]))
            S.append(tbl6)
            S.append(P("Hình 2. Biểu đồ M2-M3 và N-M (góc α)", st_cap))
            S.append(Spacer(1, 6))
        elif num == 7 and batch_rows:
            # Mục 7: Table có lưới thật
            from reportlab.platypus import PageBreak
            S.append(PageBreak())
            S.append(P("7. BẢNG TỔNG HỢP KẾT QUẢ KIỂM TRA", st_h))
            S.append(P("Tất cả tổ hợp", st_ref))
            S.append(Spacer(1, 6))
            hdr = ["Tổ hợp", "N (kN)", "M2 (kN·m)", "M3 (kN·m)", "D/C", "KQ"]
            data = [hdr]
            for f, r in batch_rows:
                dc = r["dc"]
                ok = "ĐẠT" if dc <= 1 else "KHÔNG ĐẠT"
                data.append([f"{f.case}@{f.station:.2f}", f"{f.N:.0f}",
                             f"{f.Mx:.0f}", f"{f.My:.0f}",
                             f"{dc:.3f}", ok])
            t7 = Table(data, colWidths=[32*mm, 22*mm, 24*mm, 24*mm,
                                        20*mm, 28*mm])
            t7.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#000000")),
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#e2e8f0")),
                ("FONTNAME", (0, 0), (-1, 0), "VN-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "VN"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            S.append(t7)
            S.append(Spacer(1, 6))
        else:
            S.extend(flows)

    doc.build(S)
    return filepath

def export_summary_pdf(sec, inp, res, filepath: str, case_info=None,
                       sec_img_path=None):
    """Xuất PDF Kết quả tính toán theo mẫu Excel MAU_TMTT (TCVN 5574:2018)."""
    import math as _m
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle)
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

    # Styles theo mẫu Excel
    st_title = ParagraphStyle("t", fontName=FNB, fontSize=14,
                              alignment=TA_CENTER, spaceAfter=6)
    st_sec = ParagraphStyle("sec", fontName=FNB, fontSize=11,
                            spaceBefore=10, spaceAfter=4,
                            textColor=HexColor("#1F2937"))
    st_row = ParagraphStyle("row", fontName=FN, fontSize=9, leading=12)
    st_row_b = ParagraphStyle("rowb", fontName=FNB, fontSize=9, leading=12)
    st_cell = ParagraphStyle("c", fontName=FN, fontSize=9, leading=12)
    st_cell_b = ParagraphStyle("cb", fontName=FNB, fontSize=9, leading=12)
    st_hdr = ParagraphStyle("hdr", fontName=FNB, fontSize=9, leading=12,
                             alignment=TA_CENTER)

    def _tbl(rows, widths):
        """Tạo bảng 2-3 cột kiểu Excel: cột 1 in đậm nhãn, không viền đậm."""
        data = []
        for r in rows:
            if len(r) == 2:
                data.append([Paragraph(f"<b>{r[0]}</b>", st_cell),
                             Paragraph(str(r[1]), st_cell)])
            elif len(r) == 3:
                data.append([Paragraph(f"<b>{r[0]}</b>", st_cell),
                             Paragraph(str(r[1]), st_cell),
                             Paragraph(str(r[2]), st_cell)])
            else:  # header hoặc sub-header (1 cột)
                data.append([Paragraph(f"<b>{r[0]}</b>", st_cell)])
        t = Table(data, colWidths=widths, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (0, -1), 0),
        ]))
        return t

    def _tbl3(headers, rows, widths):
        """Bảng 3 cột có header (cho kiểm tra thép đai)."""
        data = [[Paragraph(f"<b>{h}</b>", st_hdr) for h in headers]]
        for r in rows:
            data.append([Paragraph(f"<b>{r[0]}</b>", st_cell),
                         Paragraph(str(r[1]), st_cell),
                         Paragraph(str(r[2]), st_cell)])
        t = Table(data, colWidths=widths, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#9CA3AF")),
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F3F4F6")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [HexColor("#FFFFFF"), HexColor("#F9FAFB")]),
        ]))
        return t

    story = []
    W2 = [60 * mm, 110 * mm]  # bảng 2 cột
    W3 = [60 * mm, 55 * mm, 55 * mm]  # bảng 3 cột

    # ===== Tiêu đề =====
    story.append(Paragraph("KIỂM TRA CỘT BÊ TÔNG CỐT THÉP", st_title))
    story.append(Spacer(1, 4))

    # ===== THÔNG TIN CHUNG =====
    story.append(Paragraph("THÔNG TIN CHUNG", st_sec))
    _ck_name = ""
    try:
        _fn = getattr(inp, "_filename", "") or ""
        if _fn:
            _ck_name = _os.path.splitext(_os.path.basename(_fn))[0].upper()
    except Exception:
        pass
    if not _ck_name and case_info:
        _ck_name = str(case_info.get("name", "")).upper()
    story.append(_tbl([
        ("Tiêu chuẩn", "TCVN 5574:2018"),
        ("Tên cấu kiện", _ck_name or "—"),
    ], W2))

    # ===== VẬT LIỆU =====
    story.append(Paragraph("VẬT LIỆU", st_sec))
    from .materials import CONCRETE_GRADES, STEEL_GRADES
    _cg = CONCRETE_GRADES.get(inp.concrete_grade)
    _sg = STEEL_GRADES.get(inp.steel_grade)
    _swg = STEEL_GRADES.get(inp.sw_steel_grade)
    _mat_rows = []
    if _cg:
        _mat_rows += [
            ("Bê tông", inp.concrete_grade),
            ("Cường độ chịu nén, Rb", f"{_cg.Rb:.0f} MPa"),
            ("Mô đun đàn hồi, Eb", f"{_cg.Eb:.0f} MPa"),
        ]
    if _sg:
        _mat_rows += [
            ("Cốt thép dọc", inp.steel_grade),
            ("Cường độ chịu kéo, Rs", f"{_sg.Rs:.0f} MPa"),
            ("Mô đun đàn hồi, Es", f"{_sg.Es:.0f} MPa"),
        ]
    if _swg:
        _mat_rows += [
            ("Cốt thép đai", inp.sw_steel_grade),
            ("Cường độ chịu cắt, Rsw", f"{_swg.Rsw:.0f} MPa"),
            ("Mô đun đàn hồi, Es", f"{_swg.Es:.0f} MPa"),
        ]
    story.append(_tbl(_mat_rows, W2))

    # ===== TIẾT DIỆN =====
    story.append(Paragraph("TIẾT DIỆN", st_sec))
    # cx = t3 (ngang), cy = t2 (đứng)
    _t3 = getattr(sec, "cx", inp.cx)
    _t2 = getattr(sec, "cy", inp.cy)
    story.append(_tbl([
        ("Chiều rộng, t3", f"{_t3:.0f} mm"),
        ("Chiều cao, t2", f"{_t2:.0f} mm"),
        ("Lớp bê tông bảo vệ, c", f"{inp.cover:.0f} mm"),
    ], W2))

    # ===== BỐ TRÍ CỐT THÉP =====
    story.append(Paragraph("BỐ TRÍ CỐT THÉP", st_sec))
    _n = len(sec.rebars)
    _cnt = Counter(r.dia for r in sec.rebars)
    _parts = [f"{_cnt[d]}-d{d:.0f}" for d in sorted(_cnt, reverse=True)]
    _mu = getattr(sec, "reinforcement_ratio", 0) or 0
    story.append(_tbl([
        ("Cốt thép dọc", " + ".join(_parts)),
        ("Hàm lượng thép dọc, μ", f"{_mu:.4f}"),
    ], W2))

    # ===== NỘI LỰC TÍNH TOÁN =====
    story.append(Paragraph("NỘI LỰC TÍNH TOÁN", st_sec))
    _story_txt, _label_txt, _combo_txt = "—", "—", "—"
    if case_info:
        _story_txt = str(case_info.get("story", "—"))
        _label_txt = str(case_info.get("label", "—"))
        _combo_txt = str(case_info.get("case", case_info.get("combo", "—")))
    _vpos = f"{_story_txt}-{_label_txt}" if _story_txt != "—" else "—"
    story.append(_tbl([
        ("Vị trí cột", _vpos),
        ("Tổ hợp tính toán", _combo_txt),
        ("Lực dọc, N", f"{res.N:.1f} kN"),
        ("Mômen quanh trục 2, M2", f"{res.Mx:.1f} kN·m"),
        ("Mômen quanh trục 3, M3", f"{res.My:.1f} kN·m"),
        ("Lực cắt theo trục 2, V2", f"{inp.Q2:.1f} kN"),
        ("Lực cắt theo trục 3, V3", f"{inp.Q3:.1f} kN"),
    ], W2))

    # ===== KẾT QUẢ TÍNH TOÁN =====
    story.append(Paragraph("KẾT QUẢ TÍNH TOÁN", st_sec))
    _alpha = _m.degrees(_m.atan2(res.Mx_star, res.My_star)) \
        if abs(res.Mx_star) + abs(res.My_star) > 1e-9 else 0.0
    _ok_txt = "ĐẠT" if res.ok else "KHÔNG ĐẠT"
    story.append(_tbl([
        ("Góc tác dụng mômen, α", f"{_alpha:.1f}°"),
        ("Điểm tải trọng A", ""),
        ("Lực dọc, N", f"{res.N:.1f} kN"),
        ("Mômen tính toán, M2*", f"{res.Mx_star:.1f} kN·m"),
        ("Mômen tính toán, M3*", f"{res.My_star:.1f} kN·m"),
        ("Tỉ số sử dụng khả năng chịu lực, D/C", f"{res.dc:.3f}"),
        ("Hệ số an toàn, FS", f"{res.fs:.2f}"),
        ("Kết luận", f"<b>{_ok_txt}</b>"),
    ], W2))

    # ===== KIỂM TRA THÉP ĐAI =====
    story.append(Paragraph("KIỂM TRA THÉP ĐAI", st_sec))
    try:
        from .stirrup import StirrupInput, check_shear
        from .sections import bar_area
        stir_in = StirrupInput(dia=inp.sw_dia, spacing=inp.sw_spacing,
                               legs=inp.sw_legs)
        _sw_txt = (f"{stir_in.legs:.0f}φ{stir_in.dia:.0f} "
                   f"a{stir_in.spacing:.0f}")
        _sw_rows = []
        _sw_ok_all = True
        for Q, lbl, b_w, h_dim in ((inp.Q2, "V2", _t2, _t3),
                                    (inp.Q3, "V3", _t3, _t2)):
            # V2: b = t2, h0 theo t3; V3: b = t3, h0 theo t2
            h0 = h_dim - inp.cover - inp.sw_dia - 12
            Asw = stir_in.legs * bar_area(stir_in.dia)
            sh = check_shear(abs(Q), b_w, max(h0, 1),
                             _cg.Rb if _cg else 0,
                             _cg.Rbt if _cg else 0,
                             Asw, _swg.Rsw if _swg else 0,
                             stir_in.spacing)
            qsw = (_swg.Rsw * Asw / stir_in.spacing) if _swg else 0
            _sw_ok_all = _sw_ok_all and sh.ok
            _sw_rows.append(dict(
                lbl=lbl, Q=Q, b=b_w, h0=h0, Asw=Asw, qsw=qsw, sh=sh))
        _r2, _r3 = _sw_rows[0], _sw_rows[1]
        _tdata = [
            ("Thép đai bố trí", _sw_txt, _sw_txt),
            ("Lực cắt tính toán, Q",
             f"{_r2['Q']:.1f} kN", f"{_r3['Q']:.1f} kN"),
            ("Kích thước tiết diện, b × h0",
             f"{_r2['b']:.0f} × {_r2['h0']:.0f} mm",
             f"{_r3['b']:.0f} × {_r3['h0']:.0f} mm"),
            ("Asw", f"{_r2['Asw']:.0f} mm²", f"{_r3['Asw']:.0f} mm²"),
            ("qsw = Rsw × Asw/s",
             f"{_r2['qsw']:.1f} N/mm", f"{_r3['qsw']:.1f} N/mm"),
            ("ĐK1: 0.3×Rb×b×h0",
             f"{_r2['sh'].Qcap1:.1f} kN", f"{_r3['sh'].Qcap1:.1f} kN"),
            ("Qb = 1.5×Rbt×b×h0²/c",
             f"{_r2['sh'].Qb_opt:.1f} kN", f"{_r3['sh'].Qb_opt:.1f} kN"),
            ("Qsw = 0.75×qsw×c",
             f"{_r2['sh'].Qsw_opt:.1f} kN", f"{_r3['sh'].Qsw_opt:.1f} kN"),
            ("c cho [Q]min",
             f"{_r2['sh'].C_opt:.0f} mm", f"{_r3['sh'].C_opt:.0f} mm"),
            ("[Q] = Qb + Qsw",
             f"{_r2['sh'].Qcap2:.1f} kN", f"{_r3['sh'].Qcap2:.1f} kN"),
            ("Kết luận",
             "ĐẠT" if _r2['sh'].ok else "KHÔNG ĐẠT",
             "ĐẠT" if _r3['sh'].ok else "KHÔNG ĐẠT"),
        ]
        story.append(_tbl3(["Thông số", "Phương V2", "Phương V3"],
                           _tdata, W3))
    except Exception as e:
        story.append(Paragraph(f"Không tính được thép đai: {e}", st_row))

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm,
                            title="Kết quả kiểm tra cột BTCT")
    doc.build(story)
    return filepath
