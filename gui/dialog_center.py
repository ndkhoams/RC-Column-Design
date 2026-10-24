"""Căn giữa màn hình cho mọi popup/dialog tự viết (tk.Toplevel).

Quy tắc user chốt 2026-10-24: popup/dialog nào bất kỳ cũng phải mở
ở GIỮA MÀN HÌNH (gốc: popup "Chọn combo động đất" mở ra bị dồn
góc trên-trái). Helper dùng chung duy nhất cho mọi Toplevel tự viết:

- Gọi SAU khi dialog đã pack xong nội dung (và sau khi đã đặt
  geometry kích thước cố định nếu có, vd "520x560"), TRƯỚC
  wait_window() / trước khi trả quyền về cho caller.
- update_idletasks() trước để lấy kích thước THẬT (không phải kích
  thước yêu cầu lúc chưa vẽ), rồi đặt geometry sao cho tâm dialog
  trùng tâm màn hình chứa app (winfo_screenwidth/height).
- Chỉ đổi VỊ TRÍ mở: không đổi nội dung, kích thước nội dung hay
  hành vi khác. Dialog lớn hơn màn hình thì kẹp về (0, 0) thay vì
  tọa độ âm.
- Lỗi nào cũng nuốt im (no-op): vị trí không bao giờ được làm hỏng
  dialog.

KHÔNG áp cho:
- Tooltip (gui/build_mixin.py::_ToolTip): cửa sổ overrideredirect
  bám theo con trỏ, căn giữa sẽ phá đúng chức năng của nó.
- messagebox / filedialog hệ thống: vị trí do hệ điều hành quản
  lý, vốn đã căn giữa trên Windows; không hack bằng thủ thuật
  không chắc chắn (xem báo cáo: kiểm tra hành vi thực tế).
- Cửa sổ chính App (tk.Tk, geometry 1360x860): không phải popup.
"""

import tkinter as _tk  # noqa: F401  (giữ import để rõ đây là module Tk)


def list_height_for_rows(n_rows, pitch_px, min_rows=20):
    """Chiều cao vùng list popup để thấy ít nhất `min_rows` dòng.

    Quy tắc user chốt 2026-10-24 (popup "Chọn combo động đất"):
    vùng danh sách phải hiện được ít nhất 20 dòng mà không cần cuộn.
    - n_rows: tổng số dòng; pitch_px: nhịp 1 dòng (cao 1 dòng + pady).
    - Trả về pitch * min(min_rows, n_rows): ít dòng hơn thì hiện hết,
      không kéo giãn thừa; nhiều dòng hơn thì hiện đúng min_rows,
      phần còn lại cuộn. Nơi gọi tự kẹp thêm theo chiều cao màn hình.
    - Đầu vào không hợp lệ (<= 0) trả 0 để nơi gọi giữ nguyên.
    """
    try:
        n = int(n_rows)
        pitch = float(pitch_px)
        if n <= 0 or pitch <= 0:
            return 0
        return int(pitch * min(int(min_rows), n))
    except Exception:
        return 0


def center_dialog(win):
    """Đặt `win` (Toplevel) sao cho tâm nó trùng tâm màn hình.

    Trả về (x, y, w, h) đã đặt, hoặc None nếu không đặt được.
    """
    try:
        win.update_idletasks()
        w = win.winfo_width()
        if w <= 1:
            w = win.winfo_reqwidth()
        h = win.winfo_height()
        if h <= 1:
            h = win.winfo_reqheight()
        if w <= 1 or h <= 1:
            return None
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.update_idletasks()
        return (x, y, w, h)
    except Exception:
        return None
