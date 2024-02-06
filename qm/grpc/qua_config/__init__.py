# Generated by the protocol buffer compiler.  DO NOT EDIT!
# sources: qm/pb/inc_qua_config.proto
# plugin: python-betterproto
import warnings
from dataclasses import dataclass
from typing import (
    Dict,
    List,
    Optional,
)

import betterproto
import betterproto.lib.google.protobuf as betterproto_lib_google_protobuf


class QuaConfigOutputSwitchState(betterproto.Enum):
    unset = 0
    always_on = 1
    always_off = 2
    triggered = 3
    triggered_reversed = 4


class QuaConfigDigitalInputPortDecPolarity(betterproto.Enum):
    RISING = 0
    FALLING = 1


class QuaConfigOutputPulseParametersPolarity(betterproto.Enum):
    ASCENDING = 0
    DESCENDING = 1


class QuaConfigPulseDecOperation(betterproto.Enum):
    MEASUREMENT = 0
    CONTROL = 1


class QuaConfigOctaveSynthesizerOutputName(betterproto.Enum):
    synth1 = 0
    synth2 = 1
    synth3 = 2
    synth4 = 3
    synth5 = 4


class QuaConfigOctaveLoSourceInput(betterproto.Enum):
    not_set = 0
    internal = 1
    external = 2
    analyzer = 3


class QuaConfigOctaveLoopbackInput(betterproto.Enum):
    undefined = 0
    LO1 = 1
    LO2 = 2
    LO3 = 3
    LO4 = 4
    LO5 = 5
    Dmd1LO = 6
    Dmd2LO = 7


class QuaConfigOctaveDownconverterRfSource(betterproto.Enum):
    rf_in = 0
    loopback_1 = 1
    loopback_2 = 2
    loopback_3 = 3
    loopback_4 = 4
    loopback_5 = 5


class QuaConfigOctaveOutputSwitchState(betterproto.Enum):
    unset = 0
    always_on = 1
    always_off = 2
    triggered = 3
    triggered_reversed = 4


class QuaConfigOctaveIfMode(betterproto.Enum):
    direct = 0
    mixer = 1
    envelope = 2
    off = 3


@dataclass(eq=False, repr=False)
class QuaConfig(betterproto.Message):
    v1_beta: "QuaConfigQuaConfigV1" = betterproto.message_field(
        1, group="config_version"
    )
    """beta suffix means the version is not fixed yet and can changed"""

    revision: int = betterproto.int32_field(11)


@dataclass(eq=False, repr=False)
class QuaConfigQuaConfigV1(betterproto.Message):
    controllers: Dict[str, "QuaConfigControllerDec"] = betterproto.map_field(
        2, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE
    )
    controller_types: Dict[str, "QuaConfigControllerTypeDec"] = betterproto.map_field(
        10, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE
    )
    oscillators: Dict[str, "QuaConfigOscillator"] = betterproto.map_field(
        9, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE
    )
    elements: Dict[str, "QuaConfigElementDec"] = betterproto.map_field(
        3, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE
    )
    pulses: Dict[str, "QuaConfigPulseDec"] = betterproto.map_field(
        4, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE
    )
    mixers: Dict[str, "QuaConfigMixerDec"] = betterproto.map_field(
        5, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE
    )
    waveforms: Dict[str, "QuaConfigWaveformDec"] = betterproto.map_field(
        6, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE
    )
    digital_waveforms: Dict[str, "QuaConfigDigitalWaveformDec"] = betterproto.map_field(
        7, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE
    )
    integration_weights: Dict[
        str, "QuaConfigIntegrationWeightDec"
    ] = betterproto.map_field(8, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE)
    octaves: Dict[str, "QuaConfigOctaveConfig"] = betterproto.map_field(
        11, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.is_set("controllers"):
            warnings.warn(
                "QuaConfigQuaConfigV1.controllers is deprecated", DeprecationWarning
            )


@dataclass(eq=False, repr=False)
class QuaConfigControllerDec(betterproto.Message):
    type: str = betterproto.string_field(1)
    analog_outputs: Dict[int, "QuaConfigAnalogOutputPortDec"] = betterproto.map_field(
        2, betterproto.TYPE_UINT32, betterproto.TYPE_MESSAGE
    )
    analog_inputs: Dict[int, "QuaConfigAnalogInputPortDec"] = betterproto.map_field(
        3, betterproto.TYPE_UINT32, betterproto.TYPE_MESSAGE
    )
    digital_outputs: Dict[int, "QuaConfigDigitalOutputPortDec"] = betterproto.map_field(
        4, betterproto.TYPE_UINT32, betterproto.TYPE_MESSAGE
    )
    digital_inputs: Dict[int, "QuaConfigDigitalInputPortDec"] = betterproto.map_field(
        5, betterproto.TYPE_UINT32, betterproto.TYPE_MESSAGE
    )


@dataclass(eq=False, repr=False)
class QuaConfigControllerTypeDec(betterproto.Message):
    opx: "QuaConfigOpxControllerDec" = betterproto.message_field(
        1, group="controller_type_one_of"
    )
    opx_plus: "QuaConfigOpxPlusControllerDec" = betterproto.message_field(
        2, group="controller_type_one_of"
    )


@dataclass(eq=False, repr=False)
class QuaConfigOpxControllerDec(betterproto.Message):
    controller: "QuaConfigControllerDec" = betterproto.message_field(1)
    controller_name: str = betterproto.string_field(2)


@dataclass(eq=False, repr=False)
class QuaConfigOpxPlusControllerDec(betterproto.Message):
    controller: "QuaConfigControllerDec" = betterproto.message_field(1)
    controller_name: str = betterproto.string_field(2)


@dataclass(eq=False, repr=False)
class QuaConfigAnalogOutputPortDec(betterproto.Message):
    offset: float = betterproto.double_field(1)
    filter: "QuaConfigAnalogOutputPortFilter" = betterproto.message_field(2)
    delay: int = betterproto.uint32_field(3)
    channel_weights: Dict[int, float] = betterproto.map_field(
        4, betterproto.TYPE_UINT32, betterproto.TYPE_DOUBLE
    )
    shareable: bool = betterproto.bool_field(5)
    crosstalk: Dict[int, float] = betterproto.map_field(
        6, betterproto.TYPE_UINT32, betterproto.TYPE_DOUBLE
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.is_set("channel_weights"):
            warnings.warn(
                "QuaConfigAnalogOutputPortDec.channel_weights is deprecated",
                DeprecationWarning,
            )


@dataclass(eq=False, repr=False)
class QuaConfigAnalogOutputPortFilter(betterproto.Message):
    feedforward: List[float] = betterproto.double_field(1)
    feedback: List[float] = betterproto.double_field(2)


@dataclass(eq=False, repr=False)
class QuaConfigAnalogInputPortDec(betterproto.Message):
    offset: float = betterproto.double_field(1)
    gain_db: Optional[int] = betterproto.message_field(2, wraps=betterproto.TYPE_INT32)
    shareable: bool = betterproto.bool_field(3)


@dataclass(eq=False, repr=False)
class QuaConfigDigitalOutputPortDec(betterproto.Message):
    shareable: bool = betterproto.bool_field(1)
    inverted: bool = betterproto.bool_field(2)


@dataclass(eq=False, repr=False)
class QuaConfigDigitalInputPortDec(betterproto.Message):
    deadtime: int = betterproto.uint32_field(1)
    polarity: "QuaConfigDigitalInputPortDecPolarity" = betterproto.enum_field(2)
    threshold: float = betterproto.double_field(3)
    shareable: bool = betterproto.bool_field(4)


@dataclass(eq=False, repr=False)
class QuaConfigMixerRef(betterproto.Message):
    mixer: str = betterproto.string_field(1)
    lo_frequency: int = betterproto.uint64_field(2)
    lo_frequency_double: float = betterproto.double_field(3)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.is_set("lo_frequency"):
            warnings.warn(
                "QuaConfigMixerRef.lo_frequency is deprecated", DeprecationWarning
            )


@dataclass(eq=False, repr=False)
class QuaConfigOscillator(betterproto.Message):
    intermediate_frequency: Optional[int] = betterproto.message_field(
        1, wraps=betterproto.TYPE_INT64
    )
    mixer: "QuaConfigMixerRef" = betterproto.message_field(2)
    intermediate_frequency_double: float = betterproto.double_field(3)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.is_set("intermediate_frequency"):
            warnings.warn(
                "QuaConfigOscillator.intermediate_frequency is deprecated",
                DeprecationWarning,
            )


@dataclass(eq=False, repr=False)
class QuaConfigSingleInput(betterproto.Message):
    port: "QuaConfigDacPortReference" = betterproto.message_field(1)


@dataclass(eq=False, repr=False)
class QuaConfigMixInputs(betterproto.Message):
    i: "QuaConfigDacPortReference" = betterproto.message_field(1)
    q: "QuaConfigDacPortReference" = betterproto.message_field(2)
    mixer: str = betterproto.string_field(3)
    lo_frequency: int = betterproto.uint64_field(4)
    lo_frequency_double: float = betterproto.double_field(5)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.is_set("lo_frequency"):
            warnings.warn(
                "QuaConfigMixInputs.lo_frequency is deprecated", DeprecationWarning
            )


@dataclass(eq=False, repr=False)
class QuaConfigSingleInputCollection(betterproto.Message):
    inputs: Dict[str, "QuaConfigDacPortReference"] = betterproto.map_field(
        1, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE
    )


@dataclass(eq=False, repr=False)
class QuaConfigMultipleInputs(betterproto.Message):
    inputs: Dict[str, "QuaConfigDacPortReference"] = betterproto.map_field(
        1, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE
    )


@dataclass(eq=False, repr=False)
class QuaConfigGeneralPortReference(betterproto.Message):
    device_name: str = betterproto.string_field(1)
    port: int = betterproto.uint32_field(2)


@dataclass(eq=False, repr=False)
class QuaConfigElementDec(betterproto.Message):
    outputs: Dict[str, "QuaConfigAdcPortReference"] = betterproto.map_field(
        3, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE
    )
    digital_inputs: Dict[
        str, "QuaConfigDigitalInputPortReference"
    ] = betterproto.map_field(4, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE)
    digital_outputs: Dict[
        str, "QuaConfigDigitalOutputPortReference"
    ] = betterproto.map_field(9, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE)
    rf_inputs: Dict[str, "QuaConfigGeneralPortReference"] = betterproto.map_field(
        10, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE
    )
    rf_outputs: Dict[str, "QuaConfigGeneralPortReference"] = betterproto.map_field(
        11, betterproto.TYPE_STRING, betterproto.TYPE_MESSAGE
    )
    single_input: "QuaConfigSingleInput" = betterproto.message_field(
        5, group="element_inputs_one_of"
    )
    mix_inputs: "QuaConfigMixInputs" = betterproto.message_field(
        6, group="element_inputs_one_of"
    )
    single_input_collection: "QuaConfigSingleInputCollection" = (
        betterproto.message_field(50, group="element_inputs_one_of")
    )
    multiple_inputs: "QuaConfigMultipleInputs" = betterproto.message_field(
        51, group="element_inputs_one_of"
    )
    time_of_flight: Optional[int] = betterproto.message_field(
        7, wraps=betterproto.TYPE_UINT32
    )
    smearing: Optional[int] = betterproto.message_field(
        8, wraps=betterproto.TYPE_UINT32
    )
    intermediate_frequency: Optional[int] = betterproto.message_field(
        20, wraps=betterproto.TYPE_UINT64
    )
    intermediate_frequency_double: float = betterproto.double_field(24)
    intermediate_frequency_negative: bool = betterproto.bool_field(23)
    operations: Dict[str, str] = betterproto.map_field(
        21, betterproto.TYPE_STRING, betterproto.TYPE_STRING
    )
    measurement_qe: Optional[str] = betterproto.message_field(
        22, wraps=betterproto.TYPE_STRING
    )
    output_pulse_parameters: "QuaConfigOutputPulseParameters" = (
        betterproto.message_field(30)
    )
    hold_offset: "QuaConfigHoldOffset" = betterproto.message_field(31)
    sticky: "QuaConfigSticky" = betterproto.message_field(32)
    thread: "QuaConfigElementThread" = betterproto.message_field(40)
    intermediate_frequency_oscillator: Optional[int] = betterproto.message_field(
        61, wraps=betterproto.TYPE_INT64, group="oscillator_one_of"
    )
    intermediate_frequency_oscillator_double: float = betterproto.double_field(
        64, group="oscillator_one_of"
    )
    named_oscillator: Optional[str] = betterproto.message_field(
        62, wraps=betterproto.TYPE_STRING, group="oscillator_one_of"
    )
    no_oscillator: "betterproto_lib_google_protobuf.Empty" = betterproto.message_field(
        63, group="oscillator_one_of"
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.is_set("intermediate_frequency"):
            warnings.warn(
                "QuaConfigElementDec.intermediate_frequency is deprecated",
                DeprecationWarning,
            )
        if self.is_set("hold_offset"):
            warnings.warn(
                "QuaConfigElementDec.hold_offset is deprecated", DeprecationWarning
            )
        if self.is_set("intermediate_frequency_oscillator"):
            warnings.warn(
                "QuaConfigElementDec.intermediate_frequency_oscillator is deprecated",
                DeprecationWarning,
            )
        if self.is_set("intermediate_frequency_oscillator_double"):
            warnings.warn(
                "QuaConfigElementDec.intermediate_frequency_oscillator_double is deprecated",
                DeprecationWarning,
            )


@dataclass(eq=False, repr=False)
class QuaConfigElementThread(betterproto.Message):
    thread_name: str = betterproto.string_field(1)


@dataclass(eq=False, repr=False)
class QuaConfigOutputPulseParameters(betterproto.Message):
    threshold: int = betterproto.uint32_field(1)
    table: List[int] = betterproto.uint32_field(2)
    signal_threshold: int = betterproto.int32_field(3)
    signal_polarity: "QuaConfigOutputPulseParametersPolarity" = betterproto.enum_field(
        4
    )
    derivative_threshold: int = betterproto.int32_field(5)
    derivative_polarity: "QuaConfigOutputPulseParametersPolarity" = (
        betterproto.enum_field(6)
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.is_set("threshold"):
            warnings.warn(
                "QuaConfigOutputPulseParameters.threshold is deprecated",
                DeprecationWarning,
            )
        if self.is_set("table"):
            warnings.warn(
                "QuaConfigOutputPulseParameters.table is deprecated", DeprecationWarning
            )


@dataclass(eq=False, repr=False)
class QuaConfigHoldOffset(betterproto.Message):
    duration: int = betterproto.int32_field(1)


@dataclass(eq=False, repr=False)
class QuaConfigSticky(betterproto.Message):
    analog: bool = betterproto.bool_field(1)
    digital: bool = betterproto.bool_field(2)
    duration: int = betterproto.int32_field(3)


@dataclass(eq=False, repr=False)
class QuaConfigDacPortReference(betterproto.Message):
    controller: str = betterproto.string_field(1)
    number: int = betterproto.uint32_field(2)


@dataclass(eq=False, repr=False)
class QuaConfigAdcPortReference(betterproto.Message):
    controller: str = betterproto.string_field(1)
    number: int = betterproto.uint32_field(2)


@dataclass(eq=False, repr=False)
class QuaConfigDigitalInputPortReference(betterproto.Message):
    port: "QuaConfigPortReference" = betterproto.message_field(1)
    delay: int = betterproto.uint32_field(2)
    buffer: int = betterproto.uint32_field(3)


@dataclass(eq=False, repr=False)
class QuaConfigDigitalOutputPortReference(betterproto.Message):
    port: "QuaConfigPortReference" = betterproto.message_field(1)


@dataclass(eq=False, repr=False)
class QuaConfigPortReference(betterproto.Message):
    controller: str = betterproto.string_field(1)
    number: int = betterproto.uint32_field(2)


@dataclass(eq=False, repr=False)
class QuaConfigPulseDec(betterproto.Message):
    length: int = betterproto.uint32_field(2)
    operation: int = betterproto.uint32_field(3)
    waveforms: Dict[str, str] = betterproto.map_field(
        4, betterproto.TYPE_STRING, betterproto.TYPE_STRING
    )
    digital_marker: Optional[str] = betterproto.message_field(
        5, wraps=betterproto.TYPE_STRING
    )
    integration_weights: Dict[str, str] = betterproto.map_field(
        8, betterproto.TYPE_STRING, betterproto.TYPE_STRING
    )


@dataclass(eq=False, repr=False)
class QuaConfigWaveformDec(betterproto.Message):
    arbitrary: "QuaConfigArbitraryWaveformDec" = betterproto.message_field(
        1, group="waveform_oneof"
    )
    constant: "QuaConfigConstantWaveformDec" = betterproto.message_field(
        2, group="waveform_oneof"
    )
    compressed: "QuaConfigCompressedWaveformDec" = betterproto.message_field(
        3, group="waveform_oneof"
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.is_set("compressed"):
            warnings.warn(
                "QuaConfigWaveformDec.compressed is deprecated", DeprecationWarning
            )


@dataclass(eq=False, repr=False)
class QuaConfigArbitraryWaveformDec(betterproto.Message):
    samples: List[float] = betterproto.double_field(1)
    multiplier: float = betterproto.double_field(2)
    deprecated_max_allowed_error: float = betterproto.double_field(3)
    max_allowed_error: Optional[float] = betterproto.message_field(
        4, wraps=betterproto.TYPE_DOUBLE
    )
    sampling_rate: Optional[float] = betterproto.message_field(
        5, wraps=betterproto.TYPE_DOUBLE
    )
    is_overridable: bool = betterproto.bool_field(6)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.is_set("deprecated_max_allowed_error"):
            warnings.warn(
                "QuaConfigArbitraryWaveformDec.deprecated_max_allowed_error is deprecated",
                DeprecationWarning,
            )


@dataclass(eq=False, repr=False)
class QuaConfigCompressedWaveformDec(betterproto.Message):
    samples: List[float] = betterproto.double_field(1)
    sample_rate: float = betterproto.double_field(2)


@dataclass(eq=False, repr=False)
class QuaConfigConstantWaveformDec(betterproto.Message):
    sample: float = betterproto.double_field(1)
    multiplier: float = betterproto.double_field(2)


@dataclass(eq=False, repr=False)
class QuaConfigDigitalWaveformDec(betterproto.Message):
    samples: List["QuaConfigDigitalWaveformSample"] = betterproto.message_field(1)


@dataclass(eq=False, repr=False)
class QuaConfigDigitalWaveformSample(betterproto.Message):
    value: bool = betterproto.bool_field(1)
    length: int = betterproto.uint32_field(2)


@dataclass(eq=False, repr=False)
class QuaConfigMixerDec(betterproto.Message):
    correction: List["QuaConfigCorrectionEntry"] = betterproto.message_field(1)


@dataclass(eq=False, repr=False)
class QuaConfigIntegrationWeightDec(betterproto.Message):
    cosine: List["QuaConfigIntegrationWeightSample"] = betterproto.message_field(1)
    sine: List["QuaConfigIntegrationWeightSample"] = betterproto.message_field(2)


@dataclass(eq=False, repr=False)
class QuaConfigIntegrationWeightSample(betterproto.Message):
    value: float = betterproto.double_field(1)
    length: int = betterproto.uint32_field(2)


@dataclass(eq=False, repr=False)
class QuaConfigCorrectionEntry(betterproto.Message):
    frequency: int = betterproto.uint64_field(1)
    lo_frequency: int = betterproto.uint64_field(2)
    correction: "QuaConfigMatrix" = betterproto.message_field(3)
    frequency_negative: bool = betterproto.bool_field(4)
    frequency_double: float = betterproto.double_field(5)
    lo_frequency_double: float = betterproto.double_field(6)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.is_set("frequency"):
            warnings.warn(
                "QuaConfigCorrectionEntry.frequency is deprecated", DeprecationWarning
            )
        if self.is_set("lo_frequency"):
            warnings.warn(
                "QuaConfigCorrectionEntry.lo_frequency is deprecated",
                DeprecationWarning,
            )


@dataclass(eq=False, repr=False)
class QuaConfigMatrix(betterproto.Message):
    v00: float = betterproto.double_field(1)
    v01: float = betterproto.double_field(2)
    v10: float = betterproto.double_field(3)
    v11: float = betterproto.double_field(4)


@dataclass(eq=False, repr=False)
class QuaConfigOctave(betterproto.Message):
    pass


@dataclass(eq=False, repr=False)
class QuaConfigOctaveConfig(betterproto.Message):
    loopbacks: List["QuaConfigOctaveLoopback"] = betterproto.message_field(1)
    rf_outputs: Dict[int, "QuaConfigOctaveRfOutputConfig"] = betterproto.map_field(
        2, betterproto.TYPE_UINT32, betterproto.TYPE_MESSAGE
    )
    rf_inputs: Dict[int, "QuaConfigOctaveRfInputConfig"] = betterproto.map_field(
        3, betterproto.TYPE_UINT32, betterproto.TYPE_MESSAGE
    )
    if_outputs: "QuaConfigOctaveIfOutputsConfig" = betterproto.message_field(4)


@dataclass(eq=False, repr=False)
class QuaConfigOctaveLoopback(betterproto.Message):
    lo_source_input: "QuaConfigOctaveLoopbackInput" = betterproto.enum_field(1)
    lo_source_generator: "QuaConfigOctaveSynthesizerPort" = betterproto.message_field(2)


@dataclass(eq=False, repr=False)
class QuaConfigOctaveSynthesizerPort(betterproto.Message):
    device_name: str = betterproto.string_field(1)
    port_name: "QuaConfigOctaveSynthesizerOutputName" = betterproto.enum_field(2)


@dataclass(eq=False, repr=False)
class QuaConfigOctaveRfOutputConfig(betterproto.Message):
    lo_frequency: float = betterproto.double_field(1)
    lo_source: "QuaConfigOctaveLoSourceInput" = betterproto.enum_field(2)
    output_mode: "QuaConfigOctaveOutputSwitchState" = betterproto.enum_field(3)
    gain: float = betterproto.float_field(4)
    input_attenuators: bool = betterproto.bool_field(5)
    i_connection: "QuaConfigDacPortReference" = betterproto.message_field(6)
    q_connection: "QuaConfigDacPortReference" = betterproto.message_field(7)


@dataclass(eq=False, repr=False)
class QuaConfigOctaveRfInputConfig(betterproto.Message):
    rf_source: "QuaConfigOctaveDownconverterRfSource" = betterproto.enum_field(1)
    lo_frequency: float = betterproto.double_field(2)
    lo_source: "QuaConfigOctaveLoSourceInput" = betterproto.enum_field(3)
    if_mode_i: "QuaConfigOctaveIfMode" = betterproto.enum_field(4)
    if_mode_q: "QuaConfigOctaveIfMode" = betterproto.enum_field(5)


@dataclass(eq=False, repr=False)
class QuaConfigOctaveSingleIfOutputConfig(betterproto.Message):
    port: "QuaConfigAdcPortReference" = betterproto.message_field(1)
    name: str = betterproto.string_field(2)


@dataclass(eq=False, repr=False)
class QuaConfigOctaveIfOutputsConfig(betterproto.Message):
    if_out1: "QuaConfigOctaveSingleIfOutputConfig" = betterproto.message_field(1)
    if_out2: "QuaConfigOctaveSingleIfOutputConfig" = betterproto.message_field(2)
