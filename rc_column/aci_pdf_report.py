"""Xuất PDF thuyết minh kiểm tra cột theo ACI 318-19.

Render các section từ aci_report.generate_aci_report_sections thành
PDF A4 dọc với card style giống hệt bản TCVN (pdf_report_cards.py).

Không phụ thuộc GUI/matplotlib trực tiếp.
"""

import io

from .aci_report_v2 import generate_aci_report_sections_v2
# Dùng chung hàm render của TCVN để đảm bảo layout giống hệt
from .pdf_report_cards import (_get_styles, _two, _sec_head, _full_case, _mk)



def _member_name(inp):
    """Lấy tên cấu kiện IN HOA từ _filename."""
    import os
    fn = getattr(inp, "_filename", "") or ""
    if fn:
        return os.path.splitext(os.path.basename(fn))[0].upper()
    return ""

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


def _img_keep_aspect(png_bytes, w_mm=80):
    """Tạo Image giữ tỉ lệ gốc bằng PIL."""
    from reportlab.platypus import Image
    from reportlab.lib.units import mm
    from PIL import Image as _PIL
    import io
    _pil = _PIL.open(io.BytesIO(png_bytes))
    _pw, _ph = _pil.size
    _h = w_mm * _ph / _pw if _pw > 0 else w_mm
    return Image(io.BytesIO(png_bytes), width=w_mm*mm, height=_h*mm)


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
    S.append(P("THUYẾT MINH TÍNH TOÁN CỘT BTCT", st["title"]))
    S.append(P("(Tiêu chuẩn ACI 318-19)", st["sub"]))
    _mn = _member_name(inp)
    if _mn:
        S.append(P(f"Cấu kiện: {_mn}", st["sec_title"]))

    if case_info:
        S.append(P(f"Tổ hợp tính toán: {_full_case(case_info)} — "
                   f"N = {_f(case_info.get('N', 0), 1)} kN, "
                   f"M2 = {_f(case_info.get('M2', 0), 1)} kN·m, "
                   f"M3 = {_f(case_info.get('M3', 0), 1)} kN·m",
                   st["note"]))

    for _s in sections:
        # Mục 3, 6: luôn sang trang mới
        if _s["num"] in (3, 6):
            from reportlab.platypus import PageBreak as _PB36
            S.append(_PB36())
        S.append(_sec_head(P, st, _s["num"], _s["title"],
                           _s.get("ref", "")))
        # Mục 2: sơ đồ mặt cắt TRƯỚC (như TCVN)
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
        cards = _s.get("cards", [])
        # Xử lý card [FULL]: render full-width, bỏ marker
        _filtered = []
        for _cd in cards:
            if _cd.get("full"):
                _cd = dict(_cd)
                # Style kết luận: nền xanh/đỏ
                _is_concl = _cd.get("conclusion", False)
                _concl_bg = "#D1FAE5" if "KHÔNG ĐẠT" not in _cd.get("result", "") else "#FEE2E2"
                from reportlab.platypus import Table as _Tf, TableStyle as _TSf
                from reportlab.lib.colors import HexColor as _HCf
                _rows = []
                if _cd["title"]:
                    _rows.append([P(f'<b>{_cd["title"]}</b>', st["card_title"])])
                if _cd["ref"]:
                    _rows.append([P(_cd["ref"], st["card_ref"])])
                for _ln in _cd["lines"]:
                    _rows.append([P(_ln, st["formula"])])
                if _cd.get("result"):
                    _rows.append([P(_cd["result"], st["result"])])
                _tf = _Tf(_rows, colWidths=[190*mm])
                _tf.hAlign = "LEFT"
                _tf.setStyle(_TSf([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("BACKGROUND", (0, 0), (-1, -1), _HCf(_concl_bg if _is_concl else "#F9FAFB")),
                    ("LINEBEFORE", (0, 1), (0, -1), 2, _HCf("#D1D5DB")),
                    ("LEFTPADDING", (0, 1), (-1, -1), 10),
                ]))
                S.append(_tf)
                S.append(Spacer(1, 4*mm))
            else:
                _filtered.append(_cd)
        cards = _filtered
        # Mục 7: card cấu tạo full-width (span 2 cột), V2/V3 ngang hàng
        if _s["num"] == 7 and len(cards) >= 3 and "Cấu tạo" in cards[0].get("title", ""):
            _cfg = cards[0]
            # Render full-width bằng table 1 cột
            from reportlab.platypus import Table as _T, TableStyle as _TS
            from reportlab.lib.colors import HexColor as _HC
            _rows = []
            if _cfg["title"]:
                _rows.append([P(f'<b>{_cfg["title"]}</b>', st["card_title"])])
            if _cfg["ref"]:
                _rows.append([P(_cfg["ref"], st["card_ref"])])
            for _ln in _cfg["lines"]:
                _rows.append([P(_ln, st["formula"])])
            if _cfg.get("result"):
                _rows.append([P(_cfg["result"], st["result"])])
            _t1 = _T(_rows, colWidths=[190*mm])
            _t1.hAlign = "LEFT"
            _t1.setStyle(_TS([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("BACKGROUND", (0, 1), (-1, -1), _HC("#F9FAFB")),
                ("LINEBEFORE", (0, 1), (0, -1), 2, _HC("#D1D5DB")),
                ("LEFTPADDING", (0, 1), (-1, -1), 10),
            ]))
            S.append(_t1)
            S.append(Spacer(1, 4*mm))
            cards = cards[1:]
        # Xếp card 2 cột
        i = 0
        while i < len(cards):
            c1 = cards[i]
            c2 = cards[i + 1] if i + 1 < len(cards) else \
                {"title": "", "ref": "", "lines": [], "result": ""}
            S.extend(_two(P, st, c1, c2))
            i += 2

        # Mục 6 (P-M-M): tự tạo biểu đồ vuông 5x5 cho PDF (không dùng figure app)
        if _s["num"] == 6:
            try:
                from .aci_chart_draw import (aci_interaction_image,
                                             aci_m2m3_image)
                _N = float(getattr(inp, "N", 0) or 0)
                _M2 = float(getattr(inp, "Mx", 0) or getattr(inp, "M2", 0) or 0)
                _M3 = float(getattr(inp, "My", 0) or getattr(inp, "M3", 0) or 0)
                _pngs = (aci_interaction_image(sec, conc, steel, aci_res,
                                               _N, _M2, _M3, tied=tied),
                         aci_m2m3_image(sec, conc, steel, aci_res,
                                        _N, _M2, _M3, tied=tied))
            except Exception:
                _pngs = chart_pngs
            try:
                img1 = _img_keep_aspect(_pngs[0])
                img2 = _img_keep_aspect(_pngs[1])
                ct = Table([
                    [[P("Biểu đồ tương tác N-Mα", st["cap"]), img1],
                     [P("Biểu đồ tương tác M2-M3", st["cap"]), img2]]
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
            # Box kết luận D/C xanh dưới biểu đồ
            _dc = None
            for _cd in _s.get("cards", []):
                if _cd.get("dc_conclusion"):
                    _dc = _cd
                    break
            if _dc:
                from reportlab.lib.colors import HexColor as _HCf
                _ok = _dc.get("ok", True)
                _bg = "#D1FAE5" if _ok else "#FEE2E2"
                _fg = "#065F46" if _ok else "#991B1B"
                _t = Table([
                    [P(f"TỶ SỐ SỬ DỤNG (D/C) = {_dc.get('dc', 0):.3f}  (FS = {_dc.get('fs', 0):.2f})", st["result"]),
                     ],
                    [P("✓ ĐẠT — D/C ≤ 1.000" if _ok else "✗ KHÔNG ĐẠT — D/C > 1.000", st["result"])],
                ])
                _t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), _HCf(_bg)),
                    ("TEXTCOLOR", (0, 0), (-1, -1), _HCf(_fg)),
                    ("BOX", (0, 0), (-1, -1), 0.5, _HCf("#E5E7EB")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]))
                S.append(_t)
                S.append(Spacer(1, 4 * mm))


    doc.build(S)
    return filepath
