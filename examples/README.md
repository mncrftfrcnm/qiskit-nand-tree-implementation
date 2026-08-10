# Examples

Install the project first:

```bash
python -m pip install -e ".[dev]"
```

Then run any example from the repository root:

```bash
python examples/01_basic_evaluation.py
```

| Example | Demonstrates |
|---|---|
| `01_basic_evaluation.py` | A calibrated query-walk evaluation through the public API. |
| `02_compare_qiskit_and_non_qiskit.py` | Agreement between the Qiskit dense circuit and the non-Qiskit continuous-time reference. |
| `03_custom_experiment_config.py` | An explicit walk, query-step, and threshold configuration. |
| `04_sampling_and_confidence.py` | Fixed-shot, confidence-derived, and adaptive sampling. |
| `05_oracle_and_workspace_cleanup.py` | Oracle involution, query count, and clean temporary workspace. |
