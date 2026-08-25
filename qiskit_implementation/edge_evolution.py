"""Structured graph-edge evolution without full Hamiltonian matrices.

The graph Hamiltonian is minus the adjacency matrix.  For one edge ``(u, v)``,
evolution is therefore a two-level rotation in the span of ``|u>`` and ``|v>``.
This module synthesizes that rotation directly on the binary position register.
"""

from collections.abc import Iterable, Sequence

from non_qiskit.graph import NandWalkGraph

from ._imports import qiskit_api
from .hamiltonian import qubits_for_dimension


def append_two_level_edge_rotation(
    circuit,
    position_qubits: Sequence[int],
    left_vertex: int,
    right_vertex: int,
    *,
    time: float,
    controls: Sequence[int] = (),
) -> None:
    """Append ``exp(i time (|u><v| + |v><u|))``.

    An affine reversible basis change maps ``u`` and ``v`` to two basis states
    that differ only on one pivot qubit. A multi-controlled RX then performs
    the desired two-level rotation, after which the basis change is undone.
    No ``2**q`` square matrix is constructed.
    """

    qubits = tuple(position_qubits)
    external_controls = tuple(controls)
    dimension = 1 << len(qubits)
    if not 0 <= left_vertex < dimension or not 0 <= right_vertex < dimension:
        raise ValueError("edge vertex does not fit in the position register")
    if left_vertex == right_vertex:
        raise ValueError("an edge must connect two different vertices")
    if set(qubits) & set(external_controls):
        raise ValueError("position and control qubits must be disjoint")

    difference = left_vertex ^ right_vertex
    pivot = (difference & -difference).bit_length() - 1
    pivot_qubit = qubits[pivot]

    offset_bits = [bit for bit in range(len(qubits)) if (left_vertex >> bit) & 1]
    difference_bits = [
        bit for bit in range(len(qubits)) if bit != pivot and (difference >> bit) & 1
    ]
    zero_controls = [qubits[bit] for bit in range(len(qubits)) if bit != pivot]

    for bit in offset_bits:
        circuit.x(qubits[bit])
    for bit in difference_bits:
        circuit.cx(pivot_qubit, qubits[bit])
    for qubit in zero_controls:
        circuit.x(qubit)

    rotation = qiskit_api().RXGate(-2.0 * float(time))
    all_controls = [*external_controls, *zero_controls]
    if all_controls:
        circuit.append(
            rotation.control(len(all_controls), annotated=False),
            [*all_controls, pivot_qubit],
        )
    else:
        circuit.append(rotation, [pivot_qubit])

    for qubit in reversed(zero_controls):
        circuit.x(qubit)
    for bit in reversed(difference_bits):
        circuit.cx(pivot_qubit, qubits[bit])
    for bit in reversed(offset_bits):
        circuit.x(qubits[bit])


def build_edge_evolution_gate(
    graph: NandWalkGraph,
    edges: Iterable[tuple[int, int]],
    *,
    time: float,
    reps: int = 1,
    symmetric: bool = True,
    controlled: bool = False,
    name: str = "edge_evolution",
):
    """Build a product-formula evolution from structured edge rotations."""

    if reps < 1:
        raise ValueError("reps must be at least one")

    edge_list = tuple(edges)
    position_bits = qubits_for_dimension(graph.size)
    control_count = int(controlled)
    circuit = qiskit_api().QuantumCircuit(control_count + position_bits, name=name)
    controls = [0] if controlled else []
    position = list(range(control_count, control_count + position_bits))
    segment_time = float(time) / reps

    for _ in range(reps):
        if symmetric:
            for left, right in edge_list:
                append_two_level_edge_rotation(
                    circuit,
                    position,
                    left,
                    right,
                    time=segment_time / 2,
                    controls=controls,
                )
            for left, right in reversed(edge_list):
                append_two_level_edge_rotation(
                    circuit,
                    position,
                    left,
                    right,
                    time=segment_time / 2,
                    controls=controls,
                )
        else:
            for left, right in edge_list:
                append_two_level_edge_rotation(
                    circuit,
                    position,
                    left,
                    right,
                    time=segment_time,
                    controls=controls,
                )
    return circuit.to_gate()


def build_driver_edge_gate(
    graph: NandWalkGraph,
    *,
    time: float,
    reps: int = 1,
):
    return build_edge_evolution_gate(
        graph,
        graph.driver_edges(),
        time=time,
        reps=reps,
        symmetric=True,
        name="sparse_driver",
    )


def build_oracle_edge_gate(
    graph: NandWalkGraph,
    *,
    time: float,
    controlled: bool = False,
):
    """Build exact evolution for the graph's present, disjoint oracle edges."""

    return build_edge_evolution_gate(
        graph,
        graph.oracle_edges(),
        time=time,
        reps=1,
        symmetric=False,
        controlled=controlled,
        name="sparse_oracle",
    )


def build_all_leaf_edge_gate(
    graph: NandWalkGraph,
    *,
    time: float,
    controlled: bool = True,
):
    """Build evolution for every possible leaf edge, optionally controlled."""

    edges = (
        (
            graph.vertex_index("tree", graph.tree.leaf_node(leaf)),
            graph.vertex_index("oracle", leaf),
        )
        for leaf in range(graph.tree.leaf_count)
    )
    return build_edge_evolution_gate(
        graph,
        edges,
        time=time,
        reps=1,
        symmetric=False,
        controlled=controlled,
        name="sparse_leaf_edges",
    )
