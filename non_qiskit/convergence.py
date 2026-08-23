from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from .exact_walk import evolve_state, initial_runway_packet, partition_probabilities
from .graph import MatrixFormat, build_walk_graph
from .product_formula import symmetric_split_state


@dataclass(frozen=True)
class ConvergencePoint:
    steps: int
    oracle_calls: int
    fidelity: float
    state_error: float
    transmission_error: float


def product_formula_convergence(
    leaves: Iterable[int],
    *,
    runway_half_length: int,
    packet_length: int,
    time: float,
    steps: Iterable[int] = (1, 2, 4, 8, 16),
    matrix_format: MatrixFormat = "sparse",
):
    graph = build_walk_graph(
        leaves,
        runway_half_length=runway_half_length,
        matrix_format=matrix_format,
    )
    initial = initial_runway_packet(graph, packet_length)
    exact = evolve_state(graph.hamiltonian, initial, time)
    exact_transmission = partition_probabilities(graph, exact)[0]

    points: list[ConvergencePoint] = []
    for count in sorted(set(int(value) for value in steps)):
        if count < 1:
            raise ValueError("steps must contain positive integers")
        approximate = symmetric_split_state(
            graph,
            packet_length=packet_length,
            time=time,
            steps=count,
        )
        overlap = np.vdot(exact, approximate)
        transmission = partition_probabilities(graph, approximate)[0]
        points.append(
            ConvergencePoint(
                steps=count,
                oracle_calls=2 * count,
                fidelity=float(abs(overlap) ** 2),
                state_error=float(np.linalg.norm(exact - approximate)),
                transmission_error=float(abs(exact_transmission - transmission)),
            )
        )
    return tuple(points)
