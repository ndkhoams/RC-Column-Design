"""Thuyết minh tính toán theo format VietconSoft (6 mục).

Trả về list các segment (text, tags) để GUI render với màu sắc:
- sec_title: tiêu đề mục (in hoa, đậm, #0f172a)
- sec_ref: căn cứ tiêu chuẩn (xám, nhỏ)
- card: nội dung thẻ
- mono: công thức/số (monospace)
- result: kết quả (đậm)
- ok / ng: huy hiệu ĐẠT / KHÔNG ĐẠT
- dc: số D/C nổi bật
"""

import math
from typing import List, Tuple

from .checker import CheckResult, ColumnInput, build_section
from .materials import EPS_B1, EPS_B2, EPS_S2
from .stability import BOUNDARY_NAMES

Seg = Tuple[str, Tuple[str, ...]]


def _f(x: float, nd: int = 2) -> str:
    if not math.isfinite(x):
        return "—"
    return f"{x:.{nd}f}"


class ReportBuilder:
    def __init__(self):
        self.segs: List[Seg] = []
        self.sections: dict = {}  # num -> {"title":, "ref":, "segs": []}
        self._cur = None

    def add(self, text: str, *tags: str):
        seg = (text, tags)
        self.segs.append(seg)
        if self._cur is not None:
            self.sections[self._cur]["segs"].append(seg)

    def nl(self, n: int = 1):
        self.add("\n" * n)

    def section(self, num: int, title: str, ref: str):
        self._cur = num
        self.sections[num] = {"title": title, "ref": ref, "segs": []}
        self.nl(2)
        self.add(f"● {num}. {title}", "sec_title")
        self.add(f"  {ref}", "sec_ref")
        self.nl()

    def line(self, label: str, formula: str, value: str, result: str = ""):
        self.add(f"  ▪ {label}\n", "card")
        if formula:
            self.add(f"    {formula}\n", "mono")
        self.add(f"    = {value}", "result")
        if result:
            self.add(f"  {result}", "result")
        self.nl()

    def build(self) -> List[Seg]:
        return self.segs

    def build_sections(self) -> dict:
        return self.sections


def _build_report(inp: ColumnInput, res: CheckResult) -> ReportBuilder:
    sec = build_section(inp)
    conc = sec.concrete
    steel = sec.steel
    b = ReportBuilder()
    A = b.add

    # Tiêu đề chung
    A("THUYẾT MINH TÍNH TOÁN KIỂM TRA CỘT BTCT", "title")
    b.nl()
    A("Tiêu chuẩn: TCVN 5574:2018 — Mô hình biến dạng phi tuyến (Điều 8.1.2.7)",
      "sec_ref")
    b.nl()

    # ---- 1. Vật liệu ----
    b.section(1, "ĐẶC TRƯNG VẬT LIỆU & CƯỜNG ĐỘ TÍNH TOÁN",
              "TCVN 5574:2018 Mục 6.1 & 6.2")
    b.line("Bê tông chịu nén Rb*",
           f"Rb* = γb · Rb = {_f(inp.gamma_b)} × {_f(conc.grade.Rb)}",
           f"{_f(conc.Rb)} MPa")
    b.line("Mô đun đàn hồi bê tông Eb",
           f"Eb ({inp.concrete_grade})",
           f"{conc.Eb:.0f} MPa")
    b.line("Thép chịu kéo Rs",
           f"Rs = {_f(steel.grade.Rs)} × {_f(inp.gamma_s)} (γs)",
           f"{_f(steel.Rs)} MPa")
    b.line("Thép chịu nén Rsc", "", f"{_f(steel.Rsc)} MPa")
    b.line("Mô đun đàn hồi thép Es", "", f"{steel.Es:.0f} MPa")
    b.line("Tỷ số mô đun αe",
           f"αe = Es / Eb = {steel.Es:.0f} / {conc.Eb:.0f}",
           f"{_f(res.alpha_e)}")
    b.line("Biến dạng giới hạn",
           f"εb1 = {EPS_B1}, εb2 = {EPS_B2}, εs2 = {EPS_S2}",
           "MH3ĐT" if inp.concrete_model == "3line" else "MH2ĐT")

    # ---- 2. Hình học ----
    b.section(2, "ĐẶC TRƯNG HÌNH HỌC TIẾT DIỆN",
              f"{'Chữ nhật' if inp.section_type == 'rect' else 'Tròn'} "
              f"{inp.cx:.0f}×{inp.cy:.0f} mm" if inp.section_type == "rect"
              else f"Tròn D={inp.cx:.0f} mm")
    n_bar = len(sec.rebars)
    dias = sorted(set(r.dia for r in sec.rebars))
    dia_txt = "/".join(f"{d:.0f}" for d in dias)
    A(f"  ▪ Cốt thép: {n_bar} thanh d{dia_txt}, As = {res.steel_area:.0f} mm², "
      f"μ = {_f(res.reinforcement_ratio * 100)}%\n", "card")
    b.line("Diện tích bê tông A",
           f"A = {_f(sec.gross_area, 0)} mm²",
           f"{_f(sec.gross_area / 1e6, 4)} m²")
    b.line("Mô men quán tính Ix",
           f"Ix = {_f(res.Ix, 3)} mm⁴", "")
    b.line("Mô men quán tính Iy",
           f"Iy = {_f(res.Iy, 3)} mm⁴", "")
    b.line("Bán kính quán tính ix / iy",
           f"ix = {_f(res.ix, 1)} mm, iy = {_f(res.iy, 1)} mm", "")

    # ---- 3. Chiều dài tính toán ----
    b.section(3, "CHIỀU DÀI TÍNH TOÁN & ĐỘ MẢNH",
              "TCVN 5574:2018 Mục 8.1.2.4")
    b.line("L0x", f"L0x = {_f(res.L0x)} m", "")
    b.line("L0y", f"L0y = {_f(res.L0y)} m", "")
    okx = "ĐẠT" if res.lambda_x <= 120 else "KHÔNG ĐẠT"
    oky = "ĐẠT" if res.lambda_y <= 120 else "KHÔNG ĐẠT"
    b.line("Độ mảnh λx",
           f"λx = L0x/ix = {_f(res.lambda_x, 1)} ≤ 120",
           okx, "")
    b.line("Độ mảnh λy",
           f"λy = L0y/iy = {_f(res.lambda_y, 1)} ≤ 120",
           oky, "")
    buck_x = res.lambda_x > 14
    buck_y = res.lambda_y > 14
    A(f"  ▪ Uốn dọc phương X: {'BẮT BUỘC XÉT' if buck_x else 'không cần xét'} "
      f"(λx {'>' if buck_x else '≤'} 14)\n", "card")
    A(f"  ▪ Uốn dọc phương Y: {'BẮT BUỘC XÉT' if buck_y else 'không cần xét'} "
      f"(λy {'>' if buck_y else '≤'} 14)\n", "card")

    # ---- 4. Độ lệch tâm ----
    b.section(4, "ĐỘ LỆCH TÂM", "TCVN 5574:2018 Mục 8.1.2.2.4")
    b.line("e12 = |M2|/N", f"= {_f(abs(res.My) * 1000 / max(abs(res.N), 1e-9), 1)} mm",
           f"{_f(res.e1x, 1)} mm")
    b.line("e13 = |M3|/N", "", f"{_f(res.e1y, 1)} mm")
    b.line("ea2 / ea3 (ngẫu nhiên)", "",
           f"{_f(res.eax, 1)} / {_f(res.eay, 1)} mm")
    b.line("e0x / e0y (ban đầu)", "",
           f"{_f(res.e0x, 1)} / {_f(res.e0y, 1)} mm")

    # ---- 5. Uốn dọc ----
    b.section(5, "UỐN DỌC & PHÓNG ĐẠI MÔ MEN", "CT (44)–(48)")
    phi_txt = "2.00 (thiên về an toàn)" if not inp.long_term.has_data else _f(res.phi_L)
    A(f"  ▪ φL = {phi_txt}\n", "card")
    b.line("δe,x / δe,y", "", f"{_f(res.delta_ex, 3)} / {_f(res.delta_ey, 3)}")
    b.line("kb,x / kb,y", "", f"{_f(res.kbx, 3)} / {_f(res.kby, 3)}")
    b.line("D2 / D3", "", f"{_f(res.Dx, 1)} / {_f(res.Dy, 1)} kN·m²")
    b.line("Ncr,2 / Ncr,3", "", f"{_f(res.Ncrx, 1)} / {_f(res.Ncry, 1)} kN")
    b.line("η2 / η3", "", f"{_f(res.etax, 3)} / {_f(res.etay, 3)}")
    b.line("M2* = η2·M2", "", f"{_f(res.Mx_star, 1)} kN·m")
    b.line("M3* = η3·M3", "", f"{_f(res.My_star, 1)} kN·m")

    # ---- 6. NDM ----
    b.section(6, "KIỂM TRA THEO MÔ HÌNH PHI TUYẾN (NDM)",
              "TCVN 5574:2018 Điều 8.1.2.7")
    Ma = math.hypot(res.Mx_star, res.My_star)
    alpha = math.degrees(math.atan2(res.My_star, res.Mx_star)) if Ma > 1e-9 else 0
    A(f"  ▪ Điểm tải trọng A = (M2*, M3*, N) = "
      f"({_f(res.Mx_star, 1)}, {_f(res.My_star, 1)}, {_f(res.N, 1)})\n", "card")
    A(f"  ▪ Điểm giới hạn B = ({_f(res.Bx, 1)}, {_f(res.By, 1)}, "
      f"{_f(res.BN, 1)}) trên mặt tương tác\n", "card")
    A(f"  ▪ Góc uốn xiên α = {_f(alpha, 1)}°, Mα = {_f(Ma, 1)} kN·m\n", "card")
    b.nl()
    A("  TỶ SỐ SỬ DỤNG (D/C) = ", "result")
    A(f"{_f(res.dc, 3)}", "dc")
    A(f"   (FS = {_f(res.fs, 2)})\n", "result")
    b.nl()
    if res.ok:
        A("  ✓ ĐẠT — D/C ≤ 1.000", "ok")
    else:
        A("  ✗ KHÔNG ĐẠT — D/C > 1.000", "ng")
    b.nl(2)
    return b



def generate_report(inp: ColumnInput, res: CheckResult) -> List[Seg]:
    """Trả về list segments phẳng (dùng cho PDF, text thuần)."""
    return _build_report(inp, res).build()


def generate_report_sections(inp: ColumnInput, res: CheckResult) -> dict:
    """Trả về dict {num: {title, ref, segs}} cho từng mục."""
    return _build_report(inp, res).build_sections()


def generate_report_text(inp: ColumnInput, res: CheckResult) -> str:
    """Tương thích ngược: trả về text thuần."""
    return "".join(t for t, _ in generate_report(inp, res))
