"""Sàn lệch tâm ea cho phương mô men gốc = 0 (user duyệt 2026-10-27,
mức vách + cột TCVN, quy tắc dấu W, không worst-case, không ACI/EC2).

M* = sign·N·e0·η mỗi phương độc lập (e0 = max(e1, ea)); dấu: M ≠ 0 →
dấu M gốc, M = 0 → dấu sàn W: trong MP +, ngoài MP − (khung
(M_in, M_out), thống nhất cả 2 loại trục, xác nhận web C/U 2026-10-27).
Khi e1 ≥ ea thì trùng η·M nên ca thường không đổi. N ≤ 0 giữ nguyên.
P–δ tắt → η = 1 nhưng vẫn áp sàn; λ ≤ 14 vẫn áp sàn.
"""

import math

import matplotlib

matplotlib.use("Agg")

from rc_column.checker import (BatchChecker, ColumnInput, check_column)
from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.stability import design_moment
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_input import WallInput

_CONC = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
_STEEL = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)


def _wall(st, kw, Mi, Mo, N=2000.0, pd=None):
    w = WallInput(section_type=st, cover=13, dia_h=12,
                  per_dia=12, per_s=200, rot_deg=0)
    for k, v in kw.items():
        setattr(w, k, v)
    if pd is not None:
        w.pd_method = pd
    return wall_tcvn_full(w, _CONC, _STEEL,
                          loads={"N": N, "M_in": Mi, "M_out": Mo,
                                 "V_in": 0.0, "V_out": 0.0, "T": 0.0})


def test_design_moment_unit():
    # M ≠ 0, e1 < ea → N·e0·η giữ dấu M gốc; e1 ≥ ea → trùng η·M.
    assert design_moment(2000.0, -100.0, 60.0, 1.0, -1.0) == -120.0
    assert design_moment(2000.0, 800.0, 400.0, 1.0, -1.0) == 800.0
    # M = 0 → dấu sàn (không phải 0).
    assert design_moment(2000.0, 0.0, 60.0, 1.0, -1.0) == -120.0
    assert abs(design_moment(2000.0, 0.0, 66.7, 1.0, +1.0) - 133.4) < 0.11


def test_flat_wall_numbers():
    # Ca ảnh cả 2 phương e1 > ea → không đổi từng chữ số (0.35234).
    f = _wall("rect", {}, 275.23, 202.86, N=2528.65)
    assert abs(f["dc"] - 0.35234) < 5e-5
    assert abs(f["M_in_d"] - 275.2) < 0.11
    assert abs(f["M_out_d"] - 227.3) < 0.11
    # Chỉ trong MP: sàn ngoài MP −25.2 (ea 11.7 × η 1.080).
    f = _wall("rect", {}, 800.0, 0.0)
    assert abs(f["dc"] - 0.21962) < 5e-5
    assert abs(f["M_out_d"] - (-25.2)) < 0.11
    # Chỉ ngoài MP: sàn trong MP +166.7 (ea 83.3).
    f = _wall("rect", {}, 0.0, 800.0)
    assert abs(f["dc"] - 2.99138) < 5e-5
    assert abs(f["M_in_d"] - 166.7) < 0.11
    # Nén thuần túy: cả 2 sàn.
    f = _wall("rect", {}, 0.0, 0.0)
    assert abs(f["dc"] - 0.16081) < 5e-5
    assert abs(f["M_in_d"] - 166.7) < 0.11
    assert abs(f["M_out_d"] - (-25.2)) < 0.11
    # Mô men trong MP nhỏ nhưng ≠ 0: trong MP đã sàn từ trước.
    f = _wall("rect", {}, 20.0, 200.0)
    assert abs(f["dc"] - 0.31989) < 5e-5
    assert abs(f["M_in_d"] - 166.7) < 0.11


def test_l_wall_w_sign():
    kw = dict(sec_L1=2000, sec_L2=1800, sec_t=300)
    # Thuần trong MP theo dấu W: sàn ngoài MP −120 → 0.23309
    # (không phải 0.25321 của copysign +120).
    f = _wall("ell", kw, 800.0, 0.0)
    assert abs(f["M_out_d"] - (-120.0)) < 0.11
    assert abs(f["dc"] - 0.23309) < 5e-5
    # Thuần ngoài MP: sàn trong MP +133.3 → 0.22931 (khớp web +0,1%).
    f = _wall("ell", kw, 0.0, -800.0)
    assert abs(f["M_in_d"] - 133.3) < 0.11
    assert abs(f["dc"] - 0.22931) < 5e-5
    # Song trục e1 > ea cả 2 phương → không đổi.
    f = _wall("ell", kw, 800.0, -200.0)
    assert abs(f["dc"] - 0.22891) < 5e-5
    # P–δ tắt vẫn áp sàn (η = 1); N ≤ 0 không dựng sàn.
    f = _wall("ell", kw, 800.0, 0.0, pd="none")
    assert abs(f["M_out_d"] - (-120.0)) < 0.11
    assert abs(f["dc"] - 0.23309) < 5e-5
    f = _wall("ell", kw, 800.0, 0.0, N=-2000.0)
    assert abs(f["M_out_d"] - 0.0) < 1e-9
    assert abs(f["dc"] - 1.30383) < 5e-5


def test_cu_wall_w_sign():
    # U: độ lớn ea app khớp web (sàn M_in 200 / M_out 100).
    ukw = dict(Lw=3000, sec_bf=1500, sec_t=300)
    f = _wall("u-core", ukw, 800.0, 0.0)
    assert abs(f["M_out_d"] - (-100.0)) < 0.11
    assert abs(f["dc"] - 0.09977) < 5e-5  # web 0.099
    f = _wall("u-core", ukw, 0.0, -800.0)
    assert abs(f["M_in_d"] - 200.0) < 0.11
    assert abs(f["dc"] - 0.14616) < 5e-5  # web 0.145
    # C: DẤU sàn đúng W (M_in +, M_out −) nhưng ĐỘ LỚN ea app
    # khác web (app: M_in 200 / M_out 100; web: 100 / 200) — khóa
    # hành vi app hiện tại, không ép theo web ở lát này.
    ckw = dict(Lw=3000, sec_bf=1500, sec_lr=600, sec_t=300)
    f = _wall("c-core", ckw, 800.0, 0.0)
    assert abs(f["M_out_d"] - (-100.0)) < 0.11
    f = _wall("c-core", ckw, 0.0, -800.0)
    assert abs(f["M_in_d"] - 200.0) < 0.11


_BASE = dict(concrete_grade="B25", gamma_b=0.85, steel_grade="CB400-V",
             cx=400.0, cy=400.0, cover=22.0, corner_dia=20.0,
             edge_t2_count=3, edge_t2_dia=20.0, edge_t3_count=3,
             edge_t3_dia=20.0, Lx=4.0, Ly=4.0, top_x="ngam_cung",
             bottom_x="ngam_cung", top_y="ngam_cung",
             bottom_y="ngam_cung", psi_x=0.5, psi_y=0.5)


def test_column_base_numbers_and_batch_parity():
    cases = [
        # (N, Mx, My, dc_mong_doi)
        (1500.0, 80.0, 60.0, 0.61406),   # ca thường: không đổi
        (1500.0, 0.0, 60.0, 0.52448),    # 1 phương 0: +1,84%
        (1500.0, 80.0, 0.0, 0.56608),    # 1 phương 0: +1,69%
        (1500.0, 0.0, 0.0, 0.45028),     # nén thuần: +12,01%
    ]
    for N, Mx, My, dc_exp in cases:
        inp = ColumnInput(**_BASE, N=N, Mx=Mx, My=My)
        r = check_column(inp)
        assert abs(r.dc - dc_exp) < 5e-5, (N, Mx, My, r.dc, dc_exp)
        bc = BatchChecker(ColumnInput(**_BASE, N=N, Mx=Mx, My=My))
        b = bc.check_one(N, Mx, My)
        assert abs(b["Mx_star"] - r.Mx_star) < 1e-9
        assert abs(b["My_star"] - r.My_star) < 1e-9
        assert abs(b["dc"] - r.dc) < 1e-4
