"""Thuyết minh kiểm tra cột theo EC2 — cấu trúc 7 mục theo mẫu TCVN."""

import math
from typing import Any, Dict, List


def _f(x: float, nd: int = 2) -> str:
    if x is None or not math.isfinite(x):
        return "—"
    return f"{x:.{nd}f}"


def _mk(title: str, ref: str, lines: List[str], result: str = "") -> Dict[str, Any]:
    return {"title": title, "ref": ref, "lines": lines, "result": result}


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
                f"fcd = {_f(conc.fcd, 2)} MPa"),
            _mk("Cốt thép",
                "EC2 3.2",
                [f"fyk = {_f(fyk, 0)} MPa",
                 f"fyd = {_f(steel.fyd, 1)} MPa",
                 "Es = 200000 MPa"],
                f"fyd = {_f(steel.fyd, 1)} MPa"),
        ],
    })

    # ---- 2. Tiết diện ----
    Ag = sec.gross_area if hasattr(sec, 'gross_area') else 0
    Ast = sec.steel_area if hasattr(sec, 'steel_area') else 0
    cx = getattr(sec, 'cx', 0) or getattr(inp, 'cx', 0)
    cy = getattr(sec, 'cy', 0) or getattr(inp, 'cy', 0)
    sections.append({
        "num": 2,
        "title": "ĐẶC TRƯNG HÌNH HỌC TIẾT DIỆN",
        "ref": "",
        "cards": [
            _mk("Kích thước tiết diện",
                "",
                [f"t2 × t3 = {_f(cx, 0)} × {_f(cy, 0)} mm",
                 f"Ac = {_f(Ag, 0)} mm²"],
                ""),
            _mk("Cốt thép dọc",
                "",
                [f"As = {_f(Ast, 0)} mm²"],
                ""),
        ],
    })

    # ---- 3. Chiều dài tính toán & độ mảnh ----
    sections.append({
        "num": 3,
        "title": "CHIỀU DÀI TÍNH TOÁN & ĐỘ MẢNH",
        "ref": "EC2 5.8.3",
        "cards": [
            _mk("Độ mảnh",
                "EC2 5.8.3.1",
                ["λ = l0/i, λlim = 20·A·B·C/√n"],
                ""),
        ],
    })

    # ---- 4. Sai lệch & độ lệch tâm ----
    e2 = abs(MEd2/max(abs(NEd), 1e-9)*1000) if abs(NEd) > 1e-9 else 0
    e3 = abs(MEd3/max(abs(NEd), 1e-9)*1000) if abs(NEd) > 1e-9 else 0
    sections.append({
        "num": 4,
        "title": "SAI LỆCH THI CÔNG & ĐỘ LỆCH TÂM",
        "ref": "EC2 5.2, 6.1(4)",
        "cards": [
            _mk("Sai lệch thi công",
                "EC2 5.2",
                ["ei = θi·l0/2, emin = max(h/30, 20mm)"],
                ""),
            _mk("Độ lệch tâm",
                "",
                [f"e2 = {_f(e2, 1)} mm, e3 = {_f(e3, 1)} mm"],
                ""),
        ],
    })

    # ---- 5. Hiệu ứng bậc 2 ----
    sections.append({
        "num": 5,
        "title": "HIỆU ỨNG BẬC 2",
        "ref": "EC2 5.8",
        "cards": [
            _mk("Phương pháp",
                "EC2 5.8.7 / 5.8.8",
                ["Độ cứng danh nghĩa hoặc độ cong danh nghĩa"],
                ""),
            _mk("Mô men thiết kế",
                "",
                [f"MEd2 = {_f(MEd2, 1)} kN·m",
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
            _mk("Điểm tải trọng A",
                "",
                [f"NEd = {_f(NEd, 1)} kN",
                 f"MEd2 = {_f(MEd2, 1)}, MEd3 = {_f(MEd3, 1)} kN·m",
                 f"Mα = {_f(Ma, 1)} kN·m, α = {_f(alpha, 1)}°"],
                ""),
            _mk("Điểm giới hạn B",
                "",
                [f"BN = {_f(BN, 1)} kN",
                 f"BM2 = {_f(Bx, 1)}, BM3 = {_f(By, 1)} kN·m"],
                ""),
            _mk("Tỷ số D/C",
                "",
                [f"D/C = {_f(dc, 3)} (FS = {_f(fs, 2)})"],
                "ĐẠT" if pm_ok else "KHÔNG ĐẠT"),
        ],
    })

    # ---- 7. Kiểm tra cắt ----
    def _sh_card(d: Dict[str, Any], VEd: float, lbl: str):
        if not d:
            return _mk(f"Phương {lbl}", "", ["—"], "")
        VRd_c = d.get("VRd_c_kN", 0.0) or 0.0
        VRd_max = d.get("VRd_max_kN", 0.0) or 0.0
        ok = bool(d.get("ok", False))
        return _mk(f"Phương {lbl}", "EC2 6.2",
                    [f"VEd = {_f(VEd, 1)} kN",
                     f"VRd,c = {_f(VRd_c, 1)} kN",
                     f"VRd,max = {_f(VRd_max, 1)} kN"],
                    "ĐẠT" if ok else "KHÔNG ĐẠT")

    if isinstance(shear_res, dict) and "dir2" in shear_res:
        sh_cards = [_sh_card(shear_res.get("dir2"), VEd2, "V2"),
                    _sh_card(shear_res.get("dir3"), VEd3, "V3")]
    else:
        sh_cards = [_sh_card(shear_res or {}, VEd2, "V2/V3")]
    sections.append({
        "num": 7,
        "title": "KIỂM TRA KHẢ NĂNG CHỊU CẮT",
        "ref": "EC2 6.2",
        "cards": sh_cards,
    })

    return sections
