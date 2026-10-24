"""Zoom/pan dùng chung cho ô MẶT CẮT TIẾT DIỆN của cột.

Quy ước GIỐNG HỆT ô vách (gui/wall_mixin.py::_sec_zoom_*):
- Cuộn chuột = zoom tại con trỏ (0.8 vào / 1.25 ra, kẹp span 2%-600%
  span home mỗi phương).
- Giữ chuột trái kéo = pan (nắm hình kéo, con trỏ fleur).
- Double-click = về home; nút −/+/Reset tương ứng.
- Trả "break" để cuộn trên canvas mặt cắt không cuộn cả tab.

Cách dùng: nơi gọi tạo TRƯỚC một dict state rỗng (để nút −/+/Reset
đóng lên nó), rồi gọi attach_section_zoom(canvas, ax, state) SAU
_bind_wheel — bind thường sẽ ghi đè binding cuộn tab trên chính
widget canvas, nên gắn trước _bind_wheel sẽ bị ghi đè lại (ô vách
dùng after_idle cũng vì lý do này).

Zoom áp cùng một hệ số cho cả 2 phương nên với axes equal aspect
(adjustable='box' của cột) khung axes không bị co khi zoom/pan.
Vẽ lại (CHECK/làm mới/live preview) clear + vẽ lại axes nên view tự
về home; state dict vẫn trỏ đúng axes cũ nên nút/binding còn hiệu
lực mà không cần gắn lại.
"""


def _apply_limits(ax, canvas, home, factor, center):
    """Thu/phóng lims quanh center, kẹp span theo home (như ô vách)."""
    (hx0, hx1), (hy0, hy1) = home

    def _new(v0, v1, c, hspan):
        span = (v1 - v0) * factor
        span = min(max(span, hspan * 0.02), hspan * 6.0)
        f2 = span / (v1 - v0) if v1 != v0 else factor
        return c - (c - v0) * f2, c + (v1 - c) * f2

    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    ax.set_xlim(_new(x0, x1, center[0], hx1 - hx0))
    ax.set_ylim(_new(y0, y1, center[1], hy1 - hy0))
    canvas.draw_idle()


def zoom_step(state, factor):
    """Zoom 1 nấc quanh tâm khung hiện tại (nút −: 1.25, nút +: 0.8)."""
    if not state or "ax" not in state:
        return
    try:
        ax = state["ax"]
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        _apply_limits(ax, state["canvas"], state["home"], factor,
                      ((x0 + x1) / 2.0, (y0 + y1) / 2.0))
    except Exception:
        pass


def zoom_reset(state):
    """Về khung home (nút Reset / double-click)."""
    if not state or "ax" not in state:
        return
    try:
        (x0, x1), (y0, y1) = state["home"]
        state["ax"].set_xlim(x0, x1)
        state["ax"].set_ylim(y0, y1)
        state["canvas"].draw_idle()
    except Exception:
        pass
    return "break"


def attach_section_zoom(canvas, ax, state):
    """Gắn zoom/pan lên widget canvas của ô mặt cắt.

    state: dict do nơi gọi tạo trước; hàm điền canvas/ax/home/drag/
    widget vào đó. Home = lims hiện tại của axes lúc gắn (sau khi vẽ).
    """
    state.update({"canvas": canvas, "ax": ax,
                  "home": (ax.get_xlim(), ax.get_ylim()), "drag": None})
    w = canvas.get_tk_widget()
    state["widget"] = w

    def _data_at(event, lims=None):
        (x0, x1), (y0, y1) = lims or (ax.get_xlim(), ax.get_ylim())
        try:
            _fw, fh = canvas.get_width_height()
            dx, dy = ax.transData.inverted().transform(
                (float(event.x), fh - float(event.y)))
            return (float(dx), float(dy))
        except Exception:
            return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)

    def _wheel(event):
        try:
            d = getattr(event, "delta", 0) or 0
            _apply_limits(ax, canvas, state["home"],
                          0.8 if d > 0 else 1.25, _data_at(event))
        except Exception:
            pass
        return "break"

    def _wheel_btn(event, sgn):
        try:
            _apply_limits(ax, canvas, state["home"],
                          0.8 if sgn < 0 else 1.25, _data_at(event))
        except Exception:
            pass
        return "break"

    def _press(event):
        try:
            lims = (ax.get_xlim(), ax.get_ylim())
            state["drag"] = {"lims": lims, "data": _data_at(event, lims)}
            w.configure(cursor="fleur")
        except Exception:
            state["drag"] = None
        return "break"

    def _motion(event):
        dr = state.get("drag")
        if dr:
            try:
                d1 = _data_at(event, dr["lims"])
                (x0, x1), (y0, y1) = dr["lims"]
                sx = dr["data"][0] - d1[0]
                sy = dr["data"][1] - d1[1]
                ax.set_xlim(x0 + sx, x1 + sx)
                ax.set_ylim(y0 + sy, y1 + sy)
                canvas.draw_idle()
            except Exception:
                pass
        return "break"

    def _release(event):
        state["drag"] = None
        try:
            w.configure(cursor="")
        except Exception:
            pass
        return "break"

    w.bind("<MouseWheel>", _wheel)
    w.bind("<Button-4>", lambda e: _wheel_btn(e, -1))
    w.bind("<Button-5>", lambda e: _wheel_btn(e, 1))
    w.bind("<ButtonPress-1>", _press)
    w.bind("<B1-Motion>", _motion)
    w.bind("<ButtonRelease-1>", _release)
    w.bind("<Double-Button-1>", lambda e: zoom_reset(state))
    return state
