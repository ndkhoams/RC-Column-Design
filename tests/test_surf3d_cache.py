"""Cache mặt 3D (gui/surf3d_cache.py) — khóa hành vi tối ưu 2026-10-30.

- Lần 2 cùng fingerprint: KHÔNG gọi lại builder (không dựng cap,
  không gọi moment_capacity) — spy đếm calls.
- Đổi input (cover/thép) → fingerprint đổi → tính lại (builder gọi
  lại), lưới mới đúng số (khớp tính tươi từng chữ số).
- Đường cong N-Ma cache theo (mặt, góc tải).
- LRU: tối đa 8 entry.
- D/C solver không đổi (khóa số benchmark).
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import matplotlib

matplotlib.use("Agg")

from rc_column.checker import ColumnInput, build_section, check_column
from rc_column.interaction import BiaxialCapacity
from gui import surf3d_cache as SC

_BASE = dict(concrete_grade="B30", gamma_b=0.85, steel_grade="CB500-V",
             cx=400.0, cy=400.0, cover=22.0,
             corner_dia=25.0,
             edge_t2_count=2, edge_t2_dia=20.0,
             edge_t3_count=2, edge_t3_dia=20.0,
             Lx=4.0, Ly=4.0, top_x="ngam_cung", bottom_x="ngam_cung",
             top_y="ngam_cung", bottom_y="ngam_cung",
             psi_x=0.5, psi_y=0.5, N=1500.0, Mx=120.0, My=80.0)


@pytest.fixture(autouse=True)
def _clean():
    SC.clear_cache()
    yield
    SC.clear_cache()


def _case(**kw):
    d = dict(_BASE)
    d.update(kw)
    inp = ColumnInput(**d)
    return inp, build_section(inp)


def _surf_builder(sec, model, calls):
    def _b():
        calls.append(1)
        cap = BiaxialCapacity(sec, model=model, n_angles=24)
        return cap.surface_grid(n_n=SC.SURF3D_N_N,
                                n_angles=SC.SURF3D_N_ANGLES)
    return _b


# ------------------------------------------------------------------
def test_surface_cache_hit_no_rebuild():
    """Lần 2 cùng fp: builder không gọi lại; lưới trả về đúng số."""
    inp, sec = _case()
    fp = SC.surface_fp("tcvn", sec, model=inp.concrete_model)
    calls = []
    g1 = SC.get_surface(fp, _surf_builder(sec, inp.concrete_model, calls))
    g2 = SC.get_surface(fp, _surf_builder(sec, inp.concrete_model, calls))
    assert calls == [1], "cache hit mà vẫn gọi builder!"
    assert SC.cache_stats()[:2] == (1, 1)
    for a, b in zip(g1, g2):
        assert (a == b).all()
    # đúng số tính tươi từng chữ số
    cap = BiaxialCapacity(sec, model=inp.concrete_model, n_angles=24)
    fresh = cap.surface_grid(n_n=SC.SURF3D_N_N,
                             n_angles=SC.SURF3D_N_ANGLES)
    for a, b in zip(g1, fresh):
        assert (a == b).all()


def test_fingerprint_changes_on_input_change():
    """Đổi cover → fp đổi → miss → tính lại; đổi lại như cũ → hit."""
    inp1, sec1 = _case()
    inp2, sec2 = _case(cover=30.0)
    fp1 = SC.surface_fp("tcvn", sec1, model=inp1.concrete_model)
    fp2 = SC.surface_fp("tcvn", sec2, model=inp2.concrete_model)
    assert fp1 != fp2
    calls = []
    SC.get_surface(fp1, _surf_builder(sec1, inp1.concrete_model, calls))
    SC.get_surface(fp2, _surf_builder(sec2, inp2.concrete_model, calls))
    assert len(calls) == 2
    # quay lại tiết diện cũ → hit, không tính lại
    SC.get_surface(fp1, _surf_builder(sec1, inp1.concrete_model, calls))
    assert len(calls) == 2
    # lưới của 2 tiết diện phải khác nhau thật
    g1 = SC.get_surface(fp1, _surf_builder(sec1, inp1.concrete_model, calls))
    g2 = SC.get_surface(fp2, _surf_builder(sec2, inp2.concrete_model, calls))
    assert not (g1[2] == g2[2]).all()


def test_fingerprint_changes_on_steel_change():
    inp1, sec1 = _case()
    inp2, sec2 = _case(corner_dia=28.0)
    fp1 = SC.surface_fp("tcvn", sec1, model=inp1.concrete_model)
    fp2 = SC.surface_fp("tcvn", sec2, model=inp2.concrete_model)
    assert fp1 != fp2


def test_std_tags_do_not_collide():
    inp, sec = _case()
    assert (SC.surface_fp("tcvn", sec, model=inp.concrete_model)
            != SC.surface_fp("wall", sec, model=inp.concrete_model))
    assert (SC.surface_fp("aci", sec, tied=True)
            != SC.surface_fp("aci", sec, tied=False))


def test_curve_cache_hit_and_theta_miss():
    """Đường cong cache theo (mặt, θ): cùng θ hit; khác θ miss."""
    inp, sec = _case()
    fp = SC.surface_fp("tcvn", sec, model=inp.concrete_model)
    calls = []
    n_vals = SC.get_surface(
        fp, _surf_builder(sec, inp.concrete_model, calls))[0]

    def _cb():
        calls.append(1)
        return SC.alpha_curve_3d(
            lambda: BiaxialCapacity(sec, model=inp.concrete_model,
                                    n_angles=24), n_vals, 56.3)

    c1 = SC.get_curve(SC.curve_fp(fp, 56.3), _cb)
    c2 = SC.get_curve(SC.curve_fp(fp, 56.3), _cb)
    assert len(calls) == 2, "curve hit mà vẫn gọi builder!"  # 1 surf + 1 curve
    for a, b in zip(c1, c2):
        assert (a == b).all()
    # góc khác → miss
    SC.get_curve(SC.curve_fp(fp, 57.3), _cb)
    assert len(calls) == 3


def test_lru_bound():
    inp, sec = _case()
    for k in range(10):
        fp = SC.surface_fp("tcvn", sec, model=inp.concrete_model) + f"#{k}"
        SC.get_surface(fp, _surf_builder(sec, inp.concrete_model, []))
    assert SC.cache_stats()[2] == 8


def test_dc_unchanged_by_optimization():
    """Tối ưu chỉ chạm đường vẽ 3D — D/C solver phải giữ nguyên."""
    inp = ColumnInput(**_BASE)
    res = check_column(inp)
    assert round(res.dc, 5) == 0.67767
