# Sparse-first backend notes

## Defaults

- `build_walk_graph(..., matrix_format="sparse")` stores adjacency matrices as CSR.
- Non-Qiskit exact evolution uses sparse `expm_multiply`.
- Non-Qiskit split evolution applies sparse exponentials directly to state vectors.
- `build_query_walk_circuit(..., evolution_backend="sparse")` uses structured edge rotations.
- `build_evolution_circuit(..., method="edge")` is the sparse full-walk circuit mode.
- `build_phase_probe_circuit(..., evolution_backend="sparse")` uses controlled edge rotations.
- `evaluate_nand_tree(..., simulation_backend="auto")` uses the matrix-free edge simulator.

## Dense compatibility

Dense behavior remains available with:

```python
build_walk_graph(leaves, matrix_format="dense")
build_query_walk_circuit(
    leaves,
    matrix_format="dense",
    evolution_backend="dense",
)
build_evolution_circuit(graph, method="exact")
```

The dense Qiskit path pads a Hamiltonian to a power-of-two dimension and should
only be used for small reference comparisons.

## Accuracy distinction

Changing graph storage from dense to sparse does not change the Hamiltonian or
the exact non-Qiskit result, up to floating-point tolerance.

Structured Qiskit driver evolution introduces an additional product formula over
individual edges because driver edges do not all commute. `driver_reps` controls
this approximation in the query circuit; its sparse default is four, which passes
the bundled 2- and 4-leaf classifier profiles. `reps` controls the edge formula in
the full `method="edge"` circuit.

Oracle leaf edges are pairwise disjoint, so their structured edge evolution is
exact for each oracle segment.

## Fast simulation versus Qiskit execution

The sparse query block uncomputes its address and value registers after every
step. The `edge` simulator therefore applies the same ordered two-level driver
rotations and present oracle edges directly to the position vector. Small-tree
tests compare its complete state against Qiskit's statevector.

```python
evaluate_nand_tree(leaves)  # auto -> edge for sparse evolution
evaluate_nand_tree(leaves, simulation_backend="qiskit")
```

The first path is fast and matrix-free. The second executes the actual Qiskit
circuit and remains the circuit-level validation path. The edge simulator does
not claim a hardware speedup.

On the development environment, one calibrated input produced these indicative
end-to-end timings:

| Leaves | Edge simulator | Qiskit statevector | Speedup |
| ---: | ---: | ---: | ---: |
| 2 | 0.0015 s | 0.364 s | 244x |
| 4 | 0.0022 s | 0.992 s | 460x |
| 8 | 0.0043 s | 24.56 s | 5,706x |

The transmission-probability differences were between `1e-15` and `3e-11`.
Exhaustive matrix-free verification of all 256 eight-leaf inputs completed in
about one second. Timings depend on hardware and installed Qiskit/SciPy versions.

## Remaining scaling limits

For `N` power-of-two leaves and runway half-length `R`, the graph has

$$
V = 3N + 2R
$$

vertices. The complete query circuit uses approximately

$$
q = \left\lceil\log_2(3N+2R)\right\rceil + \log_2 N + 1
$$

qubits: a binary position register, a leaf-address register, and one oracle
value qubit. A Qiskit statevector therefore stores `2**q` complex amplitudes.

The driver contains `E_D = 2N + 2R - 1` edges. With `d=driver_reps`, one query
step contains approximately

$$
4dE_D + N
$$

structured edge rotations before multi-controlled-gate decomposition. The
matrix-free simulator performs these rotations in linear memory, but the real
Qiskit circuit still pays their gate cost.

Sparse-first is primarily a memory and construction-scaling improvement, not an
unconditional wall-clock speedup. Small dense `HamiltonianGate` simulations can
still be faster than simulating many decomposed controlled rotations. The sparse
backend becomes useful when dense matrix allocation or unitary synthesis is the
limiting resource.

For an all-one input with runway half-length 8, the three CSR graph matrices use
about 181 KiB at 1,024 leaves; three equivalent float64 dense matrices would use
about 218 MiB. Both figures exclude Python object overhead and the Qiskit
statevector.

circuit.
