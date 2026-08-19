from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

import numpy as np

from non_qiskit.exact_walk import initial_runway_packet, partition_probabilities
from non_qiskit.graph import MatrixFormat, NandWalkGraph, build_walk_graph

from ._imports import qiskit_api
from .edge_evolution import (
    build_driver_edge_gate,
    build_edge_evolution_gate,
    build_oracle_edge_gate,
)
from .hamiltonian import evolution_gate, graph_evolution_gate, qubits_for_dimension

CircuitMethod = Literal["edge", "exact", "trotter", "suzuki", "alternating", "symmetric"]
EvolutionBackend = Literal["sparse", "dense"]


@dataclass(frozen=True)
class QiskitWalkResult:
    root_value: int
    predicted_value: int
    method: str
    transmission_probability: float
    reflection_probability: float
    tree_probability: float
    leakage_probability: float
    norm: float
    oracle_segments: int
    state: np.ndarray


def encoded_initial_state(graph: NandWalkGraph, packet_length: int) -> np.ndarray:
    position_bits = qubits_for_dimension(graph.size)
    state = np.zeros(1 << position_bits, dtype=complex)
    state[: graph.size] = initial_runway_packet(graph, packet_length)
    return state


def _append_split_evolution(
    circuit,
    graph: NandWalkGraph,
    *,
    time: float,
    steps: int,
    symmetric: bool,
    evolution_backend: EvolutionBackend,
    edge_reps: int,
) -> None:
    if steps < 1:
        raise ValueError("steps must be at least one")
    dt = time / steps
    driver_time = dt / 2 if symmetric else dt
    if evolution_backend == "sparse":
        driver = build_driver_edge_gate(graph, time=driver_time, reps=edge_reps)
        oracle = build_oracle_edge_gate(graph, time=dt)
    elif evolution_backend == "dense":
        driver = evolution_gate(graph.driver_hamiltonian, time=driver_time, label="driver")
        oracle = evolution_gate(graph.oracle_hamiltonian, time=dt, label="oracle")
    else:
        raise ValueError("evolution_backend must be 'sparse' or 'dense'")

    for _ in range(steps):
        circuit.append(driver, circuit.qubits)
        circuit.append(oracle, circuit.qubits)
        if symmetric:
            circuit.append(driver, circuit.qubits)


def build_evolution_circuit(
    graph: NandWalkGraph,
    *,
    packet_length: int,
    time: float,
    method: CircuitMethod = "edge",
    reps: int = 1,
    evolution_backend: EvolutionBackend = "sparse",
    edge_reps: int = 1,
):
    qiskit = qiskit_api()
    if edge_reps < 1:
        raise ValueError("edge_reps must be at least one")

    position_bits = qubits_for_dimension(graph.size)
    circuit = qiskit.QuantumCircuit(position_bits, name="nand_walk")
    circuit.initialize(encoded_initial_state(graph, packet_length), circuit.qubits)

    if method == "edge":
        circuit.append(
            build_edge_evolution_gate(
                graph,
                graph.edges(),
                time=time,
                reps=reps,
                symmetric=True,
                name="sparse_full_walk",
            ),
            circuit.qubits,
        )
    elif method in ("exact", "trotter", "suzuki"):
        circuit.append(
            graph_evolution_gate(graph, time=time, method=method, reps=reps),
            circuit.qubits,
        )
    elif method == "alternating":
        _append_split_evolution(
            circuit,
            graph,
            time=time,
            steps=reps,
            symmetric=False,
            evolution_backend=evolution_backend,
            edge_reps=edge_reps,
        )
    elif method == "symmetric":
        _append_split_evolution(
            circuit,
            graph,
            time=time,
            steps=reps,
            symmetric=True,
            evolution_backend=evolution_backend,
            edge_reps=edge_reps,
        )
    else:
        raise ValueError(f"unknown circuit method: {method}")
    return circuit


def simulate_circuit(
    graph: NandWalkGraph,
    circuit,
    *,
    method: str,
    threshold: float = 0.5,
    oracle_segments: int = 0,
) -> QiskitWalkResult:
    Statevector = qiskit_api().Statevector
    state = np.asarray(Statevector.from_instruction(circuit).data)
    graph_state = state[: graph.size]
    transmission, reflection, tree_probability = partition_probabilities(graph, graph_state)
    norm = float(np.vdot(state, state).real)
    graph_probability = float(np.vdot(graph_state, graph_state).real)
    return QiskitWalkResult(
        root_value=graph.tree.root_value,
        predicted_value=int(transmission >= threshold),
        method=method,
        transmission_probability=transmission,
        reflection_probability=reflection,
        tree_probability=tree_probability,
        leakage_probability=max(0.0, norm - graph_probability),
        norm=norm,
        oracle_segments=oracle_segments,
        state=state,
    )


def run_qiskit_walk(
    leaves: Iterable[int],
    *,
    runway_half_length: int = 6,
    packet_length: int = 4,
    time: float = 2.0,
    method: CircuitMethod = "edge",
    reps: int = 1,
    threshold: float = 0.5,
    matrix_format: MatrixFormat = "sparse",
    evolution_backend: EvolutionBackend = "sparse",
    edge_reps: int = 1,
) -> QiskitWalkResult:
    graph = build_walk_graph(
        leaves,
        runway_half_length=runway_half_length,
        matrix_format=matrix_format,
    )
    circuit = build_evolution_circuit(
        graph,
        packet_length=packet_length,
        time=time,
        method=method,
        reps=reps,
        evolution_backend=evolution_backend,
        edge_reps=edge_reps,
    )
    oracle_segments = reps if method in ("alternating", "symmetric") else 0
    return simulate_circuit(
        graph,
        circuit,
        method=method,
        threshold=threshold,
        oracle_segments=oracle_segments,
    )


def sample_positions(
    graph: NandWalkGraph,
    circuit,
    *,
    shots: int = 4096,
    seed: int | None = None,
) -> dict[str, int]:
    """Sample the encoded position register."""

    if shots < 1:
        raise ValueError("shots must be positive")
    qiskit = qiskit_api()
    measured = circuit.copy()
    measured.measure_all()
    sampler = qiskit.StatevectorSampler(seed=seed)
    return sampler.run([measured], shots=shots).result()[0].data.meas.get_counts()


def circuit_resources(circuit) -> dict[str, object]:
    qiskit = qiskit_api()
    compiled = qiskit.transpile(
        circuit,
        basis_gates=["rz", "sx", "x", "cx"],
        optimization_level=0,
    )
    return {
        "qubits": compiled.num_qubits,
        "depth": compiled.depth(),
        "size": compiled.size(),
        "operations": dict(compiled.count_ops()),
    }
