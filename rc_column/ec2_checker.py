"""Kiểm tra cột BTCT theo Eurocode 2 (EN 1992-1-1).

Bao gồm:
- Biểu đồ tương tác P-M dùng fiber với khối ứng suất chữ nhật EC2
  (εcu2 = 0.0035, ứng suất η·fcd, a = λ·x; η = 1.0, λ = 0.8 với
  fck ≤ 50 MPa) và thép đàn-dẻo giới hạn ở ±fyd.
- Sai lệch thi công (độ nghiêng θi) và độ lệch tâm tối thiểu emin.
- Độ mảnh: λ = l0/i so với λlim = 20·A·B·C/√n.
- Hiệu ứng bậc 2: phương pháp độ cứng danh nghĩa (mặc định) hoặc
  độ cong danh nghĩa (tùy chọn).
- Kiểm tra cắt: VRd,c và VRd,max (công thức EC2 6.2).

Đơn vị: mm, MPa, kN, kN.m (giống aci_checker). Nén dương.
Hệ số riêng phần vật liệu đã nằm trong fcd/fyd nên đường cong
tương tác là đường cong thiết kế (không nhân thêm φ như ACI).
"""

import math
from typing import Dict, List, Tuple

import numpy as np

from .ec2_materials import EC2Concrete, EC2Steel, GAMMA_C, GAMMA_CE
from .sections import Section
from . import batch_dc


# ---------------------------------------------------------------------------
# Ứng suất thép (quy ước nén dương để cộng lực với bê tông)
# ---------------------------------------------------------------------------
def _ec2_steel_stress(eps_cpos: float, steel: EC2Steel) -> float:
    """Ứng suất thép (MPa), nén dương, giới hạn ở ±fyd."""
    fyd = steel.fyd
    if eps_cpos >= 0.0:
        return min(steel.Es * eps_cpos, fyd)
    return -min(steel.Es * (-eps_cpos), fyd)


# ---------------------------------------------------------------------------
# 1. Đường cong tương tác P-M (thiết kế) theo EC2
# ---------------------------------------------------------------------------
def ec2_interaction_curve(sec: Section, conc: EC2Concrete, steel: EC2Steel,
                          theta_deg: float,
                          n_points: int = 48) -> List[Tuple[float, float]]:
    """Đường cong tương tác (N, M) thiết kế theo EC2.

    Phương pháp fiber như aci_interaction_curve nhưng bê tông dùng
    khối ứng suất chữ nhật EC2: εcu2 = 0.0035 tại mép nén,
    a = λ·x (λ = 0.8), ứng suất η·fcd (η = 1.0) trong vùng khối
    chữ nhật. Thép: ứng suất đàn-dẻo giới hạn ở ±fyd; thép nằm
    trong khối nén dùng ứng suất thực (net): fs − η·fcd
    (trừ phần bê tông bị thép chiếm chỗ).

    Trả về list (N_kN, M_kNm) sắp theo N giảm dần (nén dương).
    """
    # Quy ước góc kiểu ETABS: α đo từ trục M3 (α=0° → thuần M3,
    # α=90° → thuần M2), tức hướng mô men (M2, M3) = (sin α, cos α).
    th = math.radians(90.0 - theta_deg)
    ct, st = math.cos(th), math.sin(th)
    fx = np.array([f.x for f in sec.fibers], dtype=float)
    fy = np.array([f.y for f in sec.fibers], dtype=float)
    fa = np.array([f.area for f in sec.fibers], dtype=float)
    rx = np.array([r.x for r in sec.rebars], dtype=float)
    ry = np.array([r.y for r in sec.rebars], dtype=float)
    ra = np.array([r.area for r in sec.rebars], dtype=float)

    if not fx.size:
        return [(0.0, 0.0)]

    # Tọa độ xoay: uốn quanh trục x' -> biến dạng theo y'
    yp_f = -fx * st + fy * ct
    yp_r = -rx * st + ry * ct if ra.size else np.array([])

    y_top = float(np.max(yp_f))
    y_bot = float(np.min(yp_f))
    h = y_top - y_bot
    if h <= 0:
        return [(0.0, 0.0)]

    eps_cu = conc.eps_cu        # 0.0035
    lam = conc.lam              # 0.8
    f_block = conc.f_block      # η·fcd (MPa)
    eps_yd = steel.eps_yd

    pts: List[Tuple[float, float]] = []

    def add_point(eps0: float, kx_p: float):
        """Một điểm trên đường cong. eps(y') = eps0 + kx_p*y', nén dương."""
        eps_top = eps0 + kx_p * y_top
        if abs(kx_p) < 1e-12:
            # Biến dạng đều
            if eps_top >= 0:
                sf = np.full_like(yp_f, f_block)
                a_blk = h  # toàn tiết diện nằm trong khối nén
            else:
                sf = np.zeros_like(yp_f)
                a_blk = 0.0
            er = np.full_like(yp_r, eps_top) if yp_r.size else yp_r
        else:
            if eps_top <= 0:
                # Không có vùng nén -> bê tông không chịu lực
                sf = np.zeros_like(yp_f)
                a_blk = 0.0
            else:
                # Chiều sâu trục trung hòa từ mép nén: x = eps_top / kx
                x = eps_top / kx_p
                a_blk = lam * x
                dist = y_top - yp_f  # khoảng cách từ mép nén
                in_block = dist <= a_blk + 1e-9
                sf = np.where(in_block, f_block, 0.0)
            er = eps0 + kx_p * yp_r if yp_r.size else yp_r

        Nf = float(np.sum(sf * fa))
        Mf = float(np.sum(sf * fa * yp_f))
        if ra.size:
            sr = np.array([_ec2_steel_stress(e, steel) for e in er])
            # Thép trong khối nén đã chiếm chỗ bê tông -> dùng ứng suất
            # thực (net): fs − η·fcd. Chỉ áp cho thanh chịu nén.
            if yp_r.size and a_blk > 0.0:
                dist_r = y_top - yp_r
                in_blk_r = dist_r <= a_blk + 1e-9
                sr = np.where(in_blk_r & (sr > 0.0), sr - f_block, sr)
            Nr = float(np.sum(sr * ra))
            Mr = float(np.sum(sr * ra * yp_r))
        else:
            Nr = Mr = 0.0

        N_d = (Nf + Nr) / 1000.0       # kN, nén dương
        M_d = abs(Mf + Mr) / 1e6       # kN.m
        pts.append((N_d, M_d))

    # Nén đúng tâm (biến dạng đều = εcu2)
    add_point(eps_cu, 0.0)

    # Quét: giữ mép nén đạt εcu2, mép kia giảm dần về kéo
    eps_s_max = max(0.01, 10.0 * eps_yd)
    for i in range(1, n_points):
        frac = i / n_points
        f2 = frac ** 0.8  # dày hơn gần vùng chuyển tiếp
        eps_bot = eps_cu - f2 * (eps_cu + eps_s_max)
        kx_p = (eps_cu - eps_bot) / h
        eps0 = eps_cu - kx_p * y_top
        add_point(eps0, kx_p)

    # Kéo đúng tâm
    add_point(-eps_s_max, 0.0)

    # Sắp theo N giảm dần, loại điểm trùng
    pts.sort(key=lambda p: -p[0])
    clean: List[Tuple[float, float]] = []
    for p in pts:
        if (not clean or abs(p[0] - clean[-1][0]) > 1e-6
                or abs(p[1] - clean[-1][1]) > 1e-6):
            clean.append(p)
    return clean


def _interp_on_curve(curve: List[Tuple], N: float, idx: int) -> float:
    """Nội suy tuyến tính giá trị tại cột idx theo N (curve sắp N giảm dần)."""
    if not curve:
        return 0.0
    if N >= curve[0][0]:
        return curve[0][idx]
    if N <= curve[-1][0]:
        return curve[-1][idx]
    for i in range(len(curve) - 1):
        n1 = curve[i][0]
        n2 = curve[i + 1][0]
        if n2 <= N <= n1 and abs(n1 - n2) > 1e-12:
            t = (N - n2) / (n1 - n2)
            return curve[i + 1][idx] + t * (curve[i][idx] - curve[i + 1][idx])
    return 0.0


def ec2_balanced_point(sec: Section, conc: EC2Concrete, steel: EC2Steel,
                       theta_deg: float = 0.0,
                       n_points: int = 96) -> Tuple[float, float]:
    """Điểm cân bằng: (N_bal_kN, M_bal_kNm) tại mô men lớn nhất
    trên đường cong P-M (dùng cho Kr của phương pháp độ cong danh nghĩa)."""
    curve = ec2_interaction_curve(sec, conc, steel, theta_deg,
                                  n_points=n_points)
    if not curve:
        return (0.0, 0.0)
    p = max(curve, key=lambda t: t[1])
    return (p[0], p[1])


# ---------------------------------------------------------------------------
# Engine song trục EXACT (2026-10-21): giải lặp cân bằng chính xác.
#
# Thay construction gần đúng cũ (đường cong đơn trục tại góc phi = hướng
# vectơ mô men, bỏ qua thành phần mô men vuông góc) bằng quét mặt phẳng
# biến dạng theo hướng gradient gamma: với mỗi gamma, trạng thái có mép
# nén đạt eps_cu và trục trung hòa cách mép nén na; tích phân fiber ra
# CẢ HAI thành phần (M2, M3). Capacity tại (N, theta) là nghiệm
# M_perp = 0 theo frame tải (lấy M_along nhỏ nhất nếu nhiều nghiệm).
# Mô hình vật liệu GIỮ NGUYÊN như ec2_interaction_curve (khối chữ nhật
# eta*fcd sâu lam*x, thép trong khối nén dùng ứng suất net fs - f_block).
# ---------------------------------------------------------------------------
class _EC2Exact:
    """Lưới trạng thái exact + nội suy contour tại mức N (cho 1 tiết diện)."""

    N_GAMMA = 360        # số hướng gamma (bước 1 độ, PA-A 2026-10-24)
    GAMMA_STEP = 1.0     # bước gamma (độ) — dùng ở MỌI điểm sinh lưới
    N_PTS = 384          # số điểm theo chiều sâu trục trung hòa (PA-A: 96→384, diệt sai số nội suy vùng sát cap)

    def __init__(self, sec, conc, steel):
        self.conc = conc
        self.steel = steel
        self.fx = np.array([f.x for f in sec.fibers], dtype=float)
        self.fy = np.array([f.y for f in sec.fibers], dtype=float)
        self.fa = np.array([f.area for f in sec.fibers], dtype=float)
        self.rx = np.array([r.x for r in sec.rebars], dtype=float)
        self.ry = np.array([r.y for r in sec.rebars], dtype=float)
        self.ra = np.array([r.area for r in sec.rebars], dtype=float)
        self.eps_cu = conc.eps_cu
        self.lam_b = conc.lam
        self.f_block = conc.f_block
        eps_s_max = max(0.01, 10.0 * steel.eps_yd)
        gam = [math.radians(self.GAMMA_STEP * i)
               for i in range(self.N_GAMMA)]
        self.gammas = gam
        # Danh sách eps_far dùng chung (như ec2_interaction_curve)
        self._eps_far = []
        for i in range(self.N_PTS):
            frac = 1.0 - (float(i) / max(1, self.N_PTS - 1)) ** 0.8
            self._eps_far.append(-eps_s_max + (self.eps_cu + eps_s_max) * frac)
        # Thêm điểm cụm ở vùng nén cao (na/h lớn): đường M(N) ở đó rất
        # dốc, nội suy tuyến tính cần lưới dày hơn để bám bản fine
        _extra = [self.eps_cu * (1.0 - 1.0 / r) for r in
                  (1.25, 1.6, 2.0, 2.6, 3.4, 4.5, 6.0, 8.0, 11.0, 15.0,
                   21.0, 30.0, 45.0, 70.0, 120.0, 250.0)]
        self._eps_far = sorted(set(self._eps_far) | set(_extra),
                               reverse=True)
        # Quét trạng thái cho từng gamma
        self.sweeps = []   # mỗi phần tử: dict(N, M2, M3, NA) mảng giảm dần theo N
        n_all = []
        for g in gam:
            cg, sg = math.cos(g), math.sin(g)
            s_f = self.fx * cg + self.fy * sg
            s_r = self.rx * cg + self.ry * sg
            s_max = float(s_f.max()) if len(s_f) else 0.0
            s_min = float(s_f.min()) if len(s_f) else 0.0
            h_s = max(s_max - s_min, 1e-9)
            _pre = (s_f, s_r, s_max)
            # Batch nhanh hon khi fiber vua/nho; tiet dien rat nhieu
            # fiber (da giac V2 ~6700) thi vong lap tung trang thai
            # nhanh hon vi mang nho vua cache L2 — giu ca 2 duong.
            if len(self.fx) <= 3000:
                Ns, M2s, M3s, NAs = self._states_batch(_pre, h_s)
            else:
                Ns, M2s, M3s, NAs = [], [], [], []
                for eps_far in self._eps_far:
                    if eps_far >= self.eps_cu - 1e-15:
                        na = float("inf")
                    else:
                        na = self.eps_cu * h_s / (self.eps_cu - eps_far)
                    N, M2, M3 = self._state(g, na, _pre)
                    Ns.append(N); M2s.append(M2); M3s.append(M3)
                    NAs.append(na)
            # Lọc N giảm nghiêm ngặt (giữ điểm đầu của mỗi mức) để nội suy
            kN, kM2, kM3, kNA = [], [], [], []
            last = None
            for N, M2, M3, na in zip(Ns, M2s, M3s, NAs):
                if last is None or N < last - 1e-9:
                    kN.append(N); kM2.append(M2); kM3.append(M3); kNA.append(na)
                    last = N
            self.sweeps.append({
                "N": np.array(kN), "M2": np.array(kM2),
                "M3": np.array(kM3), "NA": np.array(kNA),
                "s_max": s_max, "s_min": s_min})
            n_all.extend(kN)
        self.N_max = max(n_all) if n_all else 0.0
        self.N_min = min(n_all) if n_all else 0.0
        self._build_scan_cache()

    def _build_scan_cache(self):
        """Ma tran dem (padding) cua cac sweep de quet gamma vector hoa.

        XP[g] = -N tang dan (dem lap gia tri cuoi), F2/F3/FNA tuong ung.
        _scan_fast dung cong thuc f0 + ((f1-f0)/(x1-x0))*(x-x0) — da kiem
        chung khop tung bit voi np.interp o moi diem trong; rieng diem
        mut phai (x == xp[-1]) tra thang gia tri cuoi nhu np.interp.
        """
        G = len(self.sweeps)
        L = max((len(sw["N"]) for sw in self.sweeps), default=0)
        self._glen = np.zeros(G, dtype=int)
        self._N0 = np.zeros(G)
        self._N1 = np.zeros(G)
        self._XP = np.zeros((G, L))
        self._F2 = np.zeros((G, L))
        self._F3 = np.zeros((G, L))
        self._FNA = np.zeros((G, L))
        for gi, sw in enumerate(self.sweeps):
            n = len(sw["N"])
            self._glen[gi] = n
            if n == 0:
                continue
            self._N0[gi] = sw["N"][0]
            self._N1[gi] = sw["N"][-1]
            for arr, key in ((self._XP, None), (self._F2, "M2"),
                             (self._F3, "M3"), (self._FNA, "NA")):
                v = -sw["N"] if key is None else sw[key]
                arr[gi, :n] = v
                if n < L:
                    arr[gi, n:] = v[-1]

    def _scan_fast(self, N: float, theta_deg: float, full: bool):
        """Ban vector hoa cua _scan: cung pts, cung thu tu, gia tri khop
        tung bit voi _sweep_at_N/np.interp. full=False: na tra 0.0
        (capacity_fast khong dung gia tri nay)."""
        th = math.radians(theta_deg)
        ux, uy = math.sin(th), math.cos(th)
        px, py = math.cos(th), -math.sin(th)
        x = -N
        ok = (self._glen >= 2) & (N <= self._N0) & (N >= self._N1)
        idx = np.nonzero(ok)[0]
        pts = []
        if len(idx) == 0:
            return pts
        gl = self._glen[idx]
        XP = self._XP[idx]
        j = (XP <= x).sum(axis=1) - 1
        j = np.minimum(j, gl - 2)
        np.maximum(j, 0, out=j)
        rows = np.arange(len(idx))
        x0 = XP[rows, j]
        dx = XP[rows, j + 1] - x0
        xlast = XP[rows, gl - 1]
        at_end = x >= xlast

        def _interp(F):
            Fg = F[idx]
            f0 = Fg[rows, j]
            f1 = Fg[rows, j + 1]
            with np.errstate(invalid="ignore", divide="ignore",
                             over="ignore"):
                y = f0 + ((f1 - f0) / dx) * (x - x0)
            # np.interp: tai nut trai tra dung f0; dau mut khong huu han
            # (NA = inf o trang thai nen deu) thang trong doan, giong
            # hanh vi goc cua np.interp voi du lieu chua inf.
            y = np.where(at_end, Fg[rows, gl - 1], y)
            y = np.where(x == x0, f0, y)
            y = np.where(~np.isfinite(f0), f0, y)
            y = np.where((x > x0) & ~np.isfinite(f1), f1, y)
            return y

        M2a = _interp(self._F2)
        M3a = _interp(self._F3)
        NAa = _interp(self._FNA) if full else None
        for k, gi in enumerate(idx):
            M2 = float(M2a[k]); M3 = float(M3a[k])
            na = float(NAa[k]) if full else 0.0
            pts.append((math.degrees(self.gammas[gi]),
                        M2 * ux + M3 * uy, M2 * px + M3 * py,
                        na, M2, M3, int(gi)))
        return pts

    def _states_batch(self, _pre, h_s: float):
        """Toàn bộ trạng thái của 1 gamma tính BATCH.

        Phần tử (khối nén, eps thép, clip, ứng suất net) vector hoá trên
        ma trận (n_state x n_fiber) bằng ĐÚNG biểu thức của _state; tổng
        N theo axis=1 khớp .sum() 1D từng bit; M2/M3 giữ phép dot @ theo
        từng hàng như _state (matmul cả ma trận lệch ~1e-13). Kết quả
        lưới identical (đã kiểm chứng).
        Trả (Ns, M2s, M3s, NAs) dạng list, đúng thứ tự _eps_far.
        """
        s_f, s_r, s_max = _pre
        nas = []
        for eps_far in self._eps_far:
            if eps_far >= self.eps_cu - 1e-15:
                nas.append(float("inf"))
            else:
                nas.append(self.eps_cu * h_s / (self.eps_cu - eps_far))
        na_arr = np.array(nas, dtype=float)
        kappa = self.eps_cu / na_arr          # na=inf -> 0.0 (như _state)
        dist_f = s_max - s_f
        dist_r = s_max - s_r
        n = len(nas)
        # Chunk theo so fiber de ma tran tam vua cache (tiet dien lon)
        blk = max(14, min(n, 384_000 // max(len(self.fx), 1)))
        Ns = np.empty(n)
        M2s = np.empty(n)
        M3s = np.empty(n)
        for a in range(0, n, blk):
            b = min(n, a + blk)
            block_f = dist_f[None, :] <= (self.lam_b * na_arr[a:b])[:, None]
            block_r = dist_r[None, :] <= (self.lam_b * na_arr[a:b])[:, None]
            eps_r = self.eps_cu - kappa[a:b, None] * dist_r[None, :]
            sig_f = np.where(block_f, self.f_block, 0.0)
            fs_ = np.clip(self.steel.Es * eps_r,
                          -self.steel.fyd, self.steel.fyd)
            fs_ = np.where(block_r & (fs_ > 0.0), fs_ - self.f_block, fs_)
            CF = sig_f * self.fa[None, :]
            CS = fs_ * self.ra[None, :]
            Ns[a:b] = (CF.sum(axis=1) + CS.sum(axis=1)) / 1000.0
            for jj in range(b - a):
                M2s[a + jj] = (float(CF[jj] @ self.fy)
                               + float(CS[jj] @ self.ry)) / 1.0e6
                M3s[a + jj] = (float(CF[jj] @ self.fx)
                               + float(CS[jj] @ self.rx)) / 1.0e6
        return ([float(v) for v in Ns], [float(v) for v in M2s],
                [float(v) for v in M3s], nas)

    def _state(self, gamma_rad: float, na: float, _pre=None):
        """Trạng thái biến dạng phẳng (gamma, na) -> (N_kN, M2_kNm, M3_kNm).

        Mép nén (s lớn nhất theo hướng gamma) đạt eps_cu; trục trung hòa
        cách mép nén na dọc gradient. Tái dùng đúng khối ứng suất của
        ec2_interaction_curve.

        _pre = (s_f, s_r, s_max) tinh san cho gamma nay (cung bieu thuc
        nhu duoi) de tranh tinh lai khi quet nhieu na cung mot gamma.
        """
        if _pre is None:
            cg, sg = math.cos(gamma_rad), math.sin(gamma_rad)
            s_f = self.fx * cg + self.fy * sg
            s_r = self.rx * cg + self.ry * sg
            s_max = float(s_f.max()) if len(s_f) else 0.0
        else:
            s_f, s_r, s_max = _pre
        if math.isinf(na):
            kappa = 0.0
            block_f = np.ones(len(self.fx), dtype=bool)
            block_r = np.ones(len(self.rx), dtype=bool)
            eps_r = np.full(len(self.rx), self.eps_cu)
        else:
            kappa = self.eps_cu / na
            dist_f = s_max - s_f
            dist_r = s_max - s_r
            block_f = dist_f <= self.lam_b * na
            block_r = dist_r <= self.lam_b * na
            eps_r = self.eps_cu - kappa * dist_r
        sig_f = np.where(block_f, self.f_block, 0.0)
        fs = np.clip(self.steel.Es * eps_r, -self.steel.fyd, self.steel.fyd)
        fs = np.where(block_r & (fs > 0.0), fs - self.f_block, fs)
        cf = sig_f * self.fa
        cs = fs * self.ra
        N = (cf.sum() + cs.sum()) / 1000.0
        M2 = (float(cf @ self.fy) + float(cs @ self.ry)) / 1.0e6
        M3 = (float(cf @ self.fx) + float(cs @ self.rx)) / 1.0e6
        return N, M2, M3

    def _sweep_at_N(self, gi: int, N: float):
        """Nội suy trạng thái của gamma thứ gi tại mức N. None nếu ngoài dải."""
        sw = self.sweeps[gi]
        Ns = sw["N"]
        if len(Ns) < 2 or N > Ns[0] or N < Ns[-1]:
            return None
        M2 = float(np.interp(-N, -Ns, sw["M2"]))
        M3 = float(np.interp(-N, -Ns, sw["M3"]))
        na = float(np.interp(-N, -Ns, sw["NA"]))
        return M2, M3, na

    def _scan(self, N: float, theta_deg: float):
        """Quét gamma tại mức N: trả list (gamma_deg, along, perp, na, M2, M3, gi)
        cho các gamma có trạng thái (theo thứ tự gamma tăng dần)."""
        th = math.radians(theta_deg)
        ux, uy = math.sin(th), math.cos(th)     # hướng tải trong (M2, M3)
        px, py = math.cos(th), -math.sin(th)    # hướng vuông góc
        pts = []
        for gi, g in enumerate(self.gammas):
            st = self._sweep_at_N(gi, N)
            if st is None:
                continue
            M2, M3, na = st
            pts.append((math.degrees(g), M2 * ux + M3 * uy,
                        M2 * px + M3 * py, na, M2, M3, gi))
        return pts

    @staticmethod
    def _roots(pts):
        """Tìm nghiệm perp=0 (along>0) trên vòng gamma (nội suy tuyến tính).

        pts: list từ _scan. Trả list dict(gamma_deg, capacity, na, M2, M3).
        """
        out = []
        n = len(pts)
        if n == 0:
            return out
        for i in range(n):
            a = pts[i]
            b = pts[(i + 1) % n]
            if (i + 1) % n == 0:
                # Cạnh đóng vòng chỉ hợp lệ khi a là gamma cuối, b là gamma đầu
                if not (a[6] == _EC2Exact.N_GAMMA - 1 and b[6] == 0):
                    continue
            elif b[6] != a[6] + 1:
                continue
            pa, pb = a[2], b[2]
            if pa == 0.0 and a[1] > 0:
                out.append({"gamma_deg": a[0], "capacity": a[1], "na": a[3],
                            "M2": a[4], "M3": a[5],
                            "gi_a": a[6], "gi_b": a[6]})
            if pa * pb < 0.0:
                t = pa / (pa - pb)
                along = a[1] + t * (b[1] - a[1])
                if along > 0:
                    gdeg = a[0] + t * ((b[0] - a[0]) % 360.0)
                    out.append({"gamma_deg": gdeg % 360.0, "capacity": along,
                                "na": a[3] + t * (b[3] - a[3]),
                                "M2": a[4] + t * (b[4] - a[4]),
                                "M3": a[5] + t * (b[5] - a[5]),
                                "gi_a": a[6], "gi_b": b[6]})
        return out

    def _contour_state(self, g_deg, N, ux, uy, px, py):
        """Điểm contour (g_deg, along, perp, na, M2, M3) tại (gamma, N)
        từ trạng thái thô của chính gamma đó (batch vector hoá, nội
        suy theo N trên lưới _eps_far — cùng cách _sweep_at_N nội suy
        sweep đã lọc, nhưng trên trạng thái thô nên không bị cụt ở đầu
        lọc đơn điệu). None nếu gamma không có trạng thái tại mức N.
        Dùng cho phục hồi nghiệm (nhanh hơn _state_at_N_fine nhiều)."""
        g = math.radians(g_deg % 360.0)
        cg, sg = math.cos(g), math.sin(g)
        s_f = self.fx * cg + self.fy * sg
        if len(s_f) == 0:
            return None
        s_r = self.rx * cg + self.ry * sg
        s_max = float(s_f.max())
        s_min = float(s_f.min())
        h_s = max(s_max - s_min, 1e-9)
        Ns, M2s, M3s, NAs = self._states_batch((s_f, s_r, s_max), h_s)
        for i in range(len(Ns) - 1):
            n0, n1 = Ns[i], Ns[i + 1]
            if abs(n0 - n1) < 1e-9:
                continue
            if (n0 - N) * (n1 - N) <= 0.0:
                t = (n0 - N) / (n0 - n1)
                na = NAs[i] + t * (NAs[i + 1] - NAs[i])
                if not math.isfinite(na):
                    na = NAs[i + 1] if math.isfinite(NAs[i + 1]) \
                        else NAs[i]
                M2 = M2s[i] + t * (M2s[i + 1] - M2s[i])
                M3 = M3s[i] + t * (M3s[i + 1] - M3s[i])
                return (g_deg, M2 * ux + M3 * uy, M2 * px + M3 * py,
                        na, M2, M3)
        return None

    def _span_root(self, N, s0, s1, ux, uy, px, py, gi_a, gi_b):
        """Nghiệm perp=0 trong khoảng gamma (s0, s1): 2 đầu là điểm
        (g_deg, along, perp, na, M2, M3) có perp trái dấu. Lấy mẫu phụ
        theo gamma bằng _contour_state, chặt đôi gamma trên cặp trái
        dấu hẹp nhất, nội suy tuyến tính theo perp giữa 2 trạng thái
        kẹp cuối. Trả dict nghiệm như _roots hoặc None."""
        g0, g1 = s0[0], s1[0]
        span = g1 - g0
        if span <= 0.0:
            return None
        seq = [s0]
        K = min(24, max(2, int(span / 0.5)))
        for k in range(1, K):
            gd = g0 + span * k / K
            sm = self._contour_state(gd, N, ux, uy, px, py)
            if sm is not None:
                seq.append(sm)
        seq.append(s1)
        for t0, t1 in zip(seq, seq[1:]):
            if t0[2] == 0.0 and t0[1] > 0:
                return {"gamma_deg": t0[0] % 360.0, "capacity": t0[1],
                        "na": t0[3], "M2": t0[4], "M3": t0[5],
                        "gi_a": gi_a, "gi_b": gi_b}
            if t0[2] * t1[2] >= 0.0:
                continue
            lo, hi = t0, t1
            for _ in range(12):
                gm = 0.5 * (lo[0] + hi[0])
                sm = self._contour_state(gm, N, ux, uy, px, py)
                if sm is None:
                    break
                if lo[2] * sm[2] <= 0.0:
                    hi = sm
                else:
                    lo = sm
            t = lo[2] / (lo[2] - hi[2])
            along = lo[1] + t * (hi[1] - lo[1])
            if along <= 0:
                return None
            if math.isfinite(lo[3]) and math.isfinite(hi[3]):
                na_r = lo[3] + t * (hi[3] - lo[3])
            else:
                na_r = lo[3] if math.isfinite(lo[3]) else hi[3]
            return {"gamma_deg": (lo[0] + t * (hi[0] - lo[0])) % 360.0,
                    "capacity": along, "na": na_r,
                    "M2": lo[4] + t * (hi[4] - lo[4]),
                    "M3": lo[5] + t * (hi[5] - lo[5]),
                    "gi_a": gi_a, "gi_b": gi_b}
        return None

    def _gap_roots(self, N, pts, ux, uy, px, py):
        """Nghiệm perp=0 trên vòng điểm quét pts (thứ tự gamma tăng,
        khép vòng) khi xét cả các cặp LIÊN TIẾP TRONG DANH SÁCH nhưng
        không kề chỉ số gamma (cặp bắc qua lỗ). Cặp kề chỉ số cho cùng
        kết quả như _roots nên hàm này chỉ dùng khi _roots rỗng.
        Các bracket trái dấu perp được tinh chỉnh theo thứ tự along
        nội suy chord tăng dần (chord là cận dưới của nghiệm trên cung
        lồi): bỏ qua bracket ngược (chord <= 0) khi đã có bracket
        dương, dừng khi chord vượt nghiệm tốt nhất đã có."""
        out = []
        n = len(pts)
        if n < 2:
            return out
        cands = []
        for i in range(n):
            a = pts[i]
            b = pts[(i + 1) % n]
            pa, pb = a[2], b[2]
            if pa == 0.0 and a[1] > 0:
                out.append({"gamma_deg": a[0], "capacity": a[1],
                            "na": a[3], "M2": a[4], "M3": a[5],
                            "gi_a": a[6], "gi_b": a[6]})
                continue
            if pa * pb >= 0.0:
                continue
            span = (b[0] - a[0]) % 360.0
            if span <= 0.0 or span > 90.0:
                continue
            t = pa / (pa - pb)
            chord = a[1] + t * (b[1] - a[1])
            cands.append((chord, a, b, span))
        cands.sort(key=lambda c: c[0])
        best = None
        has_pos = any(c[0] > 0 for c in cands)
        for chord, a, b, span in cands:
            if chord <= 0 and has_pos:
                continue
            if best is not None and chord >= best["capacity"]:
                break
            s0 = (a[0], a[1], a[2], a[3], a[4], a[5])
            s1 = (a[0] + span, b[1], b[2], b[3], b[4], b[5])
            r = self._span_root(N, s0, s1, ux, uy, px, py, a[6], b[6])
            if r is not None and (best is None
                                  or r["capacity"] < best["capacity"]):
                best = r
        if best is not None:
            out.append(best)
        return out

    def _recover_roots(self, N: float, theta_deg: float):
        """Nghiệm tại (N, theta) khi _roots trên lưới gamma 3° rỗng:
        bắc cầu khe gamma + tinh chỉnh bằng trạng thái fine. Cache
        trên engine theo (N, theta) vì biểu đồ gọi lặp cùng mức."""
        cache = self.__dict__.setdefault("_recover_cache", {})
        key = (float(N), float(theta_deg))
        if key in cache:
            return cache[key]
        th = math.radians(theta_deg)
        ux, uy = math.sin(th), math.cos(th)
        px, py = math.cos(th), -math.sin(th)
        out = self._gap_roots(N, self._scan_fast(N, theta_deg, True),
                              ux, uy, px, py)
        if not out:
            # Vòng quét quá thưa (mức N sát mút dưới của lưới): tự lấy
            # mẫu gamma thô bằng _contour_state để dựng lại vòng.
            pts = []
            for k in range(24):
                gd = 15.0 * k
                s = self._contour_state(gd, N, ux, uy, px, py)
                if s is None:
                    continue
                # gi quy về chỉ số gamma lưới (15° = 5 bước 3°) để
                # boundary_fine dùng gi_a tra gammas[] vẫn đúng gamma
                pts.append((s[0], s[1], s[2], s[3], s[4], s[5], 5 * k))
            if len(pts) >= 2:
                out = self._gap_roots(N, pts, ux, uy, px, py)
        if len(cache) > 8192:
            cache.clear()
        cache[key] = out
        return out

    def capacity_fast(self, N: float, theta_deg: float) -> float:
        """Capacity exact tại (N, theta) từ lưới quét (nội suy)."""
        if N > self.N_max or N < self.N_min:
            return 0.0
        pts = self._scan_fast(N, theta_deg, False)
        roots = self._roots(pts)
        if not roots:
            roots = self._recover_roots(N, theta_deg)
        if roots:
            return min(r["capacity"] for r in roots)
        # Không có nghiệm perp=0 thật trên vòng contour (mức N ngoài
        # bao hoặc suy biến): capacity = 0 như bản fine. (Trước đây
        # fallback lấy max hình chiếu along trên vòng quét — số bịa ở
        # vùng vòng quét bị thủng lưới, xem _recover_roots.)
        return 0.0

    def boundary_fast(self, N: float, theta_deg: float):
        """Trạng thái biên (nghiệm perp=0 có capacity nhỏ nhất) tại (N, theta).

        Trả dict(gamma_deg, na, M2, M3, capacity) hoặc None.
        """
        if N > self.N_max or N < self.N_min:
            return None
        pts = self._scan_fast(N, theta_deg, True)
        roots = self._roots(pts)
        if not roots:
            roots = self._recover_roots(N, theta_deg)
        if not roots:
            return None
        return min(roots, key=lambda r: r["capacity"])

    def capacity_fast_batch(self, Ns, theta_degs):
        """capacity_fast cho cả mảng truy vấn (N, theta_deg): bản
        batch khớp từng bit với capacity_fast từng truy vấn
        (xem rc_column/batch_dc.py)."""
        return batch_dc.capacity_fast_batch(self, Ns, theta_degs)

    def boundary_fast_batch(self, Ns, theta_degs):
        """boundary_fast cho cả mảng truy vấn: list dict|None, dict
        như boundary_fast (khớp từng bit)."""
        return batch_dc.boundary_fast_batch(self, Ns, theta_degs)

    # ---- Bản fine: giải na bằng chặt đôi trực tiếp trên _state ----
    def _state_at_N_fine(self, gamma_rad: float, N_target: float):
        """Trạng thái exact tại (gamma, N): chặt đôi na. None nếu không có."""
        cg, sg = math.cos(gamma_rad), math.sin(gamma_rad)
        s_f = self.fx * cg + self.fy * sg
        s_r = self.rx * cg + self.ry * sg
        s_max = float(s_f.max()) if len(s_f) else 0.0
        s_min = float(s_f.min()) if len(s_f) else 0.0
        h_s = max(s_max - s_min, 1e-9)
        _pre = (s_f, s_r, s_max)
        nas = []
        for eps_far in self._eps_far:
            if eps_far >= self.eps_cu - 1e-15:
                nas.append(float("inf"))
            else:
                nas.append(self.eps_cu * h_s / (self.eps_cu - eps_far))
        vals = [self._state(gamma_rad, na, _pre) for na in nas]
        Ns = [v[0] for v in vals]
        if N_target > Ns[0] or N_target < Ns[-1]:
            return None
        # Tìm đoạn kẹp rồi chặt đôi trên na
        for i in range(len(Ns) - 1):
            if Ns[i] >= N_target >= Ns[i + 1]:
                lo, hi = nas[i + 1], nas[i]      # na tăng -> N tăng
                if math.isinf(hi):
                    # Đoạn sát trạng thái nén đều: N_target rất gần Ns[0]
                    if abs(Ns[0] - N_target) < 1e-6:
                        return (Ns[0], vals[0][1], vals[0][2], float("inf"))
                    hi = nas[i + 1] * 4.0 + h_s
                for _ in range(40):
                    mid = 0.5 * (lo + hi)
                    if self._state(gamma_rad, mid, _pre)[0] < N_target:
                        lo = mid
                    else:
                        hi = mid
                na = 0.5 * (lo + hi)
                N, M2, M3 = self._state(gamma_rad, na, _pre)
                return (N, M2, M3, na)
        return None

    def _fine_scan_roots(self, N: float, theta_deg: float):
        th = math.radians(theta_deg)
        ux, uy = math.sin(th), math.cos(th)
        px, py = math.cos(th), -math.sin(th)
        pts = []
        for g in self.gammas:
            st = self._state_at_N_fine(g, N)
            if st is None:
                continue
            _N, M2, M3, na = st
            pts.append((math.degrees(g), M2 * ux + M3 * uy,
                        M2 * px + M3 * py, na, M2, M3))
        roots = []
        n = len(pts)
        for i in range(n):
            a = pts[i]
            b = pts[(i + 1) % n]
            pa, pb = a[2], b[2]
            span = (b[0] - a[0]) % 360.0
            if span > 3.0 + 1e-9:
                # Cặp bắc qua gamma không có trạng thái tại mức N (lỗ
                # lưới ở tiết diện mảnh): tinh chỉnh bằng _span_root
                # thay cho bỏ qua như trước (trước: mất nghiệm -> 0).
                if span <= 90.0 and (pa * pb < 0.0
                                     or (pa == 0.0 and a[1] > 0)):
                    s1 = (a[0] + span, b[1], b[2], b[3], b[4], b[5])
                    r = self._span_root(N, a, s1, ux, uy, px, py, -1, -1)
                    if r is not None:
                        roots.append({"gamma_deg": r["gamma_deg"],
                                      "capacity": r["capacity"],
                                      "na": r["na"], "M2": r["M2"],
                                      "M3": r["M3"]})
                continue
            if pa * pb < 0.0:
                # Chặt đôi trên gamma trong đoạn [a, b]
                ga, gb = math.radians(a[0]), math.radians(b[0])
                if gb < ga:
                    gb += 2.0 * math.pi
                fa = pa
                gm = None
                for _ in range(30):
                    gm = 0.5 * (ga + gb)
                    stm = self._state_at_N_fine(gm % (2.0 * math.pi), N)
                    if stm is None:
                        break
                    pm = stm[1] * px + stm[2] * py
                    if fa * pm <= 0.0:
                        gb = gm
                    else:
                        ga, fa = gm, pm
                if gm is None:
                    continue
                stm = self._state_at_N_fine(gm % (2.0 * math.pi), N)
                if stm is None:
                    continue
                along = stm[1] * ux + stm[2] * uy
                if along > 0:
                    roots.append({"gamma_deg": math.degrees(gm) % 360.0,
                                  "capacity": along, "na": stm[3],
                                  "M2": stm[1], "M3": stm[2]})
            elif pa == 0.0 and a[1] > 0:
                roots.append({"gamma_deg": a[0], "capacity": a[1],
                              "na": a[3], "M2": a[4], "M3": a[5]})
        return roots

    def capacity_fine(self, N: float, theta_deg: float) -> float:
        """Capacity exact bản fine (chặt đôi na + gamma) — bản tham chiếu."""
        if N > self.N_max or N < self.N_min:
            return 0.0
        roots = self._fine_scan_roots(N, theta_deg)
        if roots:
            return min(r["capacity"] for r in roots)
        return 0.0

    def _fine_state_hint(self, gamma_rad: float, N_target: float,
                         na_hint: float):
        """Trạng thái fine tại (gamma, N) với bracket na từ na_hint
        (mở rộng hình học tới khi kẹp được N, rồi chặt đôi)."""
        cg, sg = math.cos(gamma_rad), math.sin(gamma_rad)
        _sf = self.fx * cg + self.fy * sg
        _sr = self.rx * cg + self.ry * sg
        _pre = (_sf, _sr, float(_sf.max()) if len(_sf) else 0.0)
        lo = na_hint / 2.5 if na_hint and math.isfinite(na_hint) else 10.0
        hi = na_hint * 2.5 if na_hint and math.isfinite(na_hint) else 1.0e5
        flo = self._state(gamma_rad, lo, _pre)[0] - N_target
        fhi = self._state(gamma_rad, hi, _pre)[0] - N_target
        for _ in range(8):
            if flo <= 0.0 <= fhi:
                break
            if flo > 0.0:
                hi, fhi = lo, flo
                lo = lo / 4.0
                flo = self._state(gamma_rad, lo, _pre)[0] - N_target
            else:
                lo, flo = hi, fhi
                hi = hi * 4.0
                fhi = self._state(gamma_rad, hi, _pre)[0] - N_target
        if not (flo <= 0.0 <= fhi):
            return None
        for _ in range(28):
            mid = 0.5 * (lo + hi)
            fm = self._state(gamma_rad, mid, _pre)[0] - N_target
            if fm < 0.0:
                lo = mid
            else:
                hi = mid
        na = 0.5 * (lo + hi)
        N, M2, M3 = self._state(gamma_rad, na, _pre)
        return (N, M2, M3, na)

    def boundary_fine(self, N: float, theta_deg: float):
        """Trạng thái biên fine tại (N, theta): tinh chỉnh bracket thắng
        cuộc của bản fast bằng trạng thái fine (chặt đôi gamma + na).
        Trả dict như _roots + s_max/s_min."""
        if N > self.N_max or N < self.N_min:
            return None
        roots = self._roots(self._scan(N, theta_deg))
        if not roots:
            roots = self._recover_roots(N, theta_deg)
        if not roots:
            return None
        r = min(roots, key=lambda x: x["capacity"])
        # Tinh chỉnh bracket [gi_a, gi_b] bằng trạng thái fine
        try:
            th = math.radians(theta_deg)
            px, py = math.cos(th), -math.sin(th)
            ux, uy = math.sin(th), math.cos(th)
            ga = self.gammas[r["gi_a"]]
            gb = ga + math.radians(self.GAMMA_STEP)
            sta = self._fine_state_hint(ga, N, r["na"])
            stb = self._fine_state_hint(gb % (2.0 * math.pi), N, r["na"])
            if sta is not None and stb is not None:
                fa = sta[1] * px + sta[2] * py
                fb = stb[1] * px + stb[2] * py
                if fa * fb < 0.0:
                    hint = r["na"]
                    for _ in range(25):
                        gm = 0.5 * (ga + gb)
                        stm = self._fine_state_hint(
                            gm % (2.0 * math.pi), N, hint)
                        if stm is None:
                            break
                        hint = stm[3]
                        pm = stm[1] * px + stm[2] * py
                        if fa * pm <= 0.0:
                            gb = gm
                        else:
                            ga, fa = gm, pm
                    gm = 0.5 * (ga + gb)
                    stm = self._fine_state_hint(gm % (2.0 * math.pi), N, hint)
                    if stm is not None:
                        r = {"gamma_deg": math.degrees(gm) % 360.0,
                             "capacity": stm[1] * ux + stm[2] * uy,
                             "na": stm[3], "M2": stm[1], "M3": stm[2]}
        except Exception:
            pass
        g = math.radians(r["gamma_deg"])
        s_f = self.fx * math.cos(g) + self.fy * math.sin(g)
        r["s_max"] = float(s_f.max()) if len(s_f) else 0.0
        r["s_min"] = float(s_f.min()) if len(s_f) else 0.0
        return r


def _ec2_exact_fingerprint(sec, conc, steel):
    fx = np.array([f.x for f in sec.fibers], dtype=float)
    fy = np.array([f.y for f in sec.fibers], dtype=float)
    fa = np.array([f.area for f in sec.fibers], dtype=float)
    rx = np.array([r.x for r in sec.rebars], dtype=float)
    ry = np.array([r.y for r in sec.rebars], dtype=float)
    ra = np.array([r.area for r in sec.rebars], dtype=float)

    def _r(v):
        return round(float(v), 3)
    return (len(fx), _r(fa.sum()), _r(fa @ fx), _r(fa @ fy),
            _r(fa @ (fx * fx)), _r(fa @ (fy * fy)), _r(fa @ (fx * fy)),
            len(rx), _r(ra.sum()), _r(ra @ rx), _r(ra @ ry),
            _r(ra @ (rx * rx)), _r(ra @ (ry * ry)),
            round(float(conc.fck), 4), round(float(steel.fyd), 4))


_EC2_EXACT_CACHE: dict = {}


def _get_ec2_exact(sec, conc, steel) -> _EC2Exact:
    key = _ec2_exact_fingerprint(sec, conc, steel)
    eng = _EC2_EXACT_CACHE.get(key)
    if eng is None:
        eng = _EC2Exact(sec, conc, steel)
        _EC2_EXACT_CACHE[key] = eng
    return eng


# ---------------------------------------------------------------------------
# Lớp khả năng chịu lực EC2 (mặt tương tác 3D thiết kế)
# ---------------------------------------------------------------------------
class EC2Capacity:
    """Khả năng chịu nén uốn xiên theo EC2 (mặt 3D thiết kế).

    Mỗi góc quét một đường cong thiết kế (hệ số riêng phần đã nằm
    trong fcd/fyd). Không có cắt đỉnh kiểu ACI 22.4.2.2.
    """

    def __init__(self, sec: Section, conc: EC2Concrete, steel: EC2Steel,
                 n_angles: int = 24, n_points: int = 48):
        self.sec = sec
        self.conc = conc
        self.steel = steel

        # N_Rd nén đúng tâm: (Ac − As)·fcd + As·fyd (điểm đầu đường cong)
        Ag = sec.gross_area
        Ast = sec.steel_area
        self.N_Rd_max = ((Ag - Ast) * conc.fcd + Ast * steel.fyd) / 1000.0  # kN

        self._n_angles = n_angles
        self._n_points = n_points
        step = 360.0 / n_angles
        self.angles: List[float] = [k * step for k in range(n_angles)]
        # design_curves dựng LƯỜI (lazy) khi thật sự cần: trước đây dựng
        # ngay trong __init__ khiến mỗi lần tạo EC2Capacity (rất nhiều
        # lần trong 1 CHECK do các hàm vẽ tạo mới) tốn ~0.5s cho 24
        # đường cong không ai dùng tới.
        self._design_curves = None

        # Engine song trục exact (D/C + capacity dùng bản này từ 2026-10-21;
        # design_curves giữ cho các nhu cầu phụ trợ như điểm cân bằng)
        self._exact = _get_ec2_exact(sec, conc, steel)

    @property
    def design_curves(self) -> Dict[float, List[Tuple[float, float]]]:
        """theta -> list (N, M) thiết kế, sắp N giảm dần.

        Dựng ở lần truy cập đầu tiên bằng đúng thuật toán cũ (kết quả
        không đổi), cache trong object.
        """
        if self._design_curves is None:
            self._design_curves = {
                th: ec2_interaction_curve(self.sec, self.conc, self.steel,
                                          th, n_points=self._n_points)
                for th in self.angles}
        return self._design_curves

    def _curve_at(self, phi_deg: float) -> List[Tuple[float, float]]:
        """Đường cong thiết kế tại góc gần nhất (xử lý wrap-around)."""
        def _adiff(a, b):
            d = abs(a - b) % 360.0
            return min(d, 360.0 - d)
        th = min(self.angles, key=lambda a: _adiff(a, phi_deg))
        return self.design_curves[th]

    def moment_capacity(self, N: float, phi_deg: float) -> float:
        """Khả năng chịu mô men thiết kế (kN.m) tại N (kN).

        Từ 2026-10-21: capacity EXACT (nghiệm cân bằng M_perp = 0 trên
        lưới trạng thái biến dạng phẳng), không còn construction đường
        cong đơn trục tại góc gần nhất như trước.
        """
        return self._exact.capacity_fast(N, phi_deg)

    def exact_capacity(self, N: float, theta_deg: float) -> float:
        """Capacity exact bản fine (chặt đôi na + gamma) — bản tham chiếu
        dùng cho kiểm chứng; moment_capacity là bản nội suy nhanh."""
        return self._exact.capacity_fine(N, theta_deg)

    def surface_grid(self, n_n: int = 25, n_angles: int = 36):
        """Lưới mặt tương tác 3D (N, M2, M3) để vẽ.

        Trả về (N_vals, Theta_vals, M2_grid, M3_grid).
        """
        import numpy as np
        import math
        n_min = min(min(p[0] for p in c) for c in self.design_curves.values())
        n_max = max(max(p[0] for p in c) for c in self.design_curves.values())
        n_vals = np.linspace(n_min, n_max, n_n)
        th_vals = np.linspace(0, 360, n_angles, endpoint=False)
        m2_grid = np.zeros((n_n, n_angles))
        m3_grid = np.zeros((n_n, n_angles))
        for i, nn in enumerate(n_vals):
            for j, th in enumerate(th_vals):
                m = self.moment_capacity(nn, th)
                rad = math.radians(th)
                m2_grid[i, j] = m * math.sin(rad)
                m3_grid[i, j] = m * math.cos(rad)
        return n_vals, th_vals, m2_grid, m3_grid

    def dc_ratio(self, N: float, Mx: float, My: float,
                 n_iter: int = 60) -> dict:
        """Tỷ số D/C theo phương pháp tia 3D trên mặt thiết kế.

        Tìm lam_max sao cho lam*(N, Mx, My) nằm trên mặt tương tác.
        D/C = 1/lam_max. Làm kết luận ĐẠT/KHÔNG ĐẠT.
        """
        Mstar = math.hypot(Mx, My)
        if Mstar < 1e-12 and abs(N) < 1e-12:
            return {"dc": 0.0, "lambda_max": float("inf"),
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": True}
        phi_deg = math.degrees(math.atan2(Mx, My)) if Mstar > 1e-12 else 0.0

        def f(lam: float) -> float:
            return self.moment_capacity(lam * N, phi_deg) - lam * Mstar

        if f(0.0) <= 1e-12:
            return {"dc": float("inf"), "lambda_max": 0.0,
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": False}
        lo, hi = 0.0, 1.0
        while f(hi) > 0 and hi < 1e7:
            hi *= 2.0
        if hi >= 1e7:
            return {"dc": 0.0, "lambda_max": float("inf"),
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": True}
        for _ in range(n_iter):
            mid = 0.5 * (lo + hi)
            if mid == lo or mid == hi:
                # Khoảng đã thu về 2 float kề nhau: các vòng sau không
                # đổi được lo/hi nữa — thoát sớm cho kết quả y hệt.
                break
            if f(mid) > 0:
                lo = mid
            else:
                hi = mid
        lam = 0.5 * (lo + hi)
        dc = 1.0 / lam if lam > 1e-12 else float("inf")
        BN = lam * N
        res = {"dc": dc, "lambda_max": lam,
               "Bx": lam * Mx, "By": lam * My, "BN": BN,
               "ok": dc <= 1.0}
        # Mặt phẳng biến dạng tại điểm biên B (để vẽ đường trung hòa/vùng
        # nén nhất quán với D/C exact): hướng gradient gamma* + chiều sâu
        # trục trung hòa na*
        try:
            _b = self._exact.boundary_fast(BN, phi_deg)
            if _b is not None:
                res["gamma_deg"] = _b["gamma_deg"]
                res["na_depth"] = _b["na"]
        except Exception:
            pass
        return res

    @staticmethod
    def _dc_from_raw(rw: dict) -> dict:
        """Lắp dict kết quả dc_ratio từ dict thô của batch_dc.ray_batch
        (cùng khóa/cùng giá trị như dc_ratio từng dòng)."""
        if rw["cat"] == "zero":
            return {"dc": 0.0, "lambda_max": float("inf"),
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": True}
        if rw["cat"] == "flo":
            return {"dc": float("inf"), "lambda_max": 0.0,
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": False}
        if rw["cat"] == "unbounded":
            return {"dc": 0.0, "lambda_max": float("inf"),
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": True}
        res = {"dc": rw["dc"], "lambda_max": rw["lam"],
               "Bx": rw["Bx"], "By": rw["By"], "BN": rw["BN"],
               "ok": rw["ok"]}
        _b = rw["boundary"]
        if _b is not None:
            res["gamma_deg"] = _b["gamma_deg"]
            res["na_depth"] = _b["na"]
        return res

    def dc_ratio_batch(self, rows, n_iter: int = 60) -> list:
        """dc_ratio cho cả khối dòng [(N, Mx, My), ...]: kết quả từng
        dòng giống hệt gọi dc_ratio riêng lẻ (khớp từng bit), chỉ
        khác là chặt đôi chạy đồng thời cho mọi dòng. Các dòng có
        giá trị không hữu hạn đi đường scalar như cũ."""
        rows = [(float(N), float(Mx), float(My)) for (N, Mx, My) in rows]
        out: list = [None] * len(rows)
        fin = []
        for i, (N, Mx, My) in enumerate(rows):
            if math.isfinite(N) and math.isfinite(Mx) \
                    and math.isfinite(My):
                fin.append(i)
            else:
                out[i] = self.dc_ratio(N, Mx, My, n_iter=n_iter)
        if fin:
            raws = batch_dc.ray_batch(
                self._exact, [rows[i] for i in fin], n_iter=n_iter)
            for i, rw in zip(fin, raws):
                out[i] = self._dc_from_raw(rw)
        return out


# ---------------------------------------------------------------------------
# 2. Sai lệch thi công, độ mảnh và hiệu ứng bậc 2 (EC2 5.2, 5.8)
# ---------------------------------------------------------------------------
PHI_EF = 1.21  # hệ số từ biến hiệu dụng (mặc định)


def ec2_imperfection(l0_m: float, alpha_m: float = 1.0) -> dict:
    """Độ nghiêng do sai lệch thi công (EC2 5.2).

    θi = θ0·αh·αm; θ0 = 1/200; αh = 2/√l (2/3 ≤ αh ≤ 1, l tính bằng m);
    αm = 1.0 cho cấu kiện độc lập.
    ei = θi·l0/2 (độ lệch tâm do nghiêng).
    """
    l = max(l0_m, 1e-9)
    alpha_h = 2.0 / math.sqrt(l)
    alpha_h = max(2.0 / 3.0, min(1.0, alpha_h))
    theta_i = (1.0 / 200.0) * alpha_h * alpha_m
    ei_mm = theta_i * (l0_m * 1000.0) / 2.0
    return {"theta_i": theta_i, "alpha_h": alpha_h, "alpha_m": alpha_m,
            "ei_mm": ei_mm}


def ec2_min_eccentricity(h_mm: float) -> float:
    """Độ lệch tâm tối thiểu: emin = max(h/30, 20 mm) (EC2 6.1(4))."""
    return max(h_mm / 30.0, 20.0)


def ec2_slenderness_params(NEd_kN: float, M01_kNm: float, M02_kNm: float,
                           l0_mm: float, i_mm: float,
                           Ac_mm2: float, As_mm2: float,
                           fcd_MPa: float, fyd_MPa: float,
                           unbraced: bool = False,
                           phi_ef: float = 1.21) -> dict:
    """Các thông số độ mảnh (EC2 5.8.3).

    M01, M02: mô men bậc 1 ở 2 đầu (đã cộng sai lệch thi công),
    |M02| ≥ |M01| (trị tuyệt đối).
    Trả về {lambda_sl, n, omega, A, B, C, rm, lambda_lim, slender}.
    """
    lambda_sl = (l0_mm / i_mm) if i_mm > 0 else float("inf")
    n = (NEd_kN * 1000.0) / (Ac_mm2 * fcd_MPa) if Ac_mm2 * fcd_MPa > 0 else 0.0
    omega = (As_mm2 * fyd_MPa) / (Ac_mm2 * fcd_MPa) \
        if Ac_mm2 * fcd_MPa > 0 else 0.0
    A = 1.0 / (1.0 + 0.2 * phi_ef)
    B = math.sqrt(1.0 + 2.0 * omega)
    a1 = abs(M01_kNm)
    a2 = abs(M02_kNm)
    if a2 < 1e-12:
        rm = 1.0
    else:
        rm = min(a1, a2) / a2
    if unbraced:
        # Cấu kiện không giằng (cột độc lập): C = 0.7
        C = 0.7
        rm = 1.0
    else:
        C = 1.7 - rm
    if n > 1e-12:
        lambda_lim = 20.0 * A * B * C / math.sqrt(n)
    else:
        lambda_lim = float("inf")
    return {"lambda_sl": lambda_sl, "n": n, "omega": omega,
            "A": A, "B": B, "C": C, "rm": rm,
            "lambda_lim": lambda_lim,
            "slender": lambda_sl >= lambda_lim}


def ec2_second_order_stiffness(NEd_kN: float, M01_kNm: float, M02_kNm: float,
                               l0_mm: float, Ecm_MPa: float, Ic_mm4: float,
                               Is_mm4: float, Es_MPa: float,
                               fck_MPa: float, n_rel: float,
                               lambda_sl: float,
                               const_moment: bool = True,
                               phi_ef: float = 1.21) -> dict:
    """Hiệu ứng bậc 2 bằng phương pháp độ cứng danh nghĩa (EC2 5.8.7).

    MEd = M0Ed·factor; M0Ed = 0.6·M02 + 0.4·M01 ≥ 0.4·M02
    (M01, M02 là trị tuyệt đối đã cộng sai lệch, |M02| ≥ |M01|).
    factor = 1 + β/(NB/NEd − 1); β = π²/c0
    (c0 = 8 nếu mô men bậc 1 không đổi, ngược lại c0 = π²).
    NB = π²·EI/l0²; EI = Kc·Ecd·Ic + Ks·Es·Is;
    Ecd = Ecm/γcE (γcE = 1.2); Ks = 1.0;
    Kc = k1·k2/(1+φef); k1 = √(fck/20); k2 = n·λ/170 ≤ 0.20.

    Trả về {M0Ed, EI_Nmm2, NB_kN, beta, factor, MEd, ok, reason}.

    M01, M02: mô men đầu cột CÓ DẤU (dương/âm theo chiều uốn);
    EC2 5.8.8.2: M0Ed = 0.6·M02 + 0.4·M01 ≥ 0.4·M02 (giữ dấu để
    xét đúng uốn cong kép, khi M01 ngược dấu M02).
    """
    # M0Ed có dấu theo EC2 5.8.8.2 (m2: đầu có |M| lớn hơn)
    m1, m2 = M01_kNm, M02_kNm
    if abs(m2) < abs(m1):
        m1, m2 = m2, m1
    M0Ed = 0.6 * m2 + 0.4 * m1
    if m2 >= 0:
        M0Ed = max(M0Ed, 0.4 * m2)
    else:
        M0Ed = min(M0Ed, 0.4 * m2)

    Ecd = Ecm_MPa / GAMMA_CE
    k1 = math.sqrt(max(fck_MPa, 0.0) / 20.0)
    k2 = min(n_rel * lambda_sl / 170.0, 0.20)
    Kc = k1 * k2 / (1.0 + phi_ef)
    Ks = 1.0
    EI = Kc * Ecd * Ic_mm4 + Ks * Es_MPa * Is_mm4  # N.mm²

    if l0_mm <= 0:
        return {"M0Ed": M0Ed, "EI_Nmm2": EI, "NB_kN": float("inf"),
                "beta": 0.0, "factor": 1.0, "MEd": M0Ed,
                "ok": True, "reason": "l0 ≤ 0"}
    NB_N = math.pi ** 2 * EI / (l0_mm ** 2)  # N
    NB_kN = NB_N / 1000.0
    if NB_kN <= NEd_kN:
        return {"M0Ed": M0Ed, "EI_Nmm2": EI, "NB_kN": NB_kN,
                "beta": 0.0, "factor": float("inf"), "MEd": float("inf"),
                "ok": False,
                "reason": "NB ≤ NEd: cột quá mảnh, cần tăng tiết diện"}
    c0 = 8.0 if const_moment else math.pi ** 2
    beta = math.pi ** 2 / c0
    factor = 1.0 + beta / (NB_kN / NEd_kN - 1.0)
    factor = max(factor, 1.0)
    MEd = M0Ed * factor
    # Thiết kế cần độ lớn mô men (tiết diện đối xứng); giữ M0Ed có dấu để thuyết minh
    return {"M0Ed": M0Ed, "EI_Nmm2": EI, "NB_kN": NB_kN,
            "beta": beta, "c0": c0, "k1": k1, "k2": k2, "Kc": Kc,
            "factor": factor, "MEd": abs(MEd), "ok": True, "reason": ""}


def ec2_second_order_curvature(NEd_kN: float, M01_kNm: float, M02_kNm: float,
                               l0_mm: float, fck_MPa: float,
                               eps_yd: float, d_mm: float,
                               n_rel: float, nu: float, n_bal: float,
                               lambda_sl: float, c_curv: float = 10.0,
                               phi_ef: float = 1.21) -> dict:
    """Hiệu ứng bậc 2 bằng phương pháp độ cong danh nghĩa (EC2 5.8.8).

    MEd = M0Ed + M2; M2 = NEd·e2; e2 = (1/r)·l0²/c (c = 10).
    1/r = Kr·Kφ·1/r0; 1/r0 = εyd/(0.45·d);
    Kr = (nu − n)/(nu − nbal) ≤ 1.0; nu = 1 + ω;
    Kφ = 1 + β·φef ≥ 1; β = 0.35 + fck/200 − λ/150.

    Trả về {M0Ed, e2_mm, M2, Kr, Kphi, MEd, ok}.

    M01, M02: mô men đầu cột CÓ DẤU; M0Ed tính có dấu theo EC2 5.8.8.2
    (xét đúng uốn cong kép).
    """
    m1, m2 = M01_kNm, M02_kNm
    if abs(m2) < abs(m1):
        m1, m2 = m2, m1
    M0Ed = 0.6 * m2 + 0.4 * m1
    if m2 >= 0:
        M0Ed = max(M0Ed, 0.4 * m2)
    else:
        M0Ed = min(M0Ed, 0.4 * m2)

    r0_inv = eps_yd / (0.45 * d_mm) if d_mm > 0 else 0.0  # 1/mm
    denom = nu - n_bal
    if abs(denom) < 1e-12:
        Kr = 1.0
    else:
        Kr = (nu - n_rel) / denom
    Kr = max(0.0, min(1.0, Kr))
    beta = 0.35 + fck_MPa / 200.0 - lambda_sl / 150.0
    Kphi = max(1.0, 1.0 + beta * phi_ef)
    r_inv = Kr * Kphi * r0_inv  # 1/mm
    e2_mm = r_inv * l0_mm ** 2 / c_curv
    M2 = NEd_kN * e2_mm / 1000.0  # kN.m
    MEd = M0Ed + M2
    # Thiết kế cần độ lớn mô men (tiết diện đối xứng); giữ M0Ed có dấu để thuyết minh
    return {"M0Ed": M0Ed, "r0_inv": r0_inv, "Kr": Kr, "Kphi": Kphi,
            "beta": beta, "e2_mm": e2_mm, "M2": M2, "MEd": abs(MEd),
            "ok": True, "reason": ""}


def ec2_design_moment(NEd_kN: float, M_top_kNm: float, M_bot_kNm: float,
                      l0_mm: float, i_mm: float, h_mm: float,
                      Ac_mm2: float, As_mm2: float,
                      fcd_MPa: float, fyd_MPa: float,
                      Ecm_MPa: float, Ic_mm4: float, Is_mm4: float,
                      Es_MPa: float, fck_MPa: float,
                      unbraced: bool = False,
                      method: str = "stiffness",
                      d_mm: float = 0.0, eps_yd: float = 0.0,
                      n_bal: float = 0.0,
                      const_moment: bool = True,
                      phi_ef: float = 1.21) -> dict:
    """Mô men thiết kế một phương theo EC2 (đã gồm sai lệch, emin, bậc 2).

    - NEd > 0 (nén): cộng mô men do sai lệch thi công M_imp = NEd·ei
      vào cả 2 đầu (lấy trị tuyệt đối, hướng bất lợi nhất).
    - Mmin = NEd·emin; emin = max(h/30, 20 mm).
    - NEd ≤ 0 (kéo): bỏ qua sai lệch, emin và bậc 2.
    - Nếu λ < λlim: không tính bậc 2.
    - Mô men thiết kế nhịp: max(MEd_tính, Mmin);
      tại đầu cột: max(|M_đầu_phân_tích|, Mmin).

    Trả về dict đầy đủ các thông số trung gian để thuyết minh.
    """
    out: Dict = {"NEd_kN": NEd_kN}
    if NEd_kN <= 1e-12:
        # Chịu kéo (hoặc N ≈ 0): bỏ qua sai lệch & bậc 2
        Mend = max(abs(M_top_kNm), abs(M_bot_kNm))
        out.update({
            "tension": True, "second_order": False,
            "theta_i": 0.0, "ei_mm": 0.0, "M_imp": 0.0,
            "emin_mm": 0.0, "Mmin": 0.0,
            "lambda_sl": 0.0, "lambda_lim": float("inf"),
            "M0Ed": Mend, "MEd_calc": Mend, "MEd": Mend,
            "MEd_end": Mend, "ok": True,
            "reason": "NEd kéo: bỏ qua sai lệch, emin và bậc 2",
        })
        return out

    # 1. Sai lệch thi công
    imp = ec2_imperfection(l0_mm / 1000.0)
    ei_mm = imp["ei_mm"]
    M_imp = NEd_kN * ei_mm / 1000.0  # kN.m
    # Cộng vào cả 2 đầu theo trị tuyệt đối (hướng bất lợi nhất)
    a_top = abs(M_top_kNm) + M_imp
    a_bot = abs(M_bot_kNm) + M_imp
    M02 = max(a_top, a_bot)
    M01 = min(a_top, a_bot)

    # 2. Độ lệch tâm tối thiểu
    emin_mm = ec2_min_eccentricity(h_mm)
    Mmin = NEd_kN * emin_mm / 1000.0  # kN.m

    # 3. Độ mảnh
    sl = ec2_slenderness_params(NEd_kN, M01, M02, l0_mm, i_mm,
                                Ac_mm2, As_mm2, fcd_MPa, fyd_MPa,
                                unbraced=unbraced, phi_ef=phi_ef)
    out.update({
        "tension": False,
        "theta_i": imp["theta_i"], "alpha_h": imp["alpha_h"],
        "ei_mm": ei_mm, "M_imp": M_imp,
        "M01_imp": M01, "M02_imp": M02,
        "emin_mm": emin_mm, "Mmin": Mmin,
        "lambda_sl": sl["lambda_sl"], "lambda_lim": sl["lambda_lim"],
        "n_rel": sl["n"], "omega": sl["omega"],
        "A_cf": sl["A"], "B_cf": sl["B"], "C_cf": sl["C"],
        "rm": sl["rm"], "slender": sl["slender"],
    })

    if not sl["slender"]:
        MEd_calc = M02
        out.update({
            "second_order": False, "method": method,
            "M0Ed": M02, "factor": 1.0, "MEd_calc": MEd_calc,
            "MEd": max(MEd_calc, Mmin),
            "MEd_end": max(M02, Mmin),
            "ok": True,
            "reason": f"λ = {sl['lambda_sl']:.1f} < λlim = "
                      f"{sl['lambda_lim']:.1f}: bỏ qua bậc 2",
        })
        return out

    # 4. Hiệu ứng bậc 2
    out["second_order"] = True
    out["method"] = method
    if method == "curvature":
        nu = 1.0 + sl["omega"]
        so = ec2_second_order_curvature(
            NEd_kN, M01, M02, l0_mm, fck_MPa, eps_yd, d_mm,
            sl["n"], nu, n_bal, sl["lambda_sl"])
        out.update({f"so_{k}": v for k, v in so.items()})
        MEd_calc = so["MEd"]
    else:
        so = ec2_second_order_stiffness(
            NEd_kN, M01, M02, l0_mm, Ecm_MPa, Ic_mm4, Is_mm4,
            Es_MPa, fck_MPa, sl["n"], sl["lambda_sl"],
            const_moment=const_moment)
        out.update({f"so_{k}": v for k, v in so.items()})
        MEd_calc = so["MEd"]
        if not so.get("ok", True):
            out.update({
                "MEd_calc": float("inf"), "MEd": float("inf"),
                "MEd_end": max(M02, Mmin), "ok": False,
            })
            return out

    out.update({
        "MEd_calc": MEd_calc,
        "MEd": max(MEd_calc, Mmin),
        "MEd_end": max(M02, Mmin),
        "ok": True, "reason": "",
    })
    return out


# ---------------------------------------------------------------------------
# 3. Kiểm tra cắt theo EC2 (6.2)
# ---------------------------------------------------------------------------
def ec2_shear_check(bw_mm: float, d_mm: float, Ac_mm2: float,
                    fck_MPa: float, NEd_kN: float, VEd_kN: float,
                    Asl_mm2: float, fyd_MPa: float,
                    Asw_s_mm2mm: float = 0.0,
                    theta_deg: float = 45.0) -> dict:
    """Kiểm tra khả năng chịu cắt theo EC2 6.2.

    bw_mm: chiều rộng chịu cắt; d_mm: chiều cao hữu hiệu;
    Ac_mm2: diện tích tiết diện; fck_MPa; NEd_kN (nén dương);
    VEd_kN: lực cắt tính toán; Asl_mm2: diện tích thép dọc chịu kéo
    neo qua gối (ρl = Asl/(bw·d) ≤ 0.02); fyd_MPa;
    Asw_s_mm2mm: Asw/s của đai đã bố trí (mm²/mm), 0 nếu không có;
    theta_deg: góc thanh chống nén (mặc định 45°).

    VRd,c = [CRd,c·k·(100·ρl·fck)^(1/3) + k1·σcp]·bw·d
            ≥ (vmin + k1·σcp)·bw·d
    VRd,max = αcw·bw·z·ν1·fcd/(cotθ + tanθ)
    Asw/s yêu cầu = VEd/(z·fyd·cotθ) khi VEd > VRd,c.

    Trả về {VRd_c_kN, VRd_max_kN, VRd_s_kN, VRd_kN, ok, Asw_s_req, ...}.
    """
    fcd = fck_MPa / GAMMA_C
    CRd_c = 0.18 / GAMMA_C   # 0.12
    k1 = 0.15

    k = 1.0 + math.sqrt(200.0 / d_mm) if d_mm > 0 else 2.0
    k = min(k, 2.0)
    rho_l = min(Asl_mm2 / (bw_mm * d_mm), 0.02) if bw_mm * d_mm > 0 else 0.0
    sigma_cp = (NEd_kN * 1000.0) / Ac_mm2 if Ac_mm2 > 0 else 0.0  # MPa
    sigma_cp = min(sigma_cp, 0.2 * fcd)

    vrd_c = (CRd_c * k * (100.0 * rho_l * fck_MPa) ** (1.0 / 3.0)
             + k1 * sigma_cp) * bw_mm * d_mm / 1000.0  # kN
    vmin = 0.035 * k ** 1.5 * math.sqrt(max(fck_MPa, 0.0))
    vrd_c_min = (vmin + k1 * sigma_cp) * bw_mm * d_mm / 1000.0
    VRd_c = max(vrd_c, vrd_c_min, 0.0)

    # VRd,max với θ = 45°: cotθ + tanθ = 2
    th = math.radians(theta_deg)
    cot = 1.0 / math.tan(th) if abs(math.tan(th)) > 1e-12 else 1.0
    nu1 = 0.6 * (1.0 - fck_MPa / 250.0)
    z = 0.9 * d_mm
    alpha_cw = 1.0  # không ứng suất nén trước
    VRd_max = alpha_cw * bw_mm * z * nu1 * fcd / (cot + math.tan(th)) \
        / 1000.0  # kN
    VRd_max = max(VRd_max, 0.0)

    if VEd_kN > VRd_max:
        return {"VRd_c_kN": VRd_c, "VRd_max_kN": VRd_max,
                "VRd_s_kN": 0.0, "VRd_kN": VRd_max,
                "ok": False, "Asw_s_req": float("inf"),
                "k": k, "rho_l": rho_l, "sigma_cp": sigma_cp,
                "vmin": vmin, "z_mm": z, "bw_mm": bw_mm, "d_mm": d_mm,
                "reason": "VEd > VRd,max: vượt khả năng thanh chống nén"}

    if VEd_kN <= VRd_c:
        # Không cần tính toán cốt đai
        return {"VRd_c_kN": VRd_c, "VRd_max_kN": VRd_max,
                "VRd_s_kN": 0.0, "VRd_kN": VRd_c,
                "ok": True, "Asw_s_req": 0.0,
                "k": k, "rho_l": rho_l, "sigma_cp": sigma_cp,
                "vmin": vmin, "z_mm": z, "bw_mm": bw_mm, "d_mm": d_mm,
                "reason": ""}

    # Cần cốt đai: Asw/s yêu cầu
    Asw_s_req = (VEd_kN * 1000.0) / (z * fyd_MPa * cot) \
        if z * fyd_MPa * cot > 0 else float("inf")
    VRd_s = Asw_s_mm2mm * z * fyd_MPa * cot / 1000.0  # kN
    VRd = min(VRd_s, VRd_max)
    ok = VRd >= VEd_kN
    return {"VRd_c_kN": VRd_c, "VRd_max_kN": VRd_max,
            "VRd_s_kN": VRd_s, "VRd_kN": VRd,
            "ok": ok, "Asw_s_req": Asw_s_req,
            "k": k, "rho_l": rho_l, "sigma_cp": sigma_cp,
            "vmin": vmin, "z_mm": z,
            "reason": "" if ok else "Thiếu cốt đai chịu cắt", "bw_mm": bw_mm, "d_mm": d_mm}


# ---------------------------------------------------------------------------
# 4. Kiểm tra cột tổng hợp theo EC2
# ---------------------------------------------------------------------------
def check_column_ec2(sec: Section, conc: EC2Concrete, steel: EC2Steel,
                     N_kN: float, M2_kNm: float, M3_kNm: float,
                     n_angles: int = 24) -> dict:
    """Kiểm tra khả năng chịu nén uốn xiên của cột theo EC2.

    sec: tiết diện (đã bố trí thép, hệ tọa độ x ngang / y đứng).
    N_kN: lực dọc thiết kế NEd (nén dương).
    M2_kNm, M3_kNm: mô men thiết kế MEd2, MEd3
    (đã gồm sai lệch, emin và bậc 2).

    Trả về dict {dc, fs, ok, lambda_max, Bx, By, BN, N_Rd_max, N_bal}.
    """
    cap = EC2Capacity(sec, conc, steel, n_angles=n_angles)
    # Ánh xạ: Mx = M2, My = M3 (cùng quy ước với aci_checker)
    r = cap.dc_ratio(N_kN, M2_kNm, M3_kNm)
    dc = r["dc"]
    fs = 1.0 / dc if dc > 1e-12 else float("inf")

    # Điểm cân bằng (để thuyết minh / dùng cho Kr)
    phi_deg = math.degrees(math.atan2(r["Bx"], r["By"])) if (
        abs(r["Bx"]) > 1e-12 or abs(r["By"]) > 1e-12) else 0.0
    N_bal, M_bal = ec2_balanced_point(
        sec, conc, steel,
        min(cap.angles, key=lambda a: abs((a - phi_deg + 180) % 360 - 180)))

    return {"dc": dc, "fs": fs, "ok": r["ok"],
            "lambda_max": r["lambda_max"],
            "Bx": r["Bx"], "By": r["By"], "BN": r["BN"],
            "N_Rd_max": cap.N_Rd_max,
            "N_bal": N_bal, "M_bal": M_bal,
            "gamma_deg": r.get("gamma_deg"), "na_depth": r.get("na_depth")}

def ec2_neutral_axis_at_N(sec, conc, steel, N_target_kN: float,
                          theta_deg: float, n_points: int = 96):
    """Đường trung hòa từ mặt phẳng biến dạng EXACT tại (N_target, theta).

    Từ 2026-10-21: dùng mặt phẳng biên của nghiệm cân bằng song trục
    exact (gamma*, na*) tại mức N — nhất quán với D/C exact mới, thay
    cho construction đường cong đơn trục cũ.
    Quy ước góc kiểu ETABS: theta đo từ trục M3.

    Trả về dict giống neutral_axis_at_N của TCVN. Hệ trục yp được chọn
    trùng hướng gradient gamma (yp ≡ s = x·cosγ + y·sinγ, tức
    st = −cosγ, ct = sinγ) nên: yp_na = s_max − na (vị trí strain = 0),
    eps = eps0 + kx_p·yp với kx_p = eps_cu/na, eps0 = eps_cu − kx_p·s_max.
    """
    eng = _get_ec2_exact(sec, conc, steel)
    b = eng.boundary_fine(float(N_target_kN), float(theta_deg))
    if b is None:
        th = math.radians(90.0 - theta_deg)
        return {'found': False, 'yp_na': None, 'theta_deg': theta_deg,
                'ct': math.cos(th), 'st': math.sin(th),
                'y_top': 0, 'y_bot': 0, 'eps0': 0, 'kx_p': 0}
    g = math.radians(b["gamma_deg"])
    ct = math.sin(g)
    st = -math.cos(g)
    na = b["na"]
    s_max, s_min = b["s_max"], b["s_min"]
    if math.isinf(na):
        # Nén đều: không có đường trung hòa
        return {'found': True, 'yp_na': None, 'theta_deg': theta_deg,
                'ct': ct, 'st': st, 'y_top': s_max, 'y_bot': s_min,
                'eps0': conc.eps_cu, 'kx_p': 0.0,
                'gamma_deg': b["gamma_deg"], 'na_depth': na}
    kappa = conc.eps_cu / na
    return {'found': True, 'yp_na': s_max - na, 'theta_deg': theta_deg,
            'ct': ct, 'st': st, 'y_top': s_max, 'y_bot': s_min,
            'eps0': conc.eps_cu - kappa * s_max, 'kx_p': kappa,
            'gamma_deg': b["gamma_deg"], 'na_depth': na}
