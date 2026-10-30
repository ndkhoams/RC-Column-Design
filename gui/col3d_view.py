"""View 3D cột theo đúng style ảnh mẫu "Biểu đồ 3D N–Mx–My" của vách
(quyết user 2026-10-30; style chuẩn tại
gui/wall_mixin.py::_draw_wall_3d_interaction, head b7b9c31).

Khác vách: khung cột dùng nhãn M2/M3/N (nhất quán với 2D của cột:
hoành M3, tung M2) và caption "Biểu đồ 3D N–M2–M3".

KHÔNG tính solver: nhận cap + lưới surface_grid đã dựng sẵn (khung
canonical của cột: x = M·sinθ = M2, y = M·cosθ = M3 — cùng frame mà
surface_grid/moment_capacity cả 3 chuẩn dùng) cùng điểm A/B đã tính.
"""


_GREEN = "#059669"
_ORANGE = "#F97316"
_RED = "#DC2626"
_AXC = "#4B5563"   # xám đậm: trục + nhãn, dễ đọc
_WIRE = "#9CA3AF"  # xám nhạt: wireframe mặt tương tác
_MINUS = "\u2212"  # dấu trừ U+2212 như style vách


def draw_col3d_interaction(fig, ax, cap, n_vals, m2_grid, m3_grid,
                           A=None, B=None, theta_deg=0.0,
                           caption="Biểu đồ 3D N–M2–M3", curve=None):
    """Vẽ mặt tương tác 3D cột theo style chuẩn.

    fig/ax: figure và axes 3d đã tạo (caller tự mouse_init).
    cap: BiaxialCapacity/ACICapacity/EC2Capacity (để dựng đường cong
        N–Mα bằng moment_capacity(N, θ) — cùng họ mặt 2D). Có thể
        None nếu đã truyền `curve` dựng sẵn.
    n_vals, m2_grid, m3_grid: lưới từ surface_grid (đã đóng vòng
        nếu muốn mặt kín — caller làm).
    A: (M2*, M3*, N) — điểm tải; None thì không vẽ A.
    B: (M2u, M3u, Nu) — điểm giới hạn; None thì không vẽ B/tia.
    theta_deg: góc tải α = degrees(atan2(M2*, M3*)) theo quy ước
        ETABS của cột (không hardcode đảo khung).
    curve: (cx, cy, cz) đường cong N–Mα dựng sẵn (vd từ cache
        gui/surf3d_cache) — truyền vào thì không gọi
        cap.moment_capacity lại; None thì dựng từ cap như cũ.
    """
    import math

    import numpy as np
    from matplotlib.lines import Line2D

    n_closed = m2_grid.shape[1]
    n_grid = np.tile(n_vals[:, None], (1, n_closed))

    # ---- 1. Ẩn trục/pane mặc định, vẽ 3 trục qua gốc O ----
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_zlabel("")
    try:
        for _pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
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
    ax.plot([_xe[0], _xe[1]], [0, 0], [0, 0], color=_AXC, lw=1.4)
    ax.plot([0, 0], [_ye[0], _ye[1]], [0, 0], color=_AXC, lw=1.4)
    ax.plot([0, 0], [0, 0], [_ze[0], _ze[1]], color=_AXC, lw=1.4)
    ax.set_xlim(_xe)
    ax.set_ylim(_ye)
    ax.set_zlim(_ze)
    # Nhãn 2 đầu mỗi trục (ngoài biên mặt 10%) + "O" tại gốc.
    _fs = 10
    ax.text(_xe[1], 0, 0, "+M2", color=_AXC, fontsize=_fs,
            ha="left", va="center")
    ax.text(_xe[0], 0, 0, _MINUS + "M2", color=_AXC, fontsize=_fs,
            ha="right", va="center")
    ax.text(0, _ye[1], 0, "+M3", color=_AXC, fontsize=_fs,
            ha="center", va="center")
    ax.text(0, _ye[0], 0, _MINUS + "M3", color=_AXC, fontsize=_fs,
            ha="center", va="center")
    ax.text(0, 0, _ze[1], "+N Nén", color=_AXC, fontsize=_fs,
            ha="center", va="bottom")
    ax.text(0, 0, _ze[0], _MINUS + "N Kéo", color=_AXC, fontsize=_fs,
            ha="center", va="top")
    # "O" lệch nhẹ về phía −M2 để không bị lưới wireframe che khuất
    # tại đúng điểm giao 3 trục.
    ax.text(_xe[0] * 0.035, 0, 0, "O", color=_AXC, fontsize=9,
            ha="center", va="center")

    # ---- 2. Mặt tương tác: wireframe xám nhạt mờ ----
    ax.plot_wireframe(m2_grid, m3_grid, n_grid, color=_WIRE, alpha=0.5,
                      rstride=2, cstride=3, linewidth=0.7)

    # ---- 3. Đường cong N–Mα tại góc tải (dựng từ bao 2D) ----
    # θ = atan2(M2*, M3*) — đúng quy ước ETABS của cột
    # (chart_draw.py: alpha_deg = degrees(atan2(Mx_star, My_star)),
    # với Mx_star = M2*); (x, y) = M·(sinθ, cosθ) = (M2, M3),
    # cùng frame với lưới surface_grid.
    # Nếu caller đã truyền curve dựng sẵn (cache) thì dùng luôn,
    # không gọi cap.moment_capacity lại.
    if curve is not None:
        _cx, _cy, _cz = curve
    elif cap is not None:
        _rad = math.radians(theta_deg)
        _ux, _uy = math.sin(_rad), math.cos(_rad)
        _n_lo, _n_hi = float(n_vals[0]), float(n_vals[-1])
        _cx, _cy, _cz = [], [], []
        for _i in range(64):
            _Nv = _n_hi + (_n_lo - _n_hi) * _i / 63
            _M = cap.moment_capacity(float(_Nv), theta_deg)
            _cx.append(_M * _ux)
            _cy.append(_M * _uy)
            _cz.append(float(_Nv))
    else:
        _cx = _cy = _cz = None
    if _cx is not None:
        ax.plot(_cx, _cy, _cz, color=_GREEN, lw=2.2,
                label="Đường cong N–Mα")

    # ---- 4. Điểm A (xanh lá), B (thoi cam),
    # tia đứt đỏ O–A–B kéo dài qua B ×1.18 (như 2D) ----
    if B is not None:
        ax.plot([0.0, B[0] * 1.18],
                [0.0, B[1] * 1.18],
                [0.0, B[2] * 1.18],
                color=_RED, ls="--", lw=1.5, dashes=(4, 3),
                label="Tia tải O–A–B")
        ax.scatter([B[0]], [B[1]], [B[2]], c=_ORANGE,
                   marker="D", s=70, edgecolors="white",
                   linewidths=1.2, label="Điểm giới hạn B")
    if A is not None:
        ax.scatter([A[0]], [A[1]], [A[2]], c=_GREEN,
                   s=70, edgecolors="white", linewidths=1.2,
                   label="Điểm tải A")
    if A is not None:
        ax.text(A[0], A[1], A[2], "  A", fontsize=9,
                color=_GREEN, weight="bold")
    if B is not None:
        ax.text(B[0], B[1], B[2], "  B", fontsize=9,
                color=_ORANGE, weight="bold")

    # ---- 5. Legend + caption ----
    _leg = [
        Line2D([0], [0], color=_WIRE, lw=1.4,
               label="Mặt tương tác 3D"),
        Line2D([0], [0], color=_GREEN, lw=2.2,
               label="Đường cong N–Mα"),
        Line2D([0], [0], color=_RED, lw=1.5, ls="--",
               dashes=(4, 3), label="Tia tải O–A–B"),
        Line2D([0], [0], marker="o", color="w",
               markerfacecolor=_GREEN, markersize=8,
               markeredgecolor="white", label="Điểm tải A"),
        Line2D([0], [0], marker="D", color="w",
               markerfacecolor=_ORANGE, markersize=7,
               markeredgecolor="white",
               label="Điểm giới hạn B"),
    ]
    ax.legend(handles=_leg, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.10), ncol=3,
              frameon=False)
    # Chừa chỗ dưới cho legend (2 hàng khi ncol=3) + caption
    # (khi quay lại 2D, handler đổi góc gọi lại tight_layout để
    # trả layout 2D như cũ).
    fig.subplots_adjust(left=0.02, right=0.98,
                        bottom=0.30, top=0.94)
    fig.text(0.5, 0.02, caption, ha="center",
             va="bottom", fontsize=11, fontweight="bold")
