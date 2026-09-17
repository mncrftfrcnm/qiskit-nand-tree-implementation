from benchmarks.scaling import benchmark_size
from qiskit_implementation import analyze_query_resources


def test_scaling_benchmark_records_core_resources():
    row = benchmark_size(2, gamma=1.0, runway_factor=0.5, driver_reps=1)

    assert row.leaf_count == 2
    assert row.graph_vertices > 0
    assert row.total_query_qubits >= row.position_qubits
    assert row.oracle_calls == 2 * row.query_steps
    assert row.build_seconds >= 0.0
    assert row.simulation_seconds >= 0.0
    assert row.peak_memory_bytes > 0


def test_query_resource_report_matches_profile_query_count():
    resources = analyze_query_resources(2, optimization_level=0, driver_reps=1)

    assert resources.leaf_count == 2
    assert resources.logical_qubits > 0
    assert resources.logical_depth > 0
    assert resources.transpiled_depth > 0
    assert resources.oracle_calls == 2 * resources.query_steps
