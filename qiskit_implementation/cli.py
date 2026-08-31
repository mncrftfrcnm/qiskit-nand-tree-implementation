"""Installed command-line entry point."""

from importlib.metadata import version
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Run the NAND-tree CLI, with package-level version reporting."""
    import sys

    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["--version"]:
        print(f"nandtree {version('qiskit-nand-tree-implementation')}")
        return 0

    from main import main as legacy_main

    return legacy_main(arguments)
