"""Xuất thuyết minh tính toán ra PDF (kèm hình mặt cắt và biểu đồ tương tác)."""

import io
import math
import os
from typing import List, Tuple

# --- Font hỗ trợ tiếng Việt ---
def _find_font():
    """Tìm font TTF hỗ trợ tiếng Việt: ưu tiên Arial (Windows), rồi DejaVu."""
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    # thêm font từ matplotlib
    try:
        import matplotlib
        mpl_font = os.path.join(os.path.dirname(matplotlib.__file__),
                                "mpl-data", "fonts", "ttf", "DejaVuSans.ttf")
        candidates.append(mpl_font)
    except Exception:
        pass
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def _find_font_bold():
    cands = [
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    try:
        import matplotlib
        cands.append(os.path.join(os.path.dirname(matplotlib.__file__),
                                  "mpl-data", "fonts", "ttf",
                                  "DejaVuSans-Bold.ttf"))
    except Exception:
        pass
    for p in cands:
        if os.path.exists(p):
            return p
    return _find_font()


# --- Vẽ hình bằng matplotlib, trả về bytes PNG ---
def draw_section_ax(ax, sec, show_dims: bool = True):
    """Vẽ mặt cắt lên axes: thép, trục 2/3, nét dim t2/t3 (kiểu ETABS)."""
    import matplotlib.patches as mpatches
    cx, cy = sec.cx, sec.cy
    if sec.kind == "rect":
        ax.add_patch(mpatches.Rectangle((-cx/2, -cy/2), cx, cy,
                                        fill=False, edgecolor="black", lw=1.5))
    else:
        ax.add_patch(mpatches.Circle((0, 0), cx/2, fill=False,
                                     edgecolor="black", lw=1.5))
    ax.scatter([r.x for r in sec.rebars], [r.y for r in sec.rebars],
               s=25, c="red", zorder=3, edgecolors="darkred",
               linewidths=0.5)
    # Trục 2 (ngang →), trục 3 (đứng ↑)
    L = max(cx, cy) * 0.75
    ax.annotate("", xy=(L, 0), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color="green", lw=1.5))

    ax.annotate("", xy=(0, L), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color="green", lw=1.5))

    # Chỉ hiện text t2=/t3= (không vẽ đường line dim)
    if sec.kind == "rect":
        off = max(cx, cy) * 0.12
        ax.text(0, -cy/2 - off, f"t3={cx:.0f}", fontsize=7, color="blue",
                ha="center", va="top")
        ax.text(cx/2 + off, 0, f"t2={cy:.0f}", fontsize=7, color="blue",
                va="center", rotation=90)

    ax.set_aspect("equal")
    # Ẩn vạch tọa độ (đã có dim t2/t3)
    ax.set_xticks([])
    ax.set_yticks([])


def section_image(sec, width_in=3.2, dpi=300, small=False) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if small:
        width_in, dpi = 1.3, 200
    # Figure theo đúng tỉ lệ t2/t3 (cao = rộng × cy/cx)
    ratio = sec.cy / sec.cx if sec.cx > 0 else 1.0
    fig, ax = plt.subplots(figsize=(width_in, width_in * ratio))
    draw_section_ax(ax, sec)
    ax.grid(True, alpha=0.3)
    for sp in ax.spines.values():
        sp.set_visible(False)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                pad_inches=0.1)
    plt.close(fig)
    return buf.getvalue()


def _radial_limit(curve, N_load: float, M_load: float):
    """Giao của tia từ gốc qua (N_load, M_load) với đường cong [(N, M)]."""
    best = None
    best_t = 0.0
    for i in range(len(curve) - 1):
        n1, m1 = curve[i]
        n2, m2 = curve[i + 1]
        a11, a12 = N_load, -(n2 - n1)
        a21, a22 = M_load, -(m2 - m1)
        det = a11 * a22 - a12 * a21
        if abs(det) < 1e-12:
            continue
        t = (n1 * a22 - m1 * a12) / det
        s = (a11 * m1 - a21 * n1) / det
        if t > 0 and 0 <= s <= 1 and t > best_t:
            best_t = t
            best = (t * N_load, t * M_load)
    return best


def interaction_image(sec, inp, res, width_in=6.0, dpi=300, small=False,
                      right_half=False) -> bytes:
    """Biểu đồ tương tác N-M tại góc uốn xiên α.
    right_half=True: chỉ hiện nửa phải (M>=0) có đường nội lực."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import math
    if small:
        width_in, dpi = 4.0, 200
    fig, ax = plt.subplots(figsize=(width_in, width_in * 0.75))
    from .interaction import FiberSection, uniaxial_curve_fs
    fs = FiberSection(sec)
    alpha_deg = math.degrees(math.atan2(res.My_star, res.Mx_star))
    cv = uniaxial_curve_fs(fs, alpha_deg, inp.concrete_model)
    ax.plot([p[1] for p in cv], [p[0] for p in cv], "b-", lw=1.5)
    ax.plot([-p[1] for p in cv], [p[0] for p in cv], "b-", lw=1.5)
    Ma = math.hypot(res.Mx_star, res.My_star)
    Mb = math.hypot(res.Bx, res.By)
    lim = (res.BN, Mb)
    ax.scatter([Ma], [res.N], c="green", s=80, zorder=5,
               label="A (tải trọng)")
    lc = "green" if res.fs > 1 else "red"
    ax.plot([0, lim[1] * 1.18], [0, lim[0] * 1.18], color=lc,
            ls="--", lw=1.5, alpha=0.9)
    ax.scatter([lim[1]], [lim[0]], c="orange", s=80, zorder=5,
               label="B (giới hạn)")
    ax.set_xlabel("M (kN·m)", fontsize=9)
    ax.set_ylabel("N (kN)", fontsize=9)
    ax.tick_params(labelsize=8)
    if right_half:
        # Chỉ hiện nửa phải (M >= 0)
        ax.set_xlim(left=0)
    ax.legend(fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.28), ncol=2)
    ax.grid(True, alpha=0.3)
    fig.subplots_adjust(bottom=0.38)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi)
    plt.close(fig)
    return buf.getvalue()


def m2m3_image(sec, inp, res, width_in=4.0, dpi=300) -> bytes:
    """Biểu đồ tương tác M2-M3 tại N."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(width_in, width_in * 0.75))
    from .interaction import BiaxialCapacity
    cap = BiaxialCapacity(sec, model=inp.concrete_model, n_angles=24)
    pts = cap.mx_my_curve(res.N)
    ax.plot([p[0] for p in pts], [p[1] for p in pts], "b-", lw=1.5)
    ax.scatter([res.Mx_star], [res.My_star], c="red", s=80, zorder=5,
               label="Điểm tải trọng")
    lc = "green" if res.fs > 1 else "red"
    ax.plot([0, res.Bx * 1.18], [0, res.By * 1.18], color=lc,
            ls="--", lw=1.5, alpha=0.9)
    ax.scatter([res.Bx], [res.By], c="orange", s=80, zorder=5,
               label="Giới hạn")
    ax.set_xlabel("M2 (kN·m)", fontsize=9)
    ax.set_ylabel("M3 (kN·m)", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.22), ncol=2)
    ax.grid(True, alpha=0.3)
    ax.set_aspect("equal", adjustable="datalim")
    fig.subplots_adjust(bottom=0.32)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi)
    plt.close(fig)
    return buf.getvalue()


def surface_3d_image(sec, inp, res, width_in=4.0, dpi=200) -> bytes:
    """Mặt tương tác 3D N-M2-M3."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    import numpy as np
    from .interaction import BiaxialCapacity
    fig = plt.figure(figsize=(width_in, width_in * 0.85))
    ax = fig.add_subplot(111, projection="3d")
    cap = BiaxialCapacity(sec, model=inp.concrete_model, n_angles=24)
    n_vals, th_vals, mxg, myg = cap.surface_grid(n_n=25, n_angles=48)
    N3, _ = np.meshgrid(n_vals, th_vals, indexing="ij")
    mxg = np.concatenate([mxg, mxg[:, :1]], axis=1)
    myg = np.concatenate([myg, myg[:, :1]], axis=1)
    N3 = np.concatenate([N3, N3[:, :1]], axis=1)
    ax.plot_surface(mxg, myg, N3, alpha=0.7, cmap="viridis",
                    edgecolor="none")
    ax.scatter([res.Mx_star], [res.My_star], [res.N], c="red", s=60,
               label="Điểm tải trọng")
    ax.set_xlabel("M2 (kN·m)")
    ax.set_ylabel("M3 (kN·m)")
    ax.set_zlabel("N (kN)")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def interaction_images(sec, inp, res, width_in=3.4, dpi=300,
                       small=False) -> tuple:
    """Trả về (png_NM2, png_NM3) — 2 ảnh riêng cho layout lớn."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if small:
        width_in, dpi = 3.2, 100
    from .interaction import FiberSection, uniaxial_curve_fs
    fs = FiberSection(sec)
    out = []
    for th, lab, Ms, Mb in [(0, "N-M2", res.Mx_star, res.Bx),
                             (90, "N-M3", res.My_star, res.By)]:
        fig, ax = plt.subplots(figsize=(width_in, width_in * 0.85))
        cv = uniaxial_curve_fs(fs, th, inp.concrete_model)
        ax.plot([p[1] for p in cv], [p[0] for p in cv], "b-", lw=1.5)
        ax.plot([-p[1] for p in cv], [p[0] for p in cv], "b-", lw=1.5)
        lim = (res.BN, Mb)
        ax.scatter([Ms], [res.N], c="green", s=80, zorder=5,
                   label="A (tải trọng)")
        ax.plot([0, lim[1]], [0, lim[0]], "r--", lw=1.2, alpha=0.8)
        ax.scatter([lim[1]], [lim[0]], c="orange", s=80, zorder=5,
                   label="B (giới hạn)")
        ax.set_xlabel("M (kN·m)")
        ax.set_ylabel("N (kN)")
        ax.set_title(f"Biểu đồ tương tác {lab}", fontsize=11)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.text(0.5, -0.30, f"Tỉ số an toàn FS = {res.fs:.2f}",
                transform=ax.transAxes, ha="center", fontsize=10,
                color="darkred", weight="bold")
        fig.subplots_adjust(bottom=0.22)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        out.append(buf.getvalue())
    return tuple(out)


# --- Xuất PDF ---
def _segs_to_flowables(segs, P, st_body, st_h, st_ref, st_dc,
                       st_badge_ok, st_badge_ng):
    """Chuyển segments của 1 mục thành list flowables."""
    out = []
    buf_lines: List[str] = []
    def flush():
        if buf_lines:
            out.append(P("<br/>".join(buf_lines), st_body))
            buf_lines.clear()
    for text, tags in segs:
        t = text.strip("\n")
        if not t:
            continue
        if "sec_title" in tags:
            flush()
            out.append(P(t.replace("● ", ""), st_h))
        elif "sec_ref" in tags:
            out.append(P(t.strip(), st_ref))
        elif "dc" in tags:
            flush()
            out.append(P(t, st_dc))
        elif "ok" in tags:
            flush()
            out.append(P("✓ ĐẠT — D/C ≤ 1.000", st_badge_ok))
        elif "ng" in tags:
            flush()
            out.append(P("✗ KHÔNG ĐẠT — D/C > 1.000", st_badge_ng))
        elif "title" in tags:
            continue
        else:
            buf_lines.append(t.replace("\n", "<br/>"))
    flush()
    return out


def export_pdf(inp, res, filepath: str, batch_rows=None):
    """Xuất thuyết minh ra file PDF (bố cục giống trong phần mềm).
    batch_rows: list (force, result) cho mục 7 (tùy chọn)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Image, Table, TableStyle, KeepTogether)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

    font_path = _find_font()
    bold_path = _find_font_bold()
    if not font_path:
        raise RuntimeError("Không tìm thấy font hỗ trợ tiếng Việt.")
    pdfmetrics.registerFont(TTFont("VN", font_path))
    pdfmetrics.registerFont(TTFont("VN-Bold", bold_path or font_path))

    sec = __import__("rc_column.checker", fromlist=["build_section"]).build_section(inp)

    SLATE = HexColor("#0f172a")
    GRAY = HexColor("#64748b")
    GREEN_BG = HexColor("#d1fae5")
    GREEN_TX = HexColor("#065f46")
    RED_BG = HexColor("#fee2e2")
    RED_TX = HexColor("#991b1b")
    DC_GREEN = HexColor("#059669")

    st_title = ParagraphStyle("title", fontName="VN-Bold", fontSize=14,
                              textColor=SLATE, alignment=TA_CENTER, spaceAfter=4)
    st_sub = ParagraphStyle("sub", fontName="VN", fontSize=9,
                            textColor=GRAY, alignment=TA_CENTER, spaceAfter=12)
    st_h = ParagraphStyle("h", fontName="VN-Bold", fontSize=11,
                          textColor=SLATE, spaceBefore=10, spaceAfter=2)
    st_ref = ParagraphStyle("ref", fontName="VN", fontSize=8,
                            textColor=GRAY, spaceAfter=6)
    st_body = ParagraphStyle("body", fontName="VN", fontSize=9.5,
                             textColor=SLATE, leading=13, spaceAfter=2,
                             alignment=TA_JUSTIFY)
    st_cap = ParagraphStyle("cap", fontName="VN", fontSize=8,
                            textColor=GRAY, alignment=TA_CENTER, spaceBefore=4)
    st_dc = ParagraphStyle("dc", fontName="VN-Bold", fontSize=15,
                           leading=22, textColor=DC_GREEN, alignment=TA_CENTER,
                           spaceBefore=8, spaceAfter=6)
    st_badge_ok = ParagraphStyle("bok", fontName="VN-Bold", fontSize=12,
                                 textColor=GREEN_TX, backColor=GREEN_BG,
                                 alignment=TA_CENTER, borderPadding=8,
                                 spaceBefore=8)
    st_badge_ng = ParagraphStyle("bng", fontName="VN-Bold", fontSize=12,
                                 textColor=RED_TX, backColor=RED_BG,
                                 alignment=TA_CENTER, borderPadding=8,
                                 spaceBefore=8)

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    S: list = []
    P = Paragraph
    cvt = lambda segs: _segs_to_flowables(
        segs, P, st_body, st_h, st_ref, st_dc, st_badge_ok, st_badge_ng)

    S.append(P("THUYẾT MINH TÍNH TOÁN KIỂM TRA CỘT BTCT", st_title))
    S.append(P("Tiêu chuẩn: TCVN 5574:2018 — Mô hình biến dạng phi tuyến "
               "(Điều 8.1.2.7)", st_sub))

    from .report import generate_report_sections
    sections = generate_report_sections(inp, res, batch_rows=batch_rows)

    # Ảnh cho mục 2 (cột phải) và mục 6 (2 biểu đồ lớn full-width)
    img_side = {}
    try:
        _w = 50*mm
        _h = _w * (sec.cy / sec.cx) if sec.cx > 0 else _w
        img_side[2] = Image(io.BytesIO(section_image(sec, small=True)),
                            width=_w, height=_h)
    except Exception:
        pass
    img_m6 = []
    try:
        from .pdf_export import m2m3_image  # noqa
        png_m2m3 = m2m3_image(sec, inp, res, width_in=4.0)
        # N-M chỉ hiện nửa phải có đường nội lực
        png_nm = interaction_image(sec, inp, res, width_in=4.0,
                                   right_half=True)
        _h = 64*mm
        img_m6 = [Image(io.BytesIO(png_m2m3), width=85*mm, height=_h),
                  Image(io.BytesIO(png_nm), width=85*mm, height=_h)]
    except Exception:
        pass
    captions = {2: "Hình 1. Mặt cắt cột và bố trí cốt thép"}

    for num in sorted(sections.keys()):
        info = sections[num]
        flows = cvt(info["segs"])
        if num == 2 and img_side.get(2) is not None:
            # Mục 2: text trái, hình phải
            right_col = [img_side[2], P(captions[2], st_cap)]
            tbl = Table([[flows, right_col]],
                        colWidths=[108*mm, 68*mm])
            tbl.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
            ]))
            S.append(KeepTogether(tbl))
            S.append(Spacer(1, 2))
        elif num == 6 and img_m6:
            from reportlab.platypus import PageBreak
            S.append(PageBreak())
            # Mục 6: text full-width, 2 biểu đồ cạnh nhau
            # (M2-M3 trái, N-M nửa phải có đường nội lực)
            S.extend(flows)
            S.append(Spacer(1, 4))
            tbl6 = Table([[
                [img_m6[0], P("Biểu đồ M2-M3 (tại N)", st_cap)],
                [img_m6[1], P("Biểu đồ N-M (nửa phải)", st_cap)],
            ]], colWidths=[88*mm, 88*mm])
            tbl6.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]))
            S.append(tbl6)
            S.append(P("Hình 2. Biểu đồ M2-M3 và N-M (góc α)", st_cap))
            S.append(Spacer(1, 6))
        elif num == 7 and batch_rows:
            # Mục 7: Table có lưới thật
            from reportlab.platypus import PageBreak
            S.append(PageBreak())
            S.append(P("7. BẢNG TỔNG HỢP KẾT QUẢ KIỂM TRA", st_h))
            S.append(P("Tất cả tổ hợp", st_ref))
            S.append(Spacer(1, 6))
            hdr = ["Tổ hợp", "N (kN)", "M2 (kN·m)", "M3 (kN·m)", "D/C", "KQ"]
            data = [hdr]
            for f, r in batch_rows:
                dc = r["dc"]
                ok = "ĐẠT" if dc <= 1 else "KHÔNG ĐẠT"
                data.append([f"{f.case}@{f.station:.2f}", f"{f.N:.0f}",
                             f"{f.Mx:.0f}", f"{f.My:.0f}",
                             f"{dc:.3f}", ok])
            t7 = Table(data, colWidths=[32*mm, 22*mm, 24*mm, 24*mm,
                                        20*mm, 28*mm])
            t7.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#000000")),
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#e2e8f0")),
                ("FONTNAME", (0, 0), (-1, 0), "VN-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "VN"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            S.append(t7)
            S.append(Spacer(1, 6))
        else:
            S.extend(flows)

    doc.build(S)
    return filepath
