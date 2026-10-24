"""Bảng kiểm tra cắt vách ở tab Kết quả (phần 2/7) — test ở mức
hàm pure build_wall_shear_rows (không cần Tk) + thẻ chi tiết mục 8.

Mọi số kỳ vọng lấy TAY từ parts của dict shear do wall_tcvn_full
trả (đo tươi, không hardcode số từ trí nhớ): ca mẫu preset web
(B30 γb=0.85, thép dọc CB500-V, thép ngang CB400-V, cover 25 nghĩa
mới c_đai, 2500×350, 2φ12 a200, N=2528.65, M2=275.23, M3=202.86).
Bảng/thẻ/PDF chỉ ĐỌC dict shear đã tính 1 lần — test này khẳng
định hàng bảng khớp từng số parts, không khẳng định lại engine.
"""

import math
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_input import WallInput
from rc_column.wall_engine import wall_tcvn_full
from gui.wall_mixin import build_wall_shear_rows


def _mats():
    conc = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
    return conc, steel


def _loads(v_in, v_out):
    return {"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
            "V_in": v_in, "V_out": v_out, "T": 0.0}


def _full(v_in=800.0, v_out=300.0, seis=False, rot=0):
    conc, steel = _mats()
    w = WallInput(sw_steel_grade="CB400-V")
    w.rot_deg = rot
    return wall_tcvn_full(w, conc, steel, loads=_loads(v_in, v_out),
                          seismic_shear=seis)


def _row(rows, label):
    for lab, a, b in rows:
        if lab == label:
            return a, b
    raise AssertionError(f"thiếu hàng {label!r}")


def _num(txt):
    """Số đầu tiên trong chuỗi (bỏ dấu phẩy nghìn, xử lý ∞)."""
    if "∞" in txt:
        return float("inf")
    m = re.search(r"-?[\d,]+\.?\d*", txt)
    assert m, f"không có số trong {txt!r}"
    return float(m.group(0).replace(",", ""))


def test_sample_rows_match_parts():
    """(a) Ca mẫu V2=800/V3=300: mọi hàng khớp tay từ parts."""
    full = _full()
    assert abs(full["dc"] - 0.45907315723873987) < 1e-12  # N–M không đổi
    pin = full["shear_in"]["parts"]
    pout = full["shear_out"]["parts"]
    rows = build_wall_shear_rows(full)
    assert len(rows) == 15
    assert [r[0] for r in rows] == [
        "Thép bố trí", "Lực cắt tính toán, V_Ed",
        "Kích thước tiết diện, bw × d", "Asw",
        "qsw = Rsw × Asw/s", "Hệ số φn (§8.1.3.3.2)",
        "Điều kiện (96): qsw ≥ 0.25×Rbt×b",
        "Độ bền trên dải nén xiên, [Q]1", "Qb", "Qsw",
        "Độ bền trên vết nứt xiên, [Q] = Qb + Qsw",
        "Chiều dài hình chiếu vết nứt xiên, C",
        "Asw/s yêu cầu (tối thiểu theo (96))", "Asw/s bố trí",
        "Kết luận"]
    # Cột ngoài MP nay có thép mặc định 2 nhánh (quyết user
    # 2026-10-25, thay P4 cũ Qsw = 0): mọi hàng khớp parts như
    # cột trong, kể cả (96) hỏng → Qb theo (97).
    assert _row(rows, "Thép bố trí") == ("2φ12 a200 (CB400-V)",
                                         "2φ12 a200 (CB400-V)")
    assert _row(rows, "Lực cắt tính toán, V_Ed") == (
        "800.0 kN", "300.0 kN (không phóng đại)")
    assert _row(rows, "Kích thước tiết diện, bw × d") == (
        "350 × 2457 mm", "2500 × 307 mm")
    assert _num(_row(rows, "Asw")[0]) == pytest.approx(pin["Asw"], abs=0.5)
    assert _num(_row(rows, "Asw")[1]) == pytest.approx(pout["Asw"],
                                                       abs=0.5)
    assert _num(_row(rows, "qsw = Rsw × Asw/s")[0]) == pytest.approx(
        pin["qsw"], abs=0.05)
    assert _num(_row(rows, "qsw = Rsw × Asw/s")[1]) == pytest.approx(
        pout["qsw"], abs=0.05)
    assert _row(rows, "Hệ số φn (§8.1.3.3.2)") == (
        f"{pin['phi_n']:.3f}", f"{pout['phi_n']:.3f}")
    assert _row(rows, "Điều kiện (96): qsw ≥ 0.25×Rbt×b") == (
        "✓ Đạt", "✗ Không đạt → Qb theo CT (97)")
    assert _num(_row(rows, "Độ bền trên dải nén xiên, [Q]1")[0]) == \
        pytest.approx(pin["Qcap1"], abs=0.05)
    assert _num(_row(rows, "Độ bền trên dải nén xiên, [Q]1")[1]) == \
        pytest.approx(pout["Qcap1"], abs=0.05)
    assert _num(_row(rows, "Qb")[0]) == pytest.approx(pin["Qb"], abs=0.05)
    assert _num(_row(rows, "Qb")[1]) == pytest.approx(pout["Qb"], abs=0.05)
    assert _num(_row(rows, "Qsw")[0]) == pytest.approx(pin["Qsw"],
                                                       abs=0.05)
    assert _num(_row(rows, "Qsw")[1]) == pytest.approx(pout["Qsw"],
                                                       abs=0.05)
    assert _num(_row(rows, "Độ bền trên vết nứt xiên, [Q] = Qb + Qsw")[0]) \
        == pytest.approx(pin["Qcap2"], abs=0.05)
    assert _num(_row(rows, "Độ bền trên vết nứt xiên, [Q] = Qb + Qsw")[1]) \
        == pytest.approx(pout["Qcap2"], abs=0.05)
    assert _num(_row(rows, "Chiều dài hình chiếu vết nứt xiên, C")[0]) \
        == pytest.approx(pin["C_opt"], abs=0.5)
    assert _num(_row(rows, "Chiều dài hình chiếu vết nứt xiên, C")[1]) \
        == pytest.approx(pout["C_opt"], abs=0.5)
    # Asw/s yêu cầu = qsw_min96 / Rsw (đổi đơn vị, không tính lại
    # khả năng cắt); Asw/s bố trí = Asw / s_h.
    assert _num(_row(rows, "Asw/s yêu cầu (tối thiểu theo (96))")[0]) == \
        pytest.approx(pin["qsw_min96"] / pin["Rsw"], abs=0.001)
    assert _num(_row(rows, "Asw/s yêu cầu (tối thiểu theo (96))")[1]) == \
        pytest.approx(pout["qsw_min96"] / pout["Rsw"], abs=0.001)
    assert _num(_row(rows, "Asw/s bố trí")[0]) == pytest.approx(
        pin["Asw"] / pin["s_h"], abs=0.001)
    assert _num(_row(rows, "Asw/s bố trí")[1]) == pytest.approx(
        pout["Asw"] / pout["s_h"], abs=0.001)
    assert _row(rows, "Kết luận") == ("✓ ĐẠT (D/C 0.417)",
                                      "✓ ĐẠT (D/C 0.518)")
    # Đối chiếu số tuyệt đối đã đo tươi (bắt drift định dạng/số).
    assert abs(full["shear_in"]["V_cap"] - 1920.4634365847605) < 1e-6
    assert abs(full["shear_out"]["V_cap"] - 579.077682525225) < 1e-6


def test_seismic_rows():
    """(b) Phóng đại DCM: trong MP V_Ed = 1200 (1,5×800); ghi chú
    DCM nằm ở Ô NHÃN (không ở ô giá trị) và KHÔNG hiển thị V_raw
    (quyết user 2026-10-24); ngoài MP không đổi 300."""
    full = _full(seis=True)
    rows = build_wall_shear_rows(full)
    lab = ("Lực cắt tính toán, V_Ed (×1.5 DCM — TCVN 9386-1:2025 "
           "§5.4.2.4(7))")
    v_in, v_out = _row(rows, lab)
    assert v_in == "1200.0 kN"
    assert "V_raw" not in lab and "V_raw" not in v_in
    assert v_out == "300.0 kN (không phóng đại)"
    assert _row(rows, "Kết luận") == ("✓ ĐẠT (D/C 0.625)",
                                      "✓ ĐẠT (D/C 0.518)")
    assert abs(full["dc"] - 0.45907315723873987) < 1e-12


def test_fail_rows():
    """(c) V=5000/5000: kết luận từng phương KHÔNG ĐẠT, D/C > 1."""
    full = _full(5000.0, 5000.0)
    rows = build_wall_shear_rows(full)
    cin, cout = _row(rows, "Kết luận")
    assert cin == "✗ KHÔNG ĐẠT (D/C 2.604)"
    assert cout == "✗ KHÔNG ĐẠT (D/C 7.097)"
    assert _num(cin) > 1.0 and _num(cout) > 1.0
    assert full["ok"] is True  # N–M vẫn ĐẠT, cắt kết luận riêng


def test_rotated_rows():
    """(d) Xoay 90°: b/h0 hoán đổi đúng theo wall_dims; trong MP
    (96) hỏng → Qb theo (97), kết luận trong MP KHÔNG ĐẠT."""
    full = _full(rot=90)
    rows = build_wall_shear_rows(full)
    assert _row(rows, "Kích thước tiết diện, bw × d") == (
        "2500 × 307 mm", "350 × 2457 mm")
    assert _row(rows, "Điều kiện (96): qsw ≥ 0.25×Rbt×b")[0] == \
        "✗ Không đạt → Qb theo CT (97)"
    cin, cout = _row(rows, "Kết luận")
    assert cin == "✗ KHÔNG ĐẠT (D/C 1.382)"
    # Ngoài MP ở 90° = trong MP ở 0° (cùng hình học + thép): Qb
    # theo (90), [Q]2 = 1920.5 → D/C 0.156 (thay mốc cũ 0.380 thời
    # Qsw = 0 ngoài MP).
    assert cout == "✓ ĐẠT (D/C 0.156)"


def test_pending_rows():
    """(e) Shear thiếu/V_cap None → mọi ô 'CHƯA KIỂM', không crash."""
    full = _full()
    pending = dict(full)
    pending["shear_in"] = {"V_cap": None, "dc": None, "ok": None,
                           "parts": {}}
    pending["shear_out"] = {}
    rows = build_wall_shear_rows(pending)
    assert len(rows) == 15
    for _lab, a, b in rows:
        assert a == "CHƯA KIỂM" and b == "CHƯA KIỂM"
    # Chỉ một phương pending vẫn giữ số phương còn lại.
    one = dict(full)
    one["shear_out"] = {"V_cap": None, "dc": None, "ok": None,
                        "parts": {}}
    rows1 = build_wall_shear_rows(one)
    assert _row(rows1, "Kết luận")[0] == "✓ ĐẠT (D/C 0.417)"
    assert _row(rows1, "Kết luận")[1] == "CHƯA KIỂM"


def test_dropped98_note():
    """Nhóm vi phạm (98) bị loại → ghi chú ngay ở hàng qsw."""
    conc, steel = _mats()
    w = WallInput(sw_steel_grade="CB400-V")
    w.s_h = 3000.0
    full = wall_tcvn_full(w, conc, steel, loads=_loads(800.0, 300.0))
    assert full["shear_in"]["parts"]["cond98_ok"] is False
    rows = build_wall_shear_rows(full)
    assert "(đã loại nhóm vi phạm (98))" in \
        _row(rows, "qsw = Rsw × Asw/s")[0]


def test_detail_section8_matches_table():
    """Thẻ chi tiết mục 8 có đủ số trung gian, khớp bảng tab."""
    from rc_column.wall_detail import build_wall_detail_sections
    full = _full()
    secs = build_wall_detail_sections(full)
    sec8 = [s for s in secs if s["num"] == 8][0]
    cards = {c["title"]: c for c in sec8["cards"]}
    in_txt = "\n".join(cards["Kiểm tra cắt — Trong mặt phẳng (V2)"]
                        ["lines"])
    out_txt = "\n".join(cards["Kiểm tra cắt — Ngoài mặt phẳng (V3)"]
                         ["lines"])
    for needle in ("986.8", "933.7", "4,473.4", "3931", "1.200",
                   "Asw/s yêu cầu", "Asw/s bố trí", "ĐK (96)",
                   "Công thức Qb"):
        assert needle in in_txt, needle
    for needle in ("469.7", "109.4", "579.1", "3,992.5", "460",
                   "không phóng đại", "Asw/s yêu cầu", "ĐK (96)",
                   "Công thức Qb", "2φ12 a200"):
        assert needle in out_txt, needle
    assert "D/C cắt = 0.417" in \
        cards["Kiểm tra cắt — Trong mặt phẳng (V2)"]["result"]
    assert "D/C cắt ngoài MP = 0.518" in \
        cards["Kiểm tra cắt — Ngoài mặt phẳng (V3)"]["result"]


def test_tk_table_builds():
    """Bảng Tk dựng được (skip khi không có display)."""
    try:
        import tkinter as tk
        from gui.wall_mixin import WallMixin
        root = tk.Tk()
        root.withdraw()
    except Exception as ex:
        pytest.skip(f"không có display Tk: {ex}")
    try:
        frame = tk.Frame(root)
        frame.pack()
        obj = object.__new__(WallMixin)
        tf = obj._build_wall_shear_table(frame, _full())
        texts = []

        def _walk(w):
            try:
                texts.append(w.cget("text"))
            except Exception:
                pass
            for ch in w.winfo_children():
                _walk(ch)
        _walk(tf)
        joined = " | ".join(texts)
        assert "KIỂM TRA KHẢ NĂNG CHỊU CẮT" in joined
        assert "Trong MP (V2)" in joined
        assert "Ngoài MP (V3)" in joined
        assert "2φ12 a200 (CB400-V)" in joined
        assert "✓ ĐẠT (D/C 0.417)" in joined
        assert "TCVN 5574:2018 §8.1.3" in joined  # ở header bảng
        # Khối diễn giải dưới bảng đã bỏ (quyết user 2026-10-24).
        assert "Căn cứ:" not in joined
    finally:
        try:
            root.destroy()
        except Exception:
            pass
