"""Evaluate a calibrated NAND tree with the public Qiskit API."""

from qiskit_implementation import evaluate_nand_tree


def main() -> None:
    leaves = (1, 0, 1, 1)
    results = [
        evaluate_nand_tree(leaves, mode="dense"),
        evaluate_nand_tree(leaves, mode="query"),
    ]

    print("Basic calibrated evaluation")
    print("leaves:", "".join(map(str, leaves)))
    print("expected root:", results[0].expected_value)
    for result in results:
        print(
            f"{result.mode}: root={result.predicted_value}, "
            f"transmission={result.transmission_probability:.6f}, "
            f"oracle calls={result.query_count}"
        )

    assert all(result.correct for result in results)
    assert results[0].predicted_value == results[1].predicted_value
    print("Example completed successfully.")


if __name__ == "__main__":
    main()
