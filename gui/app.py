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

        self.sum_text = tk.Text(self.tab_sum, wrap=tk.WORD, font=("Consolas", 10),
                                height=10)
        self.sum_text.pack(fill=tk.X, padx=4, pady=4)
        if HAS_MPL:
            self.fig = Figure(figsize=(5.4, 4.6), dpi=100)
            self.ax1 = self.fig.add_subplot(121)
            self.ax2 = self.fig.add_subplot(122)
            self.mpl = FigureCanvasTkAgg(self.fig, master=self.tab_sum)
            self.mpl.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.calc_text = tk.Text(self.tab_calc, wrap=tk.WORD,
                                 font=("Consolas", 10))
        self.calc_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.calc_text.insert(tk.END,
                              "Chi tiết tính toán sẽ hiển thị sau khi thực hiện kiểm tra.")

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
                  justify=tk.LEFT).pack(padx=4, pady=4, anchor=tk.W)

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
                        command=self._toggle_lt).pack(anchor=tk.W, padx=4, pady=4)
        self.lt_frame = ttk.Frame(f)
        self.en_Nlt = ttk.Entry(self.lt_frame, width=18); self.en_Nlt.insert(0, "0")
        self._row(self.lt_frame, "N dài hạn (kN)", self.en_Nlt, 0)
        self.en_Mxlt = ttk.Entry(self.lt_frame, width=18); self.en_Mxlt.insert(0, "0")
        self._row(self.lt_frame, "Mx dài hạn (kN·m)", self.en_Mxlt, 1)
        self.en_Mylt = ttk.Entry(self.lt_frame, width=18); self.en_Mylt.insert(0, "0")
        self._row(self.lt_frame, "My dài hạn (kN·m)", self.en_Mylt, 2)
        ttk.Label(self.lt_frame, foreground="gray", wraplength=380,
                  text="Nếu bỏ chọn: φL = 2.00 (thiên về an toàn). Nếu chọn: "
                       "xác định φLx, φLy theo Công thức (48), 1.00 ≤ φL ≤ 2.00."
                  ).pack(padx=4, pady=2)

    def _toggle_lt(self):
        if self.var_lt.get():
            self.lt_frame.pack(fill=tk.X, padx=4)
        else:
            self.lt_frame.pack_forget()

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
        # Thuyết minh
        self.calc_text.delete("1.0", tk.END)
        self.calc_text.insert(tk.END, generate_report(inp, res))
        # L0 preview
        self.l0_var.set(
            f"Chiều dài tính toán: L0x = {res.L0x:.2f} m, L0y = {res.L0y:.2f} m")
        if HAS_MPL:
            self._draw(sec, inp, res)

    def _draw(self, sec, inp, res):
        self.ax1.clear(); self.ax2.clear()
        a1 = self.ax1
        if sec.kind == "rect":
            a1.add_patch(mpatches.Rectangle(
                (-sec.cx/2, -sec.cy/2), sec.cx, sec.cy,
                fill=False, edgecolor="black", linewidth=1.5))
        else:
            a1.add_patch(mpatches.Circle(
                (0, 0), sec.cx/2, fill=False, edgecolor="black", linewidth=1.5))
        a1.scatter([r.x for r in sec.rebars], [r.y for r in sec.rebars],
                   s=70, c="red", zorder=3)
        a1.set_aspect("equal"); a1.set_title("Sơ đồ mặt cắt tiết diện cột")
        a1.grid(True, alpha=0.3)
        from rc_column.interaction import FiberSection, uniaxial_curve_fs
        fs = FiberSection(sec)
        for th, style, lab in [(0, "b-", "Mx (θ=0°)"), (90, "r--", "My (θ=90°)")]:
            cv = uniaxial_curve_fs(fs, th, inp.concrete_model)
            self.ax2.plot([p[1] for p in cv], [p[0] for p in cv], style,
                          label=lab, linewidth=1.5)
        self.ax2.scatter([math.hypot(inp.Mx, inp.My)], [inp.N], c="red", s=80,
                         zorder=5, label="Điểm tải trọng")
        self.ax2.set_xlabel("M (kN·m)"); self.ax2.set_ylabel("N (kN)")
        self.ax2.set_title("Biểu đồ tương tác N-M")
        self.ax2.legend(fontsize=8); self.ax2.grid(True, alpha=0.3)
        self.fig.tight_layout()
        self.mpl.draw()


def main():
    app = App()
    app._refresh_rebar()
    app.mainloop()


if __name__ == "__main__":
    main()
