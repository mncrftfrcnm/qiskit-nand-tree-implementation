import sys

from qiskit_implementation.classifier import evaluate_nand_tree


def main() -> int:
    leaves = (1, 0)
    exact = evaluate_nand_tree(leaves)
    sampled = evaluate_nand_tree(leaves, shots=512, seed=17)
    shots = sampled.shot_result
    leaf_bits = "".join(str(bit) for bit in leaves)

    print("Qiskit NAND-tree example")
    print(f"leaves: {leaf_bits}")
    print(f"expected root: {exact.expected_value}")
    print(
        "statevector: "
        f"root={exact.predicted_value}, "
        f"transmission={exact.transmission_probability:.6f}, "
        f"oracle calls={exact.query_count}"
    )
    print(
        "sampled: "
        f"root={sampled.predicted_value}, "
        f"transmission={shots.transmission_probability:.6f}, "
        f"95% CI=({shots.confidence_low:.6f}, {shots.confidence_high:.6f}), "
        f"total oracle calls={shots.total_query_count}"
    )
    return 0 if exact.correct and sampled.correct else 1


if __name__ == "__main__":
    sys.exit(main())
