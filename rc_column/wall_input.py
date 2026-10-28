"""Đầu vào vách chữ nhật đặc (chế độ Vách, GĐ1).

Lát 0: chỉ mô hình dữ liệu + mặc định cho round-trip JSON chung với cột
(khóa "wall" trong dict của _collect_data). Engine tính vách (tiết diện,
N-M, vùng biên, cắt...) thuộc các lát sau — xem
THIET_KE_TICH_HOP_VACH_GD1.md §4.

Từ 2026-10-23: mục 2/3/4 của panel vách theo format công cụ web
Vietcons "Kiểm tra vách BTCT" (TCVN 5574:2018):
- Mục 2: loại tiết diện (GĐ1 chỉ "Vách phẳng chữ nhật" hoạt động) +
  xoay tiết diện theo chu kỳ 0/90/180/270 (90/270 hoán đổi vai trò
  Lw/tw khi dựng hình và tính toán — xem wall_section.wall_dims).
- Mục 3: 2 chế độ thép dọc — "perimeter" (phân bố đều theo chu vi)
  và "boundary" (tập trung vùng biên 2 đầu + thép phân bố thân vách).
- Mục 4: phương pháp P–δ ("tcvn" | "none") + bảng 2 phương X (trong
  mặt phẳng, theo Lw) / Y (ngoài mặt phẳng, theo tw): L, liên kết 2
  đầu, ψ (tự điền theo LK, sửa tay được); L0 = ψ·L chỉ suy ra lúc tính,
  không lưu/không ghi ngược (đúng quy tắc L của app).
Các khóa cũ (h_story, l0_out_factor, dia_v, Lb_left...) GIỮ để tương
thích ngược; file JSON cũ thiếu khóa mới được dịch sang format mới
bằng normalize_wall_dict (giữ nguyên L0 ngoài mặt phẳng cũ).

Vật liệu KHÔNG nhân bản ở đây: vách đọc cùng các ô vật liệu hiện có của
3 tiêu chuẩn (TCVN: concrete/steel/sw_steel; ACI: aci_fc/aci_fy/aci_fyt;
EC2: ec2_conc/ec2_steel/ec2_phi) trong dict dữ liệu chung — NGOẠI TRỪ
cấp thép ngang của vách (``sw_steel_grade`` dưới đây): đây là ô nhập
RIÊNG của vách (phần 3/7, 2026-10-24), vì cắt trong mặt phẳng của vách
không dùng ô "Cấp độ bền thép đai" của cột. Thép dọc vách vẫn lấy từ
ô thép dọc dùng chung (cb_steel).
"""

import math
from dataclasses import dataclass, field, fields
from typing import Optional


@dataclass
class WallInput:
    """Thông số riêng của vách chữ nhật đặc (đơn vị mm, kN, kN·m)."""

    # Hình học
    Lw: float = 2500.0          # chiều dài vách
    tw: float = 350.0           # chiều dày vách
    h_story: float = 3300.0     # chiều cao đốt giữa 2 sàn
    h_total: float = 19800.0    # tổng chiều cao vách (cho hw/Lw)
    story_pos: str = "base"     # "base" | "mid" | "top"
    cover: float = 25.0         # lớp bảo vệ cốt đai c (mm, tới mặt ngoài thép ngang dia_h);
                                # lớp bảo vệ cốt dọc do engine tự tính: c_dọc = c + dia_h
    l0_out_factor: float = 1.0  # hệ số chiều dài tính toán ngoài mặt phẳng

    # Thép phân bố (đứng: vào tiết diện N-M; ngang: chỉ cắt + cấu tạo)
    dia_v: float = 12.0
    s_v: float = 200.0
    layers_v: int = 2
    dia_h: float = 12.0
    s_h: float = 200.0
    layers_h: int = 2
    # Cấp thép ngang RIÊNG của vách (phần 3/7, 2026-10-24): quyết định
    # Rsw cho kiểm tra cắt trong mặt phẳng (wall_shear), thay cho cấp
    # thép dọc. None = CHƯA ĐẶT (file JSON cũ không có khóa này) ->
    # engine fallback về cấp thép dọc để kết quả cũ tái hiện từng chữ
    # số. File mới/GUI luôn ghi cấp tường minh (mặc định GUI: CB400-V,
    # theo quy ước ô thép đai của cột); KHÔNG điền mặc định ở đây hay
    # ở normalize_wall_dict, vì điền CB400-V sẽ làm lệch file cũ có
    # thép dọc CB500-V (Rsw 300 -> 280).
    sw_steel_grade: Optional[str] = None

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

    # --- Tải dài hạn cho φl vách (2026-10-28, quyết sau đối chiếu
    # Hướng dẫn BXD QĐ 862 §5.1.2 (5-31)): nhập tay ở mục 4, dùng
    # cho đường nhập tay TCVN; batch ETABS vách (chưa có trong
    # cây này) giữ φl mặc định 2,0 cho tới khi có dữ liệu dài hạn
    # riêng. Cả 3 số đều 0 (mặc định / file cũ thiếu khóa) → coi
    # như không nhập → φl = 2,0, số cũ không đổi.
    N_lt: float = 0.0           # kN, lực dọc dài hạn, nén dương
    M_in_lt: float = 0.0        # kN·m, mô men dài hạn trong MP
    M_out_lt: float = 0.0       # kN·m, mô men dài hạn ngoài MP

    # --- Mục 2 theo format web (2026-10-23) ---
    section_type: str = "rect"  # "rect" | "barbell" | "tee" | "ell"
                                # | "c-core" | "u-core" | "dxf" (lát
                                # DXF, 2026-10-28: tiết diện bất kỳ
                                # import từ file .dxf, xem 4 khóa dưới)
    rot_deg: int = 0            # xoay tiết diện: 0 | 90 | 180 | 270

    # --- Tiết diện bất kỳ import từ DXF (lát DXF, 2026-10-28) ---
    # Tọa độ GỐC BẢN VẼ (chưa trừ trọng tâm): build_wall_section
    # trừ trọng tâm outline mỗi lần dựng (như đường import DXF của
    # cột) nên JSON round-trip giữ nguyên tọa độ gốc — không ghi
    # ngược tọa độ đã trừ trọng tâm vào đây hay vào ô nhập.
    # dxf_poly: outline bê tông, list [x, y]; dxf_holes: list các
    # polygon lỗ, mỗi lỗ là list [x, y]; dxf_bars: list [x, y, dia];
    # dxf_file: chỉ basename file DXF (không lưu full path).
    # File cũ thiếu 4 khóa này vẫn mở bình thường (mặc định rỗng);
    # wall_to_dict giữ nguyên list lồng nhau (không làm tròn,
    # không _clean list) nhờ _clean chỉ đổi float nguyên thành int.
    dxf_poly: list = field(default_factory=list)
    dxf_holes: list = field(default_factory=list)
    dxf_bars: list = field(default_factory=list)
    dxf_file: str = ""

    # --- Kích thước riêng cho 5 loại mới (lát 1, mặc định web) ---
    # Barbell: Lw = tổng dài, tw = dày thân, Bf/Tf = rộng/dài đầu mở
    # rộng (Tf đo theo chiều vách). Tee: Lw = chiều dài thân + t,
    # Bf = rộng cánh, t = dày chung. Ell: L1/L2 = 2 cạnh, t = dày
    # chung. C/U: Lw = chiều dài thân, t = dày chung, Bf = dài cánh,
    # Lr = dài hồi (chỉ C). sec_sym=True -> 1 cặp (2 bên bằng nhau);
    # False -> cặp 1/2 riêng. File cũ thiếu các khóa này -> mặc định
    # dưới đây (vách phẳng không dùng chúng nên số cũ không đổi).
    sec_bf: float = 1000.0      # Barbell Bf / Tee Bf / C-U Bf
    sec_tf: float = 450.0       # Barbell Tf
    sec_bf2: float = 1000.0     # Barbell Bf2 / C-U Bf2 (khi không đối xứng)
    sec_tf2: float = 450.0      # Barbell Tf2
    sec_lr: float = 600.0       # C Lr
    sec_lr2: float = 600.0      # C Lr2
    sec_L1: float = 2000.0      # Ell L1
    sec_L2: float = 1800.0      # Ell L2
    sec_t: float = 300.0        # Tee/Ell/C/U: dày chung t
    sec_sym: bool = True        # Đối xứng (Barbell/C/U)

    # --- Mục 3 theo format web: chế độ bố trí thép dọc ---
    steel_mode: str = "perimeter"   # "perimeter" | "boundary"
    # (a) Phân bố đều theo chu vi
    per_dia: float = 12.0       # đường kính d
    per_s: float = 200.0        # khoảng cách s (bước thực <= s)
    # (b) Tập trung vùng biên (đối xứng 2 đầu) + thép phân bố thân vách
    # LEGACY (format panel cũ, generator mới không dùng — chỉ giữ để
    # file cũ vẫn parse + mirror khi lưu): be_layout/be_nL/be_nT.
    be_layout: str = "chuvi"    # "chuvi" | "grid" (GĐ1: sinh cùng lưới)
    be_Lb: float = 500.0        # chiều dài vùng biên mỗi đầu (mm)
    be_dia: float = 20.0        # đường kính db vùng biên
    be_nL: int = 4              # số vị trí dọc trong Lb (cũ)
    be_nT: int = 2              # số hàng ngang theo tw (cũ, 2 = 2 mặt)
    # Mô hình vùng biên cột dọc (2026-10-25, user chốt, thay mô hình
    # hàng ngang 950b4d5): 6 ô nhập, nhập 1 bên áp y hệt 2 đầu.
    # Mỗi vùng: 2 hàng dọc Lb (trên + dưới, mỗi hàng n_Lb thanh tính
    # cả 2 góc ở 2 đầu hàng) + mỗi lớp (cột dọc theo tw: L_out cột
    # ngoài đếm từ đầu ngoài vào, L_in cột trong neo ở hàng trong
    # cùng đếm đi ra — user chốt 2026-10-25, sửa bản 9eac50e6 đặt
    # lớp trong kề sau lớp ngoài) đóng góp n_tw thanh Ở GIỮA
    # (không tính 2 hàng — thanh trên/dưới của cột TRÙNG thanh của
    # 2 hàng nên không đếm thêm, không sinh trùng).
    # Tổng/vùng = 2*n_Lb + n_tw*(L_out + L_in); L_out + L_in <= n_Lb.
    be_n_Lb: int = 4            # số thanh theo chiều Lb (tính cả 2 góc)
    be_n_tw: int = 2            # số thanh Ở GIỮA theo chiều tw / cột
    be_L_out: int = 1           # số lớp tw ngoài — TỔNG số cột ngoài
    be_L_in: int = 0            # số lớp tw trong — số cột trong cùng
                                # (đếm từ hàng trong cùng đi ra)
    web_dia: float = 12.0       # thép phân bố thân vách: đường kính
    web_s: float = 200.0        # thép phân bố thân vách: khoảng cách

    # --- Mục 4 theo format web: chiều dài tính toán & uốn dọc ---
    # Phương X = trong mặt phẳng (theo Lw); Phương Y = ngoài mặt phẳng
    # (theo tw) — khẳng định bằng độ mảnh của web: λx = 6.4 (quán tính
    # trong mặt phẳng), λy = 45.5 (ngoài mặt phẳng) ở ca mẫu.
    pd_method: str = "tcvn"     # "tcvn" | "none" (η = 1 hai phương)
    Lx_m: float = 5.75          # chiều cao thông thủy phương X (m)
    psi_x: float = 0.8          # hệ số ψ phương X (tự điền theo LK)
    lk_top_x: str = "ngam_nua_cung"
    lk_bot_x: str = "ngam_nua_cung"
    Ly_m: float = 5.75          # chiều cao thông thủy phương Y (m)
    psi_y: float = 0.8          # hệ số ψ phương Y (tự điền theo LK)
    lk_top_y: str = "ngam_nua_cung"
    lk_bot_y: str = "ngam_nua_cung"


def _clean(v):
    """Số nguyên dạng float (2500.0) -> int cho JSON gọn, khớp dàn ý §4.2."""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def wall_to_dict(w: WallInput) -> dict:
    """WallInput -> dict JSON (khóa "wall" trong file dữ liệu)."""
    return {f.name: _clean(getattr(w, f.name)) for f in fields(w)}


def normalize_wall_dict(d) -> dict:
    """Điền/dịch khóa format web (2026-10-23) cho dict vách bất kỳ.

    File JSON cũ (lát 0–1.5) không có các khóa mới -> dịch từ khóa cũ,
    GIỮ NGUYÊN hành vi số học cũ ở mức tối đa:
    - Chế độ thép mặc định cũ là vùng biên + bụng: steel_mode="boundary",
      be_Lb <- Lb_left, be_dia <- dia_be, be_nL <- ceil(n_be/2),
      be_nT <- 2, web_dia/web_s <- dia_v/s_v.
    - L0 ngoài mặt phẳng cũ = l0_out_factor x h_story: Ly_m <- h_story/1000,
      psi_y <- l0_out_factor (phương X lấy cùng giá trị — trước đây
      trong mặt phẳng không dùng L0 riêng).
    Dict đã có khóa mới (kể cả từ _collect_wall) được giữ nguyên.
    (2026-10-25) Format vùng biên cũ (be_nL/be_nT) được dịch sang 6 ô
    mới (be_n_Lb/be_n_tw/be_L_out/be_L_in) theo mapping ở cuối hàm;
    be_layout cũ bị bỏ qua.
    RIÊNG sw_steel_grade (phần 3/7): KHÔNG điền ở đây — file cũ thiếu
    khóa này phải giữ trạng thái "chưa đặt" để engine fallback về cấp
    thép dọc (xem WallInput.sw_steel_grade); điền CB400-V ở đây sẽ
    đổi Rsw của file cũ từ 300 (CB500-V) xuống 280 và làm lệch Vcap.
    """
    d = dict(d) if isinstance(d, dict) else {}
    # Dict rỗng hoàn toàn (file không có dữ liệu vách) -> giữ mặc
    # định mới, không áp quy tắc convert file cũ ở cuối hàm.
    _was_empty = not d
    if "steel_mode" not in d:
        d["steel_mode"] = "boundary"
        if "be_Lb" not in d and "Lb_left" in d:
            d["be_Lb"] = d["Lb_left"]
        if "be_dia" not in d and "dia_be" in d:
            d["be_dia"] = d["dia_be"]
        if "be_nL" not in d and "n_be" in d:
            try:
                d["be_nL"] = max(1, math.ceil(float(d["n_be"]) / 2.0))
            except Exception:
                pass
        if "be_nT" not in d:
            d["be_nT"] = 2
        if "web_dia" not in d and "dia_v" in d:
            d["web_dia"] = d["dia_v"]
        if "web_s" not in d and "s_v" in d:
            d["web_s"] = d["s_v"]
    if "Ly_m" not in d and "h_story" in d:
        try:
            hs = float(d["h_story"]) / 1000.0
            d["Ly_m"] = hs
            d.setdefault("Lx_m", hs)
            fac = float(d.get("l0_out_factor", 1.0))
            d["psi_y"] = fac
            d.setdefault("psi_x", fac)
        except Exception:
            pass
    # (2026-10-25) Dịch format vùng biên cũ (be_nL/be_nT) sang 6 ô mới:
    # n_Lb <- be_nL; n_tw <- 2 (mô hình cũ không có thanh tw riêng);
    # L_out <- 1; L_in <- be_nT - 2. Với mapping này generator mới sinh
    # đúng lưới cũ (R = 2*1 + (nT-2) = nT hàng, 0 thanh tw) nên thép cũ
    # không đổi số thanh/tọa độ/As/D/C. Chỉ map khi khóa mới chưa có
    # (file mới thắng); khóa be_layout cũ bị bỏ qua.
    # Dấu vết file cũ PHẢI chụp trước khi điền mặc định be_n_tw ở
    # dưới (sau khi điền thì "be_n_tw" in d luôn đúng).
    _had_old_be = any(k in d for k in ("be_n_tw", "be_nL", "be_nT",
                                       "be_layout"))
    if "be_n_Lb" not in d and "be_nL" in d:
        try:
            d["be_n_Lb"] = int(float(d["be_nL"]))
        except Exception:
            pass
    if "be_n_tw" not in d:
        d["be_n_tw"] = 2
    if "be_L_out" not in d:
        d["be_L_out"] = 1
    if "be_L_in" not in d:
        if "be_nT" in d:
            try:
                d["be_L_in"] = max(0, int(float(d["be_nT"])) - 2)
            except Exception:
                d["be_L_in"] = 0
        else:
            d["be_L_in"] = 0
    # (2026-10-25, mô hình cột dọc) Nghĩa MỚI của be_n_tw: số thanh
    # Ở GIỮA theo chiều tw (không tính 2 hàng trên/dưới). File nghĩa
    # cũ 950b4d5 (be_n_tw tính cả 2 góc, KHÔNG có khóa be_model) ->
    # trừ 2 góc: be_n_tw_mới = max(be_n_tw_cũ - 2, 0). File đã có
    # be_model="columns" (saver mới luôn ghi) -> dùng thẳng, không
    # convert lại (idempotent). File tiền-950b4d5 đi qua mapping trên
    # (cho be_n_tw=2 nghĩa cũ) rồi áp tiếp quy tắc này -> be_n_tw=0.
    # Dict không có dấu vết file cũ nào (_had_old_be False) -> giữ
    # mặc định mới 2 thanh giữa/cột.
    if d.get("be_model") != "columns":
        if _had_old_be and not _was_empty:
            try:
                d["be_n_tw"] = max(0, int(float(d["be_n_tw"])) - 2)
            except Exception:
                d["be_n_tw"] = 0
        d["be_model"] = "columns"
    return d


def wall_from_dict(d) -> WallInput:
    """Dict JSON -> WallInput; khóa lạ bỏ qua, thiếu khóa lấy mặc định
    (dict cũ được dịch trước qua normalize_wall_dict)."""
    w = WallInput()
    if not isinstance(d, dict):
        return w
    names = {f.name for f in fields(w)}
    for k, v in normalize_wall_dict(d).items():
        if k in names:
            setattr(w, k, v)
    return w


# Mặc định tường minh cho GUI/JSON khi chưa từng nhập vách
WALL_DEFAULTS = wall_to_dict(WallInput())
