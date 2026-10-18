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
from rc_column.report import generate_report, generate_report_sections
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
        from rc_column.stirrup import StirrupInput, check_stirrup, check_shear
        from rc_column.sections import bar_area
        from rc_column.materials import CONCRETE_GRADES, STEEL_GRADES, ConcreteMaterial
        _shear_cols = {}
        try:
            _stir_in = StirrupInput(dia=inp.sw_dia, spacing=inp.sw_spacing, legs=inp.sw_legs)
            _conc_mat = ConcreteMaterial(CONCRETE_GRADES[inp.concrete_grade], inp.gamma_b)
            _swg = STEEL_GRADES.get(inp.sw_steel_grade)
            _sr = check_stirrup(sec, _stir_in, inp.cover)
            for _Q, _lbl, _b_w, _h_dim, _mdia, _ms, _mlegs in (
                    (inp.Q2, "2", inp.cy, inp.cx, inp.swm2_dia, inp.swm2_spacing, inp.swm2_legs),
                    (inp.Q3, "3", inp.cx, inp.cy, inp.swm3_dia, inp.swm3_spacing, inp.swm3_legs)):
                _h0 = _h_dim - inp.cover - inp.sw_dia - 12
                # Đai bao ngoài
                _Asw_outer = _stir_in.legs * bar_area(_stir_in.dia)
                _s_outer = _stir_in.spacing
                _Rsw = _swg.Rsw if _swg else 0
                # qsw = Σ(Rsw×Asw,i/si) theo TCVN 5574:2018 (8.1.3)
                _qsw = _Rsw * _Asw_outer / _s_outer if _s_outer > 0 else 0
                _Asw = _Asw_outer
                _sw_txt = f"{_stir_in.legs:.0f}φ{_stir_in.dia:.0f} a{_stir_in.spacing:.0f}"
                # Cộng đai giữa (nếu có) - tính đúng theo spacing riêng
                if _mdia and _ms:
                    try:
                        _mdia_f = float(_mdia)
                        _ms_f = float(_ms)
                        _mlegs_i = int(_mlegs)
                        if _mdia_f > 0 and _ms_f > 0 and _mlegs_i > 0:
                            _Asw_mid = _mlegs_i * bar_area(_mdia_f)
                            _Asw += _Asw_mid
                            _qsw += _Rsw * _Asw_mid / _ms_f
                            _sw_txt += f" + {_mlegs_i}φ{_mdia_f:.0f} a{_ms_f:.0f}"
                    except: pass
                # Bước đai tương đương để check_shear tính đúng qsw
                _s_eff = _Rsw * _Asw / _qsw if _qsw > 0 else _s_outer
                _sh = check_shear(_Q, _b_w, max(_h0, 1), _conc_mat.Rb, _conc_mat.Rbt,
                                 _Asw, _Rsw, _s_eff)
                _shear_cols[_lbl] = dict(Q=_Q, b=_b_w, h0=_h0, Asw=_Asw, qsw=_qsw,
                                        sh=_sh, sw_txt=_sw_txt, s_eff=_s_eff)
        except Exception:
            pass

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
            # Fallback: tính lại nếu không có precalc (giữ để không vỡ UI)
            from rc_column.stirrup import (StirrupInput, check_stirrup, check_shear)
            from rc_column.sections import bar_area
            from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES, ConcreteMaterial)
            try:
                stir_in = StirrupInput(dia=inp.sw_dia, spacing=inp.sw_spacing, legs=inp.sw_legs)
                conc = ConcreteMaterial(CONCRETE_GRADES[inp.concrete_grade], inp.gamma_b)
                swg = STEEL_GRADES.get(inp.sw_steel_grade)
                sr = check_stirrup(self._last_sec, stir_in, inp.cover)
                cols = {}
                for Q, lbl, b_w, h_dim, mdia, ms, mlegs in (
                        (inp.Q2, "2", inp.cy, inp.cx, inp.swm2_dia, inp.swm2_spacing, inp.swm2_legs),
                        (inp.Q3, "3", inp.cx, inp.cy, inp.swm3_dia, inp.swm3_spacing, inp.swm3_legs)):
                    h0 = h_dim - inp.cover - inp.sw_dia - 12
                    Asw = stir_in.legs * bar_area(stir_in.dia)
                    s_eff = stir_in.spacing
                    sw_txt = f"{stir_in.legs:.0f}φ{stir_in.dia:.0f} a{stir_in.spacing:.0f}"
                    if mlegs and mlegs > 0:
                        try:
                            Asw += mlegs * bar_area(float(mdia))
                        except:
                            pass
                    sh = check_shear(Q, b_w, max(h0, 1), conc.Rb, conc.Rbt, Asw, swg.Rsw, s_eff)
                    qsw = swg.Rsw * Asw / s_eff if s_eff > 0 else 0
                    cols[lbl] = dict(Q=Q, b=b_w, h0=h0, Asw=Asw, qsw=qsw, sh=sh, sw_txt=sw_txt, s_eff=s_eff)
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

