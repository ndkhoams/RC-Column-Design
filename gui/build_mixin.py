"""Xây dựng giao diện nhập liệu (panel trái): vật liệu, tiết diện, cốt thép,
ổn định và nội lực. Tách từ gui/app.py."""

import tkinter as tk
from tkinter import ttk, messagebox

from rc_column.lang import T
from rc_column.materials import CONCRETE_GRADES, STEEL_GRADES
from rc_column.stability import BOUNDARY_NAMES


_COVER_TIP = (
    "Định nghĩa c khác với ETABS!\n"
    "• App: c đo từ mép bê tông đến TÂM thép dọc.\n"
    "• ETABS: cover đo đến mép NGOÀI của đai.\n"
    "→ Muốn so sánh với ETABS: nhập c = cover_đai_ETABS + đường kính đai\n"
    "  (vd ETABS cover đai 40, đai Ø10 → nhập app c = 50)."
)


class _ToolTip:
    """Tooltip hiện khi di chuột lên widget (ghi chú định nghĩa cover)."""
    def __init__(self, widget, text, delay=400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._tip = None
        self._after = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)

    def _schedule(self, event=None):
        self._cancel()
        self._after = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after is not None:
            self.widget.after_cancel(self._after)
            self._after = None

    def _show(self):
        if self._tip is not None:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self._tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        tk.Label(tw, text=self.text, justify="left",
                 background="#fffbe6", relief="solid", borderwidth=1,
                 font=("TkDefaultFont", 9), wraplength=380,
                 padx=8, pady=6).pack()

    def _hide(self, event=None):
        self._cancel()
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None

class BuildMixin:
    """Các method dựng panel nhập liệu bên trái (mục 1-5)."""

    def _build(self):
        # Layout cố định: không dùng PanedWindow (đã ẩn sash + fix cứng bề rộng)
        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self._paned = main  # giữ tên để code cũ không lỗi
        # Panel trái rộng 700px để hiện đủ bảng nội lực
        self._left_width = 700

        # ---- Trái: nhập liệu (cuộn được) ----
        left_outer = ttk.Frame(main, width=self._left_width)
        left_outer.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 2))
        left_outer.pack_propagate(False)
        # Divider mỏng (thay sash, không kéo được)
        _divider = ttk.Frame(main, width=4)
        _divider.pack(side=tk.LEFT, fill=tk.Y)
        _divider.pack_propagate(False)
        # Cụm nút cố định ĐỈNH (không bị cuộn theo) — theo yêu cầu user 2026-10-16
        top_bar = ttk.Frame(left_outer, relief=tk.RAISED, borderwidth=1)
        top_bar.pack(fill=tk.X, side=tk.TOP, padx=2, pady=2)
        # Cụm nút cố định ĐỈNH: 1 grid chung 4 cột đều nhau (uniform) để
        # hàng kiểm tra căn khít với 4 nút bên trên.
        top_grid = ttk.Frame(top_bar)
        top_grid.pack(fill=tk.X, padx=8, pady=4)
        for _c in range(4):
            top_grid.columnconfigure(_c, weight=1, uniform="topbtns")
        # Hàng 1: 4 nút dữ liệu
        ttk.Button(top_grid, text="OPEN", style="Top.TButton",
                   command=self.on_load_data).grid(row=0, column=0,
                                                   sticky=tk.EW, padx=(0, 4))
        ttk.Button(top_grid, text="SAVE", style="Top.TButton",
                   command=self.on_save_data).grid(row=0, column=1,
                                                   sticky=tk.EW, padx=(2, 2))
        ttk.Button(top_grid, text="SAVE AS", style="Top.TButton",
                   command=self.on_save_as_data).grid(row=0, column=2,
                                                      sticky=tk.EW,
                                                      padx=(2, 2))
        self.btn_check = ttk.Button(top_grid, text="✓ CHECK",
                                    style="Check.TButton",
                                    command=self.on_check)
        self.btn_check.grid(row=0, column=3, sticky=tk.EW, padx=(4, 0))
        # Hàng 2: Tiêu chuẩn [dropdown dài] Tên cấu kiện [textbox=col2] [CHECK=col3]
        # (theo yêu cầu user 2026-10-17: textbox bằng SAVE AS, CHECK bằng XUẤT PDF)
        row2 = ttk.Frame(top_grid)
        row2.grid(row=1, column=0, columnspan=4, sticky=tk.EW,
                  padx=0, pady=(6, 0))
        row2.columnconfigure(0, weight=1, uniform="row2cols")
        row2.columnconfigure(1, weight=1, uniform="row2cols")
        row2.columnconfigure(2, weight=1, uniform="row2cols")
        row2.columnconfigure(3, weight=1, uniform="row2cols")
        # Cột 0-1: Tiêu chuẩn + dropdown dài
        _std_frame = ttk.Frame(row2)
        _std_frame.grid(row=0, column=0, columnspan=2, sticky=tk.EW, padx=(0, 2))
        # Bộ chọn loại cấu kiện (Cột / Vách — chế độ Vách GĐ1)
        ttk.Label(_std_frame, text="Cấu kiện:",
                  style="Muted.TLabel").pack(side=tk.LEFT, padx=(4, 4))
        self.cb_member = ttk.Combobox(_std_frame, values=["Cột", "Vách"],
                                      state="readonly", width=6)
        self.cb_member.set("Cột")
        self.cb_member.bind("<<ComboboxSelected>>",
                            lambda e: self._toggle_member())
        self.cb_member.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(_std_frame, text="Tiêu chuẩn:",
                  style="Muted.TLabel").pack(side=tk.LEFT, padx=(4, 4))
        self.cb_code = ttk.Combobox(_std_frame, values=["TCVN 5574:2018", "ACI 318-19",
                                                        "EC2 (EN 1992-1-1:2004)"],
                                    state="readonly")
        self.cb_code.set("TCVN 5574:2018")
        self.cb_code.bind("<<ComboboxSelected>>", lambda e: self._toggle_code())
        self.cb_code.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        # Cột 2-3: Tên cấu kiện + textbox (rộng bằng SAVE AS + CHECK)
        _name_frame = ttk.Frame(row2)
        _name_frame.grid(row=0, column=2, columnspan=2, sticky=tk.EW, padx=2)
        ttk.Label(_name_frame, text="Tên cấu kiện:",
                  style="Muted.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        self.member_var = tk.StringVar(value="")
        self.member_entry = ttk.Entry(_name_frame, textvariable=self.member_var)
        self.member_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # Cập nhật hiển thị tên cấu kiện khi gõ
        self.member_var.trace_add("write", lambda *a: self._update_ck())

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
        self._left_win = canvas.create_window((0, 0), window=self.left,
                                              anchor=tk.NW)
        # Khi canvas rộng/cao hơn nội dung, giãn window fill hết
        def _fit_left_window(e):
            canvas.itemconfigure(self._left_win, width=e.width)
            # KHÔNG ép height: để nội dung cao tự nhiên mới cuộn được
            # (trước đây ép height=e.height khiến panel không cuộn được)
            self.left.update_idletasks()
        canvas.bind("<Configure>", _fit_left_window)
        canvas.configure(yscrollcommand=scr.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scr.pack(side=tk.RIGHT, fill=tk.Y)

        self._sec_materials()
        self._sec_wall()
        self._sec_section()
        self._sec_rebar()
        self._sec_stability()
        self._sec_loads()
        # Mặc định chế độ Cột: ẩn frame vách (hiện khi chọn "Vách")
        self.frm_wall.pack_forget()
        # Spacer (không expand để bảng nội lực ở mục 5 fill hết không gian)
        _spacer = ttk.Frame(self.left)
        _spacer.pack(fill=tk.X)
        # Cuộn chuột cho vùng nhập liệu
        self._bind_wheel(self.left, self._left_canvas)
        # Cuộn chuột trên cụm nút cố định đỉnh -> cuộn vùng nhập liệu
        self._bind_wheel(top_bar, self._left_canvas)

        # ---- Phải: kết quả ----
        right = ttk.Frame(main)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0))
        # Nút VN|EN đặt cùng hàng với tab (góc phải, đè lên vùng trống của tab)
        self._lang_var = tk.StringVar(value="VN")
        # (Nút VN/EN tạm bỏ theo yêu cầu - chỉ dùng tiếng Việt)
        # Hàng nút chuyển tab (style giống 4 nút bên trái)
        _tab_bar = ttk.Frame(right)
        _tab_bar.pack(fill=tk.X, padx=4, pady=(4, 0))
        self._tab_btn_sum = ttk.Button(_tab_bar, text=T("KẾT QUẢ TÍNH TOÁN"),
                                       style="Top.TButton",
                                       command=lambda: self._show_tab("sum"))
        self._tab_btn_sum.pack(side=tk.LEFT, padx=(0, 4))
        self._tab_btn_calc = ttk.Button(_tab_bar, text=T("CHI TIẾT TÍNH TOÁN"),
                                        style="Top.TButton",
                                        command=lambda: self._show_tab("calc"))
        self._tab_btn_calc.pack(side=tk.LEFT)
        # Nút XUẤT PDF chuyển từ hàng trên sang đây
        self._btn_pdf_tab = ttk.Button(_tab_bar, text="IN PDF",
                                       style="Top.TButton",
                                       command=self._export_pdf)
        self._btn_pdf_tab.pack(side=tk.LEFT, padx=(4, 0))
        # Container chứa 2 tab (thay Notebook)
        _tab_container = ttk.Frame(right)
        _tab_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.tab_sum = ttk.Frame(_tab_container)
        self.tab_calc = ttk.Frame(_tab_container)
        self.tab_sum.pack(fill=tk.BOTH, expand=True)
        self._current_tab = "sum"
        # Highlight nút tab mặc định
        self._tab_btn_sum.configure(style="TabActive.TButton")

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

    # ---- 1. Vật liệu ----
    def _sec_materials(self):
        f = self._frame(T("1. Vật liệu"))
        # Bộ chọn tiêu chuẩn đã chuyển lên hàng nút kiểm tra (top_bar)
        # Grid 4 cột đều nhau (khớp với 4 nút bên trên):
        # col 0: nhãn trái, col 1: nhãn phải, col 2: ô nhập trái (= SAVE AS),
        # col 3: ô nhập phải (= XUẤT PDF)
        def _mat_grid(parent):
            for _c in range(4):
                parent.columnconfigure(_c, weight=1, uniform="mat")
        def _mat_row(parent, r, llab, lwid, rlab, rwid):
            # Mỗi cặp nhãn-ô nhập đặt cạnh nhau: [nhãn][nhập][nhãn][nhập]
            # Bỏ qua widget None (cho hàng chỉ có 1 cặp)
            ttk.Label(parent, text=llab, style="Muted.TLabel").grid(
                row=r, column=0, sticky=tk.W, padx=(4, 8), pady=5)
            if lwid is not None:
                lwid.grid(row=r, column=1, sticky=tk.EW, padx=4, pady=5)
            if rlab:
                ttk.Label(parent, text=rlab, style="Muted.TLabel").grid(
                    row=r, column=2, sticky=tk.W, padx=(4, 8), pady=5)
            if rwid is not None:
                rwid.grid(row=r, column=3, sticky=tk.EW, padx=4, pady=5)
        # Khung TCVN (hiện mặc định)
        self.frm_tcvn = ttk.Frame(f)
        self.frm_tcvn.grid(row=0, column=0, sticky=tk.NSEW)
        f.columnconfigure(0, weight=1)
        _mat_grid(self.frm_tcvn)
        self.cb_conc = ttk.Combobox(self.frm_tcvn, values=list(CONCRETE_GRADES),
                                    state="readonly", width=12)
        self.cb_conc.set("B25")
        self.en_gb = ttk.Entry(self.frm_tcvn, width=12); self.en_gb.insert(0, "0.85")
        self.en_gs = ttk.Entry(self.frm_tcvn, width=12); self.en_gs.insert(0, "1.0")
        self.cb_steel = ttk.Combobox(self.frm_tcvn, values=list(STEEL_GRADES),
                                     state="readonly", width=12)
        self.cb_steel.set("CB400-V")
        self.cb_sw_steel = ttk.Combobox(self.frm_tcvn, values=list(STEEL_GRADES),
                                        state="readonly", width=12)
        self.cb_sw_steel.set("CB400-V")
        self.cb_model = ttk.Combobox(
            self.frm_tcvn, values=["3 đoạn thẳng (MH3ĐT)", "2 đoạn thẳng (MH2ĐT)"],
            state="readonly", width=12)
        self.cb_model.set("3 đoạn thẳng (MH3ĐT)")
        _mat_row(self.frm_tcvn, 0, "Cấp độ bền bê tông", self.cb_conc,
                 "Cấp độ bền thép dọc", self.cb_steel)
        _mat_row(self.frm_tcvn, 1, "Hệ số γb", self.en_gb,
                 "Cấp độ bền thép đai", self.cb_sw_steel)
        _mat_row(self.frm_tcvn, 2, "Hệ số γs", self.en_gs,
                 "Mô hình bê tông", self.cb_model)
        # Khung ACI (ẩn mặc định)
        self.frm_aci = ttk.Frame(f)
        self.frm_aci.grid(row=1, column=0, sticky=tk.NSEW)
        _mat_grid(self.frm_aci)
        self.en_fc = ttk.Entry(self.frm_aci, width=12); self.en_fc.insert(0, "30")
        self.en_fy = ttk.Entry(self.frm_aci, width=12); self.en_fy.insert(0, "420")
        self.cb_tie = ttk.Combobox(self.frm_aci, values=["Đai rời (tied)", "Đai xoắn (spiral)"],
                                   state="readonly", width=12)
        self.cb_tie.set("Đai rời (tied)")
        self.en_fyt = ttk.Entry(self.frm_aci, width=12); self.en_fyt.insert(0, "420")
        _mat_row(self.frm_aci, 0, "Bê tông f'c (MPa)", self.en_fc,
                 "Loại cốt đai", self.cb_tie)
        _mat_row(self.frm_aci, 1, "Thép dọc fy (MPa)", self.en_fy,
                 "Thép đai fyt (MPa)", self.en_fyt)
        self.frm_aci.grid_remove()
        # Khung EC2 (ẩn mặc định)
        self.frm_ec2 = ttk.Frame(f)
        self.frm_ec2.grid(row=2, column=0, sticky=tk.NSEW)
        _mat_grid(self.frm_ec2)
        from rc_column.ec2_materials import EC2_CONCRETE_GRADES, EC2_STEEL_GRADES
        self.cb_ec2_conc = ttk.Combobox(self.frm_ec2, values=list(EC2_CONCRETE_GRADES),
                                        state="readonly", width=12)
        self.cb_ec2_conc.set("C30/37")
        self.en_ec2_fyk = ttk.Entry(self.frm_ec2, width=12)
        self.en_ec2_fyk.insert(0, "500")
        self.cb_ec2_method = ttk.Combobox(self.frm_ec2, values=["Độ cứng danh nghĩa",
                                                               "Độ cong danh nghĩa"],
                                          state="readonly", width=12)
        self.cb_ec2_method.set("Độ cứng danh nghĩa")
        self.en_ec2_fyt = ttk.Entry(self.frm_ec2, width=12); self.en_ec2_fyt.insert(0, "500")
        self.en_ec2_phi = ttk.Entry(self.frm_ec2, width=12); self.en_ec2_phi.insert(0, "2.0")
        _mat_row(self.frm_ec2, 0, "Bê tông", self.cb_ec2_conc,
                 "Phương pháp tính bậc 2", self.cb_ec2_method)
        _mat_row(self.frm_ec2, 1, "Thép dọc fyk (MPa)", self.en_ec2_fyk,
                 "Thép đai fyk (MPa)", self.en_ec2_fyt)
        _mat_row(self.frm_ec2, 2, "Hệ số từ biến φ(∞,t0)", self.en_ec2_phi,
                 "", None)
        self.frm_ec2.grid_remove()

    def _toggle_code(self):
        """Ẩn/hiện khung nhập liệu theo tiêu chuẩn được chọn."""
        if self.cb_code.get().startswith("EC2"):
            self.frm_tcvn.grid_remove()
            self.frm_aci.grid_remove()
            self.frm_ec2.grid()
        elif self.cb_code.get().startswith("ACI"):
            self.frm_tcvn.grid_remove()
            self.frm_aci.grid()
            self.frm_ec2.grid_remove()
        else:
            self.frm_aci.grid_remove()
            self.frm_ec2.grid_remove()
            self.frm_tcvn.grid()

    # ---- 2. Tiết diện ----
    def _sec_section(self):
        f = self._frame(T("2. Tiết diện"))
        self.frm_sec_section = f  # để _toggle_member ẩn/hiện theo loại cấu kiện
        # Dùng grid 4 cột đều (khớp 4 nút bên trên) cho toàn section
        for _c in range(4):
            f.columnconfigure(_c, weight=1, uniform="sec2")
        fl = ttk.Frame(f); fl.grid(row=0, column=0, columnspan=2,
                                   sticky=tk.NW, padx=2)
        fr = ttk.Frame(f); fr.grid(row=0, column=2, columnspan=2,
                                   sticky=tk.NSEW, padx=2)
        # Khung phải: chứa ô kích thước (chữ nhật/tròn) hoặc note DXF
        dim_box = ttk.Frame(fr)
        dim_box.grid(row=0, column=0, sticky=tk.NSEW)
        fr.columnconfigure(0, weight=1)
        self.sec_dim_frame = dim_box  # để ẩn khi chọn DXF
        # Note import DXF: nằm bên phải, hiện thay chỗ ô kích thước
        self.dxf_info = tk.StringVar(value="")
        self.dxf_info_label = ttk.Label(fr, textvariable=self.dxf_info,
                                        font=("", 8, "italic"),
                                        foreground="#0a4d8c", wraplength=280,
                                        justify=tk.LEFT)
        self.dxf_info_label.grid(row=0, column=0, sticky=tk.NW,
                                 padx=4, pady=4)
        self.dxf_info_label.grid_remove()  # mặc định ẩn
        self.en_cy = ttk.Entry(dim_box, width=12); self.en_cy.insert(0, "400")
        self._row(dim_box, "Cạnh t2 (mm) — đứng", self.en_cy, 0)
        self.en_cx = ttk.Entry(dim_box, width=12); self.en_cx.insert(0, "400")
        self._row(dim_box, "Cạnh t3 (mm) — ngang", self.en_cx, 1)
        # Ô đường kính cho tiết diện tròn (hiện thay dim_box khi chọn Tròn)
        dia_box = ttk.Frame(fr)
        dia_box.grid(row=0, column=0, sticky=tk.NSEW)
        self.sec_dia_frame = dia_box
        self.en_dia = ttk.Entry(dia_box, width=12); self.en_dia.insert(0, "600")
        self._row(dia_box, "Đường kính D (mm)", self.en_dia, 0)
        dia_box.grid_remove()  # mặc định ẩn (chỉ hiện khi chọn Tròn)
        self.en_dia.bind("<FocusOut>", lambda e: self._refresh_rebar())
        # Hàng loại tiết diện: combobox gọn, không giãn full
        ttk.Label(fl, text="Loại tiết diện", style="Muted.TLabel",
                  width=self._LBL_WIDTH, anchor=tk.W).grid(
                      row=0, column=0, sticky=tk.W, padx=(4, 8), pady=5)
        self.cb_kind = ttk.Combobox(fl, values=["Chữ nhật", "Tròn",
                                                 "Tiết diện bất kỳ (DXF)"],
                                    state="readonly", width=16)
        self.cb_kind.set("Chữ nhật")
        self.cb_kind.bind("<<ComboboxSelected>>",
                          lambda e: self._refresh_rebar_panel())
        self.cb_kind.grid(row=0, column=1, sticky=tk.W, padx=4, pady=5)
        # Nút import/export: frame riêng với 2 cột đều 50/50,
        # không chung cột với label để tránh bị lệch
        _dxf_btn_frame = ttk.Frame(fl)
        _dxf_btn_frame.grid(row=1, column=0, columnspan=2,
                            sticky=tk.EW, padx=0, pady=2)
        _dxf_btn_frame.columnconfigure(0, weight=1, uniform="dxfbtn")
        _dxf_btn_frame.columnconfigure(1, weight=1, uniform="dxfbtn")
        self.btn_dxf = ttk.Button(_dxf_btn_frame, text="Import (.dxf)",
                                  command=self.on_import_dxf)
        self.btn_dxf.grid(row=0, column=0, sticky=tk.EW, padx=4)
        self.btn_dxf_export = ttk.Button(_dxf_btn_frame,
                                         text="Export (.dxf)",
                                         command=self.on_export_dxf)
        self.btn_dxf_export.grid(row=0, column=1, sticky=tk.EW, padx=4)
        self.btn_prokon = ttk.Button(_dxf_btn_frame,
                                     text="Import Prokon (.C13)",
                                     command=self.on_import_prokon)
        self.btn_prokon.grid(row=1, column=0, columnspan=2, sticky=tk.EW,
                             padx=4, pady=(4, 0))
        for w in (self.en_cx, self.en_cy):
            w.bind("<FocusOut>", lambda e: self._refresh_rebar())

    # ---- 3. Bố trí cốt thép dọc (format VietconSoft) ----
    DIAS = ["10", "12", "14", "16", "18", "20", "22", "25", "28", "32"]

    def _sec_rebar(self):
        f = self._frame(T("3. Bố trí cốt thép dọc"))
        self.frm_sec_rebar = f  # để _toggle_member ẩn/hiện theo loại cấu kiện
        DIAS = self.DIAS

        # ===== Panel cho tiết diện chữ nhật =====
        self.rebar_rect = ttk.Frame(f)
        self.rebar_rect.grid(row=0, column=0, sticky=tk.NSEW)
        # Chia 50/50 để mép phải ô nhập căn với nút SAVE bên trên
        f.columnconfigure(0, weight=1, uniform="rebar")
        f.columnconfigure(1, weight=1, uniform="rebar")
        rr = self.rebar_rect
        r = 0
        self.sp_cover = ttk.Entry(rr, width=8)
        self.sp_cover.insert(0, "30")
        lbl_cover = self._row(rr, "Lớp bảo vệ cốt dọc c (mm)",
                              self.sp_cover, r)
        _ToolTip(lbl_cover, _COVER_TIP)
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
        ttk.Label(fr2, text="– d").pack(side=tk.LEFT, padx=2)
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
        ttk.Label(fr3, text="– d").pack(side=tk.LEFT, padx=2)
        self.cb_e3d.pack(side=tk.LEFT)
        self._row(rr, "Thép cạnh t3 (2 mặt trên/dưới)", fr3, r)
        r += 1
        # Toggle 2 lớp thép
        tog = tk.Frame(rr, bg="white")
        self.var_two_layer = tk.BooleanVar(value=False)
        tk.Checkbutton(tog, text="Bố trí 2 lớp thép",
                       variable=self.var_two_layer,
                       command=self._toggle_two_layer,
                       bg="white", activebackground="white",
                       highlightthickness=0).pack(side=tk.LEFT)
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
        lbl_ccover = self._row(self.rebar_circ, "Lớp bê tông bảo vệ c (mm)",
                               self.sp_ccover, 2)
        _ToolTip(lbl_ccover, _COVER_TIP)

        # ===== Panel đổi đường kính nhanh cho tiết diện DXF =====
        self.rebar_dxf = ttk.Frame(f)
        self.rebar_dxf.grid(row=0, column=0, sticky=tk.NSEW)
        self.cb_dxf_dia = ttk.Combobox(self.rebar_dxf, values=DIAS,
                                       state="readonly", width=10)
        self.cb_dxf_dia.set("20")
        self._row(self.rebar_dxf, "Đường kính mới (mm)", self.cb_dxf_dia, 0)
        btn_dxf_dia = ttk.Button(self.rebar_dxf,
                                 text="⚡ Đổi toàn bộ thép dọc",
                                 command=self.on_change_dxf_dia)
        btn_dxf_dia.grid(row=1, column=0, columnspan=2, sticky=tk.EW,
                         padx=4, pady=6)
        ttk.Label(self.rebar_dxf,
                  text="Đổi đường kính TẤT CẢ thép dọc\n"
                       "của tiết diện DXF (giữ nguyên vị trí).",
                  font=("", 8, "italic"),
                  foreground="#6B7280").grid(row=2, column=0, columnspan=2,
                                             sticky=tk.W, padx=4)

        # ===== Cốt thép đai: bên phải =====
        sw_hdr = ttk.Frame(f)
        sw_hdr.grid(row=0, column=1, sticky=tk.NSEW,
                    padx=4, pady=(4, 2))
        # Đẩy khung đai xuống 1 hàng để thẳng hàng với các dòng thép dọc:
        # hàng tiêu đề (Số nhánh/Đ.kính/K.cách) chiếm chỗ của dòng
        # "Lớp bảo vệ", Đai bao thẳng hàng "4 thanh thép góc"...
        # Ép chiều cao hàng tiêu đề bằng hàng có ô nhập bên trái
        sw_hdr.grid_rowconfigure(0, minsize=36)
        for j, t in enumerate(("Số nhánh", "Đ.kính", "K.cách")):
            ttk.Label(sw_hdr, text=t, style="Muted.TLabel").grid(
                row=0, column=j + 1, padx=2, pady=5)
            sw_hdr.columnconfigure(j + 1, weight=1)
        self.sw_inputs = {}
        for i, lbl in enumerate(("Đai bao:", "Đai giữa t2:", "Đai giữa t3:")):
            ttk.Label(sw_hdr, text=lbl, style="Muted.TLabel").grid(
                row=i + 1, column=0, sticky=tk.W, padx=2, pady=5)
            row = {}
            for j, key in enumerate(("legs", "dia", "s")):
                e = ttk.Entry(sw_hdr, width=6)
                e.grid(row=i + 1, column=j + 1, padx=2, pady=5,
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
        # Diameter là Entry: thêm KeyRelease/FocusOut để live update
        for w in (self.cb_corner_dia, self.cb_e2d, self.cb_e3d):
            try:
                w.bind("<KeyRelease>", lambda e: self._refresh_rebar())
                w.bind("<FocusOut>", lambda e: self._refresh_rebar())
            except Exception:
                pass
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
        is_dxf = self.cb_kind.get().startswith("Tiết diện bất kỳ")
        is_rect = self.cb_kind.get() == "Chữ nhật"
        is_circ = self.cb_kind.get() == "Tròn"
        # Khung phải mục 2: chữ nhật → t2/t3, tròn → đường kính,
        # DXF → note import (chỉ hiện 1 trong 3)
        try:
            if is_dxf:
                self.sec_dim_frame.grid_remove()
                self.sec_dia_frame.grid_remove()
                self.dxf_info_label.grid()
            elif is_circ:
                self.sec_dim_frame.grid_remove()
                self.dxf_info_label.grid_remove()
                self.sec_dia_frame.grid()
            else:  # chữ nhật
                self.sec_dia_frame.grid_remove()
                self.dxf_info_label.grid_remove()
                self.sec_dim_frame.grid()
        except Exception:
            pass
        if is_dxf:
            self.rebar_rect.grid_remove()
            self.rebar_circ.grid_remove()
            self.rebar_dxf.grid()
        elif is_rect:
            self.rebar_rect.grid()
            self.rebar_circ.grid_remove()
            self.rebar_dxf.grid_remove()
        else:
            self.rebar_rect.grid_remove()
            self.rebar_circ.grid()
            self.rebar_dxf.grid_remove()
        self._refresh_rebar()

    # ---- 4. Chiều dài tính toán ----
    def _sec_stability(self):
        f = self._frame(T("4. Chiều dài tính toán"))
        self.frm_sec_stability = f  # để _toggle_member ẩn/hiện theo loại cấu kiện
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
        self.cb_tx.set("Ngàm cứng")
        self.cb_bx = ttk.Combobox(f, values=bn, state="readonly", width=12)
        self.cb_bx.set("Ngàm cứng")
        self.cb_ty = ttk.Combobox(f, values=bn, state="readonly", width=12)
        self.cb_ty.set("Ngàm cứng")
        self.cb_by = ttk.Combobox(f, values=bn, state="readonly", width=12)
        self.cb_by.set("Ngàm cứng")
        self.en_psix = ttk.Entry(f, width=12)
        self.en_psiy = ttk.Entry(f, width=12)
        rows = [
            ("Chiều dài cột L (m)", self.en_Lx, self.en_Ly),
            ("Liên kết đầu trên", self.cb_tx, self.cb_ty),
            ("Liên kết đầu dưới", self.cb_bx, self.cb_by),
            ("Hệ số ψ (tự điền theo LK)", self.en_psix, self.en_psiy),
        ]
        for i, (lab, wx, wy) in enumerate(rows, start=1):
            ttk.Label(f, text=lab, width=self._LBL_WIDTH,
                      anchor=tk.W).grid(row=i, column=0, sticky=tk.W,
                                       padx=4, pady=2)
            wx.grid(row=i, column=1, padx=4, pady=2, sticky=tk.EW)
            wy.grid(row=i, column=2, padx=4, pady=2, sticky=tk.EW)
        # (Đã bỏ note L0 và ô nhập Q sway theo yêu cầu user 2026-10-16)
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
        f = self._frame(T("5. Nội lực kiểm tra"))
        self.frm_loads = f  # mốc pack "before" cho _toggle_member
        # Cho phép giãn dọc để bảng fill hết cửa sổ
        f.pack_configure(fill=tk.BOTH, expand=True)
        # Chọn chế độ: nhập tay / import Excel
        self.var_load_mode = tk.StringVar(value="etabs")
        mode_bar = ttk.Frame(f)
        mode_bar.grid(row=0, column=0, columnspan=2, sticky=tk.W,
                      padx=4, pady=4)
        st = ttk.Style()
        st.configure("White.TRadiobutton", background="white", font=("", 9))
        ttk.Radiobutton(mode_bar, text="Nhập tay", style="White.TRadiobutton",
                        variable=self.var_load_mode, value="manual",
                        command=self._toggle_load_mode).pack(side=tk.LEFT,
                                                            padx=6)
        ttk.Radiobutton(mode_bar, text="Nhập từ ETABS",
                        style="White.TRadiobutton",
                        variable=self.var_load_mode, value="etabs",
                        command=self._toggle_load_mode).pack(side=tk.LEFT,
                                                            padx=6)
        # Ghi chú về tổ hợp TX_ (in nghiêng, căn phải, cỡ chữ thường)
        ttk.Label(mode_bar,
                  text="TX_*: tổ hợp tải trọng thường xuyên để tính các tham số (không kiểm tra D/C)",
                  font=("", 9, "italic"), foreground="black").pack(side=tk.RIGHT,
                                                                   padx=(6, 6))

        # ---- Chế độ nhập tay ----
        self.manual_frame = ttk.Frame(f)
        self.manual_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW)
        self.en_N = ttk.Entry(self.manual_frame, width=18)
        self.en_N.insert(0, "1500")
        self._row(self.manual_frame, "Lực dọc N (kN)",
                  self.en_N, 0)
        self.en_Mx = ttk.Entry(self.manual_frame, width=18)
        self.en_Mx.insert(0, "80")
        self._row(self.manual_frame, "Mô men M2 (kN·m)",
                  self.en_Mx, 1)
        self.en_My = ttk.Entry(self.manual_frame, width=18)
        self.en_My.insert(0, "60")
        self._row(self.manual_frame, "Mô men M3 (kN·m)",
                  self.en_My, 2)
        self.en_Q2 = ttk.Entry(self.manual_frame, width=18)
        self.en_Q2.insert(0, "0")
        self._row(self.manual_frame, "Lực cắt V2 (kN)",
                  self.en_Q2, 3)
        self.en_Q3 = ttk.Entry(self.manual_frame, width=18)
        self.en_Q3.insert(0, "0")
        self._row(self.manual_frame, "Lực cắt V3 (kN)",
                  self.en_Q3, 4)
        self.var_lt = tk.BooleanVar(value=False)
        tk.Checkbutton(self.manual_frame, text="Khai báo thành phần tải dài hạn",
                       variable=self.var_lt,
                       command=self._toggle_lt,
                       bg="white", activebackground="white",
                       highlightthickness=0).grid(row=5, column=0,
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
        self.etabs_frame.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW)
        self.etabs_frame.grid_remove()
        f.grid_rowconfigure(1, weight=1)
        # 3 nút Import từ Etabs: giãn đều theo cửa sổ như SAVE/SAVE AS/OPEN
        btn_row = ttk.Frame(self.etabs_frame)
        btn_row.grid(row=0, column=0, columnspan=3, sticky=tk.EW,
                     padx=4, pady=4)
        st.configure("Big.TButton", font=("", 9), padding=(6, 4))
        ttk.Button(btn_row, text="Import from Excel", style="Big.TButton",
                   command=self.on_import_etabs).pack(
                       side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        ttk.Button(btn_row, text="Add from Clipboard", style="Big.TButton",
                   command=self.on_paste_etabs_add).pack(
                       side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(btn_row, text="Replace from Clipboard", style="Big.TButton",
                   command=self.on_paste_etabs).pack(
                       side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(btn_row, text="Delete", style="Big.TButton",
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
        hd = {"story": "Story", "label": "Label", "case": "Combo",
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
        # Fill dọc hết cửa sổ
        self.etabs_tree.grid(row=4, column=0, columnspan=2, padx=4, pady=4,
                             sticky=tk.NSEW)
        self.etabs_frame.grid_rowconfigure(4, weight=1)
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
