# Contributing

Thanks for taking an interest in the project. This repository is still a prototype, so small, well-tested changes are usually more useful than large rewrites.

## Getting started

Clone the repository, create a virtual environment, and install the development dependencies:

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

Then install the project:

```bash
python -m pip install -e .[dev]
```

## Running the tests

Run the normal test suite with:

```bash
python -m pytest -v -rs
```

The Qiskit-specific tests can be run directly with:

```bash
python -m pytest tests_folder/tests/test_qiskit.py tests_folder/tests/test_qiskit_extended.py -v -rs
```

A few exhaustive checks are marked as slow. Run those with:

```bash
python -m pytest tests_folder/tests --run-slow -v -rs
```

The two runnable examples should also continue to work:

```bash
python main.py
python example_usage.py
```

## Code style

The project uses Ruff for linting:

```bash
python -m ruff check .
```

Keep changes straightforward and readable. Prefer small functions and explicit circuit construction over extra abstraction that does not make the algorithm easier to understand.

When changing Qiskit code, add or update tests for the circuit behavior rather than only checking that a circuit can be created. Useful checks include truth tables, statevector equivalence, ancilla cleanup, query counts, measurement behavior, and comparisons against the exact small-instance model.

## Algorithm changes

Changes to the NAND-tree walk, oracle, decision rule, or query accounting should be tied back to the algorithm being implemented. Please mention the relevant paper or construction in the pull request when the connection is not obvious from the code.

For changes that affect the evaluator, verify the supported small tree sizes against the classical result. For changes to approximate evolution, include an exact small-instance comparison where practical.

This repository currently focuses on finite prototype instances. A change that improves scalability is welcome, but it should not silently replace a correct small-instance reference implementation with a less verifiable approximation.

## Pull requests

Before opening a pull request:

1. Run the normal test suite.
2. Run Ruff.
3. Run `python main.py` and `python example_usage.py`.
4. Add tests for new behavior or bug fixes.
5. Keep unrelated formatting or refactoring out of the same pull request when possible.

A pull request description should briefly explain what changed, why it changed, and how it was tested. For algorithm changes, include any effect on correctness, query counts, circuit size, or supported tree sizes.

GitHub Actions runs the regular test suite across the supported Python versions and also checks linting, examples, and package builds. The slow exhaustive Qiskit suite can be started manually from the Actions tab.
