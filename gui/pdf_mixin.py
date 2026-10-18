"""Các method xuất PDF (tóm tắt và chi tiết)."""



import tkinter as tk

import tkinter as tk
from tkinter import ttk, messagebox
import math
from rc_column.checker import ColumnInput, build_section, check_column
from rc_column.report import generate_report, generate_report_sections
from rc_column.materials import CONCRETE_GRADES, STEEL_GRADES
from rc_column.sections import clear_spacing, bar_area
from rc_column.stability import BOUNDARY_NAMES, LongTermLoads
from rc_column.lang import T
class PdfMixin:
    """Các method xuất PDF (tóm tắt và chi tiết)."""

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
                                   sec_img_path=_sec_png,
                                   shear_info=getattr(self, "_pdf_shear",
                                                      None))
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
            # Với PDF chi tiết: luôn vẽ biểu đồ mới từ dữ liệu EC2 hiện tại
            # (dùng mô men thiết kế MEd2/MEd3 từ _ec2_full, đã gồm bậc 2)
            if not is_summary:
                try:
                    from rc_column.ec2_pdf_summary import _ec2_charts_png
                    # _ec2_charts_png tự lấy M2_mag/M3_mag từ ec2_res
                    # (đã lưu trong _ec2_full, tương thích ngược qua _ec2_res)
                    print(f"[PDF] Vẽ biểu đồ EC2 mới cho chi tiết")
                    pngs = _ec2_charts_png(
                        self._ec2_sec, self._ec2_conc, self._ec2_steel,
                        self._ec2_res, self._ec2_inp)
                    print("[PDF] Vẽ biểu đồ EC2 mới: OK")
                except Exception as _ex:
                    print(f"[PDF] Vẽ biểu đồ EC2 mới lỗi: {_ex}")
            if is_summary:
                from rc_column.aci_pdf_summary import export_aci_summary_pdf
                export_aci_summary_pdf(
                    self._aci_sec, self._aci_inp, self._aci_res,
                    self._aci_conc, self._aci_steel, self._aci_tied, path,
                    case_info=getattr(self, "_pdf_case", None),
                    chart_pngs=pngs,
                    shear_info=getattr(self, "_aci_shear", None),
                    mm_res=getattr(self, "_aci_mm", None))
            else:
                from rc_column.aci_pdf_report import export_aci_pdf_cards
                export_aci_pdf_cards(
                    self._aci_inp, self._aci_res, self._aci_mm,
                    getattr(self, "_aci_shear", None),
                    self._aci_conc, self._aci_steel,
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
            # Với PDF chi tiết: luôn vẽ biểu đồ mới từ dữ liệu EC2 hiện tại
            # (dùng mô men thiết kế MEd2/MEd3 từ _ec2_full, đã gồm bậc 2)
            if not is_summary:
                try:
                    from rc_column.ec2_pdf_summary import _ec2_charts_png
                    # _ec2_charts_png tự lấy M2_mag/M3_mag từ ec2_res
                    # (đã lưu trong _ec2_full, tương thích ngược qua _ec2_res)
                    print(f"[PDF] Vẽ biểu đồ EC2 mới cho chi tiết")
                    pngs = _ec2_charts_png(
                        self._ec2_sec, self._ec2_conc, self._ec2_steel,
                        self._ec2_res, self._ec2_inp)
                    print("[PDF] Vẽ biểu đồ EC2 mới: OK")
                except Exception as _ex:
                    print(f"[PDF] Vẽ biểu đồ EC2 mới lỗi: {_ex}")
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

    def _embed_report_images(self, sec, inp, res):
        """(Không dùng nữa — giữ để tương thích, logic đã chuyển vào
        _render_report_sections.)"""
        pass

