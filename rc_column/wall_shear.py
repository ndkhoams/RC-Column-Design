"""Kiểm tra cắt trong mặt phẳng cho vách chữ nhật đặc — TCVN 5574:2018.

CĂN CỨ VÀ GIỚI HẠN ÁP DỤNG (đọc kỹ trước khi dùng số này cho thiết kế):
- TCVN 5574:2018 KHÔNG có điều khoản cắt riêng cho vách trong phạm vi
  tài liệu tra cứu được ở lát này. Lát này áp dụng công thức cắt của
  cấu kiện theo §8.1.3 — đúng bộ công thức đã mã hoá và dùng cho cột
  trong ``rc_column/stirrup.py`` (``check_shear``) — với ánh xạ vách:
  b = tw (bề dày vách), chiều tính toán theo Lw, thép ngang phân bố
  quy đổi thành qsw như đai (xem ``check_wall_shear_in_plane``).
  Ánh xạ này là quyết định kỹ thuật của lát, KHÔNG phải điều khoản
  riêng cho vách trong tiêu chuẩn — cần người dùng/đơn vị thẩm tra
  xác nhận trước khi dùng cho thiết kế chính thức.
- Các công thức §8.1.3 được dùng NGUYÊN VẸN qua ``check_shear`` (không
  viết lại công thức ở đây, đúng nguyên tắc "tính 1 lần" của app):
  ĐK1 dải nén xiên (88): Q <= φn x 0.3 x Rb x b x h0, với φb1 = 0.3 là
  hằng số của bản 2018 (theo AGENTS.md); ĐK2 vết nứt xiên (89)/(90):
  Q <= Qb + Qsw, khảo sát C trong [h0, 2h0]; Qb = φb2 x Rbt x b x h0²/C
  với φb2 = 1.5, chặn trong [0.5, 2.5] x Rbt x b x h0; Qsw = φsw x qsw x C
  với φsw = 0.75; φn theo §8.1.3.3.2 CHỈ nhân số hạng bê tông (ĐK1 và
  Qb), KHÔNG nhân Qsw; điều kiện (96): qsw < 0.25 x Rbt x b thì Qb theo
  (97), đai vẫn được kể; điều kiện (98): nhóm thép ngang nào có
  s > s_max = Rbt x b x h0²/|Q| thì nhóm đó KHÔNG được kể (Qsw = 0 nếu
  mọi nhóm đều bị loại).
- Lực cắt thiết kế V_d là lực cắt truyền vào hàm này. Phóng đại cắt
  kháng chấn DCM (TCVN 9386-1:2025 §5.4.2.4(7): V_Ed = 1,5 × V'_Ed,
  chỉ trong mặt phẳng) KHÔNG nằm trong hàm này mà do
  ``wall_engine.wall_tcvn_full(..., seismic_shear=True)`` áp TRƯỚC
  khi gọi (V_d = 1,5 × V_in); gọi trực tiếp hàm này với V_in thì
  kết quả là KHÔNG kể phóng đại — caller phải ghi rõ điều đó.
- Cắt NGOÀI mặt phẳng (V_out): LÀM ở lát 4 phần 4 bằng cùng bộ công
  thức §8.1.3 qua ``check_shear`` (xem ``check_wall_shear_out_of_plane``
  cuối file: b = Lw, h0 = tw - cover - dia_v - dia_h/2; thép ngang
  mặc định 2 nhánh × φ(dia_h) @ s_h, cùng cấp thép với trong mặt
  phẳng, suy từ input thép ngang bổ sung — quyết user 2026-10-25,
  thay thế quyết P4 cũ Qsw = 0; không có thép bổ sung thì Qsw = 0
  thật). Trượt tại mạch ngừng thi công
  chân vách VẪN pending (xem ``wall_engine.py``: ``sliding``): chưa
  xác minh được điều khoản TCVN 5574:2018 cho kiểm tra đó đối với
  vách, nên không mượn công thức ma sát cắt của ACI (§22.9) hay
  EC2 (§6.2.5) sang TCVN và không lấp số.

Đơn vị: kN, kN·m, mm, MPa. N nén dương (quy ước app).
"""

import math

from .materials import STEEL_GRADES, SteelMaterial
from .sections import bar_area
from .stirrup import check_shear
from .wall_section import wall_dims


def wall_shear_geometry(winp, Lw: float = None, tw: float = None):
    """Hình học cắt trong mặt phẳng của vách.

    Lw/tw: kích thước HIỆU DỤNG sau góc xoay (``wall_dims``) nếu không
    truyền vào thì tự suy từ ``winp`` — ở 90°/270° Lw hiệu dụng là tw
    gốc và ngược lại, nên h0/b tự đi đúng phương trong mặt phẳng mới.
    b = tw; h0 = Lw - cover - dia_h - dia_v/2: ánh xạ trực tiếp quy
    ước h0 của cột (``report.py``: h0 = h - cover - sw_dia - bar_dia/2,
    với đai -> thép ngang dia_h, thép dọc -> thép đứng dia_v).
    """
    if Lw is None or tw is None:
        Lw_eff, tw_eff = wall_dims(winp)
        Lw = float(Lw_eff) if Lw is None else float(Lw)
        tw = float(tw_eff) if tw is None else float(tw)
    else:
        Lw, tw = float(Lw), float(tw)
    cover = float(getattr(winp, "cover", 0.0) or 0.0)
    dia_h = float(getattr(winp, "dia_h", 0.0) or 0.0)
    dia_v = float(getattr(winp, "dia_v", 0.0) or 0.0)
    h0 = Lw - cover - dia_h - dia_v / 2.0
    return {"Lw": Lw, "tw": tw, "b": tw, "h0": max(h0, 1.0),
            "h0_raw": h0, "cover": cover, "dia_h": dia_h,
            "dia_v": dia_v}


def qb_formula_sub(parts, rbt):
    """Thay số công thức Qb cho 1 phương — đúng nhánh code đang tính.

    parts: dict parts của shear_in/shear_out; rbt: Rbt (MPa) của bê
    tông. Trả về chuỗi "C = ..., (90)/(97): Qb = ... → ... kN;
    Qsw = ... → [Q]2 = ... kN". Nhánh (90) khi qb_mode CT90 (ĐK
    (96) đạt) hoặc NONE (không thép, chỉ bê tông); nhánh (97) khi
    CT97 (ĐK (96) không đạt). Qb_tt được chặn trong
    [0,5; 2,5]×Rbt×b×h0 rồi mới nhân φn (§8.1.3.3.2) — nếu chặn
    có hiệu lực thì ghi rõ bước chặn để thay số không lệch.
    Dùng chung cho ghi chú Qb tab Kết quả (gui) và thẻ chi tiết
    (wall_detail) để 2 nơi không lệch nhau.
    """
    b = float(parts.get("b", 0.0) or 0.0)
    h0 = float(parts.get("h0", 0.0) or 0.0)
    c_opt = float(parts.get("C_opt", 0.0) or 0.0)
    qsw = float(parts.get("qsw", 0.0) or 0.0)
    phi_n = float(parts.get("phi_n", 0.0) or 0.0)
    qmin = 0.5 * rbt * b * h0 / 1000.0
    qmax = 2.5 * rbt * b * h0 / 1000.0
    if parts.get("qb_mode") == "CT97":
        tt = 4 * 1.5 * h0 * h0 * qsw / c_opt / 1000.0 if c_opt else 0.0
        form = (f"φn×4×1,5×h0²×qsw/C = {phi_n:.3f}×4×1,5×{h0:.0f}²"
                f"×{qsw:.1f}/{c_opt:.1f}")
        clause = "(97)"
    else:
        tt = 1.5 * rbt * b * h0 * h0 / c_opt / 1000.0 if c_opt else 0.0
        form = (f"φn×1,5×Rbt×b×h0²/C = {phi_n:.3f}×1,5×{rbt:.2f}"
                f"×{b:.0f}×{h0:.0f}²/{c_opt:.1f}")
        clause = "(90)"
    clamped = min(max(tt, qmin), qmax)
    if abs(clamped - tt) > 0.05:
        form += (f" = {tt:.1f} → chặn [{qmin:.1f}; {qmax:.1f}]"
                 f" → {clamped:.1f} ×φn")
    # C hiện 1 chữ số thập phân (khác hàng C của bảng hiện số
    # nguyên) để thay số tái hiện đúng Qb/Qsw tới 0,1 kN.
    return (f"C = {c_opt:.1f} mm, {clause}: Qb = {form} → "
            f"{float(parts.get('Qb', 0.0)):.1f} kN; "
            f"Qsw = 0,75×{qsw:.1f}×{c_opt:.1f} = "
            f"{float(parts.get('Qsw', 0.0)):.1f} kN → "
            f"[Q]2 = {float(parts.get('Qcap2', 0.0)):.1f} kN")


def check_wall_shear_in_plane(winp, conc, steel, V_in: float, N: float,
                              Lw: float = None, tw: float = None,
                              steel_sw=None) -> dict:
    """Kiểm tra cắt trong mặt phẳng cho 1 tổ hợp (engine thuần).

    winp: WallInput; conc/steel: ConcreteMaterial/SteelMaterial (TCVN).
    Rsw lấy từ ``steel_sw`` (vật liệu thép ngang RIÊNG của vách, phần
    3/7) khi được truyền; steel_sw = None -> suy từ winp.sw_steel_grade
    nếu là cấp hợp lệ (cùng γs với thép dọc, như đai cột), ngược lại
    fallback về ``steel`` (cấp thép dọc x γs) — đúng hành vi cũ, để
    file JSON cũ (không có khóa sw_steel_grade) và các caller cũ tái
    hiện số cũ từng chữ số.
    Ô "Cấp độ bền thép đai" của chế độ Cột KHÔNG dùng cho vách.

    Thép ngang phân bố quy đổi: một "nhóm" duy nhất
    Asw = layers_h x Ah (Ah = π·dia_h²/4), bước s_h — đúng vai trò
    (Asw, s) của một nhóm đai trong ``check_shear``; do đó
    qsw = Rsw x Asw / s_h, và điều kiện (98) xét trên chính s_h này.

    Trả về dict đủ cho hiển thị (bảng Kết quả + thuyết minh sau này):
    V_d, V_cap = min([Q]1, [Q]2), dc = |V_d|/V_cap, ok, parts (từng số
    hạng), sh (ShearResult của stirrup — nguồn duy nhất của các số),
    note (căn cứ + giới hạn). V_cap = 0 và |V_d| > 0 -> dc = inf.
    parts["steel_grade"] = cấp thực dùng cho Rsw; parts["steel_grade_long"]
    = cấp thép dọc (để đối chiếu khi fallback).
    """
    geom = wall_shear_geometry(winp, Lw, tw)
    b, h0 = geom["b"], geom["h0"]
    dia_h = geom["dia_h"]
    s_h = float(getattr(winp, "s_h", 0.0) or 0.0)
    try:
        layers_h = int(getattr(winp, "layers_h", 0) or 0)
    except Exception:
        layers_h = 0
    Asw = layers_h * bar_area(dia_h) if dia_h > 0 and layers_h > 0 else 0.0
    if steel_sw is not None:
        sw_mat = steel_sw
    else:
        _g = getattr(winp, "sw_steel_grade", None)
        if isinstance(_g, str) and _g in STEEL_GRADES:
            sw_mat = SteelMaterial(STEEL_GRADES[_g],
                                   float(getattr(steel, "gamma_s", 1.0)))
        else:
            sw_mat = steel
    Rsw = float(sw_mat.Rsw)
    groups = [(Asw, s_h)] if Asw > 0 and s_h > 0 else []
    qsw_arr = Rsw * Asw / s_h if Asw > 0 and s_h > 0 else 0.0
    A_sec = geom["Lw"] * geom["tw"]
    sh = check_shear(float(V_in), b, h0, float(conc.Rb), float(conc.Rbt),
                     Asw, Rsw, s_h, direction="in",
                     N=float(N), A_sec=A_sec, groups=groups)
    V_cap = min(sh.Qcap1, sh.Qcap2)
    V_d = float(V_in)
    if V_cap > 0:
        dc = abs(V_d) / V_cap
    else:
        dc = 0.0 if abs(V_d) <= 1e-12 else float("inf")
    try:
        steel_name = sw_mat.grade.name
    except Exception:
        steel_name = ""
    try:
        steel_long_name = steel.grade.name
    except Exception:
        steel_long_name = ""
    if groups:
        sw_txt = f"{layers_h}φ{dia_h:.0f} a{s_h:.0f}"
    else:
        sw_txt = "không có thép ngang"
    parts = {
        "b": b, "h0": h0, "Lw": geom["Lw"], "tw": geom["tw"],
        "cover": geom["cover"], "dia_h": dia_h, "dia_v": geom["dia_v"],
        "s_h": s_h, "layers_h": layers_h, "Asw": Asw,
        "Asw_counted": sh.Asw_counted, "Rsw": Rsw,
        "steel_grade": steel_name, "sw_steel_grade": steel_name,
        "steel_grade_long": steel_long_name, "sw_txt": sw_txt,
        "qsw_arr": qsw_arr, "qsw": sh.qsw,
        "qsw_min96": sh.qsw_min96, "cond96_ok": sh.cond96_ok,
        "qb_mode": sh.qb_mode, "s_max": sh.s_max,
        "cond98_ok": sh.cond98_ok, "dropped98": list(sh.dropped98),
        "phi_n": sh.phi_n, "sigma_m": sh.sigma_m,
        "sigma_t": sh.sigma_t, "Qcap1": sh.Qcap1,
        "Qcap2": sh.Qcap2, "Qb": sh.Qb_opt, "Qsw": sh.Qsw_opt,
        "C_opt": sh.C_opt, "ok1": sh.ok1, "ok2": sh.ok2,
    }
    note = (
        "TCVN 5574:2018 §8.1.3 (công thức cắt cấu kiện, qua "
        "rc_column/stirrup.check_shear — cùng bộ công thức của cột; "
        "ánh xạ vách: b = tw, h0 = Lw - cover - dia_h - dia_v/2, "
        "qsw từ thép ngang phân bố). φn (§8.1.3.3.2) chỉ nhân số hạng "
        "bê tông (ĐK1, Qb). V_d là lực cắt thiết kế truyền vào "
        "(engine vách áp 1,5× theo TCVN 9386-1:2025 §5.4.2.4(7) "
        "trước khi gọi khi combo động đất/DCM bật). Cắt ngoài mặt "
        "phẳng: xem "
        "check_wall_shear_out_of_plane; trượt mạch ngừng: chưa kiểm "
        "(pending — xem wall_engine.sliding)."
    )
    return {"V_d": V_d, "V_cap": V_cap, "dc": dc, "ok": bool(sh.ok),
            "parts": parts, "sh": sh, "note": note}


# ================= CẮT NGOÀI MẶT PHẲNG (lát 4 — phần 4) =================
def wall_shear_geometry_out_of_plane(winp, Lw: float = None,
                                     tw: float = None):
    """Hình học cắt ngoài mặt phẳng của vách (gương hàm trong MP).

    Lw/tw: kích thước HIỆU DỤNG sau góc xoay (``wall_dims``) — ở
    90°/270° Lw hiệu dụng là tw gốc và ngược lại, nên b/h0 tự đi
    đúng phương ngoài mặt phẳng mới.
    b = Lw; h0 = tw - cover - dia_v - dia_h/2: gương trực tiếp quy
    ước h0 trong MP (report.py: h0 = h - cover - sw_dia - bar_dia/2),
    hoán đổi vai trò dia_h/dia_v vì phương uốn đổi từ Lw sang tw.
    """
    if Lw is None or tw is None:
        Lw_eff, tw_eff = wall_dims(winp)
        Lw = float(Lw_eff) if Lw is None else float(Lw)
        tw = float(tw_eff) if tw is None else float(tw)
    else:
        Lw, tw = float(Lw), float(tw)
    cover = float(getattr(winp, "cover", 0.0) or 0.0)
    dia_h = float(getattr(winp, "dia_h", 0.0) or 0.0)
    dia_v = float(getattr(winp, "dia_v", 0.0) or 0.0)
    h0 = tw - cover - dia_v - dia_h / 2.0
    return {"Lw": Lw, "tw": tw, "b": Lw, "h0": max(h0, 1.0),
            "h0_raw": h0, "cover": cover, "dia_h": dia_h,
            "dia_v": dia_v}


def check_wall_shear_out_of_plane(winp, conc, steel, V_out: float,
                                  N: float, Lw: float = None,
                                  tw: float = None,
                                  steel_sw=None) -> dict:
    """Kiểm tra cắt ngoài mặt phẳng cho 1 tổ hợp (engine thuần).

    winp: WallInput; conc/steel: ConcreteMaterial/SteelMaterial (TCVN).
    Dùng NGUYÊN VẸN ``stirrup.check_shear`` (§8.1.3) như cắt trong MP,
    chỉ khác ánh xạ (b = Lw, h0 theo tw) và thép ngang:
    - Thép ngang MẶC ĐỊNH 2 nhánh × φ(dia_h) @ s_h, cùng cấp thép
      (Rsw) với thép ngang trong mặt phẳng — suy trực tiếp từ
      input thép ngang bổ sung (quyết user 2026-10-25, thay thế
      quyết P4 cũ Qsw = 0); KHÔNG có ô nhập riêng cho ngoài MP.
      Một "nhóm" duy nhất Asw = 2 × Ah, bước s_h — đúng vai trò
      (Asw, s) của một nhóm đai trong ``check_shear``; ĐK (96)/(98)
      áp đúng luật như trong MP trên chính nhóm này.
    - Khi không có thép ngang bổ sung (dia_h = 0 hoặc s_h = 0) thì
      groups = [] và Qsw = 0 thật (không bịa thép).
    - ĐK1 (88) φb1 = 0.3; ĐK2 (89)/(90) trên C ∈ [h0, 2h0]; φn
      (§8.1.3.3.2) chỉ nhân số hạng bê tông (ĐK1, Qb) — tất cả do
      check_shear thực hiện, hàm này chỉ ánh xạ + đóng gói.
    Rsw lấy từ ``steel_sw`` khi được truyền, ngược lại suy từ
    winp.sw_steel_grade (cùng γs với thép dọc) rồi fallback về
    ``steel`` — đúng luật hàm trong MP, để caller cũ tái hiện số.
    Trả về dict cùng khung với cắt trong MP: V_d, V_cap =
    min([Q]1, [Q]2), dc = |V_d|/V_cap, ok, parts, sh, note.
    V_cap = 0 và |V_d| > 0 -> dc = inf; V_d = 0 -> dc = 0.
    parts["layers_h"] ở đây là SỐ NHÁNH ngoài MP (2 khi có thép,
    0 khi không có thép), không phải số lớp lưới trong MP.
    """
    geom = wall_shear_geometry_out_of_plane(winp, Lw, tw)
    b, h0 = geom["b"], geom["h0"]
    dia_h = geom["dia_h"]
    s_h = float(getattr(winp, "s_h", 0.0) or 0.0)
    branches = 2
    Asw = branches * bar_area(dia_h) if dia_h > 0 else 0.0
    if steel_sw is not None:
        sw_mat = steel_sw
    else:
        _g = getattr(winp, "sw_steel_grade", None)
        if isinstance(_g, str) and _g in STEEL_GRADES:
            sw_mat = SteelMaterial(STEEL_GRADES[_g],
                                   float(getattr(steel, "gamma_s", 1.0)))
        else:
            sw_mat = steel
    Rsw = float(sw_mat.Rsw)
    groups = [(Asw, s_h)] if Asw > 0 and s_h > 0 else []
    qsw_arr = Rsw * Asw / s_h if Asw > 0 and s_h > 0 else 0.0
    A_sec = geom["Lw"] * geom["tw"]
    sh = check_shear(float(V_out), b, h0, float(conc.Rb),
                     float(conc.Rbt), Asw, Rsw, s_h,
                     direction="out", N=float(N), A_sec=A_sec,
                     groups=groups)
    V_cap = min(sh.Qcap1, sh.Qcap2)
    V_d = float(V_out)
    if V_cap > 0:
        dc = abs(V_d) / V_cap
    else:
        dc = 0.0 if abs(V_d) <= 1e-12 else float("inf")
    try:
        steel_name = sw_mat.grade.name
    except Exception:
        steel_name = ""
    if groups:
        sw_txt = f"{branches}φ{dia_h:.0f} a{s_h:.0f}"
    else:
        sw_txt = "không có thép ngang"
    parts = {
        "b": b, "h0": h0, "Lw": geom["Lw"], "tw": geom["tw"],
        "cover": geom["cover"], "dia_h": geom["dia_h"],
        "dia_v": geom["dia_v"],
        "s_h": s_h, "layers_h": branches if groups else 0,
        "Asw": Asw,
        "Asw_counted": sh.Asw_counted, "Rsw": Rsw,
        "steel_grade": steel_name,
        "sw_txt": sw_txt,
        "qsw_arr": qsw_arr, "qsw": sh.qsw,
        "qsw_min96": sh.qsw_min96, "cond96_ok": sh.cond96_ok,
        "qb_mode": sh.qb_mode, "s_max": sh.s_max,
        "cond98_ok": sh.cond98_ok, "dropped98": list(sh.dropped98),
        "phi_n": sh.phi_n, "sigma_m": sh.sigma_m,
        "sigma_t": sh.sigma_t, "Qcap1": sh.Qcap1,
        "Qcap2": sh.Qcap2, "Qb": sh.Qb_opt, "Qsw": sh.Qsw_opt,
        "C_opt": sh.C_opt, "ok1": sh.ok1, "ok2": sh.ok2,
    }
    note = (
        "TCVN 5574:2018 §8.1.3 (công thức cắt cấu kiện, qua "
        "rc_column/stirrup.check_shear — cùng bộ công thức của cột; "
        "ánh xạ vách ngoài mặt phẳng: b = Lw, "
        "h0 = tw - cover - dia_v - dia_h/2, thép ngang mặc định "
        "2 nhánh × φ(dia_h) @ s_h cùng cấp thép với trong mặt phẳng "
        "(quyết user 2026-10-25). φn "
        "(§8.1.3.3.2) chỉ nhân số hạng bê tông (ĐK1, Qb). "
        "V_d = V_out = V3; cắt ngoài mặt phẳng KHÔNG phóng đại "
        "kháng chấn (TCVN 9386-1:2025 §5.4.2.4(7) chỉ áp cho cắt "
        "trong mặt phẳng của vách chịu uốn trong MP)."
    )
    return {"V_d": V_d, "V_cap": V_cap, "dc": dc, "ok": bool(sh.ok),
            "parts": parts, "sh": sh, "note": note}
