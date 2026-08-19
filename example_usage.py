import sys

from qiskit_implementation import evaluate_nand_tree


def main() -> int:
    leaves = (1, 0)
    query = evaluate_nand_tree(leaves)
    dense = evaluate_nand_tree(leaves, mode="dense")
    sampled = evaluate_nand_tree(leaves, shots=512, seed=17)
    shots = sampled.shot_result
    leaf_bits = "".join(str(bit) for bit in leaves)

    print("Qiskit NAND-tree example")
    print(f"leaves: {leaf_bits}")
    print(f"expected root: {query.expected_value}")
    print(
        "query edge simulation: "
        f"root={query.predicted_value}, "
        f"transmission={query.transmission_probability:.6f}, "
        f"oracle calls={query.query_count}"
    )
    print(
        "dense reference: "
        f"root={dense.predicted_value}, "
        f"transmission={dense.transmission_probability:.6f}"
    )
    print(
        "sampled: "
        f"root={sampled.predicted_value}, "
        f"transmission={shots.transmission_probability:.6f}, "
        f"95% CI=({shots.confidence_low:.6f}, {shots.confidence_high:.6f}), "
        f"total oracle calls={shots.total_query_count}"
    )
    modes_agree = query.predicted_value == dense.predicted_value
    return 0 if query.correct and dense.correct and sampled.correct and modes_agree else 1


if __name__ == "__main__":
    sys.exit(main())
