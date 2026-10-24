"""Tên file PDF xuất ra phân biệt CỘT/VÁCH (quy ước 2026-10-25).

Helper thuần túy rc_column/pdf_naming.py + guard: gui/pdf_mixin.py
không còn mẫu tên cũ (TMTT không có COT/VACH).
"""

import os

import pytest

from rc_column.pdf_naming import default_pdf_filename


def test_column_summary_and_detail():
    assert default_pdf_filename("cot", "TCVN", "COTBTCT", True) == \
        "TMTT-COT-TCVN-COTBTCT.pdf"
    assert default_pdf_filename("cot", "TCVN", "COTBTCT", False) == \
        "TMTT-FULL-COT-TCVN-COTBTCT.pdf"
    assert default_pdf_filename("cot", "ACI", "C2", True) == \
        "TMTT-COT-ACI-C2.pdf"
    assert default_pdf_filename("cot", "EC2", "C1", False) == \
        "TMTT-FULL-COT-EC2-C1.pdf"


def test_wall_summary_and_detail():
    assert default_pdf_filename("vach", "TCVN", "COTBTCT", True) == \
        "TMTT-VACH-TCVN-COTBTCT.pdf"
    assert default_pdf_filename("vach", "TCVN", "COTBTCT", False) == \
        "TMTT-FULL-VACH-TCVN-COTBTCT.pdf"


def test_member_normalized_and_empty():
    # strip + upper, giữ nguyên hành vi cũ ở call site.
    assert default_pdf_filename("cot", "tcvn", "  cotbtct ", True) == \
        "TMTT-COT-TCVN-COTBTCT.pdf"
    assert default_pdf_filename("cot", "TCVN", "", True) == \
        "TMTT-COT-TCVN.pdf"
    assert default_pdf_filename("vach", "TCVN", None, False) == \
        "TMTT-FULL-VACH-TCVN.pdf"
    assert default_pdf_filename("cot", "", "C1", True) == \
        "TMTT-COT-C1.pdf"


def test_bad_kind_rejected():
    with pytest.raises(ValueError):
        default_pdf_filename("dam", "TCVN", "C1", True)


def test_pdf_mixin_uses_helper_no_legacy_pattern():
    # Guard hồi quy: mọi đường xuất trong pdf_mixin đều qua helper,
    # không còn f-string tên cũ thiếu COT/VACH.
    path = os.path.join(os.path.dirname(__file__), "..",
                        "gui", "pdf_mixin.py")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    assert "default_pdf_filename(" in src
    assert "TMTT{_full}" not in src
    assert 'f"TMTT-{_ck}.pdf"' not in src
    assert 'f"TMTT.pdf"' not in src
