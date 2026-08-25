# Example commands

Run these from the repository root after installing the development dependencies:

```bash
python -m pip install -e ".[dev]"
```

## Compare dense and query results

```bash
python main.py evaluate --leaves 1011 --mode dense
python main.py evaluate --leaves 1011 --mode query
python main.py verify --leaf-count 4 --mode both
```

Dense mode is the exact finite-Hamiltonian reference. Query mode exposes the
oracle count and uses the matrix-free edge simulator by default. To run its full
Qiskit circuit, add `--simulation-backend qiskit`.

## Product-formula convergence

```bash
python main.py convergence \
  --leaves 10 \
  --runway 3 \
  --packet 3 \
  --time 0.7 \
  --steps 1,2,4,8,16
```

The output includes fidelity, state error, transmission error, and oracle calls
for each step count.

## Inspect a graph

```bash
python main.py graph --leaves 1011 --runway 3
python main.py graph --leaves 1011 --runway 3 --matrix-format dense
```

## Sampling

Sampling belongs to query mode in the current API:

```bash
python main.py evaluate --leaves 10 --mode query --shots 512 --seed 17
python main.py evaluate --leaves 10 --mode query --confidence 0.99 --seed 17
```

## Custom size

There is no built-in profile above eight leaves, so all experiment values must be
given explicitly:

```bash
python main.py evaluate \
  --leaves 0000000000000000 \
  --mode query \
  --runway 16 --packet 8 --time 4 --steps 16 --threshold 0.5
```

This command runs, but its threshold and step count are trial values until the
full classification margin is checked.

## Python examples

```bash
python example_usage.py
for file in examples/*.py; do python "$file"; done
```

Every script exercises both dense and query evaluation. The sampling and oracle
operations inside examples 04 and 05 remain query-only because those features
are part of the query implementation.
