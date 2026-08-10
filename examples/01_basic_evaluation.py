"""Evaluate a calibrated NAND tree with the public Qiskit API."""

from qiskit_implementation import evaluate_nand_tree


def main() -> None:
    leaves = (1, 0, 1, 1)
    result = evaluate_nand_tree(leaves)

    print("Basic calibrated evaluation")
    print("leaves:", "".join(map(str, leaves)))
    print("expected root:", result.expected_value)
    print("predicted root:", result.predicted_value)
    print("transmission probability:", f"{result.transmission_probability:.6f}")
    print("input-oracle calls:", result.query_count)

    assert result.correct
    print("Example completed successfully.")


if __name__ == "__main__":
    main()
