"""Đọc nội lực cột từ file Excel do ETABS xuất (bảng Element Forces - Columns).

Cột cần thiết: Story, Column, Output Case, Case Type, Station, P, M2, M3.
Quy ước: P âm = nén (ETABS) -> đổi sang N dương = nén.
Ánh xạ mô men: mặc định M2 -> Mx, M3 -> My (đổi được trên GUI).
"""

from dataclasses import dataclass
from typing import List, Optional

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


@dataclass
class EtabsForce:
    story: str
    column: str
    case: str
    case_type: str
    station: float
    N: float    # kN, nén dương
    Mx: float   # kN·m
    My: float   # kN·m


def read_etabs_excel(path: str,
                     only_combinations: bool = True) -> List[EtabsForce]:
    """Đọc file Excel ETABS.

    Quy ước trục 2/3 thống nhất: M2 (Excel) -> M2, M3 (Excel) -> M3.
    """
    if not HAS_OPENPYXL:
        raise ImportError("Cần cài openpyxl: pip install openpyxl")
    wb = openpyxl.load_workbook(path, data_only=True)
    # tìm sheet chứa "Element Forces"
    ws = None
    for name in wb.sheetnames:
        if "element forces" in name.lower():
            ws = wb[name]
            break
    if ws is None:
        ws = wb.active

    # tìm dòng header (chứa "Story" và "Output Case")
    header_row = None
    col_idx = {}
    for r in range(1, min(10, ws.max_row + 1)):
        vals = [str(ws.cell(r, c).value or "").strip().lower()
                for c in range(1, ws.max_column + 1)]
        if "story" in vals and "output case" in vals:
            header_row = r
            for c, v in enumerate(vals, start=1):
                col_idx[v] = c
            break
    if header_row is None:
        raise ValueError("Không tìm thấy bảng Element Forces trong file.")

    def val(row, *names):
        for n in names:
            c = col_idx.get(n)
            if c:
                v = ws.cell(row, c).value
                if v is not None and str(v).strip() != "":
                    return v
        return None

    def num(row, *names):
        v = val(row, *names)
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    forces: List[EtabsForce] = []
    for r in range(header_row + 1, ws.max_row + 1):
        case = val(r, "output case")
        if case is None:
            continue
        case_type = str(val(r, "case type") or "")
        if only_combinations and "combination" not in case_type.lower():
            continue
        p = num(r, "p")
        m2 = num(r, "m2")
        m3 = num(r, "m3")
        mx, my = m2, m3  # M2->M2, M3->M3 (không ánh xạ)
        forces.append(EtabsForce(
            story=str(val(r, "story") or ""),
            column=str(val(r, "column") or ""),
            case=str(case),
            case_type=case_type,
            station=num(r, "station"),
            N=-p,  # ETABS: nén âm -> đổi sang nén dương
            Mx=mx,
            My=my,
        ))
    return forces


def parse_etabs_clipboard(text: str,
                          only_combinations: bool = True) -> List[EtabsForce]:
    """Đọc nội lực từ clipboard copy từ bảng ETABS 'Element Forces - Columns'.

    Định dạng: tab-separated, 2 dòng header, các cột:
    Story | Column | Unique Name | Output Case | Case Type | Step Type |
    Station | P | V2 | V3 | T | M2 | M3 | Element | Elem Station | Location
    Quy ước: P âm = nén (ETABS) -> N dương.
    """
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if len(lines) < 3:
        raise ValueError("Clipboard không có đủ dữ liệu.")
    # Tìm dòng header chứa "Output Case"
    hi = None
    for i, ln in enumerate(lines[:5]):
        if "output case" in ln.lower():
            hi = i
            break
    if hi is None:
        raise ValueError("Không tìm thấy header ETABS (Output Case).")
    # Vị trí cột cố định theo format ETABS Element Forces - Columns
    C_CASE, C_TYPE, C_STATION = 3, 4, 6
    C_P, C_M2, C_M3 = 7, 11, 12
    C_STORY, C_COL = 0, 1

    def num(parts, idx):
        try:
            return float(parts[idx].strip()) if idx < len(parts) and parts[idx].strip() else 0.0
        except ValueError:
            return 0.0

    forces: List[EtabsForce] = []
    for ln in lines[hi + 2:]:
        parts = ln.split("\t")
        if len(parts) <= C_P:
            continue
        case = parts[C_CASE].strip() if C_CASE < len(parts) else ""
        if not case:
            continue
        case_type = parts[C_TYPE].strip() if C_TYPE < len(parts) else ""
        if only_combinations and "combination" not in case_type.lower():
            continue
        p = num(parts, C_P)
        forces.append(EtabsForce(
            story=parts[C_STORY].strip() if C_STORY < len(parts) else "",
            column=parts[C_COL].strip() if C_COL < len(parts) else "",
            case=case,
            case_type=case_type,
            station=num(parts, C_STATION),
            N=-p,
            Mx=num(parts, C_M2),
            My=num(parts, C_M3),
        ))
    if not forces:
        raise ValueError("Không đọc được dòng nội lực nào từ clipboard.")
    return forces
