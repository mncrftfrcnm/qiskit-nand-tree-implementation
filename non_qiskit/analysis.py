from dataclasses import dataclass
from math import sqrt

from .profiles import BUILTIN_PROFILES, sparse_query_sampling_plan, verify_profile


@dataclass(frozen=True)
class ScalingRow:
    leaves: int
    depth: int
    query_steps: int
    oracle_calls: int
    square_root_leaves: float
    calls_per_square_root: float
    exact_margin: float
    query_margin: float
    shots_for_99_percent: int


def scaling_report():
    rows: list[ScalingRow] = []
    for leaves, profile in sorted(BUILTIN_PROFILES.items()):
        exact = verify_profile(profile, mode="exact")
        query = verify_profile(profile, mode="query")
        oracle_calls = 2 * profile.query_steps
        root = sqrt(leaves)
        rows.append(
            ScalingRow(
                leaves=leaves,
                depth=leaves.bit_length() - 1,
                query_steps=profile.query_steps,
                oracle_calls=oracle_calls,
                square_root_leaves=root,
                calls_per_square_root=oracle_calls / root,
                exact_margin=exact.separation_margin,
                query_margin=query.separation_margin,
                shots_for_99_percent=sparse_query_sampling_plan(
                    profile, confidence=0.99
                ).shots,
            )
        )
    return tuple(rows)
