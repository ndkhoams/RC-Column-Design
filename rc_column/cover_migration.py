"""Migration ngữ nghĩa lớp bảo vệ (cover) — load-time, chỉ trong bộ nhớ.

Quy ước mới (user chốt 2026-10-24): ô nhập cover = lớp bảo vệ cốt đai
``c`` (từ mép bê tông tới mặt ngoài cốt đai); lớp bảo vệ cốt dọc do
engine tự tính: ``c_dọc = c + d_đai``; tâm cốt dọc cách mặt bê tông
``c + d_đai + d_dọc/2``.

File cũ (không có khóa ``"cover_semantics": "stirrup"``) lưu cover theo
nghĩa cũ (tới mặt cốt dọc) nên khi mở phải dịch: ``c_mới = c_cũ − d_đai``
— dịch này giữ nguyên tuyệt đối hình học fiber (vì engine mới cộng lại
đúng ``d_đai``), chỉ làm h0/d cắt tăng đúng ``d_đai`` (số cắt cũ đang
bảo thủ hơn, không thiên không an toàn).

- Cột: ``d_đai = sw_dia`` (đai bao, không phải đai giữa); thiếu
  ``sw_dia`` trong JSON rất cũ → fallback 8 mm (đúng fallback của
  ``_apply_data``); áp cả 2 khóa ``"cover"`` và ``"ccover"``.
- Vách: ``d_đai = dia_h`` thống nhất cho mọi nhóm thép (khuyến nghị
  kiểm toán §3.2 — GIẢ ĐỊNH CHỜ USER HIỆU CHỈNH: nếu thực tế đai vùng
  biên nằm ngoài thép ngang thì thép biên phải dùng ``tie_dia_be``,
  lệch ``|dia_h − tie_dia_be|`` ở preset mẫu (12 vs 10 → 2 mm), và
  migration không còn một giá trị thỏa cả 2 nhóm).
- BỎ QUA file DXF (``"kind"`` bắt đầu bằng "Tiết diện bất kỳ"): fiber
  từ bản vẽ, cover chỉ nuôi công thức cắt vốn đã đúng ngữ nghĩa c_đai
  — trừ ``d_đai`` ở đây sẽ làm h0/d tăng oan.
- ``c_mới < 0``: hình học cũ vốn phi thực tế (đai chui ra ngoài bê tông
  nếu hiểu theo nghĩa mới) → kẹp về 0 VÀ trả về cảnh báo để GUI hiển
  thị (không clamp im lặng).
- KHÔNG ghi đè file chỉ vì mở: các hàm này chỉ trả dict đã dịch trong
  bộ nhớ; dấu ``"cover_semantics": "stirrup"`` chỉ được đóng khi user
  lưu lại (xem ``_collect_data`` / ``_collect_wall``).
"""

COVER_SEMANTICS_KEY = "cover_semantics"
COVER_SEMANTICS_NEW = "stirrup"
_DXF_KIND_PREFIX = "Tiết diện bất kỳ"

# Fallback đúng fallback của GUI khi khóa thiếu trong JSON rất cũ.
_FALLBACK_SW_DIA = 8.0
_FALLBACK_DIA_H = 12.0


def _fnum(v, default):
    """Parse số từ str/float/int; lỗi hoặc None -> default."""
    try:
        if v is None or (isinstance(v, str) and not v.strip()):
            return default
        return float(str(v).replace(",", "."))
    except Exception:
        return default


def _fmt(v):
    """Số nguyên dạng float -> int cho JSON gọn (khớp wall_to_dict)."""
    f = float(v)
    return int(f) if f.is_integer() else f


def cover_long(cover, stirrup_dia):
    """Lớp bảo vệ tới mặt cốt dọc theo quy ước mới: c_dọc = c + d_đai."""
    return float(cover) + float(stirrup_dia)


def migrate_cover_value(old, stirrup_dia):
    """Dịch một giá trị cover nghĩa cũ sang nghĩa mới.

    Trả về (giá trị_mới, bị_kẹp): bị_kẹp True khi c_mới < 0 và đã
    kẹp về 0 (kèm cảnh báo ở tầng gọi).
    """
    new = float(old) - float(stirrup_dia)
    if new < 0:
        return 0.0, True
    return new, False


def _needs_migration(d):
    """File cũ = chưa có dấu ngữ nghĩa mới (kể cả thiếu khóa)."""
    return isinstance(d, dict) and d.get(COVER_SEMANTICS_KEY) != COVER_SEMANTICS_NEW


def migrate_column_dict(d):
    """Dịch cover cột trong dict JSON cũ -> dict mới + danh sách cảnh báo.

    Không đổi dict gốc. Bỏ qua (trả nguyên bản) khi: đã có dấu mới,
    hoặc là file DXF. Áp cả "cover" và "ccover" khi khóa có mặt.
    """
    if not _needs_migration(d):
        return dict(d) if isinstance(d, dict) else d, []
    kind = str(d.get("kind", "") or "")
    if kind.startswith(_DXF_KIND_PREFIX):
        return dict(d), []
    sw = _fnum(d.get("sw_dia"), _FALLBACK_SW_DIA)
    out = dict(d)
    warns = []
    for key in ("cover", "ccover"):
        if key in d:
            new, clamped = migrate_cover_value(_fnum(d[key], 30.0), sw)
            out[key] = _fmt(new)
            if clamped:
                warns.append(
                    f"Lớp bảo vệ cột '{key}' cũ {d[key]} mm trừ đai bao "
                    f"{sw:g} mm ra số âm — đã kẹp về 0 mm (hình học cũ "
                    f"phi thực tế: đai chui ra ngoài bê tông). Kiểm tra "
                    f"lại ô cover và đường kính đai.")
    return out, warns


def migrate_wall_dict(d):
    """Dịch cover vách trong dict JSON cũ -> dict mới + danh sách cảnh báo.

    Không đổi dict gốc. Bỏ qua khi đã có dấu mới. Vách không có mode
    tọa độ tuyệt đối nên migration áp cho mọi file vách.
    """
    if not _needs_migration(d):
        return dict(d) if isinstance(d, dict) else d, []
    dia_h = _fnum(d.get("dia_h"), _FALLBACK_DIA_H)
    out = dict(d)
    warns = []
    if "cover" in d:
        new, clamped = migrate_cover_value(_fnum(d["cover"], 25.0), dia_h)
        out["cover"] = _fmt(new)
        if clamped:
            warns.append(
                f"Lớp bảo vệ vách cũ {d['cover']} mm trừ thép ngang "
                f"dia_h {dia_h:g} mm ra số âm — đã kẹp về 0 mm (hình học "
                f"cũ phi thực tế). Kiểm tra lại ô cover và dia_h.")
    return out, warns
