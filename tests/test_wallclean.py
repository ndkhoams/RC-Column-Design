"""Dọn tab Kết quả vách theo 6 ghi chú đỏ của user (2026-10-24) —
test headless (không cần Tk): kết luận dạng ngắn, ghi chú DCM ở ô
nhãn (không V_raw), thứ tự dim Lw dưới dim thành phần.

Mọi số lấy từ engine thật (wall_tcvn_full / build_wall_section),
không hardcode số từ trí nhớ ngoài chuỗi định dạng kỳ vọng.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_input import WallInput
from rc_column.wall_section import build_wall_section
from gui.wall_mixin import (WallMixin, _rot_xy, _wall_section_figsize,
                            build_wall_shear_rows, draw_wall_section_ax)


def _concl(full):
    obj = object.__new__(WallMixin)
    return obj._wall_result_conclusion(full)


def _full_concl():
    return {"ok": True, "dc": 0.463, "fs": 2.16,
            "slend": {"lambda_in": 4.6, "lambda_out": 32.7},
            "shear_in": {"V_cap": 1828.8, "dc": 0.656, "ok": True},
            "shear_out": {"V_cap": 657.6, "dc": 0.0, "ok": True}}


def test_conclusion_short_form():
    """(1) 3 dòng dưới bảng thông số: chỉ tên mục + D/C + ĐẠT,
    không chú thích trong ngoặc; độ mảnh dùng λmax/120."""
    c = _concl(_full_concl())
    assert c["slend"] == ("Độ mảnh: D/C = "
                          f"{max(4.6, 32.7) / 120.0:.3f}"
                          " (λmax/120) — ĐẠT")
    assert "λx =" not in c["slend"] and "λy =" not in c["slend"]
    assert c["shear_in"] == "Cắt trong MP: D/C = 0.656 — ĐẠT"
    assert c["shear_out"] == "Cắt ngoài MP: D/C = 0.000 — ĐẠT"
    for k in ("slend", "shear_in", "shear_out"):
        assert "§" not in c[k] and "V_Ed" not in c[k]


def test_conclusion_pending_and_fail():
    """Chưa tính được giữ dạng '— (chưa tính được)'; KHÔNG ĐẠT
    khi D/C > 1 hoặc λ > 120."""
    f = _full_concl()
    f["shear_in"] = {"V_cap": None, "dc": None, "ok": None}
    c = _concl(f)
    assert c["shear_in"] == "Cắt trong MP: — (chưa tính được)"
    f2 = _full_concl()
    f2["slend"] = {"lambda_in": 4.6, "lambda_out": 130.0}
    f2["shear_in"] = {"V_cap": 100.0, "dc": 2.604, "ok": False}
    c2 = _concl(f2)
    assert c2["slend"].endswith("— KHÔNG ĐẠT")
    assert c2["shear_in"] == "Cắt trong MP: D/C = 2.604 — KHÔNG ĐẠT"


def _boundary_sec_meta():
    conc = ConcreteMaterial(CONCRETE_GRADES["B25"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB400-V"], 1.0)
    w = WallInput(steel_mode="boundary", cover=13.0, be_Lb=500.0,
                  be_dia=28.0, be_nL=4, be_nT=2, web_dia=12.0,
                  web_s=200.0, sw_steel_grade="CB400-V")
    w.rot_deg = 0
    return build_wall_section(w, conc, steel)


def _dim_label_y(sec, meta, rot):
    """y canonical của nhãn Lw và các nhãn thành phần sau khi vẽ
    (nghịch xoay vị trí data của text về khung gốc)."""
    n_seg = len((meta or {}).get("dim_segments") or [])
    fw, fh = _wall_section_figsize(sec, n_seg, rot)
    fig, ax = plt.subplots(figsize=(fw, fh))
    draw_wall_section_ax(ax, sec, meta=meta, rot_deg=rot)
    fig.canvas.draw()
    lw, segs = None, []
    for t in ax.texts:
        txt = t.get_text() or ""
        if not (txt.startswith("Lw = ") or txt.startswith("Lb = ")
                or re.fullmatch(r"\d+", txt)):
            continue
        x, y = t.get_position()
        _cx, cy = _rot_xy(x, y, -rot)
        if txt.startswith("Lw = "):
            lw = cy
        else:
            segs.append(cy)
    plt.close(fig)
    return lw, segs


def test_dim_total_below_segments():
    """(5) Nhãn dim tổng Lw nằm DƯỚI (y canonical nhỏ hơn) mọi
    nhãn thành phần, cả xoay 0° và 90°."""
    sec, meta = _boundary_sec_meta()
    assert len(meta["dim_segments"]) == 3
    for rot in (0, 90):
        lw, segs = _dim_label_y(sec, meta, rot)
        assert lw is not None and len(segs) == 3, (rot, lw, segs)
        assert all(lw < y for y in segs), (rot, lw, segs)


def test_ved_note_in_label_no_vraw():
    """(4) Ghi chú DCM ở ô nhãn, ô giá trị trơn, không V_raw —
    ở mức builder (ca DCM thật qua engine)."""
    conc = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
    w = WallInput(sw_steel_grade="CB400-V")
    full = __import__("rc_column.wall_engine",
                      fromlist=["wall_tcvn_full"]).wall_tcvn_full(
        w, conc, steel,
        loads={"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
               "V_in": 800.0, "V_out": 300.0, "T": 0.0},
        seismic_shear=True)
    rows = build_wall_shear_rows(full)
    lab = [r[0] for r in rows
           if r[0].startswith("Lực cắt tính toán, V_Ed")][0]
    val = [r[1] for r in rows
           if r[0].startswith("Lực cắt tính toán, V_Ed")][0]
    assert lab == ("Lực cắt tính toán, V_Ed "
                   "(×1.5 DCM — TCVN 9386-1:2012 §5.4.2.4(7))")
    assert val == "1200.0 kN"
    assert "V_raw" not in lab and "V_raw" not in val
    # V_raw vẫn giữ trong dict kết quả (chỉ không hiển thị).
    assert full["shear_in"]["V_raw"] == 800.0


def test_param_table_ved_no_vraw():
    """(4b) Hàng V_Ed ở BẢNG THÔNG SỐ cũng không hiển thị V_raw —
    quyết user 2026-10-24 (bỏ nốt sau khi đã bỏ ở ghi chú bảng cắt).
    Bảng thông số dựng bằng Tk nên chỉ kiểm ở mức source: khối
    rows.insert V_Ed không được nhắc tới V_raw hay hệ số × giá trị thô."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "gui",
                            "wall_mixin.py"), encoding="utf-8").read()
    start = src.index('rows.insert(4, ("V_Ed",')
    block = src[start:start + 700]
    assert "V_raw" not in block
    assert "1,5 ×" not in block
    assert "V_d" in block
