from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from non_qiskit.exact_walk import initial_runway_packet
from non_qiskit.graph import build_walk_graph

from ._imports import qiskit_api
from .hamiltonian import encode_hamiltonian, graph_evolution_gate


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
):
    """Build QPE for exp(-iHt) with a runway packet."""

    if evaluation_qubits < 1:
        raise ValueError("evaluation_qubits must be positive")

    graph = build_walk_graph(leaves, runway_half_length=runway_half_length)
    encoded = encode_hamiltonian(graph.hamiltonian)
    qiskit = qiskit_api()
    unitary = graph_evolution_gate(graph, time=evolution_time, method="exact")
    qpe = qiskit.phase_estimation(evaluation_qubits, unitary)

    circuit = qiskit.QuantumCircuit(evaluation_qubits + encoded.qubits, name="nand_qpe")
    packet = np.zeros(1 << encoded.qubits, dtype=complex)
    packet[: graph.size] = initial_runway_packet(graph, packet_length)
    system_qubits = list(range(evaluation_qubits, evaluation_qubits + encoded.qubits))
    circuit.initialize(packet, system_qubits)
    circuit.compose(qpe, qubits=circuit.qubits, inplace=True)
    return graph, circuit


def run_phase_probe(
    leaves: Iterable[int],
    *,
    runway_half_length: int = 4,
    packet_length: int = 3,
    evaluation_qubits: int = 4,
    evolution_time: float = 0.25,
    zero_phase_bins: int = 1,
) -> PhaseProbeResult:
    if zero_phase_bins < 0:
        raise ValueError("zero_phase_bins must be non-negative")

    graph, circuit = build_phase_probe_circuit(
        leaves,
        runway_half_length=runway_half_length,
        packet_length=packet_length,
        evaluation_qubits=evaluation_qubits,
        evolution_time=evolution_time,
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
