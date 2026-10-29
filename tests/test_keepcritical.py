"""Nút "Giữ lại tổ hợp nguy hiểm nhất" (mục 5, dùng chung Cột/Vách).

GUI test (skip khi không có display; chạy dưới Xvfb), KHÔNG chạy solver
thật: dựng bảng + _batch_rows/_wall_batch_rows giả lập như sau CHECK,
gọi đúng handler on_keep_critical_combos, kiểm chứng lọc.

CỘT (theo code đọc được):
- (1) mỗi nhóm (Story, Label) giữ combo D/C N-M max, toàn bộ station;
- (2) cắt: batch cột KHÔNG có D/C cắt theo dòng — code lấy Q từ combo
  có |Q2|/|Q3| lớn nhất toàn bảng (etabs_mixin: f_q2 = max(...abs(Q2)));
  handler phải giữ đúng 2 combo đó;
- (3) TX_*: chỉ giữ dòng mà code tra tới — khóa (story, column,
  round(station,3), case[3:]) khớp dòng kiểm tra được giữ.
VÁCH: (1) D/C N-M (dc_nm) max từng nhóm; (2) dc_in/dc_out max từng
nhóm, phương CHƯA KIỂM (None) thì không có tổ hợp cắt.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

try:
    import tkinter as tk
    _r = tk.Tk()
    _r.withdraw()
    _r.destroy()
    _HAS_DISPLAY = True
except Exception:
    _HAS_DISPLAY = False

pytestmark = pytest.mark.skipif(
    not _HAS_DISPLAY, reason="không có display Tk")

from unittest import mock

from rc_column.etabs_import import EtabsForce


def _mk(story, col, case, station, dc=None, q2=0.0, q3=0.0,
        n=1000.0, mx=50.0, my=40.0, location=""):
    return EtabsForce(story=story, column=col, case=case,
                      case_type="Combination", station=station, N=n,
                      Mx=mx, My=my, Q2=q2, Q3=q3, location=location)


def _col_batch(rows_dc):
    """rows_dc: [(force, dc|None)] -> _batch_rows như on_check_etabs:
    sort D/C giảm dần, TX_* (dc None) chen cuối."""
    chk = sorted([p for p in rows_dc if p[1] is not None],
                 key=lambda p: -p[1])
    tx = [p for p in rows_dc if p[1] is None]
    return [(f, {"dc": dc, "ok": dc <= 1.0}) for f, dc in chk] + \
           [(f, None) for f, dc in tx]


def _tree_dc(app):
    """{(label, case, station_txt): dc_txt} đang hiển thị trên bảng."""
    out = {}
    for ch in app.etabs_tree.get_children():
        v = app.etabs_tree.item(ch, "values")
        out[(v[1], v[2], v[3])] = v[9]
    return out


def _column_fixture():
    rows = []
    # COMBO_A: D/C N-M max nhóm (S1,C1); COMBO_B: |Q2| max; COMBO_C:
    # |Q3| max; COMBO_D: không khống chế gì -> bị xóa hẳn.
    spec = {
        "COMBO_A": (0.823, 100.0, 50.0),
        "COMBO_B": (0.500, 500.0, 60.0),
        "COMBO_C": (0.300, 80.0, 400.0),
        "COMBO_D": (0.200, 70.0, 40.0),
    }
    for case, (dc, q2, q3) in spec.items():
        for st in (0.0, 2.0, 4.0):
            rows.append((_mk("S1", "C1", case, st, q2=q2, q3=q3), dc))
    # TX_*: 2 dòng khớp COMBO_A (giữ), 1 dòng station lẻ (xóa),
    # 1 dòng của COMBO_D (xóa theo combo bị xóa).
    rows.append((_mk("S1", "C1", "TX_COMBO_A", 0.0), None))
    rows.append((_mk("S1", "C1", "TX_COMBO_A", 4.0), None))
    rows.append((_mk("S1", "C1", "TX_COMBO_A", 1.0), None))
    rows.append((_mk("S1", "C1", "TX_COMBO_D", 0.0), None))
    return rows


def _new_app():
    from gui.app import App
    app = App()
    app.update_idletasks()
    app.var_load_mode.set("etabs")
    app._toggle_load_mode()
    app.update_idletasks()
    return app


def test_column_keep_critical_two_groups():
    """D/C N-M max (COMBO_A) KHÁC combo |Q2| max (COMBO_B) và |Q3| max
    (COMBO_C): cả ba đều được giữ; COMBO_D + TX_* không tương ứng bị
    xóa; D/C các dòng còn lại không đổi từng chữ số."""
    app = _new_app()
    try:
        rows_dc = _column_fixture()
        disp = [f for f, _ in rows_dc]
        assert len(disp) == 16
        app.etabs_forces_orig = list(disp)
        app.etabs_forces = list(disp)
        app._batch_rows = _col_batch(rows_dc)
        app._wall_batch_rows = None
        app._fill_etabs_table(app._batch_rows)
        app.update_idletasks()
        before = _tree_dc(app)
        assert before[("C1", "COMBO_A", "0.00")] == "0.823"

        msgs = []
        with mock.patch("tkinter.messagebox.askyesno",
                        side_effect=lambda t, m: msgs.append((t, m))
                        or True):
            app.on_keep_critical_combos()
        app.update_idletasks()
        assert len(msgs) == 1
        _title, body = msgs[0]
        # Popup liệt kê đủ 3 nhóm giữ + TX_*
        assert "COMBO_A" in body and "0.823" in body          # N-M max
        assert "COMBO_B" in body and "|Q2|=500" in body       # cắt V2
        assert "COMBO_C" in body and "|Q3|=400" in body       # cắt V3
        assert "COMBO_D" in body                              # combo bị xóa
        assert "TX_*" in body

        after = _tree_dc(app)
        cases = sorted({c for _, c, _ in after})
        assert cases == ["COMBO_A", "COMBO_B", "COMBO_C",
                         "TX_COMBO_A"], cases
        # Toàn bộ station của combo được giữ
        assert len(after) == 11  # 3+3+3 thường + 2 TX
        # D/C không đổi từng chữ số
        for k, v in after.items():
            assert before[k] == v, k
        # TX_COMBO_A@1.0 (station không khớp dòng kiểm tra) đã bị xóa
        assert ("C1", "TX_COMBO_A", "1.00") not in after
        assert ("C1", "TX_COMBO_D", "0.00") not in after
        # Dữ liệu gốc + JSON chỉ còn dòng được giữ (không đổi schema)
        assert len(app.etabs_forces_orig) == 11
        d = app._collect_data()
        saved_cases = sorted({fd["case"] for fd in d["etabs_forces"]})
        assert saved_cases == ["COMBO_A", "COMBO_B", "COMBO_C",
                               "TX_COMBO_A"], saved_cases
        assert set(d.keys()) >= {"etabs_forces",
                                 "seismic_combo_selected"}
        # Cache batch đã đồng bộ (không còn dòng COMBO_D)
        assert all(f.case != "COMBO_D"
                   for f, _r in app._batch_rows)
        assert len(app._batch_rows) == 11
    finally:
        try:
            app.destroy()
        except Exception:
            pass


def test_column_warn_when_not_checked():
    """Chưa CHECK (bảng không có D/C) -> popup cảnh báo, bảng nguyên."""
    app = _new_app()
    try:
        rows_dc = _column_fixture()
        disp = [f for f, _ in rows_dc]
        app.etabs_forces_orig = list(disp)
        app.etabs_forces = list(disp)
        app._batch_rows = None
        app._wall_batch_rows = None
        app._fill_etabs_table([(f, None) for f in disp])
        app.update_idletasks()
        n_before = len(app.etabs_tree.get_children())
        warns = []
        with mock.patch("tkinter.messagebox.showwarning",
                        side_effect=lambda t, m: warns.append((t, m))):
            app.on_keep_critical_combos()
        assert len(warns) == 1
        assert "CHECK" in warns[0][1]
        assert len(app.etabs_tree.get_children()) == n_before
        assert len(app.etabs_forces_orig) == 16
    finally:
        try:
            app.destroy()
        except Exception:
            pass


def test_column_no_tx_rows():
    """Không có TX_*: vẫn giữ đúng combo N-M max + 2 combo cắt."""
    app = _new_app()
    try:
        rows_dc = [(f, dc) for f, dc in _column_fixture()
                   if not f.case.startswith("TX_")]
        disp = [f for f, _ in rows_dc]
        app.etabs_forces_orig = list(disp)
        app.etabs_forces = list(disp)
        app._batch_rows = _col_batch(rows_dc)
        app._wall_batch_rows = None
        app._fill_etabs_table(app._batch_rows)
        app.update_idletasks()
        with mock.patch("tkinter.messagebox.askyesno",
                        return_value=True):
            app.on_keep_critical_combos()
        app.update_idletasks()
        after = _tree_dc(app)
        assert sorted({c for _, c, _ in after}) == \
            ["COMBO_A", "COMBO_B", "COMBO_C"]
        assert len(after) == 9
    finally:
        try:
            app.destroy()
        except Exception:
            pass


def _wall_batch_rows(forces, specs):
    """specs: {(pier, case, location): (dc_nm, dc_in, dc_out)} -> list
    rowdict như run_wall_batch (đủ khóa handler dùng)."""
    rows = []
    for f in forces:
        if f.case.startswith("TX_"):
            continue
        nm, di, do = specs[(f.column, f.case, f.location)]
        vals = [v for v in (nm, di, do) if v is not None]
        rows.append({"force": f, "full": None, "seismic": False,
                     "error": None, "dc_nm": nm, "dc_in": di,
                     "dc_out": do,
                     "dc_overall": max(vals) if vals else None,
                     "ok_nm": True, "ok_in": True, "ok_out": True,
                     "ok_overall": True, "V_ed_in": None,
                     "V_raw_in": None})
    return rows


def test_wall_keep_critical():
    """Vách: (1) dc_nm max từng nhóm + (2) dc_in/dc_out max từng nhóm;
    phương CHƯA KIỂM (None) không sinh tổ hợp cắt; TX_* tương ứng giữ."""
    from gui.app import App
    app = App()
    try:
        app.update_idletasks()
        app.cb_member.set("Vách")
        app._toggle_member()
        app.var_load_mode.set("etabs")
        app._toggle_load_mode()
        app.update_idletasks()
        forces = [
            _mk("F3", "P1", "ULS1", 1.0, location="Top"),
            _mk("F3", "P1", "ULS1", 0.0, location="Bottom"),
            _mk("F3", "P1", "ULS2", 1.0, location="Top"),
            _mk("F3", "P1", "ULS2", 0.0, location="Bottom"),
            _mk("F3", "P1", "ULS3", 1.0, location="Top"),
            _mk("F3", "P1", "ULS3", 0.0, location="Bottom"),
            # Nhóm P2: ngoài MP pending hoàn toàn -> popup CHƯA KIỂM
            _mk("F3", "P2", "ULS1", 1.0, location="Top"),
            _mk("F3", "P2", "ULS1", 0.0, location="Bottom"),
            _mk("F3", "P1", "TX_ULS1", 1.0, location="Top"),
            _mk("F3", "P1", "TX_ULS3", 1.0, location="Top"),
        ]
        specs = {
            ("P1", "ULS1", "Top"): (0.90, 0.40, 0.30),
            ("P1", "ULS1", "Bottom"): (0.85, 0.38, 0.28),
            ("P1", "ULS2", "Top"): (0.50, 0.70, None),
            ("P1", "ULS2", "Bottom"): (0.48, 0.68, None),
            ("P1", "ULS3", "Top"): (0.30, 0.20, 0.10),
            ("P1", "ULS3", "Bottom"): (0.28, 0.18, 0.09),
            ("P2", "ULS1", "Top"): (0.60, 0.35, None),
            ("P2", "ULS1", "Bottom"): (0.55, 0.33, None),
        }
        app.etabs_forces_orig = list(forces)
        app.etabs_forces = list(forces)
        app._batch_rows = None  # batch cột cũ (nếu có) hết hiệu lực
        wrows = _wall_batch_rows(forces, specs)
        app._wall_batch_rows = wrows
        by_id = {id(r["force"]): r for r in wrows}
        app._fill_etabs_table(
            [(f, ({"dc": by_id[id(f)]["dc_overall"]}
                  if id(f) in by_id else None)) for f in forces])
        app.update_idletasks()
        before = _tree_dc(app)
        assert before[("P1", "ULS1", "Top")] == "0.900"

        msgs = []
        with mock.patch("tkinter.messagebox.askyesno",
                        side_effect=lambda t, m: msgs.append((t, m))
                        or True):
            app.on_keep_critical_combos()
        app.update_idletasks()
        assert len(msgs) == 1
        _title, body = msgs[0]
        assert "ULS1" in body and "0.900" in body       # N-M max P1
        assert "ULS2" in body and "0.700" in body       # cắt trong MP
        assert "CHƯA KIỂM" in body                     # P2 ngoài MP
        assert "ULS3" in body                          # combo bị xóa

        after = _tree_dc(app)
        cases = sorted({c for _, c, _ in after})
        assert cases == ["TX_ULS1", "ULS1", "ULS2"], cases
        assert len(after) == 7  # P1: 2+2, P2: 2, TX: 1
        for k, v in after.items():
            assert before[k] == v, k
        assert ("P1", "ULS3", "Top") not in after
        assert ("P1", "TX_ULS3", "Top") not in after
        # JSON chỉ còn dòng được giữ
        d = app._collect_data()
        saved = sorted({fd["case"] for fd in d["etabs_forces"]})
        assert saved == ["TX_ULS1", "ULS1", "ULS2"], saved
        # Cache batch vách đồng bộ
        assert all(r["force"].case != "ULS3"
                   for r in app._wall_batch_rows)
    finally:
        try:
            app.destroy()
        except Exception:
            pass
