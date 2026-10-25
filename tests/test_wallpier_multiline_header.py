"""Paste ETABS Pier Forces, lần 2: header tách nhiều dòng (file thật).

BÀI HỌC LẦN 1 (head c3c5622): test fixture chép từ chat (header 1 dòng
"Story | Pier | Output Case | ...") parse được 42/42, nhưng user chạy
đúng bản c3c5622, paste trực tiếp từ ETABS ở panel vách vẫn báo
"Không đọc được dòng nội lực nào từ clipboard."

NGUYÊN NHÂN GỐC: file thật user gửi sau đó
(tests/noi_luc_pier_real.txt, copy nguyên byte 3572 byte, CRLF,
54 dòng) KHÔNG có header 1 dòng. 13 dòng đầu là header bị tách:
"Story" / "\\tPier" / "\\tOutput Case" / "\\tCase Type" /
"\\tStep Type" / "\\tLocation" / "\\tP" / "kN\\tV2" / "kN\\tV3" /
"kN\\tT" / "kN-m\\tM2" / "kN-m\\tM3" / "kN-m", rồi mới tới 42 dòng
dữ liệu tab-separated 1 dòng bình thường. Parser cũ tìm dòng header
đơn chứa "output case" trong 5 dòng đầu nên nhặt nhầm đúng dòng
"Output Case" rời rạc làm header, pier_idx không thấy "pier" nên
rơi về nhánh Columns theo vị trí và loại hết mọi dòng.

SAU SỬA (xem _coalesce_multiline_header): chỉ gom header nhiều dòng
khi KHÔNG có dòng header 1 dòng đầy đủ nào; gom token theo thứ tự,
bỏ token đơn vị, dừng khi đủ cột rồi kiểm chứng dòng dữ liệu đầu
tiên bằng ô P là số. Ánh xạ giữ nguyên đợt c3c5622 (không đổi):
Story -> story, Pier -> column (Label), Output Case -> case
(Max -> "ULS14max", Min -> "ULS14min", rỗng -> trơn), P âm = nén
-> N = -P, M2 -> Mx, M3 -> My, V2 -> Q2, V3 -> Q3, T bỏ,
Location -> location + Station mã hoá (Bottom 0.0 / Top 1.0 —
mã vị trí, KHÔNG phải mét).

File test này là fixture QUYẾT ĐỊNH: đọc chính file thật đã copy
nguyên byte, không gõ lại nội dung qua chat.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rc_column.etabs_import import (
    parse_etabs_clipboard, merge_combo_max_min,
    _coalesce_multiline_header, _is_full_header_line)

REAL_TXT = os.path.join(os.path.dirname(__file__), "noi_luc_pier_real.txt")


def _read_real():
    with open(REAL_TXT, "rb") as f:
        raw = f.read()
    # Khẳng định đây đúng là file thật user gửi, không phải bản gõ lại.
    assert len(raw) == 3572
    assert raw.startswith(b"Story\r\n\tPier\r\n\tOutput Case\r\n")
    return raw.decode("ascii")


def test_real_file_multiline_header_parses_42():
    forces = parse_etabs_clipboard(_read_real(), only_combinations=True)
    assert len(forces) == 42
    plain = [f for f in forces if f.case in {f"ULS{i}" for i in range(1, 14)}]
    assert len(plain) == 26
    env = sorted(f.case for f in forces if f.case.startswith("ULS14"))
    assert env == ["ULS14max", "ULS14max", "ULS14min", "ULS14min"]
    assert all(f.story == "F3" and f.column == "E2" for f in forces)
    assert all(f.location in ("Top", "Bottom") for f in forces)
    assert sum(1 for f in forces if f.location == "Top") == 21
    assert sum(1 for f in forces if f.location == "Bottom") == 21


def test_real_file_sample_values_and_merge():
    forces = parse_etabs_clipboard(_read_real(), only_combinations=True)
    first = forces[0]
    assert (first.story, first.column, first.case, first.location,
            first.station) == ("F3", "E2", "ULS1", "Top", 1.0)
    assert abs(first.N - 561.1525) < 1e-9
    assert abs(first.Q2 + 9.5329) < 1e-9
    assert abs(first.My - 12.1744) < 1e-9
    env = [f for f in forces if f.case == "ULS14max"
           and f.location == "Top"][0]
    assert abs(env.N + 337.5598) < 1e-9
    assert abs(env.Q2 - 181.4892) < 1e-9
    assert abs(env.My - 258.8519) < 1e-9
    last = forces[-1]
    assert (last.case, last.location) == ("ULS17min", "Bottom")
    assert abs(last.N - 1018.894) < 1e-9
    # Gộp ULS14 giữ Top/Bottom riêng: 42 -> 40, 2 cặp.
    out, n = merge_combo_max_min(forces, {"ULS14"})
    assert n == 2 and len(out) == 40
    merged = {f.location: f for f in out if f.case == "ULS14"}
    assert abs(merged["Top"].N - 1255.3942) < 1e-9
    assert abs(merged["Top"].My - 258.8519) < 1e-9


def test_coalesce_is_not_hardcoded_to_real_file():
    # Header tách dòng với giá trị hoàn toàn khác file thật: chứng minh
    # thuật toán gom theo token, không hardcode 13 dòng hay F3/E2.
    text = (
        "Story\n"
        "\tPier\n"
        "\tOutput Case\n"
        "\tCase Type\n"
        "\tStep Type\n"
        "\tLocation\n"
        "\tP\n"
        "kN\tV2\n"
        "kN\tV3\n"
        "kN\tT\n"
        "kN-m\tM2\n"
        "kN-m\tM3\n"
        "kN-m\n"
        "S9\tP7\tCOMB1\tCombination\t\tTop\t-100\t5\t2\t0\t3\t4\n"
        "S9\tP7\tCOMB1\tCombination\t\tBottom\t-120\t-6\t-3\t0\t-4\t-5\n"
    )
    forces = parse_etabs_clipboard(text, only_combinations=True)
    assert len(forces) == 2
    assert (forces[0].story, forces[0].column, forces[0].location) == (
        "S9", "P7", "Top")
    assert abs(forces[0].N - 100) < 1e-9
    assert abs(forces[1].N - 120) < 1e-9


def test_full_header_line_detection():
    # Dòng header 1 dòng đầy đủ -> không gom; dòng "Output Case" rời
    # rạc -> không phải header đầy đủ, phải gom mới parse được.
    full = ("Story\tPier\tOutput Case\tCase Type\tStep Type\tLocation\t"
            "P\tV2\tV3\tT\tM2\tM3")
    assert _is_full_header_line(full) is True
    assert _is_full_header_line("Output Case") is False
    assert _is_full_header_line("Story") is False
    lines = _read_real().splitlines()
    assert _coalesce_multiline_header(lines) is not None
    synthetic, data_start = _coalesce_multiline_header(lines)
    assert synthetic.split("\t") == [
        "story", "pier", "output case", "case type", "step type",
        "location", "p", "v2", "v3", "t", "m2", "m3"]
    assert lines[data_start].startswith("F3\tE2\tULS1")
