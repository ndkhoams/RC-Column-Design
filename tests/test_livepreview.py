"""Mở file không tự tính + thông số tiết diện live update (quyết user 2026-10-29).

(1) on_load_data KHÔNG gọi on_check: không solver nào chạy, không có
    _tcvn_full/_last_res/_tcvn_wall_full; tab Kết quả chỉ hiện preview
    mặt cắt + 4 thẻ live (cột) / preview vách (vách).
(2) Đổi ô nhập (cx) -> _refresh_rebar -> thẻ Ab/As/μ/n + hình vẽ lại
    ngay, giá trị khớp build_section(_draft_input()) — cùng hàm
    _section_card_values mà _redraw_old dùng sau CHECK.
(3) Bấm CHECK sau khi mở file -> D/C đúng như _apply_data + on_check
    trực tiếp (không regression do bỏ auto-check).
(4) Cards ACI/EC2 (result_renderer) dùng StringVar -> live update được
    (trước đây là label tĩnh: mặt cắt vẽ lại mà thông số không đổi).

GUI test (skip khi không có display; chạy dưới Xvfb).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest import mock

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

from gui.app import App
from rc_column.checker import build_section


_COL_JSON = {
    "member_name": "C1",
    "member_type": "column",
    "code": "TCVN 5574:2018",
    "concrete": "B30",
    "steel": "CB500-V",
    "kind": "Chữ nhật",
    "cx": "400",
    "cy": "400",
    "cover": "28",
    "corner_dia": "25",
    "e2n": "2",
    "e2d": "20",
    "e3n": "2",
    "e3d": "20",
    "load_mode": "manual",
    "N": "2000",
    "Mx": "100",
    "My": "80",
    "Q2": "50",
    "Q3": "30",
}

_WALL_JSON = {
    "member_name": "W1",
    "member_type": "wall",
    "code": "TCVN 5574:2018",
    "concrete": "B30",
    "steel": "CB500-V",
    "load_mode": "manual",
    "N": "2000",
    "Mx": "100",
    "My": "80",
    "wall": {},
}


def _write(tmp_path, d):
    p = str(tmp_path / "t.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f)
    return p


def _open(app, path):
    """Mở file qua đúng handler on_load_data (mock filedialog)."""
    with mock.patch("tkinter.filedialog.askopenfilename",
                    return_value=path):
        app.on_load_data()
    app.update_idletasks()


def _mkapp():
    app = App()
    app.update_idletasks()
    return app


def _open_col(tmp_path):
    app = _mkapp()
    with mock.patch.object(app, "on_check") as m:
        _open(app, _write(tmp_path, _COL_JSON))
    return app, m


def test_open_column_no_solver_and_preview(tmp_path):
    app, m = _open_col(tmp_path)
    try:
        # (1) KHÔNG tự tính
        assert m.call_count == 0
        assert app._tcvn_full is None
        assert app._last_sec is None
        assert app._last_res is None
        assert app._aci_res is None and app._ec2_res is None
        # Preview mặt cắt đã vẽ + 4 thẻ live tồn tại
        assert getattr(app, "_sec_ax", None) is not None
        varmap = getattr(app, "_sec_card_vars", None)
        assert varmap and set(("n", "as", "ab", "mu")) <= set(varmap)
        for v in varmap.values():
            assert isinstance(v, tk.StringVar)
        # (2) thẻ khớp input trong file (400x400)
        assert varmap["ab"].get() == "160000 mm²"
    finally:
        app.destroy()


def test_cards_live_update_on_input_change(tmp_path):
    app, _m = _open_col(tmp_path)
    try:
        varmap = app._sec_card_vars
        ab_before = varmap["ab"].get()
        assert ab_before == "160000 mm²"
        # Đổi cạnh t3 400 -> 500, kích hoạt đúng nhịp live như user gõ
        app.en_cx.delete(0, tk.END)
        app.en_cx.insert(0, "500")
        app._refresh_rebar()
        app.update_idletasks()
        assert varmap["ab"].get() == "200000 mm²"
        # Khớp đúng hàm tính mà _redraw_old dùng sau CHECK
        sec = build_section(app._draft_input())
        vals = app._section_card_values(sec)
        for k in ("n", "as", "ab", "mu"):
            assert varmap[k].get() == vals[k], k
    finally:
        app.destroy()


def test_check_after_open_same_dc(tmp_path):
    d = dict(_COL_JSON)
    app1 = _mkapp()
    try:
        app1._apply_data(d)
        app1.on_check()
        dc1 = app1._last_res.dc
    finally:
        app1.destroy()
    app2, _m = _open_col(tmp_path)
    try:
        app2.on_check()
        dc2 = app2._last_res.dc
    finally:
        app2.destroy()
    assert dc1 == dc2 != 0


def test_aci_cards_are_live_stringvars(tmp_path):
    app = _mkapp()
    try:
        app.cb_code.set("ACI 318-19")
        app._toggle_code()
        with mock.patch.object(app, "on_check") as m:
            _open(app, _write(tmp_path, _COL_JSON))
        assert m.call_count == 0
        app.on_check()
        app.update_idletasks()
        varmap = getattr(app, "_sec_card_vars", None)
        assert varmap and set(("n", "as", "ab", "mu")) <= set(varmap)
        for v in varmap.values():
            assert isinstance(v, tk.StringVar)
        ab_before = varmap["ab"].get()
        app.en_cx.delete(0, tk.END)
        app.en_cx.insert(0, "500")
        app._refresh_rebar()
        app.update_idletasks()
        assert varmap["ab"].get() != ab_before
        assert varmap["ab"].get() == "200000 mm²"
    finally:
        app.destroy()


def test_open_wall_file_no_autocheck(tmp_path):
    app = _mkapp()
    try:
        with mock.patch.object(app, "on_check") as m:
            _open(app, _write(tmp_path, _WALL_JSON))
        assert m.call_count == 0
        assert app._tcvn_wall_full is None
        # Preview vách đã vẽ (cơ chế có sẵn)
        assert getattr(app, "_wall_view_active", False) is True
        assert getattr(app, "_sec_ax", None) is not None
        varmap = getattr(app, "_sec_card_vars", None)
        assert varmap and set(("n", "as", "ab", "mu")) <= set(varmap)
    finally:
        app.destroy()
