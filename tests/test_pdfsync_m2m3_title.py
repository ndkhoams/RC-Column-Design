"""Đồng bộ PDF theo GUI cho tiêu đề/caption M2–M3 — quyết user 2026-10-25.

GUI ở head 19b36c6 đã bỏ hậu tố "(tại N = … kN)" khỏi tiêu đề axes
M2–M3 và giữ chip N xanh ở header (chip là widget GUI, PDF không có
chip). Đợt này đồng bộ nốt các chỗ PDF còn sót:

- Tiêu đề axes trong ảnh PDF cột TCVN: rc_column/pdf_export.py::
  m2m3_image (bản sao độc lập, không dùng hàm vẽ chung đã sửa).
- Caption chữ "Mặt cắt M2-M3 (N = …)" / "(NEd = …)" trong PDF tóm
  tắt cột TCVN/ACI/EC2 và vách, và caption "(tại N = …)" trong PDF
  chi tiết vách (wall_pdf_report).
- NGOẠI LỆ sau quyết user 2026-10-25 08:06: caption PDF TÓM TẮT
  VÁCH có lại "(N = BN kN)" (khôi phục đúng format trước 39dc9a0);
  caption cột và PDF chi tiết vách vẫn không hậu tố N.
- KHÔNG đổi: bao M2–M3 vẫn vẽ tại N = BN (chứng minh bằng D/C
  không đổi + điểm B trên bao ở test_col_m2m3_bn), các câu giải
  thích trong thân thuyết minh ("lát cắt tại N = BN", ghi chú A/B,
  bảng thông số) vẫn giữ N/BN như cũ — chỉ bỏ hiển thị N ở tiêu
  đề axes và caption của hình M2–M3.
"""

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from rc_column.checker import ColumnInput, build_section, check_column
from rc_column.aci_checker import check_column_aci
from rc_column.ec2_checker import check_column_ec2
from rc_column.aci_materials import ACIConcrete, ACISteel
from rc_column.ec2_materials import EC2Concrete, EC2Steel
from rc_column.pdf_export import export_summary_pdf, m2m3_image
from rc_column.aci_pdf_summary import export_aci_summary_pdf
from rc_column.ec2_pdf_summary import export_ec2_summary_pdf
from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_input import WallInput
from rc_column.wall_pdf_summary import export_wall_summary_pdf
from rc_column.wall_pdf_report import export_wall_pdf_cards

_BASE = dict(concrete_grade="B25", gamma_b=0.85, steel_grade="CB400-V",
             cx=400.0, cy=400.0, cover=22.0, corner_dia=20.0,
             edge_t2_count=3, edge_t2_dia=20.0,
             edge_t3_count=3, edge_t3_dia=20.0, Lx=4.0, Ly=4.0,
             top_x="ngam_cung", bottom_x="ngam_cung",
             top_y="ngam_cung", bottom_y="ngam_cung",
             psi_x=0.5, psi_y=0.5)


def _pdf_text(path):
    try:
        from pypdf import PdfReader
    except Exception:
        from PyPDF2 import PdfReader
    r = PdfReader(path)
    return len(r.pages), "\n".join((p.extract_text() or "")
                                   for p in r.pages)


def _col_fixtures():
    inp = ColumnInput(**_BASE, N=1500.0, Mx=80.0, My=60.0)
    sec = build_section(inp)
    res = check_column(inp, n_angles=24)
    conc, steel = ACIConcrete(fc=30.0), ACISteel(fy=420.0)
    ares = check_column_aci(sec, conc, steel, 1500.0, 80.0, 60.0,
                            tied=True)
    conc2, steel2 = EC2Concrete(fck=20.0), EC2Steel(fyk=500.0)
    eres = check_column_ec2(sec, conc2, steel2, 1500.0, 80.0, 60.0)
    return inp, sec, res, (conc, steel, ares), (conc2, steel2, eres)


def _wall_full():
    conc = ConcreteMaterial(CONCRETE_GRADES["B25"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB400-V"], 1.0)
    winp = WallInput(
        Lw=2500.0, tw=350.0, cover=13.0, dia_h=12.0, s_h=200.0,
        layers_h=2, sw_steel_grade="CB400-V", steel_mode="boundary",
        be_Lb=500.0, be_dia=28.0, be_n_Lb=4, be_n_tw=0, be_L_out=1,
        be_L_in=0, web_dia=12.0, web_s=200.0, Lx_m=3.3, Ly_m=3.3,
        psi_x=1.0, psi_y=1.0, seismic_on=True)
    return wall_tcvn_full(
        winp, conc, steel,
        loads={"N": 2500.0, "M_in": 3000.0, "M_out": 60.0,
               "V_in": 800.0, "V_out": 0.0, "T": 0.0},
        seismic_shear=True)


def test_tcvn_m2m3_image_axes_title_has_no_n_suffix(tmp_path):
    """Ảnh M2–M3 PDF cột TCVN: tiêu đề axes KHÔNG còn (quyết mới
    2026-10-25: xóa nốt "M2–M3", chỉ giữ header ngoài + chip N ở GUI)."""
    inp, sec, res, _a, _e = _col_fixtures()
    assert abs(res.dc - 0.6140612962169418) < 1e-12, res.dc
    captured = []
    orig = plt.subplots

    def _wrap(*args, **kwargs):
        fig, ax = orig(*args, **kwargs)
        captured.append(ax)
        return fig, ax

    plt.subplots = _wrap
    try:
        png = m2m3_image(sec, inp, res)
    finally:
        plt.subplots = orig
    plt.close("all")
    assert len(png) > 10000, "ảnh M2–M3 quá nhỏ"
    assert captured, "không bắt được axes của m2m3_image"
    assert captured[-1].get_title() == "", captured[-1].get_title()


def test_summary_captions_have_no_n(tmp_path):
    """Caption M2–M3 trong PDF tóm tắt cột 3 chuẩn: không còn N;
    PDF tóm tắt vách (ngoại lệ 08:06): có lại "(N = BN kN)"."""
    inp, sec, res, (conc, steel, ares), (conc2, steel2, eres) = \
        _col_fixtures()
    p = str(tmp_path / "tcvn.pdf")
    export_summary_pdf(sec, inp, res, p)
    pages, txt = _pdf_text(p)
    assert pages == 1
    assert "Mặt cắt M2-M3" in txt
    assert "Mặt cắt M2-M3 (N" not in txt
    assert "Mặt cắt M2-M3 (tại N" not in txt

    p = str(tmp_path / "aci.pdf")
    export_aci_summary_pdf(sec, inp, ares, conc, steel, True, p)
    pages, txt = _pdf_text(p)
    assert pages == 1
    assert "Mặt cắt M2-M3" in txt
    assert "Mặt cắt M2-M3 (N" not in txt

    p = str(tmp_path / "ec2.pdf")
    export_ec2_summary_pdf(sec, inp, eres, conc2, steel2, p)
    pages, txt = _pdf_text(p)
    assert pages == 1
    assert "Mặt cắt M2-M3" in txt
    assert "Mặt cắt M2-M3 (N" not in txt
    assert "(NEd" not in txt

    full = _wall_full()
    assert abs(full["dc"] - 0.463113767258396) < 1e-9, full["dc"]
    buf = io.BytesIO()
    export_wall_summary_pdf(full, buf, member_name="COTBTCT",
                            show_compression=True)
    buf.seek(0)
    try:
        from pypdf import PdfReader
    except Exception:
        from PyPDF2 import PdfReader
    r = PdfReader(buf)
    wtxt = "\n".join((pg.extract_text() or "") for pg in r.pages)
    assert len(r.pages) == 1
    assert "Mặt cắt M2" in wtxt
    # Ngoại lệ 08:06 (chỉ PDF tóm tắt vách): caption có lại N = BN,
    # đúng format cũ "(N = <BN:,.0f> kN)"; không phải "(tại N …)".
    _n_level = float(full["m2m3"]["N_level"])
    assert f"(N = {_n_level:,.0f} kN)" in wtxt
    assert "Mặt cắt M2–M3 (tại N" not in wtxt


def test_wall_detail_caption_has_no_n(tmp_path):
    """Caption M2–M3 trong PDF chi tiết vách: không còn "(tại N …)"."""
    full = _wall_full()
    p = str(tmp_path / "wall_detail.pdf")
    export_wall_pdf_cards(full, p, member_name="COTBTCT")
    _pages, txt = _pdf_text(p)
    assert "Mặt cắt M2–M3" in txt
    assert "Mặt cắt M2–M3 (tại N" not in txt
    # Câu giải thích trong thân thẻ vẫn giữ mức BN — chỉ caption bỏ N.
    assert "lát cắt tại" in txt and "BN" in txt
