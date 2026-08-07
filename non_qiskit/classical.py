from dataclasses import dataclass
from typing import Sequence

from .tree import NandTree


@dataclass(frozen=True)
class ClassicalResult:
    value: int
    leaf_queries: int
    queried_leaves: tuple[int, ...]


class CountingOracle:
    def __init__(self, leaves: Sequence[int]):
        self._leaves = tuple(leaves)
        self._queries: list[int] = []

    def query(self, index: int) -> int:
        self._queries.append(index)
        return self._leaves[index]

    @property
    def queried(self):
        return tuple(self._queries)


def evaluate_bottom_up(leaves: Sequence[int]) -> ClassicalResult:
    tree = NandTree(leaves)
    return ClassicalResult(tree.root_value, tree.leaf_count, tuple(range(tree.leaf_count)))


def evaluate_short_circuit(
    leaves: Sequence[int],
    *,
    visit_right_first: bool = False,
) -> ClassicalResult:
    """Classical query baseline with deterministic short-circuiting."""

    tree = NandTree(leaves)
    oracle = CountingOracle(tree.leaves)

    def evaluate(node: int) -> int:
        if node >= tree.leaf_start:
            return oracle.query(node - tree.leaf_start)

        left, right = tree.children(node)
        first, second = (right, left) if visit_right_first else (left, right)
        if evaluate(first) == 0:
            return 1
        return 1 - evaluate(second)

    value = evaluate(0)
    return ClassicalResult(value, len(oracle.queried), oracle.queried)
