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
from rc_column.report import generate_report
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
        canvas = tk.Canvas(left_outer, highlightthickness=0)
        scr = ttk.Scrollbar(left_outer, orient=tk.VERTICAL, command=canvas.yview)
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

        ttk.Button(self.left, text="KIỂM TRA KHẢ NĂNG CHỊU LỰC",
                   command=self.on_check).pack(fill=tk.X, padx=8, pady=10, ipady=8)

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
        self.tab_etabs = ttk.Frame(nb); nb.add(self.tab_etabs, text="Tổ hợp ETABS")
        self._build_etabs_tab()

        self.sum_text = tk.Text(self.tab_sum, wrap=tk.WORD, font=("Consolas", 10),
                                height=10)
        self.sum_text.pack(fill=tk.X, padx=4, pady=4)
        # Chọn loại biểu đồ
        plot_bar = ttk.Frame(self.tab_sum)
        plot_bar.pack(fill=tk.X, padx=4, pady=2)
        ttk.Label(plot_bar, text="Biểu đồ:").pack(side=tk.LEFT, padx=4)
        self.cb_plot = ttk.Combobox(plot_bar, state="readonly", width=28,
                                    values=["N-M (2 phương)", "Mx-My (tại N)",
                                            "3D (N-Mx-My)"])
        self.cb_plot.set("N-M (2 phương)")
        self.cb_plot.pack(side=tk.LEFT, padx=4)
        self.cb_plot.bind("<<ComboboxSelected>>", lambda e: self._redraw())
        if HAS_MPL:
            self.fig = Figure(figsize=(5.4, 4.6), dpi=100)
            self.mpl = FigureCanvasTkAgg(self.fig, master=self.tab_sum)
            self.mpl.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        # lưu để vẽ lại khi đổi loại
        self._last_sec = None
        self._last_inp = None
        self._last_res = None

        self.calc_text = tk.Text(self.tab_calc, wrap=tk.WORD,
                                 font=("Consolas", 10))
        self.calc_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.calc_text.insert(tk.END,
                              "Chi tiết tính toán sẽ hiển thị sau khi thực hiện kiểm tra.")

    def _build_etabs_tab(self):
        """Tab import nội lực ETABS và kiểm tra tất cả tổ hợp."""
        f = self.tab_etabs
        bar = ttk.Frame(f)
        bar.pack(fill=tk.X, padx=6, pady=6)
        ttk.Button(bar, text="📂 Import Excel ETABS...",
                   command=self.on_import_etabs).pack(side=tk.LEFT, padx=4)
        ttk.Label(bar, text="Ánh xạ:").pack(side=tk.LEFT, padx=(12, 2))
        self.cb_map = ttk.Combobox(bar, state="readonly", width=16,
                                   values=["M2→Mx, M3→My", "M2→My, M3→Mx"])
        self.cb_map.set("M2→Mx, M3→My")
        self.cb_map.pack(side=tk.LEFT, padx=2)
        self.var_comb = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Chỉ tổ hợp (Combination)",
                        variable=self.var_comb).pack(side=tk.LEFT, padx=8)
        ttk.Button(bar, text="▶ Kiểm tra tất cả",
                   command=self.on_check_etabs).pack(side=tk.LEFT, padx=4)
        self.etabs_info = tk.StringVar(value="Chưa import file.")
        ttk.Label(f, textvariable=self.etabs_info,
                  foreground="#0a4d8c").pack(padx=6, pady=2, anchor=tk.W)

        cols = ("story", "col", "case", "station", "N", "Mx", "My", "dc", "kl")
        self.etabs_tree = ttk.Treeview(f, columns=cols, show="headings",
                                       height=18)
        headers = {"story": "Tầng", "col": "Cột", "case": "Tổ hợp",
                   "station": "Vị trí (m)", "N": "N (kN)",
                   "Mx": "Mx", "My": "My", "dc": "D/C", "kl": "Kết luận"}
        widths = {"story": 70, "col": 70, "case": 90, "station": 80,
                  "N": 80, "Mx": 80, "My": 80, "dc": 70, "kl": 90}
        for c in cols:
            self.etabs_tree.heading(c, text=headers[c])
            self.etabs_tree.column(c, width=widths[c], anchor=tk.CENTER)
        sb = ttk.Scrollbar(f, orient=tk.VERTICAL,
                           command=self.etabs_tree.yview)
        self.etabs_tree.configure(yscrollcommand=sb.set)
        self.etabs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                             padx=(6, 0), pady=4)
        sb.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 6), pady=4)
        self.etabs_tree.tag_configure("ng", background="#fee2e2")
        self.etabs_tree.tag_configure("worst", background="#fecaca",
                                      font=("", 9, "bold"))
        self.etabs_forces = []
        self.etabs_file = ""

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
        self.en_gb = ttk.Entry(f, width=18); self.en_gb.insert(0, "1.0")
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
        self._row(f, "Cạnh Cx (mm)", self.en_cx, 1)
        self.en_cy = ttk.Entry(f, width=18); self.en_cy.insert(0, "400")
        self._row(f, "Cạnh Cy (mm)", self.en_cy, 2)
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
        hdr = ["Tham số", "Phương X", "Phương Y"]
        for c, h in enumerate(hdr):
            ttk.Label(f, text=h, font=("", 9, "bold")).grid(
                row=0, column=c, padx=4, pady=2, sticky=tk.W)
        bn = list(BOUNDARY_NAMES.values())
        self.en_Lx = ttk.Entry(f, width=12); self.en_Lx.insert(0, "4.0")
        self.en_Ly = ttk.Entry(f, width=12); self.en_Ly.insert(0, "4.0")
        self.cb_tx = ttk.Combobox(f, values=bn, state="readonly", width=10)
        self.cb_tx.set("Khớp")
        self.cb_bx = ttk.Combobox(f, values=bn, state="readonly", width=10)
        self.cb_bx.set("Khớp")
        self.cb_ty = ttk.Combobox(f, values=bn, state="readonly", width=10)
        self.cb_ty.set("Khớp")
        self.cb_by = ttk.Combobox(f, values=bn, state="readonly", width=10)
        self.cb_by.set("Khớp")
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
        self.en_N = ttk.Entry(f, width=18); self.en_N.insert(0, "1500")
        self._row(f, "Lực dọc N (kN) — N > 0 là nén", self.en_N, 0)
        self.en_Mx = ttk.Entry(f, width=18); self.en_Mx.insert(0, "80")
        self._row(f, "Momen Mx (kN·m) — quanh trục x", self.en_Mx, 1)
        self.en_My = ttk.Entry(f, width=18); self.en_My.insert(0, "60")
        self._row(f, "Momen My (kN·m) — quanh trục y", self.en_My, 2)
        self.var_lt = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Khai báo thành phần tải dài hạn",
                        variable=self.var_lt,
                        command=self._toggle_lt).grid(row=3, column=0,
                                                     columnspan=2, sticky=tk.W,
                                                     padx=4, pady=4)
        self.lt_frame = ttk.Frame(f)
        self.lt_frame.grid(row=4, column=0, columnspan=2, sticky=tk.EW, padx=4)
        self.lt_frame.grid_remove()  # ẩn ban đầu
        self.en_Nlt = ttk.Entry(self.lt_frame, width=18); self.en_Nlt.insert(0, "0")
        self._row(self.lt_frame, "N dài hạn (kN)", self.en_Nlt, 0)
        self.en_Mxlt = ttk.Entry(self.lt_frame, width=18); self.en_Mxlt.insert(0, "0")
        self._row(self.lt_frame, "Mx dài hạn (kN·m)", self.en_Mxlt, 1)
        self.en_Mylt = ttk.Entry(self.lt_frame, width=18); self.en_Mylt.insert(0, "0")
        self._row(self.lt_frame, "My dài hạn (kN·m)", self.en_Mylt, 2)
        ttk.Label(self.lt_frame, foreground="gray", wraplength=380,
                  text="Nếu bỏ chọn: φL = 2.00 (thiên về an toàn). Nếu chọn: "
                       "xác định φLx, φLy theo Công thức (48), 1.00 ≤ φL ≤ 2.00."
                  ).grid(row=3, column=0, columnspan=2, padx=4, pady=2,
                         sticky=tk.W)

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
            concrete_grade=self.cb_conc.get(), gamma_b=self._f(self.en_gb, 1.0),
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
            lines.append(f"Khoảng hở thông thủy: Cx = {ccx:.1f} mm, "
                         f"Cy = {ccy:.1f} mm")
            lines.append(f"Khoảng cách tim: Cx = {ccx + d_avg:.1f} mm, "
                         f"Cy = {ccy + d_avg:.1f} mm")
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
        try:
            inp = self.collect()
            res = check_column(inp, n_angles=24)
        except Exception as ex:
            messagebox.showerror("Lỗi", str(ex))
            return
        ok_txt = "ĐẠT ✓" if res.ok else "KHÔNG ĐẠT ✗"
        self.result_var.set(
            f"Kết quả: {ok_txt} — Hệ số sử dụng η = {res.utilization:.3f}")
        # Tóm tắt
        sec = build_section(inp)
        n = len(sec.rebars)
        dias = sorted(set(r.dia for r in sec.rebars))
        dia_txt = "/".join(f"{d:.0f}" for d in dias)
        summ = [
            f"{n} thanh d{dia_txt} — As = {res.steel_area:.0f} mm², "
            f"μ = {res.reinforcement_ratio * 100:.2f}%",
            f"N = {res.N:.1f} kN, Mx = {res.Mx:.1f}, My = {res.My:.1f} kN·m",
            f"M = {res.M_resultant:.1f} kN·m | Khả năng = {res.M_capacity:.1f} kN·m",
            f"φL = {res.phi_L:.2f}; L0x = {res.L0x:.2f} m, L0y = {res.L0y:.2f} m",
        ]
        self.sum_text.delete("1.0", tk.END)
        self.sum_text.insert(tk.END, "\n".join(summ))
        # Thuyết minh (có format màu sắc)
        self._render_report(generate_report(inp, res))
        # L0 preview
        self.l0_var.set(
            f"Chiều dài tính toán: L0x = {res.L0x:.2f} m, L0y = {res.L0y:.2f} m")
        if HAS_MPL:
            self._last_sec = sec
            self._last_inp = inp
            self._last_res = res
            self._redraw()

    # ---------------- ETABS ----------------
    def on_import_etabs(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Chọn file Excel ETABS",
            filetypes=[("Excel", "*.xlsx *.xls"), ("All", "*.*")])
        if not path:
            return
        try:
            from rc_column.etabs_import import read_etabs_excel
            m2_to = "Mx" if self.cb_map.get().startswith("M2→Mx") else "My"
            forces = read_etabs_excel(path, m2_to=m2_to,
                                      only_combinations=self.var_comb.get())
        except Exception as ex:
            messagebox.showerror("Lỗi đọc file", str(ex))
            return
        self.etabs_forces = forces
        self.etabs_file = path
        n_case = len(set(f.case for f in forces))
        self.etabs_info.set(
            f"Đã đọc {len(forces)} dòng, {n_case} tổ hợp từ: "
            f"{path.split('/')[-1].split(chr(92))[-1]} — "
            f"Bấm 'Kiểm tra tất cả' để tính.")
        self._fill_etabs_table([(f, None) for f in forces])

    def _fill_etabs_table(self, rows):
        t = self.etabs_tree
        t.delete(*t.get_children())
        for f, r in rows:
            dc = r["dc"] if r else None
            vals = (f.story, f.column, f.case, f"{f.station:.2f}",
                    f"{f.N:.1f}", f"{f.Mx:.1f}", f"{f.My:.1f}",
                    f"{dc:.3f}" if dc is not None and dc == dc else "—",
                    ("KHÔNG ĐẠT" if dc and dc > 1 else
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
        # highlight dòng nguy hiểm nhất
        self._fill_etabs_table(rows)
        worst_f, worst_r = rows[0]
        for item in self.etabs_tree.get_children():
            vals = self.etabs_tree.item(item, "values")
            if vals[2] == worst_f.case and vals[3] == f"{worst_f.station:.2f}":
                self.etabs_tree.item(item, tags=("worst",))
                self.etabs_tree.see(item)
                break
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
        self._render_report(generate_report(inp_w, res_w))
        self.result_var.set(
            f"Tổ hợp nguy hiểm nhất: {worst_f.case} — "
            f"{'KHÔNG ĐẠT ✗' if worst_r['dc'] > 1 else 'ĐẠT ✓'} "
            f"(D/C = {worst_r['dc']:.3f})")

    def _render_report(self, segs):
        """Hiển thị thuyết minh với format VietconSoft."""
        t = self.calc_text
        t.delete("1.0", tk.END)
        # Định nghĩa tags (màu sắc theo Tailwind của web mẫu)
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
        for text, tags in segs:
            t.insert(tk.END, text, tags if tags else ())

    def _redraw(self):
        """Vẽ lại theo loại biểu đồ đang chọn."""
        if not HAS_MPL or self._last_sec is None:
            return
        sec, inp, res = self._last_sec, self._last_inp, self._last_res
        kind = self.cb_plot.get()
        self.fig.clear()
        # Trái: luôn là sơ đồ tiết diện
        a1 = self.fig.add_subplot(121)
        if sec.kind == "rect":
            a1.add_patch(mpatches.Rectangle(
                (-sec.cx/2, -sec.cy/2), sec.cx, sec.cy,
                fill=False, edgecolor="black", linewidth=1.5))
        else:
            a1.add_patch(mpatches.Circle(
                (0, 0), sec.cx/2, fill=False, edgecolor="black", linewidth=1.5))
        a1.scatter([r.x for r in sec.rebars], [r.y for r in sec.rebars],
                   s=70, c="red", zorder=3)
        a1.set_aspect("equal"); a1.set_title("Sơ đồ mặt cắt")
        a1.grid(True, alpha=0.3)

        from rc_column.interaction import (BiaxialCapacity, FiberSection,
                                           uniaxial_curve_fs)
        if kind.startswith("Mx-My"):
            a2 = self.fig.add_subplot(122)
            cap = BiaxialCapacity(sec, model=inp.concrete_model, n_angles=24)
            pts = cap.mx_my_curve(inp.N)
            a2.plot([p[0] for p in pts], [p[1] for p in pts], "b-",
                    linewidth=1.5, label=f"Tại N = {inp.N:.0f} kN")
            a2.scatter([inp.Mx], [inp.My], c="red", s=80, zorder=5,
                       label="Điểm tải trọng")
            a2.set_xlabel("Mx (kN·m)"); a2.set_ylabel("My (kN·m)")
            a2.set_title("Tương tác Mx-My")
            a2.legend(fontsize=8); a2.grid(True, alpha=0.3)
            a2.set_aspect("equal", adjustable="datalim")
        elif kind.startswith("3D"):
            from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
            a2 = self.fig.add_subplot(122, projection="3d")
            cap = BiaxialCapacity(sec, model=inp.concrete_model, n_angles=24)
            n_vals, th_vals, mxg, myg = cap.surface_grid(n_n=25, n_angles=48)
            import numpy as np
            N3, _ = np.meshgrid(n_vals, th_vals, indexing="ij")
            a2.plot_surface(mxg, myg, N3, alpha=0.7, cmap="viridis",
                            edgecolor="none")
            a2.scatter([inp.Mx], [inp.My], [inp.N], c="red", s=60,
                       label="Điểm tải trọng")
            a2.set_xlabel("Mx (kN·m)"); a2.set_ylabel("My (kN·m)")
            a2.set_zlabel("N (kN)")
            a2.set_title("Mặt tương tác 3D N-Mx-My")
        else:
            a2 = self.fig.add_subplot(122)
            fs = FiberSection(sec)
            for th, style, lab in [(0, "b-", "N-Mx (θ=0°)"),
                                   (90, "r--", "N-My (θ=90°)")]:
                cv = uniaxial_curve_fs(fs, th, inp.concrete_model)
                a2.plot([p[1] for p in cv], [p[0] for p in cv], style,
                        label=lab, linewidth=1.5)
            a2.scatter([math.hypot(inp.Mx, inp.My)], [inp.N], c="red", s=80,
                       zorder=5, label="Điểm tải trọng")
            a2.set_xlabel("M (kN·m)"); a2.set_ylabel("N (kN)")
            a2.set_title("Biểu đồ tương tác N-M")
            a2.legend(fontsize=8); a2.grid(True, alpha=0.3)
        self.fig.tight_layout()
        self.mpl.draw()



def main():
    app = App()
    app._refresh_rebar()
    app.mainloop()


if __name__ == "__main__":
    main()
