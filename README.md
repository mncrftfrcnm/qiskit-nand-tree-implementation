# Qiskit NAND-tree implementation

This repository implements a small version of the quantum NAND-tree evaluation algorithm in Qiskit.

The main goal is to connect the theoretical NAND-tree quantum walk to an explicit circuit that can be inspected and simulated. The repository contains:

- a classical NAND-tree implementation used as a reference;
- construction of the NAND-tree walk graph and Hamiltonian;
- a Qiskit implementation of the input oracle;
- continuous-time and product-formula walk simulations;
- an explicit discrete-query walk circuit;
- transmission/reflection measurements used to determine the root value; and
- tests comparing the Qiskit circuit against the corresponding small Hamiltonian model.

The current implementation supports calibrated examples with **2, 4, and 8 leaves**. These are finite models intended for studying the algorithm rather than a scalable implementation of the theoretical asymptotic construction.

## What I am testing

The main questions behind the implementation are:

- whether the input oracle implements the expected bit-query operation;
- whether the oracle work qubit is returned to its initial state after each query step;
- whether the query circuit matches the corresponding split-Hamiltonian evolution for small cases;
- how many oracle calls each walk step uses;
- whether transmission through the root region separates NAND outputs 0 and 1; and
- whether the finite-size parameters classify every supported small input correctly.

The tests in `tests_folder/tests` cover these properties directly.

## NAND tree

A NAND tree is a balanced binary tree whose leaves contain the input bits and whose internal vertices are NAND gates.

For four input bits:

```text
                 NAND
               /      \
            NAND      NAND
            /  \      /  \
           x0  x1    x2  x3
```

Each gate computes

$$
\mathrm{NAND}(a,b)=1-(a\land b).
$$

For example,

```text
NAND(0, 0) = 1
NAND(0, 1) = 1
NAND(1, 0) = 1
NAND(1, 1) = 0
```

Classically, the obvious way to evaluate the tree is to calculate the gates from the leaves upward.

The quantum algorithm takes a different approach: it represents the tree as part of a graph and extracts the root value from the behavior of a **quantum walk** on that graph.

## From the NAND tree to a walk graph

The construction used here follows the Hamiltonian NAND-tree algorithm of Farhi, Goldstone, and Gutmann. Their algorithm evaluates a balanced NAND tree using a continuous-time quantum walk and achieves \(O(\sqrt{N})\) evolution time in the Hamiltonian-oracle model.

A path called the **runway** is attached to the root of the NAND tree:

```text
 runway                         NAND tree

 ... -3 -- -2 -- -1 -- 0 ------ root
                                /    \
                               ...   ...
```

The initial state is a wave packet placed on the left side of this runway.

Each leaf also receives an auxiliary oracle vertex. Whether the edge between a leaf and its oracle vertex is active depends on the corresponding input bit.

A simplified picture is:

```text
                    tree
                     |
                   leaf j
                     |
                 x_j-dependent
                     |
                oracle vertex j
```

If the hidden bit \(x_j\) is 1, the corresponding oracle edge is included in the walk Hamiltonian. If \(x_j\) is 0, it is absent.

This means that the input does not have to be copied into the entire circuit in advance. Instead, the input appears through an oracle-dependent part of the Hamiltonian.

## Walk Hamiltonian

Let \(A\) be the adjacency matrix of the complete walk graph.

The Hamiltonian used by the walk is

$$
H=-A.
$$

It is useful to split it into two pieces:

$$
H=H_D+H_O.
$$

Here:

- \(H_D\) is the **driver Hamiltonian**. It contains the fixed runway and NAND-tree edges.
- \(H_O\) is the **oracle Hamiltonian**. It contains the input-dependent leaf/oracle edges.

The state evolves according to

$$
|\psi(t)\rangle=e^{-iHt}|\psi(0)\rangle.
$$

The initial wave packet is supported on the left part of the runway. In the original construction, its amplitudes have an approximately right-moving phase pattern. A simplified finite version is used in this repository.

One way of writing the packet used in the theoretical construction is

$$
\langle r|\psi(0)\rangle=
\begin{cases}
L^{-1/2}e^{ir\pi/2}, & -L+1\le r\le 0,\\
0, & \text{otherwise}.
\end{cases}
$$

The \(e^{ir\pi/2}\) phase is important because the initial state is not supposed to behave like a stationary distribution on the runway. It is intended to travel toward the tree.

## Why transmission tells us the NAND value

The NAND tree changes the scattering behavior of low-energy states near the root.

Very roughly, the tree acts like a structure attached to the runway whose effective behavior depends on its root value. A wave packet arriving from the left therefore behaves differently for the two possible NAND outputs.

In one case, most of the relevant part of the packet is reflected back toward the negative side of the runway. In the other case, a larger part travels through the root region to the positive side.

The implementation therefore divides the final probability into three main regions:

```text
negative runway       tree/root region       positive runway
   reflection                                  transmission

<------------------- | ------------------->
```

The code calculates

```text
reflection probability
tree probability
transmission probability
```

and uses the transmission probability as the decision statistic.

For the calibrated profiles in this repository:

```text
transmission < threshold  -> predicted NAND value 0
transmission >= threshold -> predicted NAND value 1
```

The threshold is not assumed to be universally \(0.5\). For these small finite graphs it is calibrated separately for each supported tree size.

## Continuous evolution versus a Qiskit circuit

Directly calculating

$$
e^{-i(H_D+H_O)t}
$$

is useful as a reference, but it hides the important question of **how access to the unknown input is counted**.

The discrete-query version instead separates the driver and oracle parts.

For

$$
\Delta t=\frac{t}{r},
$$

the implementation uses the symmetric product formula

$$
e^{-i(H_D+H_O)t}
\approx
\left(
e^{-iH_D\Delta t/2}
e^{-iH_O\Delta t}
e^{-iH_D\Delta t/2}
\right)^r.
$$

Increasing \(r\) gives a finer approximation, although it also increases the number of circuit operations and oracle queries.

The connection between the Hamiltonian NAND-tree algorithm and the ordinary quantum query model was studied explicitly by Childs, Cleve, Jordan, and Yonge-Mallo. Their work shows how the continuous-time construction can be converted into a discrete-query algorithm.

## The input oracle

The query circuit uses the standard bit oracle

$$
U_O|k,a\rangle
=
|k,a\oplus x_k\rangle.
$$

The register \(k\) selects a leaf and \(a\) is a work qubit.

For example, if

```text
x = 1 0 1 1
```

then querying address 2 performs

```text
|2, 0> -> |2, 1>
```

because \(x_2=1\).

Querying address 1 leaves the work bit unchanged:

```text
|1, 0> -> |1, 0>
```

because \(x_1=0\).

The oracle is also its own inverse:

$$
U_O^2=I.
$$

That property is important for the walk circuit because the input value is only needed temporarily.

## One query-walk step

The most important part of the Qiskit implementation is the oracle-evolution block.

Conceptually, one oracle step performs:

```text
position register
      |
      v
determine leaf index k
      |
      v
query x_k into work qubit
      |
      v
apply leaf-edge evolution controlled by x_k
      |
      v
query x_k again
      |
      v
work qubit returns to |0>
      |
      v
uncompute temporary leaf address
```

In circuit form, the important sequence is approximately

```python
load leaf address
U_O
controlled leaf-edge evolution
U_O
unload leaf address
```

### Why are there two oracle calls?

The first query computes

$$
|k,0\rangle
\longrightarrow
|k,x_k\rangle.
$$

The value \(x_k\) can then control the corresponding leaf-edge evolution.

But leaving the work qubit in \(|x_k\rangle\) would entangle the workspace with the position register. That extra information is not part of the desired walk state.

The oracle is therefore applied a second time:

$$
|k,x_k\rangle
\longrightarrow
|k,0\rangle.
$$

This is **uncomputation**.

As a result, every product-formula step uses exactly

$$
2
$$

oracle queries, so a circuit with \(r\) query steps has

$$
Q=2r
$$

oracle calls.

Several tests explicitly check both this query count and that the workspace leakage is approximately zero.

## Complete query-walk circuit

A full step has the form

```text
half driver evolution
        |
        v
oracle evolution block
        |
        v
half driver evolution
```

or mathematically,

$$
e^{-iH_D\Delta t/2}
e^{-iH_O\Delta t}
e^{-iH_D\Delta t/2}.
$$

Repeating this block produces the complete walk:

```text
initial runway packet
        |
        v
D/2 -> O -> D/2
        |
        v
D/2 -> O -> D/2
        |
       ...
        |
        v
measure position
        |
        v
transmission probability
        |
        v
NAND prediction
```

The Qiskit implementation is tested against direct small-matrix Hamiltonian evolution to check that the explicit query circuit produces the expected state.

## Calibration of the small models

The parameters stored in `non_qiskit/profiles.py` are **finite-size calibration values**, not asymptotic constants from the papers.

Each profile specifies:

```text
leaf count
runway half-length
packet length
evolution time
decision threshold
number of query steps
```

The current profiles are:

| Leaves | Runway half-length | Packet length | Evolution time | Threshold | Query steps |
|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 3 | 7.8 | 0.37 | 2 |
| 4 | 2 | 3 | 9.4 | 0.16 | 8 |
| 8 | 6 | 5 | 17.75 | 0.48 | 16 |

The calibration procedure evaluates every possible input for a given small tree.

For each candidate parameter set it records

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

A useful profile needs a positive separation

$$
p_{\min}^{(1)}-p_{\max}^{(0)}>0.
$$

The decision threshold can then be placed between those two groups.

This is why the thresholds are different for 2-, 4-, and 8-leaf examples. They come from the behavior of these particular finite graphs rather than from a universal rule.

The calibration search can be run with:

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

More notes on the finite-model choices are in [`EXPERIMENTS.md`](EXPERIMENTS.md).

## Installation

Create a virtual environment if wanted, then install the project in editable mode:

```bash
python -m pip install -e .[dev]
```

The main dependencies are Qiskit, NumPy, and SciPy.

## Basic usage

The simplest interface is:

```python
from qiskit_implementation import evaluate_nand_tree

result = evaluate_nand_tree([1, 0, 1, 1])

print("expected:", result.expected_value)
print("predicted:", result.predicted_value)
print("transmission:", result.transmission_probability)
print("oracle queries:", result.query_count)
```

A sampled evaluation can also be run:

```python
result = evaluate_nand_tree(
    [1, 0, 1, 1],
    shots=4096,
    seed=7,
)

print(result.predicted_value)
print(result.transmission_probability)
```

## Command-line examples

Run the default example:

```bash
python main.py
```

Evaluate a specific NAND tree:

```bash
python main.py evaluate --leaves 1011
```

Inspect the query walk:

```bash
python main.py query-walk \
    --leaves 1011 \
    --runway 2 \
    --packet 3 \
    --time 9.4 \
    --steps 8
```

Verify one of the calibrated profiles:

```bash
python main.py qiskit-verify --leaf-count 4
```

Run the tests:

```bash
python -m pytest
```

Run Ruff:

```bash
python -m ruff check .
```

## Limitations

This repository should not be interpreted as a scalable implementation of the asymptotically optimal NAND-tree algorithm.

The main limitation is the representation of the walk evolution. Parts of the current implementation construct finite Hamiltonian matrices and compile their evolution into Qiskit gates.

That is useful for small experiments because it gives a reference implementation that is easy to compare against exact linear-algebra calculations.

It does **not** scale efficiently as the NAND tree becomes large.

There is therefore an important distinction between the **theoretical algorithm** and this **finite Qiskit implementation of its main ideas**.

The theoretical results establish strong query-complexity bounds for NAND/AND-OR formula evaluation, while this repository is mainly intended to make the oracle, walk, uncomputation, product formula, and measurement rule concrete. The theoretical complexity results should not be attributed to the dense matrix compilation used here.

## References

### NAND trees and formula evaluation

1. **Edward Farhi, Jeffrey Goldstone, and Sam Gutmann — _A Quantum Algorithm for the Hamiltonian NAND Tree_ (2008).**  
   The main continuous-time quantum-walk NAND-tree paper and the closest theoretical starting point for this repository.  
   [Theory of Computing](https://theoryofcomputing.org/articles/v004a008/)

2. **Andrew M. Childs, Richard Cleve, Stephen P. Jordan, and David Yonge-Mallo — _Discrete-Query Quantum Algorithm for NAND Trees_ (2009).**  
   Explains how the Hamiltonian NAND-tree construction can be translated into the conventional discrete-query model.  
   [Theory of Computing](https://theoryofcomputing.org/articles/v005a005/)

3. **Andris Ambainis, Andrew M. Childs, Ben W. Reichardt, Robert Špalek, and Shengyu Zhang — _Any AND-OR Formula of Size N Can Be Evaluated in Time \(N^{1/2+o(1)}\) on a Quantum Computer_ (2007).**  
   An important broader result connecting NAND/AND-OR formula evaluation with near-\(\sqrt N\) quantum algorithms.  
   [arXiv](https://arxiv.org/abs/quant-ph/0703015)

4. **Ben W. Reichardt and Robert Špalek — _Span-Program-Based Quantum Algorithm for Evaluating Formulas_ (2007/2008).**  
   Develops a span-program and graph-based approach to quantum formula evaluation.  
   [arXiv](https://arxiv.org/abs/0710.2630)

5. **Ben W. Reichardt — _Span-Program-Based Quantum Algorithm for Evaluating Unbalanced Formulas_ (2009).**  
   Extends the span-program framework beyond balanced formula instances.  
   [arXiv](https://arxiv.org/abs/0907.1622)

6. **Ben W. Reichardt — _Span Programs and Quantum Query Complexity: The General Adversary Bound Is Nearly Tight for Every Boolean Function_ (2009).**  
   Connects span programs, quantum walks, and the general adversary bound.  
   [arXiv](https://arxiv.org/abs/0904.2759)

### Earlier background

7. **Edward Farhi and Sam Gutmann — _Quantum Computation and Decision Trees_ (1998).**  
   An early paper on continuous-time quantum computation on tree structures and a conceptual predecessor of later quantum-walk algorithms.  
   [arXiv](https://arxiv.org/abs/quant-ph/9706062)

8. **Edward Farhi and Sam Gutmann — _An Analog Analogue of a Digital Quantum Computation_ (1998).**  
   An early continuous-time quantum-search result based on Hamiltonian evolution.  
   [arXiv](https://arxiv.org/abs/quant-ph/9612026)

9. **Howard Barnum and Michael Saks — _A Lower Bound on the Quantum Query Complexity of Read-Once Functions_ (2004).**  
   Gives a quantum-query lower bound for read-once Boolean functions, providing useful context for NAND/AND-OR formula evaluation.  
   [arXiv](https://arxiv.org/abs/quant-ph/0201007)

10. **Peter Høyer, Troy Lee, and Robert Špalek — _Tight Adversary Bounds for Composite Functions_ (2005).**  
    Studies composition in the quantum adversary method, an important tool for Boolean formula query complexity.  
    [arXiv](https://arxiv.org/abs/quant-ph/0509067)

11. **Carlos Mochon — _Hamiltonian Oracles_ (2007).**  
    Develops the continuous-time/Hamiltonian version of the quantum oracle model.  
    [arXiv](https://arxiv.org/abs/quant-ph/0602032)

12. **Dominic W. Berry, Graeme Ahokas, Richard Cleve, and Barry C. Sanders — _Efficient Quantum Algorithms for Simulating Sparse Hamiltonians_ (2007).**  
    Background on implementing sparse Hamiltonian evolution on quantum computers.  
    [arXiv](https://arxiv.org/abs/quant-ph/0508139)

13. **Richard Cleve, Dmytro Gavinsky, and David L. Yonge-Mallo — _Quantum Algorithms for Evaluating MIN-MAX Trees_ (2007).**  
    Applies related quantum-query ideas to MIN-MAX/game-tree evaluation.  
    [arXiv](https://arxiv.org/abs/0710.5794)

### Classical tree-evaluation background

14. **Marc Snir — _Lower Bounds on Probabilistic Linear Decision Trees_ (1985).**  
    An early result on probabilistic decision-tree lower bounds.  
    [DOI](https://doi.org/10.1016/0304-3975(85)90210-5)

15. **Michael Saks and Avi Wigderson — _Probabilistic Boolean Decision Trees and the Complexity of Evaluating Game Trees_ (1986).**  
    A classical result on randomized evaluation of read-once AND/OR trees and game trees.  
    [DOI](https://doi.org/10.1109/SFCS.1986.44)
