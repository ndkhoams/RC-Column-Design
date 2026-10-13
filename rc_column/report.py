"""Sinh thuyết minh tính toán chi tiết (theo mẫu VietconSoft).

Thuyết minh gồm các mục:
 1. Số liệu đầu vào
 2. Đặc trưng vật liệu tính toán
 3. Đặc trưng tiết diện & cốt thép
 4. Chiều dài tính toán
 5. Hệ số phi_L
 6. Mô hình tính toán (NDM)
 7. Kết quả kiểm tra & kết luận
"""

import math
from typing import List

from .checker import CheckResult, ColumnInput, build_section
from .materials import EPS_B1, EPS_B2, EPS_S2
from .stability import BOUNDARY_NAMES


def _fmt(x: float, nd: int = 2) -> str:
    return f"{x:.{nd}f}"


def generate_report(inp: ColumnInput, res: CheckResult) -> str:
    sec = build_section(inp)
    conc = sec.concrete
    steel = sec.steel
    L: List[str] = []
    A = L.append

    A("=" * 64)
    A("THUYẾT MINH TÍNH TOÁN KIỂM TRA CỘT BÊ TÔNG CỐT THÉP")
    A("Tiêu chuẩn áp dụng: TCVN 5574:2018")
    A("Phương pháp: Mô hình biến dạng phi tuyến (Điều 8.1.2.7)")
    A("=" * 64)
    A("")

    # 1. Số liệu đầu vào
    A("1. SỐ LIỆU ĐẦU VÀO")
    A("-" * 64)
    A("1.1. Vật liệu")
    A(f"  - Bê tông cấp độ bền {inp.concrete_grade}: "
      f"Rb = {_fmt(conc.grade.Rb)} MPa, Rbt = {_fmt(conc.grade.Rbt)} MPa, "
      f"Eb = {conc.grade.Eb:.0f} MPa")
    A(f"  - Hệ số điều kiện làm việc bê tông γb = {_fmt(inp.gamma_b)}")
    A(f"  - Thép {inp.steel_grade}: Rs = {_fmt(steel.grade.Rs)} MPa, "
      f"Rsc = {_fmt(steel.grade.Rsc)} MPa, Es = {steel.grade.Es:.0f} MPa")
    A(f"  - Hệ số điều kiện làm việc thép γs = {_fmt(inp.gamma_s)}")
    A(f"  - Mô hình bê tông: "
      f"{'3 đoạn thẳng (parabol–chữ nhật)' if inp.concrete_model == '3line' else '2 đoạn thẳng'}")
    A("")
    A("1.2. Tiết diện")
    if inp.section_type == "rect":
        A(f"  - Tiết diện chữ nhật: Cx = {inp.cx:.0f} mm × Cy = {inp.cy:.0f} mm")
    else:
        A(f"  - Tiết diện tròn: đường kính D = {inp.cx:.0f} mm")
    A("")
    A("1.3. Cốt thép dọc")
    dias = sorted(set(r.dia for r in sec.rebars))
    dia_txt = ", ".join(f"{d:.0f}" for d in dias)
    A(f"  - Số thanh: {len(sec.rebars)} thanh (d = {dia_txt})")
    A(f"  - Tổng diện tích As = {res.steel_area:.0f} mm²")
    A(f"  - Hàm lượng μ = As/Ag = {_fmt(res.reinforcement_ratio * 100)}%")
    A("")

    # 2. Đặc trưng vật liệu tính toán
    A("2. ĐẶC TRƯNG VẬT LIỆU TÍNH TOÁN")
    A("-" * 64)
    A(f"  - Rb,tt = Rb·γb = {_fmt(conc.grade.Rb)} × {_fmt(inp.gamma_b)} "
      f"= {_fmt(conc.Rb)} MPa")
    A(f"  - Rs,tt = Rs·γs = {_fmt(steel.grade.Rs)} × {_fmt(inp.gamma_s)} "
      f"= {_fmt(steel.Rs)} MPa")
    A(f"  - Rsc,tt = {_fmt(steel.Rsc)} MPa")
    A(f"  - Biến dạng giới hạn: εb1 = {EPS_B1}, εb2 = {EPS_B2}, "
      f"εs2 = {EPS_S2}")
    A("")

    # 3. Tiết diện & cốt thép
    A("3. ĐẶC TRƯNG TIẾT DIỆN")
    A("-" * 64)
    A(f"  - Diện tích bê tông (lưới fiber): {sec.concrete_area:.0f} mm²")
    if math.isfinite(res.clear_cx):
        A(f"  - Khoảng hở thông thủy: Cx = {_fmt(res.clear_cx, 1)} mm, "
          f"Cy = {_fmt(res.clear_cy, 1)} mm")
    A("")

    # 4. Chiều dài tính toán
    A("4. CHIỀU DÀI TÍNH TOÁN")
    A("-" * 64)
    A(f"  - Phương X: L = {_fmt(inp.Lx)} m, liên kết "
      f"{BOUNDARY_NAMES.get(inp.top_x, '')}/{BOUNDARY_NAMES.get(inp.bottom_x, '')}, "
      f"L0x = {_fmt(res.L0x)} m, λx = {_fmt(res.lambda_x, 1)}")
    A(f"  - Phương Y: L = {_fmt(inp.Ly)} m, liên kết "
      f"{BOUNDARY_NAMES.get(inp.top_y, '')}/{BOUNDARY_NAMES.get(inp.bottom_y, '')}, "
      f"L0y = {_fmt(res.L0y)} m, λy = {_fmt(res.lambda_y, 1)}")
    A("")

    # 5. Hệ số phi_L
    A("5. HỆ SỐ φL (Công thức 48, TCVN 5574:2018)")
    A("-" * 64)
    if inp.long_term.has_data:
        lt = inp.long_term
        A(f"  - Tải dài hạn: Nlt = {_fmt(lt.N_lt)} kN, "
          f"Mx,lt = {_fmt(lt.Mx_lt)}, My,lt = {_fmt(lt.My_lt)} kN·m")
    else:
        A("  - Không khai báo tải dài hạn: lấy φL = 2.00 (thiên về an toàn)")
    A(f"  - Kết quả: φL = {_fmt(res.phi_L)}  (1.00 ≤ φL ≤ 2.00)")
    A("")

    # 6. Mô hình tính toán
    A("6. MÔ HÌNH TÍNH TOÁN")
    A("-" * 64)
    A("  - Giả thiết tiết diện phẳng sau biến dạng.")
    A("  - Bỏ qua khả năng chịu kéo của bê tông.")
    A("  - Quan hệ σ–ε phi tuyến theo TCVN 5574:2018.")
    A("  - Phá hoại khi bê tông vùng nén đạt biến dạng cực hạn εcu.")
    A("  - Tiết diện rời rạc thành fiber; quét góc uốn 0°–360°")
    A("    để dựng mặt tương tác N–Mx–My.")
    A("")

    # 7. Kết quả
    A("7. KIỂM TRA KHẢ NĂNG CHỊU LỰC")
    A("-" * 64)
    A(f"  - Nội lực tính toán: N = {_fmt(res.N)} kN "
      f"({'nén' if res.N >= 0 else 'kéo'}), "
      f"Mx = {_fmt(res.Mx)} kN·m, My = {_fmt(res.My)} kN·m")
    Mres = res.M_resultant
    phi = math.degrees(math.atan2(res.My, res.Mx)) if Mres > 1e-9 else 0.0
    A(f"  - Momen tổng hợp M = √(Mx² + My²) = {_fmt(Mres)} kN·m "
      f"(hướng φ = {_fmt(phi, 1)}°)")
    A(f"  - Khả năng chịu momen tại N đã cho: Mcap = {_fmt(res.M_capacity)} kN·m")
    A(f"  - Hệ số sử dụng η = M / Mcap = {_fmt(res.utilization, 3)}")
    A("")
    if res.ok:
        A("  KẾT LUẬN: ĐẠT — Tiết diện đủ khả năng chịu lực (η ≤ 1.0).")
    else:
        A("  KẾT LUẬN: KHÔNG ĐẠT — Cần tăng tiết diện hoặc hàm lượng thép (η > 1.0).")
    A("=" * 64)
    return "\n".join(L)
