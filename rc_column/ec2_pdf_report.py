"""Xuất PDF thuyết minh kiểm tra cột theo EC2 (EN 1992-1-1).

Render các section từ ec2_report.generate_ec2_report_sections thành
PDF A4 dọc với card style giống hệt bản TCVN (pdf_report_cards.py).

Không phụ thuộc GUI/matplotlib trực tiếp.
"""

import io

from .ec2_report import generate_ec2_report_sections


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
GREEN = "#059669"
GREEN_BG = "#D1FAE5"
RED = "#DC2626"
RED_BG = "#FEE2E2"
_DOT_COLORS = ["#2563EB", "#059669", "#D97706", "#7C3AED", "#DB2777", "#0891B2"]


def _find_ec2_font():
    """Tìm font DejaVu Sans: ưu tiên helper của pdf_export, fallback qua
    matplotlib.font_manager (cho môi trường hệ thống đặt mpl-data ở
    /usr/share)."""
    try:
        from .pdf_export import _find_font
        p = _find_font()
        if p:
            return p
    except Exception:
        pass
    try:
        import matplotlib.font_manager as fm
        return fm.findfont("DejaVu Sans")
    except Exception:
        return None


def _find_ec2_font_bold():
    try:
        from .pdf_export import _find_font_bold
        p = _find_font_bold()
        if p:
            return p
    except Exception:
        pass
    try:
        import matplotlib.font_manager as fm
        return fm.findfont("DejaVu Sans", weight="bold")
    except Exception:
        return None


def _get_styles():
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_path = _find_ec2_font()
    bold_path = _find_ec2_font_bold()
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
                                    fontSize=12, textColor=HexColor(TEXT),
                                    spaceBefore=12, spaceAfter=6),
        "sec_ref": ParagraphStyle("sec_ref", fontName="VN", fontSize=8,
                                  textColor=HexColor(GRAY), leading=10,
                                  spaceAfter=4),
        "card_title": ParagraphStyle("card_title", fontName="VN-Bold",
                                     fontSize=10, textColor=HexColor(TEXT),
                                     leading=12, spaceAfter=2),
        "card_ref": ParagraphStyle("card_ref", fontName="VN", fontSize=8,
                                   textColor=HexColor(GRAY), leading=10,
                                   spaceAfter=2),
        "formula": ParagraphStyle("formula", fontName="VN", fontSize=9,
                                  textColor=HexColor("#374151"), leading=12,
                                  leftIndent=6, spaceAfter=1),
        "result": ParagraphStyle("result", fontName="VN-Bold", fontSize=10,
                                 textColor=HexColor(TEXT), leading=12,
                                 spaceBefore=4),
        "result_ok": ParagraphStyle("result_ok", fontName="VN-Bold",
                                    fontSize=10,
                                    textColor=HexColor(GREEN), leading=12,
                                    spaceBefore=4),
        "result_ng": ParagraphStyle("result_ng", fontName="VN-Bold",
                                    fontSize=10,
                                    textColor=HexColor(RED), leading=12,
                                    spaceBefore=4),
        "note": ParagraphStyle("note", fontName="VN", fontSize=9,
                               textColor=HexColor(GRAY), leading=12,
                               spaceBefore=4, spaceAfter=4),
        "dc_ok": ParagraphStyle("dc_ok", fontName="VN-Bold", fontSize=10,
                                textColor=HexColor(GREEN),
                                backColor=HexColor(GREEN_BG),
                                borderPadding=10, alignment=TA_CENTER,
                                spaceBefore=10, spaceAfter=10),
        "dc_ng": ParagraphStyle("dc_ng", fontName="VN-Bold", fontSize=10,
                                textColor=HexColor(RED),
                                backColor=HexColor(RED_BG),
                                borderPadding=10, alignment=TA_CENTER,
                                spaceBefore=10, spaceAfter=10),
        "cap": ParagraphStyle("cap", fontName="VN", fontSize=8,
                              textColor=HexColor(GRAY), alignment=TA_CENTER,
                              spaceBefore=4, spaceAfter=8),
    }


def _card_story(P, st, c):
    """Trả về list flowables cho 1 card."""
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm

    items = []
    if c.get("title"):
        items.append(P(c["title"], st["card_title"]))
    if c.get("ref"):
        items.append(P(c["ref"], st["card_ref"]))
    for ln in c.get("lines", []):
        items.append(P(ln, st["formula"]))
    if c.get("result"):
        r = c["result"]
        # Tô màu kết luận ĐẠT/KHÔNG ĐẠT
        if "KHÔNG ĐẠT" in r:
            rs = st["result_ng"]
        elif "ĐẠT" in r and "→ OK" in r:
            rs = st["result_ok"]
        else:
            rs = st["result"]
        items.append(P(r, rs))
    return items


def _two_cards(P, st, c1, c2):
    """2 card đặt ngang nhau, tự chia đều cột."""
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm

    def _one(c):
        from reportlab.platypus import Table
        rows = []
        if c.get("title"):
            rows.append([P(c["title"], st["card_title"])])
        if c.get("ref"):
            rows.append([P(c["ref"], st["card_ref"])])
        for ln in c.get("lines", []):
            rows.append([P(ln, st["formula"])])
        if c.get("result"):
            r = c["result"]
            if "KHÔNG ĐẠT" in r:
                rs = st["result_ng"]
            elif "ĐẠT" in r:
                rs = st["result_ok"]
            else:
                rs = st["result"]
            rows.append([P(r, rs)])
        if not rows:
            rows.append([P("", st["formula"])])
        t = Table(rows)
        sty = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("BOX", (0, 0), (-1, -1), 0.8, HexColor(BORDER)),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, HexColor(BORDER)),
            ("BACKGROUND", (0, 0), (-1, 0), HexColor(WHITE)),
        ]
        # Dòng công thức: nền nhạt + viền trái
        for i, row in enumerate(rows):
            is_formula = (c.get("title") and c.get("ref") and i >= 2) or \
                        (c.get("title") and not c.get("ref") and i >= 1) or \
                        (not c.get("title") and c.get("ref") and i >= 1)
            if is_formula and not (c.get("result") and i == len(rows) - 1):
                sty.append(("BACKGROUND", (0, i), (-1, i),
                            HexColor(FORMULA_BG)))
        t.setStyle(TableStyle(sty))
        return t

    t = Table([[_one(c1), _one(c2)]])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [t, Spacer(1, 4 * mm)]


def _sec_head(P, st, num, title, ref=""):
    """Header mục: 'N. TITLE' bold 12 + ref xám 8 bên phải."""
    from reportlab.platypus import Table, TableStyle
    dot = _DOT_COLORS[(num - 1) % len(_DOT_COLORS)]
    rows = [[P(f'<font color="{dot}">●</font>&nbsp;&nbsp;'
               f'{num}. {title}', st["sec_title"])]]
    if ref:
        rows.append([P(f'<font color="{GRAY}">{ref}</font>',
                       st["sec_ref"])])
    t = Table(rows)
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return t


def _img_keep_aspect(png_bytes, w_mm=88):
    """Tạo Image giữ đúng tỉ lệ gốc của PNG (không méo hình)."""
    from reportlab.platypus import Image
    from reportlab.lib.units import mm
    try:
        from PIL import Image as _PILImage
        _pil = _PILImage.open(io.BytesIO(png_bytes))
        _pw, _ph = _pil.size
        _hh = w_mm * _ph / _pw if _pw > 0 else w_mm * 0.75
    except Exception:
        _hh = w_mm * 0.75
    return Image(io.BytesIO(png_bytes), width=w_mm * mm, height=_hh * mm)


def _full_case(d):
    """Format đầy đủ: [story, column, case@station]."""
    parts = []
    if d.get("story"):
        parts.append(str(d["story"]))
    if d.get("column"):
        parts.append(str(d["column"]))
    cs = f"{d.get('case', '')}@{d.get('station', 0):.2f}"
    parts.append(cs)
    return "[" + ", ".join(parts) + "]"


def export_ec2_pdf_cards(inp, ec2_res, slend_res, shear_res, conc, steel,
                         filepath, chart_pngs=None, case_info=None, tied=None):
    """Xuất PDF thuyết minh EC2 (EN 1992-1-1) kiểu card giống hệt app.

    inp: ColumnInput. ec2_res/slend_res/shear_res: dict kết quả EC2.
    conc: EC2Concrete, steel: EC2Steel.
    chart_pngs: tuple 2 bytes PNG (N-Mα, M2-M3) — nhúng vào mục 3.
    case_info: dict {story, column, case, station, N, M2, M3} (optional).
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, KeepTogether)
    from reportlab.lib.colors import HexColor

    st = _get_styles()
    P = Paragraph

    sections = generate_ec2_report_sections(inp, ec2_res, slend_res,
                                            shear_res, conc, steel)

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm)
    S = []
    S.append(P("THUYẾT MINH TÍNH TOÁN CỘT BTCT — EC2 (EN 1992-1-1)", st["title"]))
    S.append(P("Tiêu chuẩn: EC2 (EN 1992-1-1) — Kiểm tra P-M-M, độ mảnh và cắt",
               st["sub"]))

    if case_info:
        S.append(P(f"Tổ hợp tính toán: {_full_case(case_info)} — "
                   f"N = {_f(case_info.get('N', 0), 1)} kN, "
                   f"M2 = {_f(case_info.get('M2', 0), 1)} kN·m, "
                   f"M3 = {_f(case_info.get('M3', 0), 1)} kN·m",
                   st["note"]))

    for sec in sections:
        S.append(_sec_head(P, st, sec["num"], sec["title"],
                           sec.get("ref", "")))
        cards = sec.get("cards", [])
        # Xếp card 2 cột
        i = 0
        while i < len(cards):
            c1 = cards[i]
            c2 = cards[i + 1] if i + 1 < len(cards) else \
                {"title": "", "ref": "", "lines": [], "result": ""}
            S.extend(_two_cards(P, st, c1, c2))
            i += 2

        # Mục 3 (P-M-M): nhúng 2 biểu đồ ngang nhau, giữ tỉ lệ
        if sec["num"] == 3 and chart_pngs:
            try:
                img1 = _img_keep_aspect(chart_pngs[0])
                img2 = _img_keep_aspect(chart_pngs[1])
                ct = Table([
                    [[P("Biểu đồ tương tác N-Mα (EC2)", st["cap"]), img1],
                     [P("Biểu đồ tương tác M2-M3 (EC2)", st["cap"]), img2]]
                ])
                ct.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]))
                S.append(ct)
                S.append(Spacer(1, 4 * mm))
            except Exception:
                pass

        # Banner kết luận cho mục 3 (P-M-M) và mục 4 (cắt)
        if sec["num"] in (3, 4):
            if sec["num"] == 3:
                ok = bool(ec2_res.get("ok", False))
                dc = ec2_res.get("dc", 0.0) or 0.0
                fs = ec2_res.get("fs", 0.0) or 0.0
                dc_txt = f"{dc:.3f}" if dc != float("inf") else "∞"
                fs_txt = f"{fs:.2f}" if fs != float("inf") else "∞"
                txt = (f"TỶ SỐ SỬ DỤNG (D/C) = {dc_txt} (FS = {fs_txt}) — "
                       f"{'✓ ĐẠT — D/C ≤ 1.000' if ok else '✗ KHÔNG ĐẠT'}")
            else:
                _shr = shear_res or {}
                _d2 = _shr.get("dir2", {}) if isinstance(_shr, dict) else {}
                _d3 = _shr.get("dir3", {}) if isinstance(_shr, dict) else {}
                ok = bool(_d2.get("ok", False) and _d3.get("ok", False))
                _v2 = abs(getattr(inp, "Q2", 0.0) or 0.0)
                _v3 = abs(getattr(inp, "Q3", 0.0) or 0.0)
                _r2 = _d2.get("VRd_kN", 0.0) or 0.0
                _r3 = _d3.get("VRd_kN", 0.0) or 0.0
                txt = (f"VEd2 = {_f(_v2, 1)} kN ≤ VRd = {_f(_r2, 1)} kN; "
                       f"VEd3 = {_f(_v3, 1)} kN ≤ VRd = {_f(_r3, 1)} kN — "
                       f"{'✓ ĐẠT' if ok else '✗ KHÔNG ĐẠT'}")
            S.append(P(txt, st["dc_ok"] if ok else st["dc_ng"]))

    doc.build(S)
    return filepath
