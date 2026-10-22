"""Đọc nội lực cột từ file Excel do ETABS xuất (bảng Element Forces - Columns).

Cột cần thiết: Story, Column, Output Case, Case Type, Station, P, M2, M3.
Quy ước: P âm = nén (ETABS) -> đổi sang N dương = nén.
Ánh xạ mô men: mặc định M2 -> Mx, M3 -> My (đổi được trên GUI).

Hỗ trợ thêm SAP2000 (bảng Element Forces - Frames): header dùng Frame,
OutputCase, CaseType, StepType (không khoảng trắng) và KHÔNG có cột Story —
khi đó Label lấy từ Frame, Story mặc định "Story". Quy ước dấu/mô men như ETABS.
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
    Q2: float = 0.0  # kN, lực cắt V2
    Q3: float = 0.0  # kN, lực cắt V3


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

    # tìm dòng header (ETABS: "Story" + "Output Case";
    # SAP2000: "Frame" + "OutputCase" — không có Story)
    header_row = None
    col_idx = {}
    for r in range(1, min(10, ws.max_row + 1)):
        vals = [str(ws.cell(r, c).value or "").strip().lower()
                for c in range(1, ws.max_column + 1)]
        if ("story" in vals or "frame" in vals) and \
                ("output case" in vals or "outputcase" in vals):
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

    # Tự động nhận diện đơn vị từ dòng ngay sau header (vd "kN", "kN-m")
    def _unit_factor(unit_str: str, kind: str) -> float:
        u = (str(unit_str or "")).strip().lower().replace(" ", "")
        if kind == "force":
            if u in ("kn",): return 1.0
            if u in ("n",): return 0.001
            if u in ("kgf", "kg", "kgs"): return 0.00980665
            if u in ("tonf", "ton", "t", "tf"): return 9.80665
            if u in ("kip", "kips"): return 4.4482216
            if u in ("lbf", "lb", "lbs"): return 0.0044482216
            return 1.0
        else:
            if u in ("kn-m", "knm"): return 1.0
            if u in ("n-m", "nm"): return 0.001
            if u in ("n-mm", "nmm"): return 1e-6
            if u in ("kn-mm", "knmm"): return 0.001
            if u in ("kgf-m", "kg-m", "kgm"): return 0.00980665
            if u in ("kgf-cm", "kg-cm", "kgcm"): return 0.00980665 * 0.01
            if u in ("tonf-m", "ton-m", "tf-m"): return 9.80665
            if u in ("kip-ft", "kipft", "k-ft"): return 1.3558179
            if u in ("kip-in", "kipin", "k-in"): return 1.3558179 / 12.0
            if u in ("lbf-ft", "lb-ft"): return 0.0013558179
            if u in ("lbf-in", "lb-in"): return 0.0013558179 / 12.0
            return 1.0

    f_force, f_moment = 1.0, 1.0
    ur = header_row + 1
    if ur <= ws.max_row:
        c_p = col_idx.get("p")
        c_m2 = col_idx.get("m2")
        if c_p:
            f_force = _unit_factor(ws.cell(ur, c_p).value, "force")
        if c_m2:
            f_moment = _unit_factor(ws.cell(ur, c_m2).value, "moment")

    forces: List[EtabsForce] = []
    data_start = header_row + 2  # bỏ qua dòng đơn vị
    for r in range(data_start, ws.max_row + 1):
        case = val(r, "output case", "outputcase")
        if case is None:
            continue
        case_type = str(val(r, "case type", "casetype") or "")
        if only_combinations and "combination" not in case_type.lower():
            continue
        # Gắn Step Type vào tên tổ hợp: TH14max, TH15min
        step = str(val(r, "step type", "steptype") or "").strip().lower()
        if step == "max":
            case = f"{case}max"
        elif step == "min":
            case = f"{case}min"
        p = num(r, "p") * f_force
        m2 = num(r, "m2") * f_moment
        m3 = num(r, "m3") * f_moment
        v2 = num(r, "v2", "shear 2-2", "v2-2") * f_force
        v3 = num(r, "v3", "shear 3-3", "v3-3") * f_force
        mx, my = m2, m3  # M2->M2, M3->M3 (không ánh xạ)
        forces.append(EtabsForce(
            # SAP2000 không có cột Story -> mặc định "Story" (user đã duyệt)
            story=str(val(r, "story") or
                      ("Story" if "story" not in col_idx else "")),
            column=str(val(r, "column", "frame") or ""),
            case=str(case),
            case_type=case_type,
            station=num(r, "station"),
            N=-p,  # ETABS: nén âm -> đổi sang nén dương
            Mx=mx,
            My=my,
            Q2=v2,
            Q3=v3,
        ))
    return forces


def _parse_sap_clipboard(lines, hi, idx, only_combinations,
                         unit_factor) -> List[EtabsForce]:
    """Parse các dòng dữ liệu SAP2000 (Element Forces - Frames) theo TÊN cột.

    idx: dict tên trường -> vị trí cột trong header. SAP không có Story ->
    story mặc định "Story", Label lấy từ Frame. Quy ước dấu như ETABS
    (N = -P; M2 -> Mx, M3 -> My; hậu tố Step Type gắn vào tên tổ hợp).
    Dòng đơn vị (nếu có) tự bị bỏ qua vì ô P của nó không phải số.
    """
    ip, im2 = idx["p"], idx["m2"]
    f_force, f_moment = 1.0, 1.0
    if hi + 1 < len(lines):
        up = lines[hi + 1].split("\t")
        if ip is not None and ip < len(up):
            f_force = unit_factor(up[ip], "force")
        if im2 is not None and im2 < len(up):
            f_moment = unit_factor(up[im2], "moment")

    def _num(parts, i):
        if i is None or i >= len(parts):
            return 0.0
        try:
            return float(parts[i].strip())
        except ValueError:
            return 0.0

    def _txt(parts, i):
        return parts[i].strip() if i is not None and i < len(parts) else ""

    forces: List[EtabsForce] = []
    for ln in lines[hi + 1:]:
        parts = ln.split("\t")
        if ip is None or len(parts) <= ip:
            continue
        try:
            p_raw = float(parts[ip].strip())
        except (ValueError, AttributeError):
            continue  # dòng đơn vị / dòng rác: ô P không phải số
        case = _txt(parts, idx["case"])
        if not case:
            continue
        case_type = _txt(parts, idx["type"])
        if only_combinations and "combination" not in case_type.lower():
            continue
        # Gắn Step Type vào tên tổ hợp như ETABS: ENV SLS + Min -> ENV SLSmin
        step = _txt(parts, idx["step"]).lower()
        if step == "max":
            case = f"{case}max"
        elif step == "min":
            case = f"{case}min"
        forces.append(EtabsForce(
            story="Story",
            column=_txt(parts, idx["label"]),
            case=case,
            case_type=case_type,
            station=_num(parts, idx["station"]),
            N=-p_raw * f_force,
            Mx=_num(parts, idx["m2"]) * f_moment,
            My=_num(parts, idx["m3"]) * f_moment,
            Q2=_num(parts, idx["v2"]) * f_force,
            Q3=_num(parts, idx["v3"]) * f_force,
        ))
    if not forces:
        raise ValueError(
            "Không đọc được dòng nội lực nào từ clipboard SAP2000.")
    return forces


def parse_etabs_clipboard(text: str,
                          only_combinations: bool = True) -> List[EtabsForce]:
    """Đọc nội lực từ clipboard copy từ bảng ETABS 'Element Forces - Columns'.

    Định dạng: tab-separated, 2 dòng header, các cột:
    Story | Column | Unique Name | Output Case | Case Type | [Step Type] |
    Station | P | V2 | V3 | T | M2 | M3 | Element | Elem Station | Location
    (tự động nhận diện có/không có cột Step Type để match đúng vị trí)
    Quy ước: P âm = nén (ETABS) -> N dương.

    Nhận thêm clipboard SAP2000 (bảng Element Forces - Frames): header theo
    tên cột Frame | Station | OutputCase | CaseType | StepType | P | V2 | V3 |
    T | M2 | M3 | ... (không có Story) — parse theo TÊN cột, Story = "Story".
    """
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if len(lines) < 3:
        raise ValueError("Clipboard không có đủ dữ liệu.")
    # Tìm dòng header chứa "Output Case" (ETABS) hoặc "OutputCase" (SAP2000)
    hi = None
    for i, ln in enumerate(lines[:5]):
        low = ln.lower()
        if "output case" in low or "outputcase" in low:
            hi = i
            break
    if hi is None:
        raise ValueError("Không tìm thấy header ETABS (Output Case).")
    # Tự động nhận diện có cột "Step Type" hay không để match đúng vị trí
    # Có Step Type: Story|Column|Unique Name|Output Case|Case Type|Step Type|
    #               Station|P|V2|V3|T|M2|M3|...
    # Không Step Type: Story|Column|Unique Name|Output Case|Case Type|
    #               Station|P|V2|V3|T|M2|M3|...
    header_parts = [p.strip().lower() for p in lines[hi].split("\t")]
    # SAP2000: header có "frame" và KHÔNG có "story" -> parse theo tên cột
    # (vị trí cột khác hẳn ETABS nên không dùng được vị trí cố định bên dưới)
    sap_idx = None
    if "frame" in header_parts and "story" not in header_parts:
        def _find(*names):
            for n in names:
                if n in header_parts:
                    return header_parts.index(n)
            return None
        sap_idx = {
            "label": _find("frame"),
            "station": _find("station"),
            "case": _find("output case", "outputcase"),
            "type": _find("case type", "casetype"),
            "step": _find("step type", "steptype"),
            "p": _find("p"),
            "v2": _find("v2"),
            "v3": _find("v3"),
            "m2": _find("m2"),
            "m3": _find("m3"),
        }
        if sap_idx["case"] is None or sap_idx["p"] is None:
            sap_idx = None
    # Kiểm tra Step Type trên cả dòng header và các dòng lân cận
    # (ETABS đôi khi xuất header nhiều dòng)
    has_step = "step type" in header_parts
    if not has_step:
        for _ln in lines[max(0, hi-2):hi+3]:
            if "step type" in _ln.lower():
                has_step = True
                break
    if has_step:
        C_CASE, C_TYPE, C_STATION = 3, 4, 6
        C_P, C_M2, C_M3 = 7, 11, 12
        C_V2, C_V3 = 8, 9
    else:
        C_CASE, C_TYPE, C_STATION = 3, 4, 5
        C_P, C_M2, C_M3 = 6, 10, 11
        C_V2, C_V3 = 7, 8
    C_STORY, C_COL = 0, 1

    # Tự động nhận diện đơn vị từ dòng units (dòng ngay sau header)
    # Quy về kN (lực) và kN-m (mô men) để dùng trong app
    def _unit_factor(unit_str: str, kind: str) -> float:
        """Trả về hệ số nhân để đổi về kN (kind='force') hoặc kN-m (kind='moment')."""
        u = (unit_str or "").strip().lower().replace(" ", "")
        if kind == "force":
            if u in ("kn",): return 1.0
            if u in ("n",): return 0.001
            if u in ("kgf", "kg", "kgs"): return 0.00980665
            if u in ("tonf", "ton", "t", "tf"): return 9.80665
            if u in ("kip", "kips"): return 4.4482216
            if u in ("lbf", "lb", "lbs"): return 0.0044482216
            return 1.0  # mặc định kN
        else:  # moment -> kN-m
            if u in ("kn-m", "knm", "kN-m".lower()): return 1.0
            if u in ("n-m", "nm"): return 0.001
            if u in ("n-mm", "nmm"): return 1e-6
            if u in ("kn-mm", "knmm"): return 0.001
            if u in ("kgf-m", "kg-m", "kgm"): return 0.00980665
            if u in ("kgf-cm", "kg-cm", "kgcm"): return 0.00980665 * 0.01
            if u in ("tonf-m", "ton-m", "tf-m"): return 9.80665
            if u in ("kip-ft", "kipft", "k-ft"): return 1.3558179
            if u in ("kip-in", "kipin", "k-in"): return 1.3558179 / 12.0
            if u in ("lbf-ft", "lb-ft"): return 0.0013558179
            if u in ("lbf-in", "lb-in"): return 0.0013558179 / 12.0
            return 1.0  # mặc định kN-m

    # Nhánh SAP2000: parse theo TÊN cột (vị trí khác hẳn ETABS)
    if sap_idx is not None:
        return _parse_sap_clipboard(lines, hi, sap_idx,
                                    only_combinations, _unit_factor)

    f_force, f_moment = 1.0, 1.0
    if hi + 1 < len(lines):
        unit_parts = lines[hi + 1].split("\t")
        # Lấy đơn vị tại cột P (lực) và cột M2 (mô men)
        u_p = unit_parts[C_P].strip() if C_P < len(unit_parts) else ""
        u_m = unit_parts[C_M2].strip() if C_M2 < len(unit_parts) else ""
        f_force = _unit_factor(u_p, "force")
        f_moment = _unit_factor(u_m, "moment")

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
        # Gắn Step Type vào tên tổ hợp: TH14max, TH15min
        if has_step:
            step = parts[5].strip().lower() if len(parts) > 5 else ""
            if step == "max":
                case = f"{case}max"
            elif step == "min":
                case = f"{case}min"
        p = num(parts, C_P) * f_force
        forces.append(EtabsForce(
            story=parts[C_STORY].strip() if C_STORY < len(parts) else "",
            column=parts[C_COL].strip() if C_COL < len(parts) else "",
            case=case,
            case_type=case_type,
            station=num(parts, C_STATION),
            N=-p,
            Mx=num(parts, C_M2) * f_moment,
            My=num(parts, C_M3) * f_moment,
            Q2=num(parts, C_V2) * f_force,
            Q3=num(parts, C_V3) * f_force,
        ))
    if not forces:
        raise ValueError("Không đọc được dòng nội lực nào từ clipboard.")
    return forces
