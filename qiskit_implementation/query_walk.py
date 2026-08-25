from collections.abc import Iterable
from dataclasses import dataclass
from math import log2
from typing import Literal

import numpy as np

from non_qiskit.exact_walk import initial_runway_packet, partition_probabilities
from non_qiskit.graph import MatrixFormat, NandWalkGraph, build_walk_graph

from ._imports import qiskit_api
from .edge_evolution import build_all_leaf_edge_gate, build_driver_edge_gate
from .gates import append_x_on_state
from .hamiltonian import evolution_gate, qubits_for_dimension
from .oracles import build_bit_oracle

EvolutionBackend = Literal["sparse", "dense"]
SimulationBackend = Literal["auto", "edge", "qiskit"]


@dataclass(frozen=True)
class QueryWalkResult:
    root_value: int
    predicted_value: int
    steps: int
    query_count: int
    transmission_probability: float
    reflection_probability: float
    tree_probability: float
    padding_leakage: float
    workspace_leakage: float
    norm: float
    state: np.ndarray
    simulation_backend: str = "qiskit"


@dataclass(frozen=True)
class QueryShotResult:
    shots: int
    valid_shots: int
    transmitted: int
    reflected: int
    tree: int
    padding: int
    workspace: int
    transmission_probability: float
    confidence_low: float
    confidence_high: float
    predicted_value: int
    stable_decision: bool
    query_count: int
    total_query_count: int
    batches: int = 1
    simulation_backend: str = "qiskit"

    @property
    def leakage_shots(self) -> int:
        return self.padding + self.workspace


def resolve_simulation_backend(
    simulation_backend: SimulationBackend,
    evolution_backend: EvolutionBackend,
) -> Literal["edge", "qiskit"]:
    """Resolve automatic simulation without changing circuit construction."""

    if simulation_backend == "auto":
        return "edge" if evolution_backend == "sparse" else "qiskit"
    if simulation_backend == "edge":
        if evolution_backend != "sparse":
            raise ValueError("edge simulation requires evolution_backend='sparse'")
        return "edge"
    if simulation_backend == "qiskit":
        return "qiskit"
    raise ValueError("simulation_backend must be 'auto', 'edge', or 'qiskit'")


def build_leaf_index_loader(graph: NandWalkGraph):
    position_bits = qubits_for_dimension(graph.size)
    address_bits = int(log2(graph.tree.leaf_count))
    circuit = qiskit_api().QuantumCircuit(position_bits + address_bits, name="leaf_index")

    if address_bits == 0:
        return circuit

    position = list(range(position_bits))
    address = list(range(position_bits, position_bits + address_bits))

    for leaf in range(graph.tree.leaf_count):
        vertices = (
            graph.vertex_index("tree", graph.tree.leaf_node(leaf)),
            graph.vertex_index("oracle", leaf),
        )
        for vertex in vertices:
            for bit, target in enumerate(address):
                if (leaf >> bit) & 1:
                    append_x_on_state(circuit, position, target, vertex)
    return circuit


def _full_leaf_edge_hamiltonian(graph: NandWalkGraph) -> np.ndarray:
    """Legacy dense reference used only when evolution_backend='dense'."""

    adjacency = np.zeros((graph.size, graph.size), dtype=float)
    for leaf in range(graph.tree.leaf_count):
        tree_vertex = graph.vertex_index("tree", graph.tree.leaf_node(leaf))
        oracle_vertex = graph.vertex_index("oracle", leaf)
        adjacency[tree_vertex, oracle_vertex] = 1.0
        adjacency[oracle_vertex, tree_vertex] = 1.0
    return -adjacency


def build_oracle_evolution_block(
    graph: NandWalkGraph,
    leaves: Iterable[int],
    *,
    time: float,
    evolution_backend: EvolutionBackend = "sparse",
):
    """Apply the input-dependent leaf-edge evolution with a clean work qubit."""

    if evolution_backend not in ("sparse", "dense"):
        raise ValueError("evolution_backend must be 'sparse' or 'dense'")

    position_bits = qubits_for_dimension(graph.size)
    address_bits = int(log2(graph.tree.leaf_count))
    position = list(range(position_bits))
    address = list(range(position_bits, position_bits + address_bits))
    value = position_bits + address_bits

    circuit = qiskit_api().QuantumCircuit(value + 1, name="oracle_evolution")
    load_address = build_leaf_index_loader(graph).to_gate()
    query = build_bit_oracle(leaves).to_gate()
    if evolution_backend == "sparse":
        leaf_edges = build_all_leaf_edge_gate(graph, time=time, controlled=True)
    else:
        leaf_edges = evolution_gate(
            _full_leaf_edge_hamiltonian(graph),
            time=time,
            label="oracle_edges",
        ).control(1)

    # The walk register stores a graph vertex, not a leaf number. For leaf and
    # auxiliary vertices, this first step computes the corresponding leaf index k
    # into the address register. Internal tree/runway vertices leave it unchanged.
    circuit.append(load_address, [*position, *address])

    # Query x_k into the value qubit. That qubit now says whether the input-dependent
    # leaf edge is present, so it can control the leaf-edge evolution below.
    circuit.append(query, [*address, value])
    circuit.append(leaf_edges, [value, *position])

    # The bit oracle is its own inverse. Querying it a second time erases x_k from
    # the work qubit instead of leaving it entangled with the walk. This is also why
    # one product-formula step counts as two oracle calls.
    circuit.append(query, [*address, value])

    # load_address is also an involution, so this removes the temporary leaf index
    # and returns both workspace registers to |0>.
    circuit.append(load_address, [*position, *address])
    return circuit


def build_query_walk_circuit(
    leaves: Iterable[int],
    *,
    runway_half_length: int = 6,
    packet_length: int = 4,
    time: float = 2.0,
    steps: int = 2,
    matrix_format: MatrixFormat = "sparse",
    evolution_backend: EvolutionBackend = "sparse",
    driver_reps: int = 4,
):
    if steps < 1:
        raise ValueError("steps must be at least one")

    if driver_reps < 1:
        raise ValueError("driver_reps must be at least one")

    graph = build_walk_graph(
        leaves,
        runway_half_length=runway_half_length,
        matrix_format=matrix_format,
    )
    position_bits = qubits_for_dimension(graph.size)
    address_bits = int(log2(graph.tree.leaf_count))

    position = list(range(position_bits))
    value = position_bits + address_bits
    circuit = qiskit_api().QuantumCircuit(value + 1, name="query_walk")

    packet = np.zeros(1 << position_bits, dtype=complex)
    packet[: graph.size] = initial_runway_packet(graph, packet_length)
    circuit.initialize(packet, position)

    dt = time / steps
    if evolution_backend == "sparse":
        driver = build_driver_edge_gate(graph, time=dt / 2, reps=driver_reps)
    elif evolution_backend == "dense":
        driver = evolution_gate(graph.driver_hamiltonian, time=dt / 2, label="driver")
    else:
        raise ValueError("evolution_backend must be 'sparse' or 'dense'")
    oracle_step = build_oracle_evolution_block(
        graph,
        graph.tree.leaves,
        time=dt,
        evolution_backend=evolution_backend,
    ).to_gate()
    all_qubits = list(range(circuit.num_qubits))

    # Symmetric splitting: half a driver step, one input-dependent step, then the
    # other half driver step. The oracle block contains two calls to U_O.
    for _ in range(steps):
        circuit.append(driver, position)
        circuit.append(oracle_step, all_qubits)
        circuit.append(driver, position)

    return graph, circuit


def _apply_edge_sequence(
    state: np.ndarray,
    edges: tuple[tuple[int, int], ...],
    *,
    time: float,
) -> None:
    """Apply ordered two-level rotations directly to a position state."""

    if time == 0.0 or not edges:
        return
    cosine = np.cos(time)
    imaginary_sine = 1j * np.sin(time)
    for left, right in edges:
        left_amplitude = state[left]
        right_amplitude = state[right]
        state[left] = cosine * left_amplitude + imaginary_sine * right_amplitude
        state[right] = imaginary_sine * left_amplitude + cosine * right_amplitude


def _query_result_from_graph_state(
    graph: NandWalkGraph,
    state: np.ndarray,
    *,
    steps: int,
    threshold: float,
    simulation_backend: str,
    padding_leakage: float = 0.0,
    workspace_leakage: float = 0.0,
) -> QueryWalkResult:
    transmitted, reflected, tree = partition_probabilities(graph, state[: graph.size])
    norm = float(np.vdot(state, state).real)
    return QueryWalkResult(
        root_value=graph.tree.root_value,
        predicted_value=int(transmitted >= threshold),
        steps=steps,
        query_count=2 * steps,
        transmission_probability=transmitted,
        reflection_probability=reflected,
        tree_probability=tree,
        padding_leakage=padding_leakage,
        workspace_leakage=workspace_leakage,
        norm=norm,
        state=state,
        simulation_backend=simulation_backend,
    )


def simulate_edge_query_walk(
    graph: NandWalkGraph,
    *,
    packet_length: int,
    time: float,
    steps: int,
    threshold: float = 0.5,
    driver_reps: int = 4,
) -> QueryWalkResult:
    """Simulate the structured sparse query circuit without gate decomposition.

    The circuit's address and value registers are uncomputed after each oracle
    block. Their clean action on the position register is therefore exactly the
    ordered driver-edge product formula plus the present, disjoint oracle edges.
    """

    if steps < 1:
        raise ValueError("steps must be at least one")
    if driver_reps < 1:
        raise ValueError("driver_reps must be at least one")

    state = initial_runway_packet(graph, packet_length)
    driver_edges = tuple(graph.driver_edges())
    reverse_driver_edges = tuple(reversed(driver_edges))
    oracle_edges = tuple(graph.oracle_edges())
    dt = time / steps
    driver_edge_time = dt / (4 * driver_reps)

    def apply_half_driver() -> None:
        for _ in range(driver_reps):
            _apply_edge_sequence(state, driver_edges, time=driver_edge_time)
            _apply_edge_sequence(state, reverse_driver_edges, time=driver_edge_time)

    for _ in range(steps):
        apply_half_driver()
        _apply_edge_sequence(state, oracle_edges, time=dt)
        apply_half_driver()

    return _query_result_from_graph_state(
        graph,
        state,
        steps=steps,
        threshold=threshold,
        simulation_backend="edge",
    )


def simulate_query_walk(
    graph: NandWalkGraph,
    circuit,
    *,
    steps: int,
    threshold: float = 0.5,
) -> QueryWalkResult:
    position_bits = qubits_for_dimension(graph.size)
    state = np.asarray(qiskit_api().Statevector.from_instruction(circuit).data)
    position_state = state[: 1 << position_bits]
    graph_state = position_state[: graph.size]

    norm = float(np.vdot(state, state).real)
    position_norm = float(np.vdot(position_state, position_state).real)
    graph_norm = float(np.vdot(graph_state, graph_state).real)
    return _query_result_from_graph_state(
        graph,
        state,
        steps=steps,
        threshold=threshold,
        simulation_backend="qiskit",
        padding_leakage=max(0.0, position_norm - graph_norm),
        workspace_leakage=max(0.0, norm - position_norm),
    )


def run_query_walk(
    leaves: Iterable[int],
    *,
    runway_half_length: int = 6,
    packet_length: int = 4,
    time: float = 2.0,
    steps: int = 2,
    threshold: float = 0.5,
    matrix_format: MatrixFormat = "sparse",
    evolution_backend: EvolutionBackend = "sparse",
    simulation_backend: SimulationBackend = "auto",
    driver_reps: int = 4,
) -> QueryWalkResult:
    resolved_simulator = resolve_simulation_backend(simulation_backend, evolution_backend)
    if resolved_simulator == "edge":
        graph = build_walk_graph(
            leaves,
            runway_half_length=runway_half_length,
            matrix_format=matrix_format,
        )
        return simulate_edge_query_walk(
            graph,
            packet_length=packet_length,
            time=time,
            steps=steps,
            threshold=threshold,
            driver_reps=driver_reps,
        )

    graph, circuit = build_query_walk_circuit(
        leaves,
        runway_half_length=runway_half_length,
        packet_length=packet_length,
        time=time,
        steps=steps,
        matrix_format=matrix_format,
        evolution_backend=evolution_backend,
        driver_reps=driver_reps,
    )
    return simulate_query_walk(graph, circuit, steps=steps, threshold=threshold)


def _wilson_interval(successes: int, total: int, z: float = 1.96):
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * np.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    radius /= denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def _edge_sample_summary(
    counts: np.ndarray,
    *,
    steps: int,
    threshold: float,
    batches: int,
) -> QueryShotResult:
    transmitted, reflected, tree = (int(value) for value in counts)
    shots = transmitted + reflected + tree
    probability = transmitted / shots
    low, high = _wilson_interval(transmitted, shots)
    predicted = int(probability >= threshold)
    stable = low >= threshold if predicted else high < threshold
    return QueryShotResult(
        shots=shots,
        valid_shots=shots,
        transmitted=transmitted,
        reflected=reflected,
        tree=tree,
        padding=0,
        workspace=0,
        transmission_probability=probability,
        confidence_low=low,
        confidence_high=high,
        predicted_value=predicted,
        stable_decision=stable,
        query_count=2 * steps,
        total_query_count=2 * steps * shots,
        batches=batches,
        simulation_backend="edge",
    )


def _edge_category_probabilities(result: QueryWalkResult) -> np.ndarray:
    probabilities = np.array(
        [
            result.transmission_probability,
            result.reflection_probability,
            result.tree_probability,
        ],
        dtype=float,
    )
    probabilities = np.maximum(probabilities, 0.0)
    return probabilities / probabilities.sum()


def sample_edge_query_walk(
    result: QueryWalkResult,
    *,
    threshold: float,
    shots: int = 4096,
    seed: int | None = None,
) -> QueryShotResult:
    """Sample the ideal clean-register distribution from an edge result."""

    if shots < 1:
        raise ValueError("shots must be positive")
    rng = np.random.default_rng(seed)
    counts = rng.multinomial(shots, _edge_category_probabilities(result))
    return _edge_sample_summary(
        counts,
        steps=result.steps,
        threshold=threshold,
        batches=1,
    )


def sample_edge_query_walk_adaptive(
    result: QueryWalkResult,
    *,
    threshold: float,
    min_shots: int = 256,
    max_shots: int = 8192,
    batch_shots: int = 256,
    seed: int | None = None,
) -> QueryShotResult:
    """Adaptively sample a matrix-free edge-simulation result."""

    if min_shots < 1:
        raise ValueError("min_shots must be positive")
    if max_shots < min_shots:
        raise ValueError("max_shots must be at least min_shots")
    if batch_shots < 1:
        raise ValueError("batch_shots must be positive")

    rng = np.random.default_rng(seed)
    probabilities = _edge_category_probabilities(result)
    counts = np.zeros(3, dtype=np.int64)
    total = batches = 0
    summary: QueryShotResult | None = None
    while total < max_shots:
        batch = min(batch_shots, max_shots - total)
        counts += rng.multinomial(batch, probabilities)
        total += batch
        batches += 1
        summary = _edge_sample_summary(
            counts,
            steps=result.steps,
            threshold=threshold,
            batches=batches,
        )
        if total >= min_shots and summary.stable_decision:
            return summary

    assert summary is not None
    return summary


def summarize_query_counts(
    graph: NandWalkGraph,
    counts: dict[str, int],
    *,
    steps: int,
    threshold: float,
    batches: int = 1,
) -> QueryShotResult:
    position_bits = qubits_for_dimension(graph.size)
    position_mask = (1 << position_bits) - 1
    transmitted = reflected = tree = padding = workspace = 0

    for bitstring, count in counts.items():
        basis = int(bitstring.replace(" ", ""), 2)
        position = basis & position_mask
        work = basis >> position_bits

        if work:
            workspace += count
            continue
        if position >= graph.size:
            padding += count
            continue

        vertex = graph.vertices[position]
        if vertex.kind != "runway":
            tree += count
        elif vertex.index > 0:
            transmitted += count
        else:
            reflected += count

    shots = sum(counts.values())
    valid = transmitted + reflected + tree
    if shots < 1 or valid < 1:
        raise ValueError("counts contain no valid position measurements")

    probability = transmitted / valid
    low, high = _wilson_interval(transmitted, valid)
    predicted = int(probability >= threshold)
    stable = low >= threshold if predicted else high < threshold

    return QueryShotResult(
        shots=shots,
        valid_shots=valid,
        transmitted=transmitted,
        reflected=reflected,
        tree=tree,
        padding=padding,
        workspace=workspace,
        transmission_probability=probability,
        confidence_low=low,
        confidence_high=high,
        predicted_value=predicted,
        stable_decision=stable,
        query_count=2 * steps,
        total_query_count=2 * steps * shots,
        batches=batches,
    )


def _measure(circuit, shots: int, seed: int | None) -> dict[str, int]:
    measured = circuit.measure_all(inplace=False)
    sampler = qiskit_api().StatevectorSampler(seed=seed)
    result = sampler.run([measured], shots=shots).result()[0]
    return result.data.meas.get_counts()


def sample_query_walk(
    graph: NandWalkGraph,
    circuit,
    *,
    steps: int,
    threshold: float,
    shots: int = 4096,
    seed: int | None = None,
) -> QueryShotResult:
    if shots < 1:
        raise ValueError("shots must be positive")
    return summarize_query_counts(
        graph,
        _measure(circuit, shots, seed),
        steps=steps,
        threshold=threshold,
    )


def sample_query_walk_adaptive(
    graph: NandWalkGraph,
    circuit,
    *,
    steps: int,
    threshold: float,
    min_shots: int = 256,
    max_shots: int = 8192,
    batch_shots: int = 256,
    seed: int | None = None,
) -> QueryShotResult:
    if min_shots < 1:
        raise ValueError("min_shots must be positive")
    if max_shots < min_shots:
        raise ValueError("max_shots must be at least min_shots")
    if batch_shots < 1:
        raise ValueError("batch_shots must be positive")

    counts: dict[str, int] = {}
    total = 0
    batches = 0
    result: QueryShotResult | None = None

    while total < max_shots:
        batch = min(batch_shots, max_shots - total)
        batch_seed = None if seed is None else seed + batches
        for outcome, count in _measure(circuit, batch, batch_seed).items():
            counts[outcome] = counts.get(outcome, 0) + count
        total += batch
        batches += 1
        result = summarize_query_counts(
            graph,
            counts,
            steps=steps,
            threshold=threshold,
            batches=batches,
        )
        if total >= min_shots and result.stable_decision:
            return result

    return result
