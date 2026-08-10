"""Compare Qiskit's dense circuit with the non-Qiskit exact reference walk."""

from non_qiskit.exact_walk import run_continuous_walk
from non_qiskit.profiles import profile_for
from qiskit_implementation import evaluate_nand_tree


def main() -> None:
    leaves = (1, 0, 1, 1)
    profile = profile_for(len(leaves))

    qiskit_result = evaluate_nand_tree(leaves, mode="dense")
    reference_result = run_continuous_walk(
        leaves,
        runway_half_length=profile.runway_half_length,
        packet_length=profile.packet_length,
        time=profile.evolution_time,
    )
    difference = abs(
        qiskit_result.transmission_probability - reference_result.transmission_probability
    )

    print("Qiskit versus non-Qiskit continuous walk")
    print("leaves:", "".join(map(str, leaves)))
    print("Qiskit transmission:", f"{qiskit_result.transmission_probability:.10f}")
    print("reference transmission:", f"{reference_result.transmission_probability:.10f}")
    print("absolute difference:", f"{difference:.3e}")

    assert qiskit_result.expected_value == reference_result.root_value
    assert difference < 1e-8
    print("Example completed successfully.")


if __name__ == "__main__":
    main()
