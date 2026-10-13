"""Vật liệu theo TCVN 5574:2018.

Bao gồm:
- Bê tông: cấp độ bền B15..B60, cường độ tính toán Rb, Rbt, mô đun Eb,
  biến dạng giới hạn, và các mô hình phi tuyến (2 đoạn thẳng / 3 đoạn thẳng).
- Cốt thép: CB240-T, CB300-V, CB400-V, CB500-V với Rs, Rsc, Es.
"""

from dataclasses import dataclass
from typing import Dict


# ---------------------------------------------------------------------------
# Bê tông - TCVN 5574:2018, Bảng 6 (cường độ tính toán, MPa)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ConcreteGrade:
    name: str
    Rb: float    # cường độ chịu nén tính toán (MPa)
    Rbt: float   # cường độ chịu kéo tính toán (MPa)
    Eb: float    # mô đun đàn hồi (MPa)


CONCRETE_GRADES: Dict[str, ConcreteGrade] = {
    "B15": ConcreteGrade("B15", Rb=8.5,  Rbt=0.75, Eb=24000),
    "B20": ConcreteGrade("B20", Rb=11.5, Rbt=0.90, Eb=27500),
    "B25": ConcreteGrade("B25", Rb=14.5, Rbt=1.05, Eb=30000),
    "B30": ConcreteGrade("B30", Rb=17.0, Rbt=1.20, Eb=32500),
    "B35": ConcreteGrade("B35", Rb=19.5, Rbt=1.30, Eb=34500),
    "B40": ConcreteGrade("B40", Rb=22.0, Rbt=1.40, Eb=36000),
    "B45": ConcreteGrade("B45", Rb=25.0, Rbt=1.45, Eb=37000),
    "B50": ConcreteGrade("B50", Rb=27.5, Rbt=1.55, Eb=38000),
    "B55": ConcreteGrade("B55", Rb=30.0, Rbt=1.60, Eb=39000),
    "B60": ConcreteGrade("B60", Rb=33.0, Rbt=1.65, Eb=40000),
}


# ---------------------------------------------------------------------------
# Cốt thép - TCVN 5574:2018, Bảng 10 (cường độ tính toán, MPa)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SteelGrade:
    name: str
    Rs: float    # cường độ chịu kéo tính toán
    Rsc: float   # cường độ chịu nén tính toán
    Rsw: float   # cường độ tính toán cốt thép ngang (đai)
    Es: float    # mô đun đàn hồi


STEEL_GRADES: Dict[str, SteelGrade] = {
    "CB240-T": SteelGrade("CB240-T", Rs=210.0, Rsc=210.0, Rsw=170.0, Es=2.1e5),
    "CB300-V": SteelGrade("CB300-V", Rs=260.0, Rsc=260.0, Rsw=215.0, Es=2.1e5),
    "CB400-V": SteelGrade("CB400-V", Rs=350.0, Rsc=350.0, Rsw=280.0, Es=2.1e5),
    "CB500-V": SteelGrade("CB500-V", Rs=435.0, Rsc=400.0, Rsw=300.0, Es=2.1e5),
}


# Biến dạng giới hạn (tác dụng ngắn hạn), TCVN 5574:2018
EPS_B1 = 0.002    # biến dạng tại đỉnh (bê tông <= B60)
EPS_B2 = 0.0035   # biến dạng cực hạn bê tông (<= B60)
EPS_S2 = 0.025    # biến dạng cực hạn cốt thép


@dataclass
class ConcreteMaterial:
    """Bê tông với hệ số điều kiện làm việc gamma_b."""
    grade: ConcreteGrade
    gamma_b: float = 1.0

    @property
    def Rb(self) -> float:
        return self.grade.Rb * self.gamma_b

    @property
    def Rbt(self) -> float:
        return self.grade.Rbt * self.gamma_b

    @property
    def Eb(self) -> float:
        return self.grade.Eb

    def stress(self, strain: float, model: str = "3line") -> float:
        """Ứng suất nén bê tông theo biến dạng (nén dương).

        model = "3line": parabol - chữ nhật (MH3ĐT)
        model = "2line": hai đoạn thẳng (MH2ĐT)
        Kéo: bỏ qua (trả về 0).
        """
        if strain <= 0:
            return 0.0  # bỏ qua chịu kéo
        Rb = self.Rb
        if model == "3line":
            if strain <= EPS_B1:
                eta = strain / EPS_B1
                return Rb * (2.0 * eta - eta * eta)
            elif strain <= EPS_B2:
                return Rb
            return 0.0
        else:  # 2line
            eps_b0 = Rb / self.Eb
            if strain <= eps_b0:
                return self.Eb * strain
            elif strain <= EPS_B2:
                return Rb
            return 0.0


@dataclass
class SteelMaterial:
    """Cốt thép với hệ số điều kiện làm việc gamma_s."""
    grade: SteelGrade
    gamma_s: float = 1.0

    @property
    def Rs(self) -> float:
        return self.grade.Rs * self.gamma_s

    @property
    def Rsw(self) -> float:
        return self.grade.Rsw * self.gamma_s

    @property
    def Rsc(self) -> float:
        return self.grade.Rsc * self.gamma_s

    @property
    def Es(self) -> float:
        return self.grade.Es

    def stress(self, strain: float) -> float:
        """Ứng suất thép theo mô hình đàn - dẻo lý tưởng (kéo dương)."""
        eps_y = self.Rs / self.Es
        if abs(strain) <= eps_y:
            return self.Es * strain
        if abs(strain) <= EPS_S2:
            limit = self.Rs if strain > 0 else self.Rsc
            return limit if strain > 0 else -limit
        return 0.0  # quá biến dạng giới hạn
