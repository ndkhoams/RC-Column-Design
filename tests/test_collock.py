"""Khóa khung nhìn mặt cắt CỘT + popup combo thấy ít nhất 20 dòng.

Quyết user 2026-10-24: ô mặt cắt cột về dạng tĩnh như trước khi có
zoom (không wheel-zoom/kéo-pan/nút zoom/double-click reset), giữ
fit legend thép (a5cb3d8) gắn độc lập. Quyết user 2026-10-25:
ô mặt cắt vách cũng khóa khung nhìn như cột (bỏ zoom/pan riêng,
thêm checkbox "Hiển thị vùng nén" như cột) — test cũ "vách giữ
zoom riêng" đã lỗi thời và được thay bằng test khóa tĩnh vách
bên dưới. Popup "Chọn combo động đất" phải hiện ít nhất 20 dòng
không cần cuộn.

Các test này không cần màn hình: kiểm tra ở mức source (không còn
cơ chế zoom cột nào) và hàm thuần tính chiều cao list.
"""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _src(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_section_zoom_has_no_zoom_machinery():
    import gui.section_zoom as sz
    assert hasattr(sz, "attach_section_legend_fit")
    assert hasattr(sz, "_fit_section_legend_now")
    for name in ("attach_section_zoom", "zoom_step", "zoom_reset",
                 "_apply_limits"):
        assert not hasattr(sz, name), name


def test_column_renderers_have_no_zoom_references():
    for rel in ("gui/result_renderer.py", "gui/tcvn_mixin.py"):
        src = _src(rel)
        for token in ("attach_section_zoom", "zoom_step", "zoom_reset",
                      "_col_zst", "_col_zoom", "_cz_step", "_cz_reset"):
            assert token not in src, f"{rel} còn {token}"
        assert "attach_section_legend_fit" in src, rel


def test_section_zoom_source_has_no_view_bindings():
    src = _src("gui/section_zoom.py")
    for token in ("<MouseWheel>", "<Button-4>", "<Button-5>",
                  "<B1-Motion>", "<Double-Button-1>"):
        assert token not in src, token


def test_wall_section_also_static_like_column():
    """Quyết user 2026-10-25: ô mặt cắt vách khóa khung nhìn như
    cột — không còn cơ chế zoom/pan riêng, chỉ checkbox vùng nén."""
    src = _src("gui/wall_mixin.py")
    for token in ("_sec_zoom_step", "_sec_zoom_reset", "_sec_zoom_setup",
                  "_sec_zoom_wheel", "_sec_zoom_press",
                  "_sec_zoom_motion"):
        assert token not in src, token
    assert "section_zoom" not in src
    assert "Hiển thị vùng nén" in src
    assert "_wall_show_compression" in src


def test_list_height_for_rows():
    from gui.dialog_center import list_height_for_rows
    assert list_height_for_rows(25, 24) == 480
    assert list_height_for_rows(20, 24) == 480
    assert list_height_for_rows(5, 24) == 120
    assert list_height_for_rows(30, 24, min_rows=10) == 240
    assert list_height_for_rows(0, 24) == 0
    assert list_height_for_rows(10, 0) == 0
    assert list_height_for_rows(10, -5) == 0
