"""Xuất PDF thuyết minh kiểm tra cột theo ACI 318-19.

Render các section từ aci_report.generate_aci_report_sections thành
PDF A4 dọc với card style giống hệt bản TCVN (pdf_report_cards.py).

Không phụ thuộc GUI/matplotlib trực tiếp.
"""

import io

from .aci_report_v2 import generate_aci_report_sections_v2
# Dùng chung hàm render của TCVN để đảm bảo layout giống hệt
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


def _find_aci_font():
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


def _find_aci_font_bold():
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


def export_aci_pdf_cards(inp, aci_res, mm_res, shear_res, conc, steel,
                         tied, filepath, chart_pngs=None, case_info=None,
                         sec=None):
    """Xuất PDF thuyết minh ACI 318-19 kiểu card giống hệt app.

    inp: ColumnInput. aci_res/mm_res/shear_res: dict kết quả ACI.
    conc: ACIConcrete, steel: ACISteel. tied: True = đai rời.
    chart_pngs: tuple 2 bytes PNG (N-Mα, M2-M3) — nhúng vào mục 4.
    case_info: dict {story, column, case, station, N, M2, M3} (optional).
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, KeepTogether)
    from reportlab.lib.colors import HexColor

    st = _get_styles()
    P = Paragraph

    sections = generate_aci_report_sections_v2(inp, aci_res, mm_res, shear_res,
                                               conc, steel, sec, tied)

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm)
    S = []
    S.append(P("THUYẾT MINH TÍNH TOÁN CỘT BTCT — ACI 318-19", st["title"]))
    S.append(P("Tiêu chuẩn: ACI 318-19 — Kiểm tra P-M-M, độ mảnh và cắt",
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
            S.extend(_two(P, st, c1, c2))
            i += 2

        # Mục 2: nhúng sơ đồ mặt cắt
        if sec["num"] == 2 and sec is not None:
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

        # Mục 6 (P-M-M): nhúng 2 biểu đồ ngang nhau, giữ tỉ lệ
        if sec["num"] == 6 and chart_pngs:
            try:
                img1 = _img_keep_aspect(chart_pngs[0])
                img2 = _img_keep_aspect(chart_pngs[1])
                ct = Table([
                    [[P("Biểu đồ tương tác N-Mα (ACI)", st["cap"]), img1],
                     [P("Biểu đồ tương tác M2-M3 (ACI)", st["cap"]), img2]]
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

        # Banner kết luận cho mục 4 (P-M-M) và mục 5 (cắt)
        if sec["num"] in (4, 5):
            if sec["num"] == 4:
                ok = bool(aci_res.get("ok", False))
                dc = aci_res.get("dc", 0.0) or 0.0
                fs = aci_res.get("fs", 0.0) or 0.0
                dc_txt = f"{dc:.3f}" if dc != float("inf") else "∞"
                fs_txt = f"{fs:.2f}" if fs != float("inf") else "∞"
                txt = (f"TỶ SỐ SỬ DỤNG (D/C) = {dc_txt} (FS = {fs_txt}) — "
                       f"{'✓ ĐẠT — D/C ≤ 1.000' if ok else '✗ KHÔNG ĐẠT'}")
            else:
                _shr = shear_res or {}
                ok = bool(_shr.get("ok", False))
                Vu = abs(getattr(inp, "Q2", 0.0) or 0.0)
                phi_vn = _shr.get("phi_Vn_kN", 0.0) or 0.0
                txt = (f"Vu = {_f(Vu, 1)} kN "
                       f"{'≤' if Vu <= phi_vn else '>'} "
                       f"φVn = {_f(phi_vn, 1)} kN — "
                       f"{'✓ ĐẠT' if ok else '✗ KHÔNG ĐẠT'}")
            S.append(P(txt, st["dc_ok"] if ok else st["dc_ng"]))

    doc.build(S)
    return filepath
