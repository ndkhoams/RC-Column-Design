"""Kiểm chứng gộp combo max/min (mục 5 — nút chọn "Gộp Combo max/min"
+ popup "Chọn combo gộp…" theo TÊN combo gốc).

Quy tắc (theo chỉ dẫn ETABS về phổ phản ứng: max/min là biên thống kê
± từng thành phần, không đồng thời): dòng gộp lấy mỗi thành phần có
|giá trị| lớn nhất trong 2 dòng, giữ nguyên dấu; hòa trị tuyệt đối lấy
giá trị của dòng max. Dòng không có cặp, combo thường và TX_* giữ nguyên.
Cơ chế mới (không hủy diệt): merge_combo_max_min(forces, selected_bases)
chỉ gộp các cặp thuộc tên gốc được tick; popup liệt kê tên gốc qua
combo_merge_options (TX_* loại khỏi danh sách).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rc_column.etabs_import import (
    EtabsForce, merge_combo_max_min, combo_merge_options)


def _f(case, station=0.0, N=0.0, Mx=0.0, My=0.0, Q2=0.0, Q3=0.0,
       story="S1", column="C1", case_type="Combination"):
    return EtabsForce(story=story, column=column, case=case,
                      case_type=case_type, station=station, N=N, Mx=Mx,
                      My=My, Q2=Q2, Q3=Q3)


def _sig(forces):
    return [(f.story, f.column, f.case, f.station, f.N, f.Mx, f.My,
             f.Q2, f.Q3) for f in forces]


def test_basic_pair_envelope():
    """Cặp cơ bản: từng thành phần lấy max-|.|, giữ dấu; có cả trường
    hợp |min| lớn hơn |max|."""
    rows = [
        _f("ULS17max", N=1000, Mx=200, My=-50, Q2=30, Q3=-10),
        _f("ULS17min", N=-1500, Mx=-120, My=80, Q2=-40, Q3=5),
    ]
    out, n = merge_combo_max_min(rows)
    assert n == 1 and len(out) == 1
    m = out[0]
    assert m.case == "ULS17"
    assert (m.N, m.Mx, m.My, m.Q2, m.Q3) == (-1500, 200, 80, -40, -10)


def test_multi_station_unpaired_normal_tx():
    """Nhiều station + dòng không cặp + combo thường + cặp TX_* (giữ)."""
    rows = [
        _f("DL", N=500, Mx=10, My=20),
        _f("ULS17max", station=0.0, N=100, Mx=50),
        _f("ULS17min", station=0.0, N=-90, Mx=-60),
        _f("ULS17max", station=3.0, N=200, Mx=70),
        _f("ULS17min", station=3.0, N=-250, Mx=-40),
        _f("ULS18max", station=0.0, N=300),  # không có min -> giữ nguyên
        _f("TX_ULS17max", N=800),
        _f("TX_ULS17min", N=-700),
    ]
    out, n = merge_combo_max_min(rows)
    assert n == 2
    assert [f.case for f in out] == [
        "DL", "ULS17", "ULS17", "ULS18max", "TX_ULS17max", "TX_ULS17min"]
    m0, m3 = out[1], out[2]
    assert (m0.station, m0.N, m0.Mx) == (0.0, 100, -60)
    assert (m3.station, m3.N, m3.Mx) == (3.0, -250, 70)


def test_suffix_case_insensitive_and_space_base():
    rows = [
        _f("ULS18MAX", N=10),
        _f("ULS18Min", N=-20),
        _f("ENV SLSmax", station=1.0, N=5),
        _f("ENV SLSmin", station=1.0, N=-6),
    ]
    out, n = merge_combo_max_min(rows)
    assert n == 2
    assert out[0].case == "ULS18" and out[0].N == -20
    assert out[1].case == "ENV SLS" and out[1].N == -6


def test_idempotent_and_tie_goes_to_max():
    rows = [
        _f("ULS17max", N=100, Mx=100),
        _f("ULS17min", N=-100, Mx=-100),  # hòa trị tuyệt đối
    ]
    out1, n1 = merge_combo_max_min(rows)
    assert n1 == 1 and out1[0].N == 100 and out1[0].Mx == 100
    out2, n2 = merge_combo_max_min(out1)
    assert n2 == 0 and _sig(out2) == _sig(out1)


def test_duplicate_suffix_no_merge_and_order():
    """Nhóm có 2 dòng max thì không gộp; dòng gộp đứng ở vị trí đầu cặp."""
    rows = [
        _f("DL", N=1),
        _f("ULS17max", N=10),
        _f("ULS17max", N=11),  # trùng hậu tố -> cả nhóm giữ nguyên
        _f("ULS17min", N=-9),
        _f("ULS19max", N=20),
        _f("ULS19min", N=-30),
        _f("LL", N=2),
    ]
    out, n = merge_combo_max_min(rows)
    assert n == 1
    assert [f.case for f in out] == [
        "DL", "ULS17max", "ULS17max", "ULS17min", "ULS19", "LL"]
    assert out[4].N == -30


def test_empty_and_no_pair():
    assert merge_combo_max_min([]) == ([], 0)
    rows = [_f("DL", N=5), _f("LL", N=6)]
    out, n = merge_combo_max_min(rows)
    assert n == 0 and _sig(out) == _sig(rows)


def test_selected_bases_only():
    """Tick tên gốc = chỉ gộp cặp của tên đó; tên không tick giữ nguyên;
    tick tên lạ không có tác dụng; tick rỗng = không gộp gì."""
    rows = [
        _f("ULS17max", N=100, Mx=50),
        _f("ULS17min", N=-90, Mx=-60),
        _f("ULS18max", N=200),
        _f("ULS18min", N=-250),
        _f("DL", N=5),
    ]
    out, n = merge_combo_max_min(rows, {"ULS17"})
    assert n == 1
    assert [f.case for f in out] == ["ULS17", "ULS18max", "ULS18min", "DL"]
    assert (out[0].N, out[0].Mx) == (100, -60)
    out, n = merge_combo_max_min(rows, set())
    assert n == 0 and _sig(out) == _sig(rows)
    out, n = merge_combo_max_min(rows, {"KHONG_CO"})
    assert n == 0 and _sig(out) == _sig(rows)


def test_selected_base_merges_all_stories_stations():
    """Một tên gốc được tick gộp mọi cặp của nó (mọi Story/Station)."""
    rows = [
        _f("ULS17max", station=0.0, N=100, story="S1"),
        _f("ULS17min", station=0.0, N=-90, story="S1"),
        _f("ULS17max", station=3.0, N=200, story="S1"),
        _f("ULS17min", station=3.0, N=-250, story="S1"),
        _f("ULS17max", station=0.0, N=400, story="S2"),
        _f("ULS17min", station=0.0, N=-350, story="S2"),
    ]
    out, n = merge_combo_max_min(rows, {"ULS17"})
    assert n == 3
    assert [f.case for f in out] == ["ULS17", "ULS17", "ULS17"]
    assert [(f.story, f.station, f.N) for f in out] == [
        ("S1", 0.0, 100), ("S1", 3.0, -250), ("S2", 0.0, 400)]


def test_combo_merge_options():
    """Popup: tên gốc theo thứ tự xuất hiện; biến thể max/min gộp về
    tên gốc; TX_* loại khỏi danh sách; tên không cặp -> có_cặp False."""
    rows = [
        _f("DL", N=5),
        _f("ULS17max", N=100),
        _f("ULS17min", N=-90),
        _f("ULS17max", station=3.0, N=200),
        _f("ULS17min", station=3.0, N=-250),
        _f("ULS18max", N=300),  # không có min -> không cặp
        _f("TX_ULS17max", N=800),
        _f("TX_ULS17min", N=-700),
        _f("LL", N=6),
    ]
    assert combo_merge_options(rows) == [
        ("DL", False, 0),
        ("ULS17", True, 2),
        ("ULS18", False, 0),
        ("LL", False, 0),
    ]
    assert combo_merge_options([]) == []
