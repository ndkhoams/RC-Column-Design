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

  Từ phần thống nhất biểu đồ (phần 1): logic vẽ riêng cho
  M2–M3 ĐÃ XÓA — `wall_m2m3_figure` nay nhận nguyên dict `full`
  và vẽ bằng `draw_m2m3_ax` của cột qua adapter.

"Tính 1 lần": `build_wall_m2m3` nhận `BiaxialCapacity` đã dựng sẵn
trong `wall_tcvn_full` (cùng solver fiber TCVN, cùng model vật liệu
như D/C); `wall_tcvn_full` chỉ THÊM khóa `"m2m3"` vào dict kết quả.
GUI (`gui/wall_mixin.py`) và PDF chỉ đọc dict kết quả qua adapter
(`rc_column.wall_chart_adapter`) + hàm vẽ chung của cột
(`rc_column.chart_draw.draw_m2m3_ax`), không tính lại. Dict
"m2m3" vẫn được giữ làm DỮ LIỆU (wall_detail mục 7 và caption
PDF đọc N_level/A/B từ đó), chỉ logic VẼ riêng đã xóa.
"""

import math


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


def wall_m2m3_figure(full, width_in=5.0, dpi=200) -> bytes:
    """Tạo PNG biểu đồ M2–M3 vuông cho PDF vách — bằng đúng hàm vẽ
    của cột (`chart_draw.draw_m2m3_ax`) qua adapter, không còn
    logic vẽ riêng cho vách. Nhận nguyên dict `full` (không còn
    dict `m2m3`); lát cắt vẫn tại N = BN do `draw_m2m3_ax` tự lấy
    từ `res_ns.BN`."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import io
    from .chart_draw import draw_m2m3_ax
    from .wall_chart_adapter import wall_chart_inputs
    sec, inp_ns, res_ns = wall_chart_inputs(full)
    fig, ax = plt.subplots(figsize=(width_in, width_in))
    draw_m2m3_ax(ax, sec, inp_ns, res_ns)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
