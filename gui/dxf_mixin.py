"""Import/export tiết diện bất kỳ qua DXF. Tách từ gui/app.py."""

import tkinter as tk
from tkinter import ttk, messagebox

from rc_column.checker import build_section


class DxfMixin:
    """Các method nhập/xuất tiết diện DXF."""

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

    def on_import_prokon(self):
        """Import toàn bộ từ file Prokon General Column (.C13).

        Nạp: tiêu chuẩn (EC2/ACI) + vật liệu, tiết diện bất kỳ (đa giác
        + vị trí thép thật, đi đúng đường như import DXF), chiều dài +
        điều kiện biên, và nội lực (mỗi load case -> 2 dòng đầu
        dưới/trên trong bảng ETABS ở mục 5).
        Ánh xạ trục: Prokon Mx -> M2 của app (EtabsForce.Mx), Prokon My
        -> M3 của app (EtabsForce.My) — vì app M2 ≡ mô men ΣσA·y như
        Prokon Mx, app M3 ≡ ΣσA·x như Prokon My. (Đã sửa 2026-10-21:
        trước đây ánh xạ ngược Mx<->My.)
        """
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(
            title="Chọn file Prokon General Column (.C13)",
            filetypes=[("Prokon", "*.C13"), ("All", "*.*")])
        if not path:
            return
        try:
            from rc_column.prokon_import import parse_prokon_c13
            data = parse_prokon_c13(path)
        except Exception as ex:
            messagebox.showerror("Lỗi đọc Prokon", str(ex))
            return
        code = data["design_code"]
        if code not in ("EC2", "ACI"):
            messagebox.showerror(
                "Import Prokon",
                f"Chưa hỗ trợ design code: {data['design_code_text']}")
            return
        warnings = list(data["warnings"])
        # --- Dựng tiết diện polygon (giống hệt đường import DXF) ---
        try:
            from rc_column.dxf_import import DxfSection, build_polygon_section
            from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                             ConcreteMaterial, SteelMaterial)
            dxf = DxfSection(outlines=[list(data["polygon"])],
                             rebars=list(data["rebars"]),
                             warnings=warnings)
            conc = ConcreteMaterial(
                CONCRETE_GRADES[self.cb_conc.get()], 1.0)
            steel = SteelMaterial(STEEL_GRADES[self.cb_steel.get()], 1.0)
            sec = build_polygon_section(dxf, conc, steel, fiber_step=10.0)
        except Exception as ex:
            messagebox.showerror("Lỗi dựng tiết diện Prokon", str(ex))
            return
        # Preview & xác nhận (dùng chung dialog với DXF)
        if not self._preview_dxf_section(sec, dxf, path):
            return
        # --- 1) Tiêu chuẩn + vật liệu ---
        if code == "EC2":
            self.cb_code.set("EC2 (EN 1992-1-1:2004)")
            self._toggle_code()
            from rc_column.ec2_materials import EC2_CONCRETE_GRADES
            _fck = data["fck"]
            _name = next(
                (k for k, v in EC2_CONCRETE_GRADES.items()
                 if abs(v - _fck) < 1e-6), None)
            if _name is None:
                _name = min(EC2_CONCRETE_GRADES,
                            key=lambda k: abs(EC2_CONCRETE_GRADES[k] - _fck))
                warnings.append(
                    f"fck={_fck:g} MPa không có lớp bê tông EC2 khớp — "
                    f"dùng tạm {_name}.")
            self.cb_ec2_conc.set(_name)
            for _en in (self.en_ec2_fyk, self.en_ec2_fyt):
                _en.delete(0, tk.END)
                _en.insert(0, f"{data['fy']:g}")
        else:  # ACI
            self.cb_code.set("ACI 318-19")
            self._toggle_code()
            for _en, _val in ((self.en_fc, data["fck"]),
                              (self.en_fy, data["fy"]),
                              (self.en_fyt, data["fy"])):
                _en.delete(0, tk.END)
                _en.insert(0, f"{_val:g}")
        # --- 2) Tiết diện ---
        self._dxf_section = sec
        self._dxf_path = path
        self.cb_kind.set("Tiết diện bất kỳ (DXF)")
        _fname = path.replace("\\", "/").split("/")[-1]
        self.dxf_info.set(
            f"Đã import Prokon: {_fname} — "
            f"Ag={sec.gross_area:.0f} mm², {len(sec.rebars)} thép, "
            f"As={sec.steel_area:.0f} mm²")
        # --- 3) Tên cấu kiện ---
        if data["title"]:
            self.member_var.set(data["title"])
        # --- 4) Chiều dài + điều kiện biên (cả 2 phương = L0) ---
        for _en in (self.en_Lx, self.en_Ly):
            _en.delete(0, tk.END)
            _en.insert(0, f"{data['L0']:g}")
        _end_map = {"fully fixed": "Ngàm cứng", "fixed": "Ngàm cứng",
                    "pinned": "Khớp", "hinged": "Khớp",
                    "partially fixed": "Ngàm nửa cứng",
                    "partial": "Ngàm nửa cứng", "free": "Tự do"}

        def _bc(txt, which):
            name = _end_map.get(str(txt).strip().lower())
            if name is None:
                warnings.append(
                    f"Điều kiện biên {which} của Prokon ('{txt}') chưa rõ "
                    "— dùng tạm 'Ngàm cứng'.")
                name = "Ngàm cứng"
            return name
        _bc_top = _bc(data["end_top"], "đầu trên")
        _bc_bot = _bc(data["end_bottom"], "đầu dưới")
        self.cb_tx.set(_bc_top)
        self.cb_ty.set(_bc_top)
        self.cb_bx.set(_bc_bot)
        self.cb_by.set(_bc_bot)
        try:
            self._auto_psi()
        except Exception:
            pass
        if data.get("beta") is not None:
            warnings.append(
                f"Hệ số chiều dài hiệu dụng của Prokon β={data['beta']:g}; "
                "app tự tính ψ/L0 từ chiều dài + điều kiện biên nên kết "
                "quả độ mảnh có thể lệch Prokon.")
        # --- 5) Nội lực -> bảng ETABS (mỗi case: Bottom + Top) ---
        from rc_column.etabs_import import EtabsForce
        forces = []
        for ld in data["loads"]:
            forces.append(EtabsForce(
                story=data["title"], column=data["label"],
                case=ld["name"], case_type="Combination",
                station=0.0, N=ld["P"],
                Mx=ld["Mx_bottom"], My=ld["My_bottom"],
                Q2=0.0, Q3=0.0))
            forces.append(EtabsForce(
                story=data["title"], column=data["label"],
                case=ld["name"], case_type="Combination",
                station=data["L0"], N=ld["P"],
                Mx=ld["Mx_top"], My=ld["My_top"],
                Q2=0.0, Q3=0.0))
        self.etabs_forces_orig = forces
        self.etabs_file = path
        self.var_load_mode.set("etabs")
        self._toggle_load_mode()
        self._refresh_merge_display()
        self.etabs_info.set(
            f"Đã import Prokon: {len(sec.rebars)} thanh thép, "
            f"{len(data['loads'])} tổ hợp ({code}) — "
            f"Bấm 'KIỂM TRA KHẢ NĂNG CHỊU LỰC' để tính.")
        self._refresh_rebar_panel()
        try:
            self._refresh_rebar()
        except Exception:
            pass
        if warnings:
            messagebox.showwarning("Cảnh báo import Prokon",
                                   "\n".join(warnings))

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
