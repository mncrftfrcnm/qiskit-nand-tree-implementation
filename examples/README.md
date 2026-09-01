# Runnable examples

Install the development dependencies, then run the scripts from the repository
root:

```bash
python -m pip install -e ".[dev]"
for file in examples/*.py; do python "$file"; done
```


| Script | What it checks |
|---|---|
| `01_basic_evaluation.py` | Dense and query evaluation through the public API |
| `02_compare_qiskit_and_non_qiskit.py` | Both modes against the exact non-Qiskit walk |
| `03_custom_experiment_config.py` | The same explicit experiment in both modes |
| `04_sampling_and_confidence.py` | Dense/query deterministic agreement, then query sampling |
| `05_oracle_and_workspace_cleanup.py` | Dense/query agreement plus query-oracle cleanup |
| `06_plot_calibration.py` | Dense and query probabilities for all four-leaf inputs |

Examples 04 and 05 include query-only operations because dense mode does not use
the explicit bit oracle or finite-shot API.
