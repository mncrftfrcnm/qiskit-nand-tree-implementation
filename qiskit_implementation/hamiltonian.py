from dataclasses import dataclass
from math import ceil, log2
from typing import Literal

import numpy as np

from non_qiskit.graph import NandWalkGraph

from ._imports import qiskit_api

EvolutionMethod = Literal["exact", "trotter", "suzuki"]


@dataclass(frozen=True)
class EncodedHamiltonian:
    matrix: np.ndarray
    qubits: int
    graph_size: int


def encode_hamiltonian(matrix: np.ndarray) -> EncodedHamiltonian:
    matrix = np.asarray(matrix, dtype=complex)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("Hamiltonian must be square")
    if not np.allclose(matrix, matrix.conj().T):
        raise ValueError("Hamiltonian must be Hermitian")

    graph_size = matrix.shape[0]
    qubits = max(1, ceil(log2(graph_size)))
    padded = np.zeros((1 << qubits, 1 << qubits), dtype=complex)
    padded[:graph_size, :graph_size] = matrix
    return EncodedHamiltonian(padded, qubits, graph_size)


def evolution_gate(
    matrix: np.ndarray,
    *,
    time: float,
    method: EvolutionMethod = "exact",
    reps: int = 1,
    label: str = "exp(-iHt)",
):
    if reps < 1:
        raise ValueError("reps must be at least one")

    qiskit = qiskit_api()
    encoded = encode_hamiltonian(matrix)
    if method == "exact":
        return qiskit.HamiltonianGate(encoded.matrix, time=time, label=label)

    pauli = qiskit.SparsePauliOp.from_operator(qiskit.Operator(encoded.matrix))
    if method == "trotter":
        synthesis = qiskit.LieTrotter(reps=reps)
    elif method == "suzuki":
        synthesis = qiskit.SuzukiTrotter(order=2, reps=reps)
    else:
        raise ValueError(f"unknown evolution method: {method}")
    return qiskit.PauliEvolutionGate(pauli, time=time, synthesis=synthesis, label=label)


def graph_evolution_gate(
    graph: NandWalkGraph,
    *,
    time: float,
    method: EvolutionMethod = "exact",
    reps: int = 1,
):
    return evolution_gate(graph.hamiltonian, time=time, method=method, reps=reps)
