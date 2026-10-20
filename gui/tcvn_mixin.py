"""Các method tính toán và hiển thị theo TCVN 5574:2018."""

import tkinter as tk
from tkinter import ttk, messagebox
import math
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import matplotlib.patches as mpatches
    HAS_MPL = True
except Exception:
    HAS_MPL = False
from rc_column.checker import ColumnInput, build_section, check_column
from rc_column.report import generate_report_sections
from rc_column.materials import CONCRETE_GRADES, STEEL_GRADES
from rc_column.sections import clear_spacing, bar_area
from rc_column.stability import BOUNDARY_NAMES, LongTermLoads
from rc_column.lang import T


class TcvnMixin:
    """Các method tính toán và hiển thị theo TCVN 5574:2018."""

    def _tcvn_calculate_full(self, inp, n_angles=24):
        """Tính toán đầy đủ TCVN cho 1 bộ nội lực. Trả về dict kết quả hoàn chỉnh.

        NGUYÊN TẮC: Tính 1 lần ở đây, các nơi khác (tab, PDF) chỉ đọc hiển thị.

        Dict trả về gồm:
        - inp: ColumnInput (đã gán N/Mx/My/Q2/Q3)
        - res: CheckResult từ check_column (đầy đủ dc, fs, v.v.)
        - sec: Section object
        - N, M2, M3, Q2, Q3: nội lực (M2=Mx, M3=My)
        - case_info: dict thông tin tổ hợp (nếu có)
        - shear_info: dict thông tin cắt (nếu có)
        """
        from rc_column.checker import check_column, build_section

        # Tính toán đầy đủ 1 lần
        res = check_column(inp, n_angles=n_angles)
        sec = build_section(inp)

        # Tính cắt 1 lần ở đây (để tab/PDF chỉ hiển thị, không tính lại)
        # Nguồn duy nhất: rc_column.stirrup.compute_shear_cols
        from rc_column.stirrup import compute_shear_cols
        _shear_cols = compute_shear_cols(inp, sec)

        # Tính alpha 1 lần từ M* (dùng chung)
        import math as _math
        try:
            _mx_s = res.Mx_star if hasattr(res, 'Mx_star') else inp.Mx
            _my_s = res.My_star if hasattr(res, 'My_star') else inp.My
            _alpha = _math.degrees(_math.atan2(_mx_s, _my_s)) if abs(_mx_s)+abs(_my_s) > 1e-9 else 0.0
            _Malpha = _math.hypot(_mx_s, _my_s)
        except:
            _alpha, _Malpha = 0.0, 0.0
        return {
            "inp": inp,
            "res": res,
            "alpha_deg": _alpha,
            "Malpha": _Malpha,
            "sec": sec,
            "N": inp.N,
            "M2": inp.Mx,
            "M3": inp.My,
            "Q2": inp.Q2,
            "Q3": inp.Q3,
            "dc": res.dc if hasattr(res, 'dc') else 0,
            "fs": res.fs if hasattr(res, 'fs') else 0,
            "ok": res.ok if hasattr(res, 'ok') else False,
            "shear_cols": _shear_cols,
        }

    def _show_summary(self, sec, inp, res, prefix=""):
        """Cập nhật biểu đồ (note L0 đã bỏ theo yêu cầu)."""
        if HAS_MPL:
            self._last_sec = sec
            self._last_inp = inp
            self._last_res = res
            self._redraw()

    def _render_report(self, segs):
        """Hiển thị thuyết minh với format VietconSoft (giữ để tương thích)."""
        t = self.calc_text
        t.delete("1.0", tk.END)
        self._setup_report_tags(t)
        for text, tags in segs:
            t.insert(tk.END, self._clean_math(text), tags if tags else ())
        self._report_images = []

    def _render_report_sections(self, sections, sec, inp, res,
                                case_info=None, shear_info=None):
        """Hiển thị thuyết minh kiểu Vietcon: mục 1-7 dạng card."""
        from rc_column.report_widgets import build_calc_widgets
        # Xóa nội dung cũ
        for w in self._calc_inner.winfo_children():
            w.destroy()
        # Mục 1-7: widget kiểu Vietcon
        # (tab Chi tiết tự vẽ mới biểu đồ bằng hàm chung chart_draw)
        # Lấy shear_cols từ _tcvn_full (đã tính 1 lần) - KHÔNG tính lại
        _shear_cols = None
        try:
            _tf = getattr(self, "_tcvn_full", None)
            if _tf and isinstance(_tf, dict):
                _shear_cols = _tf.get("shear_cols")
        except:
            pass
        body = build_calc_widgets(self._calc_inner, inp, res, case_info,
                                  shear_info, _shear_cols)
        body.pack(fill=tk.BOTH, expand=True)
        # Cập nhật scroll
        self._calc_inner.update_idletasks()
        self._calc_canvas.configure(
            scrollregion=self._calc_canvas.bbox("all"))
        self._bind_wheel(self._calc_inner, self._calc_canvas)

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

    def _get_tcvn_param_rows(self, inp, res):
        """Trả về rows data cho bảng thông số TCVN."""
        import math
        alpha_deg = math.degrees(math.atan2(res.Mx_star, res.My_star)) \
            if abs(res.Mx_star) + abs(res.My_star) > 1e-9 else 0.0
        Ma = math.hypot(res.Mx_star, res.My_star)
        rows = [
            ("N", "Lực dọc tính toán", f"{res.N:+.1f} kN"),
            ("M2", "Mô men ban đầu phương 2", f"{res.Mx:.1f} kN×m"),
            ("M3", "Mô men ban đầu phương 3", f"{res.My:.1f} kN×m"),
            ("e02", "Độ lệch tâm ban đầu phương 2", f"{res.e0x:.1f} mm"),
            ("e03", "Độ lệch tâm ban đầu phương 3", f"{res.e0y:.1f} mm"),
            ("λ2", "Độ mảnh cột phương 2", f"{res.lambda_x:.1f}"),
            ("λ3", "Độ mảnh cột phương 3", f"{res.lambda_y:.1f}"),
            ("Ncr,2", "Lực tới hạn Euler phương 2", f"{res.Ncrx:.1f} kN"),
            ("Ncr,3", "Lực tới hạn Euler phương 3", f"{res.Ncry:.1f} kN"),
            ("α", "Góc tác dụng mô men", f"{alpha_deg:.1f} °"),
            ("η2", "Hệ số uốn dọc phương 2", f"{res.etax:.3f}"),
            ("η3", "Hệ số uốn dọc phương 3", f"{res.etay:.3f}"),
            ("M2*", "Mô men tính toán phương 2", f"{res.Mx_star:.1f} kN×m"),
            ("M3*", "Mô men tính toán phương 3", f"{res.My_star:.1f} kN×m"),
            ("Mα", "Mô men tổng theo phương kiểm tra", f"{Ma:.1f} kN×m"),
        ]
        ok = res.ok
        fs_txt = f"{res.fs:.2f}" if math.isfinite(res.fs) else "∞"
        ok_txt = "ĐẠT" if ok else "KHÔNG ĐẠT"
        dc_row = ("D/C", "Tỷ số sử dụng khả năng chịu lực",
                  f"{res.dc:.3f} (FS = {fs_txt})  {ok_txt}", ok)
        return rows, dc_row, alpha_deg, Ma

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
        tree.column("sym", width=84, anchor="center", stretch=False)
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
        tree.pack(fill=tk.X, expand=False, padx=2, pady=2)

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
        self._nm_view_angle = None

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

    def _build_stirrup_summary(self, parent, inp, res, full_res=None):
        """Bảng kiểm tra thép đai: Phương 2 | Phương 3.
        CHỈ hiển thị từ full_res (đã tính bởi _tcvn_calculate_full), KHÔNG tính lại."""
        # Lấy kết quả cắt đã tính sẵn
        _fr = full_res or {}
        _cols = _fr.get("shear_cols") or {}
        if _cols:
            # Dùng kết quả có sẵn - KHÔNG tính lại (nguyên tắc "tính 1 lần")
            cols = _cols
        else:
            # Fallback: tính bằng ĐÚNG hàm dùng chung compute_shear_cols
            # (nguồn duy nhất — không viết công thức riêng ở đây)
            from rc_column.stirrup import compute_shear_cols
            try:
                cols = compute_shear_cols(inp, self._last_sec)
                if not cols:
                    raise ValueError("compute_shear_cols trả về rỗng")
            except Exception as ex:
                # Nếu lỗi, hiển thị thông báo
                import tkinter as tk
                tk.Label(parent, text=f"Không tính được thép đai: {ex}", fg="red", bg="white").pack()
                return
        # Hiển thị bảng từ cols (dùng chung cho cả 2 nhánh)
        import tkinter as tk
        tf = tk.Frame(parent, bg="white")
        tf.pack(fill=tk.X, padx=8, pady=6)
        headers = ["KIỂM TRA KHẢ NĂNG CHỊU CẮT", "Phương V2", "Phương V3"]
        for j, h in enumerate(headers):
            tk.Label(tf, text=h, font=("", 9, "bold"), bg="#F3F4F6", fg="#111827",
                     borderwidth=0, highlightthickness=0,
                     anchor="w" if j == 0 else "center",
                     padx=6, pady=7).grid(row=0, column=j, sticky="nsew")
            tf.columnconfigure(j, weight=2 if j == 0 else 1, uniform="sw")
        rows = [
            ("Thép đai bố trí", cols['2']['sw_txt'], cols['3']['sw_txt']),
            ("Lực cắt tính toán, Q", f"{cols['2']['Q']:.1f} kN", f"{cols['3']['Q']:.1f} kN"),
            ("Kích thước tiết diện, b × h0", f"{cols['2']['b']:.0f} × {cols['2']['h0']:.0f} mm", f"{cols['3']['b']:.0f} × {cols['3']['h0']:.0f} mm"),
            ("Asw = n × φ", f"{cols['2']['Asw']:.0f} mm²", f"{cols['3']['Asw']:.0f} mm²"),
            ("qsw = Rsw × Asw/s", f"{cols['2']['qsw']:.1f} N/mm", f"{cols['3']['qsw']:.1f} N/mm"),
        ]
        # Thêm các hàng từ kết quả check_shear
        try:
            sh2 = cols['2']['sh']
            sh3 = cols['3']['sh']
            rows.extend([
                ("Độ bền trên dải nén xiên Q ≤ 0.3×Rb×b×h0", f"{sh2.Qcap1:.1f} kN", f"{sh3.Qcap1:.1f} kN"),
                ("Qb = 1.5×Rbt×b×h0²/C", f"{sh2.Qb_opt:.1f} kN", f"{sh3.Qb_opt:.1f} kN"),
                ("Qsw = 0.75×qsw×C", f"{sh2.Qsw_opt:.1f} kN", f"{sh3.Qsw_opt:.1f} kN"),
                ("Chiều dài hình chiếu của vết nứt xiên C", f"{sh2.C_opt:.0f} mm", f"{sh3.C_opt:.0f} mm"),
                ("Độ bền trên vết nứt xiên Q ≤ [Q] = Qb + Qsw", f"{sh2.Qcap2:.1f} kN", f"{sh3.Qcap2:.1f} kN"),
                ("Kết luận", "✓ ĐẠT" if sh2.ok else "✗ KHÔNG ĐẠT", "✓ ĐẠT" if sh3.ok else "✗ KHÔNG ĐẠT"),
            ])
        except:
            pass
        for i, (label, v2, v3) in enumerate(rows, start=1):
            # Màu xen kẽ như bảng thông số bên trên
            _bg = "#F9FAFB" if i % 2 == 0 else "white"
            tk.Label(tf, text=label, font=("", 9), bg=_bg, fg="#111827",
                     anchor="w", padx=6, pady=4).grid(row=i, column=0, sticky="nsew")
            tk.Label(tf, text=v2, font=("", 9), bg=_bg, fg="#111827",
                     anchor="center", padx=6, pady=4).grid(row=i, column=1, sticky="nsew")
            tk.Label(tf, text=v3, font=("", 9), bg=_bg, fg="#111827",
                     anchor="center", padx=6, pady=4).grid(row=i, column=2, sticky="nsew")


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

    def _bind_wheel_to_calc(self, widget):
        """Gắn cuộn chuột cho thanh công cụ -> cuộn canvas thuyết minh."""
        self._bind_wheel(widget, self._calc_canvas)

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
                pass
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
            import traceback
            traceback.print_exc()

    def _redraw(self):
        """Tab Kết quả tính toán cho TCVN - dùng bản gốc (ổn định).
        ACI/EC2 dùng unified renderer. Sẽ migrate TCVN sau khi ổn định."""
        return self._redraw_old()

    def _redraw_new_unified(self):
        """[WIP] Bản dùng unified renderer - đang lỗi, chưa dùng."""
        if not HAS_MPL or self._last_sec is None:
            return
        from gui.result_renderer import render_result_tab
        from rc_column.pdf_export import draw_section_ax
        from rc_column.chart_draw import draw_nm_alpha_ax, draw_m2m3_ax
        import math

        sec, inp, res = self._last_sec, self._last_inp, self._last_res

        # Lấy rows thông số
        param_rows, dc_row, alpha_deg, Ma = self._get_tcvn_param_rows(inp, res)

        # Section cards
        vals = self._section_card_values(sec)
        section_cards = {"n": vals["n"], "as": vals["as"], "ab": vals["ab"], "mu": vals["mu"]}

        # Hàm vẽ N-M (dùng góc đã chọn nếu có)
        def _draw_nm(ax):
            _view_angle = getattr(self, "_tcvn_nm_view_angle", None)
            _Mx_star = res.Mx_star
            _My_star = res.My_star
            if _view_angle is not None:
                _Ma = math.hypot(_Mx_star, _My_star)
                _rad = math.radians(_view_angle)
                _Mx_star = _Ma * math.sin(_rad)
                _My_star = _Ma * math.cos(_rad)
            draw_nm_alpha_ax(ax, sec, inp, res, _Mx_star, _My_star)

        # Hàm vẽ M2-M3
        def _draw_m2m3(ax):
            draw_m2m3_ax(ax, sec, inp, res)

        # Notes
        _ok = res.ok
        _okt = "ĐẠT" if _ok else "KHÔNG ĐẠT"
        _okc = "#059669" if _ok else "#DC2626"
        _case = getattr(self, "_pdf_case", None) or {}
        _parts = []
        if _case.get("story"): _parts.append(str(_case.get("story")))
        if _case.get("column"): _parts.append(str(_case.get("column")))
        if _case.get("case"):
            _st = _case.get("station", "")
            _st_txt = f"@{_st:.2f}" if isinstance(_st, (int, float)) else ""
            _parts.append(f"{_case.get('case')}{_st_txt}")
        _combo_txt = f" [{', '.join(_parts)}]" if _parts else ""
        # Lấy thông tin B từ res
        _BN = getattr(res, 'BN', 0)
        _Bx = getattr(res, 'Bx', 0)
        _By = getattr(res, 'By', 0)
        _Mb = math.hypot(_Bx, _By)
        notes = [
            (f"● Đường bao kiểm tra: N-Mα (α = {alpha_deg:.1f}°) — TCVN 5574:2018   D/C = {res.dc:.3f} → {_okt}", _okc),
            (f"● A (điểm tải){_combo_txt}:  N = {res.N:+.1f} kN,  Mα = {Ma:.1f} kN×m  (M2 = {res.Mx_star:.1f}, M3 = {res.My_star:.1f})", "#2563EB"),
            (f"◆ B (điểm giới hạn):  N = {_BN:+.1f} kN,  Mα,u = {_Mb:.1f} kN×m  (M2u = {_Bx:.1f}, M3u = {_By:.1f})", "#EA580C"),
        ]

        config = {
            "std_title": "(TCVN 5574:2018)",
            "param_rows": param_rows,
            "dc_row": dc_row,
            "section": sec,
            "section_cards": section_cards,
            "draw_nm": _draw_nm,
            "draw_m2m3": _draw_m2m3,
            "nm_title": "Biểu đồ tương tác N-Mα",
            "nm_alpha_text": f"α = {alpha_deg:.1f}°",
            "m2m3_title": "Mặt cắt M2-M3",
            "m2m3_n_text": f"N = {res.N:+.1f} kN",
            "notes_nm": notes,
            "on_nm_angle_change": lambda sel: self._on_tcvn_angle_unified(sel),
            "shear_builder": lambda parent: self._build_stirrup_summary(
                parent, inp, res, getattr(self, '_tcvn_full', {}) or {}),
        }
        render_result_tab(self, config)
        self._update_ck()

    def _on_tcvn_angle_unified(self, sel):
        """Xử lý chọn góc xem TCVN - chỉ vẽ lại biểu đồ N-M."""
        try:
            if sel.startswith("α"):
                self._tcvn_nm_view_angle = None
            else:
                self._tcvn_nm_view_angle = float(sel.replace("°", ""))
            ax = getattr(self, "_nm_ax", None)
            canvas = getattr(self, "_nm_canvas", None)
            draw_fn = getattr(self, "_nm_draw_fn", None)
            if ax is not None and draw_fn is not None:
                ax.clear()
                draw_fn(ax)
                if canvas:
                    canvas.draw()
        except Exception as e:
            pass

    def _redraw_old(self):
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
            # Chỉ hiện nửa có tải (Mα >= 0, N >= 0) — giữ khi đổi góc xem
            ax.set_xlim(left=0)
            ax.set_ylim(bottom=0)

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
        self._sum_inner.rowconfigure(0, weight=0)
        self._sum_inner.rowconfigure(1, weight=1)

        # ===== Ô trên-phải: vùng nén tiết diện + thẻ thống kê =====
        f_tl = tk.Frame(self._sum_inner, bg="white", highlightbackground="#D1D5DB",
                        highlightthickness=1)
        f_tl.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        if getattr(self, "_show_compression", None) is None:
            self._show_compression = tk.BooleanVar(value=True)
        _hdr = tk.Frame(f_tl, bg="white")
        _hdr.pack(fill=tk.X, pady=(2, 2))
        tk.Label(_hdr, text="MẶT CẮT TIẾT DIỆN",
                 font=("", 11, "bold"), bg="white").pack(side=tk.TOP, fill=tk.X)
        tk.Checkbutton(_hdr, text="Hiển thị vùng nén", bg="white",
                       font=("", 8), fg="#374151",
                       variable=self._show_compression,
                       command=lambda: self._redraw_tcvn_section()).place(
                           relx=1.0, rely=0.5, anchor="e", x=-4)
        self.ck_var = tk.StringVar(value="")
        # Bỏ hiển thị tên cấu kiện ở sơ đồ (đã có ở textbox panel trái)
        fig_sec, cv_sec = _new_fig(f_tl, (3.9, 3.1))
        a1 = fig_sec.add_subplot(111)
        from rc_column.pdf_export import draw_compression_zone_ax
        try:
            _tBN = getattr(res, "BN", inp.N)
            _tBx = getattr(res, "Bx", 0)
            _tBy = getattr(res, "By", 0)
            _tNmax = getattr(res, "Nmax", abs(_tBN)*2) if hasattr(res, "Nmax") else abs(_tBN)*2
            # Đường trung hòa chính xác từ fiber model TCVN
            _t_na = None
            try:
                from rc_column.interaction import FiberSection, neutral_axis_at_N
                _t_fs = FiberSection(sec)
                _t_alpha = getattr(res, "alpha_deg", 0) if hasattr(res, "alpha_deg") else 0
                # tính alpha từ Bx, By nếu chưa có
                import math as _m
                if abs(_tBx) + abs(_tBy) > 1e-9:
                    _t_alpha = _m.degrees(_m.atan2(_tBx, _tBy))
                _t_na = neutral_axis_at_N(_t_fs, _tBN, _t_alpha,
                                          getattr(inp, "concrete_model", "3line"))
            except Exception:
                _t_na = None
            _sc_tcvn = bool(self._show_compression.get())
            draw_compression_zone_ax(a1, sec, N_kN=_tBN, M2_kNm=_tBx, M3_kNm=_tBy,
                                     Nmax_kN=_tNmax, na_info=_t_na,
                                     show_compression=_sc_tcvn)
            # Lưu data để checkbox vẽ lại
            self._tcvn_sec_data = (sec, _tBN, _tBx, _tBy, _tNmax, _t_na)
        except Exception:
            draw_section_ax(a1, sec, show_stats=False, dot_scale=1.5)
        fig_sec.tight_layout()
        cv_sec.draw()
        self._sec_fig, self._sec_canvas, self._sec_ax = fig_sec, cv_sec, a1
        self._sec_card_vars = self._build_section_cards(f_tl, sec, inp)

        # ===== Ô trên-trái: bảng thông số tính toán =====
        f_tr = tk.Frame(self._sum_inner, bg="white",
                        highlightbackground="#D1D5DB", highlightcolor="#D1D5DB",
                        highlightthickness=1, takefocus=0)
        f_tr.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._build_param_table(f_tr, inp, res)

        # ===== Ô dưới-trái: header + biểu đồ N-M =====
        f_bl = tk.Frame(self._sum_inner, bg="white",
                        highlightbackground="#D1D5DB", highlightcolor="#D1D5DB",
                        highlightthickness=1, takefocus=0)
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
        f_br = tk.Frame(self._sum_inner, bg="white",
                        highlightbackground="#D1D5DB", highlightcolor="#D1D5DB",
                        highlightthickness=1, takefocus=0)
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
        _tfull = getattr(self, '_tcvn_full', {}) or {}
        self._build_stirrup_summary(f_sw, inp, res, _tfull)
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
