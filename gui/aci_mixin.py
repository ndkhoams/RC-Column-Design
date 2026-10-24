"""Các method tính toán và hiển thị theo ACI 318-19."""



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
from rc_column.report import generate_report_sections
from rc_column.materials import CONCRETE_GRADES, STEEL_GRADES
from rc_column.sections import clear_spacing, bar_area
from rc_column.stability import BOUNDARY_NAMES, LongTermLoads
from rc_column.lang import T
class AciMixin:
    """Các method tính toán và hiển thị theo ACI 318-19."""

    def is_aci(self):
        return self.cb_code.get().startswith("ACI")

    def _aci_calculate_full(self, sec, conc, steel, inp, N, M2, M3, Q2, Q3,
                              beta_dns=0.6, beta_src="", tied=True, fyt=400.0, fc=21.0):
        """Tính toán đầy đủ ACI cho 1 tổ hợp nội lực. Trả về dict kết quả hoàn chỉnh.

        NGUYÊN TẮC: Tính 1 lần ở đây, các nơi khác (tab, PDF) chỉ đọc hiển thị.

        Dict trả về gồm:
        - N, M2_orig, M3_orig, Q2, Q3: nội lực đầu vào
        - L0_2, L0_3: chiều dài tính toán (m)
        - mm2, mm3: dict từ moment_magnification (đầy đủ)
        - delta2, delta3, M2_mag, M3_mag: hệ số và mô men đã phóng đại
        - beta_dns, beta_src
        - dc, fs, phi, ok, Bx, By, BN: từ check_column_aci
        - N_cap: phi_Pn,max (lấy thẳng từ engine qua check_column_aci)
        - fyt: cường độ thép đai đã dùng cho cắt (để tab/PDF hiển thị đúng)
        - shear2, shear3: dict từ aci_shear_check
        - sec, conc, steel, tied: objects để vẽ biểu đồ/PDF
        """
        from rc_column.aci_checker import (check_column_aci, moment_magnification,
                                          aci_shear_check, sway_magnification)
        from rc_column.stability import effective_length
        import math

        res = {
            "N": N, "M2_orig": M2, "M3_orig": M3, "Q2": Q2, "Q3": Q3,
            "beta_dns": beta_dns, "beta_src": beta_src,
            "sec": sec, "conc": conc, "steel": steel, "tied": tied,
            "fyt": fyt,
        }

        # 1. Độ mảnh & phóng đại mô men (ACI 6.6.4)
        try:
            L0_2 = effective_length(inp.Lx, inp.top_x, inp.bottom_x, inp.psi_x) * 1000
            Ig2 = sec.cx * sec.cy**3 / 12
            mm2 = moment_magnification(Pu_kN=N, M1_kNm=M2, M2_kNm=M2,
                                      lu_mm=L0_2, k=1.0, Ec_MPa=conc.Ec,
                                      Ig_mm4=Ig2, beta_dns=beta_dns)
            L0_3 = effective_length(inp.Ly, inp.top_y, inp.bottom_y, inp.psi_y) * 1000
            Ig3 = sec.cy * sec.cx**3 / 12
            mm3 = moment_magnification(Pu_kN=N, M1_kNm=M3, M2_kNm=M3,
                                      lu_mm=L0_3, k=1.0, Ec_MPa=conc.Ec,
                                      Ig_mm4=Ig3, beta_dns=beta_dns)
            d2 = mm2.get("delta_ns", 1.0)
            d3 = mm3.get("delta_ns", 1.0)
            Mc2 = d2 * M2
            Mc3 = d3 * M3
            res.update({
                "mm2": mm2, "mm3": mm3,
                "delta2": d2, "delta3": d3,
                "M2_mag": Mc2, "M3_mag": Mc3,
                "L0_2": L0_2/1000, "L0_3": L0_3/1000,
            })
            # Plumbing chi de HIEN THI (PDF tom tat, muc chieu dai tinh
            # toan): ti so do manh kLu/r voi k = 1.0, Lu = L0 (mm),
            # r = sqrt(Ig/Ag) — cung dinh nghia PDF chi tiet dang dung.
            # Khong dung trong tinh toan, khong doi ket qua nao.
            _Ag_mm = sec.gross_area
            _r_2 = math.sqrt(Ig2 / _Ag_mm) if _Ag_mm > 0 else 0.0
            _r_3 = math.sqrt(Ig3 / _Ag_mm) if _Ag_mm > 0 else 0.0
            res["klu_r2"] = (L0_2 / _r_2) if _r_2 > 0 else 0.0
            res["klu_r3"] = (L0_3 / _r_3) if _r_3 > 0 else 0.0
            # Tính alpha và Malpha 1 lần từ M đã phóng đại (dùng chung)
            import math as _math
            _alpha = _math.degrees(_math.atan2(Mc2, Mc3)) % 360.0 if abs(Mc2)+abs(Mc3) > 1e-9 else 0.0
            _Malpha = _math.hypot(Mc2, Mc3)
            res["alpha_deg"] = _alpha
            res["Malpha"] = _Malpha
            # Tính alpha và Malpha 1 lần từ M đã phóng đại (dùng chung cho tab/PDF)
            import math as _math
            _alpha = _math.degrees(_math.atan2(Mc2, Mc3)) % 360.0 if abs(Mc2)+abs(Mc3) > 1e-9 else 0.0
            _Malpha = _math.hypot(Mc2, Mc3)
            res["alpha_deg"] = _alpha
            res["Malpha"] = _Malpha
        except Exception:
            Mc2, Mc3 = M2, M3
            res.update({
                "mm2": {}, "mm3": {},
                "delta2": 1.0, "delta3": 1.0,
                "M2_mag": Mc2, "M3_mag": Mc3,
                "L0_2": 0, "L0_3": 0,
                "klu_r2": 0.0, "klu_r3": 0.0,
            })

        # 1b. Sway (luôn Q=0, bỏ qua)
        Qsw = 0.0
        if Qsw > 0:
            sway_res = sway_magnification(Q=Qsw)
            ds = sway_res.get("delta_s", 1.0)
            Mc2 *= ds
            Mc3 *= ds
            res["M2_mag"] = Mc2
            res["M3_mag"] = Mc3

        # 2. P-M-M với mô men đã phóng đại
        try:
            aci_res = check_column_aci(sec, conc, steel, N_kN=N,
                                       M2_kNm=Mc2, M3_kNm=Mc3, tied=tied)
            res.update(aci_res)
        except Exception as ex:
            res.update({"dc": float("nan"), "ok": False, "error": str(ex)})

        # 2b. N_cap (phi_Pn,max): KHÔNG tính lại ở GUI. Bước 2
        # (check_column_aci) đã trả "N_cap" = ACICapacity.N_cap — đúng
        # giá trị engine dùng cho mặt tương tác/D/C: (0.80 tied / 0.85
        # spiral) * phi_c * Po với fy/f'c thật và Ag/Ast thật của tiết
        # diện. Bản cũ tính lại bằng getattr(steel, 'fy_MPa', 400):
        # ACISteel không có thuộc tính fy_MPa nên luôn fallback fy=400
        # → hiển thị sai mọi ca fy != 400 (chưa kể Ag = cx*cy chỉ đúng
        # tiết diện chữ nhật — tròn lệch tới +23% — và hệ số 0.80 cứng
        # sai cho spiral). Chỉ đặt 0.0 khi bước 2 lỗi (không có N_cap).
        if "N_cap" not in res:
            res["N_cap"] = 0.0

        # 3. Cắt 2 phương (dùng đai thật từ inp, không hardcode)
        try:
            Acv = sec.cx * sec.cy
            cover = getattr(inp, 'cover', 40)
            sw_dia = getattr(inp, 'sw_dia', 10) or 10
            sw_legs = getattr(inp, 'sw_legs', 2) or 2
            sw_s = getattr(inp, 'sw_spacing', 200) or 200
            # V2: b=t2(750), d theo t3(500); V3: b=t3(500), d theo t2(750) - khớp hiển thị
            d2_s = sec.cx - cover - sw_dia - 12
            d3_s = sec.cy - cover - sw_dia - 12
            # Av bao ngoài
            Av_outer = sw_legs * math.pi * (sw_dia**2) / 4
            sw_txt_base = f"{sw_legs:.0f}φ{sw_dia:.0f} a{sw_s:.0f}"
            # Tính cho từng phương (đai giữa có thể khác nhau)
            def _av_params(mdia, ms, mlegs):
                """Trả về (Av_total, s_eq, sw_txt) với đai giữa."""
                Av_tot = Av_outer
                # Av/s tương đương = Σ(Av,i/si)
                av_s = Av_outer / sw_s if sw_s > 0 else 0.0
                txt = sw_txt_base
                try:
                    md = float(mdia or 0); ss = float(ms or 0); ml = int(mlegs or 0)
                    if md > 0 and ss > 0 and ml > 0:
                        Av_mid = ml * math.pi * (md**2) / 4
                        Av_tot += Av_mid
                        av_s += Av_mid / ss
                        txt += f" + {ml:.0f}φ{md:.0f} a{ss:.0f}"
                except Exception:
                    pass
                s_eq = Av_tot / av_s if av_s > 0 else sw_s
                return Av_tot, s_eq, txt
            Av2, s2_eq, txt2 = _av_params(getattr(inp, 'swm2_dia', 0),
                                          getattr(inp, 'swm2_spacing', 0),
                                          getattr(inp, 'swm2_legs', 0))
            Av3, s3_eq, txt3 = _av_params(getattr(inp, 'swm3_dia', 0),
                                          getattr(inp, 'swm3_spacing', 0),
                                          getattr(inp, 'swm3_legs', 0))
            try:
                sh2 = aci_shear_check(Acv_mm2=Acv, Ag_mm2=Acv, fc_MPa=fc,
                                     Nu_kN=N, Vu_kN=abs(Q2),
                                     Av_mm2=Av2, fyt_MPa=fyt, s_mm=s2_eq, d_mm=d2_s)
            except Exception:
                sh2 = {}
            try:
                sh3 = aci_shear_check(Acv_mm2=Acv, Ag_mm2=Acv, fc_MPa=fc,
                                     Nu_kN=N, Vu_kN=abs(Q3),
                                     Av_mm2=Av3, fyt_MPa=fyt, s_mm=s3_eq, d_mm=d3_s)
            except Exception:
                sh3 = {}
            res["shear2"] = sh2 or {}
            res["shear3"] = sh3 or {}
            res["shear"] = {"dir2": sh2 or {}, "dir3": sh3 or {}}
            # Lưu thêm thông số hiển thị (để tab/PDF không phải tính lại)
            # b theo quy ước chung như TCVN/EC2: phương 2 -> b = cy (t2),
            # phương 3 -> b = cx (t3); d lấy theo cạnh còn lại.
            res["shear_disp"] = {
                "2": {"b": sec.cy, "d": d2_s, "Av": Av2, "Vu": abs(Q2), "sw_txt": txt2},
                "3": {"b": sec.cx, "d": d3_s, "Av": Av3, "Vu": abs(Q3), "sw_txt": txt3},
            }
        except Exception:
            res["shear2"] = {}
            res["shear3"] = {}
            res["shear"] = {"dir2": {}, "dir3": {}}

        return res

    def _check_aci(self, inp):
        """Kiểm tra cột theo ACI 318-19: P-M-M, độ mảnh, cắt. Vẽ biểu đồ + thuyết minh."""
        from rc_column.aci_materials import ACIConcrete, ACISteel
        from rc_column.aci_checker import (check_column_aci, moment_magnification,
                                          aci_shear_check)
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
        # TÍNH 1 LẦN: gọi hàm tính đầy đủ (không tính lại ở nơi khác)
        # Tính beta_dns từ TX_* tại ĐÚNG vị trí của tổ hợp đang xét
        # (nhất quán đường batch: map (story, column, station, tổ hợp gốc)).
        # Tổ hợp nhập tay không có story/station/tên: định danh bằng bộ nội
        # lực (N, M2, M3) khớp với 1 dòng trong bảng ETABS; không khớp được
        # thì dùng mặc định 0.6 như batch khi thiếu TX_* tại vị trí.
        _beta = 0.6
        _beta_src = ""
        try:
            _forces = getattr(self, 'etabs_forces', []) or []
            _dns_map = {}
            for _f in _forces:
                _cn = _f.case.strip()
                if _cn.startswith("TX_"):
                    _key = (_f.story.strip(), _f.column.strip(),
                            round(_f.station, 3), _cn[3:])
                    _dns_map[_key] = _f.N
            _n_sus = None
            if _dns_map and inp.N > 1e-9:
                _mres = math.hypot(inp.Mx, inp.My)
                _best = None
                _best_d = None
                for _f in _forces:
                    if _f.case.strip().startswith("TX_"):
                        continue
                    _d = (abs(_f.N - inp.N) / max(abs(inp.N), 1.0)
                          + abs(math.hypot(_f.Mx, _f.My) - _mres)
                          / max(_mres, 1.0))
                    if _best_d is None or _d < _best_d:
                        _best_d = _d
                        _best = _f
                if _best is not None and _best_d <= 0.02:
                    _cb = _best.case.strip()
                    for _sf in ("max", "min"):
                        if _cb.lower().endswith(_sf):
                            _cb = _cb[:-len(_sf)].strip()
                            break
                    _key = (_best.story.strip(), _best.column.strip(),
                            round(_best.station, 3), _cb)
                    _n_sus = _dns_map.get(_key)
            if _n_sus is not None:
                _beta = max(0.0, min(1.0, _n_sus / inp.N))
                _beta_src = f"TX_ ({_n_sus:.0f}/{inp.N:.0f})"
        except Exception:
            pass
        # Gọi hàm tính đầy đủ 1 lần
        _full = self._aci_calculate_full(
            sec, conc, steel, inp,
            N=inp.N, M2=inp.Mx, M3=inp.My, Q2=inp.Q2, Q3=inp.Q3,
            beta_dns=_beta, beta_src=_beta_src,
            tied=tied, fyt=fyt, fc=fc)
        # Lưu full result để tab/PDF chỉ đọc hiển thị (không tính lại)
        self._aci_full = _full
        # Tương thích ngược: gán các biến cũ từ full dict
        aci_res = _full
        mm_res = {"dir2": _full.get("mm2", {}), "dir3": _full.get("mm3", {}),
                  "delta2": _full.get("delta2", 1.0), "delta3": _full.get("delta3", 1.0),
                  "Mc2": _full.get("M2_mag"), "Mc3": _full.get("M3_mag"),
                  "L0_2": _full.get("L0_2"), "L0_3": _full.get("L0_3"),
                  "beta_src": _full.get("beta_src", "")}
        shear_res = _full.get("shear")
        # Cập nhật các thuộc tính cũ để tương thích
        self._aci_mm = mm_res
        self._aci_shear = shear_res
        self._aci_res = aci_res
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
        # Render tab Chi tiết: TRÌ HOÃN (lazy) tới khi user mở tab —
        # dựng thuyết minh + fig ngay trong CHECK tốn ~0.7s dù user
        # thường chỉ xem tab Kết quả. Reset state của _render_aci_report
        # vẫn làm ngay tại đây để hành vi đổi góc/3D không đổi.
        self._aci_is_3d = False
        self._aci_nm_view_angle = None

        def _render_detail_aci(_sections=sections):
            try:
                self._render_aci_report(_sections)
            except Exception as ex:
                messagebox.showerror("Lỗi hiển thị ACI",
                                     f"Không hiển thị được tab Chi tiết:\n{ex}")
        self._defer_detail(_render_detail_aci)
        self._pdf_inp, self._pdf_res = inp, None  # đánh dấu ACI mode
        self._update_ck()

    def _get_aci_param_rows(self, inp, aci_res, mm_res):
        """Trả về rows data cho bảng thông số ACI."""
        import math
        alpha_deg = (aci_res["alpha_deg"] if isinstance(aci_res, dict) and "alpha_deg" in aci_res
                     else math.degrees(math.atan2(inp.Mx, inp.My)) % 360.0 if abs(inp.Mx) + abs(inp.My) > 1e-9 else 0.0)
        Ma = (aci_res["Malpha"] if isinstance(aci_res, dict) and "Malpha" in aci_res
              else math.hypot(inp.Mx, inp.My))
        delta_txt = "—"
        if mm_res:
            try:
                d2 = mm_res.get("delta2", 1.0)
                d3 = mm_res.get("delta3", 1.0)
                delta_txt = f"δ2={d2:.3f}, δ3={d3:.3f}"
            except Exception:
                pass
        rows = [
            ("N", "Lực dọc tính toán", f"{inp.N:+.1f} kN"),
            ("M2", "Mô men phương 2", f"{inp.Mx:.1f} kN×m"),
            ("M3", "Mô men phương 3", f"{inp.My:.1f} kN×m"),
            ("α", "Góc tác dụng mô men", f"{alpha_deg:.1f} °"),
            ("Mα", "Mô men tổng hợp", f"{Ma:.1f} kN×m"),
            ("e2", "Độ lệch tâm phương 2 (M2/N)",
             f"{abs(inp.Mx/inp.N*1000):.1f} mm" if abs(inp.N) > 1e-9 else "—"),
            ("e3", "Độ lệch tâm phương 3 (M3/N)",
             f"{abs(inp.My/inp.N*1000):.1f} mm" if abs(inp.N) > 1e-9 else "—"),
            ("φ", "Hệ số sức kháng (ACI 21.2.2)", f"{aci_res['phi']:.2f}"),
            ("εt", "Biến dạng thép chịu kéo xa nhất", f"{aci_res.get('eps_t', 0):.5f}"),
            ("β1", "Hệ số khối ứng suất chữ nhật", f"{aci_res.get('beta1', 0.85):.2f}"),
            ("δns", "Hệ số phóng đại mô men (ACI 6.6.4)", delta_txt),
            ("M2*", "Mô men tính toán phương 2 (đã phóng đại)",
             f"{mm_res.get('Mc2', aci_res.get('M2_mag', inp.Mx)) if mm_res else aci_res.get('M2_mag', inp.Mx):.1f} kN×m"),
            ("M3*", "Mô men tính toán phương 3 (đã phóng đại)",
             f"{mm_res.get('Mc3', aci_res.get('M3_mag', inp.My)) if mm_res else aci_res.get('M3_mag', inp.My):.1f} kN×m"),
            ("NB", "Lực dọc tại điểm giới hạn B (trên tia tải)", f"{aci_res.get('BN', 0):+.1f} kN"),
            ("φPn,max", "Nén đúng tâm lớn nhất (ACI 22.4.2)", f"{aci_res.get('N_cap', 0):.1f} kN"),
        ]
        ok = aci_res["ok"]
        _fs = aci_res.get("fs", 0)
        _dc = aci_res.get("dc", 0)
        if not _fs and _dc and _dc > 1e-9:
            _fs = 1.0 / _dc
        fs_txt = (f"{_fs:.2f}" if math.isfinite(_fs) else "∞")
        ok_txt = "ĐẠT" if ok else "KHÔNG ĐẠT"
        dc_row = ("D/C", "Tỷ số sử dụng khả năng chịu lực",
                  f"{aci_res['dc']:.3f} (FS = {fs_txt})  {ok_txt}", ok)
        return rows, dc_row

    def _show_aci_summary(self):
        """Tab Kết quả tính toán cho ACI - dùng unified renderer."""
        if not HAS_MPL:
            return
        from gui.result_renderer import render_result_tab
        from rc_column.aci_chart_draw import draw_aci_nm_alpha_ax, draw_aci_m2m3_ax

        sec = self._aci_sec
        inp = self._aci_inp
        aci_res = self._aci_res
        conc = self._aci_conc
        steel = self._aci_steel
        tied = self._aci_tied
        mm_res = getattr(self, "_aci_mm", None)

        # Lấy rows thông số
        param_rows, dc_row = self._get_aci_param_rows(inp, aci_res, mm_res)

        # Section cards
        vals = self._section_card_values(sec)
        section_cards = {"n": vals["n"], "as": vals["as"], "ab": vals["ab"], "mu": vals["mu"]}

        # Hàm vẽ N-M (dùng góc đã chọn nếu có)
        def _draw_nm(ax):
            _mm = getattr(self, "_aci_mm", None) or {}
            _Mc2 = _mm.get("Mc2", inp.Mx)
            _Mc3 = _mm.get("Mc3", inp.My)
            # Nếu user chọn góc cụ thể, tính lại M2/M3 tại góc đó
            _view_angle = getattr(self, "_aci_nm_view_angle", None)
            if _view_angle is not None:
                import math
                _Ma = math.hypot(_Mc2, _Mc3)
                _rad = math.radians(_view_angle)
                _Mc2 = _Ma * math.sin(_rad)
                _Mc3 = _Ma * math.cos(_rad)
            draw_aci_nm_alpha_ax(ax, sec, conc, steel, aci_res, inp.N, _Mc2, _Mc3, tied=tied)

        # Hàm vẽ M2-M3
        def _draw_m2m3(ax):
            draw_aci_m2m3_ax(ax, sec, conc, steel, aci_res, inp.N, inp.Mx, inp.My, tied=tied)

        # Notes đầy đủ như TCVN
        import math
        alpha_deg = aci_res.get("alpha_deg", 0)
        _ok = aci_res['ok']
        _okt = "ĐẠT" if _ok else "KHÔNG ĐẠT"
        _okc = "#059669" if _ok else "#DC2626"
        # Thông tin combo/vị trí
        _case = getattr(self, "_pdf_case", None) or {}
        _parts = []
        if _case.get("story"): _parts.append(str(_case.get("story")))
        if _case.get("column"): _parts.append(str(_case.get("column")))
        if _case.get("case"):
            _st = _case.get("station", "")
            _st_txt = f"@{_st:.2f}" if isinstance(_st, (int, float)) else ""
            _parts.append(f"{_case.get('case')}{_st_txt}")
        _combo_txt = f" [{', '.join(_parts)}]" if _parts else ""
        _mm = getattr(self, "_aci_mm", None) or {}
        _Mc2 = _mm.get("Mc2", inp.Mx)
        _Mc3 = _mm.get("Mc3", inp.My)
        _Ma = math.hypot(_Mc2, _Mc3)
        _BN = aci_res.get("BN", 0)
        _Bx = aci_res.get("Bx", 0)
        _By = aci_res.get("By", 0)
        _Mb = math.hypot(_Bx, _By)
        notes = [
            (f"● Đường bao kiểm tra: N-Mα (α = {alpha_deg:.1f}°)", "#059669"),
            (f"● A (điểm tải){_combo_txt}:  N = {inp.N:+.1f} kN,  Mα = {_Ma:.1f} kN×m  (M2 = {_Mc2:.1f}, M3 = {_Mc3:.1f})", "#2563EB"),
            (f"◆ B (điểm giới hạn):  N = {_BN:+.1f} kN,  Mα,u = {_Mb:.1f} kN×m  (M2u = {_Bx:.1f}, M3u = {_By:.1f})", "#EA580C"),
        ]

        # Đường trung hòa chính xác từ fiber model ACI
        _aci_na_info = None
        try:
            from rc_column.aci_checker import aci_neutral_axis_at_N
            _aci_na_info = aci_neutral_axis_at_N(
                sec, conc, steel, _BN, alpha_deg, tied=tied)
        except Exception:
            _aci_na_info = None
        config = {
            "std_title": "(ACI 318-19)",
            "param_rows": param_rows,
            "dc_row": dc_row,
            "section": sec,
            "section_cards": section_cards,
            "comp_zone": {"N": _BN, "M2": _Bx, "M3": _By,
                          "Nmax": aci_res.get("N_cap", abs(_BN)*2),
                          "na_info": _aci_na_info},
            "draw_nm": _draw_nm,
            "draw_m2m3": _draw_m2m3,
            "nm_title": "Biểu đồ tương tác N-Mα",
            "nm_alpha_text": f"α = {alpha_deg:.1f}°",
            "m2m3_title": "Mặt cắt M2-M3",
            "m2m3_n_text": f"N = {aci_res.get('BN', inp.N):+.1f} kN",
            "notes_nm": notes,
            "on_nm_angle_change": lambda sel: self._on_aci_angle_unified(sel),
            "shear_builder": lambda parent: self._build_aci_shear_summary(
                parent, inp, sec, conc, steel, getattr(self, '_aci_full', {}) or {}),
        }
        render_result_tab(self, config)
        # Lưu fig cho detail tab dùng (tên cũ để tương thích)
        self._aci_nm_fig = getattr(self, "_nm_fig", None)
        self._aci_m2m3_fig = getattr(self, "_m2m3_fig", None)
        self._update_ck()

    def _on_aci_angle_unified(self, sel):
        """Xử lý chọn góc xem - chỉ vẽ lại biểu đồ N-M (mượt như TCVN)."""
        try:
            _is_3d = getattr(self, "_aci_is_3d", False)
            if sel == "3D":
                if _is_3d:
                    return  # Đã ở 3D, không tạo thêm
                self._draw_3d_aci()
                self._aci_is_3d = True
                return
            # Chọn góc 2D
            if sel.startswith("α"):
                self._aci_nm_view_angle = None
            else:
                self._aci_nm_view_angle = float(sel.replace("°", ""))
            if _is_3d:
                # Đang ở 3D, chỉ tạo lại khung 2D (không render toàn tab)
                self._aci_is_3d = False
                self._restore_2d_aci()
            else:
                # Đang ở 2D, chỉ vẽ lại axes (mượt)
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

    def _restore_2d_aci(self):
        """Khôi phục biểu đồ 2D sau khi xem 3D - chỉ tạo lại khung chart."""
        try:
            import tkinter as tk
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            parent = getattr(self, "_nm_parent", None)
            draw_fn = getattr(self, "_nm_draw_fn", None)
            if parent is None or draw_fn is None:
                # Fallback: render lại toàn tab
                self._show_aci_summary()
                return
            # Xóa canvas 3D cũ (giữ lại header)
            _old_cv = getattr(self, "_nm_canvas", None)
            if _old_cv:
                try:
                    _old_cv.get_tk_widget().destroy()
                except Exception:
                    pass
            # Xóa các widget canvas còn sót (trừ header là Frame đầu tiên)
            for w in parent.winfo_children():
                # Header là ttk.Frame, canvas là tk.Canvas
                if w.winfo_class() == "Canvas":
                    w.destroy()
            # Tạo figure/canvas 2D mới
            fig = Figure(figsize=(5.2, 3.9), dpi=100)
            cv = FigureCanvasTkAgg(fig, master=parent)
            cw = cv.get_tk_widget()
            cw.configure(highlightthickness=0, takefocus=0)
            cw.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            ax = fig.add_subplot(111)
            draw_fn(ax)
            fig.tight_layout()
            cv.draw()
            # Cập nhật ref
            self._nm_ax = ax
            self._nm_canvas = cv
        except Exception as e:
            self._show_aci_summary()

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

    def _build_aci_shear_summary(self, parent, inp, sec, conc, steel, full_res=None):
        """Bảng kiểm tra khả năng chịu cắt ACI: Phương V2 | Phương V3.
        CHỈ hiển thị từ full_res (đã tính bởi _aci_calculate_full), KHÔNG tính lại."""
        # Lấy kết quả đã tính sẵn từ _aci_calculate_full - KHÔNG tính lại
        _fr = full_res or {}
        _sh2 = _fr.get("shear2") or {}
        _sh3 = _fr.get("shear3") or {}
        _disp = _fr.get("shear_disp") or {}
        _d2 = _disp.get("2") or {}
        _d3 = _disp.get("3") or {}
        try:
            cols = {}
            # Đọc trực tiếp từ kết quả đã tính, không gọi aci_shear_check
            for lbl, sh, dp in (("2", _sh2, _d2), ("3", _sh3, _d3)):
                cols[lbl] = dict(
                    Vu=dp.get("Vu", 0),
                    b=dp.get("b", 0),
                    d=dp.get("d", 0),
                    Av=dp.get("Av", 0),
                    Vc=sh.get("Vc_kN", 0),
                    Vs=sh.get("Vs_kN", 0),
                    phiVn=sh.get("phi_Vn_kN", 0),
                    ok=sh.get("ok", False),
                    sw_txt=dp.get("sw_txt", ""),
                    combo_info=dp.get("combo_info", "") or sh.get("combo_info", ""),
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
            def _vu_txt(c):
                return f"{c['Vu']:.1f} kN"
            rows = [
                ("Thép đai bố trí",
                 cols['2']['sw_txt'], cols['3']['sw_txt']),
                ("Lực cắt tính toán, Vu",
                 _vu_txt(cols['2']), _vu_txt(cols['3'])),
                ("Kích thước tiết diện, b × d",
                 f"{cols['2']['b']:.0f} × {cols['2']['d']:.0f} mm",
                 f"{cols['3']['b']:.0f} × {cols['3']['d']:.0f} mm"),
                ("Av = n × φ",
                 f"{cols['2']['Av']:.0f} mm²", f"{cols['3']['Av']:.0f} mm²"),
                ("Vc = max[0.17λ√f'c, 0.66λsλ(ρw)⅓√f'c]×bw×d (ACI 22.5.5)",
                 f"{cols['2']['Vc']:.1f} kN", f"{cols['3']['Vc']:.1f} kN"),
                ("Vs = Av×fyt×d/s (ACI 22.5.8)",
                 f"{cols['2']['Vs']:.1f} kN", f"{cols['3']['Vs']:.1f} kN"),
                ("φVn = φ×(Vc+Vs) ≤ φ×(Vc+0.66√f'c×bw×d)",
                 f"{cols['2']['phiVn']:.1f} kN", f"{cols['3']['phiVn']:.1f} kN"),
                ("Kết luận",
                 "ĐẠT" if cols['2']['ok'] else "KHÔNG ĐẠT",
                 "ĐẠT" if cols['3']['ok'] else "KHÔNG ĐẠT"),
            ]
            for i, (a, b, cc) in enumerate(rows):
                bg = "#F9FAFB" if i % 2 else "white"
                is_kl = (a == "Kết luận")
                for j, t in enumerate((a, b, cc)):
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
        tree.column("sym", width=84, anchor="center", stretch=False)
        tree.column("desc", width=200, anchor="w")
        tree.column("val", width=220, anchor="e", stretch=False)
        tree.tag_configure("odd", background="#F9FAFB")
        dc_bg = "#D1FAE5" if aci_res["ok"] else "#FEE2E2"
        dc_fg = "#065F46" if aci_res["ok"] else "#991B1B"
        tree.tag_configure("dc", background=dc_bg, foreground=dc_fg)
        alpha_deg = (aci_res["alpha_deg"] if "aci_res" in locals() and isinstance(aci_res, dict) and "alpha_deg" in aci_res else math.degrees(math.atan2(inp.Mx, inp.My)) % 360.0 if abs(inp.Mx) + abs(inp.My) > 1e-9 else 0.0)
        Ma = (aci_res["Malpha"] if "aci_res" in locals() and isinstance(aci_res, dict) and "Malpha" in aci_res else math.hypot(inp.Mx, inp.My))
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
             f"{inp.Mx:.1f} kN×m"),
            ("M3", "Mô men phương 3",
             f"{inp.My:.1f} kN×m"),
            ("α", "Góc tác dụng mô men",
             f"{alpha_deg:.1f} °"),
            ("Mα", "Mô men tổng hợp",
             f"{Ma:.1f} kN×m"),
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
             f"{mm_res.get('Mc2', aci_res.get('M2_mag', inp.Mx)) if mm_res else aci_res.get('M2_mag', inp.Mx):.1f} kN×m"),
            ("M3*", "Mô men tính toán phương 3 (đã phóng đại)",
             f"{mm_res.get('Mc3', aci_res.get('M3_mag', inp.My)) if mm_res else aci_res.get('M3_mag', inp.My):.1f} kN×m"),
            ("NB", "Lực dọc tại điểm giới hạn B (trên tia tải)",
             f"{aci_res.get('BN', 0):+.1f} kN"),
            ("φPn,max", "Nén đúng tâm lớn nhất (ACI 22.4.2)",
             f"{aci_res.get('N_cap', 0):.1f} kN"),
        ]
        for i, (a, b, c) in enumerate(rows):
            tree.insert("", "end", values=(a, b, c),
                        tags=("odd",) if i % 2 else ())
        ok_txt = "ĐẠT" if aci_res["ok"] else "KHÔNG ĐẠT"
        # FS = 1/D/C nếu không có sẵn (trường hợp ETABS dùng dc_ratio)
        _fs = aci_res.get("fs", 0)
        _dc = aci_res.get("dc", 0)
        if not _fs and _dc and _dc > 1e-9:
            _fs = 1.0 / _dc
        fs_txt = (f"{_fs:.2f}" if math.isfinite(_fs) else "∞")
        tree.insert("", "end",
                    values=("D/C", "Tỷ số sử dụng khả năng chịu lực",
                            f"{aci_res['dc']:.3f} (FS = {fs_txt})  {ok_txt}"),
                    tags=("dc",))
        tree.pack(fill=tk.X, expand=False, padx=2, pady=2)

    def _build_aci_nm_header(self, parent, inp):
        """Header trên biểu đồ N-Mα (ACI)."""
        import math
        alpha_deg = (aci_res["alpha_deg"] if "aci_res" in locals() and isinstance(aci_res, dict) and "alpha_deg" in aci_res else math.degrees(math.atan2(inp.Mx, inp.My)) % 360.0 if abs(inp.Mx) + abs(inp.My) > 1e-9 else 0.0)
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
        self._aci_nm_view_angle = None

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
                a0 = math.degrees(math.atan2(inp.Mx, inp.My)) % 360.0 \
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
            _mm2 = getattr(self, "_aci_mm", None) or {}
            _Mc2b = _mm2.get("Mc2", self._aci_inp.Mx)
            _Mc3b = _mm2.get("Mc3", self._aci_inp.My)
            draw_aci_nm_alpha_ax(
                ax, self._aci_sec, self._aci_conc, self._aci_steel,
                self._aci_res, self._aci_inp.N, _Mc2b,
                _Mc3b, tied=self._aci_tied,
                view_angle_deg=angle)
            self._aci_nm_fig.tight_layout()
            self._aci_nm_fig.subplots_adjust(bottom=0.30)
            self._aci_nm_cv_ref.draw()
        except Exception:
            pass

    def _build_aci_m2m3_header(self, parent, inp, aci_res=None):
        """Header trên biểu đồ M2-M3 (ACI)."""
        hdr = ttk.Frame(parent)
        hdr.pack(fill=tk.X, padx=4, pady=(2, 2))
        left = ttk.Frame(hdr)
        left.pack(side=tk.LEFT)
        tk.Label(left, text="● Mặt cắt M2-M3",
                 font=("", 10, "bold"), bg="white").pack(side=tk.LEFT)
        tk.Label(left, text=f"  N = {(aci_res.get('BN', inp.N) if isinstance(aci_res, dict) else inp.N):+.1f} kN  ",
                 font=("", 8, "bold"), fg="#1D4ED8",
                 bg="#DBEAFE").pack(side=tk.LEFT, padx=6)

    def _build_aci_notes(self, parent, inp, aci_res):
        """3 dòng chú thích dưới biểu đồ ACI."""
        import math
        mono = ("TkFixedFont", 10)
        Ma = (aci_res["Malpha"] if "aci_res" in locals() and isinstance(aci_res, dict) and "Malpha" in aci_res else math.hypot(inp.Mx, inp.My))
        Mb = math.hypot(aci_res["Bx"], aci_res["By"])
        alpha_deg = (aci_res["alpha_deg"] if "aci_res" in locals() and isinstance(aci_res, dict) and "alpha_deg" in aci_res else math.degrees(math.atan2(inp.Mx, inp.My)) % 360.0 if abs(inp.Mx) + abs(inp.My) > 1e-9 else 0.0)
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
        # FS = 1/D/C nếu không có sẵn (trường hợp ETABS dùng dc_ratio)
        _fs = aci_res.get("fs", 0)
        _dc = aci_res.get("dc", 0)
        if not _fs and _dc and _dc > 1e-9:
            _fs = 1.0 / _dc
        fs_txt = (f"{_fs:.2f}" if math.isfinite(_fs) else "∞")
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
                      f"Mα = {Ma:.1f} kN×m  "
                      f"(M2 = {inp.Mx:.1f}, M3 = {inp.My:.1f})",
                 font=mono, fg="#2563EB").pack(anchor="w", pady=1)
        tk.Label(box, bg="white",
                 text=f"◆ B (điểm giới hạn):  "
                      f"N = {aci_res['BN']:+.1f} kN,  Mα,u = {Mb:.1f} kN×m  "
                      f"(M2u = {aci_res['Bx']:.1f}, M3u = {aci_res['By']:.1f})",
                 font=mono, fg="#EA580C").pack(anchor="w", pady=1)

    def _render_aci_report(self, sections):
        """Hiển thị thuyết minh ACI trong tab Chi tiết tính toán.
        Plot lại biểu đồ từ data tính toán chung (không dùng fig của result tab)."""
        # Reset trạng thái 3D của result tab để tránh ảnh hưởng
        self._aci_is_3d = False
        self._aci_nm_view_angle = None
        for w in self._calc_inner.winfo_children():
            w.destroy()
        from rc_column.report_widgets import render_report_sections
        # Tạo fig mới từ data tính toán (đúng nguyên tắc: tính 1 lần, vẽ nhiều nơi)
        _figs = self._create_aci_detail_figs()
        render_report_sections(self._calc_inner, sections, chart_figs=_figs)
        self._calc_inner.update_idletasks()
        self._calc_canvas.configure(scrollregion=self._calc_canvas.bbox("all"))
        self._bind_wheel(self._calc_inner, self._calc_canvas)
        try:
            self._calc_canvas.yview_moveto(0)
        except Exception:
            pass

    def _create_aci_detail_figs(self):
        """Tạo 2 fig biểu đồ cho tab Chi tiết từ data tính toán chung."""
        try:
            import math
            from matplotlib.figure import Figure
            from rc_column.aci_chart_draw import draw_aci_nm_alpha_ax, draw_aci_m2m3_ax
            from rc_column.pdf_export import draw_compression_zone_ax
            sec = getattr(self, "_aci_sec", None)
            inp = getattr(self, "_aci_inp", None)
            aci_res = getattr(self, "_aci_res", None)
            conc = getattr(self, "_aci_conc", None)
            steel = getattr(self, "_aci_steel", None)
            tied = getattr(self, "_aci_tied", True)
            if not all([sec, inp, aci_res, conc, steel]):
                return (None, None, None)
            mm = getattr(self, "_aci_mm", None) or {}
            Mc2 = mm.get("Mc2", inp.Mx)
            Mc3 = mm.get("Mc3", inp.My)
            # Fig N-Mα
            fig1 = Figure(figsize=(5.2, 3.9), dpi=100)
            ax1 = fig1.add_subplot(111)
            draw_aci_nm_alpha_ax(ax1, sec, conc, steel, aci_res, inp.N, Mc2, Mc3, tied=tied)
            fig1.tight_layout()
            # Fig M2-M3
            fig2 = Figure(figsize=(5.2, 3.9), dpi=100)
            ax2 = fig2.add_subplot(111)
            draw_aci_m2m3_ax(ax2, sec, conc, steel, aci_res, inp.N, inp.Mx, inp.My, tied=tied)
            fig2.tight_layout()
            return (fig1, fig2)
        except Exception as e:
            return (None, None, None)

    def _draw_3d_aci(self):
        """Vẽ biểu đồ tương tác 3D cho ACI."""
        try:
            from mpl_toolkits.mplot3d import Axes3D  # noqa
            import numpy as np
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            # Tạo figure/canvas mới hoàn toàn để tránh canvas bị lock
            try:
                # Dùng ref từ unified renderer (fallback về ref cũ)
                _old = getattr(self, '_nm_canvas', None) or getattr(self, '_aci_nm_cv_ref', None)
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
                self._aci_nm_fig = _fig
                self._aci_nm_cv_ref = _cv
            fig = self._aci_nm_fig
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
            ax.set_xlabel('M2 (kN×m)')
            ax.set_ylabel('M3 (kN×m)')
            ax.set_zlabel('N (kN)')
            fig.tight_layout()
            self._aci_nm_cv_ref.draw()
            self._aci_nm_ax_ref = None
        except Exception as ex:
            import traceback
            traceback.print_exc()

