from dataclasses import dataclass

import numpy as np
from scipy.linalg import expm
from scipy.sparse import issparse
from scipy.sparse.linalg import expm_multiply

from .exact_walk import initial_runway_packet, partition_probabilities
from .graph import NandWalkGraph


@dataclass(frozen=True)
class SplitWalkResult:
    transmission_probability: float
    reflection_probability: float
    tree_probability: float
    norm: float
    state: np.ndarray


def symmetric_split_state(
    graph: NandWalkGraph,
    *,
    packet_length: int,
    time: float,
    steps: int,
) -> np.ndarray:
    """Second-order driver/oracle product formula used by the query circuit."""

    if steps < 1:
        raise ValueError("steps must be at least one")

    dt = time / steps
    state = initial_runway_packet(graph, packet_length)

    if issparse(graph.driver_hamiltonian):
        driver = (-0.5j * dt) * graph.driver_hamiltonian
        oracle = (-1j * dt) * graph.oracle_hamiltonian
        for _ in range(steps):
            state = expm_multiply(driver, state)
            state = expm_multiply(oracle, state)
            state = expm_multiply(driver, state)
    else:
        driver = expm(-0.5j * dt * graph.driver_hamiltonian)
        oracle = expm(-1j * dt * graph.oracle_hamiltonian)
        for _ in range(steps):
            state = driver @ state
            state = oracle @ state
            state = driver @ state
    return state


def run_symmetric_split(
    graph: NandWalkGraph,
    *,
    packet_length: int,
    time: float,
    steps: int,
) -> SplitWalkResult:
    state = symmetric_split_state(
        graph,
        packet_length=packet_length,
        time=time,
        steps=steps,
    )
    transmission, reflection, tree_probability = partition_probabilities(graph, state)
    return SplitWalkResult(
        transmission_probability=transmission,
        reflection_probability=reflection,
        tree_probability=tree_probability,
        norm=float(np.vdot(state, state).real),
        state=state,
    )
