from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.sparse import issparse

from non_qiskit.graph import GraphMatrix, NandWalkGraph

from ._imports import qiskit_api

EvolutionMethod = Literal["exact", "trotter", "suzuki"]


@dataclass(frozen=True)
class EncodedHamiltonian:
    matrix: np.ndarray
    qubits: int
    graph_size: int


def qubits_for_dimension(dimension: int) -> int:
    """Return the register width without allocating a padded matrix."""

    if isinstance(dimension, bool) or not isinstance(dimension, int):
        raise TypeError("dimension must be an integer")
    if dimension < 1:
        raise ValueError("dimension must be positive")
    return max(1, (dimension - 1).bit_length())


def dense_matrix(matrix: GraphMatrix) -> np.ndarray:
    """Materialize a matrix only for the explicit legacy-dense Qiskit path."""

    return np.asarray(matrix.toarray() if issparse(matrix) else matrix, dtype=complex)


def encode_hamiltonian(matrix: GraphMatrix) -> EncodedHamiltonian:
    matrix = dense_matrix(matrix)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("Hamiltonian must be square")
    if not np.allclose(matrix, matrix.conj().T):
        raise ValueError("Hamiltonian must be Hermitian")

    graph_size = matrix.shape[0]
    qubits = qubits_for_dimension(graph_size)
    padded = np.zeros((1 << qubits, 1 << qubits), dtype=complex)
    padded[:graph_size, :graph_size] = matrix
    return EncodedHamiltonian(padded, qubits, graph_size)


def evolution_gate(
    matrix: GraphMatrix,
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
