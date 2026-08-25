"""Verify the query oracle is reversible and the walk workspace is cleaned."""

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from qiskit_implementation import evaluate_nand_tree
from qiskit_implementation.oracles import build_bit_oracle
from qiskit_implementation.query_walk import run_query_walk


def main() -> None:
    leaves = (1, 0)
    oracle = build_bit_oracle(leaves)
    circuit = QuantumCircuit(oracle.num_qubits)
    circuit.h(range(circuit.num_qubits))
    before = Statevector.from_instruction(circuit).data
    circuit.compose(oracle, inplace=True)
    circuit.compose(oracle, inplace=True)
    after = Statevector.from_instruction(circuit).data

    result = run_query_walk(
        leaves,
        runway_half_length=3,
        packet_length=3,
        time=0.5,
        steps=3,
    )
    dense = evaluate_nand_tree(leaves, mode="dense")
    query = evaluate_nand_tree(leaves, mode="query")

    print("Oracle and workspace cleanup")
    print("oracle is an involution:", np.allclose(before, after))
    print("workspace leakage:", f"{result.workspace_leakage:.3e}")
    print("padding leakage:", f"{result.padding_leakage:.3e}")
    print("query count:", result.query_count)
    print("dense/query roots:", dense.predicted_value, query.predicted_value)

    assert np.allclose(before, after)
    assert result.workspace_leakage < 1e-9
    assert result.padding_leakage < 1e-9
    assert result.query_count == 6
    assert dense.correct and query.correct
    print("Example completed successfully.")


if __name__ == "__main__":
    main()
