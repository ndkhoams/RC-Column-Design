"""Thu thập dữ liệu nhập, chạy kiểm tra, lưu/mở dữ liệu (JSON).
Tách từ gui/app.py."""

import tkinter as tk
from tkinter import ttk, messagebox

from rc_column.checker import ColumnInput
from rc_column.cover_migration import (COVER_SEMANTICS_NEW,
                                       migrate_column_dict)
from rc_column.report import generate_report_sections
from rc_column.stability import BOUNDARY_NAMES, LongTermLoads


class DataMixin:
    """Các method dữ liệu: collect input, CHECK, save/load."""

    # ============================ Logic ============================
    def _f(self, entry, default=0.0):
        try:
            return float(entry.get().strip().replace(",", "."))
        except Exception:
            return default

    def _bkey(self, combo):
        inv = {v: k for k, v in BOUNDARY_NAMES.items()}
        return inv.get(combo.get(), "khop")

    def _draft_input(self) -> ColumnInput:
        """Dựng input nháp (chưa cần nội lực) để vẽ sơ đồ & thống kê thép."""
        is_dxf = self.cb_kind.get().startswith("Tiết diện bất kỳ")
        is_rect = self.cb_kind.get() == "Chữ nhật"
        model = "3line" if self.cb_model.get().startswith("3") else "2line"

        def _gi(sp, default=0):
            try:
                return int(float(sp.get()))
            except Exception:
                return default

        def _gd(cb, default=20.0):
            try:
                return float(cb.get())
            except Exception:
                return default

        if is_rect:
            e2n = max(0, _gi(self.sp_e2n, 3)); e2d = _gd(self.cb_e2d, 20.0)
            e3n = max(0, _gi(self.sp_e3n, 3)); e3d = _gd(self.cb_e3d, 20.0)
            cover = self._f(self.sp_cover, 30.0)
            corner_dia = _gd(self.cb_corner_dia, 20.0)
        else:
            e2n, e2d, e3n, e3d = 0, 20.0, 0, 20.0
            cover = self._f(self.sp_ccover, 30.0)
            corner_dia = _gd(self.cb_cdia, 20.0)
        l2_side_txt = self.cb_l2_side.get()
        bundle_txt = self.cb_bundle_pos.get()
        # Tiết diện tròn: đường kính D dùng cho cả 2 chiều
        _dia = self._f(self.en_dia, 600.0)
        _cx = self._f(self.en_cx, 400.0) if is_rect else _dia
        _cy = self._f(self.en_cy, 400.0) if is_rect else _dia
        inp = ColumnInput(
            concrete_grade=self.cb_conc.get(), gamma_b=self._f(self.en_gb, 0.85),
            steel_grade=self.cb_steel.get(),
            sw_steel_grade=self.cb_sw_steel.get(),
            gamma_s=self._f(self.en_gs, 1.0),
            concrete_model=model,
            section_type="poly" if is_dxf else ("rect" if is_rect else "circle"),
            cx=_cx, cy=_cy,
            bar_dia=_gd(self.cb_cdia, 20.0),
            nx=e3n + 2, ny=e2n + 2,  # giữ tương thích (số thanh mỗi cạnh kể cả góc)
            n_bars=max(4, _gi(self.sp_cnbars, 8)),
            cover=cover,
            corner_dia=corner_dia,
            edge_t2_count=e2n, edge_t2_dia=e2d,
            edge_t3_count=e3n, edge_t3_dia=e3d,
            two_layer=bool(self.var_two_layer.get()),
            layer2_mode=self.var_l2mode.get(),
            l2_t2_dia=_gd(self.cb_l2_t2d, 20.0),
            l2_t3_dia=_gd(self.cb_l2_t3d, 20.0),
            l2_s_layer=self._f(self.en_l2_s, 30.0),
            l2_side="t2" if l2_side_txt.startswith("Cạnh t2") else "t3",
            l2_count=max(1, _gi(self.sp_l2_count, 5)),
            l2_dia=_gd(self.cb_l2_dia, 25.0),
            bundle_pos="inner" if bundle_txt.startswith("Lớp trong") else "outer",
            bundle_size=max(1, _gi(self.sp_bundle_size, 2)),
            bundle_corner=max(1, _gi(self.sp_bundle_corner, 2)),
            bundle_gap=self._f(self.en_bundle_gap, 0.0),
            sw_dia=self._f(self.en_sw_dia, 8.0),
            sw_spacing=self._f(self.en_sw_s, 200.0),
            sw_legs=max(2, int(self._f(self.en_sw_legs, 2))),
            swm2_dia=self._f(self.sw_inputs["Đai giữa t2:"]["dia"], 8.0),
            swm2_spacing=self._f(self.sw_inputs["Đai giữa t2:"]["s"], 200.0),
            swm2_legs=int(self._f(self.sw_inputs["Đai giữa t2:"]["legs"], 0)),
            swm3_dia=self._f(self.sw_inputs["Đai giữa t3:"]["dia"], 8.0),
            swm3_spacing=self._f(self.sw_inputs["Đai giữa t3:"]["s"], 200.0),
            swm3_legs=int(self._f(self.sw_inputs["Đai giữa t3:"]["legs"], 0)),
        )
        if is_dxf:
            inp.poly_section = getattr(self, "_dxf_section", None)
        return inp

    def collect(self) -> ColumnInput:
        inp = self._draft_input()
        def opt(e):
            t = e.get().strip()
            return float(t.replace(",", ".")) if t else None
        inp.Lx = self._f(self.en_Lx, 4.0); inp.Ly = self._f(self.en_Ly, 4.0)
        inp.top_x = self._bkey(self.cb_tx); inp.bottom_x = self._bkey(self.cb_bx)
        inp.top_y = self._bkey(self.cb_ty); inp.bottom_y = self._bkey(self.cb_by)
        inp.psi_x = opt(self.en_psix); inp.psi_y = opt(self.en_psiy)
        inp.N = self._f(self.en_N); inp.Mx = self._f(self.en_Mx)
        inp.My = self._f(self.en_My)
        inp.Q2 = self._f(self.en_Q2); inp.Q3 = self._f(self.en_Q3)
        inp.long_term = LongTermLoads(
            has_data=self.var_lt.get(), N_lt=self._f(self.en_Nlt),
            Mx_lt=self._f(self.en_Mxlt), My_lt=self._f(self.en_Mylt))
        return inp

    def on_check(self):
        # Khóa nút CHECK + con trỏ bận trong lúc tính: tránh bấm đúp và
        # cho user biết app đang chạy (tính chạy trên UI thread; batch
        # bơm sự kiện qua _batch_pump trong etabs_mixin).
        btn = getattr(self, "btn_check", None)
        try:
            if btn is not None:
                btn.config(state="disabled")
            self.config(cursor="watch")
            self.update_idletasks()
        except Exception:
            pass
        try:
            self._on_check_impl()
        finally:
            try:
                if btn is not None:
                    btn.config(state="normal")
                self.config(cursor="")
            except Exception:
                pass

    def _on_check_impl(self):
        # Chế độ Vách (GĐ1 lát 0): chưa có engine — báo rõ chưa hỗ trợ,
        # KHÔNG chạy engine cột cho dữ liệu vách
        if getattr(self, "cb_member", None) is not None \
                and self.cb_member.get() == "Vách":
            self._on_check_wall()
            return
        # Chế độ ETABS: kiểm tra tất cả tổ hợp
        if self.var_load_mode.get() == "etabs":
            self.on_check_etabs()
            return
        # Chế độ nhập tay: kiểm tra 1 bộ nội lực
        try:
            inp = self.collect()
            if self.is_ec2():
                self._check_ec2(inp)
                return
            if self.is_aci():
                self._check_aci(inp)
                return
            # TÍNH 1 LẦN: gọi hàm tính đầy đủ (không tính lại ở nơi khác)
            _full = self._tcvn_calculate_full(inp, n_angles=24)
            res = _full["res"]
            sec = _full["sec"]
            # Lưu full dict để tab/PDF chỉ đọc hiển thị
            self._tcvn_full = _full
        except Exception as ex:
            messagebox.showerror("Lỗi", str(ex))
            return
        # Tóm tắt + biểu đồ + L0 (chỉ đọc từ _full, không tính lại)
        self._show_summary(sec, inp, res)
        # Thuyết minh (chỉ đọc từ _full): TRÌ HOÃN render (lazy) tới
        # khi user mở tab Chi tiết — không dựng widget/hình ngay trong CHECK
        _secs_t = generate_report_sections(inp, res)
        self._defer_detail(lambda _s=_secs_t: self._render_report_sections(
            _s, sec, inp, res, case_info=None, shear_info=None))
        self._pdf_inp, self._pdf_res = inp, res
        # Lưu shear đã tính để PDF chỉ đọc hiển thị (nguyên tắc "tính 1 lần")
        self._pdf_shear = _full.get("shear_cols")

    def _collect_data(self) -> dict:
        """Thu thập toàn bộ dữ liệu nhập liệu thành dict."""
        def ev(e):
            return e.get()
        def bv(v):
            return v.get()
        return {
            "version": 1,
            # Dấu ngữ nghĩa cover: file do app mới lưu đã theo quy ước
            # c_đai (xem rc_column/cover_migration) — mở lại không dịch
            # nữa. File cũ thiếu khóa này sẽ được dịch khi mở.
            "cover_semantics": COVER_SEMANTICS_NEW,
            # Loại cấu kiện (khóa cộng thêm; file cũ thiếu -> hiểu là "column")
            "member_type": "wall" if (getattr(self, "cb_member", None) is not None
                                      and self.cb_member.get() == "Vách") else "column",
            # Tên cấu kiện
            "member_name": self.member_var.get().strip() if hasattr(self, "member_var") else "",
            # 1. Vật liệu
            "concrete": self.cb_conc.get(), "gamma_b": ev(self.en_gb),
            "steel": self.cb_steel.get(), "sw_steel": self.cb_sw_steel.get(),
            "gamma_s": ev(self.en_gs),
            "model": self.cb_model.get(),
            # 1b. Vật liệu ACI
            "code": self.cb_code.get(),
            "aci_fc": ev(self.en_fc), "aci_fy": ev(self.en_fy),
            "aci_fyt": ev(self.en_fyt), "aci_tie": self.cb_tie.get(),
            # 1c. Vật liệu EC2
            "ec2_conc": self.cb_ec2_conc.get(),
            "ec2_steel": ev(self.en_ec2_fyk),
            "ec2_method": self.cb_ec2_method.get(),
            "ec2_fyt": ev(self.en_ec2_fyt),
            "ec2_phi": ev(self.en_ec2_phi),
            # 2. Tiết diện
            "kind": self.cb_kind.get(),
            "cx": ev(self.en_cx), "cy": ev(self.en_cy),
            "dia": ev(self.en_dia) or "600",
            "cover": self.sp_cover.get(),
            # 3. Cốt thép dọc (kiểu VietconSoft)
            "corner_dia": self.cb_corner_dia.get(),
            "e2n": self.sp_e2n.get(), "e2d": self.cb_e2d.get(),
            "e3n": self.sp_e3n.get(), "e3d": self.cb_e3d.get(),
            "two_layer": bv(self.var_two_layer),
            "l2mode": self.var_l2mode.get(),
            "l2_t2d": self.cb_l2_t2d.get(), "l2_t3d": self.cb_l2_t3d.get(),
            "l2_s": ev(self.en_l2_s), "l2_side": self.cb_l2_side.get(),
            "l2_count": self.sp_l2_count.get(),
            "l2_dia": self.cb_l2_dia.get(),
            "bundle_pos": self.cb_bundle_pos.get(),
            "bundle_size": self.sp_bundle_size.get(),
            "bundle_corner": self.sp_bundle_corner.get(),
            "bundle_gap": ev(self.en_bundle_gap),
            # tròn
            "cdia": self.cb_cdia.get(), "cnbars": self.sp_cnbars.get(),
            "ccover": self.sp_ccover.get(),
            "nx": str(int(float(self.sp_e3n.get() or 0)) + 2),
            "ny": str(int(float(self.sp_e2n.get() or 0)) + 2),
            # đai
            "sw_dia": ev(self.en_sw_dia), "sw_s": ev(self.en_sw_s),
            "sw_legs": ev(self.en_sw_legs),
            "swm2_dia": ev(self.sw_inputs["Đai giữa t2:"]["dia"]),
            "swm2_s": ev(self.sw_inputs["Đai giữa t2:"]["s"]),
            "swm2_legs": ev(self.sw_inputs["Đai giữa t2:"]["legs"]),
            "swm3_dia": ev(self.sw_inputs["Đai giữa t3:"]["dia"]),
            "swm3_s": ev(self.sw_inputs["Đai giữa t3:"]["s"]),
            "swm3_legs": ev(self.sw_inputs["Đai giữa t3:"]["legs"]),
            # 4. Chiều dài tính toán
            "Lx": ev(self.en_Lx), "Ly": ev(self.en_Ly),
            "top_x": self.cb_tx.get(), "bot_x": self.cb_bx.get(),
            "top_y": self.cb_ty.get(), "bot_y": self.cb_by.get(),
            "psi_x": ev(self.en_psix), "psi_y": ev(self.en_psiy),
            # 5. Nội lực
            "load_mode": bv(self.var_load_mode),
            "N": ev(self.en_N), "Mx": ev(self.en_Mx), "My": ev(self.en_My),
            "Q2": ev(self.en_Q2), "Q3": ev(self.en_Q3),
            "long_term": bv(self.var_lt),
            "N_lt": ev(self.en_Nlt), "Mx_lt": ev(self.en_Mxlt),
            "My_lt": ev(self.en_Mylt),
            "etabs_path": getattr(self, "etabs_file", ""),
            "etabs_comb": True,
            # Lưu luôn nội lực đã import (không cần link lại file Excel).
            # LƯU DỮ LIỆU GỐC (không phải bảng hiển thị đang gộp) +
            # lựa chọn gộp + trạng thái nút chọn — mở lại khôi phục
            # đúng dạng gộp. File cũ không có 2 khóa mới -> mở lên
            # nút chọn TẮT, bảng như cũ (tương thích ngược).
            "etabs_forces": [
                {"story": f.story, "column": f.column, "case": f.case,
                 "case_type": f.case_type, "station": f.station,
                 "N": f.N, "Mx": f.Mx, "My": f.My,
                 "Q2": f.Q2, "Q3": f.Q3}
                for f in (getattr(self, "etabs_forces_orig", None)
                          or getattr(self, "etabs_forces", []))
            ],
            "merge_combo_enabled": bool(
                getattr(self, "merge_combo_var", None) is not None
                and self.merge_combo_var.get()),
            "merge_combo_selected": sorted(
                getattr(self, "merge_combo_selected", set()) or set()),
            # Vách (GĐ1): namespace riêng, ghi cả khi đang ở chế độ Cột để
            # chuyển qua lại không mất dữ liệu (như 3 bộ vật liệu hiện tại).
            # pier_forces: parser/batch ở lát 5; lát 0 giữ nguyên dữ liệu
            # thô đã nạp (nếu có) để không làm mất khi lưu lại.
            "wall": self._collect_wall() if hasattr(self, "w_en_Lw") else {},
            "pier_forces": getattr(self, "_pier_forces_raw", []),
        }

    def _apply_data(self, d: dict):
        """Đổ dữ liệu từ dict vào các trường nhập liệu."""
        def se(e, v):
            e.delete(0, tk.END); e.insert(0, str(v))
        try:
            # Migration cover (file cũ lưu theo nghĩa tới mặt cốt dọc):
            # dịch cover/ccover sang c_đai (c − sw_dia) TRONG BỘ NHỚ —
            # không ghi đè file chỉ vì mở; bỏ qua file DXF; kẹp 0 +
            # cảnh báo (xem cover_migration) hiện ở cuối hàm.
            d, _cover_warns = migrate_column_dict(d)
            # Tên cấu kiện (ưu tiên từ JSON, fallback tên file ở on_load_data)
            _mn = d.get("member_name", "")
            if _mn and hasattr(self, "member_var"):
                self.member_var.set(_mn)
            self.cb_conc.set(d.get("concrete", "B25")); se(self.en_gb, d.get("gamma_b", "0.85"))
            self.cb_steel.set(d.get("steel", "CB400-V"))
            self.cb_sw_steel.set(d.get("sw_steel", "CB400-V"))
            se(self.en_gs, d.get("gamma_s", "1.0"))
            self.cb_model.set(d.get("model", self.cb_model.get()))
            # Vật liệu ACI (tương thích file cũ: giữ mặc định nếu thiếu)
            _code = d.get("code", self.cb_code.get())
            if _code == "EC2 (EN 1992-1-1)":  # file cu: chuan hoa nhan
                _code = "EC2 (EN 1992-1-1:2004)"
            self.cb_code.set(_code)
            se(self.en_fc, d.get("aci_fc", "30")); se(self.en_fy, d.get("aci_fy", "420"))
            se(self.en_fyt, d.get("aci_fyt", "420"))
            self.cb_tie.set(d.get("aci_tie", "Đai rời (tied)"))
            # Vật liệu EC2 (tương thích file cũ: giữ mặc định nếu thiếu)
            self.cb_ec2_conc.set(d.get("ec2_conc", "C30/37"))
            se(self.en_ec2_fyk, d.get("ec2_steel", "500"))
            self.cb_ec2_method.set(d.get("ec2_method", "Độ cứng danh nghĩa"))
            se(self.en_ec2_phi, d.get("ec2_phi", "2.0"))
            se(self.en_ec2_fyt, d.get("ec2_fyt", "500"))
            self._toggle_code()
            # Loại cấu kiện + dữ liệu vách (file cũ thiếu khóa -> Cột)
            if hasattr(self, "cb_member"):
                self.cb_member.set(
                    "Vách" if d.get("member_type") == "wall" else "Cột")
                self._apply_wall(d.get("wall") or {})
                self._toggle_member()
            self._pier_forces_raw = d.get("pier_forces") or []
            self.cb_kind.set(d.get("kind", "Chữ nhật"))
            se(self.en_cx, d.get("cx", "400")); se(self.en_cy, d.get("cy", "400"))
            se(self.en_dia, d.get("dia", "600") or "600")
            se(self.sp_cover, d.get("cover", "30"))
            # Cốt thép dọc kiểu mới (fallback về field cũ nếu file cũ)
            se(self.cb_corner_dia, d.get("corner_dia", d.get("dia", "20")))
            se(self.sp_e2n, d.get("e2n", str(max(0, int(d.get("ny", 3)) - 2))))
            se(self.cb_e2d, d.get("e2d", d.get("dia", "20")))
            se(self.sp_e3n, d.get("e3n", str(max(0, int(d.get("nx", 3)) - 2))))
            se(self.cb_e3d, d.get("e3d", d.get("dia", "20")))
            self.var_two_layer.set(bool(d.get("two_layer", False)))
            self._set_l2mode(d.get("l2mode", "perimeter"))
            self.cb_l2_t2d.set(d.get("l2_t2d", "20"))
            self.cb_l2_t3d.set(d.get("l2_t3d", "20"))
            se(self.en_l2_s, d.get("l2_s", "30"))
            self.cb_l2_side.set(d.get("l2_side", "Cạnh t2 (trái/phải)"))
            self.sp_l2_count.set(d.get("l2_count", "5"))
            self.cb_l2_dia.set(d.get("l2_dia", "25"))
            self.cb_bundle_pos.set(d.get("bundle_pos", "Lớp trong"))
            self.sp_bundle_size.set(d.get("bundle_size", "2"))
            self.sp_bundle_corner.set(d.get("bundle_corner", "2"))
            se(self.en_bundle_gap, d.get("bundle_gap", "0"))
            self.cb_cdia.set(d.get("cdia", d.get("dia", "20")))
            self.sp_cnbars.set(d.get("cnbars", "8"))
            self.sp_ccover.set(d.get("ccover", d.get("cover", "30")))
            self._toggle_two_layer()
            self._refresh_rebar_panel()
            se(self.en_sw_dia, d.get("sw_dia", "8"))
            for lbl, pfx in (("Đai giữa t2:", "swm2"), ("Đai giữa t3:", "swm3")):
                se(self.sw_inputs[lbl]["dia"], d.get(f"{pfx}_dia", "8"))
                se(self.sw_inputs[lbl]["s"], d.get(f"{pfx}_s", "200"))
                se(self.sw_inputs[lbl]["legs"], d.get(f"{pfx}_legs", "2"))
            se(self.en_sw_s, d.get("sw_s", "200"))
            se(self.en_sw_legs, d.get("sw_legs", "2"))
            se(self.en_Lx, d.get("Lx", "4.0")); se(self.en_Ly, d.get("Ly", "4.0"))
            self.cb_tx.set(d.get("top_x", "Ngàm nửa cứng")); self.cb_bx.set(d.get("bot_x", "Ngàm nửa cứng"))
            self.cb_ty.set(d.get("top_y", "Ngàm nửa cứng")); self.cb_by.set(d.get("bot_y", "Ngàm nửa cứng"))
            se(self.en_psix, d.get("psi_x", "")); se(self.en_psiy, d.get("psi_y", ""))
            self.var_load_mode.set(d.get("load_mode", "etabs"))
            se(self.en_N, d.get("N", "")); se(self.en_Mx, d.get("Mx", ""))
            se(self.en_My, d.get("My", ""))
            se(self.en_Q2, d.get("Q2", "0")); se(self.en_Q3, d.get("Q3", "0"))
            self.var_lt.set(bool(d.get("long_term", False)))
            se(self.en_Nlt, d.get("N_lt", "")); se(self.en_Mxlt, d.get("Mx_lt", ""))
            se(self.en_Mylt, d.get("My_lt", ""))

            self.etabs_file = d.get("etabs_path", "")
            # cập nhật giao diện theo chế độ
            self._toggle_load_mode()
            self._toggle_lt()
            self._refresh_rebar()
            # Cảnh báo migration cover (nếu c_mới bị kẹp về 0 — hình
            # học cũ phi thực tế, user cần kiểm tra lại ô cover/đai).
            for _w in _cover_warns:
                messagebox.showwarning("Lớp bảo vệ (migration file cũ)", _w)
        except Exception as ex:
            messagebox.showerror("Lỗi", f"Không đọc được file dữ liệu: {ex}")

    def _do_save(self, path: str) -> bool:
        """Ghi dữ liệu ra file JSON. Trả về True nếu thành công."""
        import json
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._collect_data(), f, ensure_ascii=False,
                          indent=2)
            self.current_save_path = path
            return True
        except Exception as ex:
            messagebox.showerror("Lỗi", str(ex))
            return False

    def on_save_data(self):
        """SAVE: lần đầu mở hộp thoại, lần sau ghi đè file đang mở."""
        import os
        from tkinter import filedialog
        path = self.current_save_path
        if not path or not os.path.exists(path):
            _mn = self.member_var.get().strip() if hasattr(self, "member_var") else ""
            _init = f"{_mn}.json" if _mn else "CotBTCT.json"
            path = filedialog.asksaveasfilename(
                title="Lưu dữ liệu cột",
                defaultextension=".json",
                filetypes=[("JSON", "*.json")],
                initialfile=_init)
            if not path:
                return
        if self._do_save(path):
            self._update_title()
            messagebox.showinfo("Lưu dữ liệu", f"Đã lưu: {path}")

    def _update_ck(self):
        """Cập nhật tên cấu kiện (IN HOA) từ textbox - thay thế tên file."""
        ck = getattr(self, "ck_var", None)
        if ck is None:
            return
        mv = getattr(self, "member_var", None)
        name = mv.get().strip().upper() if mv else ""
        if name:
            ck.set(f"Cấu kiện: {name}")
        else:
            ck.set("")

    def on_save_as_data(self):
        """SAVE AS: luôn mở hộp thoại chọn file mới."""
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            title="Lưu dữ liệu cột (Save As)",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="CotBTCT.json")
        if not path:
            return
        if self._do_save(path):
            self._update_title()
            messagebox.showinfo("Lưu dữ liệu", f"Đã lưu: {path}")

    def on_load_data(self):
        """Mở file dữ liệu JSON đã lưu."""
        import json
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Mở dữ liệu cột",
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            # Cờ chặn preset ca mẫu web của chế độ Vách: mở file thì
            # giá trị trong file thắng tuyệt đối — không preset nào
            # được áp/gỡ trong lúc nạp (xem gui/wall_mixin.py).
            self._applying_data = True
            try:
                self._apply_data(d)
            finally:
                self._applying_data = False
            self._data_loaded = True
            # Đã có file: preset vách (nếu từng áp) hết hiệu lực —
            # trạng thái từ nay do file/user quyết định.
            self._wall_preset_stash = None
            # Khôi phục nội lực đã lưu trong file (không cần file Excel):
            # nạp vào dữ liệu GỐC, khôi phục lựa chọn + trạng thái nút
            # chọn gộp, rồi suy ra lại bảng hiển thị (file cũ không có
            # 2 khóa mới -> nút TẮT, bảng = gốc như trước).
            forces_data = d.get("etabs_forces", [])
            if d.get("load_mode") == "etabs":
                from rc_column.etabs_import import EtabsForce
                self.etabs_forces_orig = [EtabsForce(**fd)
                                          for fd in forces_data]
                mv = getattr(self, "merge_combo_var", None)
                if mv is not None:
                    mv.set(bool(d.get("merge_combo_enabled", False)))
                self.merge_combo_selected = set(
                    d.get("merge_combo_selected", []) or [])
                self._refresh_merge_display()
                if self.etabs_forces_orig:
                    n_case = len(set(f.case
                                     for f in self.etabs_forces_orig))
                    self.etabs_info.set(
                        f"Đã nạp {len(self.etabs_forces_orig)} dòng, "
                        f"{n_case} tổ hợp từ file dữ liệu — Bấm 'KIỂM "
                        f"TRA KHẢ NĂNG CHỊU LỰC' để tính.")
            self.current_save_path = path
            self._update_title()
            # Điền tên file vào textbox nếu JSON chưa có tên cấu kiện
            import os as _os
            if hasattr(self, "member_var") and not self.member_var.get().strip():
                _mn = _os.path.splitext(_os.path.basename(path))[0].upper()
                self.member_var.set(_mn)
            self._update_ck()
            # Tự động tính toán sau khi mở file
            try:
                self.on_check()
            except Exception:
                pass
        except Exception as ex:
            messagebox.showerror("Lỗi", str(ex))
