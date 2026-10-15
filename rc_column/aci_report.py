"""Thuyết minh kiểm tra cột theo ACI 318-19.

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


def generate_aci_report_sections(inp, aci_res: Dict[str, Any],
                                 mm_res: Dict[str, Any],
                                 shear_res: Dict[str, Any],
                                 conc, steel, tied: bool = True) -> List[Dict[str, Any]]:
    """Tạo các mục thuyết minh kiểm tra cột theo ACI 318-19.

    inp: ColumnInput (lấy N, Mx/M2, My/M3, Q2...).
    aci_res: dict từ check_column_aci {dc, fs, phi, ok, Bx, By, BN, eps_t, ...}.
    mm_res: dict từ moment_magnification {delta_ns, Pc_kN, Cm, ok, ...}.
    shear_res: dict từ aci_shear_check {Vc_kN, Vs_kN, phi_Vn_kN, ok, lambda_s, ...}.
    conc: ACIConcrete, steel: ACISteel, tied: True = cột đai rời.
    """
    fc = conc.fc
    fy = steel.fy
    eps_y = steel.eps_y
    tie_txt = "đai rời (tied)" if tied else "đai xoắn (spiral)"
    phi_c = 0.65 if tied else 0.75

    N = getattr(inp, "N", 0.0) or 0.0
    M2 = getattr(inp, "Mx", 0.0) or 0.0
    M3 = getattr(inp, "My", 0.0) or 0.0
    Vu = abs(getattr(inp, "Q2", 0.0) or 0.0)

    sections: List[Dict[str, Any]] = []

    # ---- 1. Vật liệu ----
    sections.append({
        "num": 1,
        "title": "VẬT LIỆU THEO ACI 318-19",
        "ref": "ACI 318-19 Chương 19 & 20",
        "cards": [
            _mk("Bê tông",
                "ACI 19.2.2.1, 22.2.2.1, 22.2.2.4",
                [f"f'c = {_f(fc, 0)} MPa",
                 f"Ec = 4700√f'c = 4700√{_f(fc, 0)} = {_f(conc.Ec, 0)} MPa",
                 "εcu = 0.003 (biến dạng cực hạn bê tông)",
                 f"β1 = 0.85 − 0.05(f'c−4000)/1000 = {_f(conc.beta1, 4)}",
                 f"Khối ứng suất chữ nhật: 0.85f'c = {_f(conc.f_block, 2)} MPa, a = β1·c"],
                f"f'c = {_f(fc, 0)} MPa"),
            _mk("Cốt thép",
                "ACI 20.2.2.1, 20.2.2.2, 22.2.3.2",
                [f"fy = {_f(fy, 0)} MPa",
                 "Es = 200000 MPa",
                 f"εy = fy/Es = {_f(eps_y, 5)}",
                 "Mô hình đàn–dẻo lý tưởng, ứng suất giới hạn ở fy"],
                f"fy = {_f(fy, 0)} MPa"),
        ],
    })

    # ---- 2. Hệ số sức kháng φ ----
    eps_t_b = aci_res.get("eps_t", 0.0) or 0.0
    phi_b = aci_res.get("phi", phi_c) or phi_c
    if eps_t_b <= eps_y:
        zone_txt = "nén chủ đạo"
    elif eps_t_b >= eps_y + 0.003:
        zone_txt = "kéo chủ đạo"
    else:
        zone_txt = "vùng chuyển tiếp"
    sections.append({
        "num": 2,
        "title": "HỆ SỐ SỨC KHÁNG φ",
        "ref": "ACI 21.2.2, Table 21.2.2",
        "cards": [
            _mk("φ theo biến dạng εt",
                "ACI 21.2.2",
                ["Nén chủ đạo (εt ≤ εy): "
                 f"φ = {_f(phi_c, 2)} ({tie_txt})",
                 "Kéo chủ đạo (εt ≥ εy + 0.003): φ = 0.90",
                 "Vùng chuyển tiếp: nội suy tuyến tính theo εt"],
                ""),
            _mk("φ tại điểm giới hạn B",
                "ACI 21.2.2",
                [f"εt tại B = {_f(eps_t_b, 5)} ({zone_txt})",
                 f"εy = {_f(eps_y, 5)}",
                 f"φ = {_f(phi_b, 2)}"],
                f"φ = {_f(phi_b, 2)}"),
        ],
    })

    # ---- 3. Độ mảnh & δns ----
    delta_ns = mm_res.get("delta_ns", 1.0) or 1.0
    Pc = mm_res.get("Pc_kN", 0.0) or 0.0
    Cm = mm_res.get("Cm", 1.0) or 0.0
    mm_ok = bool(mm_res.get("ok", True))
    mm_reason = mm_res.get("reason", "") or ""
    mm_lines = [f"Cm = {_f(Cm, 3)}",
                f"Pc = {_f(Pc, 0)} kN",
                f"δns = {_f(delta_ns, 3)}"]
    if mm_reason:
        mm_lines.append(mm_reason)
    sections.append({
        "num": 3,
        "title": "ĐỘ MẢNH & HỆ SỐ PHÓNG ĐẠI δns",
        "ref": "ACI 6.6.4.5",
        "cards": [
            _mk("Công thức",
                "ACI 6.6.4.5.2",
                ["δns = Cm / (1 − Pu/(0.75·Pc)) ≥ 1.0",
                 "Cm = 0.6 − 0.4·(M1/M2)",
                 "Pc = π²·EI/(k·lu)²",
                 "EI = 0.4·Ec·Ig/(1+βdns)"],
                ""),
            _mk("Kết quả δns",
                "ACI 6.6.4.5",
                mm_lines,
                f"δns = {_f(delta_ns, 3)}"
                + (" → OK" if mm_ok else " → KHÔNG ĐẠT")),
        ],
    })

    # ---- 4. Kiểm tra P-M-M ----
    dc = aci_res.get("dc", 0.0) or 0.0
    fs = aci_res.get("fs", 0.0) or 0.0
    Bx = aci_res.get("Bx", 0.0) or 0.0
    By = aci_res.get("By", 0.0) or 0.0
    BN = aci_res.get("BN", 0.0) or 0.0
    pm_ok = bool(aci_res.get("ok", False))
    dc_txt = _f(dc, 3) if math.isfinite(dc) else "∞"
    fs_txt = _f(fs, 2) if math.isfinite(fs) else "∞"
    sections.append({
        "num": 4,
        "title": "KIỂM TRA NÉN UỐN XIÊN (P-M-M)",
        "ref": "ACI 22.4",
        "cards": [
            _mk("Điểm tải trọng A (nội lực tính toán)",
                "",
                [f"N = {_f(N, 1)} kN",
                 f"M2 = {_f(M2, 1)} kN·m, M3 = {_f(M3, 1)} kN·m"],
                ""),
            _mk("Điểm giới hạn B (trên mặt tương tác)",
                "",
                [f"BN = {_f(BN, 1)} kN",
                 f"BM2 = {_f(Bx, 1)} kN·m, BM3 = {_f(By, 1)} kN·m",
                 f"φ tại B = {_f(phi_b, 2)}"],
                ""),
            _mk("Tỷ số D/C",
                "ACI 22.4",
                [f"D/C = |OA|/|OB| = {dc_txt}",
                 f"FS = {fs_txt}"],
                "ĐẠT" if pm_ok else "KHÔNG ĐẠT"),
        ],
    })

    # ---- 5. Kiểm tra cắt ----
    Vc = shear_res.get("Vc_kN", 0.0) or 0.0
    Vs = shear_res.get("Vs_kN", 0.0) or 0.0
    phi_Vn = shear_res.get("phi_Vn_kN", 0.0) or 0.0
    lam_s = shear_res.get("lambda_s", 1.0) or 0.0
    sh_ok = bool(shear_res.get("ok", False))
    cmp = "≤" if Vu <= phi_Vn else ">"
    sections.append({
        "num": 5,
        "title": "KIỂM TRA CẮT",
        "ref": "ACI 22.5",
        "cards": [
            _mk("Khả năng cắt của bê tông Vc",
                "ACI 22.5.5.1",
                [f"Vc = {_f(Vc, 1)} kN",
                 f"λs = {_f(lam_s, 3)} (hệ số kích thước)"],
                f"Vc = {_f(Vc, 1)} kN"),
            _mk("Cốt đai Vs và φVn",
                "ACI 22.5",
                [f"Vs = Av·fyt·d/s = {_f(Vs, 1)} kN",
                 f"φVn = 0.75·(Vc + Vs) = {_f(phi_Vn, 1)} kN"],
                f"φVn = {_f(phi_Vn, 1)} kN"),
            _mk("Kết luận cắt",
                "",
                [f"Vu = {_f(Vu, 1)} kN {cmp} φVn = {_f(phi_Vn, 1)} kN"],
                "ĐẠT" if sh_ok else "KHÔNG ĐẠT"),
        ],
    })

    return sections
