import abc
from dataclasses import dataclass
from typing import List, Union, Optional

from qm.grpc.frontend import SimulationRequest, ExecutionRequestSimulateSimulationInterfaceNone


class SimulatorInterface(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def update_simulate_request(self, request: SimulationRequest) -> SimulationRequest:
        pass


class SimulationConfig:
    """Creates a configuration object to pass to
    [qm.quantum_machines_manager.QuantumMachinesManager.simulate][]

    Args:
        duration (int): The duration to run the simulation for, in clock
            cycles
        include_analog_waveforms (bool): True to collect simulated
            analog waveform names
        include_digital_waveforms (bool): True to collect simulated
            digital waveform names
        simulation_interface (SimulatorInterface):
            Interface for to simulator. Currently supported interfaces
            - ``None`` - Zero inputs
            - [qm.simulate.loopback.LoopbackInterface][] - Loopback output to input
            - [qm.simulate.raw.RawInterface][] - Specify samples for inputs
        controller_connections (List[ControllerConnection]): A list of
            connections between the controllers in the config
        extraProcessingTimeoutInMs (int): timeout in ms to wait for
            stream processing to finish. Default is -1, which is
            disables the timeout

    """

    duration = 0
    simulate_analog_outputs = False

    def __init__(
        self,
        duration: int = 0,
        include_analog_waveforms: bool = False,
        include_digital_waveforms: bool = False,
        simulation_interface: Optional[SimulatorInterface] = None,
        controller_connections: Optional[List["ControllerConnection"]] = None,
        extraProcessingTimeoutInMs: int = -1,
    ):
        if controller_connections is None:
            controller_connections = []
        super(SimulationConfig, self).__init__()
        self.duration = duration
        self.include_analog_waveforms = include_analog_waveforms is True
        self.include_digital_waveforms = include_digital_waveforms is True
        self.simulation_interface = simulation_interface
        self.controller_connections = controller_connections
        self.extraProcessingTimeoutInMs = extraProcessingTimeoutInMs

    def update_simulate_request(self, request: SimulationRequest) -> SimulationRequest:
        if self.simulation_interface is None:
            request.simulate.simulation_interface.none = ExecutionRequestSimulateSimulationInterfaceNone()
        else:
            request = self.simulation_interface.update_simulate_request(request)
        return request


@dataclass
class InterOpxAddress:
    """Args:
    controller (str): The name of the controller
    is_left_connection (bool)
    """

    controller: str
    is_left_connection: bool


@dataclass
class InterOpxChannel:
    """Args:
    controller (str): The name of the controller
    channel_number (int)
    """

    controller: str
    channel_number: int


InterOpxPairing = Union[InterOpxAddress, InterOpxChannel]


@dataclass
class ControllerConnection:
    source: InterOpxPairing
    target: InterOpxPairing
