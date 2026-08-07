from ._imports import qiskit_api


def append_x_on_state(circuit, controls: list[int], target: int, state: int) -> None:
    """Flip target when controls encode ``state`` (little-endian)."""

    zeros = [qubit for bit, qubit in enumerate(controls) if not (state >> bit) & 1]
    for qubit in zeros:
        circuit.x(qubit)

    if not controls:
        circuit.x(target)
    elif len(controls) == 1:
        circuit.cx(controls[0], target)
    elif len(controls) == 2:
        circuit.ccx(controls[0], controls[1], target)
    else:
        circuit.append(qiskit_api().MCXGate(len(controls)), [*controls, target])

    for qubit in reversed(zeros):
        circuit.x(qubit)


def append_phase_on_state(circuit, qubits: list[int], state: int) -> None:
    """Apply a -1 phase to one computational-basis state."""

    zeros = [qubit for bit, qubit in enumerate(qubits) if not (state >> bit) & 1]
    for qubit in zeros:
        circuit.x(qubit)

    if len(qubits) == 1:
        circuit.z(qubits[0])
    else:
        gate = qiskit_api().ZGate().control(len(qubits) - 1)
        circuit.append(gate, qubits)

    for qubit in reversed(zeros):
        circuit.x(qubit)
