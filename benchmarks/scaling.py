from __future__ import annotations

import argparse
import csv
import json
import math
import time
import tracemalloc
from dataclasses import asdict, dataclass
from pathlib import Path

from non_qiskit.graph import build_walk_graph
from qiskit_implementation.query_walk import simulate_edge_query_walk
from qiskit_implementation.walk_parameters import theoretical_parameters


@dataclass(frozen=True)
class ScalingRow:
    leaf_count: int
    graph_vertices: int
    position_qubits: int
    address_qubits: int
    total_query_qubits: int
    query_steps: int
    oracle_calls: int
    build_seconds: float
    simulation_seconds: float
    peak_memory_bytes: int
    transmission_probability: float


def benchmark_size(
    leaf_count: int,
    *,
    gamma: float = 1.5,
    runway_factor: float = 0.5,
    driver_reps: int = 4,
) -> ScalingRow:
    """Measure one deterministic all-zero instance for a fixed scaling rule."""

    walk = theoretical_parameters(
        leaf_count,
        gamma=gamma,
        runway_factor=runway_factor,
    )
    leaves = (0,) * leaf_count
    query_steps = max(2, math.ceil(math.sqrt(leaf_count)))

    tracemalloc.start()
    started = time.perf_counter()
    graph = build_walk_graph(
        leaves,
        runway_half_length=walk.runway_half_length,
        matrix_format="sparse",
    )
    build_seconds = time.perf_counter() - started

    started = time.perf_counter()
    result = simulate_edge_query_walk(
        graph,
        packet_length=walk.packet_length,
        time=walk.evolution_time,
        steps=query_steps,
        threshold=0.5,
        driver_reps=driver_reps,
    )
    simulation_seconds = time.perf_counter() - started
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    position_qubits = max(1, math.ceil(math.log2(graph.size)))
    address_qubits = int(math.log2(leaf_count))
    return ScalingRow(
        leaf_count=leaf_count,
        graph_vertices=graph.size,
        position_qubits=position_qubits,
        address_qubits=address_qubits,
        total_query_qubits=position_qubits + address_qubits + 1,
        query_steps=query_steps,
        oracle_calls=2 * query_steps,
        build_seconds=build_seconds,
        simulation_seconds=simulation_seconds,
        peak_memory_bytes=peak_memory,
        transmission_probability=result.transmission_probability,
    )


def run_scaling_suite(
    leaf_counts: list[int],
    *,
    gamma: float = 1.5,
    runway_factor: float = 0.5,
    driver_reps: int = 4,
) -> list[ScalingRow]:
    return [
        benchmark_size(
            leaf_count,
            gamma=gamma,
            runway_factor=runway_factor,
            driver_reps=driver_reps,
        )
        for leaf_count in leaf_counts
    ]


def write_artifacts(rows: list[ScalingRow], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    records = [asdict(row) for row in rows]

    with (output_dir / "scaling.json").open("w", encoding="utf-8") as handle:
        json.dump(records, handle, indent=2)
        handle.write("\n")

    with (output_dir / "scaling.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

    _write_plots(rows, output_dir)


def _write_plots(rows: list[ScalingRow], output_dir: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("plot generation requires the 'plot' extra") from exc

    leaves = [row.leaf_count for row in rows]
    series = {
        "runtime_seconds": [row.simulation_seconds for row in rows],
        "peak_memory_mib": [row.peak_memory_bytes / (1024**2) for row in rows],
        "qubits": [row.total_query_qubits for row in rows],
        "oracle_calls": [row.oracle_calls for row in rows],
    }
    labels = {
        "runtime_seconds": "Simulation time (s)",
        "peak_memory_mib": "Peak memory (MiB)",
        "qubits": "Logical query qubits",
        "oracle_calls": "Oracle calls",
    }

    for name, values in series.items():
        figure, axis = plt.subplots()
        axis.plot(leaves, values, marker="o")
        axis.set_xlabel("Leaves (N)")
        axis.set_ylabel(labels[name])
        axis.set_title(f"NAND-tree scaling: {labels[name]}")
        axis.grid(True, alpha=0.25)
        figure.tight_layout()
        figure.savefig(output_dir / f"{name}.svg")
        plt.close(figure)


def _parse_leaf_counts(raw: str) -> list[int]:
    values = [int(value.strip()) for value in raw.split(",") if value.strip()]
    if not values:
        raise argparse.ArgumentTypeError("provide at least one leaf count")
    for value in values:
        if value < 1 or value & (value - 1):
            raise argparse.ArgumentTypeError("leaf counts must be powers of two")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark sparse NAND-tree scaling")
    parser.add_argument("--leaves", type=_parse_leaf_counts, default=[2, 4, 8, 16, 32])
    parser.add_argument("--gamma", type=float, default=1.5)
    parser.add_argument("--runway-factor", type=float, default=0.5)
    parser.add_argument("--driver-reps", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("results/scaling"))
    args = parser.parse_args()

    rows = run_scaling_suite(
        args.leaves,
        gamma=args.gamma,
        runway_factor=args.runway_factor,
        driver_reps=args.driver_reps,
    )
    write_artifacts(rows, args.output)
    for row in rows:
        print(
            f"N={row.leaf_count:<4} vertices={row.graph_vertices:<5} "
            f"qubits={row.total_query_qubits:<3} queries={row.oracle_calls:<4} "
            f"time={row.simulation_seconds:.6f}s "
            f"peak={row.peak_memory_bytes / (1024**2):.2f}MiB"
        )


if __name__ == "__main__":
    main()
