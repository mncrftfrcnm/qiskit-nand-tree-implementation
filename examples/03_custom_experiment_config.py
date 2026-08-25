"""Run an explicitly configured finite NAND-tree experiment."""

from qiskit_implementation import NandExperimentConfig, WalkParameters, evaluate_nand_tree


def main() -> None:
    leaves = (1, 0)
    experiment = NandExperimentConfig(
        walk=WalkParameters(
            runway_half_length=2,
            packet_length=3,
            evolution_time=7.8,
        ),
        query_steps=2,
        threshold=0.37,
    )
    results = [
        evaluate_nand_tree(leaves, mode="dense", experiment=experiment),
        evaluate_nand_tree(leaves, mode="query", experiment=experiment),
    ]

    print("Custom finite experiment")
    print("configuration:", experiment)
    for result in results:
        print(
            f"{result.mode}: root={result.predicted_value}, "
            f"transmission={result.transmission_probability:.6f}"
        )

    # These settings match the calibrated two-leaf profile.  Different custom
    # settings need their own calibration before their Boolean prediction is trusted.
    assert all(result.correct for result in results)
    print("Example completed successfully.")


if __name__ == "__main__":
    main()
