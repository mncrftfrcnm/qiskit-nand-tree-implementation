from dataclasses import dataclass
from math import acos, sin
from typing import Iterable

from .tree import NandTree


@dataclass(frozen=True)
class ScatteringResult:
    energy: float
    root_value: int
    branch_ratio: complex
    transmission_amplitude: complex
    transmission_probability: float


def _leaf_ratio(bit: int, energy: complex) -> complex:
    if bit == 0:
        return -1 / energy
    return -1 / (energy - 1 / energy)


def branch_ratio(leaves: Iterable[int], energy: complex) -> complex:
    tree = NandTree(leaves)
    if energy == 0:
        raise ValueError("use a small non-zero energy")

    level = [_leaf_ratio(bit, energy) for bit in tree.leaves]
    while len(level) > 1:
        level = [
            -1 / (energy + level[index] + level[index + 1])
            for index in range(0, len(level), 2)
        ]
    return level[0]


def analyze_scattering(
    leaves: Iterable[int],
    *,
    energy: float = 1e-6,
) -> ScatteringResult:
    if not -2 < energy < 2:
        raise ValueError("energy must lie strictly between -2 and 2")
    tree = NandTree(leaves)
    theta = acos(-energy / 2)
    ratio = branch_ratio(tree.leaves, complex(energy))
    amplitude = 2j * sin(theta) / (2j * sin(theta) + ratio)
    return ScatteringResult(
        energy=energy,
        root_value=tree.root_value,
        branch_ratio=ratio,
        transmission_amplitude=amplitude,
        transmission_probability=float(abs(amplitude) ** 2),
    )
