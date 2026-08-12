"""Plot calibrated transmission probabilities for every four-leaf input."""

import argparse
from collections.abc import Sequence
from itertools import product
from pathlib import Path

import matplotlib.pyplot as plt

from non_qiskit.profiles import profile_for
from qiskit_implementation import evaluate_nand_tree

plt.switch_backend("Agg")


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        description="Plot four-leaf NAND-tree calibration probabilities."
    )
    argument_parser.add_argument(
        "--output",
        type=Path,
        default=Path("calibration-4-leaf.png"),
        help="PNG output path (default: calibration-4-leaf.png)",
    )
    return argument_parser


def main(argv: Sequence[str] | None = None) -> None:
    args = parser().parse_args(argv)
    leaf_count = 4
    profile = profile_for(leaf_count)

    zero_x: list[int] = []
    zero_y: list[float] = []
    one_x: list[int] = []
    one_y: list[float] = []

    for index, leaves in enumerate(product((0, 1), repeat=leaf_count)):
        result = evaluate_nand_tree(leaves)
        if result.expected_value == 0:
            zero_x.append(index)
            zero_y.append(result.transmission_probability)
        else:
            one_x.append(index)
            one_y.append(result.transmission_probability)

    figure, axes = plt.subplots()
    axes.scatter(zero_x, zero_y, label="root = 0")
    axes.scatter(one_x, one_y, label="root = 1")
    axes.axhline(profile.threshold, linestyle="--", label="threshold")
    axes.set_xlabel("input")
    axes.set_ylabel("transmission probability")
    axes.set_title("4-leaf NAND-tree calibration")
    axes.legend()
    figure.tight_layout()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=180)
    plt.close(figure)

    print("Calibration plot saved to:", args.output)
    print("Example completed successfully.")


if __name__ == "__main__":
    main()
