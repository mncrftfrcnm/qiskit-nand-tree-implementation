from collections.abc import Iterable
from dataclasses import dataclass
from itertools import product
from typing import Literal

from non_qiskit.profiles import AlgorithmProfile, SamplingPlan, profile_for, sampling_plan
from non_qiskit.tree import NandTree

from .evolution import QiskitWalkResult, run_qiskit_walk
from .query_walk import (
    QueryShotResult,
    QueryWalkResult,
    build_query_walk_circuit,
    sample_query_walk,
    sample_query_walk_adaptive,
    simulate_query_walk,
)

EvaluationMode = Literal["query", "dense"]


@dataclass(frozen=True)
class NandEvaluation:
    leaves: tuple[int, ...]
    expected_value: int
    predicted_value: int
    correct: bool
    mode: str
    profile: AlgorithmProfile
    transmission_probability: float
    query_count: int
    shot_result: QueryShotResult | None
    walk_result: QiskitWalkResult | QueryWalkResult | None
    sampling_plan: SamplingPlan | None = None

    @property
    def statevector_result(self) -> QueryWalkResult | None:
        """Compatibility view of the old query-only result field."""
        if isinstance(self.walk_result, QueryWalkResult):
            return self.walk_result
        return None


def evaluate_nand_tree(
    leaves: Iterable[int],
    *,
    mode: EvaluationMode = "query",
    shots: int | None = None,
    seed: int | None = None,
    confidence: float | None = None,
    adaptive: bool = False,
    min_shots: int = 256,
    max_shots: int = 8192,
    batch_shots: int = 256,
    profile: AlgorithmProfile | None = None,
) -> NandEvaluation:
    tree = NandTree(leaves)
    profile = profile or profile_for(tree.leaf_count)
    if profile.leaf_count != tree.leaf_count:
        raise ValueError("profile leaf count does not match the input")

    requested = sum(value is not None for value in (shots, confidence)) + int(adaptive)
    if requested > 1:
        raise ValueError("choose one of shots, confidence, or adaptive sampling")

    if mode == "dense":
        if requested:
            raise ValueError("sampling is available only in query mode")
        result = run_qiskit_walk(
            tree.leaves,
            runway_half_length=profile.runway_half_length,
            packet_length=profile.packet_length,
            time=profile.evolution_time,
            method="exact",
            threshold=profile.threshold,
        )
        return NandEvaluation(
            leaves=tree.leaves,
            expected_value=tree.root_value,
            predicted_value=result.predicted_value,
            correct=result.predicted_value == tree.root_value,
            mode=mode,
            profile=profile,
            transmission_probability=result.transmission_probability,
            query_count=0,
            shot_result=None,
            walk_result=result,
        )

    if mode != "query":
        raise ValueError(f"unknown evaluation mode: {mode}")

    graph, circuit = build_query_walk_circuit(
        tree.leaves,
        runway_half_length=profile.runway_half_length,
        packet_length=profile.packet_length,
        time=profile.evolution_time,
        steps=profile.query_steps,
    )

    plan = None
    if confidence is not None:
        plan = sampling_plan(profile, confidence=confidence, mode="query")
        shots = plan.shots

    if adaptive:
        sampled = sample_query_walk_adaptive(
            graph,
            circuit,
            steps=profile.query_steps,
            threshold=profile.threshold,
            min_shots=min_shots,
            max_shots=max_shots,
            batch_shots=batch_shots,
            seed=seed,
        )
        return _sampled_evaluation(tree, profile, sampled, plan)

    if shots is not None:
        sampled = sample_query_walk(
            graph,
            circuit,
            steps=profile.query_steps,
            threshold=profile.threshold,
            shots=shots,
            seed=seed,
        )
        return _sampled_evaluation(tree, profile, sampled, plan)

    result = simulate_query_walk(
        graph,
        circuit,
        steps=profile.query_steps,
        threshold=profile.threshold,
    )
    return NandEvaluation(
        leaves=tree.leaves,
        expected_value=tree.root_value,
        predicted_value=result.predicted_value,
        correct=result.predicted_value == tree.root_value,
        mode=mode,
        profile=profile,
        transmission_probability=result.transmission_probability,
        query_count=result.query_count,
        shot_result=None,
        walk_result=result,
    )


def _sampled_evaluation(
    tree: NandTree,
    profile: AlgorithmProfile,
    sampled: QueryShotResult,
    plan: SamplingPlan | None,
) -> NandEvaluation:
    return NandEvaluation(
        leaves=tree.leaves,
        expected_value=tree.root_value,
        predicted_value=sampled.predicted_value,
        correct=sampled.predicted_value == tree.root_value,
        mode="query",
        profile=profile,
        transmission_probability=sampled.transmission_probability,
        query_count=sampled.query_count,
        shot_result=sampled,
        walk_result=None,
        sampling_plan=plan,
    )


@dataclass(frozen=True)
class QiskitVerification:
    leaf_count: int
    inputs: int
    correct: int
    accuracy: float
    largest_zero_probability: float
    smallest_one_probability: float
    separation_margin: float
    failed_inputs: tuple[str, ...]
    shots: int | None

    @property
    def passed(self) -> bool:
        return self.correct == self.inputs


def verify_qiskit_profile(
    leaf_count: int,
    *,
    shots: int | None = None,
    seed: int | None = None,
) -> QiskitVerification:
    profile = profile_for(leaf_count)
    zeros: list[float] = []
    ones: list[float] = []
    failed: list[str] = []
    correct = 0

    for index, leaves in enumerate(product((0, 1), repeat=leaf_count)):
        result = evaluate_nand_tree(
            leaves,
            shots=shots,
            seed=None if seed is None else seed + index,
            profile=profile,
        )
        (ones if result.expected_value else zeros).append(result.transmission_probability)
        correct += int(result.correct)
        if not result.correct:
            failed.append("".join(str(bit) for bit in leaves))

    inputs = 1 << leaf_count
    largest_zero = max(zeros)
    smallest_one = min(ones)
    return QiskitVerification(
        leaf_count=leaf_count,
        inputs=inputs,
        correct=correct,
        accuracy=correct / inputs,
        largest_zero_probability=largest_zero,
        smallest_one_probability=smallest_one,
        separation_margin=smallest_one - largest_zero,
        failed_inputs=tuple(failed),
        shots=shots,
    )
