from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Literal, TypeAlias

import numpy as np
from scipy.sparse import csr_matrix, issparse, lil_matrix, triu

from .tree import NandTree

MatrixFormat = Literal["sparse", "dense"]
GraphMatrix: TypeAlias = np.ndarray | csr_matrix


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
    adjacency: GraphMatrix
    driver_adjacency: GraphMatrix
    oracle_adjacency: GraphMatrix
    lookup: dict[tuple[str, int], int]
    matrix_format: MatrixFormat

    @property
    def size(self) -> int:
        return len(self.vertices)

    @property
    def hamiltonian(self) -> GraphMatrix:
        return -self.adjacency

    @property
    def driver_hamiltonian(self) -> GraphMatrix:
        return -self.driver_adjacency

    @property
    def oracle_hamiltonian(self) -> GraphMatrix:
        return -self.oracle_adjacency

    def vertex_index(self, kind: str, index: int) -> int:
        return self.lookup[(kind, index)]

    def runway_index(self, position: int) -> int:
        return self.vertex_index("runway", position)

    @staticmethod
    def _matrix_edges(matrix: GraphMatrix) -> Iterator[tuple[int, int]]:
        if issparse(matrix):
            upper = triu(matrix, k=1, format="coo")
            rows, cols = upper.row, upper.col
        else:
            rows, cols = np.nonzero(np.triu(matrix, k=1))
        yield from zip(rows.tolist(), cols.tolist(), strict=True)

    def edges(self) -> Iterator[tuple[int, int]]:
        yield from self._matrix_edges(self.adjacency)

    def driver_edges(self) -> Iterator[tuple[int, int]]:
        yield from self._matrix_edges(self.driver_adjacency)

    def oracle_edges(self) -> Iterator[tuple[int, int]]:
        yield from self._matrix_edges(self.oracle_adjacency)

    def summary(self) -> dict[str, int]:
        return {
            "leaves": self.tree.leaf_count,
            "root_value": self.tree.root_value,
            "vertices": self.size,
            "edges": sum(1 for _ in self.edges()),
            "oracle_edges": sum(1 for _ in self.oracle_edges()),
        }


def build_walk_graph(
    leaves: Iterable[int],
    *,
    runway_half_length: int = 8,
    matrix_format: MatrixFormat = "sparse",
) -> NandWalkGraph:
    tree = NandTree(leaves)
    if runway_half_length < 1:
        raise ValueError("runway_half_length must be at least 1")
    if matrix_format not in ("sparse", "dense"):
        raise ValueError("matrix_format must be 'sparse' or 'dense'")

    vertices: list[Vertex] = []
    vertices.extend(
        Vertex("runway", position)
        for position in range(-runway_half_length, runway_half_length + 1)
    )
    vertices.extend(Vertex("tree", node) for node in range(tree.node_count))
    vertices.extend(Vertex("oracle", leaf) for leaf in range(tree.leaf_count))
    lookup = {(vertex.kind, vertex.index): index for index, vertex in enumerate(vertices)}

    size = len(vertices)
    if matrix_format == "sparse":
        driver = lil_matrix((size, size), dtype=float)
        oracle = lil_matrix((size, size), dtype=float)
    else:
        driver = np.zeros((size, size), dtype=float)
        oracle = np.zeros((size, size), dtype=float)

    def connect(matrix, left: tuple[str, int], right: tuple[str, int]) -> None:
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

    if matrix_format == "sparse":
        driver = driver.tocsr()
        oracle = oracle.tocsr()

    return NandWalkGraph(
        tree=tree,
        runway_half_length=runway_half_length,
        vertices=tuple(vertices),
        adjacency=driver + oracle,
        driver_adjacency=driver,
        oracle_adjacency=oracle,
        lookup=lookup,
        matrix_format=matrix_format,
    )
