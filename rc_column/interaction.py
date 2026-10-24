"""Biểu đồ tương tác và kiểm tra nén uốn xiên (N + Mx + My) bằng NDM.

Phương pháp:
- Rời rạc tiết diện thành fiber (numpy, vector hóa).
- Với mỗi góc uốn theta: xoay hệ tọa độ, phân tích một phương (quét trục
  trung hòa với biến dạng bê tông mép nén đạt eps_cu) -> đường cong (N, M).
- Kiểm tra (N, Mx, My): tính M = sqrt(Mx²+My²), phi = atan2(Mx, My)  # quy ước ETABS: đo từ trục M3,
  nội suy khả năng chịu từ các đường cong theo góc -> hệ số sử dụng.

Đơn vị: N (kN), M (kN·m), kích thước (mm).
"""

import math
from typing import Dict, List, Tuple

import numpy as np

from .materials import EPS_B2, EPS_S2
from .sections import Section
from . import batch_dc


class FiberSection:
    """Tiết diện dạng mảng numpy để tính nhanh."""

    def __init__(self, sec: Section):
        self.sec = sec
        self.fx = np.array([f.x for f in sec.fibers], dtype=float)
        self.fy = np.array([f.y for f in sec.fibers], dtype=float)
        self.fa = np.array([f.area for f in sec.fibers], dtype=float)
        self.rx = np.array([r.x for r in sec.rebars], dtype=float)
        self.ry = np.array([r.y for r in sec.rebars], dtype=float)
        self.ra = np.array([r.area for r in sec.rebars], dtype=float)
        self.conc = sec.concrete
        self.steel = sec.steel
        self.Rb = sec.concrete.Rb
        self.Eb = sec.concrete.Eb
        self.Rs = sec.steel.Rs
        self.Rsc = sec.steel.Rsc
        self.Es = sec.steel.Es
        self.eps_y = self.Rs / self.Es
        # Biến dạng chảy theo từng phía (quy ước solver: eps > 0 = NÉN):
        # phía nén chảy ở Rsc, phía kéo chảy ở Rs (Bảng 10 TCVN 5574:2018).
        self.eps_y_c = self.Rsc / self.Es
        self.eps_y_t = self.Rs / self.Es

    def concrete_stress(self, eps: np.ndarray, model: str) -> np.ndarray:
        sig = np.zeros_like(eps)
        c = eps > 0
        e = eps[c]
        if model == "3line":
            e1 = 0.002
            e2 = EPS_B2
            eta = np.minimum(e / e1, 1.0)
            par = self.Rb * (2.0 * eta - eta * eta)
            sig[c] = np.where(e <= e2, np.where(e <= e1, par, self.Rb), 0.0)
        else:
            e0 = self.Rb / self.Eb
            sig[c] = np.where(e <= e0, self.Eb * e,
                              np.where(e <= EPS_B2, self.Rb, 0.0))
        return sig

    def steel_stress(self, eps: np.ndarray) -> np.ndarray:
        sig = np.zeros_like(eps)
        # NÉN (eps > 0) bị chặn ở Rsc, KÉO (eps < 0) ở Rs; vùng đàn hồi
        # cũng tách theo phía qua eps_y_c / eps_y_t.
        el = ((eps >= 0) & (eps <= self.eps_y_c)) \
            | ((eps < 0) & (-eps <= self.eps_y_t))
        sig[el] = self.Es * eps[el]
        pl = (~el) & (np.abs(eps) <= EPS_S2)
        sig[pl] = np.where(eps[pl] > 0, self.Rsc, -self.Rs)
        return sig

    def forces(self, eps0: float, kx: float, ky: float,
               model: str = "3line") -> Tuple[float, float, float]:
        """(N kN, Mx kN·m, My kN·m). Nén dương."""
        ef = eps0 + kx * self.fy + ky * self.fx
        sf = self.concrete_stress(ef, model)
        Nf = np.sum(sf * self.fa)
        Mxf = np.sum(sf * self.fa * self.fy)
        Myf = np.sum(sf * self.fa * self.fx)
        if self.ra.size:
            er = eps0 + kx * self.ry + ky * self.rx
            sr = self.steel_stress(er)
            Nr = np.sum(sr * self.ra)
            Mxr = np.sum(sr * self.ra * self.ry)
            Myr = np.sum(sr * self.ra * self.rx)
        else:
            Nr = Mxr = Myr = 0.0
        return (Nf + Nr) / 1000.0, (Mxf + Mxr) / 1e6, (Myf + Myr) / 1e6


def uniaxial_curve_fs(fs: FiberSection, theta_deg: float,
                      model: str = "3line",
                      n_points: int = 48) -> List[Tuple[float, float]]:
    """Đường cong (N, M) khi uốn với vectơ mô men nghiêng góc theta (độ).

    Quy ước góc kiểu ETABS: theta đo từ trục M3 (theta=0° → thuần M3/My,
    theta=90° → thuần M2/Mx), tức hướng mô men (M2, M3) = (sin theta, cos theta).
    Thực hiện bằng cách xoay tọa độ fiber rồi phân tích một phương.
    Trả về list (N [kN], M [kN·m]) sắp theo N giảm dần.
    """
    th = math.radians(90.0 - theta_deg)
    ct, st = math.cos(th), math.sin(th)
    # Tọa độ xoay: x' = x ct + y st ; y' = -x st + y ct
    # Uốn quanh trục x' -> biến dạng theo y'
    yp_f = -fs.fx * st + fs.fy * ct
    yp_r = -fs.rx * st + fs.ry * ct if fs.ra.size else np.array([])

    h = float(np.max(yp_f) - np.min(yp_f)) if yp_f.size else 0.0
    if h <= 0:
        return [(0.0, 0.0)]
    y_top = float(np.max(yp_f))
    y_bot = float(np.min(yp_f))
    eps_cu = EPS_B2
    pts: List[Tuple[float, float]] = []

    def add_point(eps0: float, kx_p: float):
        # kiểm tra biến dạng thép
        if yp_r.size:
            er = eps0 + kx_p * yp_r
            if np.any(np.abs(er) > EPS_S2 + 1e-9):
                return
        ef = eps0 + kx_p * yp_f
        sf = fs.concrete_stress(ef, model)
        Nf = np.sum(sf * fs.fa)
        Mf = np.sum(sf * fs.fa * yp_f)
        if fs.ra.size:
            er = eps0 + kx_p * yp_r
            sr = fs.steel_stress(er)
            Nr = np.sum(sr * fs.ra)
            Mr = np.sum(sr * fs.ra * yp_r)
        else:
            Nr = Mr = 0.0
        pts.append(((Nf + Nr) / 1000.0, abs(Mf + Mr) / 1e6))

    # Nén đúng tâm (biến dạng đều = eps_cu)
    add_point(eps_cu, 0.0)

    # Quét: giữ mép nén đạt eps_cu, biến dạng mép kia (eps_bot) giảm dần
    # từ eps_cu về -eps_s_max. Tham số hóa đều theo eps_bot để đường cong mượt.
    eps_s_max = min(0.9 * EPS_S2, 10.0 * fs.eps_y)
    for i in range(1, n_points):
        frac = i / n_points
        # phân bố dày hơn gần vùng chuyển tiếp (dùng frac^0.8)
        f2 = frac ** 0.8
        eps_bot = eps_cu - f2 * (eps_cu + eps_s_max)
        kx_p = (eps_cu - eps_bot) / h
        eps0 = eps_cu - kx_p * y_top
        add_point(eps0, kx_p)

    # Kéo đúng tâm
    add_point(-eps_s_max, 0.0)

    # Loại bỏ điểm trùng lặp gần nhau để đường cong sạch
    pts.sort(key=lambda p: -p[0])
    clean: List[Tuple[float, float]] = []
    for p in pts:
        if not clean or (abs(p[0] - clean[-1][0]) > 1e-6
                         or abs(p[1] - clean[-1][1]) > 1e-6):
            clean.append(p)
    return clean


def capacity_at_N(curve: List[Tuple[float, float]], N: float) -> float:
    if not curve:
        return 0.0
    if N >= curve[0][0]:
        return curve[0][1]
    if N <= curve[-1][0]:
        return curve[-1][1]
    for i in range(len(curve) - 1):
        n1, m1 = curve[i]
        n2, m2 = curve[i + 1]
        if n2 <= N <= n1 and abs(n1 - n2) > 1e-12:
            t = (N - n2) / (n1 - n2)
            return m2 + t * (m1 - m2)
    return 0.0


# ---------------------------------------------------------------------------
# Engine song trục EXACT (2026-10-21): giải lặp cân bằng chính xác.
#
# Như EC2/ACI: quét mặt phẳng biến dạng theo hướng gradient gamma, tích
# phân fiber ra CẢ HAI thành phần mô men; capacity tại (N, theta) là
# nghiệm M_perp = 0 trong frame tải. Với TCVN, trạng thái (gamma, na)
# được đổi thẳng sang (eps0, kx, ky) của FiberSection.forces nên mô hình
# vật liệu 3 đoạn của TCVN được tái dùng nguyên vẹn:
#   s = x·cosγ + y·sinγ (tọa độ dọc gradient), mép nén tại s_max,
#   eps(s) = eps_cu − κ(s_max − s), κ = eps_cu/na
#   -> eps0 = eps_cu − κ·s_max, kx = κ·cosγ, ky = κ·sinγ.
# ---------------------------------------------------------------------------
class _TCVNExact:
    """Lưới trạng thái exact + nội suy contour tại mức N (cho 1 tiết diện)."""

    N_GAMMA = 360        # số hướng gamma (bước 1 độ, PA-A 2026-10-24)
    GAMMA_STEP = 1.0     # bước gamma (độ) — dùng ở MỌI điểm sinh lưới
    N_PTS = 96           # số điểm theo chiều sâu trục trung hòa (dày hơn lưới cũ để nội suy contour chính xác)

    def __init__(self, fs: FiberSection, model: str = "3line"):
        self.fs = fs
        self.model = model
        self.sec = fs.sec
        self.eps_cu = EPS_B2
        fx = np.array([f.x for f in fs.sec.fibers], dtype=float)
        fy = np.array([f.y for f in fs.sec.fibers], dtype=float)
        self._fx, self._fy = fx, fy
        eps_s_max = min(0.9 * EPS_S2, 10.0 * fs.eps_y)
        gam = [math.radians(self.GAMMA_STEP * i)
               for i in range(self.N_GAMMA)]
        self.gammas = gam
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
        # Đuôi kéo (fix D/C = inf, 2026-10-24): lưới cũ dừng ở eps_far =
        # -eps_s_max nên với tiết diện ít thép, N_min vẫn > 0 và capacity
        # tại N = 0 bằng 0 -> dc_ratio sập về inf với mọi tải. Nối thêm
        # các điểm tiếp tục luật frac^0.8 cũ (i vượt N_PTS-1) xuống tới
        # sàn biến dạng an toàn của mô hình thép (-0.9*EPS_S2: thép đứt
        # khi |eps| > EPS_S2). Các điểm cũ giữ nguyên nên nội suy trong
        # miền cũ không đổi — chỉ miền mới (N < N_min cũ) thay đổi.
        _tail_floor = -0.9 * EPS_S2
        _tail = []
        for _m in (1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0, 5.5, 7.5, 10.0,
                   14.0, 20.0):
            _ef = -eps_s_max + (self.eps_cu + eps_s_max) * (1.0 - _m ** 0.8)
            if _ef >= _tail_floor:
                _tail.append(_ef)
        if _tail_floor < -eps_s_max and (not _tail or _tail_floor < min(_tail)):
            _tail.append(_tail_floor)
        self._eps_far = sorted(set(self._eps_far) | set(_tail),
                               reverse=True)
        # ---- Họ kéo sâu (2026-10-24, nối sau điểm nối họ cũ) ----
        # Họ cũ giữ mép nén ở eps_cu, mép kia (eps_far) giảm tới sàn
        # -0.9*EPS_S2: trục trung hòa không nhỏ hơn
        # eps_cu/(eps_cu + 0.9*EPS_S2) * h_s ≈ 0.135*h_s nên lưới dừng
        # ở N_min >> kéo thuần và capacity rơi thẳng đứng về 0.
        # Họ mới giữ mép kéo ở sàn cũ (eps_far = -0.9*EPS_S2, thép
        # chưa đứt vì |eps| <= EPS_S2) và hạ dần mép nén eps_top từ
        # eps_cu về -0.01: trục trung hòa thu về 0 rồi ra ngoài tiết
        # diện, khối nén bê tông triệt tiêu dần, tới kéo thuần
        # (mọi thép chảy kéo, bê tông không chịu kéo — mô hình phi
        # tuyến TCVN 5574:2018 §8.1.2.7, giới hạn eps_b2 = 0.0035 và
        # eps_s2 = 0.025 của chính mô hình này; trạng thái giới hạn
        # là khi một trong hai vật liệu đạt giới hạn của nó — ở họ
        # này là thép đạt sàn, bê tông dưới eps_b2).
        # Điểm nối là trạng thái chung (eps_cu, -0.9*EPS_S2) nên
        # capacity liên tục qua điểm nối; các điểm sau khi N đã đạt
        # kéo thuần (-As*Rs, M = 0) bị bộ lọc đơn điệu loại bỏ.
        self._deep_floor = _tail_floor
        self._deep_eps_top = (
            [self.eps_cu * _r for _r in
             (0.92, 0.84, 0.76, 0.68, 0.60, 0.52, 0.44, 0.36, 0.28,
              0.20, 0.14, 0.09, 0.05, 0.02, 0.0)]
            + [-0.0005, -0.001, -0.002, -0.005, -0.01])
        # Thứ tự quét: họ cũ (eps_top = eps_cu, eps_far giảm dần)
        # rồi họ kéo sâu (eps_far = sàn, eps_top giảm dần).
        self._state_params = ([(self.eps_cu, _ef)
                               for _ef in self._eps_far]
                              + [(_et, _tail_floor)
                                 for _et in self._deep_eps_top])
        self.sweeps = []
        n_all = []
        for g in gam:
            cg, sg = math.cos(g), math.sin(g)
            s_f = fx * cg + fy * sg
            s_max = float(s_f.max()) if len(s_f) else 0.0
            s_min = float(s_f.min()) if len(s_f) else 0.0
            h_s = max(s_max - s_min, 1e-9)
            Ns, M2s, M3s, NAs = self._states_batch(g, s_max, h_s)
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

    def _states_batch(self, gamma_rad: float, s_max: float, h_s: float):
        """Toàn bộ trạng thái của 1 gamma (theo _state_params) tính BATCH.

        Cùng biểu thức, cùng thứ tự phép tính từng phần tử như vòng lặp
        _state -> FiberSection.forces/concrete_stress/steel_stress, và
        tổng theo axis=1 khớp np.sum 1D từng bit (đã kiểm chứng) — kết
        quả lưới identical, chỉ khác là numpy chạy trên ma trận
        (n_state x n_fiber) thay vì từng trạng thái một.
        Trả (Ns, M2s, M3s, NAs) dạng list, đúng thứ tự _state_params.
        Các điểm họ cũ giữ đúng công thức na/kappa cũ từng bit;
        điểm họ kéo sâu dùng kappa = (eps_top - eps_far)/h_s và
        na = eps_top/kappa (âm khi eps_top < 0: trục trung hòa đã ra
        ngoài tiết diện phía nén — đúng ý nghĩa hình học).
        """
        fs = self.fs
        eps_tops = []
        eps_fars = []
        nas = []
        for eps_top, eps_far in self._state_params:
            eps_tops.append(eps_top)
            eps_fars.append(eps_far)
            if eps_top >= self.eps_cu - 1e-15:
                if eps_far >= self.eps_cu - 1e-15:
                    nas.append(float("inf"))
                else:
                    nas.append(self.eps_cu * h_s / (self.eps_cu - eps_far))
            else:
                _kap = (eps_top - eps_far) / h_s
                nas.append(eps_top / _kap if _kap > 0 else float("inf"))
        eps_top_arr = np.array(eps_tops, dtype=float)
        eps_far_arr = np.array(eps_fars, dtype=float)
        na_arr = np.array(nas, dtype=float)
        _old = eps_top_arr >= self.eps_cu - 1e-15
        kappa = np.empty(len(nas), dtype=float)
        kappa[_old] = self.eps_cu / na_arr[_old]  # na=inf -> 0.0 (như _state)
        kappa[~_old] = ((eps_top_arr[~_old] - eps_far_arr[~_old]) / h_s)
        cg, sg = math.cos(gamma_rad), math.sin(gamma_rad)
        eps0 = eps_top_arr - kappa * s_max
        kx = kappa * sg
        ky = kappa * cg
        n = len(nas)
        # Chunk theo so fiber de ma tran tam vua cache (tiet dien lon
        # nhu da giac V2 ~6700 fiber: batch day du cham hon vi tran RAM)
        blk = max(14, min(n, 384_000 // max(len(fs.fx), 1)))
        Ns = np.empty(n)
        M2s = np.empty(n)
        M3s = np.empty(n)
        Fa = fs.fa[None, :]
        Ra = fs.ra[None, :]
        fy2 = fs.fy[None, :]
        fx2 = fs.fx[None, :]
        ry2 = fs.ry[None, :]
        rx2 = fs.rx[None, :]
        # Workspace cap 1 lan, tai dung cho moi gamma/block: tranh cap
        # phat lai cac ma tran MB o moi gamma (chiem phan lon chi phi
        # batch tren tiet dien nhieu fiber). Cac phep tinh dung out=
        # nhung giu nguyen thu tu/trinh tu phep tinh tung phan tu.
        ws = self.__dict__.get("_batch_ws")
        if ws is None or ws[0].shape != (blk, len(fs.fx)):
            E = np.empty((blk, len(fs.fx)))
            SF = np.empty_like(E)
            P = np.empty_like(E)
            T = np.empty_like(E)
            C = np.empty((blk, len(fs.fx)), dtype=bool)
            ER = np.empty((blk, len(fs.rx)))
            SR = np.empty_like(ER)
            Q = np.empty_like(ER)
            ws = (E, SF, P, T, C, ER, SR, Q)
            self._batch_ws = ws
        E, SF, P, T, C, ER, SR, Q = ws
        for a in range(0, n, blk):
            b = min(n, a + blk)
            m = b - a
            Ev = E[:m]
            # Biến dạng fiber: eps0 + kx*fy + ky*fx (biểu thức của
            # forces; cong doi cho doi cho phep vi phep cong IEEE
            # giao hoan tung bit: kx*fy + eps0 == eps0 + kx*fy)
            np.multiply(kx[a:b, None], fy2, out=Ev)
            Ev += eps0[a:b, None]
            np.multiply(ky[a:b, None], fx2, out=T[:m])
            Ev += T[:m]
            # concrete_stress batch: xu ly tren tap con eps>0 bang mask
            # nhu FiberSection.concrete_stress (it luot quet ma tran
            # lon hon chuoi np.where long nhau, cung bieu thuc tung
            # phan tu nen khop bit)
            SFv = SF[:m]
            SFv.fill(0.0)
            np.greater(Ev, 0.0, out=C[:m])
            e = Ev[C[:m]]
            if self.model == "3line":
                eta = np.minimum(e / 0.002, 1.0)
                par = fs.Rb * (2.0 * eta - eta * eta)
                SFv[C[:m]] = np.where(e <= EPS_B2,
                                      np.where(e <= 0.002, par, fs.Rb), 0.0)
            else:
                e0 = fs.Rb / fs.Eb
                SFv[C[:m]] = np.where(e <= e0, fs.Eb * e,
                                      np.where(e <= EPS_B2, fs.Rb, 0.0))
            np.multiply(SFv, Fa, out=P[:m])
            Nf = np.sum(P[:m], axis=1)
            np.multiply(P[:m], fy2, out=T[:m])
            Mxf = np.sum(T[:m], axis=1)
            np.multiply(P[:m], fx2, out=T[:m])
            Myf = np.sum(T[:m], axis=1)
            if fs.ra.size:
                ERv = ER[:m]
                np.multiply(kx[a:b, None], ry2, out=ERv)
                ERv += eps0[a:b, None]
                np.multiply(ky[a:b, None], rx2, out=Q[:m])
                ERv += Q[:m]
                # steel_stress batch: gan theo mask nhu FiberSection
                # (nen -> Rsc, keo -> Rs; eps_y tach theo phia)
                SRv = SR[:m]
                SRv.fill(0.0)
                aER = np.abs(ERv)
                el = ((ERv >= 0) & (aER <= fs.eps_y_c)) \
                    | ((ERv < 0) & (aER <= fs.eps_y_t))
                SRv[el] = fs.Es * ERv[el]
                pl = (~el) & (aER <= EPS_S2)
                SRv[pl] = np.where(ERv[pl] > 0, fs.Rsc, -fs.Rs)
                np.multiply(SRv, Ra, out=Q[:m])
                Nr = np.sum(Q[:m], axis=1)
                np.multiply(Q[:m], ry2, out=ERv)
                Mxr = np.sum(ERv, axis=1)
                np.multiply(Q[:m], rx2, out=ERv)
                Myr = np.sum(ERv, axis=1)
            else:
                Nr = Mxr = Myr = 0.0
            Ns[a:b] = (Nf + Nr) / 1000.0
            M2s[a:b] = (Mxf + Mxr) / 1e6
            M3s[a:b] = (Myf + Myr) / 1e6
        return ([float(v) for v in Ns], [float(v) for v in M2s],
                [float(v) for v in M3s], nas)

    def _state(self, gamma_rad: float, na: float, _smax=None):
        """Trạng thái biến dạng phẳng (gamma, na) -> (N_kN, M2_kNm, M3_kNm)
        qua FiberSection.forces (đúng mô hình vật liệu TCVN).

        _smax: s_max tinh san cho gamma nay (cung bieu thuc nhu duoi)
        de tranh tinh lai s_f khi quet nhieu na cung mot gamma.
        """
        if _smax is None:
            cg, sg = math.cos(gamma_rad), math.sin(gamma_rad)
            s_f = self._fx * cg + self._fy * sg
            s_max = float(s_f.max()) if len(s_f) else 0.0
        else:
            cg, sg = math.cos(gamma_rad), math.sin(gamma_rad)
            s_max = _smax
        if math.isinf(na):
            eps0, kx, ky = self.eps_cu, 0.0, 0.0
        else:
            kappa = self.eps_cu / na
            eps0 = self.eps_cu - kappa * s_max
            # forces: eps = eps0 + kx*fy + ky*fx -> kx = κ·sinγ (hệ số
            # của y), ky = κ·cosγ (hệ số của x)
            kx, ky = kappa * sg, kappa * cg
        # forces trả sẵn (N kN, Mx kN·m, My kN·m) với Mx = ΣσA·y ≡ M2
        # của app, My = ΣσA·x ≡ M3 của app
        return self.fs.forces(eps0, kx, ky, self.model)

    def _deep_state(self, gamma_rad: float, eps_top: float,
                    _smax=None, _hs=None):
        """Trạng thái họ kéo sâu (gamma, eps_top) -> (N, M2, M3, na,
        eps_top, kappa): mép kéo giữ ở sàn _deep_floor, mép nén ở
        eps_top (< eps_cu). Cùng FiberSection.forces như _state nên
        mô hình vật liệu TCVN không đổi."""
        cg, sg = math.cos(gamma_rad), math.sin(gamma_rad)
        if _smax is None or _hs is None:
            s_f = self._fx * cg + self._fy * sg
            s_max = float(s_f.max()) if len(s_f) else 0.0
            s_min = float(s_f.min()) if len(s_f) else 0.0
            h_s = max(s_max - s_min, 1e-9)
            if _smax is not None:
                s_max = _smax
            if _hs is not None:
                h_s = _hs
        else:
            s_max, h_s = _smax, _hs
        kappa = (eps_top - self._deep_floor) / h_s
        eps0 = eps_top - kappa * s_max
        kx, ky = kappa * sg, kappa * cg
        N, M2, M3 = self.fs.forces(eps0, kx, ky, self.model)
        na = eps_top / kappa if kappa > 0 else float("inf")
        return (N, M2, M3, na, eps_top, kappa)

    def _deep_state_at_N(self, gamma_rad: float, N_target: float):
        """Trạng thái họ kéo sâu tại (gamma, N_target): chặt đôi
        eps_top trên [deep_min, eps_cu] (N đơn điệu tăng theo
        eps_top trên họ này — đã đo trên tròn/chữ nhật). Trả tuple
        như _deep_state hoặc None nếu N_target ngoài [kéo thuần,
        N tại điểm nối] của gamma này."""
        cg, sg = math.cos(gamma_rad), math.sin(gamma_rad)
        s_f = self._fx * cg + self._fy * sg
        s_max = float(s_f.max()) if len(s_f) else 0.0
        s_min = float(s_f.min()) if len(s_f) else 0.0
        h_s = max(s_max - s_min, 1e-9)
        lo = self._deep_eps_top[-1]
        hi = self.eps_cu
        n_lo = self._deep_state(gamma_rad, lo, s_max, h_s)[0]
        n_hi = self._deep_state(gamma_rad, hi, s_max, h_s)[0]
        if N_target > n_hi or N_target < n_lo - 1e-9:
            return None
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            if self._deep_state(gamma_rad, mid, s_max, h_s)[0] < N_target:
                lo = mid
            else:
                hi = mid
        return self._deep_state(gamma_rad, 0.5 * (lo + hi), s_max, h_s)

    def _sweep_at_N(self, gi: int, N: float):
        sw = self.sweeps[gi]
        Ns = sw["N"]
        if len(Ns) < 2 or N > Ns[0] or N < Ns[-1]:
            return None
        M2 = float(np.interp(-N, -Ns, sw["M2"]))
        M3 = float(np.interp(-N, -Ns, sw["M3"]))
        na = float(np.interp(-N, -Ns, sw["NA"]))
        return M2, M3, na

    def _scan(self, N: float, theta_deg: float):
        th = math.radians(theta_deg)
        ux, uy = math.sin(th), math.cos(th)
        px, py = math.cos(th), -math.sin(th)
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
        out = []
        n = len(pts)
        if n == 0:
            return out
        for i in range(n):
            a = pts[i]
            b = pts[(i + 1) % n]
            if (i + 1) % n == 0:
                if not (a[6] == _TCVNExact.N_GAMMA - 1 and b[6] == 0):
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

    # ---- Phục hồi nghiệm khi vòng gamma quét bị "thủng" ----
    # Sweep của gamma qua chiều mỏng của tiết diện dài (vd gamma 90°
    # của vách 2500x350) chỉ đạt N >= ~1300 vì eps_far bị chặn ở
    # -min(0.9*EPS_S2, 10*eps_y) (na >= 0.139*h_s), trong khi contour
    # tại mức N thấp hơn vẫn khép kín qua các gamma kề. _roots chỉ xét
    # cặp gamma kề chỉ số nên bỏ qua cặp bắc qua lỗ -> mất nghiệm thật
    # (gamma ~89°), và fallback cũ lấy max(along) trên vòng quét (đầu
    # mút contour, lớn gấp 2-3 lần nghiệm thật) làm capacity -> biểu
    # đồ N-Malpha vọt "đuôi" ở vùng N thấp. Các hàm dưới đây CHỈ chạy
    # khi _roots rỗng: bắc cầu khe gamma bằng trạng thái fine tại các
    # gamma trung gian (nghiệm thật), không đụng đường có nghiệm.

    def _contour_state(self, g_deg, N, ux, uy, px, py):
        """Điểm contour (g_deg, along, perp, na, M2, M3) tại (gamma, N)
        từ trạng thái thô của chính gamma đó (batch vector hoá, nội
        suy theo N trên lưới _eps_far — cùng cách _sweep_at_N nội suy
        sweep đã lọc, nhưng trên trạng thái thô nên không bị cụt ở đầu
        lọc đơn điệu). None nếu gamma không có trạng thái tại mức N.
        Dùng cho phục hồi nghiệm (nhanh hơn _state_at_N_fine nhiều)."""
        g = math.radians(g_deg % 360.0)
        cg, sg = math.cos(g), math.sin(g)
        s_f = self._fx * cg + self._fy * sg
        if len(s_f) == 0:
            return None
        s_max = float(s_f.max())
        s_min = float(s_f.min())
        h_s = max(s_max - s_min, 1e-9)
        Ns, M2s, M3s, NAs = self._states_batch(g, s_max, h_s)
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
        if roots:
            return min(r["capacity"] for r in roots)
        # Không nghiệm trên lưới quét: vòng gamma bị thủng ở mức N này
        # (tiết diện mảnh, vùng N thấp) -> phục hồi nghiệm thật thay
        # cho fallback max(along) cũ (đầu mút contour, sai gấp 2-3x).
        rec = self._recover_roots(N, theta_deg)
        if rec:
            return min(r["capacity"] for r in rec)
        return 0.0

    def boundary_fast(self, N: float, theta_deg: float):
        """Trạng thái biên tại (N, theta): dict(gamma_deg, na, M2, M3,
        capacity) hoặc None."""
        if N > self.N_max or N < self.N_min:
            return None
        roots = self._roots(self._scan_fast(N, theta_deg, True))
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

    # ---- Bản fine ----
    def _state_at_N_fine(self, gamma_rad: float, N_target: float):
        cg, sg = math.cos(gamma_rad), math.sin(gamma_rad)
        s_f = self._fx * cg + self._fy * sg
        s_max = float(s_f.max()) if len(s_f) else 0.0
        s_min = float(s_f.min()) if len(s_f) else 0.0
        h_s = max(s_max - s_min, 1e-9)
        nas = []
        for eps_far in self._eps_far:
            if eps_far >= self.eps_cu - 1e-15:
                nas.append(float("inf"))
            else:
                nas.append(self.eps_cu * h_s / (self.eps_cu - eps_far))
        vals = [self._state(gamma_rad, na, s_max) for na in nas]
        Ns = [v[0] for v in vals]
        if N_target > Ns[0]:
            return None
        if N_target < Ns[-1]:
            # Miền kéo sâu: họ cũ (eps_cu cố định) không với tới —
            # giải bằng họ kéo sâu (chặt đôi eps_top).
            _d = self._deep_state_at_N(gamma_rad, N_target)
            if _d is None:
                return None
            return (_d[0], _d[1], _d[2], _d[3])
        for i in range(len(Ns) - 1):
            if Ns[i] >= N_target >= Ns[i + 1]:
                lo, hi = nas[i + 1], nas[i]
                if math.isinf(hi):
                    if abs(Ns[0] - N_target) < 1e-6:
                        return (Ns[0], vals[0][1], vals[0][2], float("inf"))
                    hi = nas[i + 1] * 4.0 + h_s
                for _ in range(40):
                    mid = 0.5 * (lo + hi)
                    if self._state(gamma_rad, mid, s_max)[0] < N_target:
                        lo = mid
                    else:
                        hi = mid
                na = 0.5 * (lo + hi)
                N, M2, M3 = self._state(gamma_rad, na, s_max)
                return (N, M2, M3, na)
        # Không kẹp được trong họ cũ (N không đơn điệu tuyệt đối
        # trên lưới thô ở một số tiết diện): thử họ kéo sâu trước
        # khi kết luận không có trạng thái tại mức N này.
        _d = self._deep_state_at_N(gamma_rad, N_target)
        if _d is not None:
            return (_d[0], _d[1], _d[2], _d[3])
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
        _sf = self._fx * cg + self._fy * sg
        _smax = float(_sf.max()) if len(_sf) else 0.0
        lo = na_hint / 2.5 if na_hint and math.isfinite(na_hint) else 10.0
        hi = na_hint * 2.5 if na_hint and math.isfinite(na_hint) else 1.0e5
        flo = self._state(gamma_rad, lo, _smax)[0] - N_target
        fhi = self._state(gamma_rad, hi, _smax)[0] - N_target
        for _ in range(8):
            if flo <= 0.0 <= fhi:
                break
            if flo > 0.0:
                hi, fhi = lo, flo
                lo = lo / 4.0
                flo = self._state(gamma_rad, lo, _smax)[0] - N_target
            else:
                lo, flo = hi, fhi
                hi = hi * 4.0
                fhi = self._state(gamma_rad, hi, _smax)[0] - N_target
        if not (flo <= 0.0 <= fhi):
            return None
        for _ in range(28):
            mid = 0.5 * (lo + hi)
            fm = self._state(gamma_rad, mid, _smax)[0] - N_target
            if fm < 0.0:
                lo = mid
            else:
                hi = mid
        na = 0.5 * (lo + hi)
        N, M2, M3 = self._state(gamma_rad, na, _smax)
        return (N, M2, M3, na)

    def boundary_fine(self, N: float, theta_deg: float):
        """Trạng thái biên fine tại (N, theta): tinh chỉnh bracket thắng
        cuộc của bản fast bằng trạng thái fine (chặt đôi gamma + na).
        Trả dict như _roots + s_max/s_min."""
        if N > self.N_max or N < self.N_min:
            return None
        roots = self._roots(self._scan(N, theta_deg))
        if not roots:
            # Lỗ lưới gamma (tiết diện mảnh, N thấp): dùng nghiệm phục
            # hồi đã tinh chỉnh bằng trạng thái fine làm điểm tựa.
            roots = self._recover_roots(N, theta_deg)
        if not roots:
            return None
        r = min(roots, key=lambda x: x["capacity"])
        # Nhận diện miền kéo sâu: na họ cũ luôn >= na tại điểm nối
        # eps_cu*h_s/(eps_cu - sàn); na nhỏ hơn ngưỡng đó chỉ có ở
        # họ kéo sâu (na thu về 0 rồi âm khi trục trung hòa ra ngoài).
        _is_deep = False
        try:
            _gr = math.radians(r["gamma_deg"])
            _sf = self._fx * math.cos(_gr) + self._fy * math.sin(_gr)
            _hs = max(float(_sf.max()) - float(_sf.min()), 1e-9) \
                if len(_sf) else 1e-9
            _na_j = self.eps_cu * _hs / (self.eps_cu - self._deep_floor)
            _is_deep = math.isfinite(r["na"]) and r["na"] < _na_j
        except Exception:
            _is_deep = False
        if _is_deep:
            # Tinh chỉnh bằng họ kéo sâu (chặt đôi gamma + eps_top),
            # không dùng _fine_state_hint (chặt đôi na với eps_cu cố
            # định — không với tới miền này).
            try:
                th = math.radians(theta_deg)
                px, py = math.cos(th), -math.sin(th)
                ux, uy = math.sin(th), math.cos(th)
                ga = self.gammas[r["gi_a"]]
                gb = ga + math.radians(self.GAMMA_STEP)
                sta = self._deep_state_at_N(ga, N)
                stb = self._deep_state_at_N(gb % (2.0 * math.pi), N)
                if sta is not None and stb is not None:
                    fa = sta[1] * px + sta[2] * py
                    fb = stb[1] * px + stb[2] * py
                    if fa * fb < 0.0:
                        for _ in range(25):
                            gm = 0.5 * (ga + gb)
                            stm = self._deep_state_at_N(
                                gm % (2.0 * math.pi), N)
                            if stm is None:
                                break
                            pm = stm[1] * px + stm[2] * py
                            if fa * pm <= 0.0:
                                gb = gm
                            else:
                                ga, fa = gm, pm
                        gm = 0.5 * (ga + gb)
                        stm = self._deep_state_at_N(
                            gm % (2.0 * math.pi), N)
                        if stm is not None:
                            r = {"gamma_deg": math.degrees(gm) % 360.0,
                                 "capacity": stm[1] * ux + stm[2] * uy,
                                 "na": stm[3], "M2": stm[1], "M3": stm[2],
                                 "eps_top": stm[4], "kappa": stm[5]}
            except Exception:
                pass
        else:
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
        s_f = self._fx * math.cos(g) + self._fy * math.sin(g)
        r["s_max"] = float(s_f.max()) if len(s_f) else 0.0
        r["s_min"] = float(s_f.min()) if len(s_f) else 0.0
        # Ghi thêm (eps_top, kappa) để neutral_axis_at_N tái dựng
        # đúng mặt phẳng biến dạng cả ở miền kéo sâu (ở đó eps_top
        # != eps_cu nên công thức cũ kappa = eps_cu/na là sai).
        # Họ kéo sâu: na = eps_top*h_s/(eps_top - sàn) ->
        # eps_top = na*sàn/(na - h_s).
        if "eps_top" not in r and math.isfinite(r["na"]):
            _hs2 = max(r["s_max"] - r["s_min"], 1e-9)
            _na_j2 = self.eps_cu * _hs2 / (self.eps_cu - self._deep_floor)
            if r["na"] < _na_j2 and r["na"] != _hs2:
                _et = r["na"] * self._deep_floor / (r["na"] - _hs2)
                r["eps_top"] = _et
                r["kappa"] = (_et - self._deep_floor) / _hs2
            else:
                r["eps_top"] = self.eps_cu
                r["kappa"] = self.eps_cu / r["na"] if r["na"] != 0 else 0.0
        return r


def _tcvn_exact_fingerprint(fs: FiberSection, model: str):
    sec = fs.sec
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
            round(float(fs.Rb), 4), round(float(fs.Rs), 4),
            round(float(fs.Rsc), 4), str(model))


_TCVN_EXACT_CACHE: dict = {}


def _get_tcvn_exact(fs: FiberSection, model: str = "3line") -> _TCVNExact:
    key = _tcvn_exact_fingerprint(fs, model)
    eng = _TCVN_EXACT_CACHE.get(key)
    if eng is None:
        eng = _TCVNExact(fs, model)
        _TCVN_EXACT_CACHE[key] = eng
    return eng


class BiaxialCapacity:
    """Khả năng chịu nén uốn xiên của tiết diện (mặt tương tác 3D rời rạc)."""

    def __init__(self, sec: Section, model: str = "3line",
                 n_angles: int = 24, n_points: int = 48):
        self.fs = FiberSection(sec)
        self.model = model
        self._n_points = n_points
        step = 360.0 / n_angles
        self.angles: List[float] = [k * step for k in range(n_angles)]
        # curves dựng LƯỜI (lazy) khi thật sự cần: trước đây dựng ngay
        # trong __init__ khiến mỗi lần tạo BiaxialCapacity (rất nhiều
        # lần trong 1 CHECK do các hàm vẽ tạo mới) tốn ~1s cho 24
        # đường cong không ai dùng tới.
        self._curves = None

        # Engine song trục exact (D/C + capacity dùng bản này từ 2026-10-21;
        # curves giữ cho các nhu cầu phụ trợ như N_max)
        self._exact = _get_tcvn_exact(self.fs, model)

    @property
    def curves(self) -> Dict[float, List[Tuple[float, float]]]:
        """theta -> đường cong (N, M) đơn trục. Dựng ở lần truy cập
        đầu tiên bằng đúng thuật toán cũ, cache trong object."""
        if self._curves is None:
            self._curves = {
                th: uniaxial_curve_fs(self.fs, th, self.model,
                                      self._n_points)
                for th in self.angles}
        return self._curves

    def moment_capacity(self, N: float, phi_deg: float) -> float:
        """Mô men khả năng chịu tại (N, hướng phi độ).

        Từ 2026-10-21: capacity EXACT (nghiệm cân bằng M_perp = 0 trên
        lưới trạng thái biến dạng phẳng), không còn nội suy giữa 2 đường
        cong đơn trục construction cũ.
        """
        return self._exact.capacity_fast(N, phi_deg)

    def exact_capacity(self, N: float, theta_deg: float) -> float:
        """Capacity exact bản fine (chặt đôi na + gamma) — bản tham chiếu
        dùng cho kiểm chứng; moment_capacity là bản nội suy nhanh."""
        return self._exact.capacity_fine(N, theta_deg)

    def mx_my_curve(self, N: float, n_angles: int = 72) -> List[Tuple[float, float]]:
        """Đường cong tương tác Mx-My tại lực dọc N cho trước.

        Trả về list (Mx, My) khép kín.
        """
        pts: List[Tuple[float, float]] = []
        for k in range(n_angles):
            th = 360.0 * k / n_angles
            m = self.moment_capacity(N, th)
            rad = math.radians(th)
            pts.append((m * math.sin(rad), m * math.cos(rad)))  # quy ước ETABS: M2=M sinθ, M3=M cosθ
        pts.append(pts[0])
        return pts

    def surface_grid(self, n_n: int = 25, n_angles: int = 48):
        """Lưới mặt tương tác 3D (N, Mx, My) để vẽ.

        Trả về (N_vals, Theta_vals, Mx_grid, My_grid).
        """
        # biên N: từ kéo max đến nén max (lấy từ đường cong θ=0)
        curve0 = self.curves[self.angles[0]]
        n_min = curve0[-1][0]
        n_max = curve0[0][0]
        n_vals = np.linspace(n_min, n_max, n_n)
        th_vals = np.linspace(0, 360, n_angles, endpoint=False)
        mx_grid = np.zeros((n_n, n_angles))
        my_grid = np.zeros((n_n, n_angles))
        for i, nn in enumerate(n_vals):
            for j, th in enumerate(th_vals):
                m = self.moment_capacity(float(nn), float(th))
                rad = math.radians(th)
                mx_grid[i, j] = m * math.sin(rad)  # M2
                my_grid[i, j] = m * math.cos(rad)  # M3
        return n_vals, th_vals, mx_grid, my_grid

    def dc_ratio(self, N: float, Mx: float, My: float,
                 n_iter: int = 60) -> dict:
        """Tỷ số D/C theo phương pháp tia 3D.

        Tìm λ_max sao cho λ·(N, Mx, My) nằm trên mặt tương tác.
        D/C = 1/λ_max. Trả về dict {dc, lambda_max, Bx, By, BN, ok}.
        """
        Mstar = math.hypot(Mx, My)
        if Mstar < 1e-12 and abs(N) < 1e-12:
            return {"dc": 0.0, "lambda_max": float("inf"),
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": True}
        phi = math.degrees(math.atan2(Mx, My)) if Mstar > 1e-12 else 0.0

        def f(lam: float) -> float:
            return self.moment_capacity(lam * N, phi) - lam * Mstar

        flo = f(0.0)
        if flo <= 1e-12:
            # ngay tại gốc đã vượt khả năng (trường hợp suy biến)
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
        res = {"dc": dc, "lambda_max": lam,
               "Bx": lam * Mx, "By": lam * My, "BN": lam * N,
               "ok": dc <= 1.0}
        # Mặt phẳng biến dạng tại điểm biên B (để vẽ đường trung hòa/vùng
        # nén nhất quán với D/C exact): hướng gradient gamma* + na*
        try:
            _b = self._exact.boundary_fast(lam * N, phi)
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

    def check(self, N: float, Mx: float, My: float) -> dict:
        """Kiểm tra (N kN, Mx, My kN·m). Trả về dict kết quả."""
        M = math.hypot(Mx, My)
        phi = math.degrees(math.atan2(Mx, My)) if M > 1e-12 else 0.0
        Mcap = self.moment_capacity(N, phi)
        util = M / Mcap if Mcap > 1e-12 else (float("inf") if M > 1e-12 else 0.0)
        # khả năng chịu dọc trục
        Nmax = self.curves[0.0][0][0] if self.curves else 0.0
        return {
            "N": N, "Mx": Mx, "My": My,
            "M_resultant": M, "phi_deg": phi,
            "M_capacity": Mcap,
            "utilization": util,
            "ok": util <= 1.0,
            "N_max": Nmax,
        }

def neutral_axis_at_N(fs, N_target_kN: float, theta_deg: float,
                      model: str = "3line", n_points: int = 96):
    """Đường trung hòa từ mặt phẳng biến dạng EXACT tại (N_target, theta).

    Từ 2026-10-21: dùng mặt phẳng biên của nghiệm cân bằng song trục
    exact (gamma*, na*) tại mức N — nhất quán với D/C exact mới, thay
    cho construction đường cong đơn trục cũ.
    Quy ước góc kiểu ETABS: theta đo từ trục M3.

    Trả về dict cùng định dạng bản cũ. Hệ trục yp được chọn trùng hướng
    gradient gamma (yp ≡ s = x·cosγ + y·sinγ, tức
    st = −cosγ, ct = sinγ) nên: yp_na = s_max − na (vị trí strain = 0),
    eps = eps0 + kx_p·yp với kx_p = kappa, eps0 = eps_top − kx_p·s_max.
    Họ cũ: eps_top = eps_cu, kappa = eps_cu/na. Họ kéo sâu:
    boundary_fine ghi sẵn (eps_top, kappa); nếu thiếu (nghiệm chưa
    tinh chỉnh) thì suy từ na theo na = eps_top*h_s/(eps_top − sàn).
    Khi eps_top < 0, yp_na nằm ngoài tiết diện phía nén nên hàm vẽ
    sẽ không tô vùng nén — đúng vật lý (toàn tiết diện chịu kéo).
    """
    eng = _get_tcvn_exact(fs, model)
    b = eng.boundary_fine(float(N_target_kN), float(theta_deg))
    if b is None:
        th = math.radians(90.0 - theta_deg)
        ct, st = math.cos(th), math.sin(th)
        yp_f = -fs.fx * st + fs.fy * ct
        return {'found': False, 'yp_na': None, 'theta_deg': theta_deg,
                'ct': ct, 'st': st,
                'y_top': float(np.max(yp_f)) if yp_f.size else 0,
                'y_bot': float(np.min(yp_f)) if yp_f.size else 0,
                'eps0': 0, 'kx_p': 0}
    g = math.radians(b["gamma_deg"])
    ct = math.sin(g)
    st = -math.cos(g)
    na = b["na"]
    s_max, s_min = b["s_max"], b["s_min"]
    if math.isinf(na):
        # Nén đều: không có đường trung hòa
        return {'found': True, 'yp_na': None, 'theta_deg': theta_deg,
                'ct': ct, 'st': st, 'y_top': s_max, 'y_bot': s_min,
                'eps0': EPS_B2, 'kx_p': 0.0,
                'gamma_deg': b["gamma_deg"], 'na_depth': na}
    if "eps_top" in b and "kappa" in b:
        eps_top, kappa = b["eps_top"], b["kappa"]
    else:
        kappa = EPS_B2 / na if na != 0 else 0.0
        eps_top = EPS_B2
    return {'found': True, 'yp_na': s_max - na, 'theta_deg': theta_deg,
            'ct': ct, 'st': st, 'y_top': s_max, 'y_bot': s_min,
            'eps0': eps_top - kappa * s_max, 'kx_p': kappa,
            'gamma_deg': b["gamma_deg"], 'na_depth': na}
