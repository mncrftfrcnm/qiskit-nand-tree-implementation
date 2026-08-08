# Experiment notes

This file records what the small finite model is checking and how the built-in parameters are chosen. I keep it separate from the README because these values are implementation details, not general constants of the NAND-tree algorithm.

## Current profiles

The current built-in profiles are:

| leaves | runway half-length | packet length | evolution time | threshold | query steps | oracle calls |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 3 | 7.8 | 0.37 | 2 | 4 |
| 4 | 2 | 3 | 9.4 | 0.16 | 8 | 16 |
| 8 | 6 | 5 | 17.75 | 0.48 | 16 | 32 |

The last column follows from the query construction: each symmetric walk step queries the input once to load `x_k` and once more to uncompute it, so the query count is `2 * query_steps`.

## What calibration is optimizing

For one tree size, `calibrate_profile()` enumerates every possible input bit string. For each runway/packet/time candidate it records the transmission probabilities separately for inputs whose NAND root is 0 and inputs whose root is 1.

The useful quantity is

```text
smallest transmission for root=1
    -
largest transmission for root=0
```

A positive value means that one threshold can separate every input in that finite model. The calibration threshold is placed halfway between those two boundary probabilities.

After the continuous-time parameters are chosen, the calibration code tries product-formula step counts in increasing order. It keeps the first step count that gets every input correct with a positive separation margin.

This is why the values above should not be treated as theoretical constants or extrapolated to larger NAND trees.

## Reproducing the checks

For the non-Qiskit reference and split-walk model:

```bash
python main.py verify --leaf-count 2 --mode both
python main.py verify --leaf-count 4 --mode both
python main.py verify --leaf-count 8 --mode both
```

Each result reports:

- `largest_zero_probability`
- `smallest_one_probability`
- `separation_margin`
- `threshold`
- classification accuracy across all inputs

For the explicit Qiskit query circuit:

```bash
python main.py qiskit-verify --leaf-count 2
python main.py qiskit-verify --leaf-count 4
```

The exhaustive 8-leaf Qiskit verification covers all 256 input strings and is intentionally marked as a slow test.

## Re-running calibration

The CLI exposes the same search implemented in `non_qiskit/calibration.py`. For example:

```bash
python main.py calibrate \
  --leaf-count 4 \
  --runways 2,3,4,5,6 \
  --packets 2,3,4,5 \
  --time-start 0.5 \
  --time-stop 20.0 \
  --time-points 79 \
  --steps 1,2,4,8,16,32
```

When changing a built-in profile, I would record the old and new separation margins here instead of changing a constant without explaining why.

## Checks that matter most to the query implementation

The most useful tests are not just "does a circuit build?" checks:

1. `test_bit_oracle_truth_table` checks that the address register selects the expected input bit.
2. `test_bit_oracle_is_an_involution` checks the property used to uncompute the queried value.
3. `test_two_query_oracle_block_matches_oracle_hamiltonian` compares the full query/unquery block against direct input-dependent Hamiltonian evolution and checks that the workspace is clean afterward.
4. `test_query_walk_matches_symmetric_split_for_all_two_leaf_inputs` compares the explicit Qiskit construction with the reference split evolution.
5. `test_query_walk_counts_calls_and_cleans_workspace` checks both the `2 * steps` query count and leakage into workspace/padding states.

Those tests are the ones I would look at first after changing the oracle or the walk decomposition.

## What is still limited

The implementation deliberately favors a directly checkable finite model over scalability. The graph Hamiltonian is represented as a dense matrix and the Qiskit implementation compiles small matrix evolutions into circuits. That makes exact comparisons straightforward, but it becomes expensive quickly as the tree grows.

A future scalable version would need a more structured encoding of the walk and oracle rather than extending these calibrated dense instances to large trees.
