# Quantum NAND-tree evaluation

A balanced NAND tree stores one input bit at each leaf and a NAND gate at every internal node.
For four inputs:

```text
                 NAND
               /      \
            NAND      NAND
            /  \      /  \
           x0  x1    x2  x3
```

The value of each internal node is

\[
\operatorname{NAND}(a,b)=1-(a\land b).
\]

For \(N=2^d\) leaves, the query problem is to determine the root value while reading as few
input bits as possible.

## Continuous-time walk

Farhi, Goldstone, and Gutmann attach a path, called the runway, to the root of a complete binary
tree. Every leaf has an auxiliary vertex. The edge between leaf \(j\) and its auxiliary vertex is
present when the hidden bit \(x_j\) is one.

The walk Hamiltonian is minus the graph adjacency matrix:

\[
H=-A=H_D+H_O.
\]

\(H_D\) contains the runway and tree edges. \(H_O\) contains the input-dependent leaf edges. A
right-moving packet starts on the left side of the runway:

\[
\langle r|\psi(0)\rangle=
\begin{cases}
L^{-1/2}e^{ir\pi/2}, & -L+1\le r\le 0,\\
0, & \text{otherwise}.
\end{cases}
\]

It evolves as

\[
|\psi(t)\rangle=e^{-iHt}|\psi(0)\rangle.
\]

Near zero energy, a tree whose root is one transmits the packet and a tree whose root is zero
reflects it. The continuous-time algorithm uses \(O(\sqrt N)\) Hamiltonian-oracle time.

## Qiskit query circuit

The bit oracle is

\[
U_O|k,a\rangle=|k,a\oplus x_k\rangle.
\]

One oracle-evolution block queries the selected leaf into a work qubit, evolves the corresponding
leaf edge, and queries again to clear the work qubit. A symmetric product formula approximates the
full walk:

\[
e^{-i(H_D+H_O)t}\approx
\left(
 e^{-iH_D\Delta t/2}
 e^{-iH_O\Delta t}
 e^{-iH_D\Delta t/2}
\right)^r.
\]

Each step uses two calls to \(U_O\). The repository uses calibrated finite-size parameters for 2,
4, and 8 leaves. These small models reproduce the scattering mechanism, but the dense Hamiltonian
encoding is not the scalable asymptotic construction from the papers.

## Where this project is useful

- Teaching quantum walks, oracle queries, ancilla cleanup, and product-formula simulation.
- Reproducing small NAND-tree examples from the original algorithm papers.
- Comparing exact Hamiltonian evolution with Trotter and Suzuki approximations.
- Inspecting Qiskit circuit depth, gate counts, sampling error, and query counts.
- Testing changes to oracle circuits or finite-model calibration against exhaustive small inputs.

It is not intended for large NAND formulas or as evidence of a practical quantum advantage.

## Run the examples

Install the project:

```bash
python -m pip install -e .[dev]
```

Run the built-in Qiskit example:

```bash
python main.py
```

Run the standalone example:

```bash
python example_usage.py
```

Evaluate a four-leaf input:

```bash
python main.py evaluate --leaves 1011
```

Run the Qiskit tests:

```bash
python -m pytest tests_folder/tests/test_qiskit.py tests_folder/tests/test_qiskit_extended.py -v -rs
```

Include exhaustive slow tests:

```bash
python -m pytest tests_folder/tests --run-slow -v -rs
```

## References

- [Farhi, Goldstone, and Gutmann — *A Quantum Algorithm for the Hamiltonian NAND Tree*](https://theoryofcomputing.org/articles/v004a008/)
- [Childs, Cleve, Jordan, and Yonge-Mallo — *Discrete-Query Quantum Algorithm for NAND Trees*](https://theoryofcomputing.org/articles/v005a005/)
- [Childs, Reichardt, Špalek, and Zhang — *Every NAND Formula of Size N Can Be Evaluated in Time N^(1/2+o(1))*](https://arxiv.org/abs/quant-ph/0703015)
- [Reichardt and Špalek — *Span-Program-Based Quantum Algorithm for Evaluating Formulas*](https://theoryofcomputing.org/articles/v008a013/)
- [IBM Quantum documentation — `StatevectorSampler`](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.primitives.StatevectorSampler)
- [IBM Quantum documentation — `PauliEvolutionGate`](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.circuit.library.PauliEvolutionGate)
