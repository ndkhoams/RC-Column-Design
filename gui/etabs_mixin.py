"""Các method import và kiểm tra dữ liệu ETABS."""



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
from tkinter import ttk, messagebox
import math
from rc_column.checker import ColumnInput, build_section, check_column
from rc_column.report import generate_report, generate_report_sections
from rc_column.materials import CONCRETE_GRADES, STEEL_GRADES
from rc_column.sections import clear_spacing, bar_area
from rc_column.stability import BOUNDARY_NAMES, LongTermLoads
from rc_column.lang import T
class EtabsMixin:
    """Các method import và kiểm tra dữ liệu ETABS."""

    def on_import_etabs(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Chọn file Excel ETABS",
            filetypes=[("Excel", "*.xlsx *.xls"), ("All", "*.*")])
        if not path:
            return
        self._load_etabs_file(path)

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
            _is_tdtx = f.case.strip().startswith("TX_")
            _dc_txt = ""
            if not _is_tdtx:
                _dc_txt = f"{dc:.3f}" if dc is not None and dc == dc else "—"
            vals = (f.story, f.column, f.case, f"{f.station:.2f}",
                    f"{f.N:.0f}", f"{f.Q2:.0f}", f"{f.Q3:.0f}",
                    f"{f.Mx:.0f}", f"{f.My:.0f}", _dc_txt)
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
        # Cho sửa N(4), V2(5), V3(6), M2(7), M3(8) - 0-based
        col_idx = int(col_id[1:]) - 1
        if col_idx not in (4, 5, 6, 7, 8):
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
            # Cập nhật etabs_forces (tìm theo story+label+case+station)
            _st, _lb, _cs, _sn = vals[0], vals[1], vals[2], vals[3]
            for f in self.etabs_forces:
                if (f.story.strip() == _st.strip() and
                    f.column.strip() == _lb.strip() and
                    f.case.strip() == _cs.strip() and
                    abs(f.station - float(_sn)) < 0.01):
                    if col_idx == 4:
                        f.N = num
                    elif col_idx == 5:
                        f.Q2 = num
                    elif col_idx == 6:
                        f.Q3 = num
                    elif col_idx == 7:
                        f.Mx = num
                    elif col_idx == 8:
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
        # Tách tổ hợp TX_* (tải thường xuyên): không kiểm tra, dùng tính beta_dns
        _dns_map = {}  # (story, column, station, base_case) -> N_dns
        _forces_check = []
        for _f in self.etabs_forces:
            _cn = _f.case.strip()
            if _cn.startswith("TX_"):
                _base = _cn[3:]
                _key = (_f.story.strip(), _f.column.strip(),
                        round(_f.station, 3), _base)
                _dns_map[_key] = _f.N
            else:
                _forces_check.append(_f)
        if _dns_map:
            print(f"[ACI] Tìm thấy {len(_dns_map)} tổ hợp TX_*")
        _groups = defaultdict(list)
        for _f in _forces_check:
            _groups[(_f.story, _f.column)].append(_f)
        # Lưu map để dùng tính beta_dns
        self._dns_map = _dns_map
        rows = []
        from rc_column.aci_checker import ACICapacity
        for (_st, _cl), _flist in _groups.items():
            _Lx_man = self._f(self.en_Lx, 0.0)
            _Ly_man = self._f(self.en_Ly, 0.0)
            _max_st = max(_f.station for _f in _flist)
            _Lx_grp = _Lx_man if _Lx_man > 0 else _max_st
            _Ly_grp = _Ly_man if _Ly_man > 0 else _max_st
            _inp_g = self.collect()
            _inp_g.Lx = _Lx_grp
            _inp_g.Ly = _Ly_grp
            sec_g = build_section(_inp_g)
            # Tối ưu: dựng ACICapacity 1 lần cho cả nhóm (đắt),
            # mỗi tổ hợp chỉ tính D/C tia (rẻ)
            try:
                _cap_g = ACICapacity(sec_g, conc, steel, tied=tied,
                                     n_angles=24)
            except Exception:
                _cap_g = None
            # Tính δns cho nhóm (dùng L0 chung của nhóm)
            from rc_column.aci_checker import moment_magnification
            from rc_column.stability import effective_length
            _L0_2 = effective_length(_Lx_grp, _inp_g.top_x, _inp_g.bottom_x,
                                     _inp_g.psi_x) * 1000
            _L0_3 = effective_length(_Ly_grp, _inp_g.top_y, _inp_g.bottom_y,
                                     _inp_g.psi_y) * 1000
            _Ig2 = sec_g.cx * sec_g.cy**3 / 12
            _Ig3 = sec_g.cy * sec_g.cx**3 / 12
            for _f in _flist:
                try:
                    if _cap_g is None:
                        raise RuntimeError("capacity")
                    # βdns từ TX_ tại đúng vị trí, mặc định 0.6
                    # Bỏ Step Type (max/min) ở cuối tên Combo
                    _cb = _f.case.strip()
                    for _sf in ("max", "min"):
                        if _cb.lower().endswith(_sf):
                            _cb = _cb[:-len(_sf)].strip()
                            break
                    _key = (_f.story.strip(), _f.column.strip(),
                            round(_f.station, 3), _cb)
                    _n_dns = _dns_map.get(_key, None)
                    _beta = 0.6
                    if _n_dns is not None and abs(_f.N) > 1e-9:
                        _beta = max(0.0, min(1.0, _n_dns / _f.N))
                    # Phóng đại δns 2 phương
                    _mm2 = moment_magnification(
                        Pu_kN=_f.N, M1_kNm=_f.Mx, M2_kNm=_f.Mx,
                        lu_mm=_L0_2, k=1.0, Ec_MPa=conc.Ec,
                        Ig_mm4=_Ig2, beta_dns=_beta)
                    _mm3 = moment_magnification(
                        Pu_kN=_f.N, M1_kNm=_f.My, M2_kNm=_f.My,
                        lu_mm=_L0_3, k=1.0, Ec_MPa=conc.Ec,
                        Ig_mm4=_Ig3, beta_dns=_beta)
                    _d2 = _mm2.get("delta_ns", 1.0) if _mm2.get("ok") else 1.0
                    _d3 = _mm3.get("delta_ns", 1.0) if _mm3.get("ok") else 1.0
                    _M2s = _d2 * _f.Mx
                    _M3s = _d3 * _f.My
                    _r = _cap_g.dc_ratio(_f.N, _M2s, _M3s)
                except Exception:
                    _r = {"dc": float("nan"), "ok": False}
                rows.append((_f, _r))
        rows.sort(key=lambda x: -(x[1]["dc"]) if x[1]["dc"] == x[1]["dc"]
                  else float("inf"))
        # Thêm các dòng TX_ vào cuối (không tính D/C)
        try:
            _tdtx = [f for f in self.etabs_forces
                     if f.case.strip().startswith("TX_")]
            for _f in _tdtx:
                rows.append((_f, None))
        except Exception:
            pass
        self._fill_etabs_table(rows)
        worst_f, worst_r = rows[0]
        # TÍNH 1 LẦN cho worst case bằng hàm chung (không tính lại ở tab/PDF)
        try:
            # beta_dns từ TX_
            _case_base = worst_f.case.strip()
            for _suf in ("max", "min"):
                if _case_base.lower().endswith(_suf):
                    _case_base = _case_base[:-len(_suf)].strip()
                    break
            _keyw = (worst_f.story.strip(), worst_f.column.strip(),
                     round(worst_f.station, 3), _case_base)
            _n_dnsw = _dns_map.get(_keyw, None)
            _betaw = 0.6
            _bsrcw = "mặc định"
            if _n_dnsw is not None and abs(worst_f.N) > 1e-9:
                _betaw = max(0.0, min(1.0, _n_dnsw / worst_f.N))
                _bsrcw = f"TX_ ({_n_dnsw:.0f}/{worst_f.N:.0f})"
            # Chuẩn bị inp cho worst case
            _inpw = self.collect()
            _Lx_man = self._f(self.en_Lx, 0.0)
            _Ly_man = self._f(self.en_Ly, 0.0)
            _inpw.Lx = _Lx_man if _Lx_man > 0 else worst_f.station
            _inpw.Ly = _Ly_man if _Ly_man > 0 else worst_f.station
            _inpw.N = worst_f.N
            _inpw.Mx = worst_f.Mx
            _inpw.My = worst_f.My
            _inpw.Q2 = worst_f.Q2
            _inpw.Q3 = worst_f.Q3
            _inpw._filename = self.member_var.get().strip() if hasattr(self, "member_var") else ""
            _secw = build_section(_inpw)
            _fytw = float(self.en_fyt.get().replace(",", "."))
            _fcw = float(self.en_fc.get().replace(",", "."))
            # Gọi hàm tính đầy đủ 1 lần
            _full_w = self._aci_calculate_full(
                _secw, conc, steel, _inpw,
                N=worst_f.N, M2=worst_f.Mx, M3=worst_f.My,
                Q2=worst_f.Q2, Q3=worst_f.Q3,
                beta_dns=_betaw, beta_src=_bsrcw,
                tied=tied, fyt=_fytw, fc=_fcw)
            # Lưu full result
            self._aci_full = _full_w
            # Tương thích ngược
            self._aci_sec = _secw
            self._aci_conc = conc
            self._aci_steel = steel
            self._aci_tied = tied
            self._aci_inp = _inpw
            self._aci_res = _full_w
            _mmw = {"dir2": _full_w.get("mm2", {}), "dir3": _full_w.get("mm3", {}),
                    "delta2": _full_w.get("delta2", 1.0), "delta3": _full_w.get("delta3", 1.0),
                    "Mc2": _full_w.get("M2_mag"), "Mc3": _full_w.get("M3_mag"),
                    "L0_2": _full_w.get("L0_2"), "L0_3": _full_w.get("L0_3"),
                    "beta_src": _full_w.get("beta_src", "")}
            self._aci_mm = _mmw
            self._aci_shear = _full_w.get("shear")
            # Cập nhật worst_r để bảng hiển thị đúng D/C từ full calc
            worst_r = _full_w
            rows[0] = (worst_f, worst_r)
        except Exception as _exw:
            print(f"[ETABS] tính full worst case lỗi: {_exw}")
        try:
                    self._pdf_case = {"story": worst_f.story, "column": worst_f.column,
                              "case": worst_f.case, "station": worst_f.station,
                              "N": worst_f.N, "M2": worst_f.Mx, "M3": worst_f.My}
        except Exception:
            pass
        children = self.etabs_tree.get_children()
        if children:
            self.etabs_tree.item(children[0], tags=("worst",))
            self.etabs_tree.see(children[0])
        n_ng = sum(1 for _, r in rows if r and r["dc"] == r["dc"] and r["dc"] > 1)
        dt = time.time() - t0
        self.etabs_info.set(
            f"Xong {len(rows)} tổ hợp trong {dt:.1f}s (ACI 318-19) — "
            f"Nguy hiểm nhất: {worst_f.case} @ {worst_f.station:.2f}m "
            f"(D/C = {worst_r['dc']:.3f}) — {n_ng} tổ hợp KHÔNG ĐẠT.")
        self._batch_rows = rows
        # Hiển thị tab Kết quả đầy đủ cho trường hợp nguy hiểm nhất
        try:
            self._show_aci_summary()
        except Exception as _ex:
            print(f"[ETABS] _show_aci_summary lỗi: {_ex}")
        # Render tab Chi tiết cho worst case - CHỈ ĐỌC từ _aci_full (không tính lại)
        try:
            from rc_column.aci_report_v2 import generate_aci_report_sections_v2
            _full = getattr(self, "_aci_full", None)
            if _full is None:
                raise RuntimeError("Chưa có kết quả tính toán")
            # Dựng inp/mm/shear từ full dict (không tính lại)
            import copy
            _inp2 = copy.copy(self._aci_inp)
            _inp2.Mx = _full.get("M2_mag", _inp2.Mx)
            _inp2.My = _full.get("M3_mag", _inp2.My)
            _mm_det = {"dir2": _full.get("mm2", {}), "dir3": _full.get("mm3", {}),
                       "delta2": _full.get("delta2", 1.0), "delta3": _full.get("delta3", 1.0),
                       "Mc2": _full.get("M2_mag"), "Mc3": _full.get("M3_mag"),
                       "L0_2": _full.get("L0_2"), "L0_3": _full.get("L0_3"),
                       "beta_src": _full.get("beta_src", "")}
            _shr = _full.get("shear", {"dir2": {}, "dir3": {}})
            _fyt = float(self.en_fyt.get().replace(",", "."))
            _secs = generate_aci_report_sections_v2(
                _inp2, _full, _mm_det, _shr,
                self._aci_conc, self._aci_steel, self._aci_sec,
                self._aci_tied, _fyt)
            self._render_aci_report(_secs)
        except Exception as _ex2:
            print(f"[ETABS] render chi tiết lỗi: {_ex2}")

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
        # Tách tổ hợp TX_* (tải thường xuyên): không kiểm tra, dùng tính beta_dns
        _dns_map = {}  # (story, column, station, base_case) -> N_dns
        _forces_check = []
        for _f in self.etabs_forces:
            _cn = _f.case.strip()
            if _cn.startswith("TX_"):
                _base = _cn[3:]
                _key = (_f.story.strip(), _f.column.strip(),
                        round(_f.station, 3), _base)
                _dns_map[_key] = _f.N
            else:
                _forces_check.append(_f)
        if _dns_map:
            print(f"[EC2] Tìm thấy {len(_dns_map)} tổ hợp TX_* (tính beta_dns)")
        _groups = defaultdict(list)
        for _f in _forces_check:
            _groups[(_f.story, _f.column)].append(_f)
        # Lưu map để dùng tính beta_dns
        self._dns_map = _dns_map
        rows = []
        for (_st, _cl), _flist in _groups.items():
            _Lx_man = self._f(self.en_Lx, 0.0)
            _Ly_man = self._f(self.en_Ly, 0.0)
            _max_st = max(_f.station for _f in _flist)
            _Lx_grp = _Lx_man if _Lx_man > 0 else _max_st
            _Ly_grp = _Ly_man if _Ly_man > 0 else _max_st
            _inp_g = self.collect()
            _inp_g.Lx = _Lx_grp
            _inp_g.Ly = _Ly_grp
            sec_g = build_section(_inp_g)
            cx, cy = sec_g.cx, sec_g.cy
            Ac = sec_g.gross_area
            As = sec_g.steel_area
            try:
                l0_2 = effective_length(_Lx_grp, _inp_g.top_x, _inp_g.bottom_x,
                                        _inp_g.psi_x) * 1000.0
                l0_3 = effective_length(_Ly_grp, _inp_g.top_y, _inp_g.bottom_y,
                                        _inp_g.psi_y) * 1000.0
            except Exception:
                l0_2 = _Lx_grp * 1000.0
                l0_3 = _Ly_grp * 1000.0
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
                    # Tính Is từ thép (chính xác)
                    _bars_g = getattr(sec_g, 'rebars', None) or getattr(sec_g, 'bars', None) or []
                    _Is2_g = _Is3_g = 0.0
                    try:
                        _cx_g = sec_g.cx / 2
                        _cy_g = sec_g.cy / 2
                        for _b in _bars_g:
                            _d = getattr(_b, 'dia', 0) or 0
                            _a = getattr(_b, 'area', 0) or (math.pi * _d**2 / 4)
                            _x = getattr(_b, 'x', 0) or 0
                            _y = getattr(_b, 'y', 0) or 0
                            _Is2_g += _a * (_y - _cy_g)**2
                            _Is3_g += _a * (_x - _cx_g)**2
                    except Exception:
                        pass
                    for lbl, Mdir in (("dir2", _f.Mx), ("dir3", _f.My)):
                        h_dim, Ic, l0 = geom[lbl]
                        _Is_g = _Is2_g if lbl == "dir2" else _Is3_g
                        dm = ec2_design_moment(
                            NEd_kN=_f.N, M_top_kNm=abs(Mdir),
                            M_bot_kNm=abs(Mdir), l0_mm=l0,
                            i_mm=math.sqrt(Ic / Ac) if Ac > 0 else h_dim,
                            h_mm=h_dim, Ac_mm2=Ac, As_mm2=As,
                            fcd_MPa=conc.fcd, fyd_MPa=steel.fyd,
                            Ecm_MPa=conc.Ecm, Ic_mm4=Ic, Is_mm4=_Is_g,
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
        # Thêm các dòng TX_ vào cuối (không tính D/C)
        try:
            _tdtx = [f for f in self.etabs_forces
                     if f.case.strip().startswith("TX_")]
            for _f in _tdtx:
                rows.append((_f, None))
        except Exception:
            pass
        self._fill_etabs_table(rows)
        worst_f, worst_r = rows[0]
        children = self.etabs_tree.get_children()
        if children:
            self.etabs_tree.item(children[0], tags=("worst",))
            self.etabs_tree.see(children[0])
        n_ng = sum(1 for _, r in rows if r and r["dc"] == r["dc"] and r["dc"] > 1)
        dt = time.time() - t0
        self.etabs_info.set(
            f"Xong {len(rows)} tổ hợp trong {dt:.1f}s (EC2 EN 1992-1-1) — "
            f"Nguy hiểm nhất: {worst_f.case} @ {worst_f.station:.2f}m "
            f"(D/C = {worst_r['dc']:.3f}) — {n_ng} tổ hợp KHÔNG ĐẠT.")
        self._batch_rows = rows
        # Tính lại tổ hợp nguy hiểm nhất để hiển thị
        inp_w = self.collect()
        inp_w.N, inp_w.Mx, inp_w.My = worst_f.N, worst_f.Mx, worst_f.My
        # L riêng từng phương: ưu tiên ô nhập tay (collect() đã đọc),
        # nếu trống thì dùng max station của cột đó
        _sts_w = [f.station for f in self.etabs_forces
                  if f.story == worst_f.story and f.column == worst_f.column]
        _max_stw = max(_sts_w) if _sts_w else 0.0
        if self._f(self.en_Lx, 0.0) <= 0 and _max_stw > 0:
            inp_w.Lx = _max_stw
        if self._f(self.en_Ly, 0.0) <= 0 and _max_stw > 0:
            inp_w.Ly = _max_stw
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
        # _check_ec2 sẽ gọi _ec2_calculate_full (tính 1 lần) và lưu self._ec2_full
        self._check_ec2(inp_w)
        # Cập nhật worst_r từ full calc để bảng hiển thị đúng D/C
        # (nguyên tắc: tính 1 lần, hiển thị nhiều nơi)
        try:
            _full_w = getattr(self, "_ec2_full", None)
            if _full_w is not None:
                worst_r = _full_w
                rows[0] = (worst_f, worst_r)
                # Cập nhật lại bảng với D/C từ full calc
                self._fill_etabs_table(rows)
        except Exception as _exu:
            print(f"[ETABS-EC2] cập nhật worst_r lỗi: {_exu}")

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
        # Tách tổ hợp TX_* (tải thường xuyên): không kiểm tra D/C
        _dns_map = {}  # (story, column, station, base_case) -> N_dns
        _tx_moment_map = {}  # (story, column, station, base_case) -> (M2, M3) cho phi_L TCVN
        _forces_check = []
        for _f in self.etabs_forces:
            _cn = _f.case.strip()
            if _cn.startswith("TX_"):
                _base = _cn[3:]
                _key = (_f.story.strip(), _f.column.strip(),
                        round(_f.station, 3), _base)
                _dns_map[_key] = _f.N
                _tx_moment_map[_key] = (_f.Mx, _f.My)  # Mx=M2, My=M3 cho phi_L
            else:
                _forces_check.append(_f)
        if _dns_map:
            print(f"[TCVN] Tìm thấy {len(_dns_map)} tổ hợp TX_* (tính beta_dns)")
        _groups = defaultdict(list)
        for _f in _forces_check:
            _groups[(_f.story, _f.column)].append(_f)
        # Lưu map để dùng tính beta_dns
        self._dns_map = _dns_map
        rows = []
        for (_st, _cl), _flist in _groups.items():
            _Lx_man = self._f(self.en_Lx, 0.0)
            _Ly_man = self._f(self.en_Ly, 0.0)
            _max_st = max(_f.station for _f in _flist)
            _Lx_grp = _Lx_man if _Lx_man > 0 else _max_st
            _Ly_grp = _Ly_man if _Ly_man > 0 else _max_st
            _inp_g = self.collect()
            _inp_g.Lx = _Lx_grp
            _inp_g.Ly = _Ly_grp
            _bc = BatchChecker(_inp_g, n_angles=12)
            for _f in _flist:
                _r = _bc.check_one(_f.N, _f.Mx, _f.My, _inp_g.long_term)
                rows.append((_f, _r))
        # sắp xếp theo D/C giảm dần (nguy hiểm nhất lên đầu)
        rows.sort(key=lambda x: -(x[1]["dc"]) if x[1]["dc"] == x[1]["dc"]
                  else float("inf"))
        # Thêm các dòng TX_ vào cuối (không tính D/C)
        try:
            _tdtx = [f for f in self.etabs_forces
                     if f.case.strip().startswith("TX_")]
            for _f in _tdtx:
                rows.append((_f, None))
        except Exception:
            pass
        # highlight dòng nguy hiểm nhất (dòng đầu sau sắp xếp)
        self._fill_etabs_table(rows)
        if not _forces_check:
            from tkinter import messagebox
            messagebox.showinfo("ETABS", "Chỉ có tổ hợp TX_*, không có tổ hợp nào để kiểm tra.")
            return
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
            # Chỉ điền L tự động khi ô đang trống (không ghi đè số user đã nhập)
            # Quy tắc: ô trống -> dùng max station; user nhập -> giữ nguyên, dùng số đã nhập
            if not self.en_Lx.get().strip():
                self.en_Lx.delete(0, tk.END); self.en_Lx.insert(0, f"{_L_auto:.2f}")
            if not self.en_Ly.get().strip():
                self.en_Ly.delete(0, tk.END); self.en_Ly.insert(0, f"{_L_auto:.2f}")
        children = self.etabs_tree.get_children()
        if children:
            self.etabs_tree.item(children[0], tags=("worst",))
            self.etabs_tree.see(children[0])
        n_ng = sum(1 for _, r in rows if r and r["dc"] > 1)
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
        # phi_L TCVN: tra mô men dài hạn từ tổ hợp TX_* (nếu có)
        try:
            from rc_column.stability import LongTermLoads
            _cn_w = worst_f.case.strip()
            # Bỏ hậu tố Step Type max/min
            _base_w = _cn_w
            if _base_w.endswith("max") or _base_w.endswith("min"):
                # Tìm vị trí bắt đầu của max/min (cần cẩn thận với tên có chứa max/min)
                # Đơn giản: thử bỏ 3 ký tự cuối nếu là max/min
                _low = _base_w.lower()
                if _low.endswith("max"):
                    _base_w = _base_w[:-3]
                elif _low.endswith("min"):
                    _base_w = _base_w[:-3]
            _key_w = (worst_f.story.strip(), worst_f.column.strip(),
                      round(worst_f.station, 3), _base_w)
            _tx_m = _tx_moment_map.get(_key_w)
            if _tx_m:
                _m2_lt, _m3_lt = _tx_m
                inp_w.long_term = LongTermLoads(
                    has_data=True, N_lt=0.0,  # N không dùng cho phi_L (chỉ dùng M)
                    Mx_lt=_m2_lt, My_lt=_m3_lt)
                print(f"[TCVN] phi_L: dùng TX_* M2={_m2_lt:.1f}, M3={_m3_lt:.1f} cho {_cn_w}")
            else:
                # Không có TX_*: giữ nguyên long_term từ collect() (mặc định 2.0)
                print(f"[TCVN] phi_L: không tìm thấy TX_* cho {_cn_w}, dùng mặc định")
        except Exception as _epl:
            print(f"[TCVN] phi_L lỗi: {_epl}")
        # L cho worst (riêng từng phương): ưu tiên ô nhập tay,
        # nếu trống thì dùng station max của nhóm worst
        _Lxw_man = self._f(self.en_Lx, 0.0)
        _Lyw_man = self._f(self.en_Ly, 0.0)
        _sts_w = [f.station for f in self.etabs_forces
                  if f.story == worst_f.story and f.column == worst_f.column]
        _max_st_w = max(_sts_w) if _sts_w else 0.0
        _Lxw = _Lxw_man if _Lxw_man > 0 else _max_st_w
        _Lyw = _Lyw_man if _Lyw_man > 0 else _max_st_w
        if _Lxw > 0:
            inp_w.Lx = _Lxw
        if _Lyw > 0:
            inp_w.Ly = _Lyw
        # Lực cắt: lấy từ combo có |Q| lớn nhất (độc lập với combo N-M)
        f_q2 = max(self.etabs_forces, key=lambda f: abs(f.Q2))
        f_q3 = max(self.etabs_forces, key=lambda f: abs(f.Q3))
        inp_w.Q2, inp_w.Q3 = f_q2.Q2, f_q3.Q3
        inp_w._filename = self.member_var.get().strip() if hasattr(self, "member_var") else ""
        shear_info = {
            "q2": {"case": f_q2.case, "station": f_q2.station, "Q": f_q2.Q2,
                   "story": getattr(f_q2, "story", ""),
                   "column": getattr(f_q2, "column", "")},
            "q3": {"case": f_q3.case, "station": f_q3.station, "Q": f_q3.Q3,
                   "story": getattr(f_q3, "story", ""),
                   "column": getattr(f_q3, "column", "")},
        }
        # TÍNH 1 LẦN cho worst case: gọi hàm tính đầy đủ (không tính lại ở nơi khác)
        _full_w = self._tcvn_calculate_full(inp_w, n_angles=24)
        res_w = _full_w["res"]
        sec_w = _full_w["sec"]
        # Lưu full dict để tab/PDF chỉ đọc hiển thị
        self._tcvn_full = _full_w
        # Giữ tương thích với _last_* hiện có
        self._last_inp = inp_w
        self._last_res = res_w
        self._last_sec = sec_w
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
        # Dùng shear_cols từ _tcvn_calculate_full (tính 1 lần), không dùng shear_info thiếu
        self._pdf_shear = _full_w.get("shear_cols")
        # cập nhật cả tab Tóm tắt + biểu đồ cho tổ hợp nguy hiểm nhất
        self._show_summary(sec_w, inp_w, res_w,
                           prefix=f"Tổ hợp {worst_f.case}@{worst_f.station:.2f}m: ")
        pass

