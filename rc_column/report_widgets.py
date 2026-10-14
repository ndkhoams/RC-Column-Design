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
    """Khung lưới 2 cột."""
    g = tk.Frame(parent, bg=WHITE)
    g.pack(fill=tk.X, padx=4)
    g.columnconfigure(0, weight=1)
    g.columnconfigure(1, weight=1)
    return g


def _build_sec1(g, inp: ColumnInput, res: CheckResult, sec):
    conc = sec.concrete
    steel = sec.steel
    _section_header(g, 1, "ĐẶC TRƯNG VẬT LIỆU & CƯỜNG ĐỘ TÍNH TOÁN",
                    "TCVN 5574:2018 Mục 6.1 & 6.2")
    grid = _grid2(g)

    # Rb*
    c = _param_card(grid, "Bê tông: Cường độ chịu nén tính toán Rb*",
                    "Bảng 6 & Mục 6.1.2.3",
                    [f"Rb* = γb · Rb",
                     f"= {_f(inp.gamma_b)} × {_f(conc.grade.Rb)}",
                     f"= {_f(conc.Rb)} MPa (N/mm²)"])
    c.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
    # Eb
    c = _param_card(grid, "Bê tông: Mô đun đàn hồi ban đầu Eb", "Bảng 10",
                    [f"Eb (Cấp độ bền {inp.concrete_grade})",
                     f"= {conc.Eb:,.0f} N/mm²",
                     f"= {_f(conc.Eb / 1000, 1)} × 10³ MPa"])
    c.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
    # Rs
    c = _param_card(grid, "Cốt thép: Cường độ chịu kéo tính toán Rs",
                    "Bảng 13 & Mục 6.2.2",
                    [f"Rs = (Rsn / γs) · γsi",
                     f"= ({steel.grade.Rs:.0f} / 1.15) × {_f(inp.gamma_s)}",
                     f"= {_f(steel.Rs, 1)} MPa"])
    c.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
    # Rsc
    c = _param_card(grid, "Cốt thép: Cường độ chịu nén tính toán Rsc",
                    "Bảng 13 & Mục 6.2.2.2",
                    [f"Tác dụng ngắn hạn: Rsc = {steel.Rsc:.0f} MPa",
                     f"Tác dụng dài hạn: Rsc = {steel.Rsc:.0f} MPa",
                     f"= {_f(steel.Rsc, 1)} MPa"])
    c.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
    # Es
    c = _param_card(grid, "Cốt thép: Mô đun đàn hồi Es", "Mục 6.2.2.4",
                    [f"Es (Cốt thép {inp.steel_grade})",
                     f"= {steel.Es:,.0f} N/mm²",
                     f"= {_f(steel.Es / 1000)} × 10³ MPa"])
    c.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
    # αe
    c = _param_card(grid, "Tỷ số mô đun đàn hồi αe", "Mô hình quy đổi",
                    [f"αe = Es / Eb",
                     f"= {steel.Es:,.0f} / {conc.Eb:,.0f}",
                     f"= {_f(res.alpha_e)} -"])
    c.grid(row=2, column=1, sticky="nsew", padx=4, pady=4)

    # Bảng biến dạng giới hạn
    tk.Label(g, text="Biến dạng tỷ đối giới hạn của vật liệu",
             font=("", 10, "bold"), fg=TEXT, bg=WHITE,
             anchor="w").pack(fill=tk.X, padx=8, pady=(10, 4))
    tbl = tk.Frame(g, bg=WHITE, highlightbackground=BORDER,
                   highlightthickness=1)
    tbl.pack(fill=tk.X, padx=8, pady=4)
    headers = ["BÊ TÔNG CHỊU NÉN", "BÊ TÔNG CHỊU KÉO", "CỐT THÉP"]
    for j, h in enumerate(headers):
        tk.Label(tbl, text=h, font=("", 9, "bold"), fg=TEXT, bg="#F3F4F6",
                 padx=8, pady=6).grid(row=0, column=j, sticky="nsew")
        tbl.columnconfigure(j, weight=1)
    rows = [
        ("Biến dạng quy đổi: εb1,red = 0.0015 (1.50‰)",
         "Biến dạng quy đổi: εbt1,red = 0.00008 (0.08‰)",
         f"Biến dạng khi đạt Rs: εs0 = {_f(steel.Rs / steel.Es, 6)}"),
        (f"Tham số εb0: εb0 = {EPS_B1} (2.00‰)",
         "Tham số εbt0: εbt0 = 0.00010 (0.10‰)",
         f"Biến dạng khi đạt Rsc: εsc0 = {_f(steel.Rsc / steel.Es, 6)}"),
        (f"Biến dạng nén giới hạn: εb2 = {EPS_B2} (3.50‰)",
         "Biến dạng kéo giới hạn: εbt2 = 0.00015 (0.15‰)",
         f"Biến dạng giới hạn: εs2 = {EPS_S2} (25.00‰)"),
    ]
    for i, (a, b, cc) in enumerate(rows):
        bg = "#F9FAFB" if i % 2 else WHITE
        for j, t in enumerate((a, b, cc)):
            tk.Label(tbl, text=t, font=("", 9), fg="#374151", bg=bg,
                     padx=8, pady=6, anchor="w",
                     wraplength=280, justify=tk.LEFT).grid(
                         row=i + 1, column=j, sticky="nsew")
    tk.Label(g, text="* NDM – TCVN 5574:2018, Điều 8.1.2.7: εbu được xác định "
             "theo trạng thái ứng suất-biến dạng tiết diện theo Công thức (86), "
             "với εb0 ≤ εbu ≤ εb2. Bê tông vùng kéo không tham gia kiểm tra "
             "khả năng chịu lực TTGH I.",
             font=("", 8), fg=GRAY, bg=WHITE, wraplength=900,
             justify=tk.LEFT, anchor="w").pack(fill=tk.X, padx=8, pady=4)


def _build_sec2(g, inp: ColumnInput, res: CheckResult, sec):
    _section_header(g, 2, "ĐẶC TRƯNG HÌNH HỌC TIẾT DIỆN CỘT CHỮ NHẬT",
                    f"Kích thước {inp.cx:.0f} × {inp.cy:.0f} mm")
    grid = _grid2(g)
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
                     f"= {_f(res.ix, 2)} mm (= {_f(res.ix / 1000, 4)} m)"])
    c.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Bán kính quán tính phương 3 (i3)", "",
                    [f"i₃ = √(I₃ / A) = t3 / √12",
                     f"= {inp.cx:.0f} / 3.464",
                     f"= {_f(res.iy, 2)} mm (= {_f(res.iy / 1000, 4)} m)"])
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
        tk.Label(g, text=f"Tổ hợp tính toán: {case_info.get('case')}@"
                 f"{case_info.get('station', 0):.2f} — "
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
    _section_header(g, 5, "UỐN DỌC & PHÓNG ĐẠI MÔ MEN", "CT (44)–(48)")
    grid = _grid2(g)
    phi_txt = ("2.00 (thiên về an toàn)"
               if not inp.long_term.has_data else _f(res.phi_L))
    c = _param_card(grid, "Hệ số từ biến φL", "",
                    [f"φL = {phi_txt}"])
    c.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Hệ số δe₂ / δe₃", "",
                    [f"δe₂ = {_f(res.delta_ex, 3)}",
                     f"δe₃ = {_f(res.delta_ey, 3)}"])
    c.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Hệ số kb₂ / kb₃ (độ cứng)", "",
                    [f"kb₂ = {_f(res.kbx, 4)}",
                     f"kb₃ = {_f(res.kby, 4)}"])
    c.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Độ cứng D₂ / D₃", "",
                    [f"D₂ = {_f(res.Dx, 1)} kN·m²",
                     f"D₃ = {_f(res.Dy, 1)} kN·m²"])
    c.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Lực tới hạn Euler Ncr,2 / Ncr,3", "",
                    [f"Ncr,2 = {_f(res.Ncrx, 1)} kN",
                     f"Ncr,3 = {_f(res.Ncry, 1)} kN"])
    c.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Hệ số uốn dọc η₂ / η₃", "",
                    [f"η₂ = {_f(res.etax, 3)}",
                     f"η₃ = {_f(res.etay, 3)}"])
    c.grid(row=2, column=1, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Mô men tính toán M₂* / M₃*", "",
                    [f"M₂* = η₂·M₂ = {_f(res.Mx_star, 1)} kN·m",
                     f"M₃* = η₃·M₃ = {_f(res.My_star, 1)} kN·m"])
    c.grid(row=3, column=0, sticky="nsew", padx=4, pady=4)


def _build_sec6(g, inp: ColumnInput, res: CheckResult, sec):
    _section_header(g, 6, "KIỂM TRA THEO MÔ HÌNH PHI TUYẾN (NDM)",
                    "TCVN 5574:2018 Điều 8.1.2.7")
    Ma = math.hypot(res.Mx_star, res.My_star)
    alpha = math.degrees(math.atan2(res.My_star, res.Mx_star)) \
        if Ma > 1e-9 else 0.0
    grid = _grid2(g)
    c = _param_card(grid, "Điểm tải trọng A", "",
                    [f"A = (M₂*, M₃*, N)",
                     f"= ({_f(res.Mx_star, 1)}, {_f(res.My_star, 1)}, "
                     f"{_f(res.N, 1)})"])
    c.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Điểm giới hạn B (trên mặt tương tác)", "",
                    [f"B = ({_f(res.Bx, 1)}, {_f(res.By, 1)}, "
                     f"{_f(res.BN, 1)})"])
    c.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
    c = _param_card(grid, "Góc uốn xiên α", "",
                    [f"α = {_f(alpha, 1)}°",
                     f"Mα = {_f(Ma, 1)} kN·m"])
    c.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
    # Biểu đồ tương tác (giống web)
    try:
        from .pdf_export import interaction_image, m2m3_image
        from tkinter import PhotoImage
        import base64
        import io
        chart_frame = tk.Frame(g, bg=WHITE)
        chart_frame.pack(fill=tk.X, padx=8, pady=8)
        for title, img_fn in (("Biểu đồ tương tác N-Mα", interaction_image),
                              ("Biểu đồ tương tác M2-M3", m2m3_image)):
            try:
                png = img_fn(sec, inp, res, width_in=4.0, dpi=100)
                ph = PhotoImage(data=base64.b64encode(png).decode())
                # Giữ tham chiếu để không bị GC
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


def _build_sec7(g, inp: ColumnInput, res: CheckResult, sec, shear_info=None):
    """Mục 7: Kiểm tra cốt thép đai — dạng card khớp style mục 1-6."""
    from .stirrup import StirrupInput, check_stirrup, check_shear
    from .materials import STEEL_GRADES
    import math as _m
    _section_header(g, 7, "KIỂM TRA CỐT THÉP ĐAI",
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
    # Lực cắt tính toán
    conc = sec.concrete
    sw_grade = STEEL_GRADES.get(inp.sw_steel_grade, STEEL_GRADES["CB400-V"])
    if shear_info:
        q2i, q3i = shear_info["q2"], shear_info["q3"]
        c = _param_card(grid, "Lực cắt tính toán", "",
                        [f"Q2 = {_f(q2i['Q'], 1)} kN "
                         f"({q2i['case']}@{q2i['station']:.2f})",
                         f"Q3 = {_f(q3i['Q'], 1)} kN "
                         f"({q3i['case']}@{q3i['station']:.2f})",
                         "Độc lập với combo N-M nguy hiểm nhất"])
        c.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
    # Kiểm tra chịu cắt từng phương
    Rb = conc.Rb
    Rbt = conc.Rbt
    Rsw = sw_grade.Rsw * inp.gamma_s
    Asw_1 = _m.pi * stir_in.dia ** 2 / 4
    h0_2 = sec.cx - inp.cover - stir_in.dia - inp.bar_dia / 2
    h0_3 = sec.cy - inp.cover - stir_in.dia - inp.bar_dia / 2
    shear_ok = True
    row = 2
    for Q, b_w, h0, dnum in ((inp.Q2, sec.cy, h0_2, "2"),
                             (inp.Q3, sec.cx, h0_3, "3")):
        Asw = Asw_1 * stir_in.legs
        h0u = max(h0, 1)
        sh = check_shear(Q, b_w, h0u, Rb, Rbt, Asw, Rsw,
                         stir_in.spacing, direction=dnum)
        m1 = "✓" if sh.ok1 else "✗"
        m2 = "✓" if sh.ok2 else "✗"
        qsw = Rsw * Asw / stir_in.spacing if stir_in.spacing > 0 else 0
        Qb_lim_lo = 0.5 * Rbt * b_w * h0u / 1000.0
        Qb_lim_hi = 2.5 * Rbt * b_w * h0u / 1000.0
        lines = [
            f"Q = {_f(Q, 1)} kN; b = {b_w:.0f} mm, h₀ = {h0u:.0f} mm",
            f"Asw = {stir_in.legs}×φ{stir_in.dia:.0f} = {Asw:.0f} mm²",
            f"{m1} ĐK1 (dải nén xiên): Q ≤ 0.3×Rb×b×h₀",
            f"  = 0.3×{_f(Rb, 2)}×{b_w:.0f}×{h0u:.0f}/1000 "
            f"= {_f(sh.Qcap1, 1)} kN",
            f"{m2} ĐK2 (vết nứt xiên): Q ≤ Qb + Qsw",
            f"  qsw = Rsw×Asw/s = {_f(Rsw, 0)}×{Asw:.0f}/"
            f"{stir_in.spacing:.0f} = {_f(qsw, 1)} N/mm",
            f"  Qb = 1.5×{_f(Rbt, 2)}×{b_w:.0f}×{h0u:.0f}²/"
            f"{sh.C_opt:.0f}/1000 = {_f(sh.Qb_opt, 1)} kN",
            f"  (Qb ∈ [{_f(Qb_lim_lo, 1)}, {_f(Qb_lim_hi, 1)}] kN)",
            f"  Qsw = 0.75×{_f(qsw, 1)}×{sh.C_opt:.0f}/1000 "
            f"= {_f(sh.Qsw_opt, 1)} kN",
            f"  → [Q]min = {_f(sh.Qcap2, 1)} kN tại C = {sh.C_opt:.0f} mm",
        ]
        c = _param_card(grid, f"Kiểm tra chịu cắt phương {dnum}", "", lines)
        c.grid(row=row, column=int(dnum) - 2, sticky="nsew", padx=4, pady=4)
        shear_ok &= sh.ok
        if dnum == "2":
            row += 0  # giữ cùng hàng cho phương 3
    # Kết luận
    ok = stir_res.ok and shear_ok
    bg = "#D1FAE5" if ok else "#FEE2E2"
    fg = "#065F46" if ok else "#991B1B"
    box = tk.Frame(g, bg=bg, highlightbackground=BORDER,
                   highlightthickness=1, padx=12, pady=10)
    box.pack(fill=tk.X, padx=8, pady=8)
    tk.Label(box, text="✓ ĐẠT — Cốt đai thỏa TCVN 5574:2018" if ok else
             "✗ KHÔNG ĐẠT — Xem lại cốt đai",
             font=("", 11, "bold"), fg=fg, bg=bg).pack(anchor="w")


def build_calc_widgets(parent, inp: ColumnInput, res: CheckResult,
                       case_info=None, shear_info=None) -> tk.Frame:
    """Dựng toàn bộ thuyết minh mục 1-7 kiểu Vietcon vào parent.

    Trả về frame chứa nội dung (để caller pack/grid).
    """
    sec = build_section(inp)
    outer = tk.Frame(parent, bg=WHITE)
    # Header chung
    hdr = tk.Frame(outer, bg=WHITE)
    hdr.pack(fill=tk.X, padx=4, pady=(6, 2))
    tk.Label(hdr, text="▤", font=("", 14), fg="#059669",
             bg=WHITE).pack(side=tk.LEFT, padx=(2, 6))
    tk.Label(hdr, text="Chi tiết tính toán", font=("", 13, "bold"),
             fg=TEXT, bg=WHITE).pack(side=tk.LEFT)

    body = tk.Frame(outer, bg=WHITE)
    body.pack(fill=tk.BOTH, expand=True)

    _build_sec1(body, inp, res, sec)
    _build_sec2(body, inp, res, sec)
    _build_sec3(body, inp, res, sec)
    _build_sec4(body, inp, res, sec, case_info)
    _build_sec5(body, inp, res, sec)
    _build_sec6(body, inp, res, sec)
    _build_sec7(body, inp, res, sec, shear_info)
    return outer
