"""Chẩn đoán lỗi khoảng trống layout. Chạy: python debug_layout.py"""
import tkinter as tk
import sys
sys.path.insert(0, '.')

from gui.app import App

def dump_widget(w, indent=0, max_depth=4):
    if indent > max_depth:
        return
    try:
        cls = w.winfo_class()
        x, y = w.winfo_x(), w.winfo_y()
        wd, ht = w.winfo_width(), w.winfo_height()
        req_w, req_h = w.winfo_reqwidth(), w.winfo_reqheight()
        print(f"{'  '*indent}{cls} '{w.winfo_name()}' "
              f"pos=({x},{y}) size={wd}x{ht} req={req_w}x{req_h}")
        for ch in w.winfo_children():
            dump_widget(ch, indent+1, max_depth)
    except Exception as e:
        print(f"{'  '*indent}Lỗi: {e}")

app = App()
app.update_idletasks()
app.after(1000, lambda: [
    print("="*60),
    print("CÂY WIDGET PANEL TRÁI:"),
    print("="*60),
    dump_widget(app.left, max_depth=2),
    print(),
    print("="*60),
    print(f"Canvas trái: size={app._left_canvas.winfo_width()}x{app._left_canvas.winfo_height()}"),
    print(f"bbox all: {app._left_canvas.bbox('all')}"),
    print(f"scrollregion: {app._left_canvas.cget('scrollregion')}"),
    print(f"yview: {app._left_canvas.yview()}"),
    print("="*60),
    app.destroy()
])
app.mainloop()
