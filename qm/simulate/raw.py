from typing import List, Tuple

from qm.simulate.interface import SimulatorInterface
from qm.grpc.frontend import (
    SimulationRequest,
    ExecutionRequestSimulateSimulationInterfaceRawInterface,
    ExecutionRequestSimulateSimulationInterfaceRawInterfaceConnections,
)


class RawInterface(SimulatorInterface):
    """Creates a raw interface for use in [qm.simulate.interface.SimulationConfig][].
    A raw interface defines samples that will be inputted into the OPX inputs.

    Args:
        connections (list):

            List of tuples with the connection. Each tuple should be:

                    ``(toController: str, toPort: int, toSamples: List[float])``
        noisePower (float): How much noise to add to the input.

    Example:
        ```python
        job = qmm.simulate(config, prog, SimulationConfig(
                          duration=20000,
                          # 500 ns of DC 0.2 V into con1 input 1
                          simulation_interface=RawInterface([("con1", 1, [0.2]*500)])
        ```
    """

    def __init__(self, connections: List[Tuple[str, int, List[float]]], noisePower: float = 0.0):
        self._validate_inputs(connections, noisePower)

        self.noisePower = float(noisePower)
        self.connections = connections.copy()

    @staticmethod
    def _validate_inputs(connections: List[Tuple[str, int, List[float]]], noise_power: float) -> None:
        if not isinstance(noise_power, (int, float)) or noise_power < 0:
            raise Exception("noisePower must be a positive number")
        if type(connections) is not list:
            raise Exception("connections argument must be of type list")
        for connection in connections:
            RawInterface._validate_connection(connection)

    @staticmethod
    def _validate_connection(connection: Tuple[str, int, List[float]]) -> None:
        if not isinstance(connection, tuple):
            raise Exception("each connection must be of type tuple")
        if len(connection) != 3:
            raise Exception("connection should be tuple of length 3")
        if not all([isinstance(connection[0], str), isinstance(connection[1], int), isinstance(connection[2], list)]):
            raise Exception("connection should be (from_controller, from_port, to_samples)")

    def update_simulate_request(self, request: SimulationRequest) -> SimulationRequest:
        request.simulate.simulation_interface.raw = ExecutionRequestSimulateSimulationInterfaceRawInterface(
            noise_power=self.noisePower
        )
        for connection in self.connections:
            request.simulate.simulation_interface.raw.connections.append(
                ExecutionRequestSimulateSimulationInterfaceRawInterfaceConnections(
                    from_controller=connection[0], from_port=connection[1], to_samples=connection[2]
                )
            )
        return request
