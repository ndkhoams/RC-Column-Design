"""Chế độ Vách (GĐ1 — lát 0: khung + plumbing; lát 1: N–M TCVN).

Gồm: frame nhập liệu vách (mục 2/3/4 khi ở chế độ Vách), chuyển đổi
loại cấu kiện Cột <-> Vách (_toggle_member), thu/áp dữ liệu vách cho
JSON (_collect_wall/_apply_wall), và điều phối CHECK ở chế độ Vách.

Lát 1: CHECK tay theo TCVN chạy engine vách (rc_column/wall_engine)
qua hàm duy nhất _tcvn_wall_calculate_full, kết quả lưu ở
self._tcvn_wall_full và hiển thị ở tab Kết quả/Chi tiết từ đúng dict
đó. ACI/EC2 vách (lát 2) và batch Pier Forces (lát 5) vẫn báo rõ
chưa hỗ trợ — tuyệt đối không chạy engine cột cho dữ liệu vách.
PDF vách TCVN (tóm tắt 1 trang + chi tiết cards) đã hỗ trợ từ
rc_column/wall_pdf_summary.py / wall_pdf_report.py qua
gui/pdf_mixin.py. Thiết kế: THIET_KE_TICH_HOP_VACH_GD1.md §2, §6, §8.

Từ 2026-10-23: mục 2/3/4 theo format công cụ web Vietcons "Kiểm tra
vách BTCT" — mục 2 (loại tiết diện + xoay + Lw/tw), mục 3 (2 chế độ
thép dọc: chu vi / tập trung vùng biên + khối số đọc trực tiếp), mục 4
(bảng P–δ 2 phương X/Y, ψ tự điền theo LK như bên cột, L0 chỉ hiển
thị). Các ô GĐ1 ngoài phạm vi web (thép ngang, đai vùng biên, kháng
chấn) gom vào frame "Bổ sung GĐ1". Mặt cắt vách có DIM từng khoảng
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
# Mục 2 (web): 6 loại tiết diện — GĐ1 chỉ loại đầu hoạt động
_SECTYPES = ["Vách phẳng chữ nhật", "Vách mở rộng hai đầu (Barbell)",
             "Vách chữ T", "Vách chữ L", "Lõi chữ C", "Lõi chữ U"]
# Mục 3 (web): 2 chế độ bố trí thép dọc
_STEEL_MODES = [("perimeter", "Phân bố đều theo chu vi"),
                ("boundary", "Tập trung vùng biên")]
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
    - dưới: thấp nhất là đáy chữ 'Lw = ...' ở -cy/2 - 2.22cy
      (hàng tổng luôn ở dưới cùng, cả khi không có hàng phân
      đoạn); chừa thêm 0.07cy tới -cy/2 - 2.29cy.
    rot_deg: span hiển thị = bao hình của 4 góc span canonical đã
    xoay (sec truyền vào luôn ở khung canonical: x = Lw, y = tw).
    """
    cx, cy = float(sec.cx), float(sec.cy)
    x_lo, x_hi = -cx / 2 - 0.105 * cx, cx / 2 + 0.02 * cx
    y_hi = cy / 2 + 1.27 * cy
    # Hàng tổng Lw luôn vẽ (kể cả không có phân đoạn) nên đáy span
    # luôn là -2.29cy; nhánh cũ -1.21cy khi không phân đoạn làm
    # dim + nhãn Lw tràn khỏi khung (đo Agg: nhãn ở y < 0, ngoài
    # figure). n_seg giữ lại cho chữ ký hàm, không còn ảnh hưởng
    # tới span.
    y_lo = -cy / 2 - 2.29 * cy
    if int(rot_deg or 0) % 360 == 0:
        return (x_lo, x_hi, y_lo, y_hi)
    pts = [_rot_xy(x, y, rot_deg)
           for x in (x_lo, x_hi) for y in (y_lo, y_hi)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), max(xs), min(ys), max(ys))


_WALL_SEC_PAD_PX = 9.0

# Cỡ tối thiểu hiển thị của điểm thép vách (đường kính, px màn
# hình). Thép tỉ lệ thật ở home chỉ ~1.3px (d12 trên nhịp ~2812mm)
# nên gần như tàng hình; sàn này khôi phục đúng mức nhìn của
# marker scatter cũ (s=16 -> diện tích 16pt² -> đường kính ~4.5pt
# ≈ 6px ở dpi 100) mà không lấn át mặt cắt. Khi zoom đủ lớn để tỉ
# lệ thật vượt sàn, thép theo đúng tỉ lệ thật và scale cùng mặt
# cắt (đường kính px = max(tỉ lệ thật, sàn)).
WALL_BAR_MIN_DIAM_PX = 6.0


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
    """Áp cỡ sàn hiển thị cho thép vách trên axes đã vẽ.

    Đường kính điểm thép trên màn hình = max(đường kính tỉ lệ thật
    tại khung nhìn hiện tại, WALL_BAR_MIN_DIAM_PX). Trả True nếu có
    radius đổi (nơi gọi vẽ lại một lần); False nếu đã đúng. Chỉ
    đọc transform hiện tại, không đổi lims nên không gây vòng lặp
    vẽ lại. Với equal aspect, tỉ lệ px/mm 2 phương bằng nhau nên
    tính theo phương x là đủ.
    """
    items = getattr(ax, "_wall_bar_items", None)
    if not items:
        return False
    try:
        _p0 = ax.transData.transform((0.0, 0.0))
        _p1 = ax.transData.transform((1.0, 0.0))
        px_per_mm = abs(float(_p1[0]) - float(_p0[0]))
        if px_per_mm <= 0:
            return False
        changed = False
        for circ, dia in items:
            r = max(dia / 2.0,
                    (WALL_BAR_MIN_DIAM_PX / 2.0) / px_per_mm)
            if abs(float(circ.radius) - r) > 1e-9:
                circ.set_radius(r)
                changed = True
        return changed
    except Exception:
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
    # và không đổi lims nên zoom/pan tính trên lims cũng chính
    # xác hơn. Ở ca bị kẹp chiều cao (tiết diện xoay đứng trong ô
    # thấp) hộp co theo chiều ngang, nội dung vẫn lấp đầy chiều
    # cao và căn giữa theo chiều ngang.
    # Khung home của zoom là span do _wall_section_spans trả.
    ax.set_aspect("equal", adjustable="box")
    cx, cy = float(sec.cx), float(sec.cy)
    DIA_COLORS = ["#DC2626", "#9333EA", "#EA580C", "#0891B2",
                  "#BE123C", "#CA8A04", "#0F766E", "#4D7C0F"]
    L2_COLOR = "#F59E0B"  # lớp 2 (thép phân bố): cam — như bên cột
    ax.set_axisbelow(True)
    ax.grid(True, color="#E8EDF3", linewidth=0.7)
    _rect = [(-cx / 2, -cy / 2), (cx / 2, -cy / 2),
             (cx / 2, cy / 2), (-cx / 2, cy / 2)]
    ax.add_patch(MplPolygon(RP(_rect), closed=True, fill=True,
                            facecolor="#F4F7FB", edgecolor="black",
                            lw=2.0, zorder=2))
    # --- Vùng nén + đường trung hòa (chỉ khi đã CHECK và có na_info) ---
    if show_compression and na_info is not None \
            and na_info.get("found") and na_info.get("yp_na") is not None:
        _st, _ct, _yp = na_info["st"], na_info["ct"], na_info["yp_na"]

        def _naval(_x, _y):
            return -_x * _st + _y * _ct - _yp
        _pts = []
        for _i in range(len(_rect)):
            _cur = _rect[_i]
            _prv = _rect[_i - 1]
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
        _edges = [(_rect[i], _rect[(i + 1) % 4]) for i in range(4)]
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
    _segs = (meta or {}).get("dim_segments") or []
    if _segs:
        for _x1, _x2, _lab in (_segs[0], _segs[-1]):
            ax.add_patch(MplPolygon(
                RP([(_x1, -cy / 2), (_x2, -cy / 2),
                    (_x2, cy / 2), (_x1, cy / 2)]),
                closed=True, fill=True,
                facecolor="#E0E7FF", edgecolor="none", zorder=2.5,
                alpha=0.55))
    # Thép theo (layer, dia) — hình tròn trong KHÔNG GIAN DỮ LIỆU
    # (bán kính đúng dia/2, đơn vị mm) thay cho marker scatter theo
    # điểm ảnh: zoom/pan thì thép scale cùng mặt cắt, ở home thì cỡ
    # điểm khớp tỉ lệ thật với cạnh tiết diện. Phép xoay R bảo toàn
    # hình tròn nên tâm xoay cứng như mọi phần tử khác.
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
            _circ = mpatches.Circle(
                (_qx, _qy), dia / 2.0,
                fill=True, facecolor=color, edgecolor="white",
                linewidth=0.8, zorder=5)
            ax.add_patch(_circ)
            _bar_items.append((_circ, float(dia)))
        legend_handles.append(Line2D(
            [0], [0], marker="o", color="none", markerfacecolor=color,
            markeredgecolor="white",
            markersize=max(4.0, dia * 0.22),
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
    a2 = 0.30 * cx
    a3 = cy / 2 + 0.85 * cy
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
    _lt3 = R(0.0, a3 + 0.16 * cy)
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
        _y_seg = -cy / 2 - 0.62 * cy
        for _x1, _x2, _lab in _segs:
            for _xx in (_x1, _x2):
                _ext((_xx, -cy / 2 - 0.10 * cy),
                     (_xx, _y_seg - 0.16 * cy))
            _dim((_x1, _y_seg), (_x2, _y_seg), _lab,
                 ((_x1 + _x2) / 2.0, _y_seg + 0.14 * cy),
                 0, "center", "bottom")
    # Hàng 2 (dưới cùng): kích thước tổng Lw, đường gióng từ 2 mép.
    _y_tot = -cy / 2 - 1.70 * cy
    for _xx in (-cx / 2, cx / 2):
        _ext((_xx, -cy / 2 - 0.10 * cy), (_xx, _y_tot - 0.16 * cy))
    _dim((-cx / 2, _y_tot), (cx / 2, _y_tot), f"Lw = {cx:.0f} mm",
         (0.0, _y_tot - 0.52 * cy), 0, "center", "bottom")
    # DIM đứng bên trái: kích thước tổng tw.
    _x_dim = -cx / 2 - 0.045 * cx
    for _yy in (-cy / 2, cy / 2):
        _ext((-cx / 2 - 0.012 * cx, _yy), (_x_dim - 0.008 * cx, _yy))
    _dim((_x_dim, -cy / 2), (_x_dim, cy / 2), f"tw = {cy:.0f} mm",
         (_x_dim - 0.018 * cx, 0.0), 90, "right", "center")
    x_lo, x_hi, y_lo, y_hi = _wall_section_spans(sec, len(_segs), rot)
    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(y_lo, y_hi)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    # Sàn hiển thị cho thép (xem _wall_bar_floor_apply): lưu danh
    # sách (Circle, dia) lên axes và gắn 1 lần handler draw_event.
    # draw_event phát SAU khi Figure.draw xong nên lims/bbox đã
    # chốt; handler chỉ vẽ lại khi radius thực
    # sự đổi nên hội tụ sau tối đa 2 lần vẽ, không vòng lặp. Bao
    # phủ cả 2 đường vẽ: _build_wall_section_cell (axes mới) và
    # _refresh_wall_preview (ax.clear() + vẽ lại trên axes cũ —
    # cờ hook sống qua clear(), danh sách được ghi đè mới mỗi lần
    # vẽ nên handler luôn đọc đúng thép hiện tại).
    try:
        ax._wall_bar_items = _bar_items
        if not getattr(ax, "_wall_bar_floor_hooked", False):
            ax._wall_bar_floor_hooked = True
            _fig = ax.figure
            if _fig is not None and _fig.canvas is not None:
                def _on_wall_draw(_evt, _ax=ax):
                    try:
                        if _wall_bar_floor_apply(_ax):
                            _ax.figure.canvas.draw_idle()
                    except Exception:
                        pass
                _fig.canvas.mpl_connect("draw_event", _on_wall_draw)
    except Exception:
        pass


def build_wall_shear_rows(full):
    """Dựng các hàng bảng cắt vách từ dict kết quả đã tính 1 lần.

    full: dict wall_tcvn_full. Mỗi hàng là (nhãn, trong MP, ngoài
    MP) dạng chuỗi đã format sẵn để _build_wall_shear_table chỉ việc
    vẽ. Hàng (98) KHÔNG có hàng riêng (quy ước cột: engine vẫn kiểm
    (98), qsw dưới đây đã là giá trị sau khi loại nhóm vi phạm;
    khi có nhóm bị loại thì ghi chú ngay ở hàng qsw).
    Ghi chú phóng đại DCM nằm ở Ô NHÃN của hàng V_Ed (không ở ô
    giá trị): ô giá trị chỉ còn "1200.0 kN". Ghi chú KHÔNG hiển
    thị V_raw (quyết user 2026-10-24: người dùng tự hiểu V2 đã
    được tự nhân); V_raw vẫn giữ nguyên trong dict kết quả.
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
        v_note = None
        if in_plane:
            v_d = sh.get("V_d")
            # Ô giá trị chỉ còn số trơn; ghi chú DCM chuyển sang ô
            # nhãn hàng (khóa "_v_ed_note" — không phải một hàng,
            # vòng dựng rows dưới đây gắn vào nhãn khi có).
            v_txt = f"{float(v_d):.1f} kN"
            v_note = ("(×1.5 DCM — TCVN 9386-1:2025 §5.4.2.4(7))"
                      if sh.get("seismic_applied") else None)
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
        else:
            v_d = sh.get("V_d")
            v_txt = f"{float(v_d):.1f} kN (không phóng đại)"
            sw_txt = parts.get("sw_txt", "—")
            asw_txt = "0 mm² (không có giằng xuyên dày)"
            qsw_txt = (f"{float(parts.get('qsw', 0.0) or 0.0):.1f} "
                       f"N/mm (không có giằng)")
            req_txt = "— (không có giằng)"
            prov_txt = "—"
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
            "Lực cắt tính toán, V_Ed": v_txt,
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
            "_v_ed_note": v_note,
        }

    labels = ["Thép bố trí",
              "Lực cắt tính toán, V_Ed",
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
        if (lab == "Lực cắt tính toán, V_Ed" and col_in is not None
                and col_in.get("_v_ed_note")):
            lab = f"{lab} {col_in['_v_ed_note']}"
        rows.append((lab, in_txt, out_txt))
    return rows


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
        toán & Uốn dọc' theo format web Vietcons, và frame 'Bổ sung
        GĐ1' giữ các ô ngoài phạm vi web (thép ngang, đai vùng biên,
        kháng chấn) để không mất plumbing các lát sau."""
        f2 = self._frame(T("2. Tiết diện"))
        self.frm_wall = f2
        f3 = self._frame(T("3. Bố trí cốt thép dọc"))
        self.frm_wall_rebar = f3
        f4 = self._frame(T("4. Chiều dài tính toán & Uốn dọc"))
        self.frm_wall_len = f4
        fx = self._frame(T("Bổ sung GĐ1 — thép ngang, đai vùng biên, "
                           "kháng chấn"))
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

        def _hdr(parent, text, r, span=2):
            ttk.Label(parent, text=text, font=("", 10, "bold")).grid(
                row=r, column=0, columnspan=span, sticky=tk.W,
                padx=4, pady=(8, 2))
            return r + 1

        def sv(v):
            try:
                fv = float(v)
            except Exception:
                return str(v)
            return str(int(fv)) if fv.is_integer() else str(fv)

        # ===== Mục 2. Tiết diện (web) =====
        r = 0
        self.w_cb_sectype = _combo(f2, _SECTYPES, _SECTYPES[0], width=24)
        self._row(f2, "Loại tiết diện vách / lõi", self.w_cb_sectype, r)
        r += 1
        rot_fr = ttk.Frame(f2)
        self.w_rot_var = tk.StringVar(value="0°")
        ttk.Label(rot_fr, textvariable=self.w_rot_var, width=5).pack(
            side=tk.LEFT)
        ttk.Button(rot_fr, text="Xoay +90°",
                   command=self._rotate_wall).pack(side=tk.LEFT, padx=4)
        self._wall_rot_deg = 0
        self._row(f2, "Xoay tiết diện", rot_fr, r)
        r += 1
        self.w_en_Lw = _entry(f2, D["Lw"])
        self._row(f2, "Lw (mm)", self.w_en_Lw, r); r += 1
        self.w_en_tw = _entry(f2, D["tw"])
        self._row(f2, "tw (mm)", self.w_en_tw, r); r += 1
        ttk.Label(
            f2, foreground="gray", wraplength=520,
            text="GĐ1 chỉ hỗ trợ 'Vách phẳng chữ nhật' — 5 loại còn "
                 "lại thuộc giai đoạn sau. Xoay 90°/270° hoán đổi vai "
                 "trò Lw/tw khi dựng hình và tính toán.").grid(
                     row=r, column=0, columnspan=2, padx=4, pady=(2, 4),
                     sticky=tk.W)

        # ===== Mục 3. Bố trí cốt thép dọc (web) =====
        r = 0
        self.w_cb_steel_mode = _combo(
            f3, [lab for _, lab in _STEEL_MODES],
            _label_of(_STEEL_MODES, D["steel_mode"],
                      "Phân bố đều theo chu vi"), width=24)
        self._row(f3, "Chế độ bố trí thép", self.w_cb_steel_mode, r)
        r += 1
        self.w_en_cover = _entry(f3, D["cover"])
        self._row(f3, "Lớp bảo vệ cốt đai, c (mm)", self.w_en_cover, r); r += 1
        # -- Khung con (a): phân bố đều theo chu vi --
        self.w_frm_per = ttk.Frame(f3)
        self.w_frm_per.grid(row=r, column=0, columnspan=2, sticky=tk.EW)
        r += 1
        rr = 0
        self.w_cb_per_dia = _combo(self.w_frm_per, _DIAS_WEB,
                                   sv(D["per_dia"]))
        self._row(self.w_frm_per, "Đường kính d", self.w_cb_per_dia, rr)
        rr += 1
        self.w_en_per_s = _entry(self.w_frm_per, D["per_s"])
        self._row(self.w_frm_per, "Khoảng cách s (mm)", self.w_en_per_s,
                  rr)
        # -- Khung con (b): tập trung vùng biên --
        self.w_frm_be = ttk.Frame(f3)
        self.w_frm_be.grid(row=r, column=0, columnspan=2, sticky=tk.EW)
        r += 1
        rr = 0
        rr = _hdr(self.w_frm_be, "Cốt thép vùng biên (2 đầu vách)", rr)
        lay_fr = ttk.Frame(self.w_frm_be)
        self.w_var_be_layout = tk.StringVar(
            value=_label_of(_BE_LAYOUTS, D["be_layout"], "Chu vi"))
        for _lab in ("Chu vi", "Lưới đặc"):
            tk.Radiobutton(lay_fr, text=_lab, value=_lab,
                           variable=self.w_var_be_layout, bg="white",
                           activebackground="white",
                           highlightthickness=0).pack(
                               side=tk.LEFT, padx=(0, 10))
        self._row(self.w_frm_be, "Kiểu bố trí", lay_fr, rr); rr += 1
        self.w_en_be_Lb = _entry(self.w_frm_be, D["be_Lb"])
        self._row(self.w_frm_be, "Chiều dài Lb (mm)", self.w_en_be_Lb,
                  rr); rr += 1
        self.w_cb_be_dia = _combo(self.w_frm_be, _DIAS_WEB,
                                  sv(D["be_dia"]))
        self._row(self.w_frm_be, "Đường kính db", self.w_cb_be_dia, rr)
        rr += 1
        self.w_en_be_nL = _entry(self.w_frm_be, D["be_nL"])
        self._row(self.w_frm_be, "Số vị trí dọc nL", self.w_en_be_nL, rr)
        rr += 1
        self.w_cb_be_nT = _combo(self.w_frm_be,
                                 [lab for _, lab in _NT_OPTS],
                                 _label_of(_NT_OPTS, D["be_nT"],
                                           "2 hàng (2 mặt)"))
        self._row(self.w_frm_be, "Số hàng thép nT", self.w_cb_be_nT, rr)
        rr += 1
        rr = _hdr(self.w_frm_be, "Thép phân bố thân vách", rr)
        self.w_cb_web_dia = _combo(self.w_frm_be, _DIAS_WEB,
                                   sv(D["web_dia"]))
        self._row(self.w_frm_be, "Đường kính d", self.w_cb_web_dia, rr)
        rr += 1
        self.w_en_web_s = _entry(self.w_frm_be, D["web_s"])
        self._row(self.w_frm_be, "Khoảng cách s (mm)", self.w_en_web_s,
                  rr); rr += 1
        ttk.Label(
            self.w_frm_be, foreground="gray", wraplength=520,
            text="GĐ1: 'Chu vi' và 'Lưới đặc' sinh cùng lưới nL x nT "
                 "(chưa phân biệt hình học).").grid(
                     row=rr, column=0, columnspan=2, padx=4, pady=(2, 2),
                     sticky=tk.W)
        # (Khối "Số đọc trực tiếp" ở panel đã bỏ theo quyết user
        # 2026-10-24 — dữ liệu suy ra vẫn tính bình thường cho ô
        # mặt cắt/thẻ thép qua build_wall_section, chỉ không hiển
        # thị khối readout này ở panel nữa.)

        # ===== Mục 4. Chiều dài tính toán & Uốn dọc (web) =====
        self.w_cb_pd = _combo(
            f4, [lab for _, lab in _PD_OPTS],
            _label_of(_PD_OPTS, D["pd_method"],
                      "Xét uốn dọc theo TCVN 5574:2018"), width=30)
        self._row(f4, "Phương pháp xét uốn dọc (P–δ)", self.w_cb_pd, 0)
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
        self.w_L0_var_x = tk.StringVar(value="—")
        self.w_L0_var_y = tk.StringVar(value="—")
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
        ttk.Label(f4, text="Chiều cao tính toán L₀ = ψ·L (m)",
                  width=self._LBL_WIDTH, anchor=tk.W).grid(
                      row=6, column=0, sticky=tk.W, padx=4, pady=2)
        ttk.Label(f4, textvariable=self.w_L0_var_x,
                  font=("", 9, "bold")).grid(row=6, column=1, padx=4,
                                              pady=2, sticky=tk.W)
        ttk.Label(f4, textvariable=self.w_L0_var_y,
                  font=("", 9, "bold")).grid(row=6, column=2, padx=4,
                                              pady=2, sticky=tk.W)
        ttk.Label(
            f4, foreground="gray", wraplength=520,
            text="L₀ chỉ suy ra lúc tính, không lưu riêng. Phương X "
                 "dùng cho uốn dọc trong mặt phẳng: "
                 "M* = N·max(e1, ea = Lw/30)·ηx (bổ sung 2026-10-24)."
            ).grid(row=7, column=0, columnspan=3, padx=4, pady=(2, 4),
                   sticky=tk.W)

        # ===== Bổ sung GĐ1 (ngoài format web) =====
        r = 0
        r = _hdr(fx, "Thép phân bố ngang (dùng cho cắt trong mặt phẳng)", r)
        self.w_cb_dia_h = _combo(fx, _DIAS, D["dia_h"])
        self._row(fx, "Thép ngang: đường kính (mm)", self.w_cb_dia_h, r)
        r += 1
        self.w_en_s_h = _entry(fx, D["s_h"])
        self._row(fx, "Thép ngang: khoảng cách s (mm)", self.w_en_s_h, r)
        r += 1
        self.w_cb_layers_h = _combo(fx, ["1", "2"], D["layers_h"])
        self._row(fx, "Thép ngang: số lớp lưới", self.w_cb_layers_h, r)
        r += 1
        # Cấp thép ngang RIÊNG của vách (phần 3/7): quyết định Rsw cho
        # kiểm tra cắt trong mặt phẳng — KHÔNG dùng ô thép đai của cột
        # và KHÔNG lấy theo cấp thép dọc nữa. Mặc định CB400-V (theo
        # quy ước ô thép đai của cột); preset web chỉ đổi thép DỌC
        # sang CB500-V, không chạm ô này (xem _wall_web_preset_enter).
        self.w_cb_sw_steel = _combo(fx, list(STEEL_GRADES), "CB400-V")
        _lbl_sw = self._row(fx, "Thép ngang: cấp thép (Rsw cắt vách)",
                            self.w_cb_sw_steel, r)
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
        self._row(fx, "Đai vùng biên: đường kính (mm)", self.w_cb_tie_dia,
                  r); r += 1
        self.w_en_tie_s = _entry(fx, D["tie_s_be"])
        self._row(fx, "Đai vùng biên: khoảng cách s (mm)", self.w_en_tie_s,
                  r); r += 1
        self.w_en_tie_legs = _entry(fx, D["tie_legs_be"])
        self._row(fx, "Đai vùng biên: số nhánh", self.w_en_tie_legs, r)
        r += 1
        self.w_en_hstory = _entry(fx, D["h_story"])
        self._row(fx, "Chiều cao đốt (mm)", self.w_en_hstory, r); r += 1
        self.w_en_htotal = _entry(fx, D["h_total"])
        self._row(fx, "Tổng chiều cao vách (mm)", self.w_en_htotal, r)
        r += 1
        self.w_cb_pos = _combo(
            fx, [lab for _, lab in _STORY_POS],
            _label_of(_STORY_POS, D["story_pos"], "Chân vách"))
        self._row(fx, "Vị trí đốt", self.w_cb_pos, r); r += 1
        self.w_var_lb_auto = tk.BooleanVar(value=bool(D["lb_auto"]))
        tk.Checkbutton(
            fx, text="Tự lấy Lb theo yêu cầu khi vùng biên bắt buộc "
                     "(kèm cảnh báo)",
            variable=self.w_var_lb_auto, bg="white",
            activebackground="white", highlightthickness=0).grid(
                row=r, column=0, columnspan=2, sticky=tk.W, padx=4, pady=4)
        r += 1
        r = _hdr(fx, "Kháng chấn", r)
        self.w_cb_aci_class = _combo(
            fx, [lab for _, lab in _ACI_CLASS],
            _label_of(_ACI_CLASS, D["seismic_class"], "Đặc biệt (Ch.18)"))
        self.w_lbl_aci_class = self._row(
            fx, "Loại vách (ACI 318-19)", self.w_cb_aci_class, r); r += 1
        self.w_var_seismic = tk.BooleanVar(value=bool(D["seismic_on"]))
        self.w_chk_seismic = tk.Checkbutton(
            fx, text="Kháng chấn DCM (TCVN 9386-1:2025)",
            variable=self.w_var_seismic, bg="white",
            activebackground="white", highlightthickness=0)
        self.w_chk_seismic.grid(
            row=r, column=0, columnspan=2, sticky=tk.W, padx=4, pady=4)
        r += 1
        self._toggle_wall_seismic()
        ttk.Label(
            fx, foreground="gray", wraplength=560,
            text="Lát 1: đã hỗ trợ kiểm tra N–M vách theo TCVN (nhập "
                 "tay ở mục 5: N / M2 = mô men ngoài mặt phẳng / M3 = "
                 "mô men trong mặt phẳng / Q2 = cắt trong mặt phẳng / "
                 "Q3 = cắt ngoài mặt phẳng). ACI/EC2, vùng biên, cắt "
                 "và Pier Forces thuộc các lát sau.").grid(
                     row=r, column=0, columnspan=2, padx=4, pady=(6, 2),
                     sticky=tk.W)
        # Khởi tạo hiển thị theo chế độ thép + ψ/L0
        self._on_wall_steel_mode()
        self._auto_psi_wall()
        # Ẩn ngay các frame phụ (frame mục 2 do build_mixin pack_forget)
        for _fr in (f3, f4, fx):
            _fr.pack_forget()
        # ---- Live preview / số đọc khi đổi nhập liệu ----
        for _w in (self.w_en_Lw, self.w_en_tw, self.w_en_cover,
                   self.w_en_per_s, self.w_en_be_Lb, self.w_en_be_nL,
                   self.w_en_web_s, self.w_en_hstory, self.w_en_htotal,
                   self.w_en_s_h, self.w_en_tie_s, self.w_en_tie_legs):
            _w.bind("<FocusOut>", lambda e: self._refresh_wall_preview())
        for _w in (self.w_en_Lx_m, self.w_en_Ly_m, self.w_en_psi_x,
                   self.w_en_psi_y):
            _w.bind("<FocusOut>",
                    lambda e: (self._update_wall_L0_labels(),
                               self._refresh_wall_preview()))
        for _cb in (self.w_cb_per_dia, self.w_cb_be_dia,
                    self.w_cb_be_nT, self.w_cb_web_dia, self.w_cb_pd,
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
        self.w_var_seismic.trace_add(
            "write", lambda *a: self._refresh_wall_preview())
        self.w_var_be_layout.trace_add(
            "write", lambda *a: self._refresh_wall_preview())

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

    def _on_wall_sectype(self):
        if self.w_cb_sectype.get() != _SECTYPES[0]:
            messagebox.showinfo(
                "Chế độ Vách",
                "Loại tiết diện này thuộc giai đoạn sau — GĐ1 chỉ hỗ "
                "trợ 'Vách phẳng chữ nhật'.")
            self.w_cb_sectype.set(_SECTYPES[0])
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
        self._update_wall_L0_labels()
        self._refresh_wall_preview()

    def _update_wall_L0_labels(self):
        """Hàng L0 = ψ·L ở mục 4 — chỉ HIỂN THỊ, không lưu riêng."""
        for en_L, en_p, var in (
                (self.w_en_Lx_m, self.w_en_psi_x, self.w_L0_var_x),
                (self.w_en_Ly_m, self.w_en_psi_y, self.w_L0_var_y)):
            try:
                L = float(str(en_L.get()).strip().replace(",", "."))
                p = float(str(en_p.get()).strip().replace(",", "."))
                var.set(f"{p * L:.2f} m")
            except Exception:
                var.set("—")

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
        mode = _code_of(_STEEL_MODES, self.w_cb_steel_mode.get(),
                        "perimeter")
        rev_bn = {v: k for k, v in BOUNDARY_NAMES.items()}
        psi_y = num(self.w_en_psi_y, D["psi_y"])
        be_Lb = num(self.w_en_be_Lb, D["be_Lb"])
        be_nT = int(_code_of(_NT_OPTS, self.w_cb_be_nT.get(), 2))
        if mode == "perimeter":
            dia_v = cnum(self.w_cb_per_dia, D["per_dia"])
            s_v = num(self.w_en_per_s, D["per_s"])
        else:
            dia_v = cnum(self.w_cb_web_dia, D["web_dia"])
            s_v = num(self.w_en_web_s, D["web_s"])
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
            "n_be": int(num(self.w_en_be_nL, D["be_nL"])) * be_nT,
            "tie_dia_be": cnum(self.w_cb_tie_dia, D["tie_dia_be"]),
            "tie_s_be": num(self.w_en_tie_s, D["tie_s_be"]),
            "tie_legs_be": int(num(self.w_en_tie_legs, D["tie_legs_be"])),
            "seismic_class": _code_of(_ACI_CLASS,
                                      self.w_cb_aci_class.get(),
                                      "special"),
            "seismic_on": bool(self.w_var_seismic.get()),
            # --- Format web (2026-10-23) ---
            "section_type": "rect",
            "rot_deg": int(getattr(self, "_wall_rot_deg", 0)) % 360,
            "steel_mode": mode,
            "per_dia": cnum(self.w_cb_per_dia, D["per_dia"]),
            "per_s": num(self.w_en_per_s, D["per_s"]),
            "be_layout": _code_of(_BE_LAYOUTS,
                                  self.w_var_be_layout.get(), "chuvi"),
            "be_Lb": be_Lb,
            "be_dia": cnum(self.w_cb_be_dia, D["be_dia"]),
            "be_nL": int(num(self.w_en_be_nL, D["be_nL"])),
            "be_nT": be_nT,
            "web_dia": cnum(self.w_cb_web_dia, D["web_dia"]),
            "web_s": num(self.w_en_web_s, D["web_s"]),
            "pd_method": _code_of(_PD_OPTS, self.w_cb_pd.get(), "tcvn"),
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
            # Nội lực vách lấy từ mục 5 dùng chung khi CHECK
            # (_collect_wall_loads); trong JSON giữ 0 như WallInput
            # mặc định (nội lực thật nằm ở các khóa mục 5 của file).
            "N": D["N"], "M_in": D["M_in"], "M_out": D["M_out"],
            "V_in": D["V_in"], "V_out": D["V_out"], "T": D["T"],
            # Dấu ngữ nghĩa cover (xem cover_migration): dict do app
            # mới lưu đã theo quy ước c_đai — mở lại không dịch nữa.
            "cover_semantics": COVER_SEMANTICS_NEW,
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

        # Mục 2
        self.w_cb_sectype.set(_SECTYPES[0])
        try:
            rot = int(float(d["rot_deg"])) % 360
        except Exception:
            rot = 0
        if rot not in (0, 90, 180, 270):
            rot = 0
        self._wall_rot_deg = rot
        self.w_rot_var.set(f"{rot}°")
        se(self.w_en_Lw, sv(d["Lw"]))
        se(self.w_en_tw, sv(d["tw"]))
        # Mục 3
        self.w_cb_steel_mode.set(_label_of(
            _STEEL_MODES, d["steel_mode"], "Phân bố đều theo chu vi"))
        se(self.w_en_cover, sv(d["cover"]))
        self.w_cb_per_dia.set(sv(d["per_dia"]))
        se(self.w_en_per_s, sv(d["per_s"]))
        self.w_var_be_layout.set(_label_of(_BE_LAYOUTS, d["be_layout"],
                                           "Chu vi"))
        se(self.w_en_be_Lb, sv(d["be_Lb"]))
        self.w_cb_be_dia.set(sv(d["be_dia"]))
        se(self.w_en_be_nL, sv(d["be_nL"]))
        self.w_cb_be_nT.set(_label_of(_NT_OPTS, d["be_nT"],
                                      "2 hàng (2 mặt)"))
        self.w_cb_web_dia.set(sv(d["web_dia"]))
        se(self.w_en_web_s, sv(d["web_s"]))
        # Mục 4
        self.w_cb_pd.set(_label_of(
            _PD_OPTS, d["pd_method"], "Xét uốn dọc theo TCVN 5574:2018"))
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
        # Bổ sung GĐ1
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
        self._update_wall_L0_labels()
        self._on_wall_steel_mode()
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

        Lát 1: chỉ nhập tay + TCVN. ETABS (batch pier) -> lát 5;
        ACI/EC2 vách -> lát 2.
        """
        if self.var_load_mode.get() == "etabs":
            self._wall_notice("Kiểm tra theo Pier Forces (ETABS)", "lát 5")
            return
        if self.is_ec2() or self.is_aci():
            self._wall_notice("Kiểm tra vách theo tiêu chuẩn này", "lát 2")
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
            # là lớp riêng cho đường batch ETABS (lát 5 sẽ tiêu thụ
            # cờ theo từng combo); ở đây không có combo nên không
            # xét seismic_combo_selected.
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
        _zst = {}
        _zbtns = tk.Frame(_hdr, bg="white")
        _zbtns.pack(side=tk.RIGHT, padx=(0, 4))
        tk.Button(_zbtns, text="−", font=("", 9, "bold"), width=2,
                  bg="white", relief=tk.GROOVE,
                  command=lambda: self._sec_zoom_step(_zst, 1.25)
                  ).pack(side=tk.LEFT, padx=1)
        tk.Button(_zbtns, text="+", font=("", 9, "bold"), width=2,
                  bg="white", relief=tk.GROOVE,
                  command=lambda: self._sec_zoom_step(_zst, 0.8)
                  ).pack(side=tk.LEFT, padx=1)
        tk.Button(_zbtns, text="Reset", font=("", 8), width=5,
                  bg="white", relief=tk.GROOVE,
                  command=lambda: self._sec_zoom_reset(_zst)
                  ).pack(side=tk.LEFT, padx=1)
        tk.Label(_hdr, text="MẶT CẮT TIẾT DIỆN",
                 font=("", 11, "bold"), bg="white").pack(
                     side=tk.TOP, fill=tk.X)
        if HAS_MPL:
            _nseg = len((meta or {}).get("dim_segments") or [])
            fig, canvas = self._new_wall_fig(
                f, _wall_section_figsize(sec, _nseg, _rot))
            ax = fig.add_subplot(111)
            draw_wall_section_ax(ax, sec, meta=meta, na_info=na_info,
                                 show_compression=show_compression,
                                 rot_deg=_rot)
            try:
                _wall_section_axes_pos(fig, ax)
            except Exception:
                pass
            canvas.draw()
            self._sec_fig, self._sec_canvas, self._sec_ax = fig, canvas, ax
            self._sec_zoom_setup(fig, canvas, ax, _zst)
            # Home của zoom = span chặt của nội dung vẽ: Reset đặt
            # lại lims này; mốc kẹp zoom cũng theo span này.
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

    # ---------- Zoom / pan / reset cho ô mặt cắt vách (như web) ----
    # Cuộn chuột: zoom tại vị trí con trỏ; kéo trái: pan; nút +/− và
    # Reset ở góc ô; double-click: reset. Gắn ở mức widget SAU
    # _bind_wheel đệ quy của tab (after_idle) để cuộn trên canvas
    # mặt cắt không cuộn cả tab; các biểu đồ khác không bị ảnh
    # hưởng. Sau mỗi lần vẽ lại (CHECK/làm mới), view về khung gốc.
    def _sec_zoom_setup(self, fig, canvas, ax, zst):
        zst.update({"fig": fig, "canvas": canvas, "ax": ax,
                    "home": (ax.get_xlim(), ax.get_ylim()),
                    "drag": None})
        self._sec_zoom = zst
        w = canvas.get_tk_widget()
        zst["widget"] = w

        def _attach():
            w.bind("<MouseWheel>",
                   lambda e: self._sec_zoom_wheel(e, zst))
            w.bind("<Button-4>",
                   lambda e: self._sec_zoom_wheel_btn(e, zst, -1))
            w.bind("<Button-5>",
                   lambda e: self._sec_zoom_wheel_btn(e, zst, 1))
            w.bind("<ButtonPress-1>",
                   lambda e: self._sec_zoom_press(e, zst))
            w.bind("<B1-Motion>",
                   lambda e: self._sec_zoom_motion(e, zst))
            w.bind("<ButtonRelease-1>",
                   lambda e: self._sec_zoom_release(e, zst))
            w.bind("<Double-Button-1>",
                   lambda e: self._sec_zoom_reset(zst))
        try:
            w.after_idle(_attach)
        except Exception:
            _attach()

    def _sec_zoom_data_at(self, zst, event, lims=None):
        """Toạ độ dữ liệu tại vị trí con trỏ (event Tk trên canvas)
        theo lims cho trước (mặc định: lims hiện tại của axes)."""
        ax = zst["ax"]
        _fw, fh = zst["fig"].canvas.get_width_height()
        px, py = float(event.x), fh - float(event.y)
        bb = ax.bbox
        (x0, x1), (y0, y1) = lims or (ax.get_xlim(), ax.get_ylim())
        fx = (px - bb.x0) / max(1.0, bb.width)
        fy = (py - bb.y0) / max(1.0, bb.height)
        return (x0 + fx * (x1 - x0), y0 + fy * (y1 - y0))

    def _sec_zoom_apply(self, zst, factor, center):
        ax = zst["ax"]
        (hx0, hx1), (hy0, hy1) = zst["home"]

        def _new(v0, v1, c, hspan):
            span = (v1 - v0) * factor
            span = min(max(span, hspan * 0.02), hspan * 6.0)
            f2 = span / (v1 - v0) if v1 != v0 else factor
            return c - (c - v0) * f2, c + (v1 - c) * f2

        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        ax.set_xlim(_new(x0, x1, center[0], hx1 - hx0))
        ax.set_ylim(_new(y0, y1, center[1], hy1 - hy0))
        zst["canvas"].draw_idle()

    def _sec_zoom_wheel(self, event, zst):
        try:
            d = getattr(event, "delta", 0) or 0
            c = self._sec_zoom_data_at(zst, event)
            self._sec_zoom_apply(zst, 0.8 if d > 0 else 1.25, c)
        except Exception:
            pass
        return "break"

    def _sec_zoom_wheel_btn(self, event, zst, sgn):
        try:
            c = self._sec_zoom_data_at(zst, event)
            self._sec_zoom_apply(zst, 0.8 if sgn < 0 else 1.25, c)
        except Exception:
            pass
        return "break"

    def _sec_zoom_step(self, zst, factor):
        if not zst or "ax" not in zst:
            return
        try:
            x0, x1 = zst["ax"].get_xlim()
            y0, y1 = zst["ax"].get_ylim()
            self._sec_zoom_apply(
                zst, factor, ((x0 + x1) / 2.0, (y0 + y1) / 2.0))
        except Exception:
            pass

    def _sec_zoom_reset(self, zst):
        if zst and "ax" in zst:
            try:
                (x0, x1), (y0, y1) = zst["home"]
                zst["ax"].set_xlim(x0, x1)
                zst["ax"].set_ylim(y0, y1)
                zst["canvas"].draw_idle()
            except Exception:
                pass
        return "break"

    def _sec_zoom_press(self, event, zst):
        try:
            lims = (zst["ax"].get_xlim(), zst["ax"].get_ylim())
            zst["drag"] = {"lims": lims,
                           "data": self._sec_zoom_data_at(
                               zst, event, lims)}
            zst["widget"].configure(cursor="fleur")
        except Exception:
            zst["drag"] = None
        return "break"

    def _sec_zoom_motion(self, event, zst):
        dr = zst.get("drag") if zst else None
        if dr:
            try:
                d1 = self._sec_zoom_data_at(zst, event, dr["lims"])
                (x0, x1), (y0, y1) = dr["lims"]
                sx = dr["data"][0] - d1[0]
                sy = dr["data"][1] - d1[1]
                zst["ax"].set_xlim(x0 + sx, x1 + sx)
                zst["ax"].set_ylim(y0 + sy, y1 + sy)
                zst["canvas"].draw_idle()
            except Exception:
                pass
        return "break"

    def _sec_zoom_release(self, event, zst):
        if zst:
            zst["drag"] = None
            try:
                zst["widget"].configure(cursor="")
            except Exception:
                pass
        return "break"

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
                # Vẽ lại xong: view zoom về khung gốc của dữ liệu mới
                # (home = span gốc như ở _build_wall_section_cell)
                _zst = getattr(self, "_sec_zoom", None)
                if _zst is not None and _zst.get("ax") is ax:
                    _sp = _wall_section_spans(
                        secD,
                        len((metaD or {}).get("dim_segments") or []),
                        _rotD)
                    _zst["home"] = ((_sp[0], _sp[1]), (_sp[2], _sp[3]))
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
            # Combobox "Góc xem:" như bên cột nhưng KHÔNG có "3D"
            # (vách không có mặt 3D): đổi góc chỉ vẽ lại biểu đồ
            # N–Mα này, điểm A/B, D/C và khối ghi chú giữ nguyên
            # số góc tải.
            self._wall_nm_ax = ax2
            self._wall_nm_cv = cv2
            self._wall_nm_full = full
            _right = tk.Frame(hdr, bg="white")
            _right.pack(side=tk.RIGHT)
            tk.Label(_right, text="Góc xem:", font=("", 8),
                     bg="white").pack(side=tk.LEFT)
            _vals = ["α (góc tải)"] + \
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
        # ===== Bảng kiểm tra cắt (full-width, row 3, cuối tab) =====
        # Khối diễn giải dưới bảng cắt (căn cứ + phạm vi) đã bỏ
        # theo quyết user 2026-10-24 — tab kết thúc ở hàng Kết luận
        # của bảng cắt, không để khoảng trống.
        self._sum_inner.rowconfigure(3, weight=0)
        self._build_wall_shear_table(self._sum_inner, full)
        self._finish_wall_sum_layout()

    def _on_wall_nm_angle_changed(self, event=None):
        """Vẽ lại CHỈ biểu đồ N–Mα vách tại góc xem đã chọn.

        Như bên cột nhưng không có "3D": "α (góc tải)" -> góc tải
        của dict; "0°".."360°" -> xoay mô men thiết kế qua
        adapter. Điểm A/B, D/C và khối ghi chú giữ nguyên."""
        try:
            ax = getattr(self, "_wall_nm_ax", None)
            cv = getattr(self, "_wall_nm_cv", None)
            full = getattr(self, "_wall_nm_full", None)
            if ax is None or cv is None or full is None:
                return
            sel = self._wall_nm_cb.get()
            if sel.startswith("α"):
                angle = None
            else:
                angle = float(sel.replace("°", ""))
        except Exception:
            return
        try:
            from rc_column.chart_draw import draw_nm_alpha_ax
            from rc_column.wall_chart_adapter import wall_chart_inputs
            sec, inp_ns, res_ns = wall_chart_inputs(
                full, view_angle_deg=angle)
            ax.clear()
            draw_nm_alpha_ax(ax, sec, inp_ns, res_ns, None)
            cv.draw()
        except Exception:
            pass

    def _build_wall_param_table(self, parent, full):
        """Bảng thông số vách (đọc từ dict kết quả, không tính lại)."""
        winp = full["winp"]
        sec = full["sec"]
        sl = full["slend"]
        ttk.Label(parent, text="BẢNG THÔNG SỐ — VÁCH (TCVN 5574:2018)",
                  font=("", 11, "bold")).pack(pady=(2, 6))
        cols = ("sym", "desc", "val")
        tree = ttk.Treeview(parent, columns=cols, show="headings",
                            height=20, style="Param.Treeview")
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
        fs_txt = (f"{full['fs']:.2f}" if math.isfinite(full["fs"])
                  else "∞")
        # Bỏ 5 hàng Lw/tw/Ab/As/μ (user chốt 2026-10-22): Lw/tw đã có
        # nhãn kích thước trên hình mặt cắt, As/Ab/μ đã có ở hàng thẻ.
        rows = [
            ("N", "Lực dọc tính toán", f"{full['N']:+.1f} kN"),
            ("M3", "Mô men trong mặt phẳng ban đầu",
             f"{full['M_in']:.1f} kN·m"),
            ("M2", "Mô men ngoài mặt phẳng ban đầu",
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
            ("φL", "Hệ số φL", f"{full['phi_L']:.2f}"),
            ("Ncr", "Lực tới hạn Euler ngoài mặt phẳng",
             f"{sl['Ncr_out']:,.0f} kN"),
            ("η", "Hệ số uốn dọc ngoài mặt phẳng",
             f"{sl['factor_out']:.3f}"),
            ("Ncrx", "Lực tới hạn Euler trong mặt phẳng",
             f"{sl.get('Ncr_in', 0.0):,.0f} kN"),
            ("ηx", "Hệ số uốn dọc trong mặt phẳng",
             f"{sl.get('factor_in', 1.0):.3f}"),
            ("M2*", "Mô men ngoài mặt phẳng đã phóng đại",
             f"{full['M_out_d']:.1f} kN·m"),
            ("M3*", "Mô men trong mặt phẳng đã phóng đại",
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
        for i, (s, d, v) in enumerate(rows):
            tree.insert("", tk.END, values=(s, d, v),
                        tags=("odd",) if i % 2 else ())
        tree.insert("", tk.END,
                    values=("D/C", "Tỷ số sử dụng khả năng chịu lực (N–M)",
                            f"{full['dc']:.3f} (FS = {fs_txt})  "
                            + ("ĐẠT" if full["ok"] else "KHÔNG ĐẠT")),
                    tags=("dc",))
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
            tree.insert("", tk.END,
                        values=("Giằng xuyên dày",
                                "Giằng xuyên dày (cắt ngoài MP)",
                                "không có — Qsw = 0"),
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
