"""Hàm vẽ biểu đồ EC2 dùng chung cho tab Kết quả và tab Chi tiết.

Style COPY Y HỆT rc_column/chart_draw.py và aci_chart_draw.py (màu sắc,
legend 4 mục, font, vị trí) để 3 tiêu chuẩn hiển thị đồng nhất.
Khác biệt duy nhất là đường cong lấy từ ec2_checker (khối ứng suất
chữ nhật η·fcd, a = λ·x; không có hệ số φ — hệ số riêng phần đã nằm
trong vật liệu).
"""
import math

from .ec2_checker import ec2_interaction_curve


def ec2_signed_design_moments(ec2_res, inp):
    """Trả về (MEd2, MEd3) là mô men thiết kế ĐÃ GỒM bậc 2 và CÓ DẤU.

    Nguồn duy nhất: _ec2_calculate_full lưu MEd2_signed/MEd3_signed
    (khôi phục dấu theo mô men bậc 1 gốc, vì ec2_design_moment trả
    trị tuyệt đối). Fallback cho dict cũ: dấu(M2_orig/M3_orig) ×
    M2_mag/M3_mag; cuối cùng là mô men gốc inp.Mx/My.
    Mọi đường hiển thị điểm A/α (GUI, tóm tắt, chi tiết) đều phải
    dùng cặp này — KHÔNG dùng M2_mag/M3_mag (trị không dấu, vẽ A
    lật dấu M2) và KHÔNG dùng inp.Mx/My (mô men gốc, sai độ lớn).
    """
    er = ec2_res if isinstance(ec2_res, dict) else {}
    m2 = er.get("MEd2_signed")
    m3 = er.get("MEd3_signed")
    if m2 is None or m3 is None:
        mag2 = er.get("M2_mag")
        mag3 = er.get("M3_mag")
        org2 = er.get("M2_orig", getattr(inp, "Mx", 0) or 0)
        org3 = er.get("M3_orig", getattr(inp, "My", 0) or 0)
        if m2 is None:
            m2 = ((1.0 if org2 >= 0 else -1.0) * abs(mag2)
                  if mag2 is not None else (getattr(inp, "Mx", 0) or 0))
        if m3 is None:
            m3 = ((1.0 if org3 >= 0 else -1.0) * abs(mag3)
                  if mag3 is not None else (getattr(inp, "My", 0) or 0))
    return float(m2), float(m3)


def _design_curve(sec, conc, steel, theta_deg, n_points=48):
    """Đường cong thiết kế EC2 (hệ số riêng phần đã trong vật liệu).

    Trả về 2 list: n_dsgn (kN), m_dsgn (kN·m), sắp N giảm dần.
    Từ 2026-10-21: m_dsgn = capacity EXACT tại từng mức N (cùng nguồn
    với D/C), không còn đường cong đơn trục construction cũ.
    """
    from .ec2_checker import EC2Capacity
    cap = EC2Capacity(sec, conc, steel)
    eng = cap._exact
    n_dsgn, m_dsgn = [], []
    n_lv = 64
    for i in range(n_lv):
        N = eng.N_max + (eng.N_min - eng.N_max) * i / (n_lv - 1)
        n_dsgn.append(float(N))
        m_dsgn.append(cap.moment_capacity(float(N), theta_deg))
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


def draw_ec2_nm_alpha_ax(ax, sec, conc, steel, ec2_res,
                         N_kN, M2_kNm, M3_kNm,
                         view_angle_deg=None):
    # Biểu đồ N-Mα theo EC2 tại góc uốn xiên α
    # view_angle_deg: góc xem đường cong (None = góc tải trọng)
    # Style Y HỆT chart_draw.draw_nm_alpha_ax
    GREEN, GREEN_LT = "#059669", "#D1FAE5"
    RED, ORANGE = "#DC2626", "#F97316"
    BLUE_DASH = "#3B82F6"
    load_alpha = math.degrees(math.atan2(M2_kNm, M3_kNm))  # quy ước ETABS: đo từ trục M3
    alpha_deg = load_alpha if view_angle_deg is None else view_angle_deg
    # Từ 2026-10-21: capacity exact liên tục theo góc — vẽ đúng góc tải,
    # không snap 15° như thời checker dùng đường cong rời rạc nữa.
    alpha_snap = alpha_deg
    n_pos, m_pos = _design_curve(sec, conc, steel, alpha_snap,
                                 n_points=96)
    m_neg = [-m for m in m_pos]
    ax.plot(m_pos, n_pos, color=GREEN, linewidth=2.2, zorder=3)
    ax.plot(m_neg, n_pos, color=GREEN, linewidth=2.2, zorder=3)
    # Fill nhạt vùng trong
    ax.fill_betweenx(n_pos, 0, m_pos, color=GREEN, alpha=0.08,
                     zorder=1)
    ax.fill_betweenx(n_pos, m_neg, 0, color=GREEN, alpha=0.08,
                     zorder=1)
    Ma = math.hypot(M2_kNm, M3_kNm)
    Mb = math.hypot(ec2_res["Bx"], ec2_res["By"])
    lim = (ec2_res["BN"], Mb)
    # Nét đứt đỏ từ tâm qua A tới B (kéo dài 1.18)
    ax.plot([0, lim[1] * 1.18], [0, lim[0] * 1.18], color=RED,
            ls="--", lw=1.5, dashes=(4, 3), zorder=4)
    # Đường chiếu xanh đứt từ A xuống trục
    ax.plot([Ma, Ma], [0, N_kN], color=BLUE_DASH, ls="--",
            lw=1.2, dashes=(4, 3), alpha=0.8, zorder=2)
    ax.plot([0, Ma], [N_kN, N_kN], color=BLUE_DASH, ls="--",
            lw=1.2, dashes=(4, 3), alpha=0.8, zorder=2)
    # Điểm B (giới hạn) vẽ trước, điểm A (tải trọng) vẽ sau
    ax.scatter([lim[1]], [lim[0]], c=ORANGE, marker="D", s=70, zorder=5,
               edgecolors="white", linewidths=1.2, label="Giới hạn")
    ax.scatter([Ma], [N_kN], c=GREEN, s=70, zorder=6,
               edgecolors="white", linewidths=1.2,
               label="Điểm tải A")
    ax.text(Ma, N_kN, "  A", fontsize=9, color=GREEN,
            weight="bold", va="center", zorder=7)
    ax.text(lim[1], lim[0], "  B", fontsize=9, color=ORANGE,
            weight="bold", va="center", zorder=7)
    ax.set_xlabel(f"Mα (kN·m){'' if view_angle_deg is None else f' @ {view_angle_deg:.0f}°'}",
                fontweight="bold", fontsize=10)
    ax.set_ylabel("N (kN)", fontweight="bold", fontsize=10)
    # Chỉ hiện N >= 0 (ẩn vùng chịu kéo) — theo yêu cầu user 2026-10-16
    ax.set_ylim(bottom=0)

    # Legend 4 mục Y HỆT chart_draw, đặt dưới biểu đồ
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
    # Chỉ hiện nửa phải (Mα >= 0) có tải — theo yêu cầu user 2026-10-16
    ax.set_xlim(left=0)
    ax.grid(True, color="#E5E7EB", linestyle="--",
            linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#9CA3AF")


def draw_ec2_m2m3_ax(ax, sec, conc, steel, ec2_res,
                     N_kN, M2_kNm, M3_kNm):
    # Biểu đồ M2-M3 theo EC2 tại N = BN (lực dọc của điểm giới hạn
    # B trên tia D/C) — KHÔNG còn tại N tải như trước. Chỉ lát cắt
    # tại BN mới đi đúng qua B, vì theo định nghĩa tia D/C:
    # moment_capacity(BN, α) = |B| (cùng hướng sửa vách ở
    # rc_column/wall_m2m3.py). Điểm A vẫn là mô men thiết kế ở N
    # tải nên có thể không còn nằm trên bao mới — đúng bản chất.
    # Style Y HỆT chart_draw.draw_m2m3_ax
    BLUE, BLUE_LT = "#2563EB", "#DBEAFE"
    GREEN, RED, ORANGE = "#059669", "#DC2626", "#F97316"
    # Dựng đường bao bằng cách quét các góc 0-360° (mỗi 15°):
    # vết các trạng thái exact tại BN (cùng nguồn với D/C).
    # N_kN chỉ là fallback khi dict kết quả chưa có BN.
    _BN = N_kN
    try:
        if isinstance(ec2_res, dict) and ec2_res.get("BN") is not None:
            _v = float(ec2_res["BN"])
            if math.isfinite(_v):
                _BN = _v
    except Exception:
        pass
    from .ec2_checker import EC2Capacity
    _cap = EC2Capacity(sec, conc, steel)
    xs, ys = [], []
    for deg in range(0, 360, 15):
        Md = _cap.moment_capacity(_BN, float(deg))
        th = math.radians(deg)
        # Trục như ETABS (2026-10-22): hoành = M3, tung = M2
        xs.append(Md * math.cos(th))  # M3 = Md cosθ (trục hoành)
        ys.append(Md * math.sin(th))  # M2 = Md sinθ (trục tung)
    # Chèn điểm B đúng góc α của nó vào polyline (như vách): B là
    # điểm thật của đường cong tại BN nên việc chèn chỉ thay một
    # dây cung bằng hai dây cung qua điểm thật, không bịa số.
    _Bx = ec2_res.get("Bx", 0.0) if isinstance(ec2_res, dict) else 0.0
    _By = ec2_res.get("By", 0.0) if isinstance(ec2_res, dict) else 0.0
    if math.hypot(_Bx, _By) > 1e-12 and len(xs) >= 2:
        _alpha_b = math.degrees(math.atan2(_Bx, _By)) % 360.0
        _step = 360.0 / len(xs)
        _k = int(_alpha_b // _step)
        _nearest = min(abs(_alpha_b - _k * _step),
                       abs(_alpha_b - ((_k + 1) % len(xs)) * _step))
        if _nearest > 1e-9:
            xs.insert(_k + 1, _By)
            ys.insert(_k + 1, _Bx)
    xs.append(xs[0])
    ys.append(ys[0])
    ax.plot(xs, ys, color=BLUE, linewidth=2.2, zorder=3)
    ax.fill(xs, ys, color=BLUE, alpha=0.08, zorder=1)
    # Nét đứt đỏ từ tâm qua A tới B: (x, y) = (M3, M2)
    ax.plot([0, ec2_res["By"] * 1.18], [0, ec2_res["Bx"] * 1.18],
            color=RED, ls="--", lw=1.5, dashes=(4, 3), zorder=4)
    ax.scatter([ec2_res["By"]], [ec2_res["Bx"]], c=ORANGE, marker="D", s=70,
               zorder=5, edgecolors="white", linewidths=1.2,
               label="Giới hạn")
    ax.scatter([M3_kNm], [M2_kNm], c=GREEN, s=70,
               zorder=6, edgecolors="white", linewidths=1.2,
               label="Điểm tải A")
    ax.text(M3_kNm, M2_kNm, "  A", fontsize=9,
            color=GREEN, weight="bold", va="center", zorder=7)
    # Trục qua tâm
    ax.axhline(0, color="#6B7280", linewidth=1.0, zorder=2)
    ax.axvline(0, color="#6B7280", linewidth=1.0, zorder=2)
    ax.set_xlabel("M3 (kN·m)", fontweight="bold", fontsize=10)
    ax.set_ylabel("M2 (kN·m)", fontweight="bold", fontsize=10)
    ax.set_title(f"M2–M3 (tại N = {_BN:,.0f} kN)", fontsize=11)

    from matplotlib.lines import Line2D
    leg_elems = [
        Line2D([0], [0], color=BLUE, lw=2.2, label="Đường bao M2-M3"),
        Line2D([0], [0], color=RED, lw=1.5, ls="--", dashes=(4, 3),
               label="Tia tải O-A-B"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor=ORANGE,
               markersize=7, markeredgecolor="white", label="Điểm giới hạn B"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=GREEN,
               markersize=8, markeredgecolor="white", label="Điểm tải A"),
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


def ec2_interaction_image(sec, conc, steel, ec2_res, N_kN, M2_kNm, M3_kNm,
                          width_in=5.0, dpi=200) -> bytes:
    """Tạo PNG biểu đồ N-Mα vuông cho PDF EC2."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import io
    fig, ax = plt.subplots(figsize=(width_in, width_in))
    draw_ec2_nm_alpha_ax(ax, sec, conc, steel, ec2_res,
                         N_kN, M2_kNm, M3_kNm)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def ec2_m2m3_image(sec, conc, steel, ec2_res, N_kN, M2_kNm, M3_kNm,
                   width_in=5.0, dpi=200) -> bytes:
    """Tạo PNG biểu đồ M2-M3 vuông cho PDF EC2."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import io
    fig, ax = plt.subplots(figsize=(width_in, width_in))
    draw_ec2_m2m3_ax(ax, sec, conc, steel, ec2_res,
                     N_kN, M2_kNm, M3_kNm)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
