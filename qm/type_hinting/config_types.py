from typing import Dict, List, Tuple, Union
from typing_extensions import Literal, TypedDict

from qm.type_hinting.general import Number

PortReferenceType = Tuple[str, int]


# TODO: This is a placeholder while we still use dicts, once we move to pydantics we can simply change the
#  inheritance of the classes handled here and add a more robust validation to the types


class AnalogOutputFilterConfigType(TypedDict, total=False):
    feedforward: List[float]
    feedback: List[float]


class AnalogOutputPortConfigType(TypedDict, total=False):
    offset: Number
    filter: AnalogOutputFilterConfigType
    delay: int
    crosstalk: Dict[int, Number]
    shareable: bool


class AnalogInputPortConfigType(TypedDict, total=False):
    offset: Number
    gain_db: int
    shareable: bool


class DigitalOutputPortConfigType(TypedDict, total=False):
    sharable: bool
    inverted: bool


class DigitalInputPortConfigType(TypedDict, total=False):
    deadtime: int
    polarity: Literal["RISING", "FALLING"]
    threshold: Number


class ControllerConfigType(TypedDict, total=False):
    type: str
    analog_outputs: Dict[int, AnalogOutputPortConfigType]
    analog_inputs: Dict[int, AnalogInputPortConfigType]
    digital_outputs: Dict[int, DigitalOutputPortConfigType]
    digital_inputs: Dict[int, DigitalInputPortConfigType]


class OctaveRFOutputConfigType(TypedDict, total=False):
    LO_frequency: float
    LO_source: Literal["internal", "external"]
    output_mode: Literal["always_on", "always_off", "triggered", "triggered_reversed"]
    gain: Union[int, float]
    input_attenuators: Literal["ON", "OFF"]
    I_connection: PortReferenceType
    Q_connection: PortReferenceType


class OctaveRFInputConfigType(TypedDict, total=False):
    RF_source: Literal["RF_in", "loopback_1", "loopback_2", "loopback_3", "loopback_4", "loopback_5"]
    LO_frequency: float
    LO_source: Literal["internal", "external", "analyzer"]
    IF_mode_I: Literal["direct", "mixer", "envelope", "off"]
    IF_mode_Q: Literal["direct", "mixer", "envelope", "off"]


class OctaveSingleIfOutputConfigType(TypedDict, total=False):
    port: PortReferenceType
    name: str


class OctaveIfOutputsConfigType(TypedDict, total=False):
    IF_out1: OctaveSingleIfOutputConfigType
    IF_out2: OctaveSingleIfOutputConfigType


class OctaveConfigType(TypedDict, total=False):
    RF_outputs: Dict[int, OctaveRFOutputConfigType]
    RF_inputs: Dict[int, OctaveRFInputConfigType]
    IF_outputs: OctaveIfOutputsConfigType
    loopbacks: List[
        Tuple[
            Tuple[str, Literal["Synth1", "Synth2", "Synth3", "Synth4", "Synth5"]],
            Literal["Dmd1LO", "Dmd2LO", "LO1", "LO2", "LO3", "LO4", "LO5"],
        ],
    ]
    connectivity: str


class DigitalInputConfigType(TypedDict, total=False):
    delay: int
    buffer: int
    port: PortReferenceType


class IntegrationWeightConfigType(TypedDict, total=False):
    cosine: Union[List[Tuple[float, int]], List[float]]
    sine: Union[List[Tuple[float, int]], List[float]]


class ConstantWaveFormConfigType(TypedDict, total=False):
    type: Literal["constant"]
    sample: float


class ArbitraryWaveFormConfigType(TypedDict, total=False):
    type: Literal["arbitrary"]
    samples: List[float]
    max_allowed_error: float
    sampling_rate: Number
    is_overridable: bool


class DigitalWaveformConfigType(TypedDict, total=False):
    samples: List[Tuple[int, int]]


class MixerConfigType(TypedDict, total=False):
    intermediate_frequency: float
    lo_frequency: float
    correction: Tuple[Number, Number, Number, Number]


class PulseConfigType(TypedDict, total=False):
    operation: str
    length: int
    waveforms: Dict[str, str]
    digital_marker: str
    integration_weights: Dict[str, str]


class SingleInputConfigType(TypedDict, total=False):
    port: PortReferenceType


class HoldOffsetConfigType(TypedDict, total=False):
    duration: int


class StickyConfigType(TypedDict, total=False):
    analog: bool
    digital: bool
    duration: int


class MixInputConfigType(TypedDict, total=False):
    I: PortReferenceType
    Q: PortReferenceType
    mixer: str
    lo_frequency: float


class InputCollectionConfigType(TypedDict, total=False):
    inputs: Dict[str, PortReferenceType]


class OscillatorConfigType(TypedDict, total=False):
    intermediate_frequency: float
    mixer: str
    lo_frequency: float


class OutputPulseParameterConfigType(TypedDict):
    signalThreshold: int
    signalPolarity: Literal["ABOVE", "ASCENDING", "BELOW", "DESCENDING"]
    derivativeThreshold: int
    derivativePolarity: Literal["ABOVE", "ASCENDING", "BELOW", "DESCENDING"]


class ElementConfigType(TypedDict, total=False):
    intermediate_frequency: float
    oscillator: str
    measurement_qe: str
    operations: Dict[str, str]
    singleInput: SingleInputConfigType
    mixInputs: MixInputConfigType
    singleInputCollection: InputCollectionConfigType
    multipleInputs: InputCollectionConfigType
    time_of_flight: int
    smearing: int
    outputs: Dict[str, PortReferenceType]
    digitalInputs: Dict[str, DigitalInputConfigType]
    digitalOutputs: Dict[str, PortReferenceType]
    outputPulseParameters: OutputPulseParameterConfigType
    hold_offset: HoldOffsetConfigType
    sticky: StickyConfigType
    thread: str
    RF_inputs: Dict[str, PortReferenceType]
    RF_outputs: Dict[str, PortReferenceType]


class DictQuaConfig(TypedDict, total=False):
    version: int
    oscillators: Dict[str, OscillatorConfigType]
    elements: Dict[str, ElementConfigType]
    controllers: Dict[str, ControllerConfigType]
    octaves: Dict[str, OctaveConfigType]
    integration_weights: Dict[str, IntegrationWeightConfigType]
    waveforms: Dict[str, Union[ArbitraryWaveFormConfigType, ConstantWaveFormConfigType]]
    digital_waveforms: Dict[str, DigitalWaveformConfigType]
    pulses: Dict[str, PulseConfigType]
    mixers: Dict[str, List[MixerConfigType]]
