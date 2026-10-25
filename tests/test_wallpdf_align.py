"""PDF tom tat vach — can le + dai mau bang cat + Rsw/mác muc VAT LIEU.

Ghi chu user 2026-10-25 (anh PDF tom tat vach build cdede78d, ca VACH):
- Bang cat mat can le voi bang tren (text x0 = 48.5pt thay vi 42.5pt)
  va khong co dai mau dam/nhat. Nguyen nhan: sw_style cua bang cat
  da dinh nghia san trong wall_pdf_summary.py nhung CHUA BAO GIO
  duoc setStyle -> ReportLab dung padding mac dinh 6pt va khong ve
  BACKGROUND. Test nay khoa ca hai: x0 bang cat == x0 bang tren,
  va co fill xam #F2F2F2 trong vung bang cat.
- Dinh chinh 02:53: cuong do + mac thep dai KHONG vao bang cat ma
  vao MUC VAT LIEU o tren (1 hang gon "Thép đai: CB400-V,
  Rsw = 280 MPa", Rsw lay tu parts cat cua engine, khong hardcode).
  Test khoa: hang do co trong text, phan text SAU tieu de bang cat
  khong chua "Rsw" (bang cat khong them hang Rsw/mac), so tinh
  khong doi (dc 0.463, trong MP 1828.9, ngoai MP 568.0), dung 1 trang.
- Dinh chinh 07:12 (anh after_ca1.pdf): hang Thep dai o VAT LIEU
  tach thanh 2 dong rieng (mac / Rsw), khong gop nua; ghi chu
  phong dai V_Ed 1,5x trong bang cat bi xoa han (chi xoa text,
  V_Ed van la gia tri da phong dai). Xem test cuoi file.
"""

import io

import pytest

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_input import WallInput
from rc_column.wall_pdf_summary import export_wall_summary_pdf

CONC = ConcreteMaterial(CONCRETE_GRADES["B25"], 0.85)
STEEL = SteelMaterial(STEEL_GRADES["CB400-V"], 1.0)
LOADS = {"N": 2500.0, "M_in": 3000.0, "M_out": 60.0,
         "V_in": 800.0, "V_out": 0.0, "T": 0.0}


def _full():
    winp = WallInput(
        Lw=2500.0, tw=350.0, cover=13.0, dia_h=12.0, s_h=200.0,
        layers_h=2, sw_steel_grade="CB400-V",
        steel_mode="boundary", be_Lb=500.0, be_dia=28.0,
        be_n_Lb=4, be_n_tw=0, be_L_out=1, be_L_in=0,
        web_dia=12.0, web_s=200.0,
        Lx_m=3.3, Ly_m=3.3, psi_x=1.0, psi_y=1.0,
        seismic_on=True)
    return wall_tcvn_full(winp, CONC, STEEL, loads=dict(LOADS),
                          seismic_shear=True)


def _pdf_bytes(full):
    buf = io.BytesIO()
    export_wall_summary_pdf(full, buf, member_name="VACH",
                            show_compression=True)
    return buf.getvalue()


def test_wallpdf_align_and_material_rsw():
    full = _full()
    # So tinh khong doi (moc cdede78d).
    assert abs(full["dc"] - 0.463114) < 0.0005
    assert abs(full["shear_in"]["V_cap"] - 1828.9) < 0.5
    assert abs(full["shear_out"]["V_cap"] - 568.0) < 0.5
    # Rsw engine dung cho qsw (khong hardcode o test ngoai so moc
    # nay: no cung la gia tri parts tra ve, test chi khoa rang
    # hang VAT LIEU in dung gia tri do).
    rsw = full["shear_in"]["parts"]["Rsw"]
    grade = full["shear_in"]["parts"]["steel_grade"]
    assert grade == "CB400-V"
    assert abs(rsw - 280.0) < 1e-9
    data = _pdf_bytes(full)
    try:
        from pypdf import PdfReader
    except Exception:
        from PyPDF2 import PdfReader
    r = PdfReader(io.BytesIO(data))
    assert len(r.pages) == 1
    txt = "\n".join((p.extract_text() or "") for p in r.pages)
    # Hang VAT LIEU: tach 2 dong (ghi chu user 2026-10-25 07:12,
    # anh after_ca1.pdf khoanh hang Thep dai) — khong gop
    # "mac, Rsw" vao 1 hang nua.
    assert "Thép đai" in txt
    assert "Cường độ chịu cắt, Rsw" in txt
    assert "CB400-V, Rsw = 280 MPa" not in txt
    _head = txt.split("KIỂM TRA KHẢ NĂNG CHỊU CẮT", 1)[0]
    assert "CB400-V" in _head
    assert "280 MPa" in _head
    # Bang cat KHONG them hang Rsw/mac (dinh chinh 02:53): phan
    # text sau tieu de bang cat khong duoc chua "Rsw".
    tail = txt.split("KIỂM TRA KHẢ NĂNG CHỊU CẮT", 1)[1]
    assert "Rsw" not in tail
    # Bang cat van du hang cu, khong them/khong mat hang.
    assert "Thép ngang bố trí" in txt
    assert "1,828.9 kN" in txt
    assert "568.0 kN" in txt


def test_wallpdf_no_v2v3_row_and_no_grade_in_shear_and_chart_anchor():
    """Ghi chu user 2026-10-25 (anh after_vach.pdf 06:52 + bo sung 06:54),
    gop chung push voi wallalign — chi PDF tom tat vach:
    - Xoa hang "Lực cắt, V2, V3" khoi khoi NOI LUC KIEM TRA (luc
      cat da co du o bang cat phia duoi kem phong dai DCM); giu
      hang N va M2/M3.
    - Xoa "(CB400-V)" khoi hang "Thép ngang bố trí" o bang cat
      (ca 2 cot), chi con "2φ12 a200" — mac thep dai nay da co o
      hang "Thép đai" muc VAT LIEU; strip o tang PDF (sw_txt
      tran), khong hardcode ten cap, tab/chi tiet khong doi.
    - Neo doc 2 bieu do: M2–M3 can duoi (day anh sat bang cat),
      N–Ma (P–M) can giua khoang mat cat→M2–M3 (2 khe bang nhau).
    """
    full = _full()
    data = _pdf_bytes(full)
    try:
        from pypdf import PdfReader
    except Exception:
        from PyPDF2 import PdfReader
    r = PdfReader(io.BytesIO(data))
    assert len(r.pages) == 1
    txt = "\n".join((p.extract_text() or "") for p in r.pages)
    # 1. Hang V2/V3 da mat khoi khoi Noi luc, cac hang khac con.
    assert "Lực cắt, V2, V3" not in txt
    assert "Lực dọc tính toán, N" in txt
    assert "Mô men ban đầu, M2, M3" in txt
    # Luc cat van con o bang cat phia duoi (kem phong dai DCM).
    tail = txt.split("KIỂM TRA KHẢ NĂNG CHỊU CẮT", 1)[1]
    assert "1200.0 kN" in tail
    assert "0.0 kN" in tail
    # 2. Bang cat: thep bo tri khong con ngoac cap thep, nhung
    # muc VAT LIEU (phan truoc bang cat) van co mac + Rsw.
    assert "2φ12 a200" in tail
    assert "(CB400-V)" not in tail
    assert "CB400-V" not in tail
    head = txt.split("KIỂM TRA KHẢ NĂNG CHỊU CẮT", 1)[0]
    # VAT LIEU tach 2 dong (07:12): mac rieng, Rsw rieng.
    assert "CB400-V, Rsw = 280 MPa" not in head
    assert "Thép đai" in head
    assert "Cường độ chịu cắt, Rsw" in head
    assert "280 MPa" in head
    # 3. Neo doc 2 bieu do (fitz).
    pytest.importorskip("fitz")
    import fitz
    doc = fitz.open(stream=data, filetype="pdf")
    assert doc.page_count == 1
    page = doc[0]
    imgs = []
    for img in page.get_images(full=True):
        for rect in page.get_image_rects(img[0]):
            imgs.append(rect)
    imgs = sorted(imgs, key=lambda r: r.y0)
    assert len(imgs) == 3, f"can 3 anh, thay {len(imgs)}"
    sec, nm, m2 = imgs
    # Mat cat can tren (y0 ~53.3 nhu truoc).
    assert abs(sec.y0 - 53.3) < 3.0
    # M2–M3 can duoi: day anh > 600, khe toi tieu de bang cat < 25pt
    # (truoc sua: day ~563, khe ~59pt).
    shear_y = page.search_for("KIỂM TRA KHẢ NĂNG CHỊU CẮT")[0].y0
    assert m2.y1 > 600.0
    assert 0 < shear_y - m2.y1 < 25.0
    # N–Ma can giua: khe truoc ≈ khe sau (sai so < 2pt).
    nm_title_y = page.search_for("Biểu đồ tương tác N–Mα")[0].y0
    m2_title_y = page.search_for("Mặt cắt M2–M3")[0].y0
    gap_before = nm_title_y - sec.y1
    gap_after = m2_title_y - nm.y1
    assert abs(gap_before - gap_after) < 2.0


def test_wallpdf_shear_alignment_and_zebra():
    pytest.importorskip("fitz")
    import fitz
    full = _full()
    data = _pdf_bytes(full)
    doc = fitz.open(stream=data, filetype="pdf")
    assert doc.page_count == 1
    page = doc[0]

    def x0_of(s):
        rs = page.search_for(s)
        assert rs, f"khong tim thay text {s!r} trong PDF"
        return rs[0].x0

    # Mep trai bang cat thang hang bang thong tin phia tren.
    assert abs(x0_of("KIỂM TRA KHẢ NĂNG CHỊU CẮT")
               - x0_of("Tiêu chuẩn")) < 0.6
    assert abs(x0_of("Thép ngang bố trí")
               - x0_of("Tiêu chuẩn")) < 0.6
    # Dai mau #F2F2F2 (0.949) trong vung bang cat (y >= 580),
    # rong gan full-width (x0 ~ 42.5, x1 ~ 552.7).
    shear_fills = []
    for d in page.get_drawings():
        if not d.get("fill"):
            continue
        r = d["rect"]
        if r.y0 >= 580 and abs(d["fill"][0] - 0.949) < 0.01:
            shear_fills.append(r)
    assert shear_fills, "bang cat khong co fill dai mau"
    assert any(abs(r.x0 - 42.5) < 1.0 and r.x1 > 500
               for r in shear_fills)


def _full_ca1():
    """Ca anh user (B30/CB500-V, cover 25, L 5.75, psi 0.8,
    V_in = V_out = 0) — moc e01d839: dc 0.291393, cat
    1920.5/579.1. Chi dung de khoa 1 trang + 2 viec 07:12."""
    conc = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
    winp = WallInput(
        steel_mode="boundary", cover=25.0, dia_v=12.0, s_v=200.0,
        dia_h=12.0, s_h=200.0, layers_h=2, sw_steel_grade="CB400-V",
        be_Lb=500.0, be_dia=28.0, be_n_Lb=4, be_n_tw=2, be_L_out=2,
        be_L_in=1, web_dia=12.0, web_s=200.0, Lx_m=5.75, Ly_m=5.75,
        psi_x=0.8, psi_y=0.8)
    winp.rot_deg = 0
    loads = {"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
             "V_in": 0.0, "V_out": 0.0, "T": 0.0}
    return wall_tcvn_full(winp, conc, steel, loads=loads,
                          seismic_shear=True)


def _txt_of(full, member):
    buf = io.BytesIO()
    export_wall_summary_pdf(full, buf, member_name=member,
                            show_compression=True)
    try:
        from pypdf import PdfReader
    except Exception:
        from PyPDF2 import PdfReader
    r = PdfReader(io.BytesIO(buf.getvalue()))
    assert len(r.pages) == 1
    return "\n".join((p.extract_text() or "") for p in r.pages)


def test_wallpdf_stirrup_two_rows_and_no_dcm_note():
    """Ghi chu user 2026-10-25 07:12 (anh after_ca1.pdf) — chi
    PDF tom tat vach:
    (A) VAT LIEU: hang Thep dai tach thanh 2 dong rieng
    (mac / Rsw), giong cac vat lieu khac; khong con chuoi gop.
    (B) Bang cat: bo han ghi chu \"V2 da phong dai 1,5x...\"
    trong o nhan hang luc cat; chi xoa text hien thi — gia tri
    V_Ed (da phong dai) va D/C cat khong doi."""
    for full, member, dc, vcap_in, vcap_out in (
            (_full(), "VACH", 0.463114, 1828.9, 568.0),
            (_full_ca1(), "CA1", 0.291393, 1920.5, 579.1)):
        assert abs(full["dc"] - dc) < 0.0005
        assert abs(full["shear_in"]["V_cap"] - vcap_in) < 0.5
        assert abs(full["shear_out"]["V_cap"] - vcap_out) < 0.5
        txt = _txt_of(full, member)
        # (A) 2 hang rieng, khong gop.
        assert "Thép đai" in txt
        assert "Cường độ chịu cắt, Rsw" in txt
        assert "CB400-V, Rsw = 280 MPa" not in txt
        head = txt.split("KIỂM TRA KHẢ NĂNG CHỊU CẮT", 1)[0]
        assert "CB400-V" in head
        assert "280 MPa" in head
        # (B) Khong con ghi chu phong dai 1,5x o bat ky cho nao
        # trong PDF tom tat, nhung gia tri V_Ed van dung va
        # hang thep bo tri bang cat van khong ngoac cap thep.
        assert "phóng đại 1,5" not in txt
        assert "Ghi chú: V2 đã phóng đại" not in txt
        tail = txt.split("KIỂM TRA KHẢ NĂNG CHỊU CẮT", 1)[1]
        assert "Thép ngang bố trí" in tail
        assert "2φ12 a200" in tail
        assert "(CB400-V)" not in tail
    # Rieng ca VACH: V_Ed trong MP van la 1200.0 (da x1,5),
    # chung minh phep phong dai engine khong bi bo theo text.
    txt_vach = _txt_of(_full(), "VACH")
    tail_vach = txt_vach.split("KIỂM TRA KHẢ NĂNG CHỊU CẮT", 1)[1]
    assert "1200.0 kN" in tail_vach
