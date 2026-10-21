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

def _git_commit():
    """Lấy hash commit git ngắn (7 ký tự) khi chạy từ source.
    Đọc trực tiếp thư mục .git nên không cần git trong PATH;
    trả về '' nếu không tìm thấy."""
    import os as _os
    # Tìm thư mục .git (lên tối đa 5 cấp từ thư mục file này)
    _d = _os.path.dirname(_os.path.abspath(__file__))
    _root = None
    for _ in range(5):
        if _os.path.isdir(_os.path.join(_d, ".git")):
            _root = _os.path.join(_d, ".git")
            break
        _parent = _os.path.dirname(_d)
        if _parent == _d:
            break
        _d = _parent
    if not _root:
        return ""
    try:
        with open(_os.path.join(_root, "HEAD"), "r") as _f:
            _head = _f.read().strip()
        if _head.startswith("ref:"):
            _ref = _head[4:].strip()
            # Tìm ref trong file rời trước, rồi packed-refs
            _ref_path = _os.path.join(_root, *_ref.split("/"))
            if _os.path.isfile(_ref_path):
                with open(_ref_path, "r") as _f:
                    return _f.read().strip()[:7]
            _packed = _os.path.join(_root, "packed-refs")
            if _os.path.isfile(_packed):
                with open(_packed, "r") as _f:
                    for _line in _f:
                        _line = _line.strip()
                        if _line.endswith(_ref):
                            return _line.split()[0][:7]
            return ""
        return _head[:7]  # detached HEAD
    except Exception:
        return ""

_GIT_COMMIT = _git_commit()


def _ensure_app_user_model_id():
    """Windows: gán AppUserModelID riêng cho tiến trình để taskbar gom
    cửa sổ theo đúng app này và dùng icon của app, thay vì gom theo
    python.exe (icon Python) khi chạy từ source. Phải gọi trước khi tạo
    cửa sổ; ngoài Windows là no-op."""
    try:
        import sys as _sys
        if _sys.platform != "win32":
            return
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "RCColumnDesign.App")
    except Exception:
        pass

import math
import tkinter as tk
from tkinter import ttk, messagebox

from rc_column.checker import ColumnInput, build_section, check_column
from rc_column.lang import T, set_lang
from rc_column.aci_materials import ACIConcrete, ACISteel
from rc_column.aci_checker import check_column_aci, moment_magnification, aci_shear_check
from rc_column.materials import CONCRETE_GRADES, STEEL_GRADES
from rc_column.report import generate_report_sections
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

from .tcvn_mixin import TcvnMixin
from .aci_mixin import AciMixin
from .ec2_mixin import Ec2Mixin
from .etabs_mixin import EtabsMixin
from .pdf_mixin import PdfMixin
from .build_mixin import BuildMixin
from .data_mixin import DataMixin
from .dxf_mixin import DxfMixin
from .preview_mixin import PreviewMixin


class App(tk.Tk, TcvnMixin, AciMixin, Ec2Mixin, EtabsMixin, PdfMixin,
          BuildMixin, DataMixin, DxfMixin, PreviewMixin):
    def __init__(self):
        _ensure_app_user_model_id()
        super().__init__()
        _gc = f" · {_GIT_COMMIT}" if _GIT_COMMIT else ""
        self.title(f"RC Column Design [{APP_BUILD}]{_gc}")
        self.geometry("1360x860")
        # Icon cửa sổ (title bar + taskbar). Nguồn duy nhất: icon.png /
        # icon.ico ở thư mục gốc repo (chạy source) hoặc trong bundle exe
        # (build_exe.py đóng gói kèm bằng --add-data; thiếu là bản exe
        # không tìm thấy file và cửa sổ mất icon). PNG qua iconphoto —
        # đặt làm mặc định cho cả cửa sổ con/hộp thoại. Riêng Windows gắn
        # thêm iconbitmap bằng file .ico: đó là đường icon gốc của
        # Windows (đủ size 16/32/48 cho title bar và taskbar).
        try:
            import os, sys
            _bases = [os.path.normpath(os.path.join(
                os.path.dirname(os.path.abspath(__file__)), ".."))]
            if hasattr(sys, "_MEIPASS"):
                _bases.insert(0, sys._MEIPASS)
            if getattr(sys, "frozen", False):
                _bases.append(os.path.dirname(
                    os.path.abspath(sys.executable)))
            _png = _ico = None
            for _b in _bases:
                if _png is None and os.path.exists(
                        os.path.join(_b, "icon.png")):
                    _png = os.path.join(_b, "icon.png")
                if _ico is None and os.path.exists(
                        os.path.join(_b, "icon.ico")):
                    _ico = os.path.join(_b, "icon.ico")
            if _png:
                try:
                    _img = tk.PhotoImage(file=_png)
                    self.iconphoto(True, _img)
                    self._icon_img = _img
                except Exception:
                    pass
            if _ico and sys.platform == "win32":
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
        # Làm ấm matplotlib khi app đã hiện và rảnh: trả trước chi phí
        # font cache + tight_layout/draw lần đầu để CHECK lạnh đầu tiên
        # không phải gánh (chỉ dời chi phí, không đổi kết quả)
        self.after(600, self._warmup_matplotlib)

    def _warmup_matplotlib(self):
        """Vẽ thử 1 figure nhỏ bằng Agg (không hiện) để nạp font cache và
        chạy qua đường tight_layout/draw lần đầu của matplotlib trong
        lúc app rảnh, thay vì dồn vào lần CHECK đầu tiên."""
        if not HAS_MPL:
            return
        try:
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            fig = Figure(figsize=(3.0, 2.0))
            ax = fig.add_subplot(111)
            ax.plot([0.0, 1.0], [0.0, 1.0])
            ax.set_title("warmup")
            ax.set_xlabel("M3")
            ax.set_ylabel("M2")
            fig.tight_layout()
            FigureCanvasAgg(fig).draw()
        except Exception:
            pass

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
    def _defer_detail(self, fn):
        """Trì hoãn render tab Chi tiết tới lần mở tab đầu tiên sau CHECK.

        CHECK chỉ tính + vẽ tab Kết quả; nội dung tab Chi tiết (thuyết
        minh + fig riêng) được dựng lười (lazy) khi user bấm sang tab
        CHI TIẾT TÍNH TOÁN — hoặc NGAY trong CHECK nếu user đang đứng
        ở tab đó. fn là closure render (đã gồm xử lý lỗi như cũ); một
        CHECK mới ghi đè closure cũ chưa chạy (khớp hành vi cũ: render
        mới thay nội dung cũ). Số liệu không đổi — closure chỉ đọc dict
        kết quả đã tính 1 lần như đường render trực tiếp trước đây.
        """
        self._pending_detail = fn
        if getattr(self, "_current_tab", "sum") == "calc":
            self._flush_detail()

    def _flush_detail(self):
        """Chạy closure render tab Chi tiết đang chờ (nếu có), đúng 1 lần."""
        fn = getattr(self, "_pending_detail", None)
        if fn is not None:
            self._pending_detail = None
            fn()

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
            # Dựng nội dung Chi tiết đang chờ (lazy) ngay khi mở tab
            self._flush_detail()

    def _switch_lang(self, lang):
        """Chuyển ngôn ngữ VN/EN. Áp dụng cho kết quả mới tính."""
        from rc_column import lang as _lang
        _lang.set_lang(lang)
        self._lang_var.set(lang)
        # Nếu đã có kết quả, tính lại để hiển thị ngôn ngữ mới
        if hasattr(self, '_last_result') and self._last_result:
            self.on_check()

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

    def _update_title(self):
        """Title bar hiện tên file đang lưu + mã bản build."""
        import os
        _gc = f" · {_GIT_COMMIT}" if _GIT_COMMIT else ""
        base = f"RC Column Design [{APP_BUILD}]{_gc}"
        p = getattr(self, "current_save_path", None)
        if p:
            self.title(f"{base} — [{os.path.basename(p)}]")
        else:
            self.title(base)


def main():
    _ensure_app_user_model_id()
    app = App()
    app._refresh_rebar()
    app.mainloop()


if __name__ == "__main__":
    main()
