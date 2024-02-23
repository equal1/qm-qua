from typing import TYPE_CHECKING, List, Tuple, Union, Optional

import betterproto
from betterproto.lib.google.protobuf import Empty

import qm.grpc.qua as _qua
from qm._loc import _get_loc
from qm.exceptions import QmQuaException

if TYPE_CHECKING:
    from qm.qua._dsl import _ResultSource
    from qm.qua._dsl_specific_type_hints import PlayPulseType, MeasurePulseType
    from qm.qua._type_hinting import MessageVarType, MessageExpressionType, MessageVariableOrExpression


class StatementsCollection:
    def __init__(self, body: _qua.QuaProgramStatementsCollection):
        self._body = body

    @staticmethod
    def _check_serialised_on_wire(message: _qua.QuaProgramAnyStatement, name: str) -> None:
        if (
            not betterproto.serialized_on_wire(getattr(message, name))
            or not betterproto.which_one_of(message, "statement_oneof")[0] == name
        ):
            raise QmQuaException(f"Failed to serialize of wire {name}")

    def play(
        self,
        pulse: "PlayPulseType",
        element: str,
        duration: Optional["MessageExpressionType"] = None,
        condition: Optional["MessageExpressionType"] = None,
        target: str = "",
        chirp: Optional[_qua.QuaProgramChirp] = None,
        truncate: Optional["MessageExpressionType"] = None,
        timestamp_label: Optional[str] = None,
    ) -> None:
        """Play a pulse to a element as per the OPX config

        Args:
            pulse: A tuple (pulse, amp). pulse is string of pulse name,
                amp is a 4 matrix
            element
            duration
            condition
            target
            chirp
            truncate
            timestamp_label

        Returns:

        """

        amp = None
        if isinstance(pulse, tuple):
            pulse, amp = pulse

        loc = _get_loc()
        statement = _qua.QuaProgramAnyStatement(
            play=_qua.QuaProgramPlayStatement(
                loc=loc,
                qe=_qua.QuaProgramQuantumElementReference(name=element, loc=loc),
                target_input=target,
            )
        )
        if isinstance(pulse, _qua.QuaProgramRampPulse):
            statement.play.ramp_pulse = _qua.QuaProgramRampPulse().from_dict(pulse.to_dict())
        else:
            statement.play.named_pulse = _qua.QuaProgramPulseReference(name=pulse, loc=loc)

        if duration is not None:
            statement.play.duration = _qua.QuaProgramAnyScalarExpression().from_dict(duration.to_dict())
        if condition is not None:
            statement.play.condition = _qua.QuaProgramAnyScalarExpression().from_dict(condition.to_dict())
        if chirp is not None:
            statement.play.chirp = _qua.QuaProgramChirp().from_dict(chirp.to_dict())
            statement.play.chirp.loc = loc
        if amp is not None:
            statement.play.amp = _qua.QuaProgramAmpMultiplier(loc=loc, v0=amp[0])
            for i in range(1, 4, 1):
                if amp[i] is not None:
                    setattr(statement.play.amp, "v" + str(i), amp[i])
        if truncate is not None:
            statement.play.truncate = _qua.QuaProgramAnyScalarExpression().from_dict(truncate.to_dict())
        if timestamp_label is not None:
            statement.play.timestamp_label = timestamp_label

        self._check_serialised_on_wire(statement, "play")
        self._body.statements.append(statement)

    def pause(self, *elements: str) -> None:
        """Pause the execution of the given elements

        Args:
            *elements

        Returns:

        """
        loc = _get_loc()
        statement = _qua.QuaProgramAnyStatement(
            pause=_qua.QuaProgramPauseStatement(
                loc=_get_loc(),
                qes=[_qua.QuaProgramQuantumElementReference(name=element, loc=loc) for element in elements],
            )
        )
        self._check_serialised_on_wire(statement, "pause")
        self._body.statements.append(statement)

    def update_frequency(
        self,
        element: str,
        new_frequency: "MessageExpressionType",
        units: str,
        keep_phase: bool,
    ) -> None:
        """Updates the frequency of a given element

        Args:
            element: The element to set the frequency to
            new_frequency: The new frequency value to set
            units
            keep_phase

        Returns:

        """
        try:
            units_enum = _qua.QuaProgramUpdateFrequencyStatementUnits[units]
        except KeyError:
            raise QmQuaException(f'unknown units "{units}"')

        loc = _get_loc()
        statement = _qua.QuaProgramAnyStatement(
            update_frequency=_qua.QuaProgramUpdateFrequencyStatement(
                loc=loc,
                qe=_qua.QuaProgramQuantumElementReference(name=element, loc=loc),
                units=units_enum,
                keep_phase=keep_phase,
                value=_qua.QuaProgramAnyScalarExpression().from_dict(new_frequency.to_dict()),
            )
        )
        self._check_serialised_on_wire(statement, "update_frequency")
        self._body.statements.append(statement)

    def update_correction(
        self,
        element: str,
        c00: "MessageExpressionType",
        c01: "MessageExpressionType",
        c10: "MessageExpressionType",
        c11: "MessageExpressionType",
    ) -> None:
        """Updates the correction of a given element

        Args:
            element: The element to set the correction to
            c00: The top left matrix element
            c01: The top right matrix element
            c10: The bottom left matrix element
            c11: The bottom right matrix element
        """
        loc = _get_loc()
        statement = _qua.QuaProgramAnyStatement(
            update_correction=_qua.QuaProgramUpdateCorrectionStatement(
                loc=loc,
                qe=_qua.QuaProgramQuantumElementReference(name=element, loc=loc),
                correction=_qua.QuaProgramCorrection(c0=c00, c1=c01, c2=c10, c3=c11),
            )
        )
        self._body.statements.append(statement)

    def set_dc_offset(self, element: str, element_input: str, offset: "MessageExpressionType") -> None:
        """Update the DC offset of an element's input

        Args:
            element: The element to update its DC offset
            element_input: desired input of the element, can be 'single'
                for a 'singleInput' element or 'I' or 'Q' for a
                'mixInputs' element
            offset: Desired dc offset for single
        """
        loc = _get_loc()
        statement = _qua.QuaProgramAnyStatement(
            set_dc_offset=_qua.QuaProgramSetDcOffsetStatement(
                loc=loc,
                qe=_qua.QuaProgramQuantumElementReference(name=element, loc=loc),
                qe_input_reference=element_input,
                offset=offset,
            )
        )
        self._check_serialised_on_wire(statement, "set_dc_offset")
        self._body.statements.append(statement)

    def advance_input_stream(self, input_stream: "MessageVariableOrExpression") -> None:
        """advance an input stream pointer to be sent to the QUA program

        Args:
            input_stream: The input stream to advance
        """
        statement = _qua.QuaProgramAnyStatement(
            advance_input_stream=_qua.QuaProgramAdvanceInputStreamStatement(loc=_get_loc())
        )

        if isinstance(input_stream, _qua.QuaProgramArrayVarRefExpression):
            statement.advance_input_stream.stream_array = input_stream
        elif (
            isinstance(input_stream, _qua.QuaProgramAnyScalarExpression)
            and betterproto.which_one_of(input_stream, "expression_oneof")[0] == "variable"
        ):
            statement.advance_input_stream.stream_variable = input_stream.variable
        else:
            raise QmQuaException("unsupported type for advance input stream")

        self._check_serialised_on_wire(statement, "advance_input_stream")
        self._body.statements.append(statement)

    def align(self, *elements: str) -> None:
        """Align the given elements

        Args:
            *elements

        Returns:

        """
        loc = _get_loc()
        statement = _qua.QuaProgramAnyStatement(
            align=_qua.QuaProgramAlignStatement(
                loc=loc,
                qe=[_qua.QuaProgramQuantumElementReference(name=element, loc=loc) for element in elements],
            )
        )
        self._check_serialised_on_wire(statement, "align")
        self._body.statements.append(statement)

    def reset_phase(self, element: str) -> None:
        """TODO: document

        Args:
            element

        Returns:

        """
        loc = _get_loc()
        statement = _qua.QuaProgramAnyStatement(
            reset_phase=_qua.QuaProgramResetPhaseStatement(
                loc=loc, qe=_qua.QuaProgramQuantumElementReference(name=element, loc=loc)
            )
        )
        self._check_serialised_on_wire(statement, "reset_phase")
        self._body.statements.append(statement)

    def wait(self, duration: "MessageExpressionType", *elements: str) -> None:
        """Waits for the given duration on all provided elements

        Args:
            duration
            *elements

        Returns:

        """
        loc = _get_loc()
        statement = _qua.QuaProgramAnyStatement(
            wait=_qua.QuaProgramWaitStatement(
                loc=loc,
                time=_qua.QuaProgramAnyScalarExpression().from_dict(duration.to_dict()),
                qe=[_qua.QuaProgramQuantumElementReference(name=element, loc=loc) for element in elements],
            )
        )
        self._check_serialised_on_wire(statement, "wait")
        self._body.statements.append(statement)

    def wait_for_trigger(
        self,
        pulse_to_play: Optional[str],
        trigger_element: Optional[Union[Tuple[str, str], str]],
        time_tag_target: Optional["MessageVarType"],
        *elements: str,
    ) -> None:
        loc = _get_loc()
        statement = _qua.QuaProgramAnyStatement(
            wait_for_trigger=_qua.QuaProgramWaitForTriggerStatement(
                loc=loc,
                qe=[_qua.QuaProgramQuantumElementReference(name=element, loc=loc) for element in elements],
            )
        )

        if pulse_to_play is not None:
            statement.wait_for_trigger.pulse_to_play.name = pulse_to_play
        if trigger_element is not None:
            if isinstance(trigger_element, tuple):
                el, out = trigger_element
                statement.wait_for_trigger.element_output = _qua.QuaProgramWaitForTriggerStatementElementOutput(
                    element=el, output=out
                )
            else:
                statement.wait_for_trigger.element_output = _qua.QuaProgramWaitForTriggerStatementElementOutput(
                    element=trigger_element
                )
        else:
            statement.wait_for_trigger.global_trigger = Empty()
        if time_tag_target is not None:
            statement.wait_for_trigger.time_tag_target = time_tag_target

        self._check_serialised_on_wire(statement, "wait_for_trigger")
        self._body.statements.append(statement)

    def save(self, source: _qua.QuaProgramSaveStatementSource, result: "_ResultSource") -> None:
        statement = _qua.QuaProgramAnyStatement(
            save=_qua.QuaProgramSaveStatement(loc=_get_loc(), source=source, tag=result.get_var_name())
        )

        self._check_serialised_on_wire(statement, "save")
        self._body.statements.append(statement)

    def z_rotation(self, angle: "MessageExpressionType", *elements: str) -> None:
        loc = _get_loc()
        for element in elements:
            statement = _qua.QuaProgramAnyStatement(
                z_rotation=_qua.QuaProgramZRotationStatement(
                    loc=loc,
                    value=_qua.QuaProgramAnyScalarExpression().from_dict(angle.to_dict()),
                    qe=_qua.QuaProgramQuantumElementReference(name=element, loc=loc),
                )
            )

            self._check_serialised_on_wire(statement, "z_rotation")
            self._body.statements.append(statement)

    def reset_frame(self, *elements: str) -> None:
        loc = _get_loc()
        for element in elements:
            statement = _qua.QuaProgramAnyStatement(
                reset_frame=_qua.QuaProgramResetFrameStatement(
                    loc=loc,
                    qe=_qua.QuaProgramQuantumElementReference(name=element, loc=loc),
                )
            )

            self._check_serialised_on_wire(statement, "reset_frame")
            self._body.statements.append(statement)

    def fast_frame_rotation(
        self, cosine: _qua.QuaProgramAnyScalarExpression, sine: _qua.QuaProgramAnyScalarExpression, *elements: str
    ) -> None:
        loc = _get_loc()
        for element in elements:
            statement = _qua.QuaProgramAnyStatement(
                fast_frame_rotation=_qua.QuaProgramFastFrameRotationStatement(
                    loc=loc,
                    cosine=cosine,
                    sine=sine,
                    qe=_qua.QuaProgramQuantumElementReference(name=element, loc=loc),
                )
            )
            self._check_serialised_on_wire(statement, "fast_frame_rotation")
            self._body.statements.append(statement)

    def ramp_to_zero(self, element: str, duration: Optional[int]) -> None:
        loc = _get_loc()
        statement = _qua.QuaProgramAnyStatement(
            ramp_to_zero=_qua.QuaProgramRampToZeroStatement(
                loc=loc,
                qe=_qua.QuaProgramQuantumElementReference(name=element, loc=loc),
                duration=duration if duration else None,
            )
        )

        self._check_serialised_on_wire(statement, "ramp_to_zero")
        self._body.statements.append(statement)

    def measure(
        self,
        pulse: "MeasurePulseType",
        element: str,
        stream: Optional["_ResultSource"] = None,
        *processes: _qua.QuaProgramMeasureProcess,
        timestamp_label: Optional[str] = None,
    ) -> None:
        """Measure an element using the given pulse, process the result with the integration weights and
        store the results to the provided variables

        Args:
            pulse
            element
            stream (_ResultSource)
            *processes: an iterable of analog processes
        :param timestamp_label

        Returns:

        """
        amp = None
        if isinstance(pulse, tuple):
            pulse, amp = pulse

        loc = _get_loc()
        statement = _qua.QuaProgramAnyStatement(
            measure=_qua.QuaProgramMeasureStatement(
                loc=loc,
                pulse=_qua.QuaProgramPulseReference(name=pulse, loc=loc),
                qe=_qua.QuaProgramQuantumElementReference(name=element, loc=loc),
            )
        )
        if stream is not None:
            statement.measure.stream_as = stream.get_var_name()

        for analog_process in processes:
            statement.measure.measure_processes.append(analog_process)

        if amp is not None:
            statement.measure.amp.loc = loc
            statement.measure.amp.v0 = amp[0]
            for i in range(1, 4, 1):
                if amp[i] is not None:
                    setattr(statement.measure.amp, "v" + str(i), amp[i])

        if timestamp_label is not None:
            statement.measure.timestamp_label = timestamp_label

        self._check_serialised_on_wire(statement, "measure")
        self._body.statements.append(statement)

    def if_block(self, condition: "MessageExpressionType", unsafe: bool = False) -> "StatementsCollection":
        statement = _qua.QuaProgramAnyStatement(
            if_=_qua.QuaProgramIfStatement(
                loc=_get_loc(),
                condition=condition,
                unsafe=unsafe,
                body=_qua.QuaProgramStatementsCollection(statements=[]),
            )
        )

        self._check_serialised_on_wire(statement, "if_")
        self._body.statements.append(statement)
        return StatementsCollection(statement.if_.body)

    def for_each(
        self, iterators: List[Tuple["_qua.QuaProgramVarRefExpression", "_qua.QuaProgramArrayVarRefExpression"]]
    ) -> "StatementsCollection":
        statement = _qua.QuaProgramAnyStatement(
            for_each=_qua.QuaProgramForEachStatement(
                loc=_get_loc(),
                body=_qua.QuaProgramStatementsCollection(statements=[]),
                iterator=[
                    _qua.QuaProgramForEachStatementVariableWithValues(variable=var, array=arr) for var, arr in iterators
                ],
            )
        )

        self._check_serialised_on_wire(statement, "for_each")
        self._body.statements.append(statement)
        return StatementsCollection(statement.for_each.body)

    def get_last_statement(self) -> Optional[_qua.QuaProgramAnyStatement]:
        statements = self._body.statements
        length_statements = len(statements)
        if length_statements == 0:
            return None
        return statements[-1]

    def for_block(self) -> _qua.QuaProgramForStatement:
        statement = _qua.QuaProgramAnyStatement(
            for_=_qua.QuaProgramForStatement(loc=_get_loc(), body=_qua.QuaProgramStatementsCollection(statements=[]))
        )

        self._check_serialised_on_wire(statement, "for_")
        self._body.statements.append(statement)
        return statement.for_

    def strict_timing_block(self) -> _qua.QuaProgramStrictTimingStatement:
        statement = _qua.QuaProgramAnyStatement(
            strict_timing=_qua.QuaProgramStrictTimingStatement(
                loc=_get_loc(), body=_qua.QuaProgramStatementsCollection(statements=[])
            )
        )

        self._check_serialised_on_wire(statement, "strict_timing")
        self._body.statements.append(statement)
        return statement.strict_timing

    def assign(
        self,
        target: _qua.QuaProgramAssignmentStatementTarget,
        expression: "MessageExpressionType",
    ) -> None:
        """Assign a value calculated by :expression into :target

        Args:
            target: The name of the variable to assign to
            expression: The expression to calculate

        Returns:

        """
        statement = _qua.QuaProgramAnyStatement(
            assign=_qua.QuaProgramAssignmentStatement(loc=_get_loc(), target=target, expression=expression)
        )

        self._check_serialised_on_wire(statement, "assign")
        self._body.statements.append(statement)
