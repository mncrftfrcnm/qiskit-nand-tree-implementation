from __future__ import annotations

from dataclasses import asdict, dataclass

from non_qiskit.profiles import profile_for

from ._imports import qiskit_api
from .query_walk import build_query_walk_circuit


@dataclass(frozen=True)
class CircuitResources:
    leaf_count: int
    graph_vertices: int
    logical_qubits: int
    logical_depth: int
    logical_gates: int
    logical_two_qubit_gates: int
    transpiled_depth: int
    transpiled_gates: int
    transpiled_two_qubit_gates: int
    query_steps: int
    oracle_calls: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def _two_qubit_gate_count(circuit) -> int:
    return sum(1 for instruction in circuit.data if len(instruction.qubits) == 2)


def analyze_query_resources(
    leaf_count: int,
    *,
    optimization_level: int = 1,
    driver_reps: int = 4,
) -> CircuitResources:
    """Build and transpile one calibrated query circuit and report its resources."""

    profile = profile_for(leaf_count)
    leaves = (0,) * leaf_count
    graph, circuit = build_query_walk_circuit(
        leaves,
        runway_half_length=profile.walk.runway_half_length,
        packet_length=profile.walk.packet_length,
        time=profile.walk.evolution_time,
        steps=profile.query_steps,
        driver_reps=driver_reps,
    )
    transpiled = qiskit_api().transpile(circuit, optimization_level=optimization_level)

    return CircuitResources(
        leaf_count=leaf_count,
        graph_vertices=graph.size,
        logical_qubits=circuit.num_qubits,
        logical_depth=circuit.depth(),
        logical_gates=circuit.size(),
        logical_two_qubit_gates=_two_qubit_gate_count(circuit),
        transpiled_depth=transpiled.depth(),
        transpiled_gates=transpiled.size(),
        transpiled_two_qubit_gates=_two_qubit_gate_count(transpiled),
        query_steps=profile.query_steps,
        oracle_calls=2 * profile.query_steps,
    )
