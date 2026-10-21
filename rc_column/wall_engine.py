"""Engine thuần cho vách chữ nhật đặc (chế độ Vách, GĐ1).

LÁT 1: khả năng chịu N–M theo TCVN 5574:2018 bằng đúng primitive của
bản cột (BiaxialCapacity exact + buckling_factors/eccentricities của
stability.py), KHÔNG qua check_column của cột (hàm đó gói uốn dọc cột
2 phương — vách chỉ phóng đại mô men NGOÀI mặt phẳng theo bề dày tw,
trong mặt phẳng không phóng đại theo §5.2 bản thiết kế).

Khung dict kết quả theo §5 bản thiết kế: các khóa vùng biên / cắt /
mạch ngừng / cấu tạo có mặt từ lát 1 với ok=None + ghi chú lát sẽ làm,
để hiển thị và các lát sau không phải đổi khung.
"""

import math

from .checker import section_inertia
from .interaction import BiaxialCapacity, neutral_axis_at_N
from .stability import (LongTermLoads, buckling_factors, eccentricities,
                        phi_L, slenderness)
from .wall_section import build_wall_section

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
    Lw, tw = float(winp.Lw), float(winp.tw)
    Ix, Iy, ix, iy, Isx, Isy = section_inertia(sec)

    # --- Độ mảnh + uốn dọc NGOÀI mặt phẳng (theo tw) ---
    # Ánh xạ vào hệ cột: phương ngoài MP của vách <-> phương x của cột
    # (Mx = M_out, độ cứng Ix, bề dày cy = tw); L0 lấy theo hệ số liên
    # kết 2 đầu đốt x chiều cao đốt. Trong mặt phẳng: không phóng đại.
    L_story_m = float(winp.h_story) / 1000.0
    l0_out_m = float(winp.l0_out_factor) * L_story_m
    lam_out = slenderness(l0_out_m, tw)
    # Chưa có dữ liệu dài hạn riêng cho vách ở GĐ1 -> phi_L = 2.0
    # (giới hạn trên, thiên an toàn — như cột khi không khai dài hạn).
    lt = LongTermLoads()
    phi = phi_L(N, M_out, M_in, lt)
    ecc = eccentricities(N, M_out, M_in, L_story_m, L_story_m, Lw, tw)
    buck = buckling_factors(ecc.e0x, ecc.e0y, Lw, tw, phi, conc.Eb,
                            Ix, Iy, Isx, Isy, l0_out_m, l0_out_m,
                            N, M_out, M_in)
    eta_out = buck.etax
    Ncr_out = buck.Ncrx
    M_out_d = buck.Mx_star
    M_in_d = M_in

    # --- Sức bền tiết diện: solver fiber exact (tia song trục) ---
    cap = BiaxialCapacity(sec, model=model, n_angles=n_angles)
    r = cap.dc_ratio(N, M_out_d, M_in_d)
    dc = r["dc"]
    fs_val = 1.0 / dc if dc > 1e-12 else float("inf")
    alpha_deg = math.degrees(math.atan2(M_out_d, M_in_d)) \
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

    details = [
        f"Tiết diện vách {Lw:.0f}x{tw:.0f} mm, Ag = {Ag:.0f} mm², "
        f"As = {sec.steel_area:.0f} mm² (µ = {sec.reinforcement_ratio*100:.2f}%)",
        f"Thép: biên {meta['n_be_left'] + meta['n_be_right']} thanh d{float(winp.dia_be):.0f}, "
        f"phân bố đứng {meta['n_web']} thanh d{float(winp.dia_v):.0f} "
        f"(bước thực {meta['s_v_actual'] if meta['s_v_actual'] else 0:.0f} mm)",
        f"Ngoài mặt phẳng: L0 = {l0_out_m:.2f} m, λ = {lam_out:.1f}, "
        f"e0 = {ecc.e0y:.1f} mm, φL = {phi:.2f}, Ncr = {Ncr_out:.0f} kN, "
        f"η = {eta_out:.3f} -> M_out* = {M_out_d:.1f} kN·m",
        f"Trong mặt phẳng: không phóng đại mô men (đốt được giằng 2 đầu) "
        f"-> M_in* = {M_in_d:.1f} kN·m",
        f"Góc α = {alpha_deg:.1f}°, Mα = {Malpha:.1f} kN·m, "
        f"Mα,u = {M_cap:.1f} kN·m tại N = {N:.1f} kN",
        f"D/C = {dc:.3f} (FS = {fs_val:.2f}) -> "
        f"{'ĐẠT' if r['ok'] else 'KHÔNG ĐẠT'} (chỉ N–M, phạm vi lát 1)",
    ]
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
        "slend": {
            "l0_out": l0_out_m * 1000.0, "lambda_out": lam_out,
            "lambda_lim": None,
            "second_order": bool(eta_out > 1.0),
            "factor_out": eta_out, "Ncr_out": Ncr_out,
            "note": "TCVN: η ngoài mặt phẳng theo tw áp mọi λ như cột; "
                    "trong mặt phẳng không phóng đại (đốt giằng 2 đầu).",
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
