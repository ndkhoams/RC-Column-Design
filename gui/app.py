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
        self.geometry("1220x780")
        self._build()

    # ============================ UI ============================
    def _build(self):
        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # ---- Trái: nhập liệu (cuộn được) ----
        left_outer = ttk.Frame(main)
        main.add(left_outer, weight=1)
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
        ttk.Button(data_bar, text="💾 Lưu dữ liệu",
                   command=self.on_save_data).pack(side=tk.LEFT, expand=True,
                                                   fill=tk.X, padx=(0, 4))
        ttk.Button(data_bar, text="📂 Mở dữ liệu",
                   command=self.on_load_data).pack(side=tk.LEFT, expand=True,
                                                   fill=tk.X, padx=(4, 0))
        ttk.Button(bottom_bar, text="KIỂM TRA KHẢ NĂNG CHỊU LỰC",
                   command=self.on_check).pack(fill=tk.X, padx=8, pady=8,
                                               ipady=8)
        # Cuộn chuột trên cụm nút cố định -> cuộn vùng nhập liệu
        self._bind_wheel(bottom_bar, self._left_canvas)

        # ---- Phải: kết quả ----
        right = ttk.Frame(main)
        main.add(right, weight=1)
        self.result_var = tk.StringVar(value="Chưa có kết quả")
        ttk.Label(right, textvariable=self.result_var,
                  font=("", 12, "bold")).pack(pady=4)
        ttk.Label(right, text="Nhập dữ liệu và chọn Kiểm tra khả năng chịu lực "
                              "để xem kết quả.",
                  foreground="gray").pack()

        nb = ttk.Notebook(right)
        nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.tab_sum = ttk.Frame(nb); nb.add(self.tab_sum, text="Tóm tắt")
        self.tab_calc = ttk.Frame(nb); nb.add(self.tab_calc, text="Thuyết minh tính toán")

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

        # Chọn loại biểu đồ (trên cùng)
        plot_bar = ttk.Frame(self._sum_inner)
        plot_bar.pack(fill=tk.X, padx=4, pady=2)
        ttk.Label(plot_bar, text="Biểu đồ:").pack(side=tk.LEFT, padx=4)
        self.cb_plot = ttk.Combobox(plot_bar, state="readonly", width=28,
                                    values=["N-M (2 phương)", "M2-M3 (tại N)",
                                            "3D (N-M2-M3)"])
        self.cb_plot.set("N-M (2 phương)")
        self.cb_plot.pack(side=tk.LEFT, padx=4)
        self.cb_plot.bind("<<ComboboxSelected>>", lambda e: self._redraw())
        if HAS_MPL:
            self.fig = Figure(figsize=(6.5, 8.0), dpi=100)
            self.mpl = FigureCanvasTkAgg(self.fig, master=self._sum_inner)
            self.mpl.get_tk_widget().pack(fill=tk.X)
        # cuộn chuột cho tab Tóm tắt (đệ quy, trừ combobox đang mở)
        self._bind_wheel(self._sum_inner, self._sum_canvas)
        # lưu để vẽ lại khi đổi loại
        self._last_sec = None
        self._last_inp = None
        self._last_res = None

        # Thanh công cụ thuyết minh
        calc_bar = ttk.Frame(self.tab_calc)
        calc_bar.pack(fill=tk.X, padx=4, pady=(4, 0))
        ttk.Button(calc_bar, text="🖨️ Xuất PDF thuyết minh",
                   command=self.on_export_pdf).pack(side=tk.LEFT, padx=4)
        # Cuộn chuột trên thanh nút Xuất PDF -> cuộn text thuyết minh
        self._bind_wheel_to_calc(calc_bar)
        # Khung text + thanh cuộn
        calc_frame = ttk.Frame(self.tab_calc)
        calc_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        calc_scroll = ttk.Scrollbar(calc_frame)
        calc_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.calc_text = tk.Text(calc_frame, wrap=tk.WORD,
                                 font=("", 10),
                                 yscrollcommand=calc_scroll.set)
        self.calc_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        calc_scroll.config(command=self.calc_text.yview)
        self.calc_text.insert(tk.END,
                              "Chi tiết tính toán sẽ hiển thị sau khi thực hiện kiểm tra.")
        # Cuộn chuột mượt cho thuyết minh (2 dòng/nấc thay vì mặc định)
        self.calc_text.bind("<MouseWheel>", self._on_calc_wheel)
        self.calc_text.bind("<Button-4>", self._on_calc_wheel)
        self.calc_text.bind("<Button-5>", self._on_calc_wheel)

    def _on_calc_wheel(self, event):
        """Cuộn thuyết minh mượt hơn: bước nhỏ 2 units/nấc."""
        if getattr(event, "num", None) == 4:
            self.calc_text.yview_scroll(-2, "units")
        elif getattr(event, "num", None) == 5:
            self.calc_text.yview_scroll(2, "units")
        else:
            delta = int(-event.delta / 120) if event.delta else 0
            self.calc_text.yview_scroll(delta * 2, "units")
        return "break"

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
        f = ttk.LabelFrame(self.left, text=title, padding=6)
        f.pack(fill=tk.X, padx=8, pady=6)
        return f

    def _row(self, parent, label, widget, r, c0=0):
        ttk.Label(parent, text=label).grid(row=r, column=c0, sticky=tk.W,
                                           padx=4, pady=2)
        widget.grid(row=r, column=c0 + 1, sticky=tk.EW, padx=4, pady=2)
        parent.columnconfigure(c0 + 1, weight=1)

    # ---- 1. Vật liệu ----
    def _sec_materials(self):
        f = self._frame("1. Vật liệu")
        self.cb_conc = ttk.Combobox(f, values=list(CONCRETE_GRADES),
                                    state="readonly", width=18)
        self.cb_conc.set("B25")
        self._row(f, "Cấp độ bền bê tông", self.cb_conc, 0)
        self.en_gb = ttk.Entry(f, width=18); self.en_gb.insert(0, "0.85")
        self._row(f, "Hệ số điều kiện làm việc bê tông γb", self.en_gb, 1)
        self.cb_steel = ttk.Combobox(f, values=list(STEEL_GRADES),
                                     state="readonly", width=18)
        self.cb_steel.set("CB400-V")
        self._row(f, "Cấp độ bền thép", self.cb_steel, 2)
        self.en_gs = ttk.Entry(f, width=18); self.en_gs.insert(0, "1.0")
        self._row(f, "Hệ số điều kiện làm việc thép γs", self.en_gs, 3)
        self.cb_model = ttk.Combobox(
            f, values=["3 đoạn thẳng (MH3ĐT)", "2 đoạn thẳng (MH2ĐT)"],
            state="readonly", width=18)
        self.cb_model.set("3 đoạn thẳng (MH3ĐT)")
        self._row(f, "Mô hình bê tông", self.cb_model, 4)

    # ---- 2. Tiết diện ----
    def _sec_section(self):
        f = self._frame("2. Tiết diện")
        self.cb_kind = ttk.Combobox(f, values=["Chữ nhật", "Tròn"],
                                    state="readonly", width=18)
        self.cb_kind.set("Chữ nhật")
        self.cb_kind.bind("<<ComboboxSelected>>", lambda e: self._refresh_rebar())
        self._row(f, "Loại tiết diện", self.cb_kind, 0)
        self.en_cx = ttk.Entry(f, width=18); self.en_cx.insert(0, "400")
        self._row(f, "Cạnh t3 (mm) — ngang", self.en_cx, 1)
        self.en_cy = ttk.Entry(f, width=18); self.en_cy.insert(0, "400")
        self._row(f, "Cạnh t2 (mm) — đứng", self.en_cy, 2)
        for w in (self.en_cx, self.en_cy):
            w.bind("<FocusOut>", lambda e: self._refresh_rebar())

    # ---- 3. Bố trí cốt thép dọc ----
    def _sec_rebar(self):
        f = self._frame("3. Bố trí cốt thép dọc")
        self.en_dia = ttk.Entry(f, width=18); self.en_dia.insert(0, "20")
        self._row(f, "Đường kính (mm)", self.en_dia, 0)
        self.en_nx = ttk.Entry(f, width=18); self.en_nx.insert(0, "3")
        self._row(f, "Số thanh mỗi cạnh X", self.en_nx, 1)
        self.en_ny = ttk.Entry(f, width=18); self.en_ny.insert(0, "3")
        self._row(f, "Số thanh mỗi cạnh Y (tròn: tổng số)", self.en_ny, 2)
        self.en_cover = ttk.Entry(f, width=18); self.en_cover.insert(0, "30")
        self._row(f, "Lớp bê tông bảo vệ (mm)", self.en_cover, 3)
        for w in (self.en_dia, self.en_nx, self.en_ny, self.en_cover):
            w.bind("<FocusOut>", lambda e: self._refresh_rebar())
        self.rebar_info = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.rebar_info, font=("", 10),
                  justify=tk.LEFT).grid(row=4, column=0, columnspan=2,
                                        padx=4, pady=4, sticky=tk.W)

    # ---- 4. Chiều dài tính toán ----
    def _sec_stability(self):
        f = self._frame("4. Chiều dài tính toán")
        hdr = ["Tham số", "Trục 2", "Trục 3"]
        for c, h in enumerate(hdr):
            ttk.Label(f, text=h, font=("", 9, "bold")).grid(
                row=0, column=c, padx=4, pady=2, sticky=tk.W)
        bn = list(BOUNDARY_NAMES.values())
        self.en_Lx = ttk.Entry(f, width=12); self.en_Lx.insert(0, "4.0")
        self.en_Ly = ttk.Entry(f, width=12); self.en_Ly.insert(0, "4.0")
        self.cb_tx = ttk.Combobox(f, values=bn, state="readonly", width=10)
        self.cb_tx.set("Ngàm")
        self.cb_bx = ttk.Combobox(f, values=bn, state="readonly", width=10)
        self.cb_bx.set("Ngàm")
        self.cb_ty = ttk.Combobox(f, values=bn, state="readonly", width=10)
        self.cb_ty.set("Ngàm")
        self.cb_by = ttk.Combobox(f, values=bn, state="readonly", width=10)
        self.cb_by.set("Ngàm")
        self.en_psix = ttk.Entry(f, width=12)
        self.en_psiy = ttk.Entry(f, width=12)
        rows = [
            ("Chiều dài cột L (m)", self.en_Lx, self.en_Ly),
            ("Liên kết đầu trên", self.cb_tx, self.cb_ty),
            ("Liên kết đầu dưới", self.cb_bx, self.cb_by),
            ("Hệ số ψ (trống=tự tính)", self.en_psix, self.en_psiy),
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

    # ---- 5. Nội lực ----
    def _sec_loads(self):
        f = self._frame("5. Nội lực kiểm tra")
        # Chọn chế độ: nhập tay / import Excel
        self.var_load_mode = tk.StringVar(value="etabs")
        mode_bar = ttk.Frame(f)
        mode_bar.grid(row=0, column=0, columnspan=2, sticky=tk.W,
                      padx=4, pady=4)
        ttk.Radiobutton(mode_bar, text="Nhập tay",
                        variable=self.var_load_mode, value="manual",
                        command=self._toggle_load_mode).pack(side=tk.LEFT,
                                                            padx=6)
        ttk.Radiobutton(mode_bar, text="Import Excel ETABS",
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
        self.var_lt = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.manual_frame, text="Khai báo thành phần tải dài hạn",
                        variable=self.var_lt,
                        command=self._toggle_lt).grid(row=3, column=0,
                                                     columnspan=2, sticky=tk.W,
                                                     padx=4, pady=4)
        self.lt_frame = ttk.Frame(self.manual_frame)
        self.lt_frame.grid(row=4, column=0, columnspan=2, sticky=tk.EW, padx=4)
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
        ttk.Button(self.etabs_frame, text="📂 Chọn file Excel ETABS...",
                   command=self.on_import_etabs).grid(row=0, column=0,
                                                     padx=4, pady=4, sticky=tk.W)
        ttk.Label(self.etabs_frame,
                  text="M2, M3 trong Excel map thẳng vào M2, M3 kiểm tra.",
                  foreground="gray", font=("", 8)).grid(
                      row=1, column=0, columnspan=2, sticky=tk.W, padx=4)
        self.var_comb = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.etabs_frame, text="Chỉ tổ hợp (Combination)",
                        variable=self.var_comb).grid(row=2, column=0,
                                                    columnspan=2, sticky=tk.W,
                                                    padx=4)
        self.etabs_info = tk.StringVar(value="Chưa chọn file.")
        ttk.Label(self.etabs_frame, textvariable=self.etabs_info,
                  foreground="#0a4d8c", wraplength=360,
                  justify=tk.LEFT).grid(row=3, column=0, columnspan=2,
                                        padx=4, sticky=tk.W)
        # Bảng kết quả (gọn cho panel trái)
        cols = ("case", "N", "Mx", "My", "dc", "kl")
        self.etabs_tree = ttk.Treeview(self.etabs_frame, columns=cols,
                                       show="headings", height=12)
        hd = {"case": "Tổ hợp", "N": "N", "Mx": "M2", "My": "M3",
              "dc": "D/C", "kl": "KQ"}
        wd = {"case": 80, "N": 65, "Mx": 65, "My": 65, "dc": 55, "kl": 60}
        for c in cols:
            self.etabs_tree.heading(c, text=hd[c])
            self.etabs_tree.column(c, width=wd[c], anchor=tk.CENTER)
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
        return ColumnInput(
            concrete_grade=self.cb_conc.get(), gamma_b=self._f(self.en_gb, 0.85),
            steel_grade=self.cb_steel.get(), gamma_s=self._f(self.en_gs, 1.0),
            concrete_model=model,
            section_type="rect" if is_rect else "circle",
            cx=self._f(self.en_cx, 400.0), cy=self._f(self.en_cy, 400.0),
            bar_dia=self._f(self.en_dia, 20.0),
            nx=max(2, int(self._f(self.en_nx, 3))),
            ny=max(2, int(self._f(self.en_ny, 3))),
            n_bars=max(4, int(self._f(self.en_ny, 8))),
            cover=self._f(self.en_cover, 30.0),
        )

    def _refresh_rebar(self):
        """Cập nhật thống kê thép kiểu VietconSoft khi đổi tiết diện/thép."""
        try:
            inp = self._draft_input()
            sec = build_section(inp)
        except Exception:
            return
        n = len(sec.rebars)
        dias = sorted(set(r.dia for r in sec.rebars))
        dia_txt = "/".join(f"{d:.0f}" for d in dias)
        ccx, ccy = clear_spacing(sec)
        # khoảng cách tim = khoảng hở + đường kính trung bình
        d_avg = sum(dias) / len(dias) if dias else 0
        lines = [
            f"{n} thanh d{dia_txt}",
            f"Tổng As {sec.steel_area:.0f} mm²",
            f"Hàm lượng μ {sec.reinforcement_ratio * 100:.2f}%",
        ]
        if math.isfinite(ccx):
            lines.append(f"Khoảng hở thông thủy: t3 = {ccx:.1f} mm, "
                         f"t2 = {ccy:.1f} mm")
            lines.append(f"Khoảng cách tim: t3 = {ccx + d_avg:.1f} mm, "
                         f"t2 = {ccy + d_avg:.1f} mm")
        self.rebar_info.set("\n".join(lines))

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
                                      sec, inp, res)
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

    def _load_etabs_file(self, path: str) -> bool:
        """Nạp file Excel ETABS (dùng chung cho import tay và mở dữ liệu)."""
        try:
            from rc_column.etabs_import import read_etabs_excel
            forces = read_etabs_excel(
                path, only_combinations=self.var_comb.get())
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
        for f, r in rows:
            dc = r["dc"] if r else None
            vals = (f"{f.case}@{f.station:.2f}",
                    f"{f.N:.0f}", f"{f.Mx:.0f}", f"{f.My:.0f}",
                    f"{dc:.3f}" if dc is not None and dc == dc else "—",
                    ("NG" if dc and dc > 1 else
                     "ĐẠT" if dc else "—"))
            tag = ()
            if r and dc == dc:
                tag = ("ng",) if dc > 1 else ()
            t.insert("", tk.END, values=vals, tags=tag)

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
        bc = BatchChecker(inp, n_angles=12)
        rows = []
        for f in self.etabs_forces:
            r = bc.check_one(f.N, f.Mx, f.My, inp.long_term)
            rows.append((f, r))
        # sắp xếp theo D/C giảm dần (nguy hiểm nhất lên đầu)
        rows.sort(key=lambda x: -(x[1]["dc"]) if x[1]["dc"] == x[1]["dc"]
                  else float("inf"))
        # highlight dòng nguy hiểm nhất (dòng đầu sau sắp xếp)
        self._fill_etabs_table(rows)
        worst_f, worst_r = rows[0]
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
        # hiện thuyết minh của tổ hợp nguy hiểm nhất
        inp_w = self.collect()
        inp_w.N, inp_w.Mx, inp_w.My = worst_f.N, worst_f.Mx, worst_f.My
        res_w = check_column(inp_w, n_angles=24)
        sec_w = build_section(inp_w)
        self._render_report_sections(generate_report_sections(inp_w, res_w),
                                      sec_w, inp_w, res_w)
        self._pdf_inp, self._pdf_res = inp_w, res_w
        # cập nhật cả tab Tóm tắt + biểu đồ cho tổ hợp nguy hiểm nhất
        self._show_summary(sec_w, inp_w, res_w,
                           prefix=f"Tổ hợp {worst_f.case}@{worst_f.station:.2f}m: ")
        self.result_var.set(
            f"Tổ hợp nguy hiểm nhất: {worst_f.case} — "
            f"{'KHÔNG ĐẠT ✗' if worst_r['dc'] > 1 else 'ĐẠT ✓'} "
            f"(D/C = {worst_r['dc']:.3f})")

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

    def on_export_pdf(self):
        """Xuất thuyết minh ra PDF."""
        if not getattr(self, "_pdf_inp", None):
            messagebox.showinfo("Xuất PDF", "Hãy kiểm tra trước khi xuất PDF.")
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            title="Lưu thuyết minh PDF",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="ThuyetMinhCotBTCT.pdf")
        if not path:
            return
        try:
            from rc_column.pdf_export import export_pdf
            export_pdf(self._pdf_inp, self._pdf_res, path)
            messagebox.showinfo("Xuất PDF", f"Đã lưu: {path}")
        except Exception as ex:
            messagebox.showerror("Lỗi xuất PDF", str(ex))

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
            "steel": self.cb_steel.get(), "gamma_s": ev(self.en_gs),
            "model": self.cb_model.get(),
            # 2. Tiết diện
            "kind": self.cb_kind.get(),
            "cx": ev(self.en_cx), "cy": ev(self.en_cy),
            "cover": ev(self.en_cover),
            # 3. Cốt thép
            "dia": ev(self.en_dia), "nx": ev(self.en_nx),
            "ny": ev(self.en_ny),
            # 4. Chiều dài tính toán
            "Lx": ev(self.en_Lx), "Ly": ev(self.en_Ly),
            "top_x": self.cb_tx.get(), "bot_x": self.cb_bx.get(),
            "top_y": self.cb_ty.get(), "bot_y": self.cb_by.get(),
            "psi_x": ev(self.en_psix), "psi_y": ev(self.en_psiy),
            # 5. Nội lực
            "load_mode": bv(self.var_load_mode),
            "N": ev(self.en_N), "Mx": ev(self.en_Mx), "My": ev(self.en_My),
            "long_term": bv(self.var_lt),
            "N_lt": ev(self.en_Nlt), "Mx_lt": ev(self.en_Mxlt),
            "My_lt": ev(self.en_Mylt),
            "etabs_path": getattr(self, "etabs_file", ""),
            "etabs_comb": bv(self.var_comb),
            # Lưu luôn nội lực đã import (không cần link lại file Excel)
            "etabs_forces": [
                {"story": f.story, "column": f.column, "case": f.case,
                 "case_type": f.case_type, "station": f.station,
                 "N": f.N, "Mx": f.Mx, "My": f.My}
                for f in getattr(self, "etabs_forces", [])
            ],
        }

    def _apply_data(self, d: dict):
        """Đổ dữ liệu từ dict vào các trường nhập liệu."""
        def se(e, v):
            e.delete(0, tk.END); e.insert(0, str(v))
        try:
            self.cb_conc.set(d.get("concrete", "B25")); se(self.en_gb, d.get("gamma_b", "0.85"))
            self.cb_steel.set(d.get("steel", "CB400-V")); se(self.en_gs, d.get("gamma_s", "1.0"))
            self.cb_model.set(d.get("model", self.cb_model.get()))
            self.cb_kind.set(d.get("kind", "Chữ nhật"))
            se(self.en_cx, d.get("cx", "400")); se(self.en_cy, d.get("cy", "400"))
            se(self.en_cover, d.get("cover", "30"))
            se(self.en_dia, d.get("dia", "20")); se(self.en_nx, d.get("nx", "3"))
            se(self.en_ny, d.get("ny", "3"))
            se(self.en_Lx, d.get("Lx", "4.0")); se(self.en_Ly, d.get("Ly", "4.0"))
            self.cb_tx.set(d.get("top_x", "Ngàm")); self.cb_bx.set(d.get("bot_x", "Ngàm"))
            self.cb_ty.set(d.get("top_y", "Ngàm")); self.cb_by.set(d.get("bot_y", "Ngàm"))
            se(self.en_psix, d.get("psi_x", "")); se(self.en_psiy, d.get("psi_y", ""))
            self.var_load_mode.set(d.get("load_mode", "etabs"))
            se(self.en_N, d.get("N", "")); se(self.en_Mx, d.get("Mx", ""))
            se(self.en_My, d.get("My", ""))
            self.var_lt.set(bool(d.get("long_term", False)))
            se(self.en_Nlt, d.get("N_lt", "")); se(self.en_Mxlt, d.get("Mx_lt", ""))
            se(self.en_Mylt, d.get("My_lt", ""))
            self.var_comb.set(bool(d.get("etabs_comb", True)))
            self.etabs_file = d.get("etabs_path", "")
            # cập nhật giao diện theo chế độ
            self._toggle_load_mode()
            self._toggle_lt()
            self._refresh_rebar()
        except Exception as ex:
            messagebox.showerror("Lỗi", f"Không đọc được file dữ liệu: {ex}")

    def on_save_data(self):
        """Lưu dữ liệu nhập liệu ra file JSON."""
        import json
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            title="Lưu dữ liệu cột",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="CotBTCT.json")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._collect_data(), f, ensure_ascii=False,
                          indent=2)
            messagebox.showinfo("Lưu dữ liệu", f"Đã lưu: {path}")
        except Exception as ex:
            messagebox.showerror("Lỗi", str(ex))

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
            messagebox.showinfo("Mở dữ liệu", f"Đã nạp: {path}")
        except Exception as ex:
            messagebox.showerror("Lỗi", str(ex))

    def _render_report(self, segs):
        """Hiển thị thuyết minh với format VietconSoft (giữ để tương thích)."""
        t = self.calc_text
        t.delete("1.0", tk.END)
        self._setup_report_tags(t)
        for text, tags in segs:
            t.insert(tk.END, text, tags if tags else ())
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

    def _render_report_sections(self, sections, sec, inp, res):
        """Hiển thị thuyết minh theo từng mục; mục 2 & 6: text trái, hình phải."""
        import base64
        from tkinter import PhotoImage
        from rc_column.pdf_export import section_image, interaction_image
        t = self.calc_text
        t.delete("1.0", tk.END)
        self._setup_report_tags(t)
        self._report_images = []
        self._report_frames = []  # giữ tham chiếu frame nhúng

        # Tiêu đề chung (nằm ngoài sections)
        t.insert(tk.END, "THUYẾT MINH TÍNH TOÁN KIỂM TRA CỘT BTCT\n",
                 "title")
        t.insert(tk.END,
                 "Tiêu chuẩn: TCVN 5574:2018 — Mô hình biến dạng phi tuyến "
                 "(Điều 8.1.2.7)\n\n", "sec_ref")

        # Ảnh cho mục 2 (side-by-side) và mục 6 (2 biểu đồ lớn)
        img_map = {}
        img_m6 = ()
        if HAS_MPL:
            try:
                from rc_column.pdf_export import section_image
                img_map[2] = section_image(sec, small=True)
            except Exception:
                pass
            try:
                from rc_column.pdf_export import interaction_images
                img_m6 = interaction_images(sec, inp, res, small=True)
            except Exception:
                pass

        for num in sorted(sections.keys()):
            info = sections[num]
            if num == 2 and img_map.get(2):
                self._insert_side_by_side(num, info, img_map[2])
            elif num == 6 and img_m6:
                self._insert_charts_fullwidth(num, info, img_m6)
            else:
                # Hiển thị text thường
                for text, tags in info["segs"]:
                    t.insert(tk.END, text, tags if tags else ())
        # Phần kết quả cuối (nằm sau mục 6 trong flat segs)
        # -> lấy từ generate_report để đảm bảo đầy đủ
        from rc_column.report import generate_report, generate_report_sections
        flat = generate_report(inp, res)
        # Tìm vị trí sau mục 6: chèn phần còn lại (D/C, badge)
        # Đơn giản: tìm segment có tag 'dc'/'ok'/'ng' chưa được chèn
        # (vì sections đã bao gồm hết, ta chỉ cần đảm bảo không trùng)
        # Thực tế build_sections đã bao gồm toàn bộ -> không cần thêm

    def _insert_side_by_side(self, num, info, png: bytes):
        """Chèn mục text-trái hình-phải vào Text widget."""
        import base64
        from tkinter import PhotoImage
        t = self.calc_text
        captions = {2: "Hình 1. Mặt cắt cột và bố trí cốt thép",
                    6: "Hình 2. Biểu đồ tương tác N-M2 và N-M3"}
        # Frame chứa 2 cột
        frame = tk.Frame(t, bg="white")
        # Cột trái: text
        left_txt = tk.Text(frame, wrap=tk.WORD, font=("", 10),
                           bg="white", relief=tk.FLAT, height=14, width=52)
        self._setup_report_tags(left_txt)
        for text, tags in info["segs"]:
            left_txt.insert(tk.END, text, tags if tags else ())
        left_txt.configure(state=tk.DISABLED)
        left_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                      padx=(0, 8), anchor=tk.N)
        # Cột phải: hình
        b64 = base64.b64encode(png).decode("ascii")
        img = PhotoImage(data=b64)
        self._report_images.append(img)
        right = tk.Frame(frame, bg="white")
        tk.Label(right, image=img, bg="white").pack()
        tk.Label(right, text=captions.get(num, ""), font=("", 8),
                 fg="#64748b", bg="white", wraplength=280).pack()
        right.pack(side=tk.RIGHT, anchor=tk.N, padx=(0, 4))
        self._report_frames.append(frame)
        # Cuộn chuột trên khung nhúng -> cuộn text thuyết minh chính
        self._bind_wheel_to_calc(frame)
        t.insert(tk.END, "\n")
        t.window_create(tk.END, window=frame)
        t.insert(tk.END, "\n\n")

    def _insert_charts_fullwidth(self, num, info, pngs: tuple):
        """Mục 6: text full-width, 2 biểu đồ lớn cạnh nhau bên dưới."""
        import base64
        from tkinter import PhotoImage
        t = self.calc_text
        # Text full-width
        for text, tags in info["segs"]:
            t.insert(tk.END, text, tags if tags else ())
        t.insert(tk.END, "\n")
        # Khung 2 biểu đồ cạnh nhau
        frame = tk.Frame(t, bg="white")
        for i, (png, cap) in enumerate(
                zip(pngs, ["Biểu đồ N-M2", "Biểu đồ N-M3"])):
            b64 = base64.b64encode(png).decode("ascii")
            img = PhotoImage(data=b64)
            self._report_images.append(img)
            col = tk.Frame(frame, bg="white")
            tk.Label(col, image=img, bg="white").pack()
            tk.Label(col, text=cap, font=("", 9, "bold"),
                     fg="#0f172a", bg="white").pack()
            col.pack(side=tk.LEFT, padx=10, anchor=tk.N)
        self._report_frames.append(frame)
        self._bind_wheel_to_calc(frame)
        t.window_create(tk.END, window=frame)
        t.insert(tk.END, "\n")
        t.insert(tk.END, "Hình 2. Biểu đồ tương tác N-M2 và N-M3\n",
                 "sec_ref")
        t.insert(tk.END, "\n")

    def _bind_wheel_to_calc(self, widget):
        """Gắn cuộn chuột đệ quy cho widget nhúng -> cuộn calc_text."""
        def _rec(w):
            w.bind("<MouseWheel>", self._on_calc_wheel)
            w.bind("<Button-4>", self._on_calc_wheel)
            w.bind("<Button-5>", self._on_calc_wheel)
            for ch in w.winfo_children():
                _rec(ch)
        _rec(widget)

    def _embed_report_images(self, sec, inp, res):
        """(Không dùng nữa — giữ để tương thích, logic đã chuyển vào
        _render_report_sections.)"""
        pass

    def _redraw(self):
        """Vẽ lại theo loại biểu đồ đang chọn.

        Layout: sơ đồ mặt cắt trên, biểu đồ tương tác lớn phía dưới.
        """
        if not HAS_MPL or self._last_sec is None:
            return
        sec, inp, res = self._last_sec, self._last_inp, self._last_res
        kind = self.cb_plot.get()
        # Tạo Figure mới hoàn toàn mỗi lần vẽ -> không bao giờ sót axes cũ
        try:
            self.mpl.get_tk_widget().destroy()
        except Exception:
            pass
        self.fig = Figure(figsize=(7.0, 8.5), dpi=100)
        self.mpl = FigureCanvasTkAgg(self.fig, master=self._sum_inner)
        self.mpl.get_tk_widget().pack(fill=tk.X)
        from rc_column.pdf_export import draw_section_ax, _radial_limit
        from rc_column.interaction import (BiaxialCapacity, FiberSection,
                                           uniaxial_curve_fs)
        fs = FiberSection(sec)

        def _nm_ax(ax, th, lab, Ms, Nv, lim, fs_val, title_sz=12):
            # lim: điểm B song trục chiếu lên mặt phẳng (N, M)
            cv = uniaxial_curve_fs(fs, th, inp.concrete_model)
            # Đường cong full từ -Mmax đến +Mmax (đối xứng qua trục N)
            ax.plot([p[1] for p in cv], [p[0] for p in cv], "b-",
                    linewidth=1.5)
            ax.plot([-p[1] for p in cv], [p[0] for p in cv], "b-",
                    linewidth=1.5)
            ax.scatter([Ms], [Nv], c="red", s=90, zorder=5,
                       label="Điểm tải trọng")
            if lim:
                ax.plot([0, lim[1]], [0, lim[0]], "r--", lw=1.2, alpha=0.8)
                ax.scatter([lim[1]], [lim[0]], c="orange", s=90,
                           zorder=5, label="Giới hạn")
            ax.set_xlabel("M (kN·m)")
            ax.set_ylabel("N (kN)")
            ax.set_title(f"Biểu đồ tương tác {lab}", fontsize=title_sz)
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3)
            ax.text(0.5, -0.32, f"Tỉ số an toàn FS = {fs_val:.2f}",
                    transform=ax.transAxes, ha="center", fontsize=10,
                    color="darkred", weight="bold")

        if kind.startswith("N-M"):
            # Mặt cắt lớn trên, 2 biểu đồ cạnh nhau dưới
            self.fig.set_size_inches(7.0, 8.5)
            gs = self.fig.add_gridspec(5, 2)
            a1 = self.fig.add_subplot(gs[0:2, :])
            draw_section_ax(a1, sec)
            a1.set_title("Sơ đồ mặt cắt", fontsize=13)
            a1.grid(True, alpha=0.3)
            a2 = self.fig.add_subplot(gs[2:, 0])
            _nm_ax(a2, 0, "N-M2", res.Mx_star, res.N,
                   (res.BN, res.Bx), res.fs)
            a3 = self.fig.add_subplot(gs[2:, 1])
            _nm_ax(a3, 90, "N-M3", res.My_star, res.N,
                   (res.BN, res.By), res.fs)
        elif kind.startswith("M2-M3"):
            self.fig.set_size_inches(7.0, 8.5)
            gs = self.fig.add_gridspec(5, 1)
            a1 = self.fig.add_subplot(gs[0:2, 0])
            draw_section_ax(a1, sec)
            a1.set_title("Sơ đồ mặt cắt", fontsize=13)
            a1.grid(True, alpha=0.3)
            a2 = self.fig.add_subplot(gs[2:, 0])
            cap = BiaxialCapacity(sec, model=inp.concrete_model, n_angles=24)
            pts = cap.mx_my_curve(inp.N)
            a2.plot([p[0] for p in pts], [p[1] for p in pts], "b-",
                    linewidth=1.5, label=f"Tại N = {inp.N:.0f} kN")
            a2.scatter([inp.Mx], [inp.My], c="red", s=90, zorder=5,
                       label="Điểm tải trọng")
            a2.set_xlabel("M2 (kN·m)")
            a2.set_ylabel("M3 (kN·m)")
            a2.set_title("Tương tác M2-M3", fontsize=12)
            a2.legend(fontsize=9)
            a2.grid(True, alpha=0.3)
            a2.set_aspect("equal", adjustable="datalim")
        else:  # 3D
            from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
            self.fig.set_size_inches(7.0, 8.5)
            gs = self.fig.add_gridspec(5, 1)
            a1 = self.fig.add_subplot(gs[0:2, 0])
            draw_section_ax(a1, sec)
            a1.set_title("Sơ đồ mặt cắt", fontsize=13)
            a1.grid(True, alpha=0.3)
            a2 = self.fig.add_subplot(gs[2:, 0], projection="3d")
            cap = BiaxialCapacity(sec, model=inp.concrete_model, n_angles=24)
            n_vals, th_vals, mxg, myg = cap.surface_grid(n_n=25, n_angles=48)
            import numpy as np
            N3, _ = np.meshgrid(n_vals, th_vals, indexing="ij")
            a2.plot_surface(mxg, myg, N3, alpha=0.7, cmap="viridis",
                            edgecolor="none")
            a2.scatter([inp.Mx], [inp.My], [inp.N], c="red", s=70,
                       label="Điểm tải trọng")
            a2.set_xlabel("M2 (kN·m)")
            a2.set_ylabel("M3 (kN·m)")
            a2.set_zlabel("N (kN)")
            a2.set_title("Mặt tương tác 3D N-M2-M3", fontsize=12)
        self.fig.tight_layout()
        # Chừa chỗ dưới cho dòng "Tỉ số an toàn" (tránh đè nhãn trục)
        self.fig.subplots_adjust(bottom=0.18)
        self.mpl.draw()
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
