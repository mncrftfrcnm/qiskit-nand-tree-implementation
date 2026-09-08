import pytest

from non_qiskit.exact_walk import run_continuous_walk
from non_qiskit.profiles import profile_for
from qiskit_implementation import evaluate_nand_tree


@pytest.mark.parametrize(
    "leaves",
    [
        (1, 0),
        (1, 1),
        (1, 0, 1, 1),
        (0, 1, 0, 0),
    ],
)
def test_qiskit_dense_walk_matches_non_qiskit_continuous_walk(leaves):
    profile = profile_for(len(leaves))

    qiskit_result = evaluate_nand_tree(leaves, mode="dense")
    reference_result = run_continuous_walk(
        leaves,
        runway_half_length=profile.runway_half_length,
        packet_length=profile.packet_length,
        time=profile.evolution_time,
    )

    assert qiskit_result.expected_value == reference_result.root_value
    assert qiskit_result.transmission_probability == pytest.approx(
        reference_result.transmission_probability, abs=1e-8
    )
    assert qiskit_result.predicted_value == int(
        reference_result.transmission_probability >= profile.threshold
    )
