"""Build widget thuyết minh tính toán kiểu Vietcon (mục 1-6).

Style theo vietcons.org: card trắng viền xám nhạt, header mục có chấm màu +
tiêu đề in hoa đậm + tham chiếu TCVN bên phải, lưới 2 cột, khối công thức có
viền trái, kết quả in đậm. Hệ trục 2/3 (không dùng X/Y).
Mục 7 (thép đai) giữ nguyên, không đụng tới.
"""

import math
import tkinter as tk
from tkinter import ttk

from .checker import ColumnInput, CheckResult
from .checker import build_section
from .materials import STEEL_GRADES, EPS_B1, EPS_B2, EPS_S2

def _full_case_w(d):
    parts = []
    if d.get("story"):
        parts.append(str(d["story"]))
    if d.get("column"):
        parts.append(str(d["column"]))
    parts.append(f"{d.get('case', '')}@{d.get('station', 0):.2f}")
    return "[" + ", ".join(parts) + "]"


WHITE = "#FFFFFF"
BORDER = "#E5E7EB"
TEXT = "#111827"
GRAY = "#6B7280"
FORMULA_BG = "#F9FAFB"

_DOT_COLORS = ["#2563EB", "#059669", "#D97706", "#7C3AED", "#DB2777", "#0891B2"]


def _f(x: float, nd: int = 2) -> str:
    try:
        return f"{x:,.{nd}f}"
    except Exception:
        return "—"


def _card(parent) -> tk.Frame:
    """Một card trắng viền xám nhạt, bo góc nhẹ."""
    f = tk.Frame(parent, bg=WHITE, highlightbackground=BORDER,
                 highlightthickness=1, padx=12, pady=10)
    return f


def _section_header(parent, num: int, title: str, ref: str):
    """Header mục: chấm màu + tiêu đề in hoa + ref TCVN bên phải."""
    hdr = tk.Frame(parent, bg=WHITE)
    hdr.pack(fill=tk.X, padx=4, pady=(14, 6))
    dot = tk.Label(hdr, text="●", fg=_DOT_COLORS[(num - 1) % len(_DOT_COLORS)],
                   bg=WHITE, font=("", 10))
    dot.pack(side=tk.LEFT, padx=(2, 6))
    tk.Label(hdr, text=f"{num}. {title}", font=("", 11, "bold"),
             fg=TEXT, bg=WHITE).pack(side=tk.LEFT)
    tk.Label(hdr, text=ref, font=("", 8), fg=GRAY,
             bg=WHITE).pack(side=tk.RIGHT, padx=4)


def _param_card(parent, title: str, ref: str, lines, result: str = ""):
    """Card thông số: tiêu đề + ref, khối công thức, kết quả đậm."""
    c = _card(parent)
    top = tk.Frame(c, bg=WHITE)
    top.pack(fill=tk.X, pady=(0, 6))
    tk.Label(top, text=title, font=("", 10, "bold"), fg=TEXT,
             bg=WHITE, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
    if ref:
        tk.Label(top, text=ref, font=("", 8), fg=GRAY,
                 bg=WHITE).pack(side=tk.RIGHT)
    # Khối công thức: viền trái xám
    fb = tk.Frame(c, bg=FORMULA_BG, highlightbackground=BORDER,
                  highlightthickness=0, padx=10, pady=6)
    fb.pack(fill=tk.X)
    # viền trái bằng frame mỏng
    fb_inner = tk.Frame(fb, bg=FORMULA_BG)
    fb_inner.pack(fill=tk.X, padx=(6, 0))
    left_bar = tk.Frame(fb, bg="#D1D5DB", width=3)
    left_bar.place(relx=0, rely=0, relheight=1, width=3)
    for ln in lines:
        tk.Label(fb_inner, text=ln, font=("TkFixedFont", 9),
                 fg="#374151", bg=FORMULA_BG, anchor="w",
                 justify=tk.LEFT).pack(fill=tk.X, pady=1)
    if result:
        tk.Label(c, text=result, font=("", 10, "bold"), fg=TEXT,
                 bg=WHITE, anchor="w").pack(fill=tk.X, pady=(6, 0))
    return c


def _grid2(parent):
    """Khung lưới 2 cột; các hàng có weight để 2 card cùng hàng
    luôn căng đều chiều cao, thẳng hàng trái-phải."""
    g = tk.Frame(parent, bg=WHITE)
    g.pack(fill=tk.X, padx=4)
    g.columnconfigure(0, weight=1, uniform="col")
    g.columnconfigure(1, weight=1, uniform="col")
    # Cấu hình sẵn weight cho các hàng (đủ cho mọi mục)
    for r in range(30):
        g.rowconfigure(r, weight=1)
    return g


def _build_sec1(g, inp: ColumnInput, res: CheckResult, sec):
    conc = sec.concrete
    steel = sec.steel
    _section_header(g, 1, "ĐẶC TRƯNG VẬT LIỆU",
                    "TCVN 5574:2018 Mục 6.1 & 6.2")
    grid = _grid2(g)
    from .materials import STEEL_GRADES as _SG
    _swg = _SG.get(getattr(inp, "sw_steel_grade", "CB400-V"), _SG["CB400-V"])

    # Bê tông (gộp các chỉ tiêu)
    c = _param_card(grid, f"Bê tông ({inp.concrete_grade})",
                    "Bảng 6, Bảng 10 & Mục 6.1.2.3",
                    [f"Rb* = γb·Rb = {_f(inp.gamma_b)} × {_f(conc.grade.Rb)}",
                     f"= {_f(conc.Rb)} MPa",
                     f"Eb ({inp.concrete_grade}) = {conc.Eb:,.0f} MPa"])
    c.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
    # Cốt thép dọc (gộp các chỉ tiêu)
    c = _param_card(grid, f"Cốt thép dọc ({inp.steel_grade})",
                    "Bảng 13 & Mục 6.2.2",
                    [f"Rs = (Rsn/γs)·γsi = {_f(steel.Rs, 1)} MPa",
                     f"Rsc = {_f(steel.Rsc, 1)} MPa",
                     f"Es = {steel.Es:,.0f} MPa"])
    c.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
    # Cốt thép đai (gộp các chỉ tiêu)
    c = _param_card(grid, f"Cốt thép đai ({getattr(inp, 'sw_steel_grade', 'CB400-V')})",
                    "Bảng 13",
                    [f"Rsw = {_f(_swg.Rsw * inp.gamma_s, 1)} MPa",
                     f"Es = {steel.Es:,.0f} MPa"])
    c.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
    # Thông tin khác
    c = _param_card(grid, "Tỷ số mô đun đàn hồi αe", "Mô hình quy đổi",
                    [f"αe = Es / Eb",
                     f"= {steel.Es:,.0f} / {conc.Eb:,.0f}",
                     f"= {_f(res.alpha_e)}"])
    c.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)




def _build_sec2(g, inp: ColumnInput, res: CheckResult, sec):
    is_circle = getattr(sec, "kind", "rect") == "circle"
    if is_circle:
        D = getattr(inp, "cx", 0) or 0
        _section_header(g, 2, "ĐẶC TRƯNG HÌNH HỌC TIẾT DIỆN CỘT TRÒN",
                        f"Đường kính D = {D:.0f} mm")
    else:
        _section_header(g, 2, "ĐẶC TRƯNG HÌNH HỌC TIẾT DIỆN", "")
    grid = _grid2(g)
    if is_circle:
        D = getattr(inp, "cx", 0) or 0
        # A = πD²/4
        c = _param_card(grid, "Diện tích tiết diện bê tông nguyên A", "",
                        [f"A = π·D²/4",
                         f"= π × {D:.0f}² / 4",
                         f"= {sec.gross_area:,.0f} mm² "
                         f"(= {_f(sec.gross_area / 1e6, 4)} m²)"])
        c.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        # As
        from collections import Counter as _CtrA
        _cntA = _CtrA(getattr(r, "dia", 0) for r in sec.rebars)
        _barA = " + ".join(f"{_cntA[d]:.0f}d{d:.0f}" for d in sorted(_cntA, reverse=True))
        c = _param_card(grid, "Diện tích cốt thép dọc As", "",
                        [f"Số thanh: {_barA}",
                         f"Tổng As: {sec.steel_area:.0f} mm²",
                         f"Hàm lượng μ: {100*sec.reinforcement_ratio:.2f}%"])
        c.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        # I = πD⁴/64 (đối xứng trục)
        c = _param_card(grid, "Mô men quán tính (I2 = I3)", "",
                        [f"I = π·D⁴/64",
                         f"= π × {D:.0f}⁴ / 64",
                         f"= {_f(res.Ix / 1e9, 3)} × 10⁹ mm⁴"])
        c.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        c = _param_card(grid, "Bán kính quán tính (i2 = i3)", "",
                        [f"i = √(I / A) = D / 4",
                         f"= {D:.0f} / 4",
                         f"= {_f(res.ix, 2)} mm "])
        c.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        return
    # A
    c = _param_card(grid, "Diện tích tiết diện bê tông nguyên A", "",
                    [f"A = t2 · t3",
                     f"= {inp.cy:.0f} × {inp.cx:.0f}",
                     f"= {sec.gross_area:,.0f} mm² "
                     f"(= {_f(sec.gross_area / 1e6, 4)} m²)"])
    c.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
    # c
    c = _param_card(grid, "Lớp bê tông bảo vệ cốt dọc c", "",
                    [f"c = {inp.cover:.0f} mm",
                     "Chiều dày lớp bê tông bảo vệ",
                     f"= {inp.cover:.0f} mm"])
    c.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
    # I2 = Ix = Cx*Cy^3/12 ; I3 = Iy = Cy*Cx^3/12 (theo report.py)
    c = _param_card(grid, "Mô men quán tính trục 2 (I2)", "",
                    [f"I₂ = (t3 · t2³) / 12",
                     f"= ({inp.cx:.0f} × {inp.cy:.0f}³) / 12",
                     f"= {_f(res.Ix / 1e9, 3)} × 10⁹ mm⁴"])
    c.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Mô men quán tính trục 3 (I3)", "",
                    [f"I₃ = (t2 · t3³) / 12",
                     f"= ({inp.cy:.0f} × {inp.cx:.0f}³) / 12",
                     f"= {_f(res.Iy / 1e9, 3)} × 10⁹ mm⁴"])
    c.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
    # i2 = ix = Cy/√12 ; i3 = iy = Cx/√12
    c = _param_card(grid, "Bán kính quán tính phương 2 (i2)", "",
                    [f"i₂ = √(I₂ / A) = t2 / √12",
                     f"= {inp.cy:.0f} / 3.464",
                     f"= {_f(res.ix, 2)} mm "])
    c.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Bán kính quán tính phương 3 (i3)", "",
                    [f"i₃ = √(I₃ / A) = t3 / √12",
                     f"= {inp.cx:.0f} / 3.464",
                     f"= {_f(res.iy, 2)} mm "])
    c.grid(row=2, column=1, sticky="nsew", padx=4, pady=4)


def _build_sec3(g, inp: ColumnInput, res: CheckResult, sec):
    _section_header(g, 3, "CHIỀU DÀI TÍNH TOÁN & ĐỘ MẢNH",
                    "TCVN 5574:2018 Mục 8.1.2.4")
    grid = _grid2(g)
    c = _param_card(grid, "Chiều dài tính toán phương 2 (L02)", "",
                    [f"L₀₂ = ψ · L = {_f(inp.psi_x, 2)} × {_f(inp.Lx, 2)}",
                     f"= {_f(res.L0x, 2)} m"])
    c.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Chiều dài tính toán phương 3 (L03)", "",
                    [f"L₀₃ = ψ · L = {_f(inp.psi_y, 2)} × {_f(inp.Ly, 2)}",
                     f"= {_f(res.L0y, 2)} m"])
    c.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
    ok2 = "ĐẠT" if res.lambda_x <= 120 else "KHÔNG ĐẠT"
    ok3 = "ĐẠT" if res.lambda_y <= 120 else "KHÔNG ĐẠT"
    c = _param_card(grid, "Độ mảnh cột phương 2 (λ2)", "",
                    [f"λ₂ = L₀₂ / i₂",
                     f"= {_f(res.L0x * 1000, 0)} / {_f(res.iy, 1)}",
                     f"= {_f(res.lambda_x, 1)} ≤ 120 → {ok2}"])
    c.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Độ mảnh cột phương 3 (λ3)", "",
                    [f"λ₃ = L₀₃ / i₃",
                     f"= {_f(res.L0y * 1000, 0)} / {_f(res.iy, 1)}",
                     f"= {_f(res.lambda_y, 1)} ≤ 120 → {ok3}"])
    c.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
    # Điều kiện xét hiệu ứng uốn dọc (TCVN 5574:2018 Mục 8.1.2.1.2)
    # Phương 2: xét khi λ2 > 14 hoặc L02/t2 > 4 ; Phương 3 tương tự với t3
    l02_t2 = (res.L0x * 1000) / inp.cy if inp.cy > 0 else 0
    l03_t3 = (res.L0y * 1000) / inp.cx if inp.cx > 0 else 0
    need2 = res.lambda_x > 14 or l02_t2 > 4
    need3 = res.lambda_y > 14 or l03_t3 > 4
    kl2 = "BẮT BUỘC XÉT UỐN DỌC (kể đến hệ số η₂)" if need2 else "KHÔNG CẦN XÉT UỐN DỌC"
    kl3 = "BẮT BUỘC XÉT UỐN DỌC (kể đến hệ số η₃)" if need3 else "KHÔNG CẦN XÉT UỐN DỌC"
    c = _param_card(grid, "Điều kiện xét hiệu ứng uốn dọc phương 2",
                    "Mục 8.1.2.1.2",
                    [f"Xét khi λ₂ > 14 hoặc L₀₂ / t2 > 4",
                     f"λ₂ = {_f(res.lambda_x, 2)} {'>' if res.lambda_x > 14 else '≤'} 14",
                     f"L₀₂ / t2 = {_f(l02_t2, 2)}",
                     f"= {kl2}"])
    c.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Điều kiện xét hiệu ứng uốn dọc phương 3",
                    "Mục 8.1.2.1.2",
                    [f"Xét khi λ₃ > 14 hoặc L₀₃ / t3 > 4",
                     f"λ₃ = {_f(res.lambda_y, 2)} {'>' if res.lambda_y > 14 else '≤'} 14",
                     f"L₀₃ / t3 = {_f(l03_t3, 2)}",
                     f"= {kl3}"])
    c.grid(row=2, column=1, sticky="nsew", padx=4, pady=4)


def _build_sec4(g, inp: ColumnInput, res: CheckResult, sec, case_info=None):
    _section_header(g, 4,
                    "ĐỘ LỆCH TÂM TĨNH HỌC, ĐỘ LỆCH TÂM NGẪU NHIÊN & "
                    "ĐỘ LỆCH TÂM BAN ĐẦU",
                    "TCVN 5574:2018 Mục 8.1.2.2.4")
    if case_info:
        tk.Label(g, text=f"Tổ hợp tính toán: {_full_case_w(case_info)} — "
                 f"N = {_f(case_info.get('N', 0), 1)} kN, "
                 f"M2 = {_f(case_info.get('M2', 0), 1)} kN·m, "
                 f"M3 = {_f(case_info.get('M3', 0), 1)} kN·m",
                 font=("", 9), fg="#374151", bg=WHITE,
                 anchor="w").pack(fill=tk.X, padx=8, pady=4)
    N = abs(res.N) if res.N else 1.0
    M2 = abs(res.Mx_star / res.etax) if res.etax else 0.0
    M3 = abs(res.My_star / res.etay) if res.etay else 0.0
    grid = _grid2(g)
    # e1: tĩnh học
    c = _param_card(grid, "Độ lệch tâm tĩnh học phương 2 (e12)",
                    "Mục 8.1.2.2.4",
                    [f"e₁₂ = |M₂| / N",
                     f"= ({_f(M2 * 1000, 2)} × 10³) / {_f(N, 2)}",
                     f"= {_f(res.e1x, 2)} mm"])
    c.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Độ lệch tâm tĩnh học phương 3 (e13)",
                    "Mục 8.1.2.2.4",
                    [f"e₁₃ = |M₃| / N",
                     f"= ({_f(M3 * 1000, 2)} × 10³) / {_f(N, 2)}",
                     f"= {_f(res.e1y, 2)} mm"])
    c.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
    # ea: ngẫu nhiên
    c = _param_card(grid, "Độ lệch tâm ngẫu nhiên phương 2 (ea2)", "",
                    [f"ea₂ = max(t2/600, L₀₂/600, 10mm)",
                     f"= {_f(res.eax, 1)} mm"])
    c.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Độ lệch tâm ngẫu nhiên phương 3 (ea3)", "",
                    [f"ea₃ = max(t3/600, L₀₃/600, 10mm)",
                     f"= {_f(res.eay, 1)} mm"])
    c.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
    # e0: ban đầu
    c = _param_card(grid, "Độ lệch tâm ban đầu phương 2 (e02)", "",
                    [f"e₀₂ = e₁₂ + ea₂",
                     f"= {_f(res.e1x, 1)} + {_f(res.eax, 1)}",
                     f"= {_f(res.e0x, 1)} mm"])
    c.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Độ lệch tâm ban đầu phương 3 (e03)", "",
                    [f"e₀₃ = e₁₃ + ea₃",
                     f"= {_f(res.e1y, 1)} + {_f(res.eay, 1)}",
                     f"= {_f(res.e0y, 1)} mm"])
    c.grid(row=2, column=1, sticky="nsew", padx=4, pady=4)


def _build_sec5(g, inp: ColumnInput, res: CheckResult, sec):
    _section_header(g, 5,
                    "ĐỘ CỨNG CHỐNG UỐN, LỰC TỚI HẠN EULER & PHÓNG ĐẠI MÔ MEN UỐN DỌC",
                    "TCVN 5574:2018 Công thức (44) - (48)")
    conc = sec.concrete
    steel = sec.steel
    Eb = conc.Eb / 1000.0  # kN/mm² -> để tính D (kN·m²)
    Es = steel.Es / 1000.0
    # Giá trị cho từng phương: 2 (X) và 3 (Y)
    # Phương 2: dùng e03, t2, Ix, Isx ; Phương 3: dùng e02, t3, Iy, Isy
    N = abs(res.N)
    M2_orig = abs(res.Mx_star / res.etax) if res.etax else 0.0
    M3_orig = abs(res.My_star / res.etay) if res.etay else 0.0
    grid = _grid2(g)
    # Dữ liệu từng phương: (tên, e0, t, I, Is, delta, kb, D, Ncr, eta, M_star, M_orig, L0)
    dirs = [
        ("2", res.e0y, inp.cy, res.Ix, res.Isx, res.delta_ex, res.kbx,
         res.Dx, res.Ncrx, res.etax, res.Mx_star, M2_orig, res.L0x),
        ("3", res.e0x, inp.cx, res.Iy, res.Isy, res.delta_ey, res.kby,
         res.Dy, res.Ncry, res.etay, res.My_star, M3_orig, res.L0y),
    ]
    phi_txt = ("2 (thiên về an toàn)"
               if not inp.long_term.has_data else _f(res.phi_L))
    phi_v = 2.0 if not inp.long_term.has_data else res.phi_L
    # Mỗi loại card một hàng cố định, 2 cột cho 2 phương
    card_defs = [
        ("phi", f"Hệ số ảnh hưởng thời hạn tải trọng φL",
         "Công thức (48)",
         lambda d, e0, t, I, Is, delta, kb, D, Ncr, eta, Mstar, Morig, L0:
             [f"φL,{d} = 1 + ML1,{d} / ML,{d} ≤ 2.0",
              f"φL = {phi_txt}"]),
        ("delta", f"Độ lệch tâm tương đối (δe)",
         "Điều 8.1.2.4.2",
         lambda d, e0, t, I, Is, delta, kb, D, Ncr, eta, Mstar, Morig, L0:
             [f"δe,{d} = e0{'3' if d=='2' else '2'} / t{d} "
              f"(lấy trong [0.15, 1.5])",
              f"= {_f(e0, 2)} / {t:.0f} = {_f(delta, 3)}",
              f"= {_f(delta, 3)} -"]),
        ("kb", f"Hệ số độ cứng bê tông (kb)",
         "Công thức (47)",
         lambda d, e0, t, I, Is, delta, kb, D, Ncr, eta, Mstar, Morig, L0:
             [f"kb,{d} = 0.15 / [φL,{d} · (0.3 + δe,{d})]",
              f"= 0.15 / [{_f(phi_v, 2)} × (0.3 + {_f(delta, 3)})]",
              f"= {_f(kb, 3)} -"]),
        ("D", f"Độ cứng chống uốn quy ước (D)",
         "Công thức (46)",
         lambda d, e0, t, I, Is, delta, kb, D, Ncr, eta, Mstar, Morig, L0:
             [f"D{d} = kb,{d} · Eb · I{d} + ks · Es · Is{d}",
              f"ks = 0.7",
              f"= {_f(D, 1)} kN·m²"]),
        ("Ncr", f"Lực tới hạn Euler (Ncr)",
         "Công thức (45)",
         lambda d, e0, t, I, Is, delta, kb, D, Ncr, eta, Mstar, Morig, L0:
             [f"Ncr,{d} = (π² · D{d}) / L0{d}²",
              f"= (π² × {_f(D, 1)}) / {_f(L0, 2)}²",
              f"= {_f(Ncr, 2)} kN"]),
        ("eta", f"Hệ số uốn dọc (η)",
         "Công thức (44)",
         lambda d, e0, t, I, Is, delta, kb, D, Ncr, eta, Mstar, Morig, L0:
             [f"η{d} = 1 / [1 - N / Ncr,{d}]",
              f"= 1 / [1 - {_f(N, 1)} / {_f(Ncr, 1)}]",
              f"= {_f(eta, 3)} ≥ 1.0"]),
        ("Mstar", f"Mô men tính toán (M*)",
         "Mục 8.1.2.4",
         lambda d, e0, t, I, Is, delta, kb, D, Ncr, eta, Mstar, Morig, L0:
             [f"M{d}* = η{d} · M{d}",
              f"= {_f(eta, 3)} × {_f(Morig, 2)}",
              f"= {_f(abs(Mstar), 2)} kN·m"]),
    ]
    for r, (key, title, ref, fn) in enumerate(card_defs):
        for (d, e0, t, I, Is, delta, kb, D, Ncr, eta,
             Mstar, Morig, L0) in dirs:
            col = int(d) - 2
            c = _param_card(grid, f"{title} phương {d} ({key},{d})",
                            ref, fn(d, e0, t, I, Is, delta, kb, D, Ncr,
                                    eta, Mstar, Morig, L0))
            c.grid(row=r, column=col, sticky="nsew", padx=4, pady=4)
    # Góc α và Mα (hàng cuối, 2 cột)
    import math as _m
    Ma = _m.hypot(res.Mx_star, res.My_star)
    alpha = _m.degrees(_m.atan2(res.Mx_star, res.My_star)) if Ma > 1e-9 else 0.0
    r = len(card_defs)
    c = _param_card(grid, "Góc tác dụng mô men uốn tổng hợp α",
                    "Góc uốn xiên",
                    [f"α = arctan(M₃* / M₂*)",
                     f"= arctan({_f(abs(res.My_star), 2)} / "
                     f"{_f(abs(res.Mx_star), 2)})",
                     f"= {_f(alpha, 2)} độ (°)"])
    c.grid(row=r, column=0, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Mô men uốn xiên tổng hợp Mα",
                    "Véc-tơ tổng hợp",
                    [f"Mα = √((M₂*)² + (M₃*)²)",
                     f"= √({_f(abs(res.Mx_star), 2)}² + "
                     f"{_f(abs(res.My_star), 2)}²)",
                     f"= {_f(Ma, 2)} kN·m"])
    c.grid(row=r, column=1, sticky="nsew", padx=4, pady=4)


def _build_sec6(g, inp: ColumnInput, res: CheckResult, sec,
               chart_pngs=None, chart_figs=None):
    _section_header(g, 6,
                    "ĐÁNH GIÁ KHẢ NĂNG CHỊU LỰC THEO MÔ HÌNH BIẾN DẠNG PHI TUYẾN (NDM)",
                    "TCVN 5574:2018 Mục 8.1.2.7")
    import math as _m
    Ma = _m.hypot(res.Mx_star, res.My_star)
    alpha = _m.degrees(_m.atan2(res.Mx_star, res.My_star)) \
        if Ma > 1e-9 else 0.0
    # |OA| và |OB|: độ lớn véc-tơ 3D
    OA = _m.sqrt(res.Mx_star**2 + res.My_star**2 + res.N**2)
    OB = _m.sqrt(res.Bx**2 + res.By**2 + res.BN**2)
    grid = _grid2(g)
    # Điểm A theo format web
    c = _param_card(grid, "Điểm nội lực tính toán A (Nội lực tác dụng)", "",
                    [f"A = (M₂tt, M₃tt, N)",
                     f"= ({_f(res.Mx_star, 1)}, {_f(res.My_star, 1)}, "
                     f"{_f(res.N, 1)})",
                     f"= |OA| = {_f(OA, 1)} kN/kNm"])
    c.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
    # Điểm B theo format web
    c = _param_card(grid, "Điểm giới hạn B (trên mặt tương tác)", "",
                    [f"B = (M₂gh, M₃gh, Ngh)",
                     f"= ({_f(res.Bx, 1)}, {_f(res.By, 1)}, "
                     f"{_f(res.BN, 1)})",
                     f"= |OB| = {_f(OB, 1)} kN/kNm"])
    c.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Góc uốn xiên α", "",
                    [f"α = {_f(alpha, 1)}°",
                     f"Mα = {_f(Ma, 1)} kN·m"])
    c.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Tỷ số D/C", "",
                    [f"D/C = |OA| / |OB| = {_f(OA, 1)} / {_f(OB, 1)}",
                     f"= {_f(res.dc, 3)} (FS = {_f(res.fs, 2)})"])
    c.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
    # Biểu đồ tương tác: ưu tiên dùng figure matplotlib giống hệt tab Kết quả
    # chart_figs: tuple (fig_nm, fig_m2m3) hoặc None
    # chart_pngs: tuple (png_nm, png_m2m3) hoặc None (fallback cũ)
    chart_frame = tk.Frame(g, bg=WHITE)
    chart_frame.pack(fill=tk.X, padx=8, pady=8)
    titles = ("Biểu đồ tương tác N-Mα", "Biểu đồ tương tác M2-M3")
    # Vẽ mới biểu đồ bằng đúng hàm chung (giống hệt tab Kết quả)
    try:
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from .chart_draw import draw_nm_alpha_ax, draw_m2m3_ax
        from .interaction import FiberSection
        _fs = FiberSection(sec)
        chart_frame.columnconfigure(0, weight=1)
        chart_frame.columnconfigure(1, weight=1)
        _draw_fns = [
            ("Biểu đồ tương tác N-Mα",
             lambda ax: draw_nm_alpha_ax(ax, sec, inp, res, _fs)),
            ("Biểu đồ tương tác M2-M3",
             lambda ax: draw_m2m3_ax(ax, sec, inp, res)),
        ]
        for col, (title, _draw) in enumerate(_draw_fns):
            cf = tk.Frame(chart_frame, bg=WHITE,
                          highlightbackground=BORDER, highlightthickness=1,
                          highlightcolor=BORDER,
                          bd=0, padx=8, pady=8)
            cf.grid(row=0, column=col, sticky="nsew", padx=4)
            tk.Label(cf, text=title, font=("", 10, "bold"),
                     fg=TEXT, bg=WHITE).pack(pady=(0, 4))
            _fig = Figure(figsize=(5.2, 3.9), dpi=100)
            _ax = _fig.add_subplot(111)
            _draw(_ax)
            _fig.tight_layout()
            _fig.subplots_adjust(bottom=0.30)
            cv = FigureCanvasTkAgg(_fig, master=cf)
            cv.draw()
            _w = cv.get_tk_widget()
            # Bỏ viền highlight khi click chọn canvas:
            # chặn focus ngay từ bindtags (trước class binding của tkinter)
            try:
                _w.configure(highlightthickness=0, takefocus=0,
                             highlightbackground="white", highlightcolor="white",
                             borderwidth=0)
                _bt = list(_w.bindtags())
                _block = "NoFocus%d" % id(_w)
                _w.bind_class(_block, "<ButtonPress>",
                              lambda e: "break")
                _w.bind_class(_block, "<ButtonRelease>",
                              lambda e: "break")
                _bt.insert(1, _block)
                _w.bindtags(tuple(_bt))
            except Exception:
                pass
            _w.pack(fill=tk.BOTH, expand=True)
            if not hasattr(g, "_chart_cvs"):
                g._chart_cvs = []
            g._chart_cvs.append(cv)
            if not hasattr(g, "_chart_figs"):
                g._chart_figs = []
            g._chart_figs.append(_fig)
    except Exception:
        pass
    # Fallback PNG cũ nếu vẽ mới thất bại
    if not hasattr(g, "_chart_cvs") or not g._chart_cvs:
        # (giữ code fallback PNG cũ ở đây nếu cần)
        pass
    else:
        # Fallback PNG cũ
        from tkinter import PhotoImage
        import base64
        pngs = []
        if chart_pngs:
            pngs = list(chart_pngs)
        else:
            try:
                from .pdf_export import interaction_image, m2m3_image
                pngs = [interaction_image(sec, inp, res, width_in=4.0, dpi=100),
                        m2m3_image(sec, inp, res, width_in=4.0, dpi=100)]
            except Exception:
                pass
        for title, png in zip(titles, pngs):
            try:
                ph = PhotoImage(data=base64.b64encode(png).decode())
                if not hasattr(g, "_chart_imgs"):
                    g._chart_imgs = []
                g._chart_imgs.append(ph)
                cf = tk.Frame(chart_frame, bg=WHITE,
                              highlightbackground=BORDER, highlightthickness=1,
                              padx=8, pady=8)
                cf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
                tk.Label(cf, text=title, font=("", 10, "bold"),
                         fg=TEXT, bg=WHITE).pack(pady=(0, 4))
                tk.Label(cf, image=ph, bg=WHITE).pack()
            except Exception:
                pass
    # Kết quả D/C
    ok = res.ok
    bg = "#D1FAE5" if ok else "#FEE2E2"
    fg = "#065F46" if ok else "#991B1B"
    box = tk.Frame(g, bg=bg, highlightbackground=BORDER,
                   highlightthickness=1, padx=12, pady=10)
    box.pack(fill=tk.X, padx=8, pady=8)
    tk.Label(box, text=f"TỶ SỐ SỬ DỤNG (D/C) = {_f(res.dc, 3)}  "
             f"(FS = {_f(res.fs, 2)})",
             font=("", 11, "bold"), fg=fg, bg=bg).pack(anchor="w")
    tk.Label(box, text="✓ ĐẠT — D/C ≤ 1.000" if ok else "✗ KHÔNG ĐẠT — D/C > 1.000",
             font=("", 10, "bold"), fg=fg, bg=bg).pack(anchor="w", pady=(4, 0))


def _build_sec7(g, inp: ColumnInput, res: CheckResult, sec, shear_info=None, shear_cols=None):
    """Mục 7: Kiểm tra cốt thép đai — dạng card khớp style mục 1-6.
    
    NGUYÊN TẮC: Lấy kết quả cắt từ shear_cols (đã tính 1 lần trong _tcvn_calculate_full),
    KHÔNG tự tính lại ở đây."""
    from .stirrup import StirrupInput, check_stirrup
    from .materials import STEEL_GRADES
    import math as _m
    _section_header(g, 7, "KIỂM TRA KHẢ NĂNG CHỊU CẮT",
                    "TCVN 5574:2018 Mục 10.3.4 & 8.1.3")
    stir_in = StirrupInput(dia=inp.sw_dia, spacing=inp.sw_spacing,
                           legs=inp.sw_legs)
    stir_res = check_stirrup(sec, stir_in, inp.concrete_grade)
    # Cấu tạo
    grid = _grid2(g)
    chk_lines = []
    for chk in stir_res.checks:
        mark = "✓" if chk.ok else "✗"
        chk_lines.append(f"{mark} {chk.item}: yêu cầu {chk.required}, "
                         f"chọn {chk.provided}")
    c = _param_card(grid, "Cấu tạo cốt đai (10.3.4)", "", chk_lines)
    c.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
    # Kiểm tra chịu cắt từng phương (thông tin Q kèm combo/vị trí đưa vào từng phương)
    conc = sec.concrete
    sw_grade = STEEL_GRADES.get(inp.sw_steel_grade, STEEL_GRADES["CB400-V"])
    # Lấy thông tin combo/vị trí cho từng phương
    _q2_info = ""
    _q3_info = ""
    if shear_info and "q2" in shear_info:
        try:
            _q2_info = f" {_full_case_w(shear_info['q2'])}"
        except: pass
    if shear_info and "q3" in shear_info:
        try:
            _q3_info = f" {_full_case_w(shear_info['q3'])}"
        except: pass
    Rb = conc.Rb
    Rbt = conc.Rbt
    Rsw = sw_grade.Rsw * inp.gamma_s
    Asw_1 = _m.pi * stir_in.dia ** 2 / 4
    h0_2 = sec.cx - inp.cover - stir_in.dia - inp.bar_dia / 2
    h0_3 = sec.cy - inp.cover - stir_in.dia - inp.bar_dia / 2
    shear_ok = True
    row = 2
    # DÙNG KẾT QUẢ TỪ _tcvn_calculate_full - KHÔNG TÍNH LẠI
    for dnum in ("2", "3"):
        if shear_cols and dnum in shear_cols:
            _sc = shear_cols[dnum]
            Q = _sc["Q"]
            b_w = _sc["b"]
            h0u = _sc["h0"]
            Asw = _sc["Asw"]
            qsw = _sc["qsw"]
            sh = _sc["sh"]
            sw_txt = _sc.get("sw_txt", "")
            s_eff = _sc.get("s_eff", stir_in.spacing)
        else:
            # KHÔNG có shear_cols: báo lỗi, không tự tính
            raise ValueError(f"Thiếu shear_cols cho phương {dnum} - vi phạm nguyên tắc 'tính 1 lần'")
        m1 = "✓" if sh.ok1 else "✗"
        m2 = "✓" if sh.ok2 else "✗"
        # qsw đã lấy từ shear_cols (không tính lại)
        Qb_lim_lo = 0.5 * Rbt * b_w * h0u / 1000.0
        Qb_lim_hi = 2.5 * Rbt * b_w * h0u / 1000.0
        lines = [
            f"Q = {_f(Q, 1)} kN{(_q2_info if dnum=='2' else _q3_info)}; b = {b_w:.0f} mm, h₀ = {h0u:.0f} mm",
            f"Asw = {sw_txt} = {Asw:.0f} mm²",
            f"{m1} ĐK1 (dải nén xiên): Q ≤ 0.3×Rb×b×h₀",
            f"  = 0.3×{_f(Rb, 2)}×{b_w:.0f}×{h0u:.0f}/1000 "
            f"= {_f(sh.Qcap1, 1)} kN",
            f"{m2} ĐK2 (vết nứt xiên): Q ≤ Qb + Qsw",
            f"  qsw = Rsw×Asw/s = {_f(Rsw, 0)}×{Asw:.0f}/"
            f"{s_eff:.0f} = {_f(qsw, 1)} N/mm",
            f"  Qb = 1.5×{_f(Rbt, 2)}×{b_w:.0f}×{h0u:.0f}²/"
            f"{sh.C_opt:.0f}/1000 = {_f(sh.Qb_opt, 1)} kN",
            f"  (Qb ∈ [{_f(Qb_lim_lo, 1)}, {_f(Qb_lim_hi, 1)}] kN)",
            f"  Qsw = 0.75×{_f(qsw, 1)}×{sh.C_opt:.0f}/1000 "
            f"= {_f(sh.Qsw_opt, 1)} kN",
            f"  → [Q]min = {_f(sh.Qcap2, 1)} kN tại C = {sh.C_opt:.0f} mm",
            f"{'✓' if sh.ok else '✗'} So sánh: |Q| = {_f(abs(Q), 1)} kN "
            f"{'≤' if abs(Q) <= sh.Qcap2 else '>'} [Q]min = {_f(sh.Qcap2, 1)} kN",
        ]
        c = _param_card(grid, f"Kiểm tra chịu cắt phương {dnum}", "", lines,
                        "Kết luận: ĐẠT" if sh.ok else "Kết luận: KHÔNG ĐẠT")
        c.grid(row=row, column=int(dnum) - 2, sticky="nsew", padx=4, pady=4)
        shear_ok &= sh.ok
        if dnum == "2":
            row += 0  # giữ cùng hàng cho phương 3



def build_calc_widgets(parent, inp: ColumnInput, res: CheckResult,
                       case_info=None, shear_info=None, shear_cols=None,
                       chart_pngs=None, chart_figs=None) -> tk.Frame:
    """Dựng toàn bộ thuyết minh mục 1-7 kiểu Vietcon vào parent.

    Trả về frame chứa nội dung (để caller pack/grid).
    """
    sec = build_section(inp)
    outer = tk.Frame(parent, bg=WHITE)
    # Header chung
    body = tk.Frame(outer, bg=WHITE)
    body.pack(fill=tk.BOTH, expand=True)

    _build_sec1(body, inp, res, sec)
    _build_sec2(body, inp, res, sec)
    _build_sec3(body, inp, res, sec)
    _build_sec4(body, inp, res, sec, case_info)
    _build_sec5(body, inp, res, sec)
    _build_sec6(body, inp, res, sec, chart_pngs, chart_figs)
    _build_sec7(body, inp, res, sec, shear_info, shear_cols)
    # Spacer hút khoảng trống xuống đáy (fix Canvas Win)
    tk.Frame(body, bg=WHITE).pack(fill=tk.BOTH, expand=True)
    return outer


def render_report_sections(parent, sections, chart_figs=None):
    """Render danh sách section (dict) kiểu TCVN cho mọi tiêu chuẩn.

    sections: list dict {num, title, ref, cards: [{title, ref, lines, result}]}.
    chart_figs: tuple (fig_nm, fig_m2m3) matplotlib — nhúng vào mục 6.
    Dùng chung cho TCVN/ACI/EC2 để layout đồng nhất.
    """
    for sec in sections:
        _section_header(parent, sec["num"], sec["title"], sec.get("ref", ""))
        cards = sec.get("cards", [])
        grid = _grid2(parent)
        row = 0
        i = 0
        while i < len(cards):
            c1 = cards[i]
            # Card full-width: span 2 cột
            if c1.get("full"):
                # Card kết luận: style nền xanh/đỏ giống TCVN
                if c1.get("conclusion"):
                    _ok = "KHÔNG ĐẠT" not in c1.get("result", "")
                    _bg = "#D1FAE5" if _ok else "#FEE2E2"
                    _fg = "#065F46" if _ok else "#991B1B"
                    _box = tk.Frame(grid, bg=_bg, highlightbackground=BORDER,
                                    highlightthickness=1, padx=12, pady=10)
                    _box.grid(row=row, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
                    tk.Label(_box, text=c1.get("title", ""), font=("", 10, "bold"),
                             fg=_fg, bg=_bg, anchor="w").pack(fill=tk.X)
                    for _ln in c1.get("lines", []):
                        tk.Label(_box, text=_ln, font=("", 9),
                                 fg=_fg, bg=_bg, anchor="w").pack(fill=tk.X)
                    tk.Label(_box, text=c1.get("result", ""), font=("", 10, "bold"),
                             fg=_fg, bg=_bg, anchor="w").pack(fill=tk.X, pady=(4, 0))
                else:
                    w1 = _param_card(grid, c1.get("title", ""), c1.get("ref", ""),
                                     c1.get("lines", []), c1.get("result", ""))
                    w1.grid(row=row, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
                row += 1
                i += 1
                continue
            c2 = cards[i + 1] if i + 1 < len(cards) else None
            # Nếu c2 là full, chỉ render c1
            if c2 and c2.get("full"):
                c2 = None
            w1 = _param_card(grid, c1.get("title", ""), c1.get("ref", ""),
                             c1.get("lines", []), c1.get("result", ""))
            w1.grid(row=row, column=0, sticky="nsew", padx=4, pady=4)
            if c2:
                w2 = _param_card(grid, c2.get("title", ""), c2.get("ref", ""),
                                 c2.get("lines", []), c2.get("result", ""))
                w2.grid(row=row, column=1, sticky="nsew", padx=4, pady=4)
                i += 2
            else:
                i += 1
            row += 1
        # Mục 6: nhúng 2 biểu đồ tương tác (giống TCVN)
        if sec["num"] == 6 and chart_figs:
            try:
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                chart_frame = tk.Frame(parent, bg=WHITE)
                chart_frame.pack(fill=tk.X, padx=8, pady=8)
                chart_frame.columnconfigure(0, weight=1)
                chart_frame.columnconfigure(1, weight=1)
                _titles = ("Biểu đồ tương tác N-Mα", "Biểu đồ tương tác M2-M3")
                for col, fig in enumerate(chart_figs):
                    if fig is not None:
                        # Frame có viền giống TCVN, với tiêu đề căn giữa phía trên
                        cf = tk.Frame(chart_frame, bg=WHITE,
                                      highlightbackground=BORDER, highlightthickness=1,
                                      highlightcolor=BORDER, bd=0, padx=8, pady=8)
                        cf.grid(row=0, column=col, sticky="nsew", padx=4)
                        _t = _titles[col] if col < len(_titles) else ""
                        tk.Label(cf, text=_t, font=("", 10, "bold"),
                                 fg=TEXT, bg=WHITE).pack(pady=(0, 4))
                        cv = FigureCanvasTkAgg(fig, master=cf)
                        cv.draw()
                        cv.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            except Exception:
                pass

        # Box kết luận D/C DƯỚI biểu đồ (style TCVN) cho ACI/EC2
        if sec["num"] == 6:
            _dc_card = None
            for _cd in cards:
                if "Tỷ số D/C" in _cd.get("title", "") or "D/C" in _cd.get("title", ""):
                    _dc_card = _cd
                    break
            if _dc_card and _dc_card.get("dc_conclusion"):
                _d = _dc_card
                _ok = _d.get("ok", True)
                _bg = "#D1FAE5" if _ok else "#FEE2E2"
                _fg = "#065F46" if _ok else "#991B1B"
                _box = tk.Frame(parent, bg=_bg, highlightbackground=BORDER,
                               highlightthickness=1, padx=12, pady=10)
                _box.pack(fill=tk.X, padx=8, pady=8)
                tk.Label(_box, text=f"TỶ SỐ SỬ DỤNG (D/C) = {_f(_d.get('dc', 0), 3)}  "
                         f"(FS = {_f(_d.get('fs', 0), 2)})",
                         font=("", 11, "bold"), fg=_fg, bg=_bg).pack(anchor="w")
                tk.Label(_box, text="✓ ĐẠT — D/C ≤ 1.000" if _ok else "✗ KHÔNG ĐẠT — D/C > 1.000",
                         font=("", 10, "bold"), fg=_fg, bg=_bg).pack(anchor="w", pady=(4, 0))
