import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = sorted((PROJECT_ROOT / "examples").glob("*.py"))


def test_examples_folder_contains_the_documented_scripts():
    assert [example.name for example in EXAMPLES] == [
        "01_basic_evaluation.py",
        "02_compare_qiskit_and_non_qiskit.py",
        "03_custom_experiment_config.py",
        "04_sampling_and_confidence.py",
        "05_oracle_and_workspace_cleanup.py",
        "06_plot_calibration.py",
    ]


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda path: path.stem)
def test_example_runs_successfully(example, tmp_path):
    command = [sys.executable, str(example)]
    output_path = None

    if example.name == "06_plot_calibration.py":
        pytest.importorskip("matplotlib")
        output_path = tmp_path / "nested" / "calibration.png"
        command.extend(("--output", str(output_path)))

    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Example completed successfully." in completed.stdout
    if output_path is not None:
        assert output_path.is_file()
        assert output_path.stat().st_size > 0
