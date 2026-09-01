from collections.abc import Iterable

from non_qiskit.tree import NandTree
from ._imports import qiskit_api


def build_reversible_nand_circuit(
    leaves: Iterable[int],
    *,
    clean_ancillas: bool = True,
    measure: bool = False,
):
    """Build the reversible NAND circuit."""

    tree = NandTree(leaves)
    QuantumCircuit = qiskit_api().QuantumCircuit

    output = tree.node_count if clean_ancillas else 0
    circuit = QuantumCircuit(tree.node_count + int(clean_ancillas), int(measure), name="nand")

    for leaf, bit in enumerate(tree.leaves):
        if bit:
            circuit.x(tree.leaf_node(leaf))

    for node in range(tree.internal_count - 1, -1, -1):
        left, right = tree.children(node)
        circuit.ccx(left, right, node)
        circuit.x(node)

    if clean_ancillas:
        circuit.cx(0, output)
        for node in range(tree.internal_count):
            left, right = tree.children(node)
            circuit.x(node)
            circuit.ccx(left, right, node)

    if measure:
        circuit.measure(output, 0)
    return circuit
