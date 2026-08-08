from collections.abc import Iterable
from dataclasses import dataclass
from math import pi

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import expm_multiply

from .graph import NandWalkGraph, build_walk_graph


@dataclass(frozen=True)
class WalkResult:
    root_value: int
    predicted_value: int
    transmission_probability: float
    reflection_probability: float
    tree_probability: float
    norm: float
    time: float
    state: np.ndarray


def initial_runway_packet(graph: NandWalkGraph, packet_length: int) -> np.ndarray:
    if packet_length < 1:
        raise ValueError("packet_length must be positive")
    if packet_length > graph.runway_half_length + 1:
        raise ValueError("packet_length does not fit on the left side of the runway")

    state = np.zeros(graph.size, dtype=complex)
    scale = 1.0 / np.sqrt(packet_length)
    for position in range(-packet_length + 1, 1):
        state[graph.runway_index(position)] = scale * np.exp(1j * position * pi / 2)
    return state


def evolve_state(hamiltonian: np.ndarray, state: np.ndarray, time: float) -> np.ndarray:
    if hamiltonian.shape != (state.size, state.size):
        raise ValueError("state dimension does not match the Hamiltonian")
    return np.asarray(expm_multiply(-1j * time * csr_matrix(hamiltonian), state))


def partition_probabilities(
    graph: NandWalkGraph,
    state: np.ndarray,
):
    probabilities = np.abs(state) ** 2
    transmitted = sum(
        probabilities[graph.runway_index(position)]
        for position in range(1, graph.runway_half_length + 1)
    )
    reflected = sum(
        probabilities[graph.runway_index(position)]
        for position in range(-graph.runway_half_length, 1)
    )
    tree_probability = sum(
        probabilities[index]
        for index, vertex in enumerate(graph.vertices)
        if vertex.kind != "runway"
    )
    return float(transmitted), float(reflected), float(tree_probability)


def run_continuous_walk(
    leaves: Iterable[int],
    *,
    runway_half_length: int = 12,
    packet_length: int = 8,
    time: float | None = None,
    threshold: float = 0.5,
) -> WalkResult:
    graph = build_walk_graph(leaves, runway_half_length=runway_half_length)
    initial = initial_runway_packet(graph, packet_length)
    evolution_time = packet_length / 2 if time is None else float(time)
    final = evolve_state(graph.hamiltonian, initial, evolution_time)
    transmission, reflection, tree_probability = partition_probabilities(graph, final)
    return WalkResult(
        root_value=graph.tree.root_value,
        predicted_value=int(transmission >= threshold),
        transmission_probability=transmission,
        reflection_probability=reflection,
        tree_probability=tree_probability,
        norm=float(np.vdot(final, final).real),
        time=evolution_time,
        state=final,
    )
