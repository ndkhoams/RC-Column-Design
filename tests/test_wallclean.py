"""Dọn tab Kết quả vách theo 6 ghi chú đỏ của user (2026-10-24) —
test headless (không cần Tk): ghi chú DCM ở ô nhãn (không V_raw),
thứ tự dim Lw dưới dim thành phần, và (quyết user 2026-10-24)
khối kết luận dưới bảng thông số đã bỏ hẳn — D/C P-M chỉ còn ở
hàng D/C bảng thông số và bullets A/B/O.

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
from gui.wall_mixin import (_rot_xy, _wall_section_figsize,
                            build_wall_shear_rows, draw_wall_section_ax)


def test_param_conclusion_block_removed():
    """(quyết user 2026-10-24) Khối kết luận dưới bảng thông số đã
    bỏ hẳn: hàm _wall_result_conclusion bị xóa (không còn caller
    nào khác ngoài builder bảng thông số), 3 chuỗi nhãn của nó
    không còn trong wall_mixin, và builder bảng thông số không
    còn tham số concl cũng không tạo tk.Label kết luận nào.
    D/C P-M vẫn có ở hàng D/C bảng thông số và bullets A/B/O
    (kiểm ở cổng GUI, không dựng Tk ở đây)."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "gui",
                            "wall_mixin.py"), encoding="utf-8").read()
    assert "_wall_result_conclusion" not in src
    for s in ("Độ mảnh: D/C", "Cắt trong MP: D/C",
              "Cắt ngoài MP: D/C"):
        assert s not in src, s
    assert ("def _build_wall_param_table(self, parent, full):" in src)
    start = src.index("def _build_wall_param_table")
    nxt = src.index("\n    def ", start + 10)
    block = src[start:nxt]
    # tk.Label (không tính ttk.Label của tiêu đề bảng).
    assert re.search(r"(?<!t)tk\.Label\(", block) is None
    assert "concl" not in block


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
                   "(×1.5 DCM — TCVN 9386-1:2025 §5.4.2.4(7))")
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
