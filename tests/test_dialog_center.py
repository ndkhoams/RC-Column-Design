"""Căn giữa popup: gui/dialog_center.center_dialog.

Chạy được cả khi không có màn hình (tự skip) và dưới Xvfb
(kiểm tra thật: tâm dialog trùng tâm màn hình, dialog lớn hơn
màn hình thì kẹp về (0, 0), kích thước không đổi).
"""
import pytest

try:
    import tkinter as tk
    _root = tk.Tk()
    _root.withdraw()
    _HAS_DISPLAY = True
except Exception:
    tk = None
    _root = None
    _HAS_DISPLAY = False

pytestmark = pytest.mark.skipif(
    not _HAS_DISPLAY, reason="không có màn hình (Tk không khởi tạo được)")


def _center_of(win):
    win.update_idletasks()
    return (win.winfo_x() + win.winfo_width() // 2,
            win.winfo_y() + win.winfo_height() // 2)


def test_center_dialog_matches_screen_center():
    from gui.dialog_center import center_dialog
    win = tk.Toplevel(_root)
    try:
        win.geometry("400x300+0+0")
        tk.Label(win, text="x" * 20).pack()
        got = center_dialog(win)
        assert got is not None
        x, y, w, h = got
        assert (w, h) == (400, 300)
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        assert x == (sw - w) // 2 and y == (sh - h) // 2
        cx, cy = _center_of(win)
        assert abs(cx - sw // 2) <= 2 and abs(cy - sh // 2) <= 2
    finally:
        win.destroy()


def test_center_dialog_uses_real_size_not_requested_only():
    from gui.dialog_center import center_dialog
    win = tk.Toplevel(_root)
    try:
        # Không đặt geometry trước: kích thước lấy từ nội dung đã pack.
        tk.Label(win, text="hello dialog").pack(padx=20, pady=20)
        got = center_dialog(win)
        assert got is not None
        x, y, w, h = got
        assert w > 1 and h > 1
        cx, cy = _center_of(win)
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        assert abs(cx - sw // 2) <= 2 and abs(cy - sh // 2) <= 2
    finally:
        win.destroy()


def test_center_dialog_clamps_oversize_to_origin():
    from gui.dialog_center import center_dialog
    win = tk.Toplevel(_root)
    try:
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{sw + 500}x{sh + 500}+0+0")
        got = center_dialog(win)
        assert got is not None
        assert got[0] == 0 and got[1] == 0
    finally:
        win.destroy()
