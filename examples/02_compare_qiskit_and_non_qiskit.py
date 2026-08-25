"""Compare both public evaluators with the non-Qiskit exact walk."""

from non_qiskit.exact_walk import run_continuous_walk
from non_qiskit.profiles import profile_for
from qiskit_implementation import evaluate_nand_tree


def main() -> None:
    leaves = (1, 0, 1, 1)
    profile = profile_for(len(leaves))

    dense = evaluate_nand_tree(leaves, mode="dense")
    query = evaluate_nand_tree(leaves, mode="query")
    reference_result = run_continuous_walk(
        leaves,
        runway_half_length=profile.runway_half_length,
        packet_length=profile.packet_length,
        time=profile.evolution_time,
    )
    dense_difference = abs(
        dense.transmission_probability - reference_result.transmission_probability
    )
    query_difference = abs(
        query.transmission_probability - reference_result.transmission_probability
    )

    print("Dense and query evaluation versus the exact continuous walk")
    print("leaves:", "".join(map(str, leaves)))
    print("reference transmission:", f"{reference_result.transmission_probability:.10f}")
    print("dense transmission:", f"{dense.transmission_probability:.10f}")
    print("dense difference:", f"{dense_difference:.3e}")
    print("query transmission:", f"{query.transmission_probability:.10f}")
    print("query difference:", f"{query_difference:.3e}")

    assert dense.expected_value == reference_result.root_value
    assert dense_difference < 1e-8
    assert dense.correct and query.correct
    print("Example completed successfully.")


if __name__ == "__main__":
    main()
