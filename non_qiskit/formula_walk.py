from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Mapping

import numpy as np
from scipy.sparse import csr_matrix, issparse, lil_matrix, triu

from .exact_walk import evolve_state
from .formula import Formula, Input, evaluate_formula
from .graph import GraphMatrix, MatrixFormat, Vertex


@dataclass(frozen=True)
class FormulaWalkGraph:
    formula: Formula
    input_values: tuple[tuple[int, int], ...]
    runway_half_length: int
    vertices: tuple[Vertex, ...]
    adjacency: GraphMatrix
    driver_adjacency: GraphMatrix
    oracle_adjacency: GraphMatrix
    lookup: dict[tuple[str, int], int]
    node_inputs: dict[int, int]
    matrix_format: MatrixFormat

    @property
    def size(self) -> int:
        return len(self.vertices)

    @property
    def root_value(self) -> int:
        return evaluate_formula(self.formula, dict(self.input_values))

    @property
    def hamiltonian(self) -> GraphMatrix:
        return -self.adjacency

    def vertex_index(self, kind: str, index: int) -> int:
        return self.lookup[(kind, index)]

    def runway_index(self, position: int) -> int:
        return self.vertex_index("runway", position)

    @staticmethod
    def _matrix_edges(matrix: GraphMatrix):
        if issparse(matrix):
            upper = triu(matrix, k=1, format="coo")
            rows, cols = upper.row, upper.col
        else:
            rows, cols = np.nonzero(np.triu(matrix, k=1))
        yield from zip(rows.tolist(), cols.tolist(), strict=True)

    def edges(self):
        yield from self._matrix_edges(self.adjacency)


@dataclass(frozen=True)
class FormulaWalkResult:
    root_value: int
    transmission_probability: float
    reflection_probability: float
    formula_probability: float
    norm: float
    time: float
    state: np.ndarray


def _index_formula(formula: Formula):
    nodes: list[Formula] = []
    edges: list[tuple[int, int]] = []
    node_inputs: dict[int, int] = {}

    def visit(node: Formula) -> int:
        index = len(nodes)
        nodes.append(node)
        if isinstance(node, Input):
            node_inputs[index] = node.index
            return index
        left = visit(node.left)
        right = visit(node.right)
        edges.extend(((index, left), (index, right)))
        return index

    visit(formula)
    return tuple(nodes), tuple(edges), node_inputs


def build_formula_walk_graph(
    formula: Formula,
    values: Mapping[int, int] | tuple[int, ...],
    *,
    runway_half_length: int = 8,
    matrix_format: MatrixFormat = "sparse",
) -> FormulaWalkGraph:
    """Build the finite walk graph for any binary NAND formula shape.

    This extends the small finite model used elsewhere in the repository. It is
    intentionally not presented as an asymptotic formula-evaluation construction;
    custom shapes still need their own calibration before classification.
    """

    if runway_half_length < 1:
        raise ValueError("runway_half_length must be at least 1")
    if matrix_format not in ("sparse", "dense"):
        raise ValueError("matrix_format must be 'sparse' or 'dense'")

    nodes, tree_edges, node_inputs = _index_formula(formula)
    concrete_values = {input_index: int(values[input_index]) for input_index in set(node_inputs.values())}
    if any(value not in (0, 1) for value in concrete_values.values()):
        raise ValueError("input values must contain only 0 and 1")

    leaf_nodes = tuple(node for node in range(len(nodes)) if node in node_inputs)
    vertices: list[Vertex] = []
    vertices.extend(
        Vertex("runway", position)
        for position in range(-runway_half_length, runway_half_length + 1)
    )
    vertices.extend(Vertex("tree", node) for node in range(len(nodes)))
    vertices.extend(Vertex("oracle", occurrence) for occurrence in range(len(leaf_nodes)))
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

    for parent, child in tree_edges:
        connect(driver, ("tree", parent), ("tree", child))

    for occurrence, node in enumerate(leaf_nodes):
        input_index = node_inputs[node]
        if concrete_values[input_index]:
            connect(oracle, ("tree", node), ("oracle", occurrence))

    if matrix_format == "sparse":
        driver = driver.tocsr()
        oracle = oracle.tocsr()

    return FormulaWalkGraph(
        formula=formula,
        input_values=tuple(sorted(concrete_values.items())),
        runway_half_length=runway_half_length,
        vertices=tuple(vertices),
        adjacency=driver + oracle,
        driver_adjacency=driver,
        oracle_adjacency=oracle,
        lookup=lookup,
        node_inputs=node_inputs,
        matrix_format=matrix_format,
    )


def run_formula_walk(
    formula: Formula,
    values: Mapping[int, int] | tuple[int, ...],
    *,
    runway_half_length: int = 8,
    packet_length: int = 4,
    time: float | None = None,
    matrix_format: MatrixFormat = "sparse",
) -> FormulaWalkResult:
    graph = build_formula_walk_graph(
        formula,
        values,
        runway_half_length=runway_half_length,
        matrix_format=matrix_format,
    )
    if packet_length < 1:
        raise ValueError("packet_length must be positive")
    if packet_length > runway_half_length + 1:
        raise ValueError("packet_length does not fit on the left side of the runway")

    initial = np.zeros(graph.size, dtype=complex)
    scale = 1.0 / np.sqrt(packet_length)
    for position in range(-packet_length + 1, 1):
        initial[graph.runway_index(position)] = scale * np.exp(1j * position * pi / 2)

    evolution_time = packet_length / 2 if time is None else float(time)
    final = evolve_state(graph.hamiltonian, initial, evolution_time)
    probabilities = np.abs(final) ** 2
    transmission = sum(
        probabilities[graph.runway_index(position)]
        for position in range(1, runway_half_length + 1)
    )
    reflection = sum(
        probabilities[graph.runway_index(position)]
        for position in range(-runway_half_length, 1)
    )
    formula_probability = sum(
        probabilities[index]
        for index, vertex in enumerate(graph.vertices)
        if vertex.kind != "runway"
    )
    return FormulaWalkResult(
        root_value=graph.root_value,
        transmission_probability=float(transmission),
        reflection_probability=float(reflection),
        formula_probability=float(formula_probability),
        norm=float(np.vdot(final, final).real),
        time=evolution_time,
        state=final,
    )
