"""Ảnh PNG cho PDF vách (tóm tắt + chi tiết) — vẽ từ dict kết quả
đã lưu, không tính lại D/C.

- Mặt cắt: dùng đúng builder vẽ vách hiện có
  (gui.wall_mixin.draw_wall_section_ax, kèm DIM + vùng nén) qua
  import lười (tránh vòng import rc_column -> gui lúc nạp module);
  khi không import được GUI (vd chạy headless) thì vẽ fallback Agg
  tối giản (khung + thép tròn đúng dia/2 + vùng nén + dim Lw/tw).
- N–Mα: vẽ bằng đúng hàm vẽ của cột
  (`chart_draw.draw_nm_alpha_ax`) qua adapter
  (`wall_chart_adapter.wall_chart_inputs`) — cùng hình với tab
  Kết quả, không còn code vẽ riêng cho vách, không tính lại
  kết luận. (Hàm vẽ cột không đặt title trong axes; α ghi ở
  caption ngoài hình của PDF.)
- M2–M3: dùng sẵn rc_column.wall_m2m3.wall_m2m3_figure (nay cũng
  vẽ bằng `draw_m2m3_ax` của cột qua adapter).
"""

import io
import math


def _canonical_geom(full):
    """(sec, meta, na_info, rot) ở khung canonical cho hình mặt cắt.

    Ở 90/270° tiết diện engine đã hoán đổi Lw/tw (và hình học vùng
    biên suy biến) nên dựng lại tiết diện canonical từ winp với
    rot=0 rồi xoay cứng khi vẽ — cùng cách _wall_display_geom của
    GUI làm; đường trung hòa ánh xạ (st, ct) -> (-ct, -st).
    Số liệu tính toán không đổi.
    """
    sec = full["sec"]
    meta = full.get("meta") or {}
    na_info = full.get("na_info")
    rot = int(meta.get("rot_deg", 0) or 0) % 360
    if rot not in (90, 270):
        return sec, meta, na_info, rot
    try:
        import dataclasses
        from .wall_section import build_wall_section
        winp = full["winp"]
        w0 = dataclasses.replace(winp, rot_deg=0)
        sec_w, meta_w = build_wall_section(w0, sec.concrete, sec.steel)
        na_w = na_info
        if na_info is not None and na_info.get("st") is not None \
                and na_info.get("ct") is not None:
            na_w = dict(na_info)
            na_w["st"] = -float(na_info["ct"])
            na_w["ct"] = -float(na_info["st"])
        return sec_w, meta_w, na_w, rot
    except Exception:
        return sec, meta, na_info, 0


def _apply_bar_floor(fig, ax, floor_px=6.0):
    """Floor hiển thị thép cho ẢNH TĨNH PDF — cùng nguyên tắc với
    quyết của user cho GUI (đường kính hiển thị = max(tỉ lệ thật,
    FLOOR 6.0px)), nhưng đường xuất PDF KHÔNG đi qua cơ chế
    draw_event của GUI nên phải áp tường minh tại đây: sau khi vẽ,
    mọi hình tròn thép có đường kính màn hình < 6px (tính theo dpi
    của ảnh xuất) được phóng tới đúng 6px rồi mới savefig. Ở dpi
    200, 6px = 0,76 mm trên giấy. Quy tắc GUI không đổi — chỉ ảnh
    PDF áp floor tương đương theo dpi ảnh của chính nó."""
    try:
        fig.canvas.draw()
        import matplotlib.patches as mpatches
        for p in ax.patches:
            if not isinstance(p, mpatches.Circle):
                continue
            cx_, cy_ = p.center
            x0, y0 = ax.transData.transform((cx_, cy_))
            x1, y1 = ax.transData.transform((cx_ + p.radius, cy_))
            d = 2.0 * math.hypot(x1 - x0, y1 - y0)
            if 0 < d < floor_px:
                p.radius = p.radius * floor_px / d
    except Exception:
        pass


def _fallback_section_png(sec, meta, na_info, rot_deg, width_in, dpi):
    """Vẽ mặt cắt tối giản khi không import được builder của GUI."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import Polygon as MplPolygon
    cx, cy = float(sec.cx), float(sec.cy)
    fig, ax = plt.subplots(figsize=(width_in, width_in * 0.45))
    # "box" thay "datalim": cùng lý do như draw_wall_section_ax
    # (datalim in warning "Ignoring fixed y limits..." mỗi lần
    # savefig với bbox_inches="tight" làm lệch tỉ lệ hộp).
    ax.set_aspect("equal", adjustable="box")
    ax.add_patch(MplPolygon(
        [(-cx / 2, -cy / 2), (cx / 2, -cy / 2),
         (cx / 2, cy / 2), (-cx / 2, cy / 2)],
        closed=True, fill=True, facecolor="#F4F7FB",
        edgecolor="black", lw=2.0, zorder=2))
    if na_info is not None and na_info.get("found") \
            and na_info.get("yp_na") is not None:
        st, ct, yp = na_info["st"], na_info["ct"], na_info["yp_na"]

        def _naval(x, y):
            return -x * st + y * ct - yp
        rect = [(-cx / 2, -cy / 2), (cx / 2, -cy / 2),
                (cx / 2, cy / 2), (-cx / 2, cy / 2)]
        pts = []
        for i in range(len(rect)):
            cur, prv = rect[i], rect[i - 1]
            vc, vp = _naval(*cur), _naval(*prv)
            ci, pi = vc >= -1e-9, vp >= -1e-9
            if ci != pi:
                t = abs(vp) / (abs(vp) + abs(vc))
                pts.append((prv[0] + t * (cur[0] - prv[0]),
                            prv[1] + t * (cur[1] - prv[1])))
            if ci:
                pts.append(cur)
        if len(pts) >= 3:
            ax.add_patch(MplPolygon(pts, closed=True, fill=True,
                                    facecolor="#BFDBFE",
                                    edgecolor="#2563EB", lw=1.5,
                                    zorder=3, alpha=0.7))
    for r in sec.rebars:
        ax.add_patch(mpatches.Circle(
            (r.x, r.y), r.dia / 2.0, fill=True,
            facecolor="#DC2626" if r.layer == 1 else "#F59E0B",
            edgecolor="white", linewidth=0.8, zorder=5))
    ax.set_xlim(-cx / 2 - 0.12 * cx, cx / 2 + 0.12 * cx)
    ax.set_ylim(-cy / 2 - 0.9 * cy, cy / 2 + 0.9 * cy)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title(f"Mặt cắt vách {cx:.0f} × {cy:.0f} mm", fontsize=10)
    _apply_bar_floor(fig, ax)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                pad_inches=0.05)
    plt.close(fig)
    return buf.getvalue()


def wall_section_png(full, width_in=5.5, dpi=200,
                     show_compression=True):
    """PNG mặt cắt vách có DIM + vùng nén (nếu có na_info)."""
    sec, meta, na_info, rot = _canonical_geom(full)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from gui.wall_mixin import (_wall_section_figsize,
                                    draw_wall_section_ax)
        n_seg = len((meta or {}).get("dim_segments") or [])
        fw, fh = _wall_section_figsize(sec, n_seg, rot)
        fig = plt.figure(figsize=(fw, fh))
        ax = fig.add_subplot(111)
        draw_wall_section_ax(ax, sec, meta=meta, na_info=na_info,
                             show_compression=show_compression,
                             rot_deg=rot)
        _apply_bar_floor(fig, ax)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                    pad_inches=0.05)
        plt.close(fig)
        return buf.getvalue()
    except Exception:
        return _fallback_section_png(sec, meta, na_info, rot,
                                     width_in, dpi)


def wall_nm_alpha_png(full, width_in=5.0, dpi=200):
    """PNG biểu đồ N–Mα — bằng đúng hàm vẽ của cột qua adapter
    (cùng hình với tab Kết quả sau thống nhất). Giữ nguyên tên
    và signature để caller không đổi."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .chart_draw import draw_nm_alpha_ax
    from .wall_chart_adapter import wall_chart_inputs
    sec, inp_ns, res_ns = wall_chart_inputs(full)
    fig, ax = plt.subplots(figsize=(width_in, width_in * 0.78))
    draw_nm_alpha_ax(ax, sec, inp_ns, res_ns, None)
    try:
        fig.tight_layout()
    except Exception:
        pass
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
