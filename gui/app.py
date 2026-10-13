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
        ttk.Button(data_bar, text="💾 SAVE",
                   command=self.on_save_data).pack(side=tk.LEFT, expand=True,
                                                   fill=tk.X, padx=(0, 2))
        ttk.Button(data_bar, text="💾 SAVE AS",
                   command=self.on_save_as_data).pack(side=tk.LEFT,
                                                      expand=True, fill=tk.X,
                                                      padx=(2, 2))
        ttk.Button(data_bar, text="📂 OPEN",
                   command=self.on_load_data).pack(side=tk.LEFT, expand=True,
                                                   fill=tk.X, padx=(2, 0))
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

        # Layout 2x2 cố định: không còn dropdown chọn biểu đồ
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
        self.var_export_table = tk.BooleanVar(value=False)
        ttk.Checkbutton(calc_bar, text="Kèm bảng tổng hợp (mục 8)",
                        variable=self.var_export_table,
                        command=self._on_toggle_table).pack(side=tk.LEFT, padx=4)
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
        self._row(f, "Cấp độ bền thép dọc", self.cb_steel, 2)
        self.cb_sw_steel = ttk.Combobox(f, values=list(STEEL_GRADES),
                                        state="readonly", width=18)
        self.cb_sw_steel.set("CB400-V")
        self._row(f, "Cấp độ bền thép đai", self.cb_sw_steel, 3)
        self.en_gs = ttk.Entry(f, width=18); self.en_gs.insert(0, "1.0")
        self._row(f, "Hệ số điều kiện làm việc thép γs", self.en_gs, 4)
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
        self.cb_kind.bind("<<ComboboxSelected>>",
                          lambda e: self._refresh_rebar_panel())
        self._row(f, "Loại tiết diện", self.cb_kind, 0)
        self.en_cx = ttk.Entry(f, width=18); self.en_cx.insert(0, "400")
        self._row(f, "Cạnh t3 (mm) — ngang", self.en_cx, 1)
        self.en_cy = ttk.Entry(f, width=18); self.en_cy.insert(0, "400")
        self._row(f, "Cạnh t2 (mm) — đứng", self.en_cy, 2)
        for w in (self.en_cx, self.en_cy):
            w.bind("<FocusOut>", lambda e: self._refresh_rebar())

    # ---- 3. Bố trí cốt thép dọc (format VietconSoft) ----
    DIAS = ["10", "12", "14", "16", "18", "20", "22", "25", "28", "32"]

    def _sec_rebar(self):
        f = self._frame("3. Bố trí cốt thép dọc")
        DIAS = self.DIAS

        # ===== Panel cho tiết diện chữ nhật =====
        self.rebar_rect = ttk.Frame(f)
        self.rebar_rect.grid(row=0, column=0, columnspan=2, sticky=tk.EW)
        rr = self.rebar_rect
        r = 0
        self.sp_cover = ttk.Spinbox(rr, from_=15, to=100, width=8)
        self.sp_cover.set("30")
        self._row(rr, "Lớp bê tông bảo vệ cốt dọc c (mm)", self.sp_cover, r)
        r += 1
        self.cb_corner_dia = ttk.Combobox(rr, values=DIAS, state="readonly",
                                          width=8)
        self.cb_corner_dia.set("20")
        self._row(rr, "4 thanh thép góc", self.cb_corner_dia, r)
        r += 1
        # Thép cạnh t2: số thanh + đường kính
        fr2 = ttk.Frame(rr)
        self.sp_e2n = ttk.Spinbox(fr2, from_=0, to=20, width=5)
        self.sp_e2n.set("3")
        self.cb_e2d = ttk.Combobox(fr2, values=DIAS, state="readonly",
                                   width=5)
        self.cb_e2d.set("20")
        self.sp_e2n.pack(side=tk.LEFT)
        ttk.Label(fr2, text="thanh/mặt – d").pack(side=tk.LEFT, padx=2)
        self.cb_e2d.pack(side=tk.LEFT)
        self._row(rr, "Thép cạnh t2 (2 mặt trái/phải)", fr2, r)
        r += 1
        # Thép cạnh t3
        fr3 = ttk.Frame(rr)
        self.sp_e3n = ttk.Spinbox(fr3, from_=0, to=20, width=5)
        self.sp_e3n.set("3")
        self.cb_e3d = ttk.Combobox(fr3, values=DIAS, state="readonly",
                                   width=5)
        self.cb_e3d.set("20")
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
        self.rebar_circ.grid(row=0, column=0, columnspan=2, sticky=tk.EW)
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

        # ===== Cốt thép đai (giữ nguyên) =====
        self.en_sw_dia = ttk.Entry(f, width=18); self.en_sw_dia.insert(0, "8")
        self._row(f, "Đai: đường kính (mm)", self.en_sw_dia, 1)
        self.en_sw_s = ttk.Entry(f, width=18); self.en_sw_s.insert(0, "200")
        self._row(f, "Đai: bước đai s (mm)", self.en_sw_s, 2)
        self.en_sw_legs = ttk.Entry(f, width=18); self.en_sw_legs.insert(0, "2")
        self._row(f, "Đai: số nhánh", self.en_sw_legs, 3)
        self.rebar_info = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.rebar_info, font=("", 10),
                  justify=tk.LEFT).grid(row=4, column=0, columnspan=2,
                                        padx=4, pady=4, sticky=tk.W)
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
        self.en_Q2 = ttk.Entry(self.manual_frame, width=18)
        self.en_Q2.insert(0, "0")
        self._row(self.manual_frame, "Lực cắt Q2 (kN)",
                  self.en_Q2, 3)
        self.en_Q3 = ttk.Entry(self.manual_frame, width=18)
        self.en_Q3.insert(0, "0")
        self._row(self.manual_frame, "Lực cắt Q3 (kN)",
                  self.en_Q3, 4)
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
        # 3 nút Import từ Etabs: giãn đều theo cửa sổ như SAVE/SAVE AS/OPEN
        btn_row = ttk.Frame(self.etabs_frame)
        btn_row.grid(row=0, column=0, columnspan=3, sticky=tk.EW,
                     padx=4, pady=4)
        ttk.Button(btn_row, text="📂 Chọn file Excel",
                   command=self.on_import_etabs).pack(
                       side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        ttk.Button(btn_row, text="📋 Paste từ Clipboard",
                   command=self.on_paste_etabs).pack(
                       side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(btn_row, text="🗑️ Xóa nội lực",
                   command=self.on_delete_forces).pack(
                       side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        # Luôn chỉ tính tổ hợp (Combination) - bỏ checkbox theo yêu cầu
        self.etabs_info = tk.StringVar(value="Chưa chọn file.")
        ttk.Label(self.etabs_frame, textvariable=self.etabs_info,
                  foreground="#0a4d8c", wraplength=360,
                  justify=tk.LEFT).grid(row=3, column=0, columnspan=2,
                                        padx=4, sticky=tk.W)
        # Bảng kết quả (gọn cho panel trái)
        cols = ("case", "N", "Mx", "My", "dc", "kl")
        self.etabs_tree = ttk.Treeview(self.etabs_frame, columns=cols,
                                       show="headings", height=12)
        self.etabs_tree.bind("<Double-1>", self._edit_etabs_cell)
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
        # Lưu kết quả tất cả tổ hợp cho mục 8
        self._batch_rows = rows
        # hiện thuyết minh của tổ hợp nguy hiểm nhất
        inp_w = self.collect()
        inp_w.N, inp_w.Mx, inp_w.My = worst_f.N, worst_f.Mx, worst_f.My
        # Lực cắt: lấy từ combo có |Q| lớn nhất (độc lập với combo N-M)
        f_q2 = max(self.etabs_forces, key=lambda f: abs(f.Q2))
        f_q3 = max(self.etabs_forces, key=lambda f: abs(f.Q3))
        inp_w.Q2, inp_w.Q3 = f_q2.Q2, f_q3.Q3
        shear_info = {
            "q2": {"case": f_q2.case, "station": f_q2.station, "Q": f_q2.Q2},
            "q3": {"case": f_q3.case, "station": f_q3.station, "Q": f_q3.Q3},
        }
        res_w = check_column(inp_w, n_angles=24)
        sec_w = build_section(inp_w)
        batch = getattr(self, "_batch_rows", None)
        if not getattr(self, "var_export_table", None) or \
                not self.var_export_table.get():
            batch = None
        case_info = {"case": worst_f.case, "station": worst_f.station,
                     "N": worst_f.N, "M2": worst_f.Mx, "M3": worst_f.My}
        self._render_report_sections(
            generate_report_sections(inp_w, res_w, batch_rows=batch,
                                     case_info=case_info,
                                     shear_info=shear_info),
            sec_w, inp_w, res_w)
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
            sec, inp, res)
        self._pdf_batch = batch

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
            export_pdf(self._pdf_inp, self._pdf_res, path,
                       batch_rows=getattr(self, "_pdf_batch", None),
                       case_info=getattr(self, "_pdf_case", None),
                       shear_info=getattr(self, "_pdf_shear", None))
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
            self.sp_cover.set(d.get("cover", "30"))
            # Cốt thép dọc kiểu mới (fallback về field cũ nếu file cũ)
            self.cb_corner_dia.set(d.get("corner_dia", d.get("dia", "20")))
            self.sp_e2n.set(d.get("e2n", str(max(0, int(d.get("ny", 3)) - 2))))
            self.cb_e2d.set(d.get("e2d", d.get("dia", "20")))
            self.sp_e3n.set(d.get("e3n", str(max(0, int(d.get("nx", 3)) - 2))))
            self.cb_e3d.set(d.get("e3d", d.get("dia", "20")))
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
            se(self.en_sw_s, d.get("sw_s", "200"))
            se(self.en_sw_legs, d.get("sw_legs", "2"))
            se(self.en_Lx, d.get("Lx", "4.0")); se(self.en_Ly, d.get("Ly", "4.0"))
            self.cb_tx.set(d.get("top_x", "Ngàm")); self.cb_bx.set(d.get("bot_x", "Ngàm"))
            self.cb_ty.set(d.get("top_y", "Ngàm")); self.cb_by.set(d.get("bot_y", "Ngàm"))
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
            messagebox.showinfo("Lưu dữ liệu", f"Đã lưu: {path}")

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
            messagebox.showinfo("Mở dữ liệu", f"Đã nạp: {path}")
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
                from rc_column.pdf_export import interaction_image, m2m3_image
                # 2 biểu đồ như tab Tóm tắt: N-M full (trái), M2-M3 (phải)
                img_m6 = (interaction_image(sec, inp, res, width_in=4.0,
                                            dpi=100),
                          m2m3_image(sec, inp, res, width_in=4.0, dpi=100))
            except Exception:
                pass

        for num in sorted(sections.keys()):
            info = sections[num]
            if num == 2 and img_map.get(2):
                # Gộp mục 2+3: text 2 mục bên trái, ảnh bên phải
                info23 = {"segs": info["segs"] + sections[3]["segs"]}
                self._insert_side_by_side(num, info23, img_map[2])
            elif num == 3:
                # Đã gộp vào mục 2, bỏ qua
                continue
            elif num == 6 and img_m6:
                self._insert_charts_fullwidth(num, info, img_m6)
            else:
                # Hiển thị text thường
                for text, tags in info["segs"]:
                    t.insert(tk.END, self._clean_math(text), tags if tags else ())
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
            left_txt.insert(tk.END, self._clean_math(text), tags if tags else ())
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
        t.insert(tk.END, "\n")

    def _insert_charts_fullwidth(self, num, info, pngs: tuple):
        """Mục 6: text full-width, 2 biểu đồ cạnh nhau bên dưới."""
        import base64
        from tkinter import PhotoImage
        t = self.calc_text
        # Text full-width
        for text, tags in info["segs"]:
            t.insert(tk.END, self._clean_math(text), tags if tags else ())
        t.insert(tk.END, "\n")
        # 2 biểu đồ cạnh nhau như tab Tóm tắt: N-M trái, M2-M3 phải
        frame = tk.Frame(t, bg="white")
        for png, cap in zip(pngs, ["Biểu đồ N-M (góc α)",
                                   "Biểu đồ M2-M3 (tại N)"]):
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
        t.insert(tk.END, "Hình 2. Biểu đồ M2-M3 và N-M (góc α)\n", "sec_ref")
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
        import math
        sec, inp, res = self._last_sec, self._last_inp, self._last_res
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
                       label="Điểm tải trọng")
            ax.text(Ma, res.N, "  A", fontsize=9, color=GREEN,
                    weight="bold", va="center", zorder=7)
            ax.text(lim[1], lim[0], "  B", fontsize=9, color=ORANGE,
                    weight="bold", va="center", zorder=7)
            ax.set_xlabel("Mα (kN·m)", fontweight="bold", fontsize=10)
            ax.set_ylabel("N (kN)", fontweight="bold", fontsize=10)
            ax.text(0.05, 0.95, f"α = {alpha_deg:.1f}°",
                    transform=ax.transAxes, fontsize=9, color="#4B5563",
                    va="top", ha="left",
                    bbox=dict(boxstyle="round,pad=0.3", fc="white",
                              ec="#E5E7EB", alpha=0.9))
            ax.legend(fontsize=8, loc="upper center",
                      bbox_to_anchor=(0.5, -0.22), ncol=2, frameon=False)
            ax.grid(True, color="#E5E7EB", linestyle="--",
                    linewidth=0.7, alpha=0.9)
            ax.set_axisbelow(True)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            for sp in ("left", "bottom"):
                ax.spines[sp].set_color("#9CA3AF")
            ax.text(0.5, -0.52, f"Tỉ số an toàn FS = {res.fs:.2f}",
                    transform=ax.transAxes, ha="center", fontsize=10,
                    color="darkred", weight="bold")

        def _plot_3d(ax3d):
            # Mặt tương tác 3D: wireframe xám + mặt xanh lá mờ
            GREEN, RED, ORANGE = "#059669", "#DC2626", "#F97316"
            cap = BiaxialCapacity(sec, model=inp.concrete_model, n_angles=24)
            n_vals, th_vals, mxg, myg = cap.surface_grid(n_n=25, n_angles=48)
            N3, _ = np.meshgrid(n_vals, th_vals, indexing="ij")
            # Đóng kín mặt: thêm cột đầu vào cuối (fill góc thiếu)
            mxg = np.concatenate([mxg, mxg[:, :1]], axis=1)
            myg = np.concatenate([myg, myg[:, :1]], axis=1)
            N3 = np.concatenate([N3, N3[:, :1]], axis=1)
            # Wireframe xám nhạt
            ax3d.plot_wireframe(mxg, myg, N3, color="#D1D5DB",
                                linewidth=0.4, alpha=0.5, rstride=2,
                                cstride=2)
            # Mặt xanh lá mờ
            ax3d.plot_surface(mxg, myg, N3, alpha=0.35, color=GREEN,
                              edgecolor="none", shade=True)
            # Điểm B (giới hạn) và A (tải trọng)
            ax3d.scatter([res.Bx], [res.By], [res.BN], c=ORANGE, s=60,
                         edgecolors="white", linewidths=1.0, depthshade=False)
            ax3d.scatter([res.Mx_star], [res.My_star], [res.N], c=GREEN,
                         s=60, edgecolors="white", linewidths=1.0,
                         label="Điểm tải trọng", depthshade=False)
            # Nét đứt đỏ từ tâm qua A tới B
            ax3d.plot([0, res.Bx * 1.1], [0, res.By * 1.1],
                      [0, res.BN * 1.1], color=RED, ls="--", lw=1.5)
            ax3d.set_xlabel("M2 (kN·m)", fontsize=9)
            ax3d.set_ylabel("M3 (kN·m)", fontsize=9)
            ax3d.set_zlabel("N (kN)", fontsize=9)
            ax3d.set_title("Mặt tương tác 3D N-M2-M3", fontsize=12)
            # Nền trắng, lưới nhạt
            ax3d.xaxis.pane.fill = False
            ax3d.yaxis.pane.fill = False
            ax3d.zaxis.pane.fill = False
            ax3d.grid(True, alpha=0.25)

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
                       label="Điểm tải trọng")
            ax.text(res.Mx_star, res.My_star, "  A", fontsize=9,
                    color=GREEN, weight="bold", va="center", zorder=7)
            # Trục qua tâm
            ax.axhline(0, color="#6B7280", linewidth=1.0, zorder=2)
            ax.axvline(0, color="#6B7280", linewidth=1.0, zorder=2)
            ax.set_xlabel("M2 (kN·m)", fontweight="bold", fontsize=10)
            ax.set_ylabel("M3 (kN·m)", fontweight="bold", fontsize=10)
            ax.set_title(f"M2-M3 (tại N = {res.N:.0f} kN)", fontsize=12)
            ax.legend(fontsize=8, loc="upper center",
                      bbox_to_anchor=(0.5, -0.22), ncol=2, frameon=False)
            ax.grid(True, color="#E5E7EB", linestyle="--",
                    linewidth=0.7, alpha=0.9)
            ax.set_axisbelow(True)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            for sp in ("left", "bottom"):
                ax.spines[sp].set_color("#9CA3AF")
            ax.set_aspect("equal", adjustable="datalim")
            ax.text(0.5, -0.52, f"Tỉ số an toàn FS = {res.fs:.2f}",
                    transform=ax.transAxes, ha="center", fontsize=10,
                    color="darkred", weight="bold")

        from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
        import numpy as np
        self.fig.set_size_inches(8.0, 8.5)
        gs = self.fig.add_gridspec(2, 2, hspace=0.45)
        # Hàng 1: Sơ đồ mặt cắt | Biểu đồ 3D
        a1 = self.fig.add_subplot(gs[0, 0])
        draw_section_ax(a1, sec)
        a2 = self.fig.add_subplot(gs[0, 1], projection="3d")
        _plot_3d(a2)
        # Hàng 2: Biểu đồ N-M | Biểu đồ M2-M3 tại N
        a3 = self.fig.add_subplot(gs[1, 0])
        _nm_alpha_ax(a3)
        a4 = self.fig.add_subplot(gs[1, 1])
        _m2m3_ax(a4)
        self.fig.tight_layout()
        # Chừa chỗ dưới cho legend + dòng "Tỉ số an toàn"
        self.fig.subplots_adjust(bottom=0.38)
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
