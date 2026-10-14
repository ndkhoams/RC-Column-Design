"""Xuất PDF thuyết minh kiểu card giống app (Vietcon style).

Dùng ReportLab để tạo layout card 2 cột giống như hiển thị trong app.
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


# Màu sắc (giống app)
WHITE = "#FFFFFF"
BORDER = "#E5E7EB"
TEXT = "#111827"
GRAY = "#6B7280"
FORMULA_BG = "#F9FAFB"

_DOT_COLORS = ["#2563EB", "#059669", "#D97706", "#7C3AED", "#DB2777", "#0891B2"]


def _get_styles():
    """Tạo các ParagraphStyle cho PDF."""
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
    pdfmetrics.registerFont(TTFont("VN", font_path))
    pdfmetrics.registerFont(TTFont("VN-Bold", bold_path or font_path))

    styles = {
        "title": ParagraphStyle("title", fontName="VN-Bold", fontSize=14,
                                textColor=HexColor(TEXT), alignment=TA_CENTER,
                                spaceAfter=4),
        "sub": ParagraphStyle("sub", fontName="VN", fontSize=9,
                              textColor=HexColor(GRAY), alignment=TA_CENTER,
                              spaceAfter=8),
        "sec_title": ParagraphStyle("sec_title", fontName="VN-Bold",
                                    fontSize=11, textColor=HexColor(TEXT),
                                    spaceBefore=8, spaceAfter=4),
        "sec_ref": ParagraphStyle("sec_ref", fontName="VN", fontSize=8,
                                  textColor=HexColor(GRAY)),
        "card_title": ParagraphStyle("card_title", fontName="VN-Bold",
                                     fontSize=10, textColor=HexColor(TEXT),
                                     spaceAfter=4),
        "card_ref": ParagraphStyle("card_ref", fontName="VN", fontSize=7,
                                   textColor=HexColor(GRAY)),
        "formula": ParagraphStyle("formula", fontName="VN", fontSize=8.5,
                                  textColor=HexColor("#374151"), leading=12,
                                  leftIndent=8, spaceAfter=1),
        "result": ParagraphStyle("result", fontName="VN-Bold", fontSize=10,
                                 textColor=HexColor(TEXT), spaceBefore=4),
        "note": ParagraphStyle("note", fontName="VN", fontSize=7.5,
                               textColor=HexColor(GRAY), leading=10,
                               spaceBefore=4),
        "dc_ok": ParagraphStyle("dc_ok", fontName="VN-Bold", fontSize=11,
                                textColor=HexColor("#065F46"),
                                backColor=HexColor("#D1FAE5"),
                                borderPadding=8, alignment=TA_CENTER,
                                spaceBefore=8, spaceAfter=8),
        "dc_ng": ParagraphStyle("dc_ng", fontName="VN-Bold", fontSize=11,
                                textColor=HexColor("#991B1B"),
                                backColor=HexColor("#FEE2E2"),
                                borderPadding=8, alignment=TA_CENTER,
                                spaceBefore=8, spaceAfter=8),
    }
    return styles


def _pdf_card(P, styles, title, ref, lines, result=""):
    """Tạo một card (Table) với tiêu đề, công thức, kết quả."""
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.colors import HexColor

    content = []
    # Tiêu đề + ref
    if ref:
        t = Table([
            [P(title, styles["card_title"]),
             P(ref, styles["card_ref"])]
        ], colWidths=[220, 80])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ]))
        content.append([t])
    else:
        content.append([P(title, styles["card_title"])])
    # Công thức
    for ln in lines:
        content.append([P(ln, styles["formula"])])
    # Kết quả
    if result:
        content.append([P(result, styles["result"])])

    card = Table(content, colWidths=[300])
    card.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor(BORDER)),
        ("BACKGROUND", (0, 0), (-1, -1), HexColor(WHITE)),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        # Nền xám nhạt cho các dòng công thức (từ dòng 1 trở đi, trừ kết quả)
        ("BACKGROUND", (0, 1), (-1, -2), HexColor(FORMULA_BG)),
        ("LINEBELOW", (0, 1), (-1, -2), 2, HexColor("#D1D5DB")),
    ]))
    return card


def _pdf_two_col(P, styles, card1, card2):
    """Hai card cạnh nhau."""
    from reportlab.platypus import Table, TableStyle
    t = Table([[card1, card2]], colWidths=[155, 155])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _pdf_section_header(P, styles, num, title, ref):
    """Header mục với chấm màu."""
    from reportlab.lib.colors import HexColor
    dot_color = _DOT_COLORS[(num - 1) % len(_DOT_COLORS)]
    # Dùng HTML để tạo chấm màu
    html = (f'<font color="{dot_color}">●</font> '
            f'<b>{num}. {title}</b>')
    return P(html, styles["sec_title"])


def export_pdf_cards(inp: ColumnInput, res: CheckResult, filepath: str,
                     case_info=None, shear_info=None):
    """Xuất PDF thuyết minh kiểu card giống app."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Image, Table, TableStyle)
    from reportlab.lib.colors import HexColor

    styles = _get_styles()
    P = Paragraph
    sec = build_section(inp)

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    S = []

    # Tiêu đề
    S.append(P("THUYẾT MINH TÍNH TOÁN KIỂM TRA CỘT BTCT",
               styles["title"]))
    S.append(P("Tiêu chuẩn: TCVN 5574:2018 — Mô hình biến dạng phi tuyến "
               "(Điều 8.1.2.7)", styles["sub"]))

    # --- Mục 1 ---
    S.append(_pdf_section_header(P, styles, 1,
                                 "ĐẶC TRƯNG VẬT LIỆU & CƯỜNG ĐỘ TÍNH TOÁN",
                                 "TCVN 5574:2018 Mục 6.1 & 6.2"))
    conc = sec.concrete
    steel = sec.steel
    c1 = _pdf_card(P, styles, "Bê tông: Cường độ chịu nén tính toán Rb*",
                   "Bảng 6 & Mục 6.1.2.3",
                   [f"Rb* = γb · Rb",
                    f"= {_f(inp.gamma_b)} × {_f(conc.grade.Rb)}",
                    f"= {_f(conc.Rb)} MPa (N/mm²)"])
    c2 = _pdf_card(P, styles, "Bê tông: Mô đun đàn hồi ban đầu Eb",
                   "Bảng 10",
                   [f"Eb (Cấp độ bền {inp.concrete_grade})",
                    f"= {conc.Eb:,.0f} N/mm²",
                    f"= {_f(conc.Eb / 1000, 1)} × 10³ MPa"])
    S.append(_pdf_two_col(P, styles, c1, c2))
    c1 = _pdf_card(P, styles, "Cốt thép: Cường độ chịu kéo tính toán Rs",
                   "Bảng 13 & Mục 6.2.2",
                   [f"Rs = (Rsn / γs) · γsi",
                    f"= ({steel.grade.Rs:.0f} / 1.15) × {_f(inp.gamma_s)}",
                    f"= {_f(steel.Rs, 1)} MPa"])
    c2 = _pdf_card(P, styles, "Cốt thép: Cường độ chịu nén tính toán Rsc",
                   "Bảng 13 & Mục 6.2.2.2",
                   [f"Tác dụng ngắn hạn: Rsc = {steel.Rsc:.0f} MPa",
                    f"Tác dụng dài hạn: Rsc = {steel.Rsc:.0f} MPa"])
    S.append(_pdf_two_col(P, styles, c1, c2))
    c1 = _pdf_card(P, styles, "Cốt thép: Mô đun đàn hồi Es",
                   "Mục 6.2.2.4",
                   [f"Es (Cốt thép {inp.steel_grade})",
                    f"= {steel.Es:,.0f} N/mm²"])
    c2 = _pdf_card(P, styles, "Tỷ số mô đun đàn hồi αe", "Mô hình quy đổi",
                   [f"αe = Es / Eb",
                    f"= {steel.Es:,.0f} / {conc.Eb:,.0f}",
                    f"= {_f(res.alpha_e)} -"])
    S.append(_pdf_two_col(P, styles, c1, c2))

    # --- Mục 2 ---
    S.append(_pdf_section_header(P, styles, 2,
                                 "ĐẶC TRƯNG HÌNH HỌC TIẾT DIỆN CỘT CHỮ NHẬT",
                                 f"Kích thước {inp.cx:.0f} × {inp.cy:.0f} mm"))
    c1 = _pdf_card(P, styles, "Diện tích tiết diện bê tông nguyên A", "",
                   [f"A = t2 · t3",
                    f"= {inp.cy:.0f} × {inp.cx:.0f}",
                    f"= {sec.gross_area:,.0f} mm²"])
    c2 = _pdf_card(P, styles, "Lớp bê tông bảo vệ cốt dọc c", "",
                   [f"c = {inp.cover:.0f} mm"])
    S.append(_pdf_two_col(P, styles, c1, c2))
    c1 = _pdf_card(P, styles, "Mô men quán tính trục 2 (I2)", "",
                   [f"I₂ = (t3 · t2³) / 12",
                    f"= ({inp.cx:.0f} × {inp.cy:.0f}³) / 12",
                    f"= {_f(res.Ix / 1e9, 3)} × 10⁹ mm⁴"])
    c2 = _pdf_card(P, styles, "Mô men quán tính trục 3 (I3)", "",
                   [f"I₃ = (t2 · t3³) / 12",
                    f"= ({inp.cy:.0f} × {inp.cx:.0f}³) / 12",
                    f"= {_f(res.Iy / 1e9, 3)} × 10⁹ mm⁴"])
    S.append(_pdf_two_col(P, styles, c1, c2))
    c1 = _pdf_card(P, styles, "Bán kính quán tính phương 2 (i2)", "",
                   [f"i₂ = t2 / √12 = {inp.cy:.0f} / 3.464",
                    f"= {_f(res.ix, 2)} mm"])
    c2 = _pdf_card(P, styles, "Bán kính quán tính phương 3 (i3)", "",
                   [f"i₃ = t3 / √12 = {inp.cx:.0f} / 3.464",
                    f"= {_f(res.iy, 2)} mm"])
    S.append(_pdf_two_col(P, styles, c1, c2))

    # --- Mục 3 ---
    S.append(_pdf_section_header(P, styles, 3,
                                 "CHIỀU DÀI TÍNH TOÁN & ĐỘ MẢNH",
                                 "TCVN 5574:2018 Mục 8.1.2.4"))
    c1 = _pdf_card(P, styles, "Chiều dài tính toán phương 2 (L02)", "",
                   [f"L₀₂ = ψ · L = {_f(inp.psi_x, 2)} × {_f(inp.Lx, 2)}",
                    f"= {_f(res.L0x, 2)} m"])
    c2 = _pdf_card(P, styles, "Chiều dài tính toán phương 3 (L03)", "",
                   [f"L₀₃ = ψ · L = {_f(inp.psi_y, 2)} × {_f(inp.Ly, 2)}",
                    f"= {_f(res.L0y, 2)} m"])
    S.append(_pdf_two_col(P, styles, c1, c2))
    ok2 = "ĐẠT" if res.lambda_x <= 120 else "KHÔNG ĐẠT"
    ok3 = "ĐẠT" if res.lambda_y <= 120 else "KHÔNG ĐẠT"
    c1 = _pdf_card(P, styles, "Độ mảnh cột phương 2 (λ2)", "",
                   [f"λ₂ = L₀₂ / i₂ = {_f(res.lambda_x, 1)} ≤ 120 → {ok2}"])
    c2 = _pdf_card(P, styles, "Độ mảnh cột phương 3 (λ3)", "",
                   [f"λ₃ = L₀₃ / i₃ = {_f(res.lambda_y, 1)} ≤ 120 → {ok3}"])
    S.append(_pdf_two_col(P, styles, c1, c2))

    # --- Mục 4 ---
    S.append(_pdf_section_header(P, styles, 4, "ĐỘ LỆCH TÂM",
                                 "TCVN 5574:2018 Mục 8.1.2.2.4"))
    if case_info:
        S.append(P(f"Tổ hợp: {case_info.get('case')}@"
                   f"{case_info.get('station', 0):.2f} — "
                   f"N = {_f(case_info.get('N', 0), 1)} kN",
                   styles["note"]))
    c1 = _pdf_card(P, styles, "Độ lệch tâm tĩnh học phương 2 (e12)", "",
                   [f"e₁₂ = |M₂| / N = {_f(res.e1x, 2)} mm"])
    c2 = _pdf_card(P, styles, "Độ lệch tâm tĩnh học phương 3 (e13)", "",
                   [f"e₁₃ = |M₃| / N = {_f(res.e1y, 2)} mm"])
    S.append(_pdf_two_col(P, styles, c1, c2))
    c1 = _pdf_card(P, styles, "Độ lệch tâm ngẫu nhiên phương 2 (ea2)", "",
                   [f"ea₂ = {_f(res.eax, 1)} mm"])
    c2 = _pdf_card(P, styles, "Độ lệch tâm ngẫu nhiên phương 3 (ea3)", "",
                   [f"ea₃ = {_f(res.eay, 1)} mm"])
    S.append(_pdf_two_col(P, styles, c1, c2))
    c1 = _pdf_card(P, styles, "Độ lệch tâm ban đầu phương 2 (e02)", "",
                   [f"e₀₂ = {_f(res.e0x, 1)} mm"])
    c2 = _pdf_card(P, styles, "Độ lệch tâm ban đầu phương 3 (e03)", "",
                   [f"e₀₃ = {_f(res.e0y, 1)} mm"])
    S.append(_pdf_two_col(P, styles, c1, c2))

    # --- Mục 5 ---
    S.append(_pdf_section_header(P, styles, 5,
                                 "UỐN DỌC & PHÓNG ĐẠI MÔ MEN",
                                 "CT (44)–(48)"))
    # (Rút gọn cho PDF: hiển thị dạng bảng 2 cột)
    rows = [
        ["φL", _f(res.phi_L, 2)],
        ["δe₂ / δe₃", f"{_f(res.delta_ex, 3)} / {_f(res.delta_ey, 3)}"],
        ["kb₂ / kb₃", f"{_f(res.kbx, 4)} / {_f(res.kby, 4)}"],
        ["D₂ / D₃ (kN·m²)", f"{_f(res.Dx, 1)} / {_f(res.Dy, 1)}"],
        ["Ncr,2 / Ncr,3 (kN)", f"{_f(res.Ncrx, 1)} / {_f(res.Ncry, 1)}"],
        ["η₂ / η₃", f"{_f(res.etax, 3)} / {_f(res.etay, 3)}"],
        ["M₂* / M₃* (kN·m)",
         f"{_f(res.Mx_star, 1)} / {_f(res.My_star, 1)}"],
    ]
    tdata = [[P(f"<b>{r[0]}</b>", styles["formula"]),
              P(r[1], styles["formula"])] for r in rows]
    tbl = Table(tdata, colWidths=[150, 160])
    tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor(BORDER)),
        ("GRID", (0, 0), (-1, -1), 0.25, HexColor(BORDER)),
        ("BACKGROUND", (0, 0), (0, -1), HexColor(FORMULA_BG)),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    S.append(tbl)
    S.append(Spacer(1, 6))

    # --- Mục 6 ---
    S.append(_pdf_section_header(P, styles, 6,
                                 "KIỂM TRA THEO MÔ HÌNH PHI TUYẾN (NDM)",
                                 "TCVN 5574:2018 Điều 8.1.2.7"))
    OA = math.sqrt(res.Mx_star**2 + res.My_star**2 + res.N**2)
    OB = math.sqrt(res.Bx**2 + res.By**2 + res.BN**2)
    c1 = _pdf_card(P, styles, "Điểm nội lực tính toán A", "",
                   [f"A = (M₂tt, M₃tt, N)",
                    f"= ({_f(res.Mx_star, 1)}, {_f(res.My_star, 1)}, "
                    f"{_f(res.N, 1)})",
                    f"= |OA| = {_f(OA, 1)} kN/kNm"])
    c2 = _pdf_card(P, styles, "Điểm giới hạn B", "",
                   [f"B = (M₂gh, M₃gh, Ngh)",
                    f"= ({_f(res.Bx, 1)}, {_f(res.By, 1)}, "
                    f"{_f(res.BN, 1)})",
                    f"= |OB| = {_f(OB, 1)} kN/kNm"])
    S.append(_pdf_two_col(P, styles, c1, c2))
    # Biểu đồ
    try:
        from .pdf_export import interaction_image, m2m3_image
        png_nm = interaction_image(sec, inp, res, width_in=4.0)
        png_m2m3 = m2m3_image(sec, inp, res, width_in=4.0)
        img1 = Image(io.BytesIO(png_nm), width=85*mm, height=64*mm)
        img2 = Image(io.BytesIO(png_m2m3), width=85*mm, height=64*mm)
        t = Table([[img1, img2]], colWidths=[90*mm, 90*mm])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        S.append(t)
        S.append(Spacer(1, 6))
    except Exception:
        pass
    # D/C
    dc_text = (f"TỶ SỐ SỬ DỤNG (D/C) = {_f(res.dc, 3)} "
               f"(FS = {_f(res.fs, 2)}) — "
               f"{'ĐẠT' if res.ok else 'KHÔNG ĐẠT'}")
    S.append(P(dc_text, styles["dc_ok"] if res.ok else styles["dc_ng"]))

    # --- Mục 7 ---
    S.append(_pdf_section_header(P, styles, 7, "KIỂM TRA CỐT THÉP ĐAI",
                                 "TCVN 5574:2018 Mục 10.3.4 & 8.1.3"))
    from .stirrup import StirrupInput, check_stirrup, check_shear
    stir_in = StirrupInput(dia=inp.sw_dia, spacing=inp.sw_spacing,
                           legs=inp.sw_legs)
    stir_res = check_stirrup(sec, stir_in, inp.concrete_grade)
    # (Rút gọn: bảng kết quả)
    S.append(P(f"Kết luận: {'ĐẠT' if stir_res.ok else 'KHÔNG ĐẠT'} — "
               f"Cốt đai thỏa TCVN 5574:2018",
               styles["dc_ok"] if stir_res.ok else styles["dc_ng"]))

    doc.build(S)
