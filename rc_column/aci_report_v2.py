"""Thuyết minh kiểm tra cột theo ACI 318-19 — cấu trúc 7 mục theo mẫu TCVN.

Trả về list các section dict để GUI render (cùng cấu trúc với TCVN):
- mỗi section: {'num', 'title', 'ref', 'cards'}
- mỗi card: {'title', 'ref', 'lines', 'result'}
"""

import math
from typing import Any, Dict, List

from .lang import T


def _f(x: float, nd: int = 2) -> str:
    if x is None or not math.isfinite(x):
        return "—"
    return f"{x:.{nd}f}"


def _fm(x):
    """Định dạng cường độ tra bảng/nhập liệu: in ĐÚNG giá trị thật, cắt số 0
    thừa ở cuối (27.579 -> '27.579', 420 -> '420'). Không dùng cho giá trị
    suy ra bằng phép chia/công thức."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(v):
        return "—"
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _mk(title: str, ref: str, lines: List[str], result: str = "", full: bool = False, conclusion: bool = False, dc_conclusion: bool = False, dc: float = 0.0, fs: float = 0.0, ok: bool = True, shear_conclusion: bool = False) -> Dict[str, Any]:
    return {"title": title, "ref": ref, "lines": lines, "result": result, "full": full, "conclusion": conclusion, "dc_conclusion": dc_conclusion, "dc": dc, "fs": fs, "ok": ok, "shear_conclusion": shear_conclusion}


def generate_aci_report_sections_v2(inp, aci_res: Dict[str, Any],
                                    mm_res: Dict[str, Any],
                                    shear_res: Dict[str, Any],
                                    conc, steel, sec,
                                    tied: bool = True,
                                    fyt_MPa: float = None,
                                    lang: str = "VN") -> List[Dict[str, Any]]:
    """Tạo 7 mục thuyết minh theo mẫu TCVN cho ACI 318-19."""
    fc = conc.fc
    fy = steel.fy
    eps_y = steel.eps_y
    if fyt_MPa is None:
        fyt_MPa = fy
    tie_txt = T("đai rời (tied)", lang) if tied else T("đai xoắn (spiral)", lang)
    phi_c = 0.65 if tied else 0.75

    N = getattr(inp, "N", 0.0) or 0.0
    M2 = getattr(inp, "Mx", 0.0) or 0.0
    M3 = getattr(inp, "My", 0.0) or 0.0
    Q2 = abs(getattr(inp, "Q2", 0.0) or 0.0)
    Q3 = abs(getattr(inp, "Q3", 0.0) or 0.0)

    sections: List[Dict[str, Any]] = []

    # ---- 1. Vật liệu ----
    sections.append({
        "num": 1,
        "title": T("ĐẶC TRƯNG VẬT LIỆU", lang),
        "ref": T("ACI 318-19 Chương 19 & 20", lang),
        "cards": [
            _mk(T("Bê tông", lang),
                "ACI 19.2.2.1, 22.2.2.1",
                [f"f'c = {_fm(fc)} MPa",
                 f"Ec = 4700√f'c = {_f(conc.Ec, 0)} MPa",
                 "εcu = 0.003",
                 f"β1 = {_f(conc.beta1, 4)}",
                 f"0.85f'c = {_f(conc.f_block, 2)} MPa"],
                ""),
            _mk(T("Cốt thép dọc", lang),
                "ACI 20.2.2",
                [f"fy = {_fm(fy)} MPa",
                 "Es = 200000 MPa",
                 f"εy = {_f(eps_y, 5)}"],
                ""),
            _mk(T("Cốt thép đai", lang),
                "ACI 20.2.2",
                [f"fyt = {_fm(fyt_MPa)} MPa",
                 "Es = 200000 MPa",
                 T("Loại: {t}", lang).format(t=tie_txt)],
                ""),
            _mk(T("Hệ số sức kháng φ", lang),
                "ACI 21.2.2",
                [f"φc = {_f(phi_c, 2)} ({tie_txt})",
                 T("φ tại B = {v}", lang).format(v=_f(aci_res.get('phi', phi_c), 2))],
                ""),
        ],
    })

    # ---- 2. Tiết diện (cấu trúc giống TCVN) ----
    Ag = sec.gross_area if hasattr(sec, 'gross_area') else 0
    Ast = sec.steel_area if hasattr(sec, 'steel_area') else 0
    cx = getattr(sec, 'cx', 0) or getattr(inp, 'cx', 0)
    cy = getattr(sec, 'cy', 0) or getattr(inp, 'cy', 0)
    cover = getattr(inp, 'cover', 40) or 40
    # Số thanh-đường kính (như TCVN)
    from collections import Counter as _Ctr
    _cnt = _Ctr(getattr(r, "dia", 0) for r in getattr(sec, "rebars", []))
    _bar_str = " + ".join(f"{_cnt[d]:.0f}d{d:.0f}"
                          for d in sorted(_cnt, reverse=True)) if _cnt else "—"
    # I, i (tiết diện chữ nhật)
    _Ix = cx * cy**3 / 12 if cx and cy else 0
    _Iy = cy * cx**3 / 12 if cx and cy else 0
    _ix = math.sqrt(_Ix / Ag) if Ag > 0 else 0
    _iy = math.sqrt(_Iy / Ag) if Ag > 0 else 0
    _rho = 100 * Ast / Ag if Ag > 0 else 0
    sections.append({
        "num": 2,
        "title": T("ĐẶC TRƯNG HÌNH HỌC TIẾT DIỆN", lang),
        "ref": "",
        "cards": [
            _mk(T("Diện tích tiết diện bê tông nguyên Ag", lang),
                "",
                [f"Ag = b × h",
                 f"= {_f(cx, 0)} × {_f(cy, 0)}",
                 f"= {_f(Ag, 0)} mm² (= {_f(Ag/1e6, 4)} m²)"],
                ""),
            _mk(T("Diện tích cốt thép dọc Ast", lang),
                "",
                [T("Số thanh: {b}", lang).format(b=_bar_str),
                 T("Tổng Ast = {v} mm²", lang).format(v=_f(Ast, 0)),
                 T("Hàm lượng ρg = {v}%", lang).format(v=_f(_rho, 2))],
                ""),
            _mk(T("Mô men quán tính trục 2 (I2)", lang),
                "",
                [f"I₂ = (b × h³) / 12",
                 f"= ({_f(cx, 0)} × {_f(cy, 0)}³) / 12",
                 f"= {_f(_Ix/1e9, 3)} × 10⁹ mm⁴"],
                ""),
            _mk(T("Mô men quán tính trục 3 (I3)", lang),
                "",
                [f"I₃ = (h × b³) / 12",
                 f"= ({_f(cy, 0)} × {_f(cx, 0)}³) / 12",
                 f"= {_f(_Iy/1e9, 3)} × 10⁹ mm⁴"],
                ""),
            _mk(T("Bán kính quán tính phương 2 (i2)", lang),
                "",
                [f"i₂ = √(I₂ / Ag)",
                 f"= {_f(_ix, 2)} mm (= {_f(_ix/1000, 4)} m)"],
                ""),
            _mk(T("Bán kính quán tính phương 3 (i3)", lang),
                "",
                [f"i₃ = √(I₃ / Ag)",
                 f"= {_f(_iy, 2)} mm (= {_f(_iy/1000, 4)} m)"],
                ""),
        ],
    })

    # ---- 3. Chiều dài tính toán & độ mảnh ----
    _mm = mm_res or {}
    _L02 = _mm.get("L0_2", 0) or 0
    _L03 = _mm.get("L0_3", 0) or 0
    _k2 = _mm.get("k2", 1.0) or 1.0
    _k3 = _mm.get("k3", 1.0) or 1.0
    _klr2 = _k2 * _L02 * 1000 / _ix if _ix > 0 else 0
    _klr3 = _k3 * _L03 * 1000 / _iy if _iy > 0 else 0
    sections.append({
        "num": 3,
        "title": T("CHIỀU DÀI TÍNH TOÁN & ĐỘ MẢNH", lang),
        "ref": "ACI 6.6.4",
        "cards": [
            _mk(T("Chiều dài tính toán", lang),
                "ACI 6.6.4.4",
                [f"L0,2 = k×lu = {_f(_k2, 2)} × {_f(_L02/_k2 if _k2 else 0, 2)}",
                 f"= {_f(_L02, 2)} m",
                 f"L0,3 = {_f(_L03, 2)} m"],
                ""),
            _mk(T("Bán kính quán tính r", lang),
                "ACI 6.6.4.3.1",
                [T("r ≈ 0.3h (tiết diện chữ nhật)", lang),
                 f"r2 = {_f(_ix, 1)} mm",
                 f"r3 = {_f(_iy, 1)} mm"],
                ""),
            _mk(T("Tỉ số độ mảnh klu/r", lang),
                "ACI 6.6.4.1",
                [f"(klu/r)₂ = {_f(_k2, 2)}×{_f(_L02*1000, 0)}/{_f(_ix, 1)}",
                 f"= {_f(_klr2, 1)}",
                 f"(klu/r)₃ = {_f(_klr3, 1)}"],
                ""),
            _mk(T("Giới hạn độ mảnh", lang),
                "ACI 6.6.4.1",
                [T("Khung không chuyển vị: klu/r ≤ 34 - 12(M1/M2) ≤ 40", lang),
                 T("Khung chuyển vị: klu/r ≤ 22", lang),
                 (T("→ Xét uốn dọc", lang) if max(_klr2, _klr3) > 22 else T("→ Bỏ qua uốn dọc", lang))],
                ""),
        ],
    })

    # ---- 4. Độ lệch tâm ----
    _Nabs = abs(N) if abs(N) > 1e-9 else 1.0
    e2 = abs(M2/_Nabs*1000)
    e3 = abs(M3/_Nabs*1000)
    # M2,min theo ACI 6.6.4.5.4
    _h2 = cy
    _h3 = cx
    _Mmin2 = _Nabs * (15 + 0.03 * _h2) / 1000  # kN×m (15mm + 0.03h)
    _Mmin3 = _Nabs * (15 + 0.03 * _h3) / 1000
    sections.append({
        "num": 4,
        "title": T("ĐỘ LỆCH TÂM", lang),
        "ref": "ACI 6.6.4.5.4",
        "cards": [
            _mk(T("Mô men tối thiểu phương 2 (Mmin,2)", lang),
                "ACI 6.6.4.5.4",
                [f"Mmin = Pu×(15 + 0.03h)",
                 f"Mmin,2 = {_f(_Nabs, 1)} × (15 + 0.03×{_f(_h2, 0)})/1000",
                 f"= {_f(_Mmin2, 1)} kN×m"],
                ""),
            _mk(T("Mô men tối thiểu phương 3 (Mmin,3)", lang),
                "ACI 6.6.4.5.4",
                [f"Mmin = Pu×(15 + 0.03h)",
                 f"Mmin,3 = {_f(_Nabs, 1)} × (15 + 0.03×{_f(_h3, 0)})/1000",
                 f"= {_f(_Mmin3, 1)} kN×m"],
                ""),
            _mk(T("Độ lệch tâm phương 2 (e2)", lang),
                "ACI 6.6.4.5.4",
                [f"e₂ = |M₂| / N",
                 f"= ({_f(abs(M2), 2)} × 10³) / {_f(_Nabs, 1)}",
                 f"= {_f(e2, 1)} mm"],
                ""),
            _mk(T("Độ lệch tâm phương 3 (e3)", lang),
                "ACI 6.6.4.5.4",
                [f"e₃ = |M₃| / N",
                 f"= ({_f(abs(M3), 2)} × 10³) / {_f(_Nabs, 1)}",
                 f"= {_f(e3, 1)} mm"],
                ""),
        ],
    })

    # ---- 5. Phóng đại mô men (chi tiết như TCVN) ----
    if "dir2" in _mm:
        _d2 = _mm.get("dir2", {})
        _d3 = _mm.get("dir3", {})
        _dl2 = _mm.get("delta2", 1.0)
        _dl3 = _mm.get("delta3", 1.0)
        _pc2 = _d2.get("Pc_kN", 0) or 0
        _pc3 = _d3.get("Pc_kN", 0) or 0
        _cm2 = _d2.get("Cm", 1.0) or 1.0
        _cm3 = _d3.get("Cm", 1.0) or 1.0
        _beta = _d2.get("beta_dns", 0.6)
        # Nguồn beta_dns: từ TX_ hay mặc định
        _beta_lines = []
        _bs = _mm.get("beta_src", "")
        if _bs and "TX_" in _bs:
            # _bs dạng "TX_ (926/943)"
            import re as _re
            _m = _re.search(r"\((\d+)/([\d.]+)\)", _bs)
            if _m:
                _n_sus, _n_tot = _m.group(1), _m.group(2)
                _beta_lines = [
                    T("βdns = N_thường_xuyên / N_tính_toán", lang),
                    f"= {_n_sus} / {_n_tot}",
                    f"= {_f(_beta, 3)}",
                ]
            else:
                _beta_lines = [f"βdns = {_f(_beta, 3)} " + T("(từ {s})", lang).format(s=_bs)]
        else:
            _beta_lines = [T("βdns = {v} (mặc định)", lang).format(v=_f(_beta, 3))]
        _cards5 = [
            _mk(T("Tải trọng tới hạn Euler Pc", lang),
                "ACI 6.6.4.4.2",
                [f"EI = 0.4×Ec×Ig / (1 + βdns)"] + _beta_lines + [
                 f"Pc = π²×EI / (k×lu)²",
                 f"Pc2 = {_f(_pc2, 0)} kN",
                 f"Pc3 = {_f(_pc3, 0)} kN"],
                ""),
            _mk(T("Hệ số mô men tương đương Cm", lang),
                "ACI 6.6.4.5.3",
                [T("(a) Không tải ngang: Cm = 0.6 − 0.4×(M1/M2) ≥ 0.4", lang),
                 T("(b) Có tải ngang giữa nhịp: Cm = 1.0", lang),
                 T("→ Chọn Cm = 1.0 theo (b)", lang),
                 f"Cm2 = {_f(_cm2, 3)}",
                 f"Cm3 = {_f(_cm3, 3)}"],
                ""),
            _mk(T("Hệ số phóng đại δns", lang),
                "ACI 6.6.4.5.2",
                [f"δns = Cm / [1 - Pu/(0.75×Pc)] ≥ 1.0",
                 f"δns2 = {_f(_cm2, 3)} / [1 - {_f(abs(N), 1)}/(0.75×{_f(_pc2, 0)})]",
                 f"= {_f(_dl2, 3)}",
                 f"δns3 = {_f(_cm3, 3)} / [1 - {_f(abs(N), 1)}/(0.75×{_f(_pc3, 0)})]",
                 f"= {_f(_dl3, 3)}"],
                ""),
            _mk(T("Mô men sau phóng đại", lang),
                "ACI 6.6.4.5.1",
                [f"M2* = δns2 × M2",
                 f"= {_f(_dl2, 3)} × {_f(M2, 1)}",
                 f"= {_f(M2*_dl2, 1)} kN×m",
                 f"M3* = δns3 × M3",
                 f"= {_f(_dl3, 3)} × {_f(M3, 1)}",
                 f"= {_f(M3*_dl3, 1)} kN×m"],
                ""),
        ]
    else:
        delta_ns = _mm.get("delta_ns", 1.0)
        _cards5 = [
            _mk(T("Hệ số phóng đại δns", lang),
                "ACI 6.6.4.5.2",
                [f"δns = {_f(delta_ns, 3)}"],
                f"δns = {_f(delta_ns, 3)}"),
        ]
    # Dùng delta riêng từng phương nếu có, ngược lại dùng delta_ns chung
    try:
        M2_star = M2 * _dl2
        M3_star = M3 * _dl3
    except NameError:
        M2_star = M2 * delta_ns
        M3_star = M3 * delta_ns
    sections.append({
        "num": 5,
        "title": T("PHÓNG ĐẠI MÔ MEN UỐN DỌC", lang),
        "ref": "ACI 6.6.4.5",
        "cards": _cards5,
    })

    # ---- 6. Kiểm tra P-M-M ----
    dc = aci_res.get("dc", 0.0) or 0.0
    fs = aci_res.get("fs", 0.0) or 0.0
    # Tính FS từ D/C nếu không có (chế độ ETABS)
    _dc_tmp = aci_res.get("dc", 0) or 0
    if not fs and _dc_tmp and _dc_tmp > 1e-9:
        fs = 1.0 / _dc_tmp
    Bx = aci_res.get("Bx", 0.0) or 0.0
    By = aci_res.get("By", 0.0) or 0.0
    BN = aci_res.get("BN", 0.0) or 0.0
    pm_ok = bool(aci_res.get("ok", False))
    # Dùng alpha/Malpha đã tính 1 lần trong _aci_calculate_full (nguyên tắc single source)
    Ma = aci_res.get("Malpha", math.hypot(M2_star, M3_star))
    alpha = aci_res.get("alpha_deg", math.degrees(math.atan2(M2_star, M3_star)) % 360.0 if Ma > 1e-9 else 0.0)
    sections.append({
        "num": 6,
        "title": T("ĐÁNH GIÁ KHẢ NĂNG CHỊU LỰC NÉN UỐN XIÊN (P-M-M)", lang),
        "ref": "ACI 22.4",
        "cards": [
            _mk(T("Điểm nội lực tính toán A (Nội lực tác dụng)", lang),
                "",
                [f"A = (M2*, M3*, N)",
                 f"= ({_f(M2_star, 1)}, {_f(M3_star, 1)}, {_f(N, 1)})",
                 f"= |OA| = {_f(math.sqrt(M2_star**2 + M3_star**2 + N**2), 1)} kN/kNm"],
                ""),
            _mk(T("Điểm giới hạn B (trên mặt tương tác)", lang),
                "",
                [T("B = (M2gh, M3gh, Ngh)", lang),
                 f"= ({_f(Bx, 1)}, {_f(By, 1)}, {_f(BN, 1)})",
                 f"= |OB| = {_f(math.sqrt(Bx**2 + By**2 + BN**2), 1)} kN/kNm"],
                ""),
            _mk(T("Góc uốn xiên α", lang),
                "",
                [f"α = {_f(alpha, 1)}°",
                 f"Mα = {_f(Ma, 1)} kN×m"],
                ""),
            _mk(T("Tỷ số D/C", lang),
                "",
                [f"D/C = |OA| / |OB| = {_f(math.sqrt(M2_star**2 + M3_star**2 + N**2), 1)} / {_f(math.sqrt(Bx**2 + By**2 + BN**2), 1)}",
                 f"= {_f(dc, 3)} (FS = {_f(fs, 2)})"],
                "",
                 dc_conclusion=True, dc=dc, fs=fs, ok=pm_ok),
        ],
    })

    # ---- 7. Kiểm tra cắt (2 phương) ----
    # Card cấu tạo đai (như TCVN)
    _sw_dia = getattr(inp, "sw_dia", 10) or 10
    _sw_s = getattr(inp, "sw_spacing", 100) or 100
    _sw_legs = getattr(inp, "sw_legs", 2) or 2
    _dia_max = max((getattr(r, "dia", 0) for r in getattr(sec, "rebars", [])), default=25)
    # Dấu ✓/✗ tính từ điều kiện thật (không hard-code)
    _dia_req = max(0.25 * _dia_max, 10)
    _s_lim = min(16 * _dia_max, 48 * _sw_dia, min(cx, cy))
    _mk_d = "✓" if _sw_dia >= _dia_req - 1e-9 else "✗"
    _mk_s = "✓" if _sw_s <= _s_lim + 1e-9 else "✗"
    _cfg_card = _mk(T("Cấu tạo cốt đai (25.7.2)", lang),
                "ACI 25.7.2",
                [T("{m} Đường kính đai (25.7.2.2): yêu cầu ≥ max(0.25×{dmax:.0f}, 10) = {dreq:.1f} mm, chọn φ{sdia:.0f}", lang).format(m=_mk_d, dmax=_dia_max, dreq=_dia_req, sdia=_sw_dia),
                 T("{m} Bước đai (25.7.2.1): yêu cầu ≤ min(16×{dmax:.0f}, 48×{sdia:.0f}, min(b,h)) = {slim:.0f} mm, chọn {s:.0f} mm", lang).format(m=_mk_s, dmax=_dia_max, sdia=_sw_dia, slim=_s_lim, s=_sw_s),
                 T("Số nhánh đai: {n} nhánh", lang).format(n=_sw_legs)],
                "")
    _sh = shear_res or {}
    _d2 = _sh.get("dir2", {}) if isinstance(_sh.get("dir2"), dict) else {}
    _d3 = _sh.get("dir3", {}) if isinstance(_sh.get("dir3"), dict) else {}
    # Fallback: dùng key cũ nếu không có dir2/dir3
    if not _d2 and not _d3:
        _d2 = _sh
    def _sh_card(d, Q, label):
        Vc = d.get("Vc_kN", 0.0) or 0.0
        Vs = d.get("Vs_kN", 0.0) or 0.0
        phi_Vn = d.get("phi_Vn_kN", 0.0) or 0.0
        ok = bool(d.get("ok", False))
        # Lấy thông tin b, d, Av từ inp/sec (giống TCVN)
        _dnum = "2" if "V2" in label else "3"
        _cx = getattr(sec, "cx", 0) or 0
        _cy = getattr(sec, "cy", 0) or 0
        _cover = getattr(inp, "cover", 40) or 40
        # b, d theo phương
        if _dnum == "2":
            _b = _cy  # b = t2
            _d_eff = _cx - _cover - _sw_dia - 12
            _mdia = getattr(inp, "swm2_dia", 0) or 0
            _ms = getattr(inp, "swm2_spacing", 0) or 0
            _mlegs = getattr(inp, "swm2_legs", 0) or 0
        else:
            _b = _cx  # b = t3
            _d_eff = _cy - _cover - _sw_dia - 12
            _mdia = getattr(inp, "swm3_dia", 0) or 0
            _ms = getattr(inp, "swm3_spacing", 0) or 0
            _mlegs = getattr(inp, "swm3_legs", 0) or 0
        # Tính Av (bao + giữa)
        _Av_outer = _sw_legs * math.pi * (_sw_dia ** 2) / 4
        _Av_mid = _mlegs * math.pi * (_mdia ** 2) / 4 if _mdia > 0 else 0.0
        _Av_tot = _Av_outer + _Av_mid
        if _Av_mid > 0:
            _sw_txt = f"{_sw_legs}φ{_sw_dia:.0f} a{_sw_s:.0f} + {_mlegs}φ{_mdia:.0f} a{_ms:.0f}"
        else:
            _sw_txt = f"{_sw_legs}φ{_sw_dia:.0f} a{_sw_s:.0f}"
        # Ưu tiên thông số hiển thị đã tính 1 lần (shear_disp của
        # _aci_calculate_full) để khớp tab tuyệt đối
        try:
            _dp = (aci_res.get("shear_disp") or {}).get(_dnum, {})
            if _dp:
                _b = _dp.get("b", _b)
                _d_eff = _dp.get("d", _d_eff)
                _Av_tot = _dp.get("Av", _Av_tot)
                _sw_txt = _dp.get("sw_txt", _sw_txt)
        except Exception:
            pass
        _mark = "✓" if ok else "✗"
        _ci = d.get("combo_info", "") or ""
        _lines = [
            f"Vu = {_f(abs(Q), 1)} kN" + (f" {_ci}" if _ci else ""),
            f"b = {_b:.0f} mm, d = {_d_eff:.0f} mm",
            f"Av = {_sw_txt} = {_Av_tot:.0f} mm²",
            f"Vc = max[0.17λ√f'c, 0.66λsλ(ρw)⅓√f'c]×bw×d = {_f(Vc, 1)} kN",
            f"Vs = Av×fyt×d/s = {_f(Vs, 1)} kN",
            f"φVn = 0.75×(Vc+Vs) = {_f(phi_Vn, 1)} kN",
            T("{m} So sánh: Vu = {q} kN {op} φVn = {v} kN", lang).format(
                m=_mark, q=_f(abs(Q), 1), op=("≤" if abs(Q) <= phi_Vn else ">"),
                v=_f(phi_Vn, 1)),
        ]
        return _mk(T("Kiểm tra chịu cắt phương {n}", lang).format(n=_dnum),
                    "ACI 22.5.5.1",
                    _lines,
                    T("Kết luận: ĐẠT", lang) if ok else T("Kết luận: KHÔNG ĐẠT", lang))
    _ok2 = bool(_d2.get("ok", False)) if _d2 else True
    _ok3 = bool(_d3.get("ok", False)) if _d3 else True
    _cfg_card["full"] = True
    _cards7 = [_cfg_card, _sh_card(_d2, Q2, "V2")]
    if _d3:
        _cards7.append(_sh_card(_d3, Q3, "V3"))

    sections.append({
        "num": 7,
        "title": T("KIỂM TRA KHẢ NĂNG CHỊU CẮT", lang),
        "ref": "ACI 22.5",
        "cards": _cards7,
    })

    return sections
