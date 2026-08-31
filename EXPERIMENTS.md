# Experiment notes

This file records the finite-model checks behind the built-in profiles. These values are implementation results for the small graphs in this repository, not constants from the asymptotic NAND-tree analysis.

## Current profiles

| Leaves | Runway half-length | Packet length | Evolution time | Threshold | Query steps | Oracle calls |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 3 | 7.8 | 0.37 | 2 | 4 |
| 4 | 2 | 3 | 9.4 | 0.16 | 8 | 16 |
| 8 | 6 | 5 | 17.75 | 0.48 | 16 | 32 |

Each symmetric query-walk step uses the input oracle twice: once to compute `x_k` into the work qubit and once to erase it after the controlled leaf-edge evolution.

## Current verification results

I verify each profile by enumerating every possible input of that size. For each mode I record the largest transmission probability among root-0 inputs and the smallest transmission probability among root-1 inputs. Their difference is the separation margin.

| Leaves | Mode | Correct | Largest root-0 transmission | Smallest root-1 transmission | Separation margin | Threshold |
|---:|---|---:|---:|---:|---:|---:|
| 2 | exact | 4/4 | 0.014901 | 0.728411 | 0.713510 | 0.37 |
| 2 | query | 4/4 | 0.173945 | 0.573547 | 0.399601 | 0.37 |
| 4 | exact | 16/16 | 0.014698 | 0.309817 | 0.295119 | 0.16 |
| 4 | query | 16/16 | 0.014698 | 0.287292 | 0.272594 | 0.16 |
| 8 | exact | 256/256 | 0.313524 | 0.648962 | 0.335438 | 0.48 |
| 8 | query | 256/256 | 0.332700 | 0.662253 | 0.329553 | 0.48 |

All six rows have a positive separation margin, so the stored threshold separates the two root values for every enumerated input in the corresponding finite reference model.

## Reproducing the results

Run the non-Qiskit exact and split/query checks with:

```bash
python main.py verify --leaf-count 2 --mode both
python main.py verify --leaf-count 4 --mode both
python main.py verify --leaf-count 8 --mode both
```

The explicit Qiskit query circuit can be checked with:

```bash
python main.py qiskit-verify --leaf-count 2
python main.py qiskit-verify --leaf-count 4
```

The 8-leaf Qiskit verification covers all 256 inputs and is marked as a slow test. Run the full slow suite with:

```bash
python -m pytest tests --run-slow -v -rs
```

## How calibration chooses a profile

`calibrate_profile()` searches candidate runway lengths, packet lengths, and evolution times. For each candidate it enumerates every input and calculates

```text
smallest transmission for root=1
    -
largest transmission for root=0
```

A positive value means one threshold can separate every input in that finite model. The threshold is placed halfway between those two boundary probabilities.

After the continuous-time parameters are selected, calibration tries product-formula step counts in increasing order and keeps the first count that classifies every input with a positive separation margin.

For example, the 4-leaf search can be rerun with:

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

## Tests I rely on most

The most important checks for the query implementation are:

- `test_bit_oracle_truth_table`
- `test_bit_oracle_is_an_involution`
- `test_two_query_oracle_block_matches_oracle_hamiltonian`
- `test_query_walk_matches_symmetric_split_for_all_two_leaf_inputs`
- `test_query_walk_counts_calls_and_cleans_workspace`
- the slow four-leaf query/split comparison
- the slow exhaustive eight-leaf Qiskit profile verification

These tests cover the input lookup, uncomputation, query count, workspace cleanup, and agreement with the reference evolution.

## Limitation of these experiments

The reference implementation uses dense finite Hamiltonian matrices, and parts of the Qiskit implementation compile small matrix evolutions into circuits. This makes exact comparisons straightforward, but it is not a scalable representation for large NAND trees.
