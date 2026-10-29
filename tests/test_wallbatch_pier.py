"""Batch vách TCVN từ bảng Pier Forces đã paste (lát 5).

Dùng FILE THẬT (copy nguyên byte từ file user gửi, như
test_wallpier_multiline_header): tests/noi_luc_pier_real.txt (54 dòng
gốc -> 42 dòng parse; gộp riêng ULS14 -> 40; gộp đủ ULS14-17 -> 34).
KHÔNG fixture trích qua chat.

Kiểm chứng:
- paste -> đủ dòng; batch chạy hết không crash, đúng số hàng;
- DCM 1,5x chỉ trong MP và chỉ combo thuộc tập động đất user chọn
  (bằng số V_Ed trong dict kết quả, không hardcode ULS14-17);
- combo khống chế = max sau DCM, từng phần và chung;
- ánh xạ Pier -> loads theo trục trong MP (x: M_in=M3/M_out=M2;
  y (C/U): M_in=M2/M_out=M3; cắt luôn V_in=V2/V_out=V3);
- phương pending C/U ngoài MP hiện CHƯA KIỂM, không chặn batch;
- GUI (skip khi không display; chạy dưới Xvfb): paste file thật ->
  batch -> bảng batch + chọn 1 dòng nạp đúng tab Kết quả.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rc_column.etabs_import import (
    EtabsForce, merge_combo_max_min, parse_etabs_clipboard)
from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_batch import (
    dc_txt, ok_txt, pier_base_case, pier_is_seismic,
    pier_to_wall_loads, run_wall_batch, wall_axis_in_for,
    wall_batch_controlling)
from rc_column.wall_input import WallInput

_REAL = os.path.join(os.path.dirname(__file__), "noi_luc_pier_real.txt")
_CONC = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
_STEEL = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
_SW = SteelMaterial(STEEL_GRADES["CB400-V"], 1.0)
_SEIS_ALL = {"ULS14", "ULS15", "ULS16", "ULS17"}


def _forces():
    with open(_REAL, encoding="utf-8", errors="ignore") as fh:
        return parse_etabs_clipboard(fh.read())


def _flat_winp():
    return WallInput()  # phẳng 2500x350 mặc định


@pytest.fixture(scope="module")
def batch_all():
    """Batch 1 lần trên bảng hiển thị khi tick đủ ULS14-17 (34 dòng).

    Module-scoped để không chạy lại solver fiber 34 lần cho mỗi test.
    """
    disp, _n = merge_combo_max_min(_forces(), _SEIS_ALL)
    rows = run_wall_batch(_flat_winp(), _CONC, _STEEL, "3line",
                          disp, seismic_selected=_SEIS_ALL,
                          steel_sw=_SW)
    return disp, rows


def test_real_file_parse_and_merge_counts():
    forces = _forces()
    assert len(forces) == 42
    disp14, n14 = merge_combo_max_min(forces, {"ULS14"})
    assert n14 == 2 and len(disp14) == 40
    disp_all, n_all = merge_combo_max_min(forces, _SEIS_ALL)
    assert n_all == 8 and len(disp_all) == 34
    # Dòng gộp giữ Location riêng Top/Bottom, case = tên gốc.
    merged = [f for f in disp_all if f.case == "ULS14"]
    assert sorted(f.location for f in merged) == ["Bottom", "Top"]
    # Dòng chưa gộp giữ hậu tố max/min.
    assert any(f.case == "ULS14max" for f in _forces())


def test_mapping_flat_and_cu_axes():
    f = EtabsForce(story="F3", column="E2", case="ULS1",
                   case_type="Combination", station=0.0, N=585.4597,
                   Mx=-11.3585, My=-22.144, Q2=-9.5329, Q3=-2.5546,
                   location="Bottom")
    flat = pier_to_wall_loads(f, "rect", 0)
    assert flat == {"N": 585.4597, "M_in": -22.144, "M_out": -11.3585,
                    "V_in": -9.5329, "V_out": -2.5546, "T": 0.0}
    assert wall_axis_in_for("rect", 90) == "x"  # phẳng ép rot 0
    assert wall_axis_in_for("tee", 0) == "x"
    assert wall_axis_in_for("c-core", 0) == "y"
    assert wall_axis_in_for("c-core", 90) == "x"  # xoay hoán trục
    cu = pier_to_wall_loads(f, "c-core", 0)
    assert (cu["M_in"], cu["M_out"]) == (-11.3585, -22.144)
    assert (cu["V_in"], cu["V_out"]) == (-9.5329, -2.5546)
    assert pier_base_case("ULS14max") == "ULS14"
    assert pier_base_case("ULS1") == "ULS1"
    assert pier_is_seismic(f, set()) is False
    f14 = EtabsForce(story="F3", column="E2", case="ULS14min",
                     case_type="Combination", station=0.0, N=1277.4916,
                     Mx=-61.1225, My=-444.1095, Q2=-195.09, Q3=-28.814,
                     location="Bottom")
    assert pier_is_seismic(f14, _SEIS_ALL) is True
    assert pier_is_seismic(f14, {"ULS14"}) is True


def test_batch_all_rows_no_error(batch_all):
    disp, rows = batch_all
    assert len(rows) == 34 == len(disp)
    assert all(r["error"] is None for r in rows)
    assert all(r["dc_nm"] is not None for r in rows)
    # Thứ tự hàng = thứ tự bảng hiển thị; combo giữ nguyên.
    assert [r["force"].case for r in rows] == [f.case for f in disp]
    # Station chỉ là mã vị trí Top/Bottom, không phải mét.
    for r in rows:
        loc = getattr(r["force"], "location", "")
        assert r["force"].station == (1.0 if loc == "Top" else 0.0)


def test_dcm_only_seismic_and_only_in_plane(batch_all):
    _disp, rows = batch_all
    seis = [r for r in rows if r["seismic"]]
    plain = [r for r in rows if not r["seismic"]]
    assert len(seis) == 8 and len(plain) == 26
    for r in seis:
        sh = r["full"]["shear_in"]
        assert sh["seismic_applied"] is True
        assert sh["seismic_factor"] == 1.5
        assert abs(sh["V_d"] - 1.5 * sh["V_raw"]) < 1e-9
        # Ngoài MP không nhân: V_d ngoài = V_out gốc của dòng.
        assert abs(r["full"]["shear_out"]["V_d"]
                   - r["force"].Q3) < 1e-9
        # N-M không đổi vì DCM: dc N-M của hàng = dc engine (đã có
        # trong full, không nhân thêm ở batch).
        assert abs(r["dc_nm"] - r["full"]["dc"]) < 1e-12
    for r in plain:
        sh = r["full"]["shear_in"]
        assert sh["seismic_applied"] is False
        assert abs(sh["V_d"] - sh["V_raw"]) < 1e-9
    # DCM không hardcode tên: đổi tập chọn thì cờ đổi theo.
    disp1, _n = merge_combo_max_min(_forces(), {"ULS15"})
    rows1 = run_wall_batch(_flat_winp(), _CONC, _STEEL, "3line",
                           disp1, seismic_selected={"ULS15"},
                           steel_sw=_SW)
    for r in rows1:
        want = pier_base_case(r["force"].case) == "ULS15"
        assert r["seismic"] is want
        assert r["full"]["shear_in"]["seismic_applied"] is want


def test_controlling_is_max_after_dcm(batch_all):
    _disp, rows = batch_all
    ctrl = wall_batch_controlling(rows)
    for key, dc_key in (("nm", "dc_nm"), ("in", "dc_in"),
                        ("out", "dc_out"), ("overall", "dc_overall")):
        vals = [r[dc_key] for r in rows if r[dc_key] is not None]
        assert ctrl[key] is not None
        assert abs(ctrl[key][dc_key] - max(vals)) < 1e-12
    # Khống chế chung = hàng có max 3 phần (sau DCM, không phải
    # max V thô): kiểm trực tiếp bằng max trên các hàng.
    assert ctrl["overall"]["dc_overall"] == max(
        r["dc_overall"] for r in rows)
    assert dc_txt(None) == "CHƯA KIỂM"
    assert ok_txt(None) == "CHƯA KIỂM"
    assert ok_txt(True) == "ĐẠT" and ok_txt(False) == "KHÔNG ĐẠT"


def test_cu_out_of_plane_pending_not_blocking():
    w = WallInput(section_type="c-core", cover=28, dia_h=12,
                  per_dia=12, per_s=200, Lw=3000, sec_bf=1500,
                  sec_lr=600, sec_t=300)
    forces = _forces()[:2]  # 2 dòng ULS1 Top/Bottom, không động đất
    rows = run_wall_batch(w, _CONC, _STEEL, "3line", forces,
                          seismic_selected=set(), steel_sw=_SW)
    assert len(rows) == 2
    for r in rows:
        assert r["error"] is None
        assert r["dc_out"] is None and r["ok_out"] is None
        assert dc_txt(r["dc_out"]) == "CHƯA KIỂM"
    ctrl = wall_batch_controlling(rows)
    assert ctrl["out"] is None  # phương pending -> không có khống chế
    assert ctrl["nm"] is not None and ctrl["in"] is not None


def test_wallbatch_gui_xvfb():
    """GUI (skip khi không có display; chạy dưới Xvfb):
    paste file thật -> tick ULS14-17 -> CHECK batch -> bảng batch
    34 dòng, dòng khống chế nạp vào tab Kết quả; chọn 1 dòng khác
    nạp đúng combo đó."""
    try:
        import tkinter as tk
        _r = tk.Tk()
        _r.withdraw()
        _r.destroy()
    except Exception:
        pytest.skip("không có display Tk")
    from gui.app import App
    app = App()
    try:
        app.update_idletasks()
        app.cb_member.set("Vách")
        app._toggle_member()
        app.update_idletasks()
        app.var_load_mode.set("etabs")
        app.etabs_forces_orig = _forces()
        app.seismic_combo_selected = set(_SEIS_ALL)
        app._refresh_merge_display()
        app.update_idletasks()
        assert len(app.etabs_forces) == 34
        app._on_check_wall()
        app.update_idletasks()
        rows = getattr(app, "_wall_batch_rows", None)
        assert rows is not None and len(rows) == 34
        top = getattr(app, "_wall_batch_top", None)
        assert top is not None and top.winfo_exists()
        ctrl = wall_batch_controlling(rows)["overall"]
        assert ctrl is not None
        full = getattr(app, "_tcvn_wall_full", None)
        assert full is ctrl["full"]
        # Chọn 1 dòng batch khác -> tab Kết quả nạp đúng dict đó.
        other = rows[0] if rows[0] is not ctrl else rows[1]
        app._load_wall_batch_row(other)
        app.update_idletasks()
        assert app._tcvn_wall_full is other["full"]
        lbl = getattr(app, "_wall_nm_alpha_lbl", None)
        assert lbl is not None
        assert lbl.cget("text") == \
            f"  α = {float(other['full']['alpha_deg']):.1f}°  "
        # Cột D/C chung ở bảng mục 5 = max 3 phần của từng dòng.
        assert len(app.etabs_tree.get_children()) == 34
    finally:
        try:
            app.destroy()
        except Exception:
            pass
