from dataclasses import dataclass
from math import log2
from typing import Iterable, Iterator


def is_power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


@dataclass(frozen=True)
class NandTree:
    """Complete balanced NAND tree stored in heap order."""

    leaves: tuple[int, ...]

    def __init__(self, leaves: Iterable[int]):
        values = tuple(int(bit) for bit in leaves)
        if not is_power_of_two(len(values)):
            raise ValueError("the number of leaves must be a non-zero power of two")
        if any(bit not in (0, 1) for bit in values):
            raise ValueError("leaves must contain only 0 and 1")
        object.__setattr__(self, "leaves", values)

    @property
    def leaf_count(self) -> int:
        return len(self.leaves)

    @property
    def depth(self) -> int:
        return int(log2(self.leaf_count))

    @property
    def node_count(self) -> int:
        return 2 * self.leaf_count - 1

    @property
    def leaf_start(self) -> int:
        return self.leaf_count - 1

    @property
    def internal_count(self) -> int:
        return self.leaf_count - 1

    def children(self, node: int):
        if not 0 <= node < self.internal_count:
            raise ValueError(f"node {node} is not an internal node")
        return 2 * node + 1, 2 * node + 2

    def leaf_node(self, leaf_index: int) -> int:
        if not 0 <= leaf_index < self.leaf_count:
            raise IndexError(leaf_index)
        return self.leaf_start + leaf_index

    def values(self):
        nodes = [0] * self.node_count
        nodes[self.leaf_start :] = self.leaves
        for node in range(self.internal_count - 1, -1, -1):
            left, right = self.children(node)
            nodes[node] = 1 - (nodes[left] & nodes[right])
        return tuple(nodes)

    @property
    def root_value(self) -> int:
        return self.values()[0]

    def levels(self) -> Iterator[tuple[int, ...]]:
        values = self.values()
        start = 0
        width = 1
        for _ in range(self.depth + 1):
            yield values[start : start + width]
            start += width
            width *= 2

    def ascii(self) -> str:
        rows: list[str] = []
        for level, values in enumerate(self.levels()):
            rows.append(f"level {level}: " + "  ".join(str(value) for value in values))
        return "\n".join(rows)
