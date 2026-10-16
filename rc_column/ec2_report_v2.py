"""Thuyết minh kiểm tra cột theo EC2 — cấu trúc 7 mục theo mẫu TCVN."""

import math
from typing import Any, Dict, List


def _f(x: float, nd: int = 2) -> str:
    if x is None or not math.isfinite(x):
        return "—"
    return f"{x:.{nd}f}"


def _mk(title: str, ref: str, lines: List[str], result: str = "", dc_conclusion: bool = False, dc: float = 0.0, fs: float = 0.0, ok: bool = True, shear_conclusion: bool = False) -> Dict[str, Any]:
    return {"title": title, "ref": ref, "lines": lines, "result": result, "dc_conclusion": dc_conclusion, "dc": dc, "fs": fs, "ok": ok, "shear_conclusion": shear_conclusion, "full": False, "conclusion": False}


def generate_ec2_report_sections_v2(inp, ec2_res: Dict[str, Any],
                                    slend_res: Dict[str, Any],
                                    shear_res: Dict[str, Any],
                                    conc, steel, sec) -> List[Dict[str, Any]]:
    """Tạo 7 mục thuyết minh theo mẫu TCVN cho EC2."""
    fck = conc.fck
    fyk = steel.fyk

    NEd = getattr(inp, "N", 0.0) or 0.0
    MEd2 = getattr(inp, "Mx", 0.0) or 0.0
    MEd3 = getattr(inp, "My", 0.0) or 0.0
    VEd2 = abs(getattr(inp, "Q2", 0.0) or 0.0)
    VEd3 = abs(getattr(inp, "Q3", 0.0) or 0.0)

    sections: List[Dict[str, Any]] = []

    # ---- 1. Vật liệu ----
    sections.append({
        "num": 1,
        "title": "ĐẶC TRƯNG VẬT LIỆU",
        "ref": "EC2 3.1, 3.2",
        "cards": [
            _mk("Bê tông",
                "EC2 3.1",
                [f"fck = {_f(fck, 0)} MPa",
                 f"fcd = {_f(conc.fcd, 2)} MPa",
                 f"Ecm = {_f(conc.Ecm, 0)} MPa"],
                ""),
            _mk("Cốt thép dọc",
                "EC2 3.2",
                [f"fyk = {_f(fyk, 0)} MPa",
                 f"fyd = {_f(steel.fyd, 1)} MPa",
                 "Es = 200000 MPa"],
                ""),
            _mk("Cốt thép đai",
                "EC2 3.2",
                [f"fyk,đai = {_f(getattr(steel, 'fyk_sw', fyk), 0)} MPa",
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
        "title": "ĐẶC TRƯNG HÌNH HỌC TIẾT DIỆN",
        "ref": "",
        "cards": [
            _mk("Diện tích tiết diện bê tông nguyên Ac",
                "",
                [f"Ac = t2 × t3",
                 f"= {_f(cx, 0)} × {_f(cy, 0)}",
                 f"= {_f(Ag, 0)} mm² (= {_f(Ag/1e6, 4)} m²)"],
                ""),

            _mk("Diện tích cốt thép dọc As",
                "",
                [f"Số thanh: {_bar_str}",
                 f"Tổng As = {_f(Ast, 0)} mm²",
                 f"Hàm lượng ρ = {_f(_rho, 2)}%"],
                ""),
            _mk("Mô men quán tính trục 2 (I2)",
                "",
                [f"I₂ = (t3 · t2³) / 12",
                 f"= ({_f(cx, 0)} × {_f(cy, 0)}³) / 12",
                 f"= {_f(_Ix/1e9, 3)} × 10⁹ mm⁴"],
                ""),
            _mk("Mô men quán tính trục 3 (I3)",
                "",
                [f"I₃ = (t2 · t3³) / 12",
                 f"= ({_f(cy, 0)} × {_f(cx, 0)}³) / 12",
                 f"= {_f(_Iy/1e9, 3)} × 10⁹ mm⁴"],
                ""),
            _mk("Bán kính quán tính phương 2 (i2)",
                "",
                [f"i₂ = √(I₂ / Ac)",
                 f"= {_f(_ix, 2)} mm (= {_f(_ix/1000, 4)} m)"],
                ""),
            _mk("Bán kính quán tính phương 3 (i3)",
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
        "title": "CHIỀU DÀI TÍNH TOÁN & ĐỘ MẢNH",
        "ref": "EC2 5.8.3",
        "cards": [
            _mk("Chiều dài tính toán",
                "EC2 5.8.3.2",
                [f"l0,2 = {_f(_l02, 2)} m",
                 f"l0,3 = {_f(_l03, 2)} m"],
                ""),
            _mk("Độ mảnh",
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
        "title": "ĐỘ LỆCH TÂM",
        "ref": "EC2 6.1(4)",
        "cards": [
            _mk("Độ lệch tâm phương 2 (e2)",
                "EC2 6.1(4)",
                [f"e₂ = |MEd2| / NEd",
                 f"= ({_f(abs(MEd2), 2)} × 10³) / {_f(_Nabs, 1)}",
                 f"= {_f(e2, 1)} mm"],
                ""),
            _mk("Độ lệch tâm phương 3 (e3)",
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
    _mname = "Độ cứng danh nghĩa (5.8.7)" if "stiff" in str(_m5) else "Độ cong danh nghĩa (5.8.8)"
    _lam_lim = _d2.get("lambda_lim", 0) or 0
    sections.append({
        "num": 5,
        "title": "HIỆU ỨNG BẬC 2",
        "ref": "EC2 5.8",
        "cards": [
            _mk("Kiểm tra bỏ qua hiệu ứng bậc 2",
                "EC2 5.8.3.1",
                [f"λlim = 20·A·B·C/√n = {_f(_lam_lim, 1)}",
                 f"Phương 2: λ2 = {_f(_lam2, 1)} {'≤' if _lam2 <= _lam_lim else '>'} λlim = {_f(_lam_lim, 1)} → {'Bỏ qua' if _lam2 <= _lam_lim else 'Xét bậc 2'}",
                 f"Phương 3: λ3 = {_f(_lam3, 1)} {'≤' if _lam3 <= _lam_lim else '>'} λlim = {_f(_lam_lim, 1)} → {'Bỏ qua' if _lam3 <= _lam_lim else 'Xét bậc 2'}"],
                ""),
            _mk("Mô men thiết kế MEd",
                "EC2 5.8.7 / 5.8.8" if max(_lam2, _lam3) > _lam_lim else "",
                [f"Phương pháp: {_mname}" if max(_lam2, _lam3) > _lam_lim else "Không cần xét bậc 2 → MEd = M0Ed (mô men bậc 1)",
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
    alpha = math.degrees(math.atan2(MEd2, MEd3)) if Ma > 1e-9 else 0.0
    sections.append({
        "num": 6,
        "title": "ĐÁNH GIÁ KHẢ NĂNG CHỊU LỰC NÉN UỐN XIÊN (NEd-MEd)",
        "ref": "EC2 6.1",
        "cards": [
            _mk("Điểm nội lực tính toán A (Nội lực tác dụng)",
                "",
                [f"A = (MEd2, MEd3, NEd)",
                 f"= ({_f(MEd2, 1)}, {_f(MEd3, 1)}, {_f(NEd, 1)})",
                 f"= |OA| = {_f(math.sqrt(MEd2**2 + MEd3**2 + NEd**2), 1)} kN/kNm"],
                ""),
            _mk("Điểm giới hạn B (trên mặt tương tác)",
                "",
                [f"B = (M2gh, M3gh, Ngh)",
                 f"= ({_f(Bx, 1)}, {_f(By, 1)}, {_f(BN, 1)})",
                 f"= |OB| = {_f(math.sqrt(Bx**2 + By**2 + BN**2), 1)} kN/kNm"],
                ""),
            _mk("Góc uốn xiên α",
                "",
                [f"α = {_f(alpha, 1)}°",
                 f"Mα = {_f(Ma, 1)} kN·m"],
                ""),
            _mk("Tỷ số D/C",
                "",
                [f"D/C = |OA| / |OB| = {_f(math.sqrt(MEd2**2 + MEd3**2 + NEd**2), 1)} / {_f(math.sqrt(Bx**2 + By**2 + BN**2), 1)}",
                 f"= {_f(dc, 3)} (FS = {_f(fs, 2)})"],
                "Kết luận: ĐẠT — D/C ≤ 1.000" if pm_ok else "✗ KHÔNG ĐẠT",
                 dc_conclusion=True, dc=dc, fs=fs, ok=pm_ok),
        ],
    })

    # ---- 7. Kiểm tra cắt ----
    _sw_dia = getattr(inp, "sw_dia", 10) or 10
    _sw_s = getattr(inp, "sw_spacing", 100) or 100
    _dia_max = max((getattr(r, "dia", 0) for r in getattr(sec, "rebars", [])), default=25)
    _cfg_card = _mk("Cấu tạo cốt đai (9.5.3)",
                "EC2 9.5.3",
                [f"✓ Đường kính đai (9.5.3(1)): yêu cầu ≥ max(6, 0.25×{_dia_max:.0f}) = {max(6, 0.25*_dia_max):.1f} mm, chọn φ{_sw_dia:.0f}",
                 f"✓ Bước đai (9.5.3(3)): yêu cầu ≤ min(20×{_dia_max:.0f}, min(b,h), 400) = {min(20*_dia_max, min(cx, cy), 400):.0f} mm, chọn {_sw_s:.0f} mm"],
                "")
    def _sh_card(d: Dict[str, Any], VEd: float, lbl: str):
        if not d:
            return _mk(f"Phương {lbl}", "", ["—"], "")
        VRd_c = d.get("VRd_c_kN", 0.0) or 0.0
        VRd_max = d.get("VRd_max_kN", 0.0) or 0.0
        VRd_s = d.get("VRd_s_kN", 0.0) or 0.0
        ok = bool(d.get("ok", False))
        bw = d.get("bw_mm", 0.0) or 0.0
        deff = d.get("d_mm", 0.0) or 0.0
        k = d.get("k", 0.0) or 0.0
        rho = d.get("rho_l", 0.0) or 0.0
        _lines = [f"VEd = {_f(VEd, 1)} kN",
                  f"VRd,c = [0.12·k·(100·ρl·fck)^(1/3)]·bw·d",
                  f"= [0.12×{_f(k, 2)}×(100×{_f(rho, 4)}×{_f(fck, 0)})^(1/3)]×{_f(bw, 0)}×{_f(deff, 0)}/1000",
                  f"= {_f(VRd_c, 1)} kN",
                  f"VRd,max = αcw·bw·z·ν1·fcd/2 = {_f(VRd_max, 1)} kN"]
        if VRd_s > 0:
            _lines.append(f"VRd,s = Asw/s·z·fyd·cotθ = {_f(VRd_s, 1)} kN")
        _VRd = max(VRd_c, VRd_s)
        _lines.append(f"→ VRd = max(VRd,c, VRd,s) = {_f(_VRd, 1)} kN")
        _lines.append(f"VEd = {_f(VEd, 1)} {'≤' if VEd <= _VRd else '>'} VRd = {_f(_VRd, 1)} kN")
        return _mk(f"Phương {lbl} (VEd = {_f(VEd, 1)} kN)", "EC2 6.2",
                    _lines,
                    "Kết luận: ĐẠT" if ok else "Kết luận: KHÔNG ĐẠT")

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
        "title": "KIỂM TRA KHẢ NĂNG CHỊU CẮT",
        "ref": "EC2 6.2",
        "cards": sh_cards,
    })

    return sections
