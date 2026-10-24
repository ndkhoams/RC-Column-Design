"""Hàng D/C bảng thông số vách + ghi chú diễn giải công thức Qb
(ghi chú đỏ user 2026-10-25, mục B + C).

- B: hàng D/C N–M nằm ngay sau hàng α (trước đây nằm cuối bảng,
  dưới nếp gấp khi Treeview chỉ cao 20 hàng), lấy từ dict kết quả
  đã lưu, kết luận theo D/C ≤ 1; Treeview cao 21 để hàng D/C
  nhìn thấy được cả khi có hàng V_Ed (DCM).
- C: ghi chú Qb dưới bảng cắt (wall_qb_formula_note, pure, không
  cần Tk): công thức đúng như engine đang tính (TCVN 5574:2018
  §8.1.3) + thay số thật 2 phương, kể cả bước chặn [0,5; 2,5].
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_input import WallInput
from rc_column.wall_engine import wall_tcvn_full
from gui.wall_mixin import wall_qb_formula_note


def _full(seis=False):
    conc = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
    w = WallInput(sw_steel_grade="CB400-V")
    w.rot_deg = 0
    loads = {"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
             "V_in": 800.0, "V_out": 300.0, "T": 0.0}
    return wall_tcvn_full(w, conc, steel, loads=loads,
                          seismic_shear=seis)


def test_param_dc_row_right_after_alpha():
    """Bảng Tk: hàng D/C ngay sau α, đúng giá trị + tag dc.
    Skip khi không có display (như test_wall_shear_table)."""
    try:
        import tkinter as tk
        from gui.wall_mixin import WallMixin
        root = tk.Tk()
        root.withdraw()
    except Exception as ex:
        pytest.skip(f"không có display Tk: {ex}")
    try:
        for seis in (False, True):
            full = _full(seis=seis)
            frame = tk.Frame(root)
            frame.pack()
            obj = object.__new__(WallMixin)
            obj._build_wall_param_table(frame, full)
            tree = None
            for w in frame.winfo_children():
                if w.winfo_class() == "Treeview":
                    tree = w
            assert tree is not None
            assert int(tree.cget("height")) == 21
            rows = [tuple(tree.item(i)["values"])
                    for i in tree.get_children()]
            syms = [r[0] for r in rows]
            ia = syms.index("α")
            assert syms[ia + 1] == "D/C"
            assert ia + 1 < 21  # nhìn thấy được, không dưới nếp gấp
            dc_row = rows[ia + 1]
            assert dc_row[1] == "Kiểm tra N–M (song trục)"
            assert dc_row[2] == f"{full['dc']:.3f} — ĐẠT"
            assert "dc" in tree.item(tree.get_children()[ia + 1])["tags"]
            frame.destroy()
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def test_qb_note_formula_and_substitution():
    """Ghi chú Qb: công thức + thay số thật 2 phương, có bước chặn
    ở ngoài MP (Qb_tt 388.9 < chặn dưới 391.4)."""
    full = _full()
    note = wall_qb_formula_note(full)
    assert "TCVN 5574:2018 §8.1.3" in note
    assert "C ∈ [h0, 2h0]" in note
    assert "Qb = φn×1,5×Rbt×b×h0²/C" in note
    assert "Qb = φn×4×1,5×h0²×qsw/C" in note
    assert "Qsw = 0,75×qsw×C" in note
    assert "Trong MP: C = 3931.2 mm, (90)" in note
    assert "986.8 kN" in note and "933.7 kN" in note
    assert "1920.5 kN" in note
    assert "Ngoài MP: C = 460.5 mm, (97)" in note
    assert "388.9 → chặn [391.4; 1957.1] → 391.4 ×φn → 469.7 kN" in note
    assert "109.4 kN" in note and "579.1 kN" in note


def test_qb_note_empty_when_shear_pending():
    """Cắt pending (thiếu parts) thì không có ghi chú Qb."""
    full = _full()
    pending = dict(full)
    pending["shear_in"] = {"V_cap": None, "dc": None, "ok": None,
                           "parts": {}}
    pending["shear_out"] = {"V_cap": None, "dc": None, "ok": None,
                            "parts": {}}
    assert wall_qb_formula_note(pending) == ""
