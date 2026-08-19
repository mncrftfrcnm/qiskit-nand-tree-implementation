from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

import numpy as np

from non_qiskit.exact_walk import initial_runway_packet
from non_qiskit.graph import MatrixFormat, build_walk_graph

from ._imports import qiskit_api
from .edge_evolution import build_edge_evolution_gate
from .hamiltonian import graph_evolution_gate, qubits_for_dimension

EvolutionBackend = Literal["sparse", "dense"]


@dataclass(frozen=True)
class PhaseProbeResult:
    root_value: int
    evaluation_qubits: int
    evolution_time: float
    zero_phase_window: float
    zero_phase_weight: float
    phase_probabilities: dict[str, float]


def build_phase_probe_circuit(
    leaves: Iterable[int],
    *,
    runway_half_length: int = 4,
    packet_length: int = 3,
    evaluation_qubits: int = 4,
    evolution_time: float = 0.25,
    matrix_format: MatrixFormat = "sparse",
    evolution_backend: EvolutionBackend = "sparse",
    edge_reps: int = 4,
):
    """Build QPE for exp(-iHt) with a runway packet."""

    if evaluation_qubits < 1:
        raise ValueError("evaluation_qubits must be positive")
    if edge_reps < 1:
        raise ValueError("edge_reps must be at least one")
    if evolution_backend not in ("sparse", "dense"):
        raise ValueError("evolution_backend must be 'sparse' or 'dense'")

    graph = build_walk_graph(
        leaves,
        runway_half_length=runway_half_length,
        matrix_format=matrix_format,
    )
    position_bits = qubits_for_dimension(graph.size)
    qiskit = qiskit_api()

    circuit = qiskit.QuantumCircuit(evaluation_qubits + position_bits, name="nand_qpe")
    packet = np.zeros(1 << position_bits, dtype=complex)
    packet[: graph.size] = initial_runway_packet(graph, packet_length)
    system_qubits = list(range(evaluation_qubits, evaluation_qubits + position_bits))
    circuit.initialize(packet, system_qubits)

    if evolution_backend == "dense":
        unitary = graph_evolution_gate(graph, time=evolution_time, method="exact")
        qpe = qiskit.phase_estimation(evaluation_qubits, unitary)
        circuit.compose(qpe, qubits=circuit.qubits, inplace=True)
        return graph, circuit

    evaluation = list(range(evaluation_qubits))
    circuit.h(evaluation)
    for qubit, power in enumerate(1 << index for index in range(evaluation_qubits)):
        controlled_evolution = build_edge_evolution_gate(
            graph,
            graph.edges(),
            time=evolution_time * power,
            reps=edge_reps * power,
            symmetric=True,
            controlled=True,
            name=f"sparse_U^{power}",
        )
        circuit.append(controlled_evolution, [qubit, *system_qubits])
    circuit.append(qiskit.QFTGate(evaluation_qubits).inverse(), evaluation)
    circuit.append(qiskit.PermutationGate(list(reversed(evaluation))), evaluation)
    return graph, circuit


def run_phase_probe(
    leaves: Iterable[int],
    *,
    runway_half_length: int = 4,
    packet_length: int = 3,
    evaluation_qubits: int = 4,
    evolution_time: float = 0.25,
    zero_phase_bins: int = 1,
    matrix_format: MatrixFormat = "sparse",
    evolution_backend: EvolutionBackend = "sparse",
    edge_reps: int = 4,
) -> PhaseProbeResult:
    if zero_phase_bins < 0:
        raise ValueError("zero_phase_bins must be non-negative")

    graph, circuit = build_phase_probe_circuit(
        leaves,
        runway_half_length=runway_half_length,
        packet_length=packet_length,
        evaluation_qubits=evaluation_qubits,
        evolution_time=evolution_time,
        matrix_format=matrix_format,
        evolution_backend=evolution_backend,
        edge_reps=edge_reps,
    )
    Statevector = qiskit_api().Statevector
    state = Statevector.from_instruction(circuit)
    probabilities = state.probabilities_dict(qargs=list(range(evaluation_qubits)))

    modulus = 1 << evaluation_qubits
    close_to_zero = {
        value for value in range(modulus) if min(value, modulus - value) <= zero_phase_bins
    }
    zero_weight = sum(
        probability
        for bitstring, probability in probabilities.items()
        if int(bitstring, 2) in close_to_zero
    )
    return PhaseProbeResult(
        root_value=graph.tree.root_value,
        evaluation_qubits=evaluation_qubits,
        evolution_time=evolution_time,
        zero_phase_window=zero_phase_bins / modulus,
        zero_phase_weight=float(zero_weight),
        phase_probabilities={key: float(value) for key, value in probabilities.items()},
    )
