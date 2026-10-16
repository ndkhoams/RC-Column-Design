"""Vật liệu theo Eurocode 2 (EN 1992-1-1).

Bao gồm:
- Bê tông: các mác C16/20 .. C50/60 (fck = số đầu, MPa),
  fcd = αcc·fck/γc (αcc = 1.0, γc = 1.5),
  Ecm = 22000·(fcm/10)^0.3 (MPa), fcm = fck + 8,
  biến dạng cực hạn εcu2 = 0.0035 (fck ≤ 50 MPa).
- Khối ứng suất chữ nhật tương đương: η = 1.0, λ = 0.8
  (fck ≤ 50 MPa); cường độ η·fcd, chiều cao khối a = λ·x.
- Cốt thép: B400 / B500, fyd = fyk/γs (γs = 1.15), Es = 200000 MPa.

EC2 không dùng hệ số φ như ACI: hệ số riêng phần đã nằm trong
vật liệu (γc, γs) nên đường cong tương tác là đường cong thiết kế.
"""

import math
from dataclasses import dataclass
from typing import Dict


# Hệ số riêng phần vật liệu (EC2 2.4.2.4, tình huống bền vững/lâu dài)
GAMMA_C = 1.5    # bê tông
GAMMA_S = 1.15   # cốt thép
GAMMA_CE = 1.2   # cho Ecd = Ecm/γcE (độ cứng danh nghĩa)
ALPHA_CC = 1.0   # hệ số dài hạn cho nén


# ---------------------------------------------------------------------------
# Bê tông - EC2 (EN 1992-1-1, 3.1)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EC2Concrete:
    """Bê tông theo EC2.

    fck: cường độ nén đặc trưng mẫu trụ (MPa), = số đầu của mác
    (vd C30/37 -> fck = 30).
    """
    fck: float

    @property
    def fcd(self) -> float:
        """Cường độ nén tính toán: fcd = αcc·fck/γc (MPa)."""
        return ALPHA_CC * self.fck / GAMMA_C

    @property
    def fcm(self) -> float:
        """Cường độ nén trung bình: fcm = fck + 8 (MPa)."""
        return self.fck + 8.0

    @property
    def Ecm(self) -> float:
        """Mô đun đàn hồi cát tuyến: Ecm = 22000·(fcm/10)^0.3 (MPa)."""
        return 22000.0 * (self.fcm / 10.0) ** 0.3

    @property
    def Ecd(self) -> float:
        """Mô đun dùng cho độ cứng danh nghĩa: Ecd = Ecm/γcE."""
        return self.Ecm / GAMMA_CE

    @property
    def eps_cu(self) -> float:
        """Biến dạng cực hạn khi uốn: εcu2 = 0.0035 (fck ≤ 50 MPa)."""
        return 0.0035

    @property
    def lam(self) -> float:
        """Hệ số chiều cao khối ứng suất: λ = 0.8 (fck ≤ 50 MPa)."""
        return 0.8

    @property
    def eta(self) -> float:
        """Hệ số cường độ khối ứng suất: η = 1.0 (fck ≤ 50 MPa)."""
        return 1.0

    @property
    def f_block(self) -> float:
        """Cường độ khối ứng suất chữ nhật: η·fcd (MPa)."""
        return self.eta * self.fcd


# ---------------------------------------------------------------------------
# Cốt thép - EC2 (EN 1992-1-1, 3.2)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EC2Steel:
    """Cốt thép theo EC2.

    fyk: giới hạn chảy đặc trưng (MPa). Ứng suất = ε·Es, giới hạn
    ở ±fyd (mô hình đàn-dẻo lý tưởng, EC2 3.2.7).
    """
    fyk: float

    @property
    def fyd(self) -> float:
        """Cường độ tính toán: fyd = fyk/γs (MPa)."""
        return self.fyk / GAMMA_S

    @property
    def Es(self) -> float:
        """Mô đun đàn hồi của thép (MPa)."""
        return 200000.0

    @property
    def eps_yd(self) -> float:
        """Biến dạng chảy tính toán: εyd = fyd/Es."""
        return self.fyd / self.Es


# ---------------------------------------------------------------------------
# Cấp vật liệu thông dụng
# ---------------------------------------------------------------------------
EC2_CONCRETE_GRADES: Dict[str, float] = {
    "C16/20": 16.0,
    "C20/25": 20.0,
    "C25/30": 25.0,
    "C30/37": 30.0,
    "C35/45": 35.0,
    "C40/50": 40.0,
    "C45/55": 45.0,
    "C50/60": 50.0,
}
"""Các mác bê tông EC2 thông dụng: tên -> fck (MPa)."""

EC2_STEEL_GRADES: Dict[str, float] = {
    "B400": 400.0,
    "B500": 500.0,
}
"""Các cấp thép EC2 thông dụng: tên -> fyk (MPa)."""
