import logging

from marshmallow import ValidationError

from qm.exceptions import ConfigValidationException

logger = logging.getLogger(__name__)


def validate_timetagging_parameters(data):
    if "outputPulseParameters" in data:
        pulseParameters = data["outputPulseParameters"]
        neededParameters = [
            "signalThreshold",
            "signalPolarity",
            "derivativeThreshold",
            "derivativePolarity",
        ]
        missingParameters = []
        for parameter in neededParameters:
            if parameter not in pulseParameters:
                missingParameters.append(parameter)
        if len(missingParameters) > 0:
            raise ConfigValidationException(
                "An element defining the output pulse parameters must either "
                f"define all of the parameters: {neededParameters}. "
                f"Parameters defined: {pulseParameters}"
            )
        validPolarity = {"ASCENDING", "DESCENDING", "ABOVE", "BELOW"}
        if data["outputPulseParameters"]["signalPolarity"].upper() not in validPolarity:
            raise ConfigValidationException(
                f"'signalPolarity' is {data['outputPulseParameters']['signalPolarity'].upper()} but it must be one of {validPolarity}"
            )
        if data["outputPulseParameters"]["derivativePolarity"].upper() not in validPolarity:
            raise ConfigValidationException(
                f"'derivativePolarity' is {data['outputPulseParameters']['derivativePolarity'].upper()} but it must be one of {validPolarity}"
            )


def _element_has_outputs(data: dict) -> bool:
    return bool(data.get("outputs")) or bool(data.get("RF_outputs"))


def _validate_existence_of_field(data, field_name):
    if _element_has_outputs(data) and field_name not in data:
        raise ValidationError(f"An element with an output must have {field_name} defined")
    if not _element_has_outputs(data) and field_name in data:
        if "outputs" in data:
            logger.warning(
                f"The field `{field_name}` exists though the element has no outputs (empty dict). "
                f"This behavior is going to cause `ValidationError` in the future."
            )
            return
        raise ValidationError(f"{field_name} should be used only with elements that have outputs")


def validate_output_tof(data):
    _validate_existence_of_field(data, "time_of_flight")


def validate_output_smearing(data):
    _validate_existence_of_field(data, "smearing")


def validate_oscillator(data):
    if "intermediate_frequency" in data and "oscillator" in data:
        raise ValidationError("'intermediate_frequency' and 'oscillator' cannot be defined together")


def validate_used_inputs(data):
    used_inputs = list(
        filter(
            lambda it: it in data,
            ["singleInput", "mixInputs", "singleInputCollection", "multipleInputs"],
        )
    )
    if len(used_inputs) > 1:
        raise ValidationError(
            f"Can't support more than a single input type. " f"Used {', '.join(used_inputs)}",
            field_name="",
        )


def validate_sticky_duration(duration):
    if (duration % 4) != 0:
        raise ValidationError(
            "Sticky's element duration must be a dividable by 4",
            field_name="duration",
        )


def validate_arbitrary_waveform(is_overridable, has_max_allowed_error, has_sampling_rate):
    if is_overridable and has_max_allowed_error:
        raise ValidationError("Overridable waveforms cannot have property 'max_allowed_error'")
    if is_overridable and has_sampling_rate:
        raise ValidationError("Overridable waveforms cannot have property 'sampling_rate_key'")
    if has_max_allowed_error and has_sampling_rate:
        raise ValidationError("Cannot use both 'max_allowed_error' and 'sampling_rate'")
