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
    ]


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda path: path.stem)
def test_example_runs_successfully(example):
    completed = subprocess.run(
        [sys.executable, str(example)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Example completed successfully." in completed.stdout
