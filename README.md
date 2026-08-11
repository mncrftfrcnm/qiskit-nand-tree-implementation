# Qiskit NAND-tree implementation

[![CI](https://github.com/mncrftfrcnm/qiskit-nand-tree-implementation/actions/workflows/ci.yml/badge.svg)](https://github.com/mncrftfrcnm/qiskit-nand-tree-implementation/actions/workflows/ci.yml)


This repository is a  Qiskit implementation of quantum NAND-tree evaluation. can be used to compare a finite Hamiltonian walk with an explicit query-style circuit and to check the oracle bookkeeping on small trees.

The built-in profiles cover **2, 4, and 8 leaves, and also un-capped**. They are calibrated finite examples, not a scalable implementation of the asymptotic algorithm.

As of now, there are experimental power-of-two tree-generations, with no limit to the amount of leaves

(I hope I will continue developing this project, implementing the full, endless algorithm.)



## Project status

This project is currently a **prototype**.

The small supported tree sizes are useful for checking the mechanics of the algorithm: the input oracle, query/unquery behavior, Hamiltonian evolution, transmission probabilities, and query counts.

The main limitation is scalability. Several parts of the walk are represented using finite Hamiltonian matrices and compiled into Qiskit circuits. That makes the implementation easy to compare against exact linear algebra, but it becomes expensive quickly as the tree grows.

The theoretical complexity results from the NAND-tree papers should therefore not be attributed directly to this implementation.

## NAND tree and walk graph

A balanced NAND tree stores input bits at its leaves and applies NAND gates at the internal vertices.

For four leaves:

```text
                 NAND
               /      \
            NAND      NAND
            /  \      /  \
           x0  x1    x2  x3
```

Each internal node computes:

```text
NAND(a, b) = 1 - (a AND b)
```

A classical implementation can evaluate the tree from the leaves upward.

The quantum algorithm takes a different approach. It turns the tree into part of a graph and studies a quantum walk on that graph.

A path called the **runway** is attached to the root. The input bits control extra edges attached to the leaves.

The resulting graph contains:

- runway vertices for the incoming and outgoing packet;
- tree vertices containing the NAND-tree structure;
- one oracle vertex for each input leaf.

For input bit `x_k`, the edge between leaf `k` and its oracle vertex is present when `x_k = 1` and absent when `x_k = 0`.

That input-dependent edge is how the Boolean input enters the walk.

### Hamiltonian

Let `A` be the graph adjacency matrix.

The finite walk Hamiltonian is:

```text
H = -A
```

It is useful to split it into two parts:

```text
H = H_D + H_O
```

where:

```text
H_D = fixed runway and tree edges
H_O = input-dependent leaf/oracle edges
```

The state evolves according to:

```text
|psi(t)> = exp(-i H t) |psi(0)>
```

The finite graph construction is implemented in:

```text
non_qiskit/graph.py
```

and the direct continuous-time reference evolution is in:

```text
non_qiskit/exact_walk.py
```

### Custom experiment parameters

The calibrated finite profiles remain the default. For a custom experiment,
supply the walk geometry, product-formula step count, and decision threshold
together:

For scaling experiments, parameters can instead be generated from one fixed
rule rather than calibrated independently for each tree size:

```python
from qiskit_implementation import (
    NandExperimentConfig,
    evaluate_nand_tree,
    theoretical_parameters,
)

leaves = (1, 0, 1, 1)
experiment = NandExperimentConfig(
    walk=theoretical_parameters(len(leaves), gamma=8.0),
    query_steps=16,
    threshold=0.5,
)

result = evaluate_nand_tree(leaves, experiment=experiment)
```

Here the parameter rule uses

\[
L = \lceil \gamma \sqrt{N} \rceil,\qquad
M = \lceil L^2 \rceil,\qquad
t = L/2,
\]

where \(N\) is the number of leaves, \(L\) is the packet length, and \(M\) is
the runway half-length.

`gamma` and `runway_factor` are finite-size experiment parameters. When
studying scaling with tree size, they should be kept fixed rather than
re-fitted independently for every \(N\).

Omitting `experiment` preserves the calibrated finite profiles used by earlier
versions. A custom experiment configuration is not calibrated automatically;
its threshold and query-step count are caller-supplied finite-size choices.

### Parameter-scaling note

`gamma=8.0` is an example finite-size constant, not a theoretically prescribed
value. The important scaling is

\[
L = \Theta(\sqrt{N}),\qquad
M = \Theta(L^2),\qquad
t = L/2.
\]

When comparing different tree sizes, use the same constants rather than tuning
them independently for each \(N\).


### Initial packet

The initial state is placed on the left side of the runway.

For a packet of length `L`, the amplitudes follow the right-moving phase pattern:

```text
<r|psi(0)> = L^(-1/2) exp(i r pi / 2)
```

for the selected runway positions, and zero elsewhere.

The phase pattern matters because the packet is intended to move toward the root rather than behave like a stationary probability distribution.

### Transmission

After the packet interacts with the tree, the final probability is divided into several regions:

```text
reflection   = probability on the non-positive runway
transmission = probability on the positive runway
tree         = probability remaining in the tree/oracle region
```

The finite implementation uses transmission probability as its decision statistic.

For a calibrated tree size:

```text
transmission < threshold   -> predicted root 0
transmission >= threshold  -> predicted root 1
```

The threshold is not always `0.5`. It is calibrated independently for each supported tree size.

## Query circuit

Directly simulating:

```text
exp(-i (H_D + H_O) t)
```

is useful as a reference, but it does not expose how many times the unknown input is queried.

The query implementation separates driver evolution and oracle evolution using a symmetric product formula.

For:

```text
dt = t / r
```

the implemented approximation is:

```text
exp(-i (H_D + H_O) t)

approximately equals

[
    exp(-i H_D dt / 2)
    exp(-i H_O dt)
    exp(-i H_D dt / 2)
]^r
```

Here `r` is the number of query-walk steps.

The explicit query circuit is compared against this split-Hamiltonian reference on small instances.

## Input oracle

The implementation uses the standard bit-query oracle:

```text
U_O |k, a> = |k, a XOR x_k>
```

The address register `k` selects an input leaf and `a` is a work qubit.

The walk position register does not directly contain the leaf address, so each oracle-evolution block first derives the appropriate leaf index from the current graph position.

One block performs:

1. compute the temporary leaf address;
2. query `x_k` into the work qubit;
3. apply the leaf-edge evolution controlled by that work qubit;
4. query `x_k` again;
5. uncompute the temporary leaf address.

The second query clears the work qubit.

Because the oracle is its own inverse:

```text
U_O * U_O = I
```

the second call performs:

```text
|k, x_k> -> |k, 0>
```

This is why one product-formula step uses exactly two input-oracle calls.

query_count counts calls to the abstract input oracle U
O
. It does not represent the transpiled circuit depth, two-qubit gate count, or physical hardware execution cost.

For `r` query-walk steps:

```text
Q = 2r
```

The register-level implementation is in:

```text
qiskit_implementation/query_walk.py
```

## Calibration

The finite model uses different parameters for different tree sizes.

Current built-in profiles:

| Leaves | Runway half-length | Packet length | Evolution time | Threshold | Query steps |
|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 3 | 7.8 | 0.37 | 2 |
| 4 | 2 | 3 | 9.4 | 0.16 | 8 |
| 8 | 6 | 5 | 17.75 | 0.48 | 16 |

These are empirical values for the finite graphs in this repository. They are not constants from the theoretical NAND-tree algorithm.

For each tree size, calibration evaluates every possible input.

It finds:

```text
largest root-0 transmission
smallest root-1 transmission
```

and calculates the separation:

```text
separation =
    smallest root-1 transmission
    -
    largest root-0 transmission
```

A positive separation means one threshold can distinguish every input in that finite model.

The current verification results are recorded in [EXPERIMENTS.md](EXPERIMENTS.md).

They can be reproduced with:

```bash
python main.py verify --leaf-count 2 --mode both
python main.py verify --leaf-count 4 --mode both
python main.py verify --leaf-count 8 --mode both
```

A calibration search can also be rerun:

```bash
python main.py calibrate --leaf-count 4 --runways 2,3,4,5,6 --packets 2,3,4,5 --time-start 0.5 --time-stop 20 --time-points 79 --steps 1,2,4,8,16,32
```

## Where this can be used

This repository is mainly useful as a research and learning project.

It gives a relatively small place to experiment with parts of quantum algorithms that are often hidden behind high-level examples, including oracle construction, ancilla cleanup, query counting, Hamiltonian evolution, finite wave packets, and measurement rules.

Some practical experiments include:

- comparing exact evolution with product-formula approximations;
- testing different oracle constructions;
- checking query counts and workspace cleanup;
- measuring circuit depth and gate counts;
- experimenting with finite-shot sampling;
- testing confidence intervals;
- trying noise models or different transpilation settings;
- comparing query-based and dense-reference implementations;
- experimenting with more efficient graph encodings.

It is not intended as a practical Boolean-formula evaluator, and the current implementation should not be treated as evidence of a practical quantum speed-up.

More runnable experiments are in [EXAMPLES.md](EXAMPLES.md) and the
[examples directory](examples/README.md).

## Installation

Install the project and development dependencies with:

```bash
python -m pip install -e ".[dev]"
```

The project currently targets Python 3.10+ and Qiskit 2.4.x.

## API

The normal Python entry point is:

```python
from qiskit_implementation import evaluate_nand_tree

result = evaluate_nand_tree([1, 0, 1, 1])

print("expected:", result.expected_value)
print("predicted:", result.predicted_value)
print("transmission:", result.transmission_probability)
print("oracle queries:", result.query_count)
```

Dense finite-Hamiltonian reference mode is also available:

```python
from qiskit_implementation import evaluate_nand_tree

result = evaluate_nand_tree(
    [1, 0, 1, 1],
    mode="dense",
)

print(result.predicted_value)
print(result.transmission_probability)
```

For finite-shot sampling:

```python
sampled = evaluate_nand_tree(
    [1, 0, 1, 1],
    shots=4096,
    seed=7,
)

print(sampled.predicted_value)
print(sampled.shot_result)
```

There is also an object-oriented wrapper:

```python
from qiskit_implementation import QuantumNandEvaluator

evaluator = QuantumNandEvaluator([1, 0, 1, 1])

result = evaluator.evaluate()

print(result.predicted_value)
```

Lower-level experimental functions can be imported directly from their modules:

```python
from qiskit_implementation.query_walk import simulate_query_walk
```

### Command line

Run the small default Qiskit example:

```bash
python main.py
```

Run the standalone example:

```bash
python example_usage.py
```

Evaluate an input:

```bash
python main.py evaluate --leaves 1011
```

Evaluate using samples:

```bash
python main.py evaluate --leaves 1011 --shots 4096 --seed 7
```

Compare the finite reference models:

```bash
python main.py verify --leaf-count 4 --mode both
```

Verify the explicit Qiskit evaluator:

```bash
python main.py qiskit-verify --leaf-count 4
```

Inspect the walk graph:

```bash
python main.py graph --leaves 1011 --runway 3
```

## Tests

Run the normal suite:

```bash
python -m pytest -v -rs
```

Run the slow exhaustive checks:

```bash
python -m pytest tests_folder/tests --run-slow -v -rs
```

Run Ruff:

```bash
python -m ruff check .
```

The tests cover behavior rather than only checking that circuits can be constructed.

Important checks include:

- bit-oracle truth tables;
- oracle involution;
- query/unquery cleanup;
- address-register cleanup;
- workspace leakage;
- query counting;
- exact Hamiltonian comparisons;
- product-formula comparisons;
- Qiskit sampler behavior;
- query/dense agreement;
- exhaustive finite-profile classification.

GitHub Actions runs the regular tests on supported Python versions, runs the examples, runs Ruff, builds the package, and checks that the built wheel installs correctly.

## Limitations

The repository includes calibrated finite profiles for reproducible small
examples, as well as an opt-in parameterized mode for experiments using a
fixed \(L=\Theta(\sqrt{N})\) scaling rule. These are finite simulations and
should not be interpreted as a scalable implementation of the asymptotic
algorithm.


Several graph evolutions are represented using dense Hamiltonian matrices. Qiskit then compiles those small matrix evolutions into circuits.

That makes exact comparisons straightforward but becomes expensive quickly as the graph grows.

The calibrated evolution times, runway lengths, packet sizes, thresholds, and query-step counts are also specific to the small finite graphs in this repository.

They should not be extrapolated into a scaling claim.

A more scalable implementation would need a structured local representation of the walk rather than constructing the full graph Hamiltonian as a dense matrix.

## References

The papers most directly related to this project are:

- Edward Farhi, Jeffrey Goldstone, and Sam Gutmann — *A Quantum Algorithm for the Hamiltonian NAND Tree* — [Theory of Computing](https://theoryofcomputing.org/articles/v004a008/)
- Andrew M. Childs, Richard Cleve, Stephen P. Jordan, and David Yonge-Mallo — *Discrete-Query Quantum Algorithm for NAND Trees* — [Theory of Computing](https://theoryofcomputing.org/articles/v005a005/)
- Andris Ambainis, Andrew M. Childs, Ben W. Reichardt, Robert Špalek, and Shengyu Zhang — *Any AND-OR Formula of Size N Can Be Evaluated in Time N^(1/2+o(1)) on a Quantum Computer* — [arXiv](https://arxiv.org/abs/quant-ph/0703015)
- Ben W. Reichardt and Robert Špalek — *Span-Program-Based Quantum Algorithm for Evaluating Formulas* — [arXiv](https://arxiv.org/abs/0710.2630)
- Carlos Mochon — *Hamiltonian Oracles* — [arXiv](https://arxiv.org/abs/quant-ph/0602032)

A longer bibliography is available in [REFERENCES.md](REFERENCES.md).

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, testing, and pull-request guidelines.
