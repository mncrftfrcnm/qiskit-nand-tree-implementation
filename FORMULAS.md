# Arbitrary NAND formulas

The original `NandTree` type represents complete balanced trees with a power-of-two number of leaves. That remains the representation used by the calibrated Qiskit/query path.

For finite experiments with arbitrary binary formula shapes, use the formula API in `non_qiskit.formula`.

```python
from non_qiskit import Input, evaluate_formula, nand, run_formula_walk

formula = nand(
    Input(0),
    nand(Input(1), nand(Input(2), Input(3))),
)
values = (1, 0, 1, 1)

print(evaluate_formula(formula, values))
result = run_formula_walk(
    formula,
    values,
    runway_half_length=6,
    packet_length=4,
    time=3.0,
)
print(result.root_value, result.transmission_probability)
```

Formula children can have different depths and an input can occur more than once:

```python
formula = nand(Input(0), nand(Input(0), Input(1)))
```

`build_formula_walk_graph()` creates a finite walk graph directly from the formula topology. Each input occurrence gets its own oracle-edge location while repeated occurrences still read the same concrete input value.

This support is intentionally separated from the calibrated balanced-tree classifier. An arbitrary formula shape changes the finite graph spectrum, so the built-in thresholds and query-step counts for 2, 4, and 8 balanced leaves must not be reused. `run_formula_walk()` therefore returns the transmission/reflection data and true formula value without pretending an uncalibrated threshold is a validated classifier.

Useful helpers include:

- `evaluate_formula()` for the classical Boolean value;
- `formula_depth()` and `formula_size()` for structural measurements;
- `input_occurrences()` for the left-to-right leaf/input sequence;
- `input_indices()` for the distinct variable indices;
- `format_formula()` for a compact readable representation;
- `build_formula_walk_graph()` for inspecting the finite Hamiltonian graph;
- `run_formula_walk()` for exact sparse continuous-time evolution.

A later Qiskit implementation can compile the same explicit formula topology into a query circuit. That requires an address/oracle layout that does not assume `log2(N)` balanced-leaf indexing, so it is kept out of this first general-formula layer rather than hiding that assumption.
