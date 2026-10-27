"""Cổng λ > 14 cho hệ số uốn dọc η TCVN (TCVN 5574:2018 §8.1.2.1.2).

Phương án A (user chốt 2026-10-24): η mỗi phương chỉ được nhân khi
λ của phương đó > 14 (nghiêm ngặt ">"; λ = 14 đúng bằng → η = 1.0);
λ ≤ 14 → η = 1.0, M* = M cho phương đó. Cổng nằm trong hàm dùng
chung stability.buckling_factors nên cột và vách chịu cùng một luật;
Ncr/D/kb/δe không bị cổng (Ncr vẫn hiển thị đầy đủ).
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rc_column.checker import BatchChecker, ColumnInput, check_column
from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.stability import buckling_factors, slenderness
from rc_column.cover_migration import migrate_wall_dict
from rc_column.wall_detail import build_wall_detail_sections
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_input import WallInput, wall_from_dict

_CONC = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
_STEEL = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
_LOADS = {"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
          "V_in": 800.0, "V_out": 0.0, "T": 0.0}
_OLD = {"Lw": 2500, "tw": 350, "h_story": 3300, "h_total": 19800,
        "story_pos": "base", "cover": 25, "l0_out_factor": 1.0,
        "dia_v": 12, "s_v": 200, "layers_v": 2, "dia_h": 12, "s_h": 200,
        "layers_h": 2, "Lb_left": 500, "Lb_right": 500,
        "lb_auto": False, "dia_be": 28, "n_be": 8, "tie_dia_be": 10,
        "tie_s_be": 100, "tie_legs_be": 2, "seismic_class": "special",
        "seismic_on": True, "N": 0, "M_in": 0, "M_out": 0,
        "V_in": 0, "V_out": 0, "T": 0}

_I400 = 400.0 / math.sqrt(12.0)  # mm, tiết diện chữ nhật 400x400


def _buck(lam_x, lam_y, N=1000.0, Mx=80.0, My=60.0, explicit=True):
    """buckling_factors trên tiết diện 400x400, Is = 0 (η thuần Ncr).
    explicit=True: truyền λ tường minh; False: suy λ từ L0 (fallback)."""
    Ix = 400.0 * 400.0 ** 3 / 12.0
    L0x = lam_x * _I400 / 1000.0
    L0y = lam_y * _I400 / 1000.0
    kw = {"lambda_x": lam_x, "lambda_y": lam_y} if explicit else {}
    return buckling_factors(50.0, 50.0, 400.0, 400.0, 2.0, 25000.0,
                            Ix, Ix, 0.0, 0.0, L0x, L0y, N, Mx, My, **kw)


def _raw_eta(N, Ncr):
    return 1.0 / (1.0 - abs(N) / Ncr) if Ncr > abs(N) else 10.0


def test_gate_below_above_and_exactly_14():
    for lam, gated in ((6.37, True), (13.99, True), (14.0, True),
                       (14.01, False), (45.53, False)):
        for explicit in (True, False):
            b = _buck(lam, lam, explicit=explicit)
            assert abs(slenderness(lam * _I400 / 1000.0, 400.0)
                       - lam) < 1e-9
            if gated:
                assert b.etax == 1.0 and b.etay == 1.0, (lam, explicit)
                assert b.Mx_star == 80.0 and b.My_star == 60.0
            else:
                assert abs(b.etax - _raw_eta(1000.0, b.Ncrx)) < 1e-12
                assert abs(b.etay - _raw_eta(1000.0, b.Ncry)) < 1e-12
            # Ncr KHÔNG bị cổng: bằng đúng công thức (45) cả 2 trường hợp.
            assert b.Ncrx > 0 and b.Ncry > 0


def test_gate_independent_per_direction():
    b = _buck(6.37, 45.53)
    assert b.etax == 1.0 and b.Mx_star == 80.0
    assert abs(b.etay - _raw_eta(1000.0, b.Ncry)) < 1e-12
    assert b.My_star == b.etay * 60.0
    b2 = _buck(45.53, 6.37)
    assert b2.etay == 1.0 and b2.My_star == 60.0
    assert abs(b2.etax - _raw_eta(1000.0, b2.Ncrx)) < 1e-12


def test_gate_negative_N_keeps_gate():
    # N ≤ 0: không có hành vi riêng mới — cổng λ vẫn áp như N > 0
    # (công thức gốc vốn dùng |N|); chỉ λ quyết định η.
    b = _buck(6.37, 6.37, N=-1000.0)
    assert b.etax == 1.0 and b.etay == 1.0
    b2 = _buck(45.53, 45.53, N=-1000.0)
    assert abs(b2.etax - _raw_eta(-1000.0, b2.Ncrx)) < 1e-12


def _col_600_low():
    return ColumnInput(concrete_grade="B25", gamma_b=0.85,
                       steel_grade="CB400-V", cx=600.0, cy=600.0,
                       cover=22.0,  # MIGRATION COVER: fixture cũ 30 (nghĩa mặt thép) - sw_dia 8 = 22 (c_đai); fiber giữ nguyên
                       corner_dia=20.0,
                       edge_t2_count=3, edge_t2_dia=20.0,
                       edge_t3_count=3, edge_t3_dia=20.0,
                       Lx=4.0, Ly=4.0, top_x="ngam_cung",
                       bottom_x="ngam_cung", top_y="ngam_cung",
                       bottom_y="ngam_cung", psi_x=0.5, psi_y=0.5,
                       N=1500.0, Mx=80.0, My=60.0)


def test_gate_column_low_lambda_eta_one_and_m_star_equals_m():
    res = check_column(_col_600_low(), n_angles=24)
    assert abs(res.lambda_x - 11.547) < 0.01
    assert abs(res.lambda_y - 11.547) < 0.01
    assert res.etax == 1.0 and res.etay == 1.0
    assert res.Mx_star == 80.0 and res.My_star == 60.0
    # §3 in "không cần xét" (ngưỡng > 14) khớp đúng cổng mới; §5 in
    # η = 1.000 và M* = M.
    from rc_column.report import generate_report_sections
    secs = generate_report_sections(_col_600_low(), res)
    txt = str(secs)
    assert "không cần xét" in txt
    assert "1.000 / 1.000" in txt
    assert "80.0" in txt and "60.0" in txt


def test_gate_column_high_lambda_unchanged_and_batch_parity():
    # GUI mặc định: λ = 17.32 > 14 cả 2 phương → η giữ công thức (44),
    # D/C giữ mốc PA-A 0.61406.
    inp = ColumnInput(concrete_grade="B25", gamma_b=0.85,
                      steel_grade="CB400-V", cx=400.0, cy=400.0,
                      cover=22.0,  # MIGRATION COVER: fixture cũ 30 (nghĩa mặt thép) - sw_dia 8 = 22 (c_đai); fiber giữ nguyên
                       corner_dia=20.0,
                      edge_t2_count=3, edge_t2_dia=20.0,
                      edge_t3_count=3, edge_t3_dia=20.0,
                      Lx=4.0, Ly=4.0, top_x="ngam_cung",
                      bottom_x="ngam_cung", top_y="ngam_cung",
                      bottom_y="ngam_cung", psi_x=0.5, psi_y=0.5,
                      N=1500.0, Mx=80.0, My=60.0)
    res = check_column(inp, n_angles=24)
    assert abs(res.etax - _raw_eta(1500.0, res.Ncrx)) < 1e-12
    assert abs(res.dc - 0.6140612962169418) < 1e-12
    # BatchChecker (đường batch ETABS) chịu cùng cổng + parity scalar.
    bc = BatchChecker(_col_600_low(), n_angles=12)
    one = bc.check_one(1500.0, 80.0, 60.0)
    assert one["etax"] == 1.0 and one["etay"] == 1.0
    assert one["Mx_star"] == 80.0 and one["My_star"] == 60.0
    many = bc.check_many([(1500.0, 80.0, 60.0, None),
                          (1000.0, 50.0, 40.0, None)])
    assert many[0]["dc"] == one["dc"] and many[0]["etax"] == 1.0


def test_gate_wall_sample_in_plane_gated_out_kept():
    full = wall_tcvn_full(WallInput(cover=13.0), _CONC, _STEEL, loads=dict(_LOADS))  # MIGRATION COVER: 25-12
    sl = full["slend"]
    assert abs(sl["lambda_in"] - 6.37) < 0.01
    assert abs(sl["lambda_out"] - 45.53) < 0.01
    assert sl["factor_in"] == 1.0
    assert abs(full["M_in_d"] - 210.72) < 0.01
    assert abs(sl["factor_out"] - 1.1375729051035446) < 1e-9
    assert abs(full["M_out_d"] - 313.09) < 0.01
    # Ncr không bị cổng.
    assert abs(sl["Ncr_in"] - 1291523.27) < 1.0
    assert abs(sl["Ncr_out"] - 20909.09) < 1.0
    assert abs(full["dc"] - 0.44520) <= 1e-5


def test_gate_wall_rot90_and_old_and_pd_none():
    fr = wall_tcvn_full(WallInput(rot_deg=90, cover=13.0), _CONC, _STEEL,  # MIGRATION COVER: 25-12
                        loads={"N": 2528.65, "M_in": 275.23,
                               "M_out": 202.86, "V_in": 0.0,
                               "V_out": 0.0, "T": 0.0})
    assert fr["slend"]["factor_out"] == 1.0
    # Sàn ea (2026-10-27): cổng η vẫn giữ (factor_out = 1,0) nhưng
    # M_out* không còn bằng M_out khi e1 < ea — ở rot90, ea ngoài
    # MP = 83,33 mm (bề dày sau xoay) > e1 = 80,2 mm nên sàn nâng
    # M_out* lên N·e0·η = 210,72, giữ dấu M_out gốc (dấu sàn chỉ
    # áp khi M gốc = 0).
    assert abs(fr["M_out_d"] - 210.72) < 0.01
    assert abs(fr["slend"]["factor_in"] - 1.1375729051035446) < 1e-9
    assert abs(fr["dc"] - 0.44583) <= 1e-4
    fo = wall_tcvn_full(wall_from_dict(migrate_wall_dict(_OLD)[0]), _CONC, _STEEL,  # MIGRATION COVER qua helper
                        loads={"N": 2500.0, "M_in": 3000.0,
                               "M_out": 60.0, "V_in": 0.0,
                               "V_out": 0.0, "T": 0.0})
    assert fo["slend"]["factor_in"] == 1.0
    assert fo["M_in_d"] == 3000.0
    assert abs(fo["dc"] - 0.40226) <= 1e-5
    # P–δ tắt: η đã = 1 từ trước, cổng không đổi gì.
    fn = wall_tcvn_full(WallInput(pd_method="none", cover=13.0), _CONC, _STEEL,  # MIGRATION COVER: 25-12
                        loads=dict(_LOADS))
    assert fn["slend"]["factor_in"] == 1.0
    assert fn["slend"]["factor_out"] == 1.0
    assert fn["M_out_d"] == 275.23
    assert abs(fn["dc"] - 0.40054401998055345) < 1e-9


def test_gate_wall_detail_card_gated_direction():
    secs = build_wall_detail_sections(
        wall_tcvn_full(WallInput(cover=13.0), _CONC, _STEEL, loads=dict(_LOADS)))  # MIGRATION COVER: 25-12
    sec5 = [s for s in secs if s["num"] == 5][0]
    cards = {c["title"]: c for c in sec5["cards"]}
    x = cards["η & mô men phóng đại — Phương X (trong MP)"]
    y = cards["η & mô men phóng đại — Phương Y (ngoài MP)"]
    assert "210.72" in x["result"] and "1,000" in x["result"]
    body_x = "\n".join(x["lines"])
    assert "8.1.2.1.2" in body_x and "≤ 14" in body_x
    assert "Đối chiếu" not in body_x and "1.002" not in body_x
    assert "+0.20%" not in body_x
    assert "313.09" in y["result"] and "45.53" in "\n".join(y["lines"])
