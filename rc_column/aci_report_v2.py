"""Thuyết minh kiểm tra cột theo ACI 318-19 — cấu trúc 7 mục theo mẫu TCVN.

Trả về list các section dict để GUI render (cùng cấu trúc với TCVN):
- mỗi section: {'num', 'title', 'ref', 'cards'}
- mỗi card: {'title', 'ref', 'lines', 'result'}
"""

import math
from typing import Any, Dict, List


def _f(x: float, nd: int = 2) -> str:
    if x is None or not math.isfinite(x):
        return "—"
    return f"{x:.{nd}f}"


def _mk(title: str, ref: str, lines: List[str], result: str = "") -> Dict[str, Any]:
    return {"title": title, "ref": ref, "lines": lines, "result": result}


def generate_aci_report_sections_v2(inp, aci_res: Dict[str, Any],
                                    mm_res: Dict[str, Any],
                                    shear_res: Dict[str, Any],
                                    conc, steel, sec,
                                    tied: bool = True,
                                    fyt_MPa: float = None) -> List[Dict[str, Any]]:
    """Tạo 7 mục thuyết minh theo mẫu TCVN cho ACI 318-19."""
    fc = conc.fc
    fy = steel.fy
    eps_y = steel.eps_y
    if fyt_MPa is None:
        fyt_MPa = fy
    tie_txt = "đai rời (tied)" if tied else "đai xoắn (spiral)"
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
        "title": "ĐẶC TRƯNG VẬT LIỆU",
        "ref": "ACI 318-19 Chương 19 & 20",
        "cards": [
            _mk("Bê tông",
                "ACI 19.2.2.1, 22.2.2.1",
                [f"f'c = {_f(fc, 0)} MPa",
                 f"Ec = 4700√f'c = {_f(conc.Ec, 0)} MPa",
                 "εcu = 0.003",
                 f"β1 = {_f(conc.beta1, 4)}",
                 f"0.85f'c = {_f(conc.f_block, 2)} MPa"],
                f"f'c = {_f(fc, 0)} MPa"),
            _mk("Cốt thép dọc",
                "ACI 20.2.2",
                [f"fy = {_f(fy, 0)} MPa",
                 "Es = 200000 MPa",
                 f"εy = {_f(eps_y, 5)}"],
                f"fy = {_f(fy, 0)} MPa"),
            _mk("Cốt thép đai",
                "ACI 20.2.2",
                [f"fyt = {_f(fyt_MPa, 0)} MPa",
                 "Es = 200000 MPa",
                 f"Loại: {tie_txt}"],
                f"fyt = {_f(fyt_MPa, 0)} MPa"),
            _mk("Hệ số sức kháng φ",
                "ACI 21.2.2",
                [f"φc = {_f(phi_c, 2)} ({tie_txt})",
                 f"φ tại B = {_f(aci_res.get('phi', phi_c), 2)}"],
                f"φ = {_f(aci_res.get('phi', phi_c), 2)}"),
        ],
    })

    # ---- 2. Tiết diện ----
    Ag = sec.gross_area if hasattr(sec, 'gross_area') else 0
    Ast = sec.steel_area if hasattr(sec, 'steel_area') else 0
    cx = getattr(sec, 'cx', 0) or getattr(inp, 'cx', 0)
    cy = getattr(sec, 'cy', 0) or getattr(inp, 'cy', 0)
    # Số thanh-đường kính (như TCVN)
    from collections import Counter as _Ctr
    _cnt = _Ctr(getattr(r, "dia", 0) for r in getattr(sec, "rebars", []))
    _bar_str = " + ".join(f"{_cnt[d]:.0f}d{d:.0f}"
                          for d in sorted(_cnt, reverse=True)) if _cnt else "—"
    sections.append({
        "num": 2,
        "title": "ĐẶC TRƯNG HÌNH HỌC TIẾT DIỆN",
        "ref": "",
        "cards": [
            _mk("Kích thước tiết diện",
                "",
                [f"b × h = {_f(cx, 0)} × {_f(cy, 0)} mm",
                 f"Ag = {_f(Ag, 0)} mm²"],
                ""),
            _mk("Cốt thép dọc",
                "",
                [f"Ast = {_f(Ast, 0)} mm²",
                 f"ρg = Ast/Ag = {_f(Ast/max(Ag,1)*100, 2)}%"],
                ""),
        ],
    })

    # ---- 3. Chiều dài tính toán & độ mảnh ----
    _mm = mm_res or {}
    _L02 = _mm.get("L0_2", 0) or 0
    _L03 = _mm.get("L0_3", 0) or 0
    sections.append({
        "num": 3,
        "title": "CHIỀU DÀI TÍNH TOÁN & ĐỘ MẢNH",
        "ref": "ACI 6.6.4",
        "cards": [
            _mk("Chiều dài tính toán",
                "ACI 6.6.4.4",
                [f"L0,2 = {_f(_L02, 2)} m",
                 f"L0,3 = {_f(_L03, 2)} m"],
                ""),
            _mk("Độ mảnh",
                "ACI 6.6.4.1",
                ["klu/r ≤ 34 - 12(M1/M2) (khung không chuyển vị)",
                 "klu/r ≤ 22 (khung chuyển vị)"],
                ""),
        ],
    })

    # ---- 4. Độ lệch tâm ----
    e2 = abs(M2/max(abs(N), 1e-9)*1000) if abs(N) > 1e-9 else 0
    e3 = abs(M3/max(abs(N), 1e-9)*1000) if abs(N) > 1e-9 else 0
    sections.append({
        "num": 4,
        "title": "ĐỘ LỆCH TÂM",
        "ref": "ACI 6.6.4.5.4",
        "cards": [
            _mk("Độ lệch tâm tính toán",
                "",
                [f"e2 = |M2/N| = {_f(e2, 1)} mm",
                 f"e3 = |M3/N| = {_f(e3, 1)} mm"],
                ""),
        ],
    })

    # ---- 5. Phóng đại mô men ----
    if "dir2" in _mm:
        _d2 = _mm.get("dir2", {})
        _d3 = _mm.get("dir3", {})
        mm_lines = [
            f"δns2 = {_f(_mm.get('delta2', 1.0), 3)}, "
            f"δns3 = {_f(_mm.get('delta3', 1.0), 3)}",
            f"Pc2 = {_f(_d2.get('Pc_kN', 0), 0)} kN, "
            f"Pc3 = {_f(_d3.get('Pc_kN', 0), 0)} kN",
        ]
        delta_ns = max(_mm.get("delta2", 1.0), _mm.get("delta3", 1.0))
    else:
        mm_lines = [f"δns = {_f(_mm.get('delta_ns', 1.0), 3)}"]
        delta_ns = _mm.get("delta_ns", 1.0)
    M2_star = M2 * delta_ns
    M3_star = M3 * delta_ns
    sections.append({
        "num": 5,
        "title": "PHÓNG ĐẠI MÔ MEN UỐN DỌC",
        "ref": "ACI 6.6.4.5",
        "cards": [
            _mk("Hệ số phóng đại δns",
                "ACI 6.6.4.5.2",
                mm_lines + ["δns = Cm/(1 - Pu/(0.75·Pc)) ≥ 1.0"],
                f"δns = {_f(delta_ns, 3)}"),
            _mk("Mô men sau phóng đại",
                "",
                [f"M2* = {_f(M2_star, 1)} kN·m",
                 f"M3* = {_f(M3_star, 1)} kN·m"],
                ""),
        ],
    })

    # ---- 6. Kiểm tra P-M-M ----
    dc = aci_res.get("dc", 0.0) or 0.0
    fs = aci_res.get("fs", 0.0) or 0.0
    Bx = aci_res.get("Bx", 0.0) or 0.0
    By = aci_res.get("By", 0.0) or 0.0
    BN = aci_res.get("BN", 0.0) or 0.0
    pm_ok = bool(aci_res.get("ok", False))
    Ma = math.hypot(M2_star, M3_star)
    alpha = math.degrees(math.atan2(M2_star, M3_star)) if Ma > 1e-9 else 0.0
    sections.append({
        "num": 6,
        "title": "ĐÁNH GIÁ KHẢ NĂNG CHỊU LỰC NÉN UỐN XIÊN (P-M-M)",
        "ref": "ACI 22.4",
        "cards": [
            _mk("Điểm tải trọng A",
                "",
                [f"N = {_f(N, 1)} kN",
                 f"M2* = {_f(M2_star, 1)} kN·m, M3* = {_f(M3_star, 1)} kN·m",
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

    # ---- 7. Kiểm tra cắt (2 phương) ----
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
        return _mk(f"Phương {label} (Vu = {_f(abs(Q), 1)} kN)",
                    "ACI 22.5.5.1",
                    [f"Vc = max[0.17λ√f'c, 0.66λsλ(ρw)⅓√f'c]·bw·d = {_f(Vc, 1)} kN",
                     f"Vs = Av·fyt·d/s = {_f(Vs, 1)} kN",
                     f"φVn = 0.75·(Vc+Vs) = {_f(phi_Vn, 1)} kN",
                     f"Vu = {_f(abs(Q), 1)} kN ≤ φVn = {_f(phi_Vn, 1)} kN"],
                    "ĐẠT" if ok else "KHÔNG ĐẠT")
    _ok2 = bool(_d2.get("ok", False)) if _d2 else True
    _ok3 = bool(_d3.get("ok", False)) if _d3 else True
    _cards7 = [_sh_card(_d2, Q2, "V2")]
    if _d3:
        _cards7.append(_sh_card(_d3, Q3, "V3"))
    sections.append({
        "num": 7,
        "title": "KIỂM TRA KHẢ NĂNG CHỊU CẮT",
        "ref": "ACI 22.5",
        "cards": _cards7,
    })

    return sections
