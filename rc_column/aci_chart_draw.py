"""Hàm vẽ biểu đồ ACI 318-19 dùng chung cho tab Kết quả và tab Chi tiết.

Style COPY Y HỆT rc_column/chart_draw.py (màu sắc, legend 4 mục, font,
vị trí) để 2 tiêu chuẩn hiển thị đồng nhất. Khác biệt duy nhất là
đường cong lấy từ aci_checker (khối ứng suất chữ nhật 0.85f'c,
đã nhân hệ số φ theo từng điểm).
"""
import math

from .aci_checker import aci_interaction_curve
from .aci_materials import PHI_SPIRAL, PHI_TIED, max_axial_phi


def _design_curve(sec, conc, steel, theta_deg, tied=True, n_points=48):
    """Đường cong thiết kế (đã nhân φ từng điểm), sắp N giảm dần.

    Trả về 2 list: n_dsgn (kN), m_dsgn (kN·m).
    Từ 2026-10-21: m_dsgn = capacity EXACT tại từng mức N (cùng nguồn
    với D/C), không còn đường cong đơn trục construction cũ.
    """
    from .aci_checker import ACICapacity
    cap = ACICapacity(sec, conc, steel, tied=tied)
    eng = cap._exact
    n_dsgn, m_dsgn = [], []
    n_lv = 64
    for i in range(n_lv):
        N = eng.N_max + (eng.N_min - eng.N_max) * i / (n_lv - 1)
        n_dsgn.append(float(N))
        m_dsgn.append(cap.moment_capacity(float(N), theta_deg))
    _fix_cap_top(cap, eng, n_dsgn, m_dsgn, theta_deg)
    # Vẽ đoạn NGANG cap phi*Pn,max từ M=0 tới điểm cắt cap (đầu cong),
    # như ETABS/CSiCol trình bày: đường bao thiết kế phải KHÉP tại
    # N = N_cap. Thiếu điểm này, nét vẽ bắt đầu lơ lửng tại điểm cắt
    # cap (M > 0) và vùng cap chỉ được đóng bởi mép fill rất nhạt —
    # trông như đầu cong chưa kết thúc / vượt cap. Thuần hiển thị:
    # chỉ thêm điểm (0, N_cap) khi đỉnh polyline đúng là mặt cap.
    if n_dsgn and m_dsgn[0] > 0.0 \
            and abs(n_dsgn[0] - cap.N_cap) <= 1e-6 * max(1.0, abs(cap.N_cap)):
        n_dsgn.insert(0, n_dsgn[0])
        m_dsgn.insert(0, 0.0)
    return n_dsgn, m_dsgn


def _fix_cap_top(cap, eng, n_dsgn, m_dsgn, theta_deg):
    """Sửa đoạn đỉnh cap phi*Pn,max của polyline HIỂN THỊ (chỉ vẽ,
    không đụng bất kỳ đường tính nào — D/C không đi qua hàm này).

    Cơ chế lỗi: trong mỗi sweep gamma của engine, mọi trạng thái bị
    kẹp N tại N_cap (plateau phi*Nn >= N_cap, M chạy từ 0 tới M của
    trạng thái cắt cap) đều sụp về một điểm neo duy nhất (N_cap, M=0)
    sau bước lọc N giảm nghiêm ngặt. Tại các mức N nằm giữa N_cap và
    điểm thứ hai của sweep (điểm đầu tiên không bị kẹp), capacity_fast
    nội suy theo dây cung về điểm neo (N_cap, 0) nên M bị kéo thấp và
    mất đơn điệu — sinh đoạn "móc" zíc-zắc ở đầu cong (đo thực tế ca
    600x600 f'c=30: mức ngay dưới cap fast = 203.2 trong khi fine =
    405.2; mức tại cap fast = 306.6, fine = 376.4). Các mức tại/dưới
    điểm thứ hai của MỌI sweep đều không bị ảnh hưởng.

    Cách sửa: điểm đỉnh lấy capacity FINE tại N = N_cap — đúng trạng
    thái cắt cap (phi*Nn = N_cap theo chiều cắt, là đầu mút của đoạn
    ngang cap như ETABS/CSiCol trình bày). Các mức còn nằm trong vùng
    sụp (N lớn hơn điểm thứ hai nhỏ nhất của các sweep) được đối chiếu
    với đường giàn nội suy giữa điểm đỉnh fine và mức sạch đầu tiên
    bên dưới: mức nào lệch khỏi đường giàn quá 3% (dấu hiệu bị dây
    cung neo kéo — đo thực tế -49% và -7%) thì thay bằng capacity
    fine tại chính mức đó; mức nào khớp đường giàn thì giữ nguyên giá
    trị fast (vốn chỉ lệch fine ~0.5% như phần còn lại của đường
    cong). Cuối cùng ép đơn điệu tăng dần trong vùng sửa để không bao
    giờ còn điểm gấp ngược. Nếu mức sạch đầu tiên không cao hơn điểm
    đỉnh (hiếm), lấy capacity fine tại chính mức đó làm neo dưới.
    """
    if len(n_dsgn) < 3:
        return
    # Chỉ áp dụng khi đỉnh polyline đúng là mặt cap của engine
    if abs(n_dsgn[0] - cap.N_cap) > 1e-6 * max(1.0, abs(cap.N_cap)):
        return
    n2 = [sw["N"][1] for sw in eng.sweeps if len(sw["N"]) > 1]
    if not n2:
        return
    n2_min = min(n2)
    j = None
    for i in range(1, len(n_dsgn)):
        if n_dsgn[i] <= n2_min:
            j = i
            break
    if j is None:
        return
    m_top = cap.exact_capacity(n_dsgn[0], theta_deg)
    if m_top <= 0.0:
        return
    if j == 1:
        # Không có mức trung gian trong vùng sụp: chỉ thay điểm đỉnh
        m_dsgn[0] = m_top
        return
    m_bot = m_dsgn[j]
    if m_bot <= m_top:
        m_bot = cap.exact_capacity(n_dsgn[j], theta_deg)
        if m_bot <= m_top:
            return  # Hình dạng bất thường: giữ nguyên như cũ
        m_dsgn[j] = m_bot
    n_top, n_bot = n_dsgn[0], n_dsgn[j]
    m_dsgn[0] = m_top
    for i in range(1, j):
        t = (n_top - n_dsgn[i]) / (n_top - n_bot)
        m_scaf = m_top + t * (m_bot - m_top)
        if abs(m_dsgn[i] - m_scaf) > 0.03 * max(m_scaf, 1e-9):
            m_fine = cap.exact_capacity(n_dsgn[i], theta_deg)
            if m_fine > 0.0:
                m_dsgn[i] = m_fine
    # Ép đơn điệu trong vùng sửa (điểm gấp ngược không được quay lại)
    for i in range(1, j + 1):
        if m_dsgn[i] < m_dsgn[i - 1]:
            m_dsgn[i] = m_dsgn[i - 1]


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
                         N_kN, M2_kNm, M3_kNm, tied=True,
                         view_angle_deg=None):
    # Biểu đồ N-Mα theo ACI 318-19 tại góc uốn xiên α
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
    n_pos, m_pos = _design_curve(sec, conc, steel, alpha_snap, tied=tied,
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
    # Hiển thị nốt phần N < 0 (kéo) tới kéo thuần — theo yêu cầu user
    # 2026-10-29 (trước đây set_ylim(bottom=0) ẩn vùng kéo dù đường
    # cong đã sinh tới N_min). Chỉ đổi hiển thị, không đổi số.
    _n_lo = min(min(n_pos), float(N_kN), 0.0)
    if _n_lo < 0:
        _span = max(n_pos) - _n_lo
        ax.set_ylim(bottom=_n_lo - 0.03 * _span)
    else:
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
    # 2026-10-29: nét trục ngang N = 0 (như chart_draw): xám đậm,
    # liền, lw 1.4, zorder 2.5 — trên fill/lưới, dưới bao/tia/A/B.
    ax.axhline(0, color="#374151", linewidth=1.4, zorder=2.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#9CA3AF")


def draw_aci_m2m3_ax(ax, sec, conc, steel, aci_res,
                     N_kN, M2_kNm, M3_kNm, tied=True):
    # Biểu đồ M2-M3 theo ACI 318-19 tại N = BN (lực dọc của điểm
    # giới hạn B trên tia D/C) — KHÔNG còn tại N tải như trước.
    # Chỉ lát cắt tại BN mới đi đúng qua B, vì theo định nghĩa tia
    # D/C: moment_capacity(BN, α) = |B| (cùng hướng sửa vách ở
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
        if isinstance(aci_res, dict) and aci_res.get("BN") is not None:
            _v = float(aci_res["BN"])
            if math.isfinite(_v):
                _BN = _v
    except Exception:
        pass
    from .aci_checker import ACICapacity
    _cap = ACICapacity(sec, conc, steel, tied=tied)
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
    _Bx = aci_res.get("Bx", 0.0) if isinstance(aci_res, dict) else 0.0
    _By = aci_res.get("By", 0.0) if isinstance(aci_res, dict) else 0.0
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
    ax.plot([0, aci_res["By"] * 1.18], [0, aci_res["Bx"] * 1.18],
            color=RED, ls="--", lw=1.5, dashes=(4, 3), zorder=4)
    ax.scatter([aci_res["By"]], [aci_res["Bx"]], c=ORANGE, marker="D", s=70,
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
    # Quyết user 2026-10-25: KHÔNG còn tiêu đề trong axes của biểu đồ
    # M2–M3 (đã bỏ hậu tố "(tại N = …)" ở 19b36c6, nay bỏ nốt "M2–M3").
    # Header ngoài "Mặt cắt M2–M3" + chip N xanh phía trên biểu đồ vẫn
    # giữ nguyên và vẫn hiện BN; bao vẫn vẽ tại N = BN.

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


def aci_interaction_image(sec, conc, steel, aci_res, N_kN, M2_kNm, M3_kNm,
                          tied=True, width_in=5.0, dpi=200) -> bytes:
    """Tạo PNG biểu đồ N-Mα vuông cho PDF ACI."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import io
    fig, ax = plt.subplots(figsize=(width_in, width_in))
    draw_aci_nm_alpha_ax(ax, sec, conc, steel, aci_res,
                         N_kN, M2_kNm, M3_kNm, tied=tied)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def aci_m2m3_image(sec, conc, steel, aci_res, N_kN, M2_kNm, M3_kNm,
                   tied=True, width_in=5.0, dpi=200) -> bytes:
    """Tạo PNG biểu đồ M2-M3 vuông cho PDF ACI."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import io
    fig, ax = plt.subplots(figsize=(width_in, width_in))
    draw_aci_m2m3_ax(ax, sec, conc, steel, aci_res,
                     N_kN, M2_kNm, M3_kNm, tied=tied)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
