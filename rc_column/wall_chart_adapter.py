"""Adapter mỏng: chuyển dict kết quả vách sang đầu vào của engine
vẽ biểu đồ cột — KHÔNG vẽ gì riêng cho vách, KHÔNG tính lại.

Biểu đồ vách đi qua đúng 2 hàm vẽ của cột
(`rc_column.chart_draw.draw_nm_alpha_ax` / `draw_m2m3_ax`); adapter
chỉ đổi tên/khung dữ liệu:

- Ánh xạ đã chốt: app M2 = M_out_d (ngoài mặt phẳng),
  app M3 = M_in_d (trong mặt phẳng); A = (M_in_d, M_out_d),
  B = (Bx, By) với Bx <-> M2, By <-> M3.
- `res_ns` chỉ mang các trường 2 hàm vẽ của cột đọc:
  N, Mx_star, My_star, Bx, By, BN; `inp_ns` chỉ mang
  `concrete_model`. Mọi số đều đọc từ dict `full` đã tính 1 lần
  ở `wall_tcvn_full`, không hardcode, không tính lại D/C.
- Góc xem: khi `view_angle_deg` khác None, chỉ xoay thành phần
  mô men thiết kế (Mx', My') theo đúng ngữ nghĩa dropdown của
  cột — đường bao N–Mα đổi góc, còn điểm A/B, N, BN, D/C giữ
  nguyên (vì Bx/By/BN/N không bị xoay).
- Ghi chú A/B/O (`wall_chart_notes`) theo đúng format khối ghi
  chú cột TCVN, nhưng KHÔNG có combo: vách hiện nhập tay, chưa
  có combo nên dòng A không kèm "[...]". Góc α trong ghi chú
  luôn là góc tải của dict (`alpha_deg`), kể cả khi dropdown
  đang ở góc xem khác — handler đổi góc chỉ vẽ lại biểu đồ
  N–Mα, không vẽ lại khối ghi chú (đúng như bên cột).
"""

import math
from types import SimpleNamespace


def wall_chart_inputs(full, view_angle_deg=None):
    """Trả (sec, inp_ns, res_ns) dùng được cho cả 2 hàm vẽ cột.

    full: dict kết quả của `wall_tcvn_full`.
    view_angle_deg: None = góc tải; số độ = góc xem N–Mα mới.
    """
    sec = full["sec"]
    inp_ns = SimpleNamespace(concrete_model=full["model"])
    # Khung solver cho biểu đồ: đa giác dùng Mx_d/My_d + Bx_can/
    # By_can (khung canonical/trọng tâm mà cap đã tính); rect
    # không có các khóa này thì Mx_d = M_out_d, My_d = M_in_d
    # như cũ nên không đổi số. KHÔNG dùng M_out_d/M_in_d vật lý
    # cho đa giác C/U (ở đó M_in ↔ Mx, M_out ↔ My, đảo so với
    # phẳng) — dùng chúng sẽ vẽ điểm A/B sai khung với đường
    # bao tính từ tiết diện canonical.
    m_out = float(full.get("Mx_d", full["M_out_d"]))
    m_in = float(full.get("My_d", full["M_in_d"]))
    if view_angle_deg is None:
        mx_star, my_star = m_out, m_in
    else:
        # Quy ước ETABS như cột: M2 = Ma·sinθ, M3 = Ma·cosθ.
        ma = math.hypot(m_out, m_in)
        rad = math.radians(float(view_angle_deg))
        mx_star = ma * math.sin(rad)
        my_star = ma * math.cos(rad)
    res_ns = SimpleNamespace(
        N=float(full["N"]),
        Mx_star=mx_star,
        My_star=my_star,
        Bx=float(full.get("Bx_can", full["Bx"])),
        By=float(full.get("By_can", full["By"])),
        BN=float(full["BN"]),
    )
    return sec, inp_ns, res_ns


def wall_chart_notes(full):
    """3 dòng (text, color) theo đúng format ghi chú cột TCVN.

    Dòng 1 màu xanh lá #059669 khi ĐẠT, đỏ #DC2626 khi KHÔNG
    ĐẠT; dòng A xanh dương #2563EB; dòng B cam #EA580C.
    """
    ok = bool(full["ok"])
    dc = float(full["dc"])
    alpha = float(full["alpha_deg"])
    # Ghi chú A/B theo trục solver M2/Mx – M3/My (khớp biểu đồ):
    # đa giác dùng Mx_d/My_d, rect trùng M_out_d/M_in_d như cũ.
    m_out = float(full.get("Mx_d", full["M_out_d"]))
    m_in = float(full.get("My_d", full["M_in_d"]))
    malpha = float(full["Malpha"])
    bx = float(full.get("Bx_can", full["Bx"]))
    by = float(full.get("By_can", full["By"]))
    mb = math.hypot(bx, by)
    okt = "ĐẠT" if ok else "KHÔNG ĐẠT"
    okc = "#059669" if ok else "#DC2626"
    return [
        (f"● Đường bao kiểm tra: N-Mα (α = {alpha:.1f}°) — "
         f"TCVN 5574:2018   D/C = {dc:.3f} → {okt}", okc),
        (f"● A (điểm tải):  N = {float(full['N']):+.1f} kN,  "
         f"Mα = {malpha:.1f} kN×m  "
         f"(M2 = {m_out:.1f}, M3 = {m_in:.1f})", "#2563EB"),
        (f"◆ B (điểm giới hạn):  N = {float(full['BN']):+.1f} kN,  "
         f"Mα,u = {mb:.1f} kN×m  "
         f"(M2u = {bx:.1f}, M3u = {by:.1f})", "#EA580C"),
    ]
