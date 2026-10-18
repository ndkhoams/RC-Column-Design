"""Unified result tab renderer cho cả 3 tiêu chuẩn.

Nguyên tắc: Layout 2x2 GIỐNG HỆT nhau cho TCVN/ACI/EC2.
Mỗi tiêu chuẩn chỉ cung cấp DATA, không tự vẽ layout.
"""

import tkinter as tk
from tkinter import ttk

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MPL = True
except Exception:
    HAS_MPL = False


def render_result_tab(app, config):
    """Render tab Kết quả tính toán với layout thống nhất.

    config: dict với các khóa:
      - std_title: str, vd "(ACI 318-19)"
      - param_rows: list of (sym, desc, val) hoặc (sym, desc, val, tags)
      - dc_row: (sym, desc, val, ok) cho dòng D/C cuối
      - section: Section object để vẽ
      - section_cards: dict {n, as, ab, mu} hoặc None để tự tính
      - draw_nm: fn(ax) vẽ biểu đồ N-Mα
      - draw_m2m3: fn(ax) vẽ biểu đồ M2-M3
      - nm_title: str, vd "Biểu đồ tương tác N-Mα"
      - nm_alpha_text: str, vd "α = -176.9°"
      - m2m3_title: str, vd "Mặt cắt M2-M3"
      - m2m3_n_text: str, vd "N = +943.4 kN"
      - notes_nm: list of (text, color) cho ghi chú dưới N-M
      - shear_config: dict cho bảng cắt hoặc None
      - on_nm_angle_change: fn(angle) khi đổi góc xem (hoặc None)
    """
    if not HAS_MPL:
        return

    # Xóa toàn bộ nội dung cũ trong _sum_inner (y hệt TCVN gốc)
    for w in app._sum_inner.winfo_children():
        w.destroy()

    def _new_fig(parent, figsize):
        fig = Figure(figsize=figsize, dpi=100)
        cv = FigureCanvasTkAgg(fig, master=parent)
        _w = cv.get_tk_widget()
        try:
            _w.configure(highlightthickness=0, takefocus=0,
                         highlightbackground="white", highlightcolor="white",
                         borderwidth=0)
        except Exception:
            pass
        _w.pack(fill=tk.BOTH, expand=True)
        return fig, cv

    # Grid 2x2 trong _sum_inner
    app._sum_inner.columnconfigure(0, weight=1)
    app._sum_inner.columnconfigure(1, weight=1)
    app._sum_inner.rowconfigure(0, weight=0)
    app._sum_inner.rowconfigure(1, weight=1)

    # ===== Ô trên-phải: sơ đồ mặt cắt + thẻ thống kê =====
    f_tl = tk.Frame(app._sum_inner, bg="white", highlightbackground="#D1D5DB",
                    highlightthickness=1)
    f_tl.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
    tk.Label(f_tl, text="SƠ ĐỒ MẶT CẮT TIẾT DIỆN CỘT",
             font=("", 11, "bold"), bg="white").pack(pady=(2, 2))
    fig_sec, cv_sec = _new_fig(f_tl, (3.9, 3.1))
    a1 = fig_sec.add_subplot(111)
    from rc_column.pdf_export import draw_section_ax
    draw_section_ax(a1, config["section"], show_stats=False, dot_scale=1.5)
    fig_sec.tight_layout()
    cv_sec.draw()

    # Thẻ thống kê (4 cards)
    cards = config.get("section_cards")
    if cards:
        prow = tk.Frame(f_tl, bg="#F9FAFB")
        prow.pack(fill=tk.X, padx=2, pady=(2, 4))
        for title, vkey in [("Số thanh", "n"), ("Tổng As", "as"),
                            ("Diện tích Ab", "ab"), ("Hàm lượng μ", "mu")]:
            cell = tk.Frame(prow, bg="white", highlightbackground="#E5E7EB",
                            highlightthickness=1, height=52)
            cell.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3, pady=2)
            cell.pack_propagate(False)
            tk.Label(cell, text=title, font=("", 8), fg="#6B7280",
                     bg="white").pack(pady=(6, 0))
            tk.Label(cell, text=cards[vkey], font=("", 11, "bold"),
                     bg="white").pack(pady=2)

    # ===== Ô trên-trái: bảng thông số =====
    f_tr = tk.Frame(app._sum_inner, bg="white", highlightbackground="#D1D5DB",
                    highlightthickness=1)
    f_tr.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
    ttk.Label(f_tr, text=f"BẢNG THÔNG SỐ TÍNH TOÁN {config['std_title']}",
              font=("", 11, "bold")).pack(pady=(2, 6))
    cols = ("sym", "desc", "val")
    tree = ttk.Treeview(f_tr, columns=cols, show="headings", height=16,
                        style="Param.Treeview")
    _pst = ttk.Style()
    _pst.configure("Param.Treeview.Heading", font=("", 9, "bold"),
                   background="#F3F4F6", foreground="#111827",
                   relief="flat", borderwidth=0)
    tree.heading("sym", text="Ký hiệu")
    tree.heading("desc", text="Thông số")
    tree.heading("val", text="Giá trị")
    tree.column("sym", width=84, anchor="center", stretch=False)
    tree.column("desc", width=200, anchor="w")
    tree.column("val", width=220, anchor="e", stretch=False)
    tree.tag_configure("odd", background="#F9FAFB")
    tree.tag_configure("dc", background="#D1FAE5", foreground="#065F46")
    tree.tag_configure("dc_fail", background="#FEE2E2", foreground="#991B1B")

    for i, row in enumerate(config["param_rows"]):
        if len(row) == 4:
            a, b, c, tags = row
        else:
            a, b, c = row
            tags = ("odd",) if i % 2 else ()
        tree.insert("", "end", values=(a, b, c), tags=tags)

    # Dòng D/C cuối
    if "dc_row" in config:
        sym, desc, val, ok = config["dc_row"]
        tree.insert("", "end", values=(sym, desc, val),
                    tags=("dc",) if ok else ("dc_fail",))

    tree.pack(fill=tk.X, expand=False, padx=2, pady=2)

    # ===== Ô dưới-trái: biểu đồ N-Mα =====
    f_bl = tk.Frame(app._sum_inner, bg="white", highlightbackground="#D1D5DB",
                    highlightthickness=1)
    f_bl.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
    hdr = ttk.Frame(f_bl)
    hdr.pack(fill=tk.X, padx=4, pady=(2, 2))
    left = ttk.Frame(hdr)
    left.pack(side=tk.LEFT)
    tk.Label(left, text=f"● {config.get('nm_title', 'Biểu đồ tương tác N-Mα')}",
             font=("", 10, "bold"), bg="white").pack(side=tk.LEFT)
    if config.get("nm_alpha_text"):
        tk.Label(left, text=f"  {config['nm_alpha_text']}  ",
                 font=("", 8, "bold"), fg="#065F46", bg="#D1FAE5").pack(side=tk.LEFT, padx=6)
    # Combobox chọn góc xem (nếu có callback)
    on_angle = config.get("on_nm_angle_change")
    if on_angle:
        right = ttk.Frame(hdr)
        right.pack(side=tk.RIGHT)
        tk.Label(right, text="Góc xem:", font=("", 8), bg="white").pack(side=tk.LEFT)
        _vals = ["α (góc tải)", "3D"] + [f"{d}°" for d in range(0, 361, 15)]
        _cb = ttk.Combobox(right, values=_vals, width=11, state="readonly", font=("", 9))
        _cb.set("α (góc tải)")
        _cb.pack(side=tk.LEFT, padx=(4, 0))
        _cb.bind("<<ComboboxSelected>>", lambda e: on_angle(_cb.get()))
        # Lưu ref để dùng sau
        app._nm_angle_cb = _cb

    fig_nm, cv_nm = _new_fig(f_bl, (5.2, 3.9))
    ax_nm = fig_nm.add_subplot(111)
    config["draw_nm"](ax_nm)
    fig_nm.tight_layout()
    cv_nm.draw()

    # (Notes sẽ đặt ở frame full-width bên dưới)

    # ===== Ô dưới-phải: biểu đồ M2-M3 =====
    f_br = tk.Frame(app._sum_inner, bg="white", highlightbackground="#D1D5DB",
                    highlightthickness=1)
    f_br.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
    hdr2 = ttk.Frame(f_br)
    hdr2.pack(fill=tk.X, padx=4, pady=(2, 2))
    left2 = ttk.Frame(hdr2)
    left2.pack(side=tk.LEFT)
    tk.Label(left2, text=f"● {config.get('m2m3_title', 'Mặt cắt M2-M3')}",
             font=("", 10, "bold"), bg="white").pack(side=tk.LEFT)
    if config.get("m2m3_n_text"):
        tk.Label(left2, text=f"  {config['m2m3_n_text']}  ",
                 font=("", 8, "bold"), fg="#1D4ED8", bg="#DBEAFE").pack(side=tk.LEFT, padx=6)

    fig_mm, cv_mm = _new_fig(f_br, (5.2, 3.9))
    ax_mm = fig_mm.add_subplot(111)
    config["draw_m2m3"](ax_mm)
    fig_mm.tight_layout()
    cv_mm.draw()

    # ===== Ghi chú A/B (full-width dưới cả 2 biểu đồ) =====
    notes = config.get("notes_nm", [])
    if notes:
        f_notes = ttk.Frame(app._sum_inner, style="Card.TLabelframe")
        f_notes.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 4))
        box = tk.Frame(f_notes, bg="white", highlightbackground="#E5E7EB", highlightthickness=1)
        box.pack(fill=tk.X, padx=4, pady=4)
        for text, color in notes:
            tk.Label(box, text=text, font=("TkFixedFont", 9), fg=color,
                     bg="white", wraplength=1200, justify=tk.LEFT).pack(anchor="w", padx=4, pady=1)
        app._sum_inner.rowconfigure(2, weight=0)

    # ===== Bảng cắt (nếu có) =====
    shear_builder = config.get("shear_builder")
    if shear_builder:
        f_sw = ttk.Frame(app._sum_inner, style="Card.TLabelframe")
        f_sw.grid(row=3, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        shear_builder(f_sw)
        app._sum_inner.rowconfigure(3, weight=0)

    # Cập nhật scroll
    app._sum_inner.update_idletasks()
    try:
        app._sum_canvas.configure(scrollregion=app._sum_canvas.bbox("all"))
    except:
        pass
