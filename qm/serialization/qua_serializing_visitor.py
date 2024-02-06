import re
from typing import List, Union, Optional

import betterproto
from betterproto.lib.google.protobuf import Value, ListValue

import qm
from qm.grpc import qua
from qm.exceptions import QmQuaException
from qm.serialization.qua_node_visitor import QuaNodeVisitor
from qm.serialization.expression_serializing_visitor import ExpressionSerializingVisitor


class QuaSerializingVisitor(QuaNodeVisitor):
    def __init__(self) -> None:
        super().__init__()
        self._indent = 0
        self._lines = []
        self.tags = []

    def out(self):
        return "\n".join(["from qm.qua import *", ""] + self._lines + [""])

    def _out_lines(self):
        return self._lines

    def _default_enter(self, node) -> bool:
        name = f"{type(node).__module__}.{type(node).__name__}"
        statement = _statements.get(name, None)
        block = _blocks.get(name, None)
        if name not in _dont_print:
            print(f"entering {name}")
        if statement:
            line = statement(node)
            self._line(line)
        if block:
            self._enter_block(block(node))
        return statement is None

    @staticmethod
    def _get_result_name(value):
        value = value.list_value.values[-1]
        if value.string_value != "":
            return value.string_value
        else:
            return QuaSerializingVisitor._get_result_name(value)

    @staticmethod
    def _search_adc_trace(values):
        ADC_TRACE_NAME = "@macro_adc_trace"
        for value in values:
            if isinstance(value, str):
                if value == ADC_TRACE_NAME:
                    return True
                else:
                    return None
            elif value.string_value == ADC_TRACE_NAME:
                return True
            elif len(value.list_value) > 0:
                return QuaSerializingVisitor._search_adc_trace(value.list_value)
        return False

    @staticmethod
    def _search_auto_added_stream(values: List[Value]):
        is_auto_added_result = isinstance(values[2], Value) and values[2].string_value == "auto"
        return is_auto_added_result

    def _fix_legacy_save(self, sp_line, node: ListValue):
        sp_line = sp_line.split(".")
        trace_name = sp_line[0]
        save_name = sp_line[-1].split('"')[1]
        save_name = re.sub(r"_input\d", "", save_name)
        is_auto_added_stream = self._search_auto_added_stream(node.values)
        if is_auto_added_stream:
            self._lines.pop()
            line_to_remove_index = None
            for i in range(len(self._lines)):
                if self._lines[i].find(f"{trace_name} = declare_stream") > 0:
                    line_to_remove_index = i
                self._lines[i] = self._lines[i].replace(trace_name, f'"{save_name}"')
            if line_to_remove_index:
                self._lines.pop(line_to_remove_index)

    def enter_qm_grpc_qua_QuaResultAnalysis(self, node: qua.QuaResultAnalysis) -> bool:
        if len(node.model) > 0:
            self._enter_block("with stream_processing():")
            return True
        else:
            return False

    def enter_qm_grpc_qua_QuaProgramSaveStatement(self, node: qua.QuaProgramSaveStatement) -> bool:
        if node.tag not in self.tags:
            self._line(f"{node.tag} = declare_stream()")
            self.tags.append(node.tag)
        save_line = f"save({ExpressionSerializingVisitor.serialize(node.source)}, {node.tag})"
        self._line(save_line)
        return False

    def enter_qm_grpc_qua_QuaProgramVarDeclaration(self, node: qua.QuaProgramVarDeclaration):
        args = self._get_declare_var_args(node)

        if node.is_input_stream:
            # Removes the '_input_stream' from the end of the name
            stream_name = node.name[13:]
            self._line(
                f"{node.name} = declare_input_stream({_var_type_dec[node.type]}, '{stream_name}', {_dict_to_python_call(args)})"
            )
        else:
            self._line(f"{node.name} = declare({_var_type_dec[node.type]}, {_dict_to_python_call(args)})")

        return False

    def enter_betterproto_lib_google_protobuf_ListValue(self, node: betterproto.lib.google.protobuf.ListValue):
        name = f"{type(node).__module__}.{type(node).__name__}"
        statement = _statements.get(name, None)
        line = statement(node)
        self._line(line)
        if name == "betterproto.lib.google.protobuf.ListValue":
            self._fix_legacy_save(line, node)

        return False

    def leave_qm_grpc_qua_QuaProgram(self, node: qm.grpc.qua.QuaProgram):
        if self._lines[-1].find("with stream_processing():") > 0:
            self._lines.pop()
        return False

    def _get_declare_var_args(self, node):
        size = node.size
        dim = node.dim
        args = {}
        if dim > 0:
            args["size"] = size
        if dim > 0 and len(node.value) > 0:
            args["value"] = "[" + ", ".join([_ser_exp(it) for it in node.value]) + "]"
        elif len(node.value) == 1:
            args["value"] = _ser_exp(node.value[0])
        if "value" in args and "size" in args:
            del args["size"]
        return args

    def enter_qm_grpc_qua_QuaProgramMeasureStatement(self, node: qua.QuaProgramMeasureStatement):
        if node.timestamp_label and node.timestamp_label not in self.tags:
            self._line(f"{node.timestamp_label} = declare_stream()")
            self.tags.append(node.timestamp_label)
        if node.stream_as and node.stream_as not in self.tags:
            if node.stream_as.startswith("atr_"):
                self._line(f"{node.stream_as} = declare_stream(adc_trace=True)")
            else:
                self._line(f"{node.stream_as} = declare_stream()")
            self.tags.append(node.stream_as)
        return self._default_enter(node)

    def visit_qm_grpc_qua_QuaProgramForStatement(self, node: qua.QuaProgramForStatement):
        if len(node.body.statements) > 0:
            super()._default_visit(node.body)
        else:
            self._line("pass")

    def visit_qm_grpc_qua_QuaProgramForEachStatement(self, node: qua.QuaProgramForEachStatement):
        if len(node.body.statements) > 0:
            super()._default_visit(node.body)
        else:
            self._line("pass")

    def visit_qm_grpc_qua_QuaProgramIfStatement(self, node: qua.QuaProgramIfStatement):
        if len(node.body.statements) > 0:
            super()._default_visit(node.body)
        else:
            self._line("pass")
        elseifs_list = node.elseifs
        for elseif in elseifs_list:
            elseif_block = elseif.body
            condition = elseif.condition
            self._leave_block()
            self._line(f"with elif_({ExpressionSerializingVisitor.serialize(condition)}):")
            self._enter_block()
            if len(elseif_block.statements) > 0:
                super()._default_visit(elseif_block)
            else:
                self._line("pass")

        else_block = node.else_
        if len(else_block.statements) > 0:  # Cannot ID else_() with pass
            self._leave_block()
            self._line("with else_():")
            self._enter_block()
            super()._default_visit(else_block)

    def visit_qm_grpc_qua_QuaProgramPlayStatement(self, node: qua.QuaProgramPlayStatement):
        pulse_one_of, value = betterproto.which_one_of(node, "pulseType")
        if pulse_one_of == "named_pulse":
            pulse = f'"{node.named_pulse.name}"'
            # node.pulse - duplicate with namedPulse
        elif pulse_one_of == "ramp_pulse":
            pulse = f"ramp({ExpressionSerializingVisitor.serialize(node.ramp_pulse)})"
        else:
            raise QmQuaException(f"Unknown pulse type {pulse_one_of}")

        element = node.qe.name
        amp = ""
        if betterproto.serialized_on_wire(node.amp):
            v0 = _ser_exp(node.amp.v0)
            v1 = _ser_exp(node.amp.v1)
            v2 = _ser_exp(node.amp.v2)
            v3 = _ser_exp(node.amp.v3)
            if v0 != "":
                if v1 != "":
                    amp = f"*amp({v0}, {v1}, {v2}, {v3})"
                else:
                    amp = f"*amp({v0})"
        args = []

        _, duration = betterproto.which_one_of(node.duration, "expression_oneof")
        if duration is not None:
            args.append(f"duration={_ser_exp(duration)}")

        _, condition = betterproto.which_one_of(node.condition, "expression_oneof")
        if condition is not None:
            args.append(f"condition={_ser_exp(condition)}")

        if node.target_input:
            args.append(f'target="{node.target_input}"')

        if betterproto.serialized_on_wire(node.chirp):
            rate_one_of, value = betterproto.which_one_of(node.chirp, "rate")
            if rate_one_of in ("scalar_rate", "array_rate"):
                rate = ExpressionSerializingVisitor.serialize(value)
            else:
                raise QmQuaException(f"Unknown chirp rate {rate_one_of}")

            unit_mapping = {
                qua.QuaProgramChirpUnits.HzPerNanoSec: "Hz/nsec",
                qua.QuaProgramChirpUnits.mHzPerNanoSec: "mHz/nsec",
                qua.QuaProgramChirpUnits.uHzPerNanoSec: "uHz/nsec",
                qua.QuaProgramChirpUnits.nHzPerNanoSec: "nHz/nsec",
                qua.QuaProgramChirpUnits.pHzPerNanoSec: "pHz/nsec",
            }
            s_units = node.chirp.units
            if s_units in unit_mapping:
                units = unit_mapping[s_units]
            else:
                raise QmQuaException(f"Unsupported units {s_units}")

            times_builder = []
            for time in node.chirp.times:
                times_builder.append(f"{time}")

            if len(times_builder) > 0:
                times = f'[{", ".join(times_builder)}]'
            else:
                times = "None"

            if node.chirp.continue_chirp:
                args.append("continue_chirp=True")

            args.append(f'chirp=({rate},{times},"{units}")')

        _, truncate = betterproto.which_one_of(node.truncate, "expression_oneof")
        if truncate is not None:
            args.append(f"truncate={_ser_exp(truncate)}")

        if node.timestamp_label:
            if node.timestamp_label not in self.tags:
                self._line(f"{node.timestamp_label} = declare_stream()")
                self.tags.append(node.timestamp_label)
            args.append(f"timestamp_stream={node.timestamp_label}")

        # TODO maybe make sure no other fields?

        if len(args) > 0:
            args_str = f', {", ".join(args)}'
        else:
            args_str = ""
        self._line(f'play({pulse}{amp}, "{element}"{args_str})')

    def _default_leave(self, node):
        name = f"{type(node).__module__}.{type(node).__name__}"
        block = _blocks.get(name, None)
        if block is not None:
            self._leave_block()
        super()._default_leave(node)

    def _enter_block(self, line: Optional[str] = None):
        if line is not None:
            self._line(line)
        self._indent += 1

    def _leave_block(self):
        self._indent -= 1

    def _line(self, line: str):
        self._lines.append((self._indent * "    ") + line)


def _ser_exp(value):
    return ExpressionSerializingVisitor.serialize(value)


def _dict_to_python_call(d: dict) -> str:
    return ", ".join([f"{k}={v}" for k, v in d.items()])


def _ramp_to_zero_statement(node):
    args = []
    args.append(f'"{node.qe.name}"')
    if node.duration is not None:
        args.append(str(node.duration))
    return f'ramp_to_zero({", ".join(args)})'


def _measure_statement(node: qua.QuaProgramMeasureStatement):
    args = []

    amp = ""
    v0 = _ser_exp(node.amp.v0)
    v1 = _ser_exp(node.amp.v1)
    v2 = _ser_exp(node.amp.v2)
    v3 = _ser_exp(node.amp.v3)
    if v0 != "":
        if v1 != "":
            amp = f"*amp({v0}, {v1}, {v2}, {v3})"
        else:
            amp = f"*amp({v0})"

    args.append(f'"{node.pulse.name}"{amp}')
    args.append(f'"{node.qe.name}"')
    if node.stream_as:
        args.append(f"{node.stream_as}")
    else:
        args.append("None")

    if len(node.measure_processes) > 0:
        for process in node.measure_processes:
            args.append(ExpressionSerializingVisitor.serialize(process))
    if node.timestamp_label:
        args.append(f"timestamp_stream={node.timestamp_label}")
    return f'measure({", ".join(args)})'


def _wait_statement(node: qua.QuaProgramWaitStatement):
    args = []
    _, wait_value = betterproto.which_one_of(node.time, "expression_oneof")
    if wait_value is not None:
        args.append(f"{ExpressionSerializingVisitor.serialize(wait_value)}")
    qes = []
    for qe in node.qe:
        qes.append(f'"{qe.name}"')
    args.append(", ".join(qes))
    return f'wait({", ".join(args)})'


def _align_statement(node):
    args = []
    for qe in node.qe:
        args.append(f'"{qe.name}"')
    return f'align({", ".join(args)})'


def _wait_for_trigger_statement(node: qua.QuaProgramWaitForTriggerStatement):
    args = []
    for qe in node.qe:
        args.append(f'"{qe.name}"')
    if node.pulse_to_play.name:
        args.append(f'"{node.pulse_to_play.name}"')
    if node.element_output.element:
        if node.element_output.output:
            args.append(f'trigger_element=("{node.element_output.element}", "{node.element_output.output}")')
        else:
            args.append(f'trigger_element="{node.element_output.element}"')
    if node.time_tag_target.name != "":
        args.append(f"time_tag_target={node.time_tag_target.name}")
    return f'wait_for_trigger({", ".join(args)})'


def _frame_rotation_statement(node):
    args = []
    args.append(f"{ExpressionSerializingVisitor.serialize(node.value)}")
    args.append(f'"{node.qe.name}"')
    return f'frame_rotation_2pi({", ".join(args)})'


def _fast_frame_rotation_statement(node):
    args = []
    args.append(f"{ExpressionSerializingVisitor.serialize(node.cosine)}")
    args.append(f"{ExpressionSerializingVisitor.serialize(node.sine)}")
    args.append(f'"{node.qe.name}"')
    return f'fast_frame_rotation({", ".join(args)})'


def _reset_frame_statement(node):
    args = []
    args.append(f'"{node.qe.name}"')
    return f'reset_frame({", ".join(args)})'


def _update_frequency_statement(node):
    args = []
    args.append(f'"{node.qe.name}"')
    args.append(f"{ExpressionSerializingVisitor.serialize(node.value)}")
    args.append(f'"{qua.QuaProgramUpdateFrequencyStatementUnits(node.units).name}"')
    args.append(f"{node.keep_phase}")
    return f'update_frequency({", ".join(args)})'


def _set_dc_offset_statement(node: qua.QuaProgramSetDcOffsetStatement):
    args = []
    args.append(f'"{node.qe.name}"')
    args.append(f'"{node.qe_input_reference}"')
    args.append(f"{ExpressionSerializingVisitor.serialize(node.offset)}")
    return f'set_dc_offset({", ".join(args)})'


def _advance_input_stream_statement(node):
    if node.stream_array.name != "":
        input_stream = ExpressionSerializingVisitor.serialize(node.stream_array)
    elif node.stream_variable.name != "":
        input_stream = ExpressionSerializingVisitor.serialize(node.stream_variable)
    else:
        raise RuntimeError("unsupported type for pop input stream")
    return f"advance_input_stream({input_stream})"


def _for_block_statement(node):
    condition = ExpressionSerializingVisitor.serialize(node.condition)
    if len(node.init.statements) == 0 and len(node.update.statements) == 0:
        if condition == "True":
            return "with infinite_loop_():"
        else:
            return f"with while_({condition}):"
    else:
        if len(node.init.statements) != 1:
            raise Exception("for is not valid")
        if len(node.update.statements) != 1:
            raise Exception("for is not valid")

        init = node.init.statements[0].assign
        update = node.update.statements[0].assign

        if init is None:
            raise Exception("for is not valid")
        if update is None:
            raise Exception("for is not valid")

        return f"with for_({ExpressionSerializingVisitor.serialize(init.target)},{ExpressionSerializingVisitor.serialize(init.expression)},{condition},{ExpressionSerializingVisitor.serialize(update.expression)}):"


def _for_each_block_statement(node):
    variables = []
    arrays = []
    for it in node.iterator:
        variables.append(_ser_exp(it.variable))
        arrays.append(it.array.name)
    return f'with for_each_(({",".join(variables)}),({",".join(arrays)})):'


def _if_block_statement(node):
    condition = ExpressionSerializingVisitor.serialize(node.condition)
    if node.unsafe is True:
        unsafe = ", unsafe=True"
    else:
        unsafe = ""
    return f"with if_({condition}{unsafe}):"


def _strict_timing_block_statement(_):
    return "with strict_timing_():"


def _stream_processing_function(array):
    function = array[0].string_value

    if function == "average":
        if len(array) > 1:
            if array[1].string_value:
                var = array[1].string_value
            else:
                var = _stream_processing_operator(array[1].list_value.values)
        else:
            var = ""
        return f"average({var})"

    if function == "dot":
        if len(array) == 1:
            return "tuple_dot_product()"
        else:
            vector = _stream_processing_operator(array[1].list_value.values)
            return f"dot_product({vector})"

    if function == "vmult":
        vector = _stream_processing_operator(array[1].list_value.values)
        return f"multiply_by({vector})"

    if function == "smult":
        return f"multiply_by({array[1].string_value})"

    if function == "tmult":
        return "tuple_multiply()"

    if function == "conv":
        if len(array) == 2:
            if array[1].string_value:
                mode = f'"{array[1].string_value}"'
            else:
                mode = ""
            return f"tuple_convolution({mode})"
        else:
            vector = _stream_processing_operator(array[2].list_value.values)
            if array[1].string_value:
                mode = f',"{array[1].string_value}"'
            else:
                mode = ""
            return f"convolution({vector}{mode})"

    if function == "fft":
        return "fft()"

    if function == "booleancast":
        return "boolean_to_int()"

    if function == "demod":
        if len(array[2].list_value) > 0:
            cos = _stream_processing_operator(array[2].list_value.values)
        else:
            cos = array[2].string_value
        if len(array[3].list_value) > 0:
            sin = _stream_processing_operator(array[3].list_value.values)
        else:
            sin = array[3].string_value
        return f"demod({array[1].string_value},{cos},{sin})"

    print(f"missing function: {function}")
    return "default_function()"


def _stream_processing_operator(array: List[Value]) -> str:
    operator = array[0].string_value

    if operator == "@macro_input":
        chain = _default_stream_processing_chain(array)
        return f"{chain}.input{array[1].string_value}()"

    if operator == "@array":
        values = []
        for a in array[1:]:
            value = _stream_processing_statement(a)
            values.append(value)
        return f'[{", ".join(values)}]'

    if operator == "@macro_auto_reshape":
        chain = _default_stream_processing_chain(array)
        return f"{chain}.auto_reshape()"

    if operator == "+":
        left = _stream_processing_statement(array[1])
        right = _stream_processing_statement(array[2])
        return f"{left}.add({right})"  # arithmetic stream

    if operator == "-":
        left = _stream_processing_statement(array[1])
        right = _stream_processing_statement(array[2])
        return f"{left}.subtract({right})"  # arithmetic stream

    if operator == "/":
        left = _stream_processing_statement(array[1])
        right = _stream_processing_statement(array[2])
        return f"{left}.divide({right})"  # arithmetic stream

    if operator == "*":
        left = _stream_processing_statement(array[1])
        right = _stream_processing_statement(array[2])
        return f"{left}.multiply({right})"  # arithmetic stream

    if operator == "zip":
        left = _stream_processing_statement(array[1])
        right = _stream_processing_statement(array[2])
        return f"{right}.zip({left})"  # arithmetic stream

    if operator == "take":
        chain = _default_stream_processing_chain(array)
        return f"{chain}.take({array[1].string_value})"

    if operator == "buffer":
        chain = _default_stream_processing_chain(array)
        dims = [dim.string_value for dim in array[1:-1]]
        return f'{chain}.buffer({", ".join(dims)})'

    if operator == "bufferAndSkip":
        chain = _default_stream_processing_chain(array)
        return f"{chain}.buffer_and_skip({array[1].string_value}, {array[2].string_value})"

    if operator == "skip":
        chain = _default_stream_processing_chain(array)
        return f"{chain}.skip({array[1].string_value})"

    if operator == "skipLast":
        chain = _default_stream_processing_chain(array)
        return f"{chain}.skip_last({array[1].string_value})"

    if operator == "histogram":
        chain = _default_stream_processing_chain(array)
        bins = _stream_processing_operator(array[1].list_value.values)
        return f"{chain}.histogram({bins})"

    if operator == "average":
        chain = _default_stream_processing_chain(array)
        return f"{chain}.average()"

    if operator == "flatten":
        chain = _default_stream_processing_chain(array)
        return f"{chain}.flatten()"

    if operator == "map":
        chain = _default_stream_processing_chain(array)
        return f"{chain}.map(FUNCTIONS.{_stream_processing_function(array[1].list_value.values)})"

    if operator == "@re":
        chain = _default_stream_processing_chain(array)
        timestamp_mode = int(array[1].string_value)
        if timestamp_mode == 0:  # values
            return f"{chain}"
        elif timestamp_mode == 1:  # timestamps
            return f"{chain}.timestamps()"
        elif timestamp_mode == 2:  # ValuesAndTimestamps
            return f"{chain}.with_timestamps()"

    if operator == "@macro_adc_trace":
        chain = _default_stream_processing_chain(array)
        return f"{chain}"

    print(f"missing operator: {operator}")
    chain = _default_stream_processing_chain(array)
    return f"{chain}"


def _default_stream_processing_chain(array: List[Value]) -> str:
    last_index = len(array) - 1
    chain = _stream_processing_statement(array[last_index])
    return f"{chain}"


def _stream_processing_statement(node: Union[ListValue, Value]) -> str:
    if len(node.list_value.values) > 0:
        return _stream_processing_operator(node.list_value.values)
    else:
        return node.string_value


def _stream_processing_terminal_statement(node: ListValue):
    last_index = len(node.values) - 1
    chain = _stream_processing_statement(node.values[last_index])
    terminal = node.values[0].string_value
    terminal = "save_all" if terminal == "saveAll" else terminal  # normalize save all
    return f'{chain}.{terminal}("{node.values[1].string_value}")'


def _serialize(node):
    visitor = QuaSerializingVisitor()
    visitor.visit(node)
    return visitor._out_lines()


_blocks = {
    "qm.grpc.qua.QuaProgram": lambda n: "with program() as prog:",
    "qm.grpc.qua.QuaProgramForStatement": _for_block_statement,
    "qm.grpc.qua.QuaProgramForEachStatement": _for_each_block_statement,
    "qm.grpc.qua.QuaProgramIfStatement": _if_block_statement,
    "qm.grpc.qua.QuaProgramStrictTimingStatement": _strict_timing_block_statement,
}

_statements = {
    "qm.grpc.qua.QuaProgramMeasureStatement": _measure_statement,
    "qm.grpc.qua.QuaProgramWaitStatement": _wait_statement,
    "qm.grpc.qua.QuaProgramAssignmentStatement": lambda n: f"assign({ExpressionSerializingVisitor.serialize(n.target)}, "
    f"{ExpressionSerializingVisitor.serialize(n.expression)})",
    "qm.grpc.qua.QuaProgramPauseStatement": lambda n: "pause()",
    "qm.grpc.qua.QuaProgramResetPhaseStatement": lambda n: f'reset_phase("{n.qe.name}")',
    "qm.grpc.qua.QuaProgramUpdateFrequencyStatement": _update_frequency_statement,
    "qm.grpc.qua.QuaProgramAlignStatement": _align_statement,
    "qm.grpc.qua.QuaProgramWaitForTriggerStatement": _wait_for_trigger_statement,
    "qm.grpc.qua.QuaProgramZRotationStatement": _frame_rotation_statement,
    "qm.grpc.qua.QuaProgramRampToZeroStatement": _ramp_to_zero_statement,
    "qm.grpc.qua.QuaProgramResetFrameStatement": _reset_frame_statement,
    "betterproto.lib.google.protobuf.ListValue": _stream_processing_terminal_statement,
    # list value statement is assumed just as stream processing for now
    "qm.grpc.qua.QuaProgramUpdateCorrectionStatement": lambda n: f'update_correction("{n.qe.name}"'
    f",{ExpressionSerializingVisitor.serialize(n.correction.c0)}"
    f",{ExpressionSerializingVisitor.serialize(n.correction.c1)}"
    f",{ExpressionSerializingVisitor.serialize(n.correction.c2)}"
    f",{ExpressionSerializingVisitor.serialize(n.correction.c3)})",
    "qm.grpc.qua.QuaProgramSetDcOffsetStatement": _set_dc_offset_statement,
    "qm.grpc.qua.QuaProgramAdvanceInputStreamStatement": _advance_input_stream_statement,
    "qm.grpc.qua.QuaProgramFastFrameRotationStatement": _fast_frame_rotation_statement,
}

_var_type_dec = {0: "int", 1: "bool", 2: "fixed"}

_nodes_to_ignore = [
    "qm.grpc.qua.QuaProgramScript",
    "qm.grpc.qua.QuaProgramStatementsCollection",
    "qm.grpc.qua.QuaProgramAnyStatement",
    "qm.grpc.qua.QuaProgramAnyScalarExpression",
    "qm.grpc.qua.QuaProgramBinaryExpression",
    "qm.grpc.qua.QuaProgramVarRefExpression",
    "qm.grpc.qua.QuaProgramLiteralExpression",
    "qm.grpc.qua.QuaProgramPlayStatement",
    "qm.grpc.qua_config.QuaConfig",
]

_dont_print = set(list(_blocks.keys()) + list(_statements.keys()) + _nodes_to_ignore)
