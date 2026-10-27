"""Sửa hiển thị α cho vách C/U (2026-10-27) — CHỈ hiển thị.

Quy ước duy nhất (AGENTS.md §4, quy ước ETABS đã chốt):
α hiển thị = atan2(M2, M3) với M2 = M_out_d (ngoài MP),
M3 = M_in_d (trong MP) — đúng cặp mô men thiết kế đã phóng
đại, có dấu, chuẩn hoá [0, 360). Trước sửa, C/U dùng góc
solver atan2(M_in_d, M_out_d) nên ca trong MP 800 / ngoài MP
200 hiện 76,0° thay vì 14,0°. Sau sửa chỉ nhãn α đổi:
D/C, điểm B, Mα, Mα,u, vị trí điểm A trên tia giữ nguyên
(góc solver vẫn lưu riêng ở alpha_solver_deg và vẫn dùng
cho Mα,u/vùng nén/biểu đồ).

Ca khóa: hình học mặc định như test_wallnm_poly (B30 γb=0,85 /
CB500-V, cover 28, d12 s200), tải N = 2000, trong MP 800,
ngoài MP 200 (và ca đổi dấu ngoài MP −200 để kiểm chuẩn
hoá [0, 360)). Ca này khác ca hồi quy lát N–M dưới đây.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_input import WallInput

_CONC = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
_STEEL = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)


def _mk(st, kw):
    w = WallInput(section_type=st, cover=28, dia_h=12,
                  per_dia=12, per_s=200)
    for k, v in kw.items():
        setattr(w, k, v)
    return w


def _loads(N, Mi, Mo):
    return {"N": N, "M_in": Mi, "M_out": Mo,
            "V_in": 0.0, "V_out": 0.0, "T": 0.0}


def _disp(f):
    """α hiển thị phải đúng công thức ETABS trên mô men thiết kế."""
    exp = math.degrees(math.atan2(f["M_out_d"], f["M_in_d"])) % 360.0
    assert abs((f["alpha_deg"] - exp + 180.0) % 360.0 - 180.0) < 1e-9, \
        (f["alpha_deg"], exp)
    return exp


def test_cu_display_alpha_800_200():
    """Ca đối chiếu web: C/U, N=2000, trong MP 800, ngoài MP 200
    -> chip α 14,0° (trước sửa: 76,0°); góc solver giữ 76,0°."""
    for st, kw in [
            ("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600,
                            sec_t=300)),
            ("u-core", dict(Lw=3000, sec_bf=1500, sec_t=300))]:
        f = wall_tcvn_full(_mk(st, kw), _CONC, _STEEL,
                           loads=_loads(2000.0, 800.0, 200.0))
        assert f["M_in_d"] == 800.0 and f["M_out_d"] == 200.0
        _disp(f)
        assert f"{f['alpha_deg']:.1f}" == "14.0", \
            (st, f["alpha_deg"])
        assert abs(f["alpha_solver_deg"] - 75.9638) < 0.01, \
            (st, f["alpha_solver_deg"])
        # Mα, Mα,u, điểm B: so với giá trị đã chạy ở head e2218250
        # bằng cùng code solver (góc solver không đổi) — khóa để
        # chứng minh sửa hiển thị không chạm engine.
        assert abs(f["Malpha"] - 824.615) < 0.01


def test_cu_display_alpha_sign_flip_normalization():
    """Ca đổi dấu tương ứng: trong MP 800, ngoài MP −200
    -> α hiển thị 346,0° (chuẩn hoá [0, 360), không phải −14°);
    góc solver 104,0°."""
    for st, kw in [
            ("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600,
                            sec_t=300)),
            ("u-core", dict(Lw=3000, sec_bf=1500, sec_t=300))]:
        f = wall_tcvn_full(_mk(st, kw), _CONC, _STEEL,
                           loads=_loads(2000.0, 800.0, -200.0))
        assert f["M_in_d"] == 800.0 and f["M_out_d"] == -200.0
        _disp(f)
        assert f"{f['alpha_deg']:.1f}" == "346.0", \
            (st, f["alpha_deg"])
        assert abs(f["alpha_solver_deg"] - 104.0362) < 0.01, \
            (st, f["alpha_solver_deg"])
        assert 0.0 <= f["alpha_deg"] < 360.0


def test_axis_x_and_flat_alpha_unchanged():
    """Barbell/T/L + phẳng: α hiển thị = góc solver như trước
    (công thức cũ đã đúng), không đổi số ở ca 800/200."""
    cases = [
        ("barbell", dict(Lw=3000, tw=300, sec_bf=1000, sec_tf=450),
         14.1564),
        ("tee", dict(Lw=2500, sec_bf=1500, sec_t=300), 14.1407),
        ("ell", dict(sec_L1=2000, sec_L2=1800, sec_t=300), 14.0362),
    ]
    for st, kw, exp in cases:
        f = wall_tcvn_full(_mk(st, kw), _CONC, _STEEL,
                           loads=_loads(2000.0, 800.0, 200.0))
        _disp(f)
        assert abs(f["alpha_deg"] - f["alpha_solver_deg"]) < 1e-9
        assert abs(f["alpha_deg"] - exp) < 0.01, (st, f["alpha_deg"])
    f = wall_tcvn_full(WallInput(cover=13.0), _CONC, _STEEL,
                       loads=_loads(2000.0, 800.0, 200.0))
    _disp(f)
    assert abs(f["alpha_deg"] - f["alpha_solver_deg"]) < 1e-9
    assert abs(f["alpha_deg"] - 15.4016) < 0.01


def test_nm_dc_regression_unchanged():
    """D/C 5 loại ở ca kiểm tra lát N–M (khác ca đối chiếu web):
    từng chữ số như trước sửa."""
    cases = [
        ("barbell", dict(Lw=3000, tw=300, sec_bf=1000, sec_tf=450),
         3000.0, 1500.0, 300.0, 0.22814),
        ("tee", dict(Lw=2500, sec_bf=1500, sec_t=300),
         2000.0, 800.0, 200.0, 0.18197),
        ("ell", dict(sec_L1=2000, sec_L2=1800, sec_t=300),
         2000.0, 700.0, 500.0, 0.28919),
        ("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600, sec_t=300),
         3000.0, 1000.0, 600.0, 0.15648),
        ("u-core", dict(Lw=3000, sec_bf=1500, sec_t=300),
         3000.0, 1200.0, 400.0, 0.17834),
    ]
    for st, kw, N, Mi, Mo, dc_exp in cases:
        f = wall_tcvn_full(_mk(st, kw), _CONC, _STEEL,
                           loads=_loads(N, Mi, Mo))
        assert abs(f["dc"] - dc_exp) < 5e-6, (st, f["dc"], dc_exp)


def test_cu_detail_note_web_alpha():
    """Thẻ chi tiết C/U có ghi chú α web không cùng định nghĩa
    với α ETABS (không spam: chỉ 1 dòng ở thẻ Điểm tải A)."""
    from rc_column.wall_detail import build_wall_detail_sections
    f = wall_tcvn_full(
        _mk("c-core", dict(Lw=3000, sec_bf=1500, sec_lr=600,
                           sec_t=300)),
        _CONC, _STEEL, loads=_loads(2000.0, 800.0, 200.0))
    joined = "\n".join(
        line for s in build_wall_detail_sections(f)
        for c in s["cards"] for line in c.get("lines", []))
    assert "không cùng định nghĩa với α ETABS" in joined


def test_cu_gui_check_chip_xvfb():
    """GUI (skip khi không có display; chạy dưới Xvfb):
    CHECK lõi C nhập tay -> chip α tab Kết quả đúng α hiển thị
    (công thức ETABS), khác góc solver cũ ở ca này."""
    try:
        import tkinter as tk
        _r = tk.Tk()
        _r.withdraw()
        _r.destroy()
    except Exception:
        import pytest
        pytest.skip("không có display Tk")
    from gui.app import App
    app = App()
    try:
        app.update_idletasks()
        app.cb_member.set("Vách")
        app._toggle_member()
        app.update_idletasks()
        app.w_cb_sectype.set("Lõi chữ C")
        app._on_wall_sectype()
        app.update_idletasks()
        app.var_load_mode.set("manual")

        def _set(entry, val):
            entry.delete(0, "end")
            entry.insert(0, str(val))

        _set(app.en_N, 2000)
        _set(app.en_My, 800)
        _set(app.en_Mx, 200)
        _set(app.en_Q2, 0)
        _set(app.en_Q3, 0)
        app._on_check_wall()
        app.update_idletasks()
        full = getattr(app, "_tcvn_wall_full", None)
        assert full is not None
        assert full["winp"].section_type == "c-core"
        _disp(full)
        lbl = getattr(app, "_wall_nm_alpha_lbl", None)
        assert lbl is not None
        assert lbl.cget("text") == \
            f"  α = {float(full['alpha_deg']):.1f}°  "
        # Ca này góc solver và góc hiển thị phải khác nhau rõ
        # (nếu chip còn dùng góc solver thì test này bắt được).
        assert abs((full["alpha_deg"] - full["alpha_solver_deg"]
                     + 180.0) % 360.0 - 180.0) > 10.0
    finally:
        try:
            app.destroy()
        except Exception:
            pass
