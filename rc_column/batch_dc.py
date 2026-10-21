"""Tính D/C tia 3D theo CẢ KHỐI DÒNG cho các engine exact (TCVN/ACI/EC2).

Bản batch của capacity_fast / boundary_fast / dc_ratio, dùng cho đường
batch ETABS với file lớn (nghìn dòng): thay vì gọi dc_ratio từng dòng
(mỗi dòng ~60 lượt capacity_fast, mỗi lượt là ~20 phép numpy trên mảng
nhỏ — overhead là chính), bản batch chạy chặt đôi ĐỒNG THỜI cho mọi
dòng, mỗi lượt capacity là vài phép numpy trên ma trận (dòng × gamma).

Khớp từng bit với bản scalar nhờ:
- Mọi phép toán trên mảng đều là elementwise IEEE float64 (+, -, *, /,
  so sánh, where) với CÙNG biểu thức và CÙNG thứ tự như _scan_fast /
  _roots / dc_ratio bản scalar.
- j nội suy tìm bằng searchsorted(side='right') trên hàng XP đã sắp —
  cho đúng số phần tử <= x như (XP <= x).sum() của bản scalar.
- Các hàm thư viện có thể khác bản scalar (hypot, atan2, degrees,
  phép % 360) đều tính bằng math.* trên từng dòng / từng nghiệm thắng
  cuộc như bản scalar.
- Dòng đã hội tụ trong chặt đôi được ĐÓNG BĂNG (mid == lo hoặc
  mid == hi) đúng như điều kiện break của bản scalar.
"""

import math

import numpy as np

_CHUNK = 512


def _gamma_degs(exact):
    """degrees(gamma) tiền tính 1 lần bằng math.degrees (như _scan_fast
    tính tại chỗ) — cache trên chính object engine."""
    d = exact.__dict__.get("_gamma_degs")
    if d is None:
        d = np.array([math.degrees(g) for g in exact.gammas], dtype=float)
        exact._gamma_degs = d
    return d


def _scan_batch(exact, Ns, ths, full):
    """Bản batch của _scan_fast cho mảng truy vấn (Ns, ths) cùng độ dài.

    Trả dict: valid (R, G) bool; along, perp (R, G); khi full thêm
    na, m2, m3, et (et = None nếu engine không có eps_t như TCVN/EC2).
    Các gamma không hợp lệ vẫn được tính (bị loại bằng mask valid ở
    tầng trên), giống _scan_fast chỉ khác là không rút gọn theo idx.
    """
    Ns = np.asarray(Ns, dtype=float)
    ths = np.asarray(ths, dtype=float)
    R = len(Ns)
    G = len(exact.gammas)
    ux = np.empty(R)
    uy = np.empty(R)
    px = np.empty(R)
    py = np.empty(R)
    for i in range(R):
        th = math.radians(float(ths[i]))
        s = math.sin(th)
        c = math.cos(th)
        ux[i] = s
        uy[i] = c
        px[i] = c
        py[i] = -s
    if G == 0 or exact._XP.shape[1] < 2:
        out = {"valid": np.zeros((R, G), dtype=bool),
               "along": np.zeros((R, G)), "perp": np.zeros((R, G))}
        if full:
            out.update({"na": np.zeros((R, G)), "m2": np.zeros((R, G)),
                        "m3": np.zeros((R, G)), "et": None})
        return out
    x = -Ns
    glen = exact._glen
    valid = (glen[None, :] >= 2) & (Ns[:, None] <= exact._N0[None, :]) \
        & (Ns[:, None] >= exact._N1[None, :])
    XP = exact._XP
    j = np.empty((R, G), dtype=np.int64)
    for g in range(G):
        j[:, g] = np.searchsorted(XP[g], x, side="right") - 1
    np.minimum(j, (glen - 2)[None, :], out=j)
    np.maximum(j, 0, out=j)
    gg = np.arange(G)[None, :]
    last = (glen - 1)[None, :]
    x0 = XP[gg, j]
    dx = XP[gg, j + 1] - x0
    xlast = XP[gg, last]
    at_end = x[:, None] >= xlast
    xx = x[:, None]

    def _interp(F):
        f0 = F[gg, j]
        f1 = F[gg, j + 1]
        with np.errstate(invalid="ignore", divide="ignore",
                         over="ignore"):
            y = f0 + ((f1 - f0) / dx) * (xx - x0)
        # Chuỗi where y hệt _scan_fast (khớp np.interp ở điểm mút và
        # với dữ liệu chứa inf ở NA của trạng thái nén đều).
        y = np.where(at_end, F[gg, last], y)
        y = np.where(xx == x0, f0, y)
        y = np.where(~np.isfinite(f0), f0, y)
        y = np.where((xx > x0) & ~np.isfinite(f1), f1, y)
        return y

    M2a = _interp(exact._F2)
    M3a = _interp(exact._F3)
    out = {"valid": valid,
           "along": M2a * ux[:, None] + M3a * uy[:, None],
           "perp": M2a * px[:, None] + M3a * py[:, None]}
    if full:
        out["na"] = _interp(exact._FNA)
        out["m2"] = M2a
        out["m3"] = M3a
        FET = getattr(exact, "_FET", None)
        out["et"] = _interp(FET) if FET is not None else None
    return out


def _cap_from_scan(sc):
    """capacity_fast từ kết quả _scan_batch(full=False): min trên các
    nghiệm perp = 0 (along > 0); không có nghiệm thì max along > 0
    trên các điểm hợp lệ; không có nữa thì 0.0 — như capacity_fast."""
    V = sc["valid"]
    A = sc["along"]
    P = sc["perp"]
    R, G = V.shape
    if G >= 2:
        m = V[:, :-1] & V[:, 1:]
        pa, pb = P[:, :-1], P[:, 1:]
        aa, ab = A[:, :-1], A[:, 1:]
        prod = pa * pb
        cand0 = np.where(m & (pa == 0.0) & (aa > 0), aa, np.inf)
        with np.errstate(invalid="ignore", divide="ignore",
                         over="ignore"):
            t = pa / (pa - pb)
            along_r = aa + t * (ab - aa)
        cand1 = np.where(m & (prod < 0.0) & (along_r > 0),
                         along_r, np.inf)
        pair_min = np.minimum(cand0, cand1).min(axis=1)
    else:
        pair_min = np.full(R, np.inf)
    mw = V[:, -1] & V[:, 0] if G >= 1 else np.zeros(R, dtype=bool)
    paw, pbw = P[:, -1], P[:, 0]
    aaw, abw = A[:, -1], A[:, 0]
    cand0w = np.where(mw & (paw == 0.0) & (aaw > 0), aaw, np.inf)
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        tw = paw / (paw - pbw)
        along_w = aaw + tw * (abw - aaw)
    cand1w = np.where(mw & ((paw * pbw) < 0.0) & (along_w > 0),
                      along_w, np.inf)
    min_root = np.minimum(np.minimum(pair_min, cand0w), cand1w)
    has_root = np.isfinite(min_root)
    pos = np.where(V & (A > 0), A, -np.inf)
    max_pos = pos.max(axis=1) if G else np.full(R, -np.inf)
    has_pos = np.isfinite(max_pos)
    return np.where(has_root, min_root,
                    np.where(has_pos, max_pos, 0.0))


def capacity_fast_batch(exact, Ns, ths):
    """capacity_fast cho cả mảng truy vấn (N, theta_deg)."""
    Ns = np.asarray(Ns, dtype=float)
    ths = np.asarray(ths, dtype=float)
    out = np.zeros(len(Ns))
    for s in range(0, len(Ns), _CHUNK):
        e = min(len(Ns), s + _CHUNK)
        cap = _cap_from_scan(_scan_batch(exact, Ns[s:e], ths[s:e], False))
        nq = Ns[s:e]
        cap = np.where((nq > exact.N_max) | (nq < exact.N_min), 0.0, cap)
        out[s:e] = cap
    return out


def _fill_boundary(exact, sc, degs, nq, res, off):
    """Tìm nghiệm thắng cuộc cho từng dòng trong 1 chunk scan full và
    dựng dict root. Việc CHỌN nghiệm (min capacity, thắng đầu tiên khi
    hoà) làm trên mảng slot đúng thứ tự _roots xuất nghiệm; các GIÁ TRỊ
    trong dict (gamma_deg với phép % 360, na/M2/M3/eps_t nội suy) tính
    lại bằng Python float trên điểm thắng cuộc — y hệt _roots."""
    V = sc["valid"]
    A = sc["along"]
    P = sc["perp"]
    NA = sc["na"]
    R, G = V.shape
    if G == 0:
        return
    S = 2 * G
    cap = np.full((R, S), np.inf)
    if G >= 2:
        m = V[:, :-1] & V[:, 1:]
        pa, pb = P[:, :-1], P[:, 1:]
        aa, ab = A[:, :-1], A[:, 1:]
        prod = pa * pb
        cap[:, 0:2 * (G - 1):2] = np.where(
            m & (pa == 0.0) & (aa > 0), aa, np.inf)
        with np.errstate(invalid="ignore", divide="ignore",
                         over="ignore"):
            t = pa / (pa - pb)
            along_r = aa + t * (ab - aa)
        cap[:, 1:2 * (G - 1):2] = np.where(
            m & (prod < 0.0) & (along_r > 0), along_r, np.inf)
        # Cặp đóng vòng (G-1 -> 0): slot 2G-2 (perp=0 tại G-1), 2G-1 (nội suy)
        mw = V[:, -1] & V[:, 0]
        paw, pbw = P[:, -1], P[:, 0]
        aaw, abw = A[:, -1], A[:, 0]
        cap[:, 2 * G - 2] = np.where(
            mw & (paw == 0.0) & (aaw > 0), aaw, np.inf)
        with np.errstate(invalid="ignore", divide="ignore",
                         over="ignore"):
            tw = paw / (paw - pbw)
            along_w = aaw + tw * (abw - aaw)
        cap[:, 2 * G - 1] = np.where(
            mw & ((paw * pbw) < 0.0) & (along_w > 0), along_w, np.inf)
    inrange = (nq <= exact.N_max) & (nq >= exact.N_min)
    cap[~inrange, :] = np.inf
    idx = np.argmin(cap, axis=1)
    best = cap[np.arange(R), idx]
    ET = sc["et"]
    for i in range(R):
        if not np.isfinite(best[i]):
            continue
        s = int(idx[i])
        if s < 2 * (G - 1):
            g = s // 2
            interp = (s % 2 == 1)
            gb = g + 1
        elif s == 2 * G - 2:
            g, interp, gb = G - 1, False, G - 1
        else:
            g, interp, gb = G - 1, True, 0
        pa = float(P[i, g])
        aa = float(A[i, g])
        naa = float(NA[i, g])
        m2a = float(sc["m2"][i, g])
        m3a = float(sc["m3"][i, g])
        if not interp:
            d = {"gamma_deg": float(degs[g]), "capacity": aa, "na": naa,
                 "M2": m2a, "M3": m3a, "gi_a": g, "gi_b": g}
            if ET is not None:
                d["eps_t"] = float(ET[i, g])
        else:
            pb = float(P[i, gb])
            ab = float(A[i, gb])
            tt = pa / (pa - pb)
            along = aa + tt * (ab - aa)
            gdeg = float(degs[g]) + tt * ((float(degs[gb])
                                            - float(degs[g])) % 360.0)
            d = {"gamma_deg": gdeg % 360.0, "capacity": along,
                 "na": naa + tt * (float(NA[i, gb]) - naa),
                 "M2": m2a + tt * (float(sc["m2"][i, gb]) - m2a),
                 "M3": m3a + tt * (float(sc["m3"][i, gb]) - m3a),
                 "gi_a": g, "gi_b": gb}
            if ET is not None:
                eta = float(ET[i, g])
                d["eps_t"] = eta + tt * (float(ET[i, gb]) - eta)
        res[off + i] = d


def boundary_fast_batch(exact, Ns, ths):
    """boundary_fast cho cả mảng truy vấn: list dict|None, dict có
    cùng khóa/giá trị như root thắng cuộc của boundary_fast."""
    Ns = np.asarray(Ns, dtype=float)
    ths = np.asarray(ths, dtype=float)
    res = [None] * len(Ns)
    degs = _gamma_degs(exact)
    for s in range(0, len(Ns), _CHUNK):
        e = min(len(Ns), s + _CHUNK)
        sc = _scan_batch(exact, Ns[s:e], ths[s:e], True)
        _fill_boundary(exact, sc, degs, Ns[s:e], res, s)
    return res


def ray_batch(exact, rows, n_iter=60, n_cap=None):
    """Khung dc_ratio chạy đồng thời cho cả khối dòng.

    rows: list (N, Mx, My) — mọi giá trị phải hữu hạn (tầng trên tách
    các dòng không hữu hạn về đường scalar). n_cap: nếu có (ACI), truy
    vấn có lam*N > n_cap cho capacity 0.0 như moment_capacity của ACI.

    Trả list dict thô theo đúng thứ tự rows:
      {cat: 'zero' | 'flo' | 'unbounded'} cho các nhánh suy biến, hoặc
      {cat: 'normal', lam, dc, Bx, By, BN, ok, phi_deg, boundary}
    với boundary là dict của boundary_fast tại điểm B (hoặc None).
    """
    R = len(rows)
    N = np.array([float(r[0]) for r in rows], dtype=float)
    Mx = np.array([float(r[1]) for r in rows], dtype=float)
    My = np.array([float(r[2]) for r in rows], dtype=float)
    Mstar = np.empty(R)
    phi = np.empty(R)
    for i in range(R):
        ms = math.hypot(float(Mx[i]), float(My[i]))
        Mstar[i] = ms
        phi[i] = math.degrees(math.atan2(float(Mx[i]), float(My[i]))) \
            if ms > 1e-12 else 0.0
    # cat: 0 = thường, 1 = zero, 2 = flo <= 1e-12, 3 = hi >= 1e7
    cat = np.zeros(R, dtype=int)
    cat[(Mstar < 1e-12) & (np.abs(N) < 1e-12)] = 1

    def f_at(lam, idx):
        Nq = lam * N[idx]
        c = capacity_fast_batch(exact, Nq, phi[idx])
        if n_cap is not None:
            c = np.where(Nq > n_cap, 0.0, c)
        return c - lam * Mstar[idx]

    lo = np.zeros(R)
    hi = np.ones(R)
    idx = np.nonzero(cat == 0)[0]
    if len(idx):
        f0 = f_at(np.zeros(len(idx)), idx)
        cat[idx[f0 <= 1e-12]] = 2
    pend = np.nonzero(cat == 0)[0]
    while len(pend):
        fh = f_at(hi[pend], pend)
        nxt = pend[(fh > 0) & (hi[pend] < 1e7)]
        hi[nxt] = hi[nxt] * 2.0
        pend = nxt
    cat[(cat == 0) & (hi >= 1e7)] = 3
    live_all = np.nonzero(cat == 0)[0]
    frozen = np.zeros(R, dtype=bool)
    for _ in range(n_iter):
        live = live_all[~frozen[live_all]]
        if len(live) == 0:
            break
        mid = 0.5 * (lo[live] + hi[live])
        adj = (mid == lo[live]) | (mid == hi[live])
        if adj.any():
            frozen[live[adj]] = True
        rest = live[~adj]
        if len(rest) == 0:
            continue
        mrest = mid[~adj]
        fm = f_at(mrest, rest)
        posm = fm > 0
        lo[rest[posm]] = mrest[posm]
        hi[rest[~posm]] = mrest[~posm]
    lam = 0.5 * (lo + hi)
    bnd = [None] * R
    if len(live_all):
        bl = boundary_fast_batch(exact, lam[live_all] * N[live_all],
                                 phi[live_all])
        for k, i in enumerate(live_all):
            bnd[int(i)] = bl[k]
    names = {1: "zero", 2: "flo", 3: "unbounded"}
    out = []
    for i in range(R):
        if cat[i] != 0:
            out.append({"cat": names[int(cat[i])]})
            continue
        lm = float(lam[i])
        dc = 1.0 / lm if lm > 1e-12 else float("inf")
        out.append({"cat": "normal", "lam": lm, "dc": dc,
                    "Bx": lm * float(Mx[i]), "By": lm * float(My[i]),
                    "BN": lm * float(N[i]), "ok": dc <= 1.0,
                    "phi_deg": float(phi[i]), "boundary": bnd[i]})
    return out
