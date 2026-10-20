"""Đọc file tính toán cột của Prokon General Column (.C13).

File .C13 của Prokon (General Column Design) là file TEXT (mã hóa
Windows-1252) gồm các block:

  - ``TITLE : ...``
  - ``COLUMN SECTION``: định nghĩa tiết diện theo hệ tọa độ "sketch"
    tuyệt đối. Dòng ``+`` đầu tiên là điểm neo (đỉnh đầu tiên của đa
    giác); các dòng mã rỗng tiếp theo là các bước di chuyển TƯƠNG ĐỐI
    (dx, dy) truy vết đa giác (tổng dx = tổng dy = 0, khép kín); sau
    đó lặp lại cặp dòng ``+`` (tọa độ tuyệt đối của 1 thanh thép) và
    dòng ``b`` (đường kính thanh).
  - ``GENERAL``: L0, fck, fy, Es, hệ số chiều dài hiệu dụng (nhãn
    ``#b`` — ký tự β bị lỗi mã hóa), Braced, điều kiện biên 2 đầu.
  - ``LOAD CASES:``: các trường hợp tải P, Mx/My tại đầu trên/dưới.
  - ``Design code:...`` (Eurocode 2 / ACI ...).
  - ``Reinforcement details``: tọa độ thép theo hệ NỘI BỘ (sạch):
    hệ nội bộ = hệ tuyệt đối - offset, với offset khớp từ thanh đầu
    tiên xuất hiện ở cả 2 danh sách (thứ tự 2 danh sách trùng nhau).
  - ``Longitudinal bar details``: đường kính thép theo Mark.

Hàm chính: :func:`parse_prokon_c13` — thuần dữ liệu (không GUI),
trả về dict gồm đa giác + thép theo hệ tọa độ nội bộ (chưa đưa về
trọng tâm; việc đó do ``build_polygon_section`` của app đảm nhiệm,
giống hệt quy ước import DXF).

Giới hạn: chỉ hỗ trợ đoạn thẳng trong định nghĩa tiết diện — gặp mã
đoạn lạ (cung tròn...) sẽ báo lỗi rõ ràng. Thép đai không có trong
file (chỉ có thông tin bending schedule) nên không import đai.
"""

import re
from typing import Dict, List, Optional, Tuple

__all__ = ["parse_prokon_c13"]


# ---------------------------------------------------------------------------
# Tiện ích parse số / dòng bảng
# ---------------------------------------------------------------------------

def _num(s) -> float:
    """Parse số tolerant: chấp nhận dấu cách/phẩy ngăn nghìn, phẩy thập phân."""
    if s is None:
        raise ValueError("thiếu giá trị số")
    t = str(s).strip().replace(" ", "").replace("\u00a0", "")
    if not t:
        raise ValueError("giá trị số trống")
    if "," in t and "." in t:
        t = t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    return float(t)


def _fields(line: str) -> List[str]:
    """Tách 1 dòng bảng dạng ``| a | b | c |`` thành các trường đã strip."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [p.strip() for p in s.split("|")]


# ---------------------------------------------------------------------------
# Các block
# ---------------------------------------------------------------------------

def _parse_section_block(lines: List[str], start: int):
    """Đọc block COLUMN SECTION bắt đầu sau dòng tiêu đề tại ``start``.

    Trả về (anchor, moves, abs_bars, next_index).
    abs_bars: [(x, y, dia)] theo hệ tuyệt đối.
    """
    anchor: Optional[Tuple[float, float]] = None
    moves: List[Tuple[float, float]] = []
    abs_bars: List[Tuple[float, float, float]] = []
    pending: Optional[Tuple[float, float]] = None
    i = start
    while i < len(lines):
        line = lines[i]
        i += 1
        s = line.strip()
        if s == "GENERAL" or s.startswith("LOAD CASES"):
            break  # sang block kế tiếp
        if not s.startswith("|"):
            continue  # dòng gạch ngang / dòng trống trong bảng
        f = _fields(line)
        if len(f) < 3:
            continue
        code, xs, ys = f[0], f[1], f[2]
        if code == "COLUMN SECTION" or code == "Code":
            continue  # dòng tiêu đề bảng
        if code == "+":
            x, y = _num(xs), _num(ys)
            if anchor is None:
                anchor = (x, y)
            else:
                if pending is not None:
                    raise ValueError(
                        "COLUMN SECTION: thanh thép thiếu dòng đường kính 'b'.")
                pending = (x, y)
        elif code == "b":
            if pending is None:
                raise ValueError(
                    "COLUMN SECTION: dòng 'b' không có tọa độ '+' trước đó.")
            abs_bars.append((pending[0], pending[1], _num(xs)))
            pending = None
        elif code == "":
            if xs == "" and ys == "":
                continue  # dòng trống phân cách
            try:
                mv = (_num(xs), _num(ys))
            except ValueError:
                continue  # dòng tiêu đề phụ của bảng (vd 'Diameter (mm)')
            if abs_bars or pending is not None:
                raise ValueError(
                    "COLUMN SECTION: gặp bước di chuyển sau danh sách thép.")
            moves.append(mv)
        else:
            raise ValueError(
                f"Chưa hỗ trợ đoạn có mã '{code}' trong COLUMN SECTION "
                "(cung tròn / đoạn đặc biệt của Prokon).")
    if anchor is None:
        raise ValueError("Không tìm thấy điểm neo '+' trong COLUMN SECTION.")
    if pending is not None:
        raise ValueError(
            "COLUMN SECTION: thanh thép cuối thiếu dòng đường kính 'b'.")
    return anchor, moves, abs_bars


def _parse_general(lines: List[str], start: int) -> Dict:
    """Đọc block GENERAL (bảng đầu tiên sau dòng 'GENERAL')."""
    out: Dict = {}
    end_seen = False
    i = start
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip().startswith("|"):
            if out or end_seen:
                break
            continue
        f = _fields(line)
        if len(f) < 2:
            continue
        label = f[0]
        value = f[1] if len(f) > 1 else ""
        flag = f[2] if len(f) > 2 else ""
        low = label.lower()
        if label == "GENERAL":
            continue
        if low.startswith("lo"):
            out["L0"] = _num(value)
        elif low.startswith("fck"):
            out["fck"] = _num(value)
        elif low.startswith("fy"):
            out["fy"] = _num(value)
        elif low.startswith("es"):
            out["Es"] = _num(value)
        elif label.replace(" ", "") == "#b" or low.startswith("#b"):
            out["beta"] = _num(value)
        elif label == "Braced":
            out["braced"] = "x" in flag.lower()
        elif label == "End conditions":
            end_seen = True
        elif end_seen and label == "Top":
            out["end_top"] = value
        elif end_seen and label == "Bottom":
            out["end_bottom"] = value
            # Không break: dòng '#b' (hệ số β) nằm sau dòng Bottom
    return out


def _parse_load_cases(lines: List[str], start: int) -> List[Dict]:
    """Đọc block LOAD CASES."""
    cases: List[Dict] = []
    i = start
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip().startswith("|"):
            if cases:
                break
            continue
        f = _fields(line)
        if len(f) < 7:
            continue
        try:
            int(f[0])
        except (TypeError, ValueError):
            continue  # dòng tiêu đề
        cases.append({
            "name": f[1],
            "P": _num(f[2]),
            "Mx_top": _num(f[3]),
            "My_top": _num(f[4]),
            "Mx_bottom": _num(f[5]),
            "My_bottom": _num(f[6]),
        })
    return cases


_BAR_ROW = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(\S+)\s+(\d+)\s*$")


def _parse_reinforcement_details(lines: List[str], start: int):
    """Đọc block 'Reinforcement details' + 'Longitudinal bar details'.

    Trả về (bars, mark_dia): bars = [(x, y, mark)] hệ nội bộ.
    """
    bars: List[Tuple[float, float, str]] = []
    mark_dia: Dict[str, float] = {}
    i = start
    # Danh sách thanh: các dòng sau tiêu đề 'X Y Mark ref'
    while i < len(lines):
        m = _BAR_ROW.match(lines[i])
        i += 1
        if m:
            bars.append((float(m.group(1)), float(m.group(2)), m.group(3)))
        elif bars:
            break
    # Bảng đường kính theo Mark
    while i < len(lines):
        if lines[i].strip().startswith("Longitudinal bar details"):
            i += 1
            break
        i += 1
    while i < len(lines):
        parts = lines[i].split()
        i += 1
        if len(parts) >= 4 and parts[0] != "Mark":
            try:
                dia = float(parts[1])
                int(parts[3])
            except ValueError:
                if mark_dia:
                    break
                continue
            mark_dia[parts[0]] = dia
        elif mark_dia:
            break
    return bars, mark_dia


# ---------------------------------------------------------------------------
# Hàm chính
# ---------------------------------------------------------------------------

def parse_prokon_c13(path: str) -> Dict:
    """Parse file Prokon General Column (.C13) thành dict dữ liệu thuần.

    Trả về dict::

        {
          "title": str, "label": str,
          "design_code": "EC2" | "ACI" | <chuỗi gốc>,
          "design_code_text": str,
          "L0": float (m), "fck": float (MPa), "fy": float (MPa),
          "Es": float (GPa), "beta": float | None,
          "braced": bool, "end_top": str, "end_bottom": str,
          "polygon": [(x, y), ...]  # hệ nội bộ, chưa về trọng tâm
          "rebars": [(x, y, dia), ...]  # hệ nội bộ
          "loads": [{"name", "P", "Mx_top", "My_top",
                     "Mx_bottom", "My_bottom"}],
          "warnings": [str],
        }
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    text = raw.decode("cp1252", errors="replace")
    lines = text.splitlines()

    warnings: List[str] = []
    result: Dict = {"warnings": warnings}

    # --- TITLE ---
    title = ""
    for ln in lines:
        if ln.strip().upper().startswith("TITLE"):
            title = ln.split(":", 1)[1].strip() if ":" in ln else ""
            break
    result["title"] = title
    label = ""
    toks = title.split()
    if toks and re.fullmatch(r"[A-Za-z]+\d+", toks[-1]):
        label = toks[-1]
    result["label"] = label

    # --- Vị trí các block ---
    idx_section = idx_general = idx_loads = idx_reinf = None
    design_text = ""
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s == "COLUMN SECTION" and idx_section is None:
            idx_section = i
        elif s == "GENERAL" and idx_general is None:
            idx_general = i
        elif s.startswith("LOAD CASES") and idx_loads is None:
            idx_loads = i
        elif s == "Reinforcement details:" and idx_reinf is None:
            idx_reinf = i
        elif s.lower().startswith("design code:"):
            design_text = s.split(":", 1)[1].strip()
    if idx_section is None:
        raise ValueError("Không tìm thấy block COLUMN SECTION — "
                         "không phải file Prokon General Column?")
    if idx_loads is None:
        raise ValueError("Không tìm thấy block LOAD CASES.")

    low_code = design_text.lower()
    if "eurocode" in low_code or "euro" in low_code:
        code = "EC2"
    elif "aci" in low_code:
        code = "ACI"
    else:
        code = design_text
    result["design_code"] = code
    result["design_code_text"] = design_text

    # --- Tiết diện: đa giác tuyệt đối + thép tuyệt đối ---
    anchor, moves, abs_bars = _parse_section_block(lines, idx_section + 1)
    verts_abs: List[Tuple[float, float]] = [anchor]
    cx, cy = anchor
    for dx, dy in moves:
        cx, cy = cx + dx, cy + dy
        verts_abs.append((cx, cy))
    sum_dx = sum(m[0] for m in moves)
    sum_dy = sum(m[1] for m in moves)
    if abs(sum_dx) > 1.0 or abs(sum_dy) > 1.0:
        raise ValueError(
            f"Đa giác tiết diện không khép kín (tổng dx={sum_dx:.2f}, "
            f"dy={sum_dy:.2f}) — có thể tiết diện có cung tròn, "
            "chưa hỗ trợ.")
    # Bỏ đỉnh cuối nếu trùng đỉnh đầu (điểm quay về điểm neo)
    if len(verts_abs) > 1 and abs(verts_abs[-1][0] - anchor[0]) <= 1.0 \
            and abs(verts_abs[-1][1] - anchor[1]) <= 1.0:
        verts_abs = verts_abs[:-1]
    if len(verts_abs) < 3:
        raise ValueError("Đa giác tiết diện có ít hơn 3 đỉnh.")

    # --- Thép hệ nội bộ (block Reinforcement details) ---
    rebars: List[Tuple[float, float, float]] = []
    polygon = verts_abs
    if idx_reinf is not None:
        bars_local, mark_dia = _parse_reinforcement_details(
            lines, idx_reinf + 1)
        if bars_local and abs_bars:
            if len(bars_local) != len(abs_bars):
                raise ValueError(
                    f"Số thép không khớp: COLUMN SECTION có "
                    f"{len(abs_bars)} thanh, Reinforcement details có "
                    f"{len(bars_local)} thanh.")
            off_x = abs_bars[0][0] - bars_local[0][0]
            off_y = abs_bars[0][1] - bars_local[0][1]
            for (ax, ay, _d), (lx, ly, _m) in zip(abs_bars, bars_local):
                if abs(ax - lx - off_x) > 1.0 or abs(ay - ly - off_y) > 1.0:
                    raise ValueError(
                        "Tọa độ thép ở COLUMN SECTION không khớp "
                        "Reinforcement details (lệch quá 1 mm) — "
                        "không xác định được hệ tọa độ nội bộ.")
            polygon = [(x - off_x, y - off_y) for x, y in verts_abs]
            for lx, ly, mark in bars_local:
                if mark not in mark_dia:
                    raise ValueError(
                        f"Không tìm thấy đường kính cho Mark '{mark}'.")
                rebars.append((lx, ly, mark_dia[mark]))
        elif bars_local:
            warnings.append(
                "Không có danh sách thép ở COLUMN SECTION để đối chiếu "
                "hệ tọa độ — dùng tọa độ nội bộ của Reinforcement details.")
            for lx, ly, mark in bars_local:
                if mark not in mark_dia:
                    raise ValueError(
                        f"Không tìm thấy đường kính cho Mark '{mark}'.")
                rebars.append((lx, ly, mark_dia[mark]))
    if not rebars:
        warnings.append(
            "Không đọc được block 'Reinforcement details' — dùng tọa độ "
            "thép tuyệt đối của COLUMN SECTION (app sẽ tự đưa tiết diện "
            "về trọng tâm khi dựng).")
        rebars = list(abs_bars)
        polygon = verts_abs

    result["polygon"] = polygon
    result["rebars"] = rebars

    # --- GENERAL ---
    gen = _parse_general(lines, idx_general + 1) if idx_general is not None \
        else {}
    for key in ("L0", "fck", "fy"):
        if key not in gen:
            raise ValueError(f"Thiếu thông số '{key}' trong block GENERAL.")
    result["L0"] = gen["L0"]
    result["fck"] = gen["fck"]
    result["fy"] = gen["fy"]
    result["Es"] = gen.get("Es")
    result["beta"] = gen.get("beta")
    result["braced"] = bool(gen.get("braced", False))
    result["end_top"] = gen.get("end_top", "")
    result["end_bottom"] = gen.get("end_bottom", "")

    # --- LOAD CASES ---
    result["loads"] = _parse_load_cases(lines, idx_loads + 1)
    if not result["loads"]:
        raise ValueError("Block LOAD CASES không có trường hợp tải nào.")

    return result
