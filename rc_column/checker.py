"""Điều phối kiểm tra cột BTCT: vật liệu -> tiết diện -> ổn định -> NDM -> kết quả."""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .materials import (CONCRETE_GRADES, STEEL_GRADES, ConcreteMaterial,
                        SteelMaterial)
from .sections import (Section, bar_area, clear_spacing, layout_circle_bars,
                       layout_custom_bars, layout_rect_bars,
                       layout_vietconsoft_bars,
                       make_circle_section, make_rect_section)
from .interaction import BiaxialCapacity
from .stability import (LongTermLoads, buckling_factors, eccentricities,
                        effective_length, phi_L, slenderness)


@dataclass
class ColumnInput:
    # Vật liệu
    concrete_grade: str = "B25"
    gamma_b: float = 1.0
    steel_grade: str = "CB400-V"      # thép dọc
    sw_steel_grade: str = "CB400-V"  # thép đai
    gamma_s: float = 1.0
    concrete_model: str = "3line"  # "3line" | "2line"
    # Tiết diện
    section_type: str = "rect"     # "rect" | "circle" | "poly"
    poly_section = None  # Section(kind="poly") khi import từ DXF
    cx: float = 400.0              # mm (rect: cạnh x; circle: đường kính)
    cy: float = 400.0              # mm
    # Cốt thép
    rebar_mode: str = "auto"       # "auto" | "custom"
    bar_dia: float = 20.0          # (giữ để tương thích: dùng cho tiết diện tròn)
    n_bars: int = 8                # cho tròn / auto
    nx: int = 3                    # (giữ để tương thích)
    ny: int = 3
    cover: float = 30.0            # lớp bê tông bảo vệ cốt dọc c (mm)
    custom_bars: List[Tuple[float, float, float]] = field(default_factory=list)
    # Bố trí thép kiểu VietconSoft (chữ nhật, rebar_mode="auto")
    # cx = t3 (ngang), cy = t2 (đứng); thép cạnh t2 nằm 2 mặt trái/phải,
    # thép cạnh t3 nằm 2 mặt trên/dưới (số thanh mỗi mặt, không tính góc)
    corner_dia: float = 20.0       # đường kính 4 thanh thép góc
    edge_t2_count: int = 3
    edge_t2_dia: float = 20.0
    edge_t3_count: int = 3
    edge_t3_dia: float = 20.0
    two_layer: bool = False
    layer2_mode: str = "perimeter"  # "perimeter" | "concentrated" | "bundled"
    # perimeter: đường kính lớp 2 (số thanh tự match lớp 1)
    l2_t2_dia: float = 20.0
    l2_t3_dia: float = 20.0
    # concentrated
    l2_s_layer: float = 30.0       # khe hở giữa 2 lớp (mm)
    l2_side: str = "t2"            # "t2" | "t3": cặp mặt đặt thép lớp 2
    l2_count: int = 5              # số thanh mỗi mặt
    l2_dia: float = 25.0
    # bundled (ghép bó / đôi)
    bundle_pos: str = "inner"      # "inner" (lớp trong) | "outer" (cùng lớp ngoài)
    bundle_size: int = 2           # số thanh mỗi bó tại cạnh
    bundle_corner: int = 2         # số thanh mỗi bó tại góc
    bundle_gap: float = 0.0        # khe hở giữa các thanh trong bó (mm)
    # Ổn định
    Lx: float = 4.0                # m
    Ly: float = 4.0
    top_x: str = "ngam_nua_cung"; bottom_x: str = "ngam_nua_cung"
    top_y: str = "ngam_nua_cung"; bottom_y: str = "ngam_nua_cung"
    psi_x: Optional[float] = None
    psi_y: Optional[float] = None
    # Nội lực
    N: float = 1000.0              # kN (nén dương)
    Mx: float = 50.0               # kN·m
    My: float = 50.0               # kN·m
    Q2: float = 0.0                # kN (lực cắt theo phương 2)
    Q3: float = 0.0                # kN (lực cắt theo phương 3)
    long_term: LongTermLoads = field(default_factory=LongTermLoads)
    # Cốt thép đai (TCVN 5574:2018 10.3.4)
    sw_dia: float = 8.0            # đường kính đai bao (mm)
    sw_spacing: float = 200.0      # bước đai bao (mm)
    sw_legs: int = 2               # số nhánh đai bao
    swm2_dia: float = 8.0          # đường kính đai giữa t2 (mm)
    swm2_spacing: float = 200.0    # bước đai giữa t2 (mm)
    swm2_legs: int = 0             # số nhánh đai giữa t2
    swm3_dia: float = 8.0          # đường kính đai giữa t3 (mm)
    swm3_spacing: float = 200.0    # bước đai giữa t3 (mm)
    swm3_legs: int = 0             # số nhánh đai giữa t3


@dataclass
class CheckResult:
    ok: bool
    utilization: float       # = D/C
    dc: float                # tỷ số D/C theo tia 3D
    fs: float                # hệ số an toàn = 1/(D/C)
    N: float; Mx: float; My: float
    Mx_star: float; My_star: float   # mô men đã phóng đại uốn dọc
    M_resultant: float
    M_capacity: float
    # điểm B trên mặt tương tác
    Bx: float; By: float; BN: float
    lambda_max: float
    phi_L: float
    L0x: float; L0y: float
    lambda_x: float; lambda_y: float
    # hình học
    Ix: float; Iy: float      # mm⁴
    ix: float; iy: float      # mm
    Isx: float; Isy: float    # mm⁴ (cốt thép)
    # độ lệch tâm (mm)
    e1x: float; e1y: float; eax: float; eay: float; e0x: float; e0y: float
    # uốn dọc
    delta_ex: float; delta_ey: float
    kbx: float; kby: float
    Dx: float; Dy: float
    Ncrx: float; Ncry: float
    etax: float; etay: float
    steel_area: float
    reinforcement_ratio: float
    clear_cx: float; clear_cy: float
    alpha_e: float            # Es/Eb
    details: List[str] = field(default_factory=list)
    # Mặt phẳng biến dạng tại điểm biên B của D/C exact (2026-10-21):
    # hướng gradient gamma* (độ) + chiều sâu trục trung hòa na* (mm)
    gamma_deg: float = 0.0
    na_depth: float = 0.0


def build_section(inp: ColumnInput) -> Section:
    conc = ConcreteMaterial(CONCRETE_GRADES[inp.concrete_grade], inp.gamma_b)
    steel = SteelMaterial(STEEL_GRADES[inp.steel_grade], inp.gamma_s)
    if inp.section_type == "poly":
        if getattr(inp, "poly_section", None) is None:
            raise ValueError(
                "Chưa import tiết diện DXF. Bấm '📐 Import (.dxf)' ở mục 2.")
        sec = inp.poly_section
        sec.concrete = conc
        sec.steel = steel
        return sec
    if inp.section_type == "rect":
        sec = make_rect_section(inp.cx, inp.cy, conc, steel)
        if inp.rebar_mode == "custom" and inp.custom_bars:
            layout_custom_bars(sec, inp.custom_bars)
        else:
            # rebar_mode="auto": bố trí kiểu VietconSoft
            # (4 thép góc + thép cạnh t2/t3, hỗ trợ 2 lớp)
            layout_vietconsoft_bars(sec, inp)
    else:
        sec = make_circle_section(inp.cx, conc, steel)
        if inp.rebar_mode == "custom" and inp.custom_bars:
            layout_custom_bars(sec, inp.custom_bars)
        else:
            layout_circle_bars(sec, inp.bar_dia, inp.n_bars, inp.cover)
    return sec


def section_inertia(sec: Section):
    """Ix, Iy (mm4), ix, iy (mm), Isx, Isy cua cot thep (mm4)."""
    if sec.kind == "rect":
        b, h = sec.cx, sec.cy
        Ix = b * h ** 3 / 12.0
        Iy = h * b ** 3 / 12.0
    elif sec.kind == "poly" and sec.poly_verts:
        from .dxf_import import polygon_gross_props
        _, Ix, Iy = polygon_gross_props(sec.poly_verts, sec.poly_holes)
    else:
        r = sec.cx / 2.0
        Ix = Iy = math.pi * r ** 4 / 4.0
    A = sec.gross_area
    ix = math.sqrt(Ix / A) if A > 0 else 0.0
    iy = math.sqrt(Iy / A) if A > 0 else 0.0
    Isx = sum(r.area * r.y ** 2 for r in sec.rebars)
    Isy = sum(r.area * r.x ** 2 for r in sec.rebars)
    return Ix, Iy, ix, iy, Isx, Isy


def check_column(inp: ColumnInput, n_angles: int = 24) -> CheckResult:
    details: List[str] = []
    sec = build_section(inp)
    conc = sec.concrete
    steel = sec.steel

    # --- Hình học ---
    Ix, Iy, ix, iy, Isx, Isy = section_inertia(sec)
    alpha_e = steel.Es / conc.Eb

    # --- Chiều dài tính toán & độ mảnh ---
    L0x = effective_length(inp.Lx, inp.top_x, inp.bottom_x, inp.psi_x)
    L0y = effective_length(inp.Ly, inp.top_y, inp.bottom_y, inp.psi_y)
    lam_x = (L0x * 1000.0) / ix if ix > 0 else float("inf")
    lam_y = (L0y * 1000.0) / iy if iy > 0 else float("inf")

    # --- Độ lệch tâm ---
    ecc = eccentricities(inp.N, inp.Mx, inp.My, inp.Lx, inp.Ly, inp.cx, inp.cy)

    # --- φL ---
    phi = phi_L(inp.N, inp.Mx, inp.My, inp.long_term)

    # --- Uốn dọc ---
    buck = buckling_factors(ecc.e0x, ecc.e0y, inp.cx, inp.cy, phi,
                            conc.Eb, Ix, Iy, Isx, Isy, L0x, L0y,
                            inp.N, inp.Mx, inp.My)

    # --- NDM: D/C theo tia 3D với mô men đã phóng đại ---
    cap = BiaxialCapacity(sec, model=inp.concrete_model, n_angles=n_angles)
    r = cap.dc_ratio(inp.N, buck.Mx_star, buck.My_star)
    dc = r["dc"]
    fs_val = 1.0 / dc if dc > 1e-12 else float("inf")

    Mres = math.hypot(buck.Mx_star, buck.My_star)
    Mcap_pt = cap.moment_capacity(inp.N,
                                  math.degrees(math.atan2(buck.Mx_star,
                                                          buck.My_star))
                                  if Mres > 1e-12 else 0.0)

    mu = sec.reinforcement_ratio
    ccx, ccy = clear_spacing(sec)

    details.append(f"D/C = {dc:.3f} (FS = {fs_val:.2f})")

    return CheckResult(
        ok=r["ok"], utilization=dc, dc=dc, fs=fs_val,
        N=inp.N, Mx=inp.Mx, My=inp.My,
        Mx_star=buck.Mx_star, My_star=buck.My_star,
        M_resultant=Mres, M_capacity=Mcap_pt,
        Bx=r["Bx"], By=r["By"], BN=r["BN"], lambda_max=r["lambda_max"],
        phi_L=phi, L0x=L0x, L0y=L0y, lambda_x=lam_x, lambda_y=lam_y,
        Ix=Ix, Iy=Iy, ix=ix, iy=iy, Isx=Isx, Isy=Isy,
        e1x=ecc.e1x, e1y=ecc.e1y, eax=ecc.eax, eay=ecc.eay,
        e0x=ecc.e0x, e0y=ecc.e0y,
        delta_ex=buck.delta_ex, delta_ey=buck.delta_ey,
        kbx=buck.kbx, kby=buck.kby, Dx=buck.Dx, Dy=buck.Dy,
        Ncrx=buck.Ncrx, Ncry=buck.Ncry, etax=buck.etax, etay=buck.etay,
        steel_area=sec.steel_area, reinforcement_ratio=mu,
        clear_cx=ccx, clear_cy=ccy, alpha_e=alpha_e, details=details,
        gamma_deg=r.get("gamma_deg") or 0.0,
        na_depth=r.get("na_depth") or 0.0,
    )


class BatchChecker:
    """Kiểm tra hàng loạt tổ hợp: dựng BiaxialCapacity 1 lần rồi tái sử dụng.

    Dùng cho import ETABS: mỗi tổ hợp chỉ tính uốn dọc (rẻ) + D/C tia (nội suy).
    """

    def __init__(self, inp: ColumnInput, n_angles: int = 12):
        self.inp = inp
        self.sec = build_section(inp)
        self.cap = BiaxialCapacity(self.sec, model=inp.concrete_model,
                                   n_angles=n_angles)
        conc = self.sec.concrete
        self.Ix, self.Iy, self.ix, self.iy, self.Isx, self.Isy = \
            section_inertia(self.sec)
        self.L0x = effective_length(inp.Lx, inp.top_x, inp.bottom_x, inp.psi_x)
        self.L0y = effective_length(inp.Ly, inp.top_y, inp.bottom_y, inp.psi_y)
        self._Eb = conc.Eb

    def _buckling(self, N: float, Mx: float, My: float, lt):
        """Uốn dọc cho 1 tổ hợp: phi_L + độ lệch tâm + hệ số uốn dọc.
        Dùng chung cho check_one và check_many (cùng biểu thức, cùng
        thứ tự như bản check_one gốc)."""
        phi = phi_L(N, Mx, My, lt)
        ecc = eccentricities(N, Mx, My, self.inp.Lx, self.inp.Ly,
                             self.inp.cx, self.inp.cy)
        return buckling_factors(ecc.e0x, ecc.e0y, self.inp.cx, self.inp.cy,
                                phi, self._Eb, self.Ix, self.Iy,
                                self.Isx, self.Isy, self.L0x, self.L0y,
                                N, Mx, My)

    def check_one(self, N: float, Mx: float, My: float,
                  lt: "LongTermLoads" = None) -> dict:
        """Kiểm tra 1 tổ hợp. Trả về dict {dc, fs, ok, Mx_star, ...}."""
        from .stability import LongTermLoads as _LT
        lt = lt or _LT()
        buck = self._buckling(N, Mx, My, lt)
        r = self.cap.dc_ratio(N, buck.Mx_star, buck.My_star)
        dc = r["dc"]
        return {
            "N": N, "Mx": Mx, "My": My,
            "Mx_star": buck.Mx_star, "My_star": buck.My_star,
            "etax": buck.etax, "etay": buck.etay,
            "dc": dc,
            "fs": 1.0 / dc if dc > 1e-12 else float("inf"),
            "ok": r["ok"],
            "Bx": r["Bx"], "By": r["By"], "BN": r["BN"],
            "lambda_max": r["lambda_max"],
        }

    def check_many(self, items, pump=None) -> list:
        """Kiểm tra cả khối tổ hợp: items = list (N, Mx, My, lt).

        Trả list dict giống hệt check_one từng tổ hợp (khớp từng bit):
        phần uốn dọc tính từng dòng như check_one, riêng D/C tia tính
        theo khối bằng dc_ratio_batch. pump(n) được gọi sau mỗi lô
        256 dòng (bơm tiến trình UI) nếu được truyền.
        """
        from .stability import LongTermLoads as _LT
        out: list = [None] * len(items)
        CH = 256
        for s in range(0, len(items), CH):
            part = items[s:s + CH]
            stars = []
            bucks = []
            for (N, Mx, My, lt) in part:
                buck = self._buckling(N, Mx, My, lt or _LT())
                bucks.append(buck)
                stars.append((N, buck.Mx_star, buck.My_star))
            try:
                rs = self.cap.dc_ratio_batch(stars)
            except Exception:
                rs = [self.cap.dc_ratio(N, Mx_star, My_star)
                      for (N, Mx_star, My_star) in stars]
            for k, ((N, Mx, My, lt), buck, r) in enumerate(
                    zip(part, bucks, rs)):
                dc = r["dc"]
                out[s + k] = {
                    "N": N, "Mx": Mx, "My": My,
                    "Mx_star": buck.Mx_star, "My_star": buck.My_star,
                    "etax": buck.etax, "etay": buck.etay,
                    "dc": dc,
                    "fs": 1.0 / dc if dc > 1e-12 else float("inf"),
                    "ok": r["ok"],
                    "Bx": r["Bx"], "By": r["By"], "BN": r["BN"],
                    "lambda_max": r["lambda_max"],
                }
            if pump is not None:
                pump(len(part))
        return out
