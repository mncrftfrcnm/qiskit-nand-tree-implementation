import pytest

from non_qiskit import (
    Input,
    build_formula_walk_graph,
    evaluate_formula,
    format_formula,
    formula_depth,
    formula_size,
    input_occurrences,
    nand,
    run_formula_walk,
)


def test_unbalanced_formula_evaluates_correctly():
    formula = nand(Input(0), nand(Input(1), nand(Input(2), Input(3))))

    assert evaluate_formula(formula, (1, 1, 1, 1)) == 1
    assert evaluate_formula(formula, (1, 0, 1, 1)) == 0
    assert formula_depth(formula) == 3
    assert formula_size(formula) == 7
    assert input_occurrences(formula) == (0, 1, 2, 3)


def test_formula_supports_repeated_inputs():
    formula = nand(Input(0), nand(Input(0), Input(1)))

    assert input_occurrences(formula) == (0, 0, 1)
    assert evaluate_formula(formula, {0: 1, 1: 1}) == 1
    assert format_formula(formula) == "NAND(x0, NAND(x0, x1))"


def test_formula_requires_binary_input_values():
    with pytest.raises(ValueError, match="only 0 and 1"):
        evaluate_formula(nand(Input(0), Input(1)), (1, 2))


def test_unbalanced_formula_walk_builds_expected_topology():
    formula = nand(Input(0), nand(Input(1), Input(2)))
    graph = build_formula_walk_graph(
        formula,
        (1, 0, 1),
        runway_half_length=3,
    )

    # Five formula nodes, three oracle vertices, and seven runway vertices.
    assert graph.size == 15
    assert graph.root_value == evaluate_formula(formula, (1, 0, 1))
    assert sum(1 for vertex in graph.vertices if vertex.kind == "oracle") == 3


def test_formula_walk_preserves_state_norm():
    formula = nand(Input(0), nand(Input(1), Input(2)))
    result = run_formula_walk(
        formula,
        (1, 0, 1),
        runway_half_length=4,
        packet_length=3,
        time=1.5,
    )

    assert result.norm == pytest.approx(1.0, abs=1e-10)
    assert result.root_value == evaluate_formula(formula, (1, 0, 1))
