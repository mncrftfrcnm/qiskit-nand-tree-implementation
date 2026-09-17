from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

from non_qiskit.profiles import BUILTIN_PROFILES, verify_profile


def collect_profile_results():
    rows = []
    for leaf_count, profile in sorted(BUILTIN_PROFILES.items()):
        for mode in ("exact", "query"):
            rows.append(verify_profile(profile, mode=mode))
    return rows


def write_profile_artifacts(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = collect_profile_results()
    records = [asdict(result) | {"passed": result.passed} for result in results]

    with (output_dir / "profiles.json").open("w", encoding="utf-8") as handle:
        json.dump(records, handle, indent=2)
        handle.write("\n")

    with (output_dir / "profiles.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

    _write_margin_plot(results, output_dir / "separation_margins.svg")


def _write_margin_plot(results, path: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("plot generation requires the 'plot' extra") from exc

    labels = [f"N={row.leaf_count}\n{row.mode}" for row in results]
    margins = [row.separation_margin for row in results]
    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.bar(labels, margins)
    axis.axhline(0.0, linewidth=1)
    axis.set_ylabel("Separation margin")
    axis.set_title("Calibrated finite NAND-tree profile separation")
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(path)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate calibrated profile artifacts")
    parser.add_argument("--output", type=Path, default=Path("results/profiles"))
    args = parser.parse_args()
    write_profile_artifacts(args.output)
    print(f"wrote profile artifacts to {args.output}")


if __name__ == "__main__":
    main()
