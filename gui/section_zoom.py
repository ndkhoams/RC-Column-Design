"""Fit legend cho ô MẶT CẮT TIẾT DIỆN của cột (KHÔNG zoom/pan).

Quyết user 2026-10-24: khung nhìn mặt cắt CỘT KHÓA về dạng tĩnh như
trước khi có zoom (trước head 375bc8f) — không wheel-zoom, không
kéo-pan, không nút −/+/Reset, không double-click reset; ô luôn hiển
thị trọn khung ở home, wheel trên ô cuộn tab như bình thường (qua
_bind_wheel). Ô mặt cắt VÁCH giữ zoom/pan riêng của nó trong
gui/wall_mixin.py (không dùng module này).

Nội dung còn lại duy nhất của module này là fit legend thép
(head a5cb3d8): legend thép nằm NGOÀI axes (bbox_to_anchor 1.02)
nên fig.tight_layout() không chừa chỗ cho nó — ở hầu hết cỡ cửa sổ
legend tràn khỏi mép phải figure và bị widget cắt mất (đo thật:
tràn 17–55px ở 1024–1600, nặng hơn ở DPI cao). Handler draw_event:
sau mỗi lần vẽ, nếu legend tràn mép phải thì thu hẹp position của
axes (từ phải) vừa đủ rồi vẽ lại (hội tụ 1 lần; các lần vẽ sau
no-op). Chỉ đổi position — limits, tỉ lệ equal aspect và số tính
không đổi. PDF không dùng handler này (compression_zone_image
savefig bbox_inches='tight' nên vốn đã đủ chỗ cho legend).
"""

_SEC_FIT_PAD_PX = 2.0


def _fit_section_legend_now(fig, ax, renderer=None):
    """Thu hẹp position của axes (từ phải) vừa đủ để legend thép nằm
    trong figure. Chỉ đổi position, không đổi limits/aspect. Trả True
    nếu đã đổi (nơi gọi vẽ lại); False nếu đã vừa hoặc không đo được.
    """
    try:
        leg = ax.get_legend()
        if leg is None:
            return False
        fw = fig.bbox.width
        if not fw or fw <= 0:
            return False
        try:
            lb = leg.get_window_extent(renderer=renderer)
        except TypeError:
            lb = leg.get_window_extent()
        if lb.width <= 0 or lb.height <= 0:
            return False
        over = lb.x1 - fw
        if over <= 0.5:
            return False
        pos = ax.get_position()
        new_w = pos.width - (over + _SEC_FIT_PAD_PX) / fw
        if new_w < 0.05:
            return False
        ax.set_position([pos.x0, pos.y0, new_w, pos.height])
        return True
    except Exception:
        return False


def attach_section_legend_fit(canvas, ax):
    """Gắn handler draw_event cho ô mặt cắt cột: sau mỗi lần vẽ, nếu
    legend thép tràn mép phải figure thì fit lại rồi vẽ lại bằng
    draw_idle (bất đồng bộ nên không đệ quy; lần vẽ sau no-op).
    Handler sống theo canvas/figure nên tự áp cho mọi lần vẽ lại sau
    đó (preview, checkbox vùng nén, resize) mà không cần gọi lại.
    Gắn độc lập — không kèm zoom/pan (khung nhìn cột đã khóa).
    """
    fig = ax.figure

    def _on_draw(event):
        try:
            if _fit_section_legend_now(
                    fig, ax, renderer=getattr(event, "renderer", None)):
                canvas.draw_idle()
        except Exception:
            pass

    try:
        canvas.mpl_connect("draw_event", _on_draw)
    except Exception:
        pass
