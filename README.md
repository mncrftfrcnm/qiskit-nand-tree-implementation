# Qiskit NAND-tree implementation

This repository is a small Qiskit implementation of quantum NAND-tree evaluation. I use it to compare a finite Hamiltonian walk with an explicit query-style circuit and to check the oracle bookkeeping on small trees.

The built-in profiles cover **2, 4, and 8 leaves**. They are calibrated finite examples, not a scalable implementation of the asymptotic algorithm.

## What I am testing

The main checks are:

- the bit oracle returns the expected input bit for a leaf address;
- querying and unquerying leaves the work register clean;
- the explicit query circuit matches the corresponding split-Hamiltonian evolution on small cases;
- each walk step uses the expected number of oracle calls;
- transmission separates root values 0 and 1 for the built-in profiles; and
- the calibrated parameters classify every supported input in the finite reference model.

The detailed calibration results are recorded in [EXPERIMENTS.md](EXPERIMENTS.md).

## NAND tree and walk graph

For a balanced NAND tree, the leaves contain the input bits and the internal vertices are NAND gates. For four leaves:

```text
                 NAND
               /      \
            NAND      NAND
            /  \      /  \
           x0  x1    x2  x3
```

Instead of evaluating those gates from the leaves upward, the quantum-walk construction turns the formula into part of a graph. A path called the **runway** is attached to the root, and the input bits control extra edges attached to the leaves.

The graph therefore has three kinds of vertices:

- runway vertices, which carry the incoming and outgoing wave packet;
- tree vertices, which encode the NAND formula structure; and
- oracle vertices, one for each input leaf.

For input bit \(x_k\), the edge between leaf \(k\) and its oracle vertex is present when \(x_k=1\) and absent when \(x_k=0\). This is the input-dependent part of the walk.

### Hamiltonian

Let \(A\) be the graph adjacency matrix. The finite walk Hamiltonian is

$$
H=-A.
$$

I split it into

$$
H=H_D+H_O,
$$

where \(H_D\) contains the fixed runway/tree edges and \(H_O\) contains the input-dependent leaf/oracle edges.

The reference implementation evolves an initial state according to

$$
|\psi(t)\rangle=e^{-iHt}|\psi(0)\rangle.
$$

The code for the finite graph is in `non_qiskit/graph.py`, while `non_qiskit/exact_walk.py` performs the direct continuous-time evolution.

### Initial packet

The initial state is supported on the left side of the runway rather than on the NAND tree itself. The finite implementation uses the same right-moving phase pattern that motivates the theoretical construction:

$$
\langle r|\psi(0)\rangle=
\begin{cases}
L^{-1/2}e^{ir\pi/2}, & -L+1\le r\le 0,\\
0, & \text{otherwise}.
\end{cases}
$$

The phase matters because the packet is meant to move toward the root instead of behaving like a static probability distribution.

### Why transmission is useful

After the packet reaches the root region, the tree changes its scattering behavior depending on the NAND value. For the small finite instances here, I separate the final probability into:

- reflection: probability on the non-positive side of the runway;
- transmission: probability on the positive side of the runway; and
- tree probability: probability still inside the tree/oracle part of the graph.

The implementation uses transmission probability as its decision statistic.

For a calibrated profile,

```text
transmission < threshold  -> predicted root 0
transmission >= threshold -> predicted root 1
```

The threshold is not assumed to be universally \(0.5\). It is calibrated separately for each supported tree size.

## From Hamiltonian evolution to a query circuit

Directly calculating

$$
e^{-i(H_D+H_O)t}
$$

is useful as a reference, but it does not expose how many times the unknown input is queried.

The Qiskit query implementation instead separates the driver and oracle Hamiltonians with a symmetric product formula. For

$$
\Delta t=\frac{t}{r},
$$

the implemented approximation is

$$
e^{-i(H_D+H_O)t}
\approx
\left(
e^{-iH_D\Delta t/2}
e^{-iH_O\Delta t}
e^{-iH_D\Delta t/2}
\right)^r.
$$

Here \(r\) is the number of query-walk steps. The query implementation is compared against this split-Hamiltonian reference on small inputs.

## Input oracle

The circuit uses the standard bit-query oracle

$$
U_O|k,a\rangle=|k,a\oplus x_k\rangle.
$$

The address register \(k\) selects an input leaf and \(a\) is a work qubit.

The walk position register does not directly store a leaf number, so the oracle-evolution block first derives the relevant leaf index from the current graph vertex. It then queries \(x_k\), uses that bit to control the leaf-edge evolution, and erases the temporary information afterward.

One oracle-evolution block is therefore:

1. compute the temporary leaf address;
2. query \(x_k\) into the work qubit;
3. apply the leaf-edge evolution controlled by that work qubit;
4. query \(x_k\) again; and
5. uncompute the temporary leaf address.

The second oracle call is not an extra lookup for another input. It is **uncomputation**.

Because

$$
U_O^2=I,
$$

the second call maps

$$
|k,x_k\rangle\longrightarrow|k,0\rangle,
$$

returning the work qubit to its clean state.

That is why one product-formula step costs exactly **two oracle calls**, and a circuit with \(r\) steps reports

$$
Q=2r.
$$

The register-level implementation is in `qiskit_implementation/query_walk.py`.

## Calibration

The finite model needs different parameters for different tree sizes. The built-in values are:

| Leaves | Runway half-length | Packet length | Evolution time | Threshold | Query steps |
|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 3 | 7.8 | 0.37 | 2 |
| 4 | 2 | 3 | 9.4 | 0.16 | 8 |
| 8 | 6 | 5 | 17.75 | 0.48 | 16 |

These are empirical finite-model values, not constants from the NAND-tree papers.

For each size, calibration enumerates every possible input. Let

$$
p_{\max}^{(0)}
=
\max_{x:f(x)=0}
P_{\mathrm{transmit}}(x)
$$

and

$$
p_{\min}^{(1)}
=
\min_{x:f(x)=1}
P_{\mathrm{transmit}}(x).
$$

A usable finite profile needs

$$
p_{\min}^{(1)}-p_{\max}^{(0)}>0.
$$

The threshold can then be placed between the two groups. After choosing the continuous-time parameters, the calibration code tries increasing product-formula step counts and keeps the first one that classifies every input with a positive separation margin.

The current measured margins, including the 256-input 8-leaf reference checks, are in [EXPERIMENTS.md](EXPERIMENTS.md).

To reproduce them:

```bash
python main.py verify --leaf-count 2 --mode both
python main.py verify --leaf-count 4 --mode both
python main.py verify --leaf-count 8 --mode both
```

To rerun the parameter search, for example for four leaves:

```bash
python main.py calibrate \
    --leaf-count 4 \
    --runways 2,3,4,5,6 \
    --packets 2,3,4,5 \
    --time-start 0.5 \
    --time-stop 20 \
    --time-points 79 \
    --steps 1,2,4,8,16,32
```

## Installation

Install the package and development dependencies with:

```bash
python -m pip install -e .[dev]
```

The project currently targets Python 3.10+ with Qiskit 2.4.x, NumPy, and SciPy.

## Python API

The normal entry point is:

```python
from qiskit_implementation import evaluate_nand_tree

result = evaluate_nand_tree([1, 0, 1, 1])

print("expected:", result.expected_value)
print("predicted:", result.predicted_value)
print("transmission:", result.transmission_probability)
print("oracle queries:", result.query_count)
```

For unsampled query evaluation, `result.walk_result` contains the underlying `QueryWalkResult`. Dense mode returns its `QiskitWalkResult` through the same field:

```python
dense = evaluate_nand_tree([1, 0, 1, 1], mode="dense")
print(dense.walk_result)
```

For sampled evaluation:

```python
sampled = evaluate_nand_tree(
    [1, 0, 1, 1],
    shots=4096,
    seed=7,
)

print(sampled.predicted_value)
print(sampled.shot_result)
```

There is also a small object-oriented wrapper:

```python
from qiskit_implementation import QuantumNandEvaluator

evaluator = QuantumNandEvaluator([1, 0, 1, 1])
result = evaluator.evaluate()
```

`automatic()` remains as a compatibility alias for older code, but `evaluate()` is the preferred method name.

### Public versus low-level API

The top-level package intentionally exports only the main evaluation and verification interface plus the core circuit builders.

Low-level experimental helpers stay in their modules. For example:

```python
from qiskit_implementation.query_walk import simulate_query_walk
```

This keeps the normal API small without hiding the lower-level implementation.

## Command-line usage

Run the default example:

```bash
python main.py
```

Evaluate an input:

```bash
python main.py evaluate --leaves 1011
```

Evaluate with finite-shot sampling:

```bash
python main.py evaluate --leaves 1011 --shots 4096 --seed 7
```

Inspect a query walk directly:

```bash
python main.py query-walk \
    --leaves 1011 \
    --runway 2 \
    --packet 3 \
    --time 9.4 \
    --steps 8
```

Verify the explicit Qiskit profile:

```bash
python main.py qiskit-verify --leaf-count 4
```

## Tests

Run the normal suite:

```bash
python -m pytest -v -rs
```

Run the exhaustive slow checks as well:

```bash
python -m pytest tests_folder/tests --run-slow -v -rs
```

Run the linter:

```bash
python -m ruff check .
```

The tests cover more than successful circuit construction. In particular they check:

- bit-oracle truth tables and involution;
- query/unquery evolution against the input-dependent Hamiltonian;
- cleanup of address/workspace registers;
- query counts;
- query-walk agreement with the symmetric split reference; and
- calibrated classification over all small inputs.

The slow suite includes the exhaustive four-leaf query/split comparison and the 256-input eight-leaf Qiskit profile verification.

## Limitations

This repository favors a directly checkable finite model over scalability.

The graph Hamiltonian is represented as a dense matrix in several places, and the Qiskit implementation compiles small matrix evolutions into circuits. That makes comparison with exact linear algebra straightforward, but the representation becomes expensive quickly as the tree grows.

The calibrated thresholds and timings are also specific to the finite graphs used here. They should not be treated as a scaling prescription.

For that reason, the theoretical query-complexity results in the papers below should not be attributed to this dense finite implementation.

## References

The papers most directly related to this implementation are:

- Edward Farhi, Jeffrey Goldstone, and Sam Gutmann — *A Quantum Algorithm for the Hamiltonian NAND Tree* ([Theory of Computing](https://theoryofcomputing.org/articles/v004a008/))
- Andrew M. Childs, Richard Cleve, Stephen P. Jordan, and David Yonge-Mallo — *Discrete-Query Quantum Algorithm for NAND Trees* ([Theory of Computing](https://theoryofcomputing.org/articles/v005a005/))
- Andris Ambainis, Andrew M. Childs, Ben W. Reichardt, Robert Špalek, and Shengyu Zhang — *Any AND-OR Formula of Size N Can Be Evaluated in Time \(N^{1/2+o(1)}\) on a Quantum Computer* ([arXiv](https://arxiv.org/abs/quant-ph/0703015))
- Ben W. Reichardt and Robert Špalek — *Span-Program-Based Quantum Algorithm for Evaluating Formulas* ([arXiv](https://arxiv.org/abs/0710.2630))
- Carlos Mochon — *Hamiltonian Oracles* ([arXiv](https://arxiv.org/abs/quant-ph/0602032))

For the longer bibliography, including earlier quantum-walk, adversary-method, Hamiltonian-simulation, and classical tree-evaluation papers, see [REFERENCES.md](REFERENCES.md).
