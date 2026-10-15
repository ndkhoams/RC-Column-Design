"""Hàm vẽ biểu đồ ACI 318-19 dùng chung cho tab Kết quả và tab Chi tiết.

Style COPY Y HỆT rc_column/chart_draw.py (màu sắc, legend 4 mục, font,
vị trí) để 2 tiêu chuẩn hiển thị đồng nhất. Khác biệt duy nhất là
đường cong lấy từ aci_checker (khối ứng suất chữ nhật 0.85f'c,
đã nhân hệ số φ theo từng điểm).
"""
import math

from .aci_checker import aci_interaction_curve


def _design_curve(sec, conc, steel, theta_deg, tied=True, n_points=48):
    """Đường cong thiết kế (đã nhân φ từng điểm), sắp N giảm dần.

    Trả về 2 list: n_dsgn (kN), m_dsgn (kN·m).
    """
    nom = aci_interaction_curve(sec, conc, steel, theta_deg,
                                n_points=n_points, tied=tied)
    pts = [(N * phi, M * phi) for (N, M, _eps_t, phi) in nom]
    pts.sort(key=lambda p: -p[0])
    n_dsgn = [p[0] for p in pts]
    m_dsgn = [p[1] for p in pts]
    return n_dsgn, m_dsgn


def _interp_M_at_N(n_list, m_list, N):
    """Nội suy tuyến tính M tại N trên đường cong (n_list giảm dần)."""
    if not n_list:
        return 0.0
    if N >= n_list[0]:
        return m_list[0]
    if N <= n_list[-1]:
        return m_list[-1]
    for i in range(len(n_list) - 1):
        n1, n2 = n_list[i], n_list[i + 1]
        if n2 <= N <= n1:
            t = (N - n1) / (n2 - n1) if abs(n2 - n1) > 1e-12 else 0.0
            return m_list[i] + t * (m_list[i + 1] - m_list[i])
    return 0.0


def draw_aci_nm_alpha_ax(ax, sec, conc, steel, aci_res,
                         N_kN, M2_kNm, M3_kNm, tied=True):
    # Biểu đồ N-Mα theo ACI 318-19 tại góc uốn xiên α
    # Style Y HỆT chart_draw.draw_nm_alpha_ax
    GREEN, GREEN_LT = "#059669", "#D1FAE5"
    RED, ORANGE = "#DC2626", "#F97316"
    BLUE_DASH = "#3B82F6"
    alpha_deg = math.degrees(math.atan2(M3_kNm, M2_kNm))
    n_pos, m_pos = _design_curve(sec, conc, steel, alpha_deg, tied=tied)
    m_neg = [-m for m in m_pos]
    ax.plot(m_pos, n_pos, color=GREEN, linewidth=2.2, zorder=3)
    ax.plot(m_neg, n_pos, color=GREEN, linewidth=2.2, zorder=3)
    # Fill nhạt vùng trong
    ax.fill_betweenx(n_pos, 0, m_pos, color=GREEN, alpha=0.08,
                     zorder=1)
    ax.fill_betweenx(n_pos, m_neg, 0, color=GREEN, alpha=0.08,
                     zorder=1)
    Ma = math.hypot(M2_kNm, M3_kNm)
    Mb = math.hypot(aci_res["Bx"], aci_res["By"])
    lim = (aci_res["BN"], Mb)
    # Nét đứt đỏ từ tâm qua A tới B (kéo dài 1.18)
    ax.plot([0, lim[1] * 1.18], [0, lim[0] * 1.18], color=RED,
            ls="--", lw=1.5, dashes=(4, 3), zorder=4)
    # Đường chiếu xanh đứt từ A xuống trục
    ax.plot([Ma, Ma], [0, N_kN], color=BLUE_DASH, ls="--",
            lw=1.2, dashes=(4, 3), alpha=0.8, zorder=2)
    ax.plot([0, Ma], [N_kN, N_kN], color=BLUE_DASH, ls="--",
            lw=1.2, dashes=(4, 3), alpha=0.8, zorder=2)
    # Điểm B (giới hạn) vẽ trước, điểm A (tải trọng) vẽ sau
    ax.scatter([lim[1]], [lim[0]], c=ORANGE, s=70, zorder=5,
               edgecolors="white", linewidths=1.2, label="Giới hạn")
    ax.scatter([Ma], [N_kN], c=GREEN, s=70, zorder=6,
               edgecolors="white", linewidths=1.2,
               label="Điểm tải A")
    ax.text(Ma, N_kN, "  A", fontsize=9, color=GREEN,
            weight="bold", va="center", zorder=7)
    ax.text(lim[1], lim[0], "  B", fontsize=9, color=ORANGE,
            weight="bold", va="center", zorder=7)
    ax.set_xlabel("Mα (kN·m)", fontweight="bold", fontsize=10)
    ax.set_ylabel("N (kN)", fontweight="bold", fontsize=10)

    # Legend 4 mục Y HỆT chart_draw, đặt dưới biểu đồ
    from matplotlib.lines import Line2D
    leg_elems = [
        Line2D([0], [0], color=GREEN, lw=2.2, label="Đường bao N-Mα"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=GREEN,
               markersize=8, markeredgecolor="white", label="Điểm tải A"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor=ORANGE,
               markersize=7, markeredgecolor="white", label="Điểm giới hạn B"),
        Line2D([0], [0], color=RED, lw=1.5, ls="--", dashes=(4, 3),
               label="Tia tải O-A-B"),
    ]
    ax.legend(handles=leg_elems, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.18), ncol=4, frameon=False)
    ax.grid(True, color="#E5E7EB", linestyle="--",
            linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#9CA3AF")


def draw_aci_m2m3_ax(ax, sec, conc, steel, aci_res,
                     N_kN, M2_kNm, M3_kNm, tied=True):
    # Biểu đồ M2-M3 theo ACI 318-19 tại N cố định
    # Style Y HỆT chart_draw.draw_m2m3_ax
    BLUE, BLUE_LT = "#2563EB", "#DBEAFE"
    GREEN, RED, ORANGE = "#059669", "#DC2626", "#F97316"
    # Dựng đường bao bằng cách quét các góc 0-360° (mỗi 15°),
    # nội suy M thiết kế tại N_kN rồi chiếu lên (M2, M3)
    xs, ys = [], []
    for deg in range(0, 360, 15):
        n_d, m_d = _design_curve(sec, conc, steel, float(deg),
                                tied=tied, n_points=36)
        Md = _interp_M_at_N(n_d, m_d, N_kN)
        th = math.radians(deg)
        xs.append(Md * math.cos(th))
        ys.append(Md * math.sin(th))
    xs.append(xs[0])
    ys.append(ys[0])
    ax.plot(xs, ys, color=BLUE, linewidth=2.2, zorder=3)
    ax.fill(xs, ys, color=BLUE, alpha=0.08, zorder=1)
    # Nét đứt đỏ từ tâm qua A tới B
    ax.plot([0, aci_res["Bx"] * 1.18], [0, aci_res["By"] * 1.18],
            color=RED, ls="--", lw=1.5, dashes=(4, 3), zorder=4)
    ax.scatter([aci_res["Bx"]], [aci_res["By"]], c=ORANGE, s=70,
               zorder=5, edgecolors="white", linewidths=1.2,
               label="Giới hạn")
    ax.scatter([M2_kNm], [M3_kNm], c=GREEN, s=70,
               zorder=6, edgecolors="white", linewidths=1.2,
               label="Điểm tải A")
    ax.text(M2_kNm, M3_kNm, "  A", fontsize=9,
            color=GREEN, weight="bold", va="center", zorder=7)
    # Trục qua tâm
    ax.axhline(0, color="#6B7280", linewidth=1.0, zorder=2)
    ax.axvline(0, color="#6B7280", linewidth=1.0, zorder=2)
    ax.set_xlabel("M2 (kN·m)", fontweight="bold", fontsize=10)
    ax.set_ylabel("M3 (kN·m)", fontweight="bold", fontsize=10)

    from matplotlib.lines import Line2D
    leg_elems = [
        Line2D([0], [0], color=BLUE, lw=2.2, label="Đường bao M2-M3"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=GREEN,
               markersize=8, markeredgecolor="white", label="Điểm tải A"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor=ORANGE,
               markersize=7, markeredgecolor="white", label="Điểm giới hạn B"),
        Line2D([0], [0], color=RED, lw=1.5, ls="--", dashes=(4, 3),
               label="Tia tải O-A-B"),
    ]
    ax.legend(handles=leg_elems, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.22), ncol=4, frameon=False)
    ax.grid(True, color="#E5E7EB", linestyle="--",
            linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#9CA3AF")
