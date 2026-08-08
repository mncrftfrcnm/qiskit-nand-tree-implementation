# qiskit-nand-tree-implementation

`qiskit-nand-tree-implementation` is a small Qiskit project for experimenting with the quantum NAND-tree evaluation algorithm. It includes the NAND-tree oracle, the walk Hamiltonian, a query-based circuit model, exact and sampled evaluation, and tests for small trees.

## Project status

This project is currently a **prototype**.

The 2-, 4-, and 8-leaf cases are implemented and tested as small finite models, including an explicit query circuit and exhaustive checks for the supported calibration profiles. The code is useful for studying the algorithm and trying changes to the Qiskit implementation, but it is not a scalable implementation of the theoretical asymptotic algorithm yet.

The main limitation is the walk evolution: parts of the current implementation still build finite Hamiltonian matrices and compile them into Qiskit circuits. That is fine for small experiments, but it gets expensive quickly as the tree grows.

## How the algorithm works

A NAND tree is a balanced binary tree with input bits at the leaves and a NAND gate at every internal node. For example:

```text
                 NAND
               /      \
            NAND      NAND
            /  \      /  \
           x0  x1    x2  x3
```

Each internal node computes

\[
\operatorname{NAND}(a,b)=1-(a\land b).
\]

The quantum algorithm does not evaluate every gate from the leaves upward. Instead, it turns the tree into a graph and performs a quantum walk on that graph.

In the continuous-time version by Farhi, Goldstone, and Gutmann, a path called the **runway** is attached to the root of the tree. Each leaf also gets an auxiliary vertex. If the hidden input bit \(x_j\) is 1, the corresponding leaf is connected to its auxiliary vertex.

The walk Hamiltonian is

\[
H=-A=H_D+H_O,
\]

where \(A\) is the graph adjacency matrix, \(H_D\) contains the fixed tree and runway edges, and \(H_O\) contains the input-dependent leaf edges.

A right-moving wave packet starts on the left side of the runway and evolves under

\[
|\psi(t)\rangle=e^{-iHt}|\psi(0)\rangle.
\]

For the relevant low-energy part of the state, the value at the root changes how the packet scatters. One case is mostly transmitted through the root region and the other is mostly reflected. That transmission behavior is what is used to decide the NAND-tree value.

The query version in this repository uses the standard bit oracle

\[
U_O|k,a\rangle=|k,a\oplus x_k\rangle.
\]

A query step loads the selected leaf value into a work qubit, applies the corresponding leaf-edge evolution, and calls the oracle again to clean the work qubit. The driver and oracle evolutions are then combined with a symmetric product formula.

The original algorithm and its query-model conversion are explained in much more detail here:

- [Farhi, Goldstone, and Gutmann — *A Quantum Algorithm for the Hamiltonian NAND Tree*](https://theoryofcomputing.org/articles/v004a008/)
- [Childs, Cleve, Jordan, and Yonge-Mallo — *Discrete-Query Quantum Algorithm for NAND Trees*](https://theoryofcomputing.org/articles/v005a005/)
- [Childs, Reichardt, Špalek, and Zhang — *Every NAND Formula of Size N Can Be Evaluated in Time N^(1/2+o(1))*](https://arxiv.org/abs/quant-ph/0703015)
- [Reichardt and Špalek — *Span-Program-Based Quantum Algorithm for Evaluating Formulas*](https://theoryofcomputing.org/articles/v008a013/)

## Where this can be used

This is mainly a research and learning project rather than an application library.

It is useful for studying how a quantum-walk algorithm is translated into Qiskit, especially the parts that are easy to miss in a notebook-only implementation: the input oracle, ancilla cleanup, query counting, finite wave packets, Hamiltonian evolution, and the final measurement rule.

It can also be used as a small test bed for:

- comparing exact Hamiltonian evolution with Trotter or Suzuki approximations;
- testing alternative oracle circuits;
- measuring circuit depth, two-qubit gate counts, and query counts;
- studying sampling error and confidence intervals;
- trying noise models or hardware-oriented transpilation on small instances;
- checking changes against every possible 2-, 4-, or 8-leaf input;
- experimenting with more efficient encodings of the walk graph.

The repo is not meant for evaluating large Boolean formulas in practice, and the current implementation should not be treated as evidence of a practical quantum speed-up.

## API

Install the project in editable mode:

```bash
python -m pip install -e .[dev]
```

The simplest entry point is `evaluate_nand_tree`:

```python
from qiskit_implementation import evaluate_nand_tree

result = evaluate_nand_tree([1, 0, 1, 1])

print(result.predicted_value)
print(result.transmission_probability)
print(result.query_count)
```

For repeated experiments on the same input, `QuantumNandEvaluator` provides a slightly more convenient interface:

```python
from qiskit_implementation import QuantumNandEvaluator

evaluator = QuantumNandEvaluator([1, 0, 1, 1])

exact = evaluator.automatic()
sampled = evaluator.automatic(shots=4096, seed=7)

print(exact.predicted_value)
print(sampled.predicted_value)
```

The lower-level circuit builders are also public:

```python
from qiskit_implementation import (
    build_bit_oracle,
    build_phase_oracle,
    build_query_walk_circuit,
    build_reversible_nand_circuit,
)
```

For checking a calibrated tree size across every possible input:

```python
from qiskit_implementation import verify_qiskit_profile

report = verify_qiskit_profile(4)
print(report.accuracy)
print(report.failed_inputs)
```

There are two runnable examples in the repository:

```bash
python main.py
python example_usage.py
```

The CLI can also evaluate a specific input:

```bash
python main.py evaluate --leaves 1011
```

## Contributing

Contributions are welcome. Setup instructions, test commands, code-style notes, and guidance for algorithm changes are in [CONTRIBUTING.md](CONTRIBUTING.md).
