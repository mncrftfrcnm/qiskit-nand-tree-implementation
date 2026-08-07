from functools import lru_cache
from types import SimpleNamespace


@lru_cache(maxsize=1)
def qiskit_api() -> SimpleNamespace:
    from qiskit import QuantumCircuit, transpile
    from qiskit.circuit.library import (
        HamiltonianGate,
        MCXGate,
        PauliEvolutionGate,
        ZGate,
        phase_estimation,
    )
    from qiskit.primitives import StatevectorSampler
    from qiskit.quantum_info import Operator, SparsePauliOp, Statevector
    from qiskit.synthesis import LieTrotter, SuzukiTrotter

    return SimpleNamespace(
        HamiltonianGate=HamiltonianGate,
        LieTrotter=LieTrotter,
        MCXGate=MCXGate,
        Operator=Operator,
        PauliEvolutionGate=PauliEvolutionGate,
        QuantumCircuit=QuantumCircuit,
        SparsePauliOp=SparsePauliOp,
        Statevector=Statevector,
        StatevectorSampler=StatevectorSampler,
        SuzukiTrotter=SuzukiTrotter,
        ZGate=ZGate,
        phase_estimation=phase_estimation,
        transpile=transpile,
    )
