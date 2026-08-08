# NAND-tree evaluation in Qiskit

This repository is an implementation of the quantum NAND-tree algorithm using Qiskit. The main goal is to make the walk construction and the oracle calls concrete enough to inspect on small examples.

I use a balanced binary NAND tree, convert it into the walk graph from the NAND-tree algorithm, and simulate the resulting dynamics in two ways:

- directly from the finite Hamiltonian; and
- with a query-style Qiskit circuit that separates the fixed walk from the input oracle.

The code currently has calibrated examples for 2, 4, and 8 leaves. These are small finite simulations, not a scalable implementation of the asymptotic algorithm.

## What I wanted to check

The main question was whether the transmission probability separates inputs whose NAND-tree value is 0 from inputs whose value is 1.

The implementation also checks a few details that are easy to get wrong when translating the algorithm into a circuit:

- whether the bit oracle has the expected truth table;
- whether the oracle can be queried and then unqueried without leaving garbage in the work qubit;
- whether the query circuit matches the corresponding split Hamiltonian evolution on small cases;
- how many oracle calls each walk step uses; and
- whether the finite-size parameters classify every supported small input correctly.

The tests in `tests_folder/tests` cover these properties directly.

## NAND tree and walk graph

For four input bits the Boolean tree is

```text
                 NAND
               /      \
            NAND      NAND
            /  \      /  \
           x0  x1    x2  x3
```

with

$$
\operatorname{NAND}(a,b)=1-(a\land b).
$$

The quantum algorithm does not evaluate the gates from the leaves upward. Instead, it attaches a path (the runway) to the root and performs a quantum walk on the resulting graph. Input bits change the leaf edges of that graph.

The finite Hamiltonian used here is

$$
H=-A=H_D+H_O,
$$

where $H_D$ contains the fixed runway/tree edges and $H_O$ contains the input-dependent leaf edges.

A packet starts on the left side of the runway and evolves under

$$
|\psi(t)\rangle=e^{-iHt}|\psi(0)\rangle.
$$

For the calibrated small instances, the amount of probability transmitted to the right side of the runway is used to classify the root value.

## Query circuit

The query version uses the bit oracle

$$
U_O|k,a\rangle=|k,a\oplus x_k\rangle.
$$

For one oracle-evolution block, the circuit:

1. derives the leaf address from the current walk position;
2. queries $x_k$ into a work qubit;
3. uses that work qubit to control the leaf-edge evolution;
4. queries the oracle again to clear the work qubit; and
5. uncomputes the temporary leaf address.

That is why one product-formula step uses two calls to the input oracle. The comments in `qiskit_implementation/query_walk.py` explain this register-by-register.

## Calibration

The finite model needs different parameters for different tree sizes. The built-in values are in `non_qiskit/profiles.py`.

They are calibration values for these small simulations rather than constants from the asymptotic analysis. The calibration code searches runway length, packet length, evolution time, and query-step choices and keeps parameter sets that separate the two NAND outputs across all inputs of that size.

I keep notes on the current values and how to reproduce the checks in [EXPERIMENTS.md](EXPERIMENTS.md).

## Running it

Install the project and development dependencies:

```bash
python -m pip install -e .[dev]
```

Evaluate one input:

```bash
python main.py evaluate --leaves 1011
```

Run the default example:

```bash
python main.py
```

Run the tests:

```bash
python -m pytest -v -rs
```

Run Ruff:

```bash
python -m ruff check .
```

To reproduce the finite-profile checks:

```bash
python main.py verify --leaf-count 2 --mode both
python main.py verify --leaf-count 4 --mode both
python main.py qiskit-verify --leaf-count 2
```

The 8-leaf exhaustive Qiskit check is marked slow because it evaluates all 256 inputs.

## Limitations

The current implementation builds finite Hamiltonian matrices and compiles small instances into Qiskit circuits. This is useful for checking the mechanics of the algorithm, but the matrix representation grows quickly and is not the scalable construction used to obtain the theoretical complexity result.

The thresholds and evolution parameters are also finite-size calibration choices. They should not be interpreted as universal parameters for arbitrary NAND formulas.

## References

The two papers I used most directly for the walk and query constructions are:

- Farhi, Goldstone, and Gutmann, *A Quantum Algorithm for the Hamiltonian NAND Tree*: https://theoryofcomputing.org/articles/v004a008/
- Childs, Cleve, Jordan, and Yonge-Mallo, *Discrete-Query Quantum Algorithm for NAND Trees*: https://theoryofcomputing.org/articles/v005a005/
