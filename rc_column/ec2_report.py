"""Thuyết minh kiểm tra cột theo Eurocode 2 (EN 1992-1-1).

Trả về list các section dict để GUI render (cùng cấu trúc với
report_widgets/pdf_report_cards):
- mỗi section: {'num', 'title', 'ref', 'cards'}
- mỗi card: {'title', 'ref', 'lines', 'result'}

Không phụ thuộc GUI/matplotlib.
"""

import math
from typing import Any, Dict, List


def _f(x: float, nd: int = 2) -> str:
    if x is None or not math.isfinite(x):
        return "—"
    return f"{x:.{nd}f}"


def _mk(title: str, ref: str, lines: List[str], result: str = "") -> Dict[str, Any]:
    return {"title": title, "ref": ref, "lines": lines, "result": result}


def generate_ec2_report_sections(inp, ec2_res: Dict[str, Any],
                                 slend_res: Dict[str, Any],
                                 shear_res: Dict[str, Any],
                                 conc, steel) -> List[Dict[str, Any]]:
    """Tạo các mục thuyết minh kiểm tra cột theo EC2.

    inp: ColumnInput (lấy NEd, MEd2/MEd3 đã tính bậc 2, Q2/Q3...).
    ec2_res: dict từ check_column_ec2 {dc, fs, ok, Bx, By, BN, ...}.
    slend_res: dict {'dir2': {...}, 'dir3': {...}} từ ec2_design_moment
        cho mỗi phương (hoặc dict đơn cho tương thích).
    shear_res: dict {'dir2': {...}, 'dir3': {...}} từ ec2_shear_check.
    conc: EC2Concrete, steel: EC2Steel.
    """
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
        "title": "VẬT LIỆU THEO EC2 (EN 1992-1-1)",
        "ref": "EC2 2.4.2.4, 3.1, 3.2",
        "cards": [
            _mk("Bê tông",
                "EC2 3.1",
                [f"fck = {_f(fck, 0)} MPa",
                 f"fcd = αcc·fck/γc = 1.0×{_f(fck, 0)}/1.5 = {_f(conc.fcd, 2)} MPa",
                 f"Ecm = 22000·(fcm/10)^0.3 = {_f(conc.Ecm, 0)} MPa",
                 "εcu2 = 0.0035 (biến dạng cực hạn)",
                 f"Khối ứng suất chữ nhật: η·fcd = {_f(conc.f_block, 2)} MPa, a = λ·x (λ = 0.8)"],
                f"fcd = {_f(conc.fcd, 2)} MPa"),
            _mk("Cốt thép",
                "EC2 3.2",
                [f"fyk = {_f(fyk, 0)} MPa",
                 f"fyd = fyk/γs = {_f(fyk, 0)}/1.15 = {_f(steel.fyd, 1)} MPa",
                 "Es = 200000 MPa",
                 f"εyd = fyd/Es = {_f(steel.eps_yd, 5)}",
                 "Mô hình đàn–dẻo lý tưởng, ứng suất giới hạn ở ±fyd"],
                f"fyd = {_f(steel.fyd, 1)} MPa"),
        ],
    })

    # ---- 2. Sai lệch, độ mảnh & bậc 2 ----
    def _sl_cards(d: Dict[str, Any], lbl: str):
        if not d:
            return [_mk(f"Phương {lbl}", "", ["—"], "")]
        lines = [
            f"θi = θ0·αh·αm = (1/200)×{_f(d.get('alpha_h', 0), 3)}×1.0 = {_f(d.get('theta_i', 0), 5)}",
            f"ei = θi·l0/2 = {_f(d.get('ei_mm', 0), 1)} mm",
            f"M_imp = NEd·ei = {_f(d.get('M_imp', 0), 2)} kN·m",
            f"emin = max(h/30, 20) = {_f(d.get('emin_mm', 0), 1)} mm",
            f"Mmin = NEd·emin = {_f(d.get('Mmin', 0), 2)} kN·m",
            f"λ = l0/i = {_f(d.get('lambda_sl', 0), 1)}, "
            f"λlim = 20·A·B·C/√n = {_f(d.get('lambda_lim', 0), 1)}",
        ]
        if d.get("second_order"):
            meth = "độ cứng danh nghĩa" if d.get("method") == "stiffness" else "độ cong danh nghĩa"
            lines += [
                f"Cột mảnh (λ ≥ λlim): tính bậc 2 bằng {meth}",
                f"M0Ed = {_f(d.get('so_M0Ed', 0), 2)} kN·m",
            ]
            if d.get("method") == "stiffness":
                lines += [
                    f"NB = {_f(d.get('so_NB_kN', 0), 0)} kN, "
                    f"factor = {_f(d.get('so_factor', 0), 3)}",
                ]
            else:
                lines += [
                    f"e2 = {_f(d.get('so_e2_mm', 0), 1)} mm, "
                    f"M2 = {_f(d.get('so_M2', 0), 2)} kN·m",
                ]
            lines.append(f"MEd bậc 2 = {_f(d.get('MEd_calc', 0), 2)} kN·m")
        else:
            lines.append(d.get("reason", "Không cần tính bậc 2"))
        lines.append(f"MEd thiết kế = max(MEd, Mmin) = {_f(d.get('MEd', 0), 2)} kN·m")
        ok = bool(d.get("ok", True))
        return [_mk(f"Phương {lbl}", "EC2 5.2, 5.8, 6.1(4)", lines,
                    "OK" if ok else "KHÔNG ĐẠT")]

    if isinstance(slend_res, dict) and "dir2" in slend_res:
        sl_cards = (_sl_cards(slend_res.get("dir2"), "2")
                    + _sl_cards(slend_res.get("dir3"), "3"))
    else:
        sl_cards = _sl_cards(slend_res or {}, "2/3")
    sections.append({
        "num": 2,
        "title": "SAI LỆCH THI CÔNG, ĐỘ MẢNH & HIỆU ỨNG BẬC 2",
        "ref": "EC2 5.2, 5.8, 6.1(4)",
        "cards": sl_cards,
    })

    # ---- 3. Kiểm tra P-M-M ----
    dc = ec2_res.get("dc", 0.0) or 0.0
    fs = ec2_res.get("fs", 0.0) or 0.0
    Bx = ec2_res.get("Bx", 0.0) or 0.0
    By = ec2_res.get("By", 0.0) or 0.0
    BN = ec2_res.get("BN", 0.0) or 0.0
    N_Rd_max = ec2_res.get("N_Rd_max", 0.0) or 0.0
    pm_ok = bool(ec2_res.get("ok", False))
    dc_txt = _f(dc, 3) if math.isfinite(dc) else "∞"
    fs_txt = _f(fs, 2) if math.isfinite(fs) else "∞"
    sections.append({
        "num": 3,
        "title": "KIỂM TRA NÉN UỐN XIÊN (NEd-MEd)",
        "ref": "EC2 6.1",
        "cards": [
            _mk("Điểm tải trọng A (nội lực thiết kế)",
                "",
                [f"NEd = {_f(NEd, 1)} kN",
                 f"MEd2 = {_f(MEd2, 1)} kN·m, MEd3 = {_f(MEd3, 1)} kN·m",
                 f"N_Rd,max = {_f(N_Rd_max, 1)} kN"],
                ""),
            _mk("Điểm giới hạn B (trên mặt tương tác)",
                "",
                [f"BN = {_f(BN, 1)} kN",
                 f"BMEd2 = {_f(Bx, 1)} kN·m, BMEd3 = {_f(By, 1)} kN·m"],
                ""),
            _mk("Tỷ số D/C",
                "EC2 6.1",
                [f"D/C = |OA|/|OB| = {dc_txt}",
                 f"FS = {fs_txt}"],
                "ĐẠT" if pm_ok else "KHÔNG ĐẠT"),
        ],
    })

    # ---- 4. Kiểm tra cắt ----
    def _sh_card(d: Dict[str, Any], VEd: float, lbl: str):
        if not d:
            return _mk(f"Phương {lbl}", "", ["—"], "")
        VRd_c = d.get("VRd_c_kN", 0.0) or 0.0
        VRd_max = d.get("VRd_max_kN", 0.0) or 0.0
        VRd_s = d.get("VRd_s_kN", 0.0) or 0.0
        asw_req = d.get("Asw_s_req", 0.0)
        ok = bool(d.get("ok", False))
        lines = [
            f"VEd = {_f(VEd, 1)} kN",
            f"VRd,c = {_f(VRd_c, 1)} kN "
            f"(k = {_f(d.get('k', 0), 2)}, ρl = {_f(d.get('rho_l', 0), 4)})",
            f"VRd,max = {_f(VRd_max, 1)} kN (θ = 45°)",
        ]
        if VEd > VRd_c and math.isfinite(asw_req):
            lines.append(f"VRd,s = {_f(VRd_s, 1)} kN, "
                         f"Asw/s yêu cầu = {_f(asw_req, 3)} mm²/mm")
        # Dấu so sánh phải dùng cùng VRd khống chế của checker (VRd_kN)
        _VRd = d.get("VRd_kN", 0) or 0
        cmp = "≤" if VEd <= _VRd else ">"
        lines.append(f"VEd = {_f(VEd, 1)} kN {cmp} VRd = "
                     f"{_f(_VRd, 1)} kN")
        if d.get("reason"):
            lines.append(d["reason"])
        return _mk(f"Phương {lbl}", "EC2 6.2", lines,
                    "ĐẠT" if ok else "KHÔNG ĐẠT")

    if isinstance(shear_res, dict) and "dir2" in shear_res:
        sh_cards = [_sh_card(shear_res.get("dir2"), VEd2, "V2"),
                    _sh_card(shear_res.get("dir3"), VEd3, "V3")]
    else:
        sh_cards = [_sh_card(shear_res or {}, VEd2, "V2/V3")]
    sections.append({
        "num": 4,
        "title": "KIỂM TRA CẮT",
        "ref": "EC2 6.2",
        "cards": sh_cards,
    })

    return sections
