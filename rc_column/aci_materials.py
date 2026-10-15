"""Vật liệu theo ACI 318-19.

Bao gồm:
- Bê tông: cường độ f'c (MPa), mô đun đàn hồi Ec = 4700*sqrt(f'c),
  biến dạng cực hạn eps_cu = 0.003, hệ số khối ứng suất beta1.
- Cốt thép: fy (MPa), Es = 200000 MPa.
- Hệ số giảm cường độ phi theo ACI 21.2.2 (Table 21.2.2):
  nén chủ đạo / vùng chuyển tiếp / kéo chủ đạo.
"""

import math
from dataclasses import dataclass
from typing import Dict


# ---------------------------------------------------------------------------
# Hệ số khối ứng suất chữ nhật tương đương - ACI 22.2.2.4.3
# ---------------------------------------------------------------------------
PSI_PER_MPA = 145.038  # 1 MPa = 145.038 psi


def beta1(fc_MPa: float) -> float:
    """Hệ số beta1 của khối ứng suất chữ nhật tương đương (ACI 22.2.2.4.3).

    beta1 = 0.85 - 0.05*(f'c_psi - 4000)/1000, giới hạn 0.65 <= beta1 <= 0.85.
    Chiều sâu khối ứng suất: a = beta1 * c.
    """
    fc_psi = fc_MPa * PSI_PER_MPA
    b1 = 0.85 - 0.05 * (fc_psi - 4000.0) / 1000.0
    return max(0.65, min(0.85, b1))


# ---------------------------------------------------------------------------
# Bê tông - ACI 318-19
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ACIConcrete:
    """Bê tông theo ACI 318-19.

    fc: cường độ chịu nén đặc trưng f'c (MPa).
    Khối ứng suất chữ nhật: 0.85*f'c (ACI 22.2.2.4.1),
    biến dạng cực hạn eps_cu = 0.003 (ACI 22.2.2.1).
    """
    fc: float

    @property
    def Ec(self) -> float:
        """Mô đun đàn hồi (MPa) - ACI 19.2.2.1: Ec = 4700*sqrt(f'c)."""
        return 4700.0 * math.sqrt(self.fc)

    @property
    def eps_cu(self) -> float:
        """Biến dạng cực hạn của bê tông chịu nén."""
        return 0.003

    @property
    def beta1(self) -> float:
        """Hệ số khối ứng suất chữ nhật tương đương."""
        return beta1(self.fc)

    @property
    def f_block(self) -> float:
        """Cường độ khối ứng suất chữ nhật: 0.85*f'c (MPa)."""
        return 0.85 * self.fc


# ---------------------------------------------------------------------------
# Cốt thép - ACI 318-19
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ACISteel:
    """Cốt thép theo ACI 318-19.

    fy: giới hạn chảy (MPa). Ứng suất = eps*Es, giới hạn ở fy
    (ACI 22.2.3.2). Es = 200000 MPa (~29000 ksi, ACI 20.2.2.2).
    """
    fy: float

    @property
    def Es(self) -> float:
        """Mô đun đàn hồi của thép (MPa)."""
        return 200000.0

    @property
    def eps_y(self) -> float:
        """Biến dạng chảy: eps_y = fy / Es."""
        return self.fy / self.Es

    def stress(self, strain: float) -> float:
        """Ứng suất thép theo mô hình đàn - dẻo lý tưởng (kéo dương)."""
        eps_y = self.eps_y
        if abs(strain) <= eps_y:
            return self.Es * strain
        return self.fy if strain > 0 else -self.fy


# ---------------------------------------------------------------------------
# Hệ số giảm cường độ phi - ACI 21.2.2, Table 21.2.2
# ---------------------------------------------------------------------------
PHI_TENSION = 0.90   # phi cho tiết diện kéo chủ đạo
PHI_TIED = 0.65      # phi nén chủ đạo, cột đai rời
PHI_SPIRAL = 0.75    # phi nén chủ đạo, cột đai xoắn


def phi_factor(eps_t: float, eps_y: float, tied: bool = True) -> float:
    """Hệ số giảm cường độ phi theo biến dạng thép chịu kéo ngoài cùng.

    eps_t: biến dạng kéo lớn nhất của thép (tại lúc bê tông đạt eps_cu).
    eps_y: biến dạng chảy của thép.
    tied: True = cột đai rời (phi_c = 0.65), False = đai xoắn (phi_c = 0.75).

    - eps_t <= eps_y: nén chủ đạo -> phi_c.
    - eps_t >= eps_y + 0.003: kéo chủ đạo -> 0.90.
    - Giữa: nội suy tuyến tính (ACI 21.2.2).
    """
    phi_c = PHI_TIED if tied else PHI_SPIRAL
    if eps_t <= eps_y:
        return phi_c
    if eps_t >= eps_y + 0.003:
        return PHI_TENSION
    return phi_c + (PHI_TENSION - phi_c) * (eps_t - eps_y) / 0.003


def max_axial_phi(tied: bool = True) -> float:
    """Hệ số giảm trừ cho lực nén đúng tâm lớn nhất (ACI 22.4.2.2).

    phi*Pn,max = (0.80 hoặc 0.85) * phi_c * Po, trong đó
    Po = 0.85*f'c*(Ag - Ast) + fy*Ast.
    Trả về 0.80 cho cột đai rời, 0.85 cho cột đai xoắn.
    """
    return 0.80 if tied else 0.85


# ---------------------------------------------------------------------------
# Cấp vật liệu thông dụng
# ---------------------------------------------------------------------------
ACI_CONCRETE_GRADES: Dict[str, float] = {
    "C20": 20.0,
    "C25": 25.0,
    "C30": 30.0,
    "C40": 40.0,
    "C50": 50.0,
}
"""Các cấp bê tông ACI thông dụng: tên -> f'c (MPa)."""

ACI_STEEL_GRADES: Dict[str, float] = {
    "Grade 420": 420.0,
    "Grade 550": 550.0,
}
"""Các cấp thép ACI thông dụng: tên -> fy (MPa)."""
