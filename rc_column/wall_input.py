"""Đầu vào vách chữ nhật đặc (chế độ Vách, GĐ1).

Lát 0: chỉ mô hình dữ liệu + mặc định cho round-trip JSON chung với cột
(khóa "wall" trong dict của _collect_data). Engine tính vách (tiết diện,
N-M, vùng biên, cắt...) thuộc các lát sau — xem
THIET_KE_TICH_HOP_VACH_GD1.md §4.

Vật liệu KHÔNG nhân bản ở đây: vách đọc cùng các ô vật liệu hiện có của
3 tiêu chuẩn (TCVN: concrete/steel/sw_steel; ACI: aci_fc/aci_fy/aci_fyt;
EC2: ec2_conc/ec2_steel/ec2_phi) trong dict dữ liệu chung.
"""

from dataclasses import dataclass, fields


@dataclass
class WallInput:
    """Thông số riêng của vách chữ nhật đặc (đơn vị mm, kN, kN·m)."""

    # Hình học
    Lw: float = 2500.0          # chiều dài vách
    tw: float = 350.0           # chiều dày vách
    h_story: float = 3300.0     # chiều cao đốt giữa 2 sàn
    h_total: float = 19800.0    # tổng chiều cao vách (cho hw/Lw)
    story_pos: str = "base"     # "base" | "mid" | "top"
    cover: float = 25.0         # lớp bảo vệ tới thép phân bố
    l0_out_factor: float = 1.0  # hệ số chiều dài tính toán ngoài mặt phẳng

    # Thép phân bố (đứng: vào tiết diện N-M; ngang: chỉ cắt + cấu tạo)
    dia_v: float = 12.0
    s_v: float = 200.0
    layers_v: int = 2
    dia_h: float = 12.0
    s_h: float = 200.0
    layers_h: int = 2

    # Vùng biên (0 = không bố trí thép tập trung tại đầu đó)
    Lb_left: float = 500.0
    Lb_right: float = 500.0
    lb_auto: bool = False       # tự dùng Lb yêu cầu khi Lb bố trí thiếu (Q3)
    dia_be: float = 28.0        # đường kính thép tập trung mỗi vùng biên
    n_be: int = 8               # số thanh tập trung mỗi vùng biên
    tie_dia_be: float = 10.0    # đai vùng biên: đường kính
    tie_s_be: float = 100.0     # đai vùng biên: khoảng cách
    tie_legs_be: int = 2        # đai vùng biên: số nhánh

    # Phân loại kháng chấn
    seismic_class: str = "special"  # ACI: "special" (Ch.18) | "ordinary" (Ch.11)
    seismic_on: bool = True         # DCM 9386 / EN 1998 cho TCVN/EC2 (Q2: cho tắt)

    # Nội lực 1 tổ hợp (khi tính tay; batch pier lấy từ pier_forces)
    N: float = 0.0              # kN, nén dương
    M_in: float = 0.0           # kN·m, trong mặt phẳng (M3 của pier)
    M_out: float = 0.0          # kN·m, ngoài mặt phẳng (M2 của pier)
    V_in: float = 0.0           # kN, trong mặt phẳng (V2 của pier)
    V_out: float = 0.0          # kN, ngoài mặt phẳng (V3 của pier)
    T: float = 0.0              # kN·m — GĐ1 chỉ lưu/cảnh báo, không kiểm xoắn


def _clean(v):
    """Số nguyên dạng float (2500.0) -> int cho JSON gọn, khớp dàn ý §4.2."""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def wall_to_dict(w: WallInput) -> dict:
    """WallInput -> dict JSON (khóa "wall" trong file dữ liệu)."""
    return {f.name: _clean(getattr(w, f.name)) for f in fields(w)}


def wall_from_dict(d) -> WallInput:
    """Dict JSON -> WallInput; khóa thiếu lạ bỏ qua, thiếu khóa lấy mặc định."""
    w = WallInput()
    if not isinstance(d, dict):
        return w
    names = {f.name for f in fields(w)}
    for k, v in d.items():
        if k in names:
            setattr(w, k, v)
    return w


# Mặc định tường minh cho GUI/JSON khi chưa từng nhập vách
WALL_DEFAULTS = wall_to_dict(WallInput())
