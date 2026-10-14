"""Giao diện kiểm tra cột BTCT theo mẫu VietconSoft.

Bố cục:
 1. Vật liệu | 2. Tiết diện | 3. Bố trí cốt thép dọc | 4. Chiều dài tính toán
 5. Nội lực kiểm tra
Kết quả: trạng thái ĐẠT/KHÔNG ĐẠT, sơ đồ tiết diện, biểu đồ tương tác,
         thuyết minh tính toán chi tiết.
"""

import math
import tkinter as tk
from tkinter import ttk, messagebox

from rc_column.checker import ColumnInput, build_section, check_column
from rc_column.materials import CONCRETE_GRADES, STEEL_GRADES
from rc_column.report import generate_report, generate_report_sections
from rc_column.sections import clear_spacing
from rc_column.stability import BOUNDARY_NAMES, LongTermLoads

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import matplotlib.patches as mpatches
    HAS_MPL = True
except Exception:
    HAS_MPL = False


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Kiểm tra cột bê tông cốt thép — TCVN 5574:2018")
        self.geometry("1360x860")
        # Icon title bar
        try:
            import os, sys
            _base = getattr(sys, "_MEIPASS", os.path.dirname(
                os.path.abspath(__file__)) + "/..")
            _ico = os.path.join(_base, "icon.ico")
            if os.path.exists(_ico):
                self.iconbitmap(_ico)
            else:
                _png = os.path.join(_base, "icon.png")
                if os.path.exists(_png):
                    _img = tk.PhotoImage(file=_png)
                    self.iconphoto(True, _img)
                    self._icon_img = _img
        except Exception:
            pass
        # Mở mặc định full màn hình
        try:
            self.state("zoomed")
        except Exception:
            pass
        self._setup_styles()
        self._build()
        self.after(100, self._fix_left_width)

    def _fix_left_width(self):
        try:
            self.update_idletasks()
            self._paned.sashpos(0, self._left_width)
            # Vô hiệu hóa sash: không cho kéo
            self._paned.bind("<B1-Motion>", lambda e: "break", add="+")
            self._paned.bind("<ButtonPress-1>", lambda e: "break", add="+")
        except Exception:
            pass

    def _setup_styles(self):
        """Style giống web VietconSoft: thanh thoát, gọn gàng."""
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except Exception:
            pass
        GREEN = "#059669"
        GREEN_DARK = "#047857"
        BORDER = "#E5E7EB"
        BG = "#F9FAFB"
        TEXT = "#111827"
        MUTED = "#6B7280"
        # Nền chung
        st.configure(".", background=BG, font=("", 10))
        st.configure("TFrame", background="white")
        st.configure("TLabel", background="white", foreground=TEXT, font=("", 10))
        # Label mô tả: màu chữ bình thường, nền trắng (không in mờ)
        st.configure("Muted.TLabel", foreground=TEXT, font=("", 9),
                     background="white")
        # Tiêu đề mục: số xanh lá + chữ đậm
        st.configure("Section.TLabel", foreground=TEXT,
                     font=("", 11, "bold"))
        # Card trắng
        st.configure("Card.TLabelframe", background="white",
                     bordercolor=BORDER, relief="solid", borderwidth=1)
        st.configure("Card.TLabelframe.Label", background="white",
                     foreground=TEXT, font=("", 11, "bold"))
        # Input hiện đại: cao ráo, viền nhạt bo nhẹ
        for w in ("TEntry", "TCombobox", "TSpinbox"):
            st.configure(w, fieldbackground="white", bordercolor=BORDER,
                         lightcolor=BORDER, darkcolor=BORDER,
                         borderwidth=1, padding=(8, 6))
            st.map(w, bordercolor=[("focus", GREEN)],
                   fieldbackground=[("readonly", "white")])
        # Nút chính xanh lá
        st.configure("Accent.TButton", background=GREEN, foreground="white",
                     font=("", 11, "bold"), padding=(12, 10),
                     borderwidth=0)
        st.map("Accent.TButton",
               background=[("active", GREEN_DARK), ("pressed", "#065F46")])
        # Nút phụ viền xám
        st.configure("Ghost.TButton", background="white", foreground=TEXT,
                     font=("", 12), padding=(12, 8), borderwidth=1,
                     relief="solid", bordercolor=BORDER)
        # Treeview bảng thông số
        st.configure("Treeview", background="white",
                     fieldbackground="white", foreground=TEXT,
                     font=("", 10), rowheight=28, borderwidth=1,
                     relief="solid")
        st.configure("Treeview.Heading", background="#F3F4F6",
                     foreground=MUTED, font=("", 10, "bold"),
                     padding=6)
        st.map("Treeview",
               background=[("selected", "#D1FAE5")],
               foreground=[("selected", TEXT)])

    # ============================ UI ============================
    def _build(self):
        self._paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main = self._paned
        main.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        # Panel trái rộng 700px để hiện đủ bảng nội lực
        self._left_width = 700

        # ---- Trái: nhập liệu (cuộn được) ----
        left_outer = ttk.Frame(main)
        main.add(left_outer, weight=0)
        # Vùng cuộn
        scroll_area = ttk.Frame(left_outer)
        scroll_area.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(scroll_area, highlightthickness=0)
        self._left_canvas = canvas
        scr = ttk.Scrollbar(scroll_area, orient=tk.VERTICAL,
                            command=canvas.yview)
        self.left = ttk.Frame(canvas)
        self.left.bind("<Configure>",
                       lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.left, anchor=tk.NW)
        canvas.configure(yscrollcommand=scr.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scr.pack(side=tk.RIGHT, fill=tk.Y)

        self._sec_materials()
        self._sec_section()
        self._sec_rebar()
        self._sec_stability()
        self._sec_loads()
        # Cuộn chuột cho vùng nhập liệu
        self._bind_wheel(self.left, self._left_canvas)

        # Cụm nút cố định đáy (không bị cuộn theo)
        bottom_bar = ttk.Frame(left_outer, relief=tk.RAISED, borderwidth=1)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=2, pady=2)
        data_bar = ttk.Frame(bottom_bar)
        data_bar.pack(fill=tk.X, padx=8, pady=(8, 0))
        ttk.Button(data_bar, text="💾 SAVE", style="Ghost.TButton",
                   command=self.on_save_data).pack(side=tk.LEFT, expand=True,
                                                   fill=tk.X, padx=(0, 4))
        ttk.Button(data_bar, text="💾 SAVE AS", style="Ghost.TButton",
                   command=self.on_save_as_data).pack(side=tk.LEFT,
                                                      expand=True, fill=tk.X,
                                                      padx=(2, 2))
        ttk.Button(data_bar, text="📂 OPEN", style="Ghost.TButton",
                   command=self.on_load_data).pack(side=tk.LEFT, expand=True,
                                                   fill=tk.X, padx=(4, 0))
        ttk.Button(data_bar, text="📄 XUẤT PDF", style="Ghost.TButton",
                   command=self._export_pdf).pack(side=tk.LEFT, expand=True,
                                                   fill=tk.X, padx=(4, 0))
        ttk.Button(bottom_bar, text="✓  KIỂM TRA KHẢ NĂNG CHỊU LỰC",
                   style="Accent.TButton",
                   command=self.on_check).pack(fill=tk.X, padx=10, pady=10)
        # Cuộn chuột trên cụm nút cố định -> cuộn vùng nhập liệu
        self._bind_wheel(bottom_bar, self._left_canvas)

        # ---- Phải: kết quả ----
        right = ttk.Frame(main)
        main.add(right, weight=1)
        self.result_var = tk.StringVar(value="Chưa có kết quả")
        hdr = ttk.Frame(right)
        hdr.pack(fill=tk.X, padx=4, pady=4)
        ttk.Label(hdr, textvariable=self.result_var,
                  font=("", 12, "bold")).pack(side=tk.LEFT, expand=True)


        nb = ttk.Notebook(right)
        nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.nb = nb
        self.tab_sum = ttk.Frame(nb); nb.add(self.tab_sum, text="Kết quả tính toán")
        self.tab_calc = ttk.Frame(nb); nb.add(self.tab_calc, text="Chi tiết tính toán")

        # Tab Tóm tắt bọc trong canvas cuộn được
        sum_canvas = tk.Canvas(self.tab_sum, highlightthickness=0)
        sum_scr = ttk.Scrollbar(self.tab_sum, orient=tk.VERTICAL,
                                command=sum_canvas.yview)
        self._sum_inner = ttk.Frame(sum_canvas)
        self._sum_inner.bind(
            "<Configure>",
            lambda e: sum_canvas.configure(
                scrollregion=sum_canvas.bbox("all")))
        sum_canvas.create_window((0, 0), window=self._sum_inner,
                                 anchor=tk.NW)
        sum_canvas.configure(yscrollcommand=sum_scr.set)
        sum_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sum_scr.pack(side=tk.RIGHT, fill=tk.Y)
        self._sum_canvas = sum_canvas
        # co giãn theo chiều rộng tab
        def _sum_width(e):
            sum_canvas.itemconfig(1, width=e.width)
        sum_canvas.bind("<Configure>", _sum_width)

        # cuộn chuột cho tab Tóm tắt (đệ quy, trừ combobox đang mở)
        self._bind_wheel(self._sum_inner, self._sum_canvas)
        # lưu để vẽ lại khi đổi loại
        self._last_sec = None
        self._last_inp = None
        self._last_res = None

        # Biến kèm bảng tổng hợp (mặc định tắt; logic PDF còn dùng)
        self.var_export_table = tk.BooleanVar(value=False)
        # Khung cuộn cho thuyết minh kiểu Vietcon (widget)
        calc_frame = ttk.Frame(self.tab_calc)
        calc_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._calc_canvas = tk.Canvas(calc_frame, bg="white",
                                      highlightthickness=0)
        calc_scroll = ttk.Scrollbar(calc_frame, orient=tk.VERTICAL,
                                    command=self._calc_canvas.yview)
        self._calc_inner = tk.Frame(self._calc_canvas, bg="white")
        self._calc_inner.bind("<Configure>",
            lambda e: self._calc_canvas.configure(
                scrollregion=self._calc_canvas.bbox("all")))
        self._calc_canvas.create_window((0, 0), window=self._calc_inner,
                                        anchor=tk.NW)
        self._calc_canvas.configure(yscrollcommand=calc_scroll.set)
        self._calc_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        calc_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        def _calc_width(e):
            self._calc_canvas.itemconfig(1, width=e.width)
        self._calc_canvas.bind("<Configure>", _calc_width)
        tk.Label(self._calc_inner, text="Chi tiết tính toán sẽ hiển thị sau "
                 "khi thực hiện kiểm tra.", bg="white",
                 font=("", 10)).pack(pady=20)
        # Cuộn chuột cho thuyết minh
        self._bind_wheel(self._calc_inner, self._calc_canvas)

    def _bind_wheel(self, root_widget, canvas):
        """Gắn cuộn chuột đệ quy cho root_widget và mọi con cháu,
        cuộn canvas chỉ định. Bỏ qua Treeview (giữ cuộn riêng)."""
        def _rec(w):
            if w is getattr(self, "etabs_tree", None):
                return
            w.bind("<MouseWheel>",
                   lambda e, c=canvas: self._scroll_canvas(e, c))
            w.bind("<Button-4>",
                   lambda e, c=canvas: self._scroll_canvas(e, c))
            w.bind("<Button-5>",
                   lambda e, c=canvas: self._scroll_canvas(e, c))
            for ch in w.winfo_children():
                _rec(ch)
        _rec(root_widget)

    def _scroll_canvas(self, event, canvas):
        """Cuộn canvas 3 units/nấc."""
        if getattr(event, "num", None) == 4:
            canvas.yview_scroll(-3, "units")
        elif getattr(event, "num", None) == 5:
            canvas.yview_scroll(3, "units")
        else:
            delta = int(-event.delta / 120) if event.delta else 0
            canvas.yview_scroll(delta * 3, "units")
        return "break"

    def _on_wheel_global(self, event):
        """(Giữ để tương thích — đã chuyển sang _bind_wheel.)"""
        return None

    def _wheel_on(self):
        """(Giữ để tương thích — không còn dùng.)"""
        pass

    def _wheel_off(self):
        """(Giữ để tương thích — không còn dùng.)"""
        pass

    def _on_wheel(self, event):
        """(Giữ để tương thích — không còn dùng.)"""
        return None

    def _frame(self, title):
        # Title dạng "1. Vật liệu" -> số xanh lá
        f = ttk.LabelFrame(self.left, text=title, padding=(12, 10),
                           style="Card.TLabelframe")
        f.pack(fill=tk.X, padx=10, pady=8)
        return f

    def _row(self, parent, label, widget, r, c0=0):
        # Label xám nhỏ, widget thoáng
        ttk.Label(parent, text=label, style="Muted.TLabel").grid(
            row=r, column=c0, sticky=tk.W, padx=(4, 8), pady=5)
        widget.grid(row=r, column=c0 + 1, sticky=tk.EW, padx=4, pady=5)
        parent.columnconfigure(c0 + 1, weight=1)

    # ---- 1. Vật liệu ----
    def _sec_materials(self):
        f = self._frame("1. Vật liệu")
        fl = ttk.Frame(f); fl.grid(row=0, column=0, sticky=tk.NSEW, padx=2)
        fr = ttk.Frame(f); fr.grid(row=0, column=1, sticky=tk.NSEW, padx=2)
        f.columnconfigure(0, weight=1); f.columnconfigure(1, weight=1)
        self.cb_conc = ttk.Combobox(fl, values=list(CONCRETE_GRADES),
                                    state="readonly", width=12)
        self.cb_conc.set("B25")
        self._row(fl, "Cấp độ bền bê tông", self.cb_conc, 0)
        self.en_gb = ttk.Entry(fl, width=12); self.en_gb.insert(0, "0.85")
        self._row(fl, "Hệ số γb", self.en_gb, 1)
        self.en_gs = ttk.Entry(fl, width=12); self.en_gs.insert(0, "1.0")
        self._row(fl, "Hệ số γs", self.en_gs, 2)
        self.cb_steel = ttk.Combobox(fr, values=list(STEEL_GRADES),
                                     state="readonly", width=12)
        self.cb_steel.set("CB400-V")
        self._row(fr, "Cấp độ bền thép dọc", self.cb_steel, 0)
        self.cb_sw_steel = ttk.Combobox(fr, values=list(STEEL_GRADES),
                                        state="readonly", width=12)
        self.cb_sw_steel.set("CB400-V")
        self._row(fr, "Cấp độ bền thép đai", self.cb_sw_steel, 1)
        self.cb_model = ttk.Combobox(
            fr, values=["3 đoạn thẳng (MH3ĐT)", "2 đoạn thẳng (MH2ĐT)"],
            state="readonly", width=12)
        self.cb_model.set("3 đoạn thẳng (MH3ĐT)")
        self._row(fr, "Mô hình bê tông", self.cb_model, 2)

    # ---- 2. Tiết diện ----
    def _sec_section(self):
        f = self._frame("2. Tiết diện")
        fl = ttk.Frame(f); fl.grid(row=0, column=0, sticky=tk.NSEW, padx=2)
        fr = ttk.Frame(f); fr.grid(row=0, column=1, sticky=tk.NSEW, padx=2)
        f.columnconfigure(0, weight=1); f.columnconfigure(1, weight=1)
        self.cb_kind = ttk.Combobox(fl, values=["Chữ nhật", "Tròn"],
                                    state="readonly", width=12)
        self.cb_kind.set("Chữ nhật")
        self.cb_kind.bind("<<ComboboxSelected>>",
                          lambda e: self._refresh_rebar_panel())
        self._row(fl, "Loại tiết diện", self.cb_kind, 0)
        self.en_cx = ttk.Entry(fl, width=12); self.en_cx.insert(0, "400")
        self._row(fl, "Cạnh t3 (mm) — ngang", self.en_cx, 1)
        self.en_cy = ttk.Entry(fr, width=12); self.en_cy.insert(0, "400")
        self._row(fr, "Cạnh t2 (mm) — đứng", self.en_cy, 0)
        for w in (self.en_cx, self.en_cy):
            w.bind("<FocusOut>", lambda e: self._refresh_rebar())

    # ---- 3. Bố trí cốt thép dọc (format VietconSoft) ----
    DIAS = ["10", "12", "14", "16", "18", "20", "22", "25", "28", "32"]

    def _sec_rebar(self):
        f = self._frame("3. Bố trí cốt thép dọc")
        DIAS = self.DIAS

        # ===== Panel cho tiết diện chữ nhật =====
        self.rebar_rect = ttk.Frame(f)
        self.rebar_rect.grid(row=0, column=0, sticky=tk.NSEW)
        f.columnconfigure(0, weight=2)
        f.columnconfigure(1, weight=3)
        rr = self.rebar_rect
        r = 0
        self.sp_cover = ttk.Entry(rr, width=8)
        self.sp_cover.insert(0, "30")
        self._row(rr, "Lớp bê tông bảo vệ cốt dọc c (mm)", self.sp_cover, r)
        r += 1
        self.cb_corner_dia = ttk.Entry(rr, width=8)
        self.cb_corner_dia.insert(0, "20")
        self._row(rr, "4 thanh thép góc", self.cb_corner_dia, r)
        r += 1
        # Thép cạnh t2: số thanh + đường kính
        fr2 = ttk.Frame(rr)
        self.sp_e2n = ttk.Entry(fr2, width=5)
        self.sp_e2n.insert(0, "3")
        self.cb_e2d = ttk.Entry(fr2, width=5)
        self.cb_e2d.insert(0, "20")
        self.sp_e2n.pack(side=tk.LEFT)
        ttk.Label(fr2, text="thanh/mặt – d").pack(side=tk.LEFT, padx=2)
        self.cb_e2d.pack(side=tk.LEFT)
        self._row(rr, "Thép cạnh t2 (2 mặt trái/phải)", fr2, r)
        r += 1
        # Thép cạnh t3
        fr3 = ttk.Frame(rr)
        self.sp_e3n = ttk.Entry(fr3, width=5)
        self.sp_e3n.insert(0, "3")
        self.cb_e3d = ttk.Entry(fr3, width=5)
        self.cb_e3d.insert(0, "20")
        self.sp_e3n.pack(side=tk.LEFT)
        ttk.Label(fr3, text="thanh/mặt – d").pack(side=tk.LEFT, padx=2)
        self.cb_e3d.pack(side=tk.LEFT)
        self._row(rr, "Thép cạnh t3 (2 mặt trên/dưới)", fr3, r)
        r += 1
        # Toggle 2 lớp thép + badge "Nâng cao"
        tog = ttk.Frame(rr)
        self.var_two_layer = tk.BooleanVar(value=False)
        ttk.Checkbutton(tog, text="Bố trí 2 lớp thép",
                        variable=self.var_two_layer,
                        command=self._toggle_two_layer).pack(side=tk.LEFT)
        tk.Label(tog, text="Nâng cao", bg="#dcfce7", fg="#15803d",
                 font=("", 8, "bold"), padx=6, pady=2).pack(side=tk.LEFT,
                                                           padx=6)
        tog.grid(row=r, column=0, columnspan=2, sticky=tk.W, padx=4,
                 pady=(6, 2))
        r += 1
        # Panel lớp 2 (ẩn/hiện theo toggle)
        self.l2_panel = ttk.LabelFrame(rr, text="Lớp thép thứ 2", padding=6)
        self.l2_panel.grid(row=r, column=0, columnspan=2, sticky=tk.EW,
                           padx=4, pady=4)
        r += 1
        seg = ttk.Frame(self.l2_panel)
        seg.pack(fill=tk.X, pady=(0, 6))
        self.var_l2mode = tk.StringVar(value="perimeter")
        self.btn_seg = {}
        for key, txt in (("perimeter", "Chu vi"),
                         ("concentrated", "Tập trung"),
                         ("bundled", "Ghép bó / đôi")):
            b = tk.Button(seg, text=txt, font=("", 9), padx=8, pady=4,
                          relief=tk.RAISED, bd=1,
                          command=lambda k=key: self._set_l2mode(k))
            b.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
            self.btn_seg[key] = b
        self._seg_default_bg = self.btn_seg["perimeter"].cget("bg")
        self._seg_default_fg = self.btn_seg["perimeter"].cget("fg")
        # --- Chu vi ---
        self.fr_perimeter = ttk.Frame(self.l2_panel)
        self.cb_l2_t2d = ttk.Combobox(self.fr_perimeter, values=DIAS,
                                      state="readonly", width=8)
        self.cb_l2_t2d.set("20")
        self._row(self.fr_perimeter, "Thép lớp 2 cạnh t2 — d",
                  self.cb_l2_t2d, 0)
        self.cb_l2_t3d = ttk.Combobox(self.fr_perimeter, values=DIAS,
                                      state="readonly", width=8)
        self.cb_l2_t3d.set("20")
        self._row(self.fr_perimeter, "Thép lớp 2 cạnh t3 — d",
                  self.cb_l2_t3d, 1)
        self.l2_perim_note = tk.StringVar(value="")
        ttk.Label(self.fr_perimeter, textvariable=self.l2_perim_note,
                  foreground="gray", font=("", 8)).grid(
                      row=2, column=0, columnspan=2, sticky=tk.W,
                      padx=4, pady=2)
        # --- Tập trung ---
        self.fr_conc = ttk.Frame(self.l2_panel)
        self.en_l2_s = ttk.Entry(self.fr_conc, width=10)
        self.en_l2_s.insert(0, "30")
        self._row(self.fr_conc, "Khe hở giữa 2 lớp s (mm)", self.en_l2_s,
                  0)
        self.cb_l2_side = ttk.Combobox(
            self.fr_conc, values=["Cạnh t2 (trái/phải)", "Cạnh t3 (trên/dưới)"],
            state="readonly", width=16)
        self.cb_l2_side.set("Cạnh t2 (trái/phải)")
        self._row(self.fr_conc, "Mặt bố trí", self.cb_l2_side, 1)
        self.sp_l2_count = ttk.Spinbox(self.fr_conc, from_=1, to=30,
                                       width=10)
        self.sp_l2_count.set("5")
        self._row(self.fr_conc, "Số thanh mỗi mặt", self.sp_l2_count, 2)
        self.cb_l2_dia = ttk.Combobox(self.fr_conc, values=DIAS,
                                      state="readonly", width=10)
        self.cb_l2_dia.set("25")
        self._row(self.fr_conc, "Đường kính", self.cb_l2_dia, 3)
        # --- Ghép bó / đôi ---
        self.fr_bund = ttk.Frame(self.l2_panel)
        self.cb_bundle_pos = ttk.Combobox(
            self.fr_bund, values=["Lớp trong", "Cùng lớp ngoài"],
            state="readonly", width=14)
        self.cb_bundle_pos.set("Lớp trong")
        self._row(self.fr_bund, "Vị trí bó", self.cb_bundle_pos, 0)
        self.sp_bundle_size = ttk.Spinbox(self.fr_bund, from_=1, to=4,
                                         width=10)
        self.sp_bundle_size.set("2")
        self._row(self.fr_bund, "Số thanh mỗi bó tại cạnh",
                  self.sp_bundle_size, 1)
        self.sp_bundle_corner = ttk.Spinbox(self.fr_bund, from_=1, to=4,
                                           width=10)
        self.sp_bundle_corner.set("2")
        self._row(self.fr_bund, "Số thanh mỗi bó tại góc",
                  self.sp_bundle_corner, 2)
        self.en_bundle_gap = ttk.Entry(self.fr_bund, width=10)
        self.en_bundle_gap.insert(0, "0")
        self._row(self.fr_bund, "Khe hở trong bó (mm)",
                  self.en_bundle_gap, 3)

        # ===== Panel cho tiết diện tròn =====
        self.rebar_circ = ttk.Frame(f)
        self.rebar_circ.grid(row=0, column=0, sticky=tk.NSEW)
        self.cb_cdia = ttk.Combobox(self.rebar_circ, values=DIAS,
                                    state="readonly", width=10)
        self.cb_cdia.set("20")
        self._row(self.rebar_circ, "Đường kính (mm)", self.cb_cdia, 0)
        self.sp_cnbars = ttk.Spinbox(self.rebar_circ, from_=4, to=40,
                                     width=10)
        self.sp_cnbars.set("8")
        self._row(self.rebar_circ, "Tổng số thanh", self.sp_cnbars, 1)
        self.sp_ccover = ttk.Spinbox(self.rebar_circ, from_=15, to=100,
                                     width=10)
        self.sp_ccover.set("30")
        self._row(self.rebar_circ, "Lớp bê tông bảo vệ c (mm)",
                  self.sp_ccover, 2)

        # ===== Cốt thép đai: bên phải =====
        sw_hdr = ttk.Frame(f)
        sw_hdr.grid(row=0, column=1, sticky=tk.NSEW,
                    padx=4, pady=(4, 2))
        for j, t in enumerate(("Số nhánh", "Đ.kính", "K.cách")):
            ttk.Label(sw_hdr, text=t, style="Muted.TLabel").grid(
                row=0, column=j + 1, padx=2)
            sw_hdr.columnconfigure(j + 1, weight=1)
        self.sw_inputs = {}
        for i, lbl in enumerate(("Đai bao:", "Đai giữa t2:", "Đai giữa t3:")):
            ttk.Label(sw_hdr, text=lbl, style="Muted.TLabel").grid(
                row=i + 1, column=0, sticky=tk.W, padx=2, pady=2)
            row = {}
            for j, key in enumerate(("legs", "dia", "s")):
                e = ttk.Entry(sw_hdr, width=6)
                e.grid(row=i + 1, column=j + 1, padx=2, pady=2,
                       sticky=tk.EW)
                row[key] = e
            self.sw_inputs[lbl] = row
        # Giá trị mặc định
        for lbl in ("Đai bao:", "Đai giữa t2:", "Đai giữa t3:"):
            self.sw_inputs[lbl]["legs"].insert(0, "2")
            self.sw_inputs[lbl]["dia"].insert(0, "8")
            self.sw_inputs[lbl]["s"].insert(0, "200")
        # Giữ tên cũ để tương thích (dùng Đai bao)
        self.en_sw_dia = self.sw_inputs["Đai bao:"]["dia"]
        self.en_sw_s = self.sw_inputs["Đai bao:"]["s"]
        self.en_sw_legs = self.sw_inputs["Đai bao:"]["legs"]
        self.rebar_info = tk.StringVar(value="")  # giữ để tương thích, không hiển thị
        # Bind refresh
        for w in (self.sp_cover, self.sp_e2n, self.sp_e3n, self.en_l2_s,
                  self.sp_l2_count, self.en_bundle_gap, self.sp_cnbars,
                  self.sp_ccover, self.sp_bundle_size, self.sp_bundle_corner):
            w.bind("<FocusOut>", lambda e: self._refresh_rebar())
            w.bind("<Return>", lambda e: self._refresh_rebar())
        for w in (self.cb_corner_dia, self.cb_e2d, self.cb_e3d,
                  self.cb_l2_t2d, self.cb_l2_t3d, self.cb_l2_side,
                  self.cb_l2_dia, self.cb_bundle_pos, self.cb_cdia):
            w.bind("<<ComboboxSelected>>", lambda e: self._refresh_rebar())
        self._toggle_two_layer()
        self._set_l2mode("perimeter")
        self._refresh_rebar_panel()

    def _toggle_two_layer(self):
        """Ẩn/hiện panel lớp 2."""
        if self.var_two_layer.get():
            self.l2_panel.grid()
        else:
            self.l2_panel.grid_remove()
        self._refresh_rebar()

    def _set_l2mode(self, mode):
        """Chọn chế độ lớp 2 + highlight nút segmented."""
        self.var_l2mode.set(mode)
        for key, b in self.btn_seg.items():
            if key == mode:
                b.config(bg="#15803d", fg="white", relief=tk.SUNKEN)
            else:
                b.config(bg=self._seg_default_bg,
                         fg=self._seg_default_fg, relief=tk.RAISED)
        self.fr_perimeter.pack_forget()
        self.fr_conc.pack_forget()
        self.fr_bund.pack_forget()
        {"perimeter": self.fr_perimeter,
         "concentrated": self.fr_conc,
         "bundled": self.fr_bund}[mode].pack(fill=tk.X)
        self._refresh_rebar()

    def _refresh_rebar_panel(self):
        """Hiện panel chữ nhật/tròn theo loại tiết diện."""
        is_rect = self.cb_kind.get() == "Chữ nhật"
        if is_rect:
            self.rebar_rect.grid()
            self.rebar_circ.grid_remove()
        else:
            self.rebar_rect.grid_remove()
            self.rebar_circ.grid()
        self._refresh_rebar()

    # ---- 4. Chiều dài tính toán ----
    def _sec_stability(self):
        f = self._frame("4. Chiều dài tính toán")
        hdr = ["Tham số", "Phương 2", "Phương 3"]
        for c, h in enumerate(hdr):
            ttk.Label(f, text=h, font=("", 9, "bold")).grid(
                row=0, column=c, padx=4, pady=2, sticky=tk.W)
        f.columnconfigure(1, weight=1)
        f.columnconfigure(2, weight=1)
        bn = list(BOUNDARY_NAMES.values())
        self.en_Lx = ttk.Entry(f, width=12)
        self.en_Ly = ttk.Entry(f, width=12)
        self.cb_tx = ttk.Combobox(f, values=bn, state="readonly", width=12)
        self.cb_tx.set("Ngàm nửa cứng")
        self.cb_bx = ttk.Combobox(f, values=bn, state="readonly", width=12)
        self.cb_bx.set("Ngàm nửa cứng")
        self.cb_ty = ttk.Combobox(f, values=bn, state="readonly", width=12)
        self.cb_ty.set("Ngàm nửa cứng")
        self.cb_by = ttk.Combobox(f, values=bn, state="readonly", width=12)
        self.cb_by.set("Ngàm nửa cứng")
        self.en_psix = ttk.Entry(f, width=12)
        self.en_psiy = ttk.Entry(f, width=12)
        rows = [
            ("Chiều dài cột L (m)", self.en_Lx, self.en_Ly),
            ("Liên kết đầu trên", self.cb_tx, self.cb_ty),
            ("Liên kết đầu dưới", self.cb_bx, self.cb_by),
            ("Hệ số ψ (tự điền theo LK)", self.en_psix, self.en_psiy),
        ]
        for i, (lab, wx, wy) in enumerate(rows, start=1):
            ttk.Label(f, text=lab).grid(row=i, column=0, sticky=tk.W,
                                       padx=4, pady=2)
            wx.grid(row=i, column=1, padx=4, pady=2, sticky=tk.EW)
            wy.grid(row=i, column=2, padx=4, pady=2, sticky=tk.EW)
        self.l0_var = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.l0_var, font=("", 9, "italic"),
                  foreground="#0a4d8c").grid(row=5, column=0, columnspan=3,
                                             sticky=tk.W, padx=4, pady=4)
        # Tự điền hệ số ψ theo điều kiện biên
        for cb in (self.cb_tx, self.cb_bx, self.cb_ty, self.cb_by):
            cb.bind("<<ComboboxSelected>>", lambda e: self._auto_psi())
        self._auto_psi()

    def _auto_psi(self):
        """Điền hệ số ψ theo bảng tra từ điều kiện biên đã chọn."""
        from rc_column.stability import PSI_TABLE, BOUNDARY_NAMES
        rev = {v: k for k, v in BOUNDARY_NAMES.items()}
        for cb_t, cb_b, en in ((self.cb_tx, self.cb_bx, self.en_psix),
                               (self.cb_ty, self.cb_by, self.en_psiy)):
            t = rev.get(cb_t.get(), "")
            b = rev.get(cb_b.get(), "")
            p = PSI_TABLE.get((t, b), PSI_TABLE.get((b, t), 1.0))
            en.delete(0, tk.END)
            en.insert(0, f"{p:g}")

    # ---- 5. Nội lực ----
    def _sec_loads(self):
        f = self._frame("5. Nội lực kiểm tra")
        # Chọn chế độ: nhập tay / import Excel
        self.var_load_mode = tk.StringVar(value="etabs")
        mode_bar = ttk.Frame(f)
        mode_bar.grid(row=0, column=0, columnspan=2, sticky=tk.W,
                      padx=4, pady=4)
        st = ttk.Style()
        st.configure("White.TRadiobutton", background="white", font=("", 10))
        ttk.Radiobutton(mode_bar, text="Nhập tay", style="White.TRadiobutton",
                        variable=self.var_load_mode, value="manual",
                        command=self._toggle_load_mode).pack(side=tk.LEFT,
                                                            padx=6)
        ttk.Radiobutton(mode_bar, text="Import Excel ETABS",
                        style="White.TRadiobutton",
                        variable=self.var_load_mode, value="etabs",
                        command=self._toggle_load_mode).pack(side=tk.LEFT,
                                                            padx=6)

        # ---- Chế độ nhập tay ----
        self.manual_frame = ttk.Frame(f)
        self.manual_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW)
        self.en_N = ttk.Entry(self.manual_frame, width=18)
        self.en_N.insert(0, "1500")
        self._row(self.manual_frame, "Lực dọc N (kN) — N > 0 là nén",
                  self.en_N, 0)
        self.en_Mx = ttk.Entry(self.manual_frame, width=18)
        self.en_Mx.insert(0, "80")
        self._row(self.manual_frame, "Mô men M2 (kN·m) — quanh trục 2",
                  self.en_Mx, 1)
        self.en_My = ttk.Entry(self.manual_frame, width=18)
        self.en_My.insert(0, "60")
        self._row(self.manual_frame, "Mô men M3 (kN·m) — quanh trục 3",
                  self.en_My, 2)
        self.en_Q2 = ttk.Entry(self.manual_frame, width=18)
        self.en_Q2.insert(0, "0")
        self._row(self.manual_frame, "Lực cắt Q2/V2 (kN)",
                  self.en_Q2, 3)
        self.en_Q3 = ttk.Entry(self.manual_frame, width=18)
        self.en_Q3.insert(0, "0")
        self._row(self.manual_frame, "Lực cắt Q3/V3 (kN)",
                  self.en_Q3, 4)
        self.var_lt = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.manual_frame, text="Khai báo thành phần tải dài hạn",
                        variable=self.var_lt,
                        command=self._toggle_lt).grid(row=5, column=0,
                                                     columnspan=2, sticky=tk.W,
                                                     padx=4, pady=4)
        self.lt_frame = ttk.Frame(self.manual_frame)
        self.lt_frame.grid(row=6, column=0, columnspan=2, sticky=tk.EW, padx=4)
        self.lt_frame.grid_remove()
        self.en_Nlt = ttk.Entry(self.lt_frame, width=18); self.en_Nlt.insert(0, "0")
        self._row(self.lt_frame, "N dài hạn (kN)", self.en_Nlt, 0)
        self.en_Mxlt = ttk.Entry(self.lt_frame, width=18); self.en_Mxlt.insert(0, "0")
        self._row(self.lt_frame, "M2 dài hạn (kN·m)", self.en_Mxlt, 1)
        self.en_Mylt = ttk.Entry(self.lt_frame, width=18); self.en_Mylt.insert(0, "0")
        self._row(self.lt_frame, "M3 dài hạn (kN·m)", self.en_Mylt, 2)
        ttk.Label(self.lt_frame, foreground="gray", wraplength=380,
                  text="Nếu bỏ chọn: φL = 2.00 (thiên về an toàn). Nếu chọn: "
                       "xác định φLx, φLy theo Công thức (48), 1.00 ≤ φL ≤ 2.00."
                  ).grid(row=3, column=0, columnspan=2, padx=4, pady=2,
                         sticky=tk.W)

        # ---- Chế độ import Excel ----
        self.etabs_frame = ttk.Frame(f)
        self.etabs_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW)
        self.etabs_frame.grid_remove()
        # 3 nút Import từ Etabs: giãn đều theo cửa sổ như SAVE/SAVE AS/OPEN
        btn_row = ttk.Frame(self.etabs_frame)
        btn_row.grid(row=0, column=0, columnspan=3, sticky=tk.EW,
                     padx=4, pady=4)
        st.configure("Big.TButton", font=("", 12), padding=(8, 6))
        ttk.Button(btn_row, text="📂 Chọn file Excel", style="Big.TButton",
                   command=self.on_import_etabs).pack(
                       side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        ttk.Button(btn_row, text="📋 Paste từ Clipboard", style="Big.TButton",
                   command=self.on_paste_etabs).pack(
                       side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(btn_row, text="🗑️ Xóa nội lực", style="Big.TButton",
                   command=self.on_delete_forces).pack(
                       side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        # Luôn chỉ tính tổ hợp (Combination) - bỏ checkbox theo yêu cầu
        self.etabs_info = tk.StringVar(value="")
        # Bảng kết quả: Story, Label, Comb, Station, N, V2, V3, M2, M3, D/C
        cols = ("story", "label", "case", "station", "N", "V2", "V3",
                "M2", "M3", "dc")
        self.etabs_tree = ttk.Treeview(self.etabs_frame, columns=cols,
                                       show="headings", height=12)
        self.etabs_tree.bind("<Double-1>", self._edit_etabs_cell)
        hd = {"story": "Story", "label": "Label", "case": "Comb",
              "station": "Station", "N": "N", "V2": "V2", "V3": "V3",
              "M2": "M2", "M3": "M3", "dc": "D/C"}
        wd = {"story": 60, "label": 60, "case": 70, "station": 55,
              "N": 65, "V2": 60, "V3": 60, "M2": 65, "M3": 65, "dc": 55}
        for c in cols:
            self.etabs_tree.heading(c, text=hd[c])
            self.etabs_tree.column(c, width=wd[c], anchor=tk.CENTER)
        # Tag đỏ cho dòng D/C > 1, nền xen kẽ như bảng thép đai
        self.etabs_tree.tag_configure("over", foreground="#DC2626")
        self.etabs_tree.tag_configure("even", background="#F3F4F6")
        # Header phẳng giống bảng thép đai: nền #F3F4F6, chữ đậm, không 3D
        _st = ttk.Style()
        _st.configure("Etabs.Treeview.Heading", font=("", 9, "bold"),
                      background="#F3F4F6", foreground="#111827",
                      relief="flat", borderwidth=0)
        _st.configure("Etabs.Treeview", rowheight=22,
                      borderwidth=1, relief="solid")
        self.etabs_tree.configure(style="Etabs.Treeview")
        self.etabs_tree.grid(row=4, column=0, columnspan=2, padx=4, pady=4,
                             sticky=tk.EW)
        vsb = ttk.Scrollbar(self.etabs_frame, orient=tk.VERTICAL,
                            command=self.etabs_tree.yview)
        vsb.grid(row=4, column=2, sticky=tk.NS)
        self.etabs_tree.configure(yscrollcommand=vsb.set)
        self.etabs_tree.tag_configure("ng", background="#fee2e2")
        self.etabs_tree.tag_configure("worst", background="#fecaca",
                                      font=("", 9, "bold"))
        self.etabs_forces = []
        self.current_save_path = None
        # Áp dụng trạng thái mặc định (Ngàm / Import Excel)
        self._toggle_load_mode()

    def _toggle_load_mode(self):
        if self.var_load_mode.get() == "etabs":
            self.manual_frame.grid_remove()
            self.etabs_frame.grid()
        else:
            self.etabs_frame.grid_remove()
            self.manual_frame.grid()

    def _toggle_lt(self):
        if self.var_lt.get():
            self.lt_frame.grid()
        else:
            self.lt_frame.grid_remove()

    # ============================ Logic ============================
    def _f(self, entry, default=0.0):
        try:
            return float(entry.get().strip().replace(",", "."))
        except Exception:
            return default

    def _bkey(self, combo):
        inv = {v: k for k, v in BOUNDARY_NAMES.items()}
        return inv.get(combo.get(), "khop")

    def _draft_input(self) -> ColumnInput:
        """Dựng input nháp (chưa cần nội lực) để vẽ sơ đồ & thống kê thép."""
        is_rect = self.cb_kind.get() == "Chữ nhật"
        model = "3line" if self.cb_model.get().startswith("3") else "2line"

        def _gi(sp, default=0):
            try:
                return int(float(sp.get()))
            except Exception:
                return default

        def _gd(cb, default=20.0):
            try:
                return float(cb.get())
            except Exception:
                return default

        if is_rect:
            e2n = max(0, _gi(self.sp_e2n, 3)); e2d = _gd(self.cb_e2d, 20.0)
            e3n = max(0, _gi(self.sp_e3n, 3)); e3d = _gd(self.cb_e3d, 20.0)
            cover = self._f(self.sp_cover, 30.0)
            corner_dia = _gd(self.cb_corner_dia, 20.0)
        else:
            e2n, e2d, e3n, e3d = 0, 20.0, 0, 20.0
            cover = self._f(self.sp_ccover, 30.0)
            corner_dia = _gd(self.cb_cdia, 20.0)
        l2_side_txt = self.cb_l2_side.get()
        bundle_txt = self.cb_bundle_pos.get()
        return ColumnInput(
            concrete_grade=self.cb_conc.get(), gamma_b=self._f(self.en_gb, 0.85),
            steel_grade=self.cb_steel.get(),
            sw_steel_grade=self.cb_sw_steel.get(),
            gamma_s=self._f(self.en_gs, 1.0),
            concrete_model=model,
            section_type="rect" if is_rect else "circle",
            cx=self._f(self.en_cx, 400.0), cy=self._f(self.en_cy, 400.0),
            bar_dia=_gd(self.cb_cdia, 20.0),
            nx=e3n + 2, ny=e2n + 2,  # giữ tương thích (số thanh mỗi cạnh kể cả góc)
            n_bars=max(4, _gi(self.sp_cnbars, 8)),
            cover=cover,
            corner_dia=corner_dia,
            edge_t2_count=e2n, edge_t2_dia=e2d,
            edge_t3_count=e3n, edge_t3_dia=e3d,
            two_layer=bool(self.var_two_layer.get()),
            layer2_mode=self.var_l2mode.get(),
            l2_t2_dia=_gd(self.cb_l2_t2d, 20.0),
            l2_t3_dia=_gd(self.cb_l2_t3d, 20.0),
            l2_s_layer=self._f(self.en_l2_s, 30.0),
            l2_side="t2" if l2_side_txt.startswith("Cạnh t2") else "t3",
            l2_count=max(1, _gi(self.sp_l2_count, 5)),
            l2_dia=_gd(self.cb_l2_dia, 25.0),
            bundle_pos="inner" if bundle_txt.startswith("Lớp trong") else "outer",
            bundle_size=max(1, _gi(self.sp_bundle_size, 2)),
            bundle_corner=max(1, _gi(self.sp_bundle_corner, 2)),
            bundle_gap=self._f(self.en_bundle_gap, 0.0),
            sw_dia=self._f(self.en_sw_dia, 8.0),
            sw_spacing=self._f(self.en_sw_s, 200.0),
            sw_legs=max(2, int(self._f(self.en_sw_legs, 2))),
            swm2_dia=self._f(self.sw_inputs["Đai giữa t2:"]["dia"], 8.0),
            swm2_spacing=self._f(self.sw_inputs["Đai giữa t2:"]["s"], 200.0),
            swm2_legs=int(self._f(self.sw_inputs["Đai giữa t2:"]["legs"], 0)),
            swm3_dia=self._f(self.sw_inputs["Đai giữa t3:"]["dia"], 8.0),
            swm3_spacing=self._f(self.sw_inputs["Đai giữa t3:"]["s"], 200.0),
            swm3_legs=int(self._f(self.sw_inputs["Đai giữa t3:"]["legs"], 0)),
        )

    def _refresh_rebar(self):
        """Cập nhật thống kê thép kiểu VietconSoft khi đổi tiết diện/thép."""
        try:
            inp = self._draft_input()
            sec = build_section(inp)
        except Exception:
            return
        n = len(sec.rebars)
        # Gom theo (layer, dia): "16d25 + 8d20"
        from collections import Counter
        cnt = Counter((r.layer, r.dia) for r in sec.rebars)
        parts = []
        for (layer, dia) in sorted(cnt, key=lambda k: (k[0], -k[1])):
            parts.append(f"{cnt[(layer, dia)]}d{dia:.0f}")
        compo = " + ".join(parts)
        ccx, ccy = clear_spacing(sec)
        # khoảng cách tim = khoảng hở + đường kính trung bình
        dias = sorted(set(r.dia for r in sec.rebars))
        d_avg = sum(dias) / len(dias) if dias else 0
        lines = [
            f"{n} thanh",
            compo,
            f"Tổng As {sec.steel_area:.0f} mm²",
            f"Hàm lượng μ {sec.reinforcement_ratio * 100:.2f}%",
        ]
        if math.isfinite(ccx):
            lines.append(f"Khoảng hở thông thủy: t3 = {ccx:.1f} mm, "
                         f"t2 = {ccy:.1f} mm")
            lines.append(f"Khoảng cách tim: t3 = {ccx + d_avg:.1f} mm, "
                         f"t2 = {ccy + d_avg:.1f} mm")
        self.rebar_info.set("\n".join(lines))
        # Ghi chú số thanh lớp 2 (chu vi: tự match lớp 1)
        try:
            self.l2_perim_note.set(
                f"Số thanh tự động = lớp 1 "
                f"(t2: {inp.edge_t2_count}/mặt, t3: {inp.edge_t3_count}/mặt, "
                f"góc: 4)")
        except Exception:
            pass
        # Live update sơ đồ mặt cắt + bảng tổng hợp (nếu đã có figure)
        self._live_update_section(sec, inp)

    def _live_update_section(self, sec, inp):
        """Vẽ lại sơ đồ mặt cắt + thẻ thống kê khi đổi nhập liệu."""
        ax1 = getattr(self, "_sec_ax", None)
        if ax1 is None:
            return
        try:
            from rc_column.pdf_export import draw_section_ax
            ax1.clear()
            draw_section_ax(ax1, sec, show_stats=False)
            self._sec_fig.tight_layout()
            self._sec_canvas.draw_idle()
            # Cập nhật text các thẻ thống kê
            varmap = getattr(self, "_sec_card_vars", None)
            if varmap:
                vals = self._section_card_values(sec)
                for k, var in varmap.items():
                    if k in vals:
                        var.set(vals[k])
        except Exception:
            pass

    def collect(self) -> ColumnInput:
        inp = self._draft_input()
        def opt(e):
            t = e.get().strip()
            return float(t.replace(",", ".")) if t else None
        inp.Lx = self._f(self.en_Lx, 4.0); inp.Ly = self._f(self.en_Ly, 4.0)
        inp.top_x = self._bkey(self.cb_tx); inp.bottom_x = self._bkey(self.cb_bx)
        inp.top_y = self._bkey(self.cb_ty); inp.bottom_y = self._bkey(self.cb_by)
        inp.psi_x = opt(self.en_psix); inp.psi_y = opt(self.en_psiy)
        inp.N = self._f(self.en_N); inp.Mx = self._f(self.en_Mx)
        inp.My = self._f(self.en_My)
        inp.Q2 = self._f(self.en_Q2); inp.Q3 = self._f(self.en_Q3)
        inp.long_term = LongTermLoads(
            has_data=self.var_lt.get(), N_lt=self._f(self.en_Nlt),
            Mx_lt=self._f(self.en_Mxlt), My_lt=self._f(self.en_Mylt))
        return inp

    def on_check(self):
        # Chế độ ETABS: kiểm tra tất cả tổ hợp
        if self.var_load_mode.get() == "etabs":
            self.on_check_etabs()
            return
        # Chế độ nhập tay: kiểm tra 1 bộ nội lực
        try:
            inp = self.collect()
            res = check_column(inp, n_angles=24)
        except Exception as ex:
            messagebox.showerror("Lỗi", str(ex))
            return
        ok_txt = "ĐẠT ✓" if res.ok else "KHÔNG ĐẠT ✗"
        self.result_var.set(
            f"Kết quả: {ok_txt} — D/C = {res.dc:.3f}")
        # Tóm tắt + biểu đồ + L0
        sec = build_section(inp)
        self._show_summary(sec, inp, res)
        # Thuyết minh (có format màu sắc) + nhúng hình
        self._render_report_sections(generate_report_sections(inp, res),
                                      sec, inp, res, case_info=None,
                                      shear_info=None)
        self._pdf_inp, self._pdf_res = inp, res

    # ---------------- ETABS ----------------
    def on_import_etabs(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Chọn file Excel ETABS",
            filetypes=[("Excel", "*.xlsx *.xls"), ("All", "*.*")])
        if not path:
            return
        self._load_etabs_file(path)

    def on_paste_etabs(self):
        """Dán nội lực ETABS từ clipboard (copy từ bảng Element Forces)."""
        try:
            text = self.clipboard_get()
        except Exception:
            from tkinter import messagebox
            messagebox.showwarning("Clipboard", "Clipboard trống.")
            return
        if not text or not text.strip():
            from tkinter import messagebox
            messagebox.showwarning("Clipboard", "Clipboard trống.")
            return
        try:
            from rc_column.etabs_import import parse_etabs_clipboard
            forces = parse_etabs_clipboard(
                text, only_combinations=True)
        except Exception as ex:
            from tkinter import messagebox
            messagebox.showerror("Lỗi đọc clipboard", str(ex))
            return
        self.etabs_forces = forces
        self.etabs_file = "<clipboard>"
        n_case = len(set(f.case for f in forces))
        self.etabs_info.set(
            f"Đã dán {len(forces)} dòng, {n_case} tổ hợp từ clipboard — "
            f"Bấm 'KIỂM TRA KHẢ NĂNG CHỊU LỰC' để tính.")
        self._fill_etabs_table([(f, None) for f in forces])

    def on_delete_forces(self):
        """Xóa toàn bộ nội lực đã import."""
        from tkinter import messagebox
        if not getattr(self, "etabs_forces", []):
            messagebox.showinfo("Xóa nội lực", "Bảng nội lực đang trống.")
            return
        if messagebox.askyesno("Xóa nội lực",
                               f"Xóa toàn bộ {len(self.etabs_forces)} dòng nội lực?"):
            self.etabs_forces = []
            self.etabs_file = ""
            self.etabs_info.set("Đã xóa toàn bộ nội lực.")
            self._fill_etabs_table([])

    def _load_etabs_file(self, path: str) -> bool:
        """Nạp file Excel ETABS (dùng chung cho import tay và mở dữ liệu)."""
        try:
            from rc_column.etabs_import import read_etabs_excel
            forces = read_etabs_excel(
                path, only_combinations=True)
        except Exception as ex:
            messagebox.showerror("Lỗi đọc file", str(ex))
            return False
        self.etabs_forces = forces
        self.etabs_file = path
        n_case = len(set(f.case for f in forces))
        self.etabs_info.set(
            f"Đã đọc {len(forces)} dòng, {n_case} tổ hợp từ: "
            f"{path.split('/')[-1].split(chr(92))[-1]} — "
            f"Bấm 'KIỂM TRA KHẢ NĂNG CHỊU LỰC' để tính.")
        self._fill_etabs_table([(f, None) for f in forces])
        return True

    def _fill_etabs_table(self, rows):
        t = self.etabs_tree
        t.delete(*t.get_children())
        for i, (f, r) in enumerate(rows):
            dc = r["dc"] if r else None
            vals = (f.story, f.column, f.case, f"{f.station:.2f}",
                    f"{f.N:.0f}", f"{f.Q2:.0f}", f"{f.Q3:.0f}",
                    f"{f.Mx:.0f}", f"{f.My:.0f}",
                    f"{dc:.3f}" if dc is not None and dc == dc else "—")
            # Nền xen kẽ; dòng D/C > 1 thêm đỏ text
            tags = ["even"] if i % 2 == 0 else []
            if dc and dc == dc and dc > 1:
                tags.append("over")
            t.insert("", tk.END, values=vals, tags=tuple(tags))

    def _edit_etabs_cell(self, event):
        """Double-click vào ô N/M2/M3 để sửa trực tiếp."""
        t = self.etabs_tree
        row_id = t.identify_row(event.y)
        col_id = t.identify_column(event.x)
        if not row_id or not col_id:
            return
        # Chỉ cho sửa cột N (1), M2 (2), M3 (3) - 0-based trong values
        col_idx = int(col_id[1:]) - 1
        if col_idx not in (1, 2, 3):
            return
        # Lấy index dòng trong etabs_forces (theo thứ tự hiển thị)
        children = t.get_children()
        try:
            row_pos = list(children).index(row_id)
        except ValueError:
            return
        # Entry đè lên ô
        bbox = t.bbox(row_id, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        vals = t.item(row_id, "values")
        entry = tk.Entry(t, font=("", 9))
        entry.insert(0, vals[col_idx])
        entry.select_range(0, tk.END)
        entry.focus()
        entry.place(x=x, y=y, width=w, height=h)

        def _save(_e=None):
            new_val = entry.get().strip()
            try:
                num = float(new_val)
            except ValueError:
                entry.destroy()
                return
            # Cập nhật etabs_forces theo row_pos
            # (table có thể đã sắp xếp lại, tìm theo case+station)
            case_station = vals[0]
            for f in self.etabs_forces:
                if f"{f.case}@{f.station:.2f}" == case_station:
                    if col_idx == 1:
                        f.N = num
                    elif col_idx == 2:
                        f.Mx = num
                    elif col_idx == 3:
                        f.My = num
                    break
            new_vals = list(vals)
            new_vals[col_idx] = f"{num:.0f}"
            new_vals[4] = "—"
            new_vals[5] = "—"
            t.item(row_id, values=new_vals)
            entry.destroy()
            self.etabs_info.set("Đã sửa dữ liệu — bấm 'KIỂM TRA KHẢ NĂNG "
                                "CHỊU LỰC' để tính lại.")

        entry.bind("<Return>", _save)
        entry.bind("<FocusOut>", lambda e: entry.destroy())
        entry.bind("<Escape>", lambda e: entry.destroy())

    def on_check_etabs(self):
        if not self.etabs_forces:
            messagebox.showinfo("ETABS", "Hãy import file Excel trước.")
            return
        try:
            inp = self.collect()
        except Exception as ex:
            messagebox.showerror("Lỗi", str(ex))
            return
        from rc_column.checker import BatchChecker
        self.etabs_info.set("Đang kiểm tra, vui lòng đợi...")
        self.update_idletasks()
        import time
        t0 = time.time()
        # Xác định L cho từng (Story, Column):
        # - Nếu ô L nhập tay CÓ giá trị: dùng giá trị đó cho tất cả
        # - Nếu ô L TRỐNG: L = station lớn nhất của từng (Story, Column)
        from collections import defaultdict
        _L_manual = self._f(self.en_Lx, 0.0)
        _groups = defaultdict(list)
        for _f in self.etabs_forces:
            _groups[(_f.story, _f.column)].append(_f)
        rows = []
        for (_st, _cl), _flist in _groups.items():
            if _L_manual > 0:
                _L_grp = _L_manual
            else:
                _L_grp = max(_f.station for _f in _flist)
            _inp_g = self.collect()
            _inp_g.Lx = _inp_g.Ly = _L_grp
            _bc = BatchChecker(_inp_g, n_angles=12)
            for _f in _flist:
                _r = _bc.check_one(_f.N, _f.Mx, _f.My, _inp_g.long_term)
                rows.append((_f, _r))
        # sắp xếp theo D/C giảm dần (nguy hiểm nhất lên đầu)
        rows.sort(key=lambda x: -(x[1]["dc"]) if x[1]["dc"] == x[1]["dc"]
                  else float("inf"))
        # highlight dòng nguy hiểm nhất (dòng đầu sau sắp xếp)
        self._fill_etabs_table(rows)
        worst_f, worst_r = rows[0]
        # Tự động xác định L: station lớn nhất của cùng Story + Column Label
        _L_auto = None
        try:
            _sts = [f.station for f in self.etabs_forces
                    if f.story == worst_f.story and f.column == worst_f.column]
            if _sts:
                _L_auto = max(_sts)
        except Exception:
            pass
        if _L_auto and _L_auto > 0:
            self.en_Lx.delete(0, tk.END); self.en_Lx.insert(0, f"{_L_auto:.2f}")
            self.en_Ly.delete(0, tk.END); self.en_Ly.insert(0, f"{_L_auto:.2f}")
        children = self.etabs_tree.get_children()
        if children:
            self.etabs_tree.item(children[0], tags=("worst",))
            self.etabs_tree.see(children[0])
        n_ng = sum(1 for _, r in rows if r["dc"] > 1)
        dt = time.time() - t0
        self.etabs_info.set(
            f"Xong {len(rows)} tổ hợp trong {dt:.1f}s — "
            f"Nguy hiểm nhất: {worst_f.case} @ {worst_f.station:.2f}m "
            f"(D/C = {worst_r['dc']:.3f}) — {n_ng} tổ hợp KHÔNG ĐẠT.")
        # Lưu kết quả tất cả tổ hợp cho mục 8
        self._batch_rows = rows
        # hiện thuyết minh của tổ hợp nguy hiểm nhất
        inp_w = self.collect()
        inp_w.N, inp_w.Mx, inp_w.My = worst_f.N, worst_f.Mx, worst_f.My
        # L cho worst: nếu ô L trống thì dùng station max của nhóm worst
        _Lw = self._f(self.en_Lx, 0.0)
        if _Lw <= 0:
            _sts_w = [f.station for f in self.etabs_forces
                      if f.story == worst_f.story and f.column == worst_f.column]
            if _sts_w:
                _Lw = max(_sts_w)
        if _Lw > 0:
            inp_w.Lx = inp_w.Ly = _Lw
        # Lực cắt: lấy từ combo có |Q| lớn nhất (độc lập với combo N-M)
        f_q2 = max(self.etabs_forces, key=lambda f: abs(f.Q2))
        f_q3 = max(self.etabs_forces, key=lambda f: abs(f.Q3))
        inp_w.Q2, inp_w.Q3 = f_q2.Q2, f_q3.Q3
        shear_info = {
            "q2": {"case": f_q2.case, "station": f_q2.station, "Q": f_q2.Q2,
                   "story": getattr(f_q2, "story", ""),
                   "column": getattr(f_q2, "column", "")},
            "q3": {"case": f_q3.case, "station": f_q3.station, "Q": f_q3.Q3,
                   "story": getattr(f_q3, "story", ""),
                   "column": getattr(f_q3, "column", "")},
        }
        res_w = check_column(inp_w, n_angles=24)
        sec_w = build_section(inp_w)
        batch = getattr(self, "_batch_rows", None)
        if not getattr(self, "var_export_table", None) or \
                not self.var_export_table.get():
            batch = None
        case_info = {"case": worst_f.case, "station": worst_f.station,
                     "N": worst_f.N, "M2": worst_f.Mx, "M3": worst_f.My,
                     "story": getattr(worst_f, "story", ""),
                     "column": getattr(worst_f, "column", "")}
        self._render_report_sections(
            generate_report_sections(inp_w, res_w, batch_rows=batch,
                                     case_info=case_info,
                                     shear_info=shear_info),
            sec_w, inp_w, res_w, case_info=case_info,
            shear_info=shear_info)
        self._pdf_inp, self._pdf_res = inp_w, res_w
        self._pdf_batch = batch
        self._pdf_case = case_info
        self._pdf_shear = shear_info
        # cập nhật cả tab Tóm tắt + biểu đồ cho tổ hợp nguy hiểm nhất
        self._show_summary(sec_w, inp_w, res_w,
                           prefix=f"Tổ hợp {worst_f.case}@{worst_f.station:.2f}m: ")
        self.result_var.set(
            f"Tổ hợp nguy hiểm nhất: {worst_f.case} — "
            f"{'KHÔNG ĐẠT ✗' if worst_r['dc'] > 1 else 'ĐẠT ✓'} "
            f"(D/C = {worst_r['dc']:.3f})")

    def _export_pdf(self):
        """Xuất PDF theo tab đang mở: Tóm tắt hoặc Thuyết minh."""
        try:
            from tkinter import filedialog, messagebox
            if self._last_sec is None:
                messagebox.showwarning("Xuất PDF",
                                       "Chưa có kết quả để xuất.")
                return
            # Tab đang chọn
            cur = self.nb.select()
            is_summary = (cur == str(self.tab_sum))
            # Tên file mặc định: TMTT-TÊN CẤU KIỆN.pdf
            import os as _os
            _ck = ""
            _p = getattr(self, "current_save_path", "") or ""
            if _p:
                _ck = _os.path.splitext(_os.path.basename(_p))[0].upper()
            _def = f"TMTT-{_ck}.pdf" if _ck else "TMTT.pdf"
            path = filedialog.asksaveasfilename(
                title="Xuất PDF",
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf")],
                initialfile=_def)
            if not path:
                return
            # Lấy PNG biểu đồ từ tab Tóm tắt cho PDF
            def _get_chart_pngs():
                try:
                    import io
                    nm_fig = getattr(self, "_nm_fig", None)
                    m2m3_fig = getattr(self, "_m2m3_fig", None)
                    if nm_fig is not None and m2m3_fig is not None:
                        buf1 = io.BytesIO()
                        nm_fig.savefig(buf1, format="png", dpi=150,
                                       bbox_inches="tight")
                        buf2 = io.BytesIO()
                        m2m3_fig.savefig(buf2, format="png", dpi=150,
                                         bbox_inches="tight")
                        return (buf1.getvalue(), buf2.getvalue())
                except Exception:
                    pass
                return None
            # Hàm hiện dialog thành công có nút Mở PDF
            def _show_success(ppath):
                import tkinter as _tk
                dlg = _tk.Toplevel(self)
                dlg.title("Xuất PDF")
                dlg.resizable(False, False)
                dlg.transient(self)
                dlg.grab_set()
                # Căn giữa màn hình
                dlg.update_idletasks()
                _w, _h = 380, 130
                _x = (dlg.winfo_screenwidth() // 2) - (_w // 2)
                _y = (dlg.winfo_screenheight() // 2) - (_h // 2)
                dlg.geometry(f"{_w}x{_h}+{_x}+{_y}")
                _tk.Label(dlg, text=f"Đã lưu: {ppath}",
                          wraplength=340, justify="left").pack(
                              padx=16, pady=(16, 12))
                btns = _tk.Frame(dlg)
                btns.pack(pady=4)
                def _open():
                    import os as _os, sys as _sys, subprocess as _sp
                    try:
                        if _sys.platform.startswith("win"):
                            _os.startfile(ppath)
                        elif _sys.platform == "darwin":
                            _sp.run(["open", ppath])
                        else:
                            _sp.run(["xdg-open", ppath])
                    except Exception:
                        pass
                    dlg.destroy()
                _tk.Button(btns, text="Mở PDF", width=12,
                           command=_open).pack(side="left", padx=6)
                _tk.Button(btns, text="Đóng", width=12,
                           command=dlg.destroy).pack(side="left", padx=6)
                dlg.wait_window()
            if is_summary:
                from rc_column.pdf_export import export_summary_pdf
                # Gán tên file vào inp để hiển thị "Cấu kiện"
                try:
                    self._last_inp._filename =                         getattr(self, "current_save_path", "") or ""
                except Exception:
                    pass
                # Lưu nguyên hình mặt cắt từ app để PDF dùng
                _sec_png = None
                try:
                    import tempfile, os
                    _sec_fig = getattr(self, "_sec_fig", None)
                    if _sec_fig is not None:
                        _sec_png = os.path.join(
                            tempfile.gettempdir(), "_sec_app.png")
                        # Tight sát nội dung, giữ đúng tỉ lệ
                        _sec_fig.savefig(_sec_png, dpi=150,
                                         bbox_inches="tight",
                                         pad_inches=0.05)
                except Exception:
                    _sec_png = None
                export_summary_pdf(self._last_sec, self._last_inp,
                                   self._last_res, path,
                                   case_info=getattr(self, "_pdf_case",
                                                     None),
                                   sec_img_path=_sec_png)
            else:
                from rc_column.pdf_report_cards import export_pdf_cards
                export_pdf_cards(self._last_inp, self._last_res, path,
                           batch_rows=getattr(self, "_pdf_batch", None),
                           case_info=getattr(self, "_pdf_case", None),
                           shear_info=getattr(self, "_pdf_shear", None),
                           chart_pngs=_get_chart_pngs())
            _show_success(path)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Lỗi", f"Không xuất được: {e}")

    def _show_summary(self, sec, inp, res, prefix=""):
        """Cập nhật biểu đồ + L0 (ô text tóm tắt đã bỏ theo yêu cầu)."""
        self.l0_var.set(
            f"Chiều dài tính toán: L02 = {res.L0x:.2f} m, "
            f"L03 = {res.L0y:.2f} m")
        if HAS_MPL:
            self._last_sec = sec
            self._last_inp = inp
            self._last_res = res
            self._redraw()

    def _on_toggle_table(self):
        """Bật/tắt bảng tổng hợp (mục 8) -> render lại thuyết minh."""
        if not getattr(self, "_pdf_inp", None):
            return
        from rc_column.report import generate_report_sections
        from rc_column.checker import build_section
        inp, res = self._pdf_inp, self._pdf_res
        sec = build_section(inp)
        batch = getattr(self, "_batch_rows", None)
        if not self.var_export_table.get():
            batch = None
        case_info = getattr(self, "_pdf_case", None)
        shear_info = getattr(self, "_pdf_shear", None)
        self._render_report_sections(
            generate_report_sections(inp, res, batch_rows=batch,
                                     case_info=case_info,
                                     shear_info=shear_info),
            sec, inp, res, case_info=case_info,
            shear_info=shear_info)
        self._pdf_batch = batch

    def on_export_pdf(self):
        """Xuất thuyết minh ra PDF."""
        if not getattr(self, "_pdf_inp", None):
            messagebox.showinfo("Xuất PDF", "Hãy kiểm tra trước khi xuất PDF.")
            return
        from tkinter import filedialog
        import os as _os
        _ck = ""
        _p = getattr(self, "current_save_path", "") or ""
        if _p:
            _ck = _os.path.splitext(_os.path.basename(_p))[0].upper()
        _def = f"TMTT-{_ck}.pdf" if _ck else "TMTT.pdf"
        path = filedialog.asksaveasfilename(
            title="Lưu thuyết minh PDF",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=_def)
        if not path:
            return
        try:
            from rc_column.pdf_report_cards import export_pdf_cards
            # Lấy PNG từ tab Tóm tắt
            _cp = None
            try:
                import io
                _nf = getattr(self, "_nm_fig", None)
                _mf = getattr(self, "_m2m3_fig", None)
                if _nf is not None and _mf is not None:
                    _b1 = io.BytesIO(); _nf.savefig(_b1, format="png",
                                                    dpi=150,
                                                    bbox_inches="tight")
                    _b2 = io.BytesIO(); _mf.savefig(_b2, format="png",
                                                    dpi=150,
                                                    bbox_inches="tight")
                    _cp = (_b1.getvalue(), _b2.getvalue())
            except Exception:
                pass
            export_pdf_cards(self._pdf_inp, self._pdf_res, path,
                       batch_rows=getattr(self, "_pdf_batch", None),
                       case_info=getattr(self, "_pdf_case", None),
                       shear_info=getattr(self, "_pdf_shear", None),
                       chart_pngs=_cp)
            self._show_pdf_success(path)
        except Exception as ex:
            messagebox.showerror("Lỗi xuất PDF", str(ex))

    def _show_pdf_success(self, ppath):
        """Dialog thành công có nút Mở PDF."""
        import tkinter as _tk
        dlg = _tk.Toplevel(self)
        dlg.title("Xuất PDF")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        # Căn giữa màn hình
        dlg.update_idletasks()
        _w, _h = 380, 130
        _x = (dlg.winfo_screenwidth() // 2) - (_w // 2)
        _y = (dlg.winfo_screenheight() // 2) - (_h // 2)
        dlg.geometry(f"{_w}x{_h}+{_x}+{_y}")
        _tk.Label(dlg, text=f"Đã lưu: {ppath}",
                  wraplength=340, justify="left").pack(
                      padx=16, pady=(16, 12))
        btns = _tk.Frame(dlg)
        btns.pack(pady=4)
        def _open():
            import os as _os, sys as _sys, subprocess as _sp
            try:
                if _sys.platform.startswith("win"):
                    _os.startfile(ppath)
                elif _sys.platform == "darwin":
                    _sp.run(["open", ppath])
                else:
                    _sp.run(["xdg-open", ppath])
            except Exception:
                pass
            dlg.destroy()
        _tk.Button(btns, text="Mở PDF", width=12,
                   command=_open).pack(side="left", padx=6)
        _tk.Button(btns, text="Đóng", width=12,
                   command=dlg.destroy).pack(side="left", padx=6)
        dlg.wait_window()

    def _collect_data(self) -> dict:
        """Thu thập toàn bộ dữ liệu nhập liệu thành dict."""
        def ev(e):
            return e.get()
        def bv(v):
            return v.get()
        return {
            "version": 1,
            # 1. Vật liệu
            "concrete": self.cb_conc.get(), "gamma_b": ev(self.en_gb),
            "steel": self.cb_steel.get(), "sw_steel": self.cb_sw_steel.get(),
            "gamma_s": ev(self.en_gs),
            "model": self.cb_model.get(),
            # 2. Tiết diện
            "kind": self.cb_kind.get(),
            "cx": ev(self.en_cx), "cy": ev(self.en_cy),
            "cover": self.sp_cover.get(),
            # 3. Cốt thép dọc (kiểu VietconSoft)
            "corner_dia": self.cb_corner_dia.get(),
            "e2n": self.sp_e2n.get(), "e2d": self.cb_e2d.get(),
            "e3n": self.sp_e3n.get(), "e3d": self.cb_e3d.get(),
            "two_layer": bv(self.var_two_layer),
            "l2mode": self.var_l2mode.get(),
            "l2_t2d": self.cb_l2_t2d.get(), "l2_t3d": self.cb_l2_t3d.get(),
            "l2_s": ev(self.en_l2_s), "l2_side": self.cb_l2_side.get(),
            "l2_count": self.sp_l2_count.get(),
            "l2_dia": self.cb_l2_dia.get(),
            "bundle_pos": self.cb_bundle_pos.get(),
            "bundle_size": self.sp_bundle_size.get(),
            "bundle_corner": self.sp_bundle_corner.get(),
            "bundle_gap": ev(self.en_bundle_gap),
            # tròn
            "cdia": self.cb_cdia.get(), "cnbars": self.sp_cnbars.get(),
            "ccover": self.sp_ccover.get(),
            # tương thích cũ
            "dia": self.cb_corner_dia.get(),
            "nx": str(int(float(self.sp_e3n.get() or 0)) + 2),
            "ny": str(int(float(self.sp_e2n.get() or 0)) + 2),
            # đai
            "sw_dia": ev(self.en_sw_dia), "sw_s": ev(self.en_sw_s),
            "sw_legs": ev(self.en_sw_legs),
            "swm2_dia": ev(self.sw_inputs["Đai giữa t2:"]["dia"]),
            "swm2_s": ev(self.sw_inputs["Đai giữa t2:"]["s"]),
            "swm2_legs": ev(self.sw_inputs["Đai giữa t2:"]["legs"]),
            "swm3_dia": ev(self.sw_inputs["Đai giữa t3:"]["dia"]),
            "swm3_s": ev(self.sw_inputs["Đai giữa t3:"]["s"]),
            "swm3_legs": ev(self.sw_inputs["Đai giữa t3:"]["legs"]),
            # 4. Chiều dài tính toán
            "Lx": ev(self.en_Lx), "Ly": ev(self.en_Ly),
            "top_x": self.cb_tx.get(), "bot_x": self.cb_bx.get(),
            "top_y": self.cb_ty.get(), "bot_y": self.cb_by.get(),
            "psi_x": ev(self.en_psix), "psi_y": ev(self.en_psiy),
            # 5. Nội lực
            "load_mode": bv(self.var_load_mode),
            "N": ev(self.en_N), "Mx": ev(self.en_Mx), "My": ev(self.en_My),
            "Q2": ev(self.en_Q2), "Q3": ev(self.en_Q3),
            "long_term": bv(self.var_lt),
            "N_lt": ev(self.en_Nlt), "Mx_lt": ev(self.en_Mxlt),
            "My_lt": ev(self.en_Mylt),
            "etabs_path": getattr(self, "etabs_file", ""),
            "etabs_comb": True,
            # Lưu luôn nội lực đã import (không cần link lại file Excel)
            "etabs_forces": [
                {"story": f.story, "column": f.column, "case": f.case,
                 "case_type": f.case_type, "station": f.station,
                 "N": f.N, "Mx": f.Mx, "My": f.My,
                 "Q2": f.Q2, "Q3": f.Q3}
                for f in getattr(self, "etabs_forces", [])
            ],
        }

    def _apply_data(self, d: dict):
        """Đổ dữ liệu từ dict vào các trường nhập liệu."""
        def se(e, v):
            e.delete(0, tk.END); e.insert(0, str(v))
        try:
            self.cb_conc.set(d.get("concrete", "B25")); se(self.en_gb, d.get("gamma_b", "0.85"))
            self.cb_steel.set(d.get("steel", "CB400-V"))
            self.cb_sw_steel.set(d.get("sw_steel", "CB400-V"))
            se(self.en_gs, d.get("gamma_s", "1.0"))
            self.cb_model.set(d.get("model", self.cb_model.get()))
            self.cb_kind.set(d.get("kind", "Chữ nhật"))
            se(self.en_cx, d.get("cx", "400")); se(self.en_cy, d.get("cy", "400"))
            se(self.sp_cover, d.get("cover", "30"))
            # Cốt thép dọc kiểu mới (fallback về field cũ nếu file cũ)
            se(self.cb_corner_dia, d.get("corner_dia", d.get("dia", "20")))
            se(self.sp_e2n, d.get("e2n", str(max(0, int(d.get("ny", 3)) - 2))))
            se(self.cb_e2d, d.get("e2d", d.get("dia", "20")))
            se(self.sp_e3n, d.get("e3n", str(max(0, int(d.get("nx", 3)) - 2))))
            se(self.cb_e3d, d.get("e3d", d.get("dia", "20")))
            self.var_two_layer.set(bool(d.get("two_layer", False)))
            self._set_l2mode(d.get("l2mode", "perimeter"))
            self.cb_l2_t2d.set(d.get("l2_t2d", "20"))
            self.cb_l2_t3d.set(d.get("l2_t3d", "20"))
            se(self.en_l2_s, d.get("l2_s", "30"))
            self.cb_l2_side.set(d.get("l2_side", "Cạnh t2 (trái/phải)"))
            self.sp_l2_count.set(d.get("l2_count", "5"))
            self.cb_l2_dia.set(d.get("l2_dia", "25"))
            self.cb_bundle_pos.set(d.get("bundle_pos", "Lớp trong"))
            self.sp_bundle_size.set(d.get("bundle_size", "2"))
            self.sp_bundle_corner.set(d.get("bundle_corner", "2"))
            se(self.en_bundle_gap, d.get("bundle_gap", "0"))
            self.cb_cdia.set(d.get("cdia", d.get("dia", "20")))
            self.sp_cnbars.set(d.get("cnbars", "8"))
            self.sp_ccover.set(d.get("ccover", d.get("cover", "30")))
            self._toggle_two_layer()
            self._refresh_rebar_panel()
            se(self.en_sw_dia, d.get("sw_dia", "8"))
            for lbl, pfx in (("Đai giữa t2:", "swm2"), ("Đai giữa t3:", "swm3")):
                se(self.sw_inputs[lbl]["dia"], d.get(f"{pfx}_dia", "8"))
                se(self.sw_inputs[lbl]["s"], d.get(f"{pfx}_s", "200"))
                se(self.sw_inputs[lbl]["legs"], d.get(f"{pfx}_legs", "2"))
            se(self.en_sw_s, d.get("sw_s", "200"))
            se(self.en_sw_legs, d.get("sw_legs", "2"))
            se(self.en_Lx, d.get("Lx", "4.0")); se(self.en_Ly, d.get("Ly", "4.0"))
            self.cb_tx.set(d.get("top_x", "Ngàm nửa cứng")); self.cb_bx.set(d.get("bot_x", "Ngàm nửa cứng"))
            self.cb_ty.set(d.get("top_y", "Ngàm nửa cứng")); self.cb_by.set(d.get("bot_y", "Ngàm nửa cứng"))
            se(self.en_psix, d.get("psi_x", "")); se(self.en_psiy, d.get("psi_y", ""))
            self.var_load_mode.set(d.get("load_mode", "etabs"))
            se(self.en_N, d.get("N", "")); se(self.en_Mx, d.get("Mx", ""))
            se(self.en_My, d.get("My", ""))
            se(self.en_Q2, d.get("Q2", "0")); se(self.en_Q3, d.get("Q3", "0"))
            self.var_lt.set(bool(d.get("long_term", False)))
            se(self.en_Nlt, d.get("N_lt", "")); se(self.en_Mxlt, d.get("Mx_lt", ""))
            se(self.en_Mylt, d.get("My_lt", ""))

            self.etabs_file = d.get("etabs_path", "")
            # cập nhật giao diện theo chế độ
            self._toggle_load_mode()
            self._toggle_lt()
            self._refresh_rebar()
        except Exception as ex:
            messagebox.showerror("Lỗi", f"Không đọc được file dữ liệu: {ex}")

    def _do_save(self, path: str) -> bool:
        """Ghi dữ liệu ra file JSON. Trả về True nếu thành công."""
        import json
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._collect_data(), f, ensure_ascii=False,
                          indent=2)
            self.current_save_path = path
            return True
        except Exception as ex:
            messagebox.showerror("Lỗi", str(ex))
            return False

    def on_save_data(self):
        """SAVE: lần đầu mở hộp thoại, lần sau ghi đè file đang mở."""
        import os
        from tkinter import filedialog
        path = self.current_save_path
        if not path or not os.path.exists(path):
            path = filedialog.asksaveasfilename(
                title="Lưu dữ liệu cột",
                defaultextension=".json",
                filetypes=[("JSON", "*.json")],
                initialfile="CotBTCT.json")
            if not path:
                return
        if self._do_save(path):
            self._update_title()
            messagebox.showinfo("Lưu dữ liệu", f"Đã lưu: {path}")

    def _update_ck(self):
        """Cập nhật tên cấu kiện (IN HOA, bỏ .json)."""
        import os
        ck = getattr(self, "ck_var", None)
        if ck is None:
            return
        p = getattr(self, "current_save_path", None)
        if p:
            name = os.path.splitext(os.path.basename(p))[0].upper()
            ck.set(f"Cấu kiện: {name}")
        else:
            ck.set("")

    def _update_title(self):
        """Title bar hiện tên file đang lưu."""
        import os
        base = "Kiểm tra cột bê tông cốt thép — TCVN 5574:2018"
        p = getattr(self, "current_save_path", None)
        if p:
            self.title(f"{base} — [{os.path.basename(p)}]")
        else:
            self.title(base)

    def on_save_as_data(self):
        """SAVE AS: luôn mở hộp thoại chọn file mới."""
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            title="Lưu dữ liệu cột (Save As)",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="CotBTCT.json")
        if not path:
            return
        if self._do_save(path):
            self._update_title()
            messagebox.showinfo("Lưu dữ liệu", f"Đã lưu: {path}")

    def on_load_data(self):
        """Mở file dữ liệu JSON đã lưu."""
        import json
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Mở dữ liệu cột",
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            self._apply_data(d)
            # Khôi phục nội lực đã lưu trong file (không cần file Excel)
            forces_data = d.get("etabs_forces", [])
            if d.get("load_mode") == "etabs" and forces_data:
                from rc_column.etabs_import import EtabsForce
                self.etabs_forces = [EtabsForce(**fd) for fd in forces_data]
                n_case = len(set(f.case for f in self.etabs_forces))
                self.etabs_info.set(
                    f"Đã nạp {len(self.etabs_forces)} dòng, {n_case} tổ hợp "
                    f"từ file dữ liệu — Bấm 'KIỂM TRA KHẢ NĂNG CHỊU LỰC' để tính.")
                self._fill_etabs_table([(f, None) for f in self.etabs_forces])
            self.current_save_path = path
            self._update_title()
            self._update_ck()
            # Tự động tính toán sau khi mở file
            try:
                self.on_check()
            except Exception:
                pass
        except Exception as ex:
            messagebox.showerror("Lỗi", str(ex))

    def _render_report(self, segs):
        """Hiển thị thuyết minh với format VietconSoft (giữ để tương thích)."""
        t = self.calc_text
        t.delete("1.0", tk.END)
        self._setup_report_tags(t)
        for text, tags in segs:
            t.insert(tk.END, self._clean_math(text), tags if tags else ())
        self._report_images = []

    def _setup_report_tags(self, t):
        """Định nghĩa tags màu sắc theo Tailwind của web mẫu."""
        t.tag_configure("title", font=("", 13, "bold"),
                        foreground="#0f172a")
        t.tag_configure("sec_title", font=("", 11, "bold"),
                        foreground="#0f172a")
        t.tag_configure("sec_ref", font=("", 9),
                        foreground="#64748b")
        t.tag_configure("card", font=("", 10),
                        foreground="#1e293b")
        t.tag_configure("mono", font=("Consolas", 10),
                        foreground="#334155")
        t.tag_configure("result", font=("", 10, "bold"),
                        foreground="#0f172a")
        t.tag_configure("dc", font=("Consolas", 14, "bold"),
                        foreground="#059669")
        t.tag_configure("ok", font=("", 12, "bold"),
                        foreground="#065f46", background="#d1fae5",
                        borderwidth=1, relief="solid")
        t.tag_configure("ng", font=("", 12, "bold"),
                        foreground="#991b1b", background="#fee2e2",
                        borderwidth=1, relief="solid")

    def _clean_math(self, text: str) -> str:
        """Chuyển _{xx} thành xx cho hiển thị trong app."""
        import re
        return re.sub(r"_\{([^}]+)\}", r"\1", text)

    def _render_report_sections(self, sections, sec, inp, res,
                                case_info=None, shear_info=None):
        """Hiển thị thuyết minh kiểu Vietcon: mục 1-7 dạng card."""
        from rc_column.report_widgets import build_calc_widgets
        # Xóa nội dung cũ
        for w in self._calc_inner.winfo_children():
            w.destroy()
        # Lấy PNG biểu đồ từ tab Tóm tắt (giống hệt)
        chart_pngs = None
        try:
            import io
            nm_fig = getattr(self, "_nm_fig", None)
            m2m3_fig = getattr(self, "_m2m3_fig", None)
            if nm_fig is not None and m2m3_fig is not None:
                buf1 = io.BytesIO()
                nm_fig.savefig(buf1, format="png", dpi=100,
                               bbox_inches="tight")
                buf2 = io.BytesIO()
                m2m3_fig.savefig(buf2, format="png", dpi=100,
                                 bbox_inches="tight")
                chart_pngs = (buf1.getvalue(), buf2.getvalue())
        except Exception:
            pass
        # Mục 1-7: widget kiểu Vietcon
        body = build_calc_widgets(self._calc_inner, inp, res, case_info,
                                  shear_info, chart_pngs)
        body.pack(fill=tk.BOTH, expand=True)
        # Cập nhật scroll
        self._calc_inner.update_idletasks()
        self._calc_canvas.configure(
            scrollregion=self._calc_canvas.bbox("all"))
        self._bind_wheel(self._calc_inner, self._calc_canvas)

    def _bind_wheel_to_calc(self, widget):
        """Gắn cuộn chuột cho thanh công cụ -> cuộn canvas thuyết minh."""
        self._bind_wheel(widget, self._calc_canvas)

    def _embed_report_images(self, sec, inp, res):
        """(Không dùng nữa — giữ để tương thích, logic đã chuyển vào
        _render_report_sections.)"""
        pass

    # ============ Helpers cho tab Tóm tắt (layout 2x2) ============
    def _section_card_values(self, sec):
        """Số liệu cho các thẻ thống kê dưới sơ đồ mặt cắt."""
        import math
        from collections import Counter
        from rc_column.sections import clear_spacing
        n = len(sec.rebars)
        cnt = Counter((getattr(r, "layer", 1), r.dia) for r in sec.rebars)
        parts = [f"{cnt[k]}d{k[1]:.0f}"
                 for k in sorted(cnt, key=lambda k: (k[0], -k[1]))]
        ccx, ccy = clear_spacing(sec)
        dias = sorted(set(r.dia for r in sec.rebars))
        d_avg = sum(dias) / len(dias) if dias else 0.0
        vals = {
            "n": " + ".join(parts),
            "nsub": "",
            "as": f"{sec.steel_area:.0f} mm\u00b2",
            "mu": f"{sec.reinforcement_ratio * 100:.2f}%",
        }
        if math.isfinite(ccx):
            vals["clear"] = f"t3 = {ccx:.1f} mm, t2 = {ccy:.1f} mm"
            vals["tim"] = (f"t3 = {ccx + d_avg:.1f} mm, "
                           f"t2 = {ccy + d_avg:.1f} mm")
        else:
            vals["clear"] = vals["tim"] = "\u2014"
        return vals

    def _build_section_cards(self, parent, sec, inp=None):
        """3 thẻ TK bằng nhau + thông tin vật liệu. Trả về dict var."""
        vals = self._section_card_values(sec)
        varmap = {}

        def _card(prow, title, vkey, subkey=None):
            # Chiều cao bằng 3 box vật liệu trên (52px)
            cell = tk.Frame(prow, bg="white",
                            highlightbackground="#E5E7EB",
                            highlightthickness=1, height=52)
            cell.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3, pady=2)
            cell.pack_propagate(False)
            tk.Label(cell, text=title, font=("", 8), fg="#6B7280",
                     bg="white").pack(pady=(6, 0))
            var = tk.StringVar(value=vals[vkey])
            tk.Label(cell, textvariable=var, font=("", 11, "bold"),
                     bg="white").pack(pady=2)
            varmap[vkey] = var
            if subkey:
                svar = tk.StringVar(value=vals[subkey])
                tk.Label(cell, textvariable=svar, font=("", 8),
                         fg="#6B7280", bg="white").pack()
                varmap[subkey] = svar

        # 3 box vật liệu lên trên
        if inp is not None:
            mrow = tk.Frame(parent, bg="#F9FAFB")
            mrow.pack(fill=tk.X, padx=2, pady=2)
            for title, val in (("Bê tông", inp.concrete_grade),
                               ("Thép dọc", inp.steel_grade),
                               ("Thép đai", inp.sw_steel_grade)):
                mb = tk.Frame(mrow, bg="white",
                              highlightbackground="#E5E7EB",
                              highlightthickness=1, height=52)
                mb.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3, pady=2)
                mb.pack_propagate(False)
                tk.Label(mb, text=title, font=("", 8), fg="#6B7280",
                         bg="white").pack(pady=(6, 0))
                tk.Label(mb, text=val, font=("", 10, "bold"),
                         bg="white").pack()
            varmap["_mat"] = None
        row1 = tk.Frame(parent, bg="#F9FAFB")
        row1.pack(fill=tk.X, padx=2, pady=(2, 4))
        _card(row1, "S\u1ed1 thanh", "n", "nsub")
        _card(row1, "T\u1ed5ng As", "as")
        _card(row1, "H\u00e0m l\u01b0\u1ee3ng \u03bc", "mu")
        return varmap

    def _build_param_table(self, parent, inp, res):
        """B\u1ea3ng th\u00f4ng s\u1ed1 t\u00ednh to\u00e1n (Treeview 3 c\u1ed9t)."""
        import math
        ttk.Label(parent, text="BẢNG THÔNG SỐ TÍNH TOÁN",
                  font=("", 11, "bold")).pack(pady=(2, 6))
        cols = ("sym", "desc", "val")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=16,
                            style="Param.Treeview")
        _pst = ttk.Style()
        _pst.configure("Param.Treeview.Heading", font=("", 9, "bold"),
                       background="#F3F4F6", foreground="#111827",
                       relief="flat", borderwidth=0)
        tree.heading("sym", text="K\u00fd hi\u1ec7u")
        tree.heading("desc", text="Th\u00f4ng s\u1ed1")
        tree.heading("val", text="Gi\u00e1 tr\u1ecb")
        tree.column("sym", width=64, anchor="center", stretch=False)
        tree.column("desc", width=200, anchor="w")
        tree.column("val", width=220, anchor="e", stretch=False)
        tree.tag_configure("odd", background="#F9FAFB")
        dc_bg = "#D1FAE5" if res.ok else "#FEE2E2"
        dc_fg = "#065F46" if res.ok else "#991B1B"
        tree.tag_configure("dc", background=dc_bg, foreground=dc_fg)
        alpha_deg = math.degrees(math.atan2(res.My_star, res.Mx_star)) \
            if abs(res.Mx_star) + abs(res.My_star) > 1e-9 else 0.0
        Ma = math.hypot(res.Mx_star, res.My_star)
        rows = [
            ("N", "L\u1ef1c d\u1ecdc t\u00ednh to\u00e1n",
             f"{res.N:+.1f} kN"),
            ("M2", "M\u00f4 men ban \u0111\u1ea7u ph\u01b0\u01a1ng 2",
             f"{res.Mx:.1f} kN\u00b7m"),
            ("M3", "M\u00f4 men ban \u0111\u1ea7u ph\u01b0\u01a1ng 3",
             f"{res.My:.1f} kN\u00b7m"),
            ("e02", "\u0110\u1ed9 l\u1ec7ch t\u00e2m ban \u0111\u1ea7u ph\u01b0\u01a1ng 2",
             f"{res.e0x:.1f} mm"),
            ("e03", "\u0110\u1ed9 l\u1ec7ch t\u00e2m ban \u0111\u1ea7u ph\u01b0\u01a1ng 3",
             f"{res.e0y:.1f} mm"),
            ("\u03bb2", "\u0110\u1ed9 m\u1ea3nh c\u1ed9t ph\u01b0\u01a1ng 2",
             f"{res.lambda_x:.1f}"),
            ("\u03bb3", "\u0110\u1ed9 m\u1ea3nh c\u1ed9t ph\u01b0\u01a1ng 3",
             f"{res.lambda_y:.1f}"),
            ("Ncr,2", "L\u1ef1c t\u1edbi h\u1ea1n Euler ph\u01b0\u01a1ng 2",
             f"{res.Ncrx:.1f} kN"),
            ("Ncr,3", "L\u1ef1c t\u1edbi h\u1ea1n Euler ph\u01b0\u01a1ng 3",
             f"{res.Ncry:.1f} kN"),
            ("\u03b1", "G\u00f3c t\u00e1c d\u1ee5ng m\u00f4 men",
             f"{alpha_deg:.1f} \u00b0"),
            ("\u03b72", "H\u1ec7 s\u1ed1 u\u1ed1n d\u1ecdc ph\u01b0\u01a1ng 2",
             f"{res.etax:.3f}"),
            ("\u03b73", "H\u1ec7 s\u1ed1 u\u1ed1n d\u1ecdc ph\u01b0\u01a1ng 3",
             f"{res.etay:.3f}"),
            ("M2*", "M\u00f4 men t\u00ednh to\u00e1n ph\u01b0\u01a1ng 2",
             f"{res.Mx_star:.1f} kN\u00b7m"),
            ("M3*", "M\u00f4 men t\u00ednh to\u00e1n ph\u01b0\u01a1ng 3",
             f"{res.My_star:.1f} kN\u00b7m"),
            ("M\u03b1", "M\u00f4 men t\u1ed5ng theo ph\u01b0\u01a1ng ki\u1ec3m tra",
             f"{Ma:.1f} kN\u00b7m"),
        ]
        for i, (a, b, c) in enumerate(rows):
            tree.insert("", "end", values=(a, b, c),
                        tags=("odd",) if i % 2 else ())
        ok_txt = "\u0110\u1ea0T" if res.ok else "KH\u00d4NG \u0110\u1ea0T"
        tree.insert("", "end",
                    values=("D/C", "T\u1ef7 s\u1ed1 s\u1eed d\u1ee5ng kh\u1ea3 n\u0103ng ch\u1ecbu l\u1ef1c",
                            f"{res.dc:.3f} (FS = {res.fs:.2f})  {ok_txt}"),
                    tags=("dc",))
        tree.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

    def _build_nm_notes(self, parent, inp, res):
        """3 d\u00f2ng ch\u00fa th\u00edch d\u01b0\u1edbi bi\u1ec3u \u0111\u1ed3 N-M."""
        import math
        mono = ("TkFixedFont", 10)
        alpha_deg = math.degrees(math.atan2(res.My_star, res.Mx_star)) \
            if abs(res.Mx_star) + abs(res.My_star) > 1e-9 else 0.0
        Ma = math.hypot(res.Mx_star, res.My_star)
        Mb = math.hypot(res.Bx, res.By)
        box = tk.Frame(parent, bg="white",
                       highlightbackground="#E5E7EB", highlightthickness=1)
        box.pack(fill=tk.X, padx=4, pady=4)
        r1 = tk.Frame(box, bg="white")
        r1.pack(fill=tk.X, pady=1, padx=4)
        tk.Label(r1, text=f"\u25cf \u0110\u01b0\u1eddng bao ki\u1ec3m tra: "
                          f"N-M\u03b1 (\u03b1 = {alpha_deg:.1f}\u00b0)",
                 font=mono, fg="#059669", bg="white").pack(side=tk.LEFT)
        okc = "#059669" if res.ok else "#DC2626"
        okt = "\u0110\u1ea0T" if res.ok else "KH\u00d4NG \u0110\u1ea0T"
        bgc = "#D1FAE5" if res.ok else "#FEE2E2"
        fgc = "#065F46" if res.ok else "#991B1B"
        tk.Label(r1, text=f"  D/C = OA / OB = {res.dc:.3f} \u2192 {okt}  ",
                 font=("", 10, "bold"), fg=fgc,
                 bg=bgc).pack(side=tk.LEFT, padx=6)
        # Thêm combo@vị trí
        _case = getattr(self, "_pdf_case", None) or {}
        _parts = []
        if _case.get("story"):
            _parts.append(str(_case.get("story")))
        if _case.get("column"):
            _parts.append(str(_case.get("column")))
        if _case.get("case"):
            _st = _case.get("station", "")
            _st_txt = f"@{_st:.2f}" if isinstance(_st, (int, float)) else ""
            _parts.append(f"{_case.get('case')}{_st_txt}")
        _combo_txt = f" [{', '.join(_parts)}]" if _parts else ""
        tk.Label(box, bg="white",
                 text=f"\u25cf A (\u0111i\u1ec3m t\u1ea3i){_combo_txt}:  "
                      f"N = {res.N:+.1f} kN,  "
                      f"M\u03b1 = {Ma:.1f} kN\u00b7m  "
                      f"(M2 = {res.Mx_star:.1f}, M3 = {res.My_star:.1f})",
                 font=mono, fg="#2563EB").pack(anchor="w", pady=1)
        tk.Label(box, bg="white",
                 text=f"\u25c6 B (\u0111i\u1ec3m gi\u1edbi h\u1ea1n):  "
                      f"Nu = {res.BN:+.1f} kN,  M\u03b1,u = {Mb:.1f} kN\u00b7m  "
                      f"(M2u = {res.Bx:.1f}, M3u = {res.By:.1f})",
                 font=mono, fg="#EA580C").pack(anchor="w", pady=1)

    def _build_nm_header(self, parent, res):
        """Header trên biểu đồ N-M (format giống M2-M3)."""
        import math
        alpha_deg = math.degrees(math.atan2(res.My_star, res.Mx_star)) \
            if abs(res.Mx_star) + abs(res.My_star) > 1e-9 else 0.0
        hdr = ttk.Frame(parent)
        hdr.pack(fill=tk.X, padx=4, pady=(2, 2))
        left = ttk.Frame(hdr)
        left.pack(side=tk.LEFT)
        tk.Label(left, text="\u25cf Bi\u1ec3u \u0111\u1ed3 t\u01b0\u01a1ng t\u00e1c N\u2013M\u03b1",
                 font=("", 10, "bold"), bg="white").pack(side=tk.LEFT)
        tk.Label(left, text=f"  \u03b1 = {alpha_deg:.1f}\u00b0  ",
                 font=("", 8, "bold"), fg="#065F46",
                 bg="#D1FAE5").pack(side=tk.LEFT, padx=6)

    def _build_m2m3_header(self, parent, res):
        """Header tr\u00ean bi\u1ec3u \u0111\u1ed3 M2-M3."""
        hdr = ttk.Frame(parent)
        hdr.pack(fill=tk.X, padx=4, pady=(2, 2))
        left = ttk.Frame(hdr)
        left.pack(side=tk.LEFT)
        tk.Label(left, text="\u25cf M\u1eb7t c\u1eaft M2-M3",
                 font=("", 10, "bold"), bg="white").pack(side=tk.LEFT)
        tk.Label(left, text=f"  N = {res.N:+.1f} kN  ",
                 font=("", 8, "bold"), fg="#1D4ED8",
                 bg="#DBEAFE").pack(side=tk.LEFT, padx=6)


        # Cập nhật tên cấu kiện
        self._update_ck()

    def _build_stirrup_summary(self, parent, inp, res):
        """Bảng kiểm tra thép đai: Phương 2 | Phương 3."""
        from rc_column.stirrup import (StirrupInput, check_stirrup,
                                      check_shear)
        from rc_column.sections import bar_area
        from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                        ConcreteMaterial)
        try:
            # Lấy đai bao (dùng chung) — có thể mở rộng theo t2/t3 sau
            stir_in = StirrupInput(dia=inp.sw_dia, spacing=inp.sw_spacing,
                                   legs=inp.sw_legs)
            conc = ConcreteMaterial(CONCRETE_GRADES[inp.concrete_grade],
                                    inp.gamma_b)
            swg = STEEL_GRADES.get(inp.sw_steel_grade)
            sr = check_stirrup(self._last_sec, stir_in, inp.cover)

            # Tính chi tiết từng phương (kể cả đai giữa)
            cols = {}
            # Q2 (theo trục 2): b = t2 = cy, h0 từ t3 = cx; dùng đai giữa t2
            # Q3 (theo trục 3): b = t3 = cx, h0 từ t2 = cy; dùng đai giữa t3
            for Q, lbl, b_w, h_dim, mdia, ms, mlegs in (
                    (inp.Q2, "2", inp.cy, inp.cx,
                     inp.swm2_dia, inp.swm2_spacing, inp.swm2_legs),
                    (inp.Q3, "3", inp.cx, inp.cy,
                     inp.swm3_dia, inp.swm3_spacing, inp.swm3_legs)):
                h0 = h_dim - inp.cover - inp.sw_dia - 12
                # Asw = đai bao + đai giữa
                Asw = stir_in.legs * bar_area(stir_in.dia)
                s_eff = stir_in.spacing
                sw_txt = (f"{stir_in.legs:.0f}φ{stir_in.dia:.0f} "
                          f"a{stir_in.spacing:.0f}")
                if mlegs > 0:
                    Asw += mlegs * bar_area(mdia)
                    s_eff = min(s_eff, ms) if ms > 0 else s_eff
                    sw_txt += (f" + {mlegs:.0f}φ{mdia:.0f} a{ms:.0f} "
                               f"(giữa)")
                sh = check_shear(Q, b_w, max(h0, 1), conc.Rb, conc.Rbt,
                                 Asw, swg.Rsw, s_eff)
                qsw = swg.Rsw * Asw / s_eff if s_eff > 0 else 0
                cols[lbl] = dict(Q=Q, b=b_w, h0=h0, Asw=Asw, qsw=qsw,
                                 sh=sh, sw_txt=sw_txt, s_eff=s_eff)

            # Title rõ
            tk.Label(parent, text="Kiểm tra thép đai",
                     font=("", 11, "bold"), bg="white", fg="#111827",
                     anchor="w").pack(fill=tk.X, padx=8, pady=(4, 2))

            # Bảng Phương 2 | Phương 3
            tf = tk.Frame(parent, bg="white")
            tf.pack(fill=tk.X, padx=8, pady=(4, 2))
            headers = ["Thông số", "Phương V2", "Phương V3"]
            for j, h in enumerate(headers):
                tk.Label(tf, text=h, font=("", 9, "bold"), bg="#F3F4F6",
                         fg="#111827", borderwidth=0,
                         highlightbackground="#D1D5DB",
                         highlightthickness=1,
                         padx=6, pady=3).grid(row=0, column=j, sticky="nsew")
                tf.columnconfigure(j, weight=1 if j else 2)
            rows = [
                ("Thép đai bố trí",
                 cols['2']['sw_txt'], cols['3']['sw_txt']),
                ("Q (kN)",
                 f"{cols['2']['Q']:.1f}", f"{cols['3']['Q']:.1f}"),
                ("b × h0 (mm)",
                 f"{cols['2']['b']:.0f} × {cols['2']['h0']:.0f}",
                 f"{cols['3']['b']:.0f} × {cols['3']['h0']:.0f}"),
                (f"Asw = n×φ{stir_in.dia:.0f} (mm²)",
                 f"{cols['2']['Asw']:.0f}", f"{cols['3']['Asw']:.0f}"),
                ("qsw = Rsw×Asw/s (N/mm)",
                 f"{cols['2']['qsw']:.1f}", f"{cols['3']['qsw']:.1f}"),
                ("ĐK1: 0.3×Rb×b×h0 (kN)",
                 f"{cols['2']['sh'].Qcap1:.1f}",
                 f"{cols['3']['sh'].Qcap1:.1f}"),
                ("Qb = 1.5×Rbt×b×h0²/C (kN)",
                 f"{cols['2']['sh'].Qb_opt:.1f}",
                 f"{cols['3']['sh'].Qb_opt:.1f}"),
                ("Qsw = 0.75×qsw×C (kN)",
                 f"{cols['2']['sh'].Qsw_opt:.1f}",
                 f"{cols['3']['sh'].Qsw_opt:.1f}"),
                ("C cho [Q]min (mm)",
                 f"{cols['2']['sh'].C_opt:.0f}",
                 f"{cols['3']['sh'].C_opt:.0f}"),
                ("[Q] = Qb+Qsw (kN)",
                 f"{cols['2']['sh'].Qcap2:.1f}",
                 f"{cols['3']['sh'].Qcap2:.1f}"),
            ]
            for i, (a, b, c) in enumerate(rows):
                bg = "#F9FAFB" if i % 2 else "white"
                for j, t in enumerate((a, b, c)):
                    fw = ("", 9, "bold") if j == 0 else ("", 9)
                    tk.Label(tf, text=t, font=fw, bg=bg, fg="#1F2937",
                             borderwidth=0,
                             highlightbackground="#D1D5DB",
                             highlightthickness=1,
                             padx=6, pady=2, anchor="w" if j == 0
                             else "center").grid(row=i + 1, column=j,
                                                 sticky="nsew")
            # Kết luận từ chịu cắt
            ok_all = all(cols[lbl]["sh"].ok for lbl in ("2", "3"))
            # Kết luận
            kl = "ĐẠT" if ok_all else "KHÔNG ĐẠT"
            fgk = "#065F46" if ok_all else "#991B1B"
            tk.Label(parent, text=f"Kết luận thép đai: {kl}",
                     font=("", 10, "bold"), fg=fgk, bg="white",
                     anchor="w").pack(fill=tk.X, padx=8, pady=(4, 6))
        except Exception as e:
            tk.Label(parent, text=f"Không tính được thép đai: {e}",
                     fg="#991B1B", bg="white").pack(padx=8, pady=4)


    def _redraw(self):
        """Layout 2x2: [mặt cắt + thẻ TK | bảng thông số] /
        [N-M + chú thích | header + M2-M3]."""
        if not HAS_MPL or self._last_sec is None:
            return
        import math
        sec, inp, res = self._last_sec, self._last_inp, self._last_res
        # Xóa toàn bộ nội dung cũ trong _sum_inner
        for w in self._sum_inner.winfo_children():
            w.destroy()
        # (sẽ gọi _update_ck ở cuối method)
        self._sec_ax = None
        self._sec_fig = None
        self._sec_canvas = None
        self._sec_card_vars = {}
        from rc_column.pdf_export import draw_section_ax, _radial_limit
        from rc_column.interaction import (BiaxialCapacity, FiberSection,
                                           uniaxial_curve_fs)
        fs = FiberSection(sec)

        def _nm_alpha_ax(ax, title_sz=12):
            # Biểu đồ N-M tại góc uốn xiên α (dùng điểm B song trục)
            # Style theo mẫu: đường xanh lá, fill nhạt, lưới đứt mảnh
            GREEN, GREEN_LT = "#059669", "#D1FAE5"
            RED, ORANGE = "#DC2626", "#F97316"
            BLUE_DASH = "#3B82F6"
            alpha_deg = math.degrees(
                math.atan2(res.My_star, res.Mx_star))
            cv = uniaxial_curve_fs(fs, alpha_deg, inp.concrete_model)
            m_pos = [p[1] for p in cv]
            n_pos = [p[0] for p in cv]
            m_neg = [-p[1] for p in cv]
            ax.plot(m_pos, n_pos, color=GREEN, linewidth=2.2, zorder=3)
            ax.plot(m_neg, n_pos, color=GREEN, linewidth=2.2, zorder=3)
            # Fill nhạt vùng trong
            ax.fill_betweenx(n_pos, 0, m_pos, color=GREEN, alpha=0.08,
                             zorder=1)
            ax.fill_betweenx(n_pos, m_neg, 0, color=GREEN, alpha=0.08,
                             zorder=1)
            Ma = math.hypot(res.Mx_star, res.My_star)
            Mb = math.hypot(res.Bx, res.By)
            lim = (res.BN, Mb)
            # Nét đứt đỏ từ tâm qua A tới B (kéo dài 1.18)
            ax.plot([0, lim[1] * 1.18], [0, lim[0] * 1.18], color=RED,
                    ls="--", lw=1.5, dashes=(4, 3), zorder=4)
            # Đường chiếu xanh đứt từ A xuống trục
            ax.plot([Ma, Ma], [0, res.N], color=BLUE_DASH, ls="--",
                    lw=1.2, dashes=(4, 3), alpha=0.8, zorder=2)
            ax.plot([0, Ma], [res.N, res.N], color=BLUE_DASH, ls="--",
                    lw=1.2, dashes=(4, 3), alpha=0.8, zorder=2)
            # Điểm B (giới hạn) vẽ trước, điểm A (tải trọng) vẽ sau
            ax.scatter([lim[1]], [lim[0]], c=ORANGE, s=70, zorder=5,
                       edgecolors="white", linewidths=1.2, label="Giới hạn")
            ax.scatter([Ma], [res.N], c=GREEN, s=70, zorder=6,
                       edgecolors="white", linewidths=1.2,
                       label="Điểm tải A")
            ax.text(Ma, res.N, "  A", fontsize=9, color=GREEN,
                    weight="bold", va="center", zorder=7)
            ax.text(lim[1], lim[0], "  B", fontsize=9, color=ORANGE,
                    weight="bold", va="center", zorder=7)
            ax.set_xlabel("Mα (kN·m)", fontweight="bold", fontsize=10)
            ax.set_ylabel("N (kN)", fontweight="bold", fontsize=10)

            # Legend 4 mục như web, đặt dưới biểu đồ
            from matplotlib.lines import Line2D
            leg_elems = [
                Line2D([0], [0], color=GREEN, lw=2.2, label="Đường bao N-Mα"),
                Line2D([0], [0], marker="o", color="w", markerfacecolor=GREEN,
                       markersize=8, markeredgecolor="white", label="Điểm tải A"),
                Line2D([0], [0], marker="D", color="w", markerfacecolor=ORANGE,
                       markersize=7, markeredgecolor="white", label="Điểm giới hạn B"),
                Line2D([0], [0], color=RED, lw=1.5, ls="--", dashes=(4, 3),
                       label="Tia tải O-A-B"),
            ]
            ax.legend(handles=leg_elems, fontsize=8, loc="upper center",
                      bbox_to_anchor=(0.5, -0.18), ncol=4, frameon=False)
            ax.grid(True, color="#E5E7EB", linestyle="--",
                    linewidth=0.7, alpha=0.9)
            ax.set_axisbelow(True)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            for sp in ("left", "bottom"):
                ax.spines[sp].set_color("#9CA3AF")

        def _m2m3_ax(ax):
            # Biểu đồ M2-M3 tại N (dùng điểm B song trục)
            # Style theo mẫu: đường xanh dương, fill nhạt
            BLUE, BLUE_LT = "#2563EB", "#DBEAFE"
            GREEN, RED, ORANGE = "#059669", "#DC2626", "#F97316"
            cap = BiaxialCapacity(sec, model=inp.concrete_model, n_angles=24)
            pts = cap.mx_my_curve(res.N)
            xs = [p[0] for p in pts] + [pts[0][0]]
            ys = [p[1] for p in pts] + [pts[0][1]]
            ax.plot(xs, ys, color=BLUE, linewidth=2.2, zorder=3)
            ax.fill(xs, ys, color=BLUE, alpha=0.08, zorder=1)
            # Nét đứt đỏ từ tâm qua A tới B
            ax.plot([0, res.Bx * 1.18], [0, res.By * 1.18], color=RED,
                    ls="--", lw=1.5, dashes=(4, 3), zorder=4)
            ax.scatter([res.Bx], [res.By], c=ORANGE, s=70, zorder=5,
                       edgecolors="white", linewidths=1.2, label="Giới hạn")
            ax.scatter([res.Mx_star], [res.My_star], c=GREEN, s=70,
                       zorder=6, edgecolors="white", linewidths=1.2,
                       label="Điểm tải A")
            ax.text(res.Mx_star, res.My_star, "  A", fontsize=9,
                    color=GREEN, weight="bold", va="center", zorder=7)
            # Trục qua tâm
            ax.axhline(0, color="#6B7280", linewidth=1.0, zorder=2)
            ax.axvline(0, color="#6B7280", linewidth=1.0, zorder=2)
            ax.set_xlabel("M2 (kN·m)", fontweight="bold", fontsize=10)
            ax.set_ylabel("M3 (kN·m)", fontweight="bold", fontsize=10)

            from matplotlib.lines import Line2D
            leg_elems = [
                Line2D([0], [0], color=BLUE, lw=2.2, label="Đường bao M2-M3"),
                Line2D([0], [0], marker="o", color="w", markerfacecolor=GREEN,
                       markersize=8, markeredgecolor="white", label="Điểm tải A"),
                Line2D([0], [0], marker="D", color="w", markerfacecolor=ORANGE,
                       markersize=7, markeredgecolor="white", label="Điểm giới hạn B"),
                Line2D([0], [0], color=RED, lw=1.5, ls="--", dashes=(4, 3),
                       label="Tia tải O-A-B"),
            ]
            ax.legend(handles=leg_elems, fontsize=8, loc="upper center",
                      bbox_to_anchor=(0.5, -0.22), ncol=4, frameon=False)
            ax.grid(True, color="#E5E7EB", linestyle="--",
                    linewidth=0.7, alpha=0.9)
            ax.set_axisbelow(True)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            for sp in ("left", "bottom"):
                ax.spines[sp].set_color("#9CA3AF")


        def _new_fig(parent, figsize):
            fig = Figure(figsize=figsize, dpi=100)
            cv = FigureCanvasTkAgg(fig, master=parent)
            cv.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            return fig, cv

        # Grid 2x2 trong _sum_inner
        self._sum_inner.columnconfigure(0, weight=1)
        self._sum_inner.columnconfigure(1, weight=1)
        self._sum_inner.rowconfigure(0, weight=1)
        self._sum_inner.rowconfigure(1, weight=1)

        # ===== Ô trên-trái: sơ đồ mặt cắt + thẻ thống kê =====
        f_tl = tk.Frame(self._sum_inner, bg="white", highlightbackground="#D1D5DB",
                        highlightthickness=1)
        f_tl.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        tk.Label(f_tl, text="SƠ ĐỒ MẶT CẮT TIẾT DIỆN CỘT",
                 font=("", 11, "bold"), bg="white").pack(pady=(2, 2))
        self.ck_var = tk.StringVar(value="")
        tk.Label(f_tl, textvariable=self.ck_var,
                 font=("", 10, "bold"), fg="#92400E",
                 bg="white").pack(pady=(0, 4))
        fig_sec, cv_sec = _new_fig(f_tl, (3.9, 3.1))
        a1 = fig_sec.add_subplot(111)
        draw_section_ax(a1, sec, show_stats=False)
        fig_sec.tight_layout()
        cv_sec.draw()
        self._sec_fig, self._sec_canvas, self._sec_ax = fig_sec, cv_sec, a1
        self._sec_card_vars = self._build_section_cards(f_tl, sec, inp)

        # ===== Ô trên-phải: bảng thông số tính toán =====
        f_tr = tk.Frame(self._sum_inner, bg="white",
                        highlightbackground="#D1D5DB", highlightthickness=1)
        f_tr.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        self._build_param_table(f_tr, inp, res)

        # ===== Ô dưới-trái: header + biểu đồ N-M =====
        f_bl = ttk.Frame(self._sum_inner)
        f_bl.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._build_nm_header(f_bl, res)
        fig_nm, cv_nm = _new_fig(f_bl, (3.9, 2.9))
        self._nm_fig = fig_nm
        a3 = fig_nm.add_subplot(111)
        _nm_alpha_ax(a3)
        fig_nm.tight_layout()
        fig_nm.subplots_adjust(bottom=0.30)
        cv_nm.draw()

        # ===== Ô dưới-phải: header + biểu đồ M2-M3 =====
        f_br = ttk.Frame(self._sum_inner)
        f_br.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        self._build_m2m3_header(f_br, res)
        fig_mm, cv_mm = _new_fig(f_br, (3.9, 2.9))
        self._m2m3_fig = fig_mm
        a4 = fig_mm.add_subplot(111)
        _m2m3_ax(a4)
        fig_mm.tight_layout()
        fig_mm.subplots_adjust(bottom=0.34)
        cv_mm.draw()

        # ===== Hàng 3 full-width: chi tiết biểu đồ N-M =====
        f_notes = ttk.Frame(self._sum_inner, style="Card.TLabelframe")
        f_notes.grid(row=2, column=0, columnspan=2, sticky="ew",
                     padx=4, pady=(4, 12))
        self._build_nm_notes(f_notes, inp, res)

        # ===== Hàng 4 full-width: tóm tắt thép đai =====
        f_sw = ttk.Frame(self._sum_inner, style="Card.TLabelframe")
        f_sw.grid(row=3, column=0, columnspan=2, sticky="ew",
                  padx=4, pady=4)
        self._build_stirrup_summary(f_sw, inp, res)
        self._sum_inner.rowconfigure(3, weight=0)

        self._sum_inner.rowconfigure(2, weight=0)
        # Gắn lại cuộn chuột cho các widget mới (kể cả hình matplotlib)
        self._bind_wheel(self._sum_inner, self._sum_canvas)
        # Đẩy nội dung lên đầu sau khi layout xong (xóa vùng trống)
        def _to_top():
            try:
                self._sum_inner.update_idletasks()
                self._sum_canvas.configure(
                    scrollregion=self._sum_canvas.bbox("all"))
                self._sum_canvas.yview_moveto(0)
            except Exception:
                pass
        self._sum_canvas.after_idle(_to_top)

def main():
    app = App()
    app._refresh_rebar()
    app.mainloop()


if __name__ == "__main__":
    main()
