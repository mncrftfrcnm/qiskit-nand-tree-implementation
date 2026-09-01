# Dense and sparse backends

This file records the backend choices without repeating the algorithm overview
from the README.

## What the defaults mean

- `evaluate_nand_tree(...)` uses the dense full-Hamiltonian reference.
- `evaluate_nand_tree(..., mode="query")` uses the explicit query algorithm.
- Graph matrices use SciPy CSR storage unless `matrix_format="dense"` is set.
- Sparse query evaluation uses the matrix-free edge simulator when
  `simulation_backend="auto"`.
- `simulation_backend="qiskit"` runs the complete Qiskit statevector circuit.

These switches are independent. Sparse graph storage does not by itself mean
that the high-level query algorithm was selected.

## Numerical differences

Changing an exact non-Qiskit graph from dense storage to CSR changes only the
storage format. Results agree within floating-point tolerance.

The structured query circuit is different. It applies individual driver-edge
rotations because compiling one full Hamiltonian unitary does not scale. Driver
edges share vertices, so the ordered edge formula is approximate. `driver_reps`
controls that approximation; the default is four. Oracle leaf edges are
disjoint, so each oracle segment is exact.

The deterministic query classifier passes exhaustive checks on the bundled 2-,
4-, and 8-leaf profiles. Custom walk parameters still need calibration. Finite
shots are probabilistic regardless of how the underlying state was calculated.
The confidence planner stores separate threshold gaps for the sparse backend at
`driver_reps=4`; other sparse configurations are rejected until calibrated.

## Edge simulator and Qiskit

```python
evaluate_nand_tree(leaves, mode="query")
evaluate_nand_tree(
    leaves,
    mode="query",
    simulation_backend="qiskit",
)
```

The first call applies the circuit's ordered two-level rotations directly to the
position vector. The second constructs and simulates the full register-level
circuit. Small-tree tests compare the two complete states.

The edge path is useful for development and calibration. It is not a hardware
speedup and does not remove the gates from the circuit definition.

One development-machine run gave the following end-to-end times for a single
calibrated input:

| Leaves | Edge simulator | Qiskit statevector |
|---:|---:|---:|
| 2 | 0.0015 s | 0.364 s |
| 4 | 0.0022 s | 0.992 s |
| 8 | 0.0043 s | 24.56 s |

The probability differences were between `1e-15` and `3e-11`. These are rough
measurements, not benchmarks; hardware and dependency versions matter.

## Memory and gate growth

For `N` leaves and runway half-length `R`, the graph has

$$
V=3N+2R
$$

vertices. The full query circuit needs approximately

$$
q=\left\lceil\log_2(3N+2R)\right\rceil+\log_2N+1
$$

qubits. Qiskit statevector memory is therefore proportional to `2**q`.

The fixed driver has `2N + 2R - 1` edges. With `d=driver_reps`, one query step
contains roughly

$$
4d(2N+2R-1)+N
$$

edge rotations before decomposition. The edge simulator handles those rotations
in linear memory, while the Qiskit circuit still pays their gate cost.

For an all-one input with runway half-length 8, the three CSR graph matrices use
about 181 KiB at 1,024 leaves. Equivalent float64 dense matrices use about
218 MiB. These figures exclude Python object overhead and any statevector.

Sparse storage does not remove:

- full-register statevector growth;
- the linear-size truth-table oracle;
- multi-controlled-gate decomposition;
- product-formula repetitions;
- exhaustive calibration over `2**N` inputs.

Above eight leaves, provide a `NandExperimentConfig` and validate its threshold
and step count. Faster simulation does not perform that calibration for the user.
