from typing_extensions import Literal, TypedDict
from typing import Dict, List, Union, Mapping, Optional, Sequence, cast

import numpy.typing


class SimulatorControllerSamples:
    def __init__(self, analog: Mapping[str, Sequence[float]], digital: Mapping[str, Sequence[bool]]):
        self.analog = self._add_keys_for_first_con(analog)
        self.digital = self._add_keys_for_first_con(digital)
        self._analog_conns = analog
        self._digital_conns = digital

    @staticmethod
    def _add_keys_for_first_con(
        data: Mapping[str, Union[Sequence[float], Sequence[bool]]]
    ) -> Mapping[str, Union[Sequence[float], Sequence[bool]]]:
        # Note(jonatann): I have no idea what this function does and why it exists...
        first_con_data = {
            controller_name[2:]: samples
            for controller_name, samples in data.items()
            if controller_name.startswith("1-")
        }
        return {**data, **first_con_data}

    def plot(
        self,
        analog_ports: Optional[Union[str, List[str]]] = None,
        digital_ports: Optional[Union[str, List[str]]] = None,
    ) -> None:
        """Plots the simulated output of the OPX in the given ports.
        If no ports are given, all active ports are plotted.

        Args:
            analog_ports: Union[None, str, list[str]]
            digital_ports: Union[None, str, list[str]]
        """
        import matplotlib.pyplot as plt

        for port, samples in self._analog_conns.items():
            if analog_ports is None or port in analog_ports:
                plt.plot(samples, label=f"Analog {port}")
        for port, samples in self._digital_conns.items():
            if digital_ports is None or port in digital_ports:
                plt.plot(samples, label=f"Digital {port}")
        plt.xlabel("Time [ns]")
        plt.ylabel("Output")
        plt.legend()


class SimulatorSamplesDictType(TypedDict):
    analog: Dict[str, Sequence[float]]
    digital: Dict[str, Sequence[bool]]


class SimulatorSamples:
    def __init__(self, controllers: Dict[str, SimulatorControllerSamples]):
        for k, v in controllers.items():
            self.__setattr__(k, v)

    @staticmethod
    def from_np_array(arr: numpy.typing.NDArray[numpy.generic]) -> "SimulatorSamples":
        controllers: Dict[str, SimulatorSamplesDictType] = {}
        assert arr.dtype.names is not None
        for col in arr.dtype.names:
            controller_name, output, number = col.split(":")
            output = cast(Union[Literal["analog"], Literal["digital"]], output)
            controller = controllers.setdefault(controller_name, {"analog": {}, "digital": {}})
            controller[output][number] = arr[col]
        res = {}
        for controller_name, samples in controllers.items():
            res[controller_name] = SimulatorControllerSamples(samples["analog"], samples["digital"])
        return SimulatorSamples(res)
