"""Cache mặt tương tác 3D (N-M2-M3) dùng chung cho cột (3 chuẩn) + vách.

Động cơ: bottleneck của view 3D là TÍNH LƯỚI — `surface_grid`
~900 `moment_capacity` calls (~0.67s), trong khi render mpl chỉ
~0.07-0.12s. Lưới mặt chỉ phụ thuộc (hình học tiết diện + bố trí
thép + model vật liệu), không phụ thuộc tổ hợp tải đang xem, nên
cache được: mở 3D lần 2+ (cùng tiết diện) gần như tức thì; chuyển
qua lại 2D/3D không tính lại.

Vị trí cache: module-level OrderedDict — NGOÀI dict kết quả
(dict kết quả lưu JSON, cấm nhét numpy array). LRU giữ tối đa
`_MAX_ENTRIES` entry để không phình RAM.

Fingerprint: sha1 ổn định với cùng input; đổi khi user sửa tiết
diện/thép/vật liệu/model rồi CHECK lại → cache miss → tính lại
đúng. Bao gồm cả tham số lưới (n_n × n_angles) nên đổi mật độ
lưới không bao giờ nhầm entry cũ.

KHÔNG đụng solver/D/C/JSON: chỉ cache KẾT QUẢ VẼ của
`surface_grid`/`moment_capacity` (đúng số đã tính, không tính lại
theo cách khác).
"""

from collections import OrderedDict
import hashlib

# Mật độ lưới hiển thị (đã đối chiếu ảnh 25x36 vs 17x25 ở 3 góc
# nhìn: mean abs diff ~0.003, ~2.3% pixel lệch >5% — chỉ ở mép
# anti-aliasing của đường wireframe; mắt thường không phân biệt
# được). 17x25 = 425 calls (giảm 53% so với 900 calls của 25x36).
SURF3D_N_N = 17
SURF3D_N_ANGLES = 25
# Số điểm đường cong N-Ma (giữ nguyên như cũ — rẻ, ~0.04s).
SURF3D_CURVE_N = 64

# Giới hạn entry (mặt + đường cong chung một LRU): mỗi mặt
# ~7KB, mỗi đường cong ~1.5KB — 8 entry < 100KB.
_MAX_ENTRIES = 8

_cache = OrderedDict()  # fp -> {"kind": "surf"|"curve", "data": ...}
_hits = 0
_misses = 0


def _r6(x):
    return f"{float(x):.6f}"


def _sha1(parts):
    h = hashlib.sha1()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _mat_fp(mat, role):
    """Fingerprint vật liệu — chịu được cả 3 họ material
    (TCVN: grade.name + gamma; ACI: fc/fy; EC2: fck/fyk)."""
    if mat is None:
        return f"{role}:none"
    g = getattr(mat, "grade", None)
    if g is not None and getattr(g, "name", None):
        gam = getattr(mat, "gamma_b", getattr(mat, "gamma_s", 1.0))
        return f"{role}:{g.name}|{_r6(gam)}"
    for attr in ("fc", "fck", "fy", "fyk"):
        if hasattr(mat, attr):
            return f"{role}:{attr}={_r6(getattr(mat, attr))}"
    return f"{role}:repr={_sha1([repr(mat)])[:16]}"


def _section_fp(sec):
    """Fingerprint tiết diện: hình học + lưới fiber (proxy qua số
    lượng + tổng diện tích) + bố trí thép + lỗ/đa giác."""
    kind = getattr(sec, "kind", "?")
    cx = _r6(getattr(sec, "cx", 0.0))
    cy = _r6(getattr(sec, "cy", 0.0))
    fibers = getattr(sec, "fibers", []) or []
    n_fib = len(fibers)
    ac = _r6(sum(getattr(f, "area", 0.0) for f in fibers))
    rebars = getattr(sec, "rebars", []) or []
    as_tot = _r6(sum(getattr(r, "area", 0.0) for r in rebars))
    rb = sorted((_r6(r.x), _r6(r.y), _r6(r.area)) for r in rebars)
    rb_h = _sha1(["|".join(",".join(t) for t in rb)])
    # Đa giác (vách Barbell/T/L/C/U, DXF): vertices + lỗ.
    poly = getattr(sec, "poly_verts", []) or []
    holes = getattr(sec, "poly_holes", []) or []

    def _ring_fp(rings):
        rs = []
        for ring in rings:
            pts = sorted((_r6(x), _r6(y)) for x, y in ring)
            rs.append(";".join(f"{x},{y}" for x, y in pts))
        return _sha1(sorted(rs))

    poly_h = _ring_fp(poly) if poly else "-"
    hole_h = _ring_fp(holes) if holes else "-"
    conc_h = _mat_fp(getattr(sec, "concrete", None), "c")
    steel_h = _mat_fp(getattr(sec, "steel", None), "s")
    return "|".join([kind, cx, cy, str(n_fib), ac, as_tot,
                     rb_h, poly_h, hole_h, conc_h, steel_h])


def surface_fp(std, sec, model=None, tied=None):
    """Fingerprint cho MẶT 3D. std: 'tcvn'|'aci'|'ec2'|'wall'.

    model: model bê tông (TCVN/vách: inp.concrete_model).
    tied: True/False (ACI — ảnh hưởng hệ số mặt)."""
    return _sha1(["surf3d", std, f"{SURF3D_N_N}x{SURF3D_N_ANGLES}",
                  _section_fp(sec),
                  f"model={model}", f"tied={tied}"])


def curve_fp(fp_surface, theta_deg):
    """Fingerprint cho ĐƯỜNG CONG N-Ma: mặt + góc tải (làm tròn
    6 chữ số — cùng góc tải cho cùng entry)."""
    return _sha1(["surf3d-curve", fp_surface, f"{float(theta_deg):.6f}",
                  str(SURF3D_CURVE_N)])


def get_surface(fp, builder):
    """Trả (n_vals, th_vals, m2_grid, m3_grid) — cache hit thì không
    gọi builder; miss thì gọi builder() (= cap.surface_grid(...)),
    lưu LRU rồi trả. Builder KHÔNG được có tác dụng phụ ngoài việc
    dựng lưới."""
    global _hits, _misses
    ent = _cache.get(fp)
    if ent is not None and ent["kind"] == "surf":
        _cache.move_to_end(fp)
        _hits += 1
        return ent["data"]
    _misses += 1
    data = builder()
    _cache[fp] = {"kind": "surf", "data": data}
    _evict()
    return data


def get_curve(fp, builder):
    """Trả (cx, cy, cz) đường cong N-Ma — cache theo (mặt, góc tải).
    Trên cache hit, caller KHÔNG cần dựng cap object."""
    global _hits, _misses
    ent = _cache.get(fp)
    if ent is not None and ent["kind"] == "curve":
        _cache.move_to_end(fp)
        _hits += 1
        return ent["data"]
    _misses += 1
    data = builder()
    _cache[fp] = {"kind": "curve", "data": data}
    _evict()
    return data


def _evict():
    while len(_cache) > _MAX_ENTRIES:
        _cache.popitem(last=False)


def alpha_curve_3d(cap_factory, n_vals, theta_deg,
                   n_pts=SURF3D_CURVE_N):
    """Dựng đường cong N-Ma 3D (cx, cy, cz) tại góc tải theta_deg.

    cap_factory: callable() -> capacity object có moment_capacity
    (để trên cache hit caller không cần dựng cap). Công thức
    (M·sinθ, M·cosθ, N) — cùng frame surface_grid, đúng quy ước
    ETABS của cột và khung canonical của vách."""
    import math
    import numpy as np
    cap = cap_factory()
    rad = math.radians(theta_deg)
    ux, uy = math.sin(rad), math.cos(rad)
    n_lo, n_hi = float(n_vals[0]), float(n_vals[-1])
    cx = np.empty(n_pts)
    cy = np.empty(n_pts)
    cz = np.empty(n_pts)
    for i in range(n_pts):
        nv = n_hi + (n_lo - n_hi) * i / (n_pts - 1)
        m = cap.moment_capacity(float(nv), theta_deg)
        cx[i] = m * ux
        cy[i] = m * uy
        cz[i] = float(nv)
    return cx, cy, cz


def cache_stats():
    """(hits, misses, entries) — phục vụ đo/benchmark."""
    return _hits, _misses, len(_cache)


def clear_cache():
    """Xóa cache (dùng cho test)."""
    global _hits, _misses
    _cache.clear()
    _hits = 0
    _misses = 0
