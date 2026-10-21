"""Chế độ Vách (GĐ1 — lát 0: khung + plumbing; lát 1: N–M TCVN).

Gồm: frame nhập liệu vách (mục 2 khi ở chế độ Vách), chuyển đổi loại
cấu kiện Cột <-> Vách (_toggle_member), thu/áp dữ liệu vách cho JSON
(_collect_wall/_apply_wall), và điều phối CHECK ở chế độ Vách.

Lát 1: CHECK tay theo TCVN chạy engine vách (rc_column/wall_engine)
qua hàm duy nhất _tcvn_wall_calculate_full, kết quả lưu ở
self._tcvn_wall_full và hiển thị ở tab Kết quả/Chi tiết từ đúng dict
đó. ACI/EC2 vách (lát 2), batch Pier Forces (lát 5) và PDF vách
(lát 6) vẫn báo rõ chưa hỗ trợ — tuyệt đối không chạy engine cột cho
dữ liệu vách. Thiết kế: THIET_KE_TICH_HOP_VACH_GD1.md §2, §6, §8.
"""

import math
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MPL = True
except Exception:
    HAS_MPL = False

from rc_column.lang import T
from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_input import WALL_DEFAULTS, wall_from_dict
from rc_column.wall_section import build_wall_section

_DIAS = ["10", "12", "14", "16", "18", "20", "22", "25", "28", "32"]
_STORY_POS = [("base", "Chân vách"), ("mid", "Đốt giữa"), ("top", "Đốt trên")]
_L0_OPTS = [("Khớp – Khớp (hệ số 1.0)", 1.0),
            ("Ngàm – Khớp (hệ số 0.7)", 0.7),
            ("Ngàm – Ngàm (hệ số 0.5)", 0.5),
            ("Ngàm – Tự do (hệ số 2.0)", 2.0)]
_ACI_CLASS = [("special", "Đặc biệt (Ch.18)"), ("ordinary", "Thường (Ch.11)")]


def _code_of(pairs, label, default):
    for code, lab in pairs:
        if lab == label:
            return code
    return default


def _label_of(pairs, code, default_label):
    for c, lab in pairs:
        if c == code:
            return lab
    return default_label


def _l0_label(factor):
    for lab, fac in _L0_OPTS:
        if abs(fac - factor) < 1e-9:
            return lab
    return _L0_OPTS[0][0]


class WallMixin:
    """Các method của chế độ Vách: frame nhập, toggle, JSON, chặn lát 0."""

    # ---------------- Nhận diện chế độ ----------------
    def is_wall(self):
        cb = getattr(self, "cb_member", None)
        return cb is not None and cb.get() == "Vách"

    # ---------------- Frame nhập liệu vách ----------------
    def _sec_wall(self):
        """Dựng frame '2. Vách — tiết diện & cốt thép' (ẩn ở chế độ Cột)."""
        f = self._frame(T("2. Vách — tiết diện & cốt thép"))
        self.frm_wall = f
        r = 0

        def _hdr(text):
            nonlocal r
            ttk.Label(f, text=text, font=("", 10, "bold")).grid(
                row=r, column=0, columnspan=2, sticky=tk.W,
                padx=4, pady=(8, 2))
            r += 1

        def _entry(default):
            e = ttk.Entry(f, width=12)
            e.insert(0, str(default))
            return e

        def _combo(values, default):
            cb = ttk.Combobox(f, values=values, state="readonly", width=16)
            cb.set(str(default))
            return cb

        D = WALL_DEFAULTS
        # --- Hình học ---
        _hdr("Hình học")
        self.w_en_Lw = _entry(D["Lw"])
        self._row(f, "Chiều dài vách Lw (mm)", self.w_en_Lw, r); r += 1
        self.w_en_tw = _entry(D["tw"])
        self._row(f, "Chiều dày vách tw (mm)", self.w_en_tw, r); r += 1
        self.w_en_hstory = _entry(D["h_story"])
        self._row(f, "Chiều cao đốt (mm)", self.w_en_hstory, r); r += 1
        self.w_en_htotal = _entry(D["h_total"])
        self._row(f, "Tổng chiều cao vách (mm)", self.w_en_htotal, r); r += 1
        self.w_cb_pos = _combo([lab for _, lab in _STORY_POS],
                               _label_of(_STORY_POS, D["story_pos"], "Chân vách"))
        self._row(f, "Vị trí đốt", self.w_cb_pos, r); r += 1
        self.w_en_cover = _entry(D["cover"])
        self._row(f, "Lớp bảo vệ thép phân bố (mm)", self.w_en_cover, r); r += 1
        self.w_cb_l0 = _combo([lab for lab, _ in _L0_OPTS],
                              _l0_label(float(D["l0_out_factor"])))
        self._row(f, "Liên kết 2 đầu đốt (ngoài MP)", self.w_cb_l0, r); r += 1

        # --- Thép phân bố ---
        _hdr("Thép phân bố")
        self.w_cb_dia_v = _combo(_DIAS, D["dia_v"])
        self._row(f, "Thép đứng: đường kính (mm)", self.w_cb_dia_v, r); r += 1
        self.w_en_s_v = _entry(D["s_v"])
        self._row(f, "Thép đứng: khoảng cách s (mm)", self.w_en_s_v, r); r += 1
        self.w_cb_layers_v = _combo(["1", "2"], D["layers_v"])
        self._row(f, "Thép đứng: số lớp lưới", self.w_cb_layers_v, r); r += 1
        self.w_cb_dia_h = _combo(_DIAS, D["dia_h"])
        self._row(f, "Thép ngang: đường kính (mm)", self.w_cb_dia_h, r); r += 1
        self.w_en_s_h = _entry(D["s_h"])
        self._row(f, "Thép ngang: khoảng cách s (mm)", self.w_en_s_h, r); r += 1
        self.w_cb_layers_h = _combo(["1", "2"], D["layers_h"])
        self._row(f, "Thép ngang: số lớp lưới", self.w_cb_layers_h, r); r += 1

        # --- Vùng biên ---
        _hdr("Vùng biên (thép tập trung 2 đầu)")
        self.w_en_Lb_l = _entry(D["Lb_left"])
        self._row(f, "Chiều dài vùng biên trái Lb (mm)", self.w_en_Lb_l, r); r += 1
        self.w_en_Lb_r = _entry(D["Lb_right"])
        self._row(f, "Chiều dài vùng biên phải Lb (mm)", self.w_en_Lb_r, r); r += 1
        self.w_var_lb_auto = tk.BooleanVar(value=bool(D["lb_auto"]))
        tk.Checkbutton(
            f, text="Tự lấy Lb theo yêu cầu khi vùng biên bắt buộc (kèm cảnh báo)",
            variable=self.w_var_lb_auto, bg="white",
            activebackground="white", highlightthickness=0).grid(
                row=r, column=0, columnspan=2, sticky=tk.W, padx=4, pady=4)
        r += 1
        self.w_cb_dia_be = _combo(_DIAS, D["dia_be"])
        self._row(f, "Thép biên: đường kính (mm)", self.w_cb_dia_be, r); r += 1
        self.w_en_n_be = _entry(D["n_be"])
        self._row(f, "Thép biên: số thanh / vùng", self.w_en_n_be, r); r += 1
        self.w_cb_tie_dia = _combo(_DIAS, D["tie_dia_be"])
        self._row(f, "Đai vùng biên: đường kính (mm)", self.w_cb_tie_dia, r); r += 1
        self.w_en_tie_s = _entry(D["tie_s_be"])
        self._row(f, "Đai vùng biên: khoảng cách s (mm)", self.w_en_tie_s, r); r += 1
        self.w_en_tie_legs = _entry(D["tie_legs_be"])
        self._row(f, "Đai vùng biên: số nhánh", self.w_en_tie_legs, r); r += 1

        # --- Kháng chấn ---
        _hdr("Kháng chấn")
        self.w_cb_aci_class = _combo(
            [lab for _, lab in _ACI_CLASS],
            _label_of(_ACI_CLASS, D["seismic_class"], "Đặc biệt (Ch.18)"))
        self._row(f, "Loại vách (ACI 318-19)", self.w_cb_aci_class, r); r += 1
        self.w_var_seismic = tk.BooleanVar(value=bool(D["seismic_on"]))
        tk.Checkbutton(
            f, text="Kháng chấn DCM (TCVN 9386 / EN 1998) — áp cho TCVN & EC2",
            variable=self.w_var_seismic, bg="white",
            activebackground="white", highlightthickness=0).grid(
                row=r, column=0, columnspan=2, sticky=tk.W, padx=4, pady=4)
        r += 1
        ttk.Label(f, foreground="gray", wraplength=560,
                  text="Lát 1: đã hỗ trợ kiểm tra N–M vách theo TCVN "
                       "(nhập tay ở mục 5: N / M2 = mô men ngoài mặt phẳng / "
                       "M3 = mô men trong mặt phẳng / Q2 = cắt trong mặt "
                       "phẳng / Q3 = cắt ngoài mặt phẳng). ACI/EC2, vùng "
                       "biên, cắt và Pier Forces thuộc các lát sau."
                  ).grid(row=r, column=0, columnspan=2, padx=4, pady=(6, 2),
                         sticky=tk.W)
        # Live preview mặt cắt vách khi đổi nhập liệu
        for _w in (self.w_en_Lw, self.w_en_tw, self.w_en_hstory,
                   self.w_en_htotal, self.w_en_cover, self.w_en_s_v,
                   self.w_en_s_h, self.w_en_Lb_l, self.w_en_Lb_r,
                   self.w_en_n_be, self.w_en_tie_s, self.w_en_tie_legs):
            _w.bind("<FocusOut>", lambda e: self._refresh_wall_preview())
        for _cb in (self.w_cb_pos, self.w_cb_l0, self.w_cb_dia_v,
                    self.w_cb_layers_v, self.w_cb_dia_h,
                    self.w_cb_layers_h, self.w_cb_dia_be,
                    self.w_cb_tie_dia, self.w_cb_aci_class):
            _cb.bind("<<ComboboxSelected>>",
                     lambda e: self._refresh_wall_preview())
        self.w_var_lb_auto.trace_add(
            "write", lambda *a: self._refresh_wall_preview())
        self.w_var_seismic.trace_add(
            "write", lambda *a: self._refresh_wall_preview())

    # ---------------- Chuyển đổi Cột <-> Vách ----------------
    def _toggle_member(self):
        """Ẩn frame cột 2/3/4, hiện frame vách (hoặc ngược lại).

        Thứ tự pack được giữ bằng cách luôn pack lại ngay trước frame
        mục 5 (frm_loads); bề rộng panel trái không đổi (pack theo X).
        """
        wall = self.is_wall()
        cols = (self.frm_sec_section, self.frm_sec_rebar,
                self.frm_sec_stability)
        if wall:
            for fr in cols:
                fr.pack_forget()
            self.frm_wall.pack(fill=tk.X, padx=8, pady=8,
                               before=self.frm_loads)
            self._refresh_wall_preview()
        else:
            self.frm_wall.pack_forget()
            for fr in cols:
                fr.pack(fill=tk.X, padx=8, pady=8, before=self.frm_loads)
            self._wall_view_active = False
            # Trả lại tóm tắt cột TCVN nếu đã có (tránh sót hình vách ở
            # tab Kết quả); các chuẩn khác user CHECK lại như thường lệ.
            try:
                _tf = getattr(self, "_tcvn_full", None)
                if _tf and not (self.is_aci() or self.is_ec2()):
                    self._show_summary(_tf["sec"], _tf["inp"], _tf["res"])
            except Exception:
                pass

    # ---------------- Thu / áp dữ liệu vách (JSON) ----------------
    def _collect_wall(self) -> dict:
        """Đọc các ô vách thành dict đúng khóa của WallInput (§4.2)."""
        if not hasattr(self, "w_en_Lw"):
            return dict(WALL_DEFAULTS)

        def ev(e):
            return e.get()

        def num(e, default):
            try:
                v = float(str(e.get()).strip().replace(",", "."))
            except Exception:
                return default
            return int(v) if float(v).is_integer() else v

        def cnum(cb, default):
            try:
                v = float(str(cb.get()).strip())
            except Exception:
                return default
            return int(v) if float(v).is_integer() else v

        D = WALL_DEFAULTS
        return {
            "Lw": num(self.w_en_Lw, D["Lw"]),
            "tw": num(self.w_en_tw, D["tw"]),
            "h_story": num(self.w_en_hstory, D["h_story"]),
            "h_total": num(self.w_en_htotal, D["h_total"]),
            "story_pos": _code_of(_STORY_POS, self.w_cb_pos.get(), "base"),
            "cover": num(self.w_en_cover, D["cover"]),
            "l0_out_factor": dict(_L0_OPTS).get(self.w_cb_l0.get(), 1.0),
            "dia_v": cnum(self.w_cb_dia_v, D["dia_v"]),
            "s_v": num(self.w_en_s_v, D["s_v"]),
            "layers_v": int(cnum(self.w_cb_layers_v, D["layers_v"])),
            "dia_h": cnum(self.w_cb_dia_h, D["dia_h"]),
            "s_h": num(self.w_en_s_h, D["s_h"]),
            "layers_h": int(cnum(self.w_cb_layers_h, D["layers_h"])),
            "Lb_left": num(self.w_en_Lb_l, D["Lb_left"]),
            "Lb_right": num(self.w_en_Lb_r, D["Lb_right"]),
            "lb_auto": bool(self.w_var_lb_auto.get()),
            "dia_be": cnum(self.w_cb_dia_be, D["dia_be"]),
            "n_be": int(num(self.w_en_n_be, D["n_be"])),
            "tie_dia_be": cnum(self.w_cb_tie_dia, D["tie_dia_be"]),
            "tie_s_be": num(self.w_en_tie_s, D["tie_s_be"]),
            "tie_legs_be": int(num(self.w_en_tie_legs, D["tie_legs_be"])),
            "seismic_class": _code_of(_ACI_CLASS, self.w_cb_aci_class.get(),
                                      "special"),
            "seismic_on": bool(self.w_var_seismic.get()),
            # Nội lực vách lấy từ mục 5 dùng chung khi CHECK
            # (_collect_wall_loads); trong JSON giữ 0 như WallInput
            # mặc định (nội lực thật nằm ở các khóa mục 5 của file).
            "N": D["N"], "M_in": D["M_in"], "M_out": D["M_out"],
            "V_in": D["V_in"], "V_out": D["V_out"], "T": D["T"],
        }

    def _apply_wall(self, w: dict):
        """Đổ dict vách (khóa thiếu -> mặc định) vào các ô nhập."""
        if not hasattr(self, "w_en_Lw"):
            return
        d = dict(WALL_DEFAULTS)
        if isinstance(w, dict):
            d.update({k: v for k, v in w.items() if k in d})

        def se(e, v):
            e.delete(0, tk.END)
            e.insert(0, str(v))

        def sv(v):
            try:
                fv = float(v)
            except Exception:
                return str(v)
            return str(int(fv)) if fv.is_integer() else str(fv)

        se(self.w_en_Lw, d["Lw"])
        se(self.w_en_tw, d["tw"])
        se(self.w_en_hstory, d["h_story"])
        se(self.w_en_htotal, d["h_total"])
        self.w_cb_pos.set(_label_of(_STORY_POS, d["story_pos"], "Chân vách"))
        se(self.w_en_cover, d["cover"])
        try:
            _f0 = float(d["l0_out_factor"])
        except Exception:
            _f0 = 1.0
        self.w_cb_l0.set(_l0_label(_f0))
        self.w_cb_dia_v.set(sv(d["dia_v"]))
        se(self.w_en_s_v, d["s_v"])
        self.w_cb_layers_v.set(sv(d["layers_v"]))
        self.w_cb_dia_h.set(sv(d["dia_h"]))
        se(self.w_en_s_h, d["s_h"])
        self.w_cb_layers_h.set(sv(d["layers_h"]))
        se(self.w_en_Lb_l, d["Lb_left"])
        se(self.w_en_Lb_r, d["Lb_right"])
        self.w_var_lb_auto.set(bool(d["lb_auto"]))
        self.w_cb_dia_be.set(sv(d["dia_be"]))
        se(self.w_en_n_be, d["n_be"])
        self.w_cb_tie_dia.set(sv(d["tie_dia_be"]))
        se(self.w_en_tie_s, d["tie_s_be"])
        se(self.w_en_tie_legs, d["tie_legs_be"])
        self.w_cb_aci_class.set(_label_of(_ACI_CLASS, d["seismic_class"],
                                          "Đặc biệt (Ch.18)"))
        self.w_var_seismic.set(bool(d["seismic_on"]))

    # ---------------- Thông báo phần chưa tới lát ----------------
    def _wall_notice(self, action, slice_name=None):
        if slice_name:
            msg = (f"{action} cho vách thuộc {slice_name}, chưa được hỗ "
                   "trợ ở lát hiện tại — app KHÔNG dùng engine cột cho "
                   "vách.")
        else:
            msg = (f"{action} cho vách chưa được hỗ trợ — app KHÔNG "
                   "dùng engine cột cho vách.")
        messagebox.showinfo("Chế độ Vách", msg)

    # ---------------- Điều phối CHECK vách ----------------
    def _on_check_wall(self):
        """CHECK ở chế độ Vách: rẽ theo nguồn nội lực + tiêu chuẩn.

        Lát 1: chỉ nhập tay + TCVN. ETABS (batch pier) -> lát 5;
        ACI/EC2 vách -> lát 2.
        """
        if self.var_load_mode.get() == "etabs":
            self._wall_notice("Kiểm tra theo Pier Forces (ETABS)", "lát 5")
            return
        if self.is_ec2() or self.is_aci():
            self._wall_notice("Kiểm tra vách theo tiêu chuẩn này", "lát 2")
            return
        self._check_wall_tcvn()

    # ---------------- Thu thập cho engine vách ----------------
    def _wall_tcvn_materials(self):
        """Vật liệu TCVN từ đúng các ô vật liệu hiện có (như collect()).

        Chỉ dùng để dựng tiết diện/vật liệu cho engine vách; bản
        preview hình học cũng đi qua đây (vật liệu không ảnh hưởng
        hình vẽ mặt cắt).
        """
        conc = ConcreteMaterial(
            CONCRETE_GRADES[self.cb_conc.get()], self._f(self.en_gb, 0.85))
        steel = SteelMaterial(
            STEEL_GRADES[self.cb_steel.get()], self._f(self.en_gs, 1.0))
        model = "3line" if self.cb_model.get().startswith("3") else "2line"
        return conc, steel, model

    def _collect_wall_loads(self) -> dict:
        """Nội lực nhập tay (mục 5 dùng chung) ánh xạ sang hệ vách:
        M2 (Mx) -> M_out, M3 (My) -> M_in, Q2 -> V_in, Q3 -> V_out
        (nhất quán ánh xạ pier ở §5.4/§6 của bản thiết kế)."""
        return {
            "N": self._f(self.en_N), "M_in": self._f(self.en_My),
            "M_out": self._f(self.en_Mx), "V_in": self._f(self.en_Q2),
            "V_out": self._f(self.en_Q3), "T": 0.0,
        }

    # ---------------- Hàm tính vách TCVN duy nhất (lát 1) ----------------
    def _tcvn_wall_calculate_full(self, winp, conc, steel, model,
                                  loads=None, case_info=None):
        """Tính 1 lần bằng engine vách; tab/PDF chỉ đọc dict trả về."""
        return wall_tcvn_full(winp, conc, steel, model=model,
                              loads=loads, case_info=case_info)

    def _check_wall_tcvn(self):
        try:
            winp = wall_from_dict(self._collect_wall())
            loads = self._collect_wall_loads()
            conc, steel, model = self._wall_tcvn_materials()
            full = self._tcvn_wall_calculate_full(
                winp, conc, steel, model, loads=loads)
        except Exception as ex:
            messagebox.showerror("Lỗi", str(ex))
            return
        self._tcvn_wall_full = full
        self._show_wall_result(full)
        self._defer_detail(lambda _f=full: self._render_wall_detail(_f))

    # ---------------- Hiển thị: mặt cắt (dùng chung preview/kết quả) ----
    def _build_wall_fig_row(self, parent, sec):
        """Hàng trên của view vách: hình mặt cắt + thẻ thống kê thép."""
        row = tk.Frame(parent, bg="#F9FAFB")
        row.pack(fill=tk.X, padx=2, pady=(2, 4))
        left = tk.Frame(row, bg="#F9FAFB")
        left.pack(side=tk.LEFT)
        right = tk.Frame(row, bg="#F9FAFB")
        right.pack(side=tk.LEFT, fill=tk.X, expand=True)
        if HAS_MPL:
            from rc_column.pdf_export import draw_section_ax
            fig = Figure(figsize=(6.6, 2.9), dpi=100)
            ax = fig.add_subplot(111)
            draw_section_ax(ax, sec, show_stats=False, dot_scale=1.5)
            canvas = FigureCanvasTkAgg(fig, master=left)
            canvas.get_tk_widget().pack()
            try:
                fig.tight_layout()
            except Exception:
                pass
            canvas.draw()
            self._sec_fig, self._sec_canvas, self._sec_ax = fig, canvas, ax
        self._sec_card_vars = self._build_section_cards(right, sec)

    def _show_wall_preview(self, sec, winp):
        """View xem trước mặt cắt vách (chưa CHECK) ở tab Kết quả."""
        for w in self._sum_inner.winfo_children():
            w.destroy()
        self._wall_view_active = True
        ttk.Label(self._sum_inner,
                  text="MẶT CẮT VÁCH — XEM TRƯỚC (chưa kiểm tra)",
                  font=("", 11, "bold")).pack(pady=(4, 2))
        self._build_wall_fig_row(self._sum_inner, sec)
        ttk.Label(
            self._sum_inner, foreground="gray", wraplength=900,
            text="Nhập nội lực ở mục 5 (chế độ nhập tay: N, M2 = ngoài "
                 "mặt phẳng, M3 = trong mặt phẳng, Q2, Q3) rồi bấm "
                 "KIỂM TRA KHẢ NĂNG CHỊU LỰC. Lát 1 hỗ trợ TCVN; "
                 "ACI/EC2 vách thuộc lát 2.").pack(pady=(2, 6))

    def _refresh_wall_preview(self):
        """Vẽ/cập nhật preview mặt cắt vách khi đổi nhập liệu."""
        if not self.is_wall():
            return
        try:
            winp = wall_from_dict(self._collect_wall())
            conc, steel, _model = self._wall_tcvn_materials()
            sec, _meta = build_wall_section(winp, conc, steel)
        except Exception:
            return
        ax = getattr(self, "_sec_ax", None)
        if getattr(self, "_wall_view_active", False) and ax is not None:
            try:
                from rc_column.pdf_export import draw_section_ax
                ax.clear()
                draw_section_ax(ax, sec, show_stats=False, dot_scale=1.5)
                self._sec_fig.tight_layout()
                self._sec_canvas.draw_idle()
                varmap = getattr(self, "_sec_card_vars", None)
                if varmap:
                    vals = self._section_card_values(sec)
                    for k, var in varmap.items():
                        if k in vals:
                            var.set(vals[k])
                return
            except Exception:
                pass
        self._show_wall_preview(sec, winp)

    # ---------------- Hiển thị kết quả CHECK vách TCVN ----------------
    def _show_wall_result(self, full):
        """Tab Kết quả cho vách (đọc từ dict _tcvn_wall_full, không
        tính lại): mặt cắt + thẻ thép / biểu đồ N–Mα / bảng thông số."""
        for w in self._sum_inner.winfo_children():
            w.destroy()
        self._wall_view_active = True
        self._last_sec = full["sec"]
        ok = full["ok"]
        banner = tk.Label(
            self._sum_inner,
            text=("KẾT QUẢ KIỂM TRA VÁCH — TCVN 5574:2018   •   "
                  + ("ĐẠT (N–M)" if ok else "KHÔNG ĐẠT (N–M)")),
            font=("", 11, "bold"),
            bg="#D1FAE5" if ok else "#FEE2E2",
            fg="#065F46" if ok else "#991B1B")
        banner.pack(fill=tk.X, padx=2, pady=(4, 2))
        self._build_wall_fig_row(self._sum_inner, full["sec"])
        # Hàng dưới: biểu đồ N–Mα | bảng thông số
        row2 = tk.Frame(self._sum_inner, bg="#F9FAFB")
        row2.pack(fill=tk.X, padx=2, pady=(2, 4))
        left2 = tk.Frame(row2, bg="#F9FAFB")
        left2.pack(side=tk.LEFT)
        right2 = tk.Frame(row2, bg="#F9FAFB")
        right2.pack(side=tk.LEFT, fill=tk.X, expand=True)
        if HAS_MPL:
            from rc_column.interaction import uniaxial_curve_fs
            fig2 = Figure(figsize=(5.6, 3.9), dpi=100)
            ax2 = fig2.add_subplot(111)
            curve = uniaxial_curve_fs(full["fs_obj"], full["alpha_deg"],
                                      full["model"])
            ax2.plot([m for (_n, m) in curve], [n for (n, _m) in curve],
                     color="#059669", lw=1.8)
            ax2.scatter([full["Malpha"]], [full["N"]], c="#DC2626",
                        zorder=5, label="A (làm việc)")
            lam = full["lambda_ray"]
            if math.isfinite(lam):
                ax2.scatter([lam * full["Malpha"]], [full["BN"]],
                            c="#2563EB", zorder=5, label="B (giới hạn)")
            ax2.set_xlabel("Mα (kN·m)")
            ax2.set_ylabel("N (kN)")
            ax2.set_title(f"N–Mα (α = {full['alpha_deg']:.1f}°)",
                          fontsize=11)
            ax2.grid(True, color="#E5E7EB", lw=0.6, linestyle="--")
            ax2.legend(fontsize=8)
            cv2 = FigureCanvasTkAgg(fig2, master=left2)
            cv2.get_tk_widget().pack()
            try:
                fig2.tight_layout()
            except Exception:
                pass
            cv2.draw()
        self._build_wall_param_table(right2, full)
        ttk.Label(
            self._sum_inner, foreground="gray", wraplength=900,
            text="Phạm vi lát 1: chỉ kiểm tra N–M (đã kể uốn dọc ngoài "
                 "mặt phẳng theo tw). Vùng biên (lát 3), cắt trong mặt "
                 "phẳng + trượt mạch ngừng (lát 4) và cấu tạo (lát 3) "
                 "CHƯA kiểm — kết luận trên chỉ cho N–M."
            ).pack(pady=(2, 6))

    def _build_wall_param_table(self, parent, full):
        """Bảng thông số vách (đọc từ dict kết quả, không tính lại)."""
        winp = full["winp"]
        sec = full["sec"]
        sl = full["slend"]
        ttk.Label(parent, text="BẢNG THÔNG SỐ — VÁCH (TCVN 5574:2018)",
                  font=("", 11, "bold")).pack(pady=(2, 6))
        cols = ("sym", "desc", "val")
        tree = ttk.Treeview(parent, columns=cols, show="headings",
                            height=17, style="Param.Treeview")
        tree.heading("sym", text="Ký hiệu")
        tree.heading("desc", text="Thông số")
        tree.heading("val", text="Giá trị")
        tree.column("sym", width=84, anchor="center", stretch=False)
        tree.column("desc", width=230, anchor="w")
        tree.column("val", width=190, anchor="e", stretch=False)
        tree.tag_configure("odd", background="#F9FAFB")
        tree.tag_configure(
            "dc", background="#D1FAE5" if full["ok"] else "#FEE2E2",
            foreground="#065F46" if full["ok"] else "#991B1B")
        c = full["c_neutral"]
        c_txt = (f"{c:.0f} mm" if c is not None and math.isfinite(c)
                 else "—")
        fs_txt = (f"{full['fs']:.2f}" if math.isfinite(full["fs"])
                  else "∞")
        rows = [
            ("Lw", "Chiều dài vách", f"{float(winp.Lw):.0f} mm"),
            ("tw", "Chiều dày vách", f"{float(winp.tw):.0f} mm"),
            ("Ab", "Diện tích bê tông", f"{sec.gross_area:,.0f} mm²"),
            ("As", "Tổng diện tích thép dọc", f"{sec.steel_area:.0f} mm²"),
            ("μ", "Hàm lượng thép dọc",
             f"{sec.reinforcement_ratio * 100:.2f}%"),
            ("N", "Lực dọc tính toán", f"{full['N']:+.1f} kN"),
            ("M3", "Mô men trong mặt phẳng ban đầu",
             f"{full['M_in']:.1f} kN·m"),
            ("M2", "Mô men ngoài mặt phẳng ban đầu",
             f"{full['M_out']:.1f} kN·m"),
            ("V2", "Lực cắt trong mặt phẳng (chưa kiểm — lát 4)",
             f"{full['V_in']:.1f} kN"),
            ("L0", "Chiều dài tính toán ngoài mặt phẳng",
             f"{sl['l0_out'] / 1000.0:.2f} m"),
            ("λ", "Độ mảnh ngoài mặt phẳng", f"{sl['lambda_out']:.1f}"),
            ("e0", "Độ lệch tâm ban đầu ngoài mặt phẳng",
             f"{full['e0_out']:.1f} mm"),
            ("φL", "Hệ số φL", f"{full['phi_L']:.2f}"),
            ("Ncr", "Lực tới hạn Euler ngoài mặt phẳng",
             f"{sl['Ncr_out']:,.0f} kN"),
            ("η", "Hệ số uốn dọc ngoài mặt phẳng",
             f"{sl['factor_out']:.3f}"),
            ("M2*", "Mô men ngoài mặt phẳng đã phóng đại",
             f"{full['M_out_d']:.1f} kN·m"),
            ("M3*", "Mô men trong mặt phẳng (không phóng đại)",
             f"{full['M_in_d']:.1f} kN·m"),
            ("α", "Góc mô men (từ trục M3)", f"{full['alpha_deg']:.1f} °"),
            ("Mα", "Mô men tổng hợp", f"{full['Malpha']:.1f} kN·m"),
            ("Mα,u", "Khả năng chịu Mα tại N",
             f"{full['M_capacity']:.1f} kN·m"),
            ("c", "Chiều cao vùng nén tại điểm B", c_txt),
            ("σmép", "Ứng suất nén mép (đàn hồi)",
             f"{full['sigma_edge']:.2f} MPa"),
        ]
        for i, (s, d, v) in enumerate(rows):
            tree.insert("", tk.END, values=(s, d, v),
                        tags=("odd",) if i % 2 else ())
        tree.insert("", tk.END,
                    values=("D/C", "Tỷ số sử dụng khả năng chịu lực (N–M)",
                            f"{full['dc']:.3f} (FS = {fs_txt})  "
                            + ("ĐẠT" if full["ok"] else "KHÔNG ĐẠT")),
                    tags=("dc",))
        tree.pack(fill=tk.X, padx=2)

    def _render_wall_detail(self, full):
        """Tab Chi tiết (lát 1): thuyết minh dạng text từ dict kết quả."""
        for w in self._calc_inner.winfo_children():
            w.destroy()
        t = tk.Text(self._calc_inner, wrap="word", font=("Consolas", 10),
                    height=42)
        t.pack(fill=tk.BOTH, expand=True)
        lines = ["THUYẾT MINH KIỂM TRA VÁCH — TCVN 5574:2018 (lát 1)",
                 f"N = {full['N']:+.1f} kN, M3 (trong MP) = "
                 f"{full['M_in']:.1f} kN·m, M2 (ngoài MP) = "
                 f"{full['M_out']:.1f} kN·m, "
                 f"V2 = {full['V_in']:.1f} kN, V3 = {full['V_out']:.1f} kN",
                 ""]
        lines += full["details"]
        lines += ["", "Chưa kiểm ở lát 1: vùng biên (lát 3), cắt trong "
                      "mặt phẳng + trượt mạch ngừng (lát 4), cấu tạo "
                      "(lát 3). PDF vách thuộc lát 6."]
        t.insert(tk.END, "\n".join(lines))
        t.configure(state="disabled")
        self._calc_inner.update_idletasks()
        self._calc_canvas.configure(
            scrollregion=self._calc_canvas.bbox("all"))
        self._bind_wheel(self._calc_inner, self._calc_canvas)
