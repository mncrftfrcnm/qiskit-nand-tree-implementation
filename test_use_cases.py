import json

import pytest

from example_usage import main as run_example
from main import main
from non_qiskit.exact_walk import initial_runway_packet
from non_qiskit.graph import build_walk_graph
from non_qiskit.profiles import profile_for
from qiskit_implementation import QuantumNandEvaluator, evaluate_nand_tree
from qiskit_implementation.query_walk import build_query_walk_circuit


@pytest.mark.parametrize("leaves", [(1, 0), (1, 0, 1, 1)])
def test_query_and_dense_modes_agree_on_supported_examples(leaves):
    profile = profile_for(len(leaves))
    query = evaluate_nand_tree(leaves)
    dense = evaluate_nand_tree(leaves, mode="dense")

    assert query.correct
    assert dense.correct
    assert query.predicted_value == dense.predicted_value == query.expected_value
    assert query.query_count == 2 * profile.query_steps
    assert dense.query_count == 0


def test_query_and_dense_results_account_for_all_probability():
    query = evaluate_nand_tree((1, 0))
    dense = evaluate_nand_tree((1, 0), mode="dense")

    query_walk = query.walk_result
    dense_walk = dense.walk_result
    assert query_walk is not None
    assert dense_walk is not None

    query_total = (
        query_walk.transmission_probability
        + query_walk.reflection_probability
        + query_walk.tree_probability
        + query_walk.padding_leakage
        + query_walk.workspace_leakage
    )
    dense_total = (
        dense_walk.transmission_probability
        + dense_walk.reflection_probability
        + dense_walk.tree_probability
        + dense_walk.leakage_probability
    )

    assert query_total == pytest.approx(query_walk.norm, abs=1e-9)
    assert dense_total == pytest.approx(dense_walk.norm, abs=1e-9)


def test_sampled_public_api_is_reproducible_with_a_seed():
    first = evaluate_nand_tree((1, 0), shots=128, seed=17)
    second = evaluate_nand_tree((1, 0), shots=128, seed=17)

    assert first.shot_result is not None
    assert second.shot_result is not None
    assert first.shot_result == second.shot_result
    assert first.shot_result.total_query_count == first.query_count * first.shot_result.shots


def test_evaluator_accepts_a_generator_input():
    evaluator = QuantumNandEvaluator(bit for bit in (1, 0))

    assert evaluator.leaves == (1, 0)
    assert evaluator.classical_value == 1
    assert evaluator.evaluate().correct


def test_cli_graph_command_is_useful_for_inspecting_the_walk(capsys):
    assert main(["graph", "--leaves", "1011", "--runway", "3"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result == {
        "edges": 16,
        "leaves": 4,
        "oracle_edges": 3,
        "root_value": 1,
        "vertices": 18,
    }


def test_cli_non_qiskit_walk_reports_a_probability_partition(capsys):
    assert (
        main(
            [
                "non-qiskit-walk",
                "--leaves",
                "10",
                "--runway",
                "3",
                "--packet",
                "3",
                "--time",
                "0.5",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)

    total = (
        result["transmission_probability"]
        + result["reflection_probability"]
        + result["tree_probability"]
    )
    assert result["norm"] == pytest.approx(1.0, abs=1e-9)
    assert total == pytest.approx(1.0, abs=1e-9)


def test_cli_evaluate_reports_the_calibrated_query_count(capsys):
    assert main(["evaluate", "--leaves", "10", "--mode", "query"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["correct"] is True
    assert result["expected_value"] == result["predicted_value"] == 1
    assert result["query_count"] == 4


def test_example_script_compares_query_dense_and_sampled_modes(capsys):
    assert run_example() == 0
    output = capsys.readouterr().out

    assert "query edge simulation:" in output
    assert "dense reference:" in output
    assert "sampled:" in output


def test_query_builder_rejects_zero_steps():
    with pytest.raises(ValueError, match="steps must be at least one"):
        build_query_walk_circuit((1, 0), steps=0)


def test_profile_lookup_rejects_an_unsupported_tree_size():
    with pytest.raises(ValueError, match="no built-in profile"):
        profile_for(16)


def test_packet_builder_rejects_lengths_that_do_not_fit_the_runway():
    graph = build_walk_graph((1, 0), runway_half_length=2)

    with pytest.raises(ValueError, match="packet_length must be positive"):
        initial_runway_packet(graph, 0)
    with pytest.raises(ValueError, match="does not fit"):
        initial_runway_packet(graph, 4)
