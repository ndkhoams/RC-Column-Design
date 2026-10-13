"""Giao diện chính: kiểm tra cột BTCT theo TCVN 5574:2018 (mô hình phi tuyến).

Bố cục theo mẫu VietconSoft:
 1. Vật liệu | 2. Tiết diện | 3. Cốt thép | 4. Chiều dài tính toán | 5. Nội lực
Kết quả: ĐẠT / KHÔNG ĐẠT, hệ số sử dụng, sơ đồ tiết diện, biểu đồ tương tác.
"""

import math
import tkinter as tk
from tkinter import ttk, messagebox

from rc_column.checker import ColumnInput, build_section, check_column
from rc_column.materials import CONCRETE_GRADES, STEEL_GRADES
from rc_column.stability import BOUNDARY_NAMES, LongTermLoads

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MPL = True
except Exception:
    HAS_MPL = False


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tính cột BTCT - TCVN 5574:2018 (mô hình phi tuyến)")
        self.geometry("1180x760")
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        left = ttk.Frame(main)
        main.add(left, weight=1)
        right = ttk.Frame(main)
        main.add(right, weight=1)

        # ---- Cột nhập liệu ----
        nb = ttk.Notebook(left)
        nb.pack(fill=tk.BOTH, expand=True)

        self.f_mat = ttk.Frame(nb);   nb.add(self.f_mat, text="1. Vật liệu")
        self.f_sec = ttk.Frame(nb);   nb.add(self.f_sec, text="2. Tiết diện")
        self.f_rb = ttk.Frame(nb);    nb.add(self.f_rb, text="3. Cốt thép")
        self.f_st = ttk.Frame(nb);    nb.add(self.f_st, text="4. Ổn định")
        self.f_ld = ttk.Frame(nb);    nb.add(self.f_ld, text="5. Nội lực")
        self._build_materials()
        self._build_section()
        self._build_rebar()
        self._build_stability()
        self._build_loads()

        btn = ttk.Frame(left)
        btn.pack(fill=tk.X, pady=6)
        ttk.Button(btn, text="KIỂM TRA KHẢ NĂNG CHỊU LỰC",
                   command=self.on_check).pack(fill=tk.X, ipady=6)

        # ---- Cột kết quả ----
        self.result_var = tk.StringVar(value="Nhập dữ liệu và bấm kiểm tra.")
        ttk.Label(right, textvariable=self.result_var, font=("", 11, "bold"),
                  foreground="#0a4d8c").pack(pady=4)
        self.detail = tk.Text(right, height=14, wrap=tk.WORD, font=("Consolas", 9))
        self.detail.pack(fill=tk.X, padx=4)
        if HAS_MPL:
            self.fig = Figure(figsize=(5.2, 4.2), dpi=100)
            self.ax1 = self.fig.add_subplot(121)
            self.ax2 = self.fig.add_subplot(122)
            self.canvas = FigureCanvasTkAgg(self.fig, master=right)
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        else:
            ttk.Label(right, text="(cài matplotlib để xem biểu đồ)").pack()

    # ------------------------------------------------------------------
    def _row(self, parent, label, widget, r):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky=tk.W,
                                           padx=6, pady=3)
        widget.grid(row=r, column=1, sticky=tk.EW, padx=6, pady=3)
        parent.columnconfigure(1, weight=1)
        return widget

    def _build_materials(self):
        self.cb_conc = ttk.Combobox(self.f_mat, values=list(CONCRETE_GRADES),
                                    state="readonly")
        self.cb_conc.set("B25")
        self._row(self.f_mat, "Cấp độ bền bê tông", self.cb_conc, 0)
        self.en_gb = ttk.Entry(self.f_mat); self.en_gb.insert(0, "1.0")
        self._row(self.f_mat, "Hệ số γb", self.en_gb, 1)
        self.cb_steel = ttk.Combobox(self.f_mat, values=list(STEEL_GRADES),
                                     state="readonly")
        self.cb_steel.set("CB400-V")
        self._row(self.f_mat, "Cấp độ bền thép", self.cb_steel, 2)
        self.en_gs = ttk.Entry(self.f_mat); self.en_gs.insert(0, "1.0")
        self._row(self.f_mat, "Hệ số γs", self.en_gs, 3)
        self.cb_model = ttk.Combobox(self.f_mat,
                                     values=["3line (parabol-CN)", "2line (2 đoạn)"],
                                     state="readonly")
        self.cb_model.set("3line (parabol-CN)")
        self._row(self.f_mat, "Mô hình bê tông", self.cb_model, 4)

    def _build_section(self):
        self.cb_kind = ttk.Combobox(self.f_sec, values=["Chữ nhật", "Tròn"],
                                    state="readonly")
        self.cb_kind.set("Chữ nhật")
        self.cb_kind.bind("<<ComboboxSelected>>", lambda e: self._toggle_sec())
        self._row(self.f_sec, "Loại tiết diện", self.cb_kind, 0)
        self.en_cx = ttk.Entry(self.f_sec); self.en_cx.insert(0, "400")
        self._row(self.f_sec, "Cạnh Cx / Đường kính (mm)", self.en_cx, 1)
        self.en_cy = ttk.Entry(self.f_sec); self.en_cy.insert(0, "400")
        self._row(self.f_sec, "Cạnh Cy (mm)", self.en_cy, 2)

    def _toggle_sec(self):
        is_rect = self.cb_kind.get() == "Chữ nhật"
        self.en_cy.configure(state="normal" if is_rect else "disabled")

    def _build_rebar(self):
        self.en_dia = ttk.Entry(self.f_rb); self.en_dia.insert(0, "20")
        self._row(self.f_rb, "Đường kính (mm)", self.en_dia, 0)
        self.en_nx = ttk.Entry(self.f_rb); self.en_nx.insert(0, "3")
        self._row(self.f_rb, "Số thanh/cạnh X", self.en_nx, 1)
        self.en_ny = ttk.Entry(self.f_rb); self.en_ny.insert(0, "3")
        self._row(self.f_rb, "Số thanh/cạnh Y (tròn: tổng số)", self.en_ny, 2)
        self.en_cover = ttk.Entry(self.f_rb); self.en_cover.insert(0, "30")
        self._row(self.f_rb, "Lớp bảo vệ (mm)", self.en_cover, 3)

    def _build_stability(self):
        r = 0
        self.en_Lx = ttk.Entry(self.f_st); self.en_Lx.insert(0, "4.0")
        self._row(self.f_st, "Chiều dài cột Lx (m)", self.en_Lx, r); r += 1
        self.en_Ly = ttk.Entry(self.f_st); self.en_Ly.insert(0, "4.0")
        self._row(self.f_st, "Chiều dài cột Ly (m)", self.en_Ly, r); r += 1
        bn = list(BOUNDARY_NAMES.values())
        self.cb_tx = ttk.Combobox(self.f_st, values=bn, state="readonly")
        self.cb_tx.set("Khớp")
        self._row(self.f_st, "Liên kết đỉnh (X)", self.cb_tx, r); r += 1
        self.cb_bx = ttk.Combobox(self.f_st, values=bn, state="readonly")
        self.cb_bx.set("Khớp")
        self._row(self.f_st, "Liên kết chân (X)", self.cb_bx, r); r += 1
        self.cb_ty = ttk.Combobox(self.f_st, values=bn, state="readonly")
        self.cb_ty.set("Khớp")
        self._row(self.f_st, "Liên kết đỉnh (Y)", self.cb_ty, r); r += 1
        self.cb_by = ttk.Combobox(self.f_st, values=bn, state="readonly")
        self.cb_by.set("Khớp")
        self._row(self.f_st, "Liên kết chân (Y)", self.cb_by, r); r += 1
        self.en_psix = ttk.Entry(self.f_st)
        self._row(self.f_st, "ψx (trống=tự tính)", self.en_psix, r); r += 1
        self.en_psiy = ttk.Entry(self.f_st)
        self._row(self.f_st, "ψy (trống=tự tính)", self.en_psiy, r); r += 1

    def _build_loads(self):
        r = 0
        self.en_N = ttk.Entry(self.f_ld); self.en_N.insert(0, "1500")
        self._row(self.f_ld, "N (kN, nén dương)", self.en_N, r); r += 1
        self.en_Mx = ttk.Entry(self.f_ld); self.en_Mx.insert(0, "80")
        self._row(self.f_ld, "Mx (kN·m)", self.en_Mx, r); r += 1
        self.en_My = ttk.Entry(self.f_ld); self.en_My.insert(0, "60")
        self._row(self.f_ld, "My (kN·m)", self.en_My, r); r += 1
        self.var_lt = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.f_ld, text="Khai báo tải dài hạn",
                        variable=self.var_lt).grid(row=r, column=0,
                                                   columnspan=2, sticky=tk.W,
                                                   padx=6, pady=3); r += 1
        self.en_Nlt = ttk.Entry(self.f_ld); self.en_Nlt.insert(0, "0")
        self._row(self.f_ld, "N dài hạn (kN)", self.en_Nlt, r); r += 1
        self.en_Mxlt = ttk.Entry(self.f_ld); self.en_Mxlt.insert(0, "0")
        self._row(self.f_ld, "Mx dài hạn (kN·m)", self.en_Mxlt, r); r += 1
        self.en_Mylt = ttk.Entry(self.f_ld); self.en_Mylt.insert(0, "0")
        self._row(self.f_ld, "My dài hạn (kN·m)", self.en_Mylt, r); r += 1

    # ------------------------------------------------------------------
    def _f(self, entry, default=0.0):
        try:
            return float(entry.get().strip().replace(",", "."))
        except Exception:
            return default

    def _bkey(self, combo):
        inv = {v: k for k, v in BOUNDARY_NAMES.items()}
        return inv.get(combo.get(), "khop")

    def collect(self) -> ColumnInput:
        is_rect = self.cb_kind.get() == "Chữ nhật"
        model = "3line" if self.cb_model.get().startswith("3line") else "2line"
        def opt(e):
            t = e.get().strip()
            return float(t.replace(",", ".")) if t else None
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
            Lx=self._f(self.en_Lx, 4.0), Ly=self._f(self.en_Ly, 4.0),
            top_x=self._bkey(self.cb_tx), bottom_x=self._bkey(self.cb_bx),
            top_y=self._bkey(self.cb_ty), bottom_y=self._bkey(self.cb_by),
            psi_x=opt(self.en_psix), psi_y=opt(self.en_psiy),
            N=self._f(self.en_N), Mx=self._f(self.en_Mx), My=self._f(self.en_My),
            long_term=LongTermLoads(
                has_data=self.var_lt.get(),
                N_lt=self._f(self.en_Nlt), Mx_lt=self._f(self.en_Mxlt),
                My_lt=self._f(self.en_Mylt)),
        )

    def on_check(self):
        try:
            inp = self.collect()
            res = check_column(inp, n_angles=24)
        except Exception as ex:
            messagebox.showerror("Lỗi", str(ex))
            return
        status = "ĐẠT ✓" if res.ok else "KHÔNG ĐẠT ✗"
        color = "#0a7a2e" if res.ok else "#c00000"
        self.result_var.set(
            f"{status} — Hệ số sử dụng: {res.utilization:.3f}")
        # chi tiết
        sec = build_section(inp)
        lines = [
            f"Kết quả: {status}",
            f"N = {res.N:.1f} kN, Mx = {res.Mx:.1f}, My = {res.My:.1f} kN·m",
            f"M tổng hợp = {res.M_resultant:.1f} kN·m | "
            f"Khả năng = {res.M_capacity:.1f} kN·m",
            f"As = {res.steel_area:.0f} mm² ({len(sec.rebars)} thanh), "
            f"μ = {res.reinforcement_ratio*100:.2f}%",
            "",
        ] + res.details
        self.detail.delete("1.0", tk.END)
        self.detail.insert(tk.END, "\n".join(lines))
        if HAS_MPL:
            self._draw(sec, inp, res)

    def _draw(self, sec, inp, res):
        self.ax1.clear(); self.ax2.clear()
        # Sơ đồ tiết diện
        a1 = self.ax1
        if sec.kind == "rect":
            a1.add_patch(__import__("matplotlib").patches.Rectangle(
                (-sec.cx/2, -sec.cy/2), sec.cx, sec.cy,
                fill=False, edgecolor="black", linewidth=1.5))
        else:
            a1.add_patch(__import__("matplotlib").patches.Circle(
                (0, 0), sec.cx/2, fill=False, edgecolor="black", linewidth=1.5))
        xs = [r.x for r in sec.rebars]; ys = [r.y for r in sec.rebars]
        a1.scatter(xs, ys, s=60, c="red", zorder=3)
        a1.set_aspect("equal"); a1.set_title("Sơ đồ tiết diện")
        a1.grid(True, alpha=0.3)
        # Biểu đồ tương tác N-M (2 phương)
        from rc_column.interaction import FiberSection, uniaxial_curve_fs
        fs = FiberSection(sec)
        for th, style, lab in [(0, "b-", "Mx (θ=0°)"), (90, "r--", "My (θ=90°)")]:
            cv = uniaxial_curve_fs(fs, th, inp.concrete_model)
            ns = [p[0] for p in cv]; ms = [p[1] for p in cv]
            self.ax2.plot(ms, ns, style, label=lab, linewidth=1.5)
        Mres = math.hypot(inp.Mx, inp.My)
        self.ax2.scatter([Mres], [inp.N], c="red", s=80, zorder=5,
                         label="Điểm tải trọng")
        self.ax2.set_xlabel("M (kN·m)"); self.ax2.set_ylabel("N (kN)")
        self.ax2.set_title("Biểu đồ tương tác N-M")
        self.ax2.legend(fontsize=8); self.ax2.grid(True, alpha=0.3)
        self.fig.tight_layout()
        self.canvas.draw()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
