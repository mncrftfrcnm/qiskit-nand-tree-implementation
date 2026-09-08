import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="run exhaustive Qiskit tests",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-slow"):
        return
    skip = pytest.mark.skip(reason="use --run-slow to run this test")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)
