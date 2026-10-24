"""Engine thuần cho vách chữ nhật đặc (chế độ Vách, GĐ1).

LÁT 1: khả năng chịu N–M theo TCVN 5574:2018 bằng đúng primitive của
bản cột (BiaxialCapacity exact + buckling_factors/eccentricities của
stability.py), KHÔNG qua check_column của cột (hàm đó gói uốn dọc cột
2 phương). Uốn dọc vách: NGOÀI mặt phẳng η·M_out theo bề dày tw;
TRONG mặt phẳng M_in* = N·max(e1_in, ea_in = Lw/30)·ηx — bổ sung
2026-10-24 theo mô hình web Vietcons (user chốt, THAY thiết kế lát 1
§5.2 "không phóng đại mô men trong mặt phẳng").

Khung dict kết quả theo §5 bản thiết kế: các khóa vùng biên / cắt /
mạch ngừng / cấu tạo có mặt từ lát 1 với ok=None + ghi chú lát sẽ làm,
để hiển thị và các lát sau không phải đổi khung.
"""

import math

from .checker import section_inertia
from .interaction import BiaxialCapacity, neutral_axis_at_N
from .stability import (LongTermLoads, buckling_factors, eccentricities,
                        phi_L, slenderness)
from .wall_section import build_wall_section, wall_dims

PENDING_BOUNDARY = "Chưa kiểm ở lát 1 (vùng biên: lát 3)"
PENDING_SHEAR = "Chưa kiểm ở lát 1 (cắt trong mặt phẳng + mạch ngừng: lát 4)"
PENDING_DETAIL = "Chưa kiểm ở lát 1 (cấu tạo/ρmin: lát 3)"


def wall_tcvn_full(winp, conc, steel, model: str = "3line",
                   loads: dict = None, case_info: dict = None,
                   mesh_step: float = None, n_angles: int = 24) -> dict:
    """Kiểm tra N–M vách theo TCVN cho 1 tổ hợp (engine thuần, không GUI).

    winp: WallInput; conc/steel: ConcreteMaterial/SteelMaterial (TCVN);
    loads: dict {N, M_in, M_out, V_in, V_out, T} — None thì lấy từ winp.
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
    buck = buckling_factors(ecc.e0x, ecc.e0y, Lw, tw, phi, conc.Eb,
                            Ix, Iy, Isx, Isy, l0_out_m, l0_in_m,
                            N, M_out, M_in)
    eta_out = buck.etax
    Ncr_out = buck.Ncrx
    M_out_d = buck.Mx_star
    eta_in = buck.etay
    Ncr_in = buck.Ncry
    if pd_method == "none":
        # "Không xét bổ sung uốn dọc": η = 1 cả 2 phương. Sàn độ lệch
        # tâm e0 = max(e1, ea) ở dưới VẪN áp cho phương trong mặt
        # phẳng — đó là độ lệch tâm thiết kế tối thiểu, tách khỏi η.
        eta_out = 1.0
        eta_in = 1.0
        M_out_d = M_out
    # --- Phóng đại mô men TRONG mặt phẳng (user chốt 2026-10-24) ---
    # M_in* = N x max(e1_in, ea_in) x ηx; ecc.e0x đã là max(e1x, eax)
    # với eax = max(L/600, Lw/30, 10) — tức ea_in = Lw/30 khi Lw lớn
    # (đúng số web Vietcons dùng: 2500/30 = 83.3 mm). ηx = buck.etay
    # = 1/(1 − N/Ncr,x) từ cùng công thức độ cứng TCVN (khe "y").
    if N > 0:
        M_in_d = (math.copysign(N * ecc.e0x * eta_in / 1000.0, M_in)
                  if M_in != 0.0 else 0.0)
    else:
        # N <= 0 (kéo/không tải): không dựng mô men từ sàn lệch tâm
        # (không xác định được dấu) — giữ nguyên M_in, cùng hành vi
        # hiện tại của engine khi N <= 0.
        M_in_d = M_in

    # --- Sức bền tiết diện: solver fiber exact (tia song trục) ---
    cap = BiaxialCapacity(sec, model=model, n_angles=n_angles)
    r = cap.dc_ratio(N, M_out_d, M_in_d)
    dc = r["dc"]
    fs_val = 1.0 / dc if dc > 1e-12 else float("inf")
    # α chuẩn hoá [0, 360) theo quy ước chung của app (mốc ETABS)
    alpha_deg = (math.degrees(math.atan2(M_out_d, M_in_d)) % 360.0) \
        if abs(M_out_d) + abs(M_in_d) > 1e-9 else 0.0
    Malpha = math.hypot(M_out_d, M_in_d)
    M_cap = cap.moment_capacity(N, alpha_deg) if Malpha > 1e-9 else 0.0

    # Chiều cao vùng nén tại điểm biên B của tia (BN = lambda*N)
    c_neutral = None
    na_info = None
    try:
        na_info = neutral_axis_at_N(cap.fs, r["BN"], alpha_deg, model)
        if na_info.get("found"):
            c_neutral = na_info.get("na_depth")
    except Exception:
        na_info = None

    # Ứng suất nén mép (đàn hồi, tiết diện nguyên) — đầu vào cho tiêu
    # chí kích hoạt vùng biên ở lát 3, tính sẵn từ lát 1 theo §5.
    Ag = Lw * tw
    Ig_in = tw * Lw ** 3 / 12.0
    sigma_edge = N * 1000.0 / Ag + abs(M_in) * 1e6 * (Lw / 2.0) / Ig_in

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

    return {
        "member_type": "wall", "std": "tcvn",
        "winp": winp, "sec": sec, "meta": meta, "model": model,
        "fs_obj": cap.fs,
        "case_info": case_info,
        "N": N, "M_in": M_in, "M_out": M_out,
        "V_in": V_in, "V_out": V_out, "T": T,
        "M_in_d": M_in_d, "M_out_d": M_out_d,
        "dc": dc, "fs": fs_val, "ok": bool(r["ok"]),
        "alpha_deg": alpha_deg, "Malpha": Malpha, "M_capacity": M_cap,
        "Bx": r["Bx"], "By": r["By"], "BN": r["BN"],
        "lambda_ray": r["lambda_max"],
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
            "note": "TCVN: η ngoài mặt phẳng theo tw áp mọi λ như cột; "
                    "trong mặt phẳng M_in* = N·max(e1, ea = Lw/30)·ηx "
                    "(theo web Vietcons, user chốt 2026-10-24). "
                    "L0 = ψ x L lấy từ mục 4 tại thời điểm tính.",
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
        "shear_in": {"V_d": V_in, "V_cap": None, "dc": None,
                     "ok": None, "parts": {}, "note": PENDING_SHEAR},
        "sliding": {"V_cap": None, "dc": None, "ok": None,
                    "mu": None, "parts": {}, "note": PENDING_SHEAR},
        "detailing": [], "ok_detail": None,
        "ok_all": bool(r["ok"]),
        "checks_included": ["N-M"],
        "checks_pending": ["boundary", "shear_in", "sliding", "detailing"],
        "details": details,
    }
