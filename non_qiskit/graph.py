from collections.abc import Iterable, Iterator
from dataclasses import dataclass

import numpy as np

from .tree import NandTree


@dataclass(frozen=True)
class Vertex:
    kind: str
    index: int

    @property
    def label(self) -> str:
        prefix = {"runway": "r", "tree": "t", "oracle": "o"}[self.kind]
        return f"{prefix}{self.index}"


@dataclass(frozen=True)
class NandWalkGraph:
    tree: NandTree
    runway_half_length: int
    vertices: tuple[Vertex, ...]
    adjacency: np.ndarray
    driver_adjacency: np.ndarray
    oracle_adjacency: np.ndarray
    lookup: dict[tuple[str, int], int]

    @property
    def size(self) -> int:
        return len(self.vertices)

    @property
    def hamiltonian(self) -> np.ndarray:
        return -self.adjacency.copy()

    @property
    def driver_hamiltonian(self) -> np.ndarray:
        return -self.driver_adjacency.copy()

    @property
    def oracle_hamiltonian(self) -> np.ndarray:
        return -self.oracle_adjacency.copy()

    def vertex_index(self, kind: str, index: int) -> int:
        return self.lookup[(kind, index)]

    def runway_index(self, position: int) -> int:
        return self.vertex_index("runway", position)

    def edges(self) -> Iterator[tuple[int, int]]:
        rows, cols = np.nonzero(np.triu(self.adjacency, k=1))
        yield from zip(rows.tolist(), cols.tolist(), strict=True)

    def summary(self) -> dict[str, int]:
        return {
            "leaves": self.tree.leaf_count,
            "root_value": self.tree.root_value,
            "vertices": self.size,
            "edges": sum(1 for _ in self.edges()),
            "oracle_edges": int(np.count_nonzero(np.triu(self.oracle_adjacency, 1))),
        }


def build_walk_graph(
    leaves: Iterable[int],
    *,
    runway_half_length: int = 8,
) -> NandWalkGraph:
    tree = NandTree(leaves)
    if runway_half_length < 1:
        raise ValueError("runway_half_length must be at least 1")

    vertices: list[Vertex] = []
    vertices.extend(
        Vertex("runway", position)
        for position in range(-runway_half_length, runway_half_length + 1)
    )
    vertices.extend(Vertex("tree", node) for node in range(tree.node_count))
    vertices.extend(Vertex("oracle", leaf) for leaf in range(tree.leaf_count))
    lookup = {(vertex.kind, vertex.index): index for index, vertex in enumerate(vertices)}

    size = len(vertices)
    driver = np.zeros((size, size), dtype=float)
    oracle = np.zeros((size, size), dtype=float)

    def connect(matrix: np.ndarray, left: tuple[str, int], right: tuple[str, int]) -> None:
        i, j = lookup[left], lookup[right]
        matrix[i, j] = matrix[j, i] = 1.0

    for position in range(-runway_half_length, runway_half_length):
        connect(driver, ("runway", position), ("runway", position + 1))
    connect(driver, ("runway", 0), ("tree", 0))

    for node in range(tree.internal_count):
        left, right = tree.children(node)
        connect(driver, ("tree", node), ("tree", left))
        connect(driver, ("tree", node), ("tree", right))

    for leaf, bit in enumerate(tree.leaves):
        if bit:
            connect(oracle, ("tree", tree.leaf_node(leaf)), ("oracle", leaf))

    return NandWalkGraph(
        tree=tree,
        runway_half_length=runway_half_length,
        vertices=tuple(vertices),
        adjacency=driver + oracle,
        driver_adjacency=driver,
        oracle_adjacency=oracle,
        lookup=lookup,
    )
