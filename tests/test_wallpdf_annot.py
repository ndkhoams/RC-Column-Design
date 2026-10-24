"""PDF tóm tắt vách theo ghi chú mực đỏ/xanh của user (2026-10-25).

- Nhãn Lw lên trên đường dim (kiểm hình học ở gate_wallpdf.py).
- Hàng cover chỉ còn c, không "(c_dọc = ...)".
- Xóa dòng "Kết luận N–M" dưới N–Mα và caption "Diễn giải M2–M3"
  (kết luận N–M vẫn ở bảng KẾT QUẢ).
- Bảng cắt 3 cột [Hạng mục | Trong MP | Ngoài MP].
- V2 trơn + ghi chú DCM trong ô nhãn hàng V2.
- Ghi chú phạm vi soát lại (bỏ câu DCM trùng + mệnh đề M2–M3).
Chỉ đổi trình bày — mọi số tính giữ nguyên.
"""

import io

from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_engine import wall_tcvn_full
from rc_column.wall_input import WallInput
from rc_column.wall_pdf_summary import export_wall_summary_pdf

CONC = ConcreteMaterial(CONCRETE_GRADES["B25"], 0.85)
STEEL = SteelMaterial(STEEL_GRADES["CB400-V"], 1.0)
LOADS = {"N": 2500.0, "M_in": 3000.0, "M_out": 60.0,
         "V_in": 800.0, "V_out": 0.0, "T": 0.0}


def _full(seis=True):
    winp = WallInput(
        Lw=2500.0, tw=350.0, cover=13.0, dia_h=12.0, s_h=200.0,
        layers_h=2, sw_steel_grade="CB400-V",
        steel_mode="boundary", be_Lb=500.0, be_dia=28.0,
        be_nL=4, be_nT=2, web_dia=12.0, web_s=200.0,
        Lx_m=3.3, Ly_m=3.3, psi_x=1.0, psi_y=1.0,
        seismic_on=True)
    return wall_tcvn_full(winp, CONC, STEEL, loads=dict(LOADS),
                          seismic_shear=seis)


def _pdf_text(full):
    try:
        from pypdf import PdfReader
    except Exception:
        from PyPDF2 import PdfReader
    buf = io.BytesIO()
    export_wall_summary_pdf(full, buf, member_name="COTBTCT",
                            show_compression=True)
    buf.seek(0)
    r = PdfReader(buf)
    return len(r.pages), "\n".join((p.extract_text() or "")
                                   for p in r.pages)


def test_summary_annot_seismic():
    full = _full(seis=True)
    assert abs(full["dc"] - 0.463) < 0.0005
    pages, txt = _pdf_text(full)
    assert pages == 1
    # 1. Cover trơn.
    assert "13 mm" in txt
    assert "(c_d" not in txt
    # 2. Không còn 2 dòng/caption dưới biểu đồ; kết luận N–M vẫn
    # ở bảng KẾT QUẢ.
    assert "Kết luận N–M: D/C" not in txt
    assert "Diễn giải M2" not in txt
    assert "Kết luận N–M" in txt
    # 3. Bảng cắt 3 cột + đủ 2 phương, số không đổi.
    assert "Trong mặt phẳng" in txt
    assert "Ngoài mặt phẳng" in txt
    assert "1,828.9 kN" in txt
    assert "657.6 kN" in txt
    assert "0.656" in txt and "0.000" in txt
    # 4. V2 trơn + ghi chú DCM ở hàng V2 (không parenthetical cũ).
    assert "1,5×800.0" not in txt
    assert "800.0 → 1200.0 kN" in txt
    assert "9386-1:2025" in txt
    # 5. Ghi chú phạm vi: bỏ câu DCM + mệnh đề M2–M3, giữ phần còn
    # lại.
    assert "Phạm vi:" in txt
    assert "M2–M3 diễn" not in txt
    assert "đã phóng đại kháng chấn" not in txt
    assert "không có kết luận chung" in txt
    assert "CHƯA KIỂM" in txt


def test_summary_annot_non_seismic():
    full = _full(seis=False)
    pages, txt = _pdf_text(full)
    assert pages == 1
    # Không áp DCM: V2 = giá trị gốc, không có ghi chú DCM;
    # ghi chú phạm vi giữ câu "chưa kể phóng đại".
    assert "800.0 kN" in txt
    assert "800.0 → 1200.0 kN" not in txt
    assert "chưa kể phóng đại" in txt
    assert "M2–M3 diễn" not in txt
