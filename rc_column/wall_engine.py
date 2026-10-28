"""Engine thuần cho vách chữ nhật đặc (chế độ Vách, GĐ1).

LÁT 1: khả năng chịu N–M theo TCVN 5574:2018 bằng đúng primitive của
bản cột (BiaxialCapacity exact + buckling_factors/eccentricities của
stability.py), KHÔNG qua check_column của cột (hàm đó gói uốn dọc cột
2 phương). Uốn dọc vách (user duyệt 2026-10-27, mức vách + cột TCVN):
MỖI phương độc lập M* = sign·N·e0·η (e0 = max(e1, ea)); dấu: M ≠ 0 →
dấu M gốc, M = 0 → dấu sàn W: trong MP +, ngoài MP − (khung
(M_in, M_out); loại trục trong MP = y (C/U) chờ ánh xạ web riêng).
Khi e1 ≥ ea thì trùng η·M nên ca thường không đổi; sàn chỉ chạm
các trường hợp e1 < ea, kể cả M gốc = 0.

Khung dict kết quả theo §5 bản thiết kế: các khóa vùng biên / cắt /
mạch ngừng / cấu tạo có mặt từ lát 1 với ok=None + ghi chú lát sẽ làm,
để hiển thị và các lát sau không phải đổi khung.
"""

import math

from .checker import section_inertia
from .interaction import BiaxialCapacity, neutral_axis_at_N
from .materials import STEEL_GRADES, SteelMaterial
from .stability import (EccentricityResult, LongTermLoads,
                        buckling_factors, design_moment, eccentricities,
                        phi_L, slenderness)
from .wall_m2m3 import build_wall_m2m3
from .wall_section import build_wall_section, dxf_axis_in, wall_dims
from .wall_shear import (check_wall_shear_in_plane,
                           check_wall_shear_out_of_plane,
                           check_wall_shear_poly,
                           wall_shear_geometry_poly)

PENDING_BOUNDARY = "Chưa kiểm ở lát 1 (vùng biên: lát 3)"
PENDING_SLIDING = ("Chưa kiểm (trượt mạch ngừng chân vách: chưa xác minh "
                   "được điều khoản TCVN 5574:2018 cho mạch ngừng — không "
                   "mượn công thức ma sát cắt ACI/EC2 sang TCVN)")
PENDING_DETAIL = "Chưa kiểm ở lát 1 (cấu tạo/ρmin: lát 3)"

# Phóng đại cắt kháng chấn DCM cho vách (phần 5/7, 2026-10-24):
# TCVN 9386-1:2025 §5.4.2.4(7) (mục 5.4 = DCM; Phần 1 của TCVN 9386
# tương ứng EN 1998-1, các sửa đổi VN chỉ ở Phụ lục E–I nên số điều
# §5 giữ nguyên): "lực cắt thiết kế lấy cao hơn 50% lực cắt thu được
# từ phân tích" — tức V_Ed = 1,5 × V'_Ed. Đây là quy tắc RIÊNG của
# DCM, KHÔNG phải công thức ε của DCH (EN 1998-1 §5.5.2.4.1(7),
# (5.24)/(5.25): ε = q·√((γRd/q·MRd/MEd)² + 0,1·(Se(Tc)/Se(T1))²),
# 1,5 ≤ ε ≤ q) — nên DCM KHÔNG cần MRd/MEd, q hay phổ; đừng áp ε
# DCH cho vách DCM. (7) không có ngoại lệ theo hw/lw; (8) chỉ là
# bao lực cắt theo chiều cao cho hệ kép (dual) — kiểm tra 1 tiết
# diện chân vách ở đây không dựng bao đó. Phạm vi: CHỈ cắt trong
# mặt phẳng (chảy dẻo uốn trong MP tại chân vách là cơ chế mà (6)P
# nhắm tới); cắt ngoài mặt phẳng KHÔNG phóng đại (không tự mở rộng).
SEISMIC_SHEAR_FACTOR_DCM = 1.5


def _rot_vec(x, y, deg):
    """Xoay vectơ (x, y) ngược chiều kim đồng hồ deg độ
    (deg ∈ {0, 90, 180, 270}) — cùng quy ước _rot_xy của GUI."""
    deg = int(deg or 0) % 360
    if deg == 90:
        return (-y, x)
    if deg == 180:
        return (-x, -y)
    if deg == 270:
        return (y, -x)
    return (x, y)


def _rot_vec_inv(x, y, deg):
    """Xoay ngược của _rot_vec (xoay −deg)."""
    return _rot_vec(x, y, (-int(deg or 0)) % 360)


# Trục trong mặt phẳng (hướng dài chính) của từng loại đa giác ở
# rot = 0, theo khung canonical của _poly_* (xem wall_section.py):
# barbell/tee/ell: x (Lw / L1); c-core/u-core: y (thân Lw dọc).
# Rot 90/270° hoán đổi trục này (như wall_dims của rect hoán đổi
# Lw/tw). Ánh xạ solver: trục trong MP 'x' -> M_in ↔ My (M3),
# M_out ↔ Mx (M2) như vách phẳng; trục 'y' -> M_in ↔ Mx (M2),
# M_out ↔ My (M3) — mô men uốn trong mặt phẳng của thân vách
# (mặt y–z) có vectơ mô men dọc trục x. Đây là QUY ƯỚC ÁNH XẠ
# của app (tải pier M2/M3 gắn với phương uốn), không phải điều
# khoản TCVN — TCVN không định nghĩa "trong/ngoài MP" cho lõi
# C/U; các thẻ hiển thị đổi nhãn M2/M3 theo trục này (xem
# wall_detail / param table) để không ghi sai ký hiệu solver.
_POLY_AXIS_IN = {"barbell": "x", "tee": "x", "ell": "x",
                 "c-core": "y", "u-core": "y"}


def _poly_axis_in_rot(section_type, rot_deg, sec=None, bbox=None):
    """Trục trong MP sau khi áp góc xoay (90/270° hoán đổi).

    Lát DXF: section_type == "dxf" thì trục lấy theo cạnh bbox dài
    nhất (dxf_axis_in của wall_section: "x" nếu bbox_x >= bbox_y,
    ngược lại "y") — bbox lấy từ sec (sec.cx/sec.cy của tiết diện
    đã dựng) hoặc tham số bbox = (bbox_x, bbox_y); không có cả hai
    thì fallback "x". Quy tắc này tái hiện đúng cả 5 loại có sẵn
    (phẳng/Barbell/T/L -> x, C/U -> y) nên trục DXF và trục 5 loại
    cùng một luật, chỉ khác nguồn bbox.
    """
    st = str(section_type)
    if st == "dxf":
        if bbox is not None:
            ax = dxf_axis_in(bbox[0], bbox[1])
        elif sec is not None:
            ax = dxf_axis_in(float(sec.cx), float(sec.cy))
        else:
            ax = "x"
    else:
        ax = _POLY_AXIS_IN.get(st, "x")
    if int(rot_deg or 0) % 360 in (90, 270):
        return "y" if ax == "x" else "x"
    return ax


def wall_tcvn_full(winp, conc, steel, model: str = "3line",
                   loads: dict = None, case_info: dict = None,
                   mesh_step: float = None, n_angles: int = 24,
                   steel_sw=None, seismic_shear: bool = False) -> dict:
    """Kiểm tra N–M vách theo TCVN cho 1 tổ hợp (engine thuần, không GUI).

    winp: WallInput; conc/steel: ConcreteMaterial/SteelMaterial (TCVN);
    loads: dict {N, M_in, M_out, V_in, V_out, T} — None thì lấy từ winp.
    steel_sw: vật liệu thép ngang RIÊNG của vách (phần 3/7) — khi None,
    engine tự suy từ winp.sw_steel_grade nếu là cấp hợp lệ (cùng γs với
    thép dọc, như đai cột), ngược lại fallback về steel (thép dọc) —
    đúng hành vi cũ cho file JSON cũ không có khóa sw_steel_grade.
    seismic_shear: True = tổ hợp đang kiểm là combo động đất (hoặc
    nhập tay khi cờ DCM đang bật) -> cắt trong mặt phẳng kiểm ở
    V_Ed = 1,5 × V_in theo TCVN 9386-1:2025 §5.4.2.4(7) DCM; False
    (mặc định) = giữ đúng hành vi cũ, V_d = V_in. Cắt ngoài mặt phẳng
    không bao giờ phóng đại. N–M không đổi trong cả 2 trường hợp.
    Đơn vị: kN, kN·m, mm, MPa. N nén dương.
    """
    if loads is None:
        loads = {"N": winp.N, "M_in": winp.M_in, "M_out": winp.M_out,
                 "V_in": winp.V_in, "V_out": winp.V_out, "T": winp.T}
    N = float(loads.get("N", 0.0))
    M_in = float(loads.get("M_in", 0.0))
    M_out = float(loads.get("M_out", 0.0))
    V_in = float(loads.get("V_in", 0.0))
    V_out = float(loads.get("V_out", 0.0))
    T = float(loads.get("T", 0.0))

    sec, meta = build_wall_section(winp, conc, steel, mesh_step=mesh_step)
    _is_poly = (getattr(sec, "kind", "rect") == "poly")
    _stype = str(getattr(winp, "section_type", "rect") or "rect")
    if not _is_poly:
        # Kích thước HIỆU DỤNG (đã áp góc xoay tiết diện của mục 2)
        Lw, tw = wall_dims(winp)
        Ix, Iy, ix, iy, Isx, Isy = section_inertia(sec)

        # --- Độ mảnh + uốn dọc 2 phương ---
        # Ánh xạ vào khe của buckling_factors: phương ngoài MP <-> khe "x"
        # (Mx = M_out, Ix = Lw·tw³/12 theo tw, cy = tw, L0 = L0_out);
        # phương trong MP <-> khe "y" (My = M_in, Iy = tw·Lw³/12 theo Lw,
        # cx = Lw, L0 = L0_in) — cùng công thức độ cứng/Ncr, cùng φL.
        # Mục 4 (format web 2026-10-23): L0 = ψ x L lấy từ các ô mục 4 TẠI
        # THỜI ĐIỂM TÍNH (Phương X = trong mặt phẳng theo Lw, Phương Y =
        # ngoài mặt phẳng theo tw); L0 KHÔNG lưu riêng, không ghi ngược.
        # File cũ thiếu khóa mới -> wall_from_dict đã dịch h_story/
        # l0_out_factor sang (ở đây vẫn fallback an toàn nếu thiếu).
        pd_method = str(getattr(winp, "pd_method", "tcvn") or "tcvn")
        Lx_m = float(getattr(winp, "Lx_m", 0.0) or 0.0) \
            or float(winp.h_story) / 1000.0
        Ly_m = float(getattr(winp, "Ly_m", 0.0) or 0.0) \
            or float(winp.h_story) / 1000.0
        psi_x = float(getattr(winp, "psi_x", 0.0) or 0.0) \
            or float(winp.l0_out_factor)
        psi_y = float(getattr(winp, "psi_y", 0.0) or 0.0) \
            or float(winp.l0_out_factor)
        l0_in_m = psi_x * Lx_m
        l0_out_m = psi_y * Ly_m
        lam_out = slenderness(l0_out_m, tw)
        lam_in = slenderness(l0_in_m, Lw)
        # Chưa có dữ liệu dài hạn riêng cho vách ở GĐ1 -> phi_L = 2.0
        # (giới hạn trên, thiên an toàn — như cột khi không khai dài hạn).
        lt = LongTermLoads()
        phi = phi_L(N, M_out, M_in, lt)
        ecc = eccentricities(N, M_out, M_in, Lx_m, Ly_m, Lw, tw)
        # Ánh xạ λ vào khe buckling_factors: khe "x" = ngoài MP (lam_out),
        # khe "y" = trong MP (lam_in) — cổng η §8.1.2.1.2 (λ > 14 mới
        # nhân η, từng phương độc lập) nằm trong hàm dùng chung, cột và
        # vách chịu cùng một luật. Ca mẫu: lam_in = 6.37 → η_in = 1.0,
        # lam_out = 45.53 → η_out giữ 1.138.
        buck = buckling_factors(ecc.e0x, ecc.e0y, Lw, tw, phi, conc.Eb,
                                Ix, Iy, Isx, Isy, l0_out_m, l0_in_m,
                                N, M_out, M_in,
                                lambda_x=lam_out, lambda_y=lam_in)
        eta_out = buck.etax
        Ncr_out = buck.Ncrx
        M_out_d = buck.Mx_star
        eta_in = buck.etay
        Ncr_in = buck.Ncry
        if pd_method == "none":
            # "Không xét bổ sung uốn dọc": η = 1 cả 2 phương. Sàn độ lệch
            # tâm e0 = max(e1, ea) ở dưới VẪN áp cả 2 phương — đó là độ
            # lệch tâm thiết kế tối thiểu, tách khỏi η.
            eta_out = 1.0
            eta_in = 1.0
            M_out_d = M_out
        # --- Mô men thiết kế 2 phương (sàn ea, user duyệt 2026-10-27) ---
        # M* = sign·N·e0·η mỗi phương độc lập; ecc.e0x = e0 trong MP
        # (eax = max(L/600, Lw/30, 10) — tức ea_in = Lw/30 khi Lw lớn),
        # ecc.e0y = e0 ngoài MP. Dấu sàn W (khi M gốc = 0): trong MP +,
        # ngoài MP −. η qua cổng §8.1.2.1.2: λ ≤ 14 → η = 1.0.
        # N ≤ 0 giữ nguyên hành vi hiện tại (không dựng mô men sàn).
        if N > 0:
            M_out_d = design_moment(N, M_out, ecc.e0y, eta_out, -1.0)
            M_in_d = design_moment(N, M_in, ecc.e0x, eta_in, +1.0)
        else:
            # N <= 0 (kéo/không tải): không dựng mô men từ sàn lệch tâm
            # (không xác định được dấu) — giữ nguyên M_in, cùng hành vi
            # hiện tại của engine khi N <= 0.
            M_in_d = M_in
        # Khung solver cho đường rect: Mx = M_out, My = M_in (như cũ).
        _Mx_d, _My_d = M_out_d, M_in_d
        _axis_in_rot = "x"
        _slend_note = (
            "TCVN §8.1.2.1.2: η mỗi phương chỉ nhân khi λ phương đó "
            "> 14 (λ ≤ 14 → η = 1,0; cổng trong "
            "buckling_factors, chung với cột); mỗi phương độc lập "
            "M* = sign·N·e0·η (e0 = max(e1, ea); M gốc = 0 → dấu sàn "
            "W: trong MP +, ngoài MP −; user duyệt 2026-10-27). "
            "Sàn ea không phải bao bảo thủ theo D/C ở tiết diện "
            "không đối xứng (có thể làm D/C giảm). "
            "L0 = ψ x L lấy từ mục 4 tại thời điểm tính.")

    else:
        # ---- Nhánh đa giác (lát N–M, 2026-10-27): tổng quát hoá
        # từ công thức chữ nhật sang đa giác theo bảng giả định
        # dưới đây. Mọi điều khoản TCVN trích đúng số điều; phần
        # nào chuẩn không định nghĩa trực tiếp cho đa giác thì
        # ghi rõ là GIẢ ĐỊNH TƯƠNG ĐƯƠNG (không trình bày như
        # điều khoản chuẩn, không mượn diễn giải của web/Prokon).
        #
        # BẢNG GIẢ ĐỊNH chữ nhật -> đa giác:
        # - Khung tính: tải N/M hiểu tại TRỌNG TÂM tiết diện
        #   nguyên. Tiết diện đã dịch về trọng tâm ở
        #   _build_wall_section_poly nên solver, Ix/Iy, Is,
        #   vùng nén, biểu đồ cùng khung trọng tâm (không còn
        #   khung bbox). Đây là khung của Section ("gốc tại
        #   trọng tâm") và của polygon_gross_props.
        # - Trục trong MP: hướng dài chính — barbell/tee/ell: x
        #   (Lw/L1); c-core/u-core: y (thân Lw). Rot 90/270°
        #   hoán đổi trục (như wall_dims của rect). Ánh xạ
        #   solver: trục 'x' -> M_in ↔ My, M_out ↔ Mx (như
        #   phẳng); trục 'y' -> M_in ↔ Mx, M_out ↔ My.
        # - Độ mảnh (TCVN §8.1.2.1.2 + cổng λ > 14 giữ nguyên
        #   từng phương trong buckling_factors): λ = L0/i với
        #   i = √(I/A) từ Ix/Iy đa giác QUANH TRỌNG TÂM
        #   (section_inertia), KHÔNG dùng i = h/√12 chữ nhật.
        #   i của phương uốn = bán kính quán tính quanh trục
        #   vuông góc với phương uốn đó (uốn Mx -> ix, uốn
        #   My -> iy). Giới hạn mảnh vách 120 (§10.2.2) xét ở
        #   thẻ chi tiết như rect, không đổi kết luận N–M.
        # - Độ lệch tâm ngẫu nhiên (TCVN §8.1.2.2.4:
        #   ea = max(L/600, c/30, 10)): c = chiều sâu tiết diện
        #   theo phương uốn đang xét, lấy bằng bề rộng bbox
        #   của tiết diện ĐÃ XOAY theo phương đó (trong MP:
        #   bề rộng theo trục trong MP; ngoài MP: bề rộng
        #   theo trục còn lại). GIẢ ĐỊNH TƯƠNG ĐƯƠNG (chuẩn
        #   chỉ viết c cho tiết diện chữ nhật): với C/U/T/L,
        #   bbox là bao ngoài của nhánh nên c này là phía
        #   bảo thủ cho ea (c lớn -> ea lớn -> e0 lớn).
        # - Ncr/η: cùng CT (44)–(48) qua buckling_factors với
        #   Ix/Iy/Isx/Isy đa giác quanh trọng tâm (khung đã
        #   xoay: rot 90/270° hoán đổi Ix↔Iy, Isx↔Isy, cx↔cy
        #   như rect hoán đổi Lw/tw). Cổng λ > 14 từng
        #   phương giữ nguyên.
        # - M_in* (trong MP): giữ đúng quy tắc vách phẳng đã
        #   chốt 2026-10-24: M_in* = N·max(e1_in, ea_in)·η_in
        #   (η_in của khe trong MP), N ≤ 0 giữ M_in nguyên;
        #   M_out* = η_out·M_out (η_out của khe ngoài MP);
        #   pd_method "none" -> η = 1 hai phương nhưng sàn
        #   e0 trong MP vẫn áp (như rect).
        # - Ag = diện tích đa giác thật (sec.gross_area), KHÔNG
        #   Lw×tw. Ig_in = quán tính quanh trục vuông góc với
        #   trục trong MP (trục 'x' -> Iy, trục 'y' -> Ix).
        #   σ_mép: N/Ag + |M_in|·d_mép/Ig_in với d_mép =
        #   khoảng cách mép xa nhất từ trọng tâm theo trục
        #   trong MP (2 phía lấy max — phía bảo thủ; công
        #   thức Lw/2 chữ nhật không còn đúng với T/L/C/U
        #   không đối xứng). σ này chỉ là đầu vào tiêu chí
        #   vùng biên lát 3, không đổi kết luận N–M.
        # - Xoay: engine KHÔNG xoay lại hình học (tiết diện
        #   dựng ở khung canonical + khung trọng tâm); thay
        #   vào đó (a) tính độ mảnh/Ncr/ea trong khung đã
        #   xoay (hoán đổi I/cx/cy khi 90/270°), (b) chạy
        #   solver trên tiết diện canonical với vectơ mô men
        #   thiết kế đã xoay ngược (−rot), rồi (c) mọi số
        #   hiển thị theo khung vật lý (M_in/M_out, M*;
        #   α hiển thị = α ETABS ở dưới, ghi ở alpha_deg;
        #   α solver canonical ghi riêng ở alpha_solver_deg
        #   để Mα,u/vùng nén/biểu đồ vẫn nhất quán với
        #   tiết diện canonical mà chart vẽ). Phép xoay cứng
        #   bảo toàn D/C nên test xoay 90° + xoay tải theo
        #   phải cho D/C không đổi (xem test_wallnm_poly).
        # - Thép: dùng đúng thép chu vi + ô nút giao hiện có
        #   (lát thép 9b6481f); Barbell chế độ boundary vẫn
        #   dùng thép chu vi (be_Lb/be_dia chưa ánh xạ sang
        #   đầu Barbell — giới hạn đã ghi ở meta.layout_text,
        #   không bịa thép vùng biên Barbell).
        _rot = int(getattr(winp, "rot_deg", 0) or 0) % 360
        _axis_in = _poly_axis_in_rot(_stype, _rot, sec=sec)
        _Ix_c, _Iy_c, _ix_c, _iy_c, _Isx_c, _Isy_c = \
            section_inertia(sec)
        if _rot in (90, 270):
            Ix, Iy, Isx, Isy = _Iy_c, _Ix_c, _Isy_c, _Isx_c
            cx_r, cy_r = float(sec.cy), float(sec.cx)
        else:
            Ix, Iy, Isx, Isy = _Ix_c, _Iy_c, _Isx_c, _Isy_c
            cx_r, cy_r = float(sec.cx), float(sec.cy)
        Ag = sec.gross_area
        _ix_r = math.sqrt(Ix / Ag) if Ag > 0 else 0.0
        _iy_r = math.sqrt(Iy / Ag) if Ag > 0 else 0.0
        pd_method = str(getattr(winp, "pd_method", "tcvn") or "tcvn")
        Lx_m = float(getattr(winp, "Lx_m", 0.0) or 0.0) \
            or float(winp.h_story) / 1000.0
        Ly_m = float(getattr(winp, "Ly_m", 0.0) or 0.0) \
            or float(winp.h_story) / 1000.0
        psi_x = float(getattr(winp, "psi_x", 0.0) or 0.0) \
            or float(winp.l0_out_factor)
        psi_y = float(getattr(winp, "psi_y", 0.0) or 0.0) \
            or float(winp.l0_out_factor)
        l0_in_m = psi_x * Lx_m
        l0_out_m = psi_y * Ly_m
        # Ánh xạ mô men vào khe solver ở khung đã xoay.
        if _axis_in == "x":
            _Mx_r, _My_r = M_out, M_in
            _mx_is_in = False
        else:
            _Mx_r, _My_r = M_in, M_out
            _mx_is_in = True
        # eccentricities(Lx_arg, Ly_arg): Lx_arg cho khe My,
        # Ly_arg cho khe Mx (xem stability.eccentricities).
        _Lx_arg = Lx_m if _axis_in == "x" else Ly_m
        _Ly_arg = Ly_m if _axis_in == "x" else Lx_m
        _ecc_r = eccentricities(N, _Mx_r, _My_r, _Lx_arg, _Ly_arg,
                                cx_r, cy_r)
        if _axis_in == "x":
            e0_in, ea_in = _ecc_r.e0x, _ecc_r.eax
            e0_out, ea_out = _ecc_r.e0y, _ecc_r.eay
        else:
            e0_in, ea_in = _ecc_r.e0y, _ecc_r.eay
            e0_out, ea_out = _ecc_r.e0x, _ecc_r.eax
        _l0_Mx = l0_in_m if _mx_is_in else l0_out_m
        _l0_My = l0_out_m if _mx_is_in else l0_in_m
        _lam_Mx = _l0_Mx * 1000.0 / _ix_r if _ix_r > 0 \
            else float("inf")
        _lam_My = _l0_My * 1000.0 / _iy_r if _iy_r > 0 \
            else float("inf")
        lam_in = _lam_My if _axis_in == "x" else _lam_Mx
        lam_out = _lam_Mx if _axis_in == "x" else _lam_My
        lt = LongTermLoads()
        phi = phi_L(N, _Mx_r, _My_r, lt)
        _buck_r = buckling_factors(
            _ecc_r.e0x, _ecc_r.e0y, cx_r, cy_r, phi, conc.Eb,
            Ix, Iy, Isx, Isy, _l0_Mx, _l0_My, N, _Mx_r, _My_r,
            lambda_x=_lam_Mx, lambda_y=_lam_My)
        if _axis_in == "x":
            eta_in, eta_out = _buck_r.etay, _buck_r.etax
            Ncr_in, Ncr_out = _buck_r.Ncry, _buck_r.Ncrx
        else:
            eta_in, eta_out = _buck_r.etax, _buck_r.etay
            Ncr_in, Ncr_out = _buck_r.Ncrx, _buck_r.Ncry
        if pd_method == "none":
            eta_out = 1.0
            eta_in = 1.0
            M_out_d = M_out
        else:
            # M_out nằm ở khe Mx khi trục trong MP là 'x', ở khe
            # My khi trục trong MP là 'y' (M_in chiếm khe còn lại).
            M_out_d = _buck_r.Mx_star if _axis_in == "x" \
                else _buck_r.My_star
        # --- Sàn ea (user duyệt 2026-10-27, xác nhận web C/U
        # 2026-10-27) --- Quy tắc dấu sàn W THỐNG NHẤT trong khung
        # (M_in, M_out) cho cả 2 loại trục: sàn M_in +, sàn M_out −.
        # Web C/U thuần: C (Mx 0 → sàn M_out −200; My 0 → sàn
        # M_in +100), U (Mx 0 → sàn M_out −100; My 0 → sàn
        # M_in +200) — đúng dấu này sau khi dịch M_in = My_web,
        # M_out = −Mx_web. N ≤ 0 giữ nguyên hành vi hiện tại.
        # Lưu ý độ lớn ea của C khác web (app: sàn M_in 200 /
        # M_out 100 do bbox 3000×1500; web: 100 / 200) — đã báo
        # rõ, KHÔNG tự đổi ea theo web ở lát này; D/C thuần
        # của C so web còn lệch riêng, ngoài phạm vi sàn ea.
        if N > 0:
            M_out_d = design_moment(N, M_out, e0_out, eta_out, -1.0)
            M_in_d = design_moment(N, M_in, e0_in, eta_in, +1.0)
        else:
            M_in_d = M_in
        # Vectơ mô men thiết kế ở khung đã xoay -> khung solver
        # canonical (xoay ngược −rot) để chạy trên tiết diện
        # canonical; độ lớn không đổi (xoay cứng).
        if _axis_in == "x":
            _Mx_dr, _My_dr = M_out_d, M_in_d
        else:
            _Mx_dr, _My_dr = M_in_d, M_out_d
        _Mx_d, _My_d = _rot_vec_inv(_Mx_dr, _My_dr, _rot)
        # Các biến dùng chung ở dưới (đường rect đặt tên này).
        Lw, tw = cx_r, cy_r
        Ig_in = Iy if _axis_in == "x" else Ix
        # Khoảng cách mép xa nhất từ trọng tâm theo trục trong
        # MP, đo trên đa giác đã xoay (xoay cứng verts trọng
        # tâm): trục 'x' -> tọa độ x, trục 'y' -> tọa độ y.
        _rv = [_rot_vec(x, y, _rot) for (x, y) in sec.poly_verts[0]] \
            if sec.poly_verts else []
        if _rv:
            _coords = [p[0] if _axis_in == "x" else p[1]
                       for p in _rv]
            _d_edge = max(abs(min(_coords)), abs(max(_coords)))
        else:
            _d_edge = (cx_r if _axis_in == "x" else cy_r) / 2.0
        sigma_edge = N * 1000.0 / Ag + abs(M_in) * 1e6 * _d_edge \
            / Ig_in if Ig_in > 0 else float("inf")
        _e1_in = abs(M_in) * 1000.0 / N if N > 0 else 0.0
        _e1_out = abs(M_out) * 1000.0 / N if N > 0 else 0.0
        # Quy ước chung của app (như nhánh rect: full["e0_in"] =
        # ecc.e0x): trường x của EccentricityResult luôn là
        # TRONG MP, trường y là NGOÀI MP — cả 2 nhánh đều ghi
        # theo thứ tự in-first, không đảo theo slot solver.
        ecc = EccentricityResult(_e1_in, _e1_out, ea_in, ea_out,
                                 e0_in, e0_out)
        _c_in = cx_r if _axis_in == "x" else cy_r
        _c_out = cy_r if _axis_in == "x" else cx_r
        _slend_note = (
            "Đa giác (lát N–M): TCVN 5574:2018 §8.1.2.1.2 — η mỗi "
            "phương chỉ nhân khi λ phương đó > 14 (λ = L0/i, "
            "i = √(I/A) quanh trọng tâm từ đa giác thật; cổng "
            "trong buckling_factors, chung với cột/vách phẳng). "
            "§8.1.2.2.4 — ea = max(L/600, c/30, 10) với c = chiều "
            f"sâu tiết diện theo phương uốn (trong MP c = {_c_in:.0f} "
            f"mm theo trục {_axis_in}, ngoài MP c = {_c_out:.0f} mm; "
            "c lấy bằng bề rộng bbox đã xoay — GIẢ ĐỊNH TƯƠNG "
            "ĐƯƠNG cho đa giác, phía bảo thủ). Tải N/M hiểu tại "
            "trọng tâm tiết diện nguyên (khung trọng tâm). "
            "Trong MP: M_in* = N·max(e1, ea)·η_in. "
            "Cắt: lát cắt đa giác (xem mục cắt dưới — mỗi phương "
            "kết luận riêng); PDF cho loại này: lát sau.")
        if _stype == "dxf":
            # Ghi rõ tiết diện DXF + trục trong MP đã chọn (lát
            # DXF): trục theo cạnh bbox dài nhất, không phải theo
            # bảng 5 loại có sẵn.
            _slend_note = (
                f"Tiết diện DXF (file "
                f"{str(getattr(winp, 'dxf_file', '') or '—')}; "
                f"bbox {float(sec.cx):.0f}x{float(sec.cy):.0f} mm; "
                f"trục trong MP đã chọn: {_axis_in} — theo cạnh "
                f"bbox dài nhất (x nếu bbox_x >= bbox_y, ngược "
                f"lại y). " + _slend_note)
        _axis_in_rot = _axis_in
    # --- Sức bền tiết diện: solver fiber exact (tia song trục) ---
    cap = BiaxialCapacity(sec, model=model, n_angles=n_angles)
    # Solver chạy trên khung solver: rect (_Mx_d, _My_d) =
    # (M_out_d, M_in_d) như cũ; đa giác = mô men thiết kế đã xoay
    # ngược về khung canonical/trọng tâm (xem nhánh đa giác).
    r = cap.dc_ratio(N, _Mx_d, _My_d)
    dc = r["dc"]
    fs_val = 1.0 / dc if dc > 1e-12 else float("inf")
    # Góc SOLVER (khung canonical/trọng tâm) — CHỈ dùng nội bộ
    # cho Mα,u và vùng nén tại B, không phải α hiển thị.
    _alpha_solver = (math.degrees(math.atan2(_Mx_d, _My_d)) % 360.0) \
        if abs(_Mx_d) + abs(_My_d) > 1e-9 else 0.0
    # α HIỂN THỊ duy nhất (quy ước ETABS đã chốt, AGENTS.md §4):
    # α = atan2(M2, M3) với M2 = M_out_d (ngoài MP),
    # M3 = M_in_d (trong MP) — đúng cặp mô men thiết kế đã
    # phóng đại, có dấu, chuẩn hoá [0, 360). Với phẳng +
    # Barbell/T/L (trục trong MP = x) góc này trùng góc solver
    # nên không đổi số; với C/U (trục trong MP = y) góc solver
    # cũ là atan2(M_in_d, M_out_d) (76,0° ở ca 800/200) — nay
    # chỉ đổi nhãn hiển thị thành 14,0°, D/C/điểm B/Mα/vị trí
    # điểm A trên tia giữ nguyên (tia vẫn dùng cặp (M_in_d,
    # M_out_d) có dấu; biểu đồ vẫn vẽ bằng Mx_d/My_d/Bx_can/
    # By_can của solver, không vẽ lại theo α hiển thị).
    alpha_deg = (math.degrees(math.atan2(M_out_d, M_in_d)) % 360.0) \
        if abs(M_out_d) + abs(M_in_d) > 1e-9 else 0.0
    Malpha = math.hypot(_Mx_d, _My_d)
    M_cap = cap.moment_capacity(N, _alpha_solver) \
        if Malpha > 1e-9 else 0.0

    # Chiều cao vùng nén tại điểm biên B của tia (BN = lambda*N)
    c_neutral = None
    na_info = None
    try:
        na_info = neutral_axis_at_N(cap.fs, r["BN"], _alpha_solver,
                                    model)
        if na_info.get("found"):
            c_neutral = na_info.get("na_depth")
    except Exception:
        na_info = None

    # Ứng suất nén mép (đàn hồi, tiết diện nguyên) — đầu vào cho tiêu
    # chí kích hoạt vùng biên ở lát 3, tính sẵn từ lát 1 theo §5.
    # Đa giác đã có Ag/Ig_in/sigma_edge từ nhánh đa giác.
    if not _is_poly:
        Ag = Lw * tw
        Ig_in = tw * Lw ** 3 / 12.0
        sigma_edge = N * 1000.0 / Ag + abs(M_in) * 1e6 * (Lw / 2.0) \
            / Ig_in

    if _is_poly:
        if N > 0:
            _in_line_poly = (
                f"Trong mặt phẳng (Phương X): L0 = ψ x L = {psi_x:g} x "
                f"{Lx_m:.2f} = {l0_in_m:.2f} m, λ = {lam_in:.1f}, "
                f"e1 = {abs(M_in) * 1000.0 / N:.1f} mm, "
                f"ea = {ea_in:.1f} mm, e0 = {e0_in:.1f} mm, "
                f"Ncr = {Ncr_in:.0f} kN, η = {eta_in:.3f} "
                f"-> M_in* = {M_in_d:.1f} kN·m")
        else:
            _in_line_poly = (
                f"Trong mặt phẳng (Phương X): L0 = ψ x L = {psi_x:g} x "
                f"{Lx_m:.2f} = {l0_in_m:.2f} m, λ = {lam_in:.1f}; "
                f"N <= 0 nên không áp phóng đại/sàn lệch tâm "
                f"-> M_in* = {M_in_d:.1f} kN·m")
        details = [
            (f"Tiết diện vách DXF (file "
             f"{str(getattr(winp, 'dxf_file', '') or '—')}; bbox "
             f"{float(sec.cx):.0f}x{float(sec.cy):.0f} mm, khung "
             f"trọng tâm; trục trong MP đã chọn: {_axis_in_rot} — "
             f"theo cạnh bbox dài nhất (x nếu bbox_x >= bbox_y, "
             f"ngược lại y); Ag = {Ag:.0f} mm², "
             f"As = {sec.steel_area:.0f} mm² "
             f"(µ = {sec.reinforcement_ratio*100:.2f}%)")
            if _stype == "dxf" else
            f"Tiết diện vách đa giác {_stype} (bbox {float(sec.cx):.0f}x{float(sec.cy):.0f} mm, "
            f"khung trọng tâm; trục trong MP: {_axis_in_rot} — "
            f"Ag = {Ag:.0f} mm², "
            f"As = {sec.steel_area:.0f} mm² (µ = {sec.reinforcement_ratio*100:.2f}%)",
            meta.get("layout_text") or "",
            f"Ngoài mặt phẳng (Phương Y): L0 = ψ x L = {psi_y:g} x "
            f"{Ly_m:.2f} = {l0_out_m:.2f} m, λ = {lam_out:.1f}, "
            f"e0 = {e0_out:.1f} mm, φL = {phi:.2f}, Ncr = {Ncr_out:.0f} kN, "
            f"η = {eta_out:.3f} -> M_out* = {M_out_d:.1f} kN·m",
            _in_line_poly,
            f"Góc α hiển thị (ETABS: atan2(M_out*, M_in*)) "
            f"= {alpha_deg:.1f}°, "
            f"góc solver (khung trọng tâm, dùng cho Mα,u/vùng "
            f"nén) = {_alpha_solver:.1f}°, "
            f"Mα = {Malpha:.1f} kN·m, "
            f"Mα,u = {M_cap:.1f} kN·m tại N = {N:.1f} kN",
            f"D/C = {dc:.3f} (FS = {fs_val:.2f}) -> "
            f"{'ĐẠT' if r['ok'] else 'KHÔNG ĐẠT'} (chỉ N–M; cắt kết "
            f"luận riêng ở dưới, PDF cho loại này đang làm ở lát sau)",
        ]
        if pd_method == "none":
            details.append("Phương pháp uốn dọc: KHÔNG xét bổ sung uốn dọc "
                           "(η = 1 cả 2 phương theo mục 4; sàn lệch tâm "
                           "e0 = max(e1, ea) trong mặt phẳng vẫn áp).")
        if c_neutral is not None and math.isfinite(c_neutral):
            details.append(f"Chiều cao vùng nén tại điểm biên B: "
                           f"c = {c_neutral:.0f} mm")
        details.append(f"Ứng suất nén mép (đàn hồi): σ = {sigma_edge:.2f} MPa "
                       f"(tiêu chí vùng biên xét ở lát 3)")
    else:
        if N > 0:
            _in_line = (
                f"Trong mặt phẳng (Phương X): L0 = ψ x L = {psi_x:g} x "
                f"{Lx_m:.2f} = {l0_in_m:.2f} m, λ = {lam_in:.1f}, "
                f"e1 = {abs(M_in) * 1000.0 / N:.1f} mm, "
                f"ea = {ecc.eax:.1f} mm, e0 = {ecc.e0x:.1f} mm, "
                f"Ncr = {Ncr_in:.0f} kN, η = {eta_in:.3f} "
                f"-> M_in* = {M_in_d:.1f} kN·m")
        else:
            _in_line = (
                f"Trong mặt phẳng (Phương X): L0 = ψ x L = {psi_x:g} x "
                f"{Lx_m:.2f} = {l0_in_m:.2f} m, λ = {lam_in:.1f}; "
                f"N <= 0 nên không áp phóng đại/sàn lệch tâm "
                f"-> M_in* = {M_in_d:.1f} kN·m")
        _layout_line = meta.get("layout_text") or (
            f"Thép: biên {meta['n_be_left'] + meta['n_be_right']} thanh "
            f"d{float(winp.dia_be):.0f}, phân bố đứng {meta['n_web']} thanh "
            f"d{float(winp.dia_v):.0f} (bước thực "
            f"{meta['s_v_actual'] if meta['s_v_actual'] else 0:.0f} mm)")
        details = [
            f"Tiết diện vách {Lw:.0f}x{tw:.0f} mm, Ag = {Ag:.0f} mm², "
            f"As = {sec.steel_area:.0f} mm² (µ = {sec.reinforcement_ratio*100:.2f}%)",
            _layout_line,
            f"Ngoài mặt phẳng (Phương Y): L0 = ψ x L = {psi_y:g} x "
            f"{Ly_m:.2f} = {l0_out_m:.2f} m, λ = {lam_out:.1f}, "
            f"e0 = {ecc.e0y:.1f} mm, φL = {phi:.2f}, Ncr = {Ncr_out:.0f} kN, "
            f"η = {eta_out:.3f} -> M_out* = {M_out_d:.1f} kN·m",
            _in_line,
            f"Góc α = {alpha_deg:.1f}°, Mα = {Malpha:.1f} kN·m, "
            f"Mα,u = {M_cap:.1f} kN·m tại N = {N:.1f} kN",
            f"D/C = {dc:.3f} (FS = {fs_val:.2f}) -> "
            f"{'ĐẠT' if r['ok'] else 'KHÔNG ĐẠT'} (chỉ N–M, phạm vi lát 1)",
        ]
        if pd_method == "none":
            details.append("Phương pháp uốn dọc: KHÔNG xét bổ sung uốn dọc "
                           "(η = 1 cả 2 phương theo mục 4; sàn lệch tâm "
                           "e0 = max(e1, ea) trong mặt phẳng vẫn áp).")
        if c_neutral is not None and math.isfinite(c_neutral):
            details.append(f"Chiều cao vùng nén tại điểm biên B: "
                           f"c = {c_neutral:.0f} mm")
        details.append(f"Ứng suất nén mép (đàn hồi): σ = {sigma_edge:.2f} MPa "
                       f"(tiêu chí vùng biên xét ở lát 3)")

    # --- Biểu đồ M2–M3 (chỉ THÊM khóa "m2m3", không đổi số nào trên) ---
    # Đường bao = lát cắt mặt tương tác tại N = BN (xem wall_m2m3.py:
    # chỉ lát cắt này mới đi đúng qua B; lát cắt tại N tải lệch B
    # 8–19% ở các ca vách). Dùng đúng cap đã dựng cho D/C ở trên.
    _n_level = r["BN"] if math.isfinite(r["BN"]) else N
    _m2m3 = build_wall_m2m3(cap, _n_level, _Mx_d, _My_d,
                            r["Bx"], r["By"])

    if _is_poly:
        # --- Cắt đa giác (lát cắt, 2026-10-27) ---
        # Tính SAU và ĐỘC LẬP với N–M như phẳng; lỗi 1 phương chỉ
        # làm phương đó pending. Hình học VẬT LÝ (thân/ngang) từ
        # wall_shear_geometry_poly, rồi hoán đổi theo rot như
        # wall_dims của phẳng (khung V2/V3 cố định): rot 90/270°
        # thì shear_in (V2) lấy hình học ngang vật lý và ngược
        # lại — pending của C/U ngoài MP vật lý vì vậy cũng đổi
        # nhãn cột khi xoay (pending là tính chất của HƯỚNG, không
        # phải của nhãn). DCM 1,5× chỉ shear_in (V2), như phẳng.
        _seis_factor = SEISMIC_SHEAR_FACTOR_DCM if seismic_shear else 1.0
        _V_in_d = _seis_factor * V_in
        _sw_grade = getattr(winp, "sw_steel_grade", None)
        if steel_sw is None and isinstance(_sw_grade, str) \
                and _sw_grade in STEEL_GRADES:
            steel_sw = SteelMaterial(STEEL_GRADES[_sw_grade],
                                     float(getattr(steel, "gamma_s", 1.0)))
        try:
            _pgeom = wall_shear_geometry_poly(winp)
        except Exception as ex:
            _pgeom = None
            _pgeom_err = str(ex)
        if _pgeom is None:
            shear_in = {"V_d": _V_in_d, "V_raw": V_in,
                        "seismic_factor": _seis_factor,
                        "seismic_applied": bool(seismic_shear),
                        "V_cap": None, "dc": None,
                        "ok": None, "parts": {},
                        "note": f"Cắt trong mặt phẳng: lỗi khi tính: "
                                f"{_pgeom_err}"}
            shear_lines = [shear_in["note"]]
        else:
            _rot_p = int(getattr(winp, "rot_deg", 0) or 0) % 360
            if _rot_p in (90, 270):
                _gin, _gout = _pgeom["geom_out"], _pgeom["geom_in"]
            else:
                _gin, _gout = _pgeom["geom_in"], _pgeom["geom_out"]
            _A_sec_poly = float(sec.gross_area)
            shear_in = {"V_d": _V_in_d, "V_raw": V_in,
                        "seismic_factor": _seis_factor,
                        "seismic_applied": bool(seismic_shear),
                        "V_cap": None, "dc": None,
                        "ok": None, "parts": {},
                        "note": "Cắt trong mặt phẳng: lỗi khi tính (xem chi tiết)"}
            shear_lines = []
            if _gin is None:
                shear_in["note"] = _pgeom["pending_out"]
                shear_lines.append(shear_in["note"])
            else:
                try:
                    shear_in = check_wall_shear_poly(
                        winp, conc, steel, _V_in_d, N, _gin,
                        _A_sec_poly, steel_sw=steel_sw)
                    shear_in["V_raw"] = V_in
                    shear_in["seismic_factor"] = _seis_factor
                    shear_in["seismic_applied"] = bool(seismic_shear)
                    shear_in["parts"]["V_raw"] = V_in
                    shear_in["parts"]["seismic_factor"] = _seis_factor
                    shear_in["parts"]["seismic_applied"] = \
                        bool(seismic_shear)
                    _p = shear_in["parts"]
                    _dc_txt = (f"{shear_in['dc']:.3f}"
                               if shear_in["dc"] is not None
                               and math.isfinite(shear_in["dc"]) else "∞")
                    if seismic_shear:
                        shear_lines.append(
                            f"Phóng đại cắt kháng chấn DCM (TCVN "
                            f"9386-1:2025 §5.4.2.4(7)): V_Ed = 1,5 × "
                            f"V2 = 1,5 × {V_in:.1f} = {_V_in_d:.1f} kN "
                            f"— toàn bộ kiểm tra §8.1.3 dưới đây xét "
                            f"ở V_Ed này; cắt ngoài mặt phẳng không "
                            f"phóng đại.")
                    _map_in = ("ánh xạ vách phẳng (DXF chữ nhật)"
                               if _p.get("dxf_rectangle") else
                               "ánh xạ đa giác — GIẢ ĐỊNH TƯƠNG ĐƯƠNG")
                    shear_lines.append(
                        f"Cắt trong mặt phẳng (TCVN 5574:2018 "
                        f"§8.1.3, {_map_in}): V2 = {V_in:.1f} kN; "
                        f"b = {_p['b']:.0f} mm, h0 = {_p['h0']:.0f} "
                        f"mm, thép ngang {_p['sw_txt']} "
                        f"(Rsw = {_p['Rsw']:.0f} MPa, Asw = "
                        f"{_p['Asw']:.0f} mm²); qsw bố trí = "
                        f"{_p['qsw_arr']:.1f} N/mm, qsw được kể = "
                        f"{_p['qsw']:.1f} N/mm; "
                        f"φn = {_p['phi_n']:.3f}")
                    shear_lines.append(
                        f"  {_p['geom_note']}")
                    shear_lines.append(
                        f"  ĐK1 (dải nén xiên, (88)): [Q]1 = "
                        f"φn×0.3×Rb×b×h0 = {_p['Qcap1']:.1f} kN -> "
                        f"{'ĐẠT' if _p['ok1'] else 'KHÔNG ĐẠT'}; "
                        f"ĐK2 (vết nứt xiên): C = {_p['C_opt']:.0f} "
                        f"mm, Qb = {_p['Qb']:.1f} kN, Qsw = "
                        f"{_p['Qsw']:.1f} kN, [Q]2 = "
                        f"{_p['Qcap2']:.1f} kN -> "
                        f"{'ĐẠT' if _p['ok2'] else 'KHÔNG ĐẠT'}")
                    if not _p["cond98_ok"]:
                        shear_lines.append(
                            f"  ĐK (98) KHÔNG thỏa: s_h = "
                            f"{_p['s_h']:.0f} mm > s_max = "
                            f"{_p['s_max']:.0f} mm -> thép ngang "
                            f"không được kể, Qsw = 0")
                    if not _p["cond96_ok"]:
                        shear_lines.append(
                            f"  ĐK (96) KHÔNG thỏa: qsw = "
                            f"{_p['qsw']:.1f} < 0.25×Rbt×b = "
                            f"{_p['qsw_min96']:.1f} N/mm -> Qb theo "
                            f"(97), thép ngang vẫn được kể")
                    shear_lines.append(
                        f"  V_cap = min([Q]1, [Q]2) = "
                        f"{shear_in['V_cap']:.1f} kN, D/C cắt = "
                        f"{_dc_txt} -> "
                        f"{'ĐẠT' if shear_in['ok'] else 'KHÔNG ĐẠT'} "
                        f"(kết luận cắt RIÊNG, không đổi kết luận N–M)")
                except Exception as ex:
                    shear_in = {"V_d": _V_in_d, "V_raw": V_in,
                                "seismic_factor": _seis_factor,
                                "seismic_applied": bool(seismic_shear),
                                "V_cap": None, "dc": None,
                                "ok": None, "parts": {},
                                "note": f"Cắt trong mặt phẳng: lỗi khi "
                                        f"tính: {ex}"}
                    shear_lines.append(
                        f"Cắt trong mặt phẳng: lỗi khi tính: {ex}")
        details += shear_lines
    else:
        # --- Cắt trong mặt phẳng (lát 4 — phần 2 của chương trình vách) ---
        # Tính SAU và ĐỘC LẬP với N–M: không động vào bất kỳ số N–M nào ở
        # trên; lỗi cắt (nếu có) chỉ làm shear_in pending, không đánh sập
        # kết quả N–M. ok_all giữ = ok của N–M chỉ để tương thích
        # dict cũ — không còn render thành kết luận chung, hiển thị
        # kết luận riêng từng phần (phần 2/7).
        # Phóng đại kháng chấn (phần 5/7): V_Ed đưa vào check_shear là
        # lực cắt THIẾT KẾ đã phóng đại — toàn bộ §8.1.3 (kể cả ĐK (98)
        # với s_max theo V_Ed) xét ở V_Ed, không chỉ nhân D/C sau cùng.
        _seis_factor = SEISMIC_SHEAR_FACTOR_DCM if seismic_shear else 1.0
        _V_in_d = _seis_factor * V_in
        shear_in = {"V_d": _V_in_d, "V_raw": V_in,
                    "seismic_factor": _seis_factor,
                    "seismic_applied": bool(seismic_shear),
                    "V_cap": None, "dc": None,
                    "ok": None, "parts": {},
                    "note": "Cắt trong mặt phẳng: lỗi khi tính (xem chi tiết)"}
        shear_lines = []
        try:
            # Thép ngang RIÊNG (phần 3/7): ưu tiên steel_sw do caller (GUI)
            # truyền; nếu không có, suy từ winp.sw_steel_grade (file mới);
            # cấp lạ/None -> fallback thép dọc (file cũ, hành vi cũ).
            _sw_grade = getattr(winp, "sw_steel_grade", None)
            if steel_sw is None and isinstance(_sw_grade, str) \
                    and _sw_grade in STEEL_GRADES:
                steel_sw = SteelMaterial(STEEL_GRADES[_sw_grade],
                                         float(getattr(steel, "gamma_s", 1.0)))
            shear_in = check_wall_shear_in_plane(winp, conc, steel, _V_in_d,
                                                 N, Lw=Lw, tw=tw,
                                                 steel_sw=steel_sw)
            shear_in["V_raw"] = V_in
            shear_in["seismic_factor"] = _seis_factor
            shear_in["seismic_applied"] = bool(seismic_shear)
            shear_in["parts"]["V_raw"] = V_in
            shear_in["parts"]["seismic_factor"] = _seis_factor
            shear_in["parts"]["seismic_applied"] = bool(seismic_shear)
            _p = shear_in["parts"]
            _dc_txt = (f"{shear_in['dc']:.3f}" if shear_in["dc"] is not None
                       and math.isfinite(shear_in["dc"]) else "∞")
            if seismic_shear:
                shear_lines.append(
                    f"Phóng đại cắt kháng chấn DCM (TCVN 9386-1:2025 "
                    f"§5.4.2.4(7)): V_Ed = 1,5 × V2 = 1,5 × {V_in:.1f} = "
                    f"{_V_in_d:.1f} kN — toàn bộ kiểm tra §8.1.3 dưới đây "
                    f"xét ở V_Ed này; cắt ngoài mặt phẳng không phóng đại.")
            shear_lines.append(
                f"Cắt trong mặt phẳng (TCVN 5574:2018 §8.1.3, ánh xạ vách): "
                f"V2 = {V_in:.1f} kN; b = tw = {_p['b']:.0f} mm, "
                f"h0 = {_p['h0']:.0f} mm, thép ngang {_p['sw_txt']} "
                f"(Rsw = {_p['Rsw']:.0f} MPa, Asw = {_p['Asw']:.0f} mm²); "
                f"qsw bố trí = {_p['qsw_arr']:.1f} N/mm, "
                f"qsw được kể = {_p['qsw']:.1f} N/mm; "
                f"φn = {_p['phi_n']:.3f}")
            shear_lines.append(
                f"  ĐK1 (dải nén xiên, (88)): [Q]1 = φn×0.3×Rb×b×h0 "
                f"= {_p['Qcap1']:.1f} kN -> "
                f"{'ĐẠT' if _p['ok1'] else 'KHÔNG ĐẠT'}; "
                f"ĐK2 (vết nứt xiên): C = {_p['C_opt']:.0f} mm, "
                f"Qb = {_p['Qb']:.1f} kN, Qsw = {_p['Qsw']:.1f} kN, "
                f"[Q]2 = {_p['Qcap2']:.1f} kN -> "
                f"{'ĐẠT' if _p['ok2'] else 'KHÔNG ĐẠT'}")
            if not _p["cond98_ok"]:
                shear_lines.append(
                    f"  ĐK (98) KHÔNG thỏa: s_h = {_p['s_h']:.0f} mm > "
                    f"s_max = {_p['s_max']:.0f} mm -> thép ngang không "
                    f"được kể, Qsw = 0")
            if not _p["cond96_ok"]:
                shear_lines.append(
                    f"  ĐK (96) KHÔNG thỏa: qsw = {_p['qsw']:.1f} < "
                    f"0.25×Rbt×b = {_p['qsw_min96']:.1f} N/mm -> Qb theo "
                    f"(97), thép ngang vẫn được kể")
            shear_lines.append(
                f"  V_cap = min([Q]1, [Q]2) = {shear_in['V_cap']:.1f} kN, "
                f"D/C cắt = {_dc_txt} -> "
                f"{'ĐẠT' if shear_in['ok'] else 'KHÔNG ĐẠT'} "
                f"(kết luận cắt RIÊNG, không đổi kết luận N–M)")
        except Exception as ex:
            shear_in = {"V_d": _V_in_d, "V_raw": V_in,
                        "seismic_factor": _seis_factor,
                        "seismic_applied": bool(seismic_shear),
                        "V_cap": None, "dc": None,
                        "ok": None, "parts": {},
                        "note": f"Cắt trong mặt phẳng: lỗi khi tính: {ex}"}
            shear_lines.append(f"Cắt trong mặt phẳng: lỗi khi tính: {ex}")
        details += shear_lines

    if _is_poly:
        # Hình học đã tính ở khối shear_in (_gout/_pgeom); nếu khối
        # đó lỗi hình học thì tính lại ở đây, vẫn pending riêng
        # từng phương, không đánh sập N–M.
        try:
            _gout_poly = _gout
            _pending_poly = _pgeom["pending_out"]
        except Exception:
            _gout_poly = None
            _pending_poly = None
            try:
                _pg2 = wall_shear_geometry_poly(winp)
                _rot_p2 = int(getattr(winp, "rot_deg", 0) or 0) % 360
                _gout_poly = _pg2["geom_in"] if _rot_p2 in (90, 270) \
                    else _pg2["geom_out"]
                _pending_poly = _pg2["pending_out"]
            except Exception as ex:
                _pending_poly = (f"Cắt ngoài mặt phẳng: lỗi khi "
                                 f"tính: {ex}")
        if _gout_poly is None:
            shear_out = {"V_d": V_out, "V_cap": None, "dc": None,
                         "ok": None, "parts": {},
                         "note": _pending_poly or
                         "Cắt ngoài mặt phẳng: CHƯA KIỂM"}
            shear_out_lines = [shear_out["note"]]
            details += shear_out_lines
        else:
            shear_out = {"V_d": V_out, "V_cap": None, "dc": None,
                         "ok": None, "parts": {},
                         "note": "Cắt ngoài mặt phẳng: lỗi khi tính (xem chi tiết)"}
            shear_out_lines = []
            try:
                shear_out = check_wall_shear_poly(
                    winp, conc, steel, V_out, N, _gout_poly,
                    float(sec.gross_area), steel_sw=steel_sw)
                _q = shear_out["parts"]
                _dc_o_txt = (f"{shear_out['dc']:.3f}"
                             if shear_out["dc"] is not None
                             and math.isfinite(shear_out["dc"]) else "∞")
                _map_out = ("ánh xạ vách phẳng (DXF chữ nhật)"
                            if _q.get("dxf_rectangle") else
                            "ánh xạ đa giác — GIẢ ĐỊNH TƯƠNG ĐƯƠNG")
                shear_out_lines.append(
                    f"Cắt ngoài mặt phẳng (TCVN 5574:2018 §8.1.3, "
                    f"{_map_out}): "
                    f"V3 = {V_out:.1f} kN; b = {_q['b']:.0f} mm, "
                    f"h0 = {_q['h0']:.0f} mm, thép ngang "
                    f"{_q['sw_txt']} (Rsw = {_q['Rsw']:.0f} MPa, "
                    f"Asw = {_q['Asw']:.0f} mm²); qsw bố trí = "
                    f"{_q['qsw_arr']:.1f} N/mm, qsw được kể = "
                    f"{_q['qsw']:.1f} N/mm; "
                    f"φn = {_q['phi_n']:.3f} (không phóng đại DCM)")
                shear_out_lines.append(f"  {_q['geom_note']}")
                shear_out_lines.append(
                    f"  ĐK1 (dải nén xiên, (88)): [Q]1 = "
                    f"φn×0.3×Rb×b×h0 = {_q['Qcap1']:.1f} kN -> "
                    f"{'ĐẠT' if _q['ok1'] else 'KHÔNG ĐẠT'}; "
                    f"ĐK2 (vết nứt xiên): C = {_q['C_opt']:.0f} mm, "
                    f"Qb = {_q['Qb']:.1f} kN, Qsw = {_q['Qsw']:.1f} "
                    f"kN, [Q]2 = {_q['Qcap2']:.1f} kN -> "
                    f"{'ĐẠT' if _q['ok2'] else 'KHÔNG ĐẠT'}")
                if not _q["cond98_ok"]:
                    shear_out_lines.append(
                        f"  ĐK (98) KHÔNG thỏa: s_h = "
                        f"{_q['s_h']:.0f} mm > s_max = "
                        f"{_q['s_max']:.0f} mm -> thép ngang không "
                        f"được kể, Qsw = 0")
                if not _q["cond96_ok"]:
                    shear_out_lines.append(
                        f"  ĐK (96) KHÔNG thỏa: qsw = "
                        f"{_q['qsw']:.1f} < 0.25×Rbt×b = "
                        f"{_q['qsw_min96']:.1f} N/mm -> Qb theo "
                        f"(97), thép ngang vẫn được kể")
                shear_out_lines.append(
                    f"  V_cap = min([Q]1, [Q]2) = "
                    f"{shear_out['V_cap']:.1f} kN, D/C cắt ngoài "
                    f"MP = {_dc_o_txt} -> "
                    f"{'ĐẠT' if shear_out['ok'] else 'KHÔNG ĐẠT'} "
                    f"(kết luận cắt RIÊNG, không đổi kết luận N–M)")
            except Exception as ex:
                shear_out = {"V_d": V_out, "V_cap": None, "dc": None,
                             "ok": None, "parts": {},
                             "note": f"Cắt ngoài mặt phẳng: lỗi khi "
                                     f"tính: {ex}"}
                shear_out_lines.append(
                    f"Cắt ngoài mặt phẳng: lỗi khi tính: {ex}")
            details += shear_out_lines
    else:
        # --- Cắt ngoài mặt phẳng (lát 4 — phần 4 của chương trình vách) ---
        # Cùng khuôn với cắt trong MP: tính SAU và ĐỘC LẬP với N–M và với
        # cắt trong MP; lỗi cắt (nếu có) chỉ làm shear_out pending, không
        # đánh sập kết quả N–M. ok_all giữ = ok của N–M chỉ để tương
        # thích dict cũ (không render thành kết luận chung); phần này
        # chỉ kết luận RIÊNG trong thẻ chi tiết + số trong dict.
        # V_out = V3 (Q3 nhập tay / V3 pier —
        # xem _collect_wall_loads + WallInput: V_in = V2 trong MP,
        # V_out = V3 ngoài MP); thép ngang ngoài MP mặc định 2 nhánh ×
        # φ(dia_h) @ s_h cùng cấp thép với trong MP (quyết user
        # 2026-10-25, thay thế quyết P4 cũ Qsw = 0) — cùng steel_sw
        # đã suy cho cắt trong MP.
        shear_out = {"V_d": V_out, "V_cap": None, "dc": None,
                     "ok": None, "parts": {},
                     "note": "Cắt ngoài mặt phẳng: lỗi khi tính (xem chi tiết)"}
        shear_out_lines = []
        try:
            shear_out = check_wall_shear_out_of_plane(winp, conc, steel,
                                                      V_out, N, Lw=Lw, tw=tw,
                                                      steel_sw=steel_sw)
            _q = shear_out["parts"]
            _dc_o_txt = (f"{shear_out['dc']:.3f}"
                         if shear_out["dc"] is not None
                         and math.isfinite(shear_out["dc"]) else "∞")
            shear_out_lines.append(
                f"Cắt ngoài mặt phẳng (TCVN 5574:2018 §8.1.3, ánh xạ vách): "
                f"V3 = {V_out:.1f} kN; b = Lw = {_q['b']:.0f} mm, "
                f"h0 = {_q['h0']:.0f} mm (tw - cover - dia_v - dia_h/2), "
                f"thép ngang {_q['sw_txt']} "
                f"(Rsw = {_q['Rsw']:.0f} MPa, Asw = {_q['Asw']:.0f} mm²); "
                f"qsw bố trí = {_q['qsw_arr']:.1f} N/mm, "
                f"qsw được kể = {_q['qsw']:.1f} N/mm; "
                f"φn = {_q['phi_n']:.3f}")
            shear_out_lines.append(
                f"  ĐK1 (dải nén xiên, (88)): [Q]1 = φn×0.3×Rb×b×h0 "
                f"= {_q['Qcap1']:.1f} kN -> "
                f"{'ĐẠT' if _q['ok1'] else 'KHÔNG ĐẠT'}; "
                f"ĐK2 (vết nứt xiên): C = {_q['C_opt']:.0f} mm, "
                f"Qb = {_q['Qb']:.1f} kN, Qsw = {_q['Qsw']:.1f} kN, "
                f"[Q]2 = {_q['Qcap2']:.1f} kN -> "
                f"{'ĐẠT' if _q['ok2'] else 'KHÔNG ĐẠT'}")
            if not _q["cond98_ok"]:
                shear_out_lines.append(
                    f"  ĐK (98) KHÔNG thỏa: s_h = {_q['s_h']:.0f} mm > "
                    f"s_max = {_q['s_max']:.0f} mm -> thép ngang không "
                    f"được kể, Qsw = 0")
            if not _q["cond96_ok"]:
                shear_out_lines.append(
                    f"  ĐK (96) KHÔNG thỏa: qsw = {_q['qsw']:.1f} < "
                    f"0.25×Rbt×b = {_q['qsw_min96']:.1f} N/mm -> Qb theo "
                    f"(97), thép ngang vẫn được kể")
            shear_out_lines.append(
                f"  V_cap = min([Q]1, [Q]2) = {shear_out['V_cap']:.1f} kN, "
                f"D/C cắt ngoài MP = {_dc_o_txt} -> "
                f"{'ĐẠT' if shear_out['ok'] else 'KHÔNG ĐẠT'} "
                f"(kết luận cắt RIÊNG, không đổi kết luận N–M)")
        except Exception as ex:
            shear_out = {"V_d": V_out, "V_cap": None, "dc": None,
                         "ok": None, "parts": {},
                         "note": f"Cắt ngoài mặt phẳng: lỗi khi tính: {ex}"}
            shear_out_lines.append(f"Cắt ngoài mặt phẳng: lỗi khi tính: {ex}")
        details += shear_out_lines
    details.append("Trượt mạch ngừng chân vách: CHƯA kiểm — "
                   + PENDING_SLIDING)

    return {
        "member_type": "wall", "std": "tcvn",
        "winp": winp, "sec": sec, "meta": meta, "model": model,
        "fs_obj": cap.fs,
        "case_info": case_info,
        "N": N, "M_in": M_in, "M_out": M_out,
        "V_in": V_in, "V_out": V_out, "T": T,
        "M_in_d": M_in_d, "M_out_d": M_out_d,
        # Khung solver (canonical/trọng tâm) cho biểu đồ: rect
        # trùng (M_out_d, M_in_d); đa giác là mô men đã xoay ngược.
        "Mx_d": _Mx_d, "My_d": _My_d,
        "Bx_can": r["Bx"], "By_can": r["By"],
        # Trục trong MP sau xoay ("x" cho phẳng + barbell/tee/ell;
        # "y" cho c-core/u-core ở rot 0, hoán đổi khi 90/270°).
        "wall_axis_in": _axis_in_rot,
        "wall_section_type": _stype,
        "dc": dc, "fs": fs_val, "ok": bool(r["ok"]),
        "alpha_deg": alpha_deg, "alpha_solver_deg": _alpha_solver,
        "Malpha": Malpha, "M_capacity": M_cap,
        "Bx": r["Bx"], "By": r["By"], "BN": r["BN"],
        "lambda_ray": r["lambda_max"],
        "m2m3": _m2m3,
        "gamma_deg": r.get("gamma_deg"), "na_info": na_info,
        "c_neutral": c_neutral, "sigma_edge": sigma_edge,
        "Ix": Ix, "Iy": Iy, "Isx": Isx, "Isy": Isy,
        "phi_L": phi, "e0_out": ecc.e0y, "ea_out": ecc.eay,
        "e0_in": ecc.e0x, "ea_in": ecc.eax,
        "slend": {
            "l0_out": l0_out_m * 1000.0, "lambda_out": lam_out,
            "l0_in": l0_in_m * 1000.0, "lambda_in": lam_in,
            "pd_method": pd_method,
            "psi_x": psi_x, "psi_y": psi_y, "Lx_m": Lx_m, "Ly_m": Ly_m,
            "lambda_lim": None,
            "second_order": bool(eta_out > 1.0 or eta_in > 1.0),
            "factor_out": eta_out, "Ncr_out": Ncr_out,
            "factor_in": eta_in, "Ncr_in": Ncr_in,
            "note": _slend_note,
        },
        "boundary": {
            "required": None, "criterion": None,
            "Lb_req_left": None, "Lb_req_right": None,
            "Lb_prov_left": float(winp.Lb_left),
            "Lb_prov_right": float(winp.Lb_right),
            "rho_be": None, "rho_be_min": None,
            "tie": {"ok": None}, "hcr": None, "ok": None,
            "note": PENDING_BOUNDARY,
        },
        "shear_in": shear_in,
        "shear_out": shear_out,
        "sliding": {"V_cap": None, "dc": None, "ok": None,
                    "mu": None, "parts": {}, "note": PENDING_SLIDING},
        "detailing": [], "ok_detail": None,
        "ok_all": bool(r["ok"]),
        "checks_included": (["N-M"]
                            + (["shear_in"]
                               if shear_in.get("ok") is not None else [])
                            + (["shear_out"]
                               if shear_out.get("ok") is not None else [])),
        "checks_pending": (["boundary"]
                           + (["shear_in"]
                              if shear_in.get("ok") is None else [])
                           + (["shear_out"]
                              if shear_out.get("ok") is None else [])
                           + ["sliding", "detailing"]),
        "details": details,
    }
