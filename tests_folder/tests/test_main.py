import pytest

from main import main, parse_leaves


def test_parse_leaves_accepts_common_formats():
    assert parse_leaves("1011") == (1, 0, 1, 1)
    assert parse_leaves("1,0,1,1") == (1, 0, 1, 1)


def test_parse_leaves_rejects_unbalanced_size():
    with pytest.raises(ValueError):
        parse_leaves("101")


def test_classical_command_runs(capsys):
    assert main(["classical", "--leaves", "1011"]) == 0
    assert '"bottom_up"' in capsys.readouterr().out


def test_verify_command_runs(capsys):
    assert main(["verify", "--leaf-count", "2", "--mode", "both"]) == 0
    output = capsys.readouterr().out
    assert '"accuracy": 1.0' in output
    assert '"query_steps": 2' in output


def test_scaling_command_runs(capsys):
    assert main(["scaling"]) == 0
    output = capsys.readouterr().out
    assert '"oracle_calls": 4' in output
    assert '"shots_for_99_percent": 60' in output


def test_convergence_command_runs(capsys):
    assert main(
        [
            "convergence",
            "--leaves",
            "10",
            "--runway",
            "3",
            "--packet",
            "3",
            "--time",
            "0.7",
            "--steps",
            "1,4",
        ]
    ) == 0
    output = capsys.readouterr().out
    assert '"steps": 1' in output
    assert '"steps": 4' in output
