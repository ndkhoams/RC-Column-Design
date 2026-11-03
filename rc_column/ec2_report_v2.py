"""Thuyết minh kiểm tra cột theo EC2 — cấu trúc 7 mục theo mẫu TCVN."""

import math
from typing import Any, Dict, List

from .lang import T


def _f(x: float, nd: int = 2) -> str:
    if x is None or not math.isfinite(x):
        return "—"
    return f"{x:.{nd}f}"


def _fm(x):
    """Định dạng cường độ tra bảng/nhập liệu: in ĐÚNG giá trị thật, cắt số 0
    thừa ở cuối (460.5 -> '460.5', 500 -> '500'). Không dùng cho giá trị
    suy ra bằng phép chia (fcd/fyd giữ quy ước thập phân hiện tại)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(v):
        return "—"
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _mk(title: str, ref: str, lines: List[str], result: str = "", dc_conclusion: bool = False, dc: float = 0.0, fs: float = 0.0, ok: bool = True, shear_conclusion: bool = False) -> Dict[str, Any]:
    return {"title": title, "ref": ref, "lines": lines, "result": result, "dc_conclusion": dc_conclusion, "dc": dc, "fs": fs, "ok": ok, "shear_conclusion": shear_conclusion, "full": False, "conclusion": False}


def generate_ec2_report_sections_v2(inp, ec2_res: Dict[str, Any],
                                    slend_res: Dict[str, Any],
                                    shear_res: Dict[str, Any],
                                    conc, steel, sec,
                                    lang: str = "VN") -> List[Dict[str, Any]]:
    """Tạo 7 mục thuyết minh theo mẫu TCVN cho EC2."""
    fck = conc.fck
    fyk = steel.fyk
    fyk_sw = ec2_res.get("fyk_sw")
    if fyk_sw is None:
        fyk_sw = fyk

    NEd = getattr(inp, "N", 0.0) or 0.0
    # MEd2/MEd3 ở §5/§6 là mô men THIẾT KẾ đã gồm bậc 2 và CÓ DẤU
    # (không phải mô men gốc inp.Mx/My — gốc cho α = 286.7°/Mα = 208.8
    # trong khi tia kiểm tra D/C dùng mô men thiết kế 285.4°/244.4).
    from .ec2_chart_draw import ec2_signed_design_moments
    MEd2, MEd3 = ec2_signed_design_moments(ec2_res, inp)
    VEd2 = abs(getattr(inp, "Q2", 0.0) or 0.0)
    VEd3 = abs(getattr(inp, "Q3", 0.0) or 0.0)

    sections: List[Dict[str, Any]] = []

    # ---- 1. Vật liệu ----
    sections.append({
        "num": 1,
        "title": T("ĐẶC TRƯNG VẬT LIỆU", lang),
        "ref": "EC2 3.1, 3.2",
        "cards": [
            _mk(T("Bê tông", lang),
                "EC2 3.1",
                [f"fck = {_fm(fck)} MPa",
                 f"fcd = {_f(conc.fcd, 2)} MPa",
                 f"Ecm = {_f(conc.Ecm, 0)} MPa"],
                ""),
            _mk(T("Cốt thép dọc", lang),
                "EC2 3.2",
                [f"fyk = {_fm(fyk)} MPa",
                 f"fyd = {_f(steel.fyd, 1)} MPa",
                 "Es = 200000 MPa"],
                ""),
            _mk(T("Cốt thép đai", lang),
                "EC2 3.2",
                [T("fyk,đai = {v} MPa", lang).format(v=_fm(fyk_sw)),
                 "Es = 200000 MPa"],
                ""),
        ],
    })

    # ---- 2. Tiết diện ----
    Ag = sec.gross_area if hasattr(sec, 'gross_area') else 0
    Ast = sec.steel_area if hasattr(sec, 'steel_area') else 0
    cx = getattr(sec, 'cx', 0) or getattr(inp, 'cx', 0)
    cy = getattr(sec, 'cy', 0) or getattr(inp, 'cy', 0)
    cover = getattr(inp, 'cover', 40) or 40
    from collections import Counter as _Ctr
    _cnt = _Ctr(getattr(r, "dia", 0) for r in getattr(sec, "rebars", []))
    _bar_str = " + ".join(f"{_cnt[d]:.0f}d{d:.0f}"
                          for d in sorted(_cnt, reverse=True)) if _cnt else "—"
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
            _mk(T("Diện tích tiết diện bê tông nguyên Ac", lang),
                "",
                [f"Ac = t2 × t3",
                 f"= {_f(cx, 0)} × {_f(cy, 0)}",
                 f"= {_f(Ag, 0)} mm² (= {_f(Ag/1e6, 4)} m²)"],
                ""),

            _mk(T("Diện tích cốt thép dọc As", lang),
                "",
                [T("Số thanh: {b}", lang).format(b=_bar_str),
                 T("Tổng As = {v} mm²", lang).format(v=_f(Ast, 0)),
                 T("Hàm lượng ρ = {v}%", lang).format(v=_f(_rho, 2))],
                ""),
            _mk(T("Mô men quán tính trục 2 (I2)", lang),
                "",
                [f"I₂ = (t3 · t2³) / 12",
                 f"= ({_f(cx, 0)} × {_f(cy, 0)}³) / 12",
                 f"= {_f(_Ix/1e9, 3)} × 10⁹ mm⁴"],
                ""),
            _mk(T("Mô men quán tính trục 3 (I3)", lang),
                "",
                [f"I₃ = (t2 · t3³) / 12",
                 f"= ({_f(cy, 0)} × {_f(cx, 0)}³) / 12",
                 f"= {_f(_Iy/1e9, 3)} × 10⁹ mm⁴"],
                ""),
            _mk(T("Bán kính quán tính phương 2 (i2)", lang),
                "",
                [f"i₂ = √(I₂ / Ac)",
                 f"= {_f(_ix, 2)} mm (= {_f(_ix/1000, 4)} m)"],
                ""),
            _mk(T("Bán kính quán tính phương 3 (i3)", lang),
                "",
                [f"i₃ = √(I₃ / Ac)",
                 f"= {_f(_iy, 2)} mm (= {_f(_iy/1000, 4)} m)"],
                ""),
        ],
    })

    # ---- 3. Chiều dài tính toán & độ mảnh ----
    _sl = slend_res or {}
    _l02 = _sl.get("l0_2", 0) or _sl.get("l02", 0) or 0
    _l03 = _sl.get("l0_3", 0) or _sl.get("l03", 0) or 0
    _lam2 = _sl.get("lambda_2", 0) or _sl.get("lam2", 0) or 0
    _lam3 = _sl.get("lambda_3", 0) or _sl.get("lam3", 0) or 0
    sections.append({
        "num": 3,
        "title": T("CHIỀU DÀI TÍNH TOÁN & ĐỘ MẢNH", lang),
        "ref": "EC2 5.8.3",
        "cards": [
            _mk(T("Chiều dài tính toán", lang),
                "EC2 5.8.3.2",
                [f"l0,2 = {_f(_l02, 2)} m",
                 f"l0,3 = {_f(_l03, 2)} m"],
                ""),
            _mk(T("Độ mảnh", lang),
                "EC2 5.8.3.1",
                [f"λ2 = l0/i = {_f(_lam2, 1)}",
                 f"λ3 = l0/i = {_f(_lam3, 1)}",
                 "λlim = 20·A·B·C/√n"],
                ""),
        ],
    })

    # ---- 4. Sai lệch & độ lệch tâm ----
    _Nabs = abs(NEd) if abs(NEd) > 1e-9 else 1.0
    e2 = abs(MEd2/_Nabs*1000)
    e3 = abs(MEd3/_Nabs*1000)
    # Tính ei chi tiết (EC2 5.2)
    import math as _m
    _l0max = max(_l02, _l03)
    _theta0 = 1/200
    _alpha_h = 2/_m.sqrt(_l0max) if _l0max > 0 else 1.0
    _alpha_h = max(2/3, min(1.0, _alpha_h))
    _theta_i = _theta0 * _alpha_h  # αm = 1 (cột đơn)
    _ei = _theta_i * _l0max / 2 * 1000  # mm
    _emin = max(max(cx, cy)/30, 20)
    sections.append({
        "num": 4,
        "title": T("ĐỘ LỆCH TÂM", lang),
        "ref": "EC2 6.1(4)",
        "cards": [
            _mk(T("Độ lệch tâm phương 2 (e2)", lang),
                "EC2 6.1(4)",
                [f"e₂ = |MEd2| / NEd",
                 f"= ({_f(abs(MEd2), 2)} × 10³) / {_f(_Nabs, 1)}",
                 f"= {_f(e2, 1)} mm"],
                ""),
            _mk(T("Độ lệch tâm phương 3 (e3)", lang),
                "EC2 6.1(4)",
                [f"e₃ = |MEd3| / NEd",
                 f"= ({_f(abs(MEd3), 2)} × 10³) / {_f(_Nabs, 1)}",
                 f"= {_f(e3, 1)} mm"],
                ""),
        ],
    })

    # ---- 5. Hiệu ứng bậc 2 ----
    _d2 = slend_res.get("dir2", {}) if isinstance(slend_res, dict) else {}
    _d3 = slend_res.get("dir3", {}) if isinstance(slend_res, dict) else {}
    _m5 = _d2.get("method", "") or "stiffness"
    _mname = (T("Độ cứng danh nghĩa (5.8.7)", lang) if "stiff" in str(_m5)
              else T("Độ cong danh nghĩa (5.8.8)", lang))
    _lam_lim = _d2.get("lambda_lim", 0) or 0
    sections.append({
        "num": 5,
        "title": T("HIỆU ỨNG BẬC 2", lang),
        "ref": "EC2 5.8",
        "cards": [
            _mk(T("Kiểm tra bỏ qua hiệu ứng bậc 2", lang),
                "EC2 5.8.3.1",
                [f"λlim = 20·A·B·C/√n = {_f(_lam_lim, 1)}",
                 T("Phương 2: λ2 = {a} {op} λlim = {b} → {c}", lang).format(
                     a=_f(_lam2, 1), op="≤" if _lam2 <= _lam_lim else ">",
                     b=_f(_lam_lim, 1),
                     c=T("Bỏ qua", lang) if _lam2 <= _lam_lim else T("Xét bậc 2", lang)),
                 T("Phương 3: λ3 = {a} {op} λlim = {b} → {c}", lang).format(
                     a=_f(_lam3, 1), op="≤" if _lam3 <= _lam_lim else ">",
                     b=_f(_lam_lim, 1),
                     c=T("Bỏ qua", lang) if _lam3 <= _lam_lim else T("Xét bậc 2", lang))],
                ""),
            _mk(T("Mô men thiết kế MEd", lang),
                "EC2 5.8.7 / 5.8.8" if max(_lam2, _lam3) > _lam_lim else "",
                [T("Phương pháp: {m}", lang).format(m=_mname) if max(_lam2, _lam3) > _lam_lim
                 else T("Không cần xét bậc 2 → MEd = M0Ed (mô men bậc 1)", lang),
                 f"MEd = M0Ed + M2" if max(_lam2, _lam3) > _lam_lim else "",
                 f"MEd2 = {_f(MEd2, 1)} kN·m",
                 f"MEd3 = {_f(MEd3, 1)} kN·m"],
                ""),
        ],
    })

    # ---- 6. Kiểm tra N-M ----
    dc = ec2_res.get("dc", 0.0) or 0.0
    fs = ec2_res.get("fs", 0.0) or 0.0
    Bx = ec2_res.get("Bx", 0.0) or 0.0
    By = ec2_res.get("By", 0.0) or 0.0
    BN = ec2_res.get("BN", 0.0) or 0.0
    pm_ok = bool(ec2_res.get("ok", False))
    Ma = math.hypot(MEd2, MEd3)
    alpha = math.degrees(math.atan2(MEd2, MEd3)) % 360.0 if Ma > 1e-9 else 0.0
    sections.append({
        "num": 6,
        "title": T("ĐÁNH GIÁ KHẢ NĂNG CHỊU LỰC NÉN UỐN XIÊN (NEd-MEd)", lang),
        "ref": "EC2 6.1",
        "cards": [
            _mk(T("Điểm nội lực tính toán A (Nội lực tác dụng)", lang),
                "",
                [f"A = (MEd2, MEd3, NEd)",
                 f"= ({_f(MEd2, 1)}, {_f(MEd3, 1)}, {_f(NEd, 1)})",
                 f"= |OA| = {_f(math.sqrt(MEd2**2 + MEd3**2 + NEd**2), 1)} kN/kNm"],
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
                 f"Mα = {_f(Ma, 1)} kN·m"],
                ""),
            _mk(T("Tỷ số D/C", lang),
                "",
                [f"D/C = |OA| / |OB| = {_f(math.sqrt(MEd2**2 + MEd3**2 + NEd**2), 1)} / {_f(math.sqrt(Bx**2 + By**2 + BN**2), 1)}",
                 f"= {_f(dc, 3)} (FS = {_f(fs, 2)})"],
                "",
                 dc_conclusion=True, dc=dc, fs=fs, ok=pm_ok),
        ],
    })

    # ---- 7. Kiểm tra cắt ----
    _sw_dia = getattr(inp, "sw_dia", 10) or 10
    _sw_s = getattr(inp, "sw_spacing", 100) or 100
    _dia_max = max((getattr(r, "dia", 0) for r in getattr(sec, "rebars", [])), default=25)
    # Dấu ✓/✗ tính từ điều kiện thật (không hard-code)
    _dia_req_e = max(6, 0.25 * _dia_max)
    _s_lim_e = min(20 * _dia_max, min(cx, cy), 400)
    _mk_de = "✓" if _sw_dia >= _dia_req_e - 1e-9 else "✗"
    _mk_se = "✓" if _sw_s <= _s_lim_e + 1e-9 else "✗"
    _cfg_card = _mk(T("Cấu tạo cốt đai (9.5.3)", lang),
                "EC2 9.5.3",
                [T("{m} Đường kính đai (9.5.3(1)): yêu cầu ≥ max(6, 0.25×{dmax:.0f}) = {dreq:.1f} mm, chọn φ{sdia:.0f}", lang).format(
                     m=_mk_de, dmax=_dia_max, dreq=_dia_req_e, sdia=_sw_dia),
                 T("{m} Bước đai (9.5.3(3)): yêu cầu ≤ min(20×{dmax:.0f}, min(b,h), 400) = {slim:.0f} mm, chọn {s:.0f} mm", lang).format(
                     m=_mk_se, dmax=_dia_max, slim=_s_lim_e, s=_sw_s)],
                "")
    def _sh_card(d: Dict[str, Any], VEd: float, lbl: str):
        _dnum = "2" if "V2" in lbl else "3"
        if not d:
            return _mk(T("Kiểm tra chịu cắt phương {n}", lang).format(n=_dnum), "", ["—"], "")
        VRd_c = d.get("VRd_c_kN", 0.0) or 0.0
        VRd_max = d.get("VRd_max_kN", 0.0) or 0.0
        VRd_s = d.get("VRd_s_kN", 0.0) or 0.0
        ok = bool(d.get("ok", False))
        bw = d.get("bw_mm", 0.0) or 0.0
        deff = d.get("d_mm", 0.0) or 0.0
        k = d.get("k", 0.0) or 0.0
        rho = d.get("rho_l", 0.0) or 0.0
        scp = d.get("sigma_cp", 0.0) or 0.0
        z_mm = d.get("z_mm", 0.0) or 0.0
        asw_req = d.get("Asw_s_req", 0.0) or 0.0
        # Thông tin đai (bao + giữa) từ inp
        _sw_dia = getattr(inp, "sw_dia", 10) or 10
        _sw_s = getattr(inp, "sw_spacing", 200) or 200
        _sw_legs = getattr(inp, "sw_legs", 2) or 2
        if _dnum == "2":
            _mdia = getattr(inp, "swm2_dia", 0) or 0
            _ms = getattr(inp, "swm2_spacing", 0) or 0
            _mlegs = getattr(inp, "swm2_legs", 0) or 0
        else:
            _mdia = getattr(inp, "swm3_dia", 0) or 0
            _ms = getattr(inp, "swm3_spacing", 0) or 0
            _mlegs = getattr(inp, "swm3_legs", 0) or 0
        _Asw_outer = _sw_legs * math.pi * (_sw_dia ** 2) / 4
        _Asw_mid = _mlegs * math.pi * (_mdia ** 2) / 4 if _mdia > 0 else 0.0
        _Asw_tot = _Asw_outer + _Asw_mid
        if _Asw_mid > 0:
            _sw_txt = f"{_sw_legs}φ{_sw_dia:.0f} a{_sw_s:.0f} + {_mlegs}φ{_mdia:.0f} a{_ms:.0f}"
        else:
            _sw_txt = f"{_sw_legs}φ{_sw_dia:.0f} a{_sw_s:.0f}"
        _mark = "✓" if ok else "✗"
        _ci = d.get("combo_info", "") or ""
        _lines = [f"VEd = {_f(VEd, 1)} kN" + (f" {_ci}" if _ci else ""),
                  f"bw = {bw:.0f} mm, d = {deff:.0f} mm",
                  f"Asw = {_sw_txt} = {_Asw_tot:.0f} mm²",
                  f"VRd,c = [CRd,c×k×(100×ρl×fck)^(1/3) + k1×σcp]×bw×d",
                  f"= [0.12×{_f(k, 2)}×(100×{_f(rho, 4)}×{_f(fck, 0)})^(1/3) + 0.15×{_f(scp, 2)}]×{_f(bw, 0)}×{_f(deff, 0)}/1000",
                  f"= {_f(VRd_c, 1)} kN",
                  f"VRd,max = αcw×bw×z×ν1×fcd/(cotθ+tanθ) = {_f(VRd_max, 1)} kN",
                  f"VRd,s = (Asw/s)×z×fywd×cotθ (θ=45°) = {_f(VRd_s, 1)} kN",
                  T("Asw/s yêu cầu = VEd/(z×fywd×cotθ) = {v} mm²/mm", lang).format(
                      v=_f(asw_req, 3))]
        # Sức kháng khống chế lấy thẳng từ kết quả checker (tính 1 lần):
        # VRd,c nếu chưa cần đai tính toán, min(VRd,s, VRd,max) nếu đã cần đai
        _VRd = d.get("VRd_kN", 0.0) or 0.0
        _lines.append(T("→ VRd (khống chế, theo checker) = {v} kN", lang).format(
            v=_f(_VRd, 1)))
        _lines.append(T("{m} So sánh: VEd = {q} kN {op} VRd = {v} kN", lang).format(
            m=_mark, q=_f(VEd, 1),
            op="≤" if VEd <= _VRd else ">", v=_f(_VRd, 1)))
        return _mk(T("Kiểm tra chịu cắt phương {n}", lang).format(n=_dnum), "EC2 6.2",
                    _lines,
                    T("Kết luận: ĐẠT", lang) if ok else T("Kết luận: KHÔNG ĐẠT", lang))

    _cfg_card["full"] = True
    if isinstance(shear_res, dict) and "dir2" in shear_res:
        _d2e = shear_res.get("dir2", {})
        _d3e = shear_res.get("dir3", {})
        _ok2e = bool(_d2e.get("ok", False)) if _d2e else True
        _ok3e = bool(_d3e.get("ok", False)) if _d3e else True
        sh_cards = [_cfg_card,
                    _sh_card(_d2e, VEd2, "V2"),
                    _sh_card(_d3e, VEd3, "V3")]

    else:
        sh_cards = [_sh_card(shear_res or {}, VEd2, "V2/V3")]
    sections.append({
        "num": 7,
        "title": T("KIỂM TRA KHẢ NĂNG CHỊU CẮT", lang),
        "ref": "EC2 6.2",
        "cards": sh_cards,
    })

    return sections
