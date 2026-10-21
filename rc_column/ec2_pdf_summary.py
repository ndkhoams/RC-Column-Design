"""Xuất PDF tóm tắt kiểm tra cột theo EC2 (EN 1992-1-1) (khổ A4, 1 trang).

Bố cục COPY export_summary_pdf của pdf_export.py (TCVN):
- Tiêu đề + tên cấu kiện
- Hàng trên: [hình mặt cắt + box vật liệu | bảng thông số] (thuật toán 3 bước)
- 2 biểu đồ EC2 đặt ngang nhau, giữ tỉ lệ bằng PIL
- Chi tiết điểm A/B, kiểm tra cắt

Không phụ thuộc GUI.
"""

import io as _io
import math as _m
import os as _os

from .pdf_export import (_mpl_font, _find_font, _find_font_bold, section_image,
                          draw_section_ax)
from .ec2_chart_draw import draw_ec2_nm_alpha_ax, draw_ec2_m2m3_ax


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


def _fm(x):
    """Định dạng cường độ tra bảng/nhập liệu: in ĐÚNG giá trị thật, cắt số 0
    thừa ở cuối (460.5 -> '460.5', 500 -> '500'). Không dùng cho giá trị
    suy ra bằng phép chia (fcd/fyd giữ quy ước thập phân hiện tại)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    if not _m.isfinite(v):
        return "—"
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _f_dc(dc):
    try:
        if dc is None or not _m.isfinite(float(dc)):
            return "∞"
    except (TypeError, ValueError):
        return "∞"
    return f"{float(dc):.3f}"


def _ec2_charts_png(sec, conc, steel, ec2_res, inp):
    """Tự vẽ 2 biểu đồ EC2 -> (png_nm_alpha, png_m2m3) bytes.

    Dùng figure cao (5.0 x 5.2) để trục tung (trục y) giãn ra tự nhiên,
    không bị dẹt. Khi nhúng vào PDF giữ đúng tỉ lệ gốc bằng PIL.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = []
    _m2 = ec2_res.get("M2_mag", inp.Mx) if isinstance(ec2_res, dict) else inp.Mx
    _m3 = ec2_res.get("M3_mag", inp.My) if isinstance(ec2_res, dict) else inp.My
    for draw_fn in (draw_ec2_nm_alpha_ax, draw_ec2_m2m3_ax):
        fig = plt.figure(figsize=(3.2, 3.2))
        ax = fig.add_subplot(111)
        draw_fn(ax, sec, conc, steel, ec2_res, inp.N, _m2, _m3)
        fig.tight_layout()
        fig.subplots_adjust(bottom=0.22, top=0.93, left=0.12, right=0.95)
        buf = _io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches="tight",
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
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight",
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


def _slenderness_ec2(sec, conc, steel, inp, precalc=None):
    """Độ mảnh & mô men thiết kế EC2 cho 2 phương (bản rút gọn cho PDF).

    Dùng ec2_design_moment với M01 = M02 = |M| (mô men không đổi,
    const_moment=True) vì ColumnInput chỉ lưu một giá trị M mỗi phương.
    Trả về dict {'dir2': {...}, 'dir3': {...}}.

    precalc: dict đã tính sẵn từ app (nguyên tắc "tính 1 lần"). Nếu có, dùng luôn.
    """
    # Ưu tiên dùng kết quả đã tính sẵn từ app
    if precalc and isinstance(precalc, dict):
        if 'dir2' in precalc or 'dir3' in precalc:
            return precalc
    from .ec2_checker import ec2_design_moment
    from .checker import section_inertia
    from .stability import effective_length
    out = {}
    try:
        Ix, Iy, ix, iy, Isx, Isy = section_inertia(sec)
        Ac = sec.gross_area
        As = sec.steel_area
        params = (
            ("dir2", "2", inp.Mx, inp.Lx, inp.top_x, inp.bottom_x,
             Ix, ix, Isx, sec.cy),
            ("dir3", "3", inp.My, inp.Ly, inp.top_y, inp.bottom_y,
             Iy, iy, Isy, sec.cx),
        )
        for key, lbl, M, L, top, bot, I, i_rad, Is, h in params:
            l0_mm = effective_length(L, top, bot,
                                     getattr(inp, f"psi_{'x' if lbl == '2' else 'y'}",
                                             None)) * 1000.0
            d = max(h - getattr(inp, "cover", 30.0) - 12.0, 1.0)
            r = ec2_design_moment(
                NEd_kN=inp.N, M_top_kNm=abs(M), M_bot_kNm=abs(M),
                l0_mm=l0_mm, i_mm=i_rad, h_mm=h,
                Ac_mm2=Ac, As_mm2=As,
                fcd_MPa=conc.fcd, fyd_MPa=steel.fyd,
                Ecm_MPa=conc.Ecm, Ic_mm4=I, Is_mm4=Is,
                Es_MPa=steel.Es, fck_MPa=conc.fck,
                method="stiffness", d_mm=d, eps_yd=steel.eps_yd,
                const_moment=True)
            out[key] = r
    except Exception:
        pass
    return out


def _shear_ec2(sec, inp, steel, conc, q2_override=None, q3_override=None, precalc=None):
    """Kiểm tra cắt EC2 6.2 cho 2 phương. Trả về dict {'dir2':..., 'dir3':...}.

    q2_override/q3_override: lực cắt (kN) ghi đè khi inp.Q2/Q3 = 0
    (chế độ ETABS: gui truyền Q từ combo có |Q| lớn nhất qua shear_info).
    ρl tính từ thép dọc chịu kéo ≈ một nửa tổng As (ước lượng).

    precalc: dict đã tính sẵn từ app (nguyên tắc "tính 1 lần"). Nếu có, dùng luôn.
    """
    # Ưu tiên dùng kết quả đã tính sẵn từ app
    if precalc and isinstance(precalc, dict):
        if 'dir2' in precalc or 'dir3' in precalc:
            return precalc
    from .ec2_checker import ec2_shear_check
    from .sections import bar_area
    cols = {}
    try:
        Asw_s = (inp.sw_legs * bar_area(inp.sw_dia) / inp.sw_spacing
                 if inp.sw_spacing > 0 else 0.0)
        fyd = steel.fyd
        cover = getattr(inp, "cover", 30.0)
        Asl = sec.steel_area / 2.0  # ước lượng thép chịu kéo
        Ac = sec.gross_area
        _q2 = q2_override if q2_override not in (None, 0, 0.0) else inp.Q2
        _q3 = q3_override if q3_override not in (None, 0, 0.0) else inp.Q3
        for Q, key, b_w, h_dim in ((_q2, "dir2", inp.cy, inp.cx),
                                   (_q3, "dir3", inp.cx, inp.cy)):
            d = max(h_dim - cover - inp.sw_dia - 12.0, 1.0)
            sh = ec2_shear_check(bw_mm=b_w, d_mm=d, Ac_mm2=Ac,
                                 fck_MPa=conc.fck, NEd_kN=inp.N,
                                 VEd_kN=abs(Q or 0.0), Asl_mm2=Asl,
                                 fyd_MPa=fyd, Asw_s_mm2mm=Asw_s)
            cols[key] = {"Q": Q if Q else None, "b": b_w, "d": d, "sh": sh}
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


def _export_ec2_summary_pdf_impl(sec, inp, ec2_res, conc, steel, filepath,
                           case_info=None, sec_img_path=None, chart_pngs=None,
                           shear_info=None, slend_res=None, tied=None,
                           fyk_sw=None, show_compression: bool = True, _level: int = 0):
    """Xuất PDF Kết quả tính toán theo mẫu Excel (EC2, 1 trang A4).

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


    # --- Ep 1 trang: muc nen layout theo bac (wrapper chon muc thap
    # nhat cho ra dung 1 trang; muc 0 = le/padding goc, chi thu hep dan).
    _LV = max(0, min(3, int(_level)))
    _PAD = (2.0, 1.2, 0.8, 0.6)[_LV]     # padding doc cac o bang
    _HPAD = (3.0, 2.2, 1.8, 1.5)[_LV]    # padding duoi tieu de section
    _LEAD = (9.0, 9.0, 8.5, 8.5)[_LV]    # leading dong chu 7pt
    _TSP = (8, 4, 3, 2)[_LV]             # spaceAfter tieu de chinh
    _CSP = (2.0, 1.5, 1.0, 1.0)[_LV]     # space quanh tieu de bieu do
    _ISP = (2, 1.5, 1, 1)[_LV]           # spacer giua cac hinh
    _MSP = (4, 3, 2, 2)[_LV]             # spacer truoc bang cat
    _MRG = (8, 8, 7, 6)[_LV]             # le tren/duoi (mm)
    _IW0 = (66.0, 66.0, 62.0, 56.0)[_LV]  # co hinh cot phai theo muc nen (mm)
    # Dan y moi (user chot): MOI hang trong dan y deu la hang bat buoc,
    # khong muc nen nao duoc bo hang nua -> _DROP rong o moi muc.
    _DROP = set()

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

    # --- Dung story theo bo tham so layout (goi lai khi gian trang;
    # chi padding/leading/khoang cach/co hinh thay doi, noi dung
    # chu va so lieu giu nguyen).
    def _mk(_PAD, _HPAD, _LEAD, _TSP, _CSP, _ISP, _MSP, _IW, slend_res=None):

        st_title = ParagraphStyle("t", fontName=FNB, fontSize=14,
                                  alignment=TA_CENTER, spaceAfter=_TSP)
        st_sec = ParagraphStyle("sec", fontName=FNB, fontSize=9,
                                spaceBefore=5, spaceAfter=1,
                                textColor=HexColor("#111111"))
        st_cell = ParagraphStyle("c", fontName=FN, fontSize=7, leading=_LEAD)
        st_cell_b = ParagraphStyle("cb", fontName=FNB, fontSize=7, leading=_LEAD)
        st_hdr = ParagraphStyle("hdr", fontName=FNB, fontSize=7, leading=_LEAD,
                                 alignment=TA_CENTER)
        st_hdr_left = ParagraphStyle("hdr_left", parent=st_hdr, alignment=TA_LEFT)
        st_lbl = ParagraphStyle("lbl", parent=st_cell, alignment=TA_LEFT)
        st_val = ParagraphStyle("val", parent=st_cell, alignment=TA_LEFT)
        st_val_b = ParagraphStyle("val_b", parent=st_cell_b, alignment=TA_LEFT)
        st_sec_title = ParagraphStyle("sectitle", parent=st_cell_b, alignment=TA_LEFT)

        def _sec_table(title, rows):
            data = [[Paragraph(f"<b>{title}</b>", st_sec_title)]]
            for lbl, val in rows:
                if lbl in _DROP:
                    continue
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
                ("TOPPADDING", (0, 0), (-1, -1), _PAD),
                ("BOTTOMPADDING", (0, 0), (-1, -1), _PAD),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, HexColor("#111111")),
                ("BOTTOMPADDING", (0, 0), (-1, 0), _HPAD),
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

        _story_txt, _label_txt, _combo_txt, _station_txt = "—", "—", "—", "—"
        if case_info:
            _story_txt = str(case_info.get("story", "—"))
            _label_txt = str(case_info.get("label", case_info.get("column", "—")))
            _combo_txt = str(case_info.get("case", case_info.get("combo", "—")))
            _st = case_info.get("station", "—")
            _station_txt = f"{_st:.2f}" if isinstance(_st, (int, float)) else str(_st)
        _vpos = f"[{_story_txt}]-[{_label_txt}]-[{_station_txt}]" if _story_txt != "—" else "—"

        _alpha = _m.degrees(_m.atan2(inp.Mx, inp.My)) \
            if abs(inp.Mx) + abs(inp.My) > 1e-9 else 0.0
        _dc = ec2_res.get("dc", 0)
        _fs = ec2_res.get("fs", 0)
        _ok_txt = "<b>ĐẠT</b>" if ec2_res.get("ok") else "<b>KHÔNG ĐẠT</b>"

        # Độ mảnh (tính gọn nếu chưa truyền vào)
        if slend_res is None:
            slend_res = _slenderness_ec2(sec, conc, steel, inp)
        _sl2 = slend_res.get("dir2", {}) if isinstance(slend_res, dict) else {}
        _sl3 = slend_res.get("dir3", {}) if isinstance(slend_res, dict) else {}

        # ===== Cột trái (dan y user chot 2026-10-21, khung nhu TCVN) =====
        left_flow = []
        left_flow.append(_sec_table("THÔNG TIN CHUNG", [
            ("Tiêu chuẩn", "EC2 (EN 1992-1-1)"),
            ("Cấu kiện", _ck_name or "—"),
        ]))
        _fyk_sw = fyk_sw if fyk_sw is not None else steel.fyk
        _fyd_sw = _fyk_sw / 1.15
        left_flow.append(_sec_table("VẬT LIỆU", [
            ("Cường độ bê tông, fck", f"{_fm(conc.fck)} MPa"),
            ("Cường độ tính toán, fcd", f"{conc.fcd:.2f} MPa"),
            ("Mô đun đàn hồi, Ecm", f"{conc.Ecm:.0f} MPa"),
            ("Cường độ thép dọc, fyk", f"{_fm(steel.fyk)} MPa"),
            ("Cường độ thép đai, fyk", f"{_fm(_fyk_sw)} MPa"),
            ("Cường độ tính toán, fyd", f"{steel.fyd:.1f} MPa"),
            ("Mô đun đàn hồi thép, Es", f"{steel.Es:.0f} MPa"),
        ]))
        # TIẾT DIỆN (theo loai tiet dien)
        _kind = getattr(sec, "kind", None) or getattr(inp, "section_type", "rect")
        if _kind == "circle":
            _sec_rows = [("Hình tròn, đường kính d", f"{_t3:.0f} mm")]
        elif _kind == "poly":
            _sec_rows = [("Diện tích bê tông, A<sub>c</sub>",
                          f"{sec.gross_area:.0f} mm²")]
        else:
            _sec_rows = [("Hình chữ nhật, t2 × t3",
                          f"{_t2:.0f} × {_t3:.0f} mm")]
        _sec_rows.append(("Lớp bê tông bảo vệ cốt thép dọc, c",
                          f"{inp.cover:.0f} mm"))
        left_flow.append(_sec_table("TIẾT DIỆN", _sec_rows))
        left_flow.append(_sec_table("BỐ TRÍ CỐT THÉP DỌC", [
            ("Số lượng thép", " + ".join(_parts)),
            ("Hàm lượng thép dọc, μ", f"{_mu*100:.2f}%"),
        ]))
        left_flow.append(_sec_table("NỘI LỰC KIỂM TRA", [
            ("Vị trí cột", _vpos),
            ("Tổ hợp tính toán", _combo_txt),
            ("Lực dọc tính toán, NEd", f"{inp.N:.1f} kN"),
            ("Mômen ban đầu, M2, M3", f"{inp.Mx:.1f} / {inp.My:.1f} kNm"),
        ]))
        # CHIỀU DÀI TÍNH TOÁN & HIỆU ỨNG BẬC 2 — chi doc tu slend_res
        # (dm cua _ec2_calculate_full) / ec2_res; thieu key nao bo hang
        # do, khong tinh cong thuc moi o tang PDF.
        _dm = slend_res if isinstance(slend_res, dict) else {}
        _l0_2 = _dm.get("l0_2") or ec2_res.get("l0_2")
        _l0_3 = _dm.get("l0_3") or ec2_res.get("l0_3")
        _lam2 = _dm.get("lambda_2") or _sl2.get("lambda_sl") \
            or ec2_res.get("lambda_2")
        _lam3 = _dm.get("lambda_3") or _sl3.get("lambda_sl") \
            or ec2_res.get("lambda_3")
        _len_rows = [
            ("Chiều dài cột, L2, L3",
             f"{inp.Lx*1000:.0f} / {inp.Ly*1000:.0f} mm"),
        ]
        if _l0_2 and _l0_3:
            _len_rows.append(
                ("Chiều dài tính toán, l02, l03",
                 f"{float(_l0_2)*1000:.0f} / {float(_l0_3)*1000:.0f} mm"))
        if _lam2 and _lam3:
            _len_rows.append(
                ("Độ mảnh, λ2, λ3",
                 f"{_f(_lam2, 1)} / {_f(_lam3, 1)}"))
        _ll2 = _sl2.get("lambda_lim")
        _ll3 = _sl3.get("lambda_lim")
        if _ll2 is not None and _ll3 is not None:
            _len_rows.append(
                ("Độ mảnh giới hạn, λlim2, λlim3",
                 f"{_f(_ll2, 1)} / {_f(_ll3, 1)}"))
        _ei2 = _sl2.get("ei_mm")
        _ei3 = _sl3.get("ei_mm")
        if _ei2 is not None and _ei3 is not None:
            _len_rows.append(
                ("Độ lệch tâm sai lệch, ei2, ei3",
                 f"{_f(_ei2, 1)} / {_f(_ei3, 1)} mm"))
        _mi2 = _sl2.get("M_imp")
        _mi3 = _sl3.get("M_imp")
        if _mi2 is not None and _mi3 is not None:
            _len_rows.append(
                ("Mômen do sai lệch, Mimp2, Mimp3",
                 f"{_f(_mi2, 1)} / {_f(_mi3, 1)} kNm"))
        _fa2 = _sl2.get("factor", _sl2.get("so_factor"))
        _fa3 = _sl3.get("factor", _sl3.get("so_factor"))
        if _fa2 is not None and _fa3 is not None:
            _len_rows.append(
                ("Hệ số phóng đại bậc 2, β2, β3",
                 f"{_f(_fa2, 3)} / {_f(_fa3, 3)}"))
        _m22 = _sl2.get("so_M2")
        _m23 = _sl3.get("so_M2")
        if _m22 is not None and _m23 is not None:
            _len_rows.append(
                ("Mômen bậc 2, M2,2, M2,3",
                 f"{_f(_m22, 1)} / {_f(_m23, 1)} kNm"))
        left_flow.append(_sec_table(
            "CHIỀU DÀI TÍNH TOÁN &amp; HIỆU ỨNG BẬC 2", _len_rows))
        # KẾT QUẢ KIỂM TRA KHẢ NĂNG CHỊU LỰC (MEd da gom bac 2, giu dau
        # theo mo men goc nhu _ec2_calculate_full da khoi phuc)
        _BN = ec2_res.get("BN", 0)
        _Bx = ec2_res.get("Bx", 0)
        _By = ec2_res.get("By", 0)
        _Mb = _m.hypot(_Bx, _By)
        _M2s = ec2_res.get("M2_mag")
        _M3s = ec2_res.get("M3_mag")
        if _M2s is None:
            _M2s = abs(inp.Mx)
        if _M3s is None:
            _M3s = abs(inp.My)
        _o2 = ec2_res.get("M2_orig", inp.Mx)
        _o3 = ec2_res.get("M3_orig", inp.My)
        _M2sgn = (1.0 if _o2 >= 0 else -1.0) * _M2s
        _M3sgn = (1.0 if _o3 >= 0 else -1.0) * _M3s
        _alpha_r = ec2_res.get("alpha_deg")
        if _alpha_r is None:
            _alpha_r = _m.degrees(_m.atan2(_M2sgn, _M3sgn)) \
                if abs(_M2sgn) + abs(_M3sgn) > 1e-9 else 0.0
        _Ma = ec2_res.get("Malpha")
        if _Ma is None:
            _Ma = _m.hypot(_M2s, _M3s)
        left_flow.append(_sec_table("KẾT QUẢ KIỂM TRA KHẢ NĂNG CHỊU LỰC", [
            ("Lực dọc tính toán, NEd", f"{inp.N:.1f} kN"),
            ("Mômen thiết kế, MEd2, MEd3",
             f"{_M2sgn:.1f} / {_M3sgn:.1f} kNm"),
            (f"Mômen tổng kiểm tra, Mα (α = {_alpha_r:.1f}°)",
             f"{_Ma:.1f} kNm"),
            ("Lực dọc giới hạn, NRd", f"{_BN:.1f} kN"),
            ("Mômen giới hạn, Mα,Rd", f"{_Mb:.1f} kNm"),
            ("Tỉ số sử dụng khả năng chịu lực, D/C (FS)",
             f"{_f_dc(_dc)} ({_f(_fs, 2)})"),
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
                                          fontSize=8, spaceBefore=_CSP, spaceAfter=_CSP)

        right_flow = []
        try:
            # Vùng nén (giống app)
            import sys as _sys
            _pdf_exp = _sys.modules.get("rc_column.pdf_export")
            if _pdf_exp is None:
                from rc_column import pdf_export as _pdf_exp
            _BN = (ec2_res.get("BN", 0) or 0) if isinstance(ec2_res, dict) else 0
            _Bx = (ec2_res.get("Bx", 0) or 0) if isinstance(ec2_res, dict) else 0
            _By = (ec2_res.get("By", 0) or 0) if isinstance(ec2_res, dict) else 0
            _alpha = _m.degrees(_m.atan2(_Bx, _By)) if (abs(_Bx)+abs(_By)) > 1e-9 else 0.0
            _na = None
            try:
                from .ec2_checker import ec2_neutral_axis_at_N as _nafn
                _na = _nafn(sec, conc, steel, _BN, _alpha)
            except Exception:
                pass
            _sec_png = _pdf_exp.compression_zone_image(sec, _BN, _Bx, _By,
                                                       na_info=_na,
                                                       show_compression=show_compression)
            right_flow.append(_centered_img(_sec_png, _IW))
            right_flow.append(Spacer(1, _ISP))
            # 2 biểu đồ EC2 (có tiêu đề)
            _pngs = _ec2_charts_png(sec, conc, steel, ec2_res, inp)
            if _pngs and len(_pngs) >= 2:
                right_flow.append(Paragraph(
                    f"<b>Biểu đồ tương tác N-Mα</b> (α = {_alpha:.1f}°)",
                    st_chart_title))
                right_flow.append(_centered_img(_pngs[0], _IW))
                right_flow.append(Spacer(1, _ISP))
                right_flow.append(Paragraph(
                    f"<b>Mặt cắt M2-M3</b> (NEd = {inp.N:+.1f} kN)",
                    st_chart_title))
                right_flow.append(_centered_img(_pngs[1], _IW))
            elif chart_pngs and len(chart_pngs) >= 2:
                right_flow.append(Paragraph(
                    f"<b>Biểu đồ tương tác N-Mα</b> (α = {_alpha:.1f}°)",
                    st_chart_title))
                right_flow.append(_centered_img(chart_pngs[0], _IW))
                right_flow.append(Spacer(1, _ISP))
                right_flow.append(Paragraph(
                    f"<b>Mặt cắt M2-M3</b> (NEd = {inp.N:+.1f} kN)",
                    st_chart_title))
                right_flow.append(_centered_img(chart_pngs[1], _IW))
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
        story.append(Paragraph(
            "KIỂM TRA KHẢ NĂNG CHỊU LỰC CỘT BÊ TÔNG CỐT THÉP", st_title))
        story.append(t_main)
        story.append(Spacer(1, _MSP))

        # ===== KIỂM TRA CẮT (full width, giữ ở trang 1) =====
        from reportlab.platypus import KeepTogether
        _sw_story = []
        try:
            _q2o, _q3o = _extract_shear_q(shear_info)
            # Ưu tiên dùng kết quả từ app (đồng nhất với tab Chi tiết)
            _si = shear_info if isinstance(shear_info, dict) else {}
            if "dir2" in _si and isinstance(_si["dir2"], dict) and "VRd_c_kN" in _si["dir2"]:
                # shear_info từ app: {"dir2": {"VRd_c_kN":..., "bw":..., "d":...}, ...}
                _d2 = {"b": _si["dir2"].get("bw", 0), "d": _si["dir2"].get("d", 0),
                       "Q": _si["dir2"].get("VEd", _q2o)}
                _d3 = {"b": _si["dir3"].get("bw", 0), "d": _si["dir3"].get("d", 0),
                       "Q": _si["dir3"].get("VEd", _q3o)}
                _s2 = _si["dir2"]
                _s3 = _si["dir3"]
            else:
                # Dùng precalc từ ec2_res (đã tính bởi _ec2_calculate_full) - KHÔNG tính lại
                _pre = (ec2_res.get("shear") or {}) if isinstance(ec2_res, dict) else {}
                _sh = _shear_ec2(sec, inp, steel, conc,
                                 q2_override=_q2o, q3_override=_q3o,
                                 precalc=_pre)
                _d2 = _sh.get("dir2", {})
                _d3 = _sh.get("dir3", {})
                _s2 = _d2.get("sh", {})
                _s3 = _d3.get("sh", {})
            _sw_dia = getattr(inp, "sw_dia", 8)
            _sw_s = getattr(inp, "sw_spacing", 200)
            _sw_legs = getattr(inp, "sw_legs", 2)
            from .sections import bar_area as _ba
            _m2_dia = getattr(inp, "swm2_dia", 0) or 0
            _m2_s = getattr(inp, "swm2_spacing", 0) or 0
            _m2_legs = getattr(inp, "swm2_legs", 0) or 0
            _m3_dia = getattr(inp, "swm3_dia", 0) or 0
            _m3_s = getattr(inp, "swm3_spacing", 0) or 0
            _m3_legs = getattr(inp, "swm3_legs", 0) or 0
            _Asw2 = _sw_legs * _ba(_sw_dia) + (_m2_legs * _ba(_m2_dia) if _m2_dia > 0 else 0)
            _Asw3 = _sw_legs * _ba(_sw_dia) + (_m3_legs * _ba(_m3_dia) if _m3_dia > 0 else 0)
            if _m2_dia > 0:
                _sw_txt2 = f"{_sw_legs:.0f}φ{_sw_dia:.0f} a{_sw_s:.0f} + {_m2_legs:.0f}φ{_m2_dia:.0f} a{_m2_s:.0f}"
            else:
                _sw_txt2 = f"{_sw_legs:.0f}φ{_sw_dia:.0f} a{_sw_s:.0f}"
            if _m3_dia > 0:
                _sw_txt3 = f"{_sw_legs:.0f}φ{_sw_dia:.0f} a{_sw_s:.0f} + {_m3_legs:.0f}φ{_m3_dia:.0f} a{_m3_s:.0f}"
            else:
                _sw_txt3 = f"{_sw_legs:.0f}φ{_sw_dia:.0f} a{_sw_s:.0f}"
            _data = [
                [Paragraph("<b>KIỂM TRA KHẢ NĂNG CHỊU CẮT (EC2 6.2)</b>", st_hdr_left),
                 Paragraph("<b>Phương V2</b>", st_hdr),
                 Paragraph("<b>Phương V3</b>", st_hdr)],
            ]
            _v2 = _d2.get("Q")
            _v3 = _d3.get("Q")
            _sw_lines = [
                ("Thép đai bố trí", _sw_txt2, _sw_txt3),
                ("Asw = n × φ",
                 f"{_Asw2:.0f} mm²", f"{_Asw3:.0f} mm²"),
                ("Lực cắt tính toán, VEd",
                 f"{abs(_v2):.1f} kN" if _v2 else "—",
                 f"{abs(_v3):.1f} kN" if _v3 else "—"),
                ("Kích thước chịu cắt, bw × d",
                 f"{_d2.get('b', 0):.0f} × {_d2.get('d', 0):.0f} mm",
                 f"{_d3.get('b', 0):.0f} × {_d3.get('d', 0):.0f} mm"),
                ("VRd,c = [CRd,c×k×(100ρl×fck)⅓ + k1×σcp]×bw×d",
                 f"{_s2.get('VRd_c_kN', 0):.1f} kN",
                 f"{_s3.get('VRd_c_kN', 0):.1f} kN"),
                ("VRd,max = αcw×bw×z×ν1×fcd/(cotθ+tanθ)",
                 f"{_s2.get('VRd_max_kN', 0):.1f} kN",
                 f"{_s3.get('VRd_max_kN', 0):.1f} kN"),
                ("VRd,s = (Asw/s)×z×fywd×cotθ (θ=45°)",
                 f"{_s2.get('VRd_s_kN', 0):.1f} kN",
                 f"{_s3.get('VRd_s_kN', 0):.1f} kN"),
                ("Asw/s yêu cầu = VEd/(z×fywd×cotθ)",
                 f"{_s2.get('Asw_s_req', 0):.3f} mm²/mm",
                 f"{_s3.get('Asw_s_req', 0):.3f} mm²/mm"),
                ("Kết luận",
                 "<b>ĐẠT</b>" if _s2.get("ok") else "<b>KHÔNG ĐẠT</b>",
                 "<b>ĐẠT</b>" if _s3.get("ok") else "<b>KHÔNG ĐẠT</b>"),
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
                ("TOPPADDING", (0, 0), (-1, -1), _PAD),
                ("BOTTOMPADDING", (0, 0), (-1, -1), _PAD),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, HexColor("#111111")),
                ("BOTTOMPADDING", (0, 0), (-1, 0), _HPAD),
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

        # Do nhanh cac thanh phan (phuc vu phan bo gian trang)
        def _wh(_fl, _wmm):
            _t = 0.0
            for _f in _fl:
                _w2, _h2 = _f.wrap(_wmm * mm, 10000)
                _t += _h2
                try:
                    _t += _f.getSpaceBefore() + _f.getSpaceAfter()
                except Exception:
                    pass
            return _t
        _hl = _wh(left_flow, 90)
        _hr = _wh(right_flow, 90)
        _hs = _wh(_sw_story, 180)
        _rl = sum(len(_t._cellvalues) for _t in left_flow
                  if isinstance(_t, Table))
        _rs = sum(len(_t._cellvalues) for _t in _sw_story
                  if isinstance(_t, Table))
        _hi = 0.0
        for _t in right_flow:
            if isinstance(_t, Table):
                try:
                    _c = _t._cellvalues[0][0]
                    if isinstance(_c, Image):
                        _hi += _c.drawHeight
                except Exception:
                    pass
        return story, (_hl, _hr, _hs, _rl, _rs, _hi)


    # --- Gian lap day trang: do khoang trong day that tu trang thai
    # frame sau build, phan bo vao (a) padding o bang -> (b) khoang
    # cach giua cac khoi -> (c) leading -> (d) co hinh cot phai; moi
    # lever co tran. Chon ban build 1 trang co trong day nho nhat.
    _TARGET = 7.0
    _cands = []

    def _try(_pad, _hpad, _lead, _tsp, _csp, _isp, _msp, _iw,
             _safe=False):
        try:
            _story, _info = _mk(_pad, _hpad, _lead, _tsp, _csp, _isp,
                                _msp, _iw, slend_res=slend_res)
            _buf = _io.BytesIO()
            _doc = SimpleDocTemplate(
                _buf, pagesize=A4, leftMargin=15 * mm,
                rightMargin=15 * mm, topMargin=_MRG * mm,
                bottomMargin=_MRG * mm, title="Kết quả kiểm tra cột BTCT (EC2)")
            _doc.build(_story)
        except Exception:
            if _safe:
                return 99, None, None
            raise
        _pg = getattr(_doc, "page", 1)
        _gap = None
        if _pg == 1:
            try:
                _gap = _doc.frame._y - _doc.frame._y1
            except Exception:
                _gap = None
        _cands.append((_pg, _gap, _buf.getvalue()))
        return _pg, _gap, _info

    def _scaled(_arg, _fac):
        return (_PAD + (_arg[0] - _PAD) * _fac,
                _HPAD + (_arg[1] - _HPAD) * _fac,
                _LEAD + (_arg[2] - _LEAD) * _fac,
                _TSP + (_arg[3] - _TSP) * _fac,
                _CSP + (_arg[4] - _CSP) * _fac,
                _ISP + (_arg[5] - _ISP) * _fac,
                _MSP + (_arg[6] - _MSP) * _fac,
                _IW0 + (_arg[7] - _IW0) * _fac)

    _base = (_PAD, _HPAD, _LEAD, _TSP, _CSP, _ISP, _MSP, _IW0)
    _pg, _gap, _info = _try(*_base)
    if _pg == 1 and _gap is not None and _gap > _TARGET + 1.5:
        _hl, _hr, _hs, _rl, _rs, _hi = _info
        _need = _gap - _TARGET
        _freeL = max(0.0, _hr - _hl)
        _freeR = max(0.0, _hl - _hr)

        def _grow(_e, _free):
            # Tong chieu cao tang khi moi dong bang tang _e; cot chua
            # co dong bang (cot phai) chi tinh phan vuot do duoi kip.
            if _free > 0:
                return _e * _rs + max(0.0, _e * _rl - _free)
            return _e * (_rs + _rl)

        def _solve(_target, _cap, _free):
            if _target <= 0 or _cap <= 0:
                return 0.0
            if _grow(_cap, _free) <= _target:
                return _cap
            if _free > 0:
                _e1 = _target / _rs if _rs > 0 else _cap
                if _e1 * _rl <= _free:
                    return _e1
                return (_target + _free) / max(1, _rs + _rl)
            return _target / max(1, _rs + _rl)

        # (a) Padding doc o bang (tran: moi phia <= 4.0pt)
        _dpad = _solve(_need, 2.0 * max(0.0, 4.0 - _PAD), _freeL) / 2.0
        _rem = _need - _grow(2.0 * _dpad, _freeL)
        # (b) Khoang cach giua cac khoi
        _dmsp = _dtsp = _disp = _dcsp = 0.0
        if _rem > 0:
            _dmsp = min(14.0, _rem)
            _rem -= _dmsp
        if _rem > 0:
            _dtsp = min(6.0, _rem)
            _rem -= _dtsp
        if _rem > 0:
            _disp = min(8.0, (_rem + _freeR) / 2.0)
            _rem -= max(0.0, 2.0 * _disp - _freeR)
            _freeR = max(0.0, _freeR - 2.0 * _disp)
        if _rem > 0:
            _dcsp = min(4.0, (_rem + _freeR) / 4.0)
            _rem -= max(0.0, 4.0 * _dcsp - _freeR)
            _freeR = max(0.0, _freeR - 4.0 * _dcsp)
        # (c) Leading dong chu than bang (tran tong <= 11.5pt)
        _freeL2 = max(0.0, _freeL - 2.0 * _dpad * _rl)
        _dlead = _solve(_rem, max(0.0, 11.5 - _LEAD), _freeL2)
        _rem -= _grow(_dlead, _freeL2)
        # (d) Tang co hinh cot phai (giu nguyen ti le, tran 80mm)
        _iw = _IW0
        if _rem > 0 and _hi > 1:
            _iw = min(80.0, _IW0 * (1.0 + (_rem + _freeR) / _hi))
        # Can bang 2 cot bang chinh: cot phai con thieu so voi cot
        # trai (sau gian dong) thi bu bang spacer/tieu de/co hinh cot
        # phai — mien phi ve tong chieu cao vi cot trai dang cao nhat,
        # chi lap khoang trong trong o ben phai.
        _gL = (2.0 * _dpad + _dlead) * _rl
        _gR = 2.0 * _disp + 4.0 * _dcsp + (_iw / _IW0 - 1.0) * _hi
        _short = (_hl + _gL) - (_hr + _gR)
        if _short > 1.0:
            _add = min(8.0 - _disp, _short / 2.0)
            if _add > 0:
                _disp += _add
                _short -= 2.0 * _add
            if _short > 1.0:
                _add = min(4.0 - _dcsp, _short / 4.0)
                if _add > 0:
                    _dcsp += _add
                    _short -= 4.0 * _add
            if _short > 1.0 and _hi > 1:
                _iw = min(80.0, _iw + _IW0 * _short / _hi)
        _arg = (_PAD + _dpad, _HPAD + _dpad, _LEAD + _dlead,
                _TSP + _dtsp, _CSP + _dcsp, _ISP + _disp,
                _MSP + _dmsp, _iw)
        # Build ban gian + hieu chinh ti le toi da 2 vong
        _pgc, _gapc, _ic = _try(*_arg, _safe=True)
        for _rnd in range(2):
            if _pgc == 99 or _pgc == 1 and _gapc is not None and (
                    2.5 <= _gapc <= 12.0):
                break
            if _pgc != 1:
                _fac = 0.55
            elif _gapc is not None:
                _gain = _gap - _gapc
                if _gain <= 1.0:
                    break
                _fac = max(0.4, min(1.8, (_gap - _TARGET) / _gain))
            else:
                break
            _arg = _scaled(_arg, _fac)
            _pgc, _gapc, _ic = _try(*_arg, _safe=True)
    _ok = [c for c in _cands if c[0] == 1 and c[1] is not None]
    if _ok:
        _ok.sort(key=lambda c: c[1])
        _best = _ok[0]
    elif _cands:
        _best = _cands[0]
    else:
        _best = (1, None, b"")
    if hasattr(filepath, "write"):
        filepath.write(_best[2])
    else:
        with open(filepath, "wb") as _fh:
            _fh.write(_best[2])
    return _best[0]



def export_ec2_summary_pdf(sec, inp, ec2_res, conc, steel, filepath,
                           case_info=None, sec_img_path=None,
                           chart_pngs=None, shear_info=None,
                           slend_res=None, tied=None, fyk_sw=None,
                           show_compression: bool = True):
    """Xuat PDF tom tat EC2 — LUON dung 1 trang A4.

    Thu cac muc nen layout tu nhe den manh (giam le tren/duoi, nen
    padding/leading, thu nho hinh cot phai o muc cao) va lay muc dau
    tien cho ra dung 1 trang. Moi hang theo dan y deu giu nguyen o
    moi muc nen. So lieu/ket luan khong doi.
    """
    import io as _io
    _buf = None
    for _lvl in range(4):
        _buf = _io.BytesIO()
        _pages = _export_ec2_summary_pdf_impl(
            sec, inp, ec2_res, conc, steel, _buf,
            case_info=case_info, sec_img_path=sec_img_path,
            chart_pngs=chart_pngs, shear_info=shear_info,
            slend_res=slend_res, tied=tied, fyk_sw=fyk_sw,
            show_compression=show_compression, _level=_lvl)
        if _pages <= 1:
            break
    with open(filepath, "wb") as _f:
        _f.write(_buf.getvalue())
    return filepath
