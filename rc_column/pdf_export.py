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
def section_image(sec, width_in=3.2, dpi=150, small=False) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    if small:
        width_in, dpi = 2.6, 100
    fig, ax = plt.subplots(figsize=(width_in, width_in))
    if sec.kind == "rect":
        ax.add_patch(mpatches.Rectangle((-sec.cx/2, -sec.cy/2), sec.cx, sec.cy,
                                        fill=False, edgecolor="black", lw=1.5))
    else:
        ax.add_patch(mpatches.Circle((0, 0), sec.cx/2, fill=False,
                                     edgecolor="black", lw=1.5))
    ax.scatter([r.x for r in sec.rebars], [r.y for r in sec.rebars],
               s=80, c="red", zorder=3)
    for r in sec.rebars:
        ax.text(r.x, r.y, f"{r.dia:.0f}", fontsize=6, ha="center",
                va="center", color="white")
    ax.set_aspect("equal")
    ax.set_title("Mặt cắt cột và bố trí thép", fontsize=10)
    ax.grid(True, alpha=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def interaction_image(sec, inp, res, width_in=5.0, dpi=150, small=False) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .interaction import BiaxialCapacity
    if small:
        width_in, dpi = 3.0, 100
    fig, ax = plt.subplots(figsize=(width_in, width_in * 0.85))
    cap = BiaxialCapacity(sec, model=inp.concrete_model, n_angles=24)
    # đường bao N-M tại góc của điểm tải
    phi = math.degrees(math.atan2(res.My_star, res.Mx_star))
    # vẽ 2 đường N-Mx, N-My
    from .interaction import FiberSection, uniaxial_curve_fs
    fs = FiberSection(sec)
    for th, style, lab in [(0, "b-", "N-Mx"), (90, "r--", "N-My")]:
        cv = uniaxial_curve_fs(fs, th, inp.concrete_model)
        ax.plot([p[1] for p in cv], [p[0] for p in cv], style, label=lab, lw=1.5)
    # điểm tải A và điểm giới hạn B (quy về M)
    Ma = math.hypot(res.Mx_star, res.My_star)
    Mb = math.hypot(res.Bx, res.By)
    ax.scatter([Ma], [res.N], c="green", s=80, zorder=5, label="A (tải trọng)")
    ax.scatter([Mb], [res.BN], c="orange", s=80, zorder=5, label="B (giới hạn)")
    ax.set_xlabel("M (kN·m)")
    ax.set_ylabel("N (kN)")
    ax.set_title(f"Biểu đồ tương tác N-M (α = {phi:.1f}°)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


# --- Xuất PDF ---
def export_pdf(inp, res, filepath: str):
    """Xuất thuyết minh ra file PDF."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Image, Table, TableStyle)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

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
                          textColor=SLATE, spaceBefore=14, spaceAfter=2)
    st_ref = ParagraphStyle("ref", fontName="VN", fontSize=8,
                            textColor=GRAY, spaceAfter=6)
    st_body = ParagraphStyle("body", fontName="VN", fontSize=10,
                             textColor=SLATE, leading=14, spaceAfter=2)
    st_mono = ParagraphStyle("mono", fontName="VN", fontSize=9,
                             textColor=HexColor("#334155"), leading=13)
    st_dc = ParagraphStyle("dc", fontName="VN-Bold", fontSize=16,
                           textColor=DC_GREEN, alignment=TA_CENTER, spaceBefore=8)
    st_badge_ok = ParagraphStyle("bok", fontName="VN-Bold", fontSize=12,
                                 textColor=GREEN_TX, backColor=GREEN_BG,
                                 alignment=TA_CENTER, borderPadding=8,
                                 spaceBefore=8)
    st_badge_ng = ParagraphStyle("bng", fontName="VN-Bold", fontSize=12,
                                 textColor=RED_TX, backColor=RED_BG,
                                 alignment=TA_CENTER, borderPadding=8,
                                 spaceBefore=8)

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    S: list = []
    P = Paragraph

    S.append(P("THUYẾT MINH TÍNH TOÁN KIỂM TRA CỘT BTCT", st_title))
    S.append(P("Tiêu chuẩn: TCVN 5574:2018 — Mô hình biến dạng phi tuyến "
               "(Điều 8.1.2.7)", st_sub))

    from .report import generate_report
    segs = generate_report(inp, res)
    # chuyển segments thành paragraphs (bỏ tags màu, giữ cấu trúc)
    buf_lines: List[str] = []
    for text, tags in segs:
        t = text.strip("\n")
        if not t:
            continue
        if "sec_title" in tags:
            if buf_lines:
                S.append(P("<br/>".join(buf_lines), st_body))
                buf_lines = []
            S.append(P(t.replace("● ", ""), st_h))
        elif "sec_ref" in tags:
            S.append(P(t.strip(), st_ref))
        elif "dc" in tags:
            if buf_lines:
                S.append(P("<br/>".join(buf_lines), st_body))
                buf_lines = []
            S.append(P(f"TỶ SỐ SỬ DỤNG (D/C) = {t}", st_dc))
        elif "ok" in tags:
            if buf_lines:
                S.append(P("<br/>".join(buf_lines), st_body))
                buf_lines = []
            S.append(P("✓ ĐẠT — D/C ≤ 1.000", st_badge_ok))
        elif "ng" in tags:
            if buf_lines:
                S.append(P("<br/>".join(buf_lines), st_body))
                buf_lines = []
            S.append(P("✗ KHÔNG ĐẠT — D/C > 1.000", st_badge_ng))
        elif "title" in tags:
            continue
        else:
            buf_lines.append(t.replace("\n", "<br/>"))
    if buf_lines:
        S.append(P("<br/>".join(buf_lines), st_body))

    # Hình mặt cắt (mục 2) và biểu đồ (mục 6)
    S.append(Spacer(1, 12))
    S.append(P("Hình 1. Mặt cắt cột và bố trí cốt thép", st_h))
    img1 = Image(io.BytesIO(section_image(sec)), width=70*mm, height=70*mm)
    S.append(img1)
    S.append(Spacer(1, 8))
    S.append(P("Hình 2. Biểu đồ tương tác N-M", st_h))
    img2 = Image(io.BytesIO(interaction_image(sec, inp, res)),
                 width=140*mm, height=119*mm)
    S.append(img2)

    doc.build(S)
    return filepath
