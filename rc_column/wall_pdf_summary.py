"""PDF tóm tắt vách TCVN — ĐÚNG 1 trang A4.

Bố cục bám export_summary_pdf của cột (pdf_export.py): tiêu đề,
bảng 2 cột chính (trái = các bảng thông số, phải = 3 hình: mặt cắt
có dim + vùng nén, N–Mα, M2–M3), bảng cắt full-width ở đáy, ép 1
trang bằng thang thu layout + giãn lấp đầy (tăng dần cỡ hình /
padding / khoảng cách cho tới khi khoảng trống cuối trang nhỏ).

Mọi số đọc từ dict kết quả wall_tcvn_full đã lưu, không tính lại.
Hình mặt cắt dùng builder vẽ vách hiện có (wall_pdf_figs, kèm
FLOOR 6.0px cho thép — xem wall_pdf_figs); N–Mα vẽ đúng cách tab
Kết quả; M2–M3 dùng wall_m2m3_figure.
"""

import io
import math
import os



def _fm(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(v):
        return "—"
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _f(x, nd=1):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(v):
        return "∞" if v > 0 else "—"
    return f"{v:,.{nd}f}"


def _img_from_bytes(png_bytes, w_mm, max_h=None):
    """Image giữ tỉ lệ gốc; ảnh dọc (mặt cắt xoay 90°) thu theo
    chiều cao tối đa để không phá layout 1 trang."""
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


def _impl(full, buf, member_name, show_compression, pad, img_w, spacer):
    """Build 1 bản PDF với tham số layout cho trước. Trả về
    (số trang, khoảng trống cuối trang theo pt, hoặc None)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Image, Table, TableStyle, KeepTogether)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from .pdf_export import _find_font, _find_font_bold
    from .wall_pdf_figs import wall_nm_alpha_png, wall_section_png
    from .wall_m2m3 import wall_m2m3_figure

    FN, FNB = "Helvetica", "Helvetica-Bold"
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", _find_font()))
        FN = "DejaVu"
    except Exception:
        pass
    try:
        pdfmetrics.registerFont(TTFont("DejaVuB", _find_font_bold()))
        FNB = "DejaVuB"
    except Exception:
        pass

    st_title = ParagraphStyle("t", fontName=FNB, fontSize=14,
                              alignment=TA_CENTER, spaceAfter=4)
    st_sub = ParagraphStyle("sub", fontName=FN, fontSize=8,
                            alignment=TA_CENTER, spaceAfter=6,
                            textColor=HexColor("#6B7280"))
    st_cell = ParagraphStyle("c", fontName=FN, fontSize=7, leading=9)
    st_cell_b = ParagraphStyle("cb", fontName=FNB, fontSize=7, leading=9)
    st_lbl = ParagraphStyle("lbl", parent=st_cell, alignment=TA_LEFT)
    st_val = ParagraphStyle("val", parent=st_cell, alignment=TA_RIGHT)
    st_val_b = ParagraphStyle("val_b", parent=st_cell_b,
                              alignment=TA_RIGHT)
    st_sec_title = ParagraphStyle("sectitle", parent=st_cell_b,
                                  alignment=TA_LEFT)
    st_chart = ParagraphStyle("ct", parent=st_cell_b, alignment=TA_CENTER,
                              fontSize=8, spaceBefore=2, spaceAfter=2)
    st_note = ParagraphStyle("note", parent=st_cell, fontSize=7,
                             leading=9, textColor=HexColor("#6B7280"))
    st_hdr = ParagraphStyle("hdr", fontName=FNB, fontSize=7, leading=9,
                            alignment=TA_CENTER)
    st_hdr_left = ParagraphStyle("hdr_left", parent=st_hdr,
                                 alignment=TA_LEFT)

    def sec_table(title, rows):
        data = [[Paragraph(f"<b>{title}</b>", st_sec_title)]]
        for lbl, val in rows:
            vs = str(val)
            if "<b>" in vs:
                vc = vs.replace("<b>", "").replace("</b>", "")
                data.append([Paragraph(lbl, st_lbl),
                             Paragraph(vc, st_val_b)])
            else:
                data.append([Paragraph(lbl, st_lbl),
                             Paragraph(vs, st_val)])
        t = Table(data, colWidths=[55 * mm, 35 * mm], hAlign="LEFT")
        style = [
            ("SPAN", (0, 0), (1, 0)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), pad),
            ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, HexColor("#111111")),
            ("BOTTOMPADDING", (0, 0), (-1, 0), pad + 1.0),
        ]
        for i in range(1, len(data)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i),
                              HexColor("#F2F2F2")))
        t.setStyle(TableStyle(style))
        return t

    def centered_img(png_bytes, w_mm):
        im = _img_from_bytes(png_bytes, w_mm * mm, 170 * mm)
        t = Table([[im]], colWidths=[90 * mm], hAlign="CENTER")
        t.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        return t

    winp = full["winp"]
    sec = full["sec"]
    meta = full.get("meta") or {}
    sl = full["slend"]
    conc = sec.concrete
    steel = sec.steel
    mode = str(meta.get("steel_mode") or "boundary")
    mode_txt = {"perimeter": "Phân bố đều theo chu vi",
                "boundary": "Tập trung vùng biên"}.get(mode, "Lát 1 cũ")
    sh = full.get("shear_in") or {}
    shp = sh.get("parts") or {}
    sho = full.get("shear_out") or {}
    shop = sho.get("parts") or {}
    ok_nm = bool(full["ok"])
    fs_txt = f"{float(full['fs']):.2f}" if math.isfinite(
        float(full["fs"])) else "∞"

    left_flow = []
    left_flow.append(sec_table("THÔNG TIN CHUNG", [
        ("Tiêu chuẩn", "TCVN 5574:2018"),
        ("Cấu kiện", (str(member_name).upper() if member_name else "—")),
        ("Loại vách", "Vách phẳng chữ nhật đặc (GĐ1)"),
        ("Chế độ thép dọc", mode_txt),
        ("Xoay tiết diện",
         f"{int(getattr(winp, 'rot_deg', 0) or 0) % 360}°"),
    ]))
    left_flow.append(sec_table("VẬT LIỆU", [
        ("Bê tông", conc.grade.name),
        ("Cường độ chịu nén, R<sub>b</sub>",
         f"{_fm(conc.Rb)} MPa"),
        ("Cường độ chịu kéo, R<sub>bt</sub>",
         f"{_fm(conc.Rbt)} MPa"),
        ("Mô đun đàn hồi, E<sub>b</sub>", f"{_fm(conc.Eb)} MPa"),
        ("Cốt thép dọc", steel.grade.name),
        ("Cường độ chịu kéo, R<sub>s</sub>",
         f"{_fm(steel.Rs)} MPa"),
        ("Cường độ chịu nén, R<sub>sc</sub>",
         f"{_fm(steel.Rsc)} MPa"),
        ("Mô đun đàn hồi, E<sub>s</sub>", f"{_fm(steel.Es)} MPa"),
    ]))
    left_flow.append(sec_table("TIẾT DIỆN", [
        ("Kích thước Lw × tw",
         f"{float(sec.cx):.0f} × {float(sec.cy):.0f} mm"),
        ("Diện tích bê tông, A<sub>g</sub>",
         f"{float(sec.cx) * float(sec.cy):,.0f} mm²"),
        # Hàng cover chỉ còn c (ghi chú user 2026-10-25 gạch bỏ
        # "(c_dọc = ...)" ở PDF tóm tắt vách; c_dọc vẫn do engine
        # tự tính và vẫn hiện ở PDF chi tiết/tab Chi tiết).
        ("Lớp bảo vệ cốt đai, c",
         f"{float(winp.cover):.0f} mm"),
    ]))
    _parts = []
    from collections import Counter
    _cnt = Counter(r.dia for r in sec.rebars)
    for d in sorted(_cnt, reverse=True):
        _parts.append(f"{_cnt[d]}-d{d:.0f}")
    left_flow.append(sec_table("BỐ TRÍ CỐT THÉP DỌC", [
        ("Số lượng thép", " + ".join(_parts)),
        ("Diện tích thép, A<sub>s</sub>",
         f"{float(sec.steel_area):,.0f} mm²"),
        ("Hàm lượng thép dọc, μ",
         f"{float(sec.reinforcement_ratio) * 100:.2f}%"),
    ]))
    left_flow.append(sec_table("NỘI LỰC KIỂM TRA", [
        ("Lực dọc tính toán, N", f"{float(full['N']):.1f} kN"),
        ("Mô men ban đầu, M2, M3",
         f"{float(full['M_out']):.1f} / {float(full['M_in']):.1f} kN·m"),
        ("Lực cắt, V2, V3",
         f"{float(full['V_in']):.1f} / {float(full['V_out']):.1f} kN"),
    ]))
    left_flow.append(sec_table(
        "CHIỀU DÀI TÍNH TOÁN &amp; HIỆU ỨNG UỐN DỌC", [
            ("Chiều cao Lx, Ly",
             f"{float(sl.get('Lx_m', 0)):.2f} / "
             f"{float(sl.get('Ly_m', 0)):.2f} m"),
            ("Hệ số ψx, ψy",
             f"{float(sl.get('psi_x', 0)):.2f} / "
             f"{float(sl.get('psi_y', 0)):.2f}"),
            ("Chiều dài tính toán, L0x, L0y",
             f"{float(sl.get('l0_in', 0)) / 1000.0:.2f} / "
             f"{float(sl.get('l0_out', 0)) / 1000.0:.2f} m"),
            ("Độ mảnh, λx, λy (giới hạn 120 — §10.2.2)",
             f"{float(sl.get('lambda_in', 0)):.2f} / "
             f"{float(sl.get('lambda_out', 0)):.2f}"),
            ("Kết luận độ mảnh (§10.2.2)",
             ("ĐẠT — λx, λy ≤ 120"
              if float(sl.get('lambda_in', 0)) <= 120.0
              and float(sl.get('lambda_out', 0)) <= 120.0
              else "KHÔNG ĐẠT — có λ > 120")),
            ("Độ lệch tâm ban đầu, e0x, e0y",
             f"{float(full['e0_in']):.1f} / "
             f"{float(full['e0_out']):.1f} mm"),
            ("Lực tới hạn Euler, Ncr,x, Ncr,y",
             f"{float(sl.get('Ncr_in', 0)):,.0f} / "
             f"{float(sl.get('Ncr_out', 0)):,.0f} kN"),
            ("Hệ số uốn dọc, ηx, ηy",
             f"{float(sl.get('factor_in', 1)):.3f} / "
             f"{float(sl.get('factor_out', 1)):.3f}"),
        ]))
    _ok_txt = "<b>ĐẠT</b>" if ok_nm else "<b>KHÔNG ĐẠT</b>"
    res_rows = [
        ("Mô men sau uốn dọc, M2*, M3*",
         f"{float(full['M_out_d']):.1f} / "
         f"{float(full['M_in_d']):.1f} kN·m"),
        (f"Mô men tổng, Mα (α = {float(full['alpha_deg']):.1f}°)",
         f"{float(full['Malpha']):.1f} kN·m"),
        ("Lực dọc giới hạn, BN",
         f"{float(full['BN']):.1f} kN"),
        ("Mô men giới hạn tại N, Mα,u",
         f"{float(full['M_capacity']):.1f} kN·m"),
        ("Tỉ số sử dụng, D/C (FS)",
         f"{float(full['dc']):.3f} ({fs_txt})"),
        ("Kết luận N–M", _ok_txt),
    ]
    left_flow.append(sec_table("KẾT QUẢ KIỂM TRA KHẢ NĂNG CHỊU LỰC",
                               res_rows))

    # Cột phải: 3 hình (mặt cắt neo trên, N–Mα giữa, M2–M3 dưới
    # theo quy ước neo của PDF tóm tắt cột — spacer giãn đều).
    right_flow = []
    try:
        _sec_png = wall_section_png(
            full, show_compression=show_compression)
        right_flow.append(centered_img(_sec_png, img_w))
    except Exception as ex:
        right_flow.append(Paragraph(f"(Không vẽ được mặt cắt: {ex})",
                                    st_cell))
    right_flow.append(Spacer(1, spacer))
    try:
        right_flow.append(Paragraph(
            f"<b>Biểu đồ tương tác N–Mα</b> "
            f"(α = {float(full['alpha_deg']):.1f}°)", st_chart))
        right_flow.append(centered_img(wall_nm_alpha_png(full), img_w))
        # KHÔNG còn dòng kết luận dưới biểu đồ N–Mα (ghi chú user
        # 2026-10-25 gạch bỏ): kết luận N–M vẫn ở bảng KẾT QUẢ
        # bên trái (hàng "Kết luận N–M").
    except Exception as ex:
        right_flow.append(Paragraph(
            f"(Không vẽ được N–Mα: {ex})", st_cell))
    right_flow.append(Spacer(1, spacer))
    if full.get("m2m3") is not None:
        try:
            right_flow.append(Paragraph(
                f"<b>Mặt cắt M2–M3</b> "
                f"(N = {float(full['m2m3']['N_level']):,.0f} kN)",
                st_chart))
            right_flow.append(centered_img(
                wall_m2m3_figure(full), img_w))
            # KHÔNG còn caption diễn giải dưới biểu đồ M2–M3
            # (ghi chú user 2026-10-25 gạch bỏ cùng với dòng kết
            # luận N–Mα): biểu đồ M2–M3 vẫn giữ nguyên, chỉ là
            # lát cắt tại N = BN của cùng khả năng N–M.
        except Exception as ex:
            right_flow.append(Paragraph(
                f"(Không vẽ được M2–M3: {ex})", st_cell))

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
        "KIỂM TRA KHẢ NĂNG CHỊU LỰC VÁCH BÊ TÔNG CỐT THÉP", st_title))
    story.append(Paragraph(
        "(TCVN 5574:2018 — vách chữ nhật đặc, GĐ1)", st_sub))
    story.append(t_main)
    story.append(Spacer(1, 4))
    # Bảng cắt full-width, 3 cột (ghi chú user 2026-10-25: "check 2
    # cột trong và ngoài riêng"): [Hạng mục | Trong MP | Ngoài MP]
    # thay cho 2 cột với các hàng trong/ngoài xếp chồng dọc. Chỉ
    # đổi trình bày — mọi số lấy từ cùng dict sh/shp (trong) và
    # sho/shop (ngoài); hàng nào tóm tắt trước đây không có số
    # ngoài MP thì ô ngoài là "—". Tóm tắt chỉ hiện giá trị;
    # công thức → thay số → kết luận riêng ở PDF chi tiết.
    st_cell_c = ParagraphStyle("cc", parent=st_cell,
                               alignment=TA_CENTER)
    st_cell_bc = ParagraphStyle("ccb", parent=st_cell_b,
                                alignment=TA_CENTER)
    st_lbl_note = ParagraphStyle("lblnote", parent=st_cell,
                                 fontSize=6, leading=7.5,
                                 textColor=HexColor("#555555"))
    sw_data = [[Paragraph("<b>KIỂM TRA KHẢ NĂNG CHỊU CẮT</b>",
                          st_hdr_left),
                Paragraph("<b>Trong mặt phẳng</b>", st_hdr),
                Paragraph("<b>Ngoài mặt phẳng</b>", st_hdr)]]
    _in_ok = sh.get("V_cap") is not None
    _out_ok = sho.get("V_cap") is not None
    _dc_sh = sh.get("dc") if _in_ok else None
    _dc_sh_txt = (f"{_dc_sh:.3f}" if _dc_sh is not None
                  and math.isfinite(float(_dc_sh)) else "∞")
    _dc_sho = sho.get("dc") if _out_ok else None
    _dc_sho_txt = (f"{_dc_sho:.3f}" if _dc_sho is not None
                   and math.isfinite(float(_dc_sho)) else "∞")
    # Hàng V_Ed: ô giá trị chỉ còn số trơn; ghi chú DCM đặt trong
    # ô nhãn (ghi chú user "ghi chú vào đây" đúng ô nhãn hàng V2,
    # không phải footnote dưới bảng) — cùng quy ước với bảng cắt
    # tab Kết quả (build_wall_shear_rows: ghi chú ở ô nhãn, ô giá
    # trị trơn, không hiện V_raw).
    _v_lbl = [Paragraph("Lực cắt tính toán, V2 / V3", st_lbl)]
    if _in_ok and sh.get("seismic_applied"):
        _v_lbl.append(Paragraph(
            f"Ghi chú: V2 đã phóng đại 1,5× theo TCVN 9386-1:2025 "
            f"§5.4.2.4(7) (DCM): {float(full['V_in']):.1f} → "
            f"{float(sh.get('V_d', full['V_in'])):.1f} kN",
            st_lbl_note))
    _v_in = (f"{float(sh.get('V_d', full['V_in'])):.1f} kN"
             if _in_ok else "— (chưa tính được)")
    _v_out = (f"{float(full['V_out']):.1f} kN "
              f"(không phóng đại; Qsw = 0 — chưa có giằng xuyên dày)"
              if _out_ok else "— (chưa tính được)")
    _dash = "—"
    # Mỗi hàng: (nhãn, trong MP, ngoài MP, in đậm 2 ô giá trị?).
    sw_rows = [
        ("Thép ngang bố trí",
         shp.get("sw_txt", "—") if _in_ok else _dash, _dash, False),
        (_v_lbl, _v_in, _v_out, False),
        ("Kích thước tiết diện, b × h<sub>0</sub>",
         (f"{shp.get('b', 0):.0f} × {shp.get('h0', 0):.0f} mm"
          if _in_ok else _dash),
         (f"{shop.get('b', 0):.0f} × {shop.get('h0', 0):.0f} mm"
          if _out_ok else _dash),
         False),
        ("A<sub>sw</sub>",
         (f"{shp.get('Asw', 0):,.0f} mm²" if _in_ok else _dash),
         _dash, False),
        ("q<sub>sw</sub> được kể",
         (f"{shp.get('qsw', 0):.1f} N/mm" if _in_ok else _dash),
         _dash, False),
        ("Hệ số φ<sub>n</sub> (§8.1.3.3.2)",
         (f"{shp.get('phi_n', 0):.3f}" if _in_ok else _dash),
         _dash, False),
        ("[Q]<sub>1</sub> (dải nén xiên, (88))",
         (f"{shp.get('Qcap1', 0):,.1f} kN" if _in_ok else _dash),
         (f"{shop.get('Qcap1', 0):,.1f} kN" if _out_ok else _dash),
         False),
        ("Q<sub>b</sub> (vết nứt xiên)",
         (f"{shp.get('Qb', 0):,.1f} kN" if _in_ok else _dash),
         (f"{shop.get('Qb', 0):,.1f} kN" if _out_ok else _dash),
         False),
        ("Q<sub>sw</sub> (vết nứt xiên)",
         (f"{shp.get('Qsw', 0):,.1f} kN" if _in_ok else _dash),
         _dash, False),
        ("[Q]<sub>2</sub> (vết nứt xiên)",
         (f"{shp.get('Qcap2', 0):,.1f} kN" if _in_ok else _dash),
         _dash, False),
        ("Khả năng chịu cắt, V<sub>cap</sub>",
         (f"{float(sh['V_cap']):,.1f} kN" if _in_ok
          else "— (chưa tính được)"),
         (f"{float(sho['V_cap']):,.1f} kN" if _out_ok
          else "— (chưa tính được)"),
         False),
        ("Tỉ số sử dụng, D/C",
         (f"{_dc_sh_txt} — "
          f"{'ĐẠT' if sh.get('ok') else 'KHÔNG ĐẠT'}"
          if _in_ok else _dash),
         (f"{_dc_sho_txt} — "
          f"{'ĐẠT' if sho.get('ok') else 'KHÔNG ĐẠT'}"
          if _out_ok else _dash),
         True),
    ]
    for _lab, _bi, _bo, _bold in sw_rows:
        _cell_lab = _lab if isinstance(_lab, list) \
            else Paragraph(_lab, st_lbl)
        _sty = st_cell_bc if _bold else st_cell_c
        sw_data.append([_cell_lab, Paragraph(_bi, _sty),
                        Paragraph(_bo, _sty)])
    t_sw = Table(sw_data, colWidths=[68 * mm, 56 * mm, 56 * mm],
                 hAlign="CENTER")
    sw_style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), pad),
        ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, HexColor("#111111")),
        ("BOTTOMPADDING", (0, 0), (-1, 0), pad + 1.0),
    ]
    for i in range(1, len(sw_data)):
        if i % 2 == 0:
            sw_style.append(("BACKGROUND", (0, i), (-1, i),
                             HexColor("#F2F2F2")))
    t_sw.setStyle(TableStyle(sw_style))
    story.append(KeepTogether(t_sw))
    # Ghi chú phạm vi soát lại sau ghi chú user 2026-10-25 (nét
    # gạch phủ toàn bộ ghi chú cũ): bỏ mệnh đề "M2–M3 diễn giải
    # lại kết luận N–M" (caption M2–M3 đã bị xóa) và bỏ câu DCM
    # (thông tin phóng đại nay nằm ở ghi chú hàng V2 trong bảng
    # cắt; cắt ngoài MP không phóng đại vẫn ghi ở ô giá trị V3).
    # Giữ: "không có kết luận chung", "kết luận riêng ở bảng cắt",
    # "Trượt mạch ngừng, vùng biên và cấu tạo: CHƯA KIỂM" và câu
    # "chưa kể phóng đại" cho trường hợp không áp DCM.
    story.append(Paragraph(
        ("Phạm vi: không có kết luận chung — N–M kết luận ở khối "
         "KẾT QUẢ, độ mảnh ở khối CHIỀU DÀI TÍNH TOÁN, "
         "cắt trong và ngoài mặt phẳng kết luận riêng ở bảng cắt. "
         "Trượt mạch ngừng, vùng biên và cấu tạo: CHƯA KIỂM."
         if sh.get("seismic_applied") else
         "Phạm vi: không có kết luận chung — N–M kết luận ở khối "
         "KẾT QUẢ, độ mảnh ở khối CHIỀU DÀI TÍNH TOÁN, "
         "cắt trong và ngoài mặt phẳng kết luận riêng ở bảng cắt. "
         "Trượt mạch ngừng, vùng biên và cấu tạo: CHƯA KIỂM. "
         "Cắt chưa kể phóng đại kháng chấn TCVN 9386-1:2025 trong lần "
         "tính này."),
        st_note))

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm,
                            rightMargin=15 * mm, topMargin=10 * mm,
                            bottomMargin=10 * mm,
                            title="Kết quả kiểm tra vách BTCT")
    doc.build(story)
    pages = getattr(doc, "page", 1)
    gap = None
    if pages == 1:
        try:
            gap = doc.frame._y - doc.frame._y1
        except Exception:
            gap = None
    return pages, gap


def _try_impl(full, member_name, show_compression, params):
    """Build thử 1 tham số layout. ReportLab raise LayoutError khi
    bảng chính cao hơn cả khung trang (không tách được) — đó cũng
    chỉ là "tham số này không cho 1 trang", không phải lỗi chết:
    trả về pages=999 để thang thu tiếp tục thu hẹp."""
    buf = io.BytesIO()
    try:
        pages, gap = _impl(full, buf, member_name, show_compression,
                           *params)
        return pages, gap, buf.getvalue(), None
    except Exception as ex:
        return 999, None, None, ex


def export_wall_summary_pdf(full, filepath: str, member_name: str = None,
                            show_compression: bool = True):
    """Xuất PDF tóm tắt vách — LUÔN đúng 1 trang A4 (ép + giãn)."""
    # Thang thu layout: thử từ vừa tới chặt, lấy bản đầu tiên 1 trang.
    ladder = [(2.0, 66.0, 2.0), (1.2, 62.0, 1.5),
              (0.8, 58.0, 1.0), (0.6, 54.0, 1.0),
              # Mức sâu cho ca mặt cắt dọc (xoay 90°): ảnh mặt cắt
              # portrait chiếm chiều cao lớn nên phải thu hình thêm.
              (0.6, 50.0, 1.0), (0.5, 46.0, 1.0),
              # Nấc sâu thêm cho 4 hàng cắt ngoài MP (lát 4 — phần 4):
              # ca xoay 90° + 4 hàng vượt 1 trang ở nấc 46 mm, vừa ở
              # 42 mm (gap ~39 pt); vòng giãn phía dưới sẽ nở lại
              # hình/padding trong khi vẫn giữ 1 trang.
              (0.5, 42.0, 1.0),
              # Nấc sâu hơn cho phần 2/7 (thêm 1 hàng kết luận độ
              # mảnh + 2 chú thích kết luận dưới biểu đồ N–Mα và
              # M2–M3): ca xoay 90° vượt 1 trang ở nấc 42 mm, phải
              # thu hình thêm mới vừa; các ca đã vừa ở nấc trên
              # không bị ảnh hưởng vì thang dừng ở nấc vừa đầu
              # tiên, vòng giãn sau đó nở lại trong khi giữ 1 trang.
              (0.5, 38.0, 1.0), (0.5, 34.0, 1.0),
              (0.4, 30.0, 1.0)]
    best = None
    best_params = None
    best_gap = None
    last_err = None
    for params in ladder:
        pages, gap, data, err = _try_impl(
            full, member_name, show_compression, params)
        if err is not None:
            last_err = err
            continue
        if pages <= 1:
            best = data
            best_params = params
            best_gap = gap
            break
        best = data
        best_params = params
        best_gap = gap
    if best_params is None:
        raise RuntimeError(
            "Không dựng được PDF tóm tắt vách (mọi mức layout đều "
            f"không vừa 1 trang): {last_err}")
    # Giãn lấp đầy: tăng dần cỡ hình/padding/spacer trong khi vẫn
    # 1 trang và khoảng trống cuối trang còn lớn. Bước pad phải nhỏ
    # (0.05): đo thực tế gap giảm ~5.4pt mỗi 0.05 pad; bước 0.3 làm
    # bản giãn nhảy vọt sang 2 trang và vòng giãn dừng sớm ở gap
    # ~37pt trong khi vẫn còn dư địa tới ~10pt.
    pad, img_w, spacer = best_params
    gap = best_gap
    for _ in range(30):
        if gap is None or gap <= 12.0:
            break
        if img_w >= 82.0 and pad >= 3.0 and spacer >= 8.0:
            break
        nparams = (min(3.0, pad + 0.05), min(82.0, img_w + 1.0),
                   min(8.0, spacer + 0.5))
        pages, ngap, data, err = _try_impl(
            full, member_name, show_compression, nparams)
        if err is not None or pages != 1:
            break
        if ngap is not None and gap is not None and ngap >= gap:
            break
        best = data
        pad, img_w, spacer = nparams
        gap = ngap
    if hasattr(filepath, "write"):
        filepath.write(best)
    else:
        with open(filepath, "wb") as fh:
            fh.write(best)
    return filepath
