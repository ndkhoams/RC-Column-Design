"""Hồi quy: _refresh_layout không được hủy trạng thái maximized (zoomed).

Lỗi user báo ở bản 65d8b06: "bấm CHECK cửa sổ tự co lại". Điều tra cho thấy
đường CHECK không hề gọi lệnh wm nào (đã instrument toàn bộ tk.Wm trong lúc
CHECK: 0 lệnh); thủ phạm duy nhất là trò "nudge 1px" trong
App._refresh_layout — trên Windows, gọi geometry() khi cửa sổ đang zoomed sẽ
hủy maximized. Các after() này có thể bị dồn tới sau một lần CHECK block UI
thread (user bấm CHECK ngay sau khi mở app) nên cú co rơi đúng vào lúc CHECK.
Fix: đọc và trả lại đúng state zoomed sau khi nudge xong.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

try:
    import tkinter as tk
    _r = tk.Tk()
    _r.withdraw()
    _r.destroy()
    _HAS_DISPLAY = True
except Exception:
    _HAS_DISPLAY = False

pytestmark = pytest.mark.skipif(
    not _HAS_DISPLAY, reason="không có display Tk")

from gui.app import App


def _mkapp():
    app = App()
    app.update_idletasks()
    return app


def test_refresh_layout_restores_zoomed_state():
    """Giả lập cửa sổ đang maximized: _refresh_layout() phải gọi lại
    state('zoomed') sau khi nudge geometry xong."""
    app = _mkapp()
    try:
        calls = []
        orig_state = tk.Wm.state

        def fake_state(self, newstate=None):
            calls.append(newstate)
            if newstate is None:
                return "zoomed"  # giả lập máy user: đang maximized
            return orig_state(self, newstate)

        tk.Wm.state = fake_state
        try:
            app._refresh_layout()
            app.update_idletasks()
        finally:
            tk.Wm.state = orig_state
        # phải có đúng 1 lần setter state("zoomed") để trả lại maximized
        assert calls.count("zoomed") == 1, \
            f"_refresh_layout không trả lại zoomed, calls={calls}"
    finally:
        app.destroy()


def test_refresh_layout_no_zoomed_no_restore():
    """Khi cửa sổ không zoomed: không được tự ý zoom lên."""
    app = _mkapp()
    try:
        calls = []
        orig_state = tk.Wm.state

        def fake_state(self, newstate=None):
            calls.append(newstate)
            if newstate is None:
                return "normal"
            return orig_state(self, newstate)

        tk.Wm.state = fake_state
        try:
            app._refresh_layout()
            app.update_idletasks()
        finally:
            tk.Wm.state = orig_state
        assert "zoomed" not in calls, \
            f"tự ý zoom cửa sổ đang normal, calls={calls}"
    finally:
        app.destroy()
