from collections.abc import Iterable
from dataclasses import dataclass
from math import log2

import numpy as np

from non_qiskit.exact_walk import initial_runway_packet, partition_probabilities
from non_qiskit.graph import NandWalkGraph, build_walk_graph

from ._imports import qiskit_api
from .gates import append_x_on_state
from .hamiltonian import encode_hamiltonian, evolution_gate
from .oracles import build_bit_oracle


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

    @property
    def leakage_shots(self) -> int:
        return self.padding + self.workspace


def build_leaf_index_loader(graph: NandWalkGraph):
    position_bits = encode_hamiltonian(graph.hamiltonian).qubits
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
    adjacency = np.zeros_like(graph.adjacency)
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
):
    """Apply the input-dependent leaf-edge evolution with a clean work qubit."""

    encoded = encode_hamiltonian(graph.hamiltonian)
    address_bits = int(log2(graph.tree.leaf_count))
    position = list(range(encoded.qubits))
    address = list(range(encoded.qubits, encoded.qubits + address_bits))
    value = encoded.qubits + address_bits

    circuit = qiskit_api().QuantumCircuit(value + 1, name="oracle_evolution")
    load_address = build_leaf_index_loader(graph).to_gate()
    query = build_bit_oracle(leaves).to_gate()
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
):
    if steps < 1:
        raise ValueError("steps must be at least one")

    graph = build_walk_graph(leaves, runway_half_length=runway_half_length)
    encoded = encode_hamiltonian(graph.hamiltonian)
    address_bits = int(log2(graph.tree.leaf_count))

    position = list(range(encoded.qubits))
    value = encoded.qubits + address_bits
    circuit = qiskit_api().QuantumCircuit(value + 1, name="query_walk")

    packet = np.zeros(1 << encoded.qubits, dtype=complex)
    packet[: graph.size] = initial_runway_packet(graph, packet_length)
    circuit.initialize(packet, position)

    dt = time / steps
    driver = evolution_gate(graph.driver_hamiltonian, time=dt / 2, label="driver")
    oracle_step = build_oracle_evolution_block(graph, graph.tree.leaves, time=dt).to_gate()
    all_qubits = list(range(circuit.num_qubits))

    # Symmetric splitting: half a driver step, one input-dependent step, then the
    # other half driver step. The oracle block contains two calls to U_O.
    for _ in range(steps):
        circuit.append(driver, position)
        circuit.append(oracle_step, all_qubits)
        circuit.append(driver, position)

    return graph, circuit


def simulate_query_walk(
    graph: NandWalkGraph,
    circuit,
    *,
    steps: int,
    threshold: float = 0.5,
) -> QueryWalkResult:
    encoded = encode_hamiltonian(graph.hamiltonian)
    state = np.asarray(qiskit_api().Statevector.from_instruction(circuit).data)
    position_state = state[: 1 << encoded.qubits]
    graph_state = position_state[: graph.size]

    transmitted, reflected, tree = partition_probabilities(graph, graph_state)
    norm = float(np.vdot(state, state).real)
    position_norm = float(np.vdot(position_state, position_state).real)
    graph_norm = float(np.vdot(graph_state, graph_state).real)

    return QueryWalkResult(
        root_value=graph.tree.root_value,
        predicted_value=int(transmitted >= threshold),
        steps=steps,
        query_count=2 * steps,
        transmission_probability=transmitted,
        reflection_probability=reflected,
        tree_probability=tree,
        padding_leakage=max(0.0, position_norm - graph_norm),
        workspace_leakage=max(0.0, norm - position_norm),
        norm=norm,
        state=state,
    )


def run_query_walk(
    leaves: Iterable[int],
    *,
    runway_half_length: int = 6,
    packet_length: int = 4,
    time: float = 2.0,
    steps: int = 2,
    threshold: float = 0.5,
) -> QueryWalkResult:
    graph, circuit = build_query_walk_circuit(
        leaves,
        runway_half_length=runway_half_length,
        packet_length=packet_length,
        time=time,
        steps=steps,
    )
    return simulate_query_walk(graph, circuit, steps=steps, threshold=threshold)


def _wilson_interval(successes: int, total: int, z: float = 1.96):
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * np.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    radius /= denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def summarize_query_counts(
    graph: NandWalkGraph,
    counts: dict[str, int],
    *,
    steps: int,
    threshold: float,
    batches: int = 1,
) -> QueryShotResult:
    position_bits = encode_hamiltonian(graph.hamiltonian).qubits
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
