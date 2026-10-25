"""Paste ETABS Pier Forces cho vách (lỗi user báo 2026-10-25 12:00).

Trước sửa: clipboard Pier (Story | Pier | Output Case | Case Type |
Step Type | Location | P | V2 | V3 | T | M2 | M3) rơi vào nhánh
Columns theo vị trí cố định: C_CASE=3 trỏ vào "Case Type", C_TYPE=4
trỏ vào "Step Type" nên điều kiện only_combinations ("combination"
trong case_type) loại hết mọi dòng -> ValueError "Không đọc được
dòng nội lực nào từ clipboard." (popup trong ảnh user gửi).

Sau sửa: nhánh Pier parse theo TÊN cột (xem _parse_pier_clipboard).
Ánh xạ chốt: Story -> story, Pier -> column (hiển thị Label),
Output Case -> case (Max -> "ULS14max", Min -> "ULS14min", rỗng ->
trơn, đúng quy ước cột), Location -> location + Station mã hoá
(Bottom 0.0 / Top 1.0 — mã vị trí, KHÔNG phải mét; Top/Bottom của
cùng combo là 2 dòng khác nhau, gộp max/min không lẫn nhau),
P âm = nén -> N = -P, M2 -> Mx, M3 -> My, V2 -> Q2, V3 -> Q3,
T không có cột trong EtabsForce/bảng nên bỏ.

Fixture 42 dòng dưới đây chép từ nội dung clipboard user paste vào
chat 2026-10-25 (bài học cũ: chat có thể lệch byte — test khẳng định
số dòng + các giá trị mẫu; nếu user gửi file thật sau này mà khác
fixture này thì fixture phải cập nhật theo file thật).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rc_column.etabs_import import (
    parse_etabs_clipboard, merge_combo_max_min, read_etabs_excel)

PIER_TSV = (
    "Story\tPier\tOutput Case\tCase Type\tStep Type\tLocation\tP\tV2\tV3\tT\tM2\tM3\n"
    "\t\t\t\t\t\tkN\tkN\tkN\tkN-m\tkN-m\tkN-m\n"
    "F3\tE2\tULS1\tCombination\t\tTop\t-561.1525\t-9.5329\t-2.5546\t0.4853\t-2.1619\t12.1744\n"
    "F3\tE2\tULS1\tCombination\t\tBottom\t-585.4597\t-9.5329\t-2.5546\t0.4853\t-11.3585\t-22.144\n"
    "F3\tE2\tULS2\tCombination\t\tTop\t-432.1482\t12.5258\t-2.0167\t0.275\t-1.9833\t-18.2476\n"
    "F3\tE2\tULS2\tCombination\t\tBottom\t-456.4553\t12.5258\t-2.0167\t0.275\t-9.2434\t26.8453\n"
    "F3\tE2\tULS3\tCombination\t\tTop\t-605.3008\t-27.8427\t-3.2398\t0.5348\t-0.588\t35.518\n"
    "F3\tE2\tULS3\tCombination\t\tBottom\t-629.608\t-27.8427\t-3.2398\t0.5348\t-12.2511\t-64.7159\n"
    "F3\tE2\tULS4\tCombination\t\tTop\t-548.1206\t-4.5714\t2.3106\t0.0328\t-10.0343\t4.0613\n"
    "F3\tE2\tULS4\tCombination\t\tBottom\t-572.4277\t-4.5714\t2.3106\t0.0328\t-1.716\t-12.3956\n"
    "F3\tE2\tULS5\tCombination\t\tTop\t-489.3284\t-10.7456\t-7.5671\t0.777\t7.4629\t13.2091\n"
    "F3\tE2\tULS5\tCombination\t\tBottom\t-513.6356\t-10.7456\t-7.5671\t0.777\t-19.7785\t-25.475\n"
    "F3\tE2\tULS6\tCombination\t\tTop\t-483.2338\t8.633\t-2.0042\t0.3684\t-2.7898\t-12.0202\n"
    "F3\tE2\tULS6\tCombination\t\tBottom\t-507.541\t8.633\t-2.0042\t0.3684\t-10.005\t19.0586\n"
    "F3\tE2\tULS7\tCombination\t\tTop\t-639.0712\t-27.6987\t-3.105\t0.6023\t-1.534\t36.3689\n"
    "F3\tE2\tULS7\tCombination\t\tBottom\t-663.3784\t-27.6987\t-3.105\t0.6023\t-12.712\t-63.3465\n"
    "F3\tE2\tULS8\tCombination\t\tTop\t-587.609\t-6.7545\t1.8903\t0.1504\t-10.0356\t8.0579\n"
    "F3\tE2\tULS8\tCombination\t\tBottom\t-611.9162\t-6.7545\t1.8903\t0.1504\t-3.2304\t-16.2582\n"
    "F3\tE2\tULS9\tCombination\t\tTop\t-534.6961\t-12.3113\t-6.9996\t0.8202\t5.7118\t16.2908\n"
    "F3\tE2\tULS9\tCombination\t\tBottom\t-559.0032\t-12.3113\t-6.9996\t0.8202\t-19.4866\t-28.0297\n"
    "F3\tE2\tULS10\tCombination\t\tTop\t-470.5413\t10.8326\t-1.9448\t0.347\t-2.7834\t-15.0615\n"
    "F3\tE2\tULS10\tCombination\t\tBottom\t-494.8485\t10.8326\t-1.9448\t0.347\t-9.7847\t23.9357\n"
    "F3\tE2\tULS11\tCombination\t\tTop\t-643.694\t-29.536\t-3.1678\t0.6069\t-1.3882\t38.7041\n"
    "F3\tE2\tULS11\tCombination\t\tBottom\t-668.0011\t-29.536\t-3.1678\t0.6069\t-12.7924\t-67.6255\n"
    "F3\tE2\tULS12\tCombination\t\tTop\t-586.5137\t-6.2646\t2.3825\t0.1048\t-10.8344\t7.2474\n"
    "F3\tE2\tULS12\tCombination\t\tBottom\t-610.8209\t-6.2646\t2.3825\t0.1048\t-2.2573\t-15.3052\n"
    "F3\tE2\tULS13\tCombination\t\tTop\t-527.7216\t-12.4388\t-7.4952\t0.849\t6.6628\t16.3952\n"
    "F3\tE2\tULS13\tCombination\t\tBottom\t-552.0287\t-12.4388\t-7.4952\t0.849\t-20.3198\t-28.3846\n"
    "F3\tE2\tULS14\tCombination\tMax\tTop\t337.5598\t181.4892\t24.1413\t4.6631\t42.7169\t258.8519\n"
    "F3\tE2\tULS14\tCombination\tMax\tBottom\t315.4624\t181.4892\t24.1413\t4.6631\t42.0487\t410.4749\n"
    "F3\tE2\tULS14\tCombination\tMin\tTop\t-1255.3942\t-195.09\t-28.814\t-3.9435\t-44.9692\t-243.5238\n"
    "F3\tE2\tULS14\tCombination\tMin\tBottom\t-1277.4916\t-195.09\t-28.814\t-3.9435\t-61.1225\t-444.1095\n"
    "F3\tE2\tULS15\tCombination\tMax\tTop\t66.2123\t89.6036\t56.4025\t7.2187\t101.6768\t142.1032\n"
    "F3\tE2\tULS15\tCombination\tMax\tBottom\t44.1149\t89.6036\t56.4025\t7.2187\t99.153\t196.0393\n"
    "F3\tE2\tULS15\tCombination\tMin\tTop\t-984.0467\t-103.2043\t-61.0752\t-6.4991\t-103.9291\t-126.775\n"
    "F3\tE2\tULS15\tCombination\tMin\tBottom\t-1006.1441\t-103.2043\t-61.0752\t-6.4991\t-118.2269\t-229.6739\n"
    "F3\tE2\tULS16\tCombination\tMax\tTop\t324.8099\t181.2587\t24.1757\t4.6897\t42.5012\t259.1835\n"
    "F3\tE2\tULS16\tCombination\tMax\tBottom\t302.7125\t181.2587\t24.1757\t4.6897\t41.9569\t409.9765\n"
    "F3\tE2\tULS16\tCombination\tMin\tTop\t-1268.1441\t-195.3205\t-28.7796\t-3.917\t-45.1848\t-243.1923\n"
    "F3\tE2\tULS16\tCombination\tMin\tBottom\t-1290.2415\t-195.3205\t-28.7796\t-3.917\t-61.2143\t-444.6079\n"
    "F3\tE2\tULS17\tCombination\tMax\tTop\t53.4624\t89.3731\t56.4369\t7.2452\t101.4611\t142.4347\n"
    "F3\tE2\tULS17\tCombination\tMax\tBottom\t31.365\t89.3731\t56.4369\t7.2452\t99.0612\t195.5409\n"
    "F3\tE2\tULS17\tCombination\tMin\tTop\t-996.7965\t-103.4349\t-61.0408\t-6.4725\t-104.1447\t-126.4435\n"
    "F3\tE2\tULS17\tCombination\tMin\tBottom\t-1018.894\t-103.4349\t-61.0408\t-6.4725\t-118.3187\t-230.1723\n"
)


def _by_case_loc(forces, case, loc):
    return [f for f in forces if f.case == case and f.location == loc]


def test_pier_clipboard_count_and_mapping():
    forces = parse_etabs_clipboard(PIER_TSV, only_combinations=True)
    assert len(forces) == 42
    # ULS1-13: 26 dòng trơn, ULS14-17: 16 dòng max/min
    plain = [f for f in forces if f.case in {f"ULS{i}" for i in range(1, 14)}]
    assert len(plain) == 26
    env = [f for f in forces if f.case.startswith("ULS14")]
    assert sorted(f.case for f in env) == [
        "ULS14max", "ULS14max", "ULS14min", "ULS14min"]
    # Mọi dòng đều F3/E2, Top/Bottom phân biệt, không dòng nào mất location
    assert all(f.story == "F3" and f.column == "E2" for f in forces)
    assert all(f.location in ("Top", "Bottom") for f in forces)
    assert sum(1 for f in forces if f.location == "Top") == 21
    assert sum(1 for f in forces if f.location == "Bottom") == 21
    assert {(f.case, f.location) for f in forces} == {
        (c, loc) for c in
        [f"ULS{i}" for i in range(1, 14)] +
        [f"ULS{i}{s}" for i in range(14, 18) for s in ("max", "min")]
        for loc in ("Top", "Bottom")}


def test_pier_clipboard_sample_values():
    forces = parse_etabs_clipboard(PIER_TSV, only_combinations=True)
    first = forces[0]
    assert (first.story, first.column, first.case, first.location,
            first.station) == ("F3", "E2", "ULS1", "Top", 1.0)
    assert abs(first.N - 561.1525) < 1e-9  # N = -P
    assert abs(first.Q2 + 9.5329) < 1e-9
    assert abs(first.Q3 + 2.5546) < 1e-9
    assert abs(first.Mx + 2.1619) < 1e-9
    assert abs(first.My - 12.1744) < 1e-9
    bot = _by_case_loc(forces, "ULS1", "Bottom")[0]
    assert bot.station == 0.0 and abs(bot.N - 585.4597) < 1e-9
    # Dòng envelope: P dương (kéo) -> N âm, giữ đúng dấu các thành phần
    env = _by_case_loc(forces, "ULS14max", "Top")[0]
    assert abs(env.N + 337.5598) < 1e-9
    assert abs(env.Q2 - 181.4892) < 1e-9
    assert abs(env.My - 258.8519) < 1e-9
    env_min = _by_case_loc(forces, "ULS14min", "Bottom")[0]
    assert abs(env_min.N - 1277.4916) < 1e-9
    assert abs(env_min.My + 444.1095) < 1e-9
    last = forces[-1]
    assert (last.case, last.location) == ("ULS17min", "Bottom")
    assert abs(last.N - 1018.894) < 1e-9


def test_pier_merge_keeps_top_bottom_separate():
    forces = parse_etabs_clipboard(PIER_TSV, only_combinations=True)
    out, n = merge_combo_max_min(forces, {"ULS14"})
    # Top và Bottom gộp RIÊNG: 2 dòng gộp, tổng 42 -> 40, location giữ
    assert n == 2 and len(out) == 40
    merged = sorted([f for f in out if f.case == "ULS14"],
                    key=lambda f: f.location)
    assert [f.location for f in merged] == ["Bottom", "Top"]
    top = merged[1]
    assert abs(top.N - 1255.3942) < 1e-9  # max-|.| của cặp Top
    assert abs(top.My - 258.8519) < 1e-9


def test_columns_clipboard_unchanged():
    # Đường cột ETABS (Element Forces - Columns, có Unique Name + Station)
    text = (
        "Story\tColumn\tUnique Name\tOutput Case\tCase Type\tStep Type\t"
        "Station\tP\tV2\tV3\tT\tM2\tM3\n"
        "\t\t\t\t\t\t\tkN\tkN\tkN\tkN-m\tkN-m\tkN-m\n"
        "S1\tC1\t1\tULS1\tCombination\t\t0\t-1000\t10\t5\t0\t20\t30\n"
        "S1\tC1\t1\tULS14\tCombination\tMax\t3.3\t-800\t15\t6\t0\t25\t40\n"
        "S1\tC1\t1\tULS14\tCombination\tMin\t3.3\t-1200\t-12\t-4\t0\t-18\t-35\n"
    )
    forces = parse_etabs_clipboard(text, only_combinations=True)
    assert len(forces) == 3
    assert forces[0].case == "ULS1" and forces[0].station == 0.0
    assert forces[0].location == ""  # cột không có location
    assert abs(forces[0].N - 1000) < 1e-9
    assert forces[1].case == "ULS14max" and forces[2].case == "ULS14min"


def test_sap_frames_clipboard_unchanged():
    text = (
        "Frame\tStation\tOutputCase\tCaseType\tStepType\tP\tV2\tV3\tT\tM2\tM3\n"
        "\t\t\t\t\tkN\tkN\tkN\tkN-m\tkN-m\tkN-m\n"
        "F1\t0\tULS1\tCombination\t\t-500\t8\t3\t0\t10\t12\n"
    )
    forces = parse_etabs_clipboard(text, only_combinations=True)
    assert len(forces) == 1
    assert forces[0].story == "Story" and forces[0].column == "F1"
    assert abs(forces[0].N - 500) < 1e-9


def test_pier_excel(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pier Forces"
    ws.append(["Story", "Pier", "Output Case", "Case Type", "Step Type",
               "Location", "P", "V2", "V3", "T", "M2", "M3"])
    ws.append(["", "", "", "", "", "", "kN", "kN", "kN", "kN-m",
               "kN-m", "kN-m"])
    ws.append(["F3", "E2", "ULS1", "Combination", "", "Top",
               -561.1525, -9.5329, -2.5546, 0.4853, -2.1619, 12.1744])
    ws.append(["F3", "E2", "ULS14", "Combination", "Max", "Top",
               337.5598, 181.4892, 24.1413, 4.6631, 42.7169, 258.8519])
    path = tmp_path / "pier.xlsx"
    wb.save(path)
    forces = read_etabs_excel(str(path), only_combinations=True)
    assert len(forces) == 2
    assert (forces[0].column, forces[0].location) == ("E2", "Top")
    assert abs(forces[0].N - 561.1525) < 1e-9
    assert forces[1].case == "ULS14max"
    assert abs(forces[1].N + 337.5598) < 1e-9
