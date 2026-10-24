"""PDF thuyết minh chi tiết vách TCVN (cards) — CÙNG nội dung và số
với tab Chi tiết app, vì cùng đọc từ
rc_column.wall_detail.build_wall_detail_sections(full) (dict kết
quả đã tính 1 lần). Chỉ khác vật chứa: ReportLab thay cho Tk.

Bố cục bám pdf_report_cards.py của cột: tiêu đề, header mục có chấm
màu + căn cứ điều khoản góc phải (qua _sec_head), cards 2 cột (_two),
card full-width, box D/C, ảnh mặt cắt + N–Mα + M2–M3.
"""

import io
import math
from xml.sax.saxutils import escape as _esc

from .wall_detail import build_wall_detail_sections, wall_detail_header
from .wall_pdf_figs import wall_nm_alpha_png, wall_section_png
from .wall_m2m3 import wall_m2m3_figure


def _img_from_bytes(png_bytes, w_mm, max_h=None):
    """Image giữ tỉ lệ gốc; nếu ảnh dọc (vd mặt cắt xoay 90°) cao
    vượt max_h_mm thì thu nhỏ theo chiều cao để không vượt trang."""
    from reportlab.platypus import Image
    buf = io.BytesIO(png_bytes)
    try:
        from PIL import Image as _PIL
        pil = _PIL.open(buf)
        pw, ph = pil.size
        buf.seek(0)
        h_mm = w_mm * ph / pw if pw > 0 else w_mm
    except Exception:
        h_mm = w_mm
    if max_h is not None and h_mm > max_h:
        w_mm = w_mm * max_h / h_mm
        h_mm = max_h
    return Image(buf, width=w_mm, height=h_mm)


def _full_card(P, st, card):
    """Card chiếm trọn chiều ngang (ghi chú / kết luận)."""
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    rows = []
    if card.get("title"):
        rows.append([P(f"<b>{_esc(card['title'])}</b>",
                       st["card_title"])])
    if card.get("ref"):
        rows.append([P(_esc(card["ref"]), st["card_ref"])])
    for ln in card.get("lines", []):
        rows.append([P(_esc(ln), st["formula"])])
    if card.get("result"):
        rows.append([P(f"<b>{_esc(card['result'])}</b>",
                       st["result"])])
    if not rows:
        rows.append([P("", st["formula"])])
    t = Table(rows)
    sty = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    if len(rows) > 1:
        sty += [
            ("BACKGROUND", (0, 1), (-1, -1), HexColor("#F9FAFB")),
            ("LINEBEFORE", (0, 1), (0, -1), 2, HexColor("#D1D5DB")),
            ("LEFTPADDING", (0, 1), (-1, -1), 10),
        ]
    t.setStyle(TableStyle(sty))
    return t


def export_wall_pdf_cards(full, filepath: str, member_name: str = None,
                          show_compression: bool = True):
    """Xuất PDF thuyết minh chi tiết vách từ dict kết quả đã lưu."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Image, Table, TableStyle)
    from reportlab.lib.colors import HexColor
    from .pdf_report_cards import _get_styles, _mk, _sec_head, _two

    st = _get_styles()
    P = Paragraph
    hdr = wall_detail_header(full)
    secs = build_wall_detail_sections(full)
    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=10 * mm, rightMargin=10 * mm,
                            topMargin=10 * mm, bottomMargin=10 * mm)
    S = []
    S.append(P("THUYẾT MINH TÍNH TOÁN VÁCH BTCT", st["title"]))
    S.append(P("(Tiêu chuẩn TCVN 5574:2018 — vách chữ nhật đặc, GĐ1)",
               st["sub"]))
    if member_name:
        S.append(P(f"Cấu kiện: {_esc(str(member_name).upper())}",
                   st["sec_title"]))
    S.append(P(_esc(hdr["loads"]), st["note"]))
    # Ảnh mặt cắt (có vùng nén tại điểm B khi show_compression).
    try:
        _sec_png = wall_section_png(full, show_compression=show_compression)
        _im = _img_from_bytes(_sec_png, 170 * mm, 180 * mm)
        _t = Table([[_im]], colWidths=[190 * mm], hAlign="CENTER")
        _t.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        S.append(_t)
        S.append(P("Mặt cắt tiết diện vách (có vùng nén tại điểm B)"
                   if show_compression else "Mặt cắt tiết diện vách",
                   st["cap"]))
    except Exception as ex:
        S.append(P(f"(Không vẽ được mặt cắt: {ex})", st["note"]))

    for sec in secs:
        S.append(_sec_head(P, st, sec["num"], _esc(sec["title"]),
                           _esc(sec.get("ref", ""))))
        cards = sec.get("cards", [])
        i = 0
        while i < len(cards):
            c = cards[i]
            if c.get("full"):
                S.append(_full_card(P, st, c))
                S.append(Spacer(1, 4 * mm))
                i += 1
                continue
            c1 = _mk(_esc(c.get("title", "")), _esc(c.get("ref", "")),
                     [_esc(ln) for ln in c.get("lines", [])],
                     _esc(c.get("result", "")) if c.get("result") else "")
            nxt = cards[i + 1] if i + 1 < len(cards) else None
            if nxt is not None and not nxt.get("full"):
                c2 = _mk(_esc(nxt.get("title", "")),
                         _esc(nxt.get("ref", "")),
                         [_esc(ln) for ln in nxt.get("lines", [])],
                         _esc(nxt.get("result", ""))
                         if nxt.get("result") else "")
                S.extend(_two(P, st, c1, c2))
                i += 2
            else:
                from .pdf_report_cards import _EMPTY
                S.extend(_two(P, st, c1, _EMPTY))
                i += 1
        # Box D/C + biểu đồ sau mục 6 (như tab Chi tiết).
        if sec["num"] == 6:
            _ok = bool(full["ok"])
            _dc = float(full["dc"])
            _fs = float(full["fs"])
            S.append(P(
                f"TỶ SỐ SỬ DỤNG (D/C) N–M = {_dc:.3f} (FS = {_fs:.2f}) — "
                f"{'ĐẠT' if _ok else 'KHÔNG ĐẠT'} (chỉ N–M; cắt kết "
                f"luận riêng)",
                st["dc_ok"] if _ok else st["dc_ng"]))
            try:
                _nm_png = wall_nm_alpha_png(full)
                _im = _img_from_bytes(_nm_png, 120 * mm, 150 * mm)
                _t = Table([[_im]], colWidths=[190 * mm],
                           hAlign="CENTER")
                _t.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]))
                S.append(_t)
                S.append(P(f"Biểu đồ tương tác N–Mα "
                           f"(α = {float(full['alpha_deg']):.1f}°)",
                           st["cap"]))
            except Exception as ex:
                S.append(P(f"(Không vẽ được biểu đồ N–Mα: {ex})",
                           st["note"]))
        # Biểu đồ M2–M3 sau mục 7.
        if sec["num"] == 7 and full.get("m2m3") is not None:
            try:
                _m_png = wall_m2m3_figure(full["m2m3"])
                _im = _img_from_bytes(_m_png, 120 * mm, 150 * mm)
                _t = Table([[_im]], colWidths=[190 * mm],
                           hAlign="CENTER")
                _t.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]))
                S.append(_t)
                S.append(P(f"Mặt cắt M2–M3 (tại N = "
                           f"{float(full['m2m3']['N_level']):,.0f} kN)",
                           st["cap"]))
                # Diễn giải M2–M3 NGAY DƯỚI hình (cùng thẻ trong
                # builder mục 7): chỉ diễn giải lại kết luận N–M,
                # không phải kết luận độc lập.
                _ok7 = bool(full["ok"])
                S.append(P(
                    f"Diễn giải M2–M3: cùng kết luận N–M — "
                    f"D/C = {float(full['dc']):.3f} — "
                    f"{'ĐẠT' if _ok7 else 'KHÔNG ĐẠT'} "
                    f"(không phải kết luận độc lập; lát cắt tại "
                    f"N = BN của cùng khả năng N–M)",
                    st["note"]))
            except Exception as ex:
                S.append(P(f"(Không vẽ được biểu đồ M2–M3: {ex})",
                           st["note"]))

    S.append(P("Phạm vi: không có kết luận chung — mỗi mục kết luận "
               "riêng tại mục của nó (mục 3 độ mảnh, mục 6 N–M, "
               "mục 7 diễn giải lại N–M, mục 8 cắt trong và ngoài "
               "mặt phẳng); vùng biên, trượt mạch ngừng và cấu tạo: "
               "CHƯA KIỂM.",
               st["note"]))
    doc.build(S)
    return filepath
