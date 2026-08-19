import argparse
import json
import sys
from collections.abc import Iterable, Sequence
from dataclasses import asdict
from pathlib import Path

import numpy as np

from non_qiskit.analysis import scaling_report
from non_qiskit.calibration import calibrate_profile
from non_qiskit.classical import evaluate_bottom_up, evaluate_short_circuit
from non_qiskit.convergence import product_formula_convergence
from non_qiskit.exact_walk import run_continuous_walk
from non_qiskit.graph import build_walk_graph
from non_qiskit.profiles import BUILTIN_PROFILES, profile_for, verify_profile
from non_qiskit.scattering import analyze_scattering
from non_qiskit.tree import NandTree


def parse_leaves(value: str):
    cleaned = value.replace(",", "").replace(" ", "")
    if not cleaned or any(character not in "01" for character in cleaned):
        raise argparse.ArgumentTypeError("use a bit string such as 1011")
    return NandTree(int(character) for character in cleaned).leaves


def _parse_ints(value: str):
    values = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def _add_matrix_format(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--matrix-format",
        choices=("sparse", "dense"),
        default="sparse",
        help="graph storage format (sparse is the default)",
    )


def _add_simulation_backend(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--simulation-backend",
        choices=("auto", "edge", "qiskit"),
        default="auto",
        help="edge is fast and matrix-free; qiskit executes the full statevector circuit",
    )


def _custom_experiment(arguments) -> object | None:
    names = ("runway", "packet", "time", "steps", "threshold")
    values = {name: getattr(arguments, name) for name in names}
    if not any(value is not None for value in values.values()):
        return None
    missing = [name for name, value in values.items() if value is None]
    if missing:
        raise ValueError(
            "custom evaluation requires --runway, --packet, --time, --steps, and "
            f"--threshold; missing: {', '.join(missing)}"
        )

    from qiskit_implementation.walk_parameters import NandExperimentConfig, WalkParameters

    return NandExperimentConfig(
        walk=WalkParameters(
            runway_half_length=values["runway"],
            packet_length=values["packet"],
            evolution_time=values["time"],
        ),
        query_steps=values["steps"],
        threshold=values["threshold"],
    )


# python -m pytest -v -rs
# python main.py
# python example_usage.py


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Small NAND-tree experiments")
    commands = root.add_subparsers(dest="command", required=True)

    classical = commands.add_parser("classical")
    classical.add_argument("--leaves", type=parse_leaves, required=True)

    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--leaves", type=parse_leaves, required=True)
    evaluate.add_argument("--mode", choices=("query", "dense"), default="query")
    evaluate.add_argument("--shots", type=int)
    evaluate.add_argument("--confidence", type=float)
    evaluate.add_argument("--adaptive", action="store_true")
    evaluate.add_argument("--min-shots", type=int, default=256)
    evaluate.add_argument("--max-shots", type=int, default=8192)
    evaluate.add_argument("--batch-shots", type=int, default=256)
    evaluate.add_argument("--seed", type=int)
    _add_matrix_format(evaluate)
    evaluate.add_argument("--evolution-backend", choices=("sparse", "dense"), default="sparse")
    _add_simulation_backend(evaluate)
    evaluate.add_argument("--driver-reps", type=int, default=4)
    custom = evaluate.add_argument_group("custom experiment (required beyond built-in profiles)")
    custom.add_argument("--runway", type=int)
    custom.add_argument("--packet", type=int)
    custom.add_argument("--time", type=float)
    custom.add_argument("--steps", type=int)
    custom.add_argument("--threshold", type=float)

    verify = commands.add_parser("verify")
    verify.add_argument("--leaf-count", type=int, choices=sorted(BUILTIN_PROFILES), required=True)
    verify.add_argument("--mode", choices=("exact", "query", "both"), default="both")
    _add_matrix_format(verify)

    benchmark = commands.add_parser("benchmark")
    benchmark.add_argument("--mode", choices=("exact", "query", "both"), default="both")
    _add_matrix_format(benchmark)

    commands.add_parser("scaling")

    convergence = commands.add_parser("convergence")
    convergence.add_argument("--leaves", type=parse_leaves, required=True)
    convergence.add_argument("--runway", type=int, default=6)
    convergence.add_argument("--packet", type=int, default=4)
    convergence.add_argument("--time", type=float, default=2.0)
    convergence.add_argument("--steps", type=_parse_ints, default=(1, 2, 4, 8, 16))
    _add_matrix_format(convergence)

    qiskit_verify = commands.add_parser("qiskit-verify")
    qiskit_verify.add_argument(
        "--leaf-count", type=int, choices=sorted(BUILTIN_PROFILES), required=True
    )
    qiskit_verify.add_argument("--shots", type=int)
    qiskit_verify.add_argument("--seed", type=int)
    _add_matrix_format(qiskit_verify)
    qiskit_verify.add_argument("--evolution-backend", choices=("sparse", "dense"), default="sparse")
    _add_simulation_backend(qiskit_verify)
    qiskit_verify.add_argument("--driver-reps", type=int, default=4)

    calibrate = commands.add_parser("calibrate")
    calibrate.add_argument("--leaf-count", type=int, choices=(2, 4, 8), required=True)
    calibrate.add_argument("--runways", type=_parse_ints, default=(2, 3, 4, 5, 6))
    calibrate.add_argument("--packets", type=_parse_ints, default=(2, 3, 4, 5))
    calibrate.add_argument("--time-start", type=float, default=0.5)
    calibrate.add_argument("--time-stop", type=float, default=20.0)
    calibrate.add_argument("--time-points", type=int, default=79)
    calibrate.add_argument("--steps", type=_parse_ints, default=(1, 2, 4, 8, 16, 32))
    calibrate.add_argument("--output", type=Path)
    _add_matrix_format(calibrate)

    graph = commands.add_parser("graph")
    graph.add_argument("--leaves", type=parse_leaves, required=True)
    graph.add_argument("--runway", type=int, default=8)
    _add_matrix_format(graph)

    scatter = commands.add_parser("scatter")
    scatter.add_argument("--leaves", type=parse_leaves, required=True)
    scatter.add_argument("--energy", type=float, default=1e-6)

    exact = commands.add_parser("non-qiskit-walk")
    exact.add_argument("--leaves", type=parse_leaves, required=True)
    exact.add_argument("--runway", type=int, default=12)
    exact.add_argument("--packet", type=int, default=8)
    exact.add_argument("--time", type=float)
    _add_matrix_format(exact)

    reversible = commands.add_parser("reversible")
    reversible.add_argument("--leaves", type=parse_leaves, required=True)
    reversible.add_argument("--dirty", action="store_true")

    quantum = commands.add_parser("qiskit-walk")
    quantum.add_argument("--leaves", type=parse_leaves, required=True)
    quantum.add_argument("--runway", type=int, default=6)
    quantum.add_argument("--packet", type=int, default=4)
    quantum.add_argument("--time", type=float, default=2.0)
    quantum.add_argument(
        "--method",
        choices=("edge", "exact", "trotter", "suzuki", "alternating", "symmetric"),
        default="edge",
    )
    quantum.add_argument("--reps", type=int, default=1)
    quantum.add_argument("--threshold", type=float, default=0.5)
    quantum.add_argument("--resources", action="store_true")
    quantum.add_argument("--draw", action="store_true")
    _add_matrix_format(quantum)
    quantum.add_argument("--evolution-backend", choices=("sparse", "dense"), default="sparse")
    quantum.add_argument("--edge-reps", type=int, default=1)

    query = commands.add_parser("query-walk")
    query.add_argument("--leaves", type=parse_leaves, required=True)
    query.add_argument("--runway", type=int, default=6)
    query.add_argument("--packet", type=int, default=4)
    query.add_argument("--time", type=float, default=2.0)
    query.add_argument("--steps", type=int, default=2)
    query.add_argument("--threshold", type=float, default=0.5)
    query.add_argument("--resources", action="store_true")
    query.add_argument("--draw", action="store_true")
    _add_matrix_format(query)
    query.add_argument("--evolution-backend", choices=("sparse", "dense"), default="sparse")
    _add_simulation_backend(query)
    query.add_argument("--driver-reps", type=int, default=4)

    phase = commands.add_parser("phase-probe")
    phase.add_argument("--leaves", type=parse_leaves, required=True)
    phase.add_argument("--runway", type=int, default=4)
    phase.add_argument("--packet", type=int, default=3)
    phase.add_argument("--evaluation-qubits", type=int, default=4)
    phase.add_argument("--evolution-time", type=float, default=0.25)
    _add_matrix_format(phase)
    phase.add_argument("--evolution-backend", choices=("sparse", "dense"), default="sparse")
    phase.add_argument("--edge-reps", type=int, default=4)

    return root


def print_json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def _verification_modes(value: str) -> Iterable[str]:
    return ("exact", "query") if value == "both" else (value,)


def _evaluation_payload(result) -> dict[str, object]:
    payload: dict[str, object] = {
        "leaves": result.leaves,
        "expected_value": result.expected_value,
        "predicted_value": result.predicted_value,
        "correct": result.correct,
        "mode": result.mode,
        "profile": asdict(result.profile),
        "transmission_probability": result.transmission_probability,
        "query_count": result.query_count,
    }
    if result.shot_result is not None:
        payload["shots"] = asdict(result.shot_result)
    if result.statevector_result is not None:
        state = asdict(result.statevector_result)
        state.pop("state")
        payload["statevector"] = state
    if result.sampling_plan is not None:
        payload["sampling_plan"] = asdict(result.sampling_plan)
    return payload


def run_demo() -> int:
    from qiskit_implementation.classifier import evaluate_nand_tree

    leaves = (1, 0)
    result = evaluate_nand_tree(leaves)

    print("Qiskit NAND-tree example")
    print(f"leaves: {''.join(str(bit) for bit in leaves)}")
    print(f"expected root: {result.expected_value}")
    print(f"measured root: {result.predicted_value}")
    print(f"transmission probability: {result.transmission_probability:.6f}")
    print(f"oracle calls: {result.query_count}")
    return 0 if result.correct else 1


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        return run_demo()

    argument_parser = parser()
    args = argument_parser.parse_args(arguments)

    if args.command == "classical":
        print(NandTree(args.leaves).ascii())
        print_json(
            {
                "bottom_up": asdict(evaluate_bottom_up(args.leaves)),
                "short_circuit": asdict(evaluate_short_circuit(args.leaves)),
            }
        )
        return 0

    if args.command == "evaluate":
        from qiskit_implementation.classifier import evaluate_nand_tree

        try:
            experiment = _custom_experiment(args)
        except (TypeError, ValueError) as error:
            argument_parser.error(str(error))
        result = evaluate_nand_tree(
            args.leaves,
            mode=args.mode,
            shots=args.shots,
            seed=args.seed,
            confidence=args.confidence,
            adaptive=args.adaptive,
            min_shots=args.min_shots,
            max_shots=args.max_shots,
            batch_shots=args.batch_shots,
            experiment=experiment,
            matrix_format=args.matrix_format,
            evolution_backend=args.evolution_backend,
            simulation_backend=args.simulation_backend,
            driver_reps=args.driver_reps,
        )
        print_json(_evaluation_payload(result))
        return 0 if result.correct else 2

    if args.command == "verify":
        profile = profile_for(args.leaf_count)
        print_json(
            {
                "profile": asdict(profile),
                "results": [
                    asdict(
                        verify_profile(
                            profile,
                            mode=mode,
                            matrix_format=args.matrix_format,
                        )
                    )
                    for mode in _verification_modes(args.mode)
                ],
            }
        )
        return 0

    if args.command == "qiskit-verify":
        from qiskit_implementation.classifier import verify_qiskit_profile

        result = verify_qiskit_profile(
            args.leaf_count,
            shots=args.shots,
            seed=args.seed,
            matrix_format=args.matrix_format,
            evolution_backend=args.evolution_backend,
            simulation_backend=args.simulation_backend,
            driver_reps=args.driver_reps,
        )
        print_json(asdict(result))
        return 0 if result.passed else 2

    if args.command == "benchmark":
        rows = []
        for leaf_count in sorted(BUILTIN_PROFILES):
            profile = profile_for(leaf_count)
            rows.append(
                {
                    "profile": asdict(profile),
                    "verification": [
                        asdict(
                            verify_profile(
                                profile,
                                mode=mode,
                                matrix_format=args.matrix_format,
                            )
                        )
                        for mode in _verification_modes(args.mode)
                    ],
                }
            )
        print_json(rows)
        return 0

    if args.command == "scaling":
        print_json([asdict(row) for row in scaling_report()])
        return 0

    if args.command == "convergence":
        print_json(
            [
                asdict(point)
                for point in product_formula_convergence(
                    args.leaves,
                    runway_half_length=args.runway,
                    packet_length=args.packet,
                    time=args.time,
                    steps=args.steps,
                    matrix_format=args.matrix_format,
                )
            ]
        )
        return 0

    if args.command == "calibrate":
        result = calibrate_profile(
            args.leaf_count,
            runway_values=args.runways,
            packet_values=args.packets,
            time_values=np.linspace(args.time_start, args.time_stop, args.time_points),
            step_values=args.steps,
            matrix_format=args.matrix_format,
        )
        payload = {
            "profile": asdict(result.profile),
            "exact_margin": result.exact_margin,
            "query_margin": result.query_margin,
            "exact_accuracy": result.exact_accuracy,
            "query_accuracy": result.query_accuracy,
        }
        if args.output:
            args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print_json(payload)
        return 0

    if args.command == "graph":
        print_json(
            build_walk_graph(
                args.leaves,
                runway_half_length=args.runway,
                matrix_format=args.matrix_format,
            ).summary()
        )
        return 0

    if args.command == "scatter":
        print_json(asdict(analyze_scattering(args.leaves, energy=args.energy)))
        return 0

    if args.command == "non-qiskit-walk":
        result = asdict(
            run_continuous_walk(
                args.leaves,
                runway_half_length=args.runway,
                packet_length=args.packet,
                time=args.time,
                matrix_format=args.matrix_format,
            )
        )
        result.pop("state")
        print_json(result)
        return 0

    if args.command == "reversible":
        from qiskit_implementation.reversible import build_reversible_nand_circuit

        circuit = build_reversible_nand_circuit(
            args.leaves,
            clean_ancillas=not args.dirty,
        )
        print(circuit.draw(output="text", fold=120))
        return 0

    if args.command == "qiskit-walk":
        from qiskit_implementation.evolution import (
            build_evolution_circuit,
            circuit_resources,
            simulate_circuit,
        )

        graph = build_walk_graph(
            args.leaves,
            runway_half_length=args.runway,
            matrix_format=args.matrix_format,
        )
        circuit = build_evolution_circuit(
            graph,
            packet_length=args.packet,
            time=args.time,
            method=args.method,
            reps=args.reps,
            evolution_backend=args.evolution_backend,
            edge_reps=args.edge_reps,
        )
        if args.draw:
            print(circuit.draw(output="text", fold=120))
        result = asdict(
            simulate_circuit(
                graph,
                circuit,
                method=args.method,
                threshold=args.threshold,
                oracle_segments=args.reps if args.method in ("alternating", "symmetric") else 0,
            )
        )
        result.pop("state")
        if args.resources:
            result["resources"] = circuit_resources(circuit)
        print_json(result)
        return 0

    if args.command == "query-walk":
        from qiskit_implementation.evolution import circuit_resources
        from qiskit_implementation.query_walk import (
            build_query_walk_circuit,
            resolve_simulation_backend,
            simulate_edge_query_walk,
            simulate_query_walk,
        )

        simulator = resolve_simulation_backend(
            args.simulation_backend,
            args.evolution_backend,
        )
        circuit = None
        if simulator == "qiskit" or args.draw or args.resources:
            graph, circuit = build_query_walk_circuit(
                args.leaves,
                runway_half_length=args.runway,
                packet_length=args.packet,
                time=args.time,
                steps=args.steps,
                matrix_format=args.matrix_format,
                evolution_backend=args.evolution_backend,
                driver_reps=args.driver_reps,
            )
        else:
            graph = build_walk_graph(
                args.leaves,
                runway_half_length=args.runway,
                matrix_format=args.matrix_format,
            )
        if args.draw and circuit is not None:
            print(circuit.draw(output="text", fold=120))
        if simulator == "edge":
            walk = simulate_edge_query_walk(
                graph,
                packet_length=args.packet,
                time=args.time,
                steps=args.steps,
                threshold=args.threshold,
                driver_reps=args.driver_reps,
            )
        else:
            walk = simulate_query_walk(
                graph,
                circuit,
                steps=args.steps,
                threshold=args.threshold,
            )
        result = asdict(walk)
        result.pop("state")
        if args.resources and circuit is not None:
            result["resources"] = circuit_resources(circuit)
        result["graph_vertices"] = graph.size
        print_json(result)
        return 0

    if args.command == "phase-probe":
        from qiskit_implementation.phase_probe import run_phase_probe

        print_json(
            asdict(
                run_phase_probe(
                    args.leaves,
                    runway_half_length=args.runway,
                    packet_length=args.packet,
                    evaluation_qubits=args.evaluation_qubits,
                    evolution_time=args.evolution_time,
                    matrix_format=args.matrix_format,
                    evolution_backend=args.evolution_backend,
                    edge_reps=args.edge_reps,
                )
            )
        )
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
