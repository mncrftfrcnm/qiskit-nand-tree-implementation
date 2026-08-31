import json

import pytest

from main import main
from non_qiskit.calibration import calibrate_profile
from non_qiskit.profiles import verify_profile


def _calibrate_two_leaf_profile(**overrides):
    arguments = {
        "leaf_count": 2,
        "runway_values": (2,),
        "packet_values": (3,),
        "time_values": (7.8,),
        "step_values": (1, 2),
    }
    arguments.update(overrides)
    return calibrate_profile(**arguments)


def test_calibration_recovers_a_separating_two_leaf_profile():
    result = _calibrate_two_leaf_profile(step_values=(2, 1, 2, 0, -1))
    exact = verify_profile(result.profile, mode="exact")
    query = verify_profile(result.profile, mode="query")

    assert result.profile.leaf_count == 2
    assert result.profile.runway_half_length == 2
    assert result.profile.packet_length == 3
    assert result.profile.evolution_time == pytest.approx(7.8)
    assert result.profile.query_steps == 2
    assert result.profile.threshold == pytest.approx(
        0.5 * (exact.largest_zero_probability + exact.smallest_one_probability)
    )

    assert result.exact_accuracy == pytest.approx(exact.accuracy)
    assert result.query_accuracy == pytest.approx(query.accuracy)
    assert result.exact_margin == pytest.approx(exact.separation_margin)
    assert result.query_margin == pytest.approx(query.separation_margin)
    assert result.exact_margin > 0
    assert result.query_margin > 0


def test_calibration_keeps_the_best_available_imperfect_query_candidate():
    result = _calibrate_two_leaf_profile(step_values=(1,))

    assert result.profile.query_steps == 1
    assert 0 < result.query_accuracy < 1


def test_packet_candidates_can_be_a_one_shot_iterable():
    baseline = _calibrate_two_leaf_profile(
        runway_values=(3, 2),
        packet_values=(2, 3, 4),
        step_values=(2,),
    )
    generated = _calibrate_two_leaf_profile(
        runway_values=(3, 2),
        packet_values=iter((2, 3, 4)),
        step_values=(2,),
    )

    assert generated.profile == baseline.profile
    assert generated.exact_margin == pytest.approx(baseline.exact_margin)
    assert generated.query_margin == pytest.approx(baseline.query_margin)


@pytest.mark.parametrize("leaf_count", (0, 3, 6))
def test_calibration_requires_a_power_of_two_leaf_count(leaf_count):
    with pytest.raises(ValueError, match="power of two"):
        _calibrate_two_leaf_profile(leaf_count=leaf_count)


def test_calibration_rejects_leaf_counts_above_exhaustive_limit():
    with pytest.raises(ValueError, match="at most 8 leaves"):
        _calibrate_two_leaf_profile(leaf_count=16)


@pytest.mark.parametrize(
    "time_values",
    (
        (),
        (0.0,),
        (-0.1,),
        (1.0, 0.0),
        (float("nan"),),
        (float("inf"),),
        (float("-inf"),),
    ),
)
def test_calibration_requires_finite_positive_times(time_values):
    with pytest.raises(ValueError, match="finite positive values"):
        _calibrate_two_leaf_profile(time_values=time_values)


def test_calibration_rejects_a_grid_without_compatible_packets():
    with pytest.raises(RuntimeError, match="did not separate"):
        _calibrate_two_leaf_profile(packet_values=(0, 4))


def test_calibration_rejects_a_nonseparating_grid():
    with pytest.raises(RuntimeError, match="did not separate"):
        _calibrate_two_leaf_profile(time_values=(1e-12,))


def test_calibration_requires_a_positive_query_step_candidate():
    with pytest.raises(RuntimeError, match="no query-step candidates"):
        _calibrate_two_leaf_profile(step_values=(0, -1))


def test_calibrate_command_prints_and_writes_the_same_profile(tmp_path, capsys):
    output_path = tmp_path / "calibration.json"

    assert main(
        [
            "calibrate",
            "--leaf-count",
            "2",
            "--runways",
            "2",
            "--packets",
            "3",
            "--time-start",
            "7.8",
            "--time-stop",
            "7.8",
            "--time-points",
            "1",
            "--steps",
            "1,2",
            "--output",
            str(output_path),
        ]
    ) == 0

    printed = json.loads(capsys.readouterr().out)
    written = json.loads(output_path.read_text())

    assert written == printed
    assert written["profile"]["leaf_count"] == 2
    assert written["profile"]["query_steps"] == 2
    assert written["exact_accuracy"] == pytest.approx(1.0)
    assert written["query_accuracy"] == pytest.approx(1.0)
