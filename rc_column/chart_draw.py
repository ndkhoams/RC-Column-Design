"""Hàm vẽ biểu đồ dùng chung cho tab Kết quả và tab Chi tiết.

Đảm bảo 2 tab hiển thị GIỐNG HỆT nhau (cùng code vẽ).
"""
import math
from .interaction import BiaxialCapacity, FiberSection, uniaxial_curve_fs
def draw_nm_alpha_ax(ax, sec, inp, res, fs, title_sz=12):
    # Biểu đồ N-M tại góc uốn xiên α (dùng điểm B song trục)
    # Style theo mẫu: đường xanh lá, fill nhạt, lưới đứt mảnh
    GREEN, GREEN_LT = "#059669", "#D1FAE5"
    RED, ORANGE = "#DC2626", "#F97316"
    BLUE_DASH = "#3B82F6"
    alpha_deg = math.degrees(
        math.atan2(res.Mx_star, res.My_star))  # quy ước ETABS: đo từ trục M3
    # Từ 2026-10-21: đường cong N-Mα = capacity EXACT tại các mức N
    # (cùng nguồn với D/C), không còn đường cong đơn trục construction
    _cap = BiaxialCapacity(sec, model=inp.concrete_model)
    _eng = _cap._exact
    m_pos, n_pos = [], []
    _n_lv = 64
    for _i in range(_n_lv):
        _N = _eng.N_max + (_eng.N_min - _eng.N_max) * _i / (_n_lv - 1)
        n_pos.append(float(_N))
        m_pos.append(_cap.moment_capacity(float(_N), alpha_deg))
    m_neg = [-m for m in m_pos]
    ax.plot(m_pos, n_pos, color=GREEN, linewidth=2.2, zorder=3)
    ax.plot(m_neg, n_pos, color=GREEN, linewidth=2.2, zorder=3)
    # Fill nhạt vùng trong
    ax.fill_betweenx(n_pos, 0, m_pos, color=GREEN, alpha=0.08,
                     zorder=1)
    ax.fill_betweenx(n_pos, m_neg, 0, color=GREEN, alpha=0.08,
                     zorder=1)
    Ma = math.hypot(res.Mx_star, res.My_star)
    Mb = math.hypot(res.Bx, res.By)
    lim = (res.BN, Mb)
    # Nét đứt đỏ từ tâm qua A tới B (kéo dài 1.18)
    ax.plot([0, lim[1] * 1.18], [0, lim[0] * 1.18], color=RED,
            ls="--", lw=1.5, dashes=(4, 3), zorder=4)
    # Đường chiếu xanh đứt từ A xuống trục
    ax.plot([Ma, Ma], [0, res.N], color=BLUE_DASH, ls="--",
            lw=1.2, dashes=(4, 3), alpha=0.8, zorder=2)
    ax.plot([0, Ma], [res.N, res.N], color=BLUE_DASH, ls="--",
            lw=1.2, dashes=(4, 3), alpha=0.8, zorder=2)
    # Điểm B (giới hạn) vẽ trước, điểm A (tải trọng) vẽ sau
    ax.scatter([lim[1]], [lim[0]], c=ORANGE, marker="D", s=70, zorder=5,
               edgecolors="white", linewidths=1.2, label="Giới hạn")
    ax.scatter([Ma], [res.N], c=GREEN, s=70, zorder=6,
               edgecolors="white", linewidths=1.2,
               label="Điểm tải A")
    ax.text(Ma, res.N, "  A", fontsize=9, color=GREEN,
            weight="bold", va="center", zorder=7)
    ax.text(lim[1], lim[0], "  B", fontsize=9, color=ORANGE,
            weight="bold", va="center", zorder=7)
    ax.set_xlabel("Mα (kN·m)", fontweight="bold", fontsize=10)
    ax.set_ylabel("N (kN)", fontweight="bold", fontsize=10)

    # Legend 4 mục như web, đặt dưới biểu đồ
    from matplotlib.lines import Line2D
    leg_elems = [
        Line2D([0], [0], color=GREEN, lw=2.2, label="Đường bao N-Mα"),
        Line2D([0], [0], color=RED, lw=1.5, ls="--", dashes=(4, 3),
               label="Tia tải O-A-B"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=GREEN,
               markersize=8, markeredgecolor="white", label="Điểm tải A"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor=ORANGE,
               markersize=7, markeredgecolor="white", label="Điểm giới hạn B"),
    ]
    ax.legend(handles=leg_elems, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.18), ncol=2, frameon=False)
    # Chỉ hiện nửa phải (Mα >= 0) có tải, ẩn vùng N<0 — theo yêu cầu user 2026-10-16
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    ax.grid(True, color="#E5E7EB", linestyle="--",
            linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#9CA3AF")



def draw_m2m3_ax(ax, sec, inp, res):
    # Biểu đồ M2-M3 tại N = BN (dùng điểm B song trục)
    # — KHÔNG còn tại N tải như trước. Chỉ lát cắt tại BN mới đi
    # đúng qua B, vì theo định nghĩa tia D/C:
    # moment_capacity(BN, α) = |B| (cùng hướng sửa vách ở
    # rc_column/wall_m2m3.py, head 0db783e). Điểm A vẫn là mô men
    # thiết kế ở N tải nên có thể không còn nằm trên bao mới —
    # đúng bản chất (A ở N tải, bao ở BN), không phải lỗi vẽ.
    # Style theo mẫu: đường xanh dương, fill nhạt
    # Trục như ETABS (user chốt 2026-10-22): hoành = M3, tung = M2.
    # mx_my_curve trả (M2, M3) nên x lấy p[1], y lấy p[0]; điểm A/B
    # và tia O-A-B chuyển vị tương ứng: (x, y) = (M3, M2).
    BLUE, BLUE_LT = "#2563EB", "#DBEAFE"
    GREEN, RED, ORANGE = "#059669", "#DC2626", "#F97316"
    try:
        _BN = float(getattr(res, "BN", res.N))
        if not math.isfinite(_BN):
            _BN = float(res.N)
    except Exception:
        _BN = float(res.N)
    cap = BiaxialCapacity(sec, model=inp.concrete_model, n_angles=24)
    pts = cap.mx_my_curve(_BN)
    # mx_my_curve đã khép kín (điểm cuối = điểm đầu): bỏ điểm cuối
    # để chèn B rồi khép lại, tránh trùng điểm cuối.
    _samples = pts[:-1] if len(pts) > 1 else pts
    xs = [p[1] for p in _samples]
    ys = [p[0] for p in _samples]
    # Chèn điểm B đúng góc α của nó vào polyline (như vách): B là
    # điểm thật của đường cong tại BN nên việc chèn chỉ thay một
    # dây cung bằng hai dây cung qua điểm thật, không bịa số; nhờ
    # đó B nằm đúng trên bao vẽ dù lưới quét chỉ 15°.
    _bmag = math.hypot(res.Bx, res.By)
    if _bmag > 1e-12 and len(xs) >= 2:
        _alpha_b = math.degrees(math.atan2(res.Bx, res.By)) % 360.0
        _step = 360.0 / len(xs)
        _k = int(_alpha_b // _step)
        _nearest = min(abs(_alpha_b - _k * _step),
                       abs(_alpha_b - ((_k + 1) % len(xs)) * _step))
        if _nearest > 1e-9:
            xs.insert(_k + 1, res.By)
            ys.insert(_k + 1, res.Bx)
    xs = xs + [xs[0]]
    ys = ys + [ys[0]]
    ax.plot(xs, ys, color=BLUE, linewidth=2.2, zorder=3)
    ax.fill(xs, ys, color=BLUE, alpha=0.08, zorder=1)
    # Nét đứt đỏ từ tâm qua A tới B
    ax.plot([0, res.By * 1.18], [0, res.Bx * 1.18], color=RED,
            ls="--", lw=1.5, dashes=(4, 3), zorder=4)
    ax.scatter([res.By], [res.Bx], c=ORANGE, marker="D", s=70, zorder=5,
               edgecolors="white", linewidths=1.2, label="Giới hạn")
    ax.scatter([res.My_star], [res.Mx_star], c=GREEN, s=70,
               zorder=6, edgecolors="white", linewidths=1.2,
               label="Điểm tải A")
    ax.text(res.My_star, res.Mx_star, "  A", fontsize=9,
            color=GREEN, weight="bold", va="center", zorder=7)
    # Trục qua tâm
    ax.axhline(0, color="#6B7280", linewidth=1.0, zorder=2)
    ax.axvline(0, color="#6B7280", linewidth=1.0, zorder=2)
    ax.set_xlabel("M3 (kN·m)", fontweight="bold", fontsize=10)
    ax.set_ylabel("M2 (kN·m)", fontweight="bold", fontsize=10)
    # Quyết user 2026-10-25: tiêu đề axes chỉ còn "M2–M3", KHÔNG còn
    # hậu tố "(tại N = … kN)" — chip N xanh phía trên biểu đồ (header
    # GUI) vẫn giữ nguyên và vẫn hiện BN; bao vẫn vẽ tại N = BN.
    ax.set_title("M2–M3", fontsize=11)

    from matplotlib.lines import Line2D
    leg_elems = [
        Line2D([0], [0], color=BLUE, lw=2.2, label="Đường bao M2-M3"),
        Line2D([0], [0], color=RED, lw=1.5, ls="--", dashes=(4, 3),
               label="Tia tải O-A-B"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=GREEN,
               markersize=8, markeredgecolor="white", label="Điểm tải A"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor=ORANGE,
               markersize=7, markeredgecolor="white", label="Điểm giới hạn B"),
    ]
    ax.legend(handles=leg_elems, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.18), ncol=2, frameon=False)
    ax.grid(True, color="#E5E7EB", linestyle="--",
            linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#9CA3AF")


