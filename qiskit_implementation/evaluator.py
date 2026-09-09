from collections.abc import Iterable
from dataclasses import dataclass

from non_qiskit.graph import MatrixFormat
from non_qiskit.tree import NandTree

from .classifier import EvaluationMode, NandEvaluation, evaluate_nand_tree
from .evolution import CircuitMethod, QiskitWalkResult, run_qiskit_walk
from .phase_probe import PhaseProbeResult, run_phase_probe
from .query_walk import EvolutionBackend, QueryWalkResult, SimulationBackend, run_query_walk


@dataclass(frozen=True)
class QuantumEvaluationResult:
    leaves: tuple[int, ...]
    classical_value: int
    walk: QiskitWalkResult | QueryWalkResult
    phase_probe: PhaseProbeResult | None = None


class QuantumNandEvaluator:
    def __init__(
        self,
        leaves: Iterable[int],
        *,
        runway_half_length: int = 6,
        packet_length: int = 4,
        matrix_format: MatrixFormat = "sparse",
        evolution_backend: EvolutionBackend = "sparse",
        simulation_backend: SimulationBackend = "auto",
    ):
        tree = NandTree(leaves)
        self.leaves = tree.leaves
        self.runway_half_length = runway_half_length
        self.packet_length = packet_length
        self.matrix_format = matrix_format
        self.evolution_backend = evolution_backend
        self.simulation_backend = simulation_backend

    @property
    def classical_value(self) -> int:
        return NandTree(self.leaves).root_value

    def evaluate(
        self,
        *,
        mode: EvaluationMode = "dense",
        shots: int | None = None,
        seed: int | None = None,
    ) -> NandEvaluation:
        return evaluate_nand_tree(
            self.leaves,
            mode=mode,
            shots=shots,
            seed=seed,
            matrix_format=self.matrix_format,
            evolution_backend=self.evolution_backend,
            simulation_backend=self.simulation_backend,
        )

    # Kept as a compatibility alias for code written against versions <= 0.6.2.
    automatic = evaluate

    def dense_walk(
        self,
        *,
        time: float = 2.0,
        method: CircuitMethod = "exact",
        reps: int = 1,
        threshold: float = 0.5,
    ) -> QuantumEvaluationResult:
        walk = run_qiskit_walk(
            self.leaves,
            runway_half_length=self.runway_half_length,
            packet_length=self.packet_length,
            time=time,
            method=method,
            reps=reps,
            threshold=threshold,
            matrix_format=self.matrix_format,
            evolution_backend=self.evolution_backend,
        )
        return QuantumEvaluationResult(self.leaves, self.classical_value, walk)

    def query_walk(
        self,
        *,
        time: float = 2.0,
        steps: int = 2,
        threshold: float = 0.5,
        driver_reps: int = 4,
    ) -> QuantumEvaluationResult:
        walk = run_query_walk(
            self.leaves,
            runway_half_length=self.runway_half_length,
            packet_length=self.packet_length,
            time=time,
            steps=steps,
            threshold=threshold,
            matrix_format=self.matrix_format,
            evolution_backend=self.evolution_backend,
            simulation_backend=self.simulation_backend,
            driver_reps=driver_reps,
        )
        return QuantumEvaluationResult(self.leaves, self.classical_value, walk)

    def probe(
        self,
        *,
        evaluation_qubits: int = 4,
        evolution_time: float = 0.25,
    ) -> PhaseProbeResult:
        return run_phase_probe(
            self.leaves,
            runway_half_length=self.runway_half_length,
            packet_length=self.packet_length,
            evaluation_qubits=evaluation_qubits,
            evolution_time=evolution_time,
            matrix_format=self.matrix_format,
            evolution_backend=self.evolution_backend,
        )

    def run(
        self,
        *,
        time: float = 2.0,
        method: CircuitMethod = "exact",
        reps: int = 1,
        threshold: float = 0.5,
        include_phase_probe: bool = False,
        evaluation_qubits: int = 4,
    ) -> QuantumEvaluationResult:
        result = self.dense_walk(time=time, method=method, reps=reps, threshold=threshold)
        if not include_phase_probe:
            return result
        return QuantumEvaluationResult(
            result.leaves,
            result.classical_value,
            result.walk,
            self.probe(evaluation_qubits=evaluation_qubits),
        )
