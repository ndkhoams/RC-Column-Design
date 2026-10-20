"""Kiểm tra cấu tạo cốt thép đai cột theo TCVN 5574:2018.

Các điều khoản áp dụng:
- 10.3.4.2: Đường kính đai ≥ 0.25×d_s,max và ≥ 6mm (8mm với B70–B100)
- 10.3.4.4: Bước đai ≤ 15d và ≤ 500mm (400mm với B70–B100);
             nếu hàm lượng thép dọc chịu nén > 1.5% ở một mặt:
             bước đai ≤ 10d và ≤ 300mm (250mm với B70–B100)
- 10.3.4.5: Mỗi thanh dọc (ít nhất cách một thanh) nằm tại vị trí uốn
             của đai; các vị trí uốn cách nhau ≤ 400mm theo chiều rộng mặt bên
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class StirrupInput:
    """Thông số cốt đai do người dùng nhập."""
    dia: float = 8.0        # đường kính đai (mm)
    spacing: float = 200.0  # bước đai (mm)
    legs: int = 2           # số nhánh đai


@dataclass
class StirrupCheck:
    item: str
    required: str
    provided: str
    ok: bool


@dataclass
class StirrupResult:
    ok: bool
    checks: List[StirrupCheck] = field(default_factory=list)
    # Giá trị tính toán để hiển thị
    d_sw_min: float = 0.0   # đường kính tối thiểu yêu cầu
    s_max: float = 0.0      # bước tối đa cho phép


@dataclass
class ShearResult:
    """Kết quả kiểm tra chịu cắt theo TCVN 5574:2018.

    Điều kiện 1 (dải nén xiên): Q ≤ φn × 0.3 × Rb × b × h0
    Điều kiện 2 (vết nứt xiên): Q ≤ Qb + Qsw, khảo sát C ∈ [h0, 2h0]
      - Qb = φn × φb2 × Rbt × b × h0² / C (φb2 = 1.5),
             giới hạn [0.5×Rbt×b×h0, 2.5×Rbt×b×h0] trước khi nhân φn;
             nếu điều kiện (96) không thỏa (qsw < 0.25×Rbt×b) thì
             Qb = φn × 4×φb2×h0²×qsw/C theo công thức (97)
      - Qsw = φsw × qsw × C (φsw = 0.75), qsw = Rsw × Asw / s (KHÔNG nhân φn)
      - φn theo §8.1.3.3.2 từ lực dọc N và diện tích toàn tiết diện
    """
    ok: bool
    Q: float = 0.0            # lực cắt tính toán (kN)
    # Điều kiện 1
    Qcap1: float = 0.0         # = φn×0.3×Rb×b×h0 (kN)
    ok1: bool = True
    # Điều kiện 2
    Qcap2: float = 0.0         # = min(Qb+Qsw) khi khảo sát C (kN)
    C_opt: float = 0.0         # C cho [Q]min (mm)
    Qb_opt: float = 0.0        # Qb tại C_opt, đã gồm φn (kN)
    Qsw_opt: float = 0.0
    ok2: bool = True
    direction: str = ""        # "2" hoặc "3"
    # TCVN 5574:2018 §8.1.3.3.2 — ảnh hưởng ứng suất dọc trục
    phi_n: float = 1.0         # hệ số φn đã áp vào vế phải (88)/(90)/(94)
    sigma_m: float = 0.0       # MPa — ứng suất nén trung bình (>0 khi nén)
    sigma_t: float = 0.0       # MPa — ứng suất kéo trung bình (>0 khi kéo)
    # TCVN 5574:2018 điều kiện (96) — kể cốt đai vào tính toán
    cond96_ok: bool = True     # qsw >= 0.25*Rbt*b (True cả khi không có đai)
    qsw_min96: float = 0.0     # N/mm — ngưỡng 0.25*Rbt*b của phương
    qb_mode: str = "CT90"      # "CT90": Qb theo (90); "CT97": Qb theo (97)
                               # khi (96) không thỏa; "NONE": không có đai


def phi_n_tcvn(N_kN: float, A_mm2: float, Rb: float, Rbt: float):
    """Hệ số φn — TCVN 5574:2018 §8.1.3.3.2.

    Trả về (phi_n, sigma_m, sigma_t). N_kN: lực dọc, DƯƠNG = nén (quy ước app).
    sigma = |N| / A với A = diện tích toàn tiết diện (chuẩn cho phép không kể
    cốt thép khi hàm lượng thép dọc <= 3%).
      Nén:  φn = 1 + σm/Rb        khi 0 < σm <= 0.25*Rb
            φn = 1.25             khi 0.25*Rb < σm <= 0.75*Rb
            φn = 5*(1 - σm/Rb)    khi 0.75*Rb < σm <= Rb
      Kéo:  φn = 1 - σt/(2*Rbt)   khi 0 < σt <= Rbt
      N = 0: φn = 1.
    Ngoài miền định nghĩa (σm > Rb hoặc σt > Rbt) kéo dài tuyến tính nhánh
    cuối và chặn dưới 0 (diễn giải — ghi rõ trong báo cáo đợt áp dụng).
    """
    if A_mm2 <= 0 or N_kN == 0:
        return 1.0, 0.0, 0.0
    sigma = abs(N_kN) * 1000.0 / A_mm2  # MPa
    if N_kN > 0:  # nén
        r = sigma / Rb if Rb > 0 else 0.0
        if r <= 0.25:
            phi = 1.0 + r
        elif r <= 0.75:
            phi = 1.25
        else:
            phi = 5.0 * (1.0 - r)
        return max(phi, 0.0), sigma, 0.0
    # kéo
    phi = 1.0 - sigma / (2.0 * Rbt) if Rbt > 0 else 1.0
    return max(phi, 0.0), 0.0, sigma


def check_shear(Q: float, b: float, h0: float,
                Rb: float, Rbt: float,
                Asw: float, Rsw: float, s: float,
                direction: str = "",
                N: float = 0.0, A_sec: float = 0.0) -> ShearResult:
    """Kiểm tra chịu cắt theo TCVN 5574:2018 (như file Excel mẫu).

    Đơn vị: Q (kN), b/h0/s (mm), Rb/Rbt/Rsw (MPa), Asw (mm²).
    N (kN, dương = nén) và A_sec (mm², diện tích toàn tiết diện) dùng để
    tính hệ số φn theo §8.1.3.3.2; A_sec <= 0 -> φn = 1 (không kể lực dọc).
    Trả về kN.
    """
    res = ShearResult(ok=True, Q=Q, direction=direction)

    # --- Hệ số φn (§8.1.3.3.2): nhân vào vế phải (88), (90), (94) ---
    phi_n, sigma_m, sigma_t = phi_n_tcvn(N, A_sec, Rb, Rbt)
    res.phi_n, res.sigma_m, res.sigma_t = phi_n, sigma_m, sigma_t

    # --- Điều kiện 1: độ bền trên dải nén xiên (88) ---
    # Q ≤ [Q] = φn × 0.3 × Rb × b × h0
    res.Qcap1 = phi_n * 0.3 * Rb * b * h0 / 1000.0
    res.ok1 = abs(Q) <= res.Qcap1 + 1e-9

    # --- Điều kiện 2: độ bền trên vết nứt xiên ---
    # qsw = Rsw × Asw / s (N/mm)
    qsw = Rsw * Asw / s if s > 0 else 0.0
    # Giới hạn Qb (áp cho cả (90) và (97) theo văn bản điều (96))
    Qb_min = 0.5 * Rbt * b * h0 / 1000.0
    Qb_max = 2.5 * Rbt * b * h0 / 1000.0
    # Điều kiện (96): qsw >= 0.25*Rbt*b mới kể đai theo (90);
    # không thỏa nhưng có đai -> Qb theo công thức (97), đai vẫn được kể
    res.qsw_min96 = 0.25 * Rbt * b
    has_sw = Asw > 0 and qsw > 0
    use97 = has_sw and qsw < res.qsw_min96 - 1e-12
    res.cond96_ok = not use97
    res.qb_mode = "CT97" if use97 else ("CT90" if has_sw else "NONE")
    # Khảo sát C từ h0 đến 2h0 (11 điểm như Excel);
    # φn nằm TRONG vòng khảo sát (nhân vào Qb sau khi chặn [0.5, 2.5])
    best = None
    n_pts = 11
    for i in range(n_pts):
        C = h0 + (2 * h0 - h0) * i / (n_pts - 1)
        if use97:
            # (97): Qb = 4*φb2*h0²*qsw/C, φb2 = 1.5
            Qb_tt = 4 * 1.5 * h0 * h0 * qsw / C / 1000.0
        else:
            # (90): Qb = φb2*Rbt*b*h0²/C, φb2 = 1.5
            Qb_tt = 1.5 * Rbt * b * h0 * h0 / C / 1000.0
        Qb = phi_n * min(max(Qb_tt, Qb_min), Qb_max)
        Qsw = 0.75 * qsw * C / 1000.0
        Qcap = Qb + Qsw
        if best is None or Qcap < best[0]:
            best = (Qcap, C, Qb, Qsw)
    res.Qcap2, res.C_opt, res.Qb_opt, res.Qsw_opt = best
    res.ok2 = abs(Q) <= res.Qcap2 + 1e-9

    res.ok = res.ok1 and res.ok2
    return res


def compute_shear_cols(inp, sec) -> dict:
    """Tính kiểm tra chịu cắt TCVN 2 phương từ ColumnInput — NGUỒN DUY NHẤT.

    Mọi nơi (tab Kết quả/Chi tiết, PDF tóm tắt/chi tiết) đều đọc dict này,
    KHÔNG tự tính lại (nguyên tắc "tính 1 lần, hiển thị nhiều nơi").

    Trả về {"2": {...}, "3": {...}}; mỗi dict gồm:
    Q, b, h0, Asw (bao + giữa theo phương), qsw (= Σ Rsw·Asw,i/si),
    sh (ShearResult — đã gồm φn §8.1.3.3.2 và điều kiện (96)/(97)),
    sw_txt (vd "2φ10 a200 + 2φ10 a200"), s_eff, phi_n, cond96_ok, qb_mode.
    Lỗi bất kỳ -> {} (giữ hành vi cũ của _tcvn_calculate_full).
    """
    from .sections import bar_area
    from .materials import CONCRETE_GRADES, STEEL_GRADES, ConcreteMaterial
    cols = {}
    try:
        stir_in = StirrupInput(dia=inp.sw_dia, spacing=inp.sw_spacing,
                               legs=inp.sw_legs)
        conc_mat = ConcreteMaterial(CONCRETE_GRADES[inp.concrete_grade],
                                    inp.gamma_b)
        swg = STEEL_GRADES.get(inp.sw_steel_grade)
        # (kết quả cấu tạo không dùng ở đây — giữ lời gọi như bản gốc)
        check_stirrup(sec, stir_in, inp.cover)
        for Q, lbl, b_w, h_dim, mdia, ms, mlegs in (
                (inp.Q2, "2", inp.cy, inp.cx,
                 inp.swm2_dia, inp.swm2_spacing, inp.swm2_legs),
                (inp.Q3, "3", inp.cx, inp.cy,
                 inp.swm3_dia, inp.swm3_spacing, inp.swm3_legs)):
            h0 = h_dim - inp.cover - inp.sw_dia - 12
            # Đai bao ngoài
            Asw_outer = stir_in.legs * bar_area(stir_in.dia)
            s_outer = stir_in.spacing
            Rsw = swg.Rsw if swg else 0
            # qsw = Σ(Rsw×Asw,i/si) theo TCVN 5574:2018 (8.1.3)
            qsw = Rsw * Asw_outer / s_outer if s_outer > 0 else 0
            Asw = Asw_outer
            sw_txt = (f"{stir_in.legs:.0f}φ{stir_in.dia:.0f} "
                      f"a{stir_in.spacing:.0f}")
            # Cộng đai giữa (nếu có) - tính đúng theo spacing riêng
            if mdia and ms:
                try:
                    mdia_f = float(mdia)
                    ms_f = float(ms)
                    mlegs_i = int(mlegs)
                    if mdia_f > 0 and ms_f > 0 and mlegs_i > 0:
                        Asw_mid = mlegs_i * bar_area(mdia_f)
                        Asw += Asw_mid
                        qsw += Rsw * Asw_mid / ms_f
                        sw_txt += f" + {mlegs_i}φ{mdia_f:.0f} a{ms_f:.0f}"
                except Exception:
                    pass
            # Bước đai tương đương để check_shear tính đúng qsw
            s_eff = Rsw * Asw / qsw if qsw > 0 else s_outer
            # φn (§8.1.3.3.2): N của tổ hợp đang kiểm tra + diện tích
            # toàn tiết diện (gross) — cùng 1 N cho cả 2 phương
            try:
                A_sec = float(sec.gross_area)
            except Exception:
                A_sec = float(inp.cx) * float(inp.cy)
            sh = check_shear(Q, b_w, max(h0, 1), conc_mat.Rb, conc_mat.Rbt,
                             Asw, Rsw, s_eff, direction=lbl,
                             N=float(getattr(inp, "N", 0.0) or 0.0),
                             A_sec=A_sec)
            cols[lbl] = dict(Q=Q, b=b_w, h0=h0, Asw=Asw, qsw=qsw,
                             sh=sh, sw_txt=sw_txt, s_eff=s_eff,
                             phi_n=sh.phi_n, cond96_ok=sh.cond96_ok,
                             qb_mode=sh.qb_mode)
    except Exception:
        return {}
    return cols


def _is_high_grade(concrete_grade: str) -> bool:
    """Bê tông từ B70 đến B100."""
    try:
        num = int("".join(c for c in concrete_grade if c.isdigit()))
        return 70 <= num <= 100
    except Exception:
        return False


def check_stirrup(sec, stir: StirrupInput,
                  concrete_grade: str = "B25") -> StirrupResult:
    """Kiểm tra cấu tạo cốt đai theo TCVN 5574:2018.

    sec: ColumnSection (có .rebars với .dia, .cx, .cy)
    """
    res = StirrupResult(ok=True, checks=[])
    high = _is_high_grade(concrete_grade)

    # --- 10.3.4.2: Đường kính đai tối thiểu ---
    d_s_max = max((r.dia for r in sec.rebars), default=0)
    d_sw_min = max(0.25 * d_s_max, 8.0 if high else 6.0)
    res.d_sw_min = d_sw_min
    ok_d = stir.dia >= d_sw_min - 1e-9
    res.checks.append(StirrupCheck(
        "Đường kính đai (10.3.4.2)",
        f"≥ max(0.25×{d_s_max:.0f}, {'8' if high else '6'}) = {d_sw_min:.1f} mm",
        f"φ{stir.dia:.0f}",
        ok_d,
    ))
    res.ok &= ok_d

    # --- 10.3.4.4: Bước đai tối đa ---
    d_s_min = min((r.dia for r in sec.rebars), default=0)
    # Hàm lượng thép dọc chịu nén ở một mặt (xấp xỉ: tổng As / Ac)
    # Theo điều khoản: nếu > 1.5% ở MỘT MẶT thì siết chặt
    # Tính gần đúng: As_mặt / (b × h)
    As_total = sum(3.1416 * r.dia ** 2 / 4 for r in sec.rebars)
    Ac = sec.cx * sec.cy
    rho_face = (As_total / 2) / Ac * 100 if Ac > 0 else 0  # xấp xỉ 1 mặt

    if rho_face > 1.5:
        s_lim_d = 10 * d_s_min
        s_lim_abs = 250 if high else 300
        note = f"ρ_mặt ≈ {rho_face:.2f}% > 1.5%"
    else:
        s_lim_d = 15 * d_s_min
        s_lim_abs = 400 if high else 500
        note = f"ρ_mặt ≈ {rho_face:.2f}% ≤ 1.5%"

    s_max = min(s_lim_d, s_lim_abs)
    res.s_max = s_max
    ok_s = stir.spacing <= s_max + 1e-9
    res.checks.append(StirrupCheck(
        f"Bước đai (10.3.4.4) — {note}",
        f"≤ min({s_lim_d:.0f}, {s_lim_abs}) = {s_max:.0f} mm",
        f"{stir.spacing:.0f} mm",
        ok_s,
    ))
    res.ok &= ok_s

    # --- 10.3.4.5: Vị trí uốn đai ---
    # Yêu cầu: mỗi thanh dọc (ít nhất cách một thanh) tại vị trí uốn;
    # các vị trí uốn cách nhau ≤ 400mm theo chiều rộng mặt bên.
    # Kiểm tra đơn giản: số nhánh đai đủ để giữ các thanh
    n_bars = len(sec.rebars)
    # Với đai 2 nhánh: giữ được các thanh ở 4 góc + cạnh (nếu nx, ny ≤ 3)
    # Ước lượng: cần ít nhất ceil(n_bars / 4) vị trí uốn mỗi cạnh...
    # Kiểm tra thực tế: khoảng cách giữa các thanh ngoài cùng ≤ 400mm
    # đã được đảm bảo bởi 10.3.3.3 (400/500mm). Ở đây kiểm tra số nhánh.
    min_legs = 2
    # Nếu mỗi cạnh > 4 thanh, cần thêm nhánh
    nx = getattr(sec, "nx", 3)
    ny = getattr(sec, "ny", 3)
    if nx > 4 or ny > 4:
        min_legs = 4  # cần đai kép hoặc thêm nhánh
    ok_legs = stir.legs >= min_legs
    res.checks.append(StirrupCheck(
        "Cấu tạo nhánh đai (10.3.4.5)",
        f"≥ {min_legs} nhánh (mỗi cạnh ≤ 4 thanh)",
        f"{stir.legs} nhánh",
        ok_legs,
    ))
    res.ok &= ok_legs

    return res
