"""Kiểm tra cột BTCT theo ACI 318-19.

Bao gồm:
- Biểu đồ tương tác P-M dùng fiber với khối ứng suất chữ nhật ACI
  (eps_cu = 0.003, ứng suất 0.85*f'c, a = beta1*c) và hệ số phi theo
  biến dạng thép chịu kéo ngoài cùng (ACI 21.2.2).
- Hệ số phóng đại mô men cho cột mảnh: delta_ns (ACI 6.6.4.5).
- Kiểm tra cắt theo ACI 22.5.5.1.

Đơn vị: mm, MPa, kN, kN.m (giống interaction.py). Nén dương.
"""

import math
from typing import Dict, List, Tuple

import numpy as np

from .aci_materials import (ACIConcrete, ACISteel, PHI_SPIRAL, PHI_TIED,
                            max_axial_phi, phi_factor)
from .sections import Section


# ---------------------------------------------------------------------------
# Ứng suất thép (quy ước nén dương để cộng lực với bê tông)
# ---------------------------------------------------------------------------
def _aci_steel_stress(eps_cpos: float, steel: ACISteel) -> float:
    """Ứng suất thép (MPa), nén dương.

    eps_cpos: biến dạng, nén dương.
    """
    ey = steel.eps_y
    if eps_cpos >= 0.0:
        return min(steel.Es * eps_cpos, steel.fy)
    return -min(steel.Es * (-eps_cpos), steel.fy)


# ---------------------------------------------------------------------------
# 1. Đường cong tương tác P-M (danh nghĩa) theo ACI 318-19
# ---------------------------------------------------------------------------
def aci_interaction_curve(sec: Section, conc: ACIConcrete, steel: ACISteel,
                          theta_deg: float, n_points: int = 48,
                          tied: bool = True) -> List[Tuple[float, float, float, float]]:
    """Đường cong tương tác (N, M) danh nghĩa theo ACI 318-19.

    Phương pháp fiber như interaction.uniaxial_curve_fs nhưng bê tông dùng
    khối ứng suất chữ nhật tương đương: eps_cu = 0.003 tại mép nén,
    a = beta1*c, ứng suất 0.85*f'c trong vùng khối chữ nhật (ACI 22.2.2.4).

    Trả về list (N_kN, M_kNm, eps_t, phi) sắp theo N giảm dần, trong đó
    N, M là DANH NGHĨA (chưa nhân phi); eps_t là biến dạng kéo lớn nhất
    của thép (số dương, độ lớn); phi là hệ số giảm cường độ tại điểm đó.
    """
    # Quy ước góc kiểu ETABS: α đo từ trục M3 (α=0° → thuần M3/My,
    # α=90° → thuần M2/Mx), tức hướng mô men (M2, M3) = (sin α, cos α).
    th = math.radians(90.0 - theta_deg)
    ct, st = math.cos(th), math.sin(th)
    fx = np.array([f.x for f in sec.fibers], dtype=float)
    fy = np.array([f.y for f in sec.fibers], dtype=float)
    fa = np.array([f.area for f in sec.fibers], dtype=float)
    rx = np.array([r.x for r in sec.rebars], dtype=float)
    ry = np.array([r.y for r in sec.rebars], dtype=float)
    ra = np.array([r.area for r in sec.rebars], dtype=float)

    if not fx.size:
        return [(0.0, 0.0, 0.0, 0.90)]

    # Tọa độ xoay: uốn quanh trục x' -> biến dạng theo y'
    yp_f = -fx * st + fy * ct
    yp_r = -rx * st + ry * ct if ra.size else np.array([])

    y_top = float(np.max(yp_f))
    y_bot = float(np.min(yp_f))
    h = y_top - y_bot
    if h <= 0:
        return [(0.0, 0.0, 0.0, 0.90)]

    eps_cu = conc.eps_cu          # 0.003
    b1 = conc.beta1               # hệ số khối ứng suất
    f_block = conc.f_block        # 0.85*f'c (MPa)
    eps_y = steel.eps_y

    pts: List[Tuple[float, float, float, float]] = []

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
                # Chiều sâu trục trung hòa từ mép nén: c = eps_top / kx
                c = eps_top / kx_p
                a_blk = b1 * c
                dist = y_top - yp_f  # khoảng cách từ mép nén
                in_block = dist <= a_blk + 1e-9
                sf = np.where(in_block, f_block, 0.0)
            er = eps0 + kx_p * yp_r if yp_r.size else yp_r

        Nf = float(np.sum(sf * fa))
        Mf = float(np.sum(sf * fa * yp_f))
        if ra.size:
            sr = np.array([_aci_steel_stress(e, steel) for e in er])
            # Thép trong khối nén đã chiếm chỗ bê tông -> dùng ứng suất
            # thực (net): fs - 0.85f'c (theo cách tính tay SP: trừ 0.85f'c
            # khỏi fs' trước khi tính Cs). Chỉ áp cho thanh chịu nén.
            if yp_r.size and a_blk > 0.0:
                dist_r = y_top - yp_r
                in_blk_r = dist_r <= a_blk + 1e-9
                sr = np.where(in_blk_r & (sr > 0.0), sr - f_block, sr)
            # eps_t: biến dạng kéo lớn nhất của thép (độ lớn, số dương)
            eps_t = float(np.max(-er))
            Nr = float(np.sum(sr * ra))
            Mr = float(np.sum(sr * ra * yp_r))
        else:
            Nr = Mr = 0.0
            eps_t = 0.0

        N_nom = (Nf + Nr) / 1000.0       # kN, nén dương
        M_nom = abs(Mf + Mr) / 1e6       # kN.m
        phi = phi_factor(max(eps_t, 0.0), eps_y, tied)
        pts.append((N_nom, M_nom, eps_t, phi))

    # Nén đúng tâm (biến dạng đều = eps_cu)
    add_point(eps_cu, 0.0)

    # Quét: giữ mép nén đạt eps_cu, mép kia giảm dần về kéo
    eps_s_max = max(0.01, 10.0 * eps_y)
    for i in range(1, n_points):
        frac = i / n_points
        f2 = frac ** 0.8  # dày hơn gần vùng chuyển tiếp
        eps_bot = eps_cu - f2 * (eps_cu + eps_s_max)
        kx_p = (eps_cu - eps_bot) / h
        eps0 = eps_cu - kx_p * y_top
        add_point(eps0, kx_p)

    # Kéo đúng tâm
    add_point(-eps_s_max, 0.0)

    # Giữ đúng thứ tự sinh điểm (từ nén đúng tâm đến kéo đúng tâm),
    # KHÔNG sort lại vì N có thể không đơn điệu tuyệt đối do sai số số
    # học -> sort làm xáo trộn M gây zigzag khi vẽ
    clean: List[Tuple[float, float, float, float]] = []
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


# ---------------------------------------------------------------------------
# Engine song trục EXACT (2026-10-21): giải lặp cân bằng chính xác.
#
# Như EC2: quét mặt phẳng biến dạng theo hướng gradient gamma, tích phân
# fiber ra CẢ HAI thành phần mô men; capacity tại (N, theta) là nghiệm
# M_perp = 0 trong frame tải. Mô hình vật liệu GIỮ NGUYÊN như
# aci_interaction_curve (khối 0.85f'c sâu beta1*c, thép trong khối nén
# dùng ứng suất net fs - 0.85f'c); mỗi trạng thái danh nghĩa được nhân
# phi(eps_t của chính trạng thái đó) và cắt N thiết kế tại N_cap như
# ACICapacity vẫn làm với các đường cong thiết kế.
# ---------------------------------------------------------------------------
class _ACIExact:
    """Lưới trạng thái exact (đã nhân phi) + nội suy contour tại mức N."""

    N_GAMMA = 120        # bước gamma 3 độ
    N_PTS = 96           # số điểm theo chiều sâu trục trung hòa (dày hơn curve cũ 48 để nội suy contour chính xác)

    def __init__(self, sec, conc, steel, tied=True):
        self.conc = conc
        self.steel = steel
        self.tied = tied
        self.fx = np.array([f.x for f in sec.fibers], dtype=float)
        self.fy = np.array([f.y for f in sec.fibers], dtype=float)
        self.fa = np.array([f.area for f in sec.fibers], dtype=float)
        self.rx = np.array([r.x for r in sec.rebars], dtype=float)
        self.ry = np.array([r.y for r in sec.rebars], dtype=float)
        self.ra = np.array([r.area for r in sec.rebars], dtype=float)
        self.eps_cu = conc.eps_cu            # 0.003
        self.beta1 = conc.beta1
        self.f_block = conc.f_block          # 0.85 f'c
        Ag = sec.gross_area
        Ast = sec.steel_area
        Po_nom = (0.85 * conc.fc * (Ag - Ast) + steel.fy * Ast) / 1000.0
        phi_c = PHI_TIED if tied else PHI_SPIRAL
        self.N_cap = max_axial_phi(tied) * phi_c * Po_nom
        eps_s_max = max(0.01, 10.0 * steel.eps_y)
        gam = [math.radians(3.0 * i) for i in range(self.N_GAMMA)]
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
        self.sweeps = []
        n_all = []
        for g in gam:
            cg, sg = math.cos(g), math.sin(g)
            s_f = self.fx * cg + self.fy * sg
            s_r = self.rx * cg + self.ry * sg
            s_max = float(s_f.max()) if len(s_f) else 0.0
            s_min = float(s_f.min()) if len(s_f) else 0.0
            h_s = max(s_max - s_min, 1e-9)
            _pre = (s_f, s_r, s_max)
            Ns, M2s, M3s, NAs, ETs = [], [], [], [], []
            for eps_far in self._eps_far:
                if eps_far >= self.eps_cu - 1e-15:
                    na = float("inf")
                else:
                    na = self.eps_cu * h_s / (self.eps_cu - eps_far)
                Nd, M2, M3, et = self._state_design(g, na, _pre)
                Ns.append(Nd); M2s.append(M2); M3s.append(M3)
                NAs.append(na); ETs.append(et)
            # Lọc N thiết kế giảm nghiêm ngặt (giữ điểm đầu mỗi mức):
            # khớp ngữ nghĩa nội suy "qua điểm đầu tiên" của đường cong cũ
            kN, kM2, kM3, kNA, kET = [], [], [], [], []
            last = None
            for N, M2, M3, na, et in zip(Ns, M2s, M3s, NAs, ETs):
                if last is None or N < last - 1e-9:
                    kN.append(N); kM2.append(M2); kM3.append(M3)
                    kNA.append(na); kET.append(et)
                    last = N
            self.sweeps.append({
                "N": np.array(kN), "M2": np.array(kM2),
                "M3": np.array(kM3), "NA": np.array(kNA),
                "ET": np.array(kET), "s_max": s_max, "s_min": s_min})
            n_all.extend(kN)
        self.N_max = max(n_all) if n_all else 0.0
        self.N_min = min(n_all) if n_all else 0.0
        self._build_scan_cache()

    def _build_scan_cache(self):
        """Ma tran dem (padding) cua cac sweep de quet gamma vector hoa.

        XP[g] = -N tang dan (dem lap gia tri cuoi), F2/F3/FNA/FET tuong
        ung. _scan_fast dung cac ma tran nay voi cong thuc noi suy
        f0 + ((f1-f0)/(x1-x0))*(x-x0) — da kiem chung khop tung bit voi
        np.interp o moi diem trong; rieng diem mut phai (x == xp[-1])
        tra thang gia tri cuoi nhu np.interp.
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
        self._FET = np.zeros((G, L))
        for gi, sw in enumerate(self.sweeps):
            n = len(sw["N"])
            self._glen[gi] = n
            if n == 0:
                continue
            self._N0[gi] = sw["N"][0]
            self._N1[gi] = sw["N"][-1]
            for arr, key in ((self._XP, None), (self._F2, "M2"),
                             (self._F3, "M3"), (self._FNA, "NA"),
                             (self._FET, "ET")):
                v = -sw["N"] if key is None else sw[key]
                arr[gi, :n] = v
                if n < L:
                    arr[gi, n:] = v[-1]

    def _scan_fast(self, N: float, theta_deg: float, full: bool):
        """Ban vector hoa cua _scan: cung pts, cung thu tu, gia tri khop
        tung bit voi _sweep_at_N/np.interp. full=False: na/et tra 0.0
        (capacity_fast khong dung 2 gia tri nay)."""
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
        ETa = _interp(self._FET) if full else None
        for k, gi in enumerate(idx):
            M2 = float(M2a[k]); M3 = float(M3a[k])
            na = float(NAa[k]) if full else 0.0
            et = float(ETa[k]) if full else 0.0
            pts.append((math.degrees(self.gammas[gi]),
                        M2 * ux + M3 * uy, M2 * px + M3 * py,
                        na, M2, M3, int(gi), et))
        return pts

    def _state_nom(self, gamma_rad: float, na: float, _pre=None):
        """Trạng thái danh nghĩa (gamma, na) -> (N, M2, M3, eps_t).

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
            block_f = dist_f <= self.beta1 * na
            block_r = dist_r <= self.beta1 * na
            eps_r = self.eps_cu - kappa * dist_r
        sig_f = np.where(block_f, self.f_block, 0.0)
        fs = np.clip(self.steel.Es * eps_r, -self.steel.fy, self.steel.fy)
        fs = np.where(block_r & (fs > 0.0), fs - self.f_block, fs)
        cf = sig_f * self.fa
        cs = fs * self.ra
        N = (cf.sum() + cs.sum()) / 1000.0
        M2 = (float(cf @ self.fy) + float(cs @ self.ry)) / 1.0e6
        M3 = (float(cf @ self.fx) + float(cs @ self.rx)) / 1.0e6
        eps_t = float(max(0.0, -eps_r.min())) if len(eps_r) else 0.0
        return N, M2, M3, eps_t

    def _state_design(self, gamma_rad: float, na: float, _pre=None):
        """Trạng thái thiết kế: nhân phi(eps_t), cắt N tại N_cap."""
        Nn, M2n, M3n, eps_t = self._state_nom(gamma_rad, na, _pre)
        phi = phi_factor(eps_t, self.steel.eps_y, self.tied)
        Nd = phi * Nn
        if Nd > self.N_cap:
            Nd = self.N_cap
        return Nd, phi * M2n, phi * M3n, eps_t

    def _sweep_at_N(self, gi: int, N: float):
        sw = self.sweeps[gi]
        Ns = sw["N"]
        if len(Ns) < 2 or N > Ns[0] or N < Ns[-1]:
            return None
        M2 = float(np.interp(-N, -Ns, sw["M2"]))
        M3 = float(np.interp(-N, -Ns, sw["M3"]))
        na = float(np.interp(-N, -Ns, sw["NA"]))
        et = float(np.interp(-N, -Ns, sw["ET"]))
        return M2, M3, na, et

    def _scan(self, N: float, theta_deg: float):
        th = math.radians(theta_deg)
        ux, uy = math.sin(th), math.cos(th)
        px, py = math.cos(th), -math.sin(th)
        pts = []
        for gi, g in enumerate(self.gammas):
            st = self._sweep_at_N(gi, N)
            if st is None:
                continue
            M2, M3, na, et = st
            pts.append((math.degrees(g), M2 * ux + M3 * uy,
                        M2 * px + M3 * py, na, M2, M3, gi, et))
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
                if not (a[6] == _ACIExact.N_GAMMA - 1 and b[6] == 0):
                    continue
            elif b[6] != a[6] + 1:
                continue
            pa, pb = a[2], b[2]
            if pa == 0.0 and a[1] > 0:
                out.append({"gamma_deg": a[0], "capacity": a[1], "na": a[3],
                            "M2": a[4], "M3": a[5], "eps_t": a[7],
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
                                "eps_t": a[7] + t * (b[7] - a[7]),
                                "gi_a": a[6], "gi_b": b[6]})
        return out

    def capacity_fast(self, N: float, theta_deg: float) -> float:
        """Capacity thiết kế exact tại (N, theta) từ lưới quét (nội suy)."""
        if N > self.N_max or N < self.N_min:
            return 0.0
        pts = self._scan_fast(N, theta_deg, False)
        roots = self._roots(pts)
        if roots:
            return min(r["capacity"] for r in roots)
        pos = [p[1] for p in pts if p[1] > 0]
        return max(pos) if pos else 0.0

    def boundary_fast(self, N: float, theta_deg: float):
        """Trạng thái biên tại (N, theta): dict(gamma_deg, na, M2, M3,
        capacity, eps_t) hoặc None."""
        if N > self.N_max or N < self.N_min:
            return None
        roots = self._roots(self._scan_fast(N, theta_deg, True))
        if not roots:
            return None
        return min(roots, key=lambda r: r["capacity"])

    # ---- Bản fine ----
    def _state_at_N_fine(self, gamma_rad: float, N_target: float):
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
        vals = [self._state_design(gamma_rad, na, _pre) for na in nas]
        Ns = [v[0] for v in vals]
        if N_target > max(Ns) or N_target < min(Ns):
            return None
        for i in range(len(Ns) - 1):
            if (Ns[i] - N_target) * (Ns[i + 1] - N_target) <= 0.0 \
                    and abs(Ns[i] - Ns[i + 1]) > 1e-9:
                lo, hi = nas[i + 1], nas[i]      # na tăng -> Nd tăng (gần đúng)
                flo = self._state_design(gamma_rad, lo, _pre)[0] - N_target
                if math.isinf(hi):
                    if abs(Ns[0] - N_target) < 1e-6:
                        return (Ns[0], vals[0][1], vals[0][2],
                                float("inf"), vals[0][3])
                    hi = nas[i + 1] * 4.0 + h_s
                for _ in range(40):
                    mid = 0.5 * (lo + hi)
                    fm = self._state_design(gamma_rad, mid, _pre)[0] - N_target
                    if flo * fm <= 0.0:
                        hi = mid
                    else:
                        lo, flo = mid, fm
                na = 0.5 * (lo + hi)
                Nd, M2, M3, et = self._state_design(gamma_rad, na, _pre)
                return (Nd, M2, M3, na, et)
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
            _N, M2, M3, na, et = st
            pts.append((math.degrees(g), M2 * ux + M3 * uy,
                        M2 * px + M3 * py, na, M2, M3, et))
        roots = []
        n = len(pts)
        for i in range(n):
            a = pts[i]
            b = pts[(i + 1) % n]
            if (i + 1) % n == 0:
                if not (abs(a[0] - 357.0) < 1e-9 and abs(b[0]) < 1e-9):
                    continue
            elif abs(b[0] - a[0] - 3.0) > 1e-9:
                continue
            pa, pb = a[2], b[2]
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
                                  "M2": stm[1], "M3": stm[2],
                                  "eps_t": stm[4]})
            elif pa == 0.0 and a[1] > 0:
                roots.append({"gamma_deg": a[0], "capacity": a[1],
                              "na": a[3], "M2": a[4], "M3": a[5],
                              "eps_t": a[6]})
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
        """Trạng thái thiết kế fine tại (gamma, N) với bracket na từ
        na_hint (mở rộng hình học tới khi kẹp được N, rồi chặt đôi)."""
        cg, sg = math.cos(gamma_rad), math.sin(gamma_rad)
        _sf = self.fx * cg + self.fy * sg
        _sr = self.rx * cg + self.ry * sg
        _pre = (_sf, _sr, float(_sf.max()) if len(_sf) else 0.0)
        lo = na_hint / 2.5 if na_hint and math.isfinite(na_hint) else 10.0
        hi = na_hint * 2.5 if na_hint and math.isfinite(na_hint) else 1.0e5
        flo = self._state_design(gamma_rad, lo, _pre)[0] - N_target
        fhi = self._state_design(gamma_rad, hi, _pre)[0] - N_target
        for _ in range(8):
            if flo <= 0.0 <= fhi:
                break
            if flo > 0.0:
                hi, fhi = lo, flo
                lo = lo / 4.0
                flo = self._state_design(gamma_rad, lo, _pre)[0] - N_target
            else:
                lo, flo = hi, fhi
                hi = hi * 4.0
                fhi = self._state_design(gamma_rad, hi, _pre)[0] - N_target
        if not (flo <= 0.0 <= fhi):
            return None
        for _ in range(28):
            mid = 0.5 * (lo + hi)
            fm = self._state_design(gamma_rad, mid, _pre)[0] - N_target
            if fm < 0.0:
                lo = mid
            else:
                hi = mid
        na = 0.5 * (lo + hi)
        Nd, M2, M3, et = self._state_design(gamma_rad, na, _pre)
        return (Nd, M2, M3, na, et)

    def boundary_fine(self, N: float, theta_deg: float):
        """Trạng thái biên fine tại (N, theta): tinh chỉnh bracket thắng
        cuộc của bản fast bằng trạng thái fine (chặt đôi gamma + na).
        Trả dict như _roots + s_max/s_min."""
        if N > self.N_max or N < self.N_min:
            return None
        roots = self._roots(self._scan(N, theta_deg))
        if not roots:
            return None
        r = min(roots, key=lambda x: x["capacity"])
        try:
            th = math.radians(theta_deg)
            px, py = math.cos(th), -math.sin(th)
            ux, uy = math.sin(th), math.cos(th)
            ga = self.gammas[r["gi_a"]]
            gb = ga + math.radians(3.0)
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
                             "na": stm[3], "M2": stm[1], "M3": stm[2],
                             "eps_t": stm[4]}
        except Exception:
            pass
        g = math.radians(r["gamma_deg"])
        s_f = self.fx * math.cos(g) + self.fy * math.sin(g)
        r["s_max"] = float(s_f.max()) if len(s_f) else 0.0
        r["s_min"] = float(s_f.min()) if len(s_f) else 0.0
        return r


def _aci_exact_fingerprint(sec, conc, steel, tied):
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
            round(float(conc.fc), 4), round(float(steel.fy), 4),
            bool(tied))


_ACI_EXACT_CACHE: dict = {}


def _get_aci_exact(sec, conc, steel, tied=True) -> _ACIExact:
    key = _aci_exact_fingerprint(sec, conc, steel, tied)
    eng = _ACI_EXACT_CACHE.get(key)
    if eng is None:
        eng = _ACIExact(sec, conc, steel, tied=tied)
        _ACI_EXACT_CACHE[key] = eng
    return eng


# ---------------------------------------------------------------------------
# Lớp khả năng chịu lực ACI (mặt tương tác 3D đã giảm phi)
# ---------------------------------------------------------------------------
class ACICapacity:
    """Khả năng chịu nén uốn xiên theo ACI 318-19 (mặt 3D đã nhân phi).

    Mỗi góc quét một đường cong danh nghĩa, nhân phi theo từng điểm,
    cắt đỉnh ở phi*Pn,max (ACI 22.4.2.2).
    """

    def __init__(self, sec: Section, conc: ACIConcrete, steel: ACISteel,
                 tied: bool = True, n_angles: int = 24, n_points: int = 48):
        self.sec = sec
        self.conc = conc
        self.steel = steel
        self.tied = tied
        self.phi_c = PHI_TIED if tied else PHI_SPIRAL
        self._n_angles = n_angles
        self._n_points = n_points

        # Pn danh nghĩa lớn nhất (nén đúng tâm): Po = 0.85f'c(Ag-Ast) + fy*Ast
        Ag = sec.gross_area
        Ast = sec.steel_area
        Po_nom = (0.85 * conc.fc * (Ag - Ast) + steel.fy * Ast) / 1000.0  # kN
        # Đỉnh thiết kế: 0.80/0.85 * phi_c * Po (ACI 22.4.2.2)
        self.N_cap = max_axial_phi(tied) * self.phi_c * Po_nom
        self.Po_nom = Po_nom

        step = 360.0 / n_angles
        self.angles: List[float] = [k * step for k in range(n_angles)]
        # design_curves dựng LƯỜI (lazy) khi thật sự cần (surface_grid,
        # eps_t_at fallback): trước đây dựng ngay trong __init__ khiến
        # mỗi lần tạo ACICapacity (rất nhiều lần trong 1 CHECK do các
        # hàm vẽ tạo mới) tốn ~0.5s cho 24 đường cong không ai dùng tới.
        self._design_curves = None

        # Engine song trục exact (D/C + capacity dùng bản này từ 2026-10-21;
        # design_curves giữ cho các nhu cầu phụ trợ)
        self._exact = _get_aci_exact(sec, conc, steel, tied)

    @property
    def design_curves(self) -> Dict[float, List[Tuple[float, float, float]]]:
        """theta -> list (Nd, Md, eps_t) đã nhân phi, sắp N giảm dần.

        Dựng ở lần truy cập đầu tiên bằng đúng thuật toán cũ (kết quả
        không đổi), cache trong object.
        """
        if self._design_curves is None:
            curves: Dict[float, List[Tuple[float, float, float]]] = {}
            for th in self.angles:
                nom = aci_interaction_curve(self.sec, self.conc, self.steel,
                                            th, self._n_points, self.tied)
                dsgn: List[Tuple[float, float, float]] = []
                for (Nn, Mn, eps_t, phi) in nom:
                    Nd, Md = phi * Nn, phi * Mn
                    # Cắt đỉnh ở N_cap
                    if Nd > self.N_cap:
                        Nd = self.N_cap
                    dsgn.append((Nd, Md, eps_t))
                dsgn.sort(key=lambda p: -p[0])
                # Loại trùng sau khi cắt đỉnh
                clean: List[Tuple[float, float, float]] = []
                for p in dsgn:
                    if (not clean or abs(p[0] - clean[-1][0]) > 1e-6
                            or abs(p[1] - clean[-1][1]) > 1e-6):
                        clean.append(p)
                curves[th] = clean
            self._design_curves = curves
        return self._design_curves

    def _curve_at(self, phi_deg: float) -> List[Tuple[float, float, float]]:
        """Đường cong thiết kế tại góc gần nhất (xử lý wrap-around)."""
        def _adiff(a, b):
            d = abs(a - b) % 360.0
            return min(d, 360.0 - d)
        th = min(self.angles, key=lambda a: _adiff(a, phi_deg))
        return self.design_curves[th]

    def moment_capacity(self, N: float, phi_deg: float) -> float:
        """Khả năng chịu mô men thiết kế (kN.m) tại N (kN).

        Từ 2026-10-21: capacity EXACT (nghiệm cân bằng M_perp = 0 trên
        lưới trạng thái biến dạng phẳng, đã nhân phi từng trạng thái và
        cắt N_cap), không còn construction đường cong đơn trục cũ.
        """
        if N > self.N_cap:
            return 0.0
        return self._exact.capacity_fast(N, phi_deg)

    def exact_capacity(self, N: float, theta_deg: float) -> float:
        """Capacity exact bản fine (chặt đôi na + gamma) — bản tham chiếu
        dùng cho kiểm chứng; moment_capacity là bản nội suy nhanh."""
        if N > self.N_cap:
            return 0.0
        return self._exact.capacity_fine(N, theta_deg)

    def surface_grid(self, n_n: int = 25, n_angles: int = 36):
        """Lưới mặt tương tác 3D (N, M2, M3) để vẽ.

        Trả về (N_vals, Theta_vals, M2_grid, M3_grid).
        """
        import numpy as np
        # Biên N: từ min đến N_cap
        n_min = min(min(p[0] for p in c) for c in self.design_curves.values())
        n_vals = np.linspace(n_min, self.N_cap, n_n)
        th_vals = np.linspace(0, 360, n_angles, endpoint=False)
        m2_grid = np.zeros((n_n, n_angles))
        m3_grid = np.zeros((n_n, n_angles))
        for i, nn in enumerate(n_vals):
            for j, th in enumerate(th_vals):
                m = self.moment_capacity(nn, th)
                rad = math.radians(th)
                # Quy ước ETABS: α đo từ M3, M2 = M*sin, M3 = M*cos
                m2_grid[i, j] = m * math.sin(rad)
                m3_grid[i, j] = m * math.cos(rad)
        return n_vals, th_vals, m2_grid, m3_grid

    def eps_t_at(self, N: float, phi_deg: float) -> float:
        """Biến dạng kéo thép tại điểm có N trên đường cong thiết kế."""
        if N > self.N_cap:
            return 0.0
        return _interp_on_curve(self._curve_at(phi_deg), N, 2)

    def dc_ratio(self, N: float, Mx: float, My: float,
                 n_iter: int = 60) -> dict:
        """Tỷ số D/C theo phương pháp tia 3D trên mặt thiết kế (đã nhân phi).

        Tìm lam_max sao cho lam*(N, Mx, My) nằm trên mặt tương tác.
        D/C = 1/lam_max.
        """
        Mstar = math.hypot(Mx, My)
        if Mstar < 1e-12 and abs(N) < 1e-12:
            return {"dc": 0.0, "lambda_max": float("inf"),
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": True,
                    "phi": 0.90, "eps_t": 0.0}
        phi_deg = math.degrees(math.atan2(Mx, My)) if Mstar > 1e-12 else 0.0

        def f(lam: float) -> float:
            return self.moment_capacity(lam * N, phi_deg) - lam * Mstar

        if f(0.0) <= 1e-12:
            return {"dc": float("inf"), "lambda_max": 0.0,
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": False,
                    "phi": self.phi_c, "eps_t": 0.0}
        lo, hi = 0.0, 1.0
        while f(hi) > 0 and hi < 1e7:
            hi *= 2.0
        if hi >= 1e7:
            return {"dc": 0.0, "lambda_max": float("inf"),
                    "Bx": 0.0, "By": 0.0, "BN": 0.0, "ok": True,
                    "phi": 0.90, "eps_t": 0.01}
        for _ in range(n_iter):
            mid = 0.5 * (lo + hi)
            if mid == lo or mid == hi:
                # Khoảng đã thu về 2 float kề nhau: các vòng sau không
                # đổi được lo/hi nữa (f(mid) trùng f tại đầu mút) —
                # thoát sớm cho kết quả y hệt.
                break
            if f(mid) > 0:
                lo = mid
            else:
                hi = mid
        lam = 0.5 * (lo + hi)
        dc = 1.0 / lam if lam > 1e-12 else float("inf")
        BN = lam * N
        # eps_t/phi tại điểm biên B: lấy từ trạng thái exact tại B (nhất
        # quán với D/C mới); fallback cách cũ nếu không tìm được trạng thái
        eps_t = None
        _gamma = _na = None
        try:
            _b = self._exact.boundary_fast(BN, phi_deg)
            if _b is not None:
                eps_t = _b["eps_t"]
                _gamma = _b["gamma_deg"]
                _na = _b["na"]
        except Exception:
            eps_t = None
        if eps_t is None:
            eps_t = self.eps_t_at(BN, phi_deg)
        phi_lim = phi_factor(max(eps_t, 0.0), self.steel.eps_y, self.tied)
        res = {"dc": dc, "lambda_max": lam,
               "Bx": lam * Mx, "By": lam * My, "BN": BN,
               "ok": dc <= 1.0, "phi": phi_lim, "eps_t": eps_t}
        if _gamma is not None:
            res["gamma_deg"] = _gamma
            res["na_depth"] = _na
        return res


# ---------------------------------------------------------------------------
# 2. Hệ số phóng đại mô men cho cột mảnh (ACI 6.6.4.5)
# ---------------------------------------------------------------------------
def moment_magnification(Pu_kN: float, M1_kNm: float, M2_kNm: float,
                         lu_mm: float, k: float, Ec_MPa: float, Ig_mm4: float,
                         beta_dns: float, Cm_input: float = None) -> dict:
    """Hệ số phóng đại mô men delta_ns cho cột mảnh (ACI 6.6.4.5.2).

    Pu_kN: lực dọc tính toán (kN, nén dương).
    M1, M2: mô men 2 đầu cột (kN.m), M2 là mô men lớn hơn (trị tuyệt đối).
        M1/M2 âm khi uốn cong một chiều (single curvature).
    lu_mm: chiều dài không giằng theo phương đang xét.
    k: hệ số chiều dài hữu hiệu.
    Ec_MPa, Ig_mm4: mô đun đàn hồi và mô men quán tính nguyên.
    beta_dns: tỷ số tải trọng dọc thường xuyên / tổng tải trọng (0..1).
    Cm_input: ghi đè Cm nếu có.

    Trả về dict {delta_ns, Pc_kN, Cm, ok, reason}.
    """
    if abs(M2_kNm) > 1e-12:
        ratio = M1_kNm / M2_kNm
    else:
        ratio = 0.0
    # ACI 6.6.4.5.3:
    # (a) Không tải ngang giữa nhịp: Cm = 0.6 - 0.4*(M1/M2) >= 0.4
    # (b) Có tải ngang giữa nhịp: Cm = 1.0
    # Cột thực tế thường có tải ngang -> Cm = 1.0 (bảo thủ)
    Cm = Cm_input if Cm_input is not None else 1.0

    # EI hiệu dụng (ACI 6.6.4.4.4a): EI = 0.4*Ec*Ig/(1+beta_dns)
    EI_eff = 0.4 * Ec_MPa * Ig_mm4 / (1.0 + beta_dns)  # N.mm2
    klu = k * lu_mm
    if klu <= 0:
        return {"delta_ns": 1.0, "Pc_kN": float("inf"), "Cm": Cm,
                "beta_dns": beta_dns, "ok": True, "reason": "klu <= 0"}
    Pc_N = math.pi ** 2 * EI_eff / (klu ** 2)  # N (Euler)
    Pc_kN = Pc_N / 1000.0
    Pu_N = Pu_kN * 1000.0

    denom = 1.0 - Pu_N / (0.75 * Pc_N)
    if denom <= 0:
        return {"delta_ns": float("inf"), "Pc_kN": Pc_kN, "Cm": Cm,
                "ok": False, "reason": "Pu >= 0.75*Pc: cột quá mảnh (ACI 6.6.4.5.2)"}
    delta_ns = Cm / denom
    delta_ns = max(delta_ns, 1.0)
    return {"delta_ns": delta_ns, "Pc_kN": Pc_kN, "Cm": Cm,
            "beta_dns": beta_dns, "ok": True, "reason": ""}


# ---------------------------------------------------------------------------
# 2b. Hệ số phóng đại mô men sway delta_s (ACI 6.6.4.6.2a)
# ---------------------------------------------------------------------------
def sway_magnification(Q: float = None, sum_Pu_kN: float = None,
                       delta_o_mm: float = None, Vus_kN: float = None,
                       lc_mm: float = None) -> dict:
    """Hệ số phóng đại mô men cho khung sway (ACI 6.6.4.6.2a).

    δs = 1 / (1 - Q) ≥ 1.0
    Q = ΣPu · Δo / (Vus · lc) — chỉ số ổn định tầng.

    Có thể truyền trực tiếp Q, hoặc truyền 4 thông số để tự tính Q:
    - sum_Pu_kN: tổng tải dọc tính toán của tầng (kN)
    - delta_o_mm: chuyển vị lệch tầng bậc 1 (mm)
    - Vus_kN: tổng lực cắt tầng (kN)
    - lc_mm: chiều cao tầng (mm)

    Trả về dict {delta_s, Q, ok, reason}.
    """
    if Q is None:
        if None in (sum_Pu_kN, delta_o_mm, Vus_kN, lc_mm):
            return {"delta_s": 1.0, "Q": 0.0, "ok": True,
                    "reason": "Thiếu thông số Q — bỏ qua sway (δs=1.0)"}
        if Vus_kN == 0 or lc_mm == 0:
            return {"delta_s": 1.0, "Q": 0.0, "ok": True,
                    "reason": "Vus=0 hoặc lc=0 — bỏ qua sway"}
        Q = (sum_Pu_kN * delta_o_mm) / (Vus_kN * lc_mm)
    if Q < 0:
        Q = 0.0
    if Q >= 1.0:
        return {"delta_s": float("inf"), "Q": Q, "ok": False,
                "reason": "Q ≥ 1.0: khung không ổn định, cần phân tích bậc 2"}
    delta_s = 1.0 / (1.0 - Q)
    delta_s = max(delta_s, 1.0)
    return {"delta_s": delta_s, "Q": Q, "ok": True, "reason": ""}


# ---------------------------------------------------------------------------
# 3. Kiểm tra cắt theo ACI 22.5.5.1
# ---------------------------------------------------------------------------
_PSI_PER_MPA = 145.038
_IN2_PER_MM2 = 1.0 / 645.16
_LBF_PER_KN = 224.809


def aci_shear_check(Acv_mm2: float, Ag_mm2: float, fc_MPa: float, Nu_kN: float,
                    Vu_kN: float, Av_mm2: float, fyt_MPa: float, s_mm: float,
                    d_mm: float, lambda_: float = 1.0,
                    has_min_shear: bool = True,
                    rho_w: float = 0.015) -> dict:
    """Kiểm tra khả năng chịu cắt theo ACI 22.5.5.1.

    Acv_mm2: diện tích chịu cắt hiệu dụng (= b*d với tiết diện chữ nhật).
    Ag_mm2: diện tích nguyên của tiết diện.
    fc_MPa: f'c (MPa). Nu_kN: lực dọc tính toán (nén dương).
    Vu_kN: lực cắt tính toán (kN).
    Av_mm2: diện tích một bộ đai (2 nhánh), fyt_MPa: fy của đai,
        s_mm: khoảng cách đai, d_mm: chiều cao hữu hiệu.
    lambda_: hệ số bê tông nhẹ (1.0 bê tông thường).
    has_min_shear: True nếu có tối thiểu cốt đai (Av >= Av,min).
    rho_w: hàm lượng thép dọc chịu kéo As/(b*d) cho công thức Vc.

    Trả về dict {Vc_kN, Vs_kN, phi_Vn_kN, ok, Av_s_req, phi}.
    """
    fc_psi = fc_MPa * _PSI_PER_MPA
    Acv_in2 = Acv_mm2 * _IN2_PER_MM2
    Ag_in2 = Ag_mm2 * _IN2_PER_MM2
    Nu_lbf = Nu_kN * _LBF_PER_KN  # nén dương
    d_in = d_mm / 25.4

    # Số hạng Nu/(6*Ag) đổi ra psi, nén dương, chặn trên 0.05*f'c
    if Ag_in2 > 0:
        nu_term = Nu_lbf / (6.0 * Ag_in2)
    else:
        nu_term = 0.0
    nu_term = min(nu_term, 0.05 * fc_psi)

    sqrt_fc = math.sqrt(max(fc_psi, 0.0))
    # Hệ số kích thước (ACI 22.5.5.1.3)
    lambda_s = math.sqrt(2.0 / (1.0 + d_in / 10.0)) if d_in > 0 else 1.0
    lambda_s = min(lambda_s, 1.0)

    term_a = 2.0 * lambda_ * sqrt_fc + nu_term
    term_b = (8.0 * lambda_s * lambda_ * (max(rho_w, 0.0) ** (1.0 / 3.0))
              * sqrt_fc + nu_term)
    if has_min_shear:
        vc_lbf = max(term_a, term_b) * Acv_in2
    else:
        vc_lbf = term_b * Acv_in2

    # Giới hạn: 0 <= Vc <= 5*lambda*sqrt(f'c)*Acv
    vc_lbf = max(0.0, min(vc_lbf, 5.0 * lambda_ * sqrt_fc * Acv_in2))
    Vc_kN = vc_lbf / _LBF_PER_KN

    # Vs = Av*fyt*d/s
    if s_mm > 0 and Av_mm2 > 0:
        Vs_kN = Av_mm2 * fyt_MPa * d_mm / s_mm / 1000.0
    else:
        Vs_kN = 0.0

    # ACI 22.5.1.2: Vs ≤ 8·λs·λ·√f'c·bw·d
    if d_mm > 0 and Acv_mm2 > 0:
        bw_in = (Acv_mm2 / d_mm) / 25.4  # bw = Acv/d
        Vs_max_lbf = 8.0 * lambda_s * lambda_ * sqrt_fc * bw_in * d_in
        Vs_kN = min(Vs_kN, Vs_max_lbf / _LBF_PER_KN)

    phi = 0.75  # hệ số phi cho cắt (ACI 21.2.1)
    phi_Vn_kN = phi * (Vc_kN + Vs_kN)
    ok = phi_Vn_kN >= Vu_kN

    # Av/s yêu cầu (mm2/mm) nếu thiếu
    if Vu_kN > phi * Vc_kN and fyt_MPa > 0 and d_mm > 0:
        Vs_req_kN = Vu_kN / phi - Vc_kN
        Av_s_req = (Vs_req_kN * 1000.0) / (fyt_MPa * d_mm)
    else:
        Av_s_req = 0.0

    return {"Vc_kN": Vc_kN, "Vs_kN": Vs_kN, "phi_Vn_kN": phi_Vn_kN,
            "phi": phi, "ok": ok, "Av_s_req": Av_s_req,
            "lambda_s": lambda_s}


# ---------------------------------------------------------------------------
# 4. Kiểm tra cột tổng hợp theo ACI 318-19
# ---------------------------------------------------------------------------
def check_column_aci(sec: Section, conc: ACIConcrete, steel: ACISteel,
                     N_kN: float, M2_kNm: float, M3_kNm: float,
                     tied: bool = True, n_angles: int = 24) -> dict:
    """Kiểm tra khả năng chịu nén uốn xiên của cột theo ACI 318-19.

    sec: tiết diện (đã bố trí thép, hệ tọa độ x ngang / y đứng).
    N_kN: lực dọc tính toán (nén dương).
    M2_kNm, M3_kNm: mô men tính toán theo trục 2, 3 (ánh xạ Mx=M2, My=M3).
    tied: True = cột đai rời (phi_c=0.65), False = đai xoắn (0.75).

    Trả về dict {dc, fs, phi, ok, lambda_max, Bx, By, BN, Nn, Mn, eps_t}.
    """
    cap = ACICapacity(sec, conc, steel, tied=tied, n_angles=n_angles)
    # Ánh xạ: Mx = M2, My = M3 (cùng quy ước với interaction.py)
    r = cap.dc_ratio(N_kN, M2_kNm, M3_kNm)
    dc = r["dc"]
    fs = 1.0 / dc if dc > 1e-12 else float("inf")

    # Khả năng danh nghĩa tại điểm giới hạn B (để thuyết minh)
    phi_deg = math.degrees(math.atan2(r["Bx"], r["By"])) if (
        abs(r["Bx"]) > 1e-12 or abs(r["By"]) > 1e-12) else 0.0
    # Nội suy Nn, Mn danh nghĩa tại BN từ đường cong danh nghĩa
    nom = aci_interaction_curve(
        sec, conc, steel,
        min(cap.angles, key=lambda a: abs(a - phi_deg)),
        n_points=48, tied=tied)
    # Tính đúng: nội suy M danh nghĩa tại BN
    Mn_nom = _interp_on_curve([(p[0], p[1]) for p in nom], r["BN"], 1)
    # N danh nghĩa tại B: BN_thiết_kế / phi (gần đúng)
    phi_b = r["phi"] if r["phi"] > 1e-12 else 1.0
    Nn_b = r["BN"] / phi_b

    return {"dc": dc, "fs": fs, "phi": r["phi"], "ok": r["ok"],
            "lambda_max": r["lambda_max"],
            "Bx": r["Bx"], "By": r["By"], "BN": r["BN"],
            "Nn": Nn_b, "Mn": Mn_nom, "eps_t": r["eps_t"],
            "N_cap": cap.N_cap, "Po_nom": cap.Po_nom,
            "gamma_deg": r.get("gamma_deg"), "na_depth": r.get("na_depth")}

def aci_neutral_axis_at_N(sec, conc, steel, N_target_kN: float,
                          theta_deg: float, tied: bool = True,
                          n_points: int = 96):
    """Đường trung hòa từ mặt phẳng biến dạng EXACT tại (N_target, theta).

    Từ 2026-10-21: dùng mặt phẳng biên của nghiệm cân bằng song trục
    exact (gamma*, na*) tại mức N — trạng thái THIẾT KẾ (đã nhân phi,
    cắt N_cap) nhất quán với D/C exact mới.
    Quy ước góc kiểu ETABS: theta đo từ trục M3.

    Trả về dict giống neutral_axis_at_N của TCVN. Hệ trục yp được chọn
    trùng hướng gradient gamma (yp ≡ s = x·cosγ + y·sinγ, tức
    st = −cosγ, ct = sinγ) nên: yp_na = s_max − na, eps0 = eps_cu −
    kx_p·s_max, kx_p = eps_cu/na.
    """
    eng = _get_aci_exact(sec, conc, steel, tied)
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
        return {'found': True, 'yp_na': None, 'theta_deg': theta_deg,
                'ct': ct, 'st': st, 'y_top': s_max, 'y_bot': s_min,
                'eps0': conc.eps_cu, 'kx_p': 0.0,
                'gamma_deg': b["gamma_deg"], 'na_depth': na}
    kappa = conc.eps_cu / na
    return {'found': True, 'yp_na': s_max - na, 'theta_deg': theta_deg,
            'ct': ct, 'st': st, 'y_top': s_max, 'y_bot': s_min,
            'eps0': conc.eps_cu - kappa * s_max, 'kx_p': kappa,
            'gamma_deg': b["gamma_deg"], 'na_depth': na}
