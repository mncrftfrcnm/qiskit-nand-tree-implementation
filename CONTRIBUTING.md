# Contributing

Thanks for taking an interest in the project.

This repository is still a prototype, so small changes that are easy to understand and verify are generally more useful than large rewrites.

## Setup

Clone the repository and create a virtual environment:

```bash
python -m venv .venv
```

On Windows:

```bash
.venv\Scripts\activate
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

Install the project and development dependencies:

```bash
python -m pip install -e ".[dev]"
```

`pyproject.toml` is the source of truth for runtime and development dependencies.

## Before making changes

It helps to run the existing suite first:

```bash
python -m pytest -v -rs
```

You can also check the two runnable examples:

```bash
python main.py
python example_usage.py
```

This gives you a baseline before changing the implementation.

## Tests

New behavior should usually come with a test.

For changes to the Qiskit implementation, useful tests include:

- circuit truth tables;
- statevector comparisons;
- oracle query counts;
- ancilla and workspace cleanup;
- measurement behavior;
- exact-Hamiltonian comparisons;
- query/dense agreement;
- regression cases for specific NAND inputs.

Run the normal suite with:

```bash
python -m pytest -v -rs
```

Some exhaustive checks are marked as slow:

```bash
python -m pytest tests --run-slow -v -rs
```

The slow suite is particularly useful after changing the oracle, query walk, calibration logic, or classification rule.

## Code style

The project uses Ruff:

```bash
python -m ruff check .
```

Many simple lint problems can be fixed automatically:

```bash
python -m ruff check . --fix
```

Keep the implementation fairly direct.

The circuit code is easier to review when register operations and oracle calls are visible instead of hidden behind unnecessary abstraction.

Comments are most useful when they explain why a quantum operation is needed, especially around query counting and uncomputation.

## Algorithm changes

Changes to the NAND-tree algorithm should preserve the distinction between the finite prototype and the theoretical asymptotic algorithm.

If you change:

- the walk graph;
- the oracle;
- the Hamiltonian split;
- the product formula;
- the initial packet;
- the decision threshold;
- query counting;
- calibration parameters;

include a test or experiment showing what changed.

For changes based on a paper, include the relevant reference in the pull request when the connection is not obvious from the code.

Changes to the built-in 2-, 4-, or 8-leaf profiles should be checked against every possible input for that tree size.

If a change affects the stored calibration results, update `EXPERIMENTS.md` as well.

## Pull requests

Before opening a pull request, run:

```bash
python -m pytest -v -rs
python -m ruff check .
python main.py
python example_usage.py
```

A pull request should briefly explain:

- what changed;
- why it changed;
- how it was tested.

For algorithm-related changes, also mention any effect on correctness, query count, circuit size, or supported tree sizes.

Try to keep unrelated formatting changes and algorithm changes in separate pull requests. It makes the implementation much easier to review.

## CI

GitHub Actions runs the regular test suite across the supported Python versions.

It also checks:

- the runnable examples;
- Ruff;
- package building;
- installation of the built wheel;
- the installed `nandtree` CLI, including `nandtree --version`.

The exhaustive Qiskit suite is intentionally separate because it takes longer to run.

A pull request should normally have a green CI run before it is merged.
