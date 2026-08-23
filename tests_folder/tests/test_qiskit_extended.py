from itertools import product

import numpy as np
import pytest
from scipy.linalg import expm

qiskit = pytest.importorskip("qiskit")
from qiskit.quantum_info import Operator, Statevector  # noqa: E402

from non_qiskit.exact_walk import initial_runway_packet  # noqa: E402
from non_qiskit.graph import build_walk_graph  # noqa: E402
from non_qiskit.profiles import AlgorithmProfile, profile_for  # noqa: E402
from non_qiskit.tree import NandTree  # noqa: E402
from qiskit_implementation._imports import qiskit_api  # noqa: E402
from qiskit_implementation.classifier import evaluate_nand_tree, verify_qiskit_profile  # noqa: E402
from qiskit_implementation.edge_evolution import (  # noqa: E402
    append_two_level_edge_rotation,
)
from qiskit_implementation.evaluator import QuantumNandEvaluator  # noqa: E402
from qiskit_implementation.evolution import (  # noqa: E402
    build_evolution_circuit,
    circuit_resources,
    encoded_initial_state,
    sample_positions,
)
from qiskit_implementation.gates import append_phase_on_state, append_x_on_state  # noqa: E402
from qiskit_implementation.hamiltonian import (  # noqa: E402
    encode_hamiltonian,
    evolution_gate,
    qubits_for_dimension,
)
from qiskit_implementation.oracles import build_bit_oracle, build_phase_oracle  # noqa: E402
from qiskit_implementation.phase_probe import run_phase_probe  # noqa: E402
from qiskit_implementation.query_walk import (  # noqa: E402
    build_oracle_evolution_block,
    build_query_walk_circuit,
    resolve_simulation_backend,
    sample_query_walk,
    sample_query_walk_adaptive,
    simulate_edge_query_walk,
    simulate_query_walk,
    summarize_query_counts,
)
from qiskit_implementation.reversible import build_reversible_nand_circuit  # noqa: E402


def _basis_index(state: Statevector) -> int:
    return int(np.argmax(np.abs(state.data) ** 2))


def _assert_unitary(matrix: np.ndarray, atol: float = 1e-9) -> None:
    identity = np.eye(matrix.shape[0], dtype=complex)
    assert np.allclose(matrix.conj().T @ matrix, identity, atol=atol)


def test_qiskit_api_is_cached_and_complete():
    first = qiskit_api()
    second = qiskit_api()
    assert first is second
    for name in (
        "HamiltonianGate",
        "MCXGate",
        "PauliEvolutionGate",
        "PermutationGate",
        "QuantumCircuit",
        "QFTGate",
        "RXGate",
        "SparsePauliOp",
        "Statevector",
        "StatevectorSampler",
        "phase_estimation",
        "transpile",
    ):
        assert getattr(first, name) is not None


@pytest.mark.parametrize("control_count", [0, 1, 2, 3])
def test_append_x_on_state_has_the_expected_truth_table(control_count):
    controls = list(range(control_count))
    target = control_count
    for marked_state in range(1 << control_count):
        for input_state in range(1 << control_count):
            circuit = qiskit.QuantumCircuit(control_count + 1)
            for bit, qubit in enumerate(controls):
                if (input_state >> bit) & 1:
                    circuit.x(qubit)
            append_x_on_state(circuit, controls, target, marked_state)
            expected_target = int(input_state == marked_state)
            expected = input_state | (expected_target << target)
            assert _basis_index(Statevector.from_instruction(circuit)) == expected


@pytest.mark.parametrize("qubit_count", [1, 2, 3])
def test_append_phase_on_state_marks_exactly_one_basis_state(qubit_count):
    qubits = list(range(qubit_count))
    dimension = 1 << qubit_count
    for marked_state in range(dimension):
        circuit = qiskit.QuantumCircuit(qubit_count)
        append_phase_on_state(circuit, qubits, marked_state)
        diagonal = np.diag(Operator(circuit).data)
        expected = np.ones(dimension, dtype=complex)
        expected[marked_state] = -1
        assert np.allclose(diagonal, expected)


def test_single_leaf_bit_oracle_handles_both_inputs():
    zero = Operator(build_bit_oracle((0,))).data
    one = Operator(build_bit_oracle((1,))).data
    assert np.allclose(zero, np.eye(2))
    assert np.allclose(one, np.array([[0, 1], [1, 0]], dtype=complex))


def test_all_zero_and_all_one_bit_oracles():
    zero = Operator(build_bit_oracle((0, 0, 0, 0))).data
    assert np.allclose(zero, np.eye(8))

    oracle = build_bit_oracle((1, 1, 1, 1))
    for address in range(4):
        circuit = qiskit.QuantumCircuit(3)
        for bit in range(2):
            if (address >> bit) & 1:
                circuit.x(bit)
        circuit.compose(oracle, inplace=True)
        assert _basis_index(Statevector.from_instruction(circuit)) == address | (1 << 2)


@pytest.mark.parametrize("builder", [build_bit_oracle, build_phase_oracle])
def test_oracle_builders_reject_invalid_leaf_data(builder):
    with pytest.raises(ValueError):
        builder(())
    with pytest.raises(ValueError):
        builder((0, 1, 0))
    with pytest.raises(ValueError):
        builder((0, 2))


def test_phase_oracle_is_hermitian_and_an_involution():
    for leaves in product((0, 1), repeat=4):
        matrix = Operator(build_phase_oracle(leaves)).data
        assert np.allclose(matrix, matrix.conj().T)
        assert np.allclose(matrix @ matrix, np.eye(4))


def test_encode_hamiltonian_preserves_matrix_and_zero_pads():
    matrix = np.array([[1, 1j, 0], [-1j, 2, 0.5], [0, 0.5, -1]], dtype=complex)
    encoded = encode_hamiltonian(matrix)
    assert encoded.graph_size == 3
    assert encoded.qubits == 2
    assert np.allclose(encoded.matrix[:3, :3], matrix)
    assert np.allclose(encoded.matrix[3, :], 0)
    assert np.allclose(encoded.matrix[:, 3], 0)


@pytest.mark.parametrize(("dimension", "qubits"), [(1, 1), (2, 1), (3, 2), (8, 3), (9, 4)])
def test_qubits_for_dimension_does_not_require_a_matrix(dimension, qubits):
    assert qubits_for_dimension(dimension) == qubits


def test_two_level_edge_rotation_matches_the_expected_subspace_unitary():
    circuit = qiskit.QuantumCircuit(3)
    time = 0.37
    left, right = 1, 6
    append_two_level_edge_rotation(
        circuit,
        circuit.qubits,
        left,
        right,
        time=time,
    )
    actual = Operator(circuit).data
    expected = np.eye(8, dtype=complex)
    expected[left, left] = expected[right, right] = np.cos(time)
    expected[left, right] = expected[right, left] = 1j * np.sin(time)
    assert np.allclose(actual, expected, atol=1e-9)


@pytest.mark.parametrize(
    "matrix",
    [
        np.ones((2, 3)),
        np.array([[0, 1], [0, 0]], dtype=complex),
    ],
)
def test_encode_hamiltonian_rejects_invalid_matrices(matrix):
    with pytest.raises(ValueError):
        encode_hamiltonian(matrix)


def test_exact_evolution_gate_matches_matrix_exponential():
    matrix = np.array([[0, 1], [1, 0]], dtype=complex)
    time = 0.37
    actual = Operator(evolution_gate(matrix, time=time)).data
    expected = expm(-1j * time * matrix)
    assert np.allclose(actual, expected, atol=1e-10)


@pytest.mark.parametrize("method", ["exact", "trotter", "suzuki"])
def test_evolution_gates_are_unitary(method):
    matrix = np.array([[0.4, 1 - 0.2j], [1 + 0.2j, -0.3]], dtype=complex)
    gate = evolution_gate(matrix, time=0.6, method=method, reps=3)
    _assert_unitary(Operator(gate).data, atol=1e-8)


def test_evolution_gate_validates_method_and_repetitions():
    matrix = np.eye(2)
    with pytest.raises(ValueError):
        evolution_gate(matrix, time=1.0, reps=0)
    with pytest.raises(ValueError):
        evolution_gate(matrix, time=1.0, method="unknown")


def test_encoded_initial_state_matches_the_runway_packet():
    graph = build_walk_graph((1, 0), runway_half_length=3)
    state = encoded_initial_state(graph, packet_length=3)
    expected = initial_runway_packet(graph, 3)
    assert np.allclose(state[: graph.size], expected)
    assert np.allclose(state[graph.size :], 0)
    assert np.isclose(np.vdot(state, state).real, 1.0)


def test_exact_qiskit_walk_matches_direct_scipy_evolution():
    graph = build_walk_graph((1, 0), runway_half_length=3)
    time = 0.41
    initial = encoded_initial_state(graph, packet_length=3)
    circuit = build_evolution_circuit(
        graph,
        packet_length=3,
        time=time,
        method="exact",
    )
    actual = Statevector.from_instruction(circuit).data
    encoded = encode_hamiltonian(graph.hamiltonian)
    expected = expm(-1j * time * encoded.matrix) @ initial
    assert np.isclose(abs(np.vdot(expected, actual)), 1.0, atol=1e-9)


def test_sparse_edge_walk_converges_to_exact_evolution():
    graph = build_walk_graph((1, 0), runway_half_length=2)
    time = 0.15
    initial = encoded_initial_state(graph, packet_length=3)
    encoded = encode_hamiltonian(graph.hamiltonian)
    expected = expm(-1j * time * encoded.matrix) @ initial

    coarse = Statevector.from_instruction(
        build_evolution_circuit(
            graph,
            packet_length=3,
            time=time,
            method="edge",
            reps=1,
        )
    ).data
    refined = Statevector.from_instruction(
        build_evolution_circuit(
            graph,
            packet_length=3,
            time=time,
            method="edge",
            reps=4,
        )
    ).data

    coarse_error = 1 - abs(np.vdot(expected, coarse)) ** 2
    refined_error = 1 - abs(np.vdot(expected, refined)) ** 2
    assert refined_error < coarse_error


def test_symmetric_split_improves_with_more_steps_for_small_time():
    graph = build_walk_graph((1, 0), runway_half_length=2)
    time = 0.25
    exact = Statevector.from_instruction(
        build_evolution_circuit(graph, packet_length=3, time=time, method="exact")
    ).data

    one_step = Statevector.from_instruction(
        build_evolution_circuit(
            graph,
            packet_length=3,
            time=time,
            method="symmetric",
            reps=1,
        )
    ).data
    eight_steps = Statevector.from_instruction(
        build_evolution_circuit(
            graph,
            packet_length=3,
            time=time,
            method="symmetric",
            reps=8,
        )
    ).data

    error_one = 1 - abs(np.vdot(exact, one_step)) ** 2
    error_eight = 1 - abs(np.vdot(exact, eight_steps)) ** 2
    assert error_eight < error_one


def test_position_sampling_is_seeded_and_conserves_shots():
    graph = build_walk_graph((1, 0), runway_half_length=2)
    circuit = build_evolution_circuit(
        graph,
        packet_length=3,
        time=0.2,
        method="exact",
    )
    first = sample_positions(graph, circuit, shots=128, seed=19)
    second = sample_positions(graph, circuit, shots=128, seed=19)
    assert first == second
    assert sum(first.values()) == 128
    with pytest.raises(ValueError):
        sample_positions(graph, circuit, shots=0)


def test_circuit_resource_report_has_consistent_counts():
    graph = build_walk_graph((1, 0), runway_half_length=2)
    circuit = build_evolution_circuit(
        graph,
        packet_length=3,
        time=0.2,
        method="exact",
    )
    resources = circuit_resources(circuit)
    assert resources["qubits"] == circuit.num_qubits
    assert resources["depth"] >= 1
    assert resources["size"] == sum(resources["operations"].values())
    assert "hamiltonian" not in resources["operations"]
    assert "initialize" not in resources["operations"]


def test_zero_time_oracle_evolution_block_is_identity():
    graph = build_walk_graph((1, 0), runway_half_length=2)
    block = build_oracle_evolution_block(graph, (1, 0), time=0.0)
    matrix = Operator(block).data
    assert np.allclose(matrix, np.eye(matrix.shape[0]), atol=1e-9)


def test_query_walk_circuit_uses_expected_register_width():
    leaves = (1, 0, 1, 1)
    graph, circuit = build_query_walk_circuit(
        leaves,
        runway_half_length=2,
        packet_length=3,
        time=0.4,
        steps=2,
    )
    position_bits = encode_hamiltonian(graph.hamiltonian).qubits
    address_bits = NandTree(leaves).depth
    assert circuit.num_qubits == position_bits + address_bits + 1
    assert circuit.name == "query_walk"


@pytest.mark.parametrize("leaves", tuple(product((0, 1), repeat=2)))
def test_matrix_free_edge_simulator_matches_qiskit_statevector(leaves):
    profile = profile_for(2)
    graph, circuit = build_query_walk_circuit(
        leaves,
        runway_half_length=profile.runway_half_length,
        packet_length=profile.packet_length,
        time=profile.evolution_time,
        steps=profile.query_steps,
        driver_reps=4,
    )
    matrix_free = simulate_edge_query_walk(
        graph,
        packet_length=profile.packet_length,
        time=profile.evolution_time,
        steps=profile.query_steps,
        threshold=profile.threshold,
        driver_reps=4,
    )
    statevector = simulate_query_walk(
        graph,
        circuit,
        steps=profile.query_steps,
        threshold=profile.threshold,
    )

    assert matrix_free.simulation_backend == "edge"
    assert statevector.simulation_backend == "qiskit"
    assert np.allclose(matrix_free.state, statevector.state[: graph.size], atol=1e-9)
    assert matrix_free.transmission_probability == pytest.approx(
        statevector.transmission_probability,
        abs=1e-9,
    )


def test_simulation_backend_resolution_and_validation():
    assert resolve_simulation_backend("auto", "sparse") == "edge"
    assert resolve_simulation_backend("auto", "dense") == "qiskit"
    assert resolve_simulation_backend("qiskit", "sparse") == "qiskit"
    with pytest.raises(ValueError, match="requires evolution_backend"):
        resolve_simulation_backend("edge", "dense")
    with pytest.raises(ValueError, match="simulation_backend"):
        resolve_simulation_backend("unknown", "sparse")


def test_zero_time_query_walk_keeps_packet_on_the_left():
    graph, circuit = build_query_walk_circuit(
        (1, 0),
        runway_half_length=3,
        packet_length=3,
        time=0.0,
        steps=2,
    )
    result = simulate_query_walk(graph, circuit, steps=2, threshold=0.5)
    assert np.isclose(result.transmission_probability, 0.0, atol=1e-10)
    assert np.isclose(result.reflection_probability, 1.0, atol=1e-10)
    assert np.isclose(result.tree_probability, 0.0, atol=1e-10)
    assert result.workspace_leakage < 1e-10
    assert result.padding_leakage < 1e-10


def test_query_sampler_is_seeded_and_reports_all_shots():
    profile = profile_for(2)
    graph, circuit = build_query_walk_circuit(
        (1, 0),
        runway_half_length=profile.runway_half_length,
        packet_length=profile.packet_length,
        time=profile.evolution_time,
        steps=profile.query_steps,
    )
    first = sample_query_walk(
        graph,
        circuit,
        steps=profile.query_steps,
        threshold=profile.threshold,
        shots=128,
        seed=31,
    )
    second = sample_query_walk(
        graph,
        circuit,
        steps=profile.query_steps,
        threshold=profile.threshold,
        shots=128,
        seed=31,
    )
    assert first == second
    assert first.shots == 128
    assert first.valid_shots + first.leakage_shots == 128
    assert first.total_query_count == first.query_count * first.shots


def test_query_sampling_validates_arguments():
    graph, circuit = build_query_walk_circuit(
        (1, 0),
        runway_half_length=2,
        packet_length=3,
        time=0.2,
        steps=1,
    )
    with pytest.raises(ValueError):
        sample_query_walk(graph, circuit, steps=1, threshold=0.5, shots=0)
    with pytest.raises(ValueError):
        sample_query_walk_adaptive(
            graph,
            circuit,
            steps=1,
            threshold=0.5,
            min_shots=0,
        )
    with pytest.raises(ValueError):
        sample_query_walk_adaptive(
            graph,
            circuit,
            steps=1,
            threshold=0.5,
            min_shots=64,
            max_shots=32,
        )
    with pytest.raises(ValueError):
        sample_query_walk_adaptive(
            graph,
            circuit,
            steps=1,
            threshold=0.5,
            batch_shots=0,
        )


def test_count_summary_handles_spaced_bitstrings_and_padding():
    graph = build_walk_graph((1, 0), runway_half_length=2)
    position_bits = encode_hamiltonian(graph.hamiltonian).qubits
    total_bits = position_bits + 2
    transmitted = graph.runway_index(1)
    reflected = graph.runway_index(-1)
    padding = graph.size

    def spaced(value: int) -> str:
        bits = format(value, f"0{total_bits}b")
        return f"{bits[:-position_bits]} {bits[-position_bits:]}"

    counts = {
        spaced(transmitted): 8,
        spaced(reflected): 4,
        spaced(padding): 3,
    }
    result = summarize_query_counts(graph, counts, steps=3, threshold=0.5)
    assert result.transmitted == 8
    assert result.reflected == 4
    assert result.padding == 3
    assert result.valid_shots == 12
    assert result.shots == 15
    assert result.predicted_value == 1


def test_count_summary_rejects_empty_or_fully_invalid_results():
    graph = build_walk_graph((1, 0), runway_half_length=2)
    with pytest.raises(ValueError):
        summarize_query_counts(graph, {}, steps=1, threshold=0.5)

    position_bits = encode_hamiltonian(graph.hamiltonian).qubits
    dirty = 1 << position_bits
    with pytest.raises(ValueError):
        summarize_query_counts(
            graph,
            {format(dirty, f"0{position_bits + 2}b"): 10},
            steps=1,
            threshold=0.5,
        )


def test_phase_probe_probabilities_are_normalized():
    result = run_phase_probe(
        (1, 0),
        runway_half_length=3,
        packet_length=3,
        evaluation_qubits=3,
        evolution_time=0.2,
        zero_phase_bins=1,
    )
    assert np.isclose(sum(result.phase_probabilities.values()), 1.0, atol=1e-9)
    assert 0.0 <= result.zero_phase_weight <= 1.0
    assert len(result.phase_probabilities) <= 8


def test_identity_phase_probe_has_unit_zero_phase_weight():
    result = run_phase_probe(
        (1, 0),
        runway_half_length=3,
        packet_length=3,
        evaluation_qubits=3,
        evolution_time=0.0,
        zero_phase_bins=0,
    )
    assert np.isclose(result.zero_phase_weight, 1.0, atol=1e-9)


def test_phase_probe_validates_parameters():
    with pytest.raises(ValueError):
        run_phase_probe((1, 0), evaluation_qubits=0)
    with pytest.raises(ValueError):
        run_phase_probe((1, 0), zero_phase_bins=-1)


def test_dense_mode_classifies_every_two_leaf_input():
    for leaves in product((0, 1), repeat=2):
        result = evaluate_nand_tree(leaves, mode="dense")
        assert result.correct
        assert result.query_count == 0
        assert result.shot_result is None
        assert result.statevector_result is None


def test_evaluator_rejects_conflicting_or_invalid_options():
    with pytest.raises(ValueError):
        evaluate_nand_tree((1, 0), shots=10, confidence=0.9)
    with pytest.raises(ValueError):
        evaluate_nand_tree((1, 0), shots=10, mode="dense")
    with pytest.raises(ValueError):
        evaluate_nand_tree((1, 0), mode="unknown")

    wrong_profile = AlgorithmProfile(4, 2, 3, 1.0, 0.5, 1)
    with pytest.raises(ValueError):
        evaluate_nand_tree((1, 0), profile=wrong_profile)


def test_verification_summary_is_internally_consistent():
    verification = verify_qiskit_profile(2)
    assert verification.inputs == 4
    assert verification.correct == 4
    assert verification.accuracy == 1.0
    assert verification.separation_margin == pytest.approx(
        verification.smallest_one_probability - verification.largest_zero_probability
    )
    assert verification.failed_inputs == ()


def test_quantum_nand_evaluator_wrappers_return_consistent_values():
    evaluator = QuantumNandEvaluator((1, 0), runway_half_length=3, packet_length=3)
    assert evaluator.classical_value == 1

    automatic = evaluator.automatic()
    assert automatic.correct

    dense = evaluator.dense_walk(time=0.3)
    query = evaluator.query_walk(time=0.3, steps=2)
    combined = evaluator.run(time=0.3, include_phase_probe=True, evaluation_qubits=2)

    assert dense.classical_value == query.classical_value == combined.classical_value == 1
    assert dense.walk.norm == pytest.approx(1.0, abs=1e-9)
    assert query.walk.norm == pytest.approx(1.0, abs=1e-9)
    assert combined.phase_probe is not None
    assert combined.phase_probe.evaluation_qubits == 2


def test_reversible_circuit_without_cleanup_contains_all_tree_values():
    for leaves in product((0, 1), repeat=4):
        tree = NandTree(leaves)
        circuit = build_reversible_nand_circuit(leaves, clean_ancillas=False)
        expected = sum(value << node for node, value in enumerate(tree.values()))
        assert _basis_index(Statevector.from_instruction(circuit)) == expected


def test_measured_reversible_circuit_has_one_classical_bit():
    circuit = build_reversible_nand_circuit((1, 0), measure=True)
    assert circuit.num_clbits == 1
    assert circuit.count_ops().get("measure", 0) == 1


@pytest.mark.slow
def test_query_walk_matches_symmetric_split_for_all_four_leaf_inputs():
    profile = profile_for(4)
    for leaves in product((0, 1), repeat=4):
        graph, query_circuit = build_query_walk_circuit(
            leaves,
            runway_half_length=profile.runway_half_length,
            packet_length=profile.packet_length,
            time=profile.evolution_time,
            steps=profile.query_steps,
            matrix_format="dense",
            evolution_backend="dense",
        )
        split_circuit = build_evolution_circuit(
            graph,
            packet_length=profile.packet_length,
            time=profile.evolution_time,
            method="symmetric",
            reps=profile.query_steps,
            evolution_backend="dense",
        )
        query_state = Statevector.from_instruction(query_circuit).data
        position_bits = encode_hamiltonian(graph.hamiltonian).qubits
        clean_position = query_state[: 1 << position_bits]
        split_state = Statevector.from_instruction(split_circuit).data
        assert np.isclose(abs(np.vdot(split_state, clean_position)), 1.0, atol=1e-8)
        assert np.isclose(np.vdot(clean_position, clean_position).real, 1.0, atol=1e-9)
