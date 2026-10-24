"""Chế độ Vách (GĐ1 — lát 0: khung + plumbing; lát 1: N–M TCVN).

Gồm: frame nhập liệu vách (mục 2/3/4 khi ở chế độ Vách), chuyển đổi
loại cấu kiện Cột <-> Vách (_toggle_member), thu/áp dữ liệu vách cho
JSON (_collect_wall/_apply_wall), và điều phối CHECK ở chế độ Vách.

Lát 1: CHECK tay theo TCVN chạy engine vách (rc_column/wall_engine)
qua hàm duy nhất _tcvn_wall_calculate_full, kết quả lưu ở
self._tcvn_wall_full và hiển thị ở tab Kết quả/Chi tiết từ đúng dict
đó. ACI/EC2 vách (lát 2), batch Pier Forces (lát 5) và PDF vách
(lát 6) vẫn báo rõ chưa hỗ trợ — tuyệt đối không chạy engine cột cho
dữ liệu vách. Thiết kế: THIET_KE_TICH_HOP_VACH_GD1.md §2, §6, §8.

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
from rc_column.wall_section import build_wall_section, wall_readouts

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
#    thép vách đã lùi khỏi mép >= cover+đai+dia/2 nên không chạm viền).
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
    """Giới hạn trục (x_lo, x_hi, y_lo, y_hi) cho hình mặt cắt vách.

    n_seg > 0 (chế độ vùng biên): chừa thêm 1 hàng DIM phân đoạn
    (Lb | đoạn giữa | Lb) bên dưới hàng DIM tổng. rot_deg: span ở
    khung hiển thị = bao hình của 4 góc span canonical đã xoay
    (sec truyền vào luôn ở khung canonical: x = Lw, y = tw).
    """
    cx, cy = float(sec.cx), float(sec.cy)
    y_lo = -cy / 2 - (2.15 * cy if n_seg else 1.25 * cy)
    x_lo, x_hi = -cx / 2 - 0.10 * cx, cx / 2 + 0.05 * cx
    y_hi = cy / 2 + 1.55 * cy
    if int(rot_deg or 0) % 360 == 0:
        return (x_lo, x_hi, y_lo, y_hi)
    pts = [_rot_xy(x, y, rot_deg)
           for x in (x_lo, x_hi) for y in (y_lo, y_hi)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), max(xs), min(ys), max(ys))


def _wall_section_figsize(sec, n_seg=0, rot_deg=0):
    """Cỡ figure khớp tỉ lệ span dữ liệu -> aspect 'equal' không bóp
    dẹt hình và không chừa dải trống lớn quanh mặt cắt."""
    x_lo, x_hi, y_lo, y_hi = _wall_section_spans(sec, n_seg, rot_deg)
    ratio = (x_hi - x_lo) / max(1e-9, y_hi - y_lo)
    w = 5.5
    h = w / max(ratio, 0.55) * 0.94
    return (w, min(3.3, max(2.0, h)))


def _dim_h(ax, x1, x2, y, text, text_dy=0.30, fs=8):
    """DIM ngang kiểu bản vẽ: đường dim + 2 mũi tên vào trong + số
    ở giữa phía trên đường (text_dy theo đơn vị dữ liệu)."""
    ax.annotate("", xy=(x1, y), xytext=(x2, y),
                arrowprops=dict(arrowstyle="<->", color="black", lw=0.8,
                                shrinkA=0, shrinkB=0), zorder=4)
    if text:
        ax.text((x1 + x2) / 2.0, y + text_dy, text, fontsize=fs,
                weight="bold", ha="center", va="bottom", zorder=4)


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
    # Chấm thép theo (layer, dia) — marker cố định theo điểm ảnh
    groups = {}
    for r in sec.rebars:
        groups.setdefault((r.layer, r.dia), []).append(r)
    dias_l1 = sorted(set(d for (ly, d) in groups if ly == 1),
                     reverse=True)
    dia_color = {d: DIA_COLORS[i % len(DIA_COLORS)]
                 for i, d in enumerate(dias_l1)}
    legend_handles = []
    for (layer, dia) in sorted(groups, key=lambda k: (k[0], -k[1])):
        pts = groups[(layer, dia)]
        color = dia_color.get(dia, "#DC2626") if layer == 1 else L2_COLOR
        dot_s = (max(4.0, dia * 0.22)) ** 2
        _rp = [R(p.x, p.y) for p in pts]
        ax.scatter([q[0] for q in _rp], [q[1] for q in _rp],
                   s=dot_s, c=color, zorder=5,
                   edgecolors="white", linewidths=0.8)
        legend_handles.append(Line2D(
            [0], [0], marker="o", color="none", markerfacecolor=color,
            markeredgecolor="white",
            markersize=max(4.0, dia * 0.22),
            label=f"D{dia:.0f}"))
    # Legend thép: box viền riêng bên phải hình (như tab Kết quả cột)
    if legend_handles:
        leg = ax.legend(handles=legend_handles, loc="center left",
                        bbox_to_anchor=(1.01, 0.5), ncol=1,
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

    # Hàng 1 (dưới đáy): kích thước tổng Lw, đường gióng từ 2 mép.
    _y_tot = -cy / 2 - 0.62 * cy
    for _xx in (-cx / 2, cx / 2):
        _ext((_xx, -cy / 2 - 0.10 * cy), (_xx, _y_tot - 0.16 * cy))
    _dim((-cx / 2, _y_tot), (cx / 2, _y_tot), f"Lw = {cx:.0f} mm",
         (0.0, _y_tot - 0.52 * cy), 0, "center", "bottom")
    # Hàng 2: phân đoạn Lb | đoạn giữa | Lb (chỉ chế độ vùng biên).
    if _segs:
        _y_seg = -cy / 2 - 1.70 * cy
        for _x1, _x2, _lab in _segs:
            for _xx in (_x1, _x2):
                _ext((_xx, -cy / 2 - 0.10 * cy),
                     (_xx, _y_seg - 0.16 * cy))
            _dim((_x1, _y_seg), (_x2, _y_seg), _lab,
                 ((_x1 + _x2) / 2.0, _y_seg + 0.14 * cy),
                 0, "center", "bottom")
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
        self._row(f3, "Lớp bảo vệ c (mm)", self.w_en_cover, r); r += 1
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
        # -- Khối số đọc trực tiếp (web) --
        r = _hdr(f3, "Số đọc trực tiếp", r)
        self.w_readout = tk.Text(f3, height=8, font=("Consolas", 9),
                                 wrap="none", bg="#F9FAFB", relief="solid",
                                 borderwidth=1)
        self.w_readout.grid(row=r, column=0, columnspan=2, sticky=tk.EW,
                            padx=4, pady=(2, 4))
        self.w_readout.configure(state="disabled")

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
        r = _hdr(fx, "Thép phân bố ngang (chỉ dùng cho cắt — lát 4)", r)
        self.w_cb_dia_h = _combo(fx, _DIAS, D["dia_h"])
        self._row(fx, "Thép ngang: đường kính (mm)", self.w_cb_dia_h, r)
        r += 1
        self.w_en_s_h = _entry(fx, D["s_h"])
        self._row(fx, "Thép ngang: khoảng cách s (mm)", self.w_en_s_h, r)
        r += 1
        self.w_cb_layers_h = _combo(fx, ["1", "2"], D["layers_h"])
        self._row(fx, "Thép ngang: số lớp lưới", self.w_cb_layers_h, r)
        r += 1
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
            fx, text="Kháng chấn DCM (TCVN 9386:2012)",
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

    def _update_wall_readouts(self, sec=None, meta=None):
        """Khối SỐ ĐỌC ở mục 3 — tính từ đúng (sec, meta) của
        build_wall_section (không suy lại ở nơi khác)."""
        txt = getattr(self, "w_readout", None)
        if txt is None:
            return
        try:
            winp = wall_from_dict(self._collect_wall())
            if sec is None:
                conc, steel, _m = self._wall_tcvn_materials()
                sec, meta = build_wall_section(winp, conc, steel)
            ro = wall_readouts(winp, sec, meta)
            lines = []
            if (meta or {}).get("steel_mode") == "boundary":
                for z in ro["zones"]:
                    lines.append(
                        f"{z['name']}: {z['n']} thanh d{z['dia']:.0f} — "
                        f"As = {z['As']:.0f} mm² (µ = {z['mu'] * 100:.2f}%)")
            lines.append(f"{ro['n_bars']} thanh — {ro['summary']}")
            lines.append(f"Tổng As = {ro['As']:.0f} mm²   •   "
                         f"Hàm lượng µ = {ro['mu'] * 100:.2f}%")
            lines.append(f"Diện tích Ac = {ro['Ac_m2']:.3f} m²")
            lines.append(f"Quán tính Ix = {ro['Ix_m4']:.4g} m⁴   •   "
                         f"Iy = {ro['Iy_m4']:.4g} m⁴")
            if ro["sclear_min"] is not None:
                lines.append(
                    f"Khoảng hở thông thủy sclear,min = "
                    f"{ro['sclear_min']:.1f} mm")
                lines.append(
                    f"Khoảng cách tim smax = {ro['smax']:.1f} mm "
                    f"(min: {ro['s_step_min']:.1f})")
            body = "\n".join(lines)
        except Exception as ex:
            body = f"(chưa tính được số đọc: {ex})"
        try:
            txt.configure(state="normal")
            txt.delete("1.0", tk.END)
            txt.insert("1.0", body)
            txt.configure(state="disabled")
        except Exception:
            pass


    # ---------------- Kháng chấn: lọc option theo tiêu chuẩn ----------------
    def _toggle_wall_seismic(self):
        """Nhóm 'Kháng chấn' của panel vách: chỉ hiện option thuộc
        tiêu chuẩn đang chọn (user chốt 2026-10-22):
        ACI -> ô 'Loại vách (ACI 318-19)'; TCVN -> checkbox
        'Kháng chấn DCM (TCVN 9386:2012)'; EC2 -> checkbox
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
                else "Kháng chấn DCM (TCVN 9386:2012)")

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
            for fr in cols:
                fr.pack_forget()
            for fr in frames:
                fr.pack(fill=tk.X, padx=8, pady=8,
                        before=self.frm_loads)
            self._refresh_wall_preview()
        else:
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
        }

    def _apply_wall(self, w: dict):
        """Đổ dict vách vào các ô nhập (khóa thiếu -> mặc định; dict
        cũ được dịch trước qua normalize_wall_dict)."""
        if not hasattr(self, "w_en_Lw"):
            return
        d = dict(WALL_DEFAULTS)
        if isinstance(w, dict):
            d.update({k: v for k, v in normalize_wall_dict(w).items()
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
                                  loads=None, case_info=None):
        """Tính 1 lần bằng engine vách; tab/PDF chỉ đọc dict trả về."""
        return wall_tcvn_full(winp, conc, steel, model=model,
                              loads=loads, case_info=case_info)

    def _check_wall_tcvn(self):
        try:
            winp = wall_from_dict(self._collect_wall())
            loads = self._collect_wall_loads()
            conc, steel, model = self._wall_tcvn_materials()
            full = self._tcvn_wall_calculate_full(
                winp, conc, steel, model, loads=loads)
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
                                 winp=None):
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
                fig.tight_layout()
            except Exception:
                pass
            canvas.draw()
            self._sec_fig, self._sec_canvas, self._sec_ax = fig, canvas, ax
            self._sec_zoom_setup(fig, canvas, ax, _zst)
            # Ô bị lưới kéo co khác cỡ figure gốc: chạy lại
            # tight_layout khi kích thước canvas đã ổn định để box
            # legend bên phải luôn nằm trọn trong figure (legend có
            # cỡ chữ cố định nên không co theo tỉ lệ figure).
            _cw = canvas.get_tk_widget()
            _st = {"id": None, "size": (0, 0)}

            def _relayout(event=None):
                if event is not None:
                    if (abs(event.width - _st["size"][0]) < 4
                            and abs(event.height - _st["size"][1]) < 4):
                        return
                    _st["size"] = (event.width, event.height)
                if _st["id"] is not None:
                    try:
                        _cw.after_cancel(_st["id"])
                    except Exception:
                        pass

                def _apply():
                    _st["id"] = None
                    try:
                        fig.tight_layout()
                        canvas.draw_idle()
                    except Exception:
                        pass
                _st["id"] = _cw.after(180, _apply)
            _cw.bind("<Configure>", _relayout)
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
                                              meta=meta, winp=winp)
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
            self._update_wall_readouts()
            return
        self._update_wall_readouts(sec, meta)
        ax = getattr(self, "_sec_ax", None)
        if getattr(self, "_wall_view_active", False) and ax is not None:
            try:
                secD, metaD, _naD, _rotD = self._wall_display_geom(
                    sec, meta, None, winp)
                ax.clear()
                draw_wall_section_ax(ax, secD, meta=metaD, rot_deg=_rotD)
                self._sec_fig.tight_layout()
                self._sec_canvas.draw_idle()
                # Vẽ lại xong: view zoom về khung gốc của dữ liệu mới
                _zst = getattr(self, "_sec_zoom", None)
                if _zst is not None and _zst.get("ax") is ax:
                    _zst["home"] = (ax.get_xlim(), ax.get_ylim())
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
    def _show_wall_result(self, full):
        """Tab Kết quả cho vách (đọc từ dict _tcvn_wall_full, không
        tính lại) — lưới 2x2 như bên cột: banner trên cùng; hàng trên
        bảng thông số | mặt cắt + thẻ thép; hàng dưới biểu đồ N–Mα |
        ô dành cho biểu đồ thứ hai; ghi chú phạm vi full-width."""
        for w in self._sum_inner.winfo_children():
            w.destroy()
        self._wall_view_active = True
        self._last_sec = full["sec"]
        self._wall_sum_grid()
        ok = full["ok"]
        banner = tk.Label(
            self._sum_inner,
            text=("KẾT QUẢ KIỂM TRA VÁCH — TCVN 5574:2018   •   "
                  + ("ĐẠT (N–M)" if ok else "KHÔNG ĐẠT (N–M)")),
            font=("", 11, "bold"),
            bg="#D1FAE5" if ok else "#FEE2E2",
            fg="#065F46" if ok else "#991B1B")
        banner.grid(row=0, column=0, columnspan=2, sticky="ew",
                    padx=2, pady=(4, 2))
        # ===== Ô trên-trái: bảng thông số =====
        f_tr = tk.Frame(self._sum_inner, bg="white",
                        highlightbackground="#D1D5DB",
                        highlightcolor="#D1D5DB", highlightthickness=1,
                        takefocus=0)
        f_tr.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._build_wall_param_table(f_tr, full)
        # ===== Ô trên-phải: mặt cắt tiết diện + thẻ thép =====
        f_tl = self._build_wall_section_cell(
            self._sum_inner, full["sec"], meta=full.get("meta"),
            na_info=full.get("na_info"), show_compression=True,
            winp=full.get("winp"))
        f_tl.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        # ===== Ô dưới-trái: biểu đồ N–Mα =====
        f_bl = tk.Frame(self._sum_inner, bg="white",
                        highlightbackground="#D1D5DB",
                        highlightcolor="#D1D5DB", highlightthickness=1,
                        takefocus=0)
        f_bl.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
        hdr = tk.Frame(f_bl, bg="white")
        hdr.pack(fill=tk.X, padx=4, pady=(2, 2))
        tk.Label(hdr, text="● Biểu đồ tương tác N–Mα",
                 font=("", 10, "bold"), bg="white").pack(side=tk.LEFT)
        if HAS_MPL:
            from rc_column.interaction import BiaxialCapacity
            fig2, cv2 = self._new_wall_fig(f_bl, (5.2, 3.9))
            ax2 = fig2.add_subplot(111)
            # Đường cong N–Mα: capacity EXACT tại góc α — cùng nguồn
            # solver sinh điểm B (như chart_draw.draw_nm_alpha_ax của
            # cột từ 2026-10-21). KHÔNG dùng uniaxial_curve_fs: đường
            # cong construction đơn trục cho Mα lớn hơn exact ~2–6%
            # (tại BN của ca chuẩn: +5.8%) khiến B nằm PHÍA TRONG
            # đường cong đã vẽ.
            _cap = BiaxialCapacity(full["sec"], model=full["model"])
            _eng = _cap._exact
            _n_lv = 64
            _levels = [_eng.N_max + (_eng.N_min - _eng.N_max) * _i
                       / (_n_lv - 1) for _i in range(_n_lv)]
            _BN = full["BN"]
            if math.isfinite(_BN) and _eng.N_min < _BN < _eng.N_max \
                    and _BN not in _levels:
                # Chèn mức N của B để polyline đi đúng qua B
                _levels.append(_BN)
                _levels.sort(reverse=True)
            _ns, _ms = [], []
            for _N in _levels:
                _ns.append(float(_N))
                _ms.append(_cap.moment_capacity(float(_N),
                                                full["alpha_deg"]))
            ax2.plot(_ms, _ns, color="#059669", lw=1.8, zorder=3)
            # Tô màu vùng tương tác như biểu đồ N–M của cột
            # (chart_draw.draw_nm_alpha_ax: GREEN #059669, alpha 0.08)
            ax2.fill_betweenx(_ns, 0, _ms, color="#059669", alpha=0.08,
                              zorder=1)
            lam = full["lambda_ray"]
            _MB = lam * full["Malpha"] if math.isfinite(lam) else None
            # Tia tải O–A–B như bên cột (chart_draw.draw_nm_alpha_ax:
            # nét đứt đỏ từ gốc qua A tới B, kéo dài 1.18 lần)
            if _MB is not None:
                ax2.plot([0, _MB * 1.18], [0, _BN * 1.18],
                         color="#DC2626", ls="--", lw=1.5,
                         dashes=(4, 3), zorder=4)
            ax2.scatter([full["Malpha"]], [full["N"]], c="#DC2626",
                        zorder=5, label="A (làm việc)")
            if _MB is not None:
                ax2.scatter([_MB], [_BN],
                            c="#2563EB", zorder=5, label="B (giới hạn)")
            # Chỉ hiện góc 1/4 chứa tia làm việc như cột chỉ hiện nửa
            # có tải: Mα >= 0 luôn; phía N theo dấu N của điểm A/B.
            ax2.set_xlim(left=0)
            if full["N"] >= 0:
                ax2.set_ylim(bottom=0)
            else:
                ax2.set_ylim(top=0)
            ax2.set_xlabel("Mα (kN·m)")
            ax2.set_ylabel("N (kN)")
            ax2.set_title(f"N–Mα (α = {full['alpha_deg']:.1f}°)",
                          fontsize=11)
            ax2.grid(True, color="#E5E7EB", lw=0.6, linestyle="--")
            ax2.legend(fontsize=8)
            try:
                fig2.tight_layout()
            except Exception:
                pass
            cv2.draw()
        # ===== Ô dưới-phải: vị trí dành cho biểu đồ thứ hai =====
        f_br = tk.Frame(self._sum_inner, bg="white",
                        highlightbackground="#D1D5DB",
                        highlightcolor="#D1D5DB", highlightthickness=1,
                        takefocus=0)
        f_br.grid(row=2, column=1, sticky="nsew", padx=4, pady=4)
        hdr2 = tk.Frame(f_br, bg="white")
        hdr2.pack(fill=tk.X, padx=4, pady=(2, 2))
        tk.Label(hdr2, text="● Mặt cắt M2–M3",
                 font=("", 10, "bold"), bg="white").pack(side=tk.LEFT)
        tk.Label(
            f_br, bg="white", fg="#6B7280", justify=tk.CENTER,
            wraplength=420,
            text="Chưa dùng cho vách ở lát 1 — vị trí dành cho biểu "
                 "đồ thứ hai theo lưới của cột.").pack(
                     fill=tk.BOTH, expand=True, padx=10, pady=10)
        # ===== Ghi chú phạm vi (full-width) =====
        tk.Label(
            self._sum_inner, foreground="gray", wraplength=1150,
            justify=tk.LEFT,
            text="Phạm vi lát 1: chỉ kiểm tra N–M (đã kể uốn dọc cả 2 "
                 "phương: ngoài mặt phẳng theo tw; trong mặt phẳng "
                 "kèm sàn lệch tâm ea = Lw/30). Vùng biên (lát 3), "
                 "cắt trong mặt "
                 "phẳng + trượt mạch ngừng (lát 4) và cấu tạo (lát 3) "
                 "CHƯA kiểm — kết luận trên chỉ cho N–M."
            ).grid(row=3, column=0, columnspan=2, sticky="ew",
                   padx=4, pady=(2, 6))
        self._finish_wall_sum_layout()

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
            ("V2", "Lực cắt trong mặt phẳng (chưa kiểm — lát 4)",
             f"{full['V_in']:.1f} kN"),
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
        for i, (s, d, v) in enumerate(rows):
            tree.insert("", tk.END, values=(s, d, v),
                        tags=("odd",) if i % 2 else ())
        tree.insert("", tk.END,
                    values=("D/C", "Tỷ số sử dụng khả năng chịu lực (N–M)",
                            f"{full['dc']:.3f} (FS = {fs_txt})  "
                            + ("ĐẠT" if full["ok"] else "KHÔNG ĐẠT")),
                    tags=("dc",))
        tree.pack(fill=tk.X, padx=2)

    def _render_wall_detail(self, full):
        """Tab Chi tiết (lát 1): thuyết minh dạng text từ dict kết quả."""
        for w in self._calc_inner.winfo_children():
            w.destroy()
        t = tk.Text(self._calc_inner, wrap="word", font=("Consolas", 10),
                    height=42)
        t.pack(fill=tk.BOTH, expand=True)
        lines = ["THUYẾT MINH KIỂM TRA VÁCH — TCVN 5574:2018 (lát 1)",
                 f"N = {full['N']:+.1f} kN, M3 (trong MP) = "
                 f"{full['M_in']:.1f} kN·m, M2 (ngoài MP) = "
                 f"{full['M_out']:.1f} kN·m, "
                 f"V2 = {full['V_in']:.1f} kN, V3 = {full['V_out']:.1f} kN",
                 ""]
        lines += full["details"]
        lines += ["", "Chưa kiểm ở lát 1: vùng biên (lát 3), cắt trong "
                      "mặt phẳng + trượt mạch ngừng (lát 4), cấu tạo "
                      "(lát 3). PDF vách thuộc lát 6."]
        t.insert(tk.END, "\n".join(lines))
        t.configure(state="disabled")
        self._calc_inner.update_idletasks()
        self._calc_canvas.configure(
            scrollregion=self._calc_canvas.bbox("all"))
        self._bind_wheel(self._calc_inner, self._calc_canvas)
