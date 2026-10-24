"""Kiểm chứng phần 5/7: combo động đất + phóng đại cắt kháng chấn
TCVN 9386-1:2012 §5.4.2.4(7) DCM cho vách.

CĂN CỨ (đã tra văn bản thật, không mượn mù):
- TCVN 9386-1:2012 §5.4 "Design for DCM", §5.4.2.4 "Special
  provisions for ductile walls", (6)P: sự tăng lực cắt sau khi
  chảy dẻo tại chân vách PHẢI được kể đến; (7): được thỏa mãn nếu
  lực cắt thiết kế lấy cao hơn 50% lực cắt từ phân tích, tức
  V_Ed = 1,5 × V'_Ed. Phần 1 của TCVN 9386 tương ứng EN 1998-1,
  các sửa đổi VN chỉ ở Phụ lục E–I nên số điều §5 giữ nguyên.
- Đây là quy tắc RIÊNG của DCM: KHÔNG phải công thức ε của DCH
  (§5.5.2.4.1(7), (5.24)/(5.25) cần MRd/MEd, q, phổ) — DCM không
  cần MRd/MEd, q hay Se; đừng áp ε DCH cho vách DCM.
- Phạm vi: CHỈ cắt trong mặt phẳng; cắt ngoài mặt phẳng không
  phóng đại; (8) là bao lực cắt theo chiều cao cho hệ kép, kiểm
  tra 1 tiết diện chân vách không dựng bao đó.

Ca chuẩn: vách mẫu web 2500x350, B30 γb=0.85, thép dọc CB500-V,
V_in = 800 kN, V_out = 300 kN (như test_wall_shear_out).
Đường GUI mặc định (thép ngang CB400-V, phần 3/7): Vcap trong MP
1920.5 kN, D/C không phóng đại 0.41657 -> phóng đại 1200 kN,
D/C 0.62485 (= 1,5×, Vcap không đổi vì ĐK (98) vẫn thỏa ở 1200).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rc_column.etabs_import import effective_merge_bases
from rc_column.materials import (CONCRETE_GRADES, STEEL_GRADES,
                                 ConcreteMaterial, SteelMaterial)
from rc_column.wall_detail import build_wall_detail_sections
from rc_column.wall_engine import (SEISMIC_SHEAR_FACTOR_DCM,
                                   wall_tcvn_full)
from rc_column.wall_input import WallInput
from rc_column.wall_shear import check_wall_shear_in_plane


def _mats():
    conc = ConcreteMaterial(CONCRETE_GRADES["B30"], 0.85)
    steel = SteelMaterial(STEEL_GRADES["CB500-V"], 1.0)
    return conc, steel


def _web_loads(V_in=800.0, V_out=300.0):
    return {"N": 2528.65, "M_in": 202.86, "M_out": 275.23,
            "V_in": V_in, "V_out": V_out, "T": 0.0}


def test_factor_constant_is_dcm_1_5():
    """Hằng số phóng đại DCM đúng 1,5 (không phải ε DCH)."""
    assert SEISMIC_SHEAR_FACTOR_DCM == 1.5


def test_default_off_preserves_old_numbers_bitwise():
    """Mặc định seismic_shear=False: số cũ tái hiện từng chữ số
    (cả đường cũ CB500-V lẫn đường GUI CB400-V)."""
    conc, steel = _mats()
    f_old = wall_tcvn_full(WallInput(), conc, steel,
                           loads=_web_loads())
    assert f_old["shear_in"]["V_d"] == 800.0
    assert f_old["shear_in"]["seismic_factor"] == 1.0
    assert f_old["shear_in"]["seismic_applied"] is False
    assert abs(f_old["shear_in"]["V_cap"] - 1987.2) < 0.05
    assert abs(f_old["shear_in"]["dc"] - 0.40259) < 1e-5
    f_gui = wall_tcvn_full(WallInput(sw_steel_grade="CB400-V"),
                           conc, steel, loads=_web_loads())
    assert abs(f_gui["shear_in"]["V_cap"] - 1920.5) < 0.05
    assert abs(f_gui["shear_in"]["dc"] - 0.41657) < 1e-5


def test_seismic_amplifies_in_plane_only():
    """seismic_shear=True: V_Ed = 1,5×V_in, D/C = 1,5× (Vcap không
    đổi ở ca mẫu vì (98) vẫn thỏa); N–M và cắt ngoài MP không đổi."""
    conc, steel = _mats()
    base = wall_tcvn_full(WallInput(sw_steel_grade="CB400-V"),
                          conc, steel, loads=_web_loads())
    seis = wall_tcvn_full(WallInput(sw_steel_grade="CB400-V"),
                          conc, steel, loads=_web_loads(),
                          seismic_shear=True)
    sh = seis["shear_in"]
    assert sh["V_raw"] == 800.0
    assert sh["V_d"] == 1200.0
    assert sh["seismic_factor"] == 1.5
    assert sh["seismic_applied"] is True
    assert abs(sh["V_cap"] - base["shear_in"]["V_cap"]) < 1e-9
    assert abs(sh["dc"] - 1.5 * base["shear_in"]["dc"]) < 1e-12
    assert abs(sh["dc"] - 0.62485) < 1e-5
    # N–M từng chữ số + cắt ngoài MP không đổi
    assert seis["dc"] == base["dc"]
    # Mốc N–M mẫu SAU hợp nhất cover (f3ba890, quy ước c_đai):
    # 0.44520 (trước cover) -> 0.45907; cắt không đổi vì h0 cắt
    # không phụ thuộc vị trí thép dọc. Số cắt vẫn là mốc cũ.
    assert abs(seis["dc"] - 0.45907) < 1e-5
    assert seis["ok_all"] == base["ok_all"]
    assert seis["shear_out"]["V_d"] == base["shear_out"]["V_d"] == 300.0
    assert seis["shear_out"]["V_cap"] == base["shear_out"]["V_cap"]
    assert seis["shear_out"]["dc"] == base["shear_out"]["dc"]
    # Đối chiếu trực tiếp: phóng đại = gọi check ở V = 1200
    direct = check_wall_shear_in_plane(
        WallInput(sw_steel_grade="CB400-V"), conc, steel, 1200.0,
        2528.65)
    assert sh["V_cap"] == direct["V_cap"]
    assert sh["dc"] == direct["dc"]


def test_seismic_flows_through_full_9813_not_just_dc_scale():
    """Phóng đại đi qua toàn bộ §8.1.3: s_h = 2000 thỏa (98) ở
    V = 800 (s_max ~2694) nhưng VI PHẠM ở V_Ed = 1200
    (s_max ~1796 < 2000) -> thép ngang bị loại, Qsw = 0, Vcap
    rơi về mức chỉ còn Qb. Nếu chỉ nhân D/C sau cùng thì ca này
    sẽ sai (không bắt được (98) lật)."""
    conc, steel = _mats()
    w = WallInput(sw_steel_grade="CB400-V")
    w.s_h = 2000.0
    base = wall_tcvn_full(w, conc, steel, loads=_web_loads())
    assert base["shear_in"]["parts"]["cond98_ok"] is True
    assert base["shear_in"]["parts"]["Qsw"] > 0.0
    seis = wall_tcvn_full(w, conc, steel, loads=_web_loads(),
                          seismic_shear=True)
    p = seis["shear_in"]["parts"]
    assert p["cond98_ok"] is False
    assert p["qsw"] == 0.0
    assert p["Qsw"] == 0.0
    # Bất biến chứng minh "đi qua toàn bộ §8.1.3": D/C phóng đại
    # KHÔNG còn bằng 1,5× D/C gốc (vì Vcap đổi theo (98)), mà bằng
    # đúng 1200 / Vcap mới — đối chiếu trực tiếp với check ở 1200.
    assert seis["shear_in"]["dc"] == 1200.0 / seis["shear_in"]["V_cap"]
    assert abs(seis["shear_in"]["dc"]
               - 1.5 * base["shear_in"]["dc"]) > 0.1
    direct = check_wall_shear_in_plane(w, conc, steel, 1200.0, 2528.65)
    assert seis["shear_in"]["V_cap"] == direct["V_cap"]
    assert seis["shear_in"]["dc"] == direct["dc"]


def test_detail_builder_shows_seismic_line():
    """Builder chi tiết (tab + PDF chi tiết dùng chung) ghi rõ
    dòng phóng đại khi áp, và ghi rõ không phóng đại khi tắt."""
    conc, steel = _mats()
    w = WallInput(sw_steel_grade="CB400-V")
    seis = wall_tcvn_full(w, conc, steel, loads=_web_loads(),
                          seismic_shear=True)
    secs = build_wall_detail_sections(seis)
    sec8 = [s for s in secs if s["num"] == 8][0]
    txt = "\n".join("\n".join(c["lines"]) for c in sec8["cards"])
    assert "9386-1:2012" in txt and "1,5" in txt
    assert "V_Ed = 1,5" in txt
    base = wall_tcvn_full(w, conc, steel, loads=_web_loads())
    secs0 = build_wall_detail_sections(base)
    sec8_0 = [s for s in secs0 if s["num"] == 8][0]
    txt0 = "\n".join("\n".join(c["lines"]) for c in sec8_0["cards"])
    assert "Không phóng đại cắt kháng chấn" in txt0


def test_effective_merge_bases_is_seismic_set():
    """Tập gộp hiệu dụng = tập động đất (không còn tập gộp riêng hay
    nút chọn gộp): tên động đất tự gộp, tên khác không gộp."""
    assert effective_merge_bases(set()) == set()
    assert effective_merge_bases(None) == set()
    assert effective_merge_bases({"ULS17"}) == {"ULS17"}
    assert effective_merge_bases({"ULS17", "EQ1"}) == {"ULS17", "EQ1"}
