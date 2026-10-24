"""Biểu đồ tương tác M2–M3 cho vách TCVN (GĐ1, lát M2–M3).

Quy ước (copy từ biểu đồ M2–M3 của cột, `chart_draw.draw_m2m3_ax`):
- Trục như ETABS (user chốt 2026-10-22): hoành = M3, tung = M2.
- Đường bao #2563EB, lw 2.2, fill alpha 0.08; tia tải O–A–B nét đứt
  đỏ #DC2626 kéo dài 1.18 lần; điểm tải A tròn xanh #059669, điểm
  giới hạn B thoi cam #F97316; legend 4 mục đặt dưới biểu đồ.
- Ánh xạ vách (nhất quán `wall_engine`): M2 = M_out_d (ngoài mặt
  phẳng), M3 = M_in_d (trong mặt phẳng); Bx/By của `dc_ratio` lần
  lượt là thành phần M2/M3 của B, nên trên hình A = (M_in_d, M_out_d)
  và B = (By, Bx).

KHÁC BIỆT CÓ CHỦ Ý so với cột — mức N của đường bao:
- Cột vẽ lát cắt tại N tải (`cap.mx_my_curve(res.N)`). Tại mức đó,
  điểm B KHÔNG nằm trên đường bao: đo thực tế ca mẫu vách lệch
  18.5%, ca vùng biên 8.2%, ca cột tham chiếu 93% (khả năng chịu mô
  men thay đổi mạnh theo N ở vùng N thấp). Chỉ lát cắt tại BN — lực
  dọc của chính điểm giới hạn B trên tia — mới đi đúng qua B, vì
  theo định nghĩa tia D/C: `moment_capacity(BN, α) = |B|`.
- Vì vậy biểu đồ vách vẽ lát cắt tại N = BN và tiêu đề hình ghi rõ
  mức N đó, để không ai nhầm là lát cắt tại N tải. Mọi quy ước còn
  lại giữ y hệt cột. Mức N là tham số của `build_wall_m2m3` nên nếu
  sau này user chốt vẽ tại N tải thì chỉ đổi đối số, không đổi code vẽ.

"Tính 1 lần": `build_wall_m2m3` nhận `BiaxialCapacity` đã dựng sẵn
trong `wall_tcvn_full` (cùng solver fiber TCVN, cùng model vật liệu
như D/C); `wall_tcvn_full` chỉ THÊM khóa `"m2m3"` vào dict kết quả.
GUI (`gui/wall_mixin.py`) và PDF sau này chỉ đọc dict đó qua
`draw_wall_m2m3_ax` / `wall_m2m3_figure`, không tính lại.
"""

import math

BLUE = "#2563EB"
GREEN = "#059669"
RED = "#DC2626"
ORANGE = "#F97316"


def build_wall_m2m3(cap, n_level, a_m2, a_m3, b_m2, b_m3,
                    n_angles: int = 360):
    """Dựng dữ liệu đường bao M2–M3 tại mức lực dọc `n_level`.

    cap: BiaxialCapacity của tiết diện vách (đã dựng sẵn).
    a_m2/a_m3: mô men thiết kế tại điểm tải A (M_out_d/M_in_d).
    b_m2/b_m3: thành phần M2/M3 của điểm giới hạn B (Bx/By).
    Trả về dict: N_level, M3/M2 (2 list khép kín, thứ tự theo góc
    α từ 0° tăng dần), A_M2/A_M3, B_M2/B_M3.

    Điểm B được chèn đúng vị trí góc α của nó vào polyline (như cách
    ô N–Mα của vách chèn mức BN): B nằm trên đường cong fast theo
    định nghĩa tia D/C nên việc chèn chỉ thay một dây cung bằng hai
    dây cung đi qua điểm thật của đường cong, không bịa số. Với lưới
    1° thì sai số dây cung vốn đã ~0.004% nên chèn chỉ là đai an toàn.
    """
    m3_pts, m2_pts = [], []
    for k in range(n_angles):
        th_deg = 360.0 * k / n_angles
        m = cap.moment_capacity(float(n_level), th_deg)
        rad = math.radians(th_deg)
        m2_pts.append(m * math.sin(rad))  # M2 = M sinθ (quy ước ETABS)
        m3_pts.append(m * math.cos(rad))  # M3 = M cosθ
    # Chèn điểm B đúng góc α của tia (nếu chưa trùng mẫu lưới).
    b_mag = math.hypot(b_m2, b_m3)
    if b_mag > 1e-12:
        alpha_b = math.degrees(math.atan2(b_m2, b_m3)) % 360.0
        step = 360.0 / n_angles
        k = int(alpha_b // step)
        # Khoảng cách góc tới mẫu gần nhất; trùng mẫu thì khỏi chèn.
        nearest = min(abs(alpha_b - k * step),
                      abs(alpha_b - ((k + 1) % n_angles) * step))
        if nearest > 1e-9:
            idx = k + 1  # chèn giữa mẫu k và k+1
            m3_pts.insert(idx, b_m3)
            m2_pts.insert(idx, b_m2)
    m3_pts.append(m3_pts[0])
    m2_pts.append(m2_pts[0])
    return {
        "N_level": float(n_level),
        "M3": m3_pts,
        "M2": m2_pts,
        "A_M2": float(a_m2),
        "A_M3": float(a_m3),
        "B_M2": float(b_m2),
        "B_M3": float(b_m3),
    }


def draw_wall_m2m3_ax(ax, m2m3):
    """Vẽ biểu đồ M2–M3 lên `ax` từ dict của `build_wall_m2m3`.

    Style COPY Y HỆT `chart_draw.draw_m2m3_ax` của cột; chỉ khác
    tiêu đề ghi rõ mức N (BN) của lát cắt.
    """
    xs = m2m3["M3"]
    ys = m2m3["M2"]
    a_m3, a_m2 = m2m3["A_M3"], m2m3["A_M2"]
    b_m3, b_m2 = m2m3["B_M3"], m2m3["B_M2"]
    ax.plot(xs, ys, color=BLUE, linewidth=2.2, zorder=3)
    ax.fill(xs, ys, color=BLUE, alpha=0.08, zorder=1)
    # Nét đứt đỏ từ tâm qua A tới B (kéo dài 1.18 như cột)
    ax.plot([0, b_m3 * 1.18], [0, b_m2 * 1.18], color=RED,
            ls="--", lw=1.5, dashes=(4, 3), zorder=4)
    ax.scatter([b_m3], [b_m2], c=ORANGE, marker="D", s=70, zorder=5,
               edgecolors="white", linewidths=1.2, label="Giới hạn")
    ax.scatter([a_m3], [a_m2], c=GREEN, s=70,
               zorder=6, edgecolors="white", linewidths=1.2,
               label="Điểm tải A")
    ax.text(a_m3, a_m2, "  A", fontsize=9,
            color=GREEN, weight="bold", va="center", zorder=7)
    # Trục qua tâm
    ax.axhline(0, color="#6B7280", linewidth=1.0, zorder=2)
    ax.axvline(0, color="#6B7280", linewidth=1.0, zorder=2)
    ax.set_xlabel("M3 (kN·m)", fontweight="bold", fontsize=10)
    ax.set_ylabel("M2 (kN·m)", fontweight="bold", fontsize=10)
    ax.set_title(f"M2–M3 (tại N = {m2m3['N_level']:,.0f} kN)",
                 fontsize=11)

    from matplotlib.lines import Line2D
    leg_elems = [
        Line2D([0], [0], color=BLUE, lw=2.2, label="Đường bao M2-M3"),
        Line2D([0], [0], color=RED, lw=1.5, ls="--", dashes=(4, 3),
               label="Tia tải O-A-B"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=GREEN,
               markersize=8, markeredgecolor="white", label="Điểm tải A"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor=ORANGE,
               markersize=7, markeredgecolor="white",
               label="Điểm giới hạn B"),
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


def wall_m2m3_figure(m2m3, width_in=5.0, dpi=200) -> bytes:
    """Tạo PNG biểu đồ M2–M3 vuông cho PDF vách (dùng chung hàm vẽ
    với GUI — cùng `draw_wall_m2m3_ax`, kiểu `aci_m2m3_image`)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import io
    fig, ax = plt.subplots(figsize=(width_in, width_in))
    draw_wall_m2m3_ax(ax, m2m3)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
