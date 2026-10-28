"""5 quyết sau đối chiếu Hướng dẫn BXD QĐ 862 (2026-10-28):
(1) ghi chú phạm vi siêu tĩnh; (2) giữ tia song trục duy nhất
(không kiểm φ tách rời — chỉ ghi chú, không test số); (3) cảnh báo
η bị kẹp 10,0 khi Ncr ≤ |N|; (4) φl vách từ tải dài hạn nhập tay
theo §5.1.2 (5-31), từng phương độc lập; (5) không làm η theo
thành phần tải (không có code/tùy chọn cho việc này).
"""

import matplotlib

matplotlib.use("Agg")

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.stability import buckling_factors, phi_l_dir
from rc_column.wall_detail import build_wall_detail_sections
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_input import WallInput

_CONC = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
_STEEL = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)


def _wall(kw, Mi, Mo, N=2000.0):
    w = WallInput(section_type="rect", cover=13, dia_h=12,
                  per_dia=12, per_s=200, rot_deg=0)
    for k, v in kw.items():
        setattr(w, k, v)
    return wall_tcvn_full(w, _CONC, _STEEL,
                          loads={"N": N, "M_in": Mi, "M_out": Mo,
                                 "V_in": 0.0, "V_out": 0.0, "T": 0.0})


def test_phi_l_dir_s7_numbers():
    # Ví dụ §7: M1 = 3000 + 6000×(1500−2×79)/2000 = 7026;
    # M1l = 750 + 5000×1342/2000 = 4105; φl = 1 + 4105/7026.
    assert abs(phi_l_dir(6000.0, 3000.0, 5000.0, 750.0,
                         1500.0, 79.0) - 1.584) < 0.001
    assert phi_l_dir(6000.0, 3000.0, 5000.0, 750.0,
                     1500.0, 79.0, has_data=False) == 2.0
    assert phi_l_dir(6000.0, 3000.0, 5000.0, 750.0,
                     100.0, 80.0) == 2.0  # h − 2a ≤ 0 → fallback
    assert phi_l_dir(1000.0, 100.0, 5000.0, 5000.0,
                     1500.0, 79.0) == 2.0  # kẹp trên


def test_buckling_clamped_flag():
    # Ncr ≤ |N| + λ > 14 → η = 10,0 và cờ kẹp bật.
    b = buckling_factors(50.0, 50.0, 400.0, 400.0, 2.0, 25000.0,
                         1.0e10, 1.0e10, 1.0e8, 1.0e8, 10.0, 10.0,
                         1.0e6, 100.0, 100.0,
                         lambda_x=100.0, lambda_y=100.0)
    assert b.etax == 10.0 and b.eta_clamped_x
    assert b.etay == 10.0 and b.eta_clamped_y
    # Cùng Ncr ≤ |N| nhưng λ ≤ 14 → η = 1,0, cờ kẹp TẮT (η kẹp
    # không được dùng).
    b2 = buckling_factors(50.0, 50.0, 400.0, 400.0, 2.0, 25000.0,
                          1.0e10, 1.0e10, 1.0e8, 1.0e8, 10.0, 10.0,
                          1.0e6, 100.0, 100.0,
                          lambda_x=10.0, lambda_y=10.0)
    assert b2.etax == 1.0 and not b2.eta_clamped_x
    assert b2.etay == 1.0 and not b2.eta_clamped_y


def test_wall_no_long_term_keeps_phi_2():
    f = _wall({}, 800.0, 200.0)
    assert f["phi_L_in"] == 2.0 and f["phi_L_out"] == 2.0
    assert f["lt_has_data"] is False
    assert f["eta_clamped_in"] is False
    assert f["eta_clamped_out"] is False


def test_wall_long_term_phi_per_direction():
    # Tải dài hạn = đúng 1/2 tải toàn bộ cả 3 thành phần →
    # φl = 1,5 cả 2 phương (a = 13 + 12 + 12/2 = 31 mm;
    # trong MP: M1 = 800 + 2000×2438/2000 = 3238, M1l = 1619;
    # ngoài MP: M1 = 200 + 2000×288/2000 = 488, M1l = 244).
    lt = dict(N_lt=1000.0, M_in_lt=400.0, M_out_lt=100.0)
    base = _wall({}, 800.0, 200.0)
    f = _wall(lt, 800.0, 200.0)
    assert f["lt_has_data"] is True
    assert abs(f["phi_L_in"] - 1.5) < 1e-9
    assert abs(f["phi_L_out"] - 1.5) < 1e-9
    # φl nhỏ → kb lớn → Ncr lớn → η ngoài MP nhỏ lại (λ_out > 14).
    assert f["slend"]["Ncr_out"] > base["slend"]["Ncr_out"]
    assert f["slend"]["factor_out"] < base["slend"]["factor_out"]
    assert f["slend"]["factor_out"] > 1.0


def test_wall_eta_clamped_warning_in_detail():
    # L0 ngoài MP = 22,5 m (Ly_m = 15, psi_y = 1,5), N = 6000 →
    # Ncr_out ≈ 944 kN < N → η_out kẹp 10,0, cảnh báo phải hiện
    # trong thuyết minh chi tiết (mục 5, thẻ Y).
    f = _wall(dict(Ly_m=15.0, psi_y=1.5), 0.0, 0.0, N=6000.0)
    assert f["slend"]["factor_out"] == 10.0
    assert f["eta_clamped_out"] is True
    secs = build_wall_detail_sections(f)
    sec5 = next(s for s in secs if s["num"] == 5)
    txt = " ".join(" ".join(c["lines"]) for c in sec5["cards"])
    assert "CẢNH BÁO" in txt and "10,0" in txt
    # Ca bình thường: không có cảnh báo kẹp.
    f2 = _wall({}, 800.0, 200.0)
    secs2 = build_wall_detail_sections(f2)
    sec5b = next(s for s in secs2 if s["num"] == 5)
    txt2 = " ".join(" ".join(c["lines"]) for c in sec5b["cards"])
    assert "CẢNH BÁO" not in txt2


def test_wall_detail_scope_note():
    # Ghi chú phạm vi mục 5: siêu tĩnh / song trục duy nhất /
    # không η theo thành phần tải / φl mặc định.
    f = _wall({}, 800.0, 200.0)
    secs = build_wall_detail_sections(f)
    sec5 = next(s for s in secs if s["num"] == 5)
    txt = " ".join(" ".join(c["lines"]) for c in sec5["cards"])
    assert "SIÊU TĨNH" in txt
    assert "e1 + ea" in txt
    assert "song trục duy nhất" in txt
    assert "thành phần tải" in txt
    assert "φl = 2,0" in txt
    f3 = _wall(dict(N_lt=1000.0, M_in_lt=400.0, M_out_lt=100.0),
               800.0, 200.0)
    secs3 = build_wall_detail_sections(f3)
    sec5c = next(s for s in secs3 if s["num"] == 5)
    txt3 = " ".join(" ".join(c["lines"]) for c in sec5c["cards"])
    assert "tải dài hạn nhập tay" in txt3


def test_wall_gui_long_term_roundtrip():
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
        # Nhập tải dài hạn ở mục 4 + tải mục 5 dùng chung.
        for en, val in ((app.w_en_lt_N, "1000"),
                        (app.w_en_lt_Min, "400"),
                        (app.w_en_lt_Mout, "100")):
            en.delete(0, tk.END)
            en.insert(0, val)
        for en, val in ((app.en_N, "2000"), (app.en_My, "800"),
                        (app.en_Mx, "200"), (app.en_Q2, "0"),
                        (app.en_Q3, "0")):
            en.delete(0, tk.END)
            en.insert(0, val)
        d = app._collect_wall()
        assert float(d["N_lt"]) == 1000.0
        assert float(d["M_in_lt"]) == 400.0
        assert float(d["M_out_lt"]) == 100.0
        app._apply_wall(d)
        assert app.w_en_lt_N.get() == "1000"
        assert app.w_en_lt_Min.get() == "400"
        assert app.w_en_lt_Mout.get() == "100"
        app._check_wall_tcvn()
        full = app._tcvn_wall_full
        assert abs(full["phi_L_in"] - 1.5) < 1e-9
        assert abs(full["phi_L_out"] - 1.5) < 1e-9
    finally:
        try:
            app.destroy()
        except Exception:
            pass
