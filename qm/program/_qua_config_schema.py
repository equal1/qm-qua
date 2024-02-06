import logging
from typing import Any, Dict, List, Mapping

import betterproto
import numpy as np
from marshmallow_polyfield import PolyField
from betterproto.lib.google.protobuf import Empty
from dependency_injector.wiring import Provide, inject
from marshmallow import Schema, ValidationError, fields, validate, post_load, validates_schema

from qm.grpc import qua_config
from qm.type_hinting.config_types import DictQuaConfig
from qm.api.models.capabilities import ServerCapabilities
from qm.containers.capabilities_container import CapabilitiesContainer
from qm.exceptions import InvalidOctaveParameter, ConfigValidationException, OctaveConnectionAmbiguity
from qm.program._validate_config_schema import (
    validate_oscillator,
    validate_output_tof,
    validate_used_inputs,
    validate_output_smearing,
    validate_sticky_duration,
    validate_arbitrary_waveform,
    validate_timetagging_parameters,
)
from qm.grpc.qua_config import (
    QuaConfig,
    QuaConfigOctaveConfig,
    QuaConfigAdcPortReference,
    QuaConfigOctaveLoSourceInput,
    QuaConfigOctaveRfInputConfig,
    QuaConfigGeneralPortReference,
    QuaConfigOctaveRfOutputConfig,
    QuaConfigOctaveIfOutputsConfig,
    QuaConfigAnalogOutputPortFilter,
    QuaConfigOctaveSingleIfOutputConfig,
    QuaConfigOctaveDownconverterRfSource,
)
from qm.program._qua_config_to_pb import (
    IF_OUT1_DEFAULT,
    IF_OUT2_DEFAULT,
    rf_input_to_pb,
    rf_module_to_pb,
    dac_port_ref_to_pb,
    get_octave_loopbacks,
    single_if_output_to_pb,
    validate_inputs_or_outputs_exist,
    set_non_existing_mixers_in_mix_input_elements,
    set_octave_upconverter_connection_to_elements,
    set_octave_downconverter_connection_to_elements,
    set_lo_frequency_to_mix_input_elements_that_are_connected_to_octave,
)

logger = logging.getLogger(__name__)


def validate_config_capabilities(pb_config, server_capabilities: ServerCapabilities):
    if not server_capabilities.supports_inverted_digital_output:
        for con_name, con in pb_config.v1_beta.controllers.items():
            for port_id, port in con.digital_outputs.items():
                if port.inverted:
                    raise ConfigValidationException(
                        f"Server does not support inverted digital output used in controller "
                        f"'{con_name}', port {port_id}"
                    )
    if not server_capabilities.supports_multiple_inputs_for_element:
        for el_name, el in pb_config.v1_beta.elements.items():
            if el is not None and el.multiple_inputs:
                raise ConfigValidationException(
                    f"Server does not support multiple inputs for elements used in '{el_name}'"
                )

    if not server_capabilities.supports_analog_delay:
        for con_name, con in pb_config.v1_beta.controllers.items():
            for port_id, port in con.analog_outputs.items():
                if port.delay != 0:
                    raise ConfigValidationException(
                        f"Server does not support analog delay used in controller " f"'{con_name}', port {port_id}"
                    )

    if not server_capabilities.supports_shared_oscillators:
        for el_name, el in pb_config.v1_beta.elements.items():
            if el is not None and el.named_oscillator:
                raise ConfigValidationException(
                    f"Server does not support shared oscillators for elements used in " f"'{el_name}'"
                )

    if not server_capabilities.supports_crosstalk:
        for con_name, con in pb_config.v1_beta.controllers.items():
            for port_id, port in con.analog_outputs.items():
                if len(port.crosstalk) > 0:
                    raise ConfigValidationException(
                        f"Server does not support channel weights used in controller " f"'{con_name}', port {port_id}"
                    )

    if not server_capabilities.supports_shared_ports:
        shared_ports_by_controller = {}
        for con_name, con in pb_config.v1_beta.controllers.items():
            shared_ports_by_type = {}
            analog_outputs = [port_id for port_id, port in con.analog_outputs.items() if port.shareable]
            analog_inputs = [port_id for port_id, port in con.analog_inputs.items() if port.shareable]
            digital_outputs = [port_id for port_id, port in con.digital_outputs.items() if port.shareable]
            digital_inputs = [port_id for port_id, port in con.digital_inputs.items() if port.shareable]
            if len(analog_outputs):
                shared_ports_by_type["analog_outputs"] = analog_outputs
            if len(analog_inputs):
                shared_ports_by_type["analog_inputs"] = analog_inputs
            if len(digital_outputs):
                shared_ports_by_type["digital_outputs"] = digital_outputs
            if len(digital_inputs):
                shared_ports_by_type["digital_inputs"] = digital_inputs
            if len(shared_ports_by_type):
                shared_ports_by_controller[con_name] = shared_ports_by_type
        if len(shared_ports_by_controller) > 0:
            error_message = "Server does not support shareable ports." + "\n".join(
                [
                    f"Controller: {con_name}\n{shared_ports_list}"
                    for con_name, shared_ports_list in shared_ports_by_controller.items()
                ]
            )
            raise ConfigValidationException(error_message)
    if not server_capabilities.supports_double_frequency:
        message_template = (
            "Server does not support float frequency. "
            "Element: {element_name}: {frequency_type}={float_value} "
            "will be casted to {int_value}."
        )
        for el_name, el in list(pb_config.v1_beta.elements.items()):
            if el.intermediate_frequency_double and el.intermediate_frequency_double != el.intermediate_frequency:
                logger.warning(
                    message_template.format(
                        element_name=el_name,
                        frequency_type="intermediate_frequency",
                        float_value=el.intermediate_frequency_double,
                        int_value=el.intermediate_frequency,
                    )
                )
            if (
                betterproto.serialized_on_wire(el.mix_inputs)
                and el.mix_inputs.lo_frequency_double
                and el.mix_inputs.lo_frequency != el.mix_inputs.lo_frequency_double
            ):
                logger.warning(
                    message_template.format(
                        element_name=el_name,
                        frequency_type="lo_frequency",
                        float_value=el.mix_inputs.lo_frequency_double,
                        int_value=el.mix_inputs.lo_frequency,
                    )
                )


def load_config(config: DictQuaConfig) -> QuaConfig:
    return QuaConfigSchema().load(config)


PortReferenceSchema = fields.Tuple(
    (fields.String(), fields.Int()),
    metadata={"description": "Controller port to use. Tuple of: ([str] controller name, [int] controller port)"},
)


class UnionField(fields.Field):
    """Field that deserializes multi-type input data to app-level objects."""

    def __init__(self, val_types: List[fields.Field], **kwargs):
        self.valid_types = val_types
        super().__init__(**kwargs)

    def _deserialize(self, value: Any, attr: str = None, data: Mapping[str, Any] = None, **kwargs):
        """
        _deserialize defines a custom Marshmallow Schema Field that takes in
        mutli-type input data to app-level objects.

        Parameters
        ----------
        value : {Any}
            The value to be deserialized.

        Keyword Parameters
        ----------
        attr : {str} [Optional]
            The attribute/key in data to be deserialized. (default: {None})
        data : {Optional[Mapping[str, Any]]}
            The raw input data passed to the Schema.load. (default: {None})

        Raises
        ----------
        ValidationError : Exception
            Raised when the validation fails on a field or schema.
        """
        errors = []
        # iterate through the types being passed into UnionField via val_types
        for field in self.valid_types:
            try:
                # inherit deserialize method from Fields class
                return field.deserialize(value, attr, data, **kwargs)
            # if error, add error message to error list
            except ValidationError as error:
                errors.append(error.messages)

        raise ValidationError(errors)


class AnalogOutputFilterDefSchema(Schema):
    feedforward = fields.List(
        fields.Float(),
        metadata={"description": "Feedforward taps for the analog output filter, range: [-1,1]. List of double"},
    )
    feedback = fields.List(
        fields.Float(),
        metadata={"description": "Feedback taps for the analog output filter, range: (-1,1). List of double"},
    )


class AnalogOutputPortDefSchema(Schema):
    offset = fields.Number(
        metadata={
            "description": "DC offset to the output, range: (-0.5, 0.5). "
            "Will be applied while quantum machine is open."
        }
    )
    filter = fields.Nested(AnalogOutputFilterDefSchema)
    delay = fields.Int(metadata={"description": "Output's delay, in units of ns."})
    crosstalk = fields.Dict(
        keys=fields.Int(), values=fields.Number(), metadata={"description": ""}
    )  # TODO: add description
    shareable = fields.Bool(
        dump_default=False,
        metadata={"description": "Whether the port is shareable with other QM instances"},
    )

    class Meta:
        title = "Analog output port"
        description = "The specifications and properties of an analog output port of the controller."

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        item = qua_config.QuaConfigAnalogOutputPortDec(
            offset=data["offset"],
            shareable=data.get("shareable", False),
        )

        if "delay" in data:
            delay = data.get("delay", 0)
            if delay < 0:
                raise ConfigValidationException(f"analog output delay cannot be a negative value, given value: {delay}")
            item.delay = delay

        if "filter" in data:
            filters = data["filter"]
            item.filter = QuaConfigAnalogOutputPortFilter(
                feedforward=filters.get("feedforward", []),
                feedback=filters.get("feedback", []),
            )

        if "crosstalk" in data:
            for k, v in data["crosstalk"].items():
                item.crosstalk[k] = v

        return item


class AnalogInputPortDefSchema(Schema):
    offset = fields.Number(
        metadata={"description": "DC offset to the input, range: (-0.5, 0.5). Will be applied only when program runs."}
    )

    gain_db = fields.Int(
        strict=True,
        metadata={"description": "Gain of the pre-ADC amplifier, in dB. Accepts integers in the range: -12 to 20"},
    )

    shareable = fields.Bool(
        dump_default=False,
        metadata={"description": "Whether the port is shareable with other QM instances"},
    )

    class Meta:
        title = "Analog input port"
        description = "The specifications and properties of an analog input port of the controller."

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        item = qua_config.QuaConfigAnalogInputPortDec(
            offset=data.get("offset", 0.0),
            gain_db=data.get("gain_db"),
            shareable=data.get("shareable", False),
        )

        return item


class DigitalOutputPortDefSchema(Schema):
    shareable = fields.Bool(
        dump_default=False,
        metadata={"description": "Whether the port is shareable with other QM instances"},
    )
    inverted = fields.Bool(
        dump_default=False,
        metadata={"description": "Whether the port is inverted. " "If True, the output will be inverted."},
    )

    class Meta:
        title = "Digital port"
        description = "The specifications and properties of a digital output port of the controller."

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        item = qua_config.QuaConfigDigitalOutputPortDec(
            shareable=data.get("shareable", False), inverted=data.get("inverted", False)
        )
        return item


class DigitalInputPortDefSchema(Schema):
    deadtime = fields.Int(metadata={"description": "The minimal time between pulses, in ns."})
    polarity = fields.String(
        metadata={"description": "The Detection edge - Whether to trigger in the rising or falling edge of the pulse"},
        validate=validate.OneOf(["RISING", "FALLING"]),
    )
    threshold = fields.Number(metadata={"description": "The minimum voltage to trigger when a pulse arrives"})
    shareable = fields.Bool(
        dump_default=False,
        metadata={"description": "Whether the port is shareable with other QM instances"},
    )

    class Meta:
        title = "Digital input port"
        description = "The specifications and properties of a digital input " "port of the controller."

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        item = qua_config.QuaConfigDigitalInputPortDec()
        item.deadtime = data["deadtime"]
        if data["polarity"].upper() == "RISING":
            item.polarity = qua_config.QuaConfigDigitalInputPortDecPolarity.RISING
        elif data["polarity"].upper() == "FALLING":
            item.polarity = qua_config.QuaConfigDigitalInputPortDecPolarity.FALLING

        item.threshold = data["threshold"]
        if "shareable" in data:
            item.shareable = data["shareable"]
        return item


class OctaveRFOutputSchema(Schema):
    LO_frequency = fields.Number(metadata={"description": "The frequency of the LO in Hz"})
    LO_source = fields.String(metadata={"description": "The source of the LO}, e.g. 'internal' or 'external'"})
    output_mode = fields.String(metadata={"description": "The output mode of the RF output"})
    gain = fields.Number(metadata={"description": "The gain of the RF output in dB"})
    input_attenuators = fields.String(metadata={"description": "The attenuators of the I and Q inputs"})
    I_connection = fields.Tuple([fields.String(), fields.Int()])
    Q_connection = fields.Tuple([fields.String(), fields.Int()])

    @post_load(pass_many=False)
    def build(self, data, **kwargs) -> QuaConfigOctaveRfOutputConfig:
        return rf_module_to_pb(data)


class OctaveRFInputSchema(Schema):
    RF_source = fields.String()
    LO_frequency = fields.Number()
    LO_source = fields.String()
    IF_mode_I = fields.String()
    IF_mode_Q = fields.String()

    @post_load(pass_many=False)
    def build(self, data, **kwargs) -> QuaConfigOctaveRfInputConfig:
        return rf_input_to_pb(data)


class SingleIFOutputSchema(Schema):
    port = fields.Tuple([fields.String(), fields.Int()])
    name = fields.String()

    @post_load(pass_many=False)
    def build(self, data, **kwargs) -> QuaConfigOctaveSingleIfOutputConfig:
        return single_if_output_to_pb(data)


class IFOutputsSchema(Schema):
    IF_out1 = fields.Nested(SingleIFOutputSchema)
    IF_out2 = fields.Nested(SingleIFOutputSchema)

    @post_load(pass_many=False)
    def build(self, data, **kwargs) -> QuaConfigOctaveIfOutputsConfig:
        to_return = QuaConfigOctaveIfOutputsConfig()
        if "IF_out1" in data:
            to_return.if_out1 = data["IF_out1"]
        if "IF_out2" in data:
            to_return.if_out2 = data["IF_out2"]
        return to_return


class OctaveSchema(Schema):
    loopbacks = fields.List(
        fields.Tuple([fields.Tuple([fields.String, fields.String]), fields.String]),
        metadata={
            "description": "List of loopbacks that connected to this octave, Each loopback is "
            "in the form of ((octave_name, octave_port), target_port)"
        },
    )
    RF_outputs = fields.Dict(
        keys=fields.Int(),
        values=fields.Nested(OctaveRFOutputSchema),
        metadata={"description": "The RF outputs and their properties."},
    )
    RF_inputs = fields.Dict(
        keys=fields.Int(),
        values=fields.Nested(OctaveRFInputSchema),
        metadata={"description": "The RF inputs and their properties."},
    )
    IF_outputs = fields.Nested(IFOutputsSchema)
    connectivity = fields.String(
        metadata={"description": "Sets the default connectivity for all RF outputs and inputs in the octave."}
    )

    @post_load(pass_many=False)
    def build(self, data, **kwargs) -> QuaConfigOctaveConfig:
        to_return = QuaConfigOctaveConfig(
            loopbacks=get_octave_loopbacks(data.get("loopbacks", [])),
            rf_outputs=data.get("RF_outputs", {}),
            rf_inputs=data.get("RF_inputs", {}),
        )
        for input_idx, input_config in to_return.rf_inputs.items():
            if input_config.lo_source == QuaConfigOctaveLoSourceInput.not_set:
                input_config.lo_source = (
                    QuaConfigOctaveLoSourceInput.internal if input_idx == 1 else QuaConfigOctaveLoSourceInput.external
                )
            if input_idx == 1 and input_config.rf_source != QuaConfigOctaveDownconverterRfSource.rf_in:
                raise InvalidOctaveParameter("Downconverter 1 must be connected to RF-in")

        if "IF_outputs" in data:
            to_return.if_outputs = data["IF_outputs"]

        if "connectivity" in data:
            controller_name = data["connectivity"]
            for upconverter_idx, upconverter in to_return.rf_outputs.items():
                if betterproto.serialized_on_wire(upconverter.i_connection) or betterproto.serialized_on_wire(
                    upconverter.q_connection
                ):
                    raise OctaveConnectionAmbiguity
                upconverter.i_connection = dac_port_ref_to_pb(controller_name, 2 * upconverter_idx - 1)
                upconverter.q_connection = dac_port_ref_to_pb(controller_name, 2 * upconverter_idx)

            if betterproto.serialized_on_wire(to_return.if_outputs):
                raise OctaveConnectionAmbiguity
            to_return.if_outputs.if_out1 = QuaConfigOctaveSingleIfOutputConfig(
                port=QuaConfigAdcPortReference(controller_name, 1), name=IF_OUT1_DEFAULT
            )
            to_return.if_outputs.if_out2 = QuaConfigOctaveSingleIfOutputConfig(
                port=QuaConfigAdcPortReference(controller_name, 2), name=IF_OUT2_DEFAULT
            )
        return to_return


class ControllerSchema(Schema):
    type = fields.Constant("opx1")

    analog_outputs = fields.Dict(
        fields.Int(),
        fields.Nested(AnalogOutputPortDefSchema),
        metadata={"description": "The analog output ports and their properties."},
    )
    analog_inputs = fields.Dict(
        fields.Int(),
        fields.Nested(AnalogInputPortDefSchema),
        metadata={"description": "The analog input ports and their properties."},
    )
    digital_outputs = fields.Dict(
        fields.Int(),
        fields.Nested(DigitalOutputPortDefSchema),
        metadata={"description": "The digital output ports and their properties."},
    )
    digital_inputs = fields.Dict(
        fields.Int(),
        fields.Nested(DigitalInputPortDefSchema),
        metadata={"description": "The digital inputs ports and their properties."},
    )

    class Meta:
        title = "controller"
        description = "The specification of a single controller and its properties."

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        item = qua_config.QuaConfigControllerDec()
        item.type = data["type"]

        if "analog_outputs" in data:
            for k, v in data["analog_outputs"].items():
                item.analog_outputs[k] = v

        if "analog_inputs" in data:
            for k, v in data["analog_inputs"].items():
                item.analog_inputs[k] = v

        if "digital_outputs" in data:
            for k, v in data["digital_outputs"].items():
                item.digital_outputs[k] = v

        if "digital_inputs" in data:
            for k, v in data["digital_inputs"].items():
                item.digital_inputs[k] = v

        return item


class DigitalInputSchema(Schema):
    delay = fields.Int(
        metadata={
            "description": "The delay to apply to the digital pulses. In ns. "
            "An intrinsic negative delay of 136 ns exists by default"
        }
    )
    buffer = fields.Int(
        metadata={
            "description": "Digital pulses played to this element will be convolved with a digital "
            "pulse of value 1 with this length [ns]"
        }
    )
    port = PortReferenceSchema

    class Meta:
        title = "Digital input"
        description = "The specification of the digital input of an element"

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        item = qua_config.QuaConfigDigitalInputPortReference()
        item.delay = data["delay"]
        item.buffer = data["buffer"]
        if "port" in data:
            item.port.controller = data["port"][0]
            item.port.number = data["port"][1]
        return item


class IntegrationWeightSchema(Schema):
    cosine = UnionField(
        [
            fields.List(fields.Tuple([fields.Float(), fields.Int()])),
            fields.List(fields.Float()),
        ],
        metadata={
            "description": "The integration weights for the cosine. Given as a list of tuples, "
            "each tuple in the format of: ([double] weight, [int] duration). "
            "weight range: [-2048, 2048] in steps of 2**-15. duration is in ns "
            "and must be a multiple of 4."
        },
    )
    sine = UnionField(
        [
            fields.List(fields.Tuple([fields.Float(), fields.Int()])),
            fields.List(fields.Float()),
        ],
        metadata={
            "description": "The integration weights for the sine. Given as a list of tuples, "
            "each tuple in the format of: ([double] weight, [int] duration). "
            "weight range: [-2048, 2048] in steps of 2**-15. duration is in ns "
            "and must be a multiple of 4."
        },
    )

    class Meta:
        title = "Integration weights"
        description = "The specification of measurements' integration weights."

    @staticmethod
    def build_iw_sample(data):
        if len(data) > 0 and not isinstance(data[0], tuple):
            data = np.round(2**-15 * np.round(np.array(data) / 2**-15), 20)
            new_data = []
            for s in data:
                if len(new_data) == 0 or new_data[-1][0] != s:
                    new_data.append((s, 4))
                else:
                    new_data[-1] = (new_data[-1][0], new_data[-1][1] + 4)
            data = new_data
        res = []
        for s in data:
            sample = qua_config.QuaConfigIntegrationWeightSample(value=s[0], length=s[1])
            res.append(sample)
        return res

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        item = qua_config.QuaConfigIntegrationWeightDec()
        if "cosine" in data:
            item.cosine.extend(self.build_iw_sample(data["cosine"]))
        if "sine" in data:
            item.sine.extend(self.build_iw_sample(data["sine"]))
        return item


class WaveFormSchema(Schema):
    pass


class ConstantWaveFormSchema(WaveFormSchema):
    type = fields.String(metadata={"description": '"constant"'})
    sample = fields.Float(metadata={"description": "Waveform amplitude, range: (-0.5, 0.5)"})

    class Meta:
        title = "Constant waveform"
        description = "A waveform with a constant amplitude"

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        item = qua_config.QuaConfigWaveformDec(constant=qua_config.QuaConfigConstantWaveformDec(sample=data["sample"]))
        return item


class ArbitraryWaveFormSchema(WaveFormSchema):
    type = fields.String(metadata={"description": '"arbitrary"'})
    samples = fields.List(
        fields.Float(),
        metadata={"description": "list of values of an arbitrary waveforms, range: (-0.5, 0.5)"},
    )
    max_allowed_error = fields.Float(metadata={"description": '"Maximum allowed error for automatic compression"'})
    sampling_rate = fields.Number(
        metadata={
            "description": "Sampling rate to use in units of S/s (samples per second). "
            "Default is 1e9. Cannot be set when is_overridable=True"
        }
    )
    is_overridable = fields.Bool(
        dump_default=False,
        metadata={
            "description": "Allows overriding the waveform after compilation. "
            "Cannot use with the non-default sampling_rate"
        },
    )

    class Meta:
        title = "arbitrary waveform"
        description = "The modulating envelope of an arbitrary waveform"

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        is_overridable = data.get("is_overridable", False)
        item = qua_config.QuaConfigWaveformDec(
            arbitrary=qua_config.QuaConfigArbitraryWaveformDec(samples=data["samples"], is_overridable=is_overridable)
        )
        max_allowed_error_key = "max_allowed_error"
        sampling_rate_key = "sampling_rate"
        has_max_allowed_error = max_allowed_error_key in data
        has_sampling_rate = sampling_rate_key in data
        validate_arbitrary_waveform(is_overridable, has_max_allowed_error, has_sampling_rate)
        if has_max_allowed_error:
            item.arbitrary.max_allowed_error = data[max_allowed_error_key]
        elif has_sampling_rate:
            item.arbitrary.sampling_rate = data[sampling_rate_key]
        elif not is_overridable:
            item.arbitrary.max_allowed_error = 1e-4
        return item


def _waveform_schema_deserialization_disambiguation(object_dict, data):
    type_to_schema = {
        "constant": ConstantWaveFormSchema,
        "arbitrary": ArbitraryWaveFormSchema,
    }
    try:
        return type_to_schema[object_dict["type"]]()
    except KeyError:
        pass

    raise TypeError("Could not detect type. Did not have a base or a length. Are you sure this is a shape?")


_waveform_poly_field = PolyField(
    deserialization_schema_selector=_waveform_schema_deserialization_disambiguation,
    required=True,
)


class DigitalWaveFormSchema(Schema):
    samples = fields.List(
        fields.Tuple([fields.Int(), fields.Int()]),
        metadata={
            "description": "The digital waveform. Given as a list of tuples, each tuple in the format of: "
            "([int] state, [int] duration). state is either 0 or 1 indicating whether the "
            "digital output is off or on. duration is in ns. If the duration is 0, "
            "it will be played until the reminder of the analog pulse"
        },
    )

    class Meta:
        title = "Digital waveform"
        description = "The samples of a digital waveform"

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        item = qua_config.QuaConfigDigitalWaveformDec()
        for sample in data["samples"]:
            item.samples.append(qua_config.QuaConfigDigitalWaveformSample(value=bool(sample[0]), length=int(sample[1])))
        return item


class MixerSchema(Schema):
    intermediate_frequency = fields.Float(
        metadata={"description": "The intermediate frequency associated with the correction matrix"}
    )
    lo_frequency = fields.Float(metadata={"description": "The LO frequency associated with the correction matrix"})
    correction = fields.Tuple(
        (fields.Number(), fields.Number(), fields.Number(), fields.Number()),
        metadata={
            "description": "A 2x2 matrix entered as a 4 elements list specifying the "
            "correction matrix. Each element is a double in the range of (-2,2)"
        },
    )

    class Meta:
        title = "Mixer"
        description = (
            "The specification of the correction matrix for an IQ mixer. "
            "This is a list of correction matrices for each LO and IF frequencies."
        )

    @post_load(pass_many=False)
    @inject
    def build(
        self,
        data,
        capabilities: ServerCapabilities = Provide[CapabilitiesContainer.capabilities],
        **kwargs,
    ):
        item = qua_config.QuaConfigCorrectionEntry(correction=qua_config.QuaConfigMatrix(*data["correction"]))

        if "lo_frequency" in data:
            item.lo_frequency = int(data["lo_frequency"])  # backwards compatibility
            if capabilities.supports_double_frequency:
                item.lo_frequency_double = float(data["lo_frequency"])

        if "intermediate_frequency" in data:
            item.frequency = abs(int(data["intermediate_frequency"]))  # backwards compatibility
            if capabilities.supports_double_frequency:
                item.frequency_double = abs(float(data["intermediate_frequency"]))

            item.frequency_negative = data["intermediate_frequency"] < 0

        item.correction = qua_config.QuaConfigMatrix(
            data["correction"][0],
            data["correction"][1],
            data["correction"][2],
            data["correction"][3],
        )
        return item


class PulseSchema(Schema):
    operation = fields.String(
        metadata={"description": "The type of operation. Possible values: 'control', 'measurement'"}
    )
    length = fields.Int(
        metadata={"description": "The length of pulse [ns]. Possible values: 16 to 2^31-1 in steps of 4"}
    )
    waveforms = fields.Dict(
        fields.String(),
        fields.String(metadata={"description": "The name of analog waveform to be played."}),
        metadata={
            "description": "The specification of the analog waveform to be played. "
            "If the associated element has a single input, then the key is 'single'. "
            "If the associated element has 'mixInputs', then the keys are 'I' and 'Q'."
        },
    )
    digital_marker = fields.String(
        metadata={"description": "The name of the digital waveform to be played with this pulse."}
    )
    integration_weights = fields.Dict(
        fields.String(),
        fields.String(
            metadata={
                "description": "The name of the integration weights as it appears under the"
                ' "integration_weigths" entry in the configuration dict.'
            }
        ),
        metadata={"description": "The name of the integration weight to be used in the program."},
    )

    class Meta:
        title = "pulse"
        description = "The specification and properties of a single pulse and to the measurement associated with it."

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        item = qua_config.QuaConfigPulseDec()
        item.length = data["length"]
        if data["operation"] == "measurement":
            item.operation = qua_config.QuaConfigPulseDecOperation.MEASUREMENT
        elif data["operation"] == "control":
            item.operation = qua_config.QuaConfigPulseDecOperation.CONTROL
        if "integration_weights" in data:
            for k, v in data["integration_weights"].items():
                item.integration_weights[k] = v
        if "waveforms" in data:
            for k, v in data["waveforms"].items():
                item.waveforms[k] = v
        if "digital_marker" in data:
            item.digital_marker = data["digital_marker"]
        return item


class SingleInputSchema(Schema):
    port = PortReferenceSchema

    class Meta:
        title = "Single input"
        description = "The specification of the input of an element which has a single input port"

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        controller, number = data["port"]
        item = qua_config.QuaConfigSingleInput(
            port=qua_config.QuaConfigDacPortReference(controller=controller, number=number)
        )
        return item


class HoldOffsetSchema(Schema):
    duration = fields.Int(metadata={"description": """The ramp to zero duration, in ns"""})

    class Meta:
        title = "Hold offset"
        description = "When defined, makes the element sticky"

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        item = qua_config.QuaConfigHoldOffset()
        item.duration = data["duration"]
        return item


class StickySchema(Schema):
    analog = fields.Boolean(metadata={"description": """the analog flag must be a True of False"""})
    digital = fields.Boolean(metadata={"description": """the digital flag must be a True of False"""})
    duration = fields.Int(metadata={"description": """The ramp to zero duration, in ns"""})

    class Meta:
        title = "Sticky"
        description = "When defined, makes the element sticky"

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        item = qua_config.QuaConfigSticky()
        item.duration = data.get("duration", 4)
        item.analog = data.get("analog")
        if "digital" in data:
            item.digital = data.get("digital")
        return item


class MixInputSchema(Schema):
    I = PortReferenceSchema
    Q = PortReferenceSchema
    mixer = fields.String(
        metadata={
            "description": "The mixer used to drive the input of the element, "
            "taken from the names in mixers entry in the main configuration."
        }
    )
    lo_frequency = fields.Float(
        metadata={"description": "The frequency of the local oscillator which drives the mixer."}
    )

    class Meta:
        title = "Mixer input"
        description = "The specification of the input of an element which is driven by an IQ mixer"

    @post_load(pass_many=False)
    @inject
    def build(
        self,
        data,
        capabilities: ServerCapabilities = Provide[CapabilitiesContainer.capabilities],
        **kwargs,
    ):
        lo_frequency = data.get("lo_frequency", 0)

        item = qua_config.QuaConfigMixInputs(
            i=qua_config.QuaConfigDacPortReference(controller=data["I"][0], number=data["I"][1]),
            q=qua_config.QuaConfigDacPortReference(controller=data["Q"][0], number=data["Q"][1]),
            mixer=data.get("mixer", ""),
            lo_frequency=int(lo_frequency),
        )
        if capabilities.supports_double_frequency:
            item.lo_frequency_double = float(lo_frequency)
        return item


class SingleInputCollectionSchema(Schema):
    inputs = fields.Dict(
        keys=fields.String(),
        values=PortReferenceSchema,
        metadata={"description": "A collection of multiple single inputs to the port"},
    )

    class Meta:
        title = "Single input collection"
        description = "Defines a set of single inputs which can be switched during play statements"

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        item = qua_config.QuaConfigSingleInputCollection()
        for name, (controller, number) in data["inputs"].items():
            item.inputs[name] = qua_config.QuaConfigDacPortReference(controller=controller, number=number)
        return item


class MultipleInputsSchema(Schema):
    inputs = fields.Dict(
        keys=fields.String(),
        values=PortReferenceSchema,
        metadata={"description": "A collection of multiple single inputs to the port"},
    )

    class Meta:
        title = "Multiple inputs"
        description = "Defines a set of single inputs which are all played at once"

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        item = qua_config.QuaConfigMultipleInputs()
        for name, (controller, number) in data["inputs"].items():
            item.inputs[name] = qua_config.QuaConfigDacPortReference(controller=controller, number=number)
        return item


class OscillatorSchema(Schema):
    intermediate_frequency = fields.Float(
        metadata={"description": "The frequency of this oscillator [Hz]."},
        allow_none=True,
    )
    mixer = fields.String(
        metadata={
            "description": "The mixer used to drive the input of the oscillator, "
            "taken from the names in mixers entry in the main configuration"
        }
    )
    lo_frequency = fields.Float(
        metadata={"description": "The frequency of the local oscillator which drives the mixer [Hz]."}
    )

    @post_load(pass_many=False)
    @inject
    def build(
        self,
        data,
        capabilities: ServerCapabilities = Provide[CapabilitiesContainer.capabilities],
        **kwargs,
    ):
        osc = qua_config.QuaConfigOscillator()
        if "intermediate_frequency" in data and data["intermediate_frequency"] is not None:
            osc.intermediate_frequency = int(data["intermediate_frequency"])
            if capabilities.supports_double_frequency:
                osc.intermediate_frequency_double = float(data["intermediate_frequency"])

        if "mixer" in data and data["mixer"] is not None:
            osc.mixer.mixer = data["mixer"]
            osc.mixer.lo_frequency = int(data.get("lo_frequency", 0))
            if capabilities.supports_double_frequency:
                osc.mixer.lo_frequency_double = float(data.get("lo_frequency", 0.0))

        return osc


class ElementSchema(Schema):
    intermediate_frequency = fields.Float(
        metadata={"description": "The frequency at which the controller modulates the output to this element [Hz]."},
        allow_none=True,
    )
    oscillator = fields.String(
        metadata={
            "description": "The oscillator which is used by the controller to modulates the "
            "output to this element [Hz]. Can be used to share oscillators between elements"
        },
        allow_none=True,
    )

    measurement_qe = fields.String(metadata={"description": "not implemented"})
    operations = fields.Dict(
        keys=fields.String(),
        values=fields.String(
            metadata={
                "description": 'The name of the pulse as it appears under the "pulses" entry in the configuration dict'
            }
        ),
        metadata={"description": "A collection of all pulse names to be used in play and measure commands"},
    )
    singleInput = fields.Nested(SingleInputSchema)
    mixInputs = fields.Nested(MixInputSchema)
    singleInputCollection = fields.Nested(SingleInputCollectionSchema)
    multipleInputs = fields.Nested(MultipleInputsSchema)
    time_of_flight = fields.Int(
        metadata={
            "description": """The delay time, in ns, from the start of pulse until it reaches 
            the controller. Needs to be calibrated by looking at the raw ADC data. 
            Needs to be a multiple of 4 and the minimal value is 24. """
        }
    )
    smearing = fields.Int(
        metadata={
            "description": """Padding time, in ns, to add to both the start and end of the raw 
            ADC data window during a measure command."""
        }
    )
    outputs = fields.Dict(
        keys=fields.String(),
        values=PortReferenceSchema,
        metadata={"description": "The output ports of the element."},
    )
    digitalInputs = fields.Dict(keys=fields.String(), values=fields.Nested(DigitalInputSchema))
    digitalOutputs = fields.Dict(keys=fields.String(), values=PortReferenceSchema)
    outputPulseParameters = fields.Dict(metadata={"description": "Pulse parameters for Time-Tagging"})

    hold_offset = fields.Nested(HoldOffsetSchema)

    sticky = fields.Nested(StickySchema)

    thread = fields.String(metadata={"description": "QE thread"})
    RF_inputs = fields.Dict(keys=fields.String, values=PortReferenceSchema)
    RF_outputs = fields.Dict(keys=fields.String, values=PortReferenceSchema)

    class Meta:
        title = "Element"
        description = "The specifications, parameters and connections of a single element."

    @post_load(pass_many=False)
    @inject
    def build(
        self,
        data,
        capabilities: ServerCapabilities = Provide[CapabilitiesContainer.capabilities],
        **kwargs,
    ):
        el = qua_config.QuaConfigElementDec()
        if "intermediate_frequency" in data and data["intermediate_frequency"] is not None:
            el.intermediate_frequency = abs(int(data["intermediate_frequency"]))
            el.intermediate_frequency_oscillator = int(data["intermediate_frequency"])
            if capabilities.supports_double_frequency:
                el.intermediate_frequency_double = float(abs(data["intermediate_frequency"]))
                el.intermediate_frequency_oscillator_double = float(data["intermediate_frequency"])

            el.intermediate_frequency_negative = data["intermediate_frequency"] < 0
        elif "oscillator" in data and data["oscillator"] is not None:
            el.named_oscillator = data["oscillator"]
        else:
            el.no_oscillator = Empty()

        # validate we have only 1 set of input defined
        validate_used_inputs(data)

        if "singleInput" in data:
            el.single_input = data["singleInput"]
        if "mixInputs" in data:
            el.mix_inputs = data["mixInputs"]
        if "singleInputCollection" in data:
            el.single_input_collection = data["singleInputCollection"]
        if "multipleInputs" in data:
            el.multiple_inputs = data["multipleInputs"]
        if "measurement_qe" in data:
            el.measurement_qe = data["measurement_qe"]
        if "time_of_flight" in data:
            el.time_of_flight = data["time_of_flight"]
        if "smearing" in data:
            el.smearing = data["smearing"]
        if "operations" in data:
            for k, v in data["operations"].items():
                el.operations[k] = v
        if "inputs" in data:
            el.inputs = _build_port(data["inputs"])
        if "outputs" in data:
            el.outputs = _build_port(data["outputs"])
        if "digitalInputs" in data:
            for k, v in data["digitalInputs"].items():
                el.digital_inputs[k] = v
        if "digitalOutputs" in data:
            for k, v in data["digitalOutputs"].items():
                el.digital_outputs[k] = qua_config.QuaConfigDigitalOutputPortReference(
                    port=qua_config.QuaConfigPortReference(controller=v[0], number=v[1])
                )
        if "outputPulseParameters" in data:
            pulse_parameters = data["outputPulseParameters"]
            el.output_pulse_parameters.signal_threshold = pulse_parameters["signalThreshold"]

            signal_polarity = pulse_parameters["signalPolarity"].upper()
            if signal_polarity == "ABOVE" or signal_polarity == "ASCENDING":
                el.output_pulse_parameters.signal_polarity = qua_config.QuaConfigOutputPulseParametersPolarity.ASCENDING
            elif signal_polarity == "BELOW" or signal_polarity == "DESCENDING":
                el.output_pulse_parameters.signal_polarity = (
                    qua_config.QuaConfigOutputPulseParametersPolarity.DESCENDING
                )

            if "derivativeThreshold" in pulse_parameters:
                el.output_pulse_parameters.derivative_threshold = pulse_parameters["derivativeThreshold"]

                polarity = pulse_parameters["derivativePolarity"].upper()
                if polarity == "ABOVE" or polarity == "ASCENDING":
                    el.output_pulse_parameters.derivative_polarity = (
                        qua_config.QuaConfigOutputPulseParametersPolarity.ASCENDING
                    )
                elif polarity == "BELOW" or polarity == "DESCENDING":
                    el.output_pulse_parameters.derivative_polarity = (
                        qua_config.QuaConfigOutputPulseParametersPolarity.DESCENDING
                    )
        if "sticky" in data:
            validate_sticky_duration(data["sticky"].duration)
            if capabilities.supports_sticky_elements:
                el.sticky = data["sticky"]
                el.sticky.duration = int(el.sticky.duration / 4)
            else:
                if data["sticky"].digital:
                    raise ConfigValidationException(
                        f"Server does not support digital sticky used in element " f"'{el}'"
                    )
                el.hold_offset = qua_config.QuaConfigHoldOffset(duration=int(data["sticky"].duration / 4))

        elif "hold_offset" in data:
            if capabilities.supports_sticky_elements:
                el.sticky = qua_config.QuaConfigSticky(
                    analog=True, digital=False, duration=data["hold_offset"].duration
                )
            else:
                el.hold_offset = data["hold_offset"]

        if "thread" in data:
            el.thread.thread_name = data["thread"]

        rf_inputs = data.get("RF_inputs", {})
        for k, (device, port) in rf_inputs.items():
            el.rf_inputs[k] = QuaConfigGeneralPortReference(device_name=device, port=port)

        rf_outputs = data.get("RF_outputs", {})
        for k, (device, port) in rf_outputs.items():
            el.rf_outputs[k] = QuaConfigGeneralPortReference(device_name=device, port=port)
        return el

    @validates_schema
    def validate_timetagging_parameters(self, data, **kwargs):
        validate_timetagging_parameters(data)

    @validates_schema
    def validate_output_tof(self, data, **kwargs):
        validate_output_tof(data)

    @validates_schema
    def validate_output_smearing(self, data, **kwargs):
        validate_output_smearing(data)

    @validates_schema
    def validate_oscillator(self, data, **kwargs):
        validate_oscillator(data)


def _build_port(data) -> Dict[str, qua_config.QuaConfigAdcPortReference]:
    outputs = {}
    if data is not None:
        for k, (controller, number) in data.items():
            outputs[k] = qua_config.QuaConfigAdcPortReference(controller=controller, number=number)
    return outputs


class QuaConfigSchema(Schema):
    version = fields.Int(metadata={"description": "Config version."})
    oscillators = fields.Dict(
        keys=fields.String(),
        values=fields.Nested(OscillatorSchema),
        metadata={
            "description": """The oscillators used to drive the elements. 
        Can be used to share oscillators between elements"""
        },
    )

    elements = fields.Dict(
        keys=fields.String(),
        values=fields.Nested(ElementSchema),
        metadata={
            "description": """The elements. Each element represents and
         describes a controlled entity which is connected to the ports of the 
         controller."""
        },
    )

    controllers = fields.Dict(
        fields.String(),
        fields.Nested(ControllerSchema),
        metadata={"description": """The controllers. """},
    )

    octaves = fields.Dict(
        fields.String(),
        fields.Nested(OctaveSchema),
        metadata={"description": "The octaves that are in the system, with their interconnected loopbacks."},
    )

    integration_weights = fields.Dict(
        keys=fields.String(),
        values=fields.Nested(IntegrationWeightSchema),
        metadata={
            "description": """The integration weight vectors used in the integration 
        and demodulation of data returning from a element."""
        },
    )

    waveforms = fields.Dict(
        keys=fields.String(),
        values=_waveform_poly_field,
        metadata={
            "description": """The analog waveforms sent to an element when a pulse is 
        played."""
        },
    )
    digital_waveforms = fields.Dict(
        keys=fields.String(),
        values=fields.Nested(DigitalWaveFormSchema),
        metadata={
            "description": """The digital waveforms sent to an element when a pulse is 
        played."""
        },
    )
    pulses = fields.Dict(
        keys=fields.String(),
        values=fields.Nested(PulseSchema),
        metadata={"description": """The pulses to be played to the elements. """},
    )
    mixers = fields.Dict(
        keys=fields.String(),
        values=fields.List(fields.Nested(MixerSchema)),
        metadata={
            "description": """The IQ mixer calibration properties, used to post-shape the pulse
         to compensate for imperfections in the mixers used for up-converting the 
         analog waveforms."""
        },
    )

    class Meta:
        title = "QUA Config"
        description = "QUA program config root object"

    @post_load(pass_many=False)
    def build(self, data, **kwargs):
        config_wrapper = qua_config.QuaConfig()
        config = qua_config.QuaConfigQuaConfigV1()
        version = data["version"]
        if str(version) != "1":
            raise RuntimeError("Version must be set to 1 (was set to " + str(version) + ")")
        if "elements" in data:
            for el_name, el in data["elements"].items():
                config.elements[el_name] = el
        if "oscillators" in data:
            for osc_name, osc in data["oscillators"].items():
                config.oscillators[osc_name] = osc
        if "controllers" in data:
            for k, v in data["controllers"].items():
                config.controllers[k] = v
        if "octaves" in data:
            for k, v in data["octaves"].items():
                config.octaves[k] = v
        if "integration_weights" in data:
            for k, v in data["integration_weights"].items():
                config.integration_weights[k] = v
        if "waveforms" in data:
            for k, v in data["waveforms"].items():
                config.waveforms[k] = v
        if "digital_waveforms" in data:
            for k, v in data["digital_waveforms"].items():
                config.digital_waveforms[k] = v
        if "mixers" in data:
            for k, v in data["mixers"].items():
                config.mixers[k] = qua_config.QuaConfigMixerDec(correction=v)
        if "pulses" in data:
            for k, v in data["pulses"].items():
                config.pulses[k] = v

        config_wrapper.v1_beta = config
        set_octave_upconverter_connection_to_elements(config_wrapper)
        set_lo_frequency_to_mix_input_elements_that_are_connected_to_octave(config_wrapper)
        set_octave_downconverter_connection_to_elements(config_wrapper)
        set_non_existing_mixers_in_mix_input_elements(config_wrapper)
        validate_inputs_or_outputs_exist(config_wrapper)
        return config_wrapper
