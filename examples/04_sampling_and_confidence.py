"""Compare fixed-shot, confidence-based, and adaptive sampling."""

from qiskit_implementation import evaluate_nand_tree


def _summary(label: str, result) -> None:
    sampled = result.shot_result
    assert sampled is not None
    print(label)
    print("  predicted root:", sampled.predicted_value)
    interval = f"[{sampled.confidence_low:.3f}, {sampled.confidence_high:.3f}]"
    print("  transmission interval:", interval)
    print("  shots / valid shots:", f"{sampled.shots} / {sampled.valid_shots}")
    print("  leakage shots:", sampled.leakage_shots)
    print("  total oracle calls:", sampled.total_query_count)


def main() -> None:
    leaves = (1, 0)
    dense = evaluate_nand_tree(leaves, mode="dense")
    query = evaluate_nand_tree(leaves, mode="query")
    fixed = evaluate_nand_tree(leaves, mode="query", shots=256, seed=7)
    confidence = evaluate_nand_tree(leaves, mode="query", confidence=0.99, seed=7)
    adaptive = evaluate_nand_tree(
        leaves,
        mode="query",
        adaptive=True,
        min_shots=128,
        max_shots=1024,
        batch_shots=128,
        seed=7,
    )

    print("Sampling modes")
    print("deterministic dense/query roots:", dense.predicted_value, query.predicted_value)
    _summary("fixed shots", fixed)
    _summary("confidence-derived shots", confidence)
    _summary("adaptive shots", adaptive)

    assert dense.correct and query.correct
    assert fixed.correct and confidence.correct and adaptive.correct
    print("Example completed successfully.")


if __name__ == "__main__":
    main()
