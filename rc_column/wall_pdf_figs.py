"""Ảnh PNG cho PDF vách (tóm tắt + chi tiết) — vẽ từ dict kết quả
đã lưu, không tính lại D/C.

- Mặt cắt: dùng đúng builder vẽ vách hiện có
  (gui.wall_mixin.draw_wall_section_ax, kèm DIM + vùng nén) qua
  import lười (tránh vòng import rc_column -> gui lúc nạp module);
  khi không import được GUI (vd chạy headless) thì vẽ fallback Agg
  tối giản (khung + thép tròn đúng dia/2 + vùng nén + dim Lw/tw).
- N–Mα: vẽ lại đúng đường cong tab Kết quả vẽ (sweep exact của
  BiaxialCapacity tại góc α, chèn mức BN) — đây là vẽ biểu đồ từ
  solver đã dựng cho D/C, không phải tính lại kết luận.
- M2–M3: dùng sẵn rc_column.wall_m2m3.wall_m2m3_figure.
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
    ax.set_aspect("equal", adjustable="datalim")
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
    """PNG biểu đồ N–Mα — đúng cách vẽ của tab Kết quả vách."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .interaction import BiaxialCapacity
    cap = BiaxialCapacity(full["sec"], model=full["model"])
    eng = cap._exact
    n_lv = 64
    levels = [eng.N_max + (eng.N_min - eng.N_max) * i / (n_lv - 1)
              for i in range(n_lv)]
    BN = float(full["BN"])
    if math.isfinite(BN) and eng.N_min < BN < eng.N_max \
            and BN not in levels:
        levels.append(BN)
        levels.sort(reverse=True)
    ns, ms = [], []
    for Nv in levels:
        ns.append(float(Nv))
        ms.append(cap.moment_capacity(float(Nv), float(full["alpha_deg"])))
    fig, ax = plt.subplots(figsize=(width_in, width_in * 0.78))
    ax.plot(ms, ns, color="#059669", lw=1.8, zorder=3)
    ax.fill_betweenx(ns, 0, ms, color="#059669", alpha=0.08, zorder=1)
    lam = float(full["lambda_ray"])
    MB = lam * float(full["Malpha"]) if math.isfinite(lam) else None
    if MB is not None:
        ax.plot([0, MB * 1.18], [0, BN * 1.18], color="#DC2626",
                ls="--", lw=1.5, dashes=(4, 3), zorder=4)
    ax.scatter([float(full["Malpha"])], [float(full["N"])],
               c="#DC2626", zorder=5, label="A (làm việc)")
    if MB is not None:
        ax.scatter([MB], [BN], c="#2563EB", zorder=5,
                   label="B (giới hạn)")
    ax.set_xlim(left=0)
    if float(full["N"]) >= 0:
        ax.set_ylim(bottom=0)
    else:
        ax.set_ylim(top=0)
    ax.set_xlabel("Mα (kN·m)")
    ax.set_ylabel("N (kN)")
    ax.set_title(f"N–Mα (α = {float(full['alpha_deg']):.1f}°)",
                 fontsize=11)
    ax.grid(True, color="#E5E7EB", lw=0.6, linestyle="--")
    ax.legend(fontsize=8)
    try:
        fig.tight_layout()
    except Exception:
        pass
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
