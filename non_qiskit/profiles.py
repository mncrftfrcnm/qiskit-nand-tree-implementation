from dataclasses import asdict, dataclass
from itertools import product
from math import ceil, log
from typing import Literal

from .exact_walk import run_continuous_walk
from .graph import build_walk_graph
from .product_formula import run_symmetric_split
from .tree import NandTree


@dataclass(frozen=True)
class AlgorithmProfile:
    leaf_count: int
    runway_half_length: int
    packet_length: int
    evolution_time: float
    threshold: float
    query_steps: int

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


@dataclass(frozen=True)
class ProfileVerification:
    leaf_count: int
    mode: str
    inputs: int
    correct: int
    accuracy: float
    largest_zero_probability: float
    smallest_one_probability: float
    separation_margin: float
    threshold: float

    @property
    def passed(self) -> bool:
        return self.correct == self.inputs and self.separation_margin > 0

    @property
    def threshold_gap(self) -> float:
        return min(
            self.threshold - self.largest_zero_probability,
            self.smallest_one_probability - self.threshold,
        )


@dataclass(frozen=True)
class SamplingPlan:
    confidence: float
    failure_probability: float
    threshold_gap: float
    shots: int
    mode: str


# These are finite-size calibration results, not constants from the NAND-tree papers.
# calibrate_profile() searches runway length, packet length, and evolution time using
# every possible input for the requested tree size. For each candidate it measures
# the gap between the largest transmission probability for root=0 and the smallest
# transmission probability for root=1. The threshold is the midpoint of that gap.
#
# After choosing the best exact-walk candidate, calibration tries increasing symmetric
# product-formula step counts and keeps the first one that classifies every input with
# a positive separation margin. EXPERIMENTS.md records the current values and commands
# used to reproduce the checks.
BUILTIN_PROFILES: dict[int, AlgorithmProfile] = {
    2: AlgorithmProfile(
        leaf_count=2,
        runway_half_length=2,
        packet_length=3,
        evolution_time=7.8,
        threshold=0.37,
        query_steps=2,
    ),
    4: AlgorithmProfile(
        leaf_count=4,
        runway_half_length=2,
        packet_length=3,
        evolution_time=9.4,
        threshold=0.16,
        query_steps=8,
    ),
    8: AlgorithmProfile(
        leaf_count=8,
        runway_half_length=6,
        packet_length=5,
        evolution_time=17.75,
        threshold=0.48,
        query_steps=16,
    ),
}


def profile_for(leaf_count: int) -> AlgorithmProfile:
    profile = BUILTIN_PROFILES.get(leaf_count)
    if profile is None:
        supported = ", ".join(str(value) for value in sorted(BUILTIN_PROFILES))
        raise ValueError(
            f"no built-in profile for {leaf_count} leaves; supported sizes: {supported}"
        )
    return profile


def verify_profile(
    profile: AlgorithmProfile,
    *,
    mode: Literal["exact", "query"] = "query",
) -> ProfileVerification:
    zeros: list[float] = []
    ones: list[float] = []
    correct = 0

    for leaves in product((0, 1), repeat=profile.leaf_count):
        root = NandTree(leaves).root_value
        if mode == "exact":
            probability = run_continuous_walk(
                leaves,
                runway_half_length=profile.runway_half_length,
                packet_length=profile.packet_length,
                time=profile.evolution_time,
            ).transmission_probability
        elif mode == "query":
            graph = build_walk_graph(leaves, runway_half_length=profile.runway_half_length)
            probability = run_symmetric_split(
                graph,
                packet_length=profile.packet_length,
                time=profile.evolution_time,
                steps=profile.query_steps,
            ).transmission_probability
        else:
            raise ValueError(f"unknown verification mode: {mode}")

        (ones if root else zeros).append(probability)
        correct += int((probability >= profile.threshold) == bool(root))

    largest_zero = max(zeros)
    smallest_one = min(ones)
    inputs = 1 << profile.leaf_count
    return ProfileVerification(
        leaf_count=profile.leaf_count,
        mode=mode,
        inputs=inputs,
        correct=correct,
        accuracy=correct / inputs,
        largest_zero_probability=largest_zero,
        smallest_one_probability=smallest_one,
        separation_margin=smallest_one - largest_zero,
        threshold=profile.threshold,
    )


def sampling_plan(
    profile: AlgorithmProfile,
    *,
    confidence: float = 0.99,
    mode: Literal["exact", "query"] = "query",
) -> SamplingPlan:
    """Return a Hoeffding shot bound for the calibrated finite model."""

    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")

    verification = verify_profile(profile, mode=mode)
    gap = verification.threshold_gap
    if gap <= 0:
        raise ValueError("the profile threshold does not separate the two outputs")

    failure = 1 - confidence
    shots = ceil(log(1 / failure) / (2 * gap * gap))
    return SamplingPlan(
        confidence=confidence,
        failure_probability=failure,
        threshold_gap=gap,
        shots=shots,
        mode=mode,
    )
