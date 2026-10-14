"""Xuất PDF thuyết minh kiểu card giống hệt app (Vietcon style).

Mirror đúng cấu trúc report_widgets.py: mỗi mục gồm các card 2 cột,
mỗi card có tiêu đề, tham chiếu, các dòng công thức, kết quả.
"""

import io
import math

from .checker import ColumnInput, CheckResult, build_section
from .materials import STEEL_GRADES, EPS_B1, EPS_B2, EPS_S2


def _f(x: float, nd: int = 2) -> str:
    try:
        return f"{x:,.{nd}f}"
    except Exception:
        return "—"


WHITE = "#FFFFFF"
BORDER = "#E5E7EB"
TEXT = "#111827"
GRAY = "#6B7280"
FORMULA_BG = "#F9FAFB"
_DOT_COLORS = ["#2563EB", "#059669", "#D97706", "#7C3AED", "#DB2777", "#0891B2"]


def _get_styles():
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from .pdf_export import _find_font, _find_font_bold

    font_path = _find_font()
    bold_path = _find_font_bold()
    if not font_path:
        raise RuntimeError("Không tìm thấy font hỗ trợ tiếng Việt.")
    try:
        pdfmetrics.registerFont(TTFont("VN", font_path))
    except Exception:
        pass
    try:
        pdfmetrics.registerFont(TTFont("VN-Bold", bold_path or font_path))
    except Exception:
        pass

    return {
        "title": ParagraphStyle("title", fontName="VN-Bold", fontSize=14,
                                textColor=HexColor(TEXT), alignment=TA_CENTER,
                                spaceAfter=4),
        "sub": ParagraphStyle("sub", fontName="VN", fontSize=9,
                              textColor=HexColor(GRAY), alignment=TA_CENTER,
                              spaceAfter=10),
        "sec_title": ParagraphStyle("sec_title", fontName="VN-Bold",
                                    fontSize=11, textColor=HexColor(TEXT),
                                    spaceBefore=10, spaceAfter=6),
        "card_title": ParagraphStyle("card_title", fontName="VN-Bold",
                                     fontSize=8, textColor=HexColor(TEXT),
                                     leading=10, spaceAfter=2),
        "card_ref": ParagraphStyle("card_ref", fontName="VN", fontSize=6,
                                   textColor=HexColor(GRAY), leading=8,
                                   spaceAfter=2),
        "formula": ParagraphStyle("formula", fontName="VN", fontSize=7,
                                  textColor=HexColor("#374151"), leading=10,
                                  leftIndent=6, spaceAfter=1),
        "result": ParagraphStyle("result", fontName="VN-Bold", fontSize=7.5,
                                 textColor=HexColor(TEXT), leading=10,
                                 spaceBefore=3),
        "note": ParagraphStyle("note", fontName="VN", fontSize=7.5,
                               textColor=HexColor(GRAY), leading=10,
                               spaceBefore=4, spaceAfter=4),
        "dc_ok": ParagraphStyle("dc_ok", fontName="VN-Bold", fontSize=11,
                                textColor=HexColor("#065F46"),
                                backColor=HexColor("#D1FAE5"),
                                borderPadding=10, alignment=TA_CENTER,
                                spaceBefore=10, spaceAfter=10),
        "dc_ng": ParagraphStyle("dc_ng", fontName="VN-Bold", fontSize=11,
                                textColor=HexColor("#991B1B"),
                                backColor=HexColor("#FEE2E2"),
                                borderPadding=10, alignment=TA_CENTER,
                                spaceBefore=10, spaceAfter=10),
        "cap": ParagraphStyle("cap", fontName="VN", fontSize=8,
                              textColor=HexColor(GRAY), alignment=TA_CENTER,
                              spaceBefore=4, spaceAfter=8),
    }


def _two(P, st, c1, c2):
    """1 table phẳng duy nhất: 2 cột, không nested table.
    c1/c2 là dict {title, ref, lines, result}."""
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm

    def _title_cell(title, ref):
        if ref:
            return P(f'<b>{title}</b> <font color="{GRAY}" size=6>{ref}</font>',
                     st["card_title"])
        return P(f"<b>{title}</b>", st["card_title"])

    # Số dòng công thức tối đa
    n1 = len(c1["lines"]) + (1 if c1.get("result") else 0)
    n2 = len(c2["lines"]) + (1 if c2.get("result") else 0)
    nmax = max(n1, n2)

    # Dựng rows: [title], [ref], [formulas...]
    rows = []
    rows.append([_title_cell(c1["title"], c1["ref"]),
                 _title_cell(c2["title"], c2["ref"])])
    # Các dòng công thức
    for i in range(nmax):
        l1 = c1["lines"][i] if i < len(c1["lines"]) else ""
        l2 = c2["lines"][i] if i < len(c2["lines"]) else ""
        # Dòng result
        if i == len(c1["lines"]) and c1.get("result"):
            l1 = c1["result"]
        if i == len(c2["lines"]) and c2.get("result"):
            l2 = c2["result"]
        rows.append([P(l1, st["formula"]) if l1 else P("", st["formula"]),
                     P(l2, st["formula"]) if l2 else P("", st["formula"])])

    t = Table(rows, colWidths=[90, 90])
    sty = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        # Khối công thức: nền + viền trái (từ hàng 1 trở đi)
        ("BACKGROUND", (0, 1), (-1, -1), HexColor(FORMULA_BG)),
        ("LINEBEFORE", (0, 1), (0, -1), 1.5, HexColor("#D1D5DB")),
        ("LINEBEFORE", (1, 1), (1, -1), 1.5, HexColor("#D1D5DB")),
        ("LEFTPADDING", (0, 1), (-1, -1), 8),
    ]
    t.setStyle(TableStyle(sty))
    return [t, Spacer(1, 4*mm)]


def _mk(title, ref, lines, result=""):
    return {"title": title, "ref": ref, "lines": lines, "result": result}


_EMPTY = {"title": "", "ref": "", "lines": [], "result": ""}


def _sec_head(P, st, num, title, ref=""):
    dot = _DOT_COLORS[(num - 1) % len(_DOT_COLORS)]
    html = f'<font color="{dot}">●</font>&nbsp;&nbsp;<b>{num}. {title}</b>'
    if ref:
        html += f'&nbsp;&nbsp;<font size=8 color="{GRAY}">{ref}</font>'
    return P(html, st["sec_title"])


def export_pdf_cards(inp: ColumnInput, res: CheckResult, filepath: str,
                     batch_rows=None, case_info=None, shear_info=None,
                     chart_pngs=None):
    """Xuất PDF thuyết minh với layout card giống hệt app."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Image, Table, TableStyle, KeepTogether)
    from reportlab.lib.colors import HexColor

    st = _get_styles()
    P = Paragraph
    sec = build_section(inp)
    conc = sec.concrete
    steel = sec.steel

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    S = []
    S.append(P("THUYẾT MINH TÍNH TOÁN KIỂM TRA CỘT BTCT", st["title"]))
    S.append(P("Tiêu chuẩn: TCVN 5574:2018 — Mô hình biến dạng phi tuyến "
               "(Điều 8.1.2.7)", st["sub"]))

    # ================= MỤC 1 =================
    S.append(_sec_head(P, st, 1, "ĐẶC TRƯNG VẬT LIỆU & CƯỜNG ĐỘ TÍNH TOÁN",
                       "TCVN 5574:2018 Mục 6.1 & 6.2"))
    S.extend(_two(P, st,
        _mk( "Bê tông: Cường độ chịu nén tính toán Rb*",
              "Bảng 6 & Mục 6.1.2.3",
              ["Rb* = γb · Rb",
               f"= {_f(inp.gamma_b)} × {_f(conc.grade.Rb)}",
               f"= {_f(conc.Rb)} MPa (N/mm²)"]),
        _mk( "Bê tông: Mô đun đàn hồi ban đầu Eb", "Bảng 10",
              [f"Eb (Cấp độ bền {inp.concrete_grade})",
               f"= {conc.Eb:,.0f} N/mm²",
               f"= {_f(conc.Eb / 1000, 1)} × 10³ MPa"])))
    S.extend(_two(P, st,
        _mk( "Cốt thép: Cường độ chịu kéo tính toán Rs",
              "Bảng 13 & Mục 6.2.2",
              ["Rs = (Rsn / γs) · γsi",
               f"= ({steel.grade.Rs:.0f} / 1.15) × {_f(inp.gamma_s)}",
               f"= {_f(steel.Rs, 1)} MPa"]),
        _mk( "Cốt thép: Cường độ chịu nén tính toán Rsc",
              "Bảng 13 & Mục 6.2.2.2",
              [f"Tác dụng ngắn hạn: Rsc = {steel.Rsc:.0f} MPa",
               f"Tác dụng dài hạn: Rsc = {steel.Rsc:.0f} MPa",
               f"= {_f(steel.Rsc, 1)} MPa"])))
    S.extend(_two(P, st,
        _mk( "Cốt thép: Mô đun đàn hồi Es", "Mục 6.2.2.4",
              [f"Es (Cốt thép {inp.steel_grade})",
               f"= {steel.Es:,.0f} N/mm²",
               f"= {_f(steel.Es / 1000)} × 10³ MPa"]),
        _mk( "Tỷ số mô đun đàn hồi αe", "Mô hình quy đổi",
              ["αe = Es / Eb",
               f"= {steel.Es:,.0f} / {conc.Eb:,.0f}",
               f"= {_f(res.alpha_e)} -"])))
    # Bảng biến dạng giới hạn
    S.append(P("<b>Biến dạng tỷ đối giới hạn của vật liệu</b>",
               st["card_title"]))
    hdr = [P("<b>BÊ TÔNG CHỊU NÉN</b>", st["formula"]),
           P("<b>BÊ TÔNG CHỊU KÉO</b>", st["formula"]),
           P("<b>CỐT THÉP</b>", st["formula"])]
    dat = [
        [P(f"Biến dạng quy đổi: εb1,red = 0.0015 (1.50‰)", st["formula"]),
         P(f"Biến dạng quy đổi: εbt1,red = 0.00008 (0.08‰)", st["formula"]),
         P(f"Biến dạng khi đạt Rs: εs0 = {_f(steel.Rs / steel.Es, 6)}",
           st["formula"])],
        [P(f"Tham số εb0: εb0 = {EPS_B1} (2.00‰)", st["formula"]),
         P(f"Tham số εbt0: εbt0 = 0.00010 (0.10‰)", st["formula"]),
         P(f"Biến dạng khi đạt Rsc: εsc0 = {_f(steel.Rsc / steel.Es, 6)}",
           st["formula"])],
        [P(f"Biến dạng nén giới hạn: εb2 = {EPS_B2} (3.50‰)", st["formula"]),
         P(f"Biến dạng kéo giới hạn: εbt2 = 0.00015 (0.15‰)", st["formula"]),
         P(f"Biến dạng giới hạn: εs2 = {EPS_S2} (25.00‰)", st["formula"])],
    ]
    tbl = Table([hdr] + dat, colWidths=[64, 64, 64])
    tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor(BORDER)),
        ("GRID", (0, 0), (-1, -1), 0.25, HexColor(BORDER)),
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F3F4F6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [HexColor(WHITE), HexColor(FORMULA_BG)]),
    ]))
    S.append(tbl)
    S.append(P("* NDM – TCVN 5574:2018, Điều 8.1.2.7: εbu được xác định theo "
               "trạng thái ứng suất-biến dạng tiết diện theo Công thức (86), "
               "với εb0 ≤ εbu ≤ εb2. Bê tông vùng kéo không tham gia kiểm tra "
               "khả năng chịu lực TTGH I.", st["note"]))

    # ================= MỤC 2 =================
    S.append(_sec_head(P, st, 2, "ĐẶC TRƯNG HÌNH HỌC TIẾT DIỆN CỘT CHỮ NHẬT",
                       f"Kích thước {inp.cx:.0f} × {inp.cy:.0f} mm"))
    S.extend(_two(P, st,
        _mk( "Diện tích tiết diện bê tông nguyên A", "",
              ["A = t2 · t3",
               f"= {inp.cy:.0f} × {inp.cx:.0f}",
               f"= {sec.gross_area:,.0f} mm² "
               f"(= {_f(sec.gross_area / 1e6, 4)} m²)"]),
        _mk( "Lớp bê tông bảo vệ cốt dọc c", "",
              [f"c = {inp.cover:.0f} mm",
               "Chiều dày lớp bê tông bảo vệ",
               f"= {inp.cover:.0f} mm"])))
    S.extend(_two(P, st,
        _mk( "Mô men quán tính trục 2 (I2)", "",
              ["I₂ = (t3 · t2³) / 12",
               f"= ({inp.cx:.0f} × {inp.cy:.0f}³) / 12",
               f"= {_f(res.Ix / 1e9, 3)} × 10⁹ mm⁴"]),
        _mk( "Mô men quán tính trục 3 (I3)", "",
              ["I₃ = (t2 · t3³) / 12",
               f"= ({inp.cy:.0f} × {inp.cx:.0f}³) / 12",
               f"= {_f(res.Iy / 1e9, 3)} × 10⁹ mm⁴"])))
    S.extend(_two(P, st,
        _mk( "Bán kính quán tính phương 2 (i2)", "",
              ["i₂ = √(I₂ / A) = t2 / √12",
               f"= {inp.cy:.0f} / 3.464",
               f"= {_f(res.ix, 2)} mm (= {_f(res.ix / 1000, 4)} m)"]),
        _mk( "Bán kính quán tính phương 3 (i3)", "",
              ["i₃ = √(I₃ / A) = t3 / √12",
               f"= {inp.cx:.0f} / 3.464",
               f"= {_f(res.iy, 2)} mm (= {_f(res.iy / 1000, 4)} m)"])))

    # ================= MỤC 3 =================
    S.append(_sec_head(P, st, 3, "CHIỀU DÀI TÍNH TOÁN & ĐỘ MẢNH",
                       "TCVN 5574:2018 Mục 8.1.2.4"))
    S.extend(_two(P, st,
        _mk( "Chiều dài tính toán phương 2 (L02)", "",
              [f"L₀₂ = ψ · L = {_f(inp.psi_x, 2)} × {_f(inp.Lx, 2)}",
               f"= {_f(res.L0x, 2)} m"]),
        _mk( "Chiều dài tính toán phương 3 (L03)", "",
              [f"L₀₃ = ψ · L = {_f(inp.psi_y, 2)} × {_f(inp.Ly, 2)}",
               f"= {_f(res.L0y, 2)} m"])))
    ok2 = "ĐẠT" if res.lambda_x <= 120 else "KHÔNG ĐẠT"
    ok3 = "ĐẠT" if res.lambda_y <= 120 else "KHÔNG ĐẠT"
    S.extend(_two(P, st,
        _mk( "Độ mảnh cột phương 2 (λ2)", "",
              ["λ₂ = L₀₂ / i₂",
               f"= {_f(res.L0x * 1000, 0)} / {_f(res.ix, 1)}",
               f"= {_f(res.lambda_x, 1)} ≤ 120 → {ok2}"]),
        _mk( "Độ mảnh cột phương 3 (λ3)", "",
              ["λ₃ = L₀₃ / i₃",
               f"= {_f(res.L0y * 1000, 0)} / {_f(res.iy, 1)}",
               f"= {_f(res.lambda_y, 1)} ≤ 120 → {ok3}"])))
    l02_t2 = (res.L0x * 1000) / inp.cy if inp.cy > 0 else 0
    l03_t3 = (res.L0y * 1000) / inp.cx if inp.cx > 0 else 0
    need2 = res.lambda_x > 14 or l02_t2 > 4
    need3 = res.lambda_y > 14 or l03_t3 > 4
    kl2 = ("BẮT BUỘC XÉT UỐN DỌC (kể đến hệ số η₂)" if need2
           else "KHÔNG CẦN XÉT UỐN DỌC")
    kl3 = ("BẮT BUỘC XÉT UỐN DỌC (kể đến hệ số η₃)" if need3
           else "KHÔNG CẦN XÉT UỐN DỌC")
    S.extend(_two(P, st,
        _mk( "Điều kiện xét hiệu ứng uốn dọc phương 2",
              "Mục 8.1.2.1.2",
              ["Xét khi λ₂ > 14 hoặc L₀₂ / t2 > 4",
               f"λ₂ = {_f(res.lambda_x, 2)} "
               f"{'>' if res.lambda_x > 14 else '≤'} 14",
               f"L₀₂ / t2 = {_f(l02_t2, 2)}",
               f"= {kl2}"]),
        _mk( "Điều kiện xét hiệu ứng uốn dọc phương 3",
              "Mục 8.1.2.1.2",
              ["Xét khi λ₃ > 14 hoặc L₀₃ / t3 > 4",
               f"λ₃ = {_f(res.lambda_y, 2)} "
               f"{'>' if res.lambda_y > 14 else '≤'} 14",
               f"L₀₃ / t3 = {_f(l03_t3, 2)}",
               f"= {kl3}"])))

    # ================= MỤC 4 =================
    S.append(_sec_head(P, st, 4,
                       "ĐỘ LỆCH TÂM TĨNH HỌC, ĐỘ LỆCH TÂM NGẪU NHIÊN & "
                       "ĐỘ LỆCH TÂM BAN ĐẦU",
                       "TCVN 5574:2018 Mục 8.1.2.2.4"))
    if case_info:
        S.append(P(f"Tổ hợp tính toán: {case_info.get('case')}@"
                   f"{case_info.get('station', 0):.2f} — "
                   f"N = {_f(case_info.get('N', 0), 1)} kN, "
                   f"M2 = {_f(case_info.get('M2', 0), 1)} kN·m, "
                   f"M3 = {_f(case_info.get('M3', 0), 1)} kN·m",
                   st["note"]))
    N = abs(res.N) if res.N else 1.0
    M2 = abs(res.Mx_star / res.etax) if res.etax else 0.0
    M3 = abs(res.My_star / res.etay) if res.etay else 0.0
    S.extend(_two(P, st,
        _mk( "Độ lệch tâm tĩnh học phương 2 (e12)",
              "Mục 8.1.2.2.4",
              ["e₁₂ = |M₂| / N",
               f"= ({_f(M2 * 1000, 2)} × 10³) / {_f(N, 2)}",
               f"= {_f(res.e1x, 2)} mm"]),
        _mk( "Độ lệch tâm tĩnh học phương 3 (e13)",
              "Mục 8.1.2.2.4",
              ["e₁₃ = |M₃| / N",
               f"= ({_f(M3 * 1000, 2)} × 10³) / {_f(N, 2)}",
               f"= {_f(res.e1y, 2)} mm"])))
    S.extend(_two(P, st,
        _mk( "Độ lệch tâm ngẫu nhiên phương 2 (ea2)", "",
              ["ea₂ = max(t2/600, L₀₂/600, 10mm)",
               f"= {_f(res.eax, 1)} mm"]),
        _mk( "Độ lệch tâm ngẫu nhiên phương 3 (ea3)", "",
              ["ea₃ = max(t3/600, L₀₃/600, 10mm)",
               f"= {_f(res.eay, 1)} mm"])))
    S.extend(_two(P, st,
        _mk( "Độ lệch tâm ban đầu phương 2 (e02)", "",
              ["e₀₂ = e₁₂ + ea₂",
               f"= {_f(res.e1x, 1)} + {_f(res.eax, 1)}",
               f"= {_f(res.e0x, 1)} mm"]),
        _mk( "Độ lệch tâm ban đầu phương 3 (e03)", "",
              ["e₀₃ = e₁₃ + ea₃",
               f"= {_f(res.e1y, 1)} + {_f(res.eay, 1)}",
               f"= {_f(res.e0y, 1)} mm"])))

    # ================= MỤC 5 =================
    S.append(_sec_head(P, st, 5,
                       "ĐỘ CỨNG CHỐNG UỐN, LỰC TỚI HẠN EULER & PHÓNG ĐẠI "
                       "MÔ MEN UỐN DỌC",
                       "TCVN 5574:2018 Công thức (44) - (48)"))
    phi_txt = ("2 (thiên về an toàn)"
               if not inp.long_term.has_data else _f(res.phi_L))
    phi_v = 2.0 if not inp.long_term.has_data else res.phi_L
    dirs = [
        ("2", res.e0y, inp.cy, res.delta_ex, res.kbx, res.Dx, res.Ncrx,
         res.etax, res.Mx_star, M2, res.L0x),
        ("3", res.e0x, inp.cx, res.delta_ey, res.kby, res.Dy, res.Ncry,
         res.etay, res.My_star, M3, res.L0y),
    ]
    # Mỗi hàng: 2 card (phương 2 | phương 3)
    def _mk5(d, e0, t, delta, kb, D, Ncr, eta, Mstar, Morig, L0, kind):
        if kind == "phi":
            return _mk5(
                         f"Hệ số ảnh hưởng thời hạn tải trọng φL,{d}",
                         "Công thức (48)",
                         [f"φL,{d} = 1 + ML1,{d} / ML,{d} ≤ 2.0",
                          f"φL = {phi_txt}"])
        if kind == "de":
            return _mk5( f"Độ lệch tâm tương đối phương {d} (δe,{d})",
                         "Điều 8.1.2.4.2",
                         [f"δe,{d} = e0{'3' if d == '2' else '2'} / t{d} "
                          "(lấy trong [0.15, 1.5])",
                          f"= {_f(e0, 2)} / {t:.0f} = {_f(delta, 3)}",
                          f"= {_f(delta, 3)} -"])
        if kind == "kb":
            return _mk5( f"Hệ số độ cứng bê tông phương {d} (kb,{d})",
                         "Công thức (47)",
                         [f"kb,{d} = 0.15 / [φL,{d} · (0.3 + δe,{d})]",
                          f"= 0.15 / [{_f(phi_v, 2)} × "
                          f"(0.3 + {_f(delta, 3)})]",
                          f"= {_f(kb, 3)} -"])
        if kind == "D":
            return _mk5( f"Độ cứng chống uốn quy ước phương {d} (D{d})",
                         "Công thức (46)",
                         [f"D{d} = kb,{d} · Eb · I{d} + ks · Es · Is{d}",
                          "ks = 0.7",
                          f"= {_f(D, 1)} kN·m²"])
        if kind == "Ncr":
            return _mk5( f"Lực tới hạn Euler phương {d} (Ncr,{d})",
                         "Công thức (45)",
                         [f"Ncr,{d} = (π² · D{d}) / L0{d}²",
                          f"= (π² × {_f(D, 1)}) / {_f(L0, 2)}²",
                          f"= {_f(Ncr, 2)} kN"])
        if kind == "eta":
            return _mk5( f"Hệ số uốn dọc phương {d} (η{d})",
                         "Công thức (44)",
                         [f"η{d} = 1 / [1 - N / Ncr,{d}]",
                          f"= 1 / [1 - {_f(N, 1)} / {_f(Ncr, 1)}]",
                          f"= {_f(eta, 3)} ≥ 1.0"])
        if kind == "Ms":
            return _mk5( f"Mô men tính toán phương {d} (M{d}*)",
                         "Mục 8.1.2.4",
                         [f"M{d}* = η{d} · M{d}",
                          f"= {_f(eta, 3)} × {_f(Morig, 2)}",
                          f"= {_f(abs(Mstar), 2)} kN·m"])
        return None
    for kind in ["phi", "de", "kb", "D", "Ncr", "eta", "Ms"]:
        c1 = _mk(*dirs[0], kind)
        c2 = _mk(*dirs[1], kind)
        S.extend(_two(P, st, c1, c2))
    Ma = math.hypot(res.Mx_star, res.My_star)
    alpha = math.degrees(math.atan2(res.My_star, res.Mx_star)) \
        if Ma > 1e-9 else 0.0
    S.append(KeepTogether(_two(P, st,
        _mk( "Góc tác dụng mô men uốn tổng hợp α", "Góc uốn xiên",
              ["α = arctan(M₃* / M₂*)",
               f"= arctan({_f(abs(res.My_star), 2)} / "
               f"{_f(abs(res.Mx_star), 2)})",
               f"= {_f(alpha, 2)} độ (°)"]),
        _mk( "Mô men uốn xiên tổng hợp Mα", "Véc-tơ tổng hợp",
              ["Mα = √((M₂*)² + (M₃*)²)",
               f"= √({_f(abs(res.Mx_star), 2)}² + "
               f"{_f(abs(res.My_star), 2)}²)",
               f"= {_f(Ma, 2)} kN·m"]))))

    # ================= MỤC 6 =================
    S.append(_sec_head(P, st, 6,
                       "ĐÁNH GIÁ KHẢ NĂNG CHỊU LỰC THEO MÔ HÌNH BIẾN DẠNG "
                       "PHI TUYẾN (NDM)",
                       "TCVN 5574:2018 Mục 8.1.2.7"))
    OA = math.sqrt(res.Mx_star**2 + res.My_star**2 + res.N**2)
    OB = math.sqrt(res.Bx**2 + res.By**2 + res.BN**2)
    S.append(KeepTogether(_two(P, st,
        _mk( "Điểm nội lực tính toán A (Nội lực tác dụng)", "",
              ["A = (M₂tt, M₃tt, N)",
               f"= ({_f(res.Mx_star, 1)}, {_f(res.My_star, 1)}, "
               f"{_f(res.N, 1)})",
               f"= |OA| = {_f(OA, 1)} kN/kNm"]),
        _mk( "Điểm giới hạn B (trên mặt tương tác)", "",
              ["B = (M₂gh, M₃gh, Ngh)",
               f"= ({_f(res.Bx, 1)}, {_f(res.By, 1)}, "
               f"{_f(res.BN, 1)})",
               f"= |OB| = {_f(OB, 1)} kN/kNm"]))))
    S.append(KeepTogether(_two(P, st,
        _mk( "Góc uốn xiên α", "",
              [f"α = {_f(alpha, 1)}°",
               f"Mα = {_f(Ma, 1)} kN·m"]),
        _mk( "Tỷ số D/C", "",
              [f"D/C = |OA| / |OB| = {_f(OA, 1)} / {_f(OB, 1)}",
               f"= {_f(res.dc, 3)} (FS = {_f(res.fs, 2)})"]))))
    # Biểu đồ
    _pngs = chart_pngs
    if not _pngs:
        try:
            from .pdf_export import interaction_image, m2m3_image
            _pngs = (interaction_image(sec, inp, res, width_in=4.0),
                     m2m3_image(sec, inp, res, width_in=4.0))
        except Exception:
            _pngs = None
    if _pngs:
        img1 = Image(io.BytesIO(_pngs[0]), width=80*mm, height=60*mm)
        img2 = Image(io.BytesIO(_pngs[1]), width=80*mm, height=60*mm)
        S.append(P("Biểu đồ tương tác N-Mα", st["cap"]))
        S.append(img1)
        S.append(P("Biểu đồ tương tác M2-M3", st["cap"]))
        S.append(img2)
    S.append(P(f"TỶ SỐ SỬ DỤNG (D/C) = {_f(res.dc, 3)} "
               f"(FS = {_f(res.fs, 2)}) — "
               f"{'✓ ĐẠT — D/C ≤ 1.000' if res.ok else '✗ KHÔNG ĐẠT'}",
               st["dc_ok"] if res.ok else st["dc_ng"]))

    # ================= MỤC 7 =================
    S.append(_sec_head(P, st, 7, "KIỂM TRA CỐT THÉP ĐAI",
                       "TCVN 5574:2018 Mục 10.3.4 & 8.1.3"))
    from .stirrup import StirrupInput, check_stirrup, check_shear
    stir_in = StirrupInput(dia=inp.sw_dia, spacing=inp.sw_spacing,
                           legs=inp.sw_legs)
    stir_res = check_stirrup(sec, stir_in, inp.concrete_grade)
    chk_lines = []
    for chk in stir_res.checks:
        mark = "✓" if chk.ok else "✗"
        chk_lines.append(f"{mark} {chk.item}: yêu cầu {chk.required}, "
                         f"chọn {chk.provided}")
    S.extend(_two(P, st, _mk("Cấu tạo cốt đai (10.3.4)", "", chk_lines),
                      _EMPTY))
    sw_grade = STEEL_GRADES.get(inp.sw_steel_grade, STEEL_GRADES["CB400-V"])
    if shear_info:
        q2i, q3i = shear_info["q2"], shear_info["q3"]
        S.extend(_two(P, st, _mk("Lực cắt tính toán", "",
                       [f"Q2 = {_f(q2i['Q'], 1)} kN "
                        f"({q2i['case']}@{q2i['station']:.2f})",
                        f"Q3 = {_f(q3i['Q'], 1)} kN "
                        f"({q3i['case']}@{q3i['station']:.2f})",
                        "Độc lập với combo N-M nguy hiểm nhất"]),
                      _EMPTY))
    Rb = conc.Rb
    Rbt = conc.Rbt
    Rsw = sw_grade.Rsw * inp.gamma_s
    Asw_1 = math.pi * stir_in.dia ** 2 / 4
    h0_2 = sec.cx - inp.cover - stir_in.dia - inp.bar_dia / 2
    h0_3 = sec.cy - inp.cover - stir_in.dia - inp.bar_dia / 2
    shear_ok = True
    cards7 = []
    for Q, b_w, h0, dnum in ((inp.Q2, sec.cy, h0_2, "2"),
                             (inp.Q3, sec.cx, h0_3, "3")):
        Asw = Asw_1 * stir_in.legs
        h0u = max(h0, 1)
        sh = check_shear(Q, b_w, h0u, Rb, Rbt, Asw, Rsw,
                         stir_in.spacing, direction=dnum)
        m1 = "✓" if sh.ok1 else "✗"
        m2 = "✓" if sh.ok2 else "✗"
        qsw = Rsw * Asw / stir_in.spacing if stir_in.spacing > 0 else 0
        Qb_lo = 0.5 * Rbt * b_w * h0u / 1000.0
        Qb_hi = 2.5 * Rbt * b_w * h0u / 1000.0
        cards7.append(_mk( f"Kiểm tra chịu cắt phương {dnum}", "",
            [f"Q = {_f(Q, 1)} kN; b = {b_w:.0f} mm, h₀ = {h0u:.0f} mm",
             f"Asw = {stir_in.legs}×φ{stir_in.dia:.0f} = {Asw:.0f} mm²",
             f"{m1} ĐK1 (dải nén xiên): Q ≤ 0.3×Rb×b×h₀",
             f"  = 0.3×{_f(Rb, 2)}×{b_w:.0f}×{h0u:.0f}/1000 "
             f"= {_f(sh.Qcap1, 1)} kN",
             f"{m2} ĐK2 (vết nứt xiên): Q ≤ Qb + Qsw",
             f"  qsw = {_f(Rsw, 0)}×{Asw:.0f}/{stir_in.spacing:.0f} "
             f"= {_f(qsw, 1)} N/mm",
             f"  Qb = 1.5×{_f(Rbt, 2)}×{b_w:.0f}×{h0u:.0f}²/"
             f"{sh.C_opt:.0f}/1000 = {_f(sh.Qb_opt, 1)} kN",
             f"  (Qb ∈ [{_f(Qb_lo, 1)}, {_f(Qb_hi, 1)}] kN)",
             f"  Qsw = 0.75×{_f(qsw, 1)}×{sh.C_opt:.0f}/1000 "
             f"= {_f(sh.Qsw_opt, 1)} kN",
             f"  → [Q]min = {_f(sh.Qcap2, 1)} kN tại C = {sh.C_opt:.0f} mm"]))
        shear_ok &= sh.ok
    if len(cards7) == 2:
        S.extend(_two(P, st, cards7[0], cards7[1]))
    else:
        for c in cards7:
            S.append(c)
    ok7 = stir_res.ok and shear_ok
    S.append(P(f"{'✓ ĐẠT' if ok7 else '✗ KHÔNG ĐẠT'} — Cốt đai thỏa "
               "TCVN 5574:2018" if ok7 else "Xem lại cốt đai",
               st["dc_ok"] if ok7 else st["dc_ng"]))

    doc.build(S)
