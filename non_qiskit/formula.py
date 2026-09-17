from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Input:
    """Reference to one Boolean input in a NAND formula."""

    index: int

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("input index must be non-negative")


@dataclass(frozen=True)
class Nand:
    """Binary NAND node. Children may have different depths."""

    left: Formula
    right: Formula


Formula = Input | Nand


def input_(index: int) -> Input:
    """Small constructor that reads naturally when formulas are built inline."""

    return Input(index)


def nand(left: Formula, right: Formula) -> Nand:
    return Nand(left, right)


def evaluate_formula(formula: Formula, values: Mapping[int, int] | tuple[int, ...]) -> int:
    """Evaluate a NAND formula against concrete input values."""

    if isinstance(formula, Input):
        try:
            value = values[formula.index]
        except (IndexError, KeyError) as exc:
            raise ValueError(f"missing value for input x{formula.index}") from exc
        if value not in (0, 1):
            raise ValueError("input values must contain only 0 and 1")
        return int(value)

    left = evaluate_formula(formula.left, values)
    right = evaluate_formula(formula.right, values)
    return 1 - (left & right)


def formula_depth(formula: Formula) -> int:
    if isinstance(formula, Input):
        return 0
    return 1 + max(formula_depth(formula.left), formula_depth(formula.right))


def formula_size(formula: Formula) -> int:
    if isinstance(formula, Input):
        return 1
    return 1 + formula_size(formula.left) + formula_size(formula.right)


def input_occurrences(formula: Formula) -> tuple[int, ...]:
    """Return input indices from left to right, preserving repeated variables."""

    if isinstance(formula, Input):
        return (formula.index,)
    return input_occurrences(formula.left) + input_occurrences(formula.right)


def input_indices(formula: Formula) -> tuple[int, ...]:
    return tuple(sorted(set(input_occurrences(formula))))


def format_formula(formula: Formula) -> str:
    if isinstance(formula, Input):
        return f"x{formula.index}"
    return f"NAND({format_formula(formula.left)}, {format_formula(formula.right)})"
