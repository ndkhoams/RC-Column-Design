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


def _fm(x):
    """Định dạng cường độ tra bảng/nhập liệu: in ĐÚNG giá trị thật, cắt số 0
    thừa ở cuối (27.579 -> '27.579', 420 -> '420'). Không dùng cho giá trị
    suy ra bằng phép chia/công thức."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    if not _m.isfinite(v):
        return "—"
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _fm_m(v_m):
    """Chiều dài theo MÉT: tối đa 3 số thập phân, cắt 0 thừa ở cuối
    (10.16 -> '10.16', 1.26 -> '1.26', 4.64 -> '4.64', 5.8 -> '5.8').
    Chỉ dùng cho hiển thị chiều dài cột/chiều dài tính toán ở mục 5."""
    try:
        v = float(v_m)
    except (TypeError, ValueError):
        return "—"
    if not _m.isfinite(v):
        return "—"
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _f_dc(dc):
    try:
        if dc is None or not _m.isfinite(float(dc)):
            return "∞"
    except (TypeError, ValueError):
        return "∞"
    return f"{float(dc):.3f}"


def _aci_charts_png(sec, conc, steel, aci_res, inp, tied,
                    mc2=None, mc3=None):
    """Tự vẽ 2 biểu đồ ACI -> (png_nm_alpha, png_m2m3) bytes.

    Dùng figure cao (5.0 x 5.2) để trục tung (trục y) giãn ra tự nhiên,
    không bị dẹt. Khi nhúng vào PDF giữ đúng tỉ lệ gốc bằng PIL.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = []
    _m2 = mc2 if mc2 is not None else inp.Mx
    _m3 = mc3 if mc3 is not None else inp.My
    for draw_fn in (draw_aci_nm_alpha_ax, draw_aci_m2m3_ax):
        fig = plt.figure(figsize=(3.2, 3.2))
        ax = fig.add_subplot(111)
        draw_fn(ax, sec, conc, steel, aci_res, inp.N, _m2, _m3,
                tied=tied)
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


def _export_aci_summary_pdf_impl(sec, inp, aci_res, conc, steel, tied, filepath,
                           case_info=None, mm_res=None, sec_img_path=None, chart_pngs=None,
                           shear_info=None, show_compression: bool = True, _level: int = 0):
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
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
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
    def _mk(_PAD, _HPAD, _LEAD, _TSP, _CSP, _ISP, _MSP, _IW):

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
        st_val = ParagraphStyle("val", parent=st_cell, alignment=TA_RIGHT)
        st_val_b = ParagraphStyle("val_b", parent=st_cell_b, alignment=TA_RIGHT)
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
            t = Table(data, colWidths=[55 * mm, 35 * mm], hAlign="LEFT")
            style = [
                ("SPAN", (0, 0), (1, 0)),
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

        _alpha = _m.degrees(_m.atan2(inp.Mx, inp.My)) % 360.0 \
            if abs(inp.Mx) + abs(inp.My) > 1e-9 else 0.0
        _dc = aci_res.get("dc", 0)
        _fs = aci_res.get("fs", 0) or 0
        _dc = aci_res.get("dc", 0) or 0
        if not _fs and _dc and _dc > 1e-9:
            _fs = 1.0 / _dc
        _ok_txt = "<b>ĐẠT</b>" if aci_res.get("ok") else "<b>KHÔNG ĐẠT</b>"
        tie_txt = "Đai rời (tied)" if tied else "Đai xoắn (spiral)"
        _fyt = aci_res.get("fyt")
        if _fyt is None:
            _fyt = getattr(inp, "fyt", None) or steel.fy

        # ===== Cột trái (dan y user chot 2026-10-21, khung nhu TCVN) =====
        left_flow = []
        left_flow.append(_sec_table("THÔNG TIN CHUNG", [
            ("Tiêu chuẩn", "ACI 318-19"),
            ("Cấu kiện", _ck_name or "—"),
        ]))
        # VAT LIEU: [f'c, Ec, fy, fyt, Es] — "Loai cot dai" chuyen xuong
        # dau bang kiem tra cat (xem phan cat ben duoi).
        left_flow.append(_sec_table("VẬT LIỆU", [
            ("Cường độ bê tông, f'c", f"{_fm(conc.fc)} MPa"),
            ("Mô đun đàn hồi bê tông, Ec", f"{conc.Ec:.0f} MPa"),
            ("Cường độ thép dọc, fy", f"{_fm(steel.fy)} MPa"),
            ("Cường độ thép đai, fyt", f"{_fm(_fyt)} MPa"),
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
            ("Lực dọc tính toán, Pu", f"{inp.N:.1f} kN"),
            ("Mômen ban đầu, M2, M3", f"{inp.Mx:.1f} / {inp.My:.1f} kNm"),
        ]))
        # CHIỀU DÀI TÍNH TOÁN & PHÓNG ĐẠI MÔMEN — chi doc tu dict ket
        # qua cua _aci_calculate_full (mm2/mm3, L0, delta, klu_r) va
        # mm_res; khong tinh cong thuc moi o tang PDF.
        _mmr = mm_res or {}
        _mm2d = aci_res.get("mm2") or _mmr.get("dir2") or {}
        _mm3d = aci_res.get("mm3") or _mmr.get("dir3") or {}
        _L0_2 = aci_res.get("L0_2") or _mmr.get("L0_2")
        _L0_3 = aci_res.get("L0_3") or _mmr.get("L0_3")
        _k2v = _mmr.get("k2", 1.0)
        _k3v = _mmr.get("k3", 1.0)
        _len_rows = [
            ("Chiều dài cột, L2, L3",
             f"{_fm_m(inp.Lx)} / {_fm_m(inp.Ly)} m"),
            ("Hệ số chiều dài tính toán, k2, k3",
             f"{_f(_k2v, 2)} / {_f(_k3v, 2)}"),
        ]
        if _L0_2 and _L0_3:
            _len_rows.append(
                ("Chiều dài không giằng, Lu2, Lu3",
                 f"{_fm_m(float(_L0_2))} / {_fm_m(float(_L0_3))} m"))
        _klr2 = aci_res.get("klu_r2")
        _klr3 = aci_res.get("klu_r3")
        if _klr2 and _klr3:
            _len_rows.append(
                ("Độ mảnh, kLu/r2, kLu/r3",
                 f"{_f(_klr2, 1)} / {_f(_klr3, 1)}"))
        _pc2 = _mm2d.get("Pc_kN")
        _pc3 = _mm3d.get("Pc_kN")
        if _pc2 is not None and _pc3 is not None:
            _len_rows.append(
                ("Lực tới hạn Euler, Pc2, Pc3",
                 f"{_f(_pc2, 0)} / {_f(_pc3, 0)} kN"))
        _dl2 = aci_res.get("delta2", _mm2d.get("delta_ns"))
        _dl3 = aci_res.get("delta3", _mm3d.get("delta_ns"))
        if _dl2 is not None and _dl3 is not None:
            _len_rows.append(
                ("Hệ số phóng đại mômen, δns2, δns3",
                 f"{_f(_dl2, 3)} / {_f(_dl3, 3)}"))
        _cm2 = _mm2d.get("Cm")
        _cm3 = _mm3d.get("Cm")
        if _cm2 is not None and _cm3 is not None:
            _len_rows.append(
                ("Hệ số mômen tương đương, Cm2, Cm3",
                 f"{_f(_cm2, 2)} / {_f(_cm3, 2)}"))
        left_flow.append(_sec_table(
            "CHIỀU DÀI TÍNH TOÁN &amp; PHÓNG ĐẠI MÔMEN", _len_rows))
        # KẾT QUẢ KIỂM TRA KHẢ NĂNG CHỊU LỰC
        _BN = aci_res.get("BN", 0)
        _Bx = aci_res.get("Bx", 0)
        _By = aci_res.get("By", 0)
        _Mb_aci = _m.hypot(_Bx, _By)
        _M2s = aci_res.get("M2_mag", _mmr.get("Mc2"))
        _M3s = aci_res.get("M3_mag", _mmr.get("Mc3"))
        if _M2s is None:
            _M2s = inp.Mx
        if _M3s is None:
            _M3s = inp.My
        _alpha_r = aci_res.get("alpha_deg")
        if _alpha_r is None:
            _alpha_r = _m.degrees(_m.atan2(_M2s, _M3s)) % 360.0 \
                if abs(_M2s) + abs(_M3s) > 1e-9 else 0.0
        _Ma_aci = aci_res.get("Malpha")
        if _Ma_aci is None:
            _Ma_aci = _m.hypot(_M2s, _M3s)
        left_flow.append(_sec_table("KẾT QUẢ KIỂM TRA KHẢ NĂNG CHỊU LỰC", [
            ("Lực dọc tính toán, Pu", f"{inp.N:.1f} kN"),
            ("Mômen sau phóng đại, M2*, M3*",
             f"{_M2s:.1f} / {_M3s:.1f} kNm"),
            (f"Mômen tổng kiểm tra, Mα (α = {_alpha_r:.1f}°)",
             f"{_Ma_aci:.1f} kNm"),
            ("Lực dọc giới hạn, φPn", f"{_BN:.1f} kN"),
            ("Mômen giới hạn, Mα,u", f"{_Mb_aci:.1f} kNm"),
            ("Tỉ số sử dụng khả năng chịu lực, D/C (FS)",
             f"{_dc:.3f} ({_fs:.2f})"),
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

        _blkA, _blkB, _blkC = [], [], []
        try:
            # Vùng nén (giống app)
            import sys as _sys
            _pdf_exp = _sys.modules.get("rc_column.pdf_export")
            if _pdf_exp is None:
                from rc_column import pdf_export as _pdf_exp
            _BN = (aci_res.get("BN", 0) or 0) if isinstance(aci_res, dict) else 0
            _Bx = (aci_res.get("Bx", 0) or 0) if isinstance(aci_res, dict) else 0
            _By = (aci_res.get("By", 0) or 0) if isinstance(aci_res, dict) else 0
            _alpha = _m.degrees(_m.atan2(_Bx, _By)) if (abs(_Bx)+abs(_By)) > 1e-9 else 0.0
            _na = None
            try:
                from .aci_checker import aci_neutral_axis_at_N as _nafn
                _na = _nafn(sec, conc, steel, _BN, _alpha)
            except Exception:
                pass
            _sec_png = _pdf_exp.compression_zone_image(sec, _BN, _Bx, _By,
                                                       na_info=_na,
                                                       show_compression=show_compression)
            _blkA.append(_centered_img(_sec_png, _IW))
            # 2 biểu đồ ACI (có tiêu đề)
            _alpha_aci = _m.degrees(_m.atan2(inp.Mx, inp.My)) % 360.0 \
                if abs(inp.Mx) + abs(inp.My) > 1e-9 else 0.0
            _mm = mm_res or {}
            _pngs = _aci_charts_png(sec, conc, steel, aci_res, inp, tied,
                                    mc2=_mm.get("Mc2"), mc3=_mm.get("Mc3"))
            if _pngs and len(_pngs) >= 2:
                _blkB.append(Paragraph(
                    f"<b>Biểu đồ tương tác N-Mα</b> (α = {_alpha_aci:.1f}°)",
                    st_chart_title))
                _blkB.append(_centered_img(_pngs[0], _IW))
                _blkC.append(Paragraph(
                    f"<b>Mặt cắt M2-M3</b> (N = {inp.N:+.1f} kN)",
                    st_chart_title))
                _blkC.append(_centered_img(_pngs[1], _IW))
            elif chart_pngs and len(chart_pngs) >= 2:
                _blkB.append(Paragraph(
                    f"<b>Biểu đồ tương tác N-Mα</b> (α = {_alpha_aci:.1f}°)",
                    st_chart_title))
                _blkB.append(_centered_img(chart_pngs[0], _IW))
                _blkC.append(Paragraph(
                    f"<b>Mặt cắt M2-M3</b> (N = {inp.N:+.1f} kN)",
                    st_chart_title))
                _blkC.append(_centered_img(chart_pngs[1], _IW))
        except Exception as e:
            _blkA = [Paragraph(f"(Không vẽ được hình: {e})", st_cell)]
            _blkB, _blkC = [], []
        # --- Neo 3 khoi hinh cot phai: mat cat CAN TREN, M2-M3 CAN
        # DUOI, N-M CAN GIUA: phan chieu cao cot phai con thieu so
        # voi cot trai chia deu vao cac spacer giua cac khoi.
        def _hh(_fl):
            _t = 0.0
            for _f in _fl:
                _w2, _h2 = _f.wrap(90 * mm, 10000)
                _t += _h2
                try:
                    _t += _f.getSpaceBefore() + _f.getSpaceAfter()
                except Exception:
                    pass
            return _t
        _blocks = [_b for _b in (_blkA, _blkB, _blkC) if _b]
        _ngaps = max(0, len(_blocks) - 1)
        _extra = 0.0
        if _ngaps:
            _resid = (_hh(left_flow)
                      - sum(_hh(_b) for _b in _blocks)
                      - _ISP * _ngaps)
            _extra = max(0.0, _resid) / _ngaps
        right_flow = []
        for _i, _b in enumerate(_blocks):
            if _i:
                right_flow.append(Spacer(1, _ISP + _extra))
            right_flow.extend(_b)


        t_main = Table([[left_flow, right_flow]],
                       colWidths=[90 * mm, 90 * mm], hAlign="CENTER")
        t_main.setStyle(TableStyle([
            ("VALIGN", (0, 0), (0, 0), "TOP"),
            ("VALIGN", (1, 0), (1, 0), "TOP"),
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
        # Nguyên tắc "tính 1 lần": ưu tiên dùng kết quả đã tính từ app (aci_res)
        from reportlab.platypus import KeepTogether
        _sw_story = []
        # Lấy shear đã tính sẵn từ aci_res (do _aci_calculate_full tính)
        _precalc_sh2 = (aci_res.get("shear2") or {}) if isinstance(aci_res, dict) else {}
        _precalc_sh3 = (aci_res.get("shear3") or {}) if isinstance(aci_res, dict) else {}
        _use_precalc = bool(_precalc_sh2 or _precalc_sh3)
        try:
            from .aci_checker import aci_shear_check
            from .sections import bar_area
            _sw_dia = getattr(inp, "sw_dia", 8)
            _sw_s = getattr(inp, "sw_spacing", 200)
            _sw_legs = getattr(inp, "sw_legs", 2)
            # Đai giữa (nếu có)
            _m2_dia = getattr(inp, "swm2_dia", 0) or 0
            _m2_s = getattr(inp, "swm2_spacing", 0) or 0
            _m2_legs = getattr(inp, "swm2_legs", 0) or 0
            _m3_dia = getattr(inp, "swm3_dia", 0) or 0
            _m3_s = getattr(inp, "swm3_spacing", 0) or 0
            _m3_legs = getattr(inp, "swm3_legs", 0) or 0
            _Av_outer = _sw_legs * bar_area(_sw_dia)
            _Av_m2 = _m2_legs * bar_area(_m2_dia) if _m2_dia > 0 else 0
            _Av_m3 = _m3_legs * bar_area(_m3_dia) if _m3_dia > 0 else 0
            _Av2 = _Av_outer + _Av_m2
            _Av3 = _Av_outer + _Av_m3
            if _Av_m2 > 0:
                _sw_txt2 = f"{_sw_legs:.0f}φ{_sw_dia:.0f} a{_sw_s:.0f} + {_m2_legs:.0f}φ{_m2_dia:.0f} a{_m2_s:.0f}"
            else:
                _sw_txt2 = f"{_sw_legs:.0f}φ{_sw_dia:.0f} a{_sw_s:.0f}"
            if _Av_m3 > 0:
                _sw_txt3 = f"{_sw_legs:.0f}φ{_sw_dia:.0f} a{_sw_s:.0f} + {_m3_legs:.0f}φ{_m3_dia:.0f} a{_m3_s:.0f}"
            else:
                _sw_txt3 = f"{_sw_legs:.0f}φ{_sw_dia:.0f} a{_sw_s:.0f}"
            _data = [
                [Paragraph("<b>KIỂM TRA KHẢ NĂNG CHỊU CẮT</b>", st_hdr_left),
                 Paragraph("<b>Phương V2</b>", st_hdr),
                 Paragraph("<b>Phương V3</b>", st_hdr)],
            ]
            # "Loai cot dai" (truoc o khoi VAT LIEU) dat o dau bang cat,
            # gia tri span ca 2 cot phuong.
            _data.append([Paragraph("Loại cốt đai", st_lbl),
                          Paragraph(tie_txt, st_cell),
                          Paragraph("", st_cell)])
            _rows = []
            # CHỈ dùng kết quả đã tính từ app (nguyên tắc "tính 1 lần") - KHÔNG tính lại
            # Ưu tiên: 1) shear_info từ GUI, 2) aci_res["shear2"/"shear3"] từ _aci_calculate_full
            _si = shear_info if isinstance(shear_info, dict) else {}
            if "dir2" in _si and "dir3" in _si:
                _r2 = _si.get("dir2", {})
                _r3 = _si.get("dir3", {})
                _q2, _q3 = inp.Q2, inp.Q3
            else:
                # Dùng precalc từ aci_res - KHÔNG gọi aci_shear_check
                _r2 = _precalc_sh2
                _r3 = _precalc_sh3
                _q2, _q3 = inp.Q2, inp.Q3
                # Nếu không có precalc, để trống (không tính lại)
            _d2 = _t3 - inp.cover - _sw_dia - 12
            _d3 = _t2 - inp.cover - _sw_dia - 12
            _b2, _b3 = _t2, _t3
            # Ưu tiên thông số hiển thị đã tính 1 lần (shear_disp của
            # _aci_calculate_full) để PDF khớp tab tuyệt đối, không dựng lại ở đây
            _disp = aci_res.get("shear_disp") if isinstance(aci_res, dict) else None
            if isinstance(_disp, dict) and "2" in _disp and "3" in _disp:
                _b2 = _disp["2"].get("b", _b2)
                _d2 = _disp["2"].get("d", _d2)
                _Av2 = _disp["2"].get("Av", _Av2)
                _sw_txt2 = _disp["2"].get("sw_txt", _sw_txt2)
                _b3 = _disp["3"].get("b", _b3)
                _d3 = _disp["3"].get("d", _d3)
                _Av3 = _disp["3"].get("Av", _Av3)
                _sw_txt3 = _disp["3"].get("sw_txt", _sw_txt3)
            _sw_lines = [
                ("Thép đai bố trí", _sw_txt2, _sw_txt3),
                ("Lực cắt tính toán, Vu",
                 f"{abs(_q2):.1f} kN", f"{abs(_q3):.1f} kN"),
                ("Kích thước tiết diện, b × d",
                 f"{_b2:.0f} × {_d2:.0f} mm", f"{_b3:.0f} × {_d3:.0f} mm"),
                ("Av = n × φ",
                 f"{_Av2:.0f} mm²", f"{_Av3:.0f} mm²"),
                ("Vc = max[0.17λ√f'c, 0.66λsλ(ρw)⅓√f'c]×bw×d (ACI 22.5.5)",
                 f"{_r2['Vc_kN']:.1f} kN",
                 f"{_r3['Vc_kN']:.1f} kN"),
                ("Vs = Av×fyt×d/s (ACI 22.5.8)",
                 f"{_r2['Vs_kN']:.1f} kN",
                 f"{_r3['Vs_kN']:.1f} kN"),
                ("φVn = φ×(Vc+Vs)", f"{_r2['phi_Vn_kN']:.1f} kN",
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
            # hAlign CENTER co y: bang rong dung khung trang
            # (180mm) nhu bang chinh 2 cot; frame SimpleDocTemplate
            # co padding ngang 6pt nen bang can TRAI bi day vao 6pt
            # so voi bang chinh — can giua de mep trai trung khit.
            t_sw = Table(_data, colWidths=[90 * mm, 45 * mm, 45 * mm],
                         hAlign="CENTER")
            _st = [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("SPAN", (1, 1), (2, 1)),
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
                                _msp, _iw)
            _buf = _io.BytesIO()
            _doc = SimpleDocTemplate(
                _buf, pagesize=A4, leftMargin=15 * mm,
                rightMargin=15 * mm, topMargin=_MRG * mm,
                bottomMargin=_MRG * mm, title="Kết quả kiểm tra cột BTCT (ACI 318-19)")
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



def export_aci_summary_pdf(sec, inp, aci_res, conc, steel, tied, filepath,
                           case_info=None, mm_res=None, sec_img_path=None,
                           chart_pngs=None, shear_info=None,
                           show_compression: bool = True):
    """Xuat PDF tom tat ACI 318-19 — LUON dung 1 trang A4.

    Thu cac muc nen layout tu nhe den manh (giam le tren/duoi, nen
    padding/leading, thu nho hinh cot phai o muc cao) va lay muc dau
    tien cho ra dung 1 trang. Moi hang theo dan y deu giu nguyen o
    moi muc nen. So lieu/ket luan khong doi.
    """
    import io as _io
    _buf = None
    for _lvl in range(4):
        _buf = _io.BytesIO()
        _pages = _export_aci_summary_pdf_impl(
            sec, inp, aci_res, conc, steel, tied, _buf,
            case_info=case_info, mm_res=mm_res, sec_img_path=sec_img_path,
            chart_pngs=chart_pngs, shear_info=shear_info,
            show_compression=show_compression, _level=_lvl)
        if _pages <= 1:
            break
    with open(filepath, "wb") as _f:
        _f.write(_buf.getvalue())
    return filepath
