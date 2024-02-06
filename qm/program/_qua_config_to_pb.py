import uuid
from typing import Any, Dict, List, Optional

import betterproto
import numpy as np
from betterproto.lib.google.protobuf import Empty
from dependency_injector.wiring import Provide, inject

from qm.grpc import qua_config as cfg
from qm.api.models.capabilities import ServerCapabilities
from qm.containers.capabilities_container import CapabilitiesContainer
from qm.grpc.qua_config import QuaConfigCorrectionEntry, QuaConfigGeneralPortReference
from qm.exceptions import (
    InvalidOctaveParameter,
    NoInputsOrOutputsError,
    ConfigValidationException,
    OctaveConnectionAmbiguity,
    ElementOutputConnectionAmbiguity,
)
from qm.program._validate_config_schema import (
    validate_oscillator,
    validate_output_tof,
    validate_used_inputs,
    validate_output_smearing,
    validate_sticky_duration,
    validate_arbitrary_waveform,
    validate_timetagging_parameters,
)

ALLOWED_GAINES = {x / 2 for x in range(-40, 41)}


def analog_input_port_to_pb(data: Dict[str, Any]) -> cfg.QuaConfigAnalogInputPortDec:
    analog_input = cfg.QuaConfigAnalogInputPortDec(
        offset=data.get("offset", 0.0),
        shareable=bool(data.get("shareable")),
        gain_db=int(data.get("gain_db", 0)),
    )
    return analog_input


def analog_output_port_to_pb(data: Dict[str, Any]) -> cfg.QuaConfigAnalogOutputPortDec:
    analog_output = cfg.QuaConfigAnalogOutputPortDec(shareable=bool(data.get("shareable")))

    if "offset" in data:
        analog_output.offset = data["offset"]

    if "delay" in data:
        delay = data.get("delay", 0)
        if delay < 0:
            raise ConfigValidationException(f"analog output delay cannot be a negative value, given value: {delay}")
        analog_output.delay = delay

    if "filter" in data:
        analog_output.filter = cfg.QuaConfigAnalogOutputPortFilter(
            feedforward=data["filter"]["feedforward"],
            feedback=data["filter"]["feedback"],
        )

    if "crosstalk" in data:
        for k, v in data["crosstalk"].items():
            analog_output.crosstalk[int(k)] = v

    return analog_output


def digital_output_port_to_pb(data: Dict[str, Any]) -> cfg.QuaConfigDigitalOutputPortDec:
    digital_output = cfg.QuaConfigDigitalOutputPortDec(
        shareable=bool(data.get("shareable")),
        inverted=bool(data.get("inverted", False)),
    )
    return digital_output


def digital_input_port_to_pb(data: Dict):
    digital_input = cfg.QuaConfigDigitalInputPortDec(shareable=bool(data.get("shareable")))

    if "window" in data:
        digital_input.window = data["window"]

    if "threshold" in data:
        digital_input.threshold = data["threshold"]

    if "polarity" in data:
        if data["polarity"].upper() == "RISING":
            digital_input.polarity = cfg.QuaConfigDigitalInputPortDecPolarity.RISING
        elif data["polarity"].upper() == "FALLING":
            digital_input.polarity = cfg.QuaConfigDigitalInputPortDecPolarity.FALLING

    if "deadtime" in data:
        digital_input.deadtime = int(data["deadtime"])

    return digital_input


def controller_to_pb(data: Dict[str, Any]) -> cfg.QuaConfigControllerDec:
    cont = cfg.QuaConfigControllerDec(type=data.get("type", "opx1"))

    if "type" in data:
        cont.type = data["type"]

    if "analog_outputs" in data:
        for _k, _v in data["analog_outputs"].items():
            int_k = int(_k)
            cont.analog_outputs[int_k] = analog_output_port_to_pb(_v)

    if "analog_inputs" in data:
        for _k, _v in data["analog_inputs"].items():
            cont.analog_inputs[int(_k)] = analog_input_port_to_pb(_v)

    if "digital_outputs" in data:
        for _k, _v in data["digital_outputs"].items():
            cont.digital_outputs[int(_k)] = digital_output_port_to_pb(_v)

    if "digital_inputs" in data:
        for _k, _v in data["digital_inputs"].items():
            cont.digital_inputs[int(_k)] = digital_input_port_to_pb(_v)

    return cont


def get_octave_loopbacks(data: List) -> List[cfg.QuaConfigOctaveLoopback]:
    loopbacks = [
        cfg.QuaConfigOctaveLoopback(
            lo_source_input=cfg.QuaConfigOctaveLoopbackInput[loopback[1]],
            lo_source_generator=cfg.QuaConfigOctaveSynthesizerPort(
                device_name=loopback[0][0],
                port_name=cfg.QuaConfigOctaveSynthesizerOutputName[loopback[0][1].lower()],
            ),
        )
        for loopback in data
    ]
    return loopbacks


def octave_to_pb(data: Dict[str, Any]) -> cfg.QuaConfigOctaveConfig:
    connectivity = data.get("connectivity", None)
    loopbacks = get_octave_loopbacks(data.get("loopbacks", []))
    rf_modules = {
        k: rf_module_to_pb(standardize_connectivity_for_if_in(v, connectivity, k))
        for k, v in data.get("RF_outputs", {}).items()
    }
    rf_inputs = {k: rf_input_to_pb(v, k) for k, v in data.get("RF_inputs", {}).items()}
    if_outputs = _octave_if_outputs_to_pb(standardize_connectivity_for_if_out(data.get("IF_outputs", {}), connectivity))
    return cfg.QuaConfigOctaveConfig(
        loopbacks=loopbacks,
        rf_outputs=rf_modules,
        rf_inputs=rf_inputs,
        if_outputs=if_outputs,
    )


def standardize_connectivity_for_if_in(
    data: Dict[str, Any], opx_connectivity: Optional[str], module_number
) -> Dict[str, Any]:
    if opx_connectivity is not None:
        if ("I_connection" in data) or ("Q_connection" in data):
            raise OctaveConnectionAmbiguity()

        data["I_connection"] = (opx_connectivity, 2 * module_number - 1)
        data["Q_connection"] = (opx_connectivity, 2 * module_number)
    return data


IF_OUT1_DEFAULT = "out1"
IF_OUT2_DEFAULT = "out2"


def standardize_connectivity_for_if_out(data: Dict[str, Any], opx_connectivity: Optional[str]) -> Dict[str, Any]:
    if opx_connectivity is not None:
        if "IF_out1" not in data:
            data["IF_out1"] = {"name": IF_OUT1_DEFAULT}
        if "IF_out2" not in data:
            data["IF_out2"] = {"name": IF_OUT2_DEFAULT}
        if ("port" in data["IF_out1"]) or ("port" in data["IF_out2"]):
            raise OctaveConnectionAmbiguity()
        data["IF_out1"]["port"] = (opx_connectivity, 1)
        data["IF_out2"]["port"] = (opx_connectivity, 2)
    return data


def _get_lo_frequency(data: Dict[str, Any]) -> float:
    if "LO_frequency" not in data:
        raise ConfigValidationException("No LO frequency was set for upconverter")
    lo_freq = data["LO_frequency"]
    if not 2e9 <= lo_freq <= 18e9:
        raise ConfigValidationException(f"LO frequency {lo_freq} is out of range")
    return lo_freq


def rf_module_to_pb(data: Dict[str, Any]) -> cfg.QuaConfigOctaveRfOutputConfig:
    input_attenuators = data.get("input_attenuators", "OFF").upper()
    if input_attenuators not in {"ON", "OFF"}:
        raise ConfigValidationException("input_attenuators must be either ON or OFF")
    if "gain" not in data:
        raise ConfigValidationException("No gain was set for upconverter")
    gain = float(data["gain"])
    if gain not in ALLOWED_GAINES:
        raise ConfigValidationException(f"Gain should be an integer or half-integer between -20 and 20, got {gain})")
    to_return = cfg.QuaConfigOctaveRfOutputConfig(
        lo_frequency=_get_lo_frequency(data),
        lo_source=cfg.QuaConfigOctaveLoSourceInput[data.get("LO_source", "internal").lower()],
        output_mode=cfg.QuaConfigOctaveOutputSwitchState[data.get("output_mode", "always_off").lower()],
        gain=gain,
        input_attenuators=input_attenuators == "ON",
    )
    if "I_connection" in data:
        to_return.i_connection = dac_port_ref_to_pb(*data["I_connection"])
    if "Q_connection" in data:
        to_return.q_connection = dac_port_ref_to_pb(*data["Q_connection"])
    return to_return


def rf_input_to_pb(data: Dict[str, Any], input_idx: int = 0) -> cfg.QuaConfigOctaveRfInputConfig:
    input_idx_to_default_lo_source = {0: "not_set", 1: "internal", 2: "external"}  # 0 here is just for the default
    rf_source = cfg.QuaConfigOctaveDownconverterRfSource[data.get("RF_source", "RF_in").lower()]
    if input_idx == 1 and rf_source != cfg.QuaConfigOctaveDownconverterRfSource.rf_in:
        raise InvalidOctaveParameter("Downconverter 1 must be connected to RF-in")

    lo_source = cfg.QuaConfigOctaveLoSourceInput[
        data.get("LO_source", input_idx_to_default_lo_source[input_idx]).lower()
    ]
    if input_idx == 2 and lo_source == cfg.QuaConfigOctaveLoSourceInput.internal:
        raise InvalidOctaveParameter("Downconverter 2 does not have internal LO")

    to_return = cfg.QuaConfigOctaveRfInputConfig(
        rf_source=rf_source,
        lo_frequency=_get_lo_frequency(data),
        lo_source=lo_source,
        if_mode_i=cfg.QuaConfigOctaveIfMode[data.get("IF_mode_I", "direct").lower()],
        if_mode_q=cfg.QuaConfigOctaveIfMode[data.get("IF_mode_Q", "direct").lower()],
    )
    return to_return


def single_if_output_to_pb(data: Dict[str, Any]) -> cfg.QuaConfigOctaveSingleIfOutputConfig:
    return cfg.QuaConfigOctaveSingleIfOutputConfig(port=cfg.QuaConfigAdcPortReference(*data["port"]), name=data["name"])


def _octave_if_outputs_to_pb(data: Dict[str, Any]) -> cfg.QuaConfigOctaveIfOutputsConfig:
    inst = cfg.QuaConfigOctaveIfOutputsConfig()
    if "IF_out1" in data:
        inst.if_out1 = single_if_output_to_pb(data["IF_out1"])
    if "IF_out2" in data:
        inst.if_out2 = single_if_output_to_pb(data["IF_out2"])
    return inst


@inject
def mixer_ref_to_pb(
    name: str,
    lo_frequency: int,
    capabilities: ServerCapabilities = Provide[CapabilitiesContainer.capabilities],
) -> cfg.QuaConfigMixerRef:
    item = cfg.QuaConfigMixerRef(mixer=name, lo_frequency=int(lo_frequency))
    if capabilities.supports_double_frequency:
        item.lo_frequency_double = float(lo_frequency)
    return item


@inject
def oscillator_to_pb(
    data, capabilities: ServerCapabilities = Provide[CapabilitiesContainer.capabilities]
) -> cfg.QuaConfigOscillator:
    oscillator = cfg.QuaConfigOscillator()
    if "intermediate_frequency" in data:
        oscillator.intermediate_frequency = int(data["intermediate_frequency"])
        if capabilities.supports_double_frequency:
            oscillator.intermediate_frequency_double = float(data["intermediate_frequency"])

    if "mixer" in data:
        oscillator.mixer = cfg.QuaConfigMixerRef(mixer=data["mixer"])
        oscillator.mixer.lo_frequency = int(data.get("lo_frequency", 0))
        if capabilities.supports_double_frequency:
            oscillator.mixer.lo_frequency_double = float(data.get("lo_frequency", 0.0))

    return oscillator


@inject
def create_correction_entry(
    mixer_data,
    capabilities: ServerCapabilities = Provide[CapabilitiesContainer.capabilities],
) -> cfg.QuaConfigCorrectionEntry:
    correction = cfg.QuaConfigCorrectionEntry(
        frequency_negative=mixer_data["intermediate_frequency"] < 0,
        correction=cfg.QuaConfigMatrix(
            v00=mixer_data["correction"][0],
            v01=mixer_data["correction"][1],
            v10=mixer_data["correction"][2],
            v11=mixer_data["correction"][3],
        ),
    )
    correction.frequency = abs(int(mixer_data["intermediate_frequency"]))
    correction.lo_frequency = int(mixer_data["lo_frequency"])
    if capabilities.supports_double_frequency:
        correction.frequency_double = abs(float(mixer_data["intermediate_frequency"]))
        correction.lo_frequency_double = float(mixer_data["lo_frequency"])

    return correction


def mixer_to_pb(data) -> cfg.QuaConfigMixerDec:
    return cfg.QuaConfigMixerDec(correction=[create_correction_entry(mixer) for mixer in data])


def element_thread_to_pb(name: str) -> cfg.QuaConfigElementThread:
    return cfg.QuaConfigElementThread(thread_name=name)


def dac_port_ref_to_pb(controller: str, number: int) -> cfg.QuaConfigDacPortReference:
    return cfg.QuaConfigDacPortReference(controller=controller, number=number)


def single_input_to_pb(controller: str, number: int) -> cfg.QuaConfigSingleInput:
    return cfg.QuaConfigSingleInput(port=dac_port_ref_to_pb(controller, number))


def adc_port_ref_to_pb(controller: str, number: int) -> cfg.QuaConfigAdcPortReference:
    return cfg.QuaConfigAdcPortReference(controller=controller, number=number)


def port_ref_to_pb(controller: str, number: int) -> cfg.QuaConfigPortReference:
    return cfg.QuaConfigPortReference(controller=controller, number=number)


def digital_input_port_ref_to_pb(data) -> cfg.QuaConfigDigitalInputPortReference:
    digital_input = cfg.QuaConfigDigitalInputPortReference(
        delay=int(data["delay"]),
        buffer=int(data["buffer"]),
    )
    if "port" in data:
        digital_input.port = port_ref_to_pb(data["port"][0], data["port"][1])

    return digital_input


def digital_output_port_ref_to_pb(data) -> cfg.QuaConfigDigitalOutputPortReference:
    return cfg.QuaConfigDigitalOutputPortReference(port=port_ref_to_pb(data[0], data[1]))


@inject
def element_to_pb(
    element_name,
    data,
    capabilities: ServerCapabilities = Provide[CapabilitiesContainer.capabilities],
) -> cfg.QuaConfigElementDec():
    validate_oscillator(data)
    validate_output_smearing(data)
    validate_output_tof(data)
    validate_timetagging_parameters(data)
    validate_used_inputs(data)

    element = cfg.QuaConfigElementDec()

    if "time_of_flight" in data:
        element.time_of_flight = int(data["time_of_flight"])

    if "smearing" in data:
        element.smearing = int(data["smearing"])

    if "intermediate_frequency" in data:
        element.intermediate_frequency = abs(int(data["intermediate_frequency"]))
        element.intermediate_frequency_oscillator = int(data["intermediate_frequency"])
        if capabilities.supports_double_frequency:
            element.intermediate_frequency_double = abs(float(data["intermediate_frequency"]))
            element.intermediate_frequency_oscillator_double = float(data["intermediate_frequency"])

        element.intermediate_frequency_negative = data["intermediate_frequency"] < 0

    if "thread" in data:
        element.thread = element_thread_to_pb(data["thread"])

    if "outputs" in data:
        for k, v in data["outputs"].items():
            element.outputs[k] = adc_port_ref_to_pb(v[0], v[1])

    if "digitalInputs" in data:
        for k, v in data["digitalInputs"].items():
            element.digital_inputs[k] = digital_input_port_ref_to_pb(v)

    if "digitalOutputs" in data:
        for k, v in data["digitalOutputs"].items():
            element.digital_outputs[k] = digital_output_port_ref_to_pb(v)

    if "operations" in data:
        for k, v in data["operations"].items():
            element.operations[k] = v

    if "singleInput" in data:
        (cont, port_id) = data["singleInput"]["port"]
        element.single_input = single_input_to_pb(cont, port_id)

    if "mixInputs" in data:
        mix_inputs = data["mixInputs"]
        (cont_I, port_id_I) = mix_inputs["I"]
        (cont_Q, port_id_Q) = mix_inputs["Q"]
        element.mix_inputs = cfg.QuaConfigMixInputs(
            i=dac_port_ref_to_pb(cont_I, port_id_I),
            q=dac_port_ref_to_pb(cont_Q, port_id_Q),
            mixer=mix_inputs.get("mixer", ""),
        )

        lo_frequency = mix_inputs.get("lo_frequency", 0)
        element.mix_inputs.lo_frequency = int(lo_frequency)
        if capabilities.supports_double_frequency:
            element.mix_inputs.lo_frequency_double = float(lo_frequency)

    if "singleInputCollection" in data:
        element.single_input_collection = cfg.QuaConfigSingleInputCollection(
            inputs={k: dac_port_ref_to_pb(v[0], v[1]) for k, v in data["singleInputCollection"]["inputs"].items()}
        )

    if "multipleInputs" in data:
        element.multiple_inputs = cfg.QuaConfigMultipleInputs(
            inputs={k: dac_port_ref_to_pb(v[0], v[1]) for k, v in data["multipleInputs"]["inputs"].items()}
        )

    if "oscillator" in data:
        element.named_oscillator = data["oscillator"]
    elif "intermediate_frequency" not in data:
        element.no_oscillator = Empty()

    if "sticky" in data:
        if "duration" in data["sticky"]:
            validate_sticky_duration(data["sticky"]["duration"])
        if capabilities.supports_sticky_elements:
            element.sticky = cfg.QuaConfigSticky(
                analog=data["sticky"].get("analog", True),
                digital=data["sticky"].get("digital", False),
                duration=int(data["sticky"].get("duration", 4) / 4),
            )
        else:
            if "digital" in data["sticky"] and data["sticky"]["digital"]:
                raise ConfigValidationException(
                    f"Server does not support digital sticky used in element " f"'{element_name}'"
                )
            element.hold_offset = cfg.QuaConfigHoldOffset(duration=int(data["sticky"].get("duration", 4) / 4))

    elif "hold_offset" in data:
        if capabilities.supports_sticky_elements:
            element.sticky = cfg.QuaConfigSticky(
                analog=True,
                digital=False,
                duration=data["hold_offset"].get("duration", 1),
            )
        else:
            element.hold_offset = cfg.QuaConfigHoldOffset(duration=data["hold_offset"]["duration"])

    if "outputPulseParameters" in data:
        pulse_parameters = data["outputPulseParameters"]
        output_pulse_parameters = cfg.QuaConfigOutputPulseParameters(
            signal_threshold=pulse_parameters["signalThreshold"],
        )

        signal_polarity = pulse_parameters["signalPolarity"].upper()
        if signal_polarity == "ABOVE" or signal_polarity == "ASCENDING":
            output_pulse_parameters.signal_polarity = cfg.QuaConfigOutputPulseParametersPolarity.ASCENDING
        elif signal_polarity == "BELOW" or signal_polarity == "DESCENDING":
            output_pulse_parameters.signal_polarity = cfg.QuaConfigOutputPulseParametersPolarity.DESCENDING

        if "derivativeThreshold" in pulse_parameters:
            output_pulse_parameters.derivative_threshold = pulse_parameters["derivativeThreshold"]
            polarity = pulse_parameters["derivativePolarity"].upper()
            if polarity == "ABOVE" or polarity == "ASCENDING":
                output_pulse_parameters.derivative_polarity = cfg.QuaConfigOutputPulseParametersPolarity.ASCENDING
            elif polarity == "BELOW" or polarity == "DESCENDING":
                output_pulse_parameters.derivative_polarity = cfg.QuaConfigOutputPulseParametersPolarity.DESCENDING

        element.output_pulse_parameters = output_pulse_parameters

    rf_inputs = data.get("RF_inputs", {})
    for k, (device, port) in rf_inputs.items():
        element.rf_inputs[k] = QuaConfigGeneralPortReference(device_name=device, port=port)

    rf_outputs = data.get("RF_outputs", {})
    for k, (device, port) in rf_outputs.items():
        element.rf_outputs[k] = QuaConfigGeneralPortReference(device_name=device, port=port)
    return element


def waveform_to_pb(data) -> cfg.QuaConfigWaveformDec:
    wf = cfg.QuaConfigWaveformDec()
    if data["type"] == "constant":
        wf.constant = cfg.QuaConfigConstantWaveformDec(sample=data["sample"])
    elif data["type"] == "arbitrary":
        is_overridable = data.get("is_overridable", False)
        has_max_allowed_error = "max_allowed_error" in data
        has_sampling_rate = "sampling_rate" in data
        validate_arbitrary_waveform(is_overridable, has_max_allowed_error, has_sampling_rate)

        wf.arbitrary = cfg.QuaConfigArbitraryWaveformDec(samples=data["samples"], is_overridable=is_overridable)

        if has_max_allowed_error:
            wf.arbitrary.max_allowed_error = data["max_allowed_error"]
        elif has_sampling_rate:
            wf.arbitrary.sampling_rate = data["sampling_rate"]
        elif not is_overridable:
            wf.arbitrary.max_allowed_error = 1e-4
    return wf


def digital_waveform_to_pb(data) -> cfg.QuaConfigDigitalWaveformDec:
    return cfg.QuaConfigDigitalWaveformDec(
        samples=[cfg.QuaConfigDigitalWaveformSample(value=bool(s[0]), length=s[1]) for s in data["samples"]]
    )


def pulse_to_pb(data) -> cfg.QuaConfigPulseDec:
    pulse = cfg.QuaConfigPulseDec()

    if "length" in data:
        pulse.length = int(data["length"])

    if "operation" in data:
        if data["operation"] == "control":
            pulse.operation = cfg.QuaConfigPulseDecOperation.CONTROL
        else:
            pulse.operation = cfg.QuaConfigPulseDecOperation.MEASUREMENT

    if "digital_marker" in data:
        pulse.digital_marker = data["digital_marker"]

    if "integration_weights" in data:
        for k, v in data["integration_weights"].items():
            pulse.integration_weights[k] = v

    if "waveforms" in data:
        if "single" in data["waveforms"]:
            pulse.waveforms["single"] = data["waveforms"]["single"]

        elif "I" in data["waveforms"]:
            pulse.waveforms["I"] = data["waveforms"]["I"]
            pulse.waveforms["Q"] = data["waveforms"]["Q"]
    return pulse


def build_iw_sample(data) -> List[cfg.QuaConfigIntegrationWeightSample]:
    if len(data) > 0 and not isinstance(data[0], tuple):
        data = np.round(2**-15 * np.round(np.array(data) / 2**-15), 20)
        new_data = []
        for s in data:
            if len(new_data) == 0 or new_data[-1][0] != s:
                new_data.append((s, 4))
            else:
                new_data[-1] = (new_data[-1][0], new_data[-1][1] + 4)
        data = new_data
    return [cfg.QuaConfigIntegrationWeightSample(value=s[0], length=int(s[1])) for s in data]


def integration_weights_to_pb(data) -> cfg.QuaConfigIntegrationWeightDec:
    iw = cfg.QuaConfigIntegrationWeightDec(cosine=build_iw_sample(data["cosine"]), sine=build_iw_sample(data["sine"]))
    return iw


def set_octave_upconverter_connection_to_elements(pb_config: cfg.QuaConfig) -> None:
    for element in pb_config.v1_beta.elements.values():
        for rf_input in element.rf_inputs.values():
            if rf_input.device_name in pb_config.v1_beta.octaves:
                if rf_input.port in pb_config.v1_beta.octaves[rf_input.device_name].rf_outputs:
                    _, element_input = betterproto.which_one_of(element, "element_inputs_one_of")
                    if element_input is not None:
                        raise ValueError()

                    upconverter_config = pb_config.v1_beta.octaves[rf_input.device_name].rf_outputs[rf_input.port]
                    element.mix_inputs = cfg.QuaConfigMixInputs(
                        i=upconverter_config.i_connection, q=upconverter_config.q_connection
                    )


@inject
def set_lo_frequency_to_mix_input_elements_that_are_connected_to_octave(
    pb_config: cfg.QuaConfig, capabilities: ServerCapabilities = Provide[CapabilitiesContainer.capabilities]
) -> None:
    for element in pb_config.v1_beta.elements.values():
        _, element_input = betterproto.which_one_of(element, "element_inputs_one_of")
        if isinstance(element_input, cfg.QuaConfigMixInputs):
            for octave in pb_config.v1_beta.octaves.values():
                for _, rf_output in octave.rf_outputs.items():
                    if (
                        (rf_output.i_connection.controller == element_input.i.controller)
                        and (rf_output.i_connection.number == element_input.i.number)
                        and (rf_output.q_connection.controller == element_input.q.controller)
                        and (rf_output.q_connection.number == element_input.q.number)
                    ):
                        if element_input.lo_frequency not in {0, rf_output.lo_frequency}:
                            raise ValueError(
                                "LO frequency mismatch. The frequency stated in the element is different from "
                                "the one stated in the Octave, remove the one in the element."
                            )
                        element_input.lo_frequency = int(rf_output.lo_frequency)
                        if capabilities.supports_double_frequency:
                            element_input.lo_frequency_double = rf_output.lo_frequency


I_IN_PORT = "I"
Q_IN_PORT = "Q"


def set_octave_downconverter_connection_to_elements(pb_config: cfg.QuaConfig) -> None:
    for element in pb_config.v1_beta.elements.values():
        for _, rf_output in element.rf_outputs.items():
            if rf_output.device_name in pb_config.v1_beta.octaves:
                if rf_output.port in pb_config.v1_beta.octaves[rf_output.device_name].rf_inputs:
                    downconverter_config = pb_config.v1_beta.octaves[rf_output.device_name].if_outputs
                    outputs_form_octave = {
                        downconverter_config.if_out1.name: downconverter_config.if_out1.port,
                        downconverter_config.if_out2.name: downconverter_config.if_out2.port,
                    }
                    for k, v in outputs_form_octave.items():
                        if k in element.outputs:
                            if v != element.outputs[k]:
                                raise ElementOutputConnectionAmbiguity(
                                    f"Output {k} is connected to {element.outputs[k]} but the octave "
                                    f"downconverter is connected to {v}"
                                )
                        else:
                            element.outputs[k] = v


def set_non_existing_mixers_in_mix_input_elements(pb_config: cfg.QuaConfig) -> None:
    for element_name, element in pb_config.v1_beta.elements.items():
        _, element_input = betterproto.which_one_of(element, "element_inputs_one_of")
        if isinstance(element_input, cfg.QuaConfigMixInputs):
            if (
                element.intermediate_frequency
            ):  # This is here because in validation I saw that we can set an element without IF
                if not element_input.mixer:
                    element_input.mixer = f"{element_name}_mixer_{uuid.uuid4().hex[:3]}"  # The uuid is just to make sure the mixer doesn't exist
                if element_input.mixer not in pb_config.v1_beta.mixers:
                    pb_config.v1_beta.mixers[element_input.mixer] = cfg.QuaConfigMixerDec(
                        correction=[
                            QuaConfigCorrectionEntry(
                                frequency=element.intermediate_frequency,
                                frequency_negative=element.intermediate_frequency_negative,
                                frequency_double=element.intermediate_frequency_double,
                                lo_frequency=element_input.lo_frequency,
                                lo_frequency_double=element_input.lo_frequency_double,
                                correction=cfg.QuaConfigMatrix(v00=1, v01=0, v10=0, v11=1),
                            )
                        ]
                    )


def validate_inputs_or_outputs_exist(pb_config: cfg.QuaConfig) -> None:
    for element in pb_config.v1_beta.elements.values():
        _, element_input = betterproto.which_one_of(element, "element_inputs_one_of")
        if (
            element_input is None
            and not bool(element.outputs)
            and not bool(element.digital_outputs)
            and not bool(element.digital_inputs)
        ):
            raise NoInputsOrOutputsError


def load_config_pb(config) -> cfg.QuaConfig:

    pb_config = cfg.QuaConfig(v1_beta=cfg.QuaConfigQuaConfigV1())

    def set_controllers():
        for k, v in config["controllers"].items():
            pb_config.v1_beta.controllers[k] = controller_to_pb(v)

    def set_octaves():
        for k, v in config.get("octaves", {}).items():
            pb_config.v1_beta.octaves[k] = octave_to_pb(v)

    def set_elements():
        for k, v in config["elements"].items():
            pb_config.v1_beta.elements[k] = element_to_pb(k, v)

    def set_pulses():
        for k, v in config["pulses"].items():
            pb_config.v1_beta.pulses[k] = pulse_to_pb(v)

    def set_waveforms():
        for k, v in config["waveforms"].items():
            pb_config.v1_beta.waveforms[k] = waveform_to_pb(v)

    def set_digital_waveforms():
        for k, v in config["digital_waveforms"].items():
            pb_config.v1_beta.digital_waveforms[k] = digital_waveform_to_pb(v)

    def set_integration_weights():
        for k, v in config["integration_weights"].items():
            pb_config.v1_beta.integration_weights[k] = integration_weights_to_pb(v)

    def set_mixers():
        for k, v in config["mixers"].items():
            pb_config.v1_beta.mixers[k] = mixer_to_pb(v)

    def set_oscillators():
        for k, v in config["oscillators"].items():
            pb_config.v1_beta.oscillators[k] = oscillator_to_pb(v)

    key_to_action = {
        "version": lambda: None,
        "controllers": set_controllers,
        "elements": set_elements,
        "pulses": set_pulses,
        "waveforms": set_waveforms,
        "digital_waveforms": set_digital_waveforms,
        "integration_weights": set_integration_weights,
        "mixers": set_mixers,
        "oscillators": set_oscillators,
        "octaves": set_octaves,
    }

    for key in config:
        key_to_action[key]()

    set_octave_upconverter_connection_to_elements(pb_config)
    set_lo_frequency_to_mix_input_elements_that_are_connected_to_octave(pb_config)
    set_octave_downconverter_connection_to_elements(pb_config)
    set_non_existing_mixers_in_mix_input_elements(pb_config)
    return pb_config
