# Example experiments

These are a few concrete ways I use the repository when checking the finite NAND-tree model.

## Compare the exact and split/query reference models

To see whether both reference models separate NAND outputs for the same calibrated profile:

```bash
python main.py verify --leaf-count 4 --mode both
```

The output includes the largest root-0 transmission, the smallest root-1 transmission, and
the separation margin for both modes.

## Check product-formula convergence

To see how the symmetric split approaches the exact finite walk as the number of steps grows:

```bash
python main.py convergence \
  --leaves 10 \
  --runway 3 \
  --packet 3 \
  --time 0.7 \
  --steps 1,2,4,8,16
```

This reports state fidelity, state error, transmission error, and oracle-call count at each step
count.

## Inspect the graph built for an input

```bash
python main.py graph --leaves 1011 --runway 3
```

This is useful for checking the number of vertices, total edges, oracle edges, and classical root
value before running a quantum circuit.

## Compare query and dense Qiskit evaluation

```bash
python main.py evaluate --leaves 1011 --mode query
python main.py evaluate --leaves 1011 --mode dense
```

The query mode exposes the explicit oracle-query count. Dense mode is a small-matrix reference and
reports zero input-oracle queries.

## Look at finite-shot behavior

```bash
python main.py evaluate --leaves 10 --shots 512 --seed 17
python main.py evaluate --leaves 10 --confidence 0.99 --seed 17
```

The first command fixes the number of samples. The second uses the calibrated separation gap to
choose a shot count for the requested confidence level.

For a short Python example that compares query-statevector, dense-reference, and sampled results,
run:

```bash
python example_usage.py
```
