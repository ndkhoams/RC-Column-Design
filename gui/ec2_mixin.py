"""Các method tính toán và hiển thị theo EC2 (EN 1992-1-1)."""



import tkinter as tk

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import matplotlib.patches as mpatches
    HAS_MPL = True
except Exception:
    HAS_MPL = False

import tkinter as tk
from tkinter import ttk, messagebox
import math
from rc_column.checker import ColumnInput, build_section, check_column
from rc_column.report import generate_report, generate_report_sections
from rc_column.materials import CONCRETE_GRADES, STEEL_GRADES
from rc_column.sections import clear_spacing, bar_area
from rc_column.stability import BOUNDARY_NAMES, LongTermLoads
from rc_column.lang import T
class Ec2Mixin:
    """Các method tính toán và hiển thị theo EC2 (EN 1992-1-1)."""

    def is_ec2(self):
        return self.cb_code.get().startswith("EC2")

    def _ec2_calculate_full(self, sec, conc, steel, inp, N, M2, M3, Q2, Q3,
                              method="stiffness", fck=30.0, fyk_sw=500.0):
        """Tính toán đầy đủ EC2 cho 1 tổ hợp nội lực. Trả về dict kết quả hoàn chỉnh.

        NGUYÊN TẮC: Tính 1 lần ở đây, các nơi khác (tab, PDF) chỉ đọc hiển thị.

        Dict trả về gồm:
        - N, M2_orig, M3_orig, Q2, Q3, V2, V3: nội lực đầu vào
        - l0_2, l0_3: chiều dài tính toán (m)
        - lambda_2, lambda_3: độ mảnh
        - MEd2, MEd3: mô men thiết kế đã gồm bậc 2
        - dm: dict từ ec2_design_moment (đầy đủ chi tiết)
        - dc, fs, ok: từ check_column_ec2
        - N_Rd_max: từ check_column_ec2
        - shear2, shear3: dict từ ec2_shear_check
        - sec, conc, steel, method: objects để vẽ biểu đồ/PDF
        """
        from rc_column.ec2_checker import (ec2_design_moment, check_column_ec2,
                                           ec2_shear_check, ec2_balanced_point)
        from rc_column.sections import bar_area
        from rc_column.stability import effective_length
        import math

        res = {
            "N": N, "M2_orig": M2, "M3_orig": M3,
            "Q2": Q2, "Q3": Q3, "V2": abs(Q2), "V3": abs(Q3),
            "sec": sec, "conc": conc, "steel": steel, "method": method,
        }

        # 1. Hình học theo từng phương
        cx, cy = sec.cx, sec.cy  # t3 (ngang), t2 (đứng)
        Ac = sec.gross_area
        As = sec.steel_area
        try:
            l0_2 = effective_length(inp.Lx, inp.top_x, inp.bottom_x,
                                    inp.psi_x) * 1000.0  # mm
            l0_3 = effective_length(inp.Ly, inp.top_y, inp.bottom_y,
                                    inp.psi_y) * 1000.0
        except Exception:
            l0_2 = l0_3 = (inp.Lx or 4.0) * 1000.0
        res["l0_2"] = l0_2 / 1000.0
        res["l0_3"] = l0_3 / 1000.0

        # Ic mỗi phương
        geom = {}
        for lbl, h_dim, Ic in (("dir2", cy, cx * cy**3 / 12.0),
                               ("dir3", cx, cy * cx**3 / 12.0)):
            geom[lbl] = {"h": h_dim, "Ic": Ic,
                         "i": math.sqrt(Ic / Ac) if Ac > 0 else h_dim,
                         "l0": l0_2 if lbl == "dir2" else l0_3}
        res["lambda_2"] = (l0_2 / geom["dir2"]["i"]) if geom["dir2"]["i"] > 0 else 0
        res["lambda_3"] = (l0_3 / geom["dir3"]["i"]) if geom["dir3"]["i"] > 0 else 0

        # n_bal cho phương pháp độ cong
        n_bal = 0.0
        if method == "curvature":
            try:
                Nb, _Mb = ec2_balanced_point(sec, conc, steel, 0.0)
                n_bal = Nb / (conc.fcd * Ac / 1000.0) if Ac > 0 else 0.0
            except Exception:
                n_bal = 0.0
        res["n_bal"] = n_bal

        # 2. Tính Is từ vị trí thép (chính xác, không hardcode 0)
        _Is2 = _Is3 = 0.0
        try:
            _bars = getattr(sec, 'rebars', None) or getattr(sec, 'bars', None) or []
            _cx = getattr(sec, 'cx', 0) / 2
            _cy = getattr(sec, 'cy', 0) / 2
            for _b in _bars:
                _d = getattr(_b, 'dia', 0) or 0
                _a = getattr(_b, 'area', 0) or (math.pi * _d**2 / 4)
                _x = getattr(_b, 'x', 0) or 0
                _y = getattr(_b, 'y', 0) or 0
                _Is2 += _a * (_y - _cy)**2
                _Is3 += _a * (_x - _cx)**2
        except Exception:
            pass
        res["Is2"] = _Is2
        res["Is3"] = _Is3

        # 3. Mô men thiết kế mỗi phương (đã gồm sai lệch, emin, bậc 2)
        dm = {}
        try:
            for lbl, Mdir in (("dir2", M2), ("dir3", M3)):
                g = geom[lbl]
                _Is = _Is2 if lbl == "dir2" else _Is3
                dm[lbl] = ec2_design_moment(
                    NEd_kN=N, M_top_kNm=abs(Mdir),
                    M_bot_kNm=abs(Mdir), l0_mm=g["l0"], i_mm=g["i"],
                    h_mm=g["h"], Ac_mm2=Ac, As_mm2=As,
                    fcd_MPa=conc.fcd, fyd_MPa=steel.fyd,
                    Ecm_MPa=conc.Ecm, Ic_mm4=g["Ic"], Is_mm4=_Is,
                    Es_MPa=steel.Es, fck_MPa=fck,
                    unbraced=False, method=method,
                    d_mm=max(g["h"] - inp.cover - getattr(inp, "sw_dia", 10) - 12.0, 0.5 * g["h"]),
                    eps_yd=steel.eps_yd, n_bal=n_bal,
                    const_moment=True)
        except Exception as ex:
            res.update({"dc": float("nan"), "ok": False, "error": str(ex)})
            return res

        MEd2 = dm["dir2"]["MEd"]
        MEd3 = dm["dir3"]["MEd"]
        res["MEd2"] = MEd2
        res["MEd3"] = MEd3
        res["dm"] = dm
        # Thêm l0/lambda vào dm để tương thích với code cũ
        dm["l0_2"] = l0_2 / 1000.0
        dm["l0_3"] = l0_3 / 1000.0
        dm["lambda_2"] = res["lambda_2"]
        dm["lambda_3"] = res["lambda_3"]

        # 4. P-M-M với mô men thiết kế
        try:
            ec2_res = check_column_ec2(sec, conc, steel, N_kN=N,
                                       M2_kNm=MEd2, M3_kNm=MEd3)
            res.update(ec2_res)
            res["M2_mag"] = MEd2
            res["M3_mag"] = MEd3
            # Tính alpha 1 lần từ M thiết kế (dùng chung)
            import math as _math
            _alpha = _math.degrees(_math.atan2(MEd2, MEd3)) if abs(MEd2)+abs(MEd3) > 1e-9 else 0.0
            _Malpha = _math.hypot(MEd2, MEd3)
            res["alpha_deg"] = _alpha
            res["Malpha"] = _Malpha
        except Exception as ex:
            res.update({"dc": float("nan"), "ok": False, "error": str(ex)})

        # 5. Cắt mỗi phương (EC2 6.2)
        # Asw/s = Σ(Asw,i/si) cho đai bao + đai giữa (nếu khác spacing)
        try:
            sw_dia = getattr(inp, "sw_dia", 8.0) or 8.0
            sw_s = getattr(inp, "sw_spacing", 200.0) or 200.0
            sw_legs = getattr(inp, "sw_legs", 2) or 2
            Asw_outer = sw_legs * bar_area(sw_dia)
            Asw_s_outer = Asw_outer / sw_s if sw_s > 0 else 0.0
            sw_txt_base = f"{sw_legs:.0f}φ{sw_dia:.0f} a{sw_s:.0f}"
            def _asw_params(mdia, ms, mlegs):
                """Trả về (Asw_total, Asw_s_total, sw_txt)."""
                Atot = Asw_outer
                a_s = Asw_s_outer
                txt = sw_txt_base
                try:
                    md = float(mdia or 0); ss = float(ms or 0); ml = int(mlegs or 0)
                    if md > 0 and ss > 0 and ml > 0:
                        Am = ml * bar_area(md)
                        Atot += Am
                        a_s += Am / ss
                        txt += f" + {ml:.0f}φ{md:.0f} a{ss:.0f}"
                except Exception:
                    pass
                return Atot, a_s, txt
            # dir2 dùng đai giữa t2, dir3 dùng đai giữa t3
            Asw2, Asw_s2, txt2 = _asw_params(getattr(inp, "swm2_dia", 0),
                                             getattr(inp, "swm2_spacing", 0),
                                             getattr(inp, "swm2_legs", 0))
            Asw3, Asw_s3, txt3 = _asw_params(getattr(inp, "swm3_dia", 0),
                                             getattr(inp, "swm3_spacing", 0),
                                             getattr(inp, "swm3_legs", 0))
            fyd_sw = fyk_sw / 1.15
            dia_max = max((r.dia for r in sec.rebars), default=20.0)
            Asl = As / 2.0
            shear = {}
            for Vu, lbl, bw, h_dim, Asw_s, Atot, txt in (
                    (abs(Q2), "dir2", cy, cx, Asw_s2, Asw2, txt2),
                    (abs(Q3), "dir3", cx, cy, Asw_s3, Asw3, txt3)):
                d = h_dim - inp.cover - sw_dia - dia_max / 2.0
                shear[lbl] = ec2_shear_check(
                    bw_mm=bw, d_mm=max(d, 0.5 * h_dim), Ac_mm2=Ac,
                    fck_MPa=fck, NEd_kN=max(N, 0.0), VEd_kN=Vu,
                    Asl_mm2=Asl, fyd_MPa=fyd_sw, Asw_s_mm2mm=Asw_s,
                    theta_deg=45.0)
                shear[lbl]["bw"] = bw
                shear[lbl]["d"] = d
                shear[lbl]["VEd"] = Vu
                shear[lbl]["Asw"] = Atot
                shear[lbl]["sw_txt"] = txt
            res["shear2"] = shear.get("dir2", {})
            res["shear3"] = shear.get("dir3", {})
            res["shear"] = shear
        except Exception:
            res["shear2"] = {}
            res["shear3"] = {}
            res["shear"] = {}

        return res

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
        # TÍNH 1 LẦN bằng hàm chung (nguyên tắc: tính 1 lần, hiển thị nhiều nơi)
        _full = self._ec2_calculate_full(
            sec, conc, steel, inp,
            N=inp.N, M2=inp.Mx, M3=inp.My, Q2=inp.Q2, Q3=inp.Q3,
            method=method, fck=fck, fyk_sw=fyk_sw)
        # Kiểm tra lỗi tính toán
        if _full.get("error"):
            messagebox.showerror("Lỗi EC2", _full["error"])
            return
        # Lưu full result để tab/PDF chỉ đọc hiển thị (không tính lại)
        self._ec2_full = _full
        # Tương thích ngược: gán các biến cũ từ full dict
        ec2_res = _full
        dm = _full.get("dm", {})
        shear_res = _full.get("shear")
        MEd2 = _full.get("MEd2", 0)
        MEd3 = _full.get("MEd3", 0)
        l0_2 = _full.get("l0_2", 0) * 1000.0
        l0_3 = _full.get("l0_3", 0) * 1000.0
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
        # Lưu gọn MEd + l0 cho chế độ ETABS / PDF
        self._ec2_dm = {"MEd2": MEd2, "MEd3": MEd3,
                        "l0_2": l0_2 / 1000.0, "l0_3": l0_3 / 1000.0}
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
        self._update_ck()

    def _get_ec2_param_rows(self, inp, ec2_res, slend):
        """Trả về rows data cho bảng thông số EC2."""
        import math
        M2m = ec2_res.get("M2_mag", inp.Mx)
        M3m = ec2_res.get("M3_mag", inp.My)
        alpha_deg = (ec2_res["alpha_deg"] if isinstance(ec2_res, dict) and "alpha_deg" in ec2_res
                     else math.degrees(math.atan2(M2m, M3m)) if abs(M2m) + abs(M3m) > 1e-9 else 0.0)
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
        conc = self._ec2_conc
        rows = [
            ("NEd", "Lực dọc thiết kế", f"{inp.N:+.1f} kN"),
            ("MEd2", "Mô men thiết kế phương 2 (gồm bậc 2)", f"{M2m:.1f} kN×m"),
            ("MEd3", "Mô men thiết kế phương 3 (gồm bậc 2)", f"{M3m:.1f} kN×m"),
            ("α", "Góc tác dụng mô men", f"{alpha_deg:.1f} °"),
            ("Mα", "Mô men tổng hợp", f"{Ma:.1f} kN×m"),
            ("fck", "Cường độ nén đặc trưng", f"{conc.fck:g} MPa"),
            ("fcd", "Cường độ nén tính toán (αcc×fck/γc)", f"{conc.fcd:.2f} MPa"),
            ("Ecm", "Mô đun đàn hồi cát tuyến", f"{conc.Ecm:.0f} MPa"),
            ("λ2", "Độ mảnh phương 2 (EC2 5.8.3)", _sl("dir2")),
            ("λ3", "Độ mảnh phương 3 (EC2 5.8.3)", _sl("dir3")),
            ("e2", "Độ lệch tâm phương 2 (MEd2/NEd)",
             f"{abs(M2m/inp.N*1000):.1f} mm" if abs(inp.N) > 1e-9 else "—"),
            ("e3", "Độ lệch tâm phương 3 (MEd3/NEd)",
             f"{abs(M3m/inp.N*1000):.1f} mm" if abs(inp.N) > 1e-9 else "—"),
            ("M2_0", "Mô men bậc 1 phương 2", f"{inp.Mx:.1f} kN×m"),
            ("M3_0", "Mô men bậc 1 phương 3", f"{inp.My:.1f} kN×m"),
            ("N_Rd,max", "Nén đúng tâm lớn nhất", f"{ec2_res.get('N_Rd_max', 0):.1f} kN"),
        ]
        ok = ec2_res["ok"]
        fs_txt = (f"{ec2_res['fs']:.2f}" if math.isfinite(ec2_res.get("fs", 0)) else "∞")
        ok_txt = "ĐẠT" if ok else "KHÔNG ĐẠT"
        dc_row = ("D/C", "Tỷ số sử dụng khả năng chịu lực",
                  f"{ec2_res['dc']:.3f} (FS = {fs_txt})  {ok_txt}", ok)
        return rows, dc_row, alpha_deg, Ma

    def _show_ec2_summary(self):
        """Tab Kết quả tính toán cho EC2 - dùng unified renderer."""
        if not HAS_MPL:
            return
        from gui.result_renderer import render_result_tab
        from rc_column.ec2_chart_draw import draw_ec2_nm_alpha_ax, draw_ec2_m2m3_ax

        sec = self._ec2_sec
        inp = self._ec2_inp
        ec2_res = self._ec2_res
        conc = self._ec2_conc
        steel = self._ec2_steel
        slend = getattr(self, "_ec2_slend", None)

        param_rows, dc_row, alpha_deg, Ma = self._get_ec2_param_rows(inp, ec2_res, slend)

        vals = self._section_card_values(sec)
        section_cards = {"n": vals["n"], "as": vals["as"], "ab": vals["ab"], "mu": vals["mu"]}

        def _draw_nm(ax):
            _M2m = ec2_res.get("M2_mag", inp.Mx)
            _M3m = ec2_res.get("M3_mag", inp.My)
            _view_angle = getattr(self, "_ec2_nm_view_angle", None)
            if _view_angle is not None:
                import math
                _Ma = math.hypot(_M2m, _M3m)
                _rad = math.radians(_view_angle)
                _M2m = _Ma * math.sin(_rad)
                _M3m = _Ma * math.cos(_rad)
            draw_ec2_nm_alpha_ax(ax, sec, conc, steel, ec2_res, inp.N, _M2m, _M3m)

        def _draw_m2m3(ax):
            draw_ec2_m2m3_ax(ax, sec, conc, steel, ec2_res, inp.N, inp.Mx, inp.My)

        import math
        _ok = ec2_res['ok']
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
        _M2m = ec2_res.get("M2_mag", inp.Mx)
        _M3m = ec2_res.get("M3_mag", inp.My)
        _BN = ec2_res.get("BN", 0)
        _Bx = ec2_res.get("Bx", 0)
        _By = ec2_res.get("By", 0)
        _Mb = math.hypot(_Bx, _By)
        notes = [
            (f"● Đường bao kiểm tra: N-Mα (α = {alpha_deg:.1f}°) — EC2 (EN 1992-1-1)", "#059669"),
            (f"● A (điểm tải){_combo_txt}:  N = {inp.N:+.1f} kN,  Mα = {Ma:.1f} kN×m  (MEd2 = {_M2m:.1f}, MEd3 = {_M3m:.1f})", "#2563EB"),
            (f"◆ B (điểm giới hạn):  N = {_BN:+.1f} kN,  Mα,u = {_Mb:.1f} kN×m  (M2u = {_Bx:.1f}, M3u = {_By:.1f})", "#EA580C"),
        ]

        config = {
            "std_title": "(EC2 EN 1992-1-1)",
            "param_rows": param_rows,
            "dc_row": dc_row,
            "section": sec,
            "section_cards": section_cards,
            "draw_nm": _draw_nm,
            "draw_m2m3": _draw_m2m3,
            "nm_title": "Biểu đồ tương tác N-Mα",
            "nm_alpha_text": f"α = {alpha_deg:.1f}°",
            "m2m3_title": "Mặt cắt M2-M3",
            "m2m3_n_text": f"N = {inp.N:+.1f} kN",
            "notes_nm": notes,
            "on_nm_angle_change": lambda sel: self._on_ec2_angle_unified(sel),
            "shear_builder": lambda parent: self._build_ec2_shear_summary(
                parent, inp, sec, conc, steel, getattr(self, '_ec2_full', {}) or {}),
        }
        render_result_tab(self, config)
        self._update_ck()

    def _on_ec2_angle_unified(self, sel):
        """Xử lý chọn góc xem EC2 - chỉ vẽ lại biểu đồ N-M."""
        try:
            _is_3d = getattr(self, "_ec2_is_3d", False)
            if sel == "3D":
                if _is_3d:
                    return
                self._draw_3d_ec2()
                self._ec2_is_3d = True
                return
            if sel.startswith("α"):
                self._ec2_nm_view_angle = None
            else:
                self._ec2_nm_view_angle = float(sel.replace("°", ""))
            if _is_3d:
                self._ec2_is_3d = False
                self._restore_2d_ec2()
            else:
                ax = getattr(self, "_nm_ax", None)
                canvas = getattr(self, "_nm_canvas", None)
                draw_fn = getattr(self, "_nm_draw_fn", None)
                if ax is not None and draw_fn is not None:
                    ax.clear()
                    draw_fn(ax)
                    if canvas:
                        canvas.draw()
        except Exception as e:
            print(f"[EC2] Lỗi đổi góc xem: {e}")

    def _restore_2d_ec2(self):
        """Khôi phục biểu đồ 2D EC2 sau khi xem 3D."""
        try:
            import tkinter as tk
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            parent = getattr(self, "_nm_parent", None)
            draw_fn = getattr(self, "_nm_draw_fn", None)
            if parent is None or draw_fn is None:
                self._show_ec2_summary()
                return
            _old_cv = getattr(self, "_nm_canvas", None)
            if _old_cv:
                try:
                    _old_cv.get_tk_widget().destroy()
                except Exception:
                    pass
            for w in parent.winfo_children():
                if w.winfo_class() == "Canvas":
                    w.destroy()
            fig = Figure(figsize=(5.2, 3.9), dpi=100)
            cv = FigureCanvasTkAgg(fig, master=parent)
            cw = cv.get_tk_widget()
            cw.configure(highlightthickness=0, takefocus=0)
            cw.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            ax = fig.add_subplot(111)
            draw_fn(ax)
            fig.tight_layout()
            cv.draw()
            self._nm_ax = ax
            self._nm_canvas = cv
        except Exception as e:
            print(f"[EC2] Lỗi khôi phục 2D: {e}")
            self._show_ec2_summary()

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

    def _build_ec2_shear_summary(self, parent, inp, sec, conc, steel, full_res=None):
        """Bảng kiểm tra khả năng chịu cắt EC2: Phương V2 | Phương V3.
        CHỈ hiển thị từ full_res (đã tính bởi _ec2_calculate_full), KHÔNG tính lại."""
        try:
            # Ưu tiên full_res, fallback về _ec2_shear (tương thích cũ)
            _fr = full_res or {}
            shear = _fr.get("shear") or getattr(self, "_ec2_shear", None) or {}
            cols = {}
            for lbl, key in (("2", "dir2"), ("3", "dir3")):
                sr = shear.get(key, {}) or {}
                _combo = sr.get("combo_info", "")
                cols[lbl] = dict(
                    VEd=sr.get("VEd", 0.0),
                    bw=sr.get("bw", 0.0),
                    d=sr.get("d", 0.0),
                    Asw=sr.get("Asw", 0.0),
                    sw_txt=sr.get("sw_txt", ""),
                    VRdc=sr.get("VRd_c_kN", 0.0),
                    VRdmax=sr.get("VRd_max_kN", 0.0),
                    VRds=sr.get("VRd_s_kN", 0.0),
                    VRd=sr.get("VRd_kN", 0.0),
                    Asws=sr.get("Asw_s_req", 0.0),
                    ok=bool(sr.get("ok", False)),
                    combo_info=_combo,
                )

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
            def _ved_txt(cc):
                return f"{cc['VEd']:.1f} kN"
            def _asws_txt(v):
                if v is None or (isinstance(v, float) and (v != v or v == float("inf"))):
                    return "—"
                return f"{v:.3f} mm²/mm"
            rows = [
                ("Thép đai bố trí",
                 cols['2']['sw_txt'], cols['3']['sw_txt']),
                ("Lực cắt tính toán, VEd",
                 _ved_txt(cols['2']), _ved_txt(cols['3'])),
                ("Kích thước tiết diện, bw × d",
                 f"{cols['2']['bw']:.0f} × {cols['2']['d']:.0f} mm",
                 f"{cols['3']['bw']:.0f} × {cols['3']['d']:.0f} mm"),
                ("Asw = n × φ",
                 f"{cols['2']['Asw']:.0f} mm²", f"{cols['3']['Asw']:.0f} mm²"),
                ("VRd,c = [CRd,c×k×(100ρl×fck)⅓ + k1×σcp]×bw×d",
                 f"{cols['2']['VRdc']:.1f} kN", f"{cols['3']['VRdc']:.1f} kN"),
                ("VRd,max = αcw×bw×z×ν1×fcd/(cotθ+tanθ)",
                 f"{cols['2']['VRdmax']:.1f} kN", f"{cols['3']['VRdmax']:.1f} kN"),
                ("VRd,s = (Asw/s)×z×fywd×cotθ (θ=45°)",
                 f"{cols['2']['VRds']:.1f} kN", f"{cols['3']['VRds']:.1f} kN"),
                ("Asw/s yêu cầu",
                 _asws_txt(cols['2']['Asws']), _asws_txt(cols['3']['Asws'])),
                ("Kết luận",
                 "ĐẠT" if cols['2']['ok'] else "KHÔNG ĐẠT",
                 "ĐẠT" if cols['3']['ok'] else "KHÔNG ĐẠT"),
            ]
            for i, (a, b, cc) in enumerate(rows):
                bg = "#F9FAFB" if i % 2 else "white"
                is_kl = (a == "Kết luận")
                for j, t in enumerate((a, b, cc)):
                    fw = ("", 9)
                    fg = "#1F2937"
                    if is_kl and j > 0:
                        fg = "#065F46" if t == "ĐẠT" else "#991B1B"
                        fw = ("", 9, "bold")
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
        tree.column("sym", width=84, anchor="center", stretch=False)
        tree.column("desc", width=200, anchor="w")
        tree.column("val", width=220, anchor="e", stretch=False)
        tree.tag_configure("odd", background="#F9FAFB")
        dc_bg = "#D1FAE5" if ec2_res["ok"] else "#FEE2E2"
        dc_fg = "#065F46" if ec2_res["ok"] else "#991B1B"
        tree.tag_configure("dc", background=dc_bg, foreground=dc_fg)
        M2m = ec2_res.get("M2_mag", inp.Mx)
        M3m = ec2_res.get("M3_mag", inp.My)
        alpha_deg = (ec2_res["alpha_deg"] if "ec2_res" in locals() and isinstance(ec2_res, dict) and "alpha_deg" in ec2_res else math.degrees(math.atan2(M2m, M3m)) \
            if abs(M2m) + abs(M3m) > 1e-9 else 0.0)
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
             f"{M2m:.1f} kN×m"),
            ("MEd3", "Mô men thiết kế phương 3 (gồm bậc 2)",
             f"{M3m:.1f} kN×m"),
            ("α", "Góc tác dụng mô men",
             f"{alpha_deg:.1f} °"),
            ("Mα", "Mô men tổng hợp",
             f"{Ma:.1f} kN×m"),
            ("fck", "Cường độ nén đặc trưng",
             f"{conc.fck:g} MPa"),
            ("fcd", "Cường độ nén tính toán (αcc×fck/γc)",
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
             f"{inp.Mx:.1f} kN×m"),
            ("M3_0", "Mô men bậc 1 phương 3",
             f"{inp.My:.1f} kN×m"),
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
        tree.pack(fill=tk.X, expand=False, padx=2, pady=2)

    def _build_ec2_nm_header(self, parent, inp):
        """Header trên biểu đồ N-Mα (EC2)."""
        import math
        M2m = getattr(self, "_ec2_res", {}).get("M2_mag", inp.Mx)
        M3m = getattr(self, "_ec2_res", {}).get("M3_mag", inp.My)
        alpha_deg = (ec2_res["alpha_deg"] if "ec2_res" in locals() and isinstance(ec2_res, dict) and "alpha_deg" in ec2_res else math.degrees(math.atan2(M2m, M3m)) \
            if abs(M2m) + abs(M3m) > 1e-9 else 0.0)
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
        self._ec2_nm_view_angle = None

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

    def _build_ec2_notes(self, parent, inp, ec2_res):
        """3 dòng chú thích dưới biểu đồ EC2."""
        import math
        mono = ("TkFixedFont", 10)
        M2m = ec2_res.get("M2_mag", inp.Mx)
        M3m = ec2_res.get("M3_mag", inp.My)
        Ma = math.hypot(M2m, M3m)
        Mb = math.hypot(ec2_res["Bx"], ec2_res["By"])
        alpha_deg = (ec2_res["alpha_deg"] if "ec2_res" in locals() and isinstance(ec2_res, dict) and "alpha_deg" in ec2_res else math.degrees(math.atan2(M2m, M3m)) \
            if abs(M2m) + abs(M3m) > 1e-9 else 0.0)
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
                      f"Mα = {Ma:.1f} kN×m  "
                      f"(MEd2 = {M2m:.1f}, MEd3 = {M3m:.1f})",
                 font=mono, fg="#2563EB").pack(anchor="w", pady=1)
        tk.Label(box, bg="white",
                 text=f"◆ B (điểm giới hạn):  "
                      f"N = {ec2_res['BN']:+.1f} kN,  Mα,u = {Mb:.1f} kN×m  "
                      f"(M2u = {ec2_res['Bx']:.1f}, M3u = {ec2_res['By']:.1f})",
                 font=mono, fg="#EA580C").pack(anchor="w", pady=1)

    def _create_ec2_detail_figs(self):
        """Tạo 2 fig biểu đồ cho tab Chi tiết từ data tính toán chung."""
        try:
            from matplotlib.figure import Figure
            from rc_column.ec2_chart_draw import draw_ec2_nm_alpha_ax, draw_ec2_m2m3_ax
            sec = getattr(self, "_ec2_sec", None)
            inp = getattr(self, "_ec2_inp", None)
            ec2_res = getattr(self, "_ec2_res", None)
            conc = getattr(self, "_ec2_conc", None)
            steel = getattr(self, "_ec2_steel", None)
            if not all([sec, inp, ec2_res, conc, steel]):
                return (None, None)
            M2m = ec2_res.get("M2_mag", inp.Mx)
            M3m = ec2_res.get("M3_mag", inp.My)
            fig1 = Figure(figsize=(5.2, 3.9), dpi=100)
            ax1 = fig1.add_subplot(111)
            draw_ec2_nm_alpha_ax(ax1, sec, conc, steel, ec2_res, inp.N, M2m, M3m)
            fig1.tight_layout()
            fig2 = Figure(figsize=(5.2, 3.9), dpi=100)
            ax2 = fig2.add_subplot(111)
            draw_ec2_m2m3_ax(ax2, sec, conc, steel, ec2_res, inp.N, inp.Mx, inp.My)
            fig2.tight_layout()
            return (fig1, fig2)
        except Exception as e:
            print(f"[EC2] Lỗi tạo fig detail: {e}")
            return (None, None)

    def _render_ec2_report(self, sections):
        """Hiển thị thuyết minh EC2 trong tab Chi tiết tính toán (dùng chung renderer TCVN)."""
        for w in self._calc_inner.winfo_children():
            w.destroy()
        from rc_column.report_widgets import render_report_sections
        # Plot lại từ data (không dùng fig của result tab)
        _figs = self._create_ec2_detail_figs()
        render_report_sections(self._calc_inner, sections, chart_figs=_figs)
        self._calc_inner.update_idletasks()
        self._calc_canvas.configure(scrollregion=self._calc_canvas.bbox("all"))
        self._bind_wheel(self._calc_inner, self._calc_canvas)
        try:
            self._calc_canvas.yview_moveto(0)
        except Exception:
            pass

    def _draw_3d_ec2(self):
        """Vẽ biểu đồ tương tác 3D cho EC2."""
        try:
            from mpl_toolkits.mplot3d import Axes3D  # noqa
            import numpy as np
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            # Tạo figure/canvas mới hoàn toàn để tránh canvas bị lock
            try:
                _old = getattr(self, '_nm_canvas', None) or getattr(self, '_ec2_nm_cv_ref', None)
                _par = _old.get_tk_widget().master if _old else None
                if _old:
                    _old.get_tk_widget().destroy()
            except Exception:
                _par = None
            if _par is not None:
                _fig = Figure(figsize=(5.2, 3.9), dpi=100)
                _cv = FigureCanvasTkAgg(_fig, master=_par)
                _w = _cv.get_tk_widget()
                try:
                    _w.configure(highlightthickness=0, takefocus=0,
                                 highlightbackground="white",
                                 highlightcolor="white", borderwidth=0)
                except Exception:
                    pass
                _w.pack(fill=tk.BOTH, expand=True)
                self._ec2_nm_fig = _fig
                self._ec2_nm_cv_ref = _cv
            fig = self._ec2_nm_fig
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
            ax.set_xlabel('M2 (kN×m)')
            ax.set_ylabel('M3 (kN×m)')
            ax.set_zlabel('N (kN)')
            fig.tight_layout()
            self._ec2_nm_cv_ref.draw()
            self._ec2_nm_ax_ref = None
        except Exception as ex:
            print(f"Lỗi vẽ 3D EC2: {ex}")
            import traceback
            traceback.print_exc()

