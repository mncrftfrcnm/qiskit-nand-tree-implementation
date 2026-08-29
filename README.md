# Qiskit NAND-tree implementation

[![CI](https://github.com/mncrftfrcnm/qiskit-nand-tree-implementation/actions/workflows/ci.yml/badge.svg)](https://github.com/mncrftfrcnm/qiskit-nand-tree-implementation/actions/workflows/ci.yml)

This is a finite, small-scale implementation of the quantum NAND-tree walk. It
contains calibrated experiments for 2, 4, and 8 leaves, an explicit input
oracle, query counting, dense reference evolution, and a sparse query
implementation.

It is not the unbounded asymptotic algorithm yet. The repository is mainly a
place to check the pieces of that algorithm on instances small enough to inspect.

(as of now it is not ready to be used in production, but I hope I will continue developing this project)

## Quick start

The package supports Python 3.10+ and Qiskit `>=2.4,<3`.

```bash
python -m pip install -e ".[dev]"
python main.py
```

The public evaluator defaults to the dense reference:

```python
from qiskit_implementation import evaluate_nand_tree

dense = evaluate_nand_tree([1, 0, 1, 1])
query = evaluate_nand_tree([1, 0, 1, 1], mode="query")

print(dense.predicted_value, dense.transmission_probability)
print(query.predicted_value, query.transmission_probability, query.query_count)
```

The two modes have different jobs:

| Mode | Intended use | Main cost |
|---|---|---|
| `dense` | Exact full-Hamiltonian reference for small inputs | Dense padded matrices and statevectors |
| `query` | Explicit oracle algorithm and larger simulations | Product-formula steps and edge rotations |

`dense` is the default because it is the reference calculation. Use
`mode="query"` when you want the query algorithm, sampling, or the matrix-free
simulator(and also it is faster and uses less resources).

## The finite walk

A balanced NAND tree puts the input bits at its leaves:

```text
                 NAND
               /      \
            NAND      NAND
            /  \      /  \
           x0  x1    x2  x3
```

The code attaches a path, called the runway, to the root. Each leaf also has an
oracle vertex. The leaf-to-oracle edge is present when that input bit is `1` and
absent when it is `0`.

If `A` is the graph adjacency matrix, the walk Hamiltonian is

$$
H=-A=H_D+H_O,
$$

where `H_D` contains the fixed runway and tree edges, and `H_O` contains the
input-dependent leaf edges. The state evolves as

$$
|\psi(t)\rangle=e^{-iHt}|\psi(0)\rangle.
$$

The initial wave packet starts on the left side of the runway with amplitudes

$$
\langle r|\psi(0)\rangle=L^{-1/2}e^{ir\pi/2}.
$$

After evolution, the code measures how much probability reached the positive
side of the runway. A calibrated threshold turns that transmission probability
into a Boolean result.

The graph and exact continuous-time reference are in `non_qiskit/graph.py` and
`non_qiskit/exact_walk.py`.

## Query implementation

The query path splits the Hamiltonian with a symmetric product formula. For
`dt = t / r`, it applies

$$
\left[e^{-iH_Ddt/2}e^{-iH_Odt}e^{-iH_Ddt/2}\right]^r.
$$

The input oracle is the usual bit-query oracle:

$$
U_O|k,a\rangle=|k,a\oplus x_k\rangle.
$$

Each walk step computes the leaf address, queries its bit, applies the selected
leaf-edge rotation, queries again to clear the work qubit, and uncomputes the
address. This gives two oracle calls per step:

$$
Q=2r.
$$

`query_count` counts calls to this abstract oracle. It is not a transpiled gate
count or a hardware runtime estimate.

The register-level implementation is in
`qiskit_implementation/query_walk.py`.

## Dense, sparse, and simulated execution

There are three separate choices that are easy to confuse:

- `mode="dense"` or `mode="query"` chooses the high-level algorithm.
- `matrix_format="sparse"` or `"dense"` chooses graph storage.
- `simulation_backend="edge"` or `"qiskit"` chooses how a sparse query circuit
  is simulated.

Sparse graph storage uses SciPy CSR matrices. Exact non-Qiskit evolution applies
matrix exponentials to vectors with `scipy.sparse.linalg.expm_multiply`, so it
does not build a dense exponential.

The sparse query circuit replaces one large `HamiltonianGate` with two-level
edge rotations. Oracle edges are disjoint, but driver edges share vertices;
their ordered rotation formula is therefore approximate. `driver_reps=4` is the
tested default for the bundled profiles.

With `simulation_backend="auto"`, sparse query evaluation uses the matrix-free
edge simulator. It applies the same ordered rotations directly to the position
vector. To execute the complete Qiskit statevector circuit instead, use:

```python
result = evaluate_nand_tree(
    [1, 0, 1, 1],
    mode="query",
    simulation_backend="qiskit",
)
```

The edge simulator makes development runs much quicker, but it is still a
classical simulator. It does not reduce the circuit resources needed on quantum
hardware.

More backend details and measured resource examples are in
[SPARSE_BACKENDS.md](SPARSE_BACKENDS.md).

## Accuracy

Dense evaluation is the full finite-Hamiltonian reference, up to normal
floating-point error. The deterministic sparse query classifier has been tested
exhaustively for every input in the built-in 2-, 4-, and 8-leaf profiles.

That result should not be extended automatically to custom parameters. The
sparse driver uses an extra product formula, and larger experiments need their
own threshold and step-count checks.

Sampling is a separate issue. Any finite-shot result is probabilistic, even when
the state being sampled was calculated exactly. Sampling is available only in
query mode in the current API.

Confidence-based sampling uses stored sparse-backend margins for the built-in
profiles. If `driver_reps` or the profile changes, the API rejects a requested
confidence instead of reusing the wrong bound.

```python
sampled = evaluate_nand_tree(
    [1, 0, 1, 1],
    mode="query",
    shots=4096,
    seed=7,
)
```

## Built-in profiles

| Leaves | Runway half-length | Packet length | Time | Threshold | Query steps |
|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 3 | 7.8 | 0.37 | 2 |
| 4 | 2 | 3 | 9.4 | 0.16 | 8 |
| 8 | 6 | 5 | 17.75 | 0.48 | 16 |

These values are empirical calibrations for the finite graphs used here. You can
recheck their class separation with:

```bash
python main.py verify --leaf-count 2 --mode both
python main.py verify --leaf-count 4 --mode both
python main.py verify --leaf-count 8 --mode both
python main.py qiskit-verify --leaf-count 4
```

The recorded results are in [EXPERIMENTS.md](EXPERIMENTS.md).

## More than eight leaves

Larger power-of-two inputs require an explicit `NandExperimentConfig`:

```python
from qiskit_implementation import (
    NandExperimentConfig,
    evaluate_nand_tree,
    theoretical_parameters,
)

leaves = (0,) * 16
experiment = NandExperimentConfig(
    walk=theoretical_parameters(len(leaves), gamma=8.0),
    query_steps=16,
    threshold=0.5,
)

result = evaluate_nand_tree(
    leaves,
    mode="query",
    experiment=experiment,
    simulation_backend="edge",
)
```

The helper uses the rule

$$
L=\lceil\gamma\sqrt{N}\rceil,\qquad
M=\lceil L^2\rceil,\qquad
t=L/2.
$$

This supplies a repeatable geometry, not a calibration. The `0.5` threshold and
16 steps in the example are trial values. A larger configuration is not trusted
until its separation margin has been checked.

## Command line

```bash
# Dense reference (default)
python main.py evaluate --leaves 1011

# Sparse query path
python main.py evaluate --leaves 1011 --mode query

# Full Qiskit statevector instead of the edge simulator
python main.py evaluate --leaves 1011 --mode query --simulation-backend qiskit

# Finite-shot query result
python main.py evaluate --leaves 1011 --mode query --shots 4096 --seed 7

# Inspect sparse or dense graph storage
python main.py graph --leaves 1011 --runway 3
python main.py graph --leaves 1011 --runway 3 --matrix-format dense
```

For a custom 16-leaf experiment:

```bash
python main.py evaluate \
  --leaves 0000000000000000 \
  --mode query \
  --runway 16 --packet 8 --time 4 --steps 16 --threshold 0.5
```

These parameters are deliberately labelled uncalibrated.

See [EXAMPLES.md](EXAMPLES.md) and [examples/README.md](examples/README.md) for
more commands and runnable scripts.

## Scaling limits

For `N` leaves and runway half-length `R`, the graph has `3N + 2R` vertices. A
complete query circuit uses approximately

$$
q=\left\lceil\log_2(3N+2R)\right\rceil+\log_2N+1
$$

qubits. A full Qiskit statevector therefore grows as `2**q`, despite sparse graph
storage. The edge simulator keeps only the position vector, which is why it can
handle much larger graphs.

The remaining bottlenecks are:

- the full statevector for Qiskit circuit simulation;
- a truth-table oracle whose circuit grows with the number of leaves;
- multi-controlled edge rotations and their decomposition;
- product-formula repetitions;
- exhaustive calibration over `2**N` inputs.

Sparse storage removes the dense matrix allocation, not all exponential work.
A reversible neighbor oracle and sparse-Hamiltonian block encoding would be a
more direct route toward the asymptotic model.

## Tests

```bash
python -m pytest -v -rs
python -m pytest tests_folder/tests --run-slow -v -rs
python -m ruff check .
```

The suite covers the oracle, workspace cleanup, query counting, dense/sparse
agreement, product-formula convergence, sampling, the command line, and
exhaustive classification of the calibrated profiles. CI also runs every script
under `examples/`.

## References

- Edward Farhi, Jeffrey Goldstone, and Sam Gutmann — [A Quantum Algorithm for the Hamiltonian NAND Tree](https://theoryofcomputing.org/articles/v004a008/)
- Andrew M. Childs, Richard Cleve, Stephen P. Jordan, and David Yonge-Mallo — [Discrete-Query Quantum Algorithm for NAND Trees](https://theoryofcomputing.org/articles/v005a005/)
- Andris Ambainis, Andrew M. Childs, Ben W. Reichardt, Robert Špalek, and Shengyu Zhang — [Any AND-OR Formula of Size N Can Be Evaluated in Time N^(1/2+o(1)) on a Quantum Computer](https://arxiv.org/abs/quant-ph/0703015)
- Ben W. Reichardt and Robert Špalek — [Span-Program-Based Quantum Algorithm for Evaluating Formulas](https://arxiv.org/abs/0710.2630)
- Carlos Mochon — [Hamiltonian Oracles](https://arxiv.org/abs/quant-ph/0602032)

The longer bibliography is in [REFERENCES.md](REFERENCES.md).
