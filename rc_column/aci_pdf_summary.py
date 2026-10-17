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

from .pdf_export import (_mpl_font, _find_font, _find_font_bold, section_image,
                          draw_section_ax)
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
    """Tự vẽ 2 biểu đồ ACI -> (png_nm_alpha, png_m2m3) bytes.

    Dùng figure cao (5.0 x 5.2) để trục tung (trục y) giãn ra tự nhiên,
    không bị dẹt. Khi nhúng vào PDF giữ đúng tỉ lệ gốc bằng PIL.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = []
    for draw_fn in (draw_aci_nm_alpha_ax, draw_aci_m2m3_ax):
        fig = plt.figure(figsize=(5.0, 5.0))
        ax = fig.add_subplot(111)
        draw_fn(ax, sec, conc, steel, aci_res, inp.N, inp.Mx, inp.My,
                tied=tied)
        fig.tight_layout()
        fig.subplots_adjust(bottom=0.22, top=0.93, left=0.12, right=0.95)
        buf = _io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    pad_inches=0.05)
        plt.close(fig)
        out.append(buf.getvalue())
    return tuple(out)


def _section_png_tcvn(sec):
    """Vẽ mặt cắt kiểu TCVN (giống hệt pdf_export.export_summary_pdf):
    figure (3.9, 3.1), show_stats=False (không dòng text thống kê dưới hình).
    Trả về PNG bytes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(3.9, 3.1))
    draw_section_ax(ax, sec, show_dims=True, show_stats=False)
    ax.grid(True, color="#E5E7EB", linestyle="--", linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    for sp in ax.spines.values():
        sp.set_visible(False)
    buf = _io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                pad_inches=0.1, facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


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


def _shear_aci(sec, inp, steel, conc, q2_override=None, q3_override=None):
    """Kiểm tra cắt ACI 22.5.5.1 cho 2 phương. Trả về dict phương -> dict.

    q2_override/q3_override: lực cắt (kN) ghi đè khi inp.Q2/Q3 = 0
    (chế độ ETABS: gui truyền Q từ combo có |Q| lớn nhất qua shear_info).
    Nếu Q vẫn = 0 sau override, 'Q' = None -> hiển thị '—' thay vì 0.0
    để tránh kết luận ĐẠT gây hiểu lầm khi thiếu dữ liệu.
    """
    from .aci_checker import aci_shear_check
    cols = {}
    try:
        Av = inp.sw_legs * _m.pi * inp.sw_dia ** 2 / 4.0
        fyt = steel.fy
        cover = getattr(inp, "cover", 30.0)
        _q2 = q2_override if q2_override not in (None, 0, 0.0) else inp.Q2
        _q3 = q3_override if q3_override not in (None, 0, 0.0) else inp.Q3
        for Q, lbl, b_w, h_dim in ((_q2, "2", inp.cy, inp.cx),
                                   (_q3, "3", inp.cx, inp.cy)):
            d = max(h_dim - cover - inp.sw_dia - 12.0, 1.0)
            Acv = b_w * d
            Ag = sec.cx * sec.cy
            sh = aci_shear_check(Acv_mm2=Acv, Ag_mm2=Ag, fc_MPa=conc.fc,
                                 Nu_kN=inp.N, Vu_kN=abs(Q or 0.0),
                                 Av_mm2=Av, fyt_MPa=fyt,
                                 s_mm=inp.sw_spacing, d_mm=d)
            cols[lbl] = {"Q": Q if Q else None, "b": b_w, "d": d, "sh": sh}
    except Exception:
        pass
    return cols


def _extract_shear_q(shear_info):
    """Trích Q2/Q3 từ shear_info (hỗ trợ 2 dạng: {'Q2':..,'Q3':..} hoặc
    kiểu TCVN {'q2': {'Q':..}, 'q3': {'Q':..}}). Trả về (q2, q3) hoặc
    (None, None)."""
    if not isinstance(shear_info, dict):
        return None, None
    q2 = shear_info.get("Q2")
    q3 = shear_info.get("Q3")
    if q2 is None and isinstance(shear_info.get("q2"), dict):
        q2 = shear_info["q2"].get("Q")
    if q3 is None and isinstance(shear_info.get("q3"), dict):
        q3 = shear_info["q3"].get("Q")
    try:
        q2 = float(q2) if q2 is not None else None
    except (TypeError, ValueError):
        q2 = None
    try:
        q3 = float(q3) if q3 is not None else None
    except (TypeError, ValueError):
        q3 = None
    return q2, q3


def export_aci_summary_pdf(sec, inp, aci_res, conc, steel, tied, filepath,
                           case_info=None, sec_img_path=None, chart_pngs=None,
                           shear_info=None):
    """Xuất PDF Kết quả tính toán theo mẫu Excel (ACI 318-19, 1 trang A4).

    Layout 2 cột: trái = các bảng thông số, phải = hình mặt cắt + 2 biểu đồ.
    Dưới cùng: bảng kiểm tra cắt full-width.
    """
    import math as _m
    import io as _io
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Image, Table, TableStyle)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from collections import Counter
    import os as _os

    # Font
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

    st_title = ParagraphStyle("t", fontName=FNB, fontSize=14,
                              alignment=TA_CENTER, spaceAfter=8)
    st_sec = ParagraphStyle("sec", fontName=FNB, fontSize=9,
                            spaceBefore=5, spaceAfter=1,
                            textColor=HexColor("#111111"))
    st_cell = ParagraphStyle("c", fontName=FN, fontSize=7, leading=9)
    st_cell_b = ParagraphStyle("cb", fontName=FNB, fontSize=7, leading=9)
    st_hdr = ParagraphStyle("hdr", fontName=FNB, fontSize=7, leading=9,
                             alignment=TA_CENTER)
    st_hdr_left = ParagraphStyle("hdr_left", parent=st_hdr, alignment=TA_LEFT)
    st_lbl = ParagraphStyle("lbl", parent=st_cell, alignment=TA_LEFT)
    st_val = ParagraphStyle("val", parent=st_cell, alignment=TA_LEFT)
    st_val_b = ParagraphStyle("val_b", parent=st_cell_b, alignment=TA_LEFT)
    st_sec_title = ParagraphStyle("sectitle", parent=st_cell_b, alignment=TA_LEFT)

    def _sec_table(title, rows):
        data = [[Paragraph(f"<b>{title}</b>", st_sec_title)]]
        for lbl, val in rows:
            _vs = str(val)
            if "<b>" in _vs:
                _vs_clean = _vs.replace("<b>", "").replace("</b>", "")
                data.append([Paragraph(lbl, st_lbl),
                             Paragraph(_vs_clean, st_val_b)])
            else:
                data.append([Paragraph(lbl, st_lbl),
                             Paragraph(_vs, st_val)])
        t = Table(data, colWidths=[60 * mm, 30 * mm], hAlign="LEFT")
        style = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, HexColor("#111111")),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
        ]
        for i in range(1, len(data)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i),
                              HexColor("#F2F2F2")))
        t.setStyle(TableStyle(style))
        return t

    def _img_from_bytes(png_bytes, w_mm):
        buf = _io.BytesIO(png_bytes)
        try:
            from PIL import Image as _PIL
            _pil = _PIL.open(buf)
            _pw, _ph = _pil.size
            buf.seek(0)
            h_mm = w_mm * _ph / _pw if _pw > 0 else w_mm
        except Exception:
            h_mm = w_mm
        return Image(buf, width=w_mm * mm, height=h_mm * mm)

    # ===== Dữ liệu =====
    _ck_name = ""
    try:
        _fn = getattr(inp, "_filename", "") or ""
        if _fn:
            _ck_name = _os.path.splitext(_os.path.basename(_fn))[0].upper()
    except Exception:
        pass
    if not _ck_name and case_info:
        _ck_name = str(case_info.get("name", "")).upper()

    _t3 = getattr(sec, "cx", inp.cx)
    _t2 = getattr(sec, "cy", inp.cy)
    _cnt = Counter(r.dia for r in sec.rebars)
    _parts = [f"{_cnt[d]}-d{d:.0f}" for d in sorted(_cnt, reverse=True)]
    _mu = getattr(sec, "reinforcement_ratio", 0) or 0

    _story_txt, _label_txt, _combo_txt = "—", "—", "—"
    if case_info:
        _story_txt = str(case_info.get("story", "—"))
        _label_txt = str(case_info.get("label", case_info.get("column", "—")))
        _combo_txt = str(case_info.get("case", case_info.get("combo", "—")))
    _vpos = f"[{_story_txt}]-[{_label_txt}]" if _story_txt != "—" else "—"

    _alpha = _m.degrees(_m.atan2(inp.Mx, inp.My)) \
        if abs(inp.Mx) + abs(inp.My) > 1e-9 else 0.0
    _dc = aci_res.get("dc", 0)
    _fs = aci_res.get("fs", 0)
    _ok_txt = "<b>ĐẠT</b>" if aci_res.get("ok") else "<b>KHÔNG ĐẠT</b>"
    tie_txt = "Đai rời (tied)" if tied else "Đai xoắn (spiral)"
    _fyt = getattr(inp, "fyt", None) or getattr(steel, "fyt", steel.fy)

    # ===== Cột trái =====
    left_flow = []
    left_flow.append(_sec_table("THÔNG TIN CHUNG", [
        ("Tiêu chuẩn", "ACI 318-19"),
        ("Tên cấu kiện", _ck_name or "—"),
    ]))
    left_flow.append(_sec_table("VẬT LIỆU", [
        ("Cường độ bê tông, f'c", f"{conc.fc:.2f} MPa"),
        ("Mô đun đàn hồi bê tông, Ec", f"{conc.Ec:.0f} MPa"),
        ("Cường độ thép dọc, fy", f"{steel.fy:.0f} MPa"),
        ("Mô đun đàn hồi thép, Es", f"{steel.Es:.0f} MPa"),
        ("Cường độ thép đai, fyt", f"{_fyt:.0f} MPa"),
        ("Loại cốt đai", tie_txt),
    ]))
    left_flow.append(_sec_table("TIẾT DIỆN", [
        ("Chiều rộng, t3", f"{_t3:.0f} mm"),
        ("Chiều cao, t2", f"{_t2:.0f} mm"),
        ("Lớp bê tông bảo vệ, c", f"{inp.cover:.0f} mm"),
    ]))
    left_flow.append(_sec_table("BỐ TRÍ CỐT THÉP", [
        ("Cốt thép dọc", " + ".join(_parts)),
        ("Hàm lượng thép dọc, μ", f"{_mu*100:.2f}%"),
    ]))
    left_flow.append(_sec_table("NỘI LỰC TÍNH TOÁN", [
        ("Vị trí cột", _vpos),
        ("Tổ hợp tính toán", _combo_txt),
        ("Lực dọc, N", f"{inp.N:.1f} kN"),
        ("Momen quanh trục 2, M2", f"{inp.Mx:.1f} kNm"),
        ("Momen quanh trục 3, M3", f"{inp.My:.1f} kNm"),
    ]))
    _BN = aci_res.get("BN", 0)
    _Bx = aci_res.get("Bx", 0)
    _By = aci_res.get("By", 0)
    _Mb_aci = _m.hypot(_Bx, _By)
    _Ma_aci = _m.hypot(inp.Mx, inp.My)
    left_flow.append(_sec_table("KẾT QUẢ TÍNH TOÁN", [
        ("Góc tác dụng mômen, α", f"{_alpha:.1f}°"),
        ("Hệ số sức kháng, φ", f"{aci_res.get('phi', 0):.2f}"),
        ("Biến dạng thép, εt", f"{aci_res.get('eps_t', 0):.5f}"),
        ("Điểm tải trọng A", ""),
        ("Lực dọc, N", f"{inp.N:.1f} kN"),
        ("Mômen, M2", f"{inp.Mx:.1f} kNm"),
        ("Mômen, M3", f"{inp.My:.1f} kNm"),
        ("Mômen tổng, Mα", f"{_Ma_aci:.1f} kNm"),
        ("Điểm giới hạn B", ""),
        ("Lực dọc, Nu", f"{_BN:.1f} kN"),
        ("Mômen, M2u", f"{_Bx:.1f} kNm"),
        ("Mômen, M3u", f"{_By:.1f} kNm"),
        ("Mômen tổng, Mα,u", f"{_Mb_aci:.1f} kNm"),
        ("Tỉ số sử dụng khả năng chịu lực, D/C", f"{_dc:.3f}"),
        ("Hệ số an toàn, FS", f"{_fs:.2f}"),
        ("Kết luận", _ok_txt),
    ]))

    # ===== Cột phải: hình + biểu đồ =====
    def _centered_img(png_bytes, w_mm):
        _im = _img_from_bytes(png_bytes, w_mm)
        _t = Table([[_im]], colWidths=[90 * mm], hAlign="CENTER")
        _t.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        return _t

    st_chart_title = ParagraphStyle("ct", parent=st_cell_b, alignment=TA_CENTER,
                                      fontSize=8, spaceBefore=2, spaceAfter=2)

    right_flow = []
    try:
        # Mặt cắt (dùng hàm TCVN vì giống nhau)
        import sys as _sys
        _pdf_exp = _sys.modules.get("rc_column.pdf_export")
        if _pdf_exp is None:
            from rc_column import pdf_export as _pdf_exp
        _sec_png = _pdf_exp.section_image(sec, width_in=2.2, dpi=150,
                                          show_stats=False)
        right_flow.append(_centered_img(_sec_png, 52))
        right_flow.append(Spacer(1, 2))
        # 2 biểu đồ ACI (có tiêu đề)
        _alpha_aci = _m.degrees(_m.atan2(inp.Mx, inp.My)) \
            if abs(inp.Mx) + abs(inp.My) > 1e-9 else 0.0
        _pngs = _aci_charts_png(sec, conc, steel, aci_res, inp, tied)
        if _pngs and len(_pngs) >= 2:
            right_flow.append(Paragraph(
                f"<b>Biểu đồ tương tác N-Mα</b> (α = {_alpha_aci:.1f}°)",
                st_chart_title))
            right_flow.append(_centered_img(_pngs[0], 66))
            right_flow.append(Spacer(1, 2))
            right_flow.append(Paragraph(
                f"<b>Mặt cắt M2-M3</b> (N = {inp.N:+.1f} kN)",
                st_chart_title))
            right_flow.append(_centered_img(_pngs[1], 66))
        elif chart_pngs and len(chart_pngs) >= 2:
            right_flow.append(Paragraph(
                f"<b>Biểu đồ tương tác N-Mα</b> (α = {_alpha_aci:.1f}°)",
                st_chart_title))
            right_flow.append(_centered_img(chart_pngs[0], 66))
            right_flow.append(Spacer(1, 2))
            right_flow.append(Paragraph(
                f"<b>Mặt cắt M2-M3</b> (N = {inp.N:+.1f} kN)",
                st_chart_title))
            right_flow.append(_centered_img(chart_pngs[1], 66))
    except Exception as e:
        right_flow.append(Paragraph(f"(Không vẽ được hình: {e})", st_cell))

    t_main = Table([[left_flow, right_flow]],
                   colWidths=[90 * mm, 90 * mm], hAlign="CENTER")
    t_main.setStyle(TableStyle([
        ("VALIGN", (0, 0), (0, 0), "TOP"),
        ("VALIGN", (1, 0), (1, 0), "BOTTOM"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    story = []
    story.append(Paragraph("KIỂM TRA CỘT BÊ TÔNG CỐT THÉP", st_title))
    story.append(t_main)
    story.append(Spacer(1, 4))

    # ===== KIỂM TRA CẮT (full width, giữ ở trang 1) =====
    from reportlab.platypus import KeepTogether
    _sw_story = []
    try:
        from .aci_checker import aci_shear_check
        from .sections import bar_area
        _sw_dia = getattr(inp, "sw_dia", 8)
        _sw_s = getattr(inp, "sw_spacing", 200)
        _sw_legs = getattr(inp, "sw_legs", 2)
        _Av = _sw_legs * bar_area(_sw_dia)
        _sw_txt = f"{_sw_legs:.0f}φ{_sw_dia:.0f} a{_sw_s:.0f}"
        _data = [
            [Paragraph("<b>KIỂM TRA KHẢ NĂNG CHỊU CẮT</b>", st_hdr_left),
             Paragraph("<b>Phương V2</b>", st_hdr),
             Paragraph("<b>Phương V3</b>", st_hdr)],
        ]
        _rows = []
        for Q, b_w, h_dim in ((inp.Q2, _t2, _t3), (inp.Q3, _t3, _t2)):
            _d = h_dim - inp.cover - _sw_dia - 10
            _r = aci_shear_check(Acv_mm2=b_w * h_dim, Ag_mm2=b_w * h_dim,
                                 fc_MPa=conc.fc, Nu_kN=inp.N,
                                 Vu_kN=abs(Q), Av_mm2=_Av,
                                 fyt_MPa=_fyt, s_mm=_sw_s, d_mm=_d)
            _rows.append((Q, _r))
        (_q2, _r2), (_q3, _r3) = _rows
        _d2 = _t3 - inp.cover - _sw_dia - 12
        _d3 = _t2 - inp.cover - _sw_dia - 12
        _sw_lines = [
            ("Thép đai bố trí", _sw_txt, _sw_txt),
            ("Lực cắt tính toán, Vu",
             f"{abs(_q2):.1f} kN", f"{abs(_q3):.1f} kN"),
            ("Kích thước tiết diện, b × d",
             f"{_t2:.0f} × {_d2:.0f} mm", f"{_t3:.0f} × {_d3:.0f} mm"),
            ("Av = n × φ",
             f"{_Av:.0f} mm²", f"{_Av:.0f} mm²"),
            ("Vc = max[0.17λ√f'c, 0.66λsλ(ρw)⅓√f'c]·bw·d (ACI 22.5.5)",
             f"{_r2['Vc_kN']:.1f} kN",
             f"{_r3['Vc_kN']:.1f} kN"),
            ("Vs = Av·fyt·d/s (ACI 22.5.8)",
             f"{_r2['Vs_kN']:.1f} kN",
             f"{_r3['Vs_kN']:.1f} kN"),
            ("φVn = φ·(Vc+Vs)", f"{_r2['phi_Vn_kN']:.1f} kN",
             f"{_r3['phi_Vn_kN']:.1f} kN"),
            ("Kết luận",
             "<b>ĐẠT</b>" if _r2['ok'] else "<b>KHÔNG ĐẠT</b>",
             "<b>ĐẠT</b>" if _r3['ok'] else "<b>KHÔNG ĐẠT</b>"),
        ]
        for a, b, c in _sw_lines:
            _is_kl = "Kết luận" in a
            _data.append([
                Paragraph(a, st_lbl),
                Paragraph(b, st_cell_b if _is_kl else st_cell),
                Paragraph(c, st_cell_b if _is_kl else st_cell),
            ])
        for i in range(1, len(_data)):
            for j in (1, 2):
                _data[i][j].style.alignment = TA_CENTER
        t_sw = Table(_data, colWidths=[90 * mm, 45 * mm, 45 * mm],
                     hAlign="LEFT")
        _st = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, HexColor("#111111")),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
        ]
        for i in range(1, len(_data)):
            if i % 2 == 0:
                _st.append(("BACKGROUND", (0, i), (-1, i),
                            HexColor("#F2F2F2")))
        t_sw.setStyle(TableStyle(_st))
        _sw_story.append(t_sw)
    except Exception as e:
        _sw_story.append(Paragraph(f"Không tính được cắt: {e}", st_cell))
    story.append(KeepTogether(_sw_story))

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=10 * mm, bottomMargin=10 * mm,
                            title="Kết quả kiểm tra cột BTCT (ACI 318-19)")
    doc.build(story)
    return filepath
