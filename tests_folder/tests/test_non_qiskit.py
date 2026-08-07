from itertools import product

import numpy as np
import pytest

from non_qiskit.analysis import scaling_report
from non_qiskit.classical import evaluate_bottom_up, evaluate_short_circuit
from non_qiskit.convergence import product_formula_convergence
from non_qiskit.exact_walk import evolve_state, initial_runway_packet, partition_probabilities
from non_qiskit.graph import build_walk_graph
from non_qiskit.profiles import BUILTIN_PROFILES, sampling_plan, verify_profile
from non_qiskit.scattering import analyze_scattering
from non_qiskit.tree import NandTree


@pytest.mark.parametrize("leaf_count", [1, 2, 4, 8])
def test_classical_evaluators_match_tree(leaf_count):
    for leaves in product((0, 1), repeat=leaf_count):
        expected = NandTree(leaves).root_value
        assert evaluate_bottom_up(leaves).value == expected
        for right_first in (False, True):
            result = evaluate_short_circuit(leaves, visit_right_first=right_first)
            assert result.value == expected
            assert 1 <= result.leaf_queries <= leaf_count


def test_tree_rejects_invalid_leaves():
    with pytest.raises(ValueError):
        NandTree(())
    with pytest.raises(ValueError):
        NandTree((0, 1, 0))
    with pytest.raises(ValueError):
        NandTree((0, 2))


@pytest.mark.parametrize("leaf_count", [2, 4, 8])
def test_scattering_separates_inputs_near_zero_energy(leaf_count):
    for leaves in product((0, 1), repeat=leaf_count):
        result = analyze_scattering(leaves, energy=1e-6)
        if NandTree(leaves).root_value:
            assert result.transmission_probability > 0.999
        else:
            assert result.transmission_probability < 0.001


def test_graph_has_expected_edges_and_hamiltonian_split():
    leaves = (1, 0, 1, 1)
    runway = 5
    graph = build_walk_graph(leaves, runway_half_length=runway)
    tree_edges = graph.tree.node_count - 1
    runway_and_root_edges = 2 * runway + 1
    expected_driver_edges = tree_edges + runway_and_root_edges

    assert np.allclose(graph.driver_hamiltonian + graph.oracle_hamiltonian, graph.hamiltonian)
    assert np.allclose(graph.hamiltonian, graph.hamiltonian.conj().T)
    assert np.count_nonzero(np.triu(graph.driver_adjacency, 1)) == expected_driver_edges
    assert np.count_nonzero(np.triu(graph.oracle_adjacency, 1)) == sum(leaves)


def test_packet_is_normalized_and_stays_on_left_runway():
    graph = build_walk_graph((1, 0), runway_half_length=4)
    packet = initial_runway_packet(graph, 3)
    assert np.isclose(np.vdot(packet, packet).real, 1.0)
    occupied = set(np.flatnonzero(np.abs(packet) > 0))
    expected = {graph.runway_index(position) for position in (-2, -1, 0)}
    assert occupied == expected


def test_exact_evolution_preserves_norm_and_probability_partition():
    graph = build_walk_graph((1, 0), runway_half_length=4)
    initial = initial_runway_packet(graph, 3)
    final = evolve_state(graph.hamiltonian, initial, 2.0)
    transmission, reflection, tree_probability = partition_probabilities(graph, final)
    assert np.isclose(np.vdot(final, final).real, 1.0, atol=1e-10)
    assert np.isclose(transmission + reflection + tree_probability, 1.0, atol=1e-10)


def test_product_formula_converges_to_exact_walk():
    points = product_formula_convergence(
        (1, 0),
        runway_half_length=3,
        packet_length=3,
        time=0.7,
        steps=(1, 2, 4, 8),
    )
    assert points[-1].fidelity > points[0].fidelity
    assert points[-1].state_error < points[0].state_error / 20
    assert points[-1].transmission_error < points[0].transmission_error
    assert [point.oracle_calls for point in points] == [2, 4, 8, 16]


def test_builtin_profiles_classify_every_supported_input():
    for profile in BUILTIN_PROFILES.values():
        assert verify_profile(profile, mode="exact").passed
        assert verify_profile(profile, mode="query").passed


def test_sampling_plans_use_positive_verified_gaps():
    expected_upper_bounds = {2: 60, 4: 143, 8: 107}
    for leaves, profile in BUILTIN_PROFILES.items():
        plan = sampling_plan(profile, confidence=0.99)
        assert plan.threshold_gap > 0
        assert plan.shots == expected_upper_bounds[leaves]


def test_sampling_plan_rejects_invalid_confidence():
    profile = BUILTIN_PROFILES[2]
    for confidence in (0.0, 1.0, -0.1, 1.1):
        with pytest.raises(ValueError):
            sampling_plan(profile, confidence=confidence)


def test_scaling_report_is_consistent_with_profiles():
    rows = scaling_report()
    assert [row.leaves for row in rows] == [2, 4, 8]
    for row in rows:
        profile = BUILTIN_PROFILES[row.leaves]
        assert row.oracle_calls == 2 * profile.query_steps
        assert row.calls_per_square_root > 0
        assert row.exact_margin > 0
        assert row.query_margin > 0


def test_packet_matches_runway_formula():
    graph = build_walk_graph((1, 0), runway_half_length=4)
    packet = initial_runway_packet(graph, 4)
    expected = {
        position: np.exp(1j * position * np.pi / 2) / 2
        for position in (-3, -2, -1, 0)
    }
    for position, amplitude in expected.items():
        assert np.allclose(packet[graph.runway_index(position)], amplitude)


def test_oracle_hamiltonian_matches_input_edges():
    leaves = (1, 0, 1, 0)
    graph = build_walk_graph(leaves, runway_half_length=3)
    for leaf, bit in enumerate(leaves):
        tree_vertex = graph.vertex_index("tree", graph.tree.leaf_node(leaf))
        oracle_vertex = graph.vertex_index("oracle", leaf)
        expected = -1.0 if bit else 0.0
        assert graph.oracle_hamiltonian[tree_vertex, oracle_vertex] == expected
        assert graph.oracle_hamiltonian[oracle_vertex, tree_vertex] == expected


def test_driver_hamiltonian_is_input_independent():
    zero_graph = build_walk_graph((0, 0, 0, 0), runway_half_length=3)
    one_graph = build_walk_graph((1, 1, 1, 1), runway_half_length=3)
    assert np.array_equal(zero_graph.driver_hamiltonian, one_graph.driver_hamiltonian)
