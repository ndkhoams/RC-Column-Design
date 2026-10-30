"""Chế độ Vách (GĐ1 — lát 0: khung + plumbing; lát 1: N–M TCVN).

Gồm: frame nhập liệu vách (mục 2/3/4 khi ở chế độ Vách), chuyển đổi
loại cấu kiện Cột <-> Vách (_toggle_member), thu/áp dữ liệu vách cho
JSON (_collect_wall/_apply_wall), và điều phối CHECK ở chế độ Vách.

Lát 1: CHECK tay theo TCVN chạy engine vách (rc_column/wall_engine)
qua hàm duy nhất _tcvn_wall_calculate_full, kết quả lưu ở
self._tcvn_wall_full và hiển thị ở tab Kết quả/Chi tiết từ đúng dict
đó. Lát 5: batch Pier Forces (ETABS) theo TCVN cũng chạy đúng hàm
này cho từng dòng (rc_column/wall_batch.run_wall_batch) — kết quả
mỗi dòng lưu ở self._wall_batch_rows, chọn 1 dòng nạp vào
self._tcvn_wall_full để tab Kết quả/Chi tiết đọc như đường tay.
ACI/EC2 vách (lát 2) vẫn báo rõ chưa hỗ trợ — tuyệt đối không chạy
engine cột cho dữ liệu vách.
PDF vách TCVN (tóm tắt 1 trang + chi tiết cards) đã hỗ trợ từ
rc_column/wall_pdf_summary.py / wall_pdf_report.py qua
gui/pdf_mixin.py. Thiết kế: THIET_KE_TICH_HOP_VACH_GD1.md §2, §6, §8.

Từ 2026-10-23: mục 2/3/4 theo format công cụ web Vietcons "Kiểm tra
vách BTCT" — mục 2 (loại tiết diện + xoay + Lw/tw), mục 3 (2 chế độ
thép dọc: chu vi / tập trung vùng biên + khối số đọc trực tiếp), mục 4
(bảng P–δ 2 phương X/Y, ψ tự điền theo LK như bên cột, L0 suy ra
lúc tính, không hiển thị ở panel). Các ô ngoài phạm vi web (thép
ngang, đai vùng biên, kháng chấn) gom vào frame "Thép ngang, đai vùng biên, kháng chấn". Mặt cắt
vách có DIM từng khoảng
(tổng Lw/tw + Lb/đoạn giữa/Lb ở chế độ vùng biên) và vùng nén khi đã
CHECK — cùng hàm vẽ cho preview và kết quả.
"""

import math
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MPL = True
except Exception:
    HAS_MPL = False

from rc_column.lang import T
from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.stability import BOUNDARY_NAMES
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_shear import qb_formula_sub
from rc_column.wall_input import (WALL_DEFAULTS, normalize_wall_dict,
                                  wall_from_dict)
from rc_column.cover_migration import (COVER_SEMANTICS_NEW,
                                        migrate_wall_dict)
from rc_column.wall_section import build_wall_section

_DIAS = ["10", "12", "14", "16", "18", "20", "22", "25", "28", "32"]
# Danh mục đường kính theo format web (mục 3): d10..d40
_DIAS_WEB = ["10", "12", "14", "16", "18", "20", "22", "25", "28", "32",
             "36", "40"]
_STORY_POS = [("base", "Chân vách"), ("mid", "Đốt giữa"), ("top", "Đốt trên")]
_L0_OPTS = [("Khớp – Khớp (hệ số 1.0)", 1.0),
            ("Ngàm – Khớp (hệ số 0.7)", 0.7),
            ("Ngàm – Ngàm (hệ số 0.5)", 0.5),
            ("Ngàm – Tự do (hệ số 2.0)", 2.0)]
_ACI_CLASS = [("special", "Đặc biệt (Ch.18)"), ("ordinary", "Thường (Ch.11)")]
# Mục 2 (web): 6 loại tiết diện — lát 1 (2026-10-27) cả 6 loại đều
# chọn được ở mức mặt cắt + thép + preview; CHECK N–M/cắt vẫn chỉ
# mở cho vách phẳng (xem _on_check_wall).
_SECTYPES = ["Vách phẳng chữ nhật", "Vách mở rộng hai đầu (Barbell)",
             "Vách chữ T", "Vách chữ L", "Lõi chữ C", "Lõi chữ U",
             "Tiết diện bất kỳ (DXF)"]
_SEC_CODES = ["rect", "barbell", "tee", "ell", "c-core", "u-core",
              "dxf"]
# Mặc định web khi LẦN ĐẦU chuyển sang loại đó (mm; chỉ điền 1 lần
# khi loại chưa từng thấy trong phiên — chuyển qua lại giữ nguyên
# giá trị user đã nhập). Vách phẳng giữ nguyên mặc định app.
_SEC_WEB_DEFAULTS = {
    "barbell": {"Lw": 3000, "tw": 300, "sec_bf": 1000, "sec_tf": 450,
                "sec_bf2": 1000, "sec_tf2": 450},
    "tee": {"Lw": 2500, "sec_bf": 1500, "sec_t": 300},
    "ell": {"sec_L1": 2000, "sec_L2": 1800, "sec_t": 300},
    "c-core": {"Lw": 3000, "sec_bf": 1500, "sec_lr": 600,
               "sec_bf2": 1500, "sec_lr2": 600, "sec_t": 300},
    "u-core": {"Lw": 3000, "sec_bf": 1500, "sec_bf2": 1500,
               "sec_t": 300},
}
# Mục 3 (web): 2 chế độ bố trí thép dọc
_STEEL_MODES = [("perimeter", "Phân bố đều theo chu vi"),
                ("boundary", "Tập trung vùng biên")]
# LEGACY (2026-10-25): panel vùng biên mới không còn dùng 2 hằng này
# (radio be_layout + combo nT đã bỏ); giữ lại để grep/tham chiếu cũ
# không vỡ, không dùng cho tính toán hay load/save nữa.
_NT_OPTS = [(2, "2 hàng (2 mặt)"), (3, "3 hàng"), (4, "4 hàng")]
_BE_LAYOUTS = [("chuvi", "Chu vi"), ("grid", "Lưới đặc")]
# Mục 4 (web): phương pháp xét uốn dọc (P–δ)
_PD_OPTS = [("tcvn", "Xét uốn dọc theo TCVN 5574:2018"),
            ("none", "Không xét bổ sung uốn dọc")]

# Preset ca mẫu của web Vietcons cho các ô DÙNG CHUNG (mục 1 vật
# liệu TCVN + mục 5 nội lực nhập tay) khi vào chế độ Vách trong
# phiên mới tinh (chưa mở file, các ô còn nguyên mặc định app mới):
# mở app -> chuyển Vách -> CHECK là đối chiếu ngay với web. Mục
# 2/3/4 của vách đã mặc định sẵn theo web trong WALL_DEFAULTS.
# (N, Mx=M2, My=M3, bê tông, thép dọc, γb, γs) — thứ tự tuple dùng
# chung cho cả 2 bộ dưới đây.
_WALL_FRESH_SHARED = ("1500", "80", "60", "B25", "CB400-V",
                      "0.85", "1.0")
_WALL_WEB_SHARED = ("2528.65", "275.23", "202.86", "B30", "CB500-V",
                    "0.85", "1.0")


def _code_of(pairs, label, default):
    for code, lab in pairs:
        if lab == label:
            return code
    return default


def _label_of(pairs, code, default_label):
    for c, lab in pairs:
        if c == code:
            return lab
    return default_label


def _l0_label(factor):
    for lab, fac in _L0_OPTS:
        if abs(fac - factor) < 1e-9:
            return lab
    return _L0_OPTS[0][0]


# ---------------------------------------------------------------------
# Vẽ mặt cắt vách — phong cách tab Kết quả của CỘT (lát 1.5, chỉ hiển
# thị): cùng quy ước với draw_compression_zone_ax (pdf_export): nền
# lưới nhạt, khung đen lw=2 nền #F4F7FB, thép là marker tròn kích
# thước CỐ ĐỊNH theo điểm ảnh (s = (dia*0.22)^2) nên thép biên d28
# trong vùng biên 500mm vẫn tách từng thanh, legend thép nằm trong
# BOX viền xám ở bên phải hình (không đè hình/trục), trục t2 (xanh
# lá, ngang) / t3 (xanh dương, đứng) và nhãn dim t3/t2 sát mép.
# Khác bản cột ở 2 điểm do tỉ lệ vách rất dẹt (Lw >> tw):
#  - giới hạn trục tính RIÊNG theo từng phương (bản cột dùng ±0.70*max
#    cả 2 phương -> vách thành 1 vệt mỏng giữa khoảng trống lớn);
#  - thép vẽ tại tọa độ THẬT (bản cột co 0.96 về tâm: với vách dài
#    2500mm, co 4% làm thanh biên lệch tới 50mm khỏi vị trí thật;
#    thép vách đã lùi khỏi mép >= cover+dia_h+dia/2 nên không chạm viền).
# ---------------------------------------------------------------------
def _rot_xy(x, y, deg):
    """Xoay điểm quanh tâm tiết diện (0, 0) NGƯỢC chiều kim đồng hồ
    deg độ (deg thuộc {0, 90, 180, 270}) — phép xoay hình học DUY
    NHẤT áp cho mọi phần tử của plot mặt cắt vách khi xoay tiết
    diện (đường bao, thép, vùng nén, dim, mũi tên trục)."""
    deg = int(deg or 0) % 360
    if deg == 90:
        return (-y, x)
    if deg == 180:
        return (-x, -y)
    if deg == 270:
        return (y, -x)
    return (x, y)


def _rot_text(base_rot, deg):
    """Góc xoay của chữ sau khi hình xoay deg: cộng góc như xoay
    cứng rồi chuẩn hoá về (-90, 90] để chữ không lộn ngược. Trả
    (rotation, flip) — flip=True khi đã trừ 180°: phải hoán đổi
    ha (left<->right) và va (top<->bottom) để khối chữ vẫn nằm
    đúng phía của điểm neo như khi xoay cứng."""
    r = (float(base_rot) + float(deg or 0)) % 360.0
    if r == 180.0:
        return 0.0, True
    if r > 180.0:
        return r - 360.0, False
    return r, False


def _flip_ha(ha):
    return {"left": "right", "right": "left"}.get(ha, ha)


def _flip_va(va):
    return {"top": "bottom", "bottom": "top"}.get(va, va)


def _dir_ha_va(dx, dy):
    """(ha, va) cho nhãn nằm NGOÀI đầu mũi tên theo hướng (dx, dy)
    đã xoay: chữ ở phía ngoài đầu mũi tên, không đè lên thân."""
    ha = "left" if dx > 0.5 else ("right" if dx < -0.5 else "center")
    va = "bottom" if dy > 0.5 else ("top" if dy < -0.5 else "center")
    return ha, va


def _wall_section_spans(sec, n_seg=0, rot_deg=0):
    """Giới hạn trục (x_lo, x_hi, y_lo, y_hi) cho hình mặt cắt vách =
    BBOX CHẶT của toàn bộ nội dung vẽ (mặt cắt + thép + dim + chữ +
    mũi tên trục) cộng margin nhỏ đều — KHÔNG chừa khoảng đệm theo
    bội số cy/cx như trước (đệm cũ làm span dọc 4.7cy trong khi mực
    thật chỉ ~4.1cy). Hàng DIM tổng Lw luôn vẽ ở dưới cùng nên
    đáy span luôn phải phủ tới đáy chữ Lw (-cy/2 - 2.22cy) ở cả
    2 chế độ thép, kể cả khi không có hàng phân đoạn.

    Các mốc lấy đúng vị trí phần tử trong draw_wall_section_ax, đã
    đo kiểm chứng bằng artist extents (ca 2500x350, rot 0):
    - trái: chữ 'tw' xoay đứng — mép trái ở -(cx/2 + 0.063cx) trừ
      bề dày chữ ~0.027cx = -0.59cx; chừa margin tới -0.605cx.
    - phải: mép phải mặt cắt +0.5cx, chừa 0.02cx.
    - trên: nhãn 't3' neo ở cy/2 + 1.01cy, đỉnh chữ ~+0.21cy nữa
      (chiều cao chữ theo đơn vị dữ liệu ở tỉ lệ vẽ thường) = 1.72cy;
      chừa tới cy/2 + 1.27cy.
    - dưới: thấp nhất là đường dim tổng Lw ở -cy/2 - 1.45cy cộng
      đoạn gióng chìa qua tới -cy/2 - 1.61cy (nhãn 'Lw = ...' từ
      2026-10-25 nằm TRÊN đường dim nên không còn quyết định đáy);
      giữ đáy span cũ -cy/2 - 2.29cy để hình không đổi tỉ lệ/vị
      trí (đệm dưới thêm ~0.68cy, vô hại vì adjustable='box').
    rot_deg: span hiển thị = bao hình của 4 góc span canonical đã
    xoay (sec truyền vào luôn ở khung canonical: x = Lw, y = tw).
    """
    cx, cy = float(sec.cx), float(sec.cy)
    # Lát hiển thị 2026-10-27: đa giác dùng đơn vị dim riêng
    # _unit = 0.35*min(cx, cy) thay cho cy (55b781a dùng 0.5,
    # tinh chỉnh sau phản hồi "hình hơi nhỏ" xuống 0.35). Lý do:
    # với C/U, cy là cạnh DÀI (3000 mm) trong khi các khoảng
    # dim/trục dọc vốn tính theo cy sẽ phình span dọc tới
    # 4.56*cy, mặt cắt chỉ chiếm 22% chiều cao span nên C/U nhỏ
    # xíu giữa khung (ảnh user 9b6481f). Với _unit, span dọc =
    # cy + 3.56*_unit, mặt cắt chiếm ~45% span (T/L/Barbell) và
    # ~62% span (C/U), dim vẫn cách nhau đủ px (đo Agg sau sửa,
    # xem test_wallsecplot3). Rect giữ nguyên cy (đã
    # user-verified, test_wallsecplot khóa dim tổng -1.45cy).
    _is_poly = getattr(sec, "kind", "rect") == "poly"
    # Tinh chỉnh 2026-10-27 (sau phản hồi "chấm hơi to, hình hơi
    # nhỏ" ở 55b781a): _unit đa giác 0.5 -> 0.35*min(cx,cy), áp
    # ĐỒNG BỘ ở cả spans và draw (mọi offset dim/trục t3 đều theo
    # _unit nên thu span không làm dim tràn span). Span dọc poly
    # từ cy + 3.56*0.5*min xuống cy + 3.56*0.35*min: C/U lấp cao
    # 0.53 -> 0.62, T/L/Barbell 0.36 -> 0.45 (đo Agg, xem
    # test_wallsecplot3); khe dim phân đoạn-tổng còn
    # 0.83*_unit (~39px ở axes cao 440px) nên dim không chồng.
    # Rect giữ nguyên cy (đã user-verified, test khóa 0.22).
    _unit = 0.35 * min(cx, cy) if _is_poly else cy
    # Đa giác có dim phân đoạn dọc bên trái (C/U: Lr) nay ở cột
    # -0.28cx (xem draw_wall_section_ax) nên chừa trái tới
    # -0.34cx cho mọi poly (thu từ -0.38cx: lấp rộng poly
    # 0.71 -> 0.74; nhãn dim dọc xoay 90° chỉ chiếm ~11px bề
    # ngang nên vẫn nằm trong lề figure, đo Agg không chồng);
    # rect giữ -0.105cx như cũ.
    _left = 0.34 if _is_poly else 0.105
    # Lát N–M: span theo bbox outline thật (đa giác ở khung trọng
    # tâm nên bbox lệch khỏi ±cx/2; rect: bbox outline = ±cx/2
    # nên trùng hệt cũ).
    if _is_poly and getattr(sec, "poly_verts", None):
        _ov = list(sec.poly_verts[0])
        _bx0 = min(p[0] for p in _ov)
        _bx1 = max(p[0] for p in _ov)
        _by0 = min(p[1] for p in _ov)
        _by1 = max(p[1] for p in _ov)
    else:
        _bx0, _bx1, _by0, _by1 = -cx / 2, cx / 2, -cy / 2, cy / 2
    x_lo, x_hi = _bx0 - _left * cx, _bx1 + 0.02 * cx
    y_hi = _by1 + 1.27 * _unit
    # Hàng tổng Lw luôn vẽ (kể cả không có phân đoạn) nên đáy span
    # luôn là -2.29*_unit; nhánh cũ -1.21cy khi không phân đoạn
    # làm dim + nhãn Lw tràn khỏi khung (đo Agg: nhãn ở y < 0,
    # ngoài figure). n_seg giữ lại cho chữ ký hàm, không còn ảnh
    # hưởng tới span.
    y_lo = _by0 - 2.29 * _unit
    if int(rot_deg or 0) % 360 == 0:
        return (x_lo, x_hi, y_lo, y_hi)
    pts = [_rot_xy(x, y, rot_deg)
           for x in (x_lo, x_hi) for y in (y_lo, y_hi)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), max(xs), min(ys), max(ys))


_WALL_SEC_PAD_PX = 9.0

# Cỡ hiển thị của điểm thép vách — Lát hiển thị 2026-10-27:
# thép vẽ bằng marker scatter CỠ ĐIỂM ẢNH CỐ ĐỊNH (không còn
# Circle tỉ lệ thật + sàn draw_event). Đường kính marker
# WALL_BAR_DIAM_PT từng là 6.0pt = 8.3px ở dpi 100 (preview Tk) và
# 16.7px ở dpi 200 (ảnh PDF) — cùng kích thước vật lý 2.1mm,
# nhìn rõ như chấm đỏ web mà không phụ thuộc draw_event/resize/
# debounce (đó là điểm yếu của cơ chế sàn cũ: ảnh user 9b6481f
# chỉ còn 9–22px cam, tức chỉ legend, thép gần như không hiện
# trong Tk dù render Agg trực tiếp vẫn có 6px).
# Tinh chỉnh 2026-10-27 (phản hồi user 55b781a "chấm hơi to"):
# đo Agg cho thấy khoảng cách thanh nhỏ nhất theo dữ liệu là
# ~107 mm (nửa cạnh ô nút giao 214 mm) ở mọi loại đa giác; ở
# axes bị giới hạn chiều cao của C/U, khoảng cách này chỉ
# ~8.3px nên chấm 6pt (8.3px, tỉ lệ 1.00) chạm nhau thành vệt.
# Mục tiêu ≤40% khoảng cách không đạt được ở cỡ axes C/U nếu
# giữ sàn nhìn rõ ~5px (40% của 8.3px = 3.3px < sàn), nên sàn
# nhìn rõ thắng: chọn cỡ cố định 4.0pt = 5.6px ở dpi 100
# (11.1px ở dpi 200, 1.4mm vật lý), viền trắng 0.5pt tách chấm
# kề nhau; sau khi thu span, khoảng cách C/U lên ~9.7px nên
# tỉ lệ chấm/khoảng cách còn ~0.58 (trước 1.00), các loại khác
# ≤0.49. KHÔNG trở lại Circle tỉ lệ thật, KHÔNG khôi phục hook
# draw_event. Ở s=100 khoảng cách giảm một nửa nên chấm ở vùng
# dày sẽ chạm nhau — giới hạn đã ghi, s mặc định 200 mới là
# trường hợp thiết kế.
# WALL_BAR_MIN_DIAM_PX giữ lại cho tương thích (hàm floor cũ
# nay là no-op, xem _wall_bar_floor_apply).
# Lát hiển thị 2026-10-27 (phản hồi user 8dd839c "nên linh động
# giảm kích thước chấm thép xuống để phù hợp với mặt cắt"):
# chấm CỐ ĐỊNH 4.0pt vẫn thô ở mặt cắt nhỏ/dày — đo đúng điều
# kiện Agg figsize của app: chấm 5.6px chiếm 20.8% bề dày 300 mm
# hiển thị ở C/U (300 mm × 0.089 px/mm = 26.7px) và 58% khoảng
# cách thanh nhỏ nhất (107 mm × 0.089 = 9.5px), trong khi ở
# phẳng chỉ 10.0% bề dày và 23% khoảng cách. Một cỡ cho mọi
# loại không thể vừa cả hai đầu, nên chấm chuyển sang ĐĨA THEO
# ĐƠN VỊ DỮ LIỆU (xem _wall_bar_dot_diam): đường kính theo mm,
# tự co giãn theo tỉ lệ hiển thị (axes to/thưa -> chấm to theo
# px, axes nhỏ/dày -> chấm nhỏ theo px) và tự thích ứng khi
# Tk resize figure hay khi sang PDF dpi 200, KHÔNG cần handler
# draw_event (điểm yếu đã bỏ ở 55b781a) và KHÔNG quay lại
# Circle tỉ lệ thật: đường kính đĩa = 14% bề dày nhánh, tức
# 42 mm với nhánh 300 mm, gấp 3.5 lần đường kính thanh d12
# thật (12 mm) nên ở tỉ lệ C/U vẫn ~3.7px (không phải ~1px
# như thời Circle tỉ lệ thật), ở phẳng 49 mm ~9.0px.
# WALL_BAR_DIAM_PT nay chỉ còn là cỡ chấm của LEGEND (biểu
# tượng, không phải chấm trên mặt cắt), giữ 4.0pt để legend
# không đổi so với các lát trước.
WALL_BAR_DIAM_PT = 4.0
WALL_BAR_MIN_DIAM_PX = 4.0
# Hệ số chấm thích ứng (đơn vị dữ liệu, xem _wall_bar_dot_diam):
# 0.14 = chấm / bề dày nhánh (mục tiêu ≤15% bề dày hiển thị);
# 0.40 = chấm / khoảng cách thanh nhỏ nhất theo dữ liệu
# (mục tiêu ≤40%, để chấm không chạm nhau ở s200);
# 2.5 = sàn đường kính theo đường kính thanh (để chấm không
# nhỏ hơn 2.5 lần thanh thật khi nhánh rất mỏng).
WALL_BAR_DOT_FRAC_T = 0.14
WALL_BAR_DOT_FRAC_SPACING = 0.40
WALL_BAR_DOT_MIN_DIA_FACTOR = 2.5


def _wall_bar_dot_diam(sec, meta=None):
    """Đường kính chấm thép (mm, đơn vị dữ liệu) cho
    draw_wall_section_ax — chấm THÍCH ỨNG, không cố định pt.

    Công thức: D = min(0.14 × t_nhánh, 0.40 × d_min),
    rồi max với 2.5 × dia_max. Trong đó:
    - t_nhánh = meta["bar_branch_t"] (rect: tw; Barbell: tw;
      T/L/C/U: sec_t); thiếu meta thì suy từ hình: rect -> cy,
      đa giác -> cạnh outline ngắn nhất ≤ 0.5 × max(cx, cy)
      (300 mm ở T/L/C/U, 350 mm ở Barbell — chỉ là fallback,
      đường app luôn có meta từ build_wall_section).
    - d_min = khoảng cách nhỏ nhất theo dữ liệu giữa 2 thanh
      kề nhau (tính từ sec.rebars, O(n²) với n ≤ ~150, rẻ).
    - Thứ tự ưu tiên khi xung đột: sàn nhìn rõ (2.5 × dia)
      thắng trần khoảng cách, vì chấm dưới ~2.5 lần thanh thật
      sẽ chìm; ở s200 mặc định sàn này không kích hoạt
      (D = 42 mm ở đa giác, 49 mm ở phẳng, đều > 30 mm).
    Kết quả ở mặc định d12 s200: rect 49 mm, Barbell/T/L/C/U
    42 mm; tỉ lệ chấm/bề dày = 14%, chấm/khoảng cách nhỏ
    nhất ≤ 40% (đa giác 42/107 = 39%, phẳng 49/132 = 37%).
    Vì đĩa vẽ bằng Circle trong không gian dữ liệu và axes có
    aspect equal, đường kính theo px tự bằng D × (px/mm) ở
    mọi figure/dpi/resize — không cần draw_event, không phụ
    thuộc figsize khởi tạo.
    """
    import math
    _meta = meta or {}
    _t = _meta.get("bar_branch_t")
    if _t is None:
        if getattr(sec, "kind", "rect") != "poly":
            _t = float(sec.cy)
        else:
            _verts = list(getattr(sec, "poly_verts", [[]])[0] or [])
            _edges = []
            for _i in range(len(_verts)):
                _a, _b = _verts[_i], _verts[(_i + 1) % len(_verts)]
                _edges.append(math.hypot(_b[0] - _a[0],
                                          _b[1] - _a[1]))
            _small = [e for e in _edges
                      if e <= 0.5 * max(float(sec.cx), float(sec.cy))]
            _t = min(_small) if _small else min(float(sec.cx),
                                                float(sec.cy))
    _d = WALL_BAR_DOT_FRAC_T * float(_t)
    _pts = [(float(r.x), float(r.y)) for r in getattr(sec, "rebars", [])]
    if len(_pts) >= 2:
        _dmin = float("inf")
        for _i in range(len(_pts)):
            for _j in range(_i + 1, len(_pts)):
                _dd = math.hypot(_pts[_i][0] - _pts[_j][0],
                                 _pts[_i][1] - _pts[_j][1])
                if _dd > 0:
                    _dmin = min(_dmin, _dd)
        if _dmin != float("inf"):
            _d = min(_d, WALL_BAR_DOT_FRAC_SPACING * _dmin)
    _dias = [float(r.dia) for r in getattr(sec, "rebars", [])]
    if _dias:
        _d = max(_d, WALL_BAR_DOT_MIN_DIA_FACTOR * max(_dias))
    return float(_d)


def _wall_section_axes_pos(fig, ax, pad_px=_WALL_SEC_PAD_PX):
    """Đặt axes lấp gần trọn figure (chừa pad_px mỗi phía). Hình mặt
    cắt vách không có tick label, không artist nào ngoài axes
    (legend nằm trong axes, dim + chữ nằm trong span dữ liệu) nên
    KHÔNG dùng tight_layout: đệm mặc định của nó (theo cỡ chữ, cộng
    dồn qua các lần layout ở các cỡ figure trung gian) chừa tới
    ~20px/phía làm nội dung co lại. Position thủ công cho chrome
    cố định -> phép fit tỉ lệ trong _build_wall_section_cell tất
    định."""
    w, h = fig.bbox.width, fig.bbox.height
    if w <= 0 or h <= 0:
        return
    lft = pad_px / w
    bot = pad_px / h
    ax.set_position([lft, bot, 1.0 - 2 * lft, 1.0 - 2 * bot])


def _wall_section_figsize(sec, n_seg=0, rot_deg=0):
    """Cỡ figure KHỞI TẠO khớp tỉ lệ span chặt (cả 2 hướng ngang/
    dọc); _build_wall_section_cell sẽ fit lại đúng theo bề rộng ô
    thật khi canvas được cấp kích thước."""
    x_lo, x_hi, y_lo, y_hi = _wall_section_spans(sec, n_seg, rot_deg)
    ratio = (x_hi - x_lo) / max(1e-9, y_hi - y_lo)
    if ratio >= 1.0:
        w, h = 5.5, 5.5 / ratio
    else:
        h, w = 4.6, 4.6 * ratio
    return (min(6.0, max(2.0, w)), min(5.0, max(1.8, h)))


def _dim_h(ax, x1, x2, y, text, text_dy=0.30, fs=8):
    """DIM ngang kiểu bản vẽ: đường dim + 2 mũi tên vào trong + số
    ở giữa phía trên đường (text_dy theo đơn vị dữ liệu)."""
    ax.annotate("", xy=(x1, y), xytext=(x2, y),
                arrowprops=dict(arrowstyle="<->", color="black", lw=0.8,
                                shrinkA=0, shrinkB=0), zorder=4)
    if text:
        ax.text((x1 + x2) / 2.0, y + text_dy, text, fontsize=fs,
                weight="bold", ha="center", va="bottom", zorder=4)


def _wall_bar_floor_apply(ax):
    """Tương thích ngược (lát hiển thị 2026-10-27): thép nay vẽ
    bằng scatter cỡ điểm cố định nên không còn Circle để áp sàn;
    hàm luôn trả False (không vẽ lại). Giữ tên hàm để code cũ/
    test ngoài không vỡ khi import."""
    return False


def draw_wall_section_ax(ax, sec, meta=None, na_info=None,
                         show_compression=False, rot_deg=0):
    """Vẽ mặt cắt vách (tiết diện luôn là rect từ build_wall_section)
    lên axes có sẵn — dùng chung cho hình sau CHECK và live preview.

    meta (từ build_wall_section): dim_segments -> hàng DIM phân đoạn
    Lb | đoạn giữa | Lb ở chế độ vùng biên. na_info +
    show_compression=True (sau CHECK): tô vùng nén xanh + đường
    trung hòa đỏ đứt — cùng quy ước/hàm ý như draw_compression_zone_ax
    của cột (Sutherland–Hodgman theo nửa mặt phẳng nén exact).

    rot_deg (2026-10-24): sec/meta/na_info truyền vào luôn ở khung
    CANONICAL (x theo Lw vật lý, y theo tw — xem _wall_display_geom);
    MỌI phần tử vẽ (đường bao, thép, vùng biên, vùng nén + đường
    trung hòa, dim + nhãn, mũi tên t2/t3) đều qua cùng một phép
    xoay _rot_xy quanh tâm tiết diện nên hình ở 90/180/270° là hình
    0° đã xoay cứng, không hoán đổi nhãn dim. rot_deg=0 -> hình vẽ
    giống hệt trước đây.
    """
    import matplotlib.patches as mpatches
    from matplotlib.lines import Line2D
    from matplotlib.patches import Polygon as MplPolygon
    rot = int(rot_deg or 0) % 360

    def R(x, y):
        return _rot_xy(x, y, rot)

    def RP(pts):
        return [R(px, py) for px, py in pts]

    # adjustable="box": giữ tỉ lệ đơn vị 2 trục bằng nhau bằng cách
    # co hộp axes về đúng tỉ lệ span (căn giữa), KHÔNG đụng tới
    # lims. Bản cũ dùng "datalim" (giãn lims ở phương không khống
    # chế) nhưng mỗi lần vẽ lại lims là matplotlib lại in warning
    # "Ignoring fixed y/x limits..." ra console — tỉ lệ hộp khác
    # tỉ lệ span xảy ra thường xuyên (pad 9px làm lệch tỉ lệ ở
    # figsize khởi tạo; canvas bị kéo cao/thấp hơn need ở tab Kết
    # quả; bbox_inches="tight" ở ảnh PDF). "box" cho cùng hình
    # tiết diện (cùng chiều khống chế, cùng tâm) mà không warning
    # và không đổi lims (khung nhìn tĩnh, khóa ở home). Ở ca bị
    # kẹp chiều cao (tiết diện xoay đứng trong ô thấp) hộp co theo
    # chiều ngang, nội dung vẫn lấp đầy chiều cao và căn giữa
    # theo chiều ngang.
    # Khung home tĩnh là span do _wall_section_spans trả.
    ax.set_aspect("equal", adjustable="box")
    cx, cy = float(sec.cx), float(sec.cy)
    DIA_COLORS = ["#DC2626", "#9333EA", "#EA580C", "#0891B2",
                  "#BE123C", "#CA8A04", "#0F766E", "#4D7C0F"]
    L2_COLOR = "#F59E0B"  # lớp 2 (thép phân bố): cam — như bên cột
    ax.set_axisbelow(True)
    ax.grid(True, color="#E8EDF3", linewidth=0.7)
    _rect = [(-cx / 2, -cy / 2), (cx / 2, -cy / 2),
             (cx / 2, cy / 2), (-cx / 2, cy / 2)]
    # Lát 1 (2026-10-27): tiết diện đa giác vẽ theo poly_verts, không
    # theo hình chữ nhật bao. _outline dùng cho cả đường bao, vùng
    # nén (Sutherland–Hodgman) và dim — rect giữ nguyên _rect.
    _is_poly = (getattr(sec, "kind", "rect") == "poly"
                and getattr(sec, "poly_verts", None))
    _outline = list(sec.poly_verts[0]) if _is_poly else _rect
    # Lát N–M: outline đa giác ở khung trọng tâm, dim_segments ở
    # khung bbox cũ — dịch dim theo bbox của outline để khớp mép:
    # _sx/_sy = -(trọng tâm) theo từng trục (rect: bbox đối xứng
    # nên _sx = _sy = 0, mọi công thức dưới đây trùng hệt cũ).
    _oxs = [p[0] for p in _outline]
    _oys = [p[1] for p in _outline]
    _ox0, _ox1, _oy0, _oy1 = min(_oxs), max(_oxs), min(_oys), max(_oys)
    _sx = (_ox0 + _ox1) / 2.0
    _sy = (_oy0 + _oy1) / 2.0
    ax.add_patch(MplPolygon(RP(_outline), closed=True, fill=True,
                            facecolor="#F4F7FB", edgecolor="black",
                            lw=2.0, zorder=2))
    # --- Vùng nén + đường trung hòa (chỉ khi đã CHECK và có na_info) ---
    if show_compression and na_info is not None \
            and na_info.get("found") and na_info.get("yp_na") is not None:
        _st, _ct, _yp = na_info["st"], na_info["ct"], na_info["yp_na"]

        def _naval(_x, _y):
            return -_x * _st + _y * _ct - _yp
        _pts = []
        for _i in range(len(_outline)):
            _cur = _outline[_i]
            _prv = _outline[_i - 1]
            _vc, _vp = _naval(*_cur), _naval(*_prv)
            _ci, _pi = _vc >= -1e-9, _vp >= -1e-9
            if _ci != _pi:
                _t = abs(_vp) / (abs(_vp) + abs(_vc))
                _pts.append((_prv[0] + _t * (_cur[0] - _prv[0]),
                             _prv[1] + _t * (_cur[1] - _prv[1])))
            if _ci:
                _pts.append(_cur)
        if len(_pts) >= 3:
            ax.add_patch(MplPolygon(RP(_pts), closed=True, fill=True,
                                    facecolor="#BFDBFE",
                                    edgecolor="#2563EB", lw=1.5,
                                    zorder=3, alpha=0.7))
        _ints = []
        _edges = [(_outline[i], _outline[(i + 1) % len(_outline)])
                  for i in range(len(_outline))]
        for (_x1, _y1), (_x2, _y2) in _edges:
            _v1, _v2 = _naval(_x1, _y1), _naval(_x2, _y2)
            if _v1 * _v2 < 0:
                _t = abs(_v1) / (abs(_v1) + abs(_v2))
                _ints.append((_x1 + _t * (_x2 - _x1),
                              _y1 + _t * (_y2 - _y1)))
        if len(_ints) >= 2:
            _ints.sort(key=lambda p: p[0] * _ct + p[1] * _st)
            _p1 = R(*_ints[0])
            _p2 = R(*_ints[-1])
            ax.plot([_p1[0], _p2[0]], [_p1[1], _p2[1]],
                    "--", color="#DC2626", linewidth=1.5, zorder=4)
    # Tô phân biệt vùng biên ở chế độ vùng biên (nền xám nhạt 2 đầu)
    # — chỉ rect: đa giác lát 1 không tô dải theo dim_segments x
    # (dải full-height sẽ tô sai vùng lõm của T/L/C/U).
    _segs = [(x1 + _sx, x2 + _sx, lab)
             for (x1, x2, lab) in ((meta or {}).get("dim_segments")
                                   or [])]
    if _segs and not _is_poly:
        for _x1, _x2, _lab in (_segs[0], _segs[-1]):
            ax.add_patch(MplPolygon(
                RP([(_x1, -cy / 2), (_x2, -cy / 2),
                    (_x2, cy / 2), (_x1, cy / 2)]),
                closed=True, fill=True,
                facecolor="#E0E7FF", edgecolor="none", zorder=2.5,
                alpha=0.55))
    # Thép theo (layer, dia) — Lát hiển thị 2026-10-27 (chấm
    # thích ứng, sau phản hồi user 8dd839c): ĐĨA THEO ĐƠN VỊ
    # DỮ LIỆU (Circle bán kính D/2, D từ _wall_bar_dot_diam),
    # KHÔNG còn scatter cỡ điểm cố định 4.0pt và KHÔNG quay lại
    # Circle tỉ lệ thật (đường kính = dia thanh). Vì axes có
    # aspect equal, đĩa trong không gian dữ liệu tự cho đường
    # kính theo px = D × (px/mm) ở mọi figure/dpi/resize/PDF,
    # không cần handler draw_event (điểm yếu khiến ảnh user
    # 9b6481f gần như không thấy thép). D = 42 mm ở đa giác
    # (gấp 3.5 lần d12 thật) nên ở tỉ lệ C/U vẫn ~3.7px, không
    # phải ~1px như thời Circle tỉ lệ thật; ở phẳng D = 49 mm.
    # Màu giữ đúng legend cũ: lớp 1 theo DIA_COLORS, lớp 2 cam
    # L2_COLOR (thép đa giác toàn lớp 2 nên legend D14 cam như
    # trước, không đổi màu). Thanh trong ô nút giao cùng nhóm
    # lớp 2 nên cùng cỡ/màu, nhìn rõ như thanh chu vi. zorder=7
    # trên cả mũi tên trục (6) để chấm không bị trục che.
    _dot_diam = _wall_bar_dot_diam(sec, meta)
    _dot_rad = _dot_diam / 2.0
    groups = {}
    for r in sec.rebars:
        groups.setdefault((r.layer, r.dia), []).append(r)
    dias_l1 = sorted(set(d for (ly, d) in groups if ly == 1),
                     reverse=True)
    dia_color = {d: DIA_COLORS[i % len(DIA_COLORS)]
                 for i, d in enumerate(dias_l1)}
    legend_handles = []
    _bar_items = []
    for (layer, dia) in sorted(groups, key=lambda k: (k[0], -k[1])):
        pts = groups[(layer, dia)]
        color = dia_color.get(dia, "#DC2626") if layer == 1 else L2_COLOR
        for p in pts:
            _qx, _qy = R(p.x, p.y)
            ax.add_patch(mpatches.Circle(
                (_qx, _qy), _dot_rad, facecolor=color,
                edgecolor="white", linewidth=0.5, zorder=7))
        legend_handles.append(Line2D(
            [0], [0], marker="o", color="none", markerfacecolor=color,
            markeredgecolor="white",
            markersize=WALL_BAR_DIAM_PT,
            label=f"D{dia:.0f}"))
    # Legend thép: box viền TRONG góc trên-phải của axes (vùng luôn
    # trống: dải nội dung nằm giữa khung, dim ở mép dưới/trái). Đặt
    # ngoài axes như trước tốn ~94px chiều rộng cho cột legend, làm
    # tỉ lệ vẽ co theo chiều ngang — vách dẹt bị thiệt nặng nhất.
    if legend_handles:
        leg = ax.legend(handles=legend_handles, loc="upper right",
                        bbox_to_anchor=(1.0, 1.0), ncol=1,
                        frameon=True, fontsize=8,
                        facecolor="white", edgecolor="#D1D5DB")
        for txt in leg.get_texts():
            txt.set_fontweight("bold")
    # Trục t2 (ngang, xanh lá) / t3 (đứng, xanh dương) tại tâm —
    # độ dài mũi tên tỉ lệ theo từng phương để nằm gọn trong khung;
    # đầu mũi tên + nhãn đi theo cùng phép xoay R như mọi phần tử.
    # Lát hiển thị: đa giác dùng _unit (0.35*min(cx,cy)) cho phần
    # chìa của t3 thay cho cy, cùng lý do thu span ở
    # _wall_section_spans (tránh t3 chìa 0.85*3000 mm ở C/U).
    _unit = 0.35 * min(cx, cy) if _is_poly else cy
    a2 = 0.30 * cx
    a3 = cy / 2 + 0.85 * _unit
    ax.annotate("", xy=R(a2, 0.0), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color="#16A34A", lw=2.0,
                                shrinkA=0, shrinkB=0), zorder=6)
    ax.annotate("", xy=R(0.0, a3), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color="#2563EB", lw=2.0,
                                shrinkA=0, shrinkB=0), zorder=6)
    _lt2 = R(a2 * 1.03, 0.0)
    _ha, _va = _dir_ha_va(*R(1.0, 0.0))
    ax.text(_lt2[0], _lt2[1], "t2", fontsize=8, color="#15803D",
            weight="bold", va=_va, ha=_ha, zorder=6)
    _lt3 = R(0.0, a3 + 0.16 * _unit)
    _ha, _va = _dir_ha_va(*R(0.0, 1.0))
    ax.text(_lt3[0], _lt3[1], "t3", fontsize=8, color="#1D4ED8",
            weight="bold", va=_va, ha=_ha, zorder=6)

    # --- DIM từng khoảng (format web 2026-10-23) ---
    # Mọi đường gióng/đường dim/điểm neo chữ đều định nghĩa ở khung
    # canonical rồi qua R; góc chữ theo _rot_text (không lộn ngược).
    def _ext(p1, p2):
        q1, q2 = R(*p1), R(*p2)
        ax.plot([q1[0], q2[0]], [q1[1], q2[1]], color="black", lw=0.7)

    def _dim(p1, p2, text, anchor, base_rot, ha, va):
        q1, q2 = R(*p1), R(*p2)
        ax.annotate("", xy=q1, xytext=q2,
                    arrowprops=dict(arrowstyle="<->", color="black",
                                    lw=0.8, shrinkA=0, shrinkB=0),
                    zorder=4)
        if text:
            qa = R(*anchor)
            rr, flip = _rot_text(base_rot, rot)
            ax.text(qa[0], qa[1], text, fontsize=8, weight="bold",
                    ha=_flip_ha(ha) if flip else ha,
                    va=_flip_va(va) if flip else va,
                    rotation=rr, zorder=4)

    # Thứ tự DIM dưới đáy (quyết user 2026-10-24): hàng phân đoạn
    # Lb | đoạn giữa | Lb SÁT mặt cắt hơn, kích thước tổng Lw ở
    # DƯỚI CÙNG — ngược thứ tự cũ (tổng ở trên, phân đoạn ở dưới).
    # Hàng 1 (sát đáy): phân đoạn (chỉ chế độ vùng biên).
    if _segs:
        _y_seg = _oy0 - 0.62 * _unit
        for _x1, _x2, _lab in _segs:
            for _xx in (_x1, _x2):
                _ext((_xx, _oy0 - 0.10 * _unit),
                     (_xx, _y_seg - 0.16 * _unit))
            _dim((_x1, _y_seg), (_x2, _y_seg), _lab,
                 ((_x1 + _x2) / 2.0, _y_seg + 0.14 * _unit),
                 0, "center", "bottom")
    # Hàng 2 (dưới cùng): kích thước tổng Lw, đường gióng từ 2 mép.
    # Nhãn Lw ở TRÊN đường dim (quyết user 2026-10-25, theo ghi chú
    # trên PDF tóm tắt: "ghi phía trên dim" / "chuyển lên trên
    # đường dim") — nằm trong khoảng giữa hàng phân đoạn và đường
    # dim tổng, cùng mẫu anchor +0.14cy/va="bottom" như nhãn phân
    # đoạn. Quyết user 2026-10-25 (ảnh tab Kết quả): đẩy dim tổng
    # sát lên chút nữa — từ -1.70cy về -1.45cy (lên 0.25cy):
    # khe tới hàng phân đoạn (-0.62cy) còn 0.83cy, nhãn Lw
    # (-1.31cy) vẫn cách hàng phân đoạn 0.69cy nên không đè;
    # span đáy (-cy/2 - 2.29cy) giữ nguyên nên hình không đổi
    # tỉ lệ/vị trí, chỉ đường dim tổng dịch lên trong khung.
    # Hàm này dùng chung GUI + PDF (wall_pdf_figs) nên PDF tóm
    # tắt vách cũng dịch dim tổng lên cùng mức.
    _y_tot = _oy0 - 1.45 * _unit
    for _xx in (_ox0, _ox1):
        _ext((_xx, _oy0 - 0.10 * _unit), (_xx, _y_tot - 0.16 * _unit))
    # Nhãn tổng theo meta (lát 1): đa giác dùng nhãn riêng theo
    # loại (vd ell: L1/L2, C/U: Bf/Lw); rect giữ Lw/tw như cũ.
    _lab_x = (meta or {}).get("dim_total_x_label") or f"Lw = {cx:.0f} mm"
    _lab_y = (meta or {}).get("dim_total_y_label") or f"tw = {cy:.0f} mm"
    _dim((_ox0, _y_tot), (_ox1, _y_tot), _lab_x,
         (_sx, _y_tot + 0.14 * _unit), 0, "center", "bottom")
    # DIM đứng bên trái: kích thước tổng tw (rect) hoặc tổng y
    # của đa giác (C/U: Lw, barbell: Bf, ...).
    _x_dim = _ox0 - 0.045 * cx
    for _yy in (_oy0, _oy1):
        _ext((_ox0 - 0.012 * cx, _yy), (_x_dim - 0.008 * cx, _yy))
    _dim((_x_dim, _oy0), (_x_dim, _oy1), _lab_y,
         (_x_dim - 0.018 * cx, _sy), 90, "right", "center")
    # DIM phân đoạn dọc bên trái — chỉ C/U (lát 1): hồi Lr đo theo
    # trục thân, vẽ ở cột riêng bên ngoài dim tổng để không đè.
    _segs_y = [(y1 + _sy, y2 + _sy, lab)
               for (y1, y2, lab) in
               ((meta or {}).get("dim_segments_y") or [])]
    if _segs_y:
        _x_seg_y = _ox0 - 0.28 * cx  # lat hien thi: cach cot dim tong (-0.045cx) du de nhan doc khong de nhau
        for _y1, _y2, _lab in _segs_y:
            for _yy in (_y1, _y2):
                _ext((_ox0 - 0.012 * cx, _yy),
                     (_x_seg_y - 0.008 * cx, _yy))
            _dim((_x_seg_y, _y1), (_x_seg_y, _y2), _lab,
                 (_x_seg_y - 0.018 * cx, (_y1 + _y2) / 2.0),
                 90, "right", "center")
    x_lo, x_hi, y_lo, y_hi = _wall_section_spans(sec, len(_segs), rot)
    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(y_lo, y_hi)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    # Lát hiển thị: thép là scatter cố định nên không còn hook
    # draw_event/sàn Circle. Giữ thuộc tính _wall_bar_items rỗng
    # cho tương thích code đọc nó (luôn là list rỗng, không phải
    # danh sách Circle nữa).
    try:
        ax._wall_bar_items = []
    except Exception:
        pass


def build_wall_shear_rows(full):
    """Dựng các hàng bảng cắt vách từ dict kết quả đã tính 1 lần.

    full: dict wall_tcvn_full. Mỗi hàng là (nhãn, trong MP, ngoài
    MP) dạng chuỗi đã format sẵn để _build_wall_shear_table chỉ việc
    vẽ. Hàng (98) KHÔNG có hàng riêng (quy ước cột: engine vẫn kiểm
    (98), qsw dưới đây đã là giá trị sau khi loại nhóm vi phạm;
    khi có nhóm bị loại thì ghi chú ngay ở hàng qsw).
    Quyết user 2026-10-25 08:06: hàng cắt GUI khớp PDF — nhãn về
    đúng nhãn PDF "Lực cắt tính toán, V2 / V3", thông tin DCM chuyển
    sang HẬU TỐ ở ô giá trị trong MP khi DCM bật (kể cả V = 0):
    "1200.0 kN (1.5 Ved, TCVN 9386-1:2025 §5.4.2.4(7))", trơn khi
    DCM tắt; ngoài MP vẫn "(không phóng đại)". Ghi chú KHÔNG hiển
    thị V_raw (quyết user 2026-10-24); V_raw vẫn giữ nguyên trong
    dict kết quả.
    Builder này chỉ dùng cho bảng GUI tab Kết quả + tests (PDF
    tóm tắt/chi tiết có builder riêng, không dùng chung)."""
    full = full or {}

    def _dc_txt(sh):
        dc = sh.get("dc")
        if dc is None:
            return "—"
        try:
            v = float(dc)
        except Exception:
            return "—"
        return f"{v:.3f}" if math.isfinite(v) else "∞"

    def _col(sh, in_plane):
        """Một cột (trong hoặc ngoài MP) dạng dict nhãn -> chuỗi."""
        parts = (sh or {}).get("parts") or {}
        pending = (sh or {}).get("V_cap") is None
        if pending:
            return None
        v_d = sh.get("V_d")
        if in_plane:
            # Hậu tố DCM ở Ô GIÁ TRỊ (như PDF tóm tắt vách sau
            # 08:06); nhãn hàng trơn "Lực cắt tính toán, V2 / V3"
            # nên không còn trùng lặp thông tin DCM ở nhãn.
            v_txt = (f"{float(v_d):.1f} kN (1.5 Ved, "
                     f"TCVN 9386-1:2025 §5.4.2.4(7))"
                     if sh.get("seismic_applied")
                     else f"{float(v_d):.1f} kN")
        else:
            v_txt = f"{float(v_d):.1f} kN (không phóng đại)"
        # Thép bố trí + Asw/qsw/req/prov: cùng công thức 2 phương
        # (ngoài MP mặc định 2 nhánh × φ(dia_h) @ s_h cùng cấp thép
        # với trong MP — quyết user 2026-10-25; không có thép thì
        # parts cho sw_txt "không có thép ngang", Asw/qsw = 0).
        sw = parts.get("sw_txt", "—")
        grade = parts.get("steel_grade") or ""
        sw_txt = f"{sw} ({grade})" if grade else sw
        asw_txt = f"{float(parts.get('Asw', 0.0)):.0f} mm²"
        qsw = float(parts.get("qsw", 0.0) or 0.0)
        qsw_txt = f"{qsw:.1f} N/mm"
        if parts.get("dropped98"):
            qsw_txt += " (đã loại nhóm vi phạm (98))"
        rsw = float(parts.get("Rsw", 0.0) or 0.0)
        qmin = float(parts.get("qsw_min96", 0.0) or 0.0)
        req_txt = (f"{qmin / rsw:.3f} mm²/mm" if rsw > 0
                   else "— (không có thép)")
        s_h = float(parts.get("s_h", 0.0) or 0.0)
        asw = float(parts.get("Asw", 0.0) or 0.0)
        prov_txt = (f"{asw / s_h:.3f} mm²/mm" if s_h > 0
                    else "—")
        if parts.get("qb_mode") == "NONE":
            c96_txt = "— (không có thép)"
        elif parts.get("cond96_ok"):
            c96_txt = "✓ Đạt"
        else:
            c96_txt = "✗ Không đạt → Qb theo CT (97)"
        ok = sh.get("ok")
        concl = (("✓ ĐẠT" if ok else "✗ KHÔNG ĐẠT")
                 + f" (D/C {_dc_txt(sh)})")
        return {
            "Thép bố trí": sw_txt,
            "Lực cắt tính toán, V2 / V3": v_txt,
            "Kích thước tiết diện, bw × d":
                f"{float(parts.get('b', 0.0)):.0f} × "
                f"{float(parts.get('h0', 0.0)):.0f} mm",
            "Asw": asw_txt,
            "qsw = Rsw × Asw/s": qsw_txt,
            "Hệ số φn (§8.1.3.3.2)":
                f"{float(parts.get('phi_n', 0.0)):.3f}",
            "Điều kiện (96): qsw ≥ 0.25×Rbt×b": c96_txt,
            "Độ bền trên dải nén xiên, [Q]1":
                f"{float(parts.get('Qcap1', 0.0)):.1f} kN",
            "Qb": f"{float(parts.get('Qb', 0.0)):.1f} kN",
            "Qsw": f"{float(parts.get('Qsw', 0.0)):.1f} kN",
            "Độ bền trên vết nứt xiên, [Q] = Qb + Qsw":
                f"{float(parts.get('Qcap2', 0.0)):.1f} kN",
            "Chiều dài hình chiếu vết nứt xiên, C":
                f"{float(parts.get('C_opt', 0.0)):.0f} mm",
            "Asw/s yêu cầu (tối thiểu theo (96))": req_txt,
            "Asw/s bố trí": prov_txt,
            "Kết luận": concl,
        }

    labels = ["Thép bố trí",
              "Lực cắt tính toán, V2 / V3",
              "Kích thước tiết diện, bw × d",
              "Asw",
              "qsw = Rsw × Asw/s",
              "Hệ số φn (§8.1.3.3.2)",
              "Điều kiện (96): qsw ≥ 0.25×Rbt×b",
              "Độ bền trên dải nén xiên, [Q]1",
              "Qb",
              "Qsw",
              "Độ bền trên vết nứt xiên, [Q] = Qb + Qsw",
              "Chiều dài hình chiếu vết nứt xiên, C",
              "Asw/s yêu cầu (tối thiểu theo (96))",
              "Asw/s bố trí",
              "Kết luận"]
    col_in = _col(full.get("shear_in") or {}, True)
    col_out = _col(full.get("shear_out") or {}, False)
    rows = []
    for lab in labels:
        in_txt = col_in[lab] if col_in is not None else "CHƯA KIỂM"
        out_txt = col_out[lab] if col_out is not None else "CHƯA KIỂM"
        rows.append((lab, in_txt, out_txt))
    return rows


def wall_qb_formula_note(full):
    """Ghi chú diễn giải công thức Qb dưới bảng cắt (tab Kết quả).

    1 đoạn gọn: công thức đúng như engine đang tính (TCVN
    5574:2018 §8.1.3 qua stirrup.check_shear) + thay số thật cho
    cả 2 phương. Chỉ đọc dict kết quả đã lưu, không tính lại.
    Trả về "" khi thiếu dữ liệu (cắt pending) để caller bỏ qua.
    """
    try:
        p_in = (full.get("shear_in") or {}).get("parts") or {}
        p_out = (full.get("shear_out") or {}).get("parts") or {}
        rbt = float(full["sec"].concrete.Rbt)
        if not p_in and not p_out:
            return ""
        _head = (
            "Qb (TCVN 5574:2018 §8.1.3): khảo sát C ∈ [h0, 2h0], "
            "lấy [Q]2 = Qb + Qsw nhỏ nhất; (90) Qb = "
            "φn×1,5×Rbt×b×h0²/C khi (96) đạt; (97) Qb = "
            "φn×4×1,5×h0²×qsw/C khi (96) không đạt; "
            "Qsw = 0,75×qsw×C; Qb chặn trong [0,5; 2,5]×Rbt×b×h0. ")
        # Lát cắt đa giác: 1 phương pending (C/U ngoài MP) thì chỉ
        # hiện thay số của phương còn mở, không ẩn cả 2 như trước.
        _in_txt = (f"Trong MP: {qb_formula_sub(p_in, rbt)}"
                   if p_in else "Trong MP: CHƯA KIỂM")
        _out_txt = (f"Ngoài MP: {qb_formula_sub(p_out, rbt)}"
                    if p_out else "Ngoài MP: CHƯA KIỂM")
        return _head + _in_txt + " " + _out_txt
    except Exception:
        return ""


class WallMixin:
    """Các method của chế độ Vách: frame nhập, toggle, JSON, chặn lát 0."""

    # ---------------- Nhận diện chế độ ----------------
    def is_wall(self):
        cb = getattr(self, "cb_member", None)
        return cb is not None and cb.get() == "Vách"

    # ---------------- Frame nhập liệu vách ----------------
    def _sec_wall(self):
        """Dựng các frame nhập liệu vách (ẩn ở chế độ Cột):
        '2. Tiết diện' + '3. Bố trí cốt thép dọc' + '4. Chiều dài tính
        toán & Uốn dọc' theo format web Vietcons, và frame 'Thép ngang,
        đai vùng biên, kháng chấn'
        giữ các ô ngoài phạm vi web (thép ngang, đai vùng biên,
        kháng chấn) để không mất plumbing các lát sau."""
        f2 = self._frame(T("2. Tiết diện"))
        self.frm_wall = f2
        f3 = self._frame(T("3. Bố trí cốt thép dọc"))
        self.frm_wall_rebar = f3
        f4 = self._frame(T("4. Chiều dài tính toán & Uốn dọc"))
        self.frm_wall_len = f4
        fx = self._frame(T("Thép ngang, đai vùng biên, kháng chấn"))
        self.frm_wall_extra = fx
        self._wall_frames = (f2, f3, f4, fx)
        D = WALL_DEFAULTS

        def _entry(parent, default, width=12):
            e = ttk.Entry(parent, width=width)
            e.insert(0, str(default))
            return e

        def _combo(parent, values, default, width=16):
            cb = ttk.Combobox(parent, values=values, state="readonly",
                              width=width)
            cb.set(str(default))
            return cb

        def _hdr(parent, text, r, span=4):
            ttk.Label(parent, text=text, font=("", 10, "bold")).grid(
                row=r, column=0, columnspan=span, sticky=tk.W,
                padx=4, pady=(8, 2))
            return r + 1

        # Layout 2 cột kiểu panel Cột (_mat_row): mỗi hàng 2 cặp
        # [nhãn][nhập][nhãn][nhập], nhãn lấy rộng tự nhiên (không
        # width cố định như _row). KHÔNG dùng uniform như panel Cột:
        # nhãn vách dài (vd "Thép ngang: cấp thép (Rsw cắt vách)")
        # làm uniform phình frame fx tới 958px > panel 686px, cắt mất
        # cặp phải; weight=1 không uniform vẫn giữ 2 cặp/hàng, 2 ô
        # nhập mỗi hàng rộng bằng nhau, và frame vừa panel.
        def _grid4(parent):
            for _c in range(4):
                parent.columnconfigure(_c, weight=1)

        def _pair(parent, r, llab, lwid, rlab, rwid):
            ll = ttk.Label(parent, text=llab, style="Muted.TLabel")
            ll.grid(row=r, column=0, sticky=tk.W, padx=(4, 8), pady=5)
            lwid.grid(row=r, column=1, sticky=tk.EW, padx=4, pady=5)
            rl = ttk.Label(parent, text=rlab, style="Muted.TLabel")
            rl.grid(row=r, column=2, sticky=tk.W, padx=(4, 8), pady=5)
            rwid.grid(row=r, column=3, sticky=tk.EW, padx=4, pady=5)
            return ll, rl

        def _single(parent, r, lab, wid):
            # Hàng bắt buộc full-width: nhãn col 0 + widget span 1-3.
            lbl = ttk.Label(parent, text=lab, style="Muted.TLabel")
            lbl.grid(row=r, column=0, sticky=tk.W, padx=(4, 8), pady=5)
            wid.grid(row=r, column=1, columnspan=3, sticky=tk.EW,
                     padx=4, pady=5)
            return lbl

        def sv(v):
            try:
                fv = float(v)
            except Exception:
                return str(v)
            return str(int(fv)) if fv.is_integer() else str(fv)

        # ===== Mục 2. Tiết diện (web) =====
        _grid4(f2)
        r = 0
        self.w_cb_sectype = _combo(f2, _SECTYPES, _SECTYPES[0], width=24)
        _single(f2, r, "Loại tiết diện vách / lõi", self.w_cb_sectype)
        r += 1
        # Hàng import DXF (lát DXF, 2026-10-28): ngay sau hàng loại
        # tiết diện; nút gọi read_dxf_section (chung với cột) +
        # dialog preview kiểu _preview_dxf_section của cột, rồi lưu
        # self._wall_dxf_data, đặt combobox thành DXF, refresh
        # preview. Nhãn thông tin ẩn khi chưa import (grid_remove),
        # hiện khi đã import (tên file, Ag, số thanh, As).
        self._wall_dxf_data = None
        self.w_var_wall_dxf_info = tk.StringVar(value="")
        self.w_btn_wall_dxf = ttk.Button(
            f2, text="Import tiết diện (.dxf)",
            command=self._on_import_wall_dxf)
        self.w_btn_wall_dxf.grid(row=r, column=0, sticky=tk.W,
                                 padx=4, pady=5)
        self.w_lbl_wall_dxf_info = ttk.Label(
            f2, textvariable=self.w_var_wall_dxf_info,
            style="Muted.TLabel", wraplength=320, justify=tk.LEFT)
        self.w_lbl_wall_dxf_info.grid(row=r, column=1, columnspan=3,
                                      sticky=tk.W, padx=4, pady=5)
        self.w_lbl_wall_dxf_info.grid_remove()
        self._wall_dxf_row = r
        r += 1
        # Khung xoay: chỉ tạo widget ở đây, chưa grid — hàng xoay
        # được gộp chung với checkbox Đối xứng ở hàng _r_sym dưới
        # (lát 2 cột 2026-10-29): 2 tùy chọn tiết diện chung 1 hàng,
        # tiết kiệm 1 hàng cho Barbell/C/U (cả 2 cùng hiện); loại
        # chỉ có xoay (T/L/DXF) thì nửa phải trống như hàng Bf đơn
        # của T/C/U đối xứng, loại phẳng thì cả hàng trống (cao 0).
        rot_fr = ttk.Frame(f2)
        self.w_rot_var = tk.StringVar(value="0°")
        ttk.Label(rot_fr, textvariable=self.w_rot_var, width=5).pack(
            side=tk.LEFT)
        ttk.Button(rot_fr, text="Xoay +90°",
                   command=self._rotate_wall).pack(side=tk.LEFT, padx=4)
        self._wall_rot_deg = 0
        self.w_rot_fr = rot_fr
        self.w_en_Lw = _entry(f2, D["Lw"])
        self.w_en_tw = _entry(f2, D["tw"])
        _ll_main, _rl_main = _pair(f2, r, "Lw (mm)", self.w_en_Lw,
                                   "tw (mm)", self.w_en_tw)
        self._lbl_wall_main_l, self._lbl_wall_main_r = _ll_main, _rl_main
        # Các ô động theo loại (lát 1): cùng hàng chính nhưng widget
        # phải luân phiên (tee/ell/C/U đổi nhãn + ô phải/trái); các
        # ô này được grid/grid_remove trong
        # _update_wall_sectype_fields — không tạo widget mới mỗi lần
        # đổi loại (giữ nguyên giá trị user đã nhập khi chuyển qua
        # lại, trừ lần đầu sang loại đó thì điền mặc định web).
        self.w_en_sec_L1 = _entry(f2, D.get("sec_L1", 2000))
        self.w_en_sec_L2 = _entry(f2, D.get("sec_L2", 1800))
        self.w_en_sec_t = _entry(f2, D.get("sec_t", 300))
        _r_main = r
        r += 1
        # Hàng tiêu đề phụ (Barbell/C: "KÍCH THƯỚC HAI ĐẦU", U:
        # "KÍCH THƯỚC HAI CÁNH" — đúng chữ web; T/L không có).
        self.w_lbl_sec_sub = ttk.Label(f2, text="", font=("", 9, "bold"))
        self.w_lbl_sec_sub.grid(row=r, column=0, columnspan=4,
                                sticky=tk.W, padx=4, pady=5)
        _r_sub = r
        r += 1
        # Hàng gộp Xoay + Đối xứng (lát 2 cột 2026-10-29; xem ghi
        # chú ở khung xoay trên): nhãn xoay col 0, khung xoay col 1,
        # checkbox Đối xứng (Barbell/C/U; bật: 1 cặp, tắt: 2 cặp 1/2)
        # col 2 span 2. Ẩn/hiện 2 phía độc lập qua
        # _update_wall_rotation_visibility (xoay) và
        # _update_wall_sectype_fields (đối xứng, col 2 span 2).
        self._lbl_wall_rot = ttk.Label(f2, text="Xoay tiết diện",
                                       style="Muted.TLabel")
        self._lbl_wall_rot.grid(row=r, column=0, sticky=tk.W,
                                padx=(4, 8), pady=5)
        self.w_rot_fr.grid(row=r, column=1, sticky=tk.W, padx=4, pady=5)
        self.w_var_sec_sym = tk.BooleanVar(
            value=bool(D.get("sec_sym", True)))
        self.w_chk_sec_sym = tk.Checkbutton(
            f2, text="Đối xứng hai đầu", variable=self.w_var_sec_sym,
            bg="white", activebackground="white", highlightthickness=0,
            command=self._on_wall_sec_sym)
        self.w_chk_sec_sym.grid(row=r, column=2, columnspan=2,
                                sticky=tk.W, padx=4, pady=5)
        _r_sym = r
        r += 1
        # Hàng Bf/Tf (Barbell) — T/L/C/U dùng các hàng riêng dưới.
        self.w_en_sec_bf = _entry(f2, D.get("sec_bf", 1000))
        self.w_en_sec_tf = _entry(f2, D.get("sec_tf", 450))
        _ll, _rl = _pair(f2, r, "Bf (mm)", self.w_en_sec_bf,
                         "Tf (mm)", self.w_en_sec_tf)
        self._lbl_sec_bf, self._lbl_sec_tf = _ll, _rl
        _r_bf_tf = r
        r += 1
        # Hàng Bf2/Tf2 (Barbell không đối xứng).
        self.w_en_sec_bf2 = _entry(f2, D.get("sec_bf2", 1000))
        self.w_en_sec_tf2 = _entry(f2, D.get("sec_tf2", 450))
        _ll, _rl = _pair(f2, r, "Bf2 (mm)", self.w_en_sec_bf2,
                         "Tf2 (mm)", self.w_en_sec_tf2)
        self._lbl_sec_bf2, self._lbl_sec_tf2 = _ll, _rl
        _r_bf2_tf2 = r
        r += 1
        # Hàng Bf đơn (Tee/C) / Bf đôi (U không đối xứng) dùng CHUNG
        # hàng Bf/Tf trên: ô phải luân phiên Tf (Barbell) / Bf2 (U),
        # ô trái luôn Bf; Tee/C ẩn ô phải. (Không tạo hàng riêng vì
        # 1 widget Tk chỉ có 1 vị trí grid — _update_wall_sectype_
        # fields grid lại tường minh mỗi lần đổi loại.)
        # Hàng Lr/Lr2 (C) — đối xứng: chỉ Lr, ô phải ẩn.
        self.w_en_sec_lr = _entry(f2, D.get("sec_lr", 600))
        self.w_en_sec_lr2 = _entry(f2, D.get("sec_lr2", 600))
        _ll, _rl = _pair(f2, r, "Lr (mm)", self.w_en_sec_lr,
                         "Lr2 (mm)", self.w_en_sec_lr2)
        self._lbl_sec_lr, self._lbl_sec_lr2 = _ll, _rl
        _r_lr = r
        r += 1
        # Hàng t đơn (Ell) — full-width.
        self._lbl_sec_t = _single(f2, r, "t (mm)", self.w_en_sec_t)
        _r_t = r
        r += 1
        self._wall_sec_rows = {
            "main": _r_main, "sub": _r_sub, "sym": _r_sym,
            "bf_tf": _r_bf_tf, "bf2_tf2": _r_bf2_tf2,
            "lr": _r_lr, "t": _r_t,
        }
        self._wall_sectypes_seen = {"rect"}
        # Giá trị theo từng loại (lát 1): chuyển qua lại khôi phục
        # đúng giá trị user đã nhập ở loại đó (các khóa dùng chung
        # như sec_bf/sec_t không bị mặc định của loại mới ghi đè).
        self._wall_sec_current = "rect"
        self._wall_sec_values = {}
        # Nhãn hàng chế độ thép mục 3 (để ẩn khi loại mới không có
        # dropdown — xem _update_wall_sectype_fields).
        self._lbl_wall_steel_mode = None
        # (Ghi chú GĐ1 dưới mục 2 đã bỏ theo ghi chú đỏ của user
        # 2026-10-25 — chỉ xóa hiển thị, không đổi loại tiết diện
        # hay logic xoay; hàng xoay vẫn ẩn/hiện qua
        # _update_wall_rotation_visibility.)

        # ===== Mục 3. Bố trí cốt thép dọc (web) =====
        _grid4(f3)
        r = 0
        self.w_cb_steel_mode = _combo(
            f3, [lab for _, lab in _STEEL_MODES],
            _label_of(_STEEL_MODES, D["steel_mode"],
                      "Phân bố đều theo chu vi"), width=24)
        self._lbl_wall_steel_mode = _single(
            f3, r, "Chế độ bố trí thép", self.w_cb_steel_mode)
        self._wall_steel_mode_row = r
        r += 1
        self.w_en_cover = _entry(f3, D["cover"])
        # Ô đơn trước 2 khung con — giữ full-width (không ghép với ô
        # trong khung con để không phá nhóm chế độ thép).
        _single(f3, r, "Lớp bảo vệ cốt đai, c (mm)", self.w_en_cover)
        r += 1
        # -- Khung con (a): phân bố đều theo chu vi --
        self.w_frm_per = ttk.Frame(f3)
        self.w_frm_per.grid(row=r, column=0, columnspan=4, sticky=tk.EW)
        r += 1
        _grid4(self.w_frm_per)
        rr = 0
        self.w_cb_per_dia = _combo(self.w_frm_per, _DIAS_WEB,
                                   sv(D["per_dia"]))
        self.w_en_per_s = _entry(self.w_frm_per, D["per_s"])
        _pair(self.w_frm_per, rr, "Đường kính d", self.w_cb_per_dia,
              "Khoảng cách s (mm)", self.w_en_per_s)
        rr += 1
        # -- Khung con (b): tập trung vùng biên --
        self.w_frm_be = ttk.Frame(f3)
        self.w_frm_be.grid(row=r, column=0, columnspan=4, sticky=tk.EW)
        r += 1
        _grid4(self.w_frm_be)
        rr = 0
        rr = _hdr(self.w_frm_be, "Cốt thép vùng biên (2 đầu vách)", rr)
        # 6 ô nhập duy nhất (user chốt 2026-10-25, mô hình cột dọc):
        # nhập 1 bên, áp y hệt 2 đầu; tất cả thanh cùng db; mỗi vùng
        # có 2 hàng dọc Lb (mỗi hàng n_Lb thanh tính cả 2 góc) + mỗi
        # lớp (cột dọc theo tw: L_out cột ngoài từ đầu ngoài vào,
        # L_in cột trong từ hàng trong cùng đi ra) đóng góp n_tw
        # thanh Ở GIỮA.
        self.w_en_be_Lb = _entry(self.w_frm_be, D["be_Lb"])
        # Mặc định panel db = 28 (khớp ca mặc định hiện tại); WallInput
        # giữ mặc định 20 để test/file cũ không đổi hành vi.
        self.w_cb_be_dia = _combo(self.w_frm_be, _DIAS_WEB, "28")
        _pair(self.w_frm_be, rr, "Chiều dài Lb (mm)", self.w_en_be_Lb,
              "Đường kính db (chung)", self.w_cb_be_dia)
        rr += 1
        self.w_en_be_nLb = _entry(self.w_frm_be, D["be_n_Lb"])
        self.w_en_be_nTw = _entry(self.w_frm_be, D["be_n_tw"])
        _pair(self.w_frm_be, rr, "Số thanh theo chiều Lb",
              self.w_en_be_nLb, "Số thanh ở giữa theo chiều tw",
              self.w_en_be_nTw)
        rr += 1
        self.w_en_be_Lout = _entry(self.w_frm_be, D["be_L_out"])
        self.w_en_be_Lin = _entry(self.w_frm_be, D["be_L_in"])
        _pair(self.w_frm_be, rr, "Số lớp tw ngoài", self.w_en_be_Lout,
              "Số lớp tw trong", self.w_en_be_Lin)
        rr += 1
        rr = _hdr(self.w_frm_be, "Thép phân bố thân vách", rr)
        self.w_cb_web_dia = _combo(self.w_frm_be, _DIAS_WEB,
                                   sv(D["web_dia"]))
        self.w_en_web_s = _entry(self.w_frm_be, D["web_s"])
        _pair(self.w_frm_be, rr, "Đường kính d", self.w_cb_web_dia,
              "Khoảng cách s (mm)", self.w_en_web_s)
        rr += 1
        # (Ghi chú xám dưới khối vùng biên đã bỏ theo ghi chú đỏ của
        # user 2026-10-25 — chỉ xóa hiển thị, không đổi mô hình.)
        # (Khối "Số đọc trực tiếp" ở panel đã bỏ theo quyết user
        # 2026-10-24 — dữ liệu suy ra vẫn tính bình thường cho ô
        # mặt cắt/thẻ thép qua build_wall_section, chỉ không hiển
        # thị khối readout này ở panel nữa.)

        # ===== Mục 4. Chiều dài tính toán & Uốn dọc (web) =====
        # (2026-10-25, user chốt: dropdown P–δ 2 tùy chọn thay bằng
        # đúng 1 tick chọn. Tick = "tcvn", không tick = "none" — cùng
        # 2 giá trị _PD_OPTS cũ, JSON/engine không đổi. Mặc định
        # tick vào vì mặc định cũ là xét uốn dọc.)
        self.w_var_pd = tk.BooleanVar(
            value=(str(D.get("pd_method", "tcvn")) != "none"))
        self.w_chk_pd = tk.Checkbutton(
            f4, text="Xét uốn dọc theo TCVN 5574:2018",
            variable=self.w_var_pd, bg="white",
            activebackground="white", highlightthickness=0)
        self.w_chk_pd.grid(row=0, column=0, columnspan=3, sticky=tk.W,
                           padx=4, pady=5)
        bn = list(BOUNDARY_NAMES.values())
        for c, h in enumerate(("", "Phương X (trong mặt phẳng)",
                               "Phương Y (ngoài mặt phẳng)")):
            ttk.Label(f4, text=h, font=("", 9, "bold")).grid(
                row=1, column=c, padx=4, pady=2, sticky=tk.W)
        f4.columnconfigure(1, weight=1)
        f4.columnconfigure(2, weight=1)
        self.w_en_Lx_m = _entry(f4, D["Lx_m"])
        self.w_en_Ly_m = _entry(f4, D["Ly_m"])
        self.w_cb_lk_tx = _combo(f4, bn, "Ngàm nửa cứng")
        self.w_cb_lk_ty = _combo(f4, bn, "Ngàm nửa cứng")
        self.w_cb_lk_bx = _combo(f4, bn, "Ngàm nửa cứng")
        self.w_cb_lk_by = _combo(f4, bn, "Ngàm nửa cứng")
        self.w_en_psi_x = _entry(f4, D["psi_x"])
        self.w_en_psi_y = _entry(f4, D["psi_y"])
        # (Hàng hiển thị "Chiều cao tính toán L₀" đã bỏ theo ghi chú
        # của user 2026-10-25 — L₀ vẫn suy ra lúc tính từ L/ψ trong
        # engine, không đọc từ widget hiển thị nào.)
        _rows4 = [
            ("Chiều cao thông thủy vách L (m)", self.w_en_Lx_m,
             self.w_en_Ly_m),
            ("Liên kết đầu trên", self.w_cb_lk_tx, self.w_cb_lk_ty),
            ("Liên kết đầu dưới", self.w_cb_lk_bx, self.w_cb_lk_by),
            ("Hệ số ψ (tự điền theo LK)", self.w_en_psi_x,
             self.w_en_psi_y),
        ]
        for i, (lab, wx, wy) in enumerate(_rows4, start=2):
            ttk.Label(f4, text=lab, width=self._LBL_WIDTH,
                      anchor=tk.W).grid(row=i, column=0, sticky=tk.W,
                                        padx=4, pady=2)
            wx.grid(row=i, column=1, padx=4, pady=2, sticky=tk.EW)
            wy.grid(row=i, column=2, padx=4, pady=2, sticky=tk.EW)
        # Tải dài hạn cho φl (2026-10-28, Hướng dẫn BXD §5.1.2
        # (5-31)): hàng N chung + hàng M theo 2 phương X/Y của
        # mục 4 (X = trong MP, Y = ngoài MP). Để trống/0 → φl =
        # 2,0 như cũ; nhập đủ → φl tính từng phương độc lập.
        self.w_en_lt_N = _entry(f4, D["N_lt"])
        self.w_en_lt_Min = _entry(f4, D["M_in_lt"])
        self.w_en_lt_Mout = _entry(f4, D["M_out_lt"])
        ttk.Label(f4, text="Tải dài hạn N (kN) — φl",
                  width=self._LBL_WIDTH, anchor=tk.W).grid(
                      row=6, column=0, sticky=tk.W, padx=4, pady=2)
        self.w_en_lt_N.grid(row=6, column=1, padx=4, pady=2,
                            sticky=tk.EW)
        ttk.Label(f4, text="(0 → φl = 2,0)",
                  anchor=tk.W).grid(row=6, column=2, sticky=tk.W,
                                    padx=4, pady=2)
        ttk.Label(f4, text="Tải dài hạn M (kN·m) — φl",
                  width=self._LBL_WIDTH, anchor=tk.W).grid(
                      row=7, column=0, sticky=tk.W, padx=4, pady=2)
        self.w_en_lt_Min.grid(row=7, column=1, padx=4, pady=2,
                              sticky=tk.EW)
        self.w_en_lt_Mout.grid(row=7, column=2, padx=4, pady=2,
                               sticky=tk.EW)
        # (Ghi chú xám dưới mục 4 đã bỏ theo ghi chú đỏ của user
        # 2026-10-25 — chỉ xóa hiển thị, không đổi cách suy L₀.)

        # ===== Thép ngang, đai vùng biên, kháng chấn (ngoài format web) =====
        _grid4(fx)
        r = 0
        r = _hdr(fx, "Thép phân bố ngang (dùng cho cắt trong mặt phẳng)", r)
        self.w_cb_dia_h = _combo(fx, _DIAS, D["dia_h"])
        self.w_en_s_h = _entry(fx, D["s_h"])
        # Nhãn rút tiền tố "Thép ngang:" (đã có ở tiêu đề nhóm) để
        # 2 cặp vừa panel — xem ghi chú ở _grid4.
        _pair(fx, r, "Đường kính (mm)", self.w_cb_dia_h,
              "Khoảng cách s (mm)", self.w_en_s_h)
        r += 1
        self.w_cb_layers_h = _combo(fx, ["1", "2"], D["layers_h"])
        # Cấp thép ngang RIÊNG của vách (phần 3/7): quyết định Rsw cho
        # kiểm tra cắt trong mặt phẳng — KHÔNG dùng ô thép đai của cột
        # và KHÔNG lấy theo cấp thép dọc nữa. Mặc định CB400-V (theo
        # quy ước ô thép đai của cột); preset web chỉ đổi thép DỌC
        # sang CB500-V, không chạm ô này (xem _wall_web_preset_enter).
        self.w_cb_sw_steel = _combo(fx, list(STEEL_GRADES), "CB400-V")
        _ll, _lbl_sw = _pair(fx, r, "Số lớp lưới",
                             self.w_cb_layers_h,
                             "Cấp thép (Rsw cắt vách)",
                             self.w_cb_sw_steel)
        r += 1
        try:
            from gui.build_mixin import _ToolTip as _WallToolTip
            _WallToolTip(
                _lbl_sw,
                "Cấp thép ngang của VÁCH — quyết định Rsw cho kiểm tra "
                "cắt trong mặt phẳng (TCVN §8.1.3, qua qsw = Rsw·Asw/s).\n"
                "CB400-V → Rsw = 280 MPa; CB500-V → Rsw = 300 MPa.\n"
                "Khác với thép dọc (ô vật liệu dùng chung) và khác ô "
                "'Cấp độ bền thép đai' của chế độ Cột.")
            _WallToolTip(
                self.w_cb_sw_steel,
                "Cấp thép ngang của VÁCH — quyết định Rsw cho kiểm tra "
                "cắt trong mặt phẳng (TCVN §8.1.3, qua qsw = Rsw·Asw/s).")
        except Exception:
            pass
        r = _hdr(fx, "Đai vùng biên & vị trí đốt", r)
        self.w_cb_tie_dia = _combo(fx, _DIAS, D["tie_dia_be"])
        self.w_en_tie_s = _entry(fx, D["tie_s_be"])
        # Nhãn rút tiền tố "Đai vùng biên:" (đã có ở tiêu đề nhóm).
        _pair(fx, r, "Đường kính (mm)",
              self.w_cb_tie_dia, "Khoảng cách s (mm)",
              self.w_en_tie_s)
        r += 1
        self.w_en_tie_legs = _entry(fx, D["tie_legs_be"])
        self.w_cb_pos = _combo(
            fx, [lab for _, lab in _STORY_POS],
            _label_of(_STORY_POS, D["story_pos"], "Chân vách"))
        _pair(fx, r, "Số nhánh", self.w_en_tie_legs,
              "Vị trí đốt", self.w_cb_pos)
        r += 1
        self.w_en_hstory = _entry(fx, D["h_story"])
        self.w_en_htotal = _entry(fx, D["h_total"])
        _pair(fx, r, "Chiều cao đốt (mm)", self.w_en_hstory,
              "Tổng chiều cao vách (mm)", self.w_en_htotal)
        r += 1
        self.w_var_lb_auto = tk.BooleanVar(value=bool(D["lb_auto"]))
        tk.Checkbutton(
            fx, text="Tự lấy Lb theo yêu cầu khi vùng biên bắt buộc "
                     "(kèm cảnh báo)",
            variable=self.w_var_lb_auto, bg="white",
            activebackground="white", highlightthickness=0).grid(
                row=r, column=0, columnspan=4, sticky=tk.W, padx=4, pady=4)
        r += 1
        r = _hdr(fx, "Kháng chấn", r)
        self.w_cb_aci_class = _combo(
            fx, [lab for _, lab in _ACI_CLASS],
            _label_of(_ACI_CLASS, D["seismic_class"], "Đặc biệt (Ch.18)"))
        # Ô đơn (nhãn dài, hàng sau là checkbutton) — giữ full-width.
        self.w_lbl_aci_class = _single(
            fx, r, "Loại vách (ACI 318-19)", self.w_cb_aci_class); r += 1
        self.w_var_seismic = tk.BooleanVar(value=bool(D["seismic_on"]))
        self.w_chk_seismic = tk.Checkbutton(
            fx, text="Kháng chấn DCM (TCVN 9386-1:2025)",
            variable=self.w_var_seismic, bg="white",
            activebackground="white", highlightthickness=0)
        self.w_chk_seismic.grid(
            row=r, column=0, columnspan=4, sticky=tk.W, padx=4, pady=4)
        r += 1
        self._toggle_wall_seismic()
        # (Ghi chú xám dưới khối Kháng chấn đã bỏ theo ghi chú đỏ
        # của user 2026-10-25 — chỉ xóa hiển thị.)
        # Khởi tạo hiển thị theo chế độ thép + ψ
        self._update_wall_sectype_fields()
        self._update_wall_rotation_visibility()
        self._on_wall_steel_mode()
        self._auto_psi_wall()
        # Ẩn ngay các frame phụ (frame mục 2 do build_mixin pack_forget)
        for _fr in (f3, f4, fx):
            _fr.pack_forget()
        # ---- Live preview / số đọc khi đổi nhập liệu ----
        for _w in (self.w_en_Lw, self.w_en_tw, self.w_en_cover,
                   self.w_en_per_s, self.w_en_be_Lb, self.w_en_be_nLb,
                   self.w_en_be_nTw, self.w_en_be_Lout,
                   self.w_en_be_Lin,
                   self.w_en_web_s, self.w_en_hstory, self.w_en_htotal,
                   self.w_en_s_h, self.w_en_tie_s, self.w_en_tie_legs,
                   self.w_en_sec_bf, self.w_en_sec_tf,
                   self.w_en_sec_bf2, self.w_en_sec_tf2,
                   self.w_en_sec_L1, self.w_en_sec_L2,
                   self.w_en_sec_t, self.w_en_sec_lr,
                   self.w_en_sec_lr2):
            _w.bind("<FocusOut>", lambda e: self._refresh_wall_preview())
        for _w in (self.w_en_Lx_m, self.w_en_Ly_m, self.w_en_psi_x,
                   self.w_en_psi_y):
            _w.bind("<FocusOut>",
                    lambda e: self._refresh_wall_preview())
        for _cb in (self.w_cb_per_dia, self.w_cb_be_dia,
                    self.w_cb_web_dia,
                    self.w_cb_dia_h, self.w_cb_layers_h,
                    self.w_cb_sw_steel,
                    self.w_cb_tie_dia, self.w_cb_aci_class,
                    self.w_cb_pos):
            _cb.bind("<<ComboboxSelected>>",
                     lambda e: self._refresh_wall_preview())
        self.w_cb_sectype.bind("<<ComboboxSelected>>",
                               lambda e: self._on_wall_sectype())
        self.w_cb_steel_mode.bind("<<ComboboxSelected>>",
                                  lambda e: self._on_wall_steel_mode())
        for _cb in (self.w_cb_lk_tx, self.w_cb_lk_bx, self.w_cb_lk_ty,
                    self.w_cb_lk_by):
            _cb.bind("<<ComboboxSelected>>",
                     lambda e: self._auto_psi_wall())
        self.w_var_lb_auto.trace_add(
            "write", lambda *a: self._refresh_wall_preview())
        self.w_var_pd.trace_add(
            "write", lambda *a: self._refresh_wall_preview())
        self.w_var_seismic.trace_add(
            "write", lambda *a: self._refresh_wall_preview())
        # (2026-10-25) Radio be_layout đã bỏ — không còn trace layout.

    # ---------------- Mục 2/3/4 (web): handler ----------------
    def _rotate_wall(self):
        """Nút 'Xoay +90°': quay ngược chiều kim đồng hồ theo chu kỳ
        0 -> 90 -> 180 -> 270 -> 0 (90/270 hoán đổi Lw/tw khi tính)."""
        self._wall_rot_deg = (int(getattr(self, "_wall_rot_deg", 0))
                              + 90) % 360
        self.w_rot_var.set(f"{self._wall_rot_deg}°")
        # Xoay làm tỉ lệ khung hình lật ngang/dọc: huỷ axes cũ để
        # preview dựng lại ô mặt cắt với figsize đúng hướng mới
        # (thay vì vẽ đè vào figure cỡ cũ).
        self._sec_ax = None
        self._refresh_wall_preview()

    def _update_wall_rotation_visibility(self):
        """Ẩn/hiện hàng xoay theo loại tiết diện (user chốt 2026-10-25):
        vách phẳng không cần xoay vì ETABS xuất mặc định trục 2
        trùng chiều Lw -> ẩn hàng xoay, ép rotation về 0. Loại khác
        (lát 1: mặt cắt + thép + preview) hiện lại hàng xoay,
        machinery xoay giữ nguyên. Hàm này không refresh preview;
        caller (_on_wall_sectype/_apply_wall/khởi tạo panel) refresh.
        (Ghi chú GĐ1 dưới mục 2 đã bỏ 2026-10-25 nên hàm này không
        còn cập nhật widget ghi chú nào.)"""
        if self.w_cb_sectype.get() == _SECTYPES[0]:
            self._wall_rot_deg = 0
            self.w_rot_var.set("0°")
            self._lbl_wall_rot.grid_remove()
            self.w_rot_fr.grid_remove()
        else:
            self._lbl_wall_rot.grid()
            self.w_rot_fr.grid()

    def _wall_sec_code(self):
        try:
            return _SEC_CODES[_SECTYPES.index(self.w_cb_sectype.get())]
        except Exception:
            return "rect"

    def _on_wall_sec_sym(self):
        self._update_wall_sectype_fields()
        self._refresh_wall_preview()

    def _update_wall_sectype_fields(self):
        """Hiện đúng ô nhập của loại đang chọn ở mục 2 + mục 3
        (lát 1, 2026-10-27). Grid lại tường minh từng widget (1
        widget Tk chỉ có 1 vị trí grid — các ô luân phiên như t ở
        hàng chính/hàng t, Bf2 ở hàng Bf/Tf + hàng Bf2/Tf2 đều phải
        grid lại đúng hàng mỗi lần đổi loại, không dựa vào grid()
        không tham số). Lần đầu sang loại mới: điền mặc định web
        (_SEC_WEB_DEFAULTS); chuyển qua lại giữ nguyên giá trị user
        đã nhập (tập _wall_sectypes_seen)."""
        st = self._wall_sec_code()
        _setters = {
            "Lw": self.w_en_Lw, "tw": self.w_en_tw,
            "sec_bf": self.w_en_sec_bf, "sec_tf": self.w_en_sec_tf,
            "sec_bf2": self.w_en_sec_bf2,
            "sec_tf2": self.w_en_sec_tf2,
            "sec_L1": self.w_en_sec_L1,
            "sec_L2": self.w_en_sec_L2, "sec_t": self.w_en_sec_t,
            "sec_lr": self.w_en_sec_lr,
            "sec_lr2": self.w_en_sec_lr2,
        }
        # Lưu giá trị loại cũ trước khi đổi, rồi khôi phục loại mới
        # (đã từng vào -> giá trị user; chưa từng vào -> mặc định
        # web). Nhờ vậy khóa dùng chung (sec_bf/sec_t) không bị
        # mặc định của loại mới ghi đè khi chuyển qua lại.
        _old = getattr(self, "_wall_sec_current", None)
        if _old is not None and _old != st:
            self._wall_sec_values[_old] = {
                _k: _w.get() for _k, _w in _setters.items()}
        if st in self._wall_sec_values:
            for _k, _v in self._wall_sec_values[st].items():
                _w = _setters.get(_k)
                if _w is not None:
                    _w.delete(0, tk.END)
                    _w.insert(0, str(_v))
        elif st not in self._wall_sectypes_seen:
            self._wall_sectypes_seen.add(st)
            for _k, _v in _SEC_WEB_DEFAULTS.get(st, {}).items():
                _w = _setters.get(_k)
                if _w is not None:
                    _w.delete(0, tk.END)
                    _w.insert(0, str(_v))
        self._wall_sec_current = st
        sym = bool(self.w_var_sec_sym.get())
        R = self._wall_sec_rows

        def _show(w, row, col, colspan=1, sticky=tk.EW):
            w.grid(row=row, column=col, columnspan=colspan,
                   sticky=sticky, padx=4, pady=5)

        def _show_lbl(w, row, col):
            w.grid(row=row, column=col, sticky=tk.W, padx=(4, 8),
                   pady=5)

        def _hide(*ws):
            for _w in ws:
                _w.grid_remove()

        if st == "dxf":
            # Lát DXF: thép là thép thật từ file (không sinh theo
            # chu vi/vùng biên) nên ẩn HẾT hàng kích thước (main/
            # sub/sym/bf_tf/bf2_tf2/lr/t) và ẩn cả khung per lẫn be
            # ở mục 3 (chỉ ẩn hiển thị — giá trị widget giữ nguyên
            # để chuyển qua lại không mất số). Hàng xoay vẫn hiện
            # qua _update_wall_rotation_visibility (rot áp được cho
            # DXF như đa giác).
            _hide(self.w_en_Lw, self.w_en_tw, self.w_en_sec_L1,
                  self.w_en_sec_L2, self.w_en_sec_t,
                  self._lbl_wall_main_l, self._lbl_wall_main_r,
                  self.w_lbl_sec_sub, self.w_chk_sec_sym,
                  self.w_en_sec_bf, self.w_en_sec_tf,
                  self.w_en_sec_bf2, self.w_en_sec_tf2,
                  self.w_en_sec_lr, self.w_en_sec_lr2,
                  self._lbl_sec_bf, self._lbl_sec_tf,
                  self._lbl_sec_bf2, self._lbl_sec_tf2,
                  self._lbl_sec_lr, self._lbl_sec_lr2,
                  self._lbl_sec_t)
            if self._lbl_wall_steel_mode is not None:
                self._lbl_wall_steel_mode.grid_remove()
                self.w_cb_steel_mode.grid_remove()
            self.w_frm_per.grid_remove()
            self.w_frm_be.grid_remove()
            return

        # --- Hàng chính: nhãn + ô trái/phải theo loại ---
        _hide(self.w_en_Lw, self.w_en_tw, self.w_en_sec_L1,
              self.w_en_sec_L2, self.w_en_sec_t)
        if st == "rect":
            self._lbl_wall_main_l.config(text="Lw (mm)")
            self._lbl_wall_main_r.config(text="tw (mm)")
            _show(self.w_en_Lw, R["main"], 1)
            _show(self.w_en_tw, R["main"], 3)
        elif st == "barbell":
            self._lbl_wall_main_l.config(text="Lw (mm)")
            self._lbl_wall_main_r.config(text="tw (mm)")
            _show(self.w_en_Lw, R["main"], 1)
            _show(self.w_en_tw, R["main"], 3)
        elif st == "tee":
            self._lbl_wall_main_l.config(text="Lw (mm)")
            self._lbl_wall_main_r.config(text="t (mm)")
            _show(self.w_en_Lw, R["main"], 1)
            _show(self.w_en_sec_t, R["main"], 3)
        elif st == "ell":
            self._lbl_wall_main_l.config(text="L1 (mm)")
            self._lbl_wall_main_r.config(text="L2 (mm)")
            _show(self.w_en_sec_L1, R["main"], 1)
            _show(self.w_en_sec_L2, R["main"], 3)
        else:  # c-core / u-core
            self._lbl_wall_main_l.config(text="Lw (mm)")
            self._lbl_wall_main_r.config(text="t (mm)")
            _show(self.w_en_Lw, R["main"], 1)
            _show(self.w_en_sec_t, R["main"], 3)
        _show_lbl(self._lbl_wall_main_l, R["main"], 0)
        _show_lbl(self._lbl_wall_main_r, R["main"], 2)
        # --- Tiêu đề phụ + Đối xứng ---
        _sub = {"barbell": "KÍCH THƯỚC HAI ĐẦU",
                "c-core": "KÍCH THƯỚC HAI ĐẦU",
                "u-core": "KÍCH THƯỚC HAI CÁNH"}.get(st)
        if _sub:
            self.w_lbl_sec_sub.config(text=_sub)
            self.w_lbl_sec_sub.grid(row=R["sub"], column=0,
                                    columnspan=4, sticky=tk.W,
                                    padx=4, pady=5)
        else:
            self.w_lbl_sec_sub.grid_remove()
        if st in ("barbell", "c-core", "u-core"):
            self.w_chk_sec_sym.config(
                text="Đối xứng hai cánh" if st == "u-core"
                else "Đối xứng hai đầu")
            # Hàng gộp với xoay (lát 2 cột): checkbox ở col 2 span 2,
            # không span 4 như trước (xoay giữ col 0-1 cùng hàng).
            self.w_chk_sec_sym.grid(row=R["sym"], column=2,
                                    columnspan=2, sticky=tk.W,
                                    padx=4, pady=5)
        else:
            self.w_chk_sec_sym.grid_remove()
        # --- Các hàng phụ: ẩn hết trước, hiện đúng hàng của loại ---
        _hide(self.w_en_sec_bf, self.w_en_sec_tf, self.w_en_sec_bf2,
              self.w_en_sec_tf2, self.w_en_sec_lr, self.w_en_sec_lr2,
              self._lbl_sec_bf, self._lbl_sec_tf, self._lbl_sec_bf2,
              self._lbl_sec_tf2, self._lbl_sec_lr, self._lbl_sec_lr2,
              self._lbl_sec_t)
        if st == "barbell":
            self._lbl_sec_bf.config(text="Bf (mm)")
            self._lbl_sec_tf.config(text="Tf (mm)")
            _show_lbl(self._lbl_sec_bf, R["bf_tf"], 0)
            _show(self.w_en_sec_bf, R["bf_tf"], 1)
            _show_lbl(self._lbl_sec_tf, R["bf_tf"], 2)
            _show(self.w_en_sec_tf, R["bf_tf"], 3)
            if not sym:
                self._lbl_sec_bf2.config(text="Bf2 (mm)")
                self._lbl_sec_tf2.config(text="Tf2 (mm)")
                _show_lbl(self._lbl_sec_bf2, R["bf2_tf2"], 0)
                _show(self.w_en_sec_bf2, R["bf2_tf2"], 1)
                _show_lbl(self._lbl_sec_tf2, R["bf2_tf2"], 2)
                _show(self.w_en_sec_tf2, R["bf2_tf2"], 3)
        elif st == "tee":
            self._lbl_sec_bf.config(text="Bf (mm)")
            _show_lbl(self._lbl_sec_bf, R["bf_tf"], 0)
            _show(self.w_en_sec_bf, R["bf_tf"], 1)
        elif st == "c-core":
            self._lbl_sec_bf.config(text="Bf (mm)")
            _show_lbl(self._lbl_sec_bf, R["bf_tf"], 0)
            _show(self.w_en_sec_bf, R["bf_tf"], 1)
            self._lbl_sec_lr.config(text="Lr (mm)")
            _show_lbl(self._lbl_sec_lr, R["lr"], 0)
            _show(self.w_en_sec_lr, R["lr"], 1)
            if not sym:
                self._lbl_sec_lr2.config(text="Lr2 (mm)")
                _show_lbl(self._lbl_sec_lr2, R["lr"], 2)
                _show(self.w_en_sec_lr2, R["lr"], 3)
        elif st == "u-core":
            self._lbl_sec_bf.config(text="Bf (mm)")
            _show_lbl(self._lbl_sec_bf, R["bf_tf"], 0)
            _show(self.w_en_sec_bf, R["bf_tf"], 1)
            if not sym:
                self._lbl_sec_bf2.config(text="Bf2 (mm)")
                _show_lbl(self._lbl_sec_bf2, R["bf_tf"], 2)
                _show(self.w_en_sec_bf2, R["bf_tf"], 3)
        elif st == "ell":
            self._lbl_sec_t.config(text="t (mm)")
            _show_lbl(self._lbl_sec_t, R["t"], 0)
            _show(self.w_en_sec_t, R["t"], 1, colspan=3)
        # --- Mục 3: dropdown chế độ thép chỉ phẳng + Barbell; loại
        # mới ẩn dropdown và ép khung chu vi (thép tự động theo chu
        # vi, c/d/s giữ nguyên) — _collect_wall ép steel_mode.
        if self._lbl_wall_steel_mode is not None:
            if st in ("rect", "barbell"):
                _show_lbl(self._lbl_wall_steel_mode,
                          self._wall_steel_mode_row, 0)
                _show(self.w_cb_steel_mode, self._wall_steel_mode_row,
                      1, colspan=3)
                self._on_wall_steel_mode()
            else:
                self._lbl_wall_steel_mode.grid_remove()
                self.w_cb_steel_mode.grid_remove()
                self.w_frm_be.grid_remove()
                self.w_frm_per.grid()

    def _on_wall_sectype(self):
        # Lát N–M (2026-10-27): 5 loại mới chọn được ở mức mặt cắt
        # + thép + preview và CHECK nhập tay + TCVN đã MỞ ở
        # _on_check_wall; cắt/PDF cho loại mới vẫn chặn (xem đó).
        self._update_wall_sectype_fields()
        self._update_wall_rotation_visibility()
        self._refresh_wall_preview()

    def _on_wall_steel_mode(self):
        """Hiện đúng khung con của chế độ thép đang chọn ở mục 3."""
        mode = _code_of(_STEEL_MODES, self.w_cb_steel_mode.get(),
                        "perimeter")
        if mode == "perimeter":
            self.w_frm_be.grid_remove()
            self.w_frm_per.grid()
        else:
            self.w_frm_per.grid_remove()
            self.w_frm_be.grid()
        self._refresh_wall_preview()

    def _update_wall_dxf_info(self):
        """Cập nhật nhãn thông tin DXF ở mục 2 từ _wall_dxf_data.

        Hiện: tên file, Ag (outline trừ lỗ), số thanh, As. Ẩn khi
        chưa import (không có poly). Ag/As tính lại từ dữ liệu đã
        lưu (không đọc lại file) nên mở file JSON cũ vẫn hiện đúng.
        """
        if not hasattr(self, "w_lbl_wall_dxf_info"):
            return
        data = getattr(self, "_wall_dxf_data", None)
        if not data or not data.get("poly"):
            self.w_var_wall_dxf_info.set("")
            self.w_lbl_wall_dxf_info.grid_remove()
            return
        try:
            from rc_column.dxf_import import polygon_area
            from rc_column.sections import bar_area
            Ag = abs(polygon_area([(float(p[0]), float(p[1]))
                                   for p in data["poly"]]))
            for _h in data.get("holes", []) or []:
                Ag -= abs(polygon_area([(float(p[0]), float(p[1]))
                                        for p in _h]))
            As = sum(bar_area(float(b[2]))
                     for b in data.get("bars", []) or [])
            txt = (f"{data.get('file', '')} — Ag={Ag:.0f} mm², "
                   f"{len(data.get('bars', []) or [])} thép, "
                   f"As={As:.0f} mm²")
        except Exception:
            txt = (f"{data.get('file', '')} — "
                   f"{len(data.get('bars', []) or [])} thép")
        self.w_var_wall_dxf_info.set(txt)
        self.w_lbl_wall_dxf_info.grid()

    def _on_import_wall_dxf(self):
        """Import tiết diện vách bất kỳ từ file .dxf (lát DXF).

        Quy ước CHUNG với cột (rc_column/dxf_import.
        read_dxf_section — không sửa file đó): biên bê tông =
        LWPOLYLINE kín layer BT, lỗ = layer BT_HOLE, thép = CIRCLE
        layer THEP; đơn vị theo $INSUNITS (mặc định mm khi 0 kèm
        cảnh báo). Riêng vách: chỉ nhận đúng 1 biên BT (nhiều biên
        -> lỗi, không tự gộp — single_dxf_outline). Dialog preview
        dùng chung kiểu _preview_dxf_section của cột (vẽ outline +
        thép, nút Dùng/Hủy, hiện warnings). Sau khi đồng ý: lưu
        self._wall_dxf_data (tọa độ GỐC bản vẽ), đặt combobox loại
        thành "Tiết diện bất kỳ (DXF)", refresh preview.
        """
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(
            title="Chọn file DXF tiết diện vách",
            filetypes=[("DXF", "*.dxf"), ("All", "*.*")])
        if not path:
            return
        try:
            from rc_column.dxf_import import (
                build_polygon_section, read_dxf_section)
            from rc_column.wall_section import single_dxf_outline
            dxf = read_dxf_section(path)
            poly = single_dxf_outline(dxf.outlines)
            conc, steel, _mdl = self._wall_tcvn_materials()
            sec = build_polygon_section(dxf, conc, steel,
                                        fiber_step=10.0)
        except Exception as ex:
            messagebox.showerror("Lỗi đọc DXF", str(ex))
            return
        if not self._preview_dxf_section(sec, dxf, path):
            return
        import os as _os
        self._wall_dxf_data = {
            "poly": [list(p) for p in poly],
            "holes": [[list(p) for p in h] for h in dxf.holes],
            "bars": [[float(x), float(y), float(dd)]
                     for x, y, dd in dxf.rebars],
            "file": _os.path.basename(path),
        }
        self.w_cb_sectype.set(_SECTYPES[_SEC_CODES.index("dxf")])
        self._update_wall_sectype_fields()
        self._update_wall_rotation_visibility()
        self._update_wall_dxf_info()
        if dxf.warnings:
            messagebox.showwarning(
                "Cảnh báo import DXF", "\n".join(dxf.warnings))
        self._refresh_wall_preview()

    def _auto_psi_wall(self):
        """Tự điền ψ theo cặp liên kết 2 đầu (cùng cơ chế _auto_psi
        của cột: PSI_TABLE; người dùng vẫn sửa tay được sau đó)."""
        from rc_column.stability import PSI_TABLE
        rev = {v: k for k, v in BOUNDARY_NAMES.items()}
        for cb_t, cb_b, en in (
                (self.w_cb_lk_tx, self.w_cb_lk_bx, self.w_en_psi_x),
                (self.w_cb_lk_ty, self.w_cb_lk_by, self.w_en_psi_y)):
            t = rev.get(cb_t.get(), "")
            b = rev.get(cb_b.get(), "")
            p = PSI_TABLE.get((t, b), PSI_TABLE.get((b, t), 1.0))
            en.delete(0, tk.END)
            en.insert(0, f"{p:g}")
        self._refresh_wall_preview()

    # (_update_wall_L0_labels đã xóa cùng hàng hiển thị L₀ 2026-10-25:
    # L₀ = ψ·L vẫn do engine suy ra lúc tính từ L/ψ, không qua
    # widget hiển thị.)

    # (_update_wall_readouts đã xóa cùng khối readout panel theo
    # quyết user 2026-10-24; hàm wall_readouts trong wall_section.py
    # giữ nguyên cho nơi khác dùng sau này.)

    # ---------------- Kháng chấn: lọc option theo tiêu chuẩn ----------------
    def _toggle_wall_seismic(self):
        """Nhóm 'Kháng chấn' của panel vách: chỉ hiện option thuộc
        tiêu chuẩn đang chọn (user chốt 2026-10-22):
        ACI -> ô 'Loại vách (ACI 318-19)'; TCVN -> checkbox
        'Kháng chấn DCM (TCVN 9386-1:2025)'; EC2 -> checkbox
        'Kháng chấn DCM (EN 1998)'. Option đang ẩn chỉ bị grid_remove —
        biến giá trị (cb/BoolVar) không đổi nên JSON giữ nguyên khi
        đổi tiêu chuẩn qua lại. Được gọi từ _sec_wall (lúc dựng) và từ
        _toggle_code (build_mixin) mỗi khi đổi tiêu chuẩn."""
        if not hasattr(self, "w_cb_aci_class"):
            return
        code = self.cb_code.get() if getattr(self, "cb_code", None) else ""
        if code.startswith("ACI"):
            self.w_lbl_aci_class.grid()
            self.w_cb_aci_class.grid()
            self.w_chk_seismic.grid_remove()
        else:
            self.w_lbl_aci_class.grid_remove()
            self.w_cb_aci_class.grid_remove()
            self.w_chk_seismic.grid()
            self.w_chk_seismic.configure(
                text="Kháng chấn DCM (EN 1998)" if code.startswith("EC2")
                else "Kháng chấn DCM (TCVN 9386-1:2025)")

    # ---------------- Preset ca mẫu web khi vào Vách ----------------
    def _shared_mat_load_values(self):
        """(N, Mx, My, bê tông, thép, γb, γs) hiện tại của các ô dùng
        chung mục 1 (TCVN) + mục 5 (nhập tay)."""
        return (self.en_N.get().strip(), self.en_Mx.get().strip(),
                self.en_My.get().strip(), self.cb_conc.get(),
                self.cb_steel.get(), self.en_gb.get().strip(),
                self.en_gs.get().strip())

    def _set_shared_mat_load_values(self, vals):
        def _se(e, v):
            e.delete(0, tk.END)
            e.insert(0, v)
        _se(self.en_N, vals[0])
        _se(self.en_Mx, vals[1])
        _se(self.en_My, vals[2])
        self.cb_conc.set(vals[3])
        self.cb_steel.set(vals[4])
        _se(self.en_gb, vals[5])
        _se(self.en_gs, vals[6])

    def _wall_web_preset_enter(self):
        """Vào chế độ Vách trong phiên mới tinh (chưa từng mở file,
        các ô dùng chung còn nguyên mặc định app mới): áp ca mẫu web
        (B30/CB500-V; N=2528.65, M2=275.23, M3=202.86) để CHECK đối
        chiếu ngay. Giá trị trước khi áp được cất (_wall_preset_stash)
        để trả lại khi quay về Cột. Chỉ áp 1 lần — user đã sửa bất kỳ
        ô nào trong nhóm này thì không áp nữa.
        LƯU Ý (phần 3/7): preset KHÔNG chạm ô cấp thép ngang riêng
        của vách (w_cb_sw_steel) — CB500-V ở đây chỉ là thép DỌC.
        Ô thép ngang giữ mặc định CB400-V của nó, nên CHECK preset
        dùng Rsw = 280 MPa (không phải 300 MPa của thép dọc).
        """
        if getattr(self, "_data_loaded", False):
            return
        if getattr(self, "_wall_preset_stash", None) is not None:
            return
        try:
            cur = self._shared_mat_load_values()
        except Exception:
            return
        if cur != _WALL_FRESH_SHARED:
            return
        self._wall_preset_stash = cur
        try:
            self._set_shared_mat_load_values(_WALL_WEB_SHARED)
        except Exception:
            self._wall_preset_stash = None

    def _wall_web_preset_leave(self):
        """Rời chế độ Vách: nếu preset web đã áp và user chưa sửa các
        ô đó trong lúc ở Vách, trả lại bộ giá trị đã cất (mặc định
        app mới) — mặc định chế độ Cột không bị preset vách làm đổi.
        User đã sửa thì giữ nguyên giá trị của user."""
        stash = getattr(self, "_wall_preset_stash", None)
        if stash is None:
            return
        self._wall_preset_stash = None
        try:
            if self._shared_mat_load_values() == _WALL_WEB_SHARED:
                self._set_shared_mat_load_values(stash)
        except Exception:
            pass

    # ---------------- Chuyển đổi Cột <-> Vách ----------------
    def _toggle_member(self):
        """Ẩn frame cột 2/3/4, hiện frame vách (hoặc ngược lại).

        Thứ tự pack được giữ bằng cách luôn pack lại ngay trước frame
        mục 5 (frm_loads); bề rộng panel trái không đổi (pack theo X).
        """
        wall = self.is_wall()
        cols = (self.frm_sec_section, self.frm_sec_rebar,
                self.frm_sec_stability)
        frames = getattr(self, "_wall_frames", (self.frm_wall,))
        if wall:
            if not getattr(self, "_applying_data", False):
                self._wall_web_preset_enter()
            for fr in cols:
                fr.pack_forget()
            for fr in frames:
                fr.pack(fill=tk.X, padx=8, pady=8,
                        before=self.frm_loads)
            self._refresh_wall_preview()
        else:
            if not getattr(self, "_applying_data", False):
                self._wall_web_preset_leave()
            for fr in frames:
                fr.pack_forget()
            for fr in cols:
                fr.pack(fill=tk.X, padx=8, pady=8, before=self.frm_loads)
            self._wall_view_active = False
            # Trả lại tóm tắt cột TCVN nếu đã có (tránh sót hình vách ở
            # tab Kết quả); các chuẩn khác user CHECK lại như thường lệ.
            try:
                _tf = getattr(self, "_tcvn_full", None)
                if _tf and not (self.is_aci() or self.is_ec2()):
                    self._show_summary(_tf["sec"], _tf["inp"], _tf["res"])
            except Exception:
                pass

    # ---------------- Thu / áp dữ liệu vách (JSON) ----------------
    def _collect_wall(self) -> dict:
        """Đọc các ô vách thành dict đúng khóa của WallInput (§4.2).

        Gồm khóa format web (mục 2/3/4) lẫn khóa cũ được GƯƠNG từ
        trạng thái mới (dia_v/s_v <- thép phân bố của chế độ đang
        chọn; Lb_left/Lb_right <- be_Lb; l0_out_factor <- psi_y) để
        JSON luôn nhất quán giữa hai format.
        """
        if not hasattr(self, "w_en_Lw"):
            return dict(WALL_DEFAULTS)

        def num(e, default):
            try:
                v = float(str(e.get()).strip().replace(",", "."))
            except Exception:
                return default
            return int(v) if float(v).is_integer() else v

        def cnum(cb, default):
            try:
                v = float(str(cb.get()).strip())
            except Exception:
                return default
            return int(v) if float(v).is_integer() else v

        D = WALL_DEFAULTS
        # Lát 1: loại mới (T/L/C/U) không có dropdown chế độ thép —
        # ép perimeter (thép tự động theo chu vi); phẳng + Barbell
        # giữ dropdown như cũ. Lát DXF: dxf cũng rơi vào nhánh này
        # — mode "perimeter" ở đây CHỈ để gương dia_v/s_v, không
        # dùng cho dựng tiết diện DXF (thép DXF là thép thật).
        _st = self._wall_sec_code()
        if _st not in ("rect", "barbell"):
            mode = "perimeter"
        else:
            mode = _code_of(_STEEL_MODES, self.w_cb_steel_mode.get(),
                            "perimeter")
        rev_bn = {v: k for k, v in BOUNDARY_NAMES.items()}
        psi_y = num(self.w_en_psi_y, D["psi_y"])
        be_Lb = num(self.w_en_be_Lb, D["be_Lb"])
        # Validation panel (mô hình cột dọc, user chốt 2026-10-25):
        # n_Lb >= 2 (mỗi hàng tính cả 2 góc), n_tw >= 0 (thanh giữa,
        # có thể 0), L_out >= 1, L_in >= 0, và L_out + L_in <= n_Lb
        # (cột lớp lấy từ vị trí thanh của 2 hàng nên không vượt
        # quá số vị trí hàng).
        be_n_Lb = max(2, int(num(self.w_en_be_nLb, D["be_n_Lb"])))
        be_n_tw = max(0, int(num(self.w_en_be_nTw, D["be_n_tw"])))
        be_L_out = max(1, int(num(self.w_en_be_Lout, D["be_L_out"])))
        be_L_out = min(be_L_out, be_n_Lb)
        be_L_in = max(0, int(num(self.w_en_be_Lin, D["be_L_in"])))
        be_L_in = min(be_L_in, be_n_Lb - be_L_out)
        if mode == "perimeter":
            dia_v = cnum(self.w_cb_per_dia, D["per_dia"])
            s_v = num(self.w_en_per_s, D["per_s"])
        else:
            dia_v = cnum(self.w_cb_web_dia, D["web_dia"])
            s_v = num(self.w_en_web_s, D["web_s"])
        # Vách phẳng: ép rotation = 0 (ETABS xuất trục 2 trùng Lw);
        # loại khác giữ góc xoay đã nhập.
        _rot = int(getattr(self, "_wall_rot_deg", 0)) % 360
        try:
            if self.w_cb_sectype.get() == _SECTYPES[0]:
                _rot = 0
        except Exception:
            pass
        return {
            "Lw": num(self.w_en_Lw, D["Lw"]),
            "tw": num(self.w_en_tw, D["tw"]),
            "h_story": num(self.w_en_hstory, D["h_story"]),
            "h_total": num(self.w_en_htotal, D["h_total"]),
            "story_pos": _code_of(_STORY_POS, self.w_cb_pos.get(),
                                  "base"),
            "cover": num(self.w_en_cover, D["cover"]),
            "l0_out_factor": psi_y,
            "dia_v": dia_v,
            "s_v": s_v,
            "layers_v": 2,
            "dia_h": cnum(self.w_cb_dia_h, D["dia_h"]),
            "s_h": num(self.w_en_s_h, D["s_h"]),
            "layers_h": int(cnum(self.w_cb_layers_h, D["layers_h"])),
            # Cấp thép ngang RIÊNG của vách (phần 3/7) — khóa JSON mới
            # "sw_steel_grade" trong dict "wall"; luôn ghi tường minh
            # (cấp lạ -> CB400-V), không bao giờ để None khi lưu từ GUI.
            "sw_steel_grade": (self.w_cb_sw_steel.get()
                               if self.w_cb_sw_steel.get() in STEEL_GRADES
                               else "CB400-V"),
            "Lb_left": be_Lb,
            "Lb_right": be_Lb,
            "lb_auto": bool(self.w_var_lb_auto.get()),
            "dia_be": cnum(self.w_cb_be_dia, D["be_dia"]),
            "n_be": (2 * be_n_Lb
                     + be_n_tw * (be_L_out + be_L_in)),
            "tie_dia_be": cnum(self.w_cb_tie_dia, D["tie_dia_be"]),
            "tie_s_be": num(self.w_en_tie_s, D["tie_s_be"]),
            "tie_legs_be": int(num(self.w_en_tie_legs, D["tie_legs_be"])),
            "seismic_class": _code_of(_ACI_CLASS,
                                      self.w_cb_aci_class.get(),
                                      "special"),
            "seismic_on": bool(self.w_var_seismic.get()),
            # --- Format web (2026-10-23) + 5 loại mới (lát 1) ---
            "section_type": _st,
            "rot_deg": _rot,
            "sec_bf": num(self.w_en_sec_bf, D["sec_bf"]),
            "sec_tf": num(self.w_en_sec_tf, D["sec_tf"]),
            "sec_bf2": num(self.w_en_sec_bf2, D["sec_bf2"]),
            "sec_tf2": num(self.w_en_sec_tf2, D["sec_tf2"]),
            "sec_lr": num(self.w_en_sec_lr, D["sec_lr"]),
            "sec_lr2": num(self.w_en_sec_lr2, D["sec_lr2"]),
            "sec_L1": num(self.w_en_sec_L1, D["sec_L1"]),
            "sec_L2": num(self.w_en_sec_L2, D["sec_L2"]),
            "sec_t": num(self.w_en_sec_t, D["sec_t"]),
            "sec_sym": bool(self.w_var_sec_sym.get()),
            "steel_mode": mode,
            "per_dia": cnum(self.w_cb_per_dia, D["per_dia"]),
            "per_s": num(self.w_en_per_s, D["per_s"]),
            "be_n_Lb": be_n_Lb,
            "be_n_tw": be_n_tw,
            "be_L_out": be_L_out,
            "be_L_in": be_L_in,
            # Dấu nghĩa mới: loader thấy be_model="columns" thì dùng
            # thẳng be_n_tw (thanh giữa); thiếu dấu này thì coi là
            # file nghĩa cũ 950b4d5 và trừ 2 góc (xem normalize).
            "be_model": "columns",
            # Mirror format cũ (đọc bởi bản cũ + normalize khi khóa mới
            # bị xóa tay; best-effort: be_nT = 2 hàng, không biểu diễn
            # được cột lớp — file mới luôn ưu tiên khóa mới).
            "be_nL": be_n_Lb,
            "be_nT": 2,
            "be_layout": "chuvi",
            "be_Lb": be_Lb,
            "be_dia": cnum(self.w_cb_be_dia, D["be_dia"]),
            "web_dia": cnum(self.w_cb_web_dia, D["web_dia"]),
            "web_s": num(self.w_en_web_s, D["web_s"]),
            # Tick P–δ (2026-10-25) map đúng 2 giá trị _PD_OPTS cũ.
            "pd_method": ("tcvn" if self.w_var_pd.get() else "none"),
            "Lx_m": num(self.w_en_Lx_m, D["Lx_m"]),
            "psi_x": num(self.w_en_psi_x, D["psi_x"]),
            "lk_top_x": rev_bn.get(self.w_cb_lk_tx.get(),
                                   "ngam_nua_cung"),
            "lk_bot_x": rev_bn.get(self.w_cb_lk_bx.get(),
                                   "ngam_nua_cung"),
            "Ly_m": num(self.w_en_Ly_m, D["Ly_m"]),
            "psi_y": psi_y,
            "lk_top_y": rev_bn.get(self.w_cb_lk_ty.get(),
                                   "ngam_nua_cung"),
            "lk_bot_y": rev_bn.get(self.w_cb_lk_by.get(),
                                   "ngam_nua_cung"),
            # Tải dài hạn cho φl (mục 4, 2026-10-28).
            "N_lt": num(self.w_en_lt_N, D["N_lt"]),
            "M_in_lt": num(self.w_en_lt_Min, D["M_in_lt"]),
            "M_out_lt": num(self.w_en_lt_Mout, D["M_out_lt"]),
            # Nội lực vách lấy từ mục 5 dùng chung khi CHECK
            # (_collect_wall_loads); trong JSON giữ 0 như WallInput
            # mặc định (nội lực thật nằm ở các khóa mục 5 của file).
            "N": D["N"], "M_in": D["M_in"], "M_out": D["M_out"],
            "V_in": D["V_in"], "V_out": D["V_out"], "T": D["T"],
            # Dấu ngữ nghĩa cover (xem cover_migration): dict do app
            # mới lưu đã theo quy ước c_đai — mở lại không dịch nữa.
            "cover_semantics": COVER_SEMANTICS_NEW,
            # Tiết diện DXF (lát DXF): tọa độ gốc bản vẽ từ
            # self._wall_dxf_data; chưa import -> list rỗng, build
            # sẽ lỗi rõ ràng ở CHECK (preview bắt exception và
            # return như hiện tại, không crash app).
            "dxf_poly": [list(p) for p in
                         (getattr(self, "_wall_dxf_data", None) or {})
                         .get("poly", [])],
            "dxf_holes": [[list(p) for p in h] for h in
                          (getattr(self, "_wall_dxf_data", None) or {})
                          .get("holes", [])],
            "dxf_bars": [list(b) for b in
                         (getattr(self, "_wall_dxf_data", None) or {})
                         .get("bars", [])],
            "dxf_file": ((getattr(self, "_wall_dxf_data", None) or {})
                         .get("file", "") or ""),
        }

    def _apply_wall(self, w: dict):
        """Đổ dict vách vào các ô nhập (khóa thiếu -> mặc định; dict
        cũ được dịch trước qua normalize_wall_dict).
        RIÊNG sw_steel_grade (phần 3/7): file mới có khóa -> khôi phục
        đúng cấp đã chọn; file cũ KHÔNG có khóa (hoặc cấp lạ) ->
        fallback về cấp thép dọc hiện tại (cb_steel, đã được _apply_data
        set trước khi gọi tới đây) để kết quả cũ tái hiện từng chữ số.
        normalize_wall_dict cố tình KHÔNG điền khóa này (xem wall_input).

        Migration cover: dict vách cũ (thiếu dấu "cover_semantics")
        lưu cover theo nghĩa tới mặt thép dọc -> dịch sang c_đai
        (c − dia_h) TRONG BỘ NHỚ trước khi lọc qua WALL_DEFAULTS
        (khóa dấu không nằm trong WALL_DEFAULTS nên phải đọc từ dict
        thô w, không đọc từ d đã lọc). Kẹp 0 + cảnh báo ở cuối hàm.
        """
        if not hasattr(self, "w_en_Lw"):
            return
        _wall_cover_warns = []
        if isinstance(w, dict):
            w, _wall_cover_warns = migrate_wall_dict(w)
        d = dict(WALL_DEFAULTS)
        _raw = normalize_wall_dict(w) if isinstance(w, dict) else {}
        if isinstance(w, dict):
            d.update({k: v for k, v in _raw.items()
                      if k in d})

        def se(e, v):
            e.delete(0, tk.END)
            e.insert(0, str(v))

        def sv(v):
            try:
                fv = float(v)
            except Exception:
                return str(v)
            return str(int(fv)) if fv.is_integer() else str(fv)

        # Mục 2 (lát 1): khôi phục đúng loại đã lưu; file cũ thiếu
        # section_type -> "rect" (mặc định WALL_DEFAULTS). Vách phẳng
        # load lại luôn về 0° (kể cả file cũ lưu 90°); loại khác giữ
        # góc đã lưu. _wall_sectypes_seen đánh dấu loại đã load để
        # _update_wall_sectype_fields không ghi đè mặc định web lên
        # giá trị vừa khôi phục.
        _st_loaded = str(d.get("section_type", "rect"))
        if _st_loaded not in _SEC_CODES:
            _st_loaded = "rect"
        self.w_cb_sectype.set(_SECTYPES[_SEC_CODES.index(_st_loaded)])
        self._wall_sectypes_seen.add(_st_loaded)
        try:
            rot = int(float(d["rot_deg"])) % 360
        except Exception:
            rot = 0
        if rot not in (0, 90, 180, 270):
            rot = 0
        if self.w_cb_sectype.get() == _SECTYPES[0]:
            rot = 0
        self._wall_rot_deg = rot
        self.w_rot_var.set(f"{rot}°")
        se(self.w_en_Lw, sv(d["Lw"]))
        se(self.w_en_tw, sv(d["tw"]))
        se(self.w_en_sec_bf, sv(d["sec_bf"]))
        se(self.w_en_sec_tf, sv(d["sec_tf"]))
        se(self.w_en_sec_bf2, sv(d["sec_bf2"]))
        se(self.w_en_sec_tf2, sv(d["sec_tf2"]))
        se(self.w_en_sec_L1, sv(d["sec_L1"]))
        se(self.w_en_sec_L2, sv(d["sec_L2"]))
        se(self.w_en_sec_t, sv(d["sec_t"]))
        se(self.w_en_sec_lr, sv(d["sec_lr"]))
        se(self.w_en_sec_lr2, sv(d["sec_lr2"]))
        self.w_var_sec_sym.set(bool(d["sec_sym"]))
        # Mục 3
        self.w_cb_steel_mode.set(_label_of(
            _STEEL_MODES, d["steel_mode"], "Phân bố đều theo chu vi"))
        se(self.w_en_cover, sv(d["cover"]))
        self.w_cb_per_dia.set(sv(d["per_dia"]))
        se(self.w_en_per_s, sv(d["per_s"]))
        se(self.w_en_be_Lb, sv(d["be_Lb"]))
        self.w_cb_be_dia.set(sv(d["be_dia"]))
        se(self.w_en_be_nLb, sv(d["be_n_Lb"]))
        se(self.w_en_be_nTw, sv(d["be_n_tw"]))
        se(self.w_en_be_Lout, sv(d["be_L_out"]))
        se(self.w_en_be_Lin, sv(d["be_L_in"]))
        self.w_cb_web_dia.set(sv(d["web_dia"]))
        se(self.w_en_web_s, sv(d["web_s"]))
        # Mục 4 — tick P–δ: file cũ "tcvn" -> tick vào, "none" ->
        # không tick (mọi giá trị khác về mặc định tick vào).
        self.w_var_pd.set(str(d.get("pd_method", "tcvn")) != "none")
        se(self.w_en_Lx_m, sv(d["Lx_m"]))
        se(self.w_en_Ly_m, sv(d["Ly_m"]))
        self.w_cb_lk_tx.set(BOUNDARY_NAMES.get(d["lk_top_x"],
                                               "Ngàm nửa cứng"))
        self.w_cb_lk_bx.set(BOUNDARY_NAMES.get(d["lk_bot_x"],
                                               "Ngàm nửa cứng"))
        self.w_cb_lk_ty.set(BOUNDARY_NAMES.get(d["lk_top_y"],
                                               "Ngàm nửa cứng"))
        self.w_cb_lk_by.set(BOUNDARY_NAMES.get(d["lk_bot_y"],
                                               "Ngàm nửa cứng"))
        se(self.w_en_psi_x, sv(d["psi_x"]))
        se(self.w_en_psi_y, sv(d["psi_y"]))
        # Tải dài hạn cho φl (mục 4, 2026-10-28); file cũ thiếu
        # khóa -> mặc định 0 (φl = 2,0 như cũ).
        se(self.w_en_lt_N, sv(d["N_lt"]))
        se(self.w_en_lt_Min, sv(d["M_in_lt"]))
        se(self.w_en_lt_Mout, sv(d["M_out_lt"]))
        # Bổ sung
        self.w_cb_dia_h.set(sv(d["dia_h"]))
        se(self.w_en_s_h, sv(d["s_h"]))
        self.w_cb_layers_h.set(sv(d["layers_h"]))
        # Cấp thép ngang riêng (phần 3/7): có khóa hợp lệ -> dùng nó;
        # file cũ thiếu khóa -> fallback cấp thép dọc (cb_steel đã set).
        _sw_raw = _raw.get("sw_steel_grade")
        if _sw_raw in STEEL_GRADES:
            self.w_cb_sw_steel.set(_sw_raw)
        elif self.cb_steel.get() in STEEL_GRADES:
            self.w_cb_sw_steel.set(self.cb_steel.get())
        else:
            self.w_cb_sw_steel.set("CB400-V")
        self.w_cb_tie_dia.set(sv(d["tie_dia_be"]))
        se(self.w_en_tie_s, sv(d["tie_s_be"]))
        se(self.w_en_tie_legs, sv(d["tie_legs_be"]))
        se(self.w_en_hstory, sv(d["h_story"]))
        se(self.w_en_htotal, sv(d["h_total"]))
        self.w_cb_pos.set(_label_of(_STORY_POS, d["story_pos"],
                                    "Chân vách"))
        self.w_var_lb_auto.set(bool(d["lb_auto"]))
        self.w_cb_aci_class.set(_label_of(_ACI_CLASS, d["seismic_class"],
                                          "Đặc biệt (Ch.18)"))
        self.w_var_seismic.set(bool(d["seismic_on"]))
        self._update_wall_rotation_visibility()
        self._on_wall_steel_mode()
        # _update cuối để loại mới ép lại khung chu vi (tránh
        # _on_wall_steel_mode bật lại khung vùng biên khi combo cũ
        # còn ở boundary — file loại mới luôn lưu perimeter).
        # Đặt current = loại vừa load TRƯỚC để _update không lưu
        # đè giá trị file vừa khôi phục vào kho loại cũ rồi khôi
        # phục lại kho cũ.
        self._wall_sec_current = _st_loaded
        self._update_wall_sectype_fields()
        # Khôi phục dữ liệu DXF (lát DXF): dict có dxf_poly -> đặt
        # _wall_dxf_data + nhãn thông tin; không có -> xóa dữ liệu
        # cũ và ẩn nhãn (tránh sót file DXF của lần mở trước).
        _dxf_poly = d.get("dxf_poly") or []
        if _dxf_poly:
            self._wall_dxf_data = {
                "poly": [list(p) for p in _dxf_poly],
                "holes": [[list(p) for p in h]
                          for h in (d.get("dxf_holes") or [])],
                "bars": [list(b) for b in (d.get("dxf_bars") or [])],
                "file": str(d.get("dxf_file") or ""),
            }
        else:
            self._wall_dxf_data = None
        self._update_wall_dxf_info()
        # Cảnh báo migration cover (nếu c_mới bị kẹp về 0).
        for _w in _wall_cover_warns:
            messagebox.showwarning("Lớp bảo vệ vách (migration file cũ)",
                                   _w)


    # ---------------- Thông báo phần chưa tới lát ----------------
    def _wall_notice(self, action, slice_name=None):
        if slice_name:
            msg = (f"{action} cho vách thuộc {slice_name}, chưa được hỗ "
                   "trợ ở lát hiện tại — app KHÔNG dùng engine cột cho "
                   "vách.")
        else:
            msg = (f"{action} cho vách chưa được hỗ trợ — app KHÔNG "
                   "dùng engine cột cho vách.")
        messagebox.showinfo("Chế độ Vách", msg)

    # ---------------- Điều phối CHECK vách ----------------
    def _on_check_wall(self):
        """CHECK ở chế độ Vách: rẽ theo nguồn nội lực + tiêu chuẩn.

        TCVN + nhập tay -> _check_wall_tcvn; TCVN + ETABS (batch
        pier) -> _check_wall_etabs_batch (lát 5, mở 2026-10-27);
        ACI/EC2 vách -> lát 2, vẫn chặn cho cả 6 loại. PDF cho loại
        mới vẫn chặn ở _export_pdf (không thuộc lát này).
        """
        if self.is_ec2() or self.is_aci():
            self._wall_notice("Kiểm tra vách theo tiêu chuẩn này", "lát 2")
            return
        if self.var_load_mode.get() == "etabs":
            self._check_wall_etabs_batch()
            return
        self._check_wall_tcvn()

    # ---------------- Thu thập cho engine vách ----------------
    def _wall_tcvn_materials(self):
        """Vật liệu TCVN từ đúng các ô vật liệu hiện có (như collect()).

        Chỉ dùng để dựng tiết diện/vật liệu cho engine vách; bản
        preview hình học cũng đi qua đây (vật liệu không ảnh hưởng
        hình vẽ mặt cắt).
        """
        conc = ConcreteMaterial(
            CONCRETE_GRADES[self.cb_conc.get()], self._f(self.en_gb, 0.85))
        steel = SteelMaterial(
            STEEL_GRADES[self.cb_steel.get()], self._f(self.en_gs, 1.0))
        model = "3line" if self.cb_model.get().startswith("3") else "2line"
        return conc, steel, model

    def _wall_sw_material(self):
        """Vật liệu thép ngang RIÊNG của vách (phần 3/7): cấp từ ô
        w_cb_sw_steel, γs lấy cùng ô γs dùng chung như đai cột
        (cấp lạ -> CB400-V). Thép dọc (cb_steel) không dùng ở đây."""
        _grade = self.w_cb_sw_steel.get()
        if _grade not in STEEL_GRADES:
            _grade = "CB400-V"
        return SteelMaterial(STEEL_GRADES[_grade],
                             self._f(self.en_gs, 1.0))

    def _collect_wall_loads(self) -> dict:
        """Nội lực nhập tay (mục 5 dùng chung) ánh xạ sang hệ vách:
        M2 (Mx) -> M_out, M3 (My) -> M_in, Q2 -> V_in, Q3 -> V_out
        (nhất quán ánh xạ pier ở §5.4/§6 của bản thiết kế)."""
        return {
            "N": self._f(self.en_N), "M_in": self._f(self.en_My),
            "M_out": self._f(self.en_Mx), "V_in": self._f(self.en_Q2),
            "V_out": self._f(self.en_Q3), "T": 0.0,
        }

    # ---------------- Hàm tính vách TCVN duy nhất (lát 1) ----------------
    def _tcvn_wall_calculate_full(self, winp, conc, steel, model,
                                  loads=None, case_info=None,
                                  steel_sw=None, seismic_shear=False):
        """Tính 1 lần bằng engine vách; tab/PDF chỉ đọc dict trả về.
        steel_sw: vật liệu thép ngang riêng (phần 3/7); None -> engine
        tự suy từ winp.sw_steel_grade rồi fallback thép dọc.
        seismic_shear: True -> cắt trong MP phóng đại 1,5× theo TCVN
        9386-1:2025 §5.4.2.4(7) DCM (phần 5/7)."""
        return wall_tcvn_full(winp, conc, steel, model=model,
                              loads=loads, case_info=case_info,
                              steel_sw=steel_sw,
                              seismic_shear=seismic_shear)

    def _check_wall_tcvn(self):
        try:
            winp = wall_from_dict(self._collect_wall())
            loads = self._collect_wall_loads()
            conc, steel, model = self._wall_tcvn_materials()
            # Đường nhập tay không có tên combo: phóng đại DCM theo
            # cờ kháng chấn DCM của panel vách (w_var_seismic, mặc
            # định BẬT — Q2: cho tắt). Combo động đất ở popup mục 5
            # chỉ đường batch ETABS tiêu thụ (theo từng combo, xem
            # _check_wall_etabs_batch); ở đây không có combo nên
            # không xét seismic_combo_selected.
            _seis = bool(getattr(self, "w_var_seismic", None) is not None
                         and self.w_var_seismic.get())
            full = self._tcvn_wall_calculate_full(
                winp, conc, steel, model, loads=loads,
                steel_sw=self._wall_sw_material(),
                seismic_shear=_seis)
        except Exception as ex:
            messagebox.showerror("Lỗi", str(ex))
            return
        self._tcvn_wall_full = full
        self._show_wall_result(full)
        self._defer_detail(lambda _f=full: self._render_wall_detail(_f))

    # ---------------- Batch vách TCVN từ bảng Pier (lát 5) ----------------
    def _load_wall_batch_row(self, row):
        """Nạp 1 hàng batch vào tab Kết quả/Chi tiết.

        Chỉ đọc dict kết quả đã lưu ở hàng đó (không tính lại) —
        đúng đường hiển thị của _check_wall_tcvn. Hàng lỗi (full
        None) thì báo và giữ nguyên tab hiện tại.
        """
        full = (row or {}).get("full")
        if full is None:
            messagebox.showinfo(
                "Kết quả batch vách",
                "Dòng này lỗi khi tính: "
                f"{(row or {}).get('error') or 'không rõ'} — "
                "không có kết quả để xem.")
            return
        self._tcvn_wall_full = full
        self._show_wall_result(full)
        self._defer_detail(lambda _f=full: self._render_wall_detail(_f))

    def _check_wall_etabs_batch(self):
        """CHECK vách TCVN cho mọi dòng Pier đã paste (lát 5).

        Parity với batch cột (on_check_etabs): chạy trên bảng đang
        hiển thị self.etabs_forces (đã gộp cặp max/min của các combo
        động đất theo seismic_selected — xem _refresh_merge_display),
        TX_* bỏ khỏi kiểm tra như batch cột. Mỗi dòng chạy đúng hàm
        tính duy nhất _tcvn_wall_calculate_full qua
        rc_column.wall_batch.run_wall_batch (ánh xạ Pier -> loads +
        DCM theo từng combo ở đó); L vách lấy từ mục 4 panel như
        đường nhập tay — Station (mã Top/Bottom) KHÔNG dùng làm L.
        Kết quả: cột D/C chung của bảng mục 5 được điền (max 3 phần),
        cửa sổ bảng batch riêng liệt kê D/C từng phần + khống chế,
        và dòng khống chế chung được nạp vào tab Kết quả/Chi tiết.
        Phương pending (C/U ngoài MP) hiện CHƯA KIỂM ở đúng ô đó,
        không chặn batch. PDF cho loại mới vẫn chặn ở _export_pdf.
        """
        from rc_column.wall_batch import (
            run_wall_batch, wall_batch_controlling)
        forces = list(getattr(self, "etabs_forces", None) or [])
        if not forces:
            messagebox.showinfo("ETABS",
                                "Hãy import nội lực Pier trước.")
            return
        check = [f for f in forces
                 if not (getattr(f, "case", "") or "").strip()
                 .startswith("TX_")]
        if not check:
            messagebox.showinfo(
                "ETABS",
                "Chỉ có tổ hợp TX_*, không có tổ hợp nào để kiểm tra.")
            return
        # Nút "Giữ lại tổ hợp nguy hiểm nhất" đọc đúng batch vừa CHECK:
        # batch vách mới làm batch cột cũ hết hiệu lực (và ngược lại).
        self._batch_rows = None
        try:
            winp = wall_from_dict(self._collect_wall())
            conc, steel, model = self._wall_tcvn_materials()
            steel_sw = self._wall_sw_material()
            seismic = set(getattr(self, "seismic_combo_selected",
                                  set()) or set())

            def _calc(loads, case_info, seismic_shear):
                return self._tcvn_wall_calculate_full(
                    winp, conc, steel, model, loads=loads,
                    case_info=case_info, steel_sw=steel_sw,
                    seismic_shear=seismic_shear)

            rows = run_wall_batch(winp, conc, steel, model, check,
                                  seismic_selected=seismic,
                                  steel_sw=steel_sw, calc=_calc)
        except Exception as ex:
            messagebox.showerror("Lỗi", str(ex))
            return
        self._wall_batch_rows = rows
        # Điền cột D/C chung vào bảng mục 5 (parity batch cột):
        # TX_* giữ trống như _fill_etabs_table vẫn làm.
        _by_id = {id(r["force"]): r for r in rows}
        try:
            self._fill_etabs_table(
                [(f, ({"dc": _by_id[id(f)]["dc_overall"]}
                      if id(f) in _by_id else None))
                 for f in forces])
        except Exception:
            pass
        try:
            _ctrl = wall_batch_controlling(rows)
            _ov = _ctrl.get("overall")
            _ov_txt = (f"{_ov['force'].case} "
                       f"(D/C {_ov['dc_overall']:.3f})"
                       if _ov is not None else "—")
            self.etabs_info.set(
                f"Batch vách: {len(rows)} dòng, khống chế chung: "
                f"{_ov_txt}.")
        except Exception:
            pass
        self._show_wall_batch_window(rows)
        # Nạp dòng khống chế chung vào tab Kết quả/Chi tiết (nếu có)
        # để user thấy ngay chi tiết mà không cần mở bảng batch.
        try:
            _ov = wall_batch_controlling(rows).get("overall")
        except Exception:
            _ov = None
        if _ov is not None:
            self._load_wall_batch_row(_ov)

    def _show_wall_batch_window(self, rows):
        """Cửa sổ bảng kết quả batch vách (không modal để user vẫn
        xem được tab Kết quả/Chi tiết sau khi chọn dòng).

        Cột: Story | Pier | Combo | Vị trí | D/C N–M | D/C cắt
        trong MP | D/C cắt ngoài MP | V_Ed trong MP | DCM 1,5× |
        Kết luận từng phần. Dòng khống chế từng phần + chung ghi ở
        khung tóm tắt phía trên. Đúp-click 1 dòng (hoặc nút "Xem chi
        tiết") nạp đúng combo đó vào tab Kết quả/Chi tiết.
        """
        from rc_column.wall_batch import (
            dc_txt, ok_txt, wall_batch_controlling)
        _old = getattr(self, "_wall_batch_top", None)
        if _old is not None:
            try:
                if _old.winfo_exists():
                    _old.destroy()
            except Exception:
                pass
        top = tk.Toplevel(self)
        top.title("Kết quả batch vách — Pier Forces (ETABS)")
        top.transient(self)
        top.minsize(980, 420)
        self._wall_batch_top = top
        _bg = top.cget("bg")
        _ctrl = wall_batch_controlling(rows)

        def _ctrl_txt(key, dc_key):
            r = _ctrl.get(key)
            if r is None:
                return "CHƯA KIỂM"
            return (f"{r['force'].case} "
                    f"({getattr(r['force'], 'location', '') or ''}) "
                    f"D/C {dc_txt(r[dc_key])}")

        _sum = tk.Frame(top, bg=_bg)
        _sum.pack(fill=tk.X, padx=10, pady=(10, 4))
        tk.Label(
            _sum,
            text=(f"Batch vách TCVN 5574:2018 — {len(rows)} dòng "
                  f"(TX_* bỏ khỏi kiểm tra; phương CHƯA KIỂM không "
                  f"chặn batch). D/C chung của 1 dòng = max 3 phần "
                  f"đã kiểm."),
            font=("", 9, "italic"), bg=_bg, wraplength=960,
            justify=tk.LEFT).pack(anchor=tk.W)
        for _lab, _key, _dk in (
                ("Khống chế N–M:", "nm", "dc_nm"),
                ("Khống chế cắt trong MP:", "in", "dc_in"),
                ("Khống chế cắt ngoài MP:", "out", "dc_out"),
                ("Khống chế chung:", "overall", "dc_overall")):
            tk.Label(
                _sum, text=f"{_lab} {_ctrl_txt(_key, _dk)}",
                font=("", 9, "bold"), bg=_bg, anchor=tk.W,
                justify=tk.LEFT).pack(anchor=tk.W)
        cols = ("story", "pier", "combo", "pos", "dc_nm", "dc_in",
                "dc_out", "ved_in", "dcm", "concl")
        tree = ttk.Treeview(top, columns=cols, show="headings",
                            height=22)
        _heads = {
            "story": "Story", "pier": "Pier", "combo": "Combo",
            "pos": "Vị trí", "dc_nm": "D/C N–M",
            "dc_in": "D/C cắt trong MP",
            "dc_out": "D/C cắt ngoài MP",
            "ved_in": "V_Ed trong MP (kN)", "dcm": "DCM 1,5×",
            "concl": "Kết luận (N–M / Trong / Ngoài)",
        }
        _widths = {"story": 70, "pier": 60, "combo": 100, "pos": 80,
                   "dc_nm": 90, "dc_in": 120, "dc_out": 120,
                   "ved_in": 130, "dcm": 70, "concl": 260}
        for c in cols:
            tree.heading(c, text=_heads[c])
            tree.column(c, width=_widths[c], anchor="center")
        tree.column("concl", anchor="w")
        tree.tag_configure("over", foreground="#991B1B")
        tree.tag_configure("even", background="#F9FAFB")
        # iid Treeview đếm lại từ đầu mỗi cửa sổ nên map phải reset
        # (không giữ iid cũ của cửa sổ batch trước).
        self._wall_batch_tree_ids = {}
        for i, r in enumerate(rows):
            f = r["force"]
            _pos = (getattr(f, "location", "")
                    or f"{float(getattr(f, 'station', 0.0)):.2f}")
            _ved = (f"{float(r['V_ed_in']):.1f}"
                    if r["V_ed_in"] is not None else "—")
            _concl = (f"N–M: {ok_txt(r['ok_nm'])} / "
                      f"Trong: {ok_txt(r['ok_in'])} / "
                      f"Ngoài: {ok_txt(r['ok_out'])}")
            if r.get("error"):
                _concl = f"Lỗi khi tính: {r['error']}"
            _tags = []
            if i % 2 == 0:
                _tags.append("even")
            if any((r[k] or 0) > 1 for k in ("dc_nm", "dc_in",
                                             "dc_out")
                   if r[k] is not None):
                _tags.append("over")
            _iid = tree.insert(
                "", tk.END,
                values=(f.story, f.column, f.case, _pos,
                        dc_txt(r["dc_nm"]), dc_txt(r["dc_in"]),
                        dc_txt(r["dc_out"]), _ved,
                        "Có" if r["seismic"] else "Không", _concl),
                tags=tuple(_tags))
            # iid -> hàng batch (không dựa vào thứ tự hiển thị).
            self._wall_batch_tree_ids[_iid] = r
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        def _view_selected(_ev=None):
            _sel = tree.selection()
            if not _sel:
                return
            _row = self._wall_batch_tree_ids.get(_sel[0])
            if _row is not None:
                self._load_wall_batch_row(_row)

        tree.bind("<Double-1>", _view_selected)
        btn_row = ttk.Frame(top)
        btn_row.pack(fill=tk.X, padx=10, pady=(2, 10))
        ttk.Button(btn_row, text="Xem chi tiết",
                   command=_view_selected).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Đóng",
                   command=top.destroy).pack(side=tk.RIGHT)
        try:
            from gui.dialog_center import center_dialog
            center_dialog(top)
        except Exception:
            pass

    # ---------------- Hiển thị: lưới tab Kết quả (như bên cột) --------
    def _new_wall_fig(self, parent, figsize):
        """Figure + canvas chống vẽ chồng (như _new_fig của TCVN)."""
        fig = Figure(figsize=figsize, dpi=100)
        try:
            from gui.result_renderer import DebouncedFigureCanvasTkAgg
            cv_cls = DebouncedFigureCanvasTkAgg or FigureCanvasTkAgg
        except Exception:
            cv_cls = FigureCanvasTkAgg
        cv = cv_cls(fig, master=parent)
        _w = cv.get_tk_widget()
        try:
            _w.configure(highlightthickness=0, takefocus=0,
                         highlightbackground="white",
                         highlightcolor="white", borderwidth=0)
        except Exception:
            pass
        _w.pack(fill=tk.BOTH, expand=True)
        return fig, cv

    def _wall_sum_grid(self, bottom_weight=1):
        """Cấu hình lưới _sum_inner như renderer cột: 2 cột đều nhau,
        hàng biểu đồ (hàng 2) giãn theo chiều cao còn lại."""
        self._sum_inner.columnconfigure(0, weight=1)
        self._sum_inner.columnconfigure(1, weight=1)
        self._sum_inner.rowconfigure(0, weight=0)
        self._sum_inner.rowconfigure(1, weight=0)
        self._sum_inner.rowconfigure(2, weight=bottom_weight)
        self._sum_inner.rowconfigure(3, weight=0)

    def _finish_wall_sum_layout(self):
        """Gắn lại cuộn chuột + đẩy nội dung lên đầu (như TCVN)."""
        try:
            self._bind_wheel(self._sum_inner, self._sum_canvas)
        except Exception:
            pass

        def _to_top():
            try:
                self._sum_inner.update_idletasks()
                self._sum_canvas.configure(
                    scrollregion=self._sum_canvas.bbox("all"))
                self._sum_canvas.yview_moveto(0)
            except Exception:
                pass
        try:
            self._sum_canvas.after_idle(_to_top)
        except Exception:
            _to_top()

    def _wall_display_geom(self, sec, meta, na_info=None, winp=None):
        """Hình học HIỂN THỊ của plot mặt cắt vách: trả
        (sec, meta, na_info) ở khung CANONICAL (x theo Lw vật lý,
        y theo tw) + góc xoay hiển thị rot_deg.

        Ở 0/180° tiết diện engine dựng đã là canonical. Ở 90/270°
        engine hoán đổi vai trò Lw/tw khi dựng (và riêng chế độ
        vùng biên hình học dựng bị suy biến: Lb > cạnh ngắn nên
        thanh rơi ra ngoài mặt cắt, dim_segments rỗng) — phần VẼ
        dựng lại tiết diện canonical từ winp với rot=0 rồi xoay
        cứng khi vẽ (draw_wall_section_ax rot_deg); đường trung
        hòa ánh xạ S -> canonical: (st, ct) -> (-ct, -st), yp giữ
        nguyên. Số liệu tính toán/bảng thông số KHÔNG đổi.
        """
        rot = 0
        try:
            rot = int((meta or {}).get("rot_deg", 0) or 0) % 360
        except Exception:
            rot = 0
        if getattr(sec, "kind", "rect") == "poly":
            # Đa giác (lát N–M): engine tính trên tiết diện
            # canonical + khung trọng tâm, na_info cũng ở khung
            # đó — KHÔNG dựng lại/đổi na như rect (rect engine
            # dựng sec đã hoán đổi Lw/tw nên na phải chuyển về
            # canonical). Hình xoay cứng qua draw_wall_section_ax
            # rot_deg từ đúng sec/na canonical này.
            return sec, meta, na_info, rot
        if rot not in (90, 270):
            return sec, meta, na_info, rot
        try:
            if winp is None:
                winp = wall_from_dict(self._collect_wall())
            import dataclasses
            w0 = dataclasses.replace(winp, rot_deg=0)
            conc, steel, _mdl = self._wall_tcvn_materials()
            secW, metaW = build_wall_section(w0, conc, steel)
        except Exception:
            return sec, meta, na_info, 0
        naW = na_info
        if na_info is not None and na_info.get("st") is not None \
                and na_info.get("ct") is not None:
            naW = dict(na_info)
            naW["st"] = -float(na_info["ct"])
            naW["ct"] = -float(na_info["st"])
        return secW, metaW, naW, rot

    def _build_wall_section_cell(self, parent, sec, meta=None,
                                 na_info=None, show_compression=False,
                                 winp=None, fit_grow=False):
        """Ô MẶT CẮT TIẾT DIỆN (box viền như cột): tiêu đề + hình mặt
        cắt vách (có DIM từng khoảng; tô vùng nén khi show_compression
        và có na_info sau CHECK) + hàng thẻ thống kê thép dùng chung
        với cột. Trả về frame của ô (chưa đặt — nơi gọi tự grid)."""
        sec, meta, na_info, _rot = self._wall_display_geom(
            sec, meta, na_info, winp)
        f = tk.Frame(parent, bg="white", highlightbackground="#D1D5DB",
                     highlightcolor="#D1D5DB", highlightthickness=1,
                     takefocus=0)
        _hdr = tk.Frame(f, bg="white")
        _hdr.pack(fill=tk.X, pady=(2, 2))
        # Ô mặt cắt VÁCH KHÓA khung nhìn (quyết user 2026-10-25, như
        # ô cột): không nút zoom/pan, không binding zoom/pan — luôn
        # trọn khung ở home; chỉ còn checkbox vùng nén ở góc phải
        # tiêu đề, cùng nhãn/mặc định như cột ("Hiển thị vùng nén",
        # mặc định bật). _zst chỉ còn mang span home cho logic fit
        # khung bên dưới, không còn là trạng thái zoom.
        _zst = {}
        if getattr(self, "_wall_show_compression", None) is None:
            self._wall_show_compression = tk.BooleanVar(value=True)
        _eff_show = bool(show_compression
                         and self._wall_show_compression.get())
        tk.Checkbutton(_hdr, text="Hiển thị vùng nén", bg="white",
                       font=("", 8), fg="#374151",
                       variable=self._wall_show_compression,
                       command=lambda: self._redraw_wall_section()
                       ).pack(side=tk.RIGHT, padx=(0, 4))
        tk.Label(_hdr, text="MẶT CẮT TIẾT DIỆN",
                 font=("", 11, "bold"), bg="white").pack(
                     side=tk.TOP, fill=tk.X)
        if HAS_MPL:
            _nseg = len((meta or {}).get("dim_segments") or [])
            fig, canvas = self._new_wall_fig(
                f, _wall_section_figsize(sec, _nseg, _rot))
            ax = fig.add_subplot(111)
            draw_wall_section_ax(ax, sec, meta=meta, na_info=na_info,
                                 show_compression=_eff_show,
                                 rot_deg=_rot)
            try:
                _wall_section_axes_pos(fig, ax)
            except Exception:
                pass
            canvas.draw()
            self._sec_fig, self._sec_canvas, self._sec_ax = fig, canvas, ax
            # Dữ liệu để checkbox vẽ lại tại chỗ (không tính lại):
            # tiết diện/meta/na_info đã ở khung canonical sau
            # _wall_display_geom + cờ show_compression gốc của nơi
            # gọi (True sau CHECK, False ở preview chưa có na_info).
            self._wall_sec_cell = (sec, meta, na_info, _rot,
                                   bool(show_compression))
            # Span chặt của nội dung vẽ = khung home tĩnh (fit dùng).
            _sp = _wall_section_spans(sec, _nseg, _rot)
            _zst["home"] = ((_sp[0], _sp[1]), (_sp[2], _sp[3]))
            # FIT KHUNG: canvas fill theo CHIỀU NGANG của ô (pack X,
            # không expand dọc); chiều cao canvas theo quy tắc trong
            # _fit_now: bằng avail (chiều cao khả dụng chính xác
            # trong frame ô) khi frame do lưới kéo cao — lấp đầy
            # frame, nội dung căn giữa nhờ hộp axes co về tỉ lệ
            # span (adjustable="box"); giữ nguyên khi
            # frame ôm nội dung (tiết diện xoay đứng không phình
            # hàng); chỉ vươn tới max(need, avail) khi home vừa đổi
            # (đổi Lw/tw/chế độ); riêng preview (fit_grow) còn được
            # vươn tới need khi frame ôm nội dung. Chạy debounce
            # theo <Configure> của canvas VÀ của frame ô (đổi cỡ cửa
            # sổ / lưới giãn đều kích hoạt lại); đặt height qua
            # widget.configure (figure bám theo qua cơ chế resize
            # của canvas) — set_size_inches(forward=True) không đổi
            # được widget nhúng, đã kiểm chứng.
            _cw = canvas.get_tk_widget()
            try:
                _cw.pack_configure(fill=tk.X, expand=False)
            except Exception:
                pass
            _fit = {"id": None, "prev_home": _zst["home"],
                    "grow": bool(fit_grow)}

            def _fit_now():
                _fit["id"] = None
                try:
                    wpx = _cw.winfo_width()
                    fh_px = f.winfo_height()
                    if wpx < 80 or fh_px < 50:
                        return  # layout chưa ổn định, Configure sau lo
                    (hx0, hx1), (hy0, hy1) = _zst["home"]
                    ratio = (hx1 - hx0) / max(1e-9, hy1 - hy0)
                    # Chiều cao KHẢ DỤNG CHÍNH XÁC cho canvas trong
                    # frame ô: chiều cao frame trừ mọi anh em (kèm
                    # pady của chúng), trừ pady của chính canvas và
                    # trừ viền highlight của frame. Bản trước dùng
                    # fudge "-8" trong khi padding thật là 12
                    # (header pady 2+2, thẻ pady 2+4, viền 2) -> hav
                    # thừa đúng +4px so với canvas, gây vòng rò rỉ
                    # +4px/vòng ở preview và — khi trần hav nhỏ hơn
                    # need — để lại khoảng trống dưới canvas trong ô
                    # bị lưới kéo cao (hàng kết quả có weight=1, xem
                    # _show_wall_result/_show_wall_preview): canvas
                    # giữ need, frame giãn thêm, thẻ nằm cuối frame
                    # -> dải trắng lớn giữa hình và thẻ (đúng ảnh
                    # user báo). Tính chính xác thì đặt canvas =
                    # avail không làm đổi chiều cao frame (khi frame
                    # do lưới quyết) và không gây vòng lặp.
                    def _pady(w):
                        try:
                            _py = w.pack_info().get("pady", 0)
                        except Exception:
                            return 0
                        if isinstance(_py, (tuple, list)):
                            return sum(_py)
                        return int(_py or 0)
                    try:
                        _border = 2 * int(f.cget("highlightthickness"))
                    except Exception:
                        _border = 2
                    avail = fh_px - _border - _pady(_cw)
                    for sib in f.winfo_children():
                        if sib is not _cw:
                            avail -= sib.winfo_height() + _pady(sib)
                    dpr = float(getattr(fig.canvas,
                                        "device_pixel_ratio", 1.0)
                                or 1.0)
                    # CÔNG THỨC ĐÓNG: axes position cố định (pad
                    # _WALL_SEC_PAD_PX mỗi phía, display px) nên từ bề
                    # rộng widget (mốc cuối chắc chắn mà figure sẽ
                    # hội tụ về) suy thẳng chiều cao figure để tỉ lệ
                    # axes = tỉ lệ span — không đo bbox figure lúc
                    # đang đổi cỡ (cả 2 chiều của figure đều có thể
                    # trễ so với widget tại thời điểm đo, từng làm
                    # delta sai ~13px và view co ~5% thời còn
                    # adjustable="datalim").
                    axes_w = wpx * dpr - 2 * _WALL_SEC_PAD_PX
                    if axes_w < 40:
                        return
                    need = (axes_w / ratio
                            + 2 * _WALL_SEC_PAD_PX) / dpr
                    # QUY TẮC ĐÍCH (phân biệt 2 trạng thái frame):
                    # - Frame do LƯỚI kéo cao (hàng kết quả
                    #   weight=1, đúng ca ảnh user): canvas = avail
                    #   (lấp đầy frame); figure cao theo, equal
                    #   aspect + hộp co về tỉ lệ span giữ nguyên
                    #   kích thước tiết diện theo chiều khống chế
                    #   (bề ngang) và căn giữa phần dư theo chiều
                    #   dọc -> hết dải trắng mà nội dung vẫn gọn
                    #   trong khung home.
                    # - Frame ÔM NỘI DUNG (avail == chiều cao canvas
                    #   hiện tại, ca tiết diện xoay đứng): canvas
                    #   giữ nguyên — vươn tới need ở đây sẽ phình
                    #   hàng lên ~1200px (từng bị coi là lỗi ở
                    #   rot90); figsize khởi tạo vốn đã khớp tỉ lệ
                    #   span nên nội dung vẫn lấp đầy chiều khống
                    #   chế (cao) và căn giữa theo chiều ngang.
                    # - Ngoại lệ DUY NHẤT được vươn tới need: home
                    #   vừa ĐỔI (đổi Lw/tw/chế độ thép qua vẽ đè):
                    #   target = max(need, avail) để canvas theo kịp
                    #   tỉ lệ span mới, rồi các vòng sau lại về
                    #   avail và ổn định (frame đã giãn theo).
                    # Điểm cố định: đặt canvas = avail không đổi
                    # chiều cao frame (khi frame do lưới quyết) nên
                    # vòng fit sau tính lại đúng avail đó -> ổn
                    # định, không rò rỉ. Cơ chế nhận diện phản hồi/
                    # escape của bản trước không còn cần nên đã gỡ.
                    _home_now = _zst["home"]
                    if avail < 60:
                        target = int(round(need))
                    elif _home_now != _fit.get("prev_home"):
                        _fit["prev_home"] = _home_now
                        target = int(round(max(need, avail)))
                    elif _fit.get("grow") and need > avail \
                            and avail <= _cw.winfo_height() + 4:
                        # Riêng PREVIEW (vùng cuộn được): frame ôm
                        # nội dung thì vươn tới need để hình lấp đầy
                        # cả 2 chiều như vòng trước (250 -> 303 ở ca
                        # chu vi); ô kết quả không áp nhánh này để
                        # tiết diện xoay đứng không phình hàng.
                        target = int(round(need))
                    else:
                        target = int(round(avail))
                    # Chiều cao figure HIỆN TẠI theo display px (=
                    # miền px của widget/sự kiện Configure của TkAgg).
                    # Không dùng canvas.get_width_height(): nó trả
                    # LOGICAL px (đã chia device_pixel_ratio) — trộn
                    # 2 miền làm tiêu chí "đã khớp chưa" lệch ~4%.
                    hpx = fig.bbox.height
                    adjusted = abs(target - hpx) > 3
                    if adjusted:
                        _cw.configure(height=target)
                        # Ép backend resize ĐỒNG BỘ theo đúng (w,
                        # target) — bỏ qua lớp Debounced giữ sự kiện
                        # Configure cũ áp lại trễ (chính lớp đó từng
                        # ghi đè kích thước figure về cỡ khởi tạo).
                        # Sự kiện Configure do configure() sinh ra sẽ
                        # áp lại cùng kích thước này -> idempotent.
                        try:
                            from matplotlib.backends.backend_tkagg \
                                import FigureCanvasTkAgg as _BaseCv
                            import types as _types
                            _BaseCv.resize(canvas, _types.SimpleNamespace(
                                width=wpx, height=target))
                        except Exception:
                            pass
                        # Position axes tính theo fraction của cỡ
                        # figure tại lúc đặt — đặt lại sau resize để
                        # pad đúng 9px ở cỡ cuối, rồi vẽ lại.
                        try:
                            _wall_section_axes_pos(fig, ax)
                            canvas.draw()
                        except Exception:
                            pass
                    # Vòng kiểm chứng (settle): sự kiện Configure cũ
                    # của lớp canvas Debounced có thể áp lại trễ sau
                    # vòng fit này, kéo figure lệch vài px (hộp axes
                    # lệch khỏi tỉ lệ span vài px). 300ms sau —
                    # khi mọi áp lại đã xong — fit lại một lần cho
                    # hội tụ hẳn; vòng kiểm chứng tự nó không arm
                    # thêm vòng nữa.
                    if adjusted and not _fit.get("in_settle"):
                        def _settle():
                            _fit["in_settle"] = True
                            try:
                                _fit_now()
                            finally:
                                _fit["in_settle"] = False
                        try:
                            _cw.after(300, _settle)
                        except Exception:
                            pass
                except Exception:
                    pass

            def _schedule_fit(event=None):
                if _fit["id"] is not None:
                    try:
                        _cw.after_cancel(_fit["id"])
                    except Exception:
                        pass
                try:
                    _fit["id"] = _cw.after(150, _fit_now)
                except Exception:
                    _fit["id"] = None

            _cw.bind("<Configure>", _schedule_fit)
            try:
                f.bind("<Configure>", _schedule_fit)
            except Exception:
                pass
            self._sec_fit_schedule = _schedule_fit
            try:
                _cw.after_idle(_schedule_fit)
            except Exception:
                pass
        self._sec_card_vars = self._build_section_cards(f, sec)
        return f

    def _redraw_wall_section(self):
        """Vẽ lại tại chỗ ô mặt cắt vách theo checkbox vùng nén
        (như _redraw_tcvn_section / redraw_section_figure của cột):
        chỉ đọc lại dữ liệu đã lưu ở _build_wall_section_cell
        (sec/meta/na_info canonical + na_info từ dict kết quả CHECK
        đã tính 1 lần, KHÔNG tính lại), không đụng bảng/biểu đồ
        khác. Ở preview (show_param=False, chưa có na_info) thì
        vẽ lại cũng không hiện vùng nén — đúng như cột trước CHECK.
        """
        try:
            _data = getattr(self, "_wall_sec_cell", None)
            _ax = getattr(self, "_sec_ax", None)
            _cv = getattr(self, "_sec_canvas", None)
            if not _data or _ax is None or _cv is None:
                return
            _sec, _meta, _na, _rot, _param = _data
            _show = bool(_param
                         and getattr(self, "_wall_show_compression",
                                     None) is not None
                         and self._wall_show_compression.get())
            _ax.clear()
            draw_wall_section_ax(_ax, _sec, meta=_meta, na_info=_na,
                                 show_compression=_show, rot_deg=_rot)
            _wall_section_axes_pos(self._sec_fig, _ax)
            _cv.draw()
        except Exception:
            pass

    # ---------- (Đã gỡ 2026-10-25) Zoom / pan / reset ô mặt cắt ----
    # Quyết user 2026-10-25: ô mặt cắt vách khóa khung nhìn như ô
    # cột — không nút −/+/Reset, không binding cuộn chuột zoom,
    # kéo pan, double-click reset. Các method _sec_zoom_* cũ đã
    # xóa hẳn ở đây; _zst trong _build_wall_section_cell chỉ còn
    # là span home cho logic fit khung, không phải trạng thái zoom.
    def _show_wall_preview(self, sec, winp, meta=None):
        """View xem trước mặt cắt vách (chưa CHECK) ở tab Kết quả —
        cùng lưới với view kết quả: ô hướng dẫn trái, ô mặt cắt phải."""
        for w in self._sum_inner.winfo_children():
            w.destroy()
        self._wall_view_active = True
        self._wall_sum_grid(bottom_weight=0)
        self._sum_inner.rowconfigure(1, weight=1)
        title = tk.Label(
            self._sum_inner,
            text="MẶT CẮT VÁCH — XEM TRƯỚC (chưa kiểm tra)",
            font=("", 11, "bold"), bg="#FFFBEB", fg="#92400E")
        title.grid(row=0, column=0, columnspan=2, sticky="ew",
                   padx=2, pady=(4, 2))
        f_info = tk.Frame(self._sum_inner, bg="white",
                          highlightbackground="#D1D5DB",
                          highlightcolor="#D1D5DB",
                          highlightthickness=1, takefocus=0)
        f_info.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        tk.Label(
            f_info, bg="white", fg="#374151", justify=tk.LEFT,
            wraplength=360,
            text="Nhập nội lực ở mục 5 (chế độ nhập tay: N, M2 = ngoài "
                 "mặt phẳng, M3 = trong mặt phẳng, Q2, Q3) rồi bấm "
                 "KIỂM TRA KHẢ NĂNG CHỊU LỰC. Lát 1 hỗ trợ TCVN; "
                 "ACI/EC2 vách thuộc lát 2.").pack(
                     anchor="nw", padx=10, pady=10)
        f_sec = self._build_wall_section_cell(self._sum_inner, sec,
                                              meta=meta, winp=winp,
                                              fit_grow=True)
        f_sec.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        self._finish_wall_sum_layout()

    def _refresh_wall_preview(self):
        """Vẽ/cập nhật preview mặt cắt vách khi đổi nhập liệu."""
        if not self.is_wall():
            return
        try:
            winp = wall_from_dict(self._collect_wall())
            conc, steel, _model = self._wall_tcvn_materials()
            sec, meta = build_wall_section(winp, conc, steel)
        except Exception:
            return
        ax = getattr(self, "_sec_ax", None)
        if getattr(self, "_wall_view_active", False) and ax is not None:
            try:
                secD, metaD, _naD, _rotD = self._wall_display_geom(
                    sec, meta, None, winp)
                ax.clear()
                draw_wall_section_ax(ax, secD, meta=metaD, rot_deg=_rotD)
                _wall_section_axes_pos(self._sec_fig, ax)
                self._sec_canvas.draw_idle()
                # Cập nhật dữ liệu để checkbox vùng nén vẽ lại đúng
                # tiết diện mới (preview: chưa có na_info nên cờ False).
                self._wall_sec_cell = (secD, metaD, None, _rotD, False)
                # Span đổi (đổi Lw/tw, chế độ thép...) -> fit lại
                # chiều cao canvas theo tỉ lệ span mới.
                _sf = getattr(self, "_sec_fit_schedule", None)
                if _sf is not None:
                    try:
                        _sf()
                    except Exception:
                        pass
                varmap = getattr(self, "_sec_card_vars", None)
                if varmap:
                    vals = self._section_card_values(secD)
                    for k, var in varmap.items():
                        if k in vals:
                            var.set(vals[k])
                return
            except Exception:
                pass
        self._show_wall_preview(sec, winp, meta)

    # ---------------- Hiển thị kết quả CHECK vách TCVN ----------------
    def _build_wall_shear_table(self, parent, full):
        """Bảng kiểm tra cắt vách ở tab Kết quả (phần 2/7).

        Dựng TƯƠNG TỰ bảng cắt cột
        (gui/tcvn_mixin._build_stirrup_summary: 3 cột, hàng xen kẽ
        trắng/xám, header xám #F3F4F6) nhưng KHÔNG tái dùng trực
        tiếp hàm đó: hàm cột là method mixin cột, đọc cols cột
        (shear_cols với khóa '2'/'3' + đối tượng sh của cột) và gắn
        với full_res cột — không đọc được dict shear vách
        (shear_in/shear_out + parts, ánh xạ b/h0 và V_Ed DCM riêng
        của vách). Vì vậy bảng vách có builder riêng ở đây, dùng
        chung duy nhất hàm pure build_wall_shear_rows ở trên để
        test không cần Tk. Chỉ vẽ, không tính lại."""
        rows = build_wall_shear_rows(full)
        tf = tk.Frame(parent, bg="white",
                      highlightbackground="#D1D5DB",
                      highlightcolor="#D1D5DB", highlightthickness=1,
                      takefocus=0)
        tf.grid(row=3, column=0, columnspan=2, sticky="nsew",
                padx=4, pady=4)
        headers = ["KIỂM TRA KHẢ NĂNG CHỊU CẮT "
                   "(TCVN 5574:2018 §8.1.3)",
                   "Trong MP (V2)", "Ngoài MP (V3)"]
        for j, h in enumerate(headers):
            tk.Label(tf, text=h, font=("", 9, "bold"), bg="#F3F4F6",
                     fg="#111827", anchor="w" if j == 0 else "center",
                     padx=6, pady=7).grid(row=0, column=j,
                                          sticky="nsew")
            tf.columnconfigure(j, weight=2 if j == 0 else 1,
                               uniform="sw")
        for i, (label, v_in, v_out) in enumerate(rows, start=1):
            _bg = "#F9FAFB" if i % 2 == 0 else "white"
            _bold = (label == "Kết luận")
            # wraplength cho ô nhãn: khi phóng đại DCM, ghi chú
            # nằm ở ô nhãn hàng V_Ed (~70 ký tự) nên phải ngắt
            # dòng thay vì tràn/kẹp — các nhãn khác ngắn nên
            # không bị ảnh hưởng.
            tk.Label(tf, text=label, font=("", 9, "bold" if _bold
                                          else ""), bg=_bg,
                     fg="#111827", anchor="w", padx=6,
                     wraplength=420,
                     pady=4).grid(row=i, column=0, sticky="nsew")
            for j, v in enumerate((v_in, v_out), start=1):
                _fg = "#111827"
                if label == "Kết luận":
                    if v.startswith("✓"):
                        _fg = "#065F46"
                    elif v.startswith("✗"):
                        _fg = "#991B1B"
                tk.Label(tf, text=v, font=("", 9, "bold" if _bold
                                          else ""), bg=_bg, fg=_fg,
                         anchor="center", padx=6, wraplength=280,
                         pady=4).grid(row=i, column=j, sticky="nsew")
        # Ghi chú diễn giải công thức Qb dưới bảng cắt (ghi chú đỏ
        # user 2026-10-25): 1 đoạn gọn — công thức + thay số thật
        # 2 phương, lấy từ wall_qb_formula_note (chỉ đọc dict kết
        # quả, không tính lại). Đặt ở row 4 của parent (sau bảng
        # cắt row 3), không chen vào frame tf của bảng.
        _qb_note = wall_qb_formula_note(full)
        if _qb_note:
            tk.Label(parent, text=_qb_note, font=("", 9),
                     fg="#6B7280", wraplength=1200, justify=tk.LEFT,
                     anchor="w", padx=4, pady=2).grid(
                         row=4, column=0, columnspan=2, sticky="ew",
                         padx=4, pady=(2, 6))
        # (Khối diễn giải dưới bảng — căn cứ §8.1.3 + phạm vi —
        # đã bỏ theo quyết user 2026-10-24; căn cứ đầy đủ vẫn ở
        # tab Chi tiết mục 8 và PDF chi tiết.)
        return tf

    def _show_wall_result(self, full):
        """Tab Kết quả cho vách (đọc từ dict _tcvn_wall_full, không
        tính lại) — lưới 2x2 như bên cột, KHÔNG còn banner kết luận
        chung: hàng trên bảng thông số | mặt cắt + thẻ thép; hàng
        dưới biểu đồ N–Mα | biểu đồ M2–M3 (tại N = BN); KHÔNG còn
        khối kết luận dưới bảng thông số (quyết user 2026-10-24:
        chỉ thể hiện D/C P-M — đã có ở hàng D/C bảng thông số và
        bullets A/B/O); kết luận N–M chỉ còn ở bullets A/B/O
        (dải xanh dưới biểu đồ đã bỏ theo quyết user 2026-10-24);
        ghi chú A/B/O full-width ở row 2; row 3 là bảng cắt vách
        (phần 2, không còn khối diễn giải dưới nó)."""
        for w in self._sum_inner.winfo_children():
            w.destroy()
        self._wall_view_active = True
        self._last_sec = full["sec"]
        self._wall_sum_grid()
        # Lưới chung đặt hàng biểu đồ ở row 2 (khi còn banner ở
        # row 0); nay không banner nên biểu đồ lên row 1, ghi chú
        # A/B/O xuống row 2 — preview vẫn dùng row 0/1 riêng của nó.
        self._sum_inner.rowconfigure(1, weight=1)
        self._sum_inner.rowconfigure(2, weight=0)
        self._sum_inner.rowconfigure(3, weight=0)
        # ===== Ô trên-trái: bảng thông số =====
        f_tr = tk.Frame(self._sum_inner, bg="white",
                        highlightbackground="#D1D5DB",
                        highlightcolor="#D1D5DB", highlightthickness=1,
                        takefocus=0)
        f_tr.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._build_wall_param_table(f_tr, full)
        # ===== Ô trên-phải: mặt cắt tiết diện + thẻ thép =====
        f_tl = self._build_wall_section_cell(
            self._sum_inner, full["sec"], meta=full.get("meta"),
            na_info=full.get("na_info"), show_compression=True,
            winp=full.get("winp"))
        f_tl.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        # ===== Ô dưới-trái: biểu đồ N–Mα =====
        f_bl = tk.Frame(self._sum_inner, bg="white",
                        highlightbackground="#D1D5DB",
                        highlightcolor="#D1D5DB", highlightthickness=1,
                        takefocus=0)
        f_bl.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        hdr = tk.Frame(f_bl, bg="white")
        hdr.pack(fill=tk.X, padx=4, pady=(2, 2))
        tk.Label(hdr, text="● Biểu đồ tương tác N–Mα",
                 font=("", 10, "bold"), bg="white").pack(side=tk.LEFT)
        # Chip α như mẫu bên cột (quyết user 2026-10-25: hiển thị ở
        # cả cột và vách): góc tải từ dict kết quả, 1 chữ số thập
        # phân, cùng màu/format chip α của cột.
        self._wall_nm_alpha_lbl = tk.Label(
            hdr, text=f"  α = {float(full['alpha_deg']):.1f}°  ",
            font=("", 8, "bold"), fg="#065F46", bg="#D1FAE5")
        self._wall_nm_alpha_lbl.pack(side=tk.LEFT, padx=6)
        if HAS_MPL:
            # Vẽ bằng ĐÚNG hàm vẽ của cột qua adapter (không còn
            # code vẽ N–Mα riêng cho vách): A xanh lá tròn, B cam
            # thoi, legend 4 mục dưới biểu đồ — y hệt bên cột.
            from rc_column.chart_draw import draw_nm_alpha_ax
            from rc_column.wall_chart_adapter import wall_chart_inputs
            fig2, cv2 = self._new_wall_fig(f_bl, (5.2, 3.9))
            ax2 = fig2.add_subplot(111)
            _sec2, _inp2, _res2 = wall_chart_inputs(full)
            draw_nm_alpha_ax(ax2, _sec2, _inp2, _res2, None)
            try:
                fig2.tight_layout()
            except Exception:
                pass
            cv2.draw()
            # Combobox "Góc xem:" như bên cột, gồm "3D" (quyết user
            # 2026-10-30): đổi góc chỉ vẽ lại biểu đồ N–Mα này,
            # điểm A/B, D/C và khối ghi chú giữ nguyên số góc tải.
            self._wall_nm_ax = ax2
            self._wall_nm_cv = cv2
            self._wall_nm_full = full
            _right = tk.Frame(hdr, bg="white")
            _right.pack(side=tk.RIGHT)
            tk.Label(_right, text="Góc xem:", font=("", 8),
                     bg="white").pack(side=tk.LEFT)
            _vals = ["α (góc tải)", "3D"] + \
                [f"{d}°" for d in range(0, 361, 15)]
            self._wall_nm_cb = ttk.Combobox(
                _right, values=_vals, width=11, state="readonly",
                font=("", 9))
            self._wall_nm_cb.set("α (góc tải)")
            self._wall_nm_cb.pack(side=tk.LEFT, padx=(4, 0))
            self._wall_nm_cb.bind(
                "<<ComboboxSelected>>",
                self._on_wall_nm_angle_changed)
        # (Dải kết luận xanh dưới biểu đồ đã bỏ theo quyết user
        # 2026-10-24 — kết luận N–M chỉ còn ở bullets A/B/O row 2.)
        # ===== Ô dưới-phải: biểu đồ M2–M3 (tại N = BN) =====
        # Vẽ bằng ĐÚNG hàm vẽ của cột qua adapter (không còn hàm
        # vẽ M2–M3 riêng cho vách): lát cắt tại N = BN do hàm cột
        # tự lấy từ res_ns.BN; mọi số đọc từ dict kết quả, KHÔNG
        # tính lại — cùng hàm vẽ với figure PDF.
        f_br = tk.Frame(self._sum_inner, bg="white",
                        highlightbackground="#D1D5DB",
                        highlightcolor="#D1D5DB", highlightthickness=1,
                        takefocus=0)
        f_br.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        hdr2 = tk.Frame(f_br, bg="white")
        hdr2.pack(fill=tk.X, padx=4, pady=(2, 2))
        tk.Label(hdr2, text="● Mặt cắt M2–M3",
                 font=("", 10, "bold"), bg="white").pack(side=tk.LEFT)
        # Chip N xanh như bên cột (quyết user 2026-10-25: GIỮ chip N,
        # chỉ bỏ hậu tố "(tại N = …)" trong tiêu đề axes): vách trước
        # đây chưa có chip này ở header, nay thêm cho đồng bộ với
        # cột; giá trị là BN (lực dọc điểm giới hạn B), như chip cột.
        tk.Label(hdr2, text=f"  N = {float(full['BN']):+.1f} kN  ",
                 font=("", 8, "bold"), fg="#1D4ED8",
                 bg="#DBEAFE").pack(side=tk.LEFT, padx=6)
        if HAS_MPL:
            from rc_column.chart_draw import draw_m2m3_ax
            from rc_column.wall_chart_adapter import wall_chart_inputs
            fig3, cv3 = self._new_wall_fig(f_br, (5.2, 3.9))
            ax3 = fig3.add_subplot(111)
            _sec3, _inp3, _res3 = wall_chart_inputs(full)
            draw_m2m3_ax(ax3, _sec3, _inp3, _res3)
            try:
                fig3.tight_layout()
            except Exception:
                pass
            cv3.draw()
        else:
            tk.Label(
                f_br, bg="white", fg="#6B7280", justify=tk.CENTER,
                wraplength=420,
                text="Chưa có dữ liệu biểu đồ M2–M3.").pack(
                    fill=tk.BOTH, expand=True, padx=10, pady=10)
        # (Diễn giải M2–M3 dưới biểu đồ đã bỏ cùng dải xanh —
        # M2–M3 chỉ là lát cắt hiển thị của cùng khả năng N–M,
        # kết luận của nó nằm ở bullets A/B/O row 2.)
        # ===== Ghi chú A/B/O (full-width, row 2) =====
        # Cùng format khối ghi chú cột TCVN (adapter
        # wall_chart_notes): góc α và các số luôn là góc tải,
        # kể cả khi dropdown "Góc xem" đang ở góc khác.
        from rc_column.wall_chart_adapter import wall_chart_notes
        f_notes = tk.Frame(self._sum_inner, bg="white",
                           highlightbackground="#D1D5DB",
                           highlightcolor="#D1D5DB",
                           highlightthickness=1, takefocus=0)
        f_notes.grid(row=2, column=0, columnspan=2, sticky="ew",
                     padx=4, pady=4)
        _box = tk.Frame(f_notes, bg="white",
                        highlightbackground="#E5E7EB",
                        highlightthickness=1, takefocus=0)
        _box.pack(fill=tk.X, padx=4, pady=4)
        for _txt, _col in wall_chart_notes(full):
            tk.Label(_box, text=_txt, font=("TkFixedFont", 9),
                     fg=_col, bg="white", wraplength=1200,
                     justify=tk.LEFT).pack(anchor="w", padx=4, pady=1)
        # ===== Bảng kiểm tra cắt (full-width, row 3) + ghi chú Qb
        # (row 4) =====
        # Khối diễn giải chung dưới bảng cắt (căn cứ + phạm vi) đã
        # bỏ theo quyết user 2026-10-24; ghi chú Qb ở row 4 là yêu
        # cầu mới rõ ràng của user 2026-10-25 (chỉ 1 đoạn công thức
        # Qb), không phải khôi phục khối cũ.
        self._sum_inner.rowconfigure(3, weight=0)
        self._build_wall_shear_table(self._sum_inner, full)
        self._finish_wall_sum_layout()

    def _on_wall_nm_angle_changed(self, event=None):
        """Vẽ lại CHỈ biểu đồ N–Mα vách tại góc xem đã chọn.

        Như bên cột (có "3D" từ 2026-10-30): "α (góc tải)" -> góc
        tải của dict; "3D" -> mặt tương tác 3D; "0°".."360°" ->
        xoay mô men thiết kế qua adapter. Điểm A/B, D/C và khối
        ghi chú giữ nguyên."""
        try:
            ax = getattr(self, "_wall_nm_ax", None)
            cv = getattr(self, "_wall_nm_cv", None)
            full = getattr(self, "_wall_nm_full", None)
            if cv is None or full is None:
                return
            sel = self._wall_nm_cb.get()
            if sel == "3D":
                self._draw_wall_3d_interaction()
                return
            if ax is None:
                return
            if sel.startswith("α"):
                angle = None
            else:
                angle = float(sel.replace("°", ""))
        except Exception:
            return
        # Cập nhật chip α như bên cột: về góc tải khi chọn "α (góc
        # tải)", hiện "xem X°" khi chọn góc xem khác (khối ghi chú
        # và D/C vẫn giữ số góc tải, không đổi).
        try:
            _lbl = getattr(self, "_wall_nm_alpha_lbl", None)
            if _lbl is not None:
                if angle is None:
                    _lbl.config(
                        text=f"  α = {float(full['alpha_deg']):.1f}°  ")
                else:
                    _lbl.config(text=f"  xem {angle:.0f}°  ")
        except Exception:
            pass
        try:
            from rc_column.chart_draw import draw_nm_alpha_ax
            from rc_column.wall_chart_adapter import wall_chart_inputs
            sec, inp_ns, res_ns = wall_chart_inputs(
                full, view_angle_deg=angle)
            # Nếu đang ở 3D, tạo lại axes 2D (như bên cột)
            _fig = cv.figure
            _cur = _fig.axes[0] if _fig.axes else None
            if _cur is not None and getattr(_cur, 'name', '') == '3d':
                _fig.clear()
                ax = _fig.add_subplot(111)
                self._wall_nm_ax = ax
                # Trả layout 2D như lúc build ban đầu (view 3D đã
                # đổi subplots_adjust để chừa chỗ legend/caption).
                try:
                    _fig.tight_layout()
                except Exception:
                    pass
            else:
                ax.clear()
            draw_nm_alpha_ax(ax, sec, inp_ns, res_ns, None)
            cv.draw()
        except Exception:
            pass

    def _draw_wall_3d_interaction(self):
        """Vẽ mặt tương tác 3D (N–Mx–My) cho vách — theo đúng ảnh mẫu
        user (quyết 2026-10-30).

        Dữ liệu từ dict kết quả vách đã lưu (`_wall_nm_full`) qua
        adapter `wall_chart_inputs`: `sec` tương thích
        `BiaxialCapacity` (đúng class mà `draw_nm_alpha_ax` dùng
        vẽ bao 2D nên cùng họ mặt cho mọi loại tiết diện:
        phẳng, Barbell/T/L/C/U, DXF) — KHÔNG tính lại solver.
        Khung tọa độ là khung canonical Mx–My của tiết diện
        (mặt từ `surface_grid` vốn là Mx = M·sinθ, My = M·cosθ);
        vách phẳng: Mx = M_out, My = M_in; vách C/U: Mx = M_in,
        My = M_out (trục trong MP là y) — điểm A/B và đường cong
        α đều lấy đúng khung này qua adapter nên khớp mặt.

        Hiển thị theo ảnh mẫu:
        - 3 trục tọa độ qua gốc O, nhãn 2 đầu mỗi trục:
          "+Mx"/"−Mx", "+My"/"−My", "+N Nén"/"−N Kéo", chữ "O"
          tại gốc (pane/tick mặc định của mplot3d được ẩn).
        - Mặt tương tác: wireframe xám nhạt mờ (không còn mặt đặc
          xanh) — cùng lưới `surface_grid`, chỉ đổi cách vẽ.
        - Đường cong N–Mα tại góc tải: đường bao 2D
          (`moment_capacity(N, θ_can)`, θ_can = atan2(Mx*, My*)
          như `draw_nm_alpha_ax`) dựng thành đường 3D
          (Mx, My) = Mα·(sinθ_can, cosθ_can), màu xanh lá.
        - Điểm A: chấm xanh lá; điểm B: thoi cam; tia đứt đỏ
          O–A–B kéo dài qua B ×1.18 (như 2D).
        - Legend 5 mục + caption "Biểu đồ 3D N–Mx–My" dưới figure.
        """
        try:
            from mpl_toolkits.mplot3d import Axes3D  # noqa
            from matplotlib.lines import Line2D
            import math
            import numpy as np
            cv = getattr(self, "_wall_nm_cv", None)
            full = getattr(self, "_wall_nm_full", None)
            if cv is None or full is None:
                return
            fig = cv.figure
            fig.clear()
            ax = fig.add_subplot(111, projection='3d')
            # Xoay bằng kéo chuột (như bên cột)
            try:
                ax.mouse_init()
            except Exception:
                pass
            from rc_column.interaction import BiaxialCapacity
            from rc_column.wall_chart_adapter import wall_chart_inputs
            from gui.surf3d_cache import (
                SURF3D_N_N, SURF3D_N_ANGLES, alpha_curve_3d,
                curve_fp, get_curve, get_surface, surface_fp)
            sec, inp_ns, res_ns = wall_chart_inputs(full)
            # Mặt 3D qua cache (fingerprint theo tiết diện + thép +
            # vật liệu + model): lần mở 3D thứ 2+ cùng tiết diện
            # không tính lại lưới. KHÔNG đụng solver.
            _fp = surface_fp("wall", sec,
                             model=inp_ns.concrete_model)

            def _build_cap():
                return BiaxialCapacity(
                    sec, model=inp_ns.concrete_model, n_angles=24)

            n_vals, th_vals, m2_grid, m3_grid = get_surface(
                _fp, lambda: _build_cap().surface_grid(
                    n_n=SURF3D_N_N, n_angles=SURF3D_N_ANGLES))
            # Đóng vòng mặt 3D (thêm cột 360° = cột 0°) để
            # wireframe kín, không hở đường nối.
            m2_grid = np.hstack([m2_grid, m2_grid[:, :1]])
            m3_grid = np.hstack([m3_grid, m3_grid[:, :1]])
            n_closed = len(th_vals) + 1
            n_grid = np.tile(n_vals[:, None], (1, n_closed))
            # ---- 1. Ẩn trục/pane mặc định, vẽ 3 trục qua gốc O ----
            ax.grid(False)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_zticks([])
            try:
                for _pane in (ax.xaxis.pane, ax.yaxis.pane,
                              ax.zaxis.pane):
                    _pane.set_visible(False)
            except Exception:
                pass

            def _extend(lo, hi, frac=0.10):
                _s = hi - lo
                _m = frac * _s if _s > 0 else 1.0
                return lo - _m, hi + _m

            _xe = _extend(float(m2_grid.min()), float(m2_grid.max()))
            _ye = _extend(float(m3_grid.min()), float(m3_grid.max()))
            _ze = _extend(float(n_vals.min()), float(n_vals.max()))
            _AXC = "#4B5563"  # xám đậm: trục + nhãn, dễ đọc
            ax.plot([_xe[0], _xe[1]], [0, 0], [0, 0],
                    color=_AXC, lw=1.4)
            ax.plot([0, 0], [_ye[0], _ye[1]], [0, 0],
                    color=_AXC, lw=1.4)
            ax.plot([0, 0], [0, 0], [_ze[0], _ze[1]],
                    color=_AXC, lw=1.4)
            ax.set_xlim(_xe)
            ax.set_ylim(_ye)
            ax.set_zlim(_ze)
            # Nhãn 2 đầu mỗi trục (đặt ngoài biên mặt 10% nên
            # không đè lên wireframe) + "O" tại gốc.
            _fs = 10
            ax.text(_xe[1], 0, 0, "+Mx", color=_AXC,
                    fontsize=_fs, ha="left", va="center")
            ax.text(_xe[0], 0, 0, "−Mx", color=_AXC,
                    fontsize=_fs, ha="right", va="center")
            ax.text(0, _ye[1], 0, "+My", color=_AXC,
                    fontsize=_fs, ha="center", va="center")
            ax.text(0, _ye[0], 0, "−My", color=_AXC,
                    fontsize=_fs, ha="center", va="center")
            ax.text(0, 0, _ze[1], "+N Nén", color=_AXC,
                    fontsize=_fs, ha="center", va="bottom")
            ax.text(0, 0, _ze[0], "−N Kéo", color=_AXC,
                    fontsize=_fs, ha="center", va="top")
            # "O" lệch nhẹ về phía −Mx để không bị lưới wireframe
            # che khuất tại đúng điểm giao 3 trục.
            ax.text(_xe[0] * 0.035, 0, 0, "O", color=_AXC,
                    fontsize=9, ha="center", va="center")
            # ---- 2. Mặt tương tác: wireframe xám nhạt mờ ----
            # (ảnh mẫu là dạng lưới; cùng lưới surface_grid,
            # chỉ đổi cách vẽ — không còn mặt đặc xanh).
            ax.plot_wireframe(m2_grid, m3_grid, n_grid,
                              color="#9CA3AF", alpha=0.5,
                              rstride=2, cstride=3, linewidth=0.7)
            # ---- 3. Đường cong N–Mα tại góc tải (dựng từ bao 2D)
            # θ_can = góc tải trong khung canonical, đúng công
            # thức draw_nm_alpha_ax dùng (chart_draw.py):
            #   alpha_deg = degrees(atan2(Mx_star, My_star)).
            _theta = math.degrees(
                math.atan2(res_ns.Mx_star, res_ns.My_star))
            # Đường cong N–Mα cache theo (mặt, góc tải): cache hit
            # thì không dựng cap, không gọi moment_capacity lại.
            _cx, _cy, _cz = get_curve(
                curve_fp(_fp, _theta),
                lambda: alpha_curve_3d(_build_cap, n_vals, _theta))
            GREEN, ORANGE, RED = "#059669", "#F97316", "#DC2626"
            ax.plot(_cx, _cy, _cz, color=GREEN, lw=2.2,
                    label="Đường cong N–Mα")
            # ---- 4. Điểm A (xanh lá), B (thoi cam),
            # tia đứt đỏ O–A–B kéo dài qua B ×1.18 (như 2D) ----
            _Ax = (float(res_ns.Mx_star), float(res_ns.My_star),
                   float(res_ns.N))
            _Bx = (float(res_ns.Bx), float(res_ns.By),
                   float(res_ns.BN))
            ax.plot([0.0, _Bx[0] * 1.18],
                    [0.0, _Bx[1] * 1.18],
                    [0.0, _Bx[2] * 1.18],
                    color=RED, ls="--", lw=1.5, dashes=(4, 3),
                    label="Tia tải O–A–B")
            ax.scatter([_Bx[0]], [_Bx[1]], [_Bx[2]], c=ORANGE,
                       marker="D", s=70, edgecolors="white",
                       linewidths=1.2, label="Điểm giới hạn B")
            ax.scatter([_Ax[0]], [_Ax[1]], [_Ax[2]], c=GREEN,
                       s=70, edgecolors="white", linewidths=1.2,
                       label="Điểm tải A")
            ax.text(_Ax[0], _Ax[1], _Ax[2], "  A", fontsize=9,
                    color=GREEN, weight="bold")
            ax.text(_Bx[0], _Bx[1], _Bx[2], "  B", fontsize=9,
                    color=ORANGE, weight="bold")
            # ---- 5. Legend + caption ----
            _leg = [
                Line2D([0], [0], color="#9CA3AF", lw=1.4,
                       label="Mặt tương tác 3D"),
                Line2D([0], [0], color=GREEN, lw=2.2,
                       label="Đường cong N–Mα"),
                Line2D([0], [0], color=RED, lw=1.5, ls="--",
                       dashes=(4, 3), label="Tia tải O–A–B"),
                Line2D([0], [0], marker="o", color="w",
                       markerfacecolor=GREEN, markersize=8,
                       markeredgecolor="white", label="Điểm tải A"),
                Line2D([0], [0], marker="D", color="w",
                       markerfacecolor=ORANGE, markersize=7,
                       markeredgecolor="white",
                       label="Điểm giới hạn B"),
            ]
            ax.legend(handles=_leg, fontsize=8, loc="upper center",
                      bbox_to_anchor=(0.5, -0.10), ncol=3,
                      frameon=False)
            # Chừa chỗ dưới cho legend (2 hàng khi ncol=3) +
            # caption (khi quay lại 2D, handler đổi góc gọi lại
            # tight_layout để trả layout 2D như cũ).
            fig.subplots_adjust(left=0.02, right=0.98,
                                bottom=0.30, top=0.94)
            fig.text(0.5, 0.02, "Biểu đồ 3D N–Mx–My", ha="center",
                     va="bottom", fontsize=11, fontweight="bold")
            cv.draw()
            self._wall_nm_ax = ax
        except Exception:
            import traceback
            traceback.print_exc()

    def _build_wall_param_table(self, parent, full):
        """Bảng thông số vách (đọc từ dict kết quả, không tính lại)."""
        winp = full["winp"]
        sec = full["sec"]
        sl = full["slend"]
        ttk.Label(parent, text="BẢNG THÔNG SỐ — VÁCH (TCVN 5574:2018)",
                  font=("", 11, "bold")).pack(pady=(2, 6))
        cols = ("sym", "desc", "val")
        tree = ttk.Treeview(parent, columns=cols, show="headings",
                            height=21, style="Param.Treeview")
        tree.heading("sym", text="Ký hiệu")
        tree.heading("desc", text="Thông số")
        tree.heading("val", text="Giá trị")
        tree.column("sym", width=84, anchor="center", stretch=False)
        tree.column("desc", width=230, anchor="w")
        tree.column("val", width=190, anchor="e", stretch=False)
        tree.tag_configure("odd", background="#F9FAFB")
        tree.tag_configure(
            "dc", background="#D1FAE5" if full["ok"] else "#FEE2E2",
            foreground="#065F46" if full["ok"] else "#991B1B")
        _sh = full.get("shear_in") or {}
        _sh_ok = _sh.get("ok")
        tree.tag_configure(
            "dc_shear",
            background="#D1FAE5" if _sh_ok else "#FEE2E2",
            foreground="#065F46" if _sh_ok else "#991B1B")
        _sho = full.get("shear_out") or {}
        _sho_ok = _sho.get("ok")
        tree.tag_configure(
            "dc_shear_out",
            background="#D1FAE5" if _sho_ok else "#FEE2E2",
            foreground="#065F46" if _sho_ok else "#991B1B")
        c = full["c_neutral"]
        c_txt = (f"{c:.0f} mm" if c is not None and math.isfinite(c)
                 else "—")
        # Ký hiệu solver cho mô men (lát N–M): phẳng + barbell/
        # tee/ell: trong MP = M3, ngoài MP = M2 như cũ; c-core/
        # u-core (trục trong MP là y): trong MP = M2, ngoài MP
        # = M3 — đổi nhãn để ký hiệu khớp khung solver, giá trị
        # M_in/M_out không đổi.
        _axis_y = full.get("wall_axis_in") == "y"
        _sym_in = "M2" if _axis_y else "M3"
        _sym_out = "M3" if _axis_y else "M2"
        # Bỏ 5 hàng Lw/tw/Ab/As/μ (user chốt 2026-10-22): Lw/tw đã có
        # nhãn kích thước trên hình mặt cắt, As/Ab/μ đã có ở hàng thẻ.
        rows = [
            ("N", "Lực dọc tính toán", f"{full['N']:+.1f} kN"),
            (_sym_in, "Mô men trong mặt phẳng ban đầu",
             f"{full['M_in']:.1f} kN·m"),
            (_sym_out, "Mô men ngoài mặt phẳng ban đầu",
             f"{full['M_out']:.1f} kN·m"),
            ("V2", "Lực cắt trong mặt phẳng",
             f"{full['V_in']:.1f} kN"),
            ("V3", "Lực cắt ngoài mặt phẳng",
             f"{full['V_out']:.1f} kN"),
            ("L0", "Chiều dài tính toán ngoài mặt phẳng",
             f"{sl['l0_out'] / 1000.0:.2f} m"),
            ("λ", "Độ mảnh ngoài mặt phẳng", f"{sl['lambda_out']:.1f}"),
            ("L0x", "Chiều dài tính toán trong mặt phẳng (mục 4)",
             f"{sl.get('l0_in', 0.0) / 1000.0:.2f} m"),
            ("λx", "Độ mảnh trong mặt phẳng",
             f"{sl.get('lambda_in', 0.0):.1f}"),
            ("e0", "Độ lệch tâm ban đầu ngoài mặt phẳng",
             f"{full['e0_out']:.1f} mm"),
            ("e0x", "Độ lệch tâm ban đầu trong mặt phẳng",
             f"{full.get('e0_in', 0.0):.1f} mm"),
            ("φL", "Hệ số φL",
             (f"{full.get('phi_L_in', full['phi_L']):.2f} (trong MP) / "
              f"{full.get('phi_L_out', full['phi_L']):.2f} (ngoài MP)")
             if abs(float(full.get('phi_L_in', full['phi_L']))
                    - float(full.get('phi_L_out', full['phi_L']))) > 1e-9
             else f"{full['phi_L']:.2f}"),
            ("Ncr", "Lực tới hạn Euler ngoài mặt phẳng",
             f"{sl['Ncr_out']:,.0f} kN"),
            ("η", "Hệ số uốn dọc ngoài mặt phẳng",
             f"{sl['factor_out']:.3f}"),
            ("Ncrx", "Lực tới hạn Euler trong mặt phẳng",
             f"{sl.get('Ncr_in', 0.0):,.0f} kN"),
            ("ηx", "Hệ số uốn dọc trong mặt phẳng",
             f"{sl.get('factor_in', 1.0):.3f}"),
            (f"{_sym_out}*", "Mô men ngoài mặt phẳng đã phóng đại",
             f"{full['M_out_d']:.1f} kN·m"),
            (f"{_sym_in}*", "Mô men trong mặt phẳng đã phóng đại",
             f"{full['M_in_d']:.1f} kN·m"),
            ("α", "Góc mô men (từ trục M3)", f"{full['alpha_deg']:.1f} °"),
            ("Mα", "Mô men tổng hợp", f"{full['Malpha']:.1f} kN·m"),
            ("Mα,u", "Khả năng chịu Mα tại N",
             f"{full['M_capacity']:.1f} kN·m"),
            ("c", "Chiều cao vùng nén tại điểm B", c_txt),
            ("σmép", "Ứng suất nén mép (đàn hồi)",
             f"{full['sigma_edge']:.2f} MPa"),
        ]
        # Phần 5/7: khi phóng đại DCM đang áp, hiện thêm hàng V_Ed
        # ngay sau hàng V2 (V2 ở vị trí 3) để không nhầm V gốc với
        # V thiết kế đã phóng đại; D/C cắt dưới đây đã tính ở V_Ed.
        if _sh.get("seismic_applied") and _sh.get("V_cap") is not None:
            # Giá trị chỉ còn V_Ed trơn, không hiển thị V_raw (quyết
            # user 2026-10-24: người dùng tự hiểu V2 đã được tự nhân;
            # cột mô tả bên cạnh đã ghi rõ phóng đại DCM).
            rows.insert(4, ("V_Ed",
                            "Lực cắt trong MP đã phóng đại kháng chấn "
                            "(TCVN 9386-1:2025 §5.4.2.4(7) DCM)",
                            f"{_sh['V_d']:.1f} kN"))
        # Cảnh báo η kẹp (2026-10-28): η = 10,0 do Ncr ≤ |N| là
        # giá trị kẹp tùy tiện, không phải giá trị vật lý — hiện
        # ngay sau hàng ηx trong bảng thông số (chi tiết đầy đủ
        # ở tab Chi tiết, mục 5).
        if full.get("eta_clamped_in") or full.get("eta_clamped_out"):
            _cdirs = []
            if full.get("eta_clamped_in"):
                _cdirs.append("trong MP")
            if full.get("eta_clamped_out"):
                _cdirs.append("ngoài MP")
            _eta_idx = next((i for i, r in enumerate(rows)
                             if r[0] == "ηx"), None)
            if _eta_idx is not None:
                rows.insert(_eta_idx + 1,
                            ("⚠ η kẹp",
                             "Cảnh báo: η bị kẹp ở 10,0 (" + " + ".join(_cdirs)
                             + ") vì Ncr ≤ |N| — kiểm tra lại độ mảnh/tiết diện",
                             "η = 10,000 (kẹp)"))
        # Hàng D/C N–M đặt ngay sau hàng α (ghi chú đỏ user
        # 2026-10-25: trước đây nằm cuối bảng, dưới nếp gấp khi
        # Treeview chỉ cao 20 hàng nên không nhìn thấy được) — lấy
        # từ dict kết quả đã lưu, không tính lại; kết luận theo
        # D/C ≤ 1 như bullets A/B/O dưới biểu đồ.
        _alpha_idx = next(i for i, r in enumerate(rows) if r[0] == "α")
        rows.insert(_alpha_idx + 1,
                    ("D/C", "Kiểm tra N–M (song trục)",
                     f"{full['dc']:.3f} — "
                     + ("ĐẠT" if full["ok"] else "KHÔNG ĐẠT")))
        for i, (s, d, v) in enumerate(rows):
            tree.insert("", tk.END, values=(s, d, v),
                        tags=("dc",) if s == "D/C"
                        else (("odd",) if i % 2 else ()))
        # --- Kết quả cắt trong mặt phẳng (lát 4): chỉ giá trị, theo
        # quy ước hiển thị cắt đã chốt (chi tiết combo/vị trí thuộc
        # phần tab Chi tiết sau; ở đây dict shear_in đã đủ dữ liệu).
        _shp = _sh.get("parts") or {}
        if _sh.get("V_cap") is not None:
            _dc_sh = _sh.get("dc")
            _dc_sh_txt = (f"{_dc_sh:.3f}" if _dc_sh is not None
                          and math.isfinite(_dc_sh) else "∞")
            tree.insert("", tk.END,
                        values=("Vcap", "Khả năng chịu cắt trong mặt phẳng",
                                f"{_sh['V_cap']:.1f} kN"),
                        tags=("odd",))
            tree.insert("", tk.END,
                        values=("D/C cắt", "Tỷ số sử dụng khả năng chịu cắt",
                                f"{_dc_sh_txt}  "
                                + ("ĐẠT" if _sh_ok else "KHÔNG ĐẠT")),
                        tags=("dc_shear",) if _sh_ok is not None
                        else ("odd",))
            tree.insert("", tk.END,
                        values=("Thép ngang", "Thép ngang phân bố (cắt)",
                                _shp.get("sw_txt", "—")),
                        tags=("odd",))
        else:
            tree.insert("", tk.END,
                        values=("Vcap", "Khả năng chịu cắt trong mặt phẳng",
                                "— (chưa tính được)"),
                        tags=("odd",))
        # --- Kết quả cắt ngoài mặt phẳng (lát 4 — phần 4): chỉ giá trị;
        # công thức → thay số → kết luận riêng ở tab Chi tiết/PDF chi
        # tiết (cùng builder wall_detail).
        if _sho.get("V_cap") is not None:
            _dc_sho = _sho.get("dc")
            _dc_sho_txt = (f"{_dc_sho:.3f}" if _dc_sho is not None
                           and math.isfinite(_dc_sho) else "∞")
            tree.insert("", tk.END,
                        values=("Vcap ngoài MP",
                                "Khả năng chịu cắt ngoài mặt phẳng",
                                f"{_sho['V_cap']:.1f} kN"),
                        tags=("odd",))
            tree.insert("", tk.END,
                        values=("D/C cắt ngoài MP",
                                "Tỷ số sử dụng khả năng chịu cắt "
                                "ngoài mặt phẳng",
                                f"{_dc_sho_txt}  "
                                + ("ĐẠT" if _sho_ok else "KHÔNG ĐẠT")),
                        tags=("dc_shear_out",) if _sho_ok is not None
                        else ("odd",))
            _shop = _sho.get("parts") or {}
            _g_val = (_shop.get("sw_txt", "—")
                      if _shop.get("Asw", 0) > 0
                      and _shop.get("s_h", 0) > 0
                      else "không có — Qsw = 0")
            tree.insert("", tk.END,
                        values=("Giằng xuyên dày",
                                "Giằng xuyên dày (cắt ngoài MP)",
                                _g_val),
                        tags=("odd",))
        else:
            tree.insert("", tk.END,
                        values=("Vcap ngoài MP",
                                "Khả năng chịu cắt ngoài mặt phẳng",
                                "— (chưa tính được)"),
                        tags=("odd",))
        tree.pack(fill=tk.X, padx=2)
        # KHÔNG còn khối kết luận dưới bảng thông số (quyết user
        # 2026-10-24: chỉ thể hiện D/C P-M — đã có ở hàng D/C trong
        # bảng này và bullets A/B/O dưới biểu đồ). Bảng kết thúc ở
        # Treeview, không để khoảng trống.

    def _render_wall_detail(self, full):
        """Tab Chi tiết vách: các mục đánh số theo format web
        Vietcons (tiêu đề mục + căn cứ điều khoản góc phải, thẻ 2
        cột X/Y song song, công thức → thay số → kết quả + badge),
        dựng từ CÙNG builder với PDF chi tiết
        (rc_column.wall_detail.build_wall_detail_sections) nên số
        tab/PDF khớp nhau từng chữ số — chỉ đọc dict kết quả đã
        lưu, không tính lại. X = trong mặt phẳng, Y = ngoài mặt
        phẳng (xem ghi chú đảo nhãn web ở mục 4)."""
        for w in self._calc_inner.winfo_children():
            w.destroy()
        try:
            from rc_column.report_widgets import render_report_sections
            from rc_column.wall_detail import (
                build_wall_detail_sections, wall_detail_header)
            hdr = wall_detail_header(full)
            tk.Label(
                self._calc_inner, text=hdr["title"],
                font=("", 12, "bold"), bg="white").pack(
                    fill=tk.X, padx=4, pady=(6, 2))
            tk.Label(
                self._calc_inner, text=hdr["loads"],
                font=("", 9), fg="#374151", bg="white").pack(
                    fill=tk.X, padx=4, pady=(0, 4))
            sections = build_wall_detail_sections(full)
            render_report_sections(self._calc_inner, sections)
        except Exception as ex:
            # Fallback: thuyết minh text cũ nếu builder/render lỗi —
            # không để tab Chi tiết trắng sau CHECK.
            t = tk.Text(self._calc_inner, wrap="word",
                        font=("Consolas", 10), height=42)
            t.pack(fill=tk.BOTH, expand=True)
            lines = ["THUYẾT MINH KIỂM TRA VÁCH — TCVN 5574:2018",
                     f"(Lỗi dựng thẻ chi tiết: {ex} — hiển thị "
                     f"dạng text dự phòng)",
                     ""]
            lines += full["details"]
            t.insert(tk.END, "\n".join(lines))
            t.configure(state="disabled")
        self._calc_inner.update_idletasks()
        self._calc_canvas.configure(
            scrollregion=self._calc_canvas.bbox("all"))
        self._bind_wheel(self._calc_inner, self._calc_canvas)
