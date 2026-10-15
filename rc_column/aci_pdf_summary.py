"""Xuất PDF tóm tắt kiểm tra cột theo ACI 318-19 (khổ A4, 1 trang).

Bố cục COPY export_summary_pdf của pdf_export.py (TCVN):
- Tiêu đề + tên cấu kiện
- Hàng trên: [hình mặt cắt + box vật liệu | bảng thông số] (thuật toán 3 bước)
- 2 biểu đồ ACI đặt ngang nhau, giữ tỉ lệ bằng PIL
- Chi tiết điểm A/B, kiểm tra cắt

Không phụ thuộc GUI.
"""

import io as _io
import math as _m
import os as _os

from .pdf_export import _mpl_font, _find_font, _find_font_bold, section_image
from .aci_chart_draw import draw_aci_nm_alpha_ax, draw_aci_m2m3_ax


def _sys_font(bold=False):
    """Fallback: font DejaVu Sans của hệ thống (khi matplotlib thiếu font)."""
    import os
    cands = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def _f(x, nd=1, unit=""):
    """Format số an toàn với None/inf/nan -> '—'."""
    try:
        if x is None or not _m.isfinite(float(x)):
            return "—"
    except (TypeError, ValueError):
        return "—"
    return f"{float(x):.{nd}f}{unit}"


def _f_dc(dc):
    try:
        if dc is None or not _m.isfinite(float(dc)):
            return "∞"
    except (TypeError, ValueError):
        return "∞"
    return f"{float(dc):.3f}"


def _aci_charts_png(sec, conc, steel, aci_res, inp, tied):
    """Tự vẽ 2 biểu đồ ACI -> (png_nm_alpha, png_m2m3) bytes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = []
    for draw_fn in (draw_aci_nm_alpha_ax, draw_aci_m2m3_ax):
        fig = plt.figure(figsize=(5.2, 3.9))
        ax = fig.add_subplot(111)
        draw_fn(ax, sec, conc, steel, aci_res, inp.N, inp.Mx, inp.My,
                tied=tied)
        fig.tight_layout()
        fig.subplots_adjust(bottom=0.30)
        buf = _io.BytesIO()
        fig.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        out.append(buf.getvalue())
    return tuple(out)


def _img_keep_ratio(png_bytes, w_mm):
    """reportlab Image giữ tỉ lệ gốc (đọc kích thước PNG bằng PIL)."""
    from reportlab.lib.units import mm
    from reportlab.platypus import Image
    from PIL import Image as _PIL
    pil = _PIL.open(_io.BytesIO(png_bytes))
    pw, ph = pil.size
    h_mm = w_mm * ph / pw if pw > 0 else w_mm * 0.75
    return Image(_io.BytesIO(png_bytes), width=w_mm * mm, height=h_mm * mm)


def _slenderness_aci(sec, conc, inp):
    """Tính δns theo ACI 6.6.4.5.2 cho phương 2 (k=1.0)."""
    from .aci_checker import moment_magnification
    from .stability import effective_length
    try:
        L0_2 = effective_length(inp.Lx, inp.top_x, inp.bottom_x,
                                inp.psi_x) * 1000.0  # mm
        Ig = sec.cx * sec.cy ** 3 / 12.0
        lt = getattr(inp, "long_term", None)
        if lt is not None and getattr(lt, "has_data", False) and inp.N:
            beta_dns = max(0.0, min(1.0, lt.N_lt / inp.N))
        else:
            beta_dns = 0.6
        mm = moment_magnification(Pu_kN=inp.N, M1_kNm=inp.Mx,
                                  M2_kNm=inp.Mx, lu_mm=L0_2, k=1.0,
                                  Ec_MPa=conc.Ec, Ig_mm4=Ig,
                                  beta_dns=beta_dns)
        return mm.get("delta_ns"), mm.get("Pc_kN"), beta_dns
    except Exception:
        return None, None, None


def _shear_aci(sec, inp, steel, conc):
    """Kiểm tra cắt ACI 22.5.5.1 cho 2 phương. Trả về dict phương -> dict."""
    from .aci_checker import aci_shear_check
    cols = {}
    try:
        Av = inp.sw_legs * _m.pi * inp.sw_dia ** 2 / 4.0
        fyt = steel.fy
        cover = getattr(inp, "cover", 30.0)
        for Q, lbl, b_w, h_dim in ((inp.Q2, "2", inp.cy, inp.cx),
                                   (inp.Q3, "3", inp.cx, inp.cy)):
            d = max(h_dim - cover - inp.sw_dia - 12.0, 1.0)
            Acv = b_w * d
            Ag = sec.cx * sec.cy
            sh = aci_shear_check(Acv_mm2=Acv, Ag_mm2=Ag, fc_MPa=conc.fc,
                                 Nu_kN=inp.N, Vu_kN=abs(Q),
                                 Av_mm2=Av, fyt_MPa=fyt,
                                 s_mm=inp.sw_spacing, d_mm=d)
            cols[lbl] = {"Q": Q, "b": b_w, "d": d, "sh": sh}
    except Exception:
        pass
    return cols


def export_aci_summary_pdf(sec, inp, aci_res, conc, steel, tied, filepath,
                           case_info=None, sec_img_path=None, chart_pngs=None):
    """Xuất PDF tóm tắt kiểm tra cột theo ACI 318-19 (A4 dọc, 1 trang).

    sec: Section đã bố trí thép. inp: ColumnInput. aci_res: dict từ
    check_column_aci (dc, fs, phi, ok, Bx, By, BN, eps_t, N_cap...).
    conc: ACIConcrete, steel: ACISteel. tied: True = đai thường.
    chart_pngs: tuple (png_nm_alpha, png_m2m3) bytes (tùy chọn, nếu không
    có sẽ tự vẽ bằng aci_chart_draw).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Image, Table, TableStyle)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    # --- Font (thử font matplotlib trước, rồi font hệ thống) ---
    FN, FNB = "Helvetica", "Helvetica-Bold"
    try:
        _fp = _find_font()
    except Exception:
        _fp = _sys_font(False)
    if _fp:
        try:
            pdfmetrics.registerFont(TTFont("DejaVu", _fp))
            FN = "DejaVu"
        except Exception:
            pass
    try:
        _fb = _find_font_bold()
    except Exception:
        _fb = _sys_font(True)
    if _fb:
        try:
            pdfmetrics.registerFont(TTFont("DejaVuB", _fb))
            FNB = "DejaVuB"
        except Exception:
            pass

    st_title = ParagraphStyle("t", fontName=FNB, fontSize=13,
                              alignment=TA_CENTER, spaceAfter=4)
    st_sub2 = ParagraphStyle("sub2", fontName=FN, fontSize=9,
                             alignment=TA_CENTER, spaceAfter=4,
                             textColor=HexColor("#6B7280"))
    st_h = ParagraphStyle("h", fontName=FNB, fontSize=10, spaceBefore=6,
                          spaceAfter=3)
    st_b = ParagraphStyle("b", fontName=FN, fontSize=8.5, spaceAfter=1.5,
                          leading=11)
    st_cell = ParagraphStyle("c", fontName=FN, fontSize=7, leading=9)
    st_cell_b = ParagraphStyle("cb", fontName=FNB, fontSize=7, leading=9)
    st_box_t = ParagraphStyle("bt", fontName=FN, fontSize=7,
                              textColor=HexColor("#111827"),
                              alignment=TA_CENTER)
    st_box_v = ParagraphStyle("bv", fontName=FN, fontSize=7,
                              alignment=TA_CENTER, leading=9,
                              textColor=HexColor("#111827"))

    ok = bool(aci_res.get("ok"))
    ok_txt = "ĐẠT" if ok else "KHÔNG ĐẠT"
    dc_bg = HexColor("#D1FAE5") if ok else HexColor("#FEE2E2")
    story = []

    # ===== Tiêu đề =====
    story.append(Paragraph("KIỂM TRA CỘT BÊ TÔNG CỐT THÉP", st_title))
    story.append(Paragraph("(Theo ACI 318-19)", st_sub2))
    _ck_name = ""
    try:
        _fn = getattr(inp, "_filename", "") or ""
        if _fn:
            _ck_name = _os.path.splitext(_os.path.basename(_fn))[0].upper()
    except Exception:
        pass
    story.append(Spacer(1, 1))

    # ===== Số liệu chung =====
    from collections import Counter
    n = len(sec.rebars)
    cnt = Counter(r.dia for r in sec.rebars)
    parts = [f"{cnt[d]}d{d:.0f}" for d in sorted(cnt, reverse=True)]
    tie_txt = "Tied (đai thường)" if tied else "Spiral (đai xoắn)"
    sw_txt = (f"{getattr(inp, 'sw_legs', 2):.0f}"
              f"φ{getattr(inp, 'sw_dia', 8):.0f} "
              f"a{getattr(inp, 'sw_spacing', 200):.0f}")
    box_data = [
        [Paragraph("Bê tông", st_box_t),
         Paragraph("Thép dọc", st_box_t),
         Paragraph("Loại đai", st_box_t)],
        [Paragraph(f"f'c = {_f(conc.fc, 0)} MPa", st_box_v),
         Paragraph(f"fy = {_f(steel.fy, 0)} MPa", st_box_v),
         Paragraph(tie_txt, st_box_v)],
        [Paragraph("Số thanh", st_box_t),
         Paragraph("Tổng As", st_box_t),
         Paragraph("Hàm lượng μ", st_box_t)],
        [Paragraph(" + ".join(parts), st_box_v),
         Paragraph(f"{sec.steel_area:.0f} mm²", st_box_v),
         Paragraph(f"{sec.reinforcement_ratio * 100:.2f}%", st_box_v)],
        [Paragraph("Thép đai bố trí", st_box_t),
         Paragraph("β1", st_box_t),
         Paragraph("Ec", st_box_t)],
        [Paragraph(sw_txt, st_box_v),
         Paragraph(f"{_f(conc.beta1, 3)}", st_box_v),
         Paragraph(f"{_f(conc.Ec, 0)} MPa", st_box_v)],
    ]
    t_box = Table(box_data, colWidths=[30 * mm, 30 * mm, 30 * mm])
    t_box.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#E5E7EB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    # ===== Bảng thông số =====
    alpha_deg = (_m.degrees(_m.atan2(inp.My, inp.Mx))
                 if abs(inp.Mx) + abs(inp.My) > 1e-9 else 0.0)
    Ma = _m.hypot(inp.Mx, inp.My)
    d_ns, Pc_kN, beta_dns = _slenderness_aci(sec, conc, inp)
    prows = [
        ("N", "Lực dọc tính toán", f"{inp.N:+.1f} kN"),
        ("M2", "Mô men phương 2", f"{inp.Mx:.1f} kN·m"),
        ("M3", "Mô men phương 3", f"{inp.My:.1f} kN·m"),
        ("α", "Góc tác dụng mô men", f"{alpha_deg:.1f} °"),
        ("Mα", "Mô men tổng theo phương kiểm tra", f"{Ma:.1f} kN·m"),
        ("φ", "Hệ số sức kháng tại điểm B (ACI 21.2.2)",
         f"{_f(aci_res.get('phi'), 3)}"),
        ("εt", "Biến dạng kéo thép ngoài cùng tại B",
         f"{_f(aci_res.get('eps_t'), 5)}"),
        ("δns", "Hệ số phóng đại mô men (ACI 6.6.4.5.2)",
         _f(d_ns, 3) if d_ns else "—"),
        ("Pc", "Tải trọng tới hạn Euler",
         f"{_f(Pc_kN, 1)} kN" if Pc_kN else "—"),
        ("φPn,max", "Nén thiết kế lớn nhất (ACI 22.4.2.2)",
         f"{_f(aci_res.get('N_cap'), 1)} kN"),
    ]
    pdata = [[Paragraph("<b>Ký hiệu</b>", st_cell_b),
              Paragraph("<b>Thông số</b>", st_cell_b),
              Paragraph("<b>Giá trị</b>", st_cell_b)]]
    for a, b, c in prows:
        pdata.append([Paragraph(a, st_cell), Paragraph(b, st_cell),
                      Paragraph(c, st_cell)])
    fs_txt = _f(aci_res.get("fs"), 2)
    pdata.append([Paragraph("<b>D/C</b>", st_cell_b),
                  Paragraph("Tỷ số sử dụng khả năng chịu lực", st_cell),
                  Paragraph(f"<b>{_f_dc(aci_res.get('dc'))} "
                            f"(FS = {fs_txt}) {ok_txt}</b>", st_cell_b)])
    t_param = Table(pdata, colWidths=[11 * mm, 48 * mm, 24 * mm])
    t_param.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#D1D5DB")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F3F4F6")),
        ("BACKGROUND", (0, -1), (-1, -1), dc_bg),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2),
         [HexColor("#FFFFFF"), HexColor("#F9FAFB")]),
    ]))

    _ck_style = ParagraphStyle(
        "ck", fontName=FNB, fontSize=11, alignment=TA_LEFT,
        textColor=HexColor("#111827"), spaceBefore=2, spaceAfter=2)
    _ck_para = Paragraph(f"CẤU KIỆN: {_ck_name}", _ck_style) \
        if _ck_name else Spacer(1, 1)

    # BƯỚC 1: Đo chiều cao bảng phải
    _right_tbl = Table(
        [[Paragraph("BẢNG THÔNG SỐ TÍNH TOÁN", st_h)],
         [t_param]],
        colWidths=[83 * mm])
    _right_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    _, _rh = _right_tbl.wrap(83 * mm, 1000)

    # BƯỚC 2: Đo boxes, tính vị trí đáy
    _, _bh = t_box.wrap(90 * mm, 1000)
    _title_tbl = Table(
        [[Paragraph("SƠ ĐỒ MẶT CẮT TIẾT DIỆN CỘT", st_h)],
         [_ck_para]],
        colWidths=[83 * mm])
    _, _th = _title_tbl.wrap(83 * mm, 1000)

    # BƯỚC 3: Khoảng trống còn lại -> scale hình vào (giữ tỉ lệ)
    _avail_h = _rh - _th - _bh - 4 * mm
    _avail_h = max(_avail_h, 20 * mm)
    if sec_img_path:
        from PIL import Image as _PILImage
        _pil = _PILImage.open(sec_img_path)
        _w, _h = _pil.size
        _ratio = _w / _h
        _max_w = 81 * mm
        if _max_w / _avail_h > _ratio:
            _hh = _avail_h
            _ww = _hh * _ratio
        else:
            _ww = _max_w
            _hh = _ww / _ratio
        img_sec = Image(sec_img_path, width=_ww, height=_hh)
    else:
        try:
            png = section_image(sec, small=True)
            img_sec = _img_keep_ratio(png, 81)
        except Exception:
            img_sec = Spacer(1, 30 * mm)

    _left_tbl = Table(
        [[Paragraph("SƠ ĐỒ MẶT CẮT TIẾT DIỆN CỘT", st_h)],
         [_ck_para],
         [img_sec],
         [t_box]],
        colWidths=[83 * mm])
    _left_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("VALIGN", (0, 3), (0, 3), "BOTTOM"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    _outer = Table([[_left_tbl, _right_tbl]],
                   colWidths=[87 * mm, 87 * mm])
    _outer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.6, HexColor("#D1D5DB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(_outer)
    story.append(Spacer(1, 1))

    # ===== Biểu đồ =====
    story.append(Paragraph("BIỂU ĐỒ TƯƠNG TÁC (ACI 318-19)", st_h))
    if chart_pngs and len(chart_pngs) == 2:
        png_nm, png_m2m3 = chart_pngs
    else:
        png_nm, png_m2m3 = _aci_charts_png(sec, conc, steel, aci_res,
                                           inp, tied)
    img_nm = _img_keep_ratio(png_nm, 88)
    img_mm = _img_keep_ratio(png_m2m3, 88)
    story.append(Table([[img_nm, img_mm]], colWidths=[88 * mm, 88 * mm],
                       style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")])))
    story.append(Spacer(1, 1))

    # ===== Chi tiết điểm A/B =====
    story.append(Paragraph("CHI TIẾT ĐIỂM TẢI & GIỚI HẠN", st_h))
    story.append(Paragraph(
        f"• Đường bao kiểm tra: N-Mα (α = {alpha_deg:.1f}°), "
        f"D/C = OA/OB = {_f_dc(aci_res.get('dc'))} → <b>{ok_txt}</b>", st_b))
    _combo = ""
    if case_info:
        _parts = []
        if case_info.get("story"):
            _parts.append(str(case_info.get("story")))
        if case_info.get("column"):
            _parts.append(str(case_info.get("column")))
        if case_info.get("case"):
            _st = case_info.get("station", "")
            _st_txt = f"@{_st:.2f}" if isinstance(_st, (int, float)) else ""
            _parts.append(f"{case_info.get('case')}{_st_txt}")
        if _parts:
            _combo = f" [{', '.join(_parts)}]"
    _p_ind = ParagraphStyle("a2", parent=st_b, leftIndent=12)
    Mb = _m.hypot(aci_res.get("Bx") or 0.0, aci_res.get("By") or 0.0)
    story.append(Paragraph(f"• A (điểm tải){_combo}:", st_b))
    story.append(Paragraph(
        f"N = {inp.N:+.1f} kN, Mα = {Ma:.1f} kN·m "
        f"(M2 = {inp.Mx:.1f}, M3 = {inp.My:.1f})", _p_ind))
    story.append(Paragraph(
        f"• B (điểm giới hạn): Nu = {_f(aci_res.get('BN'), 1)} kN, "
        f"Mα,u = {Mb:.1f} kN·m "
        f"(M2u = {_f(aci_res.get('Bx'), 1)}, "
        f"M3u = {_f(aci_res.get('By'), 1)})", st_b))
    story.append(Spacer(1, 1))

    # ===== Kiểm tra cắt =====
    story.append(Paragraph("KIỂM TRA CẮT (ACI 22.5)", st_h))
    cols = _shear_aci(sec, inp, steel, conc)
    if cols:
        def _pc(t, bold=False):
            st = st_cell_b if bold else st_cell
            return Paragraph(str(t), st)
        tdata = [[_pc("Thông số", True), _pc("Phương V2", True),
                  _pc("Phương V3", True)]]
        _rows = [
            ("Thép đai bố trí", sw_txt, sw_txt),
            ("Vu (kN)", f"{abs(cols['2']['Q']):.1f}",
             f"{abs(cols['3']['Q']):.1f}"),
            ("Vc (kN)", f"{cols['2']['sh']['Vc_kN']:.1f}",
             f"{cols['3']['sh']['Vc_kN']:.1f}"),
            ("Vs (kN)", f"{cols['2']['sh']['Vs_kN']:.1f}",
             f"{cols['3']['sh']['Vs_kN']:.1f}"),
            ("φVn (kN)", f"{cols['2']['sh']['phi_Vn_kN']:.1f}",
             f"{cols['3']['sh']['phi_Vn_kN']:.1f}"),
            ("Kết luận",
             "ĐẠT" if cols["2"]["sh"]["ok"] else "KHÔNG ĐẠT",
             "ĐẠT" if cols["3"]["sh"]["ok"] else "KHÔNG ĐẠT"),
        ]
        for a, b, c in _rows:
            tdata.append([_pc(a, True), _pc(b), _pc(c)])
        t_sw = Table(tdata, colWidths=[56 * mm, 50 * mm, 50 * mm])
        t_sw.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#D1D5DB")),
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F3F4F6")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [HexColor("#FFFFFF"), HexColor("#F9FAFB")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(Spacer(1, 3))
        story.append(t_sw)
    else:
        story.append(Paragraph("Không tính được kiểm tra cắt.", st_b))

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=10 * mm, bottomMargin=10 * mm,
                            title="Tóm tắt kiểm tra cột BTCT - ACI 318-19")
    doc.build(story)
    return filepath
