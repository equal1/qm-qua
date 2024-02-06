from typing import cast

from qm.type_hinting.config_types import DictQuaConfig
from qm.grpc.qua_config import QuaConfig, QuaConfigQuaConfigV1, QuaConfigPulseDecOperation


def convert_msg_to_config(config: QuaConfig) -> DictQuaConfig:
    msg_dict = config.to_dict()

    if "v1Beta" in msg_dict:
        return _convert_v1_beta(msg_dict["v1Beta"])
    else:
        raise Exception("Invalid config")


def _convert_mixers(mixers):
    if mixers is None:
        return {}

    ret = {}
    for name, data in mixers.items():
        temp_list = []
        for correction in data["correction"]:
            if "frequencyDouble" in correction:
                frequency = float(correction["frequencyDouble"])
            elif "frequency" in correction:
                frequency = float(correction["frequency"])
            else:
                frequency = 0.0

            if "frequencyNegative" in correction:
                if bool(correction["frequencyNegative"]):
                    frequency = -frequency

            if "loFrequencyDouble" in correction:
                lo_frequency = float(correction["loFrequencyDouble"])
            elif "loFrequency" in correction:
                lo_frequency = float(correction["loFrequency"])
            else:
                lo_frequency = 0.0

            temp_dict = {
                "intermediate_frequency": frequency,
                "lo_frequency": lo_frequency,
                "correction": _convert_matrix(correction["correction"]),
            }
            temp_list.append(temp_dict)

        ret[name] = temp_list
    return ret


def _convert_matrix(matrix):
    if "v00" in matrix:
        v00 = matrix["v00"]
    else:
        v00 = 0.0

    if "v01" in matrix:
        v01 = matrix["v01"]
    else:
        v01 = 0.0

    if "v10" in matrix:
        v10 = matrix["v10"]
    else:
        v10 = 0.0
    if "v11" in matrix:
        v11 = matrix["v11"]
    else:
        v11 = 0.0

    return [v00, v01, v10, v11]


def _convert_integration_weights(integration_weights):
    if integration_weights is None:
        return {}

    ret = {}
    for name, data in integration_weights.items():
        ret[name] = {
            "cosine": [(s.get("value", 0.0), s.get("length", 0)) for s in data["cosine"]],
            "sine": [(s.get("value", 0.0), s.get("length", 0)) for s in data["sine"]],
        }
    return ret


def _convert_digital_wave_forms(digital_wave_forms):
    if digital_wave_forms is None:
        return {}

    ret = {}
    for name, data in digital_wave_forms.items():
        temp_list = []
        for sample in data["samples"]:
            value = 0
            if "value" in sample:
                value = 1

            if "length" in sample:
                temp_list.append((value, sample["length"]))
            else:
                temp_list.append((value, 0))

        ret[name] = {"samples": temp_list}
    return ret


def _convert_wave_forms(wave_forms):
    if wave_forms is None:
        return {}

    ret = {}
    for name, data in wave_forms.items():
        if "arbitrary" in data:
            data = data["arbitrary"]

            ret[name] = {}
            ret[name]["samples"] = data["samples"]
            ret[name]["type"] = "arbitrary"
            ret[name]["is_overridable"] = data.get("isOverridable", False)

            max_allowed_error = data.get("maxAllowedError")
            if max_allowed_error is not None:
                ret[name]["max_allowed_error"] = max_allowed_error

            sampling_rate = data.get("samplingRate")
            if sampling_rate is not None:
                ret[name]["sampling_rate"] = sampling_rate

        elif "constant" in data:
            ret[name] = data["constant"]
            if "sample" not in ret[name]:
                ret[name]["sample"] = 0.0
            ret[name]["type"] = "constant"
        elif "compressed" in data:
            ret[name] = {}
            ret[name]["samples"] = data["compressed"]["samples"]
            ret[name]["sample_rate"] = data["compressed"]["sampleRate"]
            ret[name]["type"] = "compressed"

    return ret


def _convert_pulses(pulses):
    if pulses is None:
        return {}

    ret = {}

    for name, data in pulses.items():
        temp_dict = {
            "length": data.get("length"),
        }

        waveforms = data.get("waveforms")
        if waveforms is not None:
            temp_dict["waveforms"] = waveforms

        digital_markers = data.get("digitalMarker")
        if digital_markers is not None:
            temp_dict["digital_marker"] = digital_markers

        integration_weights = data.get("integrationWeights")
        if integration_weights is not None:
            temp_dict["integration_weights"] = integration_weights

        if "operation" in data:
            for item in QuaConfigPulseDecOperation:
                if item.value == data["operation"]:
                    temp_dict["operation"] = item.name.lower()
        else:
            temp_dict["operation"] = "measurement"

        ret[name] = temp_dict
    return ret


def _convert_v1_beta(config: QuaConfigQuaConfigV1) -> DictQuaConfig:
    results = {
        "version": 1,
        "controllers": _convert_controllers(config.get("controllers")),
        "oscillators": _convert_oscillators(config.get("oscillators")),
        "elements": _convert_elements(config.get("elements")),
        "pulses": _convert_pulses(config.get("pulses")),
        "waveforms": _convert_wave_forms(config.get("waveforms")),
        "digital_waveforms": _convert_digital_wave_forms(config.get("digitalWaveforms")),
        "integration_weights": _convert_integration_weights(config.get("integrationWeights")),
        "mixers": _convert_mixers(config.get("mixers")),
    }
    return cast(DictQuaConfig, results)


def _convert_controllers(controllers):
    if controllers is None:
        return {}

    ret = {}
    for name, data in controllers.items():
        ret[name] = {"type": data["type"]}
        if "analogOutputs" in data:
            ret[name]["analog_outputs"] = _convert_controller_analog_outputs(data["analogOutputs"])
        if "analogInputs" in data:
            ret[name]["analog_inputs"] = _convert_controller_analog_inputs(data["analogInputs"])
        if "digitalOutputs" in data:
            ret[name]["digital_outputs"] = _convert_controller_digital_outputs(data["digitalOutputs"])

        if "digitalInputs" in data:
            ret[name]["digital_inputs"] = _convert_controller_digital_inputs(data["digitalInputs"])

    return ret


def _convert_inputs(inputs):
    if inputs is None:
        return {}

    ret = {}
    for name, data in inputs.items():
        ret[name] = {"delay": data.get("delay", 0)}
        ret[name]["buffer"] = data.get("buffer", 0)

        if "output" in data:
            # deprecation from 0.0.28
            ret[name]["output"] = _port_reference(data["output"])
        if "port" in data:
            ret[name]["port"] = _port_reference(data["port"])

    return ret


def _convert_digital_output(outputs):
    if outputs is None:
        return {}

    ret = {}
    for name, data in outputs.items():
        ret[name] = _port_reference(data["port"])

    return ret


def _convert_single_input_collection(data):
    temp = {}
    for input_info in data["inputs"].items():
        temp[input_info[0]] = _port_reference(input_info[1])

    res = {"inputs": temp}
    return res


def _convert_multiple_inputs(data):
    temp = {}
    for input_info in data["inputs"].items():
        temp[input_info[0]] = _port_reference(input_info[1])

    res = {"inputs": temp}
    return res


def _convert_oscillators(oscillator):
    if oscillator is None:
        return {}

    ret = {}
    for name, data in oscillator.items():
        oscillator_config_data = {}
        if "intermediateFrequencyDouble" in data:
            freq = data["intermediateFrequencyDouble"]
            oscillator_config_data["intermediate_frequency"] = freq
        elif "intermediateFrequency" in data:
            freq = int(data["intermediateFrequency"])
            oscillator_config_data["intermediate_frequency"] = freq
        if "mixer" in data:
            if "mixer" in data["mixer"]:
                oscillator_config_data["mixer"] = data["mixer"]["mixer"]
            if "loFrequencyDouble" in data["mixer"]:
                lo_freq = data["mixer"]["loFrequencyDouble"]
                oscillator_config_data["lo_frequency"] = float(lo_freq)
            elif "loFrequency" in data["mixer"]:
                lo_freq = data["mixer"]["loFrequency"]
                oscillator_config_data["lo_frequency"] = float(lo_freq)
        ret[name] = oscillator_config_data
    return ret


def _convert_elements(elements):
    if elements is None:
        return {}

    ret = {}
    for name, data in elements.items():
        element_config_data = {
            "digitalInputs": _convert_inputs(data.get("digitalInputs")),
            "digitalOutputs": _convert_digital_output(data.get("digitalOutputs")),
        }

        if "outputs" in data:
            element_config_data["outputs"] = _convert_element_output(data.get("outputs"))

        if "timeOfFlight" in data:
            element_config_data["time_of_flight"] = int(data["timeOfFlight"])

        if "smearing" in data:
            element_config_data["smearing"] = int(data["smearing"])

        if "namedOscillator" in data:
            element_config_data["oscillator"] = str(data["namedOscillator"])
        else:
            sign = (-1) ** data.get("intermediateFrequencyNegative", False)
            if "intermediateFrequencyDouble" in data:
                freq = float(data["intermediateFrequencyDouble"])
                element_config_data["intermediate_frequency"] = abs(freq) * sign
            elif "intermediateFrequency" in data:
                freq = int(data["intermediateFrequency"])
                element_config_data["intermediate_frequency"] = abs(freq) * sign

        if "operations" in data:
            element_config_data["operations"] = data["operations"]

        if "measurementQe" in data:
            element_config_data["measurement_qe"] = data["measurementQe"]

        if "singleInput" in data:
            element_config_data["singleInput"] = _convert_single_inputs(data["singleInput"])
        elif "mixInputs" in data:
            element_config_data["mixInputs"] = _convert_mix_inputs(data["mixInputs"])
        elif "singleInputCollection" in data:
            element_config_data["singleInputCollection"] = _convert_single_input_collection(
                data["singleInputCollection"]
            )
        elif "multipleInputs" in data:
            element_config_data["multipleInputs"] = _convert_multiple_inputs(data["multipleInputs"])

        if "holdOffset" in data:
            element_config_data["hold_offset"] = _convert_hold_offset(data["holdOffset"])
        if "sticky" in data:
            element_config_data["sticky"] = _convert_sticky(data["sticky"])
        if "thread" in data:
            element_config_data["thread"] = _convert_element_thread(data["thread"])

        ret[name] = element_config_data

    return ret


def _convert_mix_inputs(mix_inputs):
    res = {"I": _port_reference(mix_inputs["i"]), "Q": _port_reference(mix_inputs["q"])}

    mixer = mix_inputs.get("mixer")
    if mixer is not None:
        res["mixer"] = mixer

    if "loFrequencyDouble" in mix_inputs:
        res["lo_frequency"] = float(mix_inputs["loFrequencyDouble"])
    elif "loFrequency" in mix_inputs:
        res["lo_frequency"] = int(mix_inputs["loFrequency"])
    else:
        res["lo_frequency"] = 0.0

    return res


def _convert_single_inputs(single):
    res = {"port": _port_reference(single["port"])}
    return res


def _convert_hold_offset(hold_offset):
    res = {"duration": hold_offset["duration"]}
    return res


def _convert_sticky(sticky):
    res = {
        "analog": sticky.get("analog", True),
        "digital": sticky.get("digital", False),
        "duration": sticky.get("duration", 1) * 4,
    }
    return res


def _convert_element_thread(element_thread):
    return element_thread["threadName"]


def _convert_controller_analog_outputs(outputs):
    if outputs is None:
        return {}

    ret = {}
    for name, data in outputs.items():
        port_info = {"offset": 0.0, "delay": 0, "shareable": False}
        if "offset" in data:
            port_info["offset"] = data["offset"]
        if "filter" in data:
            feedforward = []
            if "feedforward" in data["filter"]:
                feedforward = data["filter"]["feedforward"]

            feedback = []
            if "feedback" in data["filter"]:
                feedback = data["filter"]["feedback"]

            port_info["filter"] = {"feedforward": feedforward, "feedback": feedback}

        if "delay" in data:
            port_info["delay"] = data["delay"]

        if "crosstalk" in data:
            port_info["crosstalk"] = {int(k): v for k, v in data["crosstalk"].items()}
        if "shareable" in data:
            port_info["shareable"] = data["shareable"]

        ret[int(name)] = port_info
    return ret


def _convert_controller_analog_inputs(inputs):
    if inputs is None:
        return {}

    ret = {}
    for name, data in inputs.items():
        port_info = {"offset": 0.0, "gain_db": 0, "shareable": False}
        if "offset" in data:
            port_info["offset"] = data["offset"]

        if "gainDb" in data:
            port_info["gain_db"] = data["gainDb"]

        if "shareable" in data:
            port_info["shareable"] = data["shareable"]

        ret[int(name)] = port_info
    return ret


def _convert_controller_digital_outputs(outputs):
    if outputs is None:
        return {}

    ret = {}
    for name, data in outputs.items():
        port_info = {"shareable": False, "inverted": False}
        if "shareable" in data:
            port_info["shareable"] = data["shareable"]
        if "inverted" in data:
            port_info["inverted"] = data["inverted"]
        ret[int(name)] = port_info
    return ret


def _convert_controller_digital_inputs(inputs):
    if inputs is None:
        return {}

    ret = {}
    for name, data in inputs.items():
        port_info = {"polarity": "RISING", "shareable": False}
        if "polarity" in data:
            port_info["polarity"] = data["polarity"]
        if "deadtime" in data:
            port_info["deadtime"] = data["deadtime"]
        if "threshold" in data:
            port_info["threshold"] = data["threshold"]
        if "shareable" in data:
            port_info["shareable"] = data["shareable"]

        ret[int(name)] = port_info
    return ret


def _convert_element_output(outputs):
    if outputs is None:
        return {}

    ret = {}
    for name, data in outputs.items():
        ret[name] = _port_reference(data)
    return ret


def _port_reference(data):
    return data["controller"], data["number"]
