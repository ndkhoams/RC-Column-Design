"""Tên file mặc định khi xuất PDF — dùng chung cho mọi đường xuất
(cột + vách, tóm tắt + chi tiết).

Quy ước (2026-10-25, theo yêu cầu phân biệt đúng chức năng):
    CỘT tóm tắt: TMTT-COT-[TC]-TênCK.pdf
    CỘT chi tiết: TMTT-FULL-COT-[TC]-TênCK.pdf
    VÁCH tóm tắt: TMTT-VACH-[TC]-TênCK.pdf
    VÁCH chi tiết: TMTT-FULL-VACH-[TC]-TênCK.pdf
TênCK rỗng thì bỏ đoạn tên (vd TMTT-COT-TCVN.pdf).
Dùng ASCII COT/VACH cho nhất quán với quy ước tên file ASCII hiện
tại (TMTT, TCVN, ACI, EC2, tên cấu kiện) — không dùng CỘT/VÁCH có
dấu. Hàm thuần túy, không phụ thuộc GUI, để unit test trực tiếp.
"""


def default_pdf_filename(kind, std, member, is_summary):
    """Trả về tên file PDF mặc định.

    kind: "cot" | "vach"; std: "TCVN" | "ACI" | "EC2" (chuẩn hóa
    upper/strip); member: tên cấu kiện bất kỳ (strip + upper);
    is_summary: True = tóm tắt, False = chi tiết (FULL).
    """
    if kind not in ("cot", "vach"):
        raise ValueError(f"kind phải là 'cot' hoặc 'vach', nhận: {kind!r}")
    tag = "COT" if kind == "cot" else "VACH"
    std = (std or "").strip().upper()
    ck = (member or "").strip().upper()
    full = "" if is_summary else "-FULL"
    base = f"TMTT{full}-{tag}"
    if std:
        base += f"-{std}"
    return f"{base}-{ck}.pdf" if ck else f"{base}.pdf"
