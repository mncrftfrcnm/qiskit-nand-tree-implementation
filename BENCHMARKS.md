# Benchmarks and experiment artifacts

The repository has two small reproducibility workflows. They are deliberately kept separate from the normal test suite so timing measurements are not mixed with correctness checks.

## Scaling benchmark

Run:

```bash
python -m benchmarks.scaling
```

By default this measures sparse graph construction and matrix-free query simulation for 2, 4, 8, 16, and 32 leaves. The parameter family is fixed across sizes so the results are useful as a scaling comparison rather than a per-size calibration.

The command writes:

```text
results/scaling/
├── scaling.csv
├── scaling.json
├── runtime_seconds.svg
├── peak_memory_mib.svg
├── qubits.svg
└── oracle_calls.svg
```

Each row includes the number of graph vertices, position/address/total query qubits, product-formula steps, oracle calls, graph-build time, simulation time, peak Python memory measured by `tracemalloc`, and the resulting transmission probability.

For a different range:

```bash
python -m benchmarks.scaling \
  --leaves 2,4,8,16,32,64 \
  --gamma 1.5 \
  --runway-factor 0.5 \
  --output results/scaling
```

These timings are development measurements, not hardware runtime estimates. They depend on the machine, Python build, dependency versions, and background load.

## Circuit resource report

The public helper `analyze_query_resources()` builds a calibrated query circuit and reports logical and transpiled resources:

```python
from qiskit_implementation import analyze_query_resources

resources = analyze_query_resources(4)
print(resources)
```

It records logical qubits, circuit depth, gate count, two-qubit gate count, transpiled depth/gate counts, product-formula steps, and abstract oracle calls. The oracle-call number is intentionally kept separate from transpiled gate counts.

## Calibrated profile artifacts

Regenerate the profile verification data and separation plot with:

```bash
python -m benchmarks.profile_artifacts
```

This exhaustively rechecks the built-in 2-, 4-, and 8-leaf profiles in the exact and symmetric-query reference modes and writes CSV, JSON, and SVG outputs under `results/profiles/`.

The tracked files in `results/profiles/` are snapshots of the current experiment table in `EXPERIMENTS.md`. When a profile, walk implementation, or product formula changes, regenerate these artifacts in the same commit as the code change.

## Reproducibility notes

For benchmark comparisons, record the Python, Qiskit, NumPy, and SciPy versions alongside any published numbers. Avoid comparing wall-clock measurements from different machines as though they were controlled experiments. Resource counts and exhaustive classification results are more portable than timings.
