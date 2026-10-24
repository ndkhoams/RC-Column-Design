"""Nội dung "Chi tiết tính toán" vách TCVN — NGUỒN DUY NHẤT cho cả
tab Chi tiết app (Tk, qua report_widgets.render_report_sections) và
PDF chi tiết vách (ReportLab, qua wall_pdf_report).

QUY TẮC (theo AGENTS.md + spec detail_format_spec.md §4/§4b/§4c):
- Mọi số đọc từ dict kết quả của wall_tcvn_full (đã tính 1 lần),
  KHÔNG tính lại engine. Các phép hiển thị duy nhất là số học trực
  tiếp trên số đã lưu (vd e1 = |M|/N, i = h/√12, |B| = hypot(Bx, By),
  Mx* theo quy trình chuẩn = N·e0/1000) — không gọi lại solver.
- Nhãn app: X = trong mặt phẳng (theo Lw), Y = ngoài mặt phẳng
  (theo tw). Trang web Vietcons gắn nhãn độ lệch tâm ĐẢO ngược
  (xem ghi chú mục 4) — KHÔNG copy nhãn web, KHÔNG đổi engine.
- Thẻ η trình bày ĐÚNG đường tính thật của app (η từ
  buckling_factors khi bật P–δ, ĐÃ CÓ cổng λ > 14 theo
  TCVN §8.1.2.1.2 — phương án A user chốt 2026-10-24, thay phương
  án B cũ): phương λ ≤ 14 ghi giá trị áp dụng η = 1,0 kèm căn cứ
  §8.1.2.1.2, KHÔNG còn khối đối chiếu "app vs quy trình chuẩn"
  (nay hai bên khớp nhau); phương λ > 14 giữ nguyên cách trình
  bày theo CT (44)–(48).
- Trích dẫn độ mảnh: "TCVN 5574:2018 Mục 10.2.2", KHÔNG ghi "Bảng 30"
  (đã xác minh là sai địa chỉ). Giới hạn độ mảnh áp dụng cho vách
  là 120 theo TCVN 5574:2018 §10.2.2 (user chốt 2026-10-24).
- KHÔNG có banner/kết luận chung: mỗi phần kết luận riêng ngay
  dưới phần đó (mục 3 độ mảnh, mục 6 N–M, mục 7 diễn giải lại
  N–M, mục 8 cắt trong/ngoài MP + trượt CHƯA KIỂM, mục 9 chỉ
  phạm vi + phần CHƯA KIỂM). Khóa "ok_all" vẫn giữ trong dict
  kết quả (= ok N–M) chỉ để tương thích file/code cũ — không
  còn render thành banner và không được dùng làm kết luận tổng.
"""

import math

from .cover_migration import cover_long


def _f(x, nd=1):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(v):
        return "∞" if v > 0 else ("-∞" if v < 0 else "—")
    return f"{v:,.{nd}f}"


def _fm(x):
    """Cường độ tra bảng: cắt số 0 thừa (như pdf_export._fm)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(v):
        return "—"
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _wrap(text, width=95):
    """Tách một ghi chú dài thành nhiều dòng ≤ width ký tự (để card
    Tk không bị tràn; PDF tự ngắt dòng lại nên không hại)."""
    words = str(text).split()
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]


def _card(title, ref, lines, result=""):
    return {"title": title, "ref": ref, "lines": list(lines),
            "result": result}


def _lam_badge(lam):
    """Badge độ mảnh theo giới hạn 120 (TCVN 5574:2018 §10.2.2,
    user chốt 2026-10-24). Chỉ là câu chữ hiển thị — không tham
    gia kết luận N–M của engine."""
    if lam <= 120.0:
        return f"λ = {_f(lam, 2)} ≤ 120: ĐẠT"
    return f"λ = {_f(lam, 2)} > 120: KHÔNG ĐẠT"


def _slend_conclusion_card(lam_in, lam_out):
    """Thẻ kết luận cuối mục 3: độ mảnh ĐẠT chỉ khi CẢ 2 phương
    ≤ 120 (TCVN 5574:2018 §10.2.2). Đây là kết luận độ mảnh
    riêng — §10.2.2 dùng chữ “nên”, không phải điều kiện bền,
    nên không đổi kết luận N–M ở mục 6."""
    ok = lam_in <= 120.0 and lam_out <= 120.0
    if ok:
        lines = [f"λx = {_f(lam_in, 2)} ≤ 120 và λy = {_f(lam_out, 2)} "
                 "≤ 120 → cả 2 phương đều trong giới hạn.",
                 "§10.2.2 dùng chữ “nên”, không phải điều kiện bền "
                 "— kết luận này không đổi kết luận N–M (mục 6)."]
        result = "Kết luận độ mảnh: ĐẠT (λ ≤ 120)"
    else:
        _bad = []
        if lam_in > 120.0:
            _bad.append(f"λx = {_f(lam_in, 2)} > 120")
        if lam_out > 120.0:
            _bad.append(f"λy = {_f(lam_out, 2)} > 120")
        lines = ["; ".join(_bad) + " → vượt giới hạn độ mảnh.",
                 "§10.2.2 dùng chữ “nên”, không phải điều kiện bền "
                 "— kết luận này không đổi kết luận N–M (mục 6)."]
        result = "Kết luận độ mảnh: KHÔNG ĐẠT (λ > 120)"
    card = _card("Kết luận độ mảnh", "TCVN 5574:2018 Mục 10.2.2",
                 lines, result)
    card["full"] = True
    return card


def _m2m3_reinterpret_card(full):
    """Thẻ diễn giải cuối mục 7: M2–M3 chỉ là lát cắt tại N = BN
    của cùng mặt tương tác N–M (mục 6) nên KHÔNG tự tạo thêm
    một ĐẠT/KHÔNG ĐẠT độc lập — chỉ diễn giải lại kết luận N–M
    cùng D/C đó."""
    dc_val = float(full["dc"])
    ok_nm = bool(full["ok"])
    card = _card(
        "Diễn giải kết luận M2–M3",
        "Cùng khả năng N–M (mục 6)",
        ["M2–M3 chỉ là lát cắt tại N = BN của cùng mặt tương tác "
         "N–M ở mục 6, không phải kiểm tra độc lập.",
         "Vì vậy không tự tạo thêm một ĐẠT/KHÔNG ĐẠT mới có thể "
         "mâu thuẫn N–M: diễn giải lại kết luận N–M cùng D/C đó "
         "(không phải kết luận độc lập)."],
        f"Diễn giải M2–M3: cùng kết luận N–M — "
        f"D/C = {_f(dc_val, 3)} — "
        f"{'ĐẠT' if ok_nm else 'KHÔNG ĐẠT'}")
    card["full"] = True
    return card


def _eta_card(direction, lam, L0_m, h_mm, N, e0, ea, eta, Ncr,
              M_star, M_orig, pd_method, phi_L):
    """Thẻ hệ số uốn dọc 1 phương. direction: 'X' (trong MP) hoặc
    'Y' (ngoài MP). M_star/M_orig: mô men đã/ chưa phóng đại của
    phương đó (M_in_d/M_in cho X, M_out_d/M_out cho Y)."""
    if direction == "X":
        title = "η & mô men phóng đại — Phương X (trong MP)"
        m_sym, m_star_sym = "M3", "M3*"
        ref = "Mục 8.1.2.1.2 & 8.1.2.4.2"
    else:
        title = "η & mô men phóng đại — Phương Y (ngoài MP)"
        m_sym, m_star_sym = "M2", "M2*"
        ref = "Mục 8.1.2.1.2 & 8.1.2.4.2"
    if pd_method == "none":
        lines = [
            f"Ncr = {_f(Ncr, 0)} kN (chỉ để đối chiếu);  "
            f"φL = {_f(phi_L, 2)}",
            "Phương pháp mục 4: KHÔNG xét bổ sung uốn dọc "
            "(η = 1 cả 2 phương).",
        ]
        if direction == "X":
            lines.append(
                f"{m_star_sym} = N × e0x × ηx / 1000 "
                f"= {_f(N, 1)} × {_f(e0, 2)} × 1.000 / 1000 "
                f"(sàn lệch tâm e0 trong MP vẫn áp)")
        else:
            lines.append(f"{m_star_sym} = {m_sym} (không nhân η)")
        result = f"{m_star_sym} = {_f(M_star, 2)} kN·m (η = 1,000)"
        return _card(title, ref, lines, result)
    # P–δ bật: η đã qua cổng §8.1.2.1.2 trong buckling_factors
    # (λ > 14 mới nhân η, từng phương độc lập — chung luật với cột).
    if lam is not None and lam <= 14.0:
        # Phương bị cổng: giá trị áp dụng là η = 1,0 — KHÔNG còn
        # khối đối chiếu "app vs quy trình chuẩn" (nay hai bên khớp
        # nhau theo phương án A); Ncr chỉ để đối chiếu.
        lines = [
            f"Ncr = {_f(Ncr, 0)} kN (chỉ để đối chiếu);  "
            f"φL = {_f(phi_L, 2)}",
            f"λ = {_f(lam, 2)} ≤ 14 → theo 8.1.2.1.2 không nhân η: "
            f"η = 1,000.",
        ]
        if direction == "X":
            if N > 0:
                lines.append(
                    f"{m_star_sym} = N × e0x × ηx / 1000 "
                    f"= {_f(N, 1)} × {_f(e0, 2)} × 1.000 / 1000 "
                    f"(sàn lệch tâm e0 trong MP vẫn áp)")
            else:
                lines.append(
                    f"{m_star_sym} = {m_sym} (N ≤ 0: không dựng mô men "
                    f"từ sàn lệch tâm; η = 1,000)")
        else:
            lines.append(
                f"{m_star_sym} = ηy × {m_sym} "
                f"= 1.000 × {_f(M_orig, 2)}")
        result = f"{m_star_sym} = {_f(M_star, 2)} kN·m (η = 1,000)"
        return _card(title, ref, lines, result)
    lines = [
        f"η = 1 / (1 − N / Ncr) = 1 / (1 − {_f(N, 1)} / {_f(Ncr, 0)})",
        f"Ncr = {_f(Ncr, 0)} kN;  φL = {_f(phi_L, 2)}",
    ]
    if direction == "X":
        lines.append(
            f"{m_star_sym} = N × e0x × ηx / 1000 "
            f"= {_f(N, 1)} × {_f(e0, 2)} × {_f(eta, 3)} / 1000")
    else:
        lines.append(
            f"{m_star_sym} = ηy × {m_sym} "
            f"= {_f(eta, 3)} × {_f(M_orig, 2)}")
    result = f"{m_star_sym} = {_f(M_star, 2)} kN·m (η = {_f(eta, 3)})"
    if lam is not None:
        lines.append(
            f"λ = {_f(lam, 2)} > 14 → xét uốn dọc theo 8.1.2.1.2; "
            f"η theo CT (44)–(48).")
    return _card(title, ref, lines, result)


def build_wall_detail_sections(full):
    """Dựng các mục chi tiết từ dict kết quả wall_tcvn_full.

    Trả về list section dict {num, title, ref, cards} tương thích
    report_widgets.render_report_sections (Tk) và wall_pdf_report
    (ReportLab) — CÙNG nội dung và số, chỉ khác vật chứa.
    """
    winp = full["winp"]
    sec = full["sec"]
    meta = full.get("meta") or {}
    sl = full["slend"]
    conc = sec.concrete
    steel = sec.steel
    N = float(full["N"])
    M_in = float(full["M_in"])
    M_out = float(full["M_out"])
    V_in = float(full["V_in"])
    V_out = float(full["V_out"])
    Lw_eff = float(sec.cx)
    tw_eff = float(sec.cy)
    Ag = Lw_eff * tw_eff
    As = float(sec.steel_area)
    mu = float(sec.reinforcement_ratio) * 100.0
    rot = int(getattr(winp, "rot_deg", 0) or 0) % 360
    mode = str(meta.get("steel_mode") or getattr(winp, "steel_mode",
                                                 "boundary"))
    mode_txt = {"perimeter": "Phân bố đều theo chu vi",
                "boundary": "Tập trung vùng biên"}.get(mode, "Lát 1 cũ")
    pd_method = str(sl.get("pd_method") or "tcvn")

    # Độ lệch tâm tĩnh học (hiển thị từ N/M đã lưu; engine dùng
    # đúng công thức này trong stability.eccentricities).
    if N > 0:
        e1_in = abs(M_in) * 1000.0 / N
        e1_out = abs(M_out) * 1000.0 / N
    else:
        e1_in = None
        e1_out = None
    e0_in = float(full["e0_in"])
    ea_in = float(full["ea_in"])
    e0_out = float(full["e0_out"])
    ea_out = float(full["ea_out"])
    Lx_m = float(sl.get("Lx_m", 0.0) or 0.0)
    Ly_m = float(sl.get("Ly_m", 0.0) or 0.0)
    psi_x = float(sl.get("psi_x", 0.0) or 0.0)
    psi_y = float(sl.get("psi_y", 0.0) or 0.0)
    l0_in_m = float(sl.get("l0_in", 0.0) or 0.0) / 1000.0
    l0_out_m = float(sl.get("l0_out", 0.0) or 0.0) / 1000.0
    lam_in = float(sl.get("lambda_in", 0.0) or 0.0)
    lam_out = float(sl.get("lambda_out", 0.0) or 0.0)
    ix = Lw_eff / math.sqrt(12.0)
    iy = tw_eff / math.sqrt(12.0)
    L0h_in = l0_in_m / (Lw_eff / 1000.0) if Lw_eff > 0 else 0.0
    L0h_out = l0_out_m / (tw_eff / 1000.0) if tw_eff > 0 else 0.0

    sections = []

    # ================= MỤC 1: VẬT LIỆU =================
    conc_lines = [
        f"Rb = γb × Rb,bảng = {_fm(conc.gamma_b)} × "
        f"{_fm(conc.grade.Rb)} = {_fm(conc.Rb)} MPa",
        f"Rbt = γb × Rbt,bảng = {_fm(conc.gamma_b)} × "
        f"{_fm(conc.grade.Rbt)} = {_fm(conc.Rbt)} MPa",
        f"Eb = {_fm(conc.Eb)} MPa;  γb = {_fm(conc.gamma_b)}",
    ]
    steel_lines = [
        f"Rs = γs × Rs,bảng = {_fm(steel.gamma_s)} × "
        f"{_fm(steel.grade.Rs)} = {_fm(steel.Rs)} MPa",
        f"Rsc = γs × Rsc,bảng = {_fm(steel.gamma_s)} × "
        f"{_fm(steel.grade.Rsc)} = {_fm(steel.Rsc)} MPa",
        f"Es = {_fm(steel.Es)} MPa;  γs = {_fm(steel.gamma_s)}",
        f"Mô hình bê tông: {full.get('model', '3line')}",
    ]
    sections.append({
        "num": 1, "title": "VẬT LIỆU",
        "ref": "TCVN 5574:2018 Mục 6.1 & 6.2",
        "cards": [
            _card(f"Bê tông ({conc.grade.name})",
                  "Bảng 6, Bảng 10 & Mục 6.1.2.3", conc_lines,
                  f"Rb = {_fm(conc.Rb)} MPa;  Rbt = {_fm(conc.Rbt)} MPa"),
            _card(f"Cốt thép dọc ({steel.grade.name})",
                  "Bảng 13 & Mục 6.2.2", steel_lines,
                  f"Rs = {_fm(steel.Rs)} MPa;  "
                  f"Rsc = {_fm(steel.Rsc)} MPa"),
        ]})

    # ================= MỤC 2: TIẾT DIỆN & THÉP =================
    sec_lines = [
        f"Lw × tw (hiệu dụng sau xoay {rot}°) = "
        f"{Lw_eff:.0f} × {tw_eff:.0f} mm",
    ]
    if rot in (90, 270):
        sec_lines.append(
            f"(Lw/tw nhập: {float(winp.Lw):.0f} × "
            f"{float(winp.tw):.0f} mm — đã hoán đổi khi tính)")
    sec_lines += [
        f"Ag = Lw × tw = {Ag:,.0f} mm²",
        f"Ix (trong MP) = tw × Lw³ / 12 = "
        f"{tw_eff * Lw_eff ** 3 / 12.0 / 1e12:.4g} m⁴",
        f"Iy (ngoài MP) = Lw × tw³ / 12 = "
        f"{Lw_eff * tw_eff ** 3 / 12.0 / 1e12:.4g} m⁴",
        f"Lớp bảo vệ cốt đai, c = {float(winp.cover):.0f} mm "
        f"(c_dọc = c + dia_h = "
        f"{cover_long(float(winp.cover), float(getattr(winp, 'dia_h', 0.0) or 0.0)):.0f} mm)",
    ]
    steel2_lines = [f"Chế độ: {mode_txt}"]
    layout_txt = meta.get("layout_text")
    if layout_txt:
        steel2_lines += _wrap(layout_txt)
    else:
        steel2_lines.append(
            f"{len(sec.rebars)} thanh — As = {As:,.0f} mm²")
    for zname, zn, zdia in (meta.get("zones") or []):
        from .sections import bar_area as _ba
        steel2_lines.append(
            f"{zname}: {zn} thanh d{zdia:.0f} — "
            f"As = {_ba(float(zdia)) * zn:,.0f} mm²")
    steel2_lines.append(
        f"Tổng As = {As:,.0f} mm²;  μ = {mu:.2f}%")
    for _w in (meta.get("warnings") or []):
        steel2_lines += _wrap(f"Cảnh báo bố trí: {_w}")
    sections.append({
        "num": 2, "title": "TIẾT DIỆN & BỐ TRÍ THÉP",
        "ref": "Vách chữ nhật đặc — GĐ1",
        "cards": [
            _card("Tiết diện", "", sec_lines,
                  f"{Lw_eff:.0f} × {tw_eff:.0f} mm;  "
                  f"Ag = {Ag:,.0f} mm²"),
            _card("Bố trí thép dọc", "", steel2_lines,
                  f"{len(sec.rebars)} thanh;  As = {As:,.0f} mm²;  "
                  f"μ = {mu:.2f}%"),
        ]})

    # ================= MỤC 3: L0 & ĐỘ MẢNH =================
    def _l0_card(direction):
        if direction == "X":
            return _card(
                "L0 & độ mảnh — Phương X (trong MP)",
                "Mục 8.1.2.4.4 & 10.2.2",
                [f"L0x = ψx × Lx = {_fm(psi_x)} × {_f(Lx_m, 2)} "
                 f"= {_f(l0_in_m, 3)} m ({l0_in_m * 1000.0:.0f} mm)",
                 f"ix = Lw / √12 = {Lw_eff:.0f} / 3,464 = {_f(ix, 2)} mm",
                 f"λx = L0x / ix = {l0_in_m * 1000.0:.0f} / {_f(ix, 2)} "
                 f"= {_f(lam_in, 2)}",
                 f"L0x / Lw = {_f(L0h_in, 2)}"],
                _lam_badge(lam_in))
        return _card(
            "L0 & độ mảnh — Phương Y (ngoài MP)",
            "Mục 8.1.2.4.4 & 10.2.2",
            [f"L0y = ψy × Ly = {_fm(psi_y)} × {_f(Ly_m, 2)} "
             f"= {_f(l0_out_m, 3)} m ({l0_out_m * 1000.0:.0f} mm)",
             f"iy = tw / √12 = {tw_eff:.0f} / 3,464 = {_f(iy, 2)} mm",
             f"λy = L0y / iy = {l0_out_m * 1000.0:.0f} / {_f(iy, 2)} "
             f"= {_f(lam_out, 2)}",
             f"L0y / tw = {_f(L0h_out, 2)}"],
            _lam_badge(lam_out))

    sections.append({
        "num": 3, "title": "CHIỀU DÀI TÍNH TOÁN & KIỂM TRA ĐỘ MẢNH",
        "ref": "TCVN 5574:2018 Mục 8.1.2.4.4 & Mục 10.2.2",
        "cards": [
            _l0_card("X"),
            _l0_card("Y"),
            _card("Ghi chú giới hạn độ mảnh",
                  "TCVN 5574:2018 Mục 10.2.2",
                  ["Giới hạn độ mảnh áp dụng cho vách: λ ≤ 120 "
                   "theo TCVN 5574:2018 Mục 10.2.2 "
                   "(user chốt 2026-10-24). §10.2.2 dùng chữ "
                   "“nên”, không phải điều kiện bền cứng.",
                   "Không trích dẫn “Bảng 30” cho giới hạn này — "
                   "đã xác minh là sai địa chỉ."],
                  "", ),
        ]})
    # Card ghi chú chiếm full-width trong cả 2 vật chứa.
    sections[-1]["cards"][-1]["full"] = True
    # Kết luận độ mảnh ở CUỐI mục 3 (sau ghi chú).
    sections[-1]["cards"].append(
        _slend_conclusion_card(lam_in, lam_out))

    # ================= MỤC 4: ĐỘ LỆCH TÂM =================
    def _ecc_card(direction):
        if direction == "X":
            e1_txt = (f"e1x = |M3| / N = {_f(abs(M_in), 2)} × 1000 / "
                      f"{_f(N, 1)} = {_f(e1_in, 2)} mm"
                      if e1_in is not None else
                      "e1x: N ≤ 0 — không xác định e1")
            lines = [
                e1_txt,
                f"eax = max(Lx/600, Lw/30, 10) = max("
                f"{_f(Lx_m * 1000.0 / 600.0, 2)}, "
                f"{_f(Lw_eff / 30.0, 2)}, 10) = {_f(ea_in, 2)} mm",
                f"e0x = max(e1x, eax) = {_f(e0_in, 2)} mm",
            ]
            return _card("Độ lệch tâm — Phương X (trong MP)",
                         "Mục 8.1.2.2.4", lines,
                         f"e0x = {_f(e0_in, 2)} mm")
        e1_txt = (f"e1y = |M2| / N = {_f(abs(M_out), 2)} × 1000 / "
                  f"{_f(N, 1)} = {_f(e1_out, 2)} mm"
                  if e1_out is not None else
                  "e1y: N ≤ 0 — không xác định e1")
        lines = [
            e1_txt,
            f"eay = max(Ly/600, tw/30, 10) = max("
            f"{_f(Ly_m * 1000.0 / 600.0, 2)}, "
            f"{_f(tw_eff / 30.0, 2)}, 10) = {_f(ea_out, 2)} mm",
            f"e0y = max(e1y, eay) = {_f(e0_out, 2)} mm",
        ]
        return _card("Độ lệch tâm — Phương Y (ngoài MP)",
                     "Mục 8.1.2.2.4", lines,
                     f"e0y = {_f(e0_out, 2)} mm")

    note4_lines = [
        "Ghi chú đối chiếu nhãn (không đổi nhãn app, không đổi engine):",
        "Trang web gắn nhãn độ lệch tâm ĐẢO NGƯỢC so với nhãn độ mảnh "
        "của chính nó và so với app. Ở ca này:",
    ]
    if e1_in is not None and e1_out is not None:
        note4_lines += [
            f"Cặp web gắn nhãn “X” (e1x = {_f(e1_out, 2)} mm, "
            f"eax = {_f(ea_out, 2)} mm) chính là cặp NGOÀI mặt phẳng "
            "của app (Y).",
            f"Cặp web gắn nhãn “Y” (e1y = {_f(e1_in, 2)} mm, "
            f"eay = {_f(ea_in, 2)} mm) chính là cặp TRONG mặt phẳng "
            "của app (X).",
        ]
    note4_lines.append(
        "Chi tiết này giữ nhãn app: X = trong mặt phẳng (theo Lw), "
        "Y = ngoài mặt phẳng (theo tw), với số của engine app.")
    sections.append({
        "num": 4,
        "title": "ĐỘ LỆCH TÂM TĨNH HỌC, NGẪU NHIÊN & BAN ĐẦU",
        "ref": "TCVN 5574:2018 Mục 8.1.2.2.4",
        "cards": [_ecc_card("X"), _ecc_card("Y")]})
    _note4 = _card("Đối chiếu nhãn độ lệch tâm với trang web", "",
                   note4_lines, "")
    _note4["full"] = True
    sections[-1]["cards"].append(_note4)

    # ================= MỤC 5: η & M* =================
    sections.append({
        "num": 5, "title": "HỆ SỐ UỐN DỌC & MÔ MEN PHÓNG ĐẠI",
        "ref": "TCVN 5574:2018 Mục 8.1.2.1.2 & 8.1.2.4.2",
        "cards": [
            _eta_card("X", lam_in, l0_in_m, Lw_eff, N, e0_in, ea_in,
                      float(sl.get("factor_in", 1.0) or 1.0),
                      float(sl.get("Ncr_in", 0.0) or 0.0),
                      float(full["M_in_d"]), M_in, pd_method,
                      float(full["phi_L"])),
            _eta_card("Y", lam_out, l0_out_m, tw_eff, N, e0_out, ea_out,
                      float(sl.get("factor_out", 1.0) or 1.0),
                      float(sl.get("Ncr_out", 0.0) or 0.0),
                      float(full["M_out_d"]), M_out, pd_method,
                      float(full["phi_L"])),
        ]})
    # Kết quả mục 5 ở CUỐI mục: mô men thiết kế dùng cho mục 6
    # (không phải ĐẠT/KHÔNG ĐẠT — η/M* là đầu vào, không phải
    # kiểm tra bền).
    _sec5_res = _card(
        "Kết quả mục 5 — Mô men thiết kế",
        "Dùng cho kiểm tra N–M (mục 6)",
        [f"M3* (trong MP) = {_f(float(full['M_in_d']), 2)} kN·m",
         f"M2* (ngoài MP) = {_f(float(full['M_out_d']), 2)} kN·m",
         f"α = {_f(float(full['alpha_deg']), 2)}° "
         f"(từ trục M3, chuẩn hoá [0, 360))"],
        f"Mô men dùng cho kiểm tra N–M (mục 6): "
        f"M3* = {_f(float(full['M_in_d']), 2)} kN·m;  "
        f"M2* = {_f(float(full['M_out_d']), 2)} kN·m;  "
        f"Mα = {_f(float(full['Malpha']), 2)} kN·m")
    _sec5_res["full"] = True
    sections[-1]["cards"].append(_sec5_res)

    # ================= MỤC 6: N–Mα & D/C =================
    lam_ray = float(full["lambda_ray"])
    fs_val = float(full["fs"])
    dc_val = float(full["dc"])
    ok_nm = bool(full["ok"])
    Malpha = float(full["Malpha"])
    Mcap_N = float(full["M_capacity"])
    BN = float(full["BN"])
    Bx = float(full["Bx"])
    By = float(full["By"])
    Bmag = math.hypot(Bx, By)
    c_txt = (f"{float(full['c_neutral']):.0f} mm"
             if full.get("c_neutral") is not None
             and math.isfinite(float(full["c_neutral"])) else "—")
    dc_card = _card(
        "Tỷ số sử dụng (D/C) — N–M",
        "D/C tia 3D (kết luận N–M)",
        [f"Điểm tải A: N = {_f(N, 1)} kN, Mα = {_f(Malpha, 2)} kN·m "
         f"(α = {_f(float(full['alpha_deg']), 2)}°)",
         f"Điểm giới hạn B: BN = {_f(BN, 1)} kN, "
         f"|B| = λ × Mα = {_f(lam_ray, 3)} × {_f(Malpha, 2)} "
         f"= {_f(Bmag, 2)} kN·m",
         f"Mα,u tại N tải = {_f(Mcap_N, 2)} kN·m;  "
         f"chiều cao vùng nén tại B: c = {c_txt}",
         f"Ứng suất nén mép (đàn hồi): "
         f"σ = {_f(float(full['sigma_edge']), 2)} MPa"],
        f"D/C = {_f(dc_val, 3)} (FS = {_f(fs_val, 2)}) — "
        f"{'ĐẠT' if ok_nm else 'KHÔNG ĐẠT'} (chỉ N–M)")
    dc_card["dc_conclusion"] = True
    dc_card["ok"] = ok_nm
    dc_card["dc"] = dc_val
    dc_card["fs"] = fs_val
    sections.append({
        "num": 6, "title": "MẶT TƯƠNG TÁC N–Mα & D/C",
        "ref": "TCVN 5574:2018 Mục 8.1.2 — mặt tương tác N–Mα (solver fiber)",
        "cards": [
            _card("Điểm tải A",
                  "Mô men đã phóng đại (mục 5)",
                  [f"N = {_f(N, 1)} kN",
                   f"M3* (trong MP) = {_f(float(full['M_in_d']), 2)} kN·m",
                   f"M2* (ngoài MP) = {_f(float(full['M_out_d']), 2)} kN·m",
                   f"α = {_f(float(full['alpha_deg']), 2)}° "
                   f"(từ trục M3, chuẩn hoá [0, 360))",
                   f"Mα = {_f(Malpha, 2)} kN·m"],
                  f"A: N = {_f(N, 1)} kN;  Mα = {_f(Malpha, 2)} kN·m"),
            _card("Điểm giới hạn B",
                  "Trên tia O–A–B",
                  [f"BN = {_f(BN, 1)} kN",
                   f"Bx (M2) = {_f(Bx, 2)} kN·m;  "
                   f"By (M3) = {_f(By, 2)} kN·m",
                   f"|B| = {_f(Bmag, 2)} kN·m;  λ = {_f(lam_ray, 5)}",
                   f"Chiều cao vùng nén tại B: c = {c_txt}"],
                  f"B: BN = {_f(BN, 1)} kN;  |B| = {_f(Bmag, 2)} kN·m"),
            dc_card,
        ]})
    sections[-1]["cards"][-1]["full"] = True

    # ================= MỤC 7: M2–M3 =================
    m2m3 = full.get("m2m3") or {}
    if m2m3:
        m_cards = [
            _card("Đường bao M2–M3",
                  "Trục ETABS: hoành = M3, tung = M2",
                  [f"Lát cắt tại N = BN = {_f(float(m2m3['N_level']), 1)} kN",
                   f"Số điểm đường bao: {len(m2m3['M3'])} (khép kín)",
                   "Chỉ lát cắt tại BN mới đi đúng qua B; lát cắt "
                   "tại N tải lệch B 8–19% ở các ca vách nên không dùng."],
                  f"Đường bao tại N = {_f(float(m2m3['N_level']), 1)} kN"),
            _card("Điểm A / B trên M2–M3",
                  "A = mô men thiết kế; B = điểm giới hạn",
                  [f"A: M3 = {_f(float(m2m3['A_M3']), 2)} kN·m, "
                   f"M2 = {_f(float(m2m3['A_M2']), 2)} kN·m",
                   f"B: M3 = {_f(float(m2m3['B_M3']), 2)} kN·m, "
                   f"M2 = {_f(float(m2m3['B_M2']), 2)} kN·m"],
                  f"B: ({_f(float(m2m3['B_M3']), 2)}; "
                  f"{_f(float(m2m3['B_M2']), 2)}) kN·m"),
        ]
    else:
        m_cards = [_card("Đường bao M2–M3", "",
                         ["Chưa có dữ liệu biểu đồ M2–M3 trong dict "
                          "kết quả."], "—")]
        m_cards[0]["full"] = True
    sections.append({
        "num": 7, "title": "MẶT CẮT M2–M3",
        "ref": "Lát cắt mặt tương tác tại N = BN",
        "cards": m_cards})
    # Diễn giải kết luận M2–M3 ở CUỐI mục 7 (chỉ khi có dữ liệu
    # đường bao; khi chưa có dữ liệu thì thẻ trên đã ghi rõ và
    # không kết luận gì thêm).
    if m2m3:
        sections[-1]["cards"].append(_m2m3_reinterpret_card(full))

    # ================= MỤC 8: CẮT =================
    sh = full.get("shear_in") or {}
    shp = sh.get("parts") or {}
    sh_cards = []
    if sh.get("V_cap") is not None:
        sh_lines = [
            f"V2 = {_f(V_in, 1)} kN (lực cắt trong mặt phẳng)",
        ]
        if sh.get("seismic_applied"):
            sh_lines.append(
                f"Phóng đại kháng chấn DCM (TCVN 9386-1:2012 "
                f"§5.4.2.4(7)): V_Ed = 1,5 × V2 = "
                f"{_f(float(sh.get('V_d', V_in)), 1)} kN — toàn bộ "
                f"kiểm tra §8.1.3 dưới đây xét ở V_Ed này "
                f"(kể cả ĐK (98) với s_max theo V_Ed); cắt ngoài "
                f"mặt phẳng không phóng đại.")
        else:
            sh_lines.append(
                "Không phóng đại cắt kháng chấn (combo không phải "
                "động đất / cờ DCM đang tắt): V_Ed = V2.")
        sh_lines += [
            f"b × h0 = {shp.get('b', 0):.0f} × {shp.get('h0', 0):.0f} mm;  "
            f"thép ngang: {shp.get('sw_txt', '—')}",
            f"b × h0 = {shp.get('b', 0):.0f} × {shp.get('h0', 0):.0f} mm;  "
            f"thép ngang: {shp.get('sw_txt', '—')}",
            f"Asw = {shp.get('Asw', 0):,.0f} mm²;  "
            f"Rsw = {shp.get('Rsw', 0):.0f} MPa",
            f"qsw bố trí = {shp.get('qsw_arr', 0):.1f} N/mm;  "
            f"qsw được kể = {shp.get('qsw', 0):.1f} N/mm",
            f"φn = {shp.get('phi_n', 0):.3f} "
            f"(§8.1.3.3.2 — chỉ nhân số hạng bê tông)",
            f"ĐK1 (88) dải nén xiên: [Q]1 = "
            f"{shp.get('Qcap1', 0):,.1f} kN → "
            f"{'ĐẠT' if shp.get('ok1') else 'KHÔNG ĐẠT'}",
            f"ĐK2 vết nứt xiên: C = {shp.get('C_opt', 0):.0f} mm, "
            f"Qb = {shp.get('Qb', 0):,.1f} kN, "
            f"Qsw = {shp.get('Qsw', 0):,.1f} kN, "
            f"[Q]2 = {shp.get('Qcap2', 0):,.1f} kN → "
            f"{'ĐẠT' if shp.get('ok2') else 'KHÔNG ĐẠT'}",
        ]
        if not shp.get("cond98_ok", True):
            sh_lines.append(
                f"ĐK (98) KHÔNG thỏa: s_h = {shp.get('s_h', 0):.0f} mm > "
                f"s_max = {shp.get('s_max', 0):.0f} mm → thép ngang "
                f"không được kể, Qsw = 0")
        if not shp.get("cond96_ok", True):
            sh_lines.append(
                f"ĐK (96) KHÔNG thỏa: qsw < 0,25 × Rbt × b → Qb theo "
                f"(97), thép ngang vẫn được kể")
        sh_dc = sh.get("dc")
        sh_dc_txt = (_f(sh_dc, 3) if sh_dc is not None
                     and math.isfinite(float(sh_dc)) else "∞")
        sh_lines.append(
            f"Vcap = min([Q]1, [Q]2) = {float(sh['V_cap']):,.1f} kN")
        sh_cards.append(_card(
            "Kiểm tra cắt — Trong mặt phẳng (V2)",
            "§8.1.3 (ánh xạ vách)",
            sh_lines,
            f"D/C cắt = {sh_dc_txt} — "
            f"{'ĐẠT' if sh.get('ok') else 'KHÔNG ĐẠT'} "
            f"(kết luận cắt RIÊNG, không đổi kết luận N–M)"))
    else:
        _nc = _card("Kiểm tra cắt — Trong mặt phẳng (V2)",
                    "§8.1.3 (ánh xạ vách)",
                    [f"Chưa tính được: {sh.get('note', '—')}"],
                    "—")
        _nc["full"] = True
        sh_cards.append(_nc)
    # --- Cắt ngoài mặt phẳng (lát 4 — phần 4): thẻ riêng, cùng
    # builder với PDF chi tiết nên số tab/PDF khớp nhau; chỉ đọc
    # dict shear_out đã tính 1 lần ở wall_tcvn_full, không tính lại.
    sho = full.get("shear_out") or {}
    shop = sho.get("parts") or {}
    if sho.get("V_cap") is not None:
        _o_dc = sho.get("dc")
        _o_dc_txt = (_f(_o_dc, 3) if _o_dc is not None
                      and math.isfinite(float(_o_dc)) else "∞")
        _o_lines = [
            f"V3 = {_f(V_out, 1)} kN (lực cắt ngoài mặt phẳng — "
            f"Q3 nhập tay / V3 pier)",
            f"b × h0 = Lw × (tw − cover − dia_v − dia_h/2) = "
            f"{_f(shop.get('Lw', 0), 0)} × "
            f"({_f(shop.get('tw', 0), 0)} − "
            f"{_f(shop.get('cover', 0), 0)} − "
            f"{_f(shop.get('dia_v', 0), 0)} − "
            f"{_f(shop.get('dia_h', 0) / 2.0, 1)}) = "
            f"{shop.get('b', 0):.0f} × {shop.get('h0', 0):.0f} mm",
            "Giằng xuyên dày: CHƯA CÓ ô nhập — không bịa thép "
            "giằng, không tự thêm thép: Qsw = 0 (chỉ tính Qb)",
            f"φn = {shop.get('phi_n', 0):.3f} "
            f"(§8.1.3.3.2 — chỉ nhân số hạng bê tông)",
            f"ĐK1 (88) dải nén xiên: [Q]1 = φn × 0,3 × Rb × b × h0 "
            f"= {shop.get('phi_n', 0):.3f} × 0,3 × {_fm(conc.Rb)} × "
            f"{shop.get('b', 0):.0f} × {shop.get('h0', 0):.0f} / 1000 "
            f"= {shop.get('Qcap1', 0):,.1f} kN → "
            f"{'ĐẠT' if shop.get('ok1') else 'KHÔNG ĐẠT'}",
            f"ĐK2 vết nứt xiên: C = {shop.get('C_opt', 0):.0f} mm, "
            f"Qb = {shop.get('Qb', 0):,.1f} kN, "
            f"Qsw = {shop.get('Qsw', 0):,.1f} kN, "
            f"[Q]2 = {shop.get('Qcap2', 0):,.1f} kN → "
            f"{'ĐẠT' if shop.get('ok2') else 'KHÔNG ĐẠT'}",
            f"Vcap = min([Q]1, [Q]2) = {float(sho['V_cap']):,.1f} kN",
        ]
        sh_cards.append(_card(
            "Kiểm tra cắt — Ngoài mặt phẳng (V3)",
            "§8.1.3 (ánh xạ vách, Qsw = 0)",
            _o_lines,
            f"D/C cắt ngoài MP = {_o_dc_txt} — "
            f"{'ĐẠT' if sho.get('ok') else 'KHÔNG ĐẠT'} "
            f"(kết luận cắt RIÊNG, không đổi kết luận N–M)"))
    else:
        _nc_o = _card("Kiểm tra cắt — Ngoài mặt phẳng (V3)",
                      "§8.1.3 (ánh xạ vách, Qsw = 0)",
                      [f"Chưa tính được: {sho.get('note', '—')}"],
                      "—")
        _nc_o["full"] = True
        sh_cards.append(_nc_o)
    # Trượt mạch ngừng vẫn CHƯA KIỂM (phần riêng, không thuộc lát này).
    sliding_note = (full.get("sliding") or {}).get("note") or ""
    slide_lines = [
        "Trượt mạch ngừng chân vách: CHƯA KIỂM — chưa xác minh "
        "được điều khoản TCVN 5574:2018 cho vách nên không mượn "
        "công thức ma sát cắt ACI/EC2 sang TCVN.",
    ]
    if sliding_note:
        slide_lines += _wrap(f"Ghi chú engine: {sliding_note}")
    sh_cards.append(_card("Trượt mạch ngừng chân vách",
                          "CHƯA KIỂM", slide_lines, "CHƯA KIỂM"))
    sections.append({
        "num": 8, "title": "KIỂM TRA CẮT",
        "ref": "TCVN 5574:2018 §8.1.3 (ánh xạ vách — xem ghi chú)",
        "cards": sh_cards})

    # ================= MỤC 9: PHẠM VI & CHƯA KIỂM =================
    bnd = full.get("boundary") or {}
    sections.append({
        "num": 9, "title": "PHẠM VI & PHẦN CHƯA KIỂM",
        "ref": "Phạm vi GĐ1",
        "cards": [
            _card("Vùng biên & cấu tạo (lát 3)",
                  "CHƯA KIỂM",
                  [f"Lb bố trí: trái {float(bnd.get('Lb_prov_left', 0) or 0):.0f} mm, "
                   f"phải {float(bnd.get('Lb_prov_right', 0) or 0):.0f} mm "
                   f"(chỉ ghi nhận, chưa đối chiếu yêu cầu)",
                   "Vùng biên (tiêu chí kích hoạt, Lb yêu cầu, ρ vùng "
                   "biên, đai vùng biên): CHƯA KIỂM — lát 3.",
                   "Cấu tạo / ρmin: CHƯA KIỂM — lát 3."],
                  "CHƯA KIỂM"),
            _card("Ghi chú phạm vi kết luận",
                  "Không có kết luận chung",
                  ["Không có kết luận chung: mỗi phần kết "
                   "luận riêng tại mục của nó — mục 3 (độ mảnh), "
                   "mục 6 (N–M), mục 7 (diễn giải lại N–M, không "
                   "phải kết luận độc lập), mục 8 (cắt trong và "
                   "ngoài MP; trượt mạch ngừng CHƯA KIỂM).",
                   ("Cắt trong mặt phẳng ĐÃ kể phóng đại kháng chấn "
                    "TCVN 9386-1:2012 §5.4.2.4(7) DCM (V_Ed = 1,5 × V2) "
                    "trong lần tính này; cắt ngoài mặt phẳng không "
                    "phóng đại."
                    if (full.get("shear_in") or {}).get("seismic_applied")
                    else "Cắt trong mặt phẳng CHƯA kể phóng đại cắt "
                    "kháng chấn trong lần tính này (combo không phải "
                    "động đất / cờ DCM đang tắt): V_Ed = V2; cắt ngoài "
                    "mặt phẳng không bao giờ phóng đại."),
                   "Ánh xạ cắt §8.1.3 sang vách (trong MP: b = tw, h0 "
                   "theo Lw, qsw từ thép ngang phân bố; ngoài MP: "
                   "b = Lw, h0 theo tw, Qsw = 0 vì chưa có giằng xuyên "
                   "dày) là quyết định kỹ thuật "
                   "của lát, KHÔNG phải điều khoản riêng cho vách "
                   "trong tiêu chuẩn — cần thẩm tra xác nhận trước "
                   "khi dùng cho thiết kế chính thức."],
                  "Không có kết luận chung — xem kết luận từng mục"),
        ]})

    return sections


def wall_detail_header(full):
    """Dòng tiêu đề + nội lực cho đầu tab/PDF chi tiết."""
    return {
        "title": "THUYẾT MINH KIỂM TRA VÁCH — TCVN 5574:2018",
        "loads": (f"N = {_f(float(full['N']), 1)} kN, "
                  f"M3 (trong MP) = {_f(float(full['M_in']), 1)} kN·m, "
                  f"M2 (ngoài MP) = {_f(float(full['M_out']), 1)} kN·m, "
                  f"V2 = {_f(float(full['V_in']), 1)} kN, "
                  f"V3 = {_f(float(full['V_out']), 1)} kN"),
    }
