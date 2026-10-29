"""Batch vách TCVN từ bảng nội lực Pier Forces (ETABS) — lát 5.

Module thuần (không GUI): ánh xạ 1 dòng Pier -> loads cho hàm tính
vách duy nhất wall_tcvn_full, trích D/C từng phần từ dict kết quả đã
lưu, xác định combo khống chế. GUI (gui/wall_mixin) chỉ hiển thị các
hàng này + nạp 1 hàng vào tab Kết quả/Chi tiết (đọc từ dict đã lưu,
không tính lại) — đúng nguyên tắc "tính 1 lần" của AGENTS.md §3.

ÁNH XẠ PIER -> (M_in, M_out, V_in, V_out)
---------------------------------------
Dòng Pier (EtabsForce) mang đúng ký hiệu ETABS: N = -P (P âm = nén),
Mx = M2, My = M3, Q2 = V2, Q3 = V3; Station chỉ là mã vị trí
(Bottom -> 0.0, Top -> 1.0, xem etabs_import._pier_station_code) —
KHÔNG phải mét, KHÔNG dùng làm chiều dài tính toán L. L vách lấy từ
mục 4 panel tại thời điểm tính (Lx_m/Ly_m + psi, qua winp) như đường
nhập tay; quy tắc Station max của cột KHÔNG áp cho vách.

Trục trong mặt phẳng theo loại tiết diện (như engine vách):
- trục "x" (phẳng/Barbell/T/L, kể cả khi xoay vì phẳng ép rot 0):
  M_in = M3, M_out = M2 — đúng ánh xạ đường nhập tay
  (_collect_wall_loads) và chú thích WallInput (M_in "M3 của pier").
- trục "y" (lõi C/U; xoay 90/270° hoán đổi trục như engine):
  M_in = M2, M_out = M3 — vì engine ánh xạ M_in <-> Mx (solver) ở
  trục y, mà Mx chính là khe M2 của app (xem wall_engine._POLY_AXIS_IN
  và nhãn bảng thông số vách: trục y thì trong MP ký hiệu M2).
  Đây là điểm batch KHÁC đường nhập tay hiện tại (nhập tay luôn dùng
  ánh xạ phẳng cho mọi loại — xem ghi chú cuối file); không tự sửa
  đường nhập tay ở lát này vì sẽ đổi số C/U nhập tay.
- Cắt giữ nguyên mọi loại: V_in = V2, V_out = V3 — đúng nhãn bảng
  cắt/tham số vách (V_in luôn ghi "V2", V_out luôn ghi "V3").

ĐỘNG ĐẤT / DCM
--------------
Một dòng là động đất khi TÊN GỐC của nó (bỏ hậu tố max/min, vd
"ULS14max" -> "ULS14") thuộc tập seismic_selected mà user đã chọn ở
popup "Chọn combo động đất" mục 5 — KHÔNG hardcode ULS14-17. Dòng đã
gộp (case = tên gốc, không hậu tố) cũng nhận diện bằng chính tên đó.
DCM 1,5x (TCVN 9386-1:2025 §5.4.2.4(7)) do engine áp: CHỈ cắt trong MP
(V_Ed = 1,5 x V_in, thể hiện ở shear_in["V_d"] /
shear_in["seismic_applied"]); ngoài MP không nhân, N-M không đổi.
TX_* không phải combo kiểm tra nên bị bỏ khỏi batch (như batch cột).

PHƯƠNG PENDING
--------------
shear dc = None (vd cắt ngoài MP của lõi hở C/U) -> ô đó hiển thị
"CHƯA KIỂM", không chặn batch, không tham gia max khống chế của
phương đó. Kết luận chung của 1 dòng: KHÔNG ĐẠT nếu bất kỳ phần nào
đã kiểm mà không đạt; CHƯA KIỂM nếu không phần nào không đạt nhưng
còn phần pending; ĐẠT chỉ khi mọi phần đã kiểm đều đạt và không còn
phần pending nào trong 3 phần (N-M, cắt trong, cắt ngoài).
"""

import math

from .etabs_import import _max_min_suffix
from .wall_engine import _poly_axis_in_rot, wall_tcvn_full


def wall_axis_in_for(section_type, rot_deg=0):
    """Trục trong mặt phẳng sau xoay, đúng luật engine vách.

    Nhánh chữ nhật của engine hardcode trục "x" (GUI ép rot 0 cho
    vách phẳng) nên rect luôn trả "x" bất kể rot_deg truyền vào;
    các loại đa giác dùng chung _poly_axis_in_rot của engine (90/270°
    hoán đổi trục) để không trôi khỏi engine.
    """
    if str(section_type or "rect") == "rect":
        return "x"
    return _poly_axis_in_rot(section_type, rot_deg)


def pier_base_case(case):
    """Tên gốc của combo: bỏ hậu tố max/min của ETABS nếu có."""
    name = (case or "").strip()
    split = _max_min_suffix(name)
    return split[0] if split else name


def pier_is_seismic(force, seismic_selected):
    """Dòng này có thuộc tập động đất user đã chọn không."""
    return pier_base_case(getattr(force, "case", "")) in set(
        seismic_selected or set())


def pier_to_wall_loads(force, section_type="rect", rot_deg=0):
    """Ánh xạ 1 dòng Pier -> loads cho wall_tcvn_full (xem docstring
    module). T (xoắn) không có trong kiểm tra vách nên = 0."""
    if wall_axis_in_for(section_type, rot_deg) == "y":
        m_in, m_out = float(force.Mx), float(force.My)
    else:
        m_in, m_out = float(force.My), float(force.Mx)
    return {
        "N": float(force.N),
        "M_in": m_in,
        "M_out": m_out,
        "V_in": float(force.Q2),
        "V_out": float(force.Q3),
        "T": 0.0,
    }


def dc_txt(dc):
    """Text D/C cho bảng: None -> CHƯA KIỂM, vô cùng -> ∞."""
    if dc is None:
        return "CHƯA KIỂM"
    if isinstance(dc, float) and math.isinf(dc):
        return "∞"
    try:
        return f"{float(dc):.3f}"
    except (TypeError, ValueError):
        return "CHƯA KIỂM"


def ok_txt(ok):
    """Text kết luận 1 phần: True/False/None."""
    if ok is True:
        return "ĐẠT"
    if ok is False:
        return "KHÔNG ĐẠT"
    return "CHƯA KIỂM"


def wall_batch_row(force, full, seismic):
    """Trích 1 hàng batch từ dict kết quả đã lưu (không tính lại).

    full = None -> hàng lỗi (engine raise ở dòng đó): mọi D/C None,
    error ghi thông điệp, batch vẫn chạy các dòng còn lại.
    """
    if full is None:
        return {
            "force": force, "full": None, "seismic": bool(seismic),
            "error": None, "dc_nm": None, "dc_in": None,
            "dc_out": None, "dc_overall": None, "ok_nm": None,
            "ok_in": None, "ok_out": None, "ok_overall": None,
            "V_ed_in": None, "V_raw_in": None,
        }
    sh_in = full.get("shear_in") or {}
    sh_out = full.get("shear_out") or {}
    dc_nm = full.get("dc")
    dc_in = sh_in.get("dc")
    dc_out = sh_out.get("dc")
    vals = [v for v in (dc_nm, dc_in, dc_out) if v is not None]
    dc_overall = max(vals) if vals else None
    ok_nm = full.get("ok")
    ok_in = sh_in.get("ok")
    ok_out = sh_out.get("ok")
    oks = [o for o in (ok_nm, ok_in, ok_out) if o is not None]
    if any(o is False for o in oks):
        ok_overall = False
    elif len(oks) < 3:
        ok_overall = None
    else:
        ok_overall = True
    return {
        "force": force, "full": full, "seismic": bool(seismic),
        "error": None, "dc_nm": dc_nm, "dc_in": dc_in,
        "dc_out": dc_out, "dc_overall": dc_overall,
        "ok_nm": ok_nm, "ok_in": ok_in, "ok_out": ok_out,
        "ok_overall": ok_overall,
        "V_ed_in": sh_in.get("V_d"),
        "V_raw_in": sh_in.get("V_raw"),
    }


def wall_batch_row_error(force, seismic, error):
    """Hàng batch cho dòng engine lỗi (xem wall_batch_row)."""
    row = wall_batch_row(force, None, seismic)
    row["error"] = str(error)
    return row


def wall_batch_controlling(rows):
    """Combo khống chế từng phần + chung: hàng có D/C lớn nhất.

    Phương pending ở mọi hàng -> None. Hòa D/C -> hàng đầu tiên.
    Trả về {"nm": row|None, "in": row|None, "out": row|None,
    "overall": row|None}.
    """
    out = {}
    for key in ("nm", "in", "out", "overall"):
        dc_key = {"nm": "dc_nm", "in": "dc_in", "out": "dc_out",
                  "overall": "dc_overall"}[key]
        best = None
        best_dc = None
        for row in rows:
            dc = row.get(dc_key)
            if dc is None:
                continue
            if best_dc is None or dc > best_dc:
                best, best_dc = row, dc
        out[key] = best
    return out


def run_wall_batch(winp, conc, steel, model, forces,
                   seismic_selected=None, steel_sw=None, calc=None):
    """Chạy batch vách TCVN qua mọi dòng Pier (trừ TX_*).

    winp/conc/steel/model/steel_sw: đúng 1 bộ như đường nhập tay
    (GUI lấy từ panel tại thời điểm bấm CHECK — không ghi ngược).
    calc: hàm tính 1 dòng, mặc định wall_tcvn_full; GUI truyền
    wrapper _tcvn_wall_calculate_full của nó để giữ đúng 1 hàm tính
    duy nhất. calc(loads, case_info, seismic_shear) -> full dict.
    Trả về list hàng theo đúng thứ tự bảng (TX_* bị bỏ, không chen).
    """
    if calc is None:
        def calc(loads, case_info, seismic_shear):
            return wall_tcvn_full(
                winp, conc, steel, model=model, loads=loads,
                case_info=case_info, steel_sw=steel_sw,
                seismic_shear=seismic_shear)
    section_type = str(getattr(winp, "section_type", "rect") or "rect")
    rot_deg = int(getattr(winp, "rot_deg", 0) or 0)
    rows = []
    for force in forces or []:
        case = (getattr(force, "case", "") or "").strip()
        if case.startswith("TX_"):
            continue
        seismic = pier_is_seismic(force, seismic_selected)
        loads = pier_to_wall_loads(force, section_type, rot_deg)
        case_info = {
            "combo": case,
            "story": getattr(force, "story", ""),
            "label": getattr(force, "column", ""),
            "location": getattr(force, "location", ""),
            "station": getattr(force, "station", 0.0),
            "seismic": bool(seismic),
        }
        try:
            full = calc(loads, case_info, seismic)
        except Exception as ex:
            rows.append(wall_batch_row_error(force, seismic, ex))
            continue
        rows.append(wall_batch_row(force, full, seismic))
    return rows
