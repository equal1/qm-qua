import logging
from typing import List, Tuple

from qm.simulate.interface import SimulatorInterface
from qm.grpc.frontend import (
    SimulationRequest,
    ExecutionRequestSimulateSimulationInterfaceLoopback,
    ExecutionRequestSimulateSimulationInterfaceNone,
    ExecutionRequestSimulateSimulationInterfaceLoopbackConnections,
)


logger = logging.getLogger(__name__)


class LoopbackInterface(SimulatorInterface):
    """Creates a loopback interface for use in
    [qm.simulate.interface.SimulationConfig][].
    A loopback connects the output of the OPX into it's input. This can be defined
    directly using the ports or through the elements.

    Args:
        connections (list):
            List of tuples with loopback connections. Each tuple should represent physical connection between ports:

                    ``(from_controller: str, from_port: int, to_controller: str, to_port: int)``

        latency (int): The latency between the OPX outputs and its
            input.
        noisePower (float): How much noise to add to the input.

    Example:
        ```python
        job = qmm.simulate(config, prog, SimulationConfig(
                          duration=20000,
                          # loopback from output 1 to input 2 of controller 1:
                          simulation_interface=LoopbackInterface([("con1", 1, "con1", 2)])
        ```
    """

    def __init__(self, connections: List[Tuple[str, int, str, int]], latency: int = 24, noisePower: float = 0.0):
        self._validate_inputs(connections, latency, noisePower)

        self.latency = latency
        self.noisePower = float(noisePower)
        self.connections = connections.copy()

    @staticmethod
    def _validate_inputs(connections: List[Tuple[str, int, str, int]], latency: int, noise_power: float) -> None:
        if (not isinstance(latency, int)) or latency < 0:
            raise Exception("latency must be a positive integer")
        if (not isinstance(noise_power, (int, float))) or noise_power < 0:
            raise Exception("noisePower must be a positive number")
        if not isinstance(connections, list):
            raise Exception("connections argument must be of type list")
        for connection in connections:
            LoopbackInterface._validate_connection(connection)

    @staticmethod
    def _validate_connection(connection: Tuple[str, int, str, int]) -> None:
        if not connection:
            logger.warning("No loopback was defined, treating as no loopback.")
        if not isinstance(connection, tuple):
            raise Exception("each connection must be a tuple")
        if len(connection) != 4:
            raise Exception("connection should be tuple of length 4.")
        if not all(
            [
                isinstance(connection[0], str),
                isinstance(connection[1], int),
                isinstance(connection[2], str),
                isinstance(connection[3], int),
            ]
        ):
            raise Exception("connection should be (from_controller, from_port, to_controller, to_port)")

    def update_simulate_request(self, request: SimulationRequest) -> SimulationRequest:
        if not self.connections:
            request.simulate.simulation_interface.none = ExecutionRequestSimulateSimulationInterfaceNone()
            return request

        request.simulate.simulation_interface.loopback = ExecutionRequestSimulateSimulationInterfaceLoopback(
            latency=self.latency, noise_power=self.noisePower
        )
        for connection in self.connections:
            con = ExecutionRequestSimulateSimulationInterfaceLoopbackConnections(
                from_controller=connection[0],
                from_port=connection[1],
                to_controller=connection[2],
                to_port=connection[3],
            )
            request.simulate.simulation_interface.loopback.connections.append(con)
        return request
