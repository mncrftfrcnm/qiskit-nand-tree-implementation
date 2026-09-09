import qiskit_implementation as qni
import qiskit_implementation.evolution as evolution
import qiskit_implementation.query_walk as query_walk

EXPECTED_PUBLIC_API = {
    "NandEvaluation",
    "NandExperimentConfig",
    "QiskitVerification",
    "QuantumNandEvaluator",
    "WalkParameters",
    "build_bit_oracle",
    "build_query_walk_circuit",
    "build_reversible_nand_circuit",
    "evaluate_nand_tree",
    "theoretical_parameters",
    "verify_qiskit_profile",
}


def test_top_level_api_is_intentional():
    assert set(qni.__all__) == EXPECTED_PUBLIC_API
    for name in EXPECTED_PUBLIC_API:
        assert hasattr(qni, name)

    for low_level_name in (
        "run_query_walk",
        "sample_query_walk",
        "sample_query_walk_adaptive",
        "simulate_query_walk",
        "summarize_query_counts",
    ):
        assert not hasattr(qni, low_level_name)


def test_evaluator_uses_evaluate_name_and_keeps_legacy_alias():
    evaluator = qni.QuantumNandEvaluator((1, 0))
    result = evaluator.evaluate()
    query = evaluator.evaluate(mode="query")
    legacy = evaluator.automatic()

    assert result.correct
    assert result.mode == "dense"
    assert isinstance(result.walk_result, evolution.QiskitWalkResult)
    assert isinstance(query.walk_result, query_walk.QueryWalkResult)
    assert legacy.predicted_value == result.predicted_value
    assert legacy.transmission_probability == result.transmission_probability


def test_nand_evaluation_exposes_underlying_walk_result():
    dense = qni.evaluate_nand_tree((1, 0))
    query = qni.evaluate_nand_tree((1, 0), mode="query")
    qiskit_query = qni.evaluate_nand_tree(
        (1, 0),
        mode="query",
        simulation_backend="qiskit",
    )

    assert isinstance(query.walk_result, query_walk.QueryWalkResult)
    assert isinstance(qiskit_query.walk_result, query_walk.QueryWalkResult)
    assert isinstance(dense.walk_result, evolution.QiskitWalkResult)
    assert query.walk_result.simulation_backend == "edge"
    assert qiskit_query.walk_result.simulation_backend == "qiskit"

    # Older callers can still read the query-only compatibility property.
    assert query.statevector_result is query.walk_result
    assert dense.statevector_result is None


def test_evaluator_requires_experiment_for_custom_classification_settings():
    evaluator = qni.QuantumNandEvaluator(
        (1, 0),
        runway_half_length=3,
        packet_length=3,
    )
    try:
        evaluator.evaluate()
    except ValueError as error:
        assert "experiment" in str(error)
    else:
        raise AssertionError("custom walk settings must not be silently ignored")


def test_evaluator_uses_explicit_experiment_for_classification():
    experiment = qni.NandExperimentConfig(
        walk=qni.WalkParameters(
            runway_half_length=2,
            packet_length=3,
            evolution_time=7.8,
        ),
        query_steps=2,
        threshold=0.37,
    )
    evaluator = qni.QuantumNandEvaluator((1, 0), experiment=experiment)
    result = evaluator.evaluate(mode="query")

    assert result.correct
    assert result.profile is experiment
