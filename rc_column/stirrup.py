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

    Điều kiện 1 (dải nén xiên): Q ≤ 0.3 × Rb × b × h0
    Điều kiện 2 (vết nứt xiên): Q ≤ Qb + Qsw, khảo sát C ∈ [h0, 2h0]
      - Qb = φb2 × Rbt × b × h0² / C (φb2 = 1.5),
             giới hạn [0.5×Rbt×b×h0, 2.5×Rbt×b×h0]
      - Qsw = φsw × qsw × C (φsw = 0.75), qsw = Rsw × Asw / s
    """
    ok: bool
    Q: float = 0.0            # lực cắt tính toán (kN)
    # Điều kiện 1
    Qcap1: float = 0.0         # = 0.3×Rb×b×h0 (kN)
    ok1: bool = True
    # Điều kiện 2
    Qcap2: float = 0.0         # = min(Qb+Qsw) khi khảo sát C (kN)
    C_opt: float = 0.0         # C cho [Q]min (mm)
    Qb_opt: float = 0.0
    Qsw_opt: float = 0.0
    ok2: bool = True
    direction: str = ""        # "2" hoặc "3"


def check_shear(Q: float, b: float, h0: float,
                Rb: float, Rbt: float,
                Asw: float, Rsw: float, s: float,
                direction: str = "") -> ShearResult:
    """Kiểm tra chịu cắt theo TCVN 5574:2018 (như file Excel mẫu).

    Đơn vị: Q (kN), b/h0/s (mm), Rb/Rbt/Rsw (MPa), Asw (mm²).
    Trả về kN.
    """
    res = ShearResult(ok=True, Q=Q, direction=direction)

    # --- Điều kiện 1: độ bền trên dải nén xiên ---
    # Q ≤ [Q] = 0.3 × Rb × b × h0
    res.Qcap1 = 0.3 * Rb * b * h0 / 1000.0
    res.ok1 = abs(Q) <= res.Qcap1 + 1e-9

    # --- Điều kiện 2: độ bền trên vết nứt xiên ---
    # qsw = Rsw × Asw / s (N/mm)
    qsw = Rsw * Asw / s if s > 0 else 0.0
    # Giới hạn Qb
    Qb_min = 0.5 * Rbt * b * h0 / 1000.0
    Qb_max = 2.5 * Rbt * b * h0 / 1000.0
    # Khảo sát C từ h0 đến 2h0 (11 điểm như Excel)
    best = None
    n_pts = 11
    for i in range(n_pts):
        C = h0 + (2 * h0 - h0) * i / (n_pts - 1)
        Qb_tt = 1.5 * Rbt * b * h0 * h0 / C / 1000.0
        Qb = min(max(Qb_tt, Qb_min), Qb_max)
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
    sh (ShearResult), sw_txt (vd "2φ10 a200 + 2φ10 a200"), s_eff.
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
            sh = check_shear(Q, b_w, max(h0, 1), conc_mat.Rb, conc_mat.Rbt,
                             Asw, Rsw, s_eff)
            cols[lbl] = dict(Q=Q, b=b_w, h0=h0, Asw=Asw, qsw=qsw,
                             sh=sh, sw_txt=sw_txt, s_eff=s_eff)
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
