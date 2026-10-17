# Thời điểm build: lấy từ build_info.py (do build_exe.py sinh khi đóng gói).
try:
    from build_info import BUILD_TIME as APP_BUILD
except Exception:
    # Fallback: exe frozen -> mtime của file exe; source -> mtime của file này
    try:
        import os as _os, sys as _sys, datetime as _dt
        _p = _sys.executable if getattr(_sys, "frozen", False) else __file__
        APP_BUILD = _dt.datetime.fromtimestamp(
            _os.path.getmtime(_p)).strftime("%Y%m%d%H%M")
    except Exception:
        APP_BUILD = "000000000000"

import math
import tkinter as tk
from tkinter import ttk, messagebox

from rc_column.checker import ColumnInput, build_section, check_column
from rc_column.lang import T, set_lang
from rc_column.aci_materials import ACIConcrete, ACISteel
from rc_column.aci_checker import check_column_aci, moment_magnification, aci_shear_check
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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"RC Column Design [{APP_BUILD}]")
        self.geometry("1360x860")
        # Icon title bar: ưu tiên PNG (ổn định hơn ICO trên tkinter)
        try:
            import os, sys
            _base = os.path.normpath(os.path.join(
                os.path.dirname(os.path.abspath(__file__)), ".."))
            if hasattr(sys, "_MEIPASS"):
                _base = sys._MEIPASS
            _png = os.path.join(_base, "icon.png")
            _ico = os.path.join(_base, "icon.ico")
            _done = False
            if os.path.exists(_png):
                try:
                    _img = tk.PhotoImage(file=_png)
                    self.iconphoto(True, _img)
                    self._icon_img = _img
                    _done = True
                except Exception:
                    pass
            if not _done and os.path.exists(_ico):
                try:
                    self.iconbitmap(_ico)
                except Exception:
                    pass
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
        # Ép tính lại layout sau khi hiện cửa sổ (fix khoảng trống trên Win)
        self.after(300, self._refresh_layout)

    def _refresh_layout(self, _retry=0):
        """Ép tkinter tính lại layout (fix lỗi khoảng trống khi mở app)."""
        try:
            self.update_idletasks()
            for _c in ('_left_canvas', '_calc_canvas', '_sum_canvas'):
                if hasattr(self, _c):
                    cv = getattr(self, _c)
                    try:
                        cv.configure(scrollregion=cv.bbox("all"))
                        cv.yview_moveto(0)
                    except Exception:
                        pass
            # Giả lập resize: nudge kích thước 1px rồi trả lại
            # (kích hoạt lại geometry manager như khi user resize thủ công)
            _g = self.geometry()
            try:
                _w, _h = self.winfo_width(), self.winfo_height()
                if _w > 100 and _h > 100:
                    self.geometry(f"{_w+1}x{_h}")
                    self.update_idletasks()
                    self.geometry(f"{_w}x{_h}")
            except Exception:
                try:
                    self.geometry(_g)
                except Exception:
                    pass
            self.update()
            if _retry < 2:
                self.after(500, lambda: self._refresh_layout(_retry + 1))
        except Exception:
            pass

    def _fix_left_width(self, _retry=0):
        # Layout đã fix cứng bằng pack (không dùng PanedWindow), không cần set sash
        try:
            self.after(200, self._refresh_layout)
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
        # Nút hàng trên cùng: gọn như nút import, icon căn giữa
        st.configure("Top.TButton", background="white", foreground=TEXT,
                     font=("", 10), padding=(10, 4), borderwidth=1,
                     relief="solid", bordercolor=BORDER, anchor="center",
                     justify="center")
        # Nút CHECK: design nổi bật
        st.configure("Check.TButton", background=GREEN, foreground="white",
                     font=("", 11, "bold"), padding=(16, 6), borderwidth=0,
                     relief="flat", anchor=tk.CENTER)
        st.map("Check.TButton",
               background=[("active", GREEN_DARK), ("pressed", "#065F46")])
        # Tab đang chọn: highlight xanh lá nhạt
        st.configure("TabActive.TButton", background="#D1FAE5",
                     foreground="#065F46", font=("", 10, "bold"),
                     padding=(10, 4), borderwidth=1, relief="solid",
                     bordercolor="#059669", anchor="center")
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
    def _show_tab(self, which):
        """Chuyển giữa tab Kết quả / Chi tiết."""
        if which == "sum":
            self.tab_calc.pack_forget()
            self.tab_sum.pack(fill=tk.BOTH, expand=True)
            self._current_tab = "sum"
            # Highlight nút được chọn
            self._tab_btn_sum.configure(style="TabActive.TButton")
            self._tab_btn_calc.configure(style="Top.TButton")
        else:
            self.tab_sum.pack_forget()
            self.tab_calc.pack(fill=tk.BOTH, expand=True)
            self._current_tab = "calc"
            # Highlight nút được chọn
            self._tab_btn_calc.configure(style="TabActive.TButton")
            self._tab_btn_sum.configure(style="Top.TButton")

    def _switch_lang(self, lang):
        """Chuyển ngôn ngữ VN/EN. Áp dụng cho kết quả mới tính."""
        from rc_column import lang as _lang
        _lang.set_lang(lang)
        self._lang_var.set(lang)
        # Nếu đã có kết quả, tính lại để hiển thị ngôn ngữ mới
        if hasattr(self, '_last_result') and self._last_result:
            self.on_check()

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
        ttk.Button(top_grid, text="✓ CHECK", style="Check.TButton",
                   command=self.on_check).grid(row=0, column=3,
                                               sticky=tk.EW, padx=(4, 0))
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
        ttk.Label(_std_frame, text="Tiêu chuẩn:",
                  style="Muted.TLabel").pack(side=tk.LEFT, padx=(4, 4))
        self.cb_code = ttk.Combobox(_std_frame, values=["TCVN 5574:2018", "ACI 318-19",
                                                        "EC2 (EN 1992-1-1)"],
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
        self._sec_section()
        self._sec_rebar()
        self._sec_stability()
        self._sec_loads()
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
        # padx=8 để lề trái khớp với hàng 4 nút bên trên
        f = ttk.LabelFrame(self.left, text=title, padding=(12, 10),
                           style="Card.TLabelframe")
        f.pack(fill=tk.X, padx=8, pady=8)
        return f

    # Độ rộng chuẩn cho cột label (để các ô nhập thẳng hàng dọc)
    _LBL_WIDTH = 24

    def _row(self, parent, label, widget, r, c0=0):
        # Label xám nhỏ, độ rộng cố định để ô nhập thẳng hàng
        lbl = ttk.Label(parent, text=label, style="Muted.TLabel",
                        width=self._LBL_WIDTH, anchor=tk.W)
        lbl.grid(row=r, column=c0, sticky=tk.W, padx=(4, 8), pady=5)
        widget.grid(row=r, column=c0 + 1, sticky=tk.EW, padx=4, pady=5)
        parent.columnconfigure(c0 + 1, weight=1)
        return lbl

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
            ttk.Label(parent, text=llab, style="Muted.TLabel").grid(
                row=r, column=0, sticky=tk.W, padx=(4, 8), pady=5)
            lwid.grid(row=r, column=1, sticky=tk.EW, padx=4, pady=5)
            ttk.Label(parent, text=rlab, style="Muted.TLabel").grid(
                row=r, column=2, sticky=tk.W, padx=(4, 8), pady=5)
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
        _mat_row(self.frm_ec2, 0, "Bê tông", self.cb_ec2_conc,
                 "Phương pháp tính bậc 2", self.cb_ec2_method)
        _mat_row(self.frm_ec2, 1, "Thép dọc fyk (MPa)", self.en_ec2_fyk,
                 "Thép đai fyk (MPa)", self.en_ec2_fyt)
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

    def is_aci(self):
        return self.cb_code.get().startswith("ACI")

    def is_ec2(self):
        return self.cb_code.get().startswith("EC2")

    # ---- 2. Tiết diện ----
    def _sec_section(self):
        f = self._frame(T("2. Tiết diện"))
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
        for w in (self.en_cx, self.en_cy):
            w.bind("<FocusOut>", lambda e: self._refresh_rebar())

    # ---- 3. Bố trí cốt thép dọc (format VietconSoft) ----
    DIAS = ["10", "12", "14", "16", "18", "20", "22", "25", "28", "32"]

    def _sec_rebar(self):
        f = self._frame(T("3. Bố trí cốt thép dọc"))
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
        ttk.Button(btn_row, text="Chọn file Excel", style="Big.TButton",
                   command=self.on_import_etabs).pack(
                       side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        ttk.Button(btn_row, text="Paste từ Clipboard", style="Big.TButton",
                   command=self.on_paste_etabs).pack(
                       side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(btn_row, text="Xóa nội lực", style="Big.TButton",
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
        is_dxf = self.cb_kind.get().startswith("Tiết diện bất kỳ")
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
        # Tiết diện tròn: đường kính D dùng cho cả 2 chiều
        _dia = self._f(self.en_dia, 600.0)
        _cx = self._f(self.en_cx, 400.0) if is_rect else _dia
        _cy = self._f(self.en_cy, 400.0) if is_rect else _dia
        inp = ColumnInput(
            concrete_grade=self.cb_conc.get(), gamma_b=self._f(self.en_gb, 0.85),
            steel_grade=self.cb_steel.get(),
            sw_steel_grade=self.cb_sw_steel.get(),
            gamma_s=self._f(self.en_gs, 1.0),
            concrete_model=model,
            section_type="poly" if is_dxf else ("rect" if is_rect else "circle"),
            cx=_cx, cy=_cy,
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
        if is_dxf:
            inp.poly_section = getattr(self, "_dxf_section", None)
        return inp

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
            draw_section_ax(ax1, sec, show_stats=False, dot_scale=1.5)
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
            if self.is_ec2():
                self._check_ec2(inp)
                return
            if self.is_aci():
                self._check_aci(inp)
                return
            res = check_column(inp, n_angles=24)
        except Exception as ex:
            messagebox.showerror("Lỗi", str(ex))
            return
        # Tóm tắt + biểu đồ + L0
        sec = build_section(inp)
        self._show_summary(sec, inp, res)
        # Thuyết minh (có format màu sắc) + nhúng hình
        self._render_report_sections(generate_report_sections(inp, res),
                                      sec, inp, res, case_info=None,
                                      shear_info=None)
        self._pdf_inp, self._pdf_res = inp, res

    def _check_aci(self, inp):
        """Kiểm tra cột theo ACI 318-19: P-M-M, độ mảnh, cắt. Vẽ biểu đồ + thuyết minh."""
        from rc_column.aci_materials import ACIConcrete, ACISteel
        from rc_column.aci_checker import (check_column_aci, moment_magnification,
                                          aci_shear_check)
        from rc_column.aci_report import generate_aci_report_sections
        try:
            fc = float(self.en_fc.get().replace(",", "."))
            fy = float(self.en_fy.get().replace(",", "."))
            fyt = float(self.en_fyt.get().replace(",", "."))
        except Exception:
            messagebox.showerror("Lỗi", "Nhập f'c, fy và fyt hợp lệ (MPa).")
            return
        tied = "tied" in self.cb_tie.get().lower()
        conc = ACIConcrete(fc=fc)
        steel = ACISteel(fy=fy)
        sec = build_section(inp)
        # 1. Độ mảnh & phóng đại mô men (ACI 6.6.4) — tính TRƯỚC, áp vào mô men
        # P0-1/P0-3: Mc = δns·M theo từng phương, rồi mới check P-M-M
        try:
            from rc_column.stability import effective_length
            # Phương 2 (M2): lu = Lx, Ig = t3·t2³/12
            L0_2 = effective_length(inp.Lx, inp.top_x, inp.bottom_x, inp.psi_x) * 1000
            Ig2 = sec.cx * sec.cy**3 / 12
            mm2 = moment_magnification(Pu_kN=inp.N, M1_kNm=inp.Mx, M2_kNm=inp.Mx,
                                      lu_mm=L0_2, k=1.0, Ec_MPa=conc.Ec,
                                      Ig_mm4=Ig2, beta_dns=0.6)
            # Phương 3 (M3): lu = Ly, Ig = t2·t3³/12
            L0_3 = effective_length(inp.Ly, inp.top_y, inp.bottom_y, inp.psi_y) * 1000
            Ig3 = sec.cy * sec.cx**3 / 12
            mm3 = moment_magnification(Pu_kN=inp.N, M1_kNm=inp.My, M2_kNm=inp.My,
                                      lu_mm=L0_3, k=1.0, Ec_MPa=conc.Ec,
                                      Ig_mm4=Ig3, beta_dns=0.6)
            d2 = mm2.get("delta_ns", 1.0)
            d3 = mm3.get("delta_ns", 1.0)
            Mc2 = d2 * inp.Mx
            Mc3 = d3 * inp.My
            mm_res = {"dir2": mm2, "dir3": mm3, "delta2": d2, "delta3": d3,
                        "L0_2": L0_2/1000, "L0_3": L0_3/1000}
        except Exception:
            Mc2, Mc3 = inp.Mx, inp.My
            mm_res = None
        # 1b. Sway (ACI 6.6.4.6): δs = 1/(1-Q) — đã bỏ ô nhập, luôn Q=0 (bỏ qua)
        from rc_column.aci_checker import sway_magnification
        Qsw = 0.0
        sway_res = None
        if Qsw > 0:
            sway_res = sway_magnification(Q=Qsw)
            ds = sway_res.get("delta_s", 1.0)
            Mc2 *= ds
            Mc3 *= ds
        self._aci_sway = sway_res
        # 2. P-M-M với mô men đã phóng đại
        try:
            aci_res = check_column_aci(sec, conc, steel, N_kN=inp.N,
                                       M2_kNm=Mc2, M3_kNm=Mc3, tied=tied)
            # Lưu mô men gốc và phóng đại để thuyết minh
            aci_res["M2_orig"] = inp.Mx
            aci_res["M3_orig"] = inp.My
            aci_res["M2_mag"] = Mc2
            aci_res["M3_mag"] = Mc3
        except Exception as ex:
            messagebox.showerror("Lỗi ACI P-M-M", str(ex))
            return
        # 3. Cắt
        try:
            Acv = sec.cx * sec.cy
            d = sec.cy - inp.cover - 10
            Av = 2 * 3.1416 * (8**2) / 4
            try:
                _sh2 = aci_shear_check(Acv_mm2=Acv, Ag_mm2=Acv, fc_MPa=fc,
                                       Nu_kN=inp.N, Vu_kN=abs(inp.Q2),
                                       Av_mm2=Av, fyt_MPa=fyt, s_mm=200, d_mm=d)
            except Exception:
                _sh2 = None
            try:
                _sh3 = aci_shear_check(Acv_mm2=Acv, Ag_mm2=Acv, fc_MPa=fc,
                                       Nu_kN=inp.N, Vu_kN=abs(inp.Q3),
                                       Av_mm2=Av, fyt_MPa=fyt, s_mm=200, d_mm=d)
            except Exception:
                _sh3 = None
            # Gộp 2 phương vào shear_res
            if _sh2 is not None or _sh3 is not None:
                shear_res = {"dir2": _sh2 or {}, "dir3": _sh3 or {}}
                # Giữ tương thích: các key cũ lấy từ phương có Vu lớn nhất
                _mx = _sh2 if abs(inp.Q2) >= abs(inp.Q3) else _sh3
                if _mx:
                    shear_res.update(_mx)
            else:
                shear_res = None
        except Exception:
            shear_res = None
        # Lưu để vẽ lại / xuất PDF
        self._aci_sec = sec
        self._aci_inp = inp
        # Đảm bảo có tên file cho PDF (giống TCVN)
        try:
            self._aci_inp._filename = self.member_var.get().strip() if hasattr(self, "member_var") else ""
        except Exception:
            pass
        self._aci_res = aci_res
        self._aci_conc = conc
        self._aci_steel = steel
        self._aci_tied = tied
        self._aci_mm = mm_res
        self._aci_shear = shear_res
        # Vẽ tab Kết quả
        self._show_aci_summary()
        # Vẽ tab Chi tiết
        try:
            from rc_column.aci_report_v2 import generate_aci_report_sections_v2
            sections = generate_aci_report_sections_v2(
                inp, aci_res, mm_res, shear_res, conc, steel, sec,
                tied, fyt)
        except Exception as ex:
            messagebox.showerror("Lỗi thuyết minh ACI",
                                 f"Không tạo được thuyết minh ACI:\n{ex}")
            return
        try:
            self._render_aci_report(sections)
        except Exception as ex:
            messagebox.showerror("Lỗi hiển thị ACI",
                                 f"Không hiển thị được tab Chi tiết:\n{ex}")
            return
        self._pdf_inp, self._pdf_res = inp, None  # đánh dấu ACI mode
        self._update_ck()  # cập nhật tên cấu kiện

    def _check_ec2(self, inp):
        """Kiểm tra cột theo EC2 (EN 1992-1-1): P-M-M, độ mảnh (bậc 2), cắt."""
        from rc_column.ec2_materials import (EC2Concrete, EC2Steel,
                                             EC2_CONCRETE_GRADES,
                                             EC2_STEEL_GRADES)
        from rc_column.ec2_checker import (ec2_design_moment, check_column_ec2,
                                           ec2_shear_check, ec2_balanced_point)
        from rc_column.ec2_report import generate_ec2_report_sections
        from rc_column.sections import bar_area
        try:
            fck = EC2_CONCRETE_GRADES.get(self.cb_ec2_conc.get(), 30.0)
            fyk = float(self.en_ec2_fyk.get().replace(",", "."))
            fyk_sw = float(self.en_ec2_fyt.get().replace(",", "."))
        except Exception:
            messagebox.showerror("Lỗi", "Nhập fyk thép đai hợp lệ (MPa).")
            return
        method = ("curvature"
                  if self.cb_ec2_method.get().startswith("Độ cong")
                  else "stiffness")
        conc = EC2Concrete(fck=fck)
        steel = EC2Steel(fyk=fyk)
        try:
            sec = build_section(inp)
        except Exception as ex:
            messagebox.showerror("Lỗi tiết diện", str(ex))
            return
        # 1. Hình học theo từng phương (bbox cho poly, như ACI)
        cx, cy = sec.cx, sec.cy  # t3 (ngang), t2 (đứng)
        Ac = sec.gross_area
        As = sec.steel_area
        try:
            from rc_column.stability import effective_length
            l0_2 = effective_length(inp.Lx, inp.top_x, inp.bottom_x,
                                    inp.psi_x) * 1000.0  # mm
            l0_3 = effective_length(inp.Ly, inp.top_y, inp.bottom_y,
                                    inp.psi_y) * 1000.0
        except Exception:
            l0_2 = l0_3 = (inp.Lx or 4.0) * 1000.0
        # Ic mỗi phương (bbox): phương 2 → Ig = t3·t2³/12, phương 3 → t2·t3³/12
        geom = {}
        for lbl, h_dim, Ic in (("dir2", cy, cx * cy**3 / 12.0),
                               ("dir3", cx, cy * cx**3 / 12.0)):
            geom[lbl] = {"h": h_dim, "Ic": Ic,
                         "i": math.sqrt(Ic / Ac) if Ac > 0 else h_dim,
                         "l0": l0_2 if lbl == "dir2" else l0_3}
        # n_bal cho phương pháp độ cong danh nghĩa (Kr)
        n_bal = 0.0
        if method == "curvature":
            try:
                Nb, _Mb = ec2_balanced_point(sec, conc, steel, 0.0)
                n_bal = Nb / (conc.fcd * Ac / 1000.0) if Ac > 0 else 0.0
            except Exception:
                n_bal = 0.0
        # 2. Mô men thiết kế mỗi phương (đã gồm sai lệch, emin, bậc 2)
        dm = {}
        try:
            for lbl, Mdir in (("dir2", inp.Mx), ("dir3", inp.My)):
                g = geom[lbl]
                dm[lbl] = ec2_design_moment(
                    NEd_kN=inp.N, M_top_kNm=abs(Mdir),
                    M_bot_kNm=abs(Mdir), l0_mm=g["l0"], i_mm=g["i"],
                    h_mm=g["h"], Ac_mm2=Ac, As_mm2=As,
                    fcd_MPa=conc.fcd, fyd_MPa=steel.fyd,
                    Ecm_MPa=conc.Ecm, Ic_mm4=g["Ic"], Is_mm4=0.0,
                    Es_MPa=steel.Es, fck_MPa=fck,
                    unbraced=False, method=method,
                    d_mm=max(g["h"] - inp.cover - 10.0, 0.5 * g["h"]),
                    eps_yd=steel.eps_yd, n_bal=n_bal,
                    const_moment=True)
        except Exception as ex:
            messagebox.showerror("Lỗi độ mảnh EC2", str(ex))
            return
        MEd2 = dm["dir2"]["MEd"]
        MEd3 = dm["dir3"]["MEd"]
        # Lưu l0 (m) và lambda để report dùng
        dm["l0_2"] = l0_2 / 1000.0
        dm["l0_3"] = l0_3 / 1000.0
        dm["lambda_2"] = (l0_2 / geom["dir2"]["i"]) if geom["dir2"]["i"] > 0 else 0
        dm["lambda_3"] = (l0_3 / geom["dir3"]["i"]) if geom["dir3"]["i"] > 0 else 0
        # 3. P-M-M với mô men thiết kế
        try:
            ec2_res = check_column_ec2(sec, conc, steel, N_kN=inp.N,
                                       M2_kNm=MEd2, M3_kNm=MEd3)
            ec2_res["M2_orig"] = inp.Mx
            ec2_res["M3_orig"] = inp.My
            ec2_res["M2_mag"] = MEd2
            ec2_res["M3_mag"] = MEd3
            ec2_res["method"] = method
        except Exception as ex:
            messagebox.showerror("Lỗi EC2 P-M-M", str(ex))
            return
        # 4. Cắt mỗi phương (EC2 6.2)
        try:
            sw_dia = getattr(inp, "sw_dia", 8.0) or 8.0
            sw_s = getattr(inp, "sw_spacing", 200.0) or 200.0
            sw_legs = getattr(inp, "sw_legs", 2) or 2
            Asw = sw_legs * bar_area(sw_dia)
            Asw_s = Asw / sw_s if sw_s > 0 else 0.0
            fyd_sw = fyk_sw / 1.15
            dia_max = max((r.dia for r in sec.rebars), default=20.0)
            Asl = As / 2.0  # thép dọc chịu kéo neo qua gối (ước lượng)
            shear = {}
            # V2: bw = t2 = cy, d từ t3 = cx; V3 ngược lại
            for Vu, lbl, bw, h_dim in ((abs(inp.Q2), "dir2", cy, cx),
                                       (abs(inp.Q3), "dir3", cx, cy)):
                d = h_dim - inp.cover - sw_dia - dia_max / 2.0
                shear[lbl] = ec2_shear_check(
                    bw_mm=bw, d_mm=max(d, 0.5 * h_dim), Ac_mm2=Ac,
                    fck_MPa=fck, NEd_kN=max(inp.N, 0.0), VEd_kN=Vu,
                    Asl_mm2=Asl, fyd_MPa=fyd_sw, Asw_s_mm2mm=Asw_s,
                    theta_deg=45.0)
                shear[lbl]["bw"] = bw
                shear[lbl]["d"] = d
                shear[lbl]["VEd"] = Vu
            shear_res = shear
        except Exception:
            shear_res = None
        # Lưu để vẽ lại / xuất PDF
        self._ec2_sec = sec
        self._ec2_inp = inp
        try:
            self._ec2_inp._filename = self.member_var.get().strip() if hasattr(self, "member_var") else ""
        except Exception:
            pass
        self._ec2_res = ec2_res
        self._ec2_conc = conc
        self._ec2_steel = steel
        self._ec2_slend = dm
        self._ec2_shear = shear_res
        self._ec2_method = method
        # Vẽ tab Kết quả
        self._show_ec2_summary()
        # Vẽ tab Chi tiết
        try:
            from rc_column.ec2_report_v2 import generate_ec2_report_sections_v2
            sections = generate_ec2_report_sections_v2(
                inp, ec2_res, dm, shear_res, conc, steel, sec)
        except Exception as ex:
            messagebox.showerror("Lỗi thuyết minh EC2",
                                 f"Không tạo được thuyết minh EC2:\n{ex}")
            return
        try:
            self._render_ec2_report(sections)
        except Exception as ex:
            messagebox.showerror("Lỗi hiển thị EC2",
                                 f"Không hiển thị được tab Chi tiết:\n{ex}")
            return
        self._pdf_inp, self._pdf_res = inp, None  # đánh dấu EC2 mode
        self._update_ck()  # cập nhật tên cấu kiện

    def _show_aci_summary(self):
        """Tab Kết quả tính toán cho ACI: layout 2x2 giống TCVN.
        Hàng trên: [mặt cắt + thẻ TK | bảng thông số] /
        Hàng dưới: [biểu đồ N-Mα | biểu đồ M2-M3]."""
        if not HAS_MPL:
            return
        import math
        sec = self._aci_sec
        inp = self._aci_inp
        aci_res = self._aci_res
        conc = self._aci_conc
        steel = self._aci_steel
        tied = self._aci_tied
        mm_res = getattr(self, "_aci_mm", None)
        from rc_column.aci_chart_draw import (draw_aci_nm_alpha_ax,
                                              draw_aci_m2m3_ax)
        from rc_column.pdf_export import draw_section_ax
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        def _new_fig(parent, figsize):
            fig = Figure(figsize=figsize, dpi=100)
            cv = FigureCanvasTkAgg(fig, master=parent)
            _w = cv.get_tk_widget()
            try:
                # takefocus=0 ngăn canvas chiếm focus (đủ để cuộn chuột
                # hoạt động); KHÔNG chặn ButtonPress/Release để biểu đồ
                # 3D xoay được bằng kéo chuột
                _w.configure(highlightthickness=0, takefocus=0,
                             highlightbackground="white",
                             highlightcolor="white", borderwidth=0)
            except Exception:
                pass
            _w.pack(fill=tk.BOTH, expand=True)
            return fig, cv

        # Xóa nội dung cũ
        for w in self._sum_inner.winfo_children():
            w.destroy()
        self._sum_inner.columnconfigure(0, weight=1)
        self._sum_inner.columnconfigure(1, weight=1)
        self._sum_inner.rowconfigure(0, weight=1)
        self._sum_inner.rowconfigure(1, weight=1)

        # ===== Ô trên-phải: sơ đồ mặt cắt + thẻ thống kê =====
        f_tl = tk.Frame(self._sum_inner, bg="white",
                        highlightbackground="#D1D5DB", highlightthickness=1)
        f_tl.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        tk.Label(f_tl, text="SƠ ĐỒ MẶT CẮT TIẾT DIỆN CỘT",
                 font=("", 11, "bold"), bg="white").pack(pady=(2, 2))
        self.ck_var = tk.StringVar(value="")
        # Bỏ hiển thị tên cấu kiện ở sơ đồ (đã có ở textbox panel trái)
        fig_sec, cv_sec = _new_fig(f_tl, (3.9, 3.1))
        a1 = fig_sec.add_subplot(111)
        draw_section_ax(a1, sec, show_stats=False, dot_scale=1.5)
        fig_sec.tight_layout()
        cv_sec.draw()
        self._sec_fig, self._sec_canvas, self._sec_ax = fig_sec, cv_sec, a1
        # Thẻ thống kê ACI: hàng vật liệu + hàng số liệu thép
        self._build_aci_section_cards(f_tl, sec, conc, steel, tied)

        # ===== Ô trên-trái: bảng thông số tính toán ACI =====
        f_tr = tk.Frame(self._sum_inner, bg="white",
                        highlightbackground="#D1D5DB", highlightthickness=1)
        f_tr.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._build_aci_param_table(f_tr, inp, aci_res, mm_res)

        # ===== Ô dưới-trái: header + biểu đồ N-Mα (ACI) =====
        f_bl = ttk.Frame(self._sum_inner)
        f_bl.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._build_aci_nm_header(f_bl, inp)
        fig_nm, cv_nm = _new_fig(f_bl, (5.2, 3.9))
        self._aci_nm_fig = fig_nm
        a3 = fig_nm.add_subplot(111)
        draw_aci_nm_alpha_ax(a3, sec, conc, steel, aci_res,
                             inp.N, inp.Mx, inp.My, tied=tied)
        fig_nm.tight_layout()
        fig_nm.subplots_adjust(bottom=0.30)
        cv_nm.draw()
        # Lưu tham chiếu để vẽ lại khi đổi góc xem
        self._aci_nm_ax_ref = a3
        self._aci_nm_cv_ref = cv_nm

        # ===== Ô dưới-phải: header + biểu đồ M2-M3 (ACI) =====
        f_br = ttk.Frame(self._sum_inner)
        f_br.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        self._build_aci_m2m3_header(f_br, inp)
        fig_mm, cv_mm = _new_fig(f_br, (5.2, 3.9))
        self._aci_m2m3_fig = fig_mm
        a4 = fig_mm.add_subplot(111)
        draw_aci_m2m3_ax(a4, sec, conc, steel, aci_res,
                         inp.N, inp.Mx, inp.My, tied=tied)
        fig_mm.tight_layout()
        fig_mm.subplots_adjust(bottom=0.30)
        cv_mm.draw()

        # ===== Hàng 3 full-width: chi tiết điểm A/B + D/C =====
        f_notes = ttk.Frame(self._sum_inner, style="Card.TLabelframe")
        f_notes.grid(row=2, column=0, columnspan=2, sticky="ew",
                     padx=4, pady=(4, 12))
        self._build_aci_notes(f_notes, inp, aci_res)
        self._sum_inner.rowconfigure(2, weight=0)

        # ===== Hàng 4 full-width: bảng kiểm tra cắt ACI =====
        f_sw = ttk.Frame(self._sum_inner, style="Card.TLabelframe")
        f_sw.grid(row=3, column=0, columnspan=2, sticky="ew",
                  padx=4, pady=4)
        self._build_aci_shear_summary(f_sw, inp, sec, conc, steel)
        self._sum_inner.rowconfigure(3, weight=0)

        # Gắn lại cuộn chuột cho các widget mới
        self._bind_wheel(self._sum_inner, self._sum_canvas)
        def _to_top():
            try:
                self._sum_inner.update_idletasks()
                self._sum_canvas.configure(
                    scrollregion=self._sum_canvas.bbox("all"))
                self._sum_canvas.yview_moveto(0)
            except Exception:
                pass
        self._sum_canvas.after_idle(_to_top)

    def _build_aci_section_cards(self, parent, sec, conc, steel, tied):
        """6 thẻ thống kê ACI: hàng vật liệu (f'c, fy, đai) + hàng thép."""
        vals = self._section_card_values(sec)

        def _card(prow, title, value, sub=None):
            cell = tk.Frame(prow, bg="white",
                            highlightbackground="#E5E7EB",
                            highlightthickness=1, height=52)
            cell.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3, pady=2)
            cell.pack_propagate(False)
            tk.Label(cell, text=title, font=("", 8), fg="#6B7280",
                     bg="white").pack(pady=(6, 0))
            tk.Label(cell, text=value, font=("", 11, "bold"),
                     bg="white").pack(pady=2)
            if sub:
                tk.Label(cell, text=sub, font=("", 8),
                         fg="#6B7280", bg="white").pack()

        # (Đã bỏ hàng vật liệu ACI theo yêu cầu user — chỉ giữ hàng thép)
        # Hàng số liệu thép
        row1 = tk.Frame(parent, bg="#F9FAFB")
        row1.pack(fill=tk.X, padx=2, pady=(2, 4))
        _card(row1, "Số thanh", vals["n"], vals.get("nsub", ""))
        _card(row1, "Tổng As", vals["as"])
        _card(row1, "Diện tích Ab", vals["ab"])
        _card(row1, "Hàm lượng μ", vals["mu"])

    def _build_aci_shear_summary(self, parent, inp, sec, conc, steel):
        """Bảng kiểm tra khả năng chịu cắt ACI: Phương V2 | Phương V3."""
        from rc_column.aci_checker import aci_shear_check
        from rc_column.sections import bar_area
        try:
            fc = conc.fc
            fyt = getattr(steel, "fyt", steel.fy)
            # Thông tin đai
            sw_dia = getattr(inp, "sw_dia", 10)
            sw_spacing = getattr(inp, "sw_spacing", 200)
            sw_legs = getattr(inp, "sw_legs", 2)
            Av = sw_legs * bar_area(sw_dia)
            sw_txt = f"{sw_legs:.0f}φ{sw_dia:.0f} a{sw_spacing:.0f}"

            cols = {}
            # V2: b = t2 = cy, d từ t3 = cx
            # V3: b = t3 = cx, d từ t2 = cy
            for Vu, lbl, b_w, h_dim in (
                    (abs(inp.Q2), "2", inp.cy, inp.cx),
                    (abs(inp.Q3), "3", inp.cx, inp.cy)):
                d = h_dim - inp.cover - sw_dia - 12
                Acv = b_w * d
                Ag = inp.cx * inp.cy
                sr = aci_shear_check(Acv_mm2=Acv, Ag_mm2=Ag, fc_MPa=fc,
                                    Nu_kN=max(inp.N, 0), Vu_kN=Vu,
                                    Av_mm2=Av, fyt_MPa=fyt,
                                    s_mm=sw_spacing, d_mm=d)
                cols[lbl] = dict(Vu=Vu, b=b_w, d=d, Av=Av,
                                Vc=sr["Vc_kN"], Vs=sr["Vs_kN"],
                                phiVn=sr["phi_Vn_kN"], ok=sr["ok"],
                                sw_txt=sw_txt)

            tf = tk.Frame(parent, bg="white")
            tf.pack(fill=tk.X, padx=8, pady=6)
            headers = ["KIỂM TRA KHẢ NĂNG CHỊU CẮT", "Phương V2", "Phương V3"]
            for j, h in enumerate(headers):
                tk.Label(tf, text=h, font=("", 9, "bold"), bg="#F3F4F6",
                         fg="#111827", borderwidth=0,
                         highlightthickness=0,
                         anchor="w" if j == 0 else "center",
                         padx=6, pady=7).grid(row=0, column=j, sticky="nsew")
                tf.columnconfigure(j, weight=2 if j == 0 else 1, uniform="sw")
            rows = [
                ("Thép đai bố trí",
                 cols['2']['sw_txt'], cols['3']['sw_txt']),
                ("Lực cắt tính toán, Vu",
                 f"{cols['2']['Vu']:.1f} kN", f"{cols['3']['Vu']:.1f} kN"),
                ("Kích thước tiết diện, b × d",
                 f"{cols['2']['b']:.0f} × {cols['2']['d']:.0f} mm",
                 f"{cols['3']['b']:.0f} × {cols['3']['d']:.0f} mm"),
                ("Av = n × φ",
                 f"{cols['2']['Av']:.0f} mm²", f"{cols['3']['Av']:.0f} mm²"),
                ("Vc = max[0.17λ√f'c, 0.66λsλ(ρw)⅓√f'c]·bw·d (ACI 22.5.5)",
                 f"{cols['2']['Vc']:.1f} kN", f"{cols['3']['Vc']:.1f} kN"),
                ("Vs = Av·fyt·d/s (ACI 22.5.8)",
                 f"{cols['2']['Vs']:.1f} kN", f"{cols['3']['Vs']:.1f} kN"),
                ("φVn = φ·(Vc+Vs) ≤ φ·(Vc+0.66√f'c·bw·d)",
                 f"{cols['2']['phiVn']:.1f} kN", f"{cols['3']['phiVn']:.1f} kN"),
                ("Kết luận",
                 "ĐẠT" if cols['2']['ok'] else "KHÔNG ĐẠT",
                 "ĐẠT" if cols['3']['ok'] else "KHÔNG ĐẠT"),
            ]
            for i, (a, b, c) in enumerate(rows):
                bg = "#F9FAFB" if i % 2 else "white"
                is_kl = (a == "Kết luận")
                for j, t in enumerate((a, b, c)):
                    fw = ("", 9)  # nội dung bảng không in đậm
                    fg = "#1F2937"
                    if is_kl and j > 0:
                        fg = "#065F46" if t == "ĐẠT" else "#991B1B"
                        fw = ("", 9, "bold")  # kết quả in đậm
                    tk.Label(tf, text=t, font=fw, bg=bg, fg=fg,
                             borderwidth=0, highlightthickness=0,
                             padx=6, pady=6, anchor="w" if j == 0
                             else "center").grid(row=i + 1, column=j,
                                                 sticky="nsew")
        except Exception as e:
            tk.Label(parent, text=f"Không tính được chịu cắt: {e}",
                     fg="#991B1B", bg="white").pack(padx=8, pady=4)

    def _build_aci_param_table(self, parent, inp, aci_res, mm_res):
        """Bảng thông số tính toán ACI (Treeview 3 cột)."""
        import math
        ttk.Label(parent, text="BẢNG THÔNG SỐ TÍNH TOÁN (ACI 318-19)",
                  font=("", 11, "bold")).pack(pady=(2, 6))
        cols = ("sym", "desc", "val")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=16,
                            style="Param.Treeview")
        _pst = ttk.Style()
        _pst.configure("Param.Treeview.Heading", font=("", 9, "bold"),
                       background="#F3F4F6", foreground="#111827",
                       relief="flat", borderwidth=0)
        tree.heading("sym", text="Ký hiệu")
        tree.heading("desc", text="Thông số")
        tree.heading("val", text="Giá trị")
        tree.column("sym", width=64, anchor="center", stretch=False)
        tree.column("desc", width=200, anchor="w")
        tree.column("val", width=220, anchor="e", stretch=False)
        tree.tag_configure("odd", background="#F9FAFB")
        dc_bg = "#D1FAE5" if aci_res["ok"] else "#FEE2E2"
        dc_fg = "#065F46" if aci_res["ok"] else "#991B1B"
        tree.tag_configure("dc", background=dc_bg, foreground=dc_fg)
        alpha_deg = math.degrees(math.atan2(inp.Mx, inp.My)) \
            if abs(inp.Mx) + abs(inp.My) > 1e-9 else 0.0
        Ma = math.hypot(inp.Mx, inp.My)
        delta_txt = "—"
        if mm_res:
            try:
                d2 = mm_res.get("delta2", 1.0)
                d3 = mm_res.get("delta3", 1.0)
                delta_txt = f"δ2={d2:.3f}, δ3={d3:.3f}"
            except Exception:
                pass
        rows = [
            ("N", "Lực dọc tính toán",
             f"{inp.N:+.1f} kN"),
            ("M2", "Mô men phương 2",
             f"{inp.Mx:.1f} kN·m"),
            ("M3", "Mô men phương 3",
             f"{inp.My:.1f} kN·m"),
            ("α", "Góc tác dụng mô men",
             f"{alpha_deg:.1f} °"),
            ("Mα", "Mô men tổng hợp",
             f"{Ma:.1f} kN·m"),
            ("e2", "Độ lệch tâm phương 2 (M2/N)",
             f"{abs(inp.Mx/inp.N*1000):.1f} mm" if abs(inp.N) > 1e-9 else "—"),
            ("e3", "Độ lệch tâm phương 3 (M3/N)",
             f"{abs(inp.My/inp.N*1000):.1f} mm" if abs(inp.N) > 1e-9 else "—"),
            ("φ", "Hệ số sức kháng (ACI 21.2.2)",
             f"{aci_res['phi']:.2f}"),
            ("εt", "Biến dạng thép chịu kéo xa nhất",
             f"{aci_res.get('eps_t', 0):.5f}"),
            ("β1", "Hệ số khối ứng suất chữ nhật",
             f"{aci_res.get('beta1', 0.85):.2f}"),
            ("δns", "Hệ số phóng đại mô men (ACI 6.6.4)",
             delta_txt),
            ("M2*", "Mô men tính toán phương 2 (đã phóng đại)",
             f"{aci_res.get('M2_mag', inp.Mx):.1f} kN·m"),
            ("M3*", "Mô men tính toán phương 3 (đã phóng đại)",
             f"{aci_res.get('M3_mag', inp.My):.1f} kN·m"),
            ("NB", "Lực dọc tại điểm giới hạn B (trên tia tải)",
             f"{aci_res.get('BN', 0):+.1f} kN"),
            ("φPn,max", "Nén đúng tâm lớn nhất (ACI 22.4.2)",
             f"{aci_res.get('N_cap', 0):.1f} kN"),
        ]
        for i, (a, b, c) in enumerate(rows):
            tree.insert("", "end", values=(a, b, c),
                        tags=("odd",) if i % 2 else ())
        ok_txt = "ĐẠT" if aci_res["ok"] else "KHÔNG ĐẠT"
        fs_txt = (f"{aci_res['fs']:.2f}"
                  if math.isfinite(aci_res.get("fs", 0)) else "∞")
        tree.insert("", "end",
                    values=("D/C", "Tỷ số sử dụng khả năng chịu lực",
                            f"{aci_res['dc']:.3f} (FS = {fs_txt})  {ok_txt}"),
                    tags=("dc",))
        tree.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

    def _build_aci_nm_header(self, parent, inp):
        """Header trên biểu đồ N-Mα (ACI)."""
        import math
        alpha_deg = math.degrees(math.atan2(inp.Mx, inp.My)) \
            if abs(inp.Mx) + abs(inp.My) > 1e-9 else 0.0
        hdr = ttk.Frame(parent)
        hdr.pack(fill=tk.X, padx=4, pady=(2, 2))
        left = ttk.Frame(hdr)
        left.pack(side=tk.LEFT)
        tk.Label(left, text="● Biểu đồ tương tác N–Mα",
                 font=("", 10, "bold"), bg="white").pack(side=tk.LEFT)
        self._aci_nm_alpha_lbl = tk.Label(
            left, text=f"  α = {alpha_deg:.1f}°  ",
            font=("", 8, "bold"), fg="#065F46", bg="#D1FAE5")
        self._aci_nm_alpha_lbl.pack(side=tk.LEFT, padx=6)
        # Combobox chọn góc xem biểu đồ N-M
        right = ttk.Frame(hdr)
        right.pack(side=tk.RIGHT)
        tk.Label(right, text="Góc xem:", font=("", 9),
                 bg="white").pack(side=tk.LEFT)
        _vals = ["α (góc tải)", "3D"] + [f"{d}°" for d in range(0, 361, 15)]
        self._aci_nm_angle_cb = ttk.Combobox(
            right, values=_vals, width=11, state="readonly", font=("", 9))
        self._aci_nm_angle_cb.set("α (góc tải)")
        self._aci_nm_angle_cb.pack(side=tk.LEFT, padx=(4, 0))
        self._aci_nm_angle_cb.bind("<<ComboboxSelected>>",
                                   self._on_aci_nm_angle_changed)
        self._aci_nm_view_angle = None  # None = góc tải mặc định

    def _on_aci_nm_angle_changed(self, event=None):
        """Vẽ lại biểu đồ N-Mα (ACI) tại góc được chọn."""
        try:
            sel = self._aci_nm_angle_cb.get()
            if sel == "3D":
                self._draw_3d_aci()
                return
            if sel.startswith("α"):
                angle = None
            else:
                angle = float(sel.replace("°", ""))
        except Exception:
            angle = None
        self._aci_nm_view_angle = angle
        try:
            if angle is None:
                import math
                inp = self._aci_inp
                a0 = math.degrees(math.atan2(inp.Mx, inp.My)) \
                    if abs(inp.Mx) + abs(inp.My) > 1e-9 else 0.0
                self._aci_nm_alpha_lbl.config(text=f"  α = {a0:.1f}°  ")
            else:
                self._aci_nm_alpha_lbl.config(text=f"  xem {angle:.0f}°  ")
        except Exception:
            pass
        try:
            from rc_column.aci_chart_draw import draw_aci_nm_alpha_ax
            _fig = self._aci_nm_fig
            _cur = _fig.axes[0] if _fig.axes else None
            if _cur is not None and getattr(_cur, 'name', '') == '3d':
                _fig.clear()
                ax = _fig.add_subplot(111)
                self._aci_nm_ax_ref = ax
            else:
                ax = self._aci_nm_ax_ref
                ax.clear()
            draw_aci_nm_alpha_ax(
                ax, self._aci_sec, self._aci_conc, self._aci_steel,
                self._aci_res, self._aci_inp.N, self._aci_inp.Mx,
                self._aci_inp.My, tied=self._aci_tied,
                view_angle_deg=angle)
            self._aci_nm_fig.tight_layout()
            self._aci_nm_fig.subplots_adjust(bottom=0.30)
            self._aci_nm_cv_ref.draw()
        except Exception:
            pass

    def _build_aci_m2m3_header(self, parent, inp):
        """Header trên biểu đồ M2-M3 (ACI)."""
        hdr = ttk.Frame(parent)
        hdr.pack(fill=tk.X, padx=4, pady=(2, 2))
        left = ttk.Frame(hdr)
        left.pack(side=tk.LEFT)
        tk.Label(left, text="● Mặt cắt M2-M3",
                 font=("", 10, "bold"), bg="white").pack(side=tk.LEFT)
        tk.Label(left, text=f"  N = {inp.N:+.1f} kN  ",
                 font=("", 8, "bold"), fg="#1D4ED8",
                 bg="#DBEAFE").pack(side=tk.LEFT, padx=6)

    def _build_aci_notes(self, parent, inp, aci_res):
        """3 dòng chú thích dưới biểu đồ ACI."""
        import math
        mono = ("TkFixedFont", 10)
        Ma = math.hypot(inp.Mx, inp.My)
        Mb = math.hypot(aci_res["Bx"], aci_res["By"])
        alpha_deg = math.degrees(math.atan2(inp.Mx, inp.My)) \
            if abs(inp.Mx) + abs(inp.My) > 1e-9 else 0.0
        box = tk.Frame(parent, bg="white",
                       highlightbackground="#E5E7EB", highlightthickness=1)
        box.pack(fill=tk.X, padx=4, pady=4)
        r1 = tk.Frame(box, bg="white")
        r1.pack(fill=tk.X, pady=1, padx=4)
        tk.Label(r1, text=f"● Đường bao kiểm tra: "
                          f"N-Mα (α = {alpha_deg:.1f}°) — ACI 318-19",
                 font=mono, fg="#059669", bg="white").pack(side=tk.LEFT)
        okt = "ĐẠT" if aci_res["ok"] else "KHÔNG ĐẠT"
        bgc = "#D1FAE5" if aci_res["ok"] else "#FEE2E2"
        fgc = "#065F46" if aci_res["ok"] else "#991B1B"
        fs_txt = (f"{aci_res['fs']:.2f}"
                  if math.isfinite(aci_res.get("fs", 0)) else "∞")
        tk.Label(r1, text=f"  D/C = {aci_res['dc']:.3f} (FS = {fs_txt}) → {okt}  ",
                 font=("", 10, "bold"), fg=fgc,
                 bg=bgc).pack(side=tk.LEFT, padx=6)
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
                 text=f"● A (điểm tải){_combo_txt}:  "
                      f"N = {inp.N:+.1f} kN,  "
                      f"Mα = {Ma:.1f} kN·m  "
                      f"(M2 = {inp.Mx:.1f}, M3 = {inp.My:.1f})",
                 font=mono, fg="#2563EB").pack(anchor="w", pady=1)
        tk.Label(box, bg="white",
                 text=f"◆ B (điểm giới hạn):  "
                      f"N = {aci_res['BN']:+.1f} kN,  Mα,u = {Mb:.1f} kN·m  "
                      f"(M2u = {aci_res['Bx']:.1f}, M3u = {aci_res['By']:.1f})",
                 font=mono, fg="#EA580C").pack(anchor="w", pady=1)

    def _render_aci_report(self, sections):
        """Hiển thị thuyết minh ACI trong tab Chi tiết tính toán (dùng chung renderer TCVN)."""
        for w in self._calc_inner.winfo_children():
            w.destroy()
        from rc_column.report_widgets import render_report_sections
        _figs = (getattr(self, "_aci_nm_fig", None),
                 getattr(self, "_aci_m2m3_fig", None))
        render_report_sections(self._calc_inner, sections, chart_figs=_figs)
        self._calc_inner.update_idletasks()
        self._calc_canvas.configure(scrollregion=self._calc_canvas.bbox("all"))
        self._bind_wheel(self._calc_inner, self._calc_canvas)
        try:
            self._calc_canvas.yview_moveto(0)
        except Exception:
            pass

    def _show_ec2_summary(self):
        """Tab Kết quả tính toán cho EC2: layout 2x2 giống TCVN/ACI.
        Hàng trên: [mặt cắt + thẻ TK | bảng thông số] /
        Hàng dưới: [biểu đồ N-Mα | biểu đồ M2-M3]."""
        if not HAS_MPL:
            return
        import math
        sec = self._ec2_sec
        inp = self._ec2_inp
        ec2_res = self._ec2_res
        conc = self._ec2_conc
        steel = self._ec2_steel
        slend = getattr(self, "_ec2_slend", None)
        from rc_column.ec2_chart_draw import (draw_ec2_nm_alpha_ax,
                                              draw_ec2_m2m3_ax)
        from rc_column.pdf_export import draw_section_ax
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        def _new_fig(parent, figsize):
            fig = Figure(figsize=figsize, dpi=100)
            cv = FigureCanvasTkAgg(fig, master=parent)
            _w = cv.get_tk_widget()
            try:
                # takefocus=0 ngăn canvas chiếm focus (đủ để cuộn chuột
                # hoạt động); KHÔNG chặn ButtonPress/Release để biểu đồ
                # 3D xoay được bằng kéo chuột
                _w.configure(highlightthickness=0, takefocus=0,
                             highlightbackground="white",
                             highlightcolor="white", borderwidth=0)
            except Exception:
                pass
            _w.pack(fill=tk.BOTH, expand=True)
            return fig, cv

        # Xóa nội dung cũ
        for w in self._sum_inner.winfo_children():
            w.destroy()
        self._sum_inner.columnconfigure(0, weight=1)
        self._sum_inner.columnconfigure(1, weight=1)
        self._sum_inner.rowconfigure(0, weight=1)
        self._sum_inner.rowconfigure(1, weight=1)

        # ===== Ô trên-phải: sơ đồ mặt cắt + thẻ thống kê =====
        f_tl = tk.Frame(self._sum_inner, bg="white",
                        highlightbackground="#D1D5DB", highlightthickness=1)
        f_tl.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        tk.Label(f_tl, text="SƠ ĐỒ MẶT CẮT TIẾT DIỆN CỘT",
                 font=("", 11, "bold"), bg="white").pack(pady=(2, 2))
        self.ck_var = tk.StringVar(value="")
        # Bỏ hiển thị tên cấu kiện ở sơ đồ (đã có ở textbox panel trái)
        fig_sec, cv_sec = _new_fig(f_tl, (3.9, 3.1))
        a1 = fig_sec.add_subplot(111)
        draw_section_ax(a1, sec, show_stats=False, dot_scale=1.5)
        fig_sec.tight_layout()
        cv_sec.draw()
        self._sec_fig, self._sec_canvas, self._sec_ax = fig_sec, cv_sec, a1
        # Thẻ thống kê EC2: hàng vật liệu + hàng số liệu thép
        self._build_ec2_section_cards(f_tl, sec, conc, steel)

        # ===== Ô trên-trái: bảng thông số tính toán EC2 =====
        f_tr = tk.Frame(self._sum_inner, bg="white",
                        highlightbackground="#D1D5DB", highlightthickness=1)
        f_tr.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._build_ec2_param_table(f_tr, inp, ec2_res, slend)

        # ===== Ô dưới-trái: header + biểu đồ N-Mα (EC2) =====
        f_bl = ttk.Frame(self._sum_inner)
        f_bl.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._build_ec2_nm_header(f_bl, inp)
        fig_nm, cv_nm = _new_fig(f_bl, (5.2, 3.9))
        self._ec2_nm_fig = fig_nm
        a3 = fig_nm.add_subplot(111)
        draw_ec2_nm_alpha_ax(a3, sec, conc, steel, ec2_res,
                             inp.N, ec2_res.get("M2_mag", inp.Mx),
                             ec2_res.get("M3_mag", inp.My))
        fig_nm.tight_layout()
        fig_nm.subplots_adjust(bottom=0.30)
        cv_nm.draw()
        # Lưu tham chiếu để vẽ lại khi đổi góc xem
        self._ec2_nm_ax_ref = a3
        self._ec2_nm_cv_ref = cv_nm

        # ===== Ô dưới-phải: header + biểu đồ M2-M3 (EC2) =====
        f_br = ttk.Frame(self._sum_inner)
        f_br.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        self._build_ec2_m2m3_header(f_br, inp)
        fig_mm, cv_mm = _new_fig(f_br, (5.2, 3.9))
        self._ec2_m2m3_fig = fig_mm
        a4 = fig_mm.add_subplot(111)
        draw_ec2_m2m3_ax(a4, sec, conc, steel, ec2_res,
                         inp.N, ec2_res.get("M2_mag", inp.Mx),
                         ec2_res.get("M3_mag", inp.My))
        fig_mm.tight_layout()
        fig_mm.subplots_adjust(bottom=0.30)
        cv_mm.draw()

        # ===== Hàng 3 full-width: chi tiết điểm A/B + D/C =====
        f_notes = ttk.Frame(self._sum_inner, style="Card.TLabelframe")
        f_notes.grid(row=2, column=0, columnspan=2, sticky="ew",
                     padx=4, pady=(4, 12))
        self._build_ec2_notes(f_notes, inp, ec2_res)
        self._sum_inner.rowconfigure(2, weight=0)

        # ===== Hàng 4 full-width: bảng kiểm tra cắt EC2 =====
        f_sw = ttk.Frame(self._sum_inner, style="Card.TLabelframe")
        f_sw.grid(row=3, column=0, columnspan=2, sticky="ew",
                  padx=4, pady=4)
        self._build_ec2_shear_summary(f_sw, inp, sec, conc, steel)
        self._sum_inner.rowconfigure(3, weight=0)

        # Gắn lại cuộn chuột cho các widget mới
        self._bind_wheel(self._sum_inner, self._sum_canvas)
        def _to_top():
            try:
                self._sum_inner.update_idletasks()
                self._sum_canvas.configure(
                    scrollregion=self._sum_canvas.bbox("all"))
                self._sum_canvas.yview_moveto(0)
            except Exception:
                pass
        self.after(50, _to_top)
        self._update_ck()

    def _build_ec2_section_cards(self, parent, sec, conc, steel):
        """6 thẻ thống kê EC2: hàng vật liệu (fck, fyk, đai) + hàng thép."""
        vals = self._section_card_values(sec)

        def _card(prow, title, value, sub=None):
            cell = tk.Frame(prow, bg="white",
                            highlightbackground="#E5E7EB",
                            highlightthickness=1, height=52)
            cell.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3, pady=2)
            cell.pack_propagate(False)
            tk.Label(cell, text=title, font=("", 8), fg="#6B7280",
                     bg="white").pack(pady=(6, 0))
            tk.Label(cell, text=value, font=("", 11, "bold"),
                     bg="white").pack(pady=2)
            if sub:
                tk.Label(cell, text=sub, font=("", 8),
                         fg="#6B7280", bg="white").pack()

        # (Đã bỏ hàng vật liệu EC2 theo yêu cầu user — chỉ giữ hàng thép)
        # Hàng số liệu thép
        row1 = tk.Frame(parent, bg="#F9FAFB")
        row1.pack(fill=tk.X, padx=2, pady=(2, 4))
        _card(row1, "Số thanh", vals["n"], vals.get("nsub", ""))
        _card(row1, "Tổng As", vals["as"])
        _card(row1, "Diện tích Ab", vals["ab"])
        _card(row1, "Hàm lượng μ", vals["mu"])

    def _build_ec2_shear_summary(self, parent, inp, sec, conc, steel):
        """Bảng kiểm tra khả năng chịu cắt EC2: Phương V2 | Phương V3."""
        try:
            shear = getattr(self, "_ec2_shear", None) or {}
            try:
                sw_dia = float(getattr(inp, "sw_dia", 8) or 8)
                sw_s = float(getattr(inp, "sw_spacing", 200) or 200)
                sw_legs = int(getattr(inp, "sw_legs", 2) or 2)
            except Exception:
                sw_dia, sw_s, sw_legs = 8.0, 200.0, 2
            sw_txt = f"{sw_legs:.0f}φ{sw_dia:.0f} a{sw_s:.0f}"
            cols = {}
            for lbl, qv in (("2", abs(inp.Q2)), ("3", abs(inp.Q3))):
                sr = shear.get("dir2" if lbl == "2" else "dir3", {}) or {}
                cols[lbl] = dict(
                    Vu=qv, sw_txt=sw_txt,
                    bw=sr.get("bw", 0.0), d=sr.get("d", 0.0),
                    VRdc=sr.get("VRd_c_kN", 0.0),
                    VRdmax=sr.get("VRd_max_kN", 0.0),
                    VRds=sr.get("VRd_s_kN", 0.0),
                    VRd=sr.get("VRd_kN", 0.0),
                    Asws=sr.get("Asw_s_req", 0.0),
                    ok=bool(sr.get("ok", False)))
            tf = tk.Frame(parent, bg="white")
            tf.pack(fill=tk.X, padx=8, pady=6)
            headers = ["KIỂM TRA KHẢ NĂNG CHỊU CẮT",
                       "Phương V2", "Phương V3"]
            for j, h in enumerate(headers):
                tk.Label(tf, text=h, font=("", 9, "bold"), bg="#F3F4F6",
                         fg="#111827", borderwidth=0,
                         highlightthickness=0,
                         anchor="w" if j == 0 else "center",
                         padx=6, pady=7).grid(row=0, column=j, sticky="nsew")
                tf.columnconfigure(j, weight=2 if j == 0 else 1, uniform="sw")
            def _asws(v):
                if v is None or (isinstance(v, float) and
                                 (v != v or v == float("inf"))):
                    return "—"
                return f"{v:.3f} mm²/mm"
            rows = [
                ("Thép đai bố trí",
                 cols['2']['sw_txt'], cols['3']['sw_txt']),
                ("Lực cắt tính toán, VEd",
                 f"{cols['2']['Vu']:.1f} kN", f"{cols['3']['Vu']:.1f} kN"),
                ("Kích thước tiết diện, bw × d",
                 f"{cols['2']['bw']:.0f} × {cols['2']['d']:.0f} mm",
                 f"{cols['3']['bw']:.0f} × {cols['3']['d']:.0f} mm"),
                ("VRd,c = [CRd,c·k·(100ρl·fck)⅓ + k1·σcp]·bw·d",
                 f"{cols['2']['VRdc']:.1f} kN", f"{cols['3']['VRdc']:.1f} kN"),
                ("VRd,max = αcw·bw·z·ν1·fcd/(cotθ+tanθ)",
                 f"{cols['2']['VRdmax']:.1f} kN",
                 f"{cols['3']['VRdmax']:.1f} kN"),
                ("VRd,s = (Asw/s)·z·fywd·cotθ (θ=45°)",
                 f"{cols['2']['VRds']:.1f} kN", f"{cols['3']['VRds']:.1f} kN"),
                ("Asw/s yêu cầu = VEd/(z·fywd·cotθ)",
                 _asws(cols['2']['Asws']), _asws(cols['3']['Asws'])),
                ("Kết luận",
                 "ĐẠT" if cols['2']['ok'] else "KHÔNG ĐẠT",
                 "ĐẠT" if cols['3']['ok'] else "KHÔNG ĐẠT"),
            ]
            for i, (a, b, c) in enumerate(rows):
                bg = "#F9FAFB" if i % 2 else "white"
                is_kl = (a == "Kết luận")
                for j, t in enumerate((a, b, c)):
                    fw = ("", 9)  # nội dung bảng không in đậm
                    fg = "#1F2937"
                    if is_kl and j > 0:
                        fg = "#065F46" if t == "ĐẠT" else "#991B1B"
                        fw = ("", 9, "bold")  # kết quả in đậm
                    tk.Label(tf, text=t, font=fw, bg=bg, fg=fg,
                             borderwidth=0, highlightthickness=0,
                             padx=6, pady=6, anchor="w" if j == 0
                             else "center").grid(row=i + 1, column=j,
                                                 sticky="nsew")
        except Exception as e:
            tk.Label(parent, text=f"Không tính được chịu cắt: {e}",
                     fg="#991B1B", bg="white").pack(padx=8, pady=4)

    def _build_ec2_param_table(self, parent, inp, ec2_res, slend):
        """Bảng thông số tính toán EC2 (Treeview 3 cột)."""
        import math
        ttk.Label(parent, text="BẢNG THÔNG SỐ TÍNH TOÁN (EC2 EN 1992-1-1)",
                  font=("", 11, "bold")).pack(pady=(2, 6))
        cols = ("sym", "desc", "val")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=16,
                            style="Param.Treeview")
        _pst = ttk.Style()
        _pst.configure("Param.Treeview.Heading", font=("", 9, "bold"),
                       background="#F3F4F6", foreground="#111827",
                       relief="flat", borderwidth=0)
        tree.heading("sym", text="Ký hiệu")
        tree.heading("desc", text="Thông số")
        tree.heading("val", text="Giá trị")
        tree.column("sym", width=64, anchor="center", stretch=False)
        tree.column("desc", width=200, anchor="w")
        tree.column("val", width=220, anchor="e", stretch=False)
        tree.tag_configure("odd", background="#F9FAFB")
        dc_bg = "#D1FAE5" if ec2_res["ok"] else "#FEE2E2"
        dc_fg = "#065F46" if ec2_res["ok"] else "#991B1B"
        tree.tag_configure("dc", background=dc_bg, foreground=dc_fg)
        M2m = ec2_res.get("M2_mag", inp.Mx)
        M3m = ec2_res.get("M3_mag", inp.My)
        alpha_deg = math.degrees(math.atan2(M2m, M3m)) \
            if abs(M2m) + abs(M3m) > 1e-9 else 0.0
        Ma = math.hypot(M2m, M3m)
        def _sl(lbl):
            try:
                d = (slend or {}).get(lbl, {}) or {}
                lam, lim = d.get("lambda_sl", 0.0), d.get("lambda_lim", 0.0)
                man = "mảnh" if d.get("slender") else "không mảnh"
                lim_txt = f"{lim:.1f}" if math.isfinite(lim) else "∞"
                return f"λ = {lam:.1f}, λlim = {lim_txt} ({man})"
            except Exception:
                return "—"
        method_txt = ("Độ cứng danh nghĩa"
                      if ec2_res.get("method") != "curvature"
                      else "Độ cong danh nghĩa")
        conc = self._ec2_conc
        rows = [
            ("NEd", "Lực dọc thiết kế",
             f"{inp.N:+.1f} kN"),
            ("MEd2", "Mô men thiết kế phương 2 (gồm bậc 2)",
             f"{M2m:.1f} kN·m"),
            ("MEd3", "Mô men thiết kế phương 3 (gồm bậc 2)",
             f"{M3m:.1f} kN·m"),
            ("α", "Góc tác dụng mô men",
             f"{alpha_deg:.1f} °"),
            ("Mα", "Mô men tổng hợp",
             f"{Ma:.1f} kN·m"),
            ("fck", "Cường độ nén đặc trưng",
             f"{conc.fck:g} MPa"),
            ("fcd", "Cường độ nén tính toán (αcc·fck/γc)",
             f"{conc.fcd:.2f} MPa"),
            ("Ecm", "Mô đun đàn hồi cát tuyến",
             f"{conc.Ecm:.0f} MPa"),
            ("λ2", "Độ mảnh phương 2 (EC2 5.8.3)",
             _sl("dir2")),
            ("λ3", "Độ mảnh phương 3 (EC2 5.8.3)",
             _sl("dir3")),
            ("e2", "Độ lệch tâm phương 2 (MEd2/NEd)",
             f"{abs(M2m/inp.N*1000):.1f} mm" if abs(inp.N) > 1e-9 else "—"),
            ("e3", "Độ lệch tâm phương 3 (MEd3/NEd)",
             f"{abs(M3m/inp.N*1000):.1f} mm" if abs(inp.N) > 1e-9 else "—"),
            ("M2_0", "Mô men bậc 1 phương 2",
             f"{inp.Mx:.1f} kN·m"),
            ("M3_0", "Mô men bậc 1 phương 3",
             f"{inp.My:.1f} kN·m"),
            ("N_Rd,max", "Nén đúng tâm lớn nhất",
             f"{ec2_res.get('N_Rd_max', 0):.1f} kN"),
        ]
        for i, (a, b, c) in enumerate(rows):
            tree.insert("", "end", values=(a, b, c),
                        tags=("odd",) if i % 2 else ())
        ok_txt = "ĐẠT" if ec2_res["ok"] else "KHÔNG ĐẠT"
        fs_txt = (f"{ec2_res['fs']:.2f}"
                  if math.isfinite(ec2_res.get("fs", 0)) else "∞")
        tree.insert("", "end",
                    values=("D/C", "Tỷ số sử dụng khả năng chịu lực",
                            f"{ec2_res['dc']:.3f} (FS = {fs_txt})  {ok_txt}"),
                    tags=("dc",))
        tree.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

    def _build_ec2_nm_header(self, parent, inp):
        """Header trên biểu đồ N-Mα (EC2)."""
        import math
        M2m = getattr(self, "_ec2_res", {}).get("M2_mag", inp.Mx)
        M3m = getattr(self, "_ec2_res", {}).get("M3_mag", inp.My)
        alpha_deg = math.degrees(math.atan2(M2m, M3m)) \
            if abs(M2m) + abs(M3m) > 1e-9 else 0.0
        hdr = ttk.Frame(parent)
        hdr.pack(fill=tk.X, padx=4, pady=(2, 2))
        left = ttk.Frame(hdr)
        left.pack(side=tk.LEFT)
        tk.Label(left, text="● Biểu đồ tương tác N–Mα",
                 font=("", 10, "bold"), bg="white").pack(side=tk.LEFT)
        self._ec2_nm_alpha_lbl = tk.Label(
            left, text=f"  α = {alpha_deg:.1f}°  ",
            font=("", 8, "bold"), fg="#065F46", bg="#D1FAE5")
        self._ec2_nm_alpha_lbl.pack(side=tk.LEFT, padx=6)
        # Combobox chọn góc xem biểu đồ N-M
        right = ttk.Frame(hdr)
        right.pack(side=tk.RIGHT)
        tk.Label(right, text="Góc xem:", font=("", 9),
                 bg="white").pack(side=tk.LEFT)
        _vals = ["α (góc tải)", "3D"] + [f"{d}°" for d in range(0, 361, 15)]
        self._ec2_nm_angle_cb = ttk.Combobox(
            right, values=_vals, width=11, state="readonly", font=("", 9))
        self._ec2_nm_angle_cb.set("α (góc tải)")
        self._ec2_nm_angle_cb.pack(side=tk.LEFT, padx=(4, 0))
        self._ec2_nm_angle_cb.bind("<<ComboboxSelected>>",
                                   self._on_ec2_nm_angle_changed)
        self._ec2_nm_view_angle = None  # None = góc tải mặc định

    def _on_ec2_nm_angle_changed(self, event=None):
        """Vẽ lại biểu đồ N-Mα (EC2) tại góc được chọn."""
        try:
            sel = self._ec2_nm_angle_cb.get()
            if sel == "3D":
                self._draw_3d_ec2()
                return
            if sel.startswith("α"):
                angle = None
            else:
                angle = float(sel.replace("°", ""))
        except Exception:
            angle = None
        self._ec2_nm_view_angle = angle
        try:
            if angle is None:
                import math
                res = self._ec2_res
                a0 = math.degrees(math.atan2(res.get("M2_mag", 0),
                                             res.get("M3_mag", 0)))
                self._ec2_nm_alpha_lbl.config(text=f"  α = {a0:.1f}°  ")
            else:
                self._ec2_nm_alpha_lbl.config(text=f"  xem {angle:.0f}°  ")
        except Exception:
            pass
        try:
            from rc_column.ec2_chart_draw import draw_ec2_nm_alpha_ax
            _fig = self._ec2_nm_fig
            _cur = _fig.axes[0] if _fig.axes else None
            if _cur is not None and getattr(_cur, 'name', '') == '3d':
                _fig.clear()
                ax = _fig.add_subplot(111)
                self._ec2_nm_ax_ref = ax
            else:
                ax = self._ec2_nm_ax_ref
                ax.clear()
            draw_ec2_nm_alpha_ax(
                ax, self._ec2_sec, self._ec2_conc, self._ec2_steel,
                self._ec2_res, self._ec2_inp.N,
                self._ec2_res.get("M2_mag", self._ec2_inp.Mx),
                self._ec2_res.get("M3_mag", self._ec2_inp.My),
                view_angle_deg=angle)
            self._ec2_nm_fig.tight_layout()
            self._ec2_nm_fig.subplots_adjust(bottom=0.30)
            self._ec2_nm_cv_ref.draw()
        except Exception:
            pass

    def _build_ec2_m2m3_header(self, parent, inp):
        """Header trên biểu đồ M2-M3 (EC2)."""
        hdr = ttk.Frame(parent)
        hdr.pack(fill=tk.X, padx=4, pady=(2, 2))
        left = ttk.Frame(hdr)
        left.pack(side=tk.LEFT)
        tk.Label(left, text="● Mặt cắt M2-M3",
                 font=("", 10, "bold"), bg="white").pack(side=tk.LEFT)
        tk.Label(left, text=f"  N = {inp.N:+.1f} kN  ",
                 font=("", 8, "bold"), fg="#1D4ED8",
                 bg="#DBEAFE").pack(side=tk.LEFT, padx=6)
        # Góc xem (EC2)

    def _build_ec2_notes(self, parent, inp, ec2_res):
        """3 dòng chú thích dưới biểu đồ EC2."""
        import math
        mono = ("TkFixedFont", 10)
        M2m = ec2_res.get("M2_mag", inp.Mx)
        M3m = ec2_res.get("M3_mag", inp.My)
        Ma = math.hypot(M2m, M3m)
        Mb = math.hypot(ec2_res["Bx"], ec2_res["By"])
        alpha_deg = math.degrees(math.atan2(M2m, M3m)) \
            if abs(M2m) + abs(M3m) > 1e-9 else 0.0
        box = tk.Frame(parent, bg="white",
                       highlightbackground="#E5E7EB", highlightthickness=1)
        box.pack(fill=tk.X, padx=4, pady=4)
        r1 = tk.Frame(box, bg="white")
        r1.pack(fill=tk.X, pady=1, padx=4)
        tk.Label(r1, text=f"● Đường bao kiểm tra: "
                          f"N-Mα (α = {alpha_deg:.1f}°) — EC2 (EN 1992-1-1)",
                 font=mono, fg="#059669", bg="white").pack(side=tk.LEFT)
        okt = "ĐẠT" if ec2_res["ok"] else "KHÔNG ĐẠT"
        bgc = "#D1FAE5" if ec2_res["ok"] else "#FEE2E2"
        fgc = "#065F46" if ec2_res["ok"] else "#991B1B"
        fs_txt = (f"{ec2_res['fs']:.2f}"
                  if math.isfinite(ec2_res.get("fs", 0)) else "∞")
        tk.Label(r1, text=f"  D/C = {ec2_res['dc']:.3f} (FS = {fs_txt}) → {okt}  ",
                 font=("", 10, "bold"), fg=fgc,
                 bg=bgc).pack(side=tk.LEFT, padx=6)
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
                 text=f"● A (điểm tải){_combo_txt}:  "
                      f"N = {inp.N:+.1f} kN,  "
                      f"Mα = {Ma:.1f} kN·m  "
                      f"(MEd2 = {M2m:.1f}, MEd3 = {M3m:.1f})",
                 font=mono, fg="#2563EB").pack(anchor="w", pady=1)
        tk.Label(box, bg="white",
                 text=f"◆ B (điểm giới hạn):  "
                      f"N = {ec2_res['BN']:+.1f} kN,  Mα,u = {Mb:.1f} kN·m  "
                      f"(M2u = {ec2_res['Bx']:.1f}, M3u = {ec2_res['By']:.1f})",
                 font=mono, fg="#EA580C").pack(anchor="w", pady=1)

    def _render_ec2_report(self, sections):
        """Hiển thị thuyết minh EC2 trong tab Chi tiết tính toán (dùng chung renderer TCVN)."""
        for w in self._calc_inner.winfo_children():
            w.destroy()
        from rc_column.report_widgets import render_report_sections
        _figs = (getattr(self, "_ec2_nm_fig", None),
                 getattr(self, "_ec2_m2m3_fig", None))
        render_report_sections(self._calc_inner, sections, chart_figs=_figs)
        self._calc_inner.update_idletasks()
        self._calc_canvas.configure(scrollregion=self._calc_canvas.bbox("all"))
        self._bind_wheel(self._calc_inner, self._calc_canvas)
        try:
            self._calc_canvas.yview_moveto(0)
        except Exception:
            pass

    # ---------------- ETABS ----------------
    def on_import_etabs(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Chọn file Excel ETABS",
            filetypes=[("Excel", "*.xlsx *.xls"), ("All", "*.*")])
        if not path:
            return
        self._load_etabs_file(path)

    def on_import_dxf(self):
        """Import tiết diện bất kỳ từ file DXF (AutoCAD Save As DXF).

        Quy ước: biên bê tông = LWPOLYLINE kín (layer BT),
        thép = CIRCLE (layer THEP).
        """
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(
            title="Chọn file DXF tiết diện",
            filetypes=[("DXF", "*.dxf"), ("All", "*.*")])
        if not path:
            return
        try:
            from rc_column.dxf_import import (
                read_dxf_section, build_polygon_section, polygon_area)
            dxf = read_dxf_section(path)
            # Dựng section với vật liệu hiện tại
            from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                             ConcreteMaterial, SteelMaterial)
            conc = ConcreteMaterial(
                CONCRETE_GRADES[self.cb_conc.get()], 1.0)
            steel = SteelMaterial(STEEL_GRADES[self.cb_steel.get()], 1.0)
            sec = build_polygon_section(dxf, conc, steel, fiber_step=10.0)
        except Exception as ex:
            messagebox.showerror("Lỗi đọc DXF", str(ex))
            return
        # Preview dialog
        if not self._preview_dxf_section(sec, dxf, path):
            return
        self._dxf_section = sec
        self._dxf_path = path
        self.cb_kind.set("Tiết diện bất kỳ (DXF)")
        Ag = sec.gross_area
        As = sec.steel_area
        self.dxf_info.set(
            f"Đã import: {path.split('/')[-1]} — "
            f"Ag={Ag:.0f} mm², {len(sec.rebars)} thép, "
            f"As={As:.0f} mm²")
        if dxf.warnings:
            messagebox.showwarning(
                "Cảnh báo import DXF", "\n".join(dxf.warnings))
        self._refresh_rebar_panel()
        # Tự chạy kiểm tra lại để mặt cắt/biểu đồ cập nhật theo DXF
        try:
            self.on_check()
        except Exception:
            pass

    def on_export_dxf(self):
        """Xuất tiết diện đang có ra file DXF (để sửa trong AutoCAD)."""
        from tkinter import filedialog, messagebox
        try:
            inp = self._draft_input()
            sec = build_section(inp)
        except Exception as ex:
            messagebox.showerror("Lỗi xuất DXF", str(ex))
            return
        path = filedialog.asksaveasfilename(
            title="Xuất tiết diện ra DXF",
            defaultextension=".dxf",
            filetypes=[("DXF", "*.dxf"), ("All", "*.*")])
        if not path:
            return
        try:
            from rc_column.dxf_import import write_dxf_section
            write_dxf_section(sec, path)
        except Exception as ex:
            messagebox.showerror("Lỗi xuất DXF", str(ex))
            return
        messagebox.showinfo("Xong",
                            f"Đã xuất tiết diện ra:\n{path}\n"
                            f"({len(sec.rebars)} thép, "
                            f"Ag={sec.gross_area:.0f} mm²)")

    def on_change_dxf_dia(self):
        """Đổi đường kính toàn bộ thép dọc của tiết diện DXF."""
        from tkinter import messagebox
        if getattr(self, "_dxf_section", None) is None:
            messagebox.showerror("Lỗi", "Chưa import tiết diện DXF.")
            return
        try:
            new_dia = float(self.cb_dxf_dia.get())
            if new_dia <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror("Lỗi", "Chọn đường kính hợp lệ.")
            return
        import math
        for r in self._dxf_section.rebars:
            r.dia = new_dia
            r.area = math.pi * new_dia ** 2 / 4
        Ag = self._dxf_section.gross_area
        As = self._dxf_section.steel_area
        self.dxf_info.set(
            f"Đã import: {self._dxf_path.split('/')[-1]} — "
            f"Ag={Ag:.0f} mm², {len(self._dxf_section.rebars)} thép, "
            f"As={As:.0f} mm² (d={new_dia:.0f})")
        # Chạy lại kiểm tra để cập nhật kết quả
        try:
            self.on_check()
        except Exception:
            pass

    def _preview_dxf_section(self, sec, dxf, path) -> bool:
        """Dialog preview tiết diện trước khi nhận. Trả về True nếu đồng ý."""
        from tkinter import messagebox
        win = tk.Toplevel(self)
        win.title("Preview tiết diện DXF")
        win.geometry("520x560")
        win.transient(self)
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.patches import Polygon as MplPolygon
            fig = Figure(figsize=(5, 4.5), dpi=100)
            ax = fig.add_subplot(111)
            for verts in sec.poly_verts:
                ax.add_patch(MplPolygon(verts, closed=True, fill=True,
                                        facecolor="#DBEAFE", edgecolor="#1D4ED8",
                                        linewidth=1.5))
            for verts in sec.poly_holes:
                ax.add_patch(MplPolygon(verts, closed=True, fill=True,
                                        facecolor="white", edgecolor="#DC2626",
                                        linewidth=1.0, linestyle="--"))
            import matplotlib.patches as mpatches
            for r in sec.rebars:
                ax.add_patch(mpatches.Circle((r.x, r.y), r.dia / 2.0,
                                             facecolor="#DC2626",
                                             edgecolor="#7F1D1D"))
            # Cập nhật giới hạn trục theo patch (add_patch không tự autoscale)
            ax.relim()
            ax.autoscale_view()
            ax.set_aspect("equal", adjustable="datalim")
            ax.set_title(f"{path.split('/')[-1]}\n"
                         f"Ag={sec.gross_area:.0f} mm², "
                         f"{len(sec.rebars)} thép")
            ax.axhline(0, color="#9CA3AF", linewidth=0.5)
            ax.axvline(0, color="#9CA3AF", linewidth=0.5)
            fig.tight_layout()
            cv = FigureCanvasTkAgg(fig, master=win)
            cv.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            cv.draw()
        except Exception as ex:
            messagebox.showerror("Lỗi preview", str(ex))
            win.destroy()
            return False
        result = {"ok": False}

        def _ok():
            result["ok"] = True
            win.destroy()

        btnf = ttk.Frame(win)
        btnf.pack(fill=tk.X, padx=8, pady=8)
        ttk.Button(btnf, text="✓ Dùng tiết diện này",
                   command=_ok).pack(side=tk.LEFT, expand=True,
                                     fill=tk.X, padx=2)
        ttk.Button(btnf, text="Hủy",
                   command=win.destroy).pack(side=tk.LEFT, expand=True,
                                             fill=tk.X, padx=2)
        if dxf.warnings:
            ttk.Label(win, text="\n".join(dxf.warnings),
                      foreground="#92400E", wraplength=480,
                      justify=tk.LEFT).pack(padx=8, pady=4)
        self.wait_window(win)
        return result["ok"]

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

    def _check_aci_etabs(self):
        """Kiểm tra tất cả tổ hợp ETABS theo ACI 318-19."""
        from rc_column.aci_materials import ACIConcrete, ACISteel
        from rc_column.aci_checker import check_column_aci
        try:
            fc = float(self.en_fc.get().replace(",", "."))
            fy = float(self.en_fy.get().replace(",", "."))
            fyt = float(self.en_fyt.get().replace(",", "."))
        except Exception:
            from tkinter import messagebox
            messagebox.showerror("Lỗi", "Nhập f'c, fy và fyt hợp lệ (MPa).")
            return
        tied = "tied" in self.cb_tie.get().lower()
        conc = ACIConcrete(fc=fc)
        steel = ACISteel(fy=fy)
        self.etabs_info.set("Đang kiểm tra ACI, vui lòng đợi...")
        self.update_idletasks()
        import time
        t0 = time.time()
        from collections import defaultdict
        _L_manual = self._f(self.en_Lx, 0.0)
        _groups = defaultdict(list)
        for _f in self.etabs_forces:
            _groups[(_f.story, _f.column)].append(_f)
        rows = []
        from rc_column.aci_checker import ACICapacity
        for (_st, _cl), _flist in _groups.items():
            if _L_manual > 0:
                _L_grp = _L_manual
            else:
                _L_grp = max(_f.station for _f in _flist)
            _inp_g = self.collect()
            _inp_g.Lx = _inp_g.Ly = _L_grp
            sec_g = build_section(_inp_g)
            # Tối ưu: dựng ACICapacity 1 lần cho cả nhóm (đắt),
            # mỗi tổ hợp chỉ tính D/C tia (rẻ)
            try:
                _cap_g = ACICapacity(sec_g, conc, steel, tied=tied,
                                     n_angles=24)
            except Exception:
                _cap_g = None
            for _f in _flist:
                try:
                    if _cap_g is None:
                        raise RuntimeError("capacity")
                    _r = _cap_g.dc_ratio(_f.N, _f.Mx, _f.My)
                except Exception:
                    _r = {"dc": float("nan"), "ok": False}
                rows.append((_f, _r))
        rows.sort(key=lambda x: -(x[1]["dc"]) if x[1]["dc"] == x[1]["dc"]
                  else float("inf"))
        self._fill_etabs_table(rows)
        worst_f, worst_r = rows[0]
        children = self.etabs_tree.get_children()
        if children:
            self.etabs_tree.item(children[0], tags=("worst",))
            self.etabs_tree.see(children[0])
        n_ng = sum(1 for _, r in rows if r["dc"] == r["dc"] and r["dc"] > 1)
        dt = time.time() - t0
        self.etabs_info.set(
            f"Xong {len(rows)} tổ hợp trong {dt:.1f}s (ACI 318-19) — "
            f"Nguy hiểm nhất: {worst_f.case} @ {worst_f.station:.2f}m "
            f"(D/C = {worst_r['dc']:.3f}) — {n_ng} tổ hợp KHÔNG ĐẠT.")
        self._batch_rows = rows
        # Tính lại tổ hợp nguy hiểm nhất để hiển thị
        inp_w = self.collect()
        inp_w.N, inp_w.Mx, inp_w.My = worst_f.N, worst_f.Mx, worst_f.My
        _Lw = self._f(self.en_Lx, 0.0)
        if _Lw <= 0:
            _sts_w = [f.station for f in self.etabs_forces
                      if f.story == worst_f.story and f.column == worst_f.column]
            if _sts_w:
                _Lw = max(_sts_w)
        if _Lw > 0:
            inp_w.Lx = inp_w.Ly = _Lw
        # Lực cắt: lấy từ combo có |Q| lớn nhất (giống TCVN)
        try:
            f_q2 = max(self.etabs_forces, key=lambda f: abs(f.Q2))
            f_q3 = max(self.etabs_forces, key=lambda f: abs(f.Q3))
            inp_w.Q2, inp_w.Q3 = f_q2.Q2, f_q3.Q3
        except Exception:
            pass
        # Gọi _check_aci với inp_w (nó tự vẽ charts + report + lưu PDF data)
        # nhưng cần giữ case_info cho thuyết minh
        self._pdf_case = {"case": worst_f.case, "station": worst_f.station,
                          "N": worst_f.N, "M2": worst_f.Mx, "M3": worst_f.My,
                          "story": getattr(worst_f, "story", ""),
                          "column": getattr(worst_f, "column", "")}
        # Tạm lưu inp gốc để _check_aci dùng đúng nội lực worst
        self._check_aci(inp_w)

    def _check_ec2_etabs(self):
        """Kiểm tra tất cả tổ hợp ETABS theo EC2 (EN 1992-1-1)."""
        from rc_column.ec2_materials import (EC2Concrete, EC2Steel,
                                             EC2_CONCRETE_GRADES,
                                             EC2_STEEL_GRADES)
        from rc_column.ec2_checker import (ec2_design_moment,
                                           ec2_balanced_point, EC2Capacity)
        from rc_column.stability import effective_length
        import math
        fck = EC2_CONCRETE_GRADES.get(self.cb_ec2_conc.get(), 30.0)
        fyk = float(self.en_ec2_fyk.get().replace(",", "."))
        conc = EC2Concrete(fck=fck)
        steel = EC2Steel(fyk=fyk)
        method = ("curvature"
                  if self.cb_ec2_method.get().startswith("Độ cong")
                  else "stiffness")
        self.etabs_info.set("Đang kiểm tra EC2, vui lòng đợi...")
        self.update_idletasks()
        import time
        t0 = time.time()
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
            sec_g = build_section(_inp_g)
            cx, cy = sec_g.cx, sec_g.cy
            Ac = sec_g.gross_area
            As = sec_g.steel_area
            try:
                l0_2 = effective_length(_L_grp, _inp_g.top_x, _inp_g.bottom_x,
                                        _inp_g.psi_x) * 1000.0
                l0_3 = effective_length(_L_grp, _inp_g.top_y, _inp_g.bottom_y,
                                        _inp_g.psi_y) * 1000.0
            except Exception:
                l0_2 = l0_3 = _L_grp * 1000.0
            geom = {"dir2": (cy, cx * cy**3 / 12.0, l0_2),
                    "dir3": (cx, cy * cx**3 / 12.0, l0_3)}
            # Tối ưu: dựng EC2Capacity 1 lần cho cả nhóm,
            # mỗi tổ hợp chỉ tính mô men bậc 2 + D/C tia
            try:
                _cap_g = EC2Capacity(sec_g, conc, steel, n_angles=24)
            except Exception:
                _cap_g = None
            n_bal = 0.0
            if method == "curvature":
                try:
                    Nb, _Mb = ec2_balanced_point(sec_g, conc, steel, 0.0)
                    n_bal = Nb / (conc.fcd * Ac / 1000.0) if Ac > 0 else 0.0
                except Exception:
                    n_bal = 0.0
            for _f in _flist:
                try:
                    if _cap_g is None:
                        raise RuntimeError("capacity")
                    meds = []
                    for lbl, Mdir in (("dir2", _f.Mx), ("dir3", _f.My)):
                        h_dim, Ic, l0 = geom[lbl]
                        dm = ec2_design_moment(
                            NEd_kN=_f.N, M_top_kNm=abs(Mdir),
                            M_bot_kNm=abs(Mdir), l0_mm=l0,
                            i_mm=math.sqrt(Ic / Ac) if Ac > 0 else h_dim,
                            h_mm=h_dim, Ac_mm2=Ac, As_mm2=As,
                            fcd_MPa=conc.fcd, fyd_MPa=steel.fyd,
                            Ecm_MPa=conc.Ecm, Ic_mm4=Ic, Is_mm4=0.0,
                            Es_MPa=steel.Es, fck_MPa=fck,
                            unbraced=False, method=method,
                            d_mm=max(h_dim - (_inp_g.cover or 30) - 10.0,
                                     0.5 * h_dim),
                            eps_yd=steel.eps_yd, n_bal=n_bal,
                            const_moment=True)
                        meds.append(dm["MEd"])
                    _r = _cap_g.dc_ratio(_f.N, meds[0], meds[1])
                except Exception:
                    _r = {"dc": float("nan"), "ok": False}
                rows.append((_f, _r))
        rows.sort(key=lambda x: -(x[1]["dc"]) if x[1]["dc"] == x[1]["dc"]
                  else float("inf"))
        self._fill_etabs_table(rows)
        worst_f, worst_r = rows[0]
        children = self.etabs_tree.get_children()
        if children:
            self.etabs_tree.item(children[0], tags=("worst",))
            self.etabs_tree.see(children[0])
        n_ng = sum(1 for _, r in rows if r["dc"] == r["dc"] and r["dc"] > 1)
        dt = time.time() - t0
        self.etabs_info.set(
            f"Xong {len(rows)} tổ hợp trong {dt:.1f}s (EC2 EN 1992-1-1) — "
            f"Nguy hiểm nhất: {worst_f.case} @ {worst_f.station:.2f}m "
            f"(D/C = {worst_r['dc']:.3f}) — {n_ng} tổ hợp KHÔNG ĐẠT.")
        self._batch_rows = rows
        # Tính lại tổ hợp nguy hiểm nhất để hiển thị
        inp_w = self.collect()
        inp_w.N, inp_w.Mx, inp_w.My = worst_f.N, worst_f.Mx, worst_f.My
        _Lw = self._f(self.en_Lx, 0.0)
        if _Lw <= 0:
            _sts_w = [f.station for f in self.etabs_forces
                      if f.story == worst_f.story and f.column == worst_f.column]
            if _sts_w:
                _Lw = max(_sts_w)
        if _Lw > 0:
            inp_w.Lx = inp_w.Ly = _Lw
        # Lực cắt: lấy từ combo có |Q| lớn nhất (giống TCVN)
        try:
            f_q2 = max(self.etabs_forces, key=lambda f: abs(f.Q2))
            f_q3 = max(self.etabs_forces, key=lambda f: abs(f.Q3))
            inp_w.Q2, inp_w.Q3 = f_q2.Q2, f_q3.Q3
        except Exception:
            pass
        # Gọi _check_ec2 với inp_w (nó tự vẽ charts + report + lưu PDF data)
        # nhưng cần giữ case_info cho thuyết minh
        self._pdf_case = {"case": worst_f.case, "station": worst_f.station,
                          "N": worst_f.N, "M2": worst_f.Mx, "M3": worst_f.My,
                          "story": getattr(worst_f, "story", ""),
                          "column": getattr(worst_f, "column", "")}
        # Tạm lưu inp gốc để _check_ec2 dùng đúng nội lực worst
        self._check_ec2(inp_w)

    def on_check_etabs(self):
        if not self.etabs_forces:
            messagebox.showinfo("ETABS", "Hãy import file Excel trước.")
            return
        if self.is_ec2():
            self._check_ec2_etabs()
            return
        if self.is_aci():
            self._check_aci_etabs()
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
        pass  # (đã bỏ header tổ hợp nguy hiểm nhất)

    def _export_pdf(self):
        """Xuất PDF theo tab đang mở: Tóm tắt hoặc Thuyết minh."""
        try:
            from tkinter import filedialog, messagebox
            # Kiểm tra kết quả theo tiêu chuẩn đang chọn
            # (trước đây chỉ kiểm tra _last_sec của TCVN nên ACI/EC2 báo lỗi)
            if self.is_aci():
                has_result = getattr(self, "_aci_res", None) is not None
            elif self.is_ec2():
                has_result = getattr(self, "_ec2_res", None) is not None
            else:
                has_result = self._last_sec is not None
            if not has_result:
                messagebox.showwarning("Xuất PDF",
                                       "Chưa có kết quả để xuất.")
                return
            # Tab đang chọn
            is_summary = (self._current_tab == "sum")
            # Tên file mặc định:
            #   KẾT QUẢ: TMTT-[TC]-TênCK.pdf
            #   CHI TIẾT: TMTT-FULL-[TC]-TênCK.pdf
            _ck = ""
            if hasattr(self, "member_var"):
                _ck = self.member_var.get().strip().upper()
            if not _ck:
                import os as _os
                _p = getattr(self, "current_save_path", "") or ""
                if _p:
                    _ck = _os.path.splitext(_os.path.basename(_p))[0].upper()
            if self.is_aci():
                _std = "ACI"
            elif self.is_ec2():
                _std = "EC2"
            else:
                _std = "TCVN"
            _full = "" if is_summary else "-FULL"
            _def = f"TMTT{_full}-{_std}-{_ck}.pdf" if _ck else f"TMTT{_full}-{_std}.pdf"
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
                        nm_fig.savefig(buf1, format="png", dpi=200,
                                       bbox_inches="tight")
                        buf2 = io.BytesIO()
                        m2m3_fig.savefig(buf2, format="png", dpi=200,
                                         bbox_inches="tight")
                        return (buf1.getvalue(), buf2.getvalue())
                except Exception:
                    pass
                return None
            # Hàm hiện dialog thành công có nút Mở PDF
            def _show_success(ppath):
                self._show_pdf_success(ppath)
            # --- ACI mode: dùng PDF ACI (đặt sau khi path & _show_success đã có) ---
            if self.is_aci() and getattr(self, "_aci_res", None) is not None:
                self._export_pdf_aci(is_summary, path, _show_success)
                return
            # --- EC2 mode: dùng PDF EC2 ---
            if self.is_ec2() and getattr(self, "_ec2_res", None) is not None:
                self._export_pdf_ec2(is_summary, path, _show_success)
                return
            if is_summary:
                from rc_column.pdf_export import export_summary_pdf
                # Gán tên file vào inp để hiển thị "Cấu kiện"
                try:
                    self._last_inp._filename = self.member_var.get().strip() if hasattr(self, "member_var") else ""
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
                # Gán tên cấu kiện từ textbox để hiển thị ở đầu PDF
                try:
                    self._last_inp._filename = self.member_var.get().strip() if hasattr(self, "member_var") else ""
                except Exception:
                    pass
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
        """Cập nhật biểu đồ (note L0 đã bỏ theo yêu cầu)."""
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

    def _export_pdf_aci(self, is_summary, path, _show_success):
        """Xuất PDF cho chế độ ACI 318-19."""
        try:
            import io
            def _get_pngs():
                try:
                    f1 = getattr(self, "_aci_nm_fig", None)
                    f2 = getattr(self, "_aci_m2m3_fig", None)
                    if f1 is not None and f2 is not None:
                        b1, b2 = io.BytesIO(), io.BytesIO()
                        f1.savefig(b1, format="png", dpi=200, bbox_inches="tight")
                        f2.savefig(b2, format="png", dpi=200, bbox_inches="tight")
                        return (b1.getvalue(), b2.getvalue())
                except Exception:
                    pass
                return None
            pngs = _get_pngs()
            if is_summary:
                from rc_column.aci_pdf_summary import export_aci_summary_pdf
                export_aci_summary_pdf(
                    self._aci_sec, self._aci_inp, self._aci_res,
                    self._aci_conc, self._aci_steel, self._aci_tied, path,
                    case_info=getattr(self, "_pdf_case", None),
                    chart_pngs=pngs,
                    shear_info=getattr(self, "_aci_shear", None))
            else:
                from rc_column.aci_pdf_report import export_aci_pdf_cards
                export_aci_pdf_cards(
                    self._aci_inp, self._aci_res, self._aci_mm,
                    self._aci_shear, self._aci_conc, self._aci_steel,
                    self._aci_tied, path, chart_pngs=pngs,
                    case_info=getattr(self, "_pdf_case", None),
                    sec=self._aci_sec)
            _show_success(path)
        except Exception as ex:
            from tkinter import messagebox
            messagebox.showerror("Xuất PDF ACI", str(ex))

    def _export_pdf_ec2(self, is_summary, path, _show_success):
        """Xuất PDF cho chế độ EC2 (EN 1992-1-1)."""
        try:
            import io
            def _get_pngs():
                try:
                    f1 = getattr(self, "_ec2_nm_fig", None)
                    f2 = getattr(self, "_ec2_m2m3_fig", None)
                    if f1 is not None and f2 is not None:
                        b1, b2 = io.BytesIO(), io.BytesIO()
                        f1.savefig(b1, format="png", dpi=200, bbox_inches="tight")
                        f2.savefig(b2, format="png", dpi=200, bbox_inches="tight")
                        return (b1.getvalue(), b2.getvalue())
                except Exception:
                    pass
                return None
            pngs = _get_pngs()
            if is_summary:
                from rc_column.ec2_pdf_summary import export_ec2_summary_pdf
                _fyk_sw = None
                try:
                    _fyk_sw = float(self.en_ec2_fyt.get().replace(",", "."))
                except Exception:
                    pass
                export_ec2_summary_pdf(
                    self._ec2_sec, self._ec2_inp, self._ec2_res,
                    self._ec2_conc, self._ec2_steel, path,
                    case_info=getattr(self, "_pdf_case", None),
                    chart_pngs=pngs,
                    shear_info=getattr(self, "_ec2_shear", None),
                    slend_res=getattr(self, "_ec2_slend", None),
                    fyk_sw=_fyk_sw)
            else:
                from rc_column.ec2_pdf_report import export_ec2_pdf_cards
                export_ec2_pdf_cards(
                    self._ec2_inp, self._ec2_res, self._ec2_slend,
                    self._ec2_shear, self._ec2_conc, self._ec2_steel,
                    path, chart_pngs=pngs,
                    case_info=getattr(self, "_pdf_case", None),
                    sec=self._ec2_sec)
            _show_success(path)
        except Exception as ex:
            from tkinter import messagebox
            messagebox.showerror("Xuất PDF EC2", str(ex))

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
        """Dialog thành công có nút Mở PDF - thiết kế đẹp."""
        import tkinter as _tk
        import os as _os
        dlg = _tk.Toplevel(self)
        dlg.title("Xuất PDF")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.configure(bg="white")
        # Căn giữa màn hình
        _w, _h = 440, 190
        _x = (dlg.winfo_screenwidth() // 2) - (_w // 2)
        _y = (dlg.winfo_screenheight() // 2) - (_h // 2)
        dlg.geometry(f"{_w}x{_h}+{_x}+{_y}")
        # Header xanh lá với icon check
        _header = _tk.Frame(dlg, bg="#059669", height=52)
        _header.pack(fill=_tk.X)
        _header.pack_propagate(False)
        _tk.Label(_header, text="✓", font=("", 20, "bold"),
                  fg="white", bg="#059669").pack(side=_tk.LEFT, padx=(16, 8))
        _tk.Label(_header, text="Xuất PDF thành công",
                  font=("", 12, "bold"), fg="white",
                  bg="#059669").pack(side=_tk.LEFT, pady=12)
        # Tên file
        _fname = _os.path.basename(ppath)
        _tk.Label(dlg, text=_fname, font=("", 10, "bold"),
                  fg="#111827", bg="white",
                  wraplength=400, justify="center").pack(pady=(14, 4))
        _tk.Label(dlg, text=_os.path.dirname(ppath), font=("", 8),
                  fg="#6B7280", bg="white",
                  wraplength=400, justify="center").pack(pady=(0, 12))
        # Nút bấm
        btns = _tk.Frame(dlg, bg="white")
        btns.pack(pady=(0, 12))
        def _open():
            import sys as _sys, subprocess as _sp
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
        _tk.Button(btns, text="Mở PDF", font=("", 10, "bold"),
                   fg="white", bg="#059669", activeforeground="white",
                   activebackground="#047857", relief="flat",
                   padx=20, pady=6, cursor="hand2",
                   command=_open).pack(side="left", padx=6)
        _tk.Button(btns, text="Đóng", font=("", 10),
                   fg="#374151", bg="#F3F4F6", activebackground="#E5E7EB",
                   relief="flat", padx=20, pady=6, cursor="hand2",
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
            # Tên cấu kiện
            "member_name": self.member_var.get().strip() if hasattr(self, "member_var") else "",
            # 1. Vật liệu
            "concrete": self.cb_conc.get(), "gamma_b": ev(self.en_gb),
            "steel": self.cb_steel.get(), "sw_steel": self.cb_sw_steel.get(),
            "gamma_s": ev(self.en_gs),
            "model": self.cb_model.get(),
            # 1b. Vật liệu ACI
            "code": self.cb_code.get(),
            "aci_fc": ev(self.en_fc), "aci_fy": ev(self.en_fy),
            "aci_fyt": ev(self.en_fyt), "aci_tie": self.cb_tie.get(),
            # 1c. Vật liệu EC2
            "ec2_conc": self.cb_ec2_conc.get(),
            "ec2_steel": ev(self.en_ec2_fyk),
            "ec2_method": self.cb_ec2_method.get(),
            "ec2_fyt": ev(self.en_ec2_fyt),
            # 2. Tiết diện
            "kind": self.cb_kind.get(),
            "cx": ev(self.en_cx), "cy": ev(self.en_cy),
            "dia": ev(self.en_dia),
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
            # Tên cấu kiện (ưu tiên từ JSON, fallback tên file ở on_load_data)
            _mn = d.get("member_name", "")
            if _mn and hasattr(self, "member_var"):
                self.member_var.set(_mn)
            self.cb_conc.set(d.get("concrete", "B25")); se(self.en_gb, d.get("gamma_b", "0.85"))
            self.cb_steel.set(d.get("steel", "CB400-V"))
            self.cb_sw_steel.set(d.get("sw_steel", "CB400-V"))
            se(self.en_gs, d.get("gamma_s", "1.0"))
            self.cb_model.set(d.get("model", self.cb_model.get()))
            # Vật liệu ACI (tương thích file cũ: giữ mặc định nếu thiếu)
            self.cb_code.set(d.get("code", self.cb_code.get()))
            se(self.en_fc, d.get("aci_fc", "30")); se(self.en_fy, d.get("aci_fy", "420"))
            se(self.en_fyt, d.get("aci_fyt", "420"))
            self.cb_tie.set(d.get("aci_tie", "Đai rời (tied)"))
            # Vật liệu EC2 (tương thích file cũ: giữ mặc định nếu thiếu)
            self.cb_ec2_conc.set(d.get("ec2_conc", "C30/37"))
            se(self.en_ec2_fyk, d.get("ec2_steel", "500"))
            self.cb_ec2_method.set(d.get("ec2_method", "Độ cứng danh nghĩa"))
            se(self.en_ec2_fyt, d.get("ec2_fyt", "500"))
            self._toggle_code()
            self.cb_kind.set(d.get("kind", "Chữ nhật"))
            se(self.en_cx, d.get("cx", "400")); se(self.en_cy, d.get("cy", "400"))
            se(self.en_dia, d.get("dia", "600"))
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
            _mn = self.member_var.get().strip() if hasattr(self, "member_var") else ""
            _init = f"{_mn}.json" if _mn else "CotBTCT.json"
            path = filedialog.asksaveasfilename(
                title="Lưu dữ liệu cột",
                defaultextension=".json",
                filetypes=[("JSON", "*.json")],
                initialfile=_init)
            if not path:
                return
        if self._do_save(path):
            self._update_title()
            messagebox.showinfo("Lưu dữ liệu", f"Đã lưu: {path}")

    def _update_ck(self):
        """Cập nhật tên cấu kiện (IN HOA) từ textbox - thay thế tên file."""
        ck = getattr(self, "ck_var", None)
        if ck is None:
            return
        mv = getattr(self, "member_var", None)
        name = mv.get().strip().upper() if mv else ""
        if name:
            ck.set(f"Cấu kiện: {name}")
        else:
            ck.set("")

    def _update_title(self):
        """Title bar hiện tên file đang lưu + mã bản build."""
        import os
        base = f"RC Column Design [{APP_BUILD}]"
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
            # Điền tên file vào textbox nếu JSON chưa có tên cấu kiện
            import os as _os
            if hasattr(self, "member_var") and not self.member_var.get().strip():
                _mn = _os.path.splitext(_os.path.basename(path))[0].upper()
                self.member_var.set(_mn)
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
        # Mục 1-7: widget kiểu Vietcon
        # (tab Chi tiết tự vẽ mới biểu đồ bằng hàm chung chart_draw)
        body = build_calc_widgets(self._calc_inner, inp, res, case_info,
                                  shear_info)
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
            "ab": f"{sec.concrete_area:.0f} mm\u00b2",
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

        # (Đã bỏ 3 box vật liệu theo yêu cầu user — chỉ giữ box thép)
        row1 = tk.Frame(parent, bg="#F9FAFB")
        row1.pack(fill=tk.X, padx=2, pady=(2, 4))
        _card(row1, "S\u1ed1 thanh", "n", "nsub")
        _card(row1, "T\u1ed5ng As", "as")
        _card(row1, "Di\u1ec7n t\u00edch Ab", "ab")
        _card(row1, "H\u00e0m l\u01b0\u1ee3ng \u03bc", "mu")
        return varmap

    def _build_param_table(self, parent, inp, res):
        """B\u1ea3ng th\u00f4ng s\u1ed1 t\u00ednh to\u00e1n (Treeview 3 c\u1ed9t)."""
        import math
        ttk.Label(parent, text="BẢNG THÔNG SỐ TÍNH TOÁN (TCVN 5574:2018)",
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
        alpha_deg = math.degrees(math.atan2(res.Mx_star, res.My_star)) \
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
        alpha_deg = math.degrees(math.atan2(res.Mx_star, res.My_star)) \
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
        alpha_deg = math.degrees(math.atan2(res.Mx_star, res.My_star)) \
            if abs(res.Mx_star) + abs(res.My_star) > 1e-9 else 0.0
        hdr = ttk.Frame(parent)
        hdr.pack(fill=tk.X, padx=4, pady=(2, 2))
        left = ttk.Frame(hdr)
        left.pack(side=tk.LEFT)
        tk.Label(left, text="\u25cf Bi\u1ec3u \u0111\u1ed3 t\u01b0\u01a1ng t\u00e1c N\u2013M\u03b1",
                 font=("", 10, "bold"), bg="white").pack(side=tk.LEFT)
        self._nm_alpha_lbl = tk.Label(
            left, text=f"  \u03b1 = {alpha_deg:.1f}\u00b0  ",
            font=("", 8, "bold"), fg="#065F46", bg="#D1FAE5")
        self._nm_alpha_lbl.pack(side=tk.LEFT, padx=6)
        # Combobox chọn góc xem biểu đồ N-M
        right = ttk.Frame(hdr)
        right.pack(side=tk.RIGHT)
        tk.Label(right, text="G\u00f3c xem:", font=("", 8),
                 bg="white").pack(side=tk.LEFT)
        _vals = ["\u03b1 (g\u00f3c t\u1ea3i)", "3D"] + \
            [f"{d}\u00b0" for d in range(0, 361, 15)]
        self._nm_angle_cb = ttk.Combobox(right, values=_vals, width=11,
                                         state="readonly", font=("", 9))
        self._nm_angle_cb.set("\u03b1 (g\u00f3c t\u1ea3i)")
        self._nm_angle_cb.pack(side=tk.LEFT, padx=(4, 0))
        self._nm_angle_cb.bind("<<ComboboxSelected>>",
                               self._on_nm_angle_changed)
        self._nm_view_angle = None  # None = góc tải mặc định

    def _on_nm_angle_changed(self, event=None):
        """Vẽ lại biểu đồ N-M tại góc được chọn trong Combobox."""
        try:
            sel = self._nm_angle_cb.get()
            if sel == "3D":
                self._draw_3d_interaction()
                return
            if sel.startswith("\u03b1"):
                angle = None
            else:
                angle = float(sel.replace("\u00b0", ""))
        except Exception:
            angle = None
        self._nm_view_angle = angle
        # Cập nhật nhãn α trên header
        try:
            if angle is None:
                import math
                res = self._last_res
                a0 = math.degrees(math.atan2(res.Mx_star, res.My_star)) \
                    if abs(res.Mx_star) + abs(res.My_star) > 1e-9 else 0.0
                self._nm_alpha_lbl.config(text=f"  \u03b1 = {a0:.1f}\u00b0  ")
            else:
                self._nm_alpha_lbl.config(
                    text=f"  xem {angle:.0f}\u00b0  ")
        except Exception:
            pass
        # Vẽ lại chỉ biểu đồ N-M
        try:
            # Nếu đang ở 3D (axes có projection 3d), tạo lại axes 2D
            _fig = self._nm_fig
            _cur_axes = _fig.axes[0] if _fig.axes else None
            _is_3d = _cur_axes is not None and getattr(_cur_axes, 'name', '') == '3d'
            if _is_3d:
                _fig.clear()
                ax = _fig.add_subplot(111)
                self._nm_ax_ref = ax
            else:
                ax = self._nm_ax_ref
                ax.clear()
            self._nm_draw_fn(ax, angle)
            self._nm_fig.tight_layout()
            self._nm_fig.subplots_adjust(bottom=0.30)
            self._nm_cv_ref.draw()
        except Exception:
            pass


    def _enable_manual_3d_rotate(self, cv_widget, fig, ax):
        """Xoay 3D thủ công bằng chuột trái (dự phòng khi mouse_init không hoạt động)."""
        state = {"drag": False, "x0": 0, "y0": 0, "elev0": 0, "azim0": 0}
        def _get_ax():
            try:
                _a = fig.axes[0] if fig.axes else None
                return _a if getattr(_a, 'name', '') == '3d' else None
            except Exception:
                return None
        def _press(ev):
            _a = _get_ax()
            if _a is None:
                return
            try:
                state["drag"] = True
                state["x0"], state["y0"] = ev.x, ev.y
                state["elev0"], state["azim0"] = _a.elev, _a.azim
            except Exception:
                pass
        def _move(ev):
            if not state["drag"]:
                return
            _a = _get_ax()
            if _a is None:
                return
            try:
                dx = ev.x - state["x0"]
                dy = ev.y - state["y0"]
                _a.view_init(elev=state["elev0"] - dy * 0.3,
                             azim=state["azim0"] + dx * 0.3)
                fig.stale = True
                fig.canvas.draw_idle()
                fig.canvas.flush_events()
            except Exception as ex:
                print(f"[3D-DEBUG] Move error: {ex}")
        def _rel(ev):
            state["drag"] = False
        try:
            # Xóa binding cũ tránh trùng lặp khi hàm 3D được gọi nhiều lần
            for _seq in ("<ButtonPress-1>", "<B1-Motion>", "<ButtonRelease-1>"):
                try:
                    cv_widget.unbind(_seq)
                except Exception:
                    pass
            cv_widget.bind("<ButtonPress-1>", _press)
            cv_widget.bind("<B1-Motion>", _move)
            cv_widget.bind("<ButtonRelease-1>", _rel)
        except Exception:
            pass

    def _draw_3d_aci(self):
        """Vẽ biểu đồ tương tác 3D cho ACI."""
        try:
            from mpl_toolkits.mplot3d import Axes3D  # noqa
            import numpy as np
            fig = self._aci_nm_fig
            fig.clear()
            ax = fig.add_subplot(111, projection='3d')
            # Đảm bảo mouse rotation hoạt động
            try:
                ax.mouse_init()
            except Exception:
                pass
            sec = getattr(self, '_aci_sec', None)
            conc = getattr(self, '_aci_conc', None)
            steel = getattr(self, '_aci_steel', None)
            tied = getattr(self, '_aci_tied', True)
            if sec is None or conc is None or steel is None:
                ax.text2D(0.5, 0.5, "Chưa có dữ liệu - hãy bấm KIỂM TRA",
                          transform=ax.transAxes, ha='center')
            else:
                from rc_column.aci_checker import ACICapacity
                cap = ACICapacity(sec, conc, steel, tied=tied, n_angles=24)
                n_vals, th_vals, m2_grid, m3_grid = cap.surface_grid(
                    n_n=25, n_angles=36)
                # Đóng vòng mặt 3D để fill kín 100%
                m2_grid = np.hstack([m2_grid, m2_grid[:, :1]])
                m3_grid = np.hstack([m3_grid, m3_grid[:, :1]])
                n_closed = len(th_vals) + 1
                ax.plot_surface(m2_grid, m3_grid,
                                np.tile(n_vals[:, None], (1, n_closed)),
                                cmap='Blues', alpha=0.7, edgecolor='none')
                # Điểm tải trọng A
                aci_inp = getattr(self, '_aci_inp', None)
                if aci_inp is not None:
                    ax.scatter([aci_inp.Mx], [aci_inp.My], [aci_inp.N],
                               color='red', s=50, label='Điểm tải A')
                    ax.legend()
                # (bỏ title theo yêu cầu)
            ax.set_xlabel('M2 (kN·m)')
            ax.set_ylabel('M3 (kN·m)')
            ax.set_zlabel('N (kN)')
            fig.tight_layout()
            self._aci_nm_cv_ref.draw()
            self._aci_nm_ax_ref = None
        except Exception as ex:
            print(f"Lỗi vẽ 3D ACI: {ex}")
            import traceback
            traceback.print_exc()

    def _draw_3d_ec2(self):
        """Vẽ biểu đồ tương tác 3D cho EC2."""
        try:
            from mpl_toolkits.mplot3d import Axes3D  # noqa
            import numpy as np
            fig = self._ec2_nm_fig
            fig.clear()
            ax = fig.add_subplot(111, projection='3d')
            # Đảm bảo mouse rotation hoạt động
            try:
                ax.mouse_init()
            except Exception:
                pass
            sec = getattr(self, '_ec2_sec', None)
            conc = getattr(self, '_ec2_conc', None)
            steel = getattr(self, '_ec2_steel', None)
            if sec is None or conc is None or steel is None:
                ax.text2D(0.5, 0.5, "Chưa có dữ liệu - hãy bấm KIỂM TRA",
                          transform=ax.transAxes, ha='center')
            else:
                from rc_column.ec2_checker import EC2Capacity
                cap = EC2Capacity(sec, conc, steel, n_angles=24)
                n_vals, th_vals, m2_grid, m3_grid = cap.surface_grid(
                    n_n=25, n_angles=36)
                # Đóng vòng mặt 3D để fill kín 100%
                m2_grid = np.hstack([m2_grid, m2_grid[:, :1]])
                m3_grid = np.hstack([m3_grid, m3_grid[:, :1]])
                n_closed = len(th_vals) + 1
                ax.plot_surface(m2_grid, m3_grid,
                                np.tile(n_vals[:, None], (1, n_closed)),
                                cmap='Oranges', alpha=0.7, edgecolor='none')
                # Điểm tải trọng A
                ec2_inp = getattr(self, '_ec2_inp', None)
                if ec2_inp is not None:
                    ax.scatter([ec2_inp.Mx], [ec2_inp.My], [ec2_inp.N],
                               color='red', s=50, label='Điểm tải A')
                    ax.legend()
                # (bỏ title theo yêu cầu)
            ax.set_xlabel('M2 (kN·m)')
            ax.set_ylabel('M3 (kN·m)')
            ax.set_zlabel('N (kN)')
            fig.tight_layout()
            self._ec2_nm_cv_ref.draw()
            self._ec2_nm_ax_ref = None
        except Exception as ex:
            print(f"Lỗi vẽ 3D EC2: {ex}")
            import traceback
            traceback.print_exc()

    def _draw_3d_interaction(self):
        """Vẽ biểu đồ tương tác 3D (N-M2-M3) cho TCVN."""
        try:
            from mpl_toolkits.mplot3d import Axes3D  # noqa
            import numpy as np
            fig = self._nm_fig
            fig.clear()
            ax = fig.add_subplot(111, projection='3d')
            # Đảm bảo mouse rotation hoạt động
            try:
                ax.mouse_init()
            except Exception:
                pass
            # Lấy sec và inp từ lần tính cuối, dựng BiaxialCapacity
            sec = getattr(self, '_last_sec', None)
            inp = getattr(self, '_last_inp', None)
            if sec is None or inp is None:
                ax.text2D(0.5, 0.5, "Chưa có dữ liệu - hãy bấm KIỂM TRA",
                          transform=ax.transAxes, ha='center')
            else:
                from rc_column.interaction import BiaxialCapacity
                cap = BiaxialCapacity(sec, model=inp.concrete_model,
                                      n_angles=24)
                n_vals, th_vals, mx_grid, my_grid = cap.surface_grid(
                    n_n=25, n_angles=36)
                # Đóng vòng mặt 3D (thêm cột 360° = cột 0°) để fill kín
                mx_grid = np.hstack([mx_grid, mx_grid[:, :1]])
                my_grid = np.hstack([my_grid, my_grid[:, :1]])
                n_angles_closed = len(th_vals) + 1
                # Vẽ mặt 3D
                ax.plot_surface(mx_grid, my_grid,
                                np.tile(n_vals[:, None], (1, n_angles_closed)),
                                cmap='Greens', alpha=0.7, edgecolor='none')
                # Vẽ điểm tải trọng A
                res = getattr(self, '_last_res', None)
                if res is not None:
                    ax.scatter([res.Mx_star], [res.My_star], [res.N],
                               color='red', s=50, label='Điểm tải A')
                    ax.legend()
            ax.set_xlabel('M2 (kN·m)')
            ax.set_ylabel('M3 (kN·m)')
            ax.set_zlabel('N (kN)')
            # (bỏ title theo yêu cầu)
            fig.tight_layout()
            self._nm_cv_ref.draw()
            self._nm_ax_ref = None
        except Exception as ex:
            print(f"Lỗi vẽ 3D: {ex}")
            import traceback
            traceback.print_exc()

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

            # Bảng Phương 2 | Phương 3 (header là tiêu đề, không cần label riêng)
            tf = tk.Frame(parent, bg="white")
            tf.pack(fill=tk.X, padx=8, pady=(4, 2))
            headers = ["KIỂM TRA KHẢ NĂNG CHỊU CẮT", "Phương V2", "Phương V3"]
            for j, h in enumerate(headers):
                tk.Label(tf, text=h, font=("", 9, "bold"), bg="#F3F4F6",
                         fg="#111827", borderwidth=0,
                         highlightthickness=0,
                         anchor="w" if j == 0 else "center",
                         padx=6, pady=7).grid(row=0, column=j, sticky="nsew")
                # Tỉ lệ cột 90-45-45 (2:1:1), uniform để giữ đúng tỉ lệ
                tf.columnconfigure(j, weight=2 if j == 0 else 1, uniform="sw")
            rows = [
                ("Thép đai bố trí",
                 cols['2']['sw_txt'], cols['3']['sw_txt']),
                ("Lực cắt tính toán, Q",
                 f"{cols['2']['Q']:.1f} kN", f"{cols['3']['Q']:.1f} kN"),
                ("Kích thước tiết diện, b × h0",
                 f"{cols['2']['b']:.0f} × {cols['2']['h0']:.0f} mm",
                 f"{cols['3']['b']:.0f} × {cols['3']['h0']:.0f} mm"),
                ("Asw = n × φ",
                 f"{cols['2']['Asw']:.0f} mm²", f"{cols['3']['Asw']:.0f} mm²"),
                ("qsw = Rsw × Asw/s",
                 f"{cols['2']['qsw']:.1f} N/mm", f"{cols['3']['qsw']:.1f} N/mm"),
                ("Độ bền trên dải nén xiên Q ≤ 0.3×Rb×b×h0",
                 f"{cols['2']['sh'].Qcap1:.1f} kN",
                 f"{cols['3']['sh'].Qcap1:.1f} kN"),
                ("Qb = 1.5×Rbt×b×h0²/C",
                 f"{cols['2']['sh'].Qb_opt:.1f} kN",
                 f"{cols['3']['sh'].Qb_opt:.1f} kN"),
                ("Qsw = 0.75×qsw×C",
                 f"{cols['2']['sh'].Qsw_opt:.1f} kN",
                 f"{cols['3']['sh'].Qsw_opt:.1f} kN"),
                ("Chiều dài hình chiếu của vết nứt xiên C",
                 f"{cols['2']['sh'].C_opt:.0f} mm",
                 f"{cols['3']['sh'].C_opt:.0f} mm"),
                ("Độ bền trên vết nứt xiên Q ≤ [Q] = Qb + Qsw",
                 f"{cols['2']['sh'].Qcap2:.1f} kN",
                 f"{cols['3']['sh'].Qcap2:.1f} kN"),
                ("Kết luận",
                 "ĐẠT" if cols['2']['sh'].ok else "KHÔNG ĐẠT",
                 "ĐẠT" if cols['3']['sh'].ok else "KHÔNG ĐẠT"),
            ]
            for i, (a, b, c) in enumerate(rows):
                bg = "#F9FAFB" if i % 2 else "white"
                is_kl = (a == "Kết luận")
                for j, t in enumerate((a, b, c)):
                    fw = ("", 9)  # nội dung bảng không in đậm
                    fg = "#1F2937"
                    if is_kl and j > 0:
                        fg = "#065F46" if t == "ĐẠT" else "#991B1B"
                        fw = ("", 9, "bold")  # kết quả in đậm
                    tk.Label(tf, text=t, font=fw, bg=bg, fg=fg,
                             borderwidth=0,
                             highlightthickness=0,
                             padx=6, pady=6, anchor="w" if j == 0
                             else "center").grid(row=i + 1, column=j,
                                                 sticky="nsew")
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
        from rc_column.chart_draw import draw_nm_alpha_ax, draw_m2m3_ax
        fs = FiberSection(sec)

        def _nm_alpha_ax(ax, title_sz=12, view_angle_deg=None):
            # Biểu đồ N-M tại góc uốn xiên α (dùng điểm B song trục)
            # view_angle_deg: góc xem đường cong (None = góc tải trọng)
            # Style theo mẫu: đường xanh lá, fill nhạt, lưới đứt mảnh
            GREEN, GREEN_LT = "#059669", "#D1FAE5"
            RED, ORANGE = "#DC2626", "#F97316"
            BLUE_DASH = "#3B82F6"
            if view_angle_deg is not None:
                alpha_deg = view_angle_deg
            else:
                alpha_deg = math.degrees(
                    math.atan2(res.Mx_star, res.My_star))
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
            _xlbl = ("Mα (kN·m)" if view_angle_deg is None
                     else f"Mα (kN·m) @ {view_angle_deg:.0f}°")
            ax.set_xlabel(_xlbl, fontweight="bold", fontsize=10)
            ax.set_ylabel("N (kN)", fontweight="bold", fontsize=10)

            # Legend 4 mục như web, đặt dưới biểu đồ
            from matplotlib.lines import Line2D
            leg_elems = [
                Line2D([0], [0], color=GREEN, lw=2.2, label="Đường bao N-Mα"),
                Line2D([0], [0], color=RED, lw=1.5, ls="--", dashes=(4, 3),
                       label="Tia tải O-A-B"),
                Line2D([0], [0], marker="o", color="w", markerfacecolor=GREEN,
                       markersize=8, markeredgecolor="white", label="Điểm tải A"),
                Line2D([0], [0], marker="D", color="w", markerfacecolor=ORANGE,
                       markersize=7, markeredgecolor="white", label="Điểm giới hạn B"),
            ]
            ax.legend(handles=leg_elems, fontsize=8, loc="upper center",
                      bbox_to_anchor=(0.5, -0.18), ncol=2, frameon=False)
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
                Line2D([0], [0], color=RED, lw=1.5, ls="--", dashes=(4, 3),
                       label="Tia tải O-A-B"),
                Line2D([0], [0], marker="o", color="w", markerfacecolor=GREEN,
                       markersize=8, markeredgecolor="white", label="Điểm tải A"),
                Line2D([0], [0], marker="D", color="w", markerfacecolor=ORANGE,
                       markersize=7, markeredgecolor="white", label="Điểm giới hạn B"),
            ]
            ax.legend(handles=leg_elems, fontsize=8, loc="upper center",
                      bbox_to_anchor=(0.5, -0.18), ncol=2, frameon=False)
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
            _w = cv.get_tk_widget()
            # takefocus=0 ngăn canvas chiếm focus (đủ để cuộn chuột
            # hoạt động); KHÔNG chặn ButtonPress/Release để biểu đồ
            # 3D xoay được bằng kéo chuột
            try:
                _w.configure(highlightthickness=0, takefocus=0,
                             highlightbackground="white", highlightcolor="white",
                             borderwidth=0)
            except Exception:
                pass
            _w.pack(fill=tk.BOTH, expand=True)
            return fig, cv

        # Grid 2x2 trong _sum_inner
        self._sum_inner.columnconfigure(0, weight=1)
        self._sum_inner.columnconfigure(1, weight=1)
        self._sum_inner.rowconfigure(0, weight=1)
        self._sum_inner.rowconfigure(1, weight=1)

        # ===== Ô trên-phải: sơ đồ mặt cắt + thẻ thống kê =====
        f_tl = tk.Frame(self._sum_inner, bg="white", highlightbackground="#D1D5DB",
                        highlightthickness=1)
        f_tl.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        tk.Label(f_tl, text="SƠ ĐỒ MẶT CẮT TIẾT DIỆN CỘT",
                 font=("", 11, "bold"), bg="white").pack(pady=(2, 2))
        self.ck_var = tk.StringVar(value="")
        # Bỏ hiển thị tên cấu kiện ở sơ đồ (đã có ở textbox panel trái)
        fig_sec, cv_sec = _new_fig(f_tl, (3.9, 3.1))
        a1 = fig_sec.add_subplot(111)
        draw_section_ax(a1, sec, show_stats=False, dot_scale=1.5)
        fig_sec.tight_layout()
        cv_sec.draw()
        self._sec_fig, self._sec_canvas, self._sec_ax = fig_sec, cv_sec, a1
        self._sec_card_vars = self._build_section_cards(f_tl, sec, inp)

        # ===== Ô trên-trái: bảng thông số tính toán =====
        f_tr = tk.Frame(self._sum_inner, bg="white",
                        highlightbackground="#D1D5DB", highlightthickness=1)
        f_tr.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._build_param_table(f_tr, inp, res)

        # ===== Ô dưới-trái: header + biểu đồ N-M =====
        f_bl = ttk.Frame(self._sum_inner)
        f_bl.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._build_nm_header(f_bl, res)
        fig_nm, cv_nm = _new_fig(f_bl, (5.2, 3.9))
        self._nm_fig = fig_nm
        a3 = fig_nm.add_subplot(111)
        draw_nm_alpha_ax(a3, sec, inp, res, fs)
        fig_nm.tight_layout()
        fig_nm.subplots_adjust(bottom=0.30)
        cv_nm.draw()
        # Lưu tham chiếu để vẽ lại khi đổi góc xem
        self._nm_ax_ref = a3
        self._nm_cv_ref = cv_nm
        self._nm_draw_fn = lambda ax, va=None: _nm_alpha_ax(
            ax, view_angle_deg=va)

        # ===== Ô dưới-phải: header + biểu đồ M2-M3 =====
        f_br = ttk.Frame(self._sum_inner)
        f_br.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        self._build_m2m3_header(f_br, res)
        fig_mm, cv_mm = _new_fig(f_br, (5.2, 3.9))
        self._m2m3_fig = fig_mm
        a4 = fig_mm.add_subplot(111)
        draw_m2m3_ax(a4, sec, inp, res)
        fig_mm.tight_layout()
        fig_mm.subplots_adjust(bottom=0.30)
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
