"""Live preview mặt cắt ở tab Kết quả (không cần CHECK).

Trước khi CHECK: hiển thị mặt cắt (khung, cốt thép, kích thước, mũi tên trục,
legend) nhưng KHÔNG có vùng bôi màu xanh.
Sau khi CHECK: render_result_tab/_redraw_old vẽ đè hình full có vùng nén.
Khi user sửa thép/kích thước: update ngay hình preview (vẫn không vùng nén).
"""

import math
import tkinter as tk

from rc_column.checker import build_section
from rc_column.sections import clear_spacing

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MPL = True
except Exception:
    HAS_MPL = False


def _build_section_from_inputs(app):
    """Build Section từ input GUI hiện tại. Trả về None nếu không hợp lệ."""
    try:
        from rc_column.checker import build_section
        inp = app.collect()
        sec = build_section(inp)
        _cx = getattr(sec, "cx", 0) or 0
        _cy = getattr(sec, "cy", 0) or 0
        if _cx <= 0 or _cy <= 0:
            return None
        if not getattr(sec, "rebars", None):
            return None
        return sec
    except Exception:
        return None


def draw_section_preview(app):
    """Vẽ preview mặt cắt (KHÔNG vùng nén) vào tab Kết quả."""
    if not HAS_MPL:
        return
    try:
        from rc_column.pdf_export import draw_compression_zone_ax
        sec = _build_section_from_inputs(app)
        if sec is None:
            return
        # Lấy figure hiện có (sau CHECK) hoặc tạo mới
        ax = getattr(app, "_sec_ax", None)
        cv = getattr(app, "_sec_cv", None) or getattr(app, "_sec_canvas", None)
        fig = getattr(app, "_sec_fig", None)
        try:
            _valid = ax is not None and cv is not None and fig is not None
            if _valid:
                _w = cv.get_tk_widget()
                _valid = bool(_w.winfo_exists())
        except Exception:
            _valid = False
        if not _valid:
            create_preview_layout(app, sec)
            return
        # Vẽ lại vào axes hiện có (không vùng nén)
        ax.clear()
        draw_compression_zone_ax(ax, sec, N_kN=0, M2_kNm=0, M3_kNm=0,
                                   show_compression=False)
        try:
            fig.tight_layout()
        except Exception:
            pass
        cv.draw()
    except Exception:
        pass  # Không crash khi input chưa hợp lệ


def create_preview_layout(app, sec):
    """Tạo layout preview đơn giản (chỉ hình mặt cắt) cho tab Kết quả."""
    if not HAS_MPL:
        return
    try:
        from rc_column.pdf_export import draw_compression_zone_ax
        # Xóa nội dung cũ
        for w in app._sum_inner.winfo_children():
            w.destroy()
        app._sum_inner.columnconfigure(0, weight=1)
        app._sum_inner.rowconfigure(0, weight=1)
        f = tk.Frame(app._sum_inner, bg="white",
                     highlightbackground="#D1D5DB", highlightcolor="#D1D5DB",
                     highlightthickness=1, takefocus=0)
        f.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        tk.Label(f, text="MẶT CẮT TIẾT DIỆN",
                 font=("", 11, "bold"), bg="white").pack(pady=(2, 2))
        fig = Figure(figsize=(3.9, 3.1), dpi=100)
        cv = FigureCanvasTkAgg(fig, master=f)
        _w = cv.get_tk_widget()
        try:
            _w.configure(highlightthickness=0, takefocus=0, borderwidth=0)
        except Exception:
            pass
        _w.pack(fill=tk.BOTH, expand=True)
        ax = fig.add_subplot(111)
        draw_compression_zone_ax(ax, sec, N_kN=0, M2_kNm=0, M3_kNm=0,
                                   show_compression=False)
        try:
            fig.tight_layout()
        except Exception:
            pass
        cv.draw()
        app._sec_fig = fig
        app._sec_ax = ax
        app._sec_cv = cv
        app._sec_canvas = cv
    except Exception:
        pass


def setup_section_preview(app):
    """Bind sự kiện thay đổi input để live preview mặt cắt.

    Gọi một lần sau khi App được tạo (trong main.py).
    """
    app._preview_after = None

    def _schedule(event=None):
        try:
            if getattr(app, "_preview_after", None):
                app.after_cancel(app._preview_after)
        except Exception:
            pass
        try:
            app._preview_after = app.after(300, lambda: draw_section_preview(app))
        except Exception:
            pass

    # Các widget ảnh hưởng hình mặt cắt
    _attrs = ["en_cx", "en_cy", "en_dia",
              "sp_cover", "sp_ccover",
              "cb_corner_dia", "sp_e2n", "cb_e2d", "sp_e3n", "cb_e3d",
              "cb_cdia", "sp_cnbars",
              "cb_l2_t2d", "cb_l2_t3d"]
    for _a in _attrs:
        _w = getattr(app, _a, None)
        if _w is None:
            continue
        try:
            _w.bind("<KeyRelease>", _schedule)
            _w.bind("<FocusOut>", _schedule)
        except Exception:
            pass
    # Combobox: bind khi chọn giá trị
    for _a in ["cb_cdia", "cb_sec_type", "cb_l2_t2d", "cb_l2_t3d",
               "cb_corner_dia", "cb_e2d", "cb_e3d"]:
        _w = getattr(app, _a, None)
        if _w is None:
            continue
        try:
            _w.bind("<<ComboboxSelected>>", _schedule)
        except Exception:
            pass
    # Vẽ preview ban đầu
    try:
        app.after(600, lambda: draw_section_preview(app))
    except Exception:
        pass


class PreviewMixin:
    """Các method live preview mặt cắt ở tab Kết quả (tách từ gui/app.py)."""

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

    def _redraw_tcvn_section(self):
        """Vẽ lại hình mặt cắt TCVN theo checkbox 'Hiển thị vùng nén'."""
        try:
            a1 = getattr(self, "_sec_ax", None)
            data = getattr(self, "_tcvn_sec_data", None)
            if a1 is None or data is None:
                return
            from rc_column.pdf_export import draw_compression_zone_ax
            sec, _tBN, _tBx, _tBy, _tNmax, _t_na = data
            a1.clear()
            _sc = bool(self._show_compression.get())
            draw_compression_zone_ax(a1, sec, N_kN=_tBN, M2_kNm=_tBx, M3_kNm=_tBy,
                                     Nmax_kN=_tNmax, na_info=_t_na,
                                     show_compression=_sc)
            try:
                self._sec_fig.tight_layout()
            except Exception:
                pass
            try:
                self._sec_canvas.draw()
            except Exception:
                pass
        except Exception:
            pass

    def _live_update_section(self, sec, inp):
        """Vẽ lại sơ đồ mặt cắt + thẻ thống kê khi đổi nhập liệu."""
        ax1 = getattr(self, "_sec_ax", None)
        if ax1 is None:
            return
        try:
            from rc_column.pdf_export import draw_compression_zone_ax
            ax1.clear()
            draw_compression_zone_ax(ax1, sec, N_kN=0, M2_kNm=0, M3_kNm=0,
                                     show_compression=False)
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
