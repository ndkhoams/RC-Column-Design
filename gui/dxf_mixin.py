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
