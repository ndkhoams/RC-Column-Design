"""Dấu P ở đường Paste from Clipboard của SAP2000 (lát 2026-10-29).

Quy ước chốt (giống đường Excel, user xác nhận Excel đã đúng):
cột nén SAP P âm -> app N dương, tức N = -P ở MỌI đường paste SAP.
Không đụng đường Excel, không đụng đường ETABS clipboard, không đổi
dấu V2/V3/M2/M3/T.

Số khóa lấy từ ảnh user gửi (bảng SAP2000 "Element Forces - Frames"):
Frame 361, LRFD_2, Station 0, P -1459,501 -> N +1459,501;
Station 1, P -1498,643 -> N +1498,643;
LRFD_1, Station 0, P -73,487 -> N +73,487.
(V2/V3/M2/M3 trong fixture đặt giá trị phân biệt 5/6/7/8 để khóa
luôn mapping cột: chỉ N được xét dấu, các thành phần khác giữ nguyên
giá trị và dấu như dữ liệu gốc.)

ĐỊNH DẠNG CLIPBOARD SAP THẬT được khóa ở đây (không dựng theo
định dạng ETABS):
- (a) Copy kiểu xuất Excel: dòng tiêu đề "TABLE:  Element Forces -
  Frames", dòng header 1 dòng, dòng đơn vị, rồi dữ liệu tab-separated.
  Ảnh user gửi có 12 cột (không cột StepType); file Excel SAP thật
  của user (NOI_LUC_SAP2000.xlsx, SAP2000 26.3.0) có 13 cột (có
  StepType, giá trị rỗng với tổ hợp thường) — khóa cả hai.
- (b) Copy trực tiếp từ bảng SAP (kiểu lưới CSI, như file thật
  noi_luc_pier_real.txt của ETABS): header tách nhiều dòng, đơn vị
  nằm ở đầu dòng cột sau ("KN\tV2", "KN-m\tM3"), có thêm cột trailing
  FrameElem/ElemStation sau M3, có hoặc không có dòng tiêu đề TABLE.
- (c) Chỉ dòng số liệu, không header (kiểu file thật nl.txt của user:
  mỗi dòng dính TAB đầu + CRLF, không cột StepType).

LÝ DO LÁT NÀY TỒN TẠI (trung thực về phạm vi): định dạng (a) và (c)
ĐÃ cho N đúng (+1459/+1498) trên code trước lát — test khóa chúng để
chúng không bao giờ trôi. Định dạng (b) có cột trailing thì TRƯỚC
LÁT BỊ LỖI HOÀN TOÀN: _coalesce_multiline_header dừng ngay ở M3 rồi
coi dòng "KN-m\tFrameElem" là dòng dữ liệu, kiểm chứng ô P thất bại
(chỉ có 2 trường) nên trả None -> parse_etabs_clipboard báo "Không
đọc được dòng nội lực nào từ clipboard" và clipboard SAP copy trực
tiếp không bao giờ vào được nhánh SAP với N = -P. Fixture 1 dòng
kiểu ETABS của đợt kiểm chứng trước (header 1 dòng, không TABLE,
không cột trailing) không đi qua _coalesce_multiline_header nên
không bắt được lỗi này. Sửa chỉ trong _coalesce_multiline_header
(rc_column/etabs_import.py): bỏ qua dòng "TABLE: ...", coi "Text"/"m"
là token đơn vị, và gom nốt các dòng header còn lại sau M3 trước khi
chốt dòng dữ liệu. Không đổi công thức N = -P ở bất kỳ nhánh nào,
không đổi đường Excel hay ETABS.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rc_column.etabs_import import parse_etabs_clipboard, read_etabs_excel

# Dữ liệu Frame 361 từ ảnh user gửi (V2/V3/T/M2/M3 đặt phân biệt).
DATA_13 = [
    "361\t0\tLRFD_2\tCombination\t\t-1459.501\t5\t6\t0\t7\t8\t361-1\t0",
    "361\t1\tLRFD_2\tCombination\t\t-1498.643\t5\t6\t0\t7\t8\t361-1\t1",
    "361\t0\tLRFD_1\tCombination\t\t-73.487\t5\t6\t0\t7\t8\t361-1\t0",
]
DATA_12 = [
    "361\t0\tLRFD_2\tCombination\t-1459.501\t5\t6\t0\t7\t8\t361-1\t0",
    "361\t1\tLRFD_2\tCombination\t-1498.643\t5\t6\t0\t7\t8\t361-1\t1",
    "361\t0\tLRFD_1\tCombination\t-73.487\t5\t6\t0\t7\t8\t361-1\t0",
]
EXPECTED = [
    ("361", "LRFD_2", 0.0, 1459.501),
    ("361", "LRFD_2", 1.0, 1498.643),
    ("361", "LRFD_1", 0.0, 73.487),
]


def _check_361(forces):
    assert len(forces) == 3
    for f, (col, case, st, n) in zip(forces, EXPECTED):
        assert (f.column, f.case, f.station) == (col, case, st)
        assert abs(f.N - n) < 1e-9
        # Các thành phần khác giữ nguyên giá trị/dấu, không bị đổi
        # theo N và không bị lệch cột (V2=5, V3=6, Mx=M2=7, My=M3=8).
        assert (f.Q2, f.Q3, f.Mx, f.My) == (5.0, 6.0, 7.0, 8.0)


def test_sap_clipboard_table_header_units_12col_photo():
    # (a) đúng định dạng ảnh: 12 cột, không StepType.
    txt = "\n".join([
        "TABLE:  Element Forces - Frames",
        "Frame\tStation\tOutputCase\tCaseType\tP\tV2\tV3\tT\tM2\tM3"
        "\tFrameElem\tElemStation",
        "Text\tm\tText\tText\tKN\tKN\tKN\tKN-m\tKN-m\tKN-m\tText\tm",
    ] + DATA_12)
    _check_361(parse_etabs_clipboard(txt))


def test_sap_clipboard_table_header_units_13col_excel_style():
    # (a) đúng định dạng file Excel SAP thật: 13 cột, có StepType rỗng.
    txt = "\n".join([
        "TABLE:  Element Forces - Frames",
        "Frame\tStation\tOutputCase\tCaseType\tStepType\tP\tV2\tV3\tT\tM2"
        "\tM3\tFrameElem\tElemStation",
        "Text\tm\tText\tText\tText\tKN\tKN\tKN\tKN-m\tKN-m\tKN-m"
        "\tText\tm",
    ] + DATA_13)
    _check_361(parse_etabs_clipboard(txt))


def test_sap_clipboard_multiline_direct_copy_with_trailing_cols():
    # (b) copy trực tiếp từ bảng SAP: header tách dòng + cột trailing.
    # TRƯỚC LÁT: lỗi "Không đọc được dòng nội lực nào từ clipboard".
    txt = (
        "Frame\n\tStation\n\tOutputCase\n\tCaseType\n\tStepType\n\tP\n"
        "KN\tV2\nKN\tV3\nKN\tT\nKN-m\tM2\nKN-m\tM3\n"
        "KN-m\tFrameElem\nText\tElemStation\nm\n"
        + "\n".join(DATA_13) + "\n"
    )
    _check_361(parse_etabs_clipboard(txt))


def test_sap_clipboard_multiline_direct_copy_with_table_title():
    # (b) như trên nhưng có thêm dòng tiêu đề TABLE ở đầu.
    # TRƯỚC LÁT: dòng TABLE bị gom thành token đầu, lệch mọi chỉ số
    # cột và cũng rơi về lỗi không đọc được dòng nào.
    txt = (
        "TABLE:  Element Forces - Frames\n"
        "Frame\n\tStation\n\tOutputCase\n\tCaseType\n\tStepType\n\tP\n"
        "KN\tV2\nKN\tV3\nKN\tT\nKN-m\tM2\nKN-m\tM3\n"
        "KN-m\tFrameElem\nText\tElemStation\nm\n"
        + "\n".join(DATA_13) + "\n"
    )
    _check_361(parse_etabs_clipboard(txt))


def test_sap_clipboard_noheader_nl_style():
    # (c) chỉ dòng số liệu kiểu file thật nl.txt: TAB đầu + CRLF,
    # không cột StepType.
    txt = "\r\n".join("\t" + d for d in DATA_12) + "\r\n"
    _check_361(parse_etabs_clipboard(txt))


def test_sap_clipboard_real_nl_file_unchanged():
    # File clipboard SAP thật của user (Frame 218, 126 dòng): N vẫn
    # bằng -P, không đổi bởi lát này.
    path = os.path.join(os.path.dirname(__file__), "..", "..",
                         "user", "files", "nl.txt")
    if not os.path.exists(path):
        # File user không nằm trong repo nên test này chỉ chạy khi
        # có file thật; thiếu file thì bỏ qua, không fail giả.
        return
    with open(path, encoding="utf-8") as f:
        forces = parse_etabs_clipboard(f.read())
    assert len(forces) == 126
    assert abs(forces[0].N - 114.562) < 1e-9  # P -114.562 -> N +114.562
    assert abs(forces[-1].N - 105.817) < 1e-9


def test_sap_excel_control_unchanged(tmp_path):
    # Đối chứng: đường Excel cùng số Frame 361 vẫn N = -P (không đổi).
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Element Forces - Frames"
    ws.append(["TABLE:  Element Forces - Frames"])
    ws.append(["Frame", "Station", "OutputCase", "CaseType", "StepType",
               "P", "V2", "V3", "T", "M2", "M3", "FrameElem",
               "ElemStation"])
    ws.append(["Text", "m", "Text", "Text", "Text", "KN", "KN", "KN",
               "KN-m", "KN-m", "KN-m", "Text", "m"])
    ws.append(["361", 0, "LRFD_2", "Combination", None, -1459.501,
               5, 6, 0, 7, 8, "361-1", 0])
    ws.append(["361", 1, "LRFD_2", "Combination", None, -1498.643,
               5, 6, 0, 7, 8, "361-1", 1])
    ws.append(["361", 0, "LRFD_1", "Combination", None, -73.487,
               5, 6, 0, 7, 8, "361-1", 0])
    path = tmp_path / "sap361.xlsx"
    wb.save(path)
    forces = read_etabs_excel(str(path), only_combinations=True)
    assert len(forces) == 3
    for f, (_col, _case, _st, n) in zip(forces, EXPECTED):
        assert abs(f.N - n) < 1e-9


def test_etabs_clipboard_control_unchanged():
    # Đối chứng: đường ETABS clipboard không đổi (C1 ULS1 P -1000).
    text = (
        "Story\tColumn\tUnique Name\tOutput Case\tCase Type\tStep Type\t"
        "Station\tP\tV2\tV3\tT\tM2\tM3\n"
        "\t\t\t\t\t\t\tkN\tkN\tkN\tkN-m\tkN-m\tkN-m\n"
        "S1\tC1\t1\tULS1\tCombination\t\t0\t-1000\t10\t5\t0\t20\t30\n"
    )
    forces = parse_etabs_clipboard(text, only_combinations=True)
    assert len(forces) == 1
    assert abs(forces[0].N - 1000) < 1e-9
