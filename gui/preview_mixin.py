"""Live preview mặt cắt ở tab Kết quả (không cần CHECK).

Trước khi CHECK: hiển thị mặt cắt (khung, cốt thép, kích thước, mũi tên trục,
legend) nhưng KHÔNG có vùng bôi màu xanh.
Sau khi CHECK: render_result_tab/_redraw_old vẽ đè hình full có vùng nén.
Khi user sửa thép/kích thước: update ngay hình preview (vẫn không vùng nén).
"""

import math

from rc_column.checker import build_section
from rc_column.sections import clear_spacing

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
