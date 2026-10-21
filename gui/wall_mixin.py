"""Chế độ Vách (GĐ1 — lát 0: khung giao diện + plumbing dữ liệu).

Gồm: frame nhập liệu vách (mục 2 khi ở chế độ Vách), chuyển đổi loại
cấu kiện Cột <-> Vách (_toggle_member), thu/áp dữ liệu vách cho JSON
(_collect_wall/_apply_wall), và chặn CHECK/PDF ở chế độ Vách.

Lát 0 CHƯA có engine tính vách: CHECK/PDF ở chế độ Vách báo rõ chưa
hỗ trợ, tuyệt đối không chạy engine cột cho dữ liệu vách. Thiết kế:
THIET_KE_TICH_HOP_VACH_GD1.md §2, §6, §8 (lát 0).
"""

import tkinter as tk
from tkinter import ttk, messagebox

from rc_column.lang import T
from rc_column.wall_input import WALL_DEFAULTS

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
                  text="Chế độ Vách đang triển khai theo giai đoạn: lát 0 mới "
                       "có khung nhập liệu + lưu/mở dữ liệu; phần kiểm tra "
                       "khả năng chịu lực sẽ bổ sung ở các lát tiếp theo."
                  ).grid(row=r, column=0, columnspan=2, padx=4, pady=(6, 2),
                         sticky=tk.W)

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
        else:
            self.frm_wall.pack_forget()
            for fr in cols:
                fr.pack(fill=tk.X, padx=8, pady=8, before=self.frm_loads)

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
            # Nội lực vách tính qua mục 5 dùng chung (lát 1 mới ánh xạ);
            # lát 0 giữ 0 như WallInput mặc định.
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

    # ---------------- Chặn ở lát 0 ----------------
    def _wall_notice(self, action):
        messagebox.showinfo(
            "Chế độ Vách — lát 0",
            f"{action} cho vách chưa được hỗ trợ ở lát 0 (mới có khung "
            "nhập liệu + lưu/mở dữ liệu). Engine tính vách sẽ bổ sung ở "
            "các lát tiếp theo — app KHÔNG dùng engine cột cho vách.")

    def _on_check_wall(self):
        """CHECK ở chế độ Vách (lát 0): báo rõ chưa hỗ trợ, không tính."""
        self._wall_notice("Kiểm tra khả năng chịu lực")
