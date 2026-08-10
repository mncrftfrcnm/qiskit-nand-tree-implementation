import pytest

from non_qiskit.profiles import profile_for
from qiskit_implementation import NandExperimentConfig, WalkParameters, evaluate_nand_tree


def test_experiment_config_from_profile_matches_default_query_evaluation():
    leaves = (1, 0)
    experiment = NandExperimentConfig.from_profile(profile_for(len(leaves)))

    configured = evaluate_nand_tree(leaves, experiment=experiment)
    default = evaluate_nand_tree(leaves)

    assert configured.profile is experiment
    assert configured.correct == default.correct
    assert configured.predicted_value == default.predicted_value
    assert configured.query_count == default.query_count
    assert configured.transmission_probability == pytest.approx(
        default.transmission_probability, abs=1e-10
    )


def test_custom_experiment_is_used_for_dense_evaluation():
    profile = profile_for(2)
    experiment = NandExperimentConfig.from_profile(profile)

    result = evaluate_nand_tree((1, 0), mode="dense", experiment=experiment)

    assert result.profile is experiment
    assert result.correct
    assert result.query_count == 0


def test_profile_and_experiment_are_mutually_exclusive():
    profile = profile_for(2)
    experiment = NandExperimentConfig.from_profile(profile)

    with pytest.raises(ValueError, match="either profile or experiment"):
        evaluate_nand_tree((1, 0), profile=profile, experiment=experiment)


def test_confidence_sampling_requires_a_calibrated_profile():
    experiment = NandExperimentConfig.from_profile(profile_for(2))

    with pytest.raises(ValueError, match="calibrated profile"):
        evaluate_nand_tree((1, 0), experiment=experiment, confidence=0.99)


@pytest.mark.parametrize(
    ("query_steps", "threshold", "error"),
    [
        (0, 0.5, ValueError),
        (True, 0.5, TypeError),
        (2, -0.01, ValueError),
        (2, 1.01, ValueError),
        (2, float("nan"), ValueError),
        (2, float("inf"), ValueError),
        (2, True, TypeError),
    ],
)
def test_experiment_config_rejects_invalid_classifier_settings(
    query_steps, threshold, error
):
    walk = WalkParameters(runway_half_length=2, packet_length=3, evolution_time=7.8)

    with pytest.raises(error):
        NandExperimentConfig(walk=walk, query_steps=query_steps, threshold=threshold)
