from collections.abc import Iterable
from math import log2, pi

from non_qiskit.tree import NandTree

from ._imports import qiskit_api
from .gates import append_phase_on_state, append_x_on_state


def build_bit_oracle(leaves: Iterable[int]):
    """Build O_x |j,b> = |j,b xor x_j>."""

    tree = NandTree(leaves)
    address_bits = int(log2(tree.leaf_count))
    target = address_bits
    circuit = qiskit_api().QuantumCircuit(address_bits + 1, name="O_x")

    if address_bits == 0:
        if tree.leaves[0]:
            circuit.x(target)
        return circuit

    controls = list(range(address_bits))
    for address, bit in enumerate(tree.leaves):
        if bit:
            append_x_on_state(circuit, controls, target, address)
    return circuit


def build_phase_oracle(leaves: Iterable[int]):
    """Build O_x^phase |j> = (-1)^x_j |j>."""

    tree = NandTree(leaves)
    address_bits = int(log2(tree.leaf_count))
    circuit = qiskit_api().QuantumCircuit(address_bits, name="phase_Ox")

    if address_bits == 0:
        if tree.leaves[0]:
            circuit.global_phase = pi
        return circuit

    qubits = list(range(address_bits))
    for address, bit in enumerate(tree.leaves):
        if bit:
            append_phase_on_state(circuit, qubits, address)
    return circuit
