from itertools import product

import numpy as np
import pytest

qiskit = pytest.importorskip("qiskit")
from qiskit.quantum_info import Operator, Statevector  # noqa: E402

from non_qiskit.graph import build_walk_graph  # noqa: E402
from non_qiskit.profiles import profile_for  # noqa: E402
from non_qiskit.tree import NandTree  # noqa: E402
from qiskit_implementation.classifier import evaluate_nand_tree, verify_qiskit_profile  # noqa: E402
from qiskit_implementation.evolution import (  # noqa: E402
    build_evolution_circuit,
    simulate_circuit,
)
from qiskit_implementation.hamiltonian import encode_hamiltonian, evolution_gate  # noqa: E402
from qiskit_implementation.oracles import build_bit_oracle, build_phase_oracle  # noqa: E402
from qiskit_implementation.phase_probe import build_phase_probe_circuit  # noqa: E402
from qiskit_implementation.query_walk import (  # noqa: E402
    build_leaf_index_loader,
    build_oracle_evolution_block,
    build_query_walk_circuit,
    run_query_walk,
    summarize_query_counts,
)
from qiskit_implementation.reversible import build_reversible_nand_circuit  # noqa: E402


def basis_index(state) -> int:
    return int(np.argmax(np.abs(state.data) ** 2))


@pytest.mark.parametrize("leaf_count", [2, 4])
def test_reversible_circuit_truth_table_and_cleanup(leaf_count):
    for leaves in product((0, 1), repeat=leaf_count):
        tree = NandTree(leaves)
        circuit = build_reversible_nand_circuit(leaves)
        output = circuit.num_qubits - 1
        expected = tree.root_value << output
        for leaf, bit in enumerate(leaves):
            expected |= bit << tree.leaf_node(leaf)
        state = Statevector.from_instruction(circuit)
        assert basis_index(state) == expected
        assert np.isclose(abs(state.data[expected]) ** 2, 1.0)


def test_bit_oracle_truth_table():
    leaves = (1, 0, 1, 0)
    oracle = build_bit_oracle(leaves)
    for address, bit in enumerate(leaves):
        circuit = qiskit.QuantumCircuit(3)
        for qubit in range(2):
            if (address >> qubit) & 1:
                circuit.x(qubit)
        circuit.compose(oracle, inplace=True)
        expected = address | (bit << 2)
        assert basis_index(Statevector.from_instruction(circuit)) == expected


def test_bit_oracle_is_an_involution():
    # The query walk uses the same oracle once to load x_k and once to erase it.
    # If U_O^2 were not the identity, the work qubit would stay entangled with the walk state.
    for leaves in product((0, 1), repeat=4):
        oracle = build_bit_oracle(leaves)
        circuit = qiskit.QuantumCircuit(3)
        circuit.h(range(3))
        before = Statevector.from_instruction(circuit)
        circuit.compose(oracle, inplace=True)
        circuit.compose(oracle, inplace=True)
        after = Statevector.from_instruction(circuit)
        assert np.allclose(before.data, after.data)


def test_phase_oracle_marks_requested_addresses():
    for leaves in product((0, 1), repeat=4):
        diagonal = np.diag(Operator(build_phase_oracle(leaves)).data)
        expected = np.array([(-1) ** bit for bit in leaves], dtype=complex)
        assert np.allclose(diagonal, expected)


def test_bit_oracle_phase_kickback_matches_phase_oracle():
    for leaves in product((0, 1), repeat=4):
        bit_version = qiskit.QuantumCircuit(3)
        bit_version.h([0, 1])
        bit_version.x(2)
        bit_version.h(2)
        bit_version.compose(build_bit_oracle(leaves), inplace=True)

        phase_version = qiskit.QuantumCircuit(3)
        phase_version.h([0, 1])
        phase_version.x(2)
        phase_version.h(2)
        phase_version.compose(build_phase_oracle(leaves), qubits=[0, 1], inplace=True)

        left = Statevector.from_instruction(bit_version)
        right = Statevector.from_instruction(phase_version)
        assert np.isclose(abs(left.inner(right)), 1.0, atol=1e-10)


def test_encoded_hamiltonian_is_power_of_two_dimension():
    encoded = encode_hamiltonian(np.eye(5))
    assert encoded.qubits == 3
    assert encoded.matrix.shape == (8, 8)


def test_exact_and_split_circuits_preserve_norm():
    graph = build_walk_graph((1, 0), runway_half_length=3)
    for method in ("exact", "alternating", "symmetric"):
        circuit = build_evolution_circuit(
            graph,
            packet_length=3,
            time=1.0,
            method=method,
            reps=2,
        )
        result = simulate_circuit(graph, circuit, method=method)
        assert np.isclose(result.norm, 1.0, atol=1e-9)


def test_phase_probe_has_evaluation_and_system_qubits():
    graph, circuit = build_phase_probe_circuit(
        (1, 0),
        runway_half_length=3,
        packet_length=3,
        evaluation_qubits=3,
    )
    encoded = encode_hamiltonian(graph.hamiltonian)
    assert graph.matrix_format == "sparse"
    assert circuit.num_qubits == 3 + encoded.qubits


def test_leaf_index_loader_maps_leaf_and_oracle_vertices():
    graph = build_walk_graph((0, 0, 0, 0), runway_half_length=2)
    loader = build_leaf_index_loader(graph)
    position_bits = encode_hamiltonian(graph.hamiltonian).qubits

    for leaf in range(4):
        for kind, index in (
            ("tree", graph.tree.leaf_node(leaf)),
            ("oracle", leaf),
        ):
            vertex = graph.vertex_index(kind, index)
            circuit = qiskit.QuantumCircuit(loader.num_qubits)
            for bit in range(position_bits):
                if (vertex >> bit) & 1:
                    circuit.x(bit)
            circuit.compose(loader, inplace=True)
            expected = vertex | (leaf << position_bits)
            assert basis_index(Statevector.from_instruction(circuit)) == expected


def test_leaf_index_loader_is_an_involution_and_ignores_internal_vertices():
    graph = build_walk_graph((0, 0, 0, 0), runway_half_length=2)
    loader = build_leaf_index_loader(graph)
    root = graph.vertex_index("tree", 0)
    circuit = qiskit.QuantumCircuit(loader.num_qubits)
    for bit in range(encode_hamiltonian(graph.hamiltonian).qubits):
        if (root >> bit) & 1:
            circuit.x(bit)
    before = Statevector.from_instruction(circuit)
    circuit.compose(loader, inplace=True)
    middle = Statevector.from_instruction(circuit)
    circuit.compose(loader, inplace=True)
    after = Statevector.from_instruction(circuit)
    assert np.allclose(before.data, middle.data)
    assert np.allclose(before.data, after.data)


@pytest.mark.parametrize("leaf_count", [2, 4])
def test_two_query_oracle_block_matches_oracle_hamiltonian(leaf_count):
    # This is the important query/unquery check: after the controlled leaf-edge evolution,
    # the address/work registers should be clean and the position register should match
    # direct evolution under the input-dependent Hamiltonian.
    rng = np.random.default_rng(leaf_count)
    for leaves in product((0, 1), repeat=leaf_count):
        graph = build_walk_graph(leaves, runway_half_length=2)
        encoded = encode_hamiltonian(graph.hamiltonian)
        size = 1 << encoded.qubits
        initial = rng.normal(size=size) + 1j * rng.normal(size=size)
        initial /= np.linalg.norm(initial)

        block = build_oracle_evolution_block(graph, leaves, time=0.37)
        block_circuit = qiskit.QuantumCircuit(block.num_qubits)
        block_circuit.initialize(initial, range(encoded.qubits))
        block_circuit.compose(block, inplace=True)
        block_state = Statevector.from_instruction(block_circuit).data

        expected_circuit = qiskit.QuantumCircuit(encoded.qubits)
        expected_circuit.initialize(initial, range(encoded.qubits))
        expected_circuit.append(
            evolution_gate(graph.oracle_hamiltonian, time=0.37),
            range(encoded.qubits),
        )
        expected = Statevector.from_instruction(expected_circuit).data

        clean_workspace = block_state[:size]
        assert np.isclose(abs(np.vdot(expected, clean_workspace)), 1.0, atol=1e-8)
        assert np.isclose(np.vdot(clean_workspace, clean_workspace).real, 1.0, atol=1e-9)
        assert np.isclose(np.vdot(block_state[size:], block_state[size:]).real, 0.0, atol=1e-9)


def test_query_walk_matches_symmetric_split_for_all_two_leaf_inputs():
    profile = profile_for(2)
    for leaves in product((0, 1), repeat=2):
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
        query_position = query_state[: 1 << position_bits]
        split_state = Statevector.from_instruction(split_circuit).data
        assert np.isclose(abs(np.vdot(split_state, query_position)), 1.0, atol=1e-8)
        assert np.isclose(np.vdot(query_position, query_position).real, 1.0, atol=1e-9)


def test_query_walk_counts_calls_and_cleans_workspace():
    result = run_query_walk(
        (1, 0),
        runway_half_length=3,
        packet_length=3,
        time=0.5,
        steps=3,
    )
    assert result.query_count == 6
    assert result.workspace_leakage < 1e-9
    assert result.padding_leakage < 1e-9
    assert np.isclose(result.norm, 1.0, atol=1e-9)


@pytest.mark.parametrize("leaf_count", [2, 4])
def test_automatic_query_evaluator_classifies_all_fast_inputs(leaf_count):
    for leaves in product((0, 1), repeat=leaf_count):
        result = evaluate_nand_tree(leaves)
        assert result.correct
        assert result.query_count == 2 * profile_for(leaf_count).query_steps


def test_count_summary_excludes_dirty_workspace_from_decision():
    graph = build_walk_graph((1, 0), runway_half_length=2)
    position_bits = encode_hamiltonian(graph.hamiltonian).qubits
    total_bits = position_bits + 2
    transmitted = graph.runway_index(1)
    reflected = graph.runway_index(-1)
    tree_vertex = graph.vertex_index("tree", 0)
    dirty = (1 << position_bits) | transmitted
    counts = {
        format(transmitted, f"0{total_bits}b"): 60,
        format(reflected, f"0{total_bits}b"): 20,
        format(tree_vertex, f"0{total_bits}b"): 10,
        format(dirty, f"0{total_bits}b"): 10,
    }
    result = summarize_query_counts(graph, counts, steps=2, threshold=0.5)
    assert result.transmitted == 60
    assert result.reflected == 20
    assert result.tree == 10
    assert result.workspace == 10
    assert result.valid_shots == 90
    assert np.isclose(result.transmission_probability, 2 / 3)
    assert result.predicted_value == 1
    assert result.query_count == 4
    assert result.total_query_count == 400


def test_confidence_bound_selects_shot_count():
    result = evaluate_nand_tree((1, 0), confidence=0.99, seed=7)
    assert result.sampling_plan is not None
    assert result.shot_result is not None
    assert result.shot_result.shots == result.sampling_plan.shots == 60
    assert result.shot_result.total_query_count == 240


def test_adaptive_sampling_reaches_stable_decision():
    for leaves in ((1, 0), (1, 1)):
        result = evaluate_nand_tree(
            leaves,
            adaptive=True,
            min_shots=256,
            max_shots=2048,
            batch_shots=128,
            seed=23,
        )
        assert result.correct
        assert result.shot_result is not None
        assert result.shot_result.stable_decision
        assert 256 <= result.shot_result.shots <= 2048


def test_qiskit_profile_verifier_passes_two_leaf_inputs():
    result = verify_qiskit_profile(2)
    assert result.passed
    assert result.correct == 4
    assert not result.failed_inputs


def test_matrix_free_profile_verifier_passes_all_eight_leaf_inputs():
    result = verify_qiskit_profile(8)
    assert result.passed
    assert result.correct == 256
    assert result.simulation_backend == "edge"


def test_example_usage_runs(capsys):
    from example_usage import main as run_example

    assert run_example() == 0
    output = capsys.readouterr().out
    assert "expected root:" in output
    assert "edge simulation:" in output
    assert "sampled:" in output


def test_main_runs_qiskit_demo_without_arguments(capsys):
    from main import main

    assert main([]) == 0
    output = capsys.readouterr().out
    assert "Qiskit NAND-tree example" in output
    assert "transmission probability:" in output
