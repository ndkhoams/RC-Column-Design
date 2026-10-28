"""Import tiết diện vách bất kỳ từ .DXF + so sánh với tiết diện có sẵn
(lát DXF, 2026-10-28).

Quy ước import (CHUNG với cột, rc_column/dxf_import.read_dxf_section
— không sửa file đó): biên bê tông = LWPOLYLINE kín layer BT, lỗ =
layer BT_HOLE, thép = CIRCLE layer THEP; đơn vị theo $INSUNITS
(4=mm, 5=cm, 6=m, 0 -> mm kèm cảnh báo); tọa độ GỐC BẢN VẼ lưu
trong JSON (dxf_poly/dxf_holes/dxf_bars/dxf_file), build trừ trọng
tâm outline mỗi lần dựng (như cột). Vách chỉ nhận đúng 1 biên BT
(nhiều biên -> ValueError, không tự gộp — single_dxf_outline).

So sánh import vs có sẵn (cùng tải/vật liệu: B30 γb=0.85/CB500-V,
thép ngang CB400-V, Lx=Ly=5.75, ψ=0.8, ngàm nửa cứng, DCM tắt):
(a) phẳng 2500x350, thép chu vi _gen_perimeter(..., cover=13,
    dia_h=12, d=12, s=200) -> 30 thanh: N–M và cắt trong MP khớp
    1e-3; D/C N–M lệch 0,40% còn lại ĐÃ ĐIỀU TRA — không phải lỗi
    DXF mà do lưới fiber khác nhau: rect dùng mesh_counts (ny luôn
    = 40, dy = 8,75 mm) trong khi DXF theo bước 25 mm (ny = 14,
    dy = 25 mm) như nhánh đa giác; chứng minh bằng lưới DXF mịn
    ny=40 thì D/C khớp rect trong 1e-3 (xem test_dxf_vs_flat).
    Cắt NGOÀI MP của DXF phẳng KHÔNG khớp phẳng có sẵn — cũng là
    khác biệt ÁNH XẠ theo thiết kế, không phải lỗi: DXF là đa giác
    nên theo ánh xạ đa giác (b = thân mỏng nhất t_branch = 350 mm,
    h0 = 319 mm) trong khi phẳng có sẵn dùng b = Lw = 2500 mm,
    h0 = 331 mm (xem test_dxf_vs_flat, Vcap 98,9 vs 584,7 kN).
    Muốn DXF hình chữ nhật khớp cả ngoài MP thì cần thêm trường
    hợp riêng "hình chữ nhật" cho cắt DXF — đó là đổi thiết kế
    (item 4), KHÔNG tự làm ở lát này.
(b) chữ L: polygon + thép đúng _build_wall_section_poly của L
    (chu vi + ô nút giao, dịch về tọa độ gốc): D/C N–M và cắt
    trong/ngoài MP khớp 1e-3 (lưới fiber và hình học cắt trùng
    nhau thật ở đây vì cả 2 đều qua nhánh đa giác).
(c) tiết diện bất kỳ không trùng loại có sẵn (Γ 6 cạnh trực giao,
    thép đặt tay trong biên): CHECK chạy được, D/C hữu hạn, xoay
    90° kèm hoán đổi M_in<->M_out theo quy ước xoay của
    test_wallnm_poly (trục x: M_in' = -M_in, M_out' = M_out) cho
    D/C không đổi trong 1e-4.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from rc_column.dxf_import import (point_in_polygon, polygon_centroid,
                                  read_dxf_section)
from rc_column.interaction import BiaxialCapacity
from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_detail import build_wall_detail_sections
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_input import (WallInput, wall_from_dict,
                                  wall_to_dict)
from rc_column.wall_section import (_gen_perimeter, _poly_ell,
                                    _polygon_centroid,
                                    build_wall_section,
                                    single_dxf_outline)
from rc_column.wall_shear import (count_reflex_vertices,
                                  wall_shear_geometry_poly)
from gui.wall_mixin import build_wall_shear_rows, draw_wall_section_ax

_CONC = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
_STEEL = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
_SW = SteelMaterial(STEEL_GRADES["CB400-V"], 1.0)


def _rel(a, b):
    return abs(a - b) / max(1e-12, abs(b))


def _base(**kw):
    """WallInput dùng chung cho so sánh: thép ngang CB400-V,
    Lx=Ly=5.75, ψ=0.8, ngàm nửa cứng (mặc định WallInput đã là
    ngam_nua_cung 2 đầu 2 phương)."""
    w = WallInput(cover=28, dia_h=12, s_h=200, layers_h=2,
                  sw_steel_grade="CB400-V",
                  Lx_m=5.75, Ly_m=5.75, psi_x=0.8, psi_y=0.8)
    for k, v in kw.items():
        setattr(w, k, v)
    return w


def _loads(N, Mi, Mo, Vi=0.0, Vo=0.0):
    return {"N": N, "M_in": Mi, "M_out": Mo,
            "V_in": Vi, "V_out": Vo, "T": 0.0}


def _write_dxf(path, outlines, holes=(), bars=(), insunits=4):
    """Ghi fixture DXF bằng ezdxf (không cần file user)."""
    import ezdxf
    doc = ezdxf.new("R2010")
    try:
        doc.header["$INSUNITS"] = insunits
    except Exception:
        pass
    msp = doc.modelspace()
    for lname in ("BT", "BT_HOLE", "THEP"):
        if lname not in doc.layers:
            try:
                doc.layers.add(lname)
            except Exception:
                pass
    for verts in outlines:
        msp.add_lwpolyline(list(verts), close=True,
                           dxfattribs={"layer": "BT"})
    for verts in holes:
        msp.add_lwpolyline(list(verts), close=True,
                           dxfattribs={"layer": "BT_HOLE"})
    for x, y, d in bars:
        msp.add_circle((x, y), d / 2.0, dxfattribs={"layer": "THEP"})
    doc.saveas(path)


# ---------------- Parser DXF (qua read_dxf_section chung với cột) ----------------

def test_dxf_parser_units_and_errors(tmp_path):
    poly = [(0, 0), (2500, 0), (2500, 350), (0, 350)]
    bars = [(200, 175, 12), (2300, 175, 12)]
    p = str(tmp_path / "flat_mm.dxf")
    _write_dxf(p, [poly], bars=bars, insunits=4)
    dxf = read_dxf_section(p)
    assert len(dxf.outlines) == 1
    assert dxf.outlines[0] == [(float(x), float(y)) for x, y in poly]
    assert len(dxf.rebars) == 2
    assert not any("Không rõ đơn vị" in w for w in dxf.warnings)
    # cm (5): tọa độ /10, đọc lại ra mm như cũ.
    p_cm = str(tmp_path / "flat_cm.dxf")
    _write_dxf(p_cm, [[(x / 10.0, y / 10.0) for x, y in poly]],
               bars=[(x / 10.0, y / 10.0, d / 10.0) for x, y, d in bars],
               insunits=5)
    dxf_cm = read_dxf_section(p_cm)
    assert dxf_cm.outlines[0] == dxf.outlines[0]
    assert dxf_cm.rebars == dxf.rebars
    # m (6): tọa độ /1000.
    p_m = str(tmp_path / "flat_m.dxf")
    _write_dxf(p_m, [[(x / 1000.0, y / 1000.0) for x, y in poly]],
               bars=[(x / 1000.0, y / 1000.0, d / 1000.0)
                     for x, y, d in bars],
               insunits=6)
    dxf_m = read_dxf_section(p_m)
    assert dxf_m.outlines[0] == dxf.outlines[0]
    assert dxf_m.rebars == dxf.rebars
    # $INSUNITS=0 -> mm kèm cảnh báo.
    p0 = str(tmp_path / "flat_0.dxf")
    _write_dxf(p0, [poly], bars=bars, insunits=0)
    assert any("Không rõ đơn vị" in w
               for w in read_dxf_section(p0).warnings)
    # Không có BT -> lỗi rõ ràng.
    p_nb = str(tmp_path / "nobeton.dxf")
    _write_dxf(p_nb, [], bars=bars, insunits=4)
    try:
        read_dxf_section(p_nb)
        raise AssertionError("phải lỗi khi không có biên BT")
    except ValueError as ex:
        assert "BT" in str(ex)
    # Polyline hở > 1 đơn vị -> lỗi (không tự đóng mù).
    import ezdxf
    p_open = str(tmp_path / "open.dxf")
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (2500, 0), (2500, 350)],
                       close=False, dxfattribs={"layer": "BT"})
    doc.saveas(p_open)
    try:
        read_dxf_section(p_open)
        raise AssertionError("phải lỗi khi polyline không kín")
    except ValueError as ex:
        assert "không khép kín" in str(ex)
    # Tự cắt (bowtie) -> lỗi.
    p_self = str(tmp_path / "self.dxf")
    _write_dxf(p_self, [[(0, 0), (1000, 1000), (1000, 0), (0, 1000)]],
               insunits=4)
    try:
        read_dxf_section(p_self)
        raise AssertionError("phải lỗi khi polyline tự cắt")
    except ValueError as ex:
        assert "tự cắt" in str(ex)
    # Nhiều biên -> single_dxf_outline lỗi, không tự gộp.
    try:
        single_dxf_outline([poly, [(0, 0), (100, 0), (100, 100)]])
        raise AssertionError("phải lỗi khi nhiều biên BT")
    except ValueError as ex:
        assert "đúng 1 biên" in str(ex)
    assert single_dxf_outline([poly]) == [list(p) for p in poly]


# ---------------- (a) DXF phẳng vs phẳng có sẵn ----------------

def _flat_bars():
    bars, _runs, _extra = _gen_perimeter(2500, 350, 13, 12, 200,
                                         dia_h=12)
    assert len(bars) == 30
    return bars


def _flat_dxf_data():
    bars = _flat_bars()
    poly = [[0, 0], [2500, 0], [2500, 350], [0, 350]]
    dxf_bars = [[x + 1250.0, y + 175.0, d] for x, y, d in bars]
    return poly, dxf_bars


def test_dxf_flat_section_build():
    poly, dxf_bars = _flat_dxf_data()
    w = _base(section_type="dxf", cover=13, dxf_poly=poly,
              dxf_bars=dxf_bars, dxf_file="flat.dxf")
    sec, meta = build_wall_section(w, _CONC, _STEEL)
    assert sec.kind == "poly"
    assert sec.cx == 2500.0 and sec.cy == 350.0
    assert abs(sec.gross_area - 875000.0) < 1e-6
    assert len(sec.rebars) == 30
    got = sorted((round(r.x, 6), round(r.y, 6), r.dia)
                 for r in sec.rebars)
    exp = sorted((round(x, 6), round(y, 6), d)
                 for x, y, d in _flat_bars())
    assert got == exp
    assert meta["layout_text"].startswith("Tiết diện DXF:")
    assert meta["dim_total_x_label"] == "Lw = 2500 mm"
    assert meta["dim_total_y_label"] == "tw = 350 mm"
    assert meta["bar_branch_t"] == 350.0
    assert meta["warnings"] == []
    assert meta["zones"] == [("DXF d12", 30, 12.0)]


def test_dxf_vs_flat():
    """(a) Xem docstring module: trong MP + N–M (sau khi trừ ảnh
    hưởng lưới) khớp 1e-3; ngoài MP lệch do ánh xạ — khóa số để
    lệch đó không trôi lặng lẽ."""
    poly, dxf_bars = _flat_dxf_data()
    loads = _loads(2000.0, 800.0, 200.0, 800.0, 300.0)
    w_flat = _base(section_type="rect", cover=13, dia_v=12, s_v=200,
                   per_dia=12, per_s=200, steel_mode="perimeter")
    w_dxf = _base(section_type="dxf", cover=13, dia_v=12, s_v=200,
                  per_dia=12, per_s=200, steel_mode="perimeter",
                  dxf_poly=poly, dxf_bars=dxf_bars,
                  dxf_file="flat.dxf")
    f_flat = wall_tcvn_full(w_flat, _CONC, _STEEL, loads=loads,
                            steel_sw=_SW, seismic_shear=False)
    f_dxf = wall_tcvn_full(w_dxf, _CONC, _STEEL, loads=loads,
                           steel_sw=_SW, seismic_shear=False)
    # Mô men thiết kế / η / λ trùng nhau từng chữ số (cùng Ix/Iy/
    # Is, cùng ea theo bbox) — lệch D/C chỉ còn do lưới fiber.
    assert abs(f_dxf["M_in_d"] - f_flat["M_in_d"]) < 1e-9
    assert abs(f_dxf["M_out_d"] - f_flat["M_out_d"]) < 1e-9
    assert f_dxf["wall_axis_in"] == "x" == f_flat["wall_axis_in"]
    assert "Tiết diện vách DXF" in f_dxf["details"][0]
    assert "trục trong MP đã chọn: x" in f_dxf["details"][0]
    # Cắt trong MP: hình học trùng nhau thật (b=350, h0=2469) -> 1e-3.
    assert _rel(f_dxf["shear_in"]["V_cap"],
                f_flat["shear_in"]["V_cap"]) <= 1e-3
    assert abs(f_dxf["shear_in"]["V_cap"] - 1895.29) < 1.0
    # D/C N–M: lệch 0,40% do lưới (rect ny=40, dy=8,75; DXF ny=14,
    # dy=25) — khóa trong 1% và chứng minh bằng lưới mịn dưới đây.
    assert _rel(f_dxf["dc"], f_flat["dc"]) <= 0.01, \
        (f_dxf["dc"], f_flat["dc"])
    sec_fine, _m = build_wall_section(w_dxf, _CONC, _STEEL)
    # Lưới DXF mịn theo y như rect (100x40, dx=25, dy=8,75):
    # cùng solver, cùng tải, cùng thép -> D/C phải khớp rect 1e-3.
    import copy
    from rc_column.sections import Fiber
    verts = sec_fine.poly_verts[0]
    xs = [p[0] for p in verts]
    ys = [p[1] for p in verts]
    fibers = []
    for i in range(100):
        for j in range(40):
            x = min(xs) + (i + 0.5) * 25.0
            y = min(ys) + (j + 0.5) * (350.0 / 40.0)
            if point_in_polygon(x, y, verts):
                fibers.append(Fiber(x, y, 25.0 * 350.0 / 40.0))
    fsum = sum(f.area for f in fibers)
    for f in fibers:
        f.area *= sec_fine.gross_area / fsum
    sec_fine = copy.copy(sec_fine)
    sec_fine.fibers = fibers
    cap = BiaxialCapacity(sec_fine, model="3line", n_angles=24)
    dc_fine = cap.dc_ratio(2000.0, f_flat["Mx_d"],
                           f_flat["My_d"])["dc"]
    assert _rel(dc_fine, f_flat["dc"]) <= 1e-3, \
        (dc_fine, f_flat["dc"])
    # Cắt NGOÀI MP: DXF theo ánh xạ đa giác (b=350, h0=319) nên
    # Vcap ~98,9 kN, khác phẳng có sẵn (b=2500, h0=331 -> 584,7 kN)
    # — lệch do thiết kế item 4, không phải lỗi số; khóa cả 2 đầu
    # để ai đổi ánh xạ cũng thấy ngay.
    p_out = f_dxf["shear_out"]["parts"]
    assert p_out["b"] == 350.0 and p_out["h0"] == 319.0
    assert 90.0 < f_dxf["shear_out"]["V_cap"] < 110.0
    assert abs(f_flat["shear_out"]["V_cap"] - 584.71) < 1.0
    assert f_flat["shear_out"]["parts"]["b"] == 2500.0


# ---------------- (b) DXF chữ L vs L có sẵn ----------------

def test_dxf_vs_ell():
    w_built = _base(section_type="ell", sec_L1=2000, sec_L2=1800,
                    sec_t=300, per_dia=12, per_s=200)
    sec_b, meta_b = build_wall_section(w_built, _CONC, _STEEL)
    assert len(sec_b.rebars) == 44  # khóa lát thép
    verts_can = _poly_ell(w_built)
    xs = [p[0] for p in verts_can]
    ys = [p[1] for p in verts_can]
    # Dịch về tọa độ dương (tọa độ gốc bản vẽ cho DXF).
    dx, dy = -min(xs), -min(ys)
    outline = [[x + dx, y + dy] for x, y in verts_can]
    cx_d, cy_d = polygon_centroid(
        [(float(x), float(y)) for x, y in outline])
    dxf_bars = [[r.x + cx_d, r.y + cy_d, r.dia]
                for r in sec_b.rebars]
    w_dxf = _base(section_type="dxf", dxf_poly=outline,
                  dxf_bars=dxf_bars, dxf_file="ell.dxf",
                  per_dia=12, per_s=200)
    sec_d, meta_d = build_wall_section(w_dxf, _CONC, _STEEL)
    assert len(sec_d.rebars) == len(sec_b.rebars) == 44
    got = sorted((round(r.x, 6), round(r.y, 6), r.dia)
                 for r in sec_d.rebars)
    exp = sorted((round(r.x, 6), round(r.y, 6), r.dia)
                 for r in sec_b.rebars)
    assert got == exp, "thép DXF phải trùng thép L có sẵn từng thanh"
    assert abs(sec_d.gross_area - sec_b.gross_area) < 1e-6
    loads = _loads(2000.0, 700.0, 500.0, 800.0, 300.0)
    f_b = wall_tcvn_full(w_built, _CONC, _STEEL, loads=loads,
                         steel_sw=_SW, seismic_shear=False)
    f_d = wall_tcvn_full(w_dxf, _CONC, _STEEL, loads=loads,
                         steel_sw=_SW, seismic_shear=False)
    assert f_d["wall_axis_in"] == "x" == f_b["wall_axis_in"]
    assert _rel(f_d["dc"], f_b["dc"]) <= 1e-3, (f_d["dc"], f_b["dc"])
    assert _rel(f_d["shear_in"]["V_cap"],
                f_b["shear_in"]["V_cap"]) <= 1e-3
    assert _rel(f_d["shear_out"]["V_cap"],
                f_b["shear_out"]["V_cap"]) <= 1e-3
    # Hình học cắt DXF trùng L có sẵn (E_stem=2000, E_trans=1800,
    # t_branch=300, h0_in=1954, h0_out=1754 ở cover 28/dia 12).
    g = wall_shear_geometry_poly(w_dxf)
    assert g["geom_in"]["b"] == 300.0
    assert g["geom_in"]["h0"] == 1954.0
    assert g["geom_out"]["h0"] == 1754.0
    assert g["pending_out"] is None


# ---------------- (c) Tiết diện bất kỳ + xoay ----------------

def _arbitrary_data():
    # Γ 6 cạnh trực giao (không trùng loại có sẵn): đáy 2400x900
    # + khối trên trái 1500x900. 1 đỉnh lõm tại (1500, 900).
    poly = [[0, 0], [2400, 0], [2400, 900], [1500, 900],
            [1500, 1800], [0, 1800]]
    bars = [[200, 200, 16], [1200, 200, 16], [2200, 200, 16],
            [200, 700, 16], [2200, 700, 16],
            [200, 1200, 16], [1300, 1200, 16],
            [200, 1600, 16], [1300, 1600, 16]]
    return poly, bars


def test_dxf_arbitrary_and_rotation():
    poly, bars = _arbitrary_data()
    assert count_reflex_vertices(poly) == 1
    w = _base(section_type="dxf", dxf_poly=poly, dxf_bars=bars,
              dxf_file="gamma.dxf")
    loads = _loads(2000.0, 700.0, 500.0, 800.0, 300.0)
    f = wall_tcvn_full(w, _CONC, _STEEL, loads=loads, steel_sw=_SW,
                       seismic_shear=False)
    assert f["wall_axis_in"] == "x"  # bbox 2400 >= 1800
    assert math.isfinite(f["dc"]) and f["dc"] > 0
    assert f["shear_in"]["V_cap"] is not None
    # Trục x, chỉ 1 đỉnh lõm -> ngoài MP tính bình thường.
    assert f["shear_out"]["V_cap"] is not None
    assert f["checks_included"] == ["N-M", "shear_in", "shear_out"]
    # Xoay 90° + hoán đổi tải theo quy ước trục x (như
    # test_wallnm_poly): M_in' = -M_in, M_out' = M_out.
    w90 = _base(section_type="dxf", dxf_poly=poly, dxf_bars=bars,
                dxf_file="gamma.dxf", rot_deg=90)
    f90 = wall_tcvn_full(w90, _CONC, _STEEL,
                         loads=_loads(2000.0, -700.0, 500.0, 300.0,
                                      800.0),
                         steel_sw=_SW, seismic_shear=False)
    assert _rel(f90["dc"], f["dc"]) <= 1e-4, (f90["dc"], f["dc"])
    # JSON round-trip giữ nguyên tọa độ gốc + file, D/C không đổi.
    d = wall_to_dict(w)
    assert d["dxf_poly"] == poly and d["dxf_bars"] == bars
    assert d["dxf_file"] == "gamma.dxf"
    w2 = wall_from_dict(d)
    assert w2.dxf_poly == poly and w2.dxf_bars == bars
    f2 = wall_tcvn_full(w2, _CONC, _STEEL, loads=loads, steel_sw=_SW,
                        seismic_shear=False)
    assert abs(f2["dc"] - f["dc"]) < 1e-12
    # Thẻ chi tiết + bảng cắt đọc dict, không crash; preview vẽ được.
    secs = build_wall_detail_sections(f)
    assert len(secs) >= 7
    rows = build_wall_shear_rows(f)
    assert all(r[1] != "CHƯA KIỂM" and r[2] != "CHƯA KIỂM"
               for r in rows)
    fig, ax = plt.subplots(figsize=(5, 5))
    draw_wall_section_ax(ax, f["sec"], meta=f["meta"],
                         na_info=f["na_info"], show_compression=True,
                         rot_deg=0)
    fig.canvas.draw()
    plt.close(fig)


def test_dxf_hole_and_outside_bar():
    poly = [[0, 0], [2500, 0], [2500, 350], [0, 350]]
    hole = [[500, 100], [1000, 100], [1000, 250], [500, 250]]
    bars = [[200, 175, 12], [2300, 175, 12], [5000, 5000, 12]]
    w = _base(section_type="dxf", dxf_poly=poly, dxf_holes=[hole],
              dxf_bars=bars, dxf_file="hole.dxf")
    sec, meta = build_wall_section(w, _CONC, _STEEL)
    # Fiber Ac = outline trừ lỗ (chuẩn hoá ở build); gross_area là
    # property dùng chung với cột, chỉ tính outline (không trừ lỗ)
    # — KHÔNG sửa sections.py ở lát này (code cột dùng chung), nên
    # test khóa đúng 2 ngữ nghĩa đó thay vì ép gross_area = net.
    assert abs(sec.concrete_area - (875000.0 - 500.0 * 150.0)) < 1e-3
    assert abs(meta["poly_ac"] - (875000.0 - 500.0 * 150.0)) < 1e-6
    assert abs(sec.gross_area - 875000.0) < 1e-6
    assert len(sec.rebars) == 2  # thanh ngoài biên bị bỏ qua
    assert any("ngoài biên" in x for x in meta["warnings"])
    assert sec.poly_holes and len(sec.poly_holes[0]) == 4


def test_dxf_open_core_pending_out():
    """Pending ngoài MP: trục y + >= 2 đỉnh lõm -> lõi hở dạng C/U."""
    from rc_column.wall_section import _poly_c_core
    w_c = _base(section_type="c-core", Lw=3000, sec_bf=1500,
                sec_lr=600, sec_t=300, per_dia=12, per_s=200)
    sec_c, _m = build_wall_section(w_c, _CONC, _STEEL)
    verts_can = _poly_c_core(w_c)
    xs = [p[0] for p in verts_can]
    ys = [p[1] for p in verts_can]
    dx, dy = -min(xs), -min(ys)
    outline = [[x + dx, y + dy] for x, y in verts_can]
    cx_d, cy_d = polygon_centroid(
        [(float(x), float(y)) for x, y in outline])
    dxf_bars = [[r.x + cx_d, r.y + cy_d, r.dia]
                for r in sec_c.rebars]
    w = _base(section_type="dxf", dxf_poly=outline,
              dxf_bars=dxf_bars, dxf_file="ccore.dxf")
    g = wall_shear_geometry_poly(w)
    assert g["base"]["axis_canonical"] == "y"  # bbox 1500 < 3000
    assert count_reflex_vertices(outline) >= 2
    assert g["geom_out"] is None
    assert "CHƯA KIỂM" in g["pending_out"]
    assert g["geom_in"] is not None
    f = wall_tcvn_full(w, _CONC, _STEEL,
                       loads=_loads(3000.0, 1000.0, 600.0, 800.0,
                                    300.0),
                       steel_sw=_SW, seismic_shear=False)
    assert f["wall_axis_in"] == "y"
    assert math.isfinite(f["dc"]) and f["dc"] > 0
    assert f["shear_in"]["V_cap"] is not None
    assert f["shear_out"]["V_cap"] is None
    assert "shear_out" in f["checks_pending"]


def test_dxf_empty_build_error():
    w = _base(section_type="dxf")
    try:
        build_wall_section(w, _CONC, _STEEL)
        raise AssertionError("phải lỗi khi chưa import DXF")
    except ValueError as ex:
        assert "dxf_poly" in str(ex) or "biên bê tông" in str(ex)
    # File cũ thiếu khóa DXF vẫn mở bình thường.
    w_old = wall_from_dict({"section_type": "rect"})
    assert w_old.dxf_poly == [] and w_old.dxf_file == ""


# ---------------- GUI Xvfb: import -> preview -> CHECK ----------------

def test_dxf_gui_xvfb(tmp_path):
    """GUI (skip khi không có display; chạy dưới Xvfb): nạp dữ liệu
    DXF như sau khi import (dialog filedialog/preview không mô phỏng
    được trong test nên đặt _wall_dxf_data trực tiếp — đúng dữ liệu
    mà _on_import_wall_dxf lưu), preview đúng (kind poly, 30 thanh),
    CHECK ra D/C đúng số engine, _apply_wall khôi phục lại dữ liệu."""
    try:
        import tkinter as tk
        _r = tk.Tk()
        _r.withdraw()
        _r.destroy()
    except Exception:
        import pytest
        pytest.skip("không có display Tk")
    from gui.app import App
    poly, dxf_bars = _flat_dxf_data()
    app = App()
    try:
        app.update_idletasks()
        app.cb_member.set("Vách")
        app._toggle_member()
        app.update_idletasks()
        # Dữ liệu như _on_import_wall_dxf lưu sau preview Dùng.
        app._wall_dxf_data = {"poly": [list(p) for p in poly],
                              "holes": [],
                              "bars": [list(b) for b in dxf_bars],
                              "file": "flat.dxf"}
        app.w_cb_sectype.set("Tiết diện bất kỳ (DXF)")
        app._update_wall_sectype_fields()
        app._update_wall_rotation_visibility()
        app._update_wall_dxf_info()
        app.update_idletasks()
        assert "flat.dxf" in app.w_var_wall_dxf_info.get()
        assert "30 thép" in app.w_var_wall_dxf_info.get()
        assert app.w_lbl_wall_dxf_info.winfo_manager() == "grid"
        # Hàng kích thước + khung thép đều ẩn ở loại DXF.
        assert app.w_en_Lw.winfo_manager() == ""
        assert app.w_frm_per.winfo_manager() == ""
        assert app.w_frm_be.winfo_manager() == ""
        # _collect_wall -> build preview đúng.
        w = wall_from_dict(app._collect_wall())
        assert w.section_type == "dxf"
        assert w.dxf_poly == [list(p) for p in poly]
        sec, meta = build_wall_section(w, _CONC, _STEEL)
        assert sec.kind == "poly" and len(sec.rebars) == 30
        # _apply_wall khôi phục dữ liệu + nhãn.
        app._apply_wall(app._collect_wall())
        app.update_idletasks()
        assert (app._wall_dxf_data or {}).get("file") == "flat.dxf"
        assert "flat.dxf" in app.w_var_wall_dxf_info.get()
        # CHECK nhập tay + TCVN ra D/C đúng số engine.
        app.var_load_mode.set("manual")
        app.cb_conc.set("B30")
        app.cb_steel.set("CB500-V")
        app.w_cb_sw_steel.set("CB400-V")
        app.w_var_seismic.set(False)

        def _set(entry, val):
            entry.delete(0, "end")
            entry.insert(0, str(val))

        _set(app.en_N, 2000)
        _set(app.en_My, 800)
        _set(app.en_Mx, 200)
        _set(app.en_Q2, 800)
        _set(app.en_Q3, 300)
        _set(app.en_gb, 0.85)
        _set(app.en_gs, 1.0)
        app._on_check_wall()
        app.update_idletasks()
        full = getattr(app, "_tcvn_wall_full", None)
        assert full is not None
        assert full["winp"].section_type == "dxf"
        assert math.isfinite(full["dc"]) and full["dc"] > 0
        f_eng = wall_tcvn_full(
            _base(section_type="dxf", cover=13, dia_v=12, s_v=200,
                  per_dia=12, per_s=200, steel_mode="perimeter",
                  dxf_poly=poly, dxf_bars=dxf_bars,
                  dxf_file="flat.dxf"),
            _CONC, _STEEL,
            loads=_loads(2000.0, 800.0, 200.0, 800.0, 300.0),
            steel_sw=_SW, seismic_shear=False)
        # D/C N–M của DXF không phụ thuộc cover panel (thép thật,
        # ea theo bbox) nên GUI CHECK phải ra đúng số engine (mốc
        # cover 13); cắt thì khác cover nên chỉ kiểm có số.
        assert full["sec"].kind == "poly"
        assert len(full["sec"].rebars) == 30
        assert _rel(full["dc"], f_eng["dc"]) <= 1e-9, \
            (full["dc"], f_eng["dc"])
        assert full["shear_in"]["V_cap"] is not None
    finally:
        try:
            app.destroy()
        except Exception:
            pass
