"""Xuất PDF thuyết minh kiểm tra cột theo EC2 (EN 1992-1-1).

Render các section từ ec2_report.generate_ec2_report_sections thành
PDF A4 dọc với card style giống hệt bản TCVN (pdf_report_cards.py).

Không phụ thuộc GUI/matplotlib trực tiếp.
"""

import io

from .ec2_report_v2 import generate_ec2_report_sections_v2
from .pdf_report_cards import (_get_styles, _two, _sec_head, _full_case)


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


def export_ec2_pdf_cards(inp, ec2_res, slend_res, shear_res, conc, steel,
                         filepath, chart_pngs=None, case_info=None, tied=None,
                         sec=None):
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

    sections = generate_ec2_report_sections_v2(inp, ec2_res, slend_res,
                                                  shear_res, conc, steel, sec)

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

    for _s in sections:
        S.append(_sec_head(P, st, _s["num"], _s["title"],
                           _s.get("ref", "")))
        cards = _s.get("cards", [])
        # Xếp card 2 cột
        i = 0
        while i < len(cards):
            c1 = cards[i]
            c2 = cards[i + 1] if i + 1 < len(cards) else \
                {"title": "", "ref": "", "lines": [], "result": ""}
            S.extend(_two(P, st, c1, c2))
            i += 2

        # Mục 3 (P-M-M): nhúng 2 biểu đồ ngang nhau, giữ tỉ lệ
        # Mục 2: nhúng sơ đồ mặt cắt
        if _s["num"] == 2 and sec is not None:
            try:
                from .pdf_export import section_image as _si
                import io as _io
                _sec_png = _si(sec, width_in=2.8, show_stats=False)
                if _sec_png:
                    from reportlab.platypus import Image as _Img
                    _simg = _Img(_io.BytesIO(_sec_png), width=65*mm, height=65*mm)
                    _simg.hAlign = "CENTER"
                    S.append(_simg)
                    S.append(Spacer(1, 4*mm))
            except Exception:
                pass

        if _s["num"] == 6 and chart_pngs:
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
        if _s["num"] in (6, 7):
            if _s["num"] == 6:
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
