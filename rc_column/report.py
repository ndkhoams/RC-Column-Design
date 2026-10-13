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
        # Gọn 1 hàng: ▪ Label: formula = value (result)
        txt = f"  ▪ {label}"
        if formula:
            txt += f": {formula}"
        if value:
            txt += f" = {value}"
        if result:
            txt += f"  {result}"
        self.add(txt + "\n", "card")

    def build(self) -> List[Seg]:
        return self.segs

    def build_sections(self) -> dict:
        return self.sections


def _build_report(inp: ColumnInput, res: CheckResult,
                  case_info=None, shear_info=None) -> ReportBuilder:
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
    b.line("Bê tông chịu nén R_{b}*",
           f"R_{{b}}* = γ_{{b}} · R_{{b}} = {_f(inp.gamma_b)} × {_f(conc.grade.Rb)}",
           f"{_f(conc.Rb)} MPa")
    b.line("Mô đun đàn hồi bê tông E_{b}",
           f"E_{{b}} ({inp.concrete_grade})",
           f"{conc.Eb:.0f} MPa")
    b.line("Thép chịu kéo R_{s}",
           f"R_{{s}} = {_f(steel.grade.Rs)} × {_f(inp.gamma_s)} (γ_{{s}})",
           f"{_f(steel.Rs)} MPa")
    b.line("Thép chịu nén R_{sc}", "", f"{_f(steel.Rsc)} MPa")
    b.line("Mô đun đàn hồi thép E_{s}", "", f"{steel.Es:.0f} MPa")
    b.line("Tỷ số mô đun α_{e}",
           f"α_{{e}} = E_{{s}} / E_{{b}} = {steel.Es:.0f} / {conc.Eb:.0f}",
           f"{_f(res.alpha_e)}")
    b.line("Biến dạng giới hạn",
           f"ε_{{b1}} = {EPS_B1}, ε_{{b2}} = {EPS_B2}, ε_{{s2}} = {EPS_S2}",
           "MH3ĐT" if inp.concrete_model == "3line" else "MH2ĐT")
    # Mác thép đai (chuyển từ mục 7)
    from .materials import STEEL_GRADES as _SG1
    _swg1 = _SG1.get(inp.sw_steel_grade, _SG1["CB400-V"])
    A(f"  ▪ Mác thép đai: {_swg1.name}\n", "card")

    # ---- 2. Hình học ----
    b.section(2, "ĐẶC TRƯNG HÌNH HỌC TIẾT DIỆN",
              f"{'Chữ nhật' if inp.section_type == 'rect' else 'Tròn'} "
              f"{inp.cx:.0f}×{inp.cy:.0f} mm" if inp.section_type == "rect"
              else f"Tròn D={inp.cx:.0f} mm")
    from collections import Counter as _Counter
    _cnt = _Counter((r.layer, r.dia) for r in sec.rebars)
    _compo = " + ".join(
        f"{_cnt[k]}d{k[1]:.0f}"
        for k in sorted(_cnt, key=lambda k: (k[0], -k[1])))
    n_bar = len(sec.rebars)
    A(f"  ▪ Cốt thép: {n_bar} thanh ({_compo}), As = {res.steel_area:.0f} mm², "
      f"μ = {_f(res.reinforcement_ratio * 100)}%\n", "card")
    if inp.section_type == "rect" and inp.rebar_mode != "custom":
        A(f"      Lớp 1: 4d{inp.corner_dia:.0f} (góc)"
          f" + {inp.edge_t2_count}d{inp.edge_t2_dia:.0f}/mặt cạnh t2"
          f" + {inp.edge_t3_count}d{inp.edge_t3_dia:.0f}/mặt cạnh t3\n",
          "card")
        if inp.two_layer:
            _m = inp.layer2_mode
            if _m == "perimeter":
                _t2 = (f"Lớp 2 (chu vi): d{inp.l2_t2_dia:.0f}/cạnh t2,"
                       f" d{inp.l2_t3_dia:.0f}/cạnh t3 (số thanh = lớp 1)")
            elif _m == "concentrated":
                _t2 = (f"Lớp 2 (tập trung): {inp.l2_count}d{inp.l2_dia:.0f}/mặt"
                       f" cạnh {inp.l2_side}, s = {inp.l2_s_layer:.0f} mm")
            else:
                _t2 = (f"Lớp 2 (ghép bó): {inp.bundle_size} thanh/bó tại cạnh,"
                       f" {inp.bundle_corner} thanh/bó tại góc"
                       f" ({'lớp trong' if inp.bundle_pos == 'inner' else 'cùng lớp ngoài'})")
            A(f"      {_t2}\n", "card")
    b.line("Diện tích bê tông A",
           f"A = {_f(sec.gross_area, 0)} mm²",
           f"{_f(sec.gross_area / 1e6, 4)} m²")
    b.line("Mô men quán tính I_{2}",
           f"I_{{2}} = {_f(res.Ix, 3)} mm⁴", "")
    b.line("Mô men quán tính I_{3}",
           f"I_{{3}} = {_f(res.Iy, 3)} mm⁴", "")
    b.line("Bán kính quán tính i_{2} / i_{3}",
           f"i_{{2}} = {_f(res.ix, 1)} mm, i_{{3}} = {_f(res.iy, 1)} mm", "")
    # Đường kính / khoảng cách thép đai (chuyển từ mục 7)
    A(f"  ▪ Cốt đai: φ{inp.sw_dia:.0f}, bước s = {inp.sw_spacing:.0f} mm, "
      f"{inp.sw_legs} nhánh\n", "card")

    # ---- 3. Chiều dài tính toán ----
    b.section(3, "CHIỀU DÀI TÍNH TOÁN & ĐỘ MẢNH",
              "TCVN 5574:2018 Mục 8.1.2.4")
    b.line("L_{02}", f"L_{{02}} = {_f(res.L0x)} m", "")
    b.line("L_{03}", f"L_{{03}} = {_f(res.L0y)} m", "")
    okx = "ĐẠT" if res.lambda_x <= 120 else "KHÔNG ĐẠT"
    oky = "ĐẠT" if res.lambda_y <= 120 else "KHÔNG ĐẠT"
    b.line("Độ mảnh λ_{2}",
           f"λ_{{2}} = L_{{02}}/i_{{2}} = {_f(res.lambda_x, 1)} ≤ 120",
           okx, "")
    b.line("Độ mảnh λ_{3}",
           f"λ_{{3}} = L_{{03}}/i_{{3}} = {_f(res.lambda_y, 1)} ≤ 120",
           oky, "")
    buck_x = res.lambda_x > 14
    buck_y = res.lambda_y > 14
    A(f"  ▪ Uốn dọc trục 2: {'BẮT BUỘC XÉT' if buck_x else 'không cần xét'} "
      f"(λ_{{2}} {'>' if buck_x else '≤'} 14)\n", "card")
    A(f"  ▪ Uốn dọc trục 3: {'BẮT BUỘC XÉT' if buck_y else 'không cần xét'} "
      f"(λ_{{3}} {'>' if buck_y else '≤'} 14)\n", "card")

    # ---- 4. Độ lệch tâm ----
    b.section(4, "ĐỘ LỆCH TÂM", "TCVN 5574:2018 Mục 8.1.2.2.4")
    if case_info:
        A(f"  ▪ Tổ hợp tính toán: {case_info['case']}@{case_info['station']:.2f} — "
          f"N = {_f(case_info['N'], 1)} kN, "
          f"M2 = {_f(case_info['M2'], 1)} kN·m, "
          f"M3 = {_f(case_info['M3'], 1)} kN·m\n", "card")
    b.line("e_{12} = |M_{2}|/N", f"= {_f(abs(res.My) * 1000 / max(abs(res.N), 1e-9), 1)} mm",
           f"{_f(res.e1x, 1)} mm")
    b.line("e_{13} = |M_{3}|/N", "", f"{_f(res.e1y, 1)} mm")
    b.line("e_{a2} / e_{a3} (ngẫu nhiên)", "",
           f"{_f(res.eax, 1)} / {_f(res.eay, 1)} mm")
    b.line("e_{02} / e_{03} (ban đầu)", "",
           f"{_f(res.e0x, 1)} / {_f(res.e0y, 1)} mm")

    # ---- 5. Uốn dọc ----
    b.section(5, "UỐN DỌC & PHÓNG ĐẠI MÔ MEN", "CT (44)–(48)")
    phi_txt = "2.00 (thiên về an toàn)" if not inp.long_term.has_data else _f(res.phi_L)
    A(f"  ▪ φ_{{L}} = {phi_txt}\n", "card")
    # Công thức dạng Mathtype: subscript Unicode ₂₃
    b.line("δ_{e2} / δ_{e3}", "", f"{_f(res.delta_ex, 3)} / {_f(res.delta_ey, 3)}")
    b.line("k_{b2} / k_{b3}", "", f"{_f(res.kbx, 3)} / {_f(res.kby, 3)}")
    b.line("D_{2} / D_{3}", "", f"{_f(res.Dx, 1)} / {_f(res.Dy, 1)} kN·m²")
    b.line("N_{cr,2} / N_{cr,3}", "", f"{_f(res.Ncrx, 1)} / {_f(res.Ncry, 1)} kN")
    b.line("η_{2} / η_{3}", "", f"{_f(res.etax, 3)} / {_f(res.etay, 3)}")
    b.line("M_{2}* = η_{2}·M_{2}", "", f"{_f(res.Mx_star, 1)} kN·m")
    b.line("M_{3}* = η_{3}·M_{3}", "", f"{_f(res.My_star, 1)} kN·m")

    # ---- 6. NDM ----
    b.section(6, "KIỂM TRA THEO MÔ HÌNH PHI TUYẾN (NDM)",
              "TCVN 5574:2018 Điều 8.1.2.7")
    Ma = math.hypot(res.Mx_star, res.My_star)
    alpha = math.degrees(math.atan2(res.My_star, res.Mx_star)) if Ma > 1e-9 else 0
    A(f"  ▪ Điểm tải trọng A = (M_{{2}}*, M_{{3}}*, N) = "
      f"({_f(res.Mx_star, 1)}, {_f(res.My_star, 1)}, {_f(res.N, 1)})\n", "card")
    A(f"  ▪ Điểm giới hạn B = ({_f(res.Bx, 1)}, {_f(res.By, 1)}, "
      f"{_f(res.BN, 1)}) trên mặt tương tác\n", "card")
    A(f"  ▪ Góc uốn xiên α = {_f(alpha, 1)}°, M_{{α}} = {_f(Ma, 1)} kN·m\n", "card")
    b.nl()
    A(f"  TỶ SỐ SỬ DỤNG (D/C) = {_f(res.dc, 3)}  "
      f"(FS = {_f(res.fs, 2)})\n", "dc")
    b.nl()
    if res.ok:
        A("  ✓ ĐẠT — D/C ≤ 1.000", "ok")
    else:
        A("  ✗ KHÔNG ĐẠT — D/C > 1.000", "ng")
    b.nl(2)

    # --- Mục 7: Kiểm tra cốt thép đai (TCVN 5574:2018 10.3.4 & 8.1.3) ---
    from .stirrup import StirrupInput, check_stirrup, check_shear
    import math as _m
    stir_in = StirrupInput(dia=inp.sw_dia, spacing=inp.sw_spacing,
                           legs=inp.sw_legs)
    stir_res = check_stirrup(sec, stir_in, inp.concrete_grade)
    b.section(7, "KIỂM TRA CỐT THÉP ĐAI",
              "TCVN 5574:2018 Mục 10.3.4 & 8.1.3")
    A("  — Cấu tạo (10.3.4):\n", "card")
    for chk in stir_res.checks:
        mark = "✓" if chk.ok else "✗"
        A(f"  {mark} {chk.item}: yêu cầu {chk.required}, "
          f"chọn {chk.provided}\n", "card")
    # — Chịu cắt (TCVN 5574:2018, như bảng Excel mẫu) —
    from .materials import STEEL_GRADES
    sw_grade = STEEL_GRADES.get(inp.sw_steel_grade, STEEL_GRADES["CB400-V"])
    if shear_info:
        q2i, q3i = shear_info["q2"], shear_info["q3"]
        A(f"  ▪ Lực cắt tính toán: "
          f"Q2 = {_f(q2i['Q'], 1)} kN ({q2i['case']}@{q2i['station']:.2f}), "
          f"Q3 = {_f(q3i['Q'], 1)} kN ({q3i['case']}@{q3i['station']:.2f})\n",
          "card")
    Rb = conc.Rb
    Rbt = conc.Rbt
    Rsw = sw_grade.Rsw * inp.gamma_s
    Asw_1 = _m.pi * stir_in.dia ** 2 / 4  # 1 nhánh
    # Phương 2: b = t3 (cx), h0 = t2 - cover - sw_dia - bar_dia/2
    h0_2 = sec.cy - inp.cover - stir_in.dia - inp.bar_dia / 2
    # Phương 3: b = t2 (cy), h0 = t3 - cover - sw_dia - bar_dia/2
    h0_3 = sec.cx - inp.cover - stir_in.dia - inp.bar_dia / 2
    shear_ok = True
    for Q, b_w, h0, dnum in ((inp.Q2, sec.cx, h0_2, "2"),
                             (inp.Q3, sec.cy, h0_3, "3")):
        Asw = Asw_1 * stir_in.legs
        h0u = max(h0, 1)
        sh = check_shear(Q, b_w, h0u, Rb, Rbt, Asw, Rsw,
                         stir_in.spacing, direction=dnum)
        m1 = "✓" if sh.ok1 else "✗"
        m2 = "✓" if sh.ok2 else "✗"
        # Diễn giải công thức
        qsw = Rsw * Asw / stir_in.spacing if stir_in.spacing > 0 else 0
        Qb_lim_lo = 0.5 * Rbt * b_w * h0u / 1000.0
        Qb_lim_hi = 2.5 * Rbt * b_w * h0u / 1000.0
        A(f"  Phương {dnum}: Q = {_f(Q, 1)} kN; "
          f"b = {b_w:.0f} mm, h_{{0}} = {h0u:.0f} mm, "
          f"A_{{sw}} = {stir_in.legs}×φ{stir_in.dia:.0f} = {Asw:.0f} mm²\n",
          "card")
        A(f"    {m1} ĐK1 (dải nén xiên): Q ≤ 0.3×R_{{b}}×b×h_{{0}}\n", "card")
        A(f"       = 0.3×{_f(Rb, 2)}×{b_w:.0f}×{h0u:.0f}/1000 "
          f"= {_f(sh.Qcap1, 1)} kN\n", "card")
        A(f"    {m2} ĐK2 (vết nứt xiên): Q ≤ Q_{{b}} + Q_{{sw}}\n", "card")
        A(f"       q_{{sw}} = R_{{sw}}×A_{{sw}}/s = {_f(Rsw, 0)}×{Asw:.0f}/{stir_in.spacing:.0f}"
          f" = {_f(qsw, 1)} N/mm\n", "card")
        A(f"       Q_{{b}} = φ_{{b2}}×R_{{bt}}×b×h_{{0}}²/C = 1.5×{_f(Rbt, 2)}×{b_w:.0f}×{h0u:.0f}²"
          f"/{sh.C_opt:.0f}/1000 = {_f(sh.Qb_opt, 1)} kN\n", "card")
        A(f"       (giới hạn Q_{{b}} ∈ [{_f(Qb_lim_lo, 1)}, {_f(Qb_lim_hi, 1)}] kN)\n",
          "card")
        A(f"       Q_{{sw}} = φ_{{sw}}×q_{{sw}}×C = 0.75×{_f(qsw, 1)}×{sh.C_opt:.0f}/1000 "
          f"= {_f(sh.Qsw_opt, 1)} kN\n", "card")
        A(f"       → [Q]min = {_f(sh.Qcap2, 1)} kN tại C = {sh.C_opt:.0f} mm "
          f"(khảo sát C ∈ [h0, 2h0])\n", "card")
        shear_ok &= sh.ok
    if stir_res.ok and shear_ok:
        A("  ✓ ĐẠT — Cốt đai thỏa TCVN 5574:2018", "ok")
    else:
        A("  ✗ KHÔNG ĐẠT — Xem lại cốt đai", "ng")
    b.nl(2)
    return b



def generate_report(inp: ColumnInput, res: CheckResult) -> List[Seg]:
    """Trả về list segments phẳng (dùng cho PDF, text thuần)."""
    return _build_report(inp, res).build()


def generate_report_sections(inp: ColumnInput, res: CheckResult,
                             batch_rows=None, case_info=None,
                             shear_info=None) -> dict:
    """Trả về dict {num: {title, ref, segs}} cho từng mục.
    batch_rows: list of (force, result_dict) cho mục 8 (tùy chọn).
    case_info: dict {case, station, N, M2, M3} cho dòng tổ hợp tính toán.
    shear_info: dict {q2: {case, station, Q}, q3: {...}} cho lực cắt."""
    builder = _build_report(inp, res, case_info, shear_info)
    if batch_rows:
        _build_section7(builder, batch_rows)
    return builder.build_sections()


def _build_section7(b: "ReportBuilder", batch_rows):
    """Mục 8: Bảng tổng hợp kết quả tất cả tổ hợp (có lưới)."""
    b.section(8, "BẢNG TỔNG HỢP KẾT QUẢ KIỂM TRA", "Tất cả tổ hợp")
    # Header
    hdr = ("Tổ hợp", "N (kN)", "M2 (kN·m)", "M3 (kN·m)", "D/C", "KQ")
    rows = []
    for f, r in batch_rows:
        dc = r["dc"]
        ok = "ĐẠT" if dc <= 1 else "KHÔNG ĐẠT"
        rows.append((f"{f.case}@{f.station:.2f}", f"{f.N:.0f}",
                     f"{f.Mx:.0f}", f"{f.My:.0f}", f"{dc:.3f}", ok))
    # Tính độ rộng cột
    widths = [len(h) for h in hdr]
    for row in rows:
        for i, c in enumerate(row):
            widths[i] = max(widths[i], len(c))
    def line(ch="-"):
        return "+" + "+".join(ch * (w + 2) for w in widths) + "+\n"
    def fmt_row(cells):
        return "|" + "|".join(f" {c:<{w}} " for c, w in zip(cells, widths)) + "|\n"
    b.add(line("="), "mono")
    b.add(fmt_row(hdr), "mono")
    b.add(line("="), "mono")
    for row in rows:
        b.add(fmt_row(row), "mono")
        b.add(line("-"), "mono")
    b.nl()


def generate_report_text(inp: ColumnInput, res: CheckResult) -> str:
    """Tương thích ngược: trả về text thuần."""
    return "".join(t for t, _ in generate_report(inp, res))
