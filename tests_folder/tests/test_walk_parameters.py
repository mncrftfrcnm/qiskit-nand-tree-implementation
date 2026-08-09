from types import SimpleNamespace

import pytest

from qiskit_implementation.walk_parameters import (
    WalkParameters,
    theoretical_parameters,
)


def test_walk_parameters_accept_valid_values():
    params = WalkParameters(
        runway_half_length=8,
        packet_length=5,
        evolution_time=2.5,
    )

    assert params.runway_half_length == 8
    assert params.packet_length == 5
    assert params.evolution_time == 2.5


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("runway_half_length", 0, ValueError),
        ("runway_half_length", -1, ValueError),
        ("runway_half_length", 1.5, TypeError),
        ("packet_length", 0, ValueError),
        ("packet_length", -1, ValueError),
        ("packet_length", 1.5, TypeError),
        ("evolution_time", -0.1, ValueError),
        ("evolution_time", float("inf"), ValueError),
    ],
)
def test_walk_parameters_reject_invalid_values(field, value, error):
    kwargs = {
        "runway_half_length": 8,
        "packet_length": 5,
        "evolution_time": 2.5,
    }
    kwargs[field] = value

    with pytest.raises(error):
        WalkParameters(**kwargs)


def test_packet_must_fit_on_left_runway():
    with pytest.raises(ValueError, match="packet_length"):
        WalkParameters(
            runway_half_length=2,
            packet_length=4,
            evolution_time=1.0,
        )


def test_from_profile_preserves_legacy_walk_values():
    legacy = SimpleNamespace(
        runway_half_length=6,
        packet_length=5,
        evolution_time=17.75,
        threshold=0.48,
        query_steps=16,
    )

    params = WalkParameters.from_profile(legacy)

    assert params == WalkParameters(
        runway_half_length=6,
        packet_length=5,
        evolution_time=17.75,
    )


@pytest.mark.parametrize("leaf_count", [0, 3, 5, 6, 7, 12])
def test_theoretical_parameters_require_power_of_two(leaf_count):
    with pytest.raises(ValueError, match="power of two"):
        theoretical_parameters(leaf_count, gamma=4.0)


def test_theoretical_parameters_scale_with_sqrt_n():
    p4 = theoretical_parameters(4, gamma=4.0)
    p16 = theoretical_parameters(16, gamma=4.0)

    assert p4.packet_length == 8
    assert p16.packet_length == 16


def test_theoretical_evolution_time_is_half_packet_scale():
    params = theoretical_parameters(16, gamma=4.0)

    assert params.evolution_time == params.packet_length / 2


def test_theoretical_runway_uses_l_squared_by_default():
    params = theoretical_parameters(4, gamma=4.0)

    assert params.runway_half_length == params.packet_length**2


def test_runway_factor_changes_only_runway_size():
    default = theoretical_parameters(4, gamma=4.0)
    wider = theoretical_parameters(4, gamma=4.0, runway_factor=2.0)

    assert wider.packet_length == default.packet_length
    assert wider.evolution_time == default.evolution_time
    assert wider.runway_half_length == 2 * default.runway_half_length
