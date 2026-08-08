from collections.abc import Iterable
from dataclasses import dataclass
from itertools import product

import numpy as np

from .exact_walk import initial_runway_packet
from .graph import NandWalkGraph, build_walk_graph
from .product_formula import run_symmetric_split
from .profiles import AlgorithmProfile
from .tree import NandTree, is_power_of_two


@dataclass(frozen=True)
class CalibrationResult:
    profile: AlgorithmProfile
    exact_margin: float
    query_margin: float
    exact_accuracy: float
    query_accuracy: float


def _transmission_curve(
    graph: NandWalkGraph,
    packet_length: int,
    times: np.ndarray,
) -> np.ndarray:
    eigenvalues, eigenvectors = np.linalg.eigh(graph.hamiltonian)
    initial = initial_runway_packet(graph, packet_length)
    coefficients = eigenvectors.conj().T @ initial
    phases = np.exp(-1j * np.outer(eigenvalues, times))
    states = eigenvectors @ (coefficients[:, None] * phases)
    transmitted = [
        graph.runway_index(position)
        for position in range(1, graph.runway_half_length + 1)
    ]
    return np.sum(np.abs(states[transmitted, :]) ** 2, axis=0)


def _score(zero_values: list[float], one_values: list[float]):
    largest_zero = max(zero_values)
    smallest_one = min(one_values)
    threshold = 0.5 * (largest_zero + smallest_one)
    return smallest_one - largest_zero, threshold, largest_zero


def calibrate_profile(
    leaf_count: int,
    *,
    runway_values: Iterable[int],
    packet_values: Iterable[int],
    time_values: Iterable[float],
    step_values: Iterable[int] = (1, 2, 4, 8, 16, 32),
) -> CalibrationResult:
    """Find a finite-model profile by exhaustive input separation."""

    if not is_power_of_two(leaf_count):
        raise ValueError("leaf_count must be a power of two")
    if leaf_count > 8:
        raise ValueError("exhaustive calibration is limited to at most 8 leaves")

    times = np.asarray(tuple(float(value) for value in time_values), dtype=float)
    if times.size == 0 or np.any(times <= 0):
        raise ValueError("time_values must contain positive values")

    inputs = tuple(product((0, 1), repeat=leaf_count))
    roots = {leaves: NandTree(leaves).root_value for leaves in inputs}
    best: tuple[float, int, int, float, float] | None = None

    for runway in runway_values:
        graphs = {
            leaves: build_walk_graph(leaves, runway_half_length=runway)
            for leaves in inputs
        }
        for packet in packet_values:
            if packet < 1 or packet > runway + 1:
                continue
            curves = {
                leaves: _transmission_curve(graph, packet, times)
                for leaves, graph in graphs.items()
            }
            for index, evolution_time in enumerate(times):
                zeros = [curves[leaves][index] for leaves in inputs if roots[leaves] == 0]
                ones = [curves[leaves][index] for leaves in inputs if roots[leaves] == 1]
                margin, threshold, _ = _score(zeros, ones)
                candidate = (margin, runway, packet, float(evolution_time), threshold)
                if best is None or candidate > best:
                    best = candidate

    if best is None or best[0] <= 0:
        raise RuntimeError("the supplied search grid did not separate the two root values")

    exact_margin, runway, packet, evolution_time, threshold = best
    chosen_steps: int | None = None
    query_margin = float("-inf")
    query_accuracy = 0.0

    for steps in sorted(set(int(value) for value in step_values if int(value) > 0)):
        zero_values: list[float] = []
        one_values: list[float] = []
        correct = 0
        for leaves in inputs:
            graph = build_walk_graph(leaves, runway_half_length=runway)
            probability = run_symmetric_split(
                graph,
                packet_length=packet,
                time=evolution_time,
                steps=steps,
            ).transmission_probability
            root = roots[leaves]
            (one_values if root else zero_values).append(probability)
            correct += int((probability >= threshold) == bool(root))

        margin = min(one_values) - max(zero_values)
        accuracy = correct / len(inputs)
        if accuracy > query_accuracy or (accuracy == query_accuracy and margin > query_margin):
            chosen_steps = steps
            query_margin = margin
            query_accuracy = accuracy
        if accuracy == 1.0 and margin > 0:
            chosen_steps = steps
            query_margin = margin
            query_accuracy = accuracy
            break

    if chosen_steps is None:
        raise RuntimeError("no query-step candidates were supplied")

    profile = AlgorithmProfile(
        leaf_count=leaf_count,
        runway_half_length=runway,
        packet_length=packet,
        evolution_time=evolution_time,
        threshold=threshold,
        query_steps=chosen_steps,
    )
    return CalibrationResult(
        profile=profile,
        exact_margin=exact_margin,
        query_margin=query_margin,
        exact_accuracy=1.0,
        query_accuracy=query_accuracy,
    )
