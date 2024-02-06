import sys
import types
import logging
import datetime
import traceback
from typing import Any, Dict, Optional

import betterproto
import numpy as np
from marshmallow import ValidationError

from qm.grpc import qua
from qm.grpc.qua import QuaProgram
from qm.program import load_config
from qm.grpc.qua_config import QuaConfig
from qm import Program, DictQuaConfig, version
from qm.program.ConfigBuilder import convert_msg_to_config
from qm.serialization.qua_node_visitor import QuaNodeVisitor
from qm.serialization.qua_serializing_visitor import QuaSerializingVisitor
from qm.exceptions import ConfigValidationException, ConfigSerializationException

SERIALIZATION_VALIDATION_ERROR = "SERIALIZATION VALIDATION ERROR"

LOADED_CONFIG_ERROR = "LOADED CONFIG SERIALIZATION ERROR"

CONFIG_ERROR = "CONFIG SERIALIZATION ERROR"

SERIALIZATION_NOT_COMPLETE = "SERIALIZATION WAS NOT COMPLETE"


logger = logging.getLogger(__name__)


def assert_programs_are_equal(prog1: QuaProgram, prog2: QuaProgram):
    StripLocationVisitor.strip(prog1)
    StripLocationVisitor.strip(prog2)
    RenameStreamVisitor().visit(prog1)
    RenameStreamVisitor().visit(prog2)
    assert prog1.compiler_options == prog2.compiler_options
    assert prog1.config == prog2.config
    assert prog1.dyn_config == prog2.dyn_config
    assert prog1.script.to_dict() == prog2.script.to_dict()
    assert sorted(prog1.result_analysis.model, key=str) == sorted(prog2.result_analysis.model, key=str)


def generate_qua_script(prog: Program, config: Optional[DictQuaConfig] = None) -> str:
    if prog.is_in_scope():
        raise RuntimeError("Can not generate script inside the qua program scope")

    proto_config = None
    if config is not None:
        try:
            proto_config = load_config(config)
        except (ConfigValidationException, ValidationError) as e:
            raise RuntimeError("Can not generate script - bad config") from e
        except AttributeError:
            logger.warning("Could not generate a loaded config. Maybe there is no `QuantumMachinesManager` instance?")

    proto_prog = prog.build(QuaConfig())
    return _generate_qua_script_pb(proto_prog, proto_config, config)


def _generate_qua_script_pb(proto_prog, proto_config: Optional, original_config: Optional):
    extra_info = ""
    serialized_program = ""
    pretty_original_config = None

    if original_config is not None:
        try:
            pretty_original_config = _print_config(original_config)
        except Exception as e:
            trace = traceback.format_exception(*sys.exc_info())
            extra_info = extra_info + _error_string(e, trace, CONFIG_ERROR)
            pretty_original_config = original_config

    pretty_proto_config = None
    if proto_config is not None:
        try:
            normalized_config = convert_msg_to_config(proto_config)
            pretty_proto_config = _print_config(normalized_config)
        except Exception as e:
            trace = traceback.format_exception(*sys.exc_info())
            extra_info = extra_info + _error_string(e, trace, LOADED_CONFIG_ERROR)

    try:
        visitor = QuaSerializingVisitor()
        visitor.visit(proto_prog)
        serialized_program = visitor.out()

        extra_info = extra_info + _validate_program(proto_prog, serialized_program)
    except Exception as e:
        trace = traceback.format_exception(*sys.exc_info())
        extra_info = extra_info + _error_string(e, trace, SERIALIZATION_VALIDATION_ERROR)

    return f"""
# Single QUA script generated at {datetime.datetime.now()}
# QUA library version: {version.__version__}

{serialized_program}
{extra_info if extra_info else ""}
config = {pretty_original_config}

loaded_config = {pretty_proto_config}

"""


def _validate_program(old_prog, serialized_program: str) -> Optional[str]:
    generated_mod = types.ModuleType("gen")
    exec(serialized_program, generated_mod.__dict__)
    new_prog = generated_mod.prog.build(QuaConfig())

    try:
        assert_programs_are_equal(old_prog, new_prog)
        return ""
    except AssertionError:

        new_prog_str = _program_string(new_prog)
        old_prog_str = _program_string(old_prog)
        new_prog_str = new_prog_str.replace("\n", "")
        old_prog_str = old_prog_str.replace("\n", "")
        return f"""

####     {SERIALIZATION_NOT_COMPLETE}     ####
#
#  Original   {old_prog_str}
#  Serialized {new_prog_str}
#
################################################

        """


def _error_string(e: Exception, trace, error_type: str) -> str:
    return f"""

    ####     {error_type}     ####
    #
    #  {str(e)}
    #
    # Trace:
    #   {str(trace)}
    #
    ################################################

            """


def _program_string(prog) -> str:
    """Will create a canonized string representation of the program"""
    strip_location_visitor = StripLocationVisitor()
    strip_location_visitor.visit(prog)
    string = prog.to_json(2)
    return string


def _print_config(config_part: Dict[str, Any], indent_level: int = 1) -> str:
    """Formats a python dictionary into an executable string representation.
    Unlike pretty print, it better supports nested dictionaries. Also, auto converts
    lists into a more compact form.
    Works recursively.
    :param Dict[str, Any] config_part: The dictionary to format

    Args:
        indent_level (int): Internally used by the function to indicate
            the current
    indention
    :returns str: The string representation of the dictionary.
    """
    if indent_level > 100:
        raise ConfigSerializationException("Reached maximum depth of config pretty print")

    config_part_str = ""
    if len(config_part) > 0:
        config_part_str += "{\n"

        for key, value in config_part.items():
            config_part_str += "    " * indent_level + f'"{str(key)}": ' + _value_to_str(indent_level, value)

        if indent_level > 1:
            # add an indentation and go down a line
            config_part_str += "    " * (indent_level - 1) + "},\n"
        else:
            # in root indent level, no need to add a line
            config_part_str += "}"

    else:
        config_part_str = "{},\n"

    return config_part_str


def _value_to_str(indent_level, value):
    # To support numpy types, we convert them to normal python types:
    if type(value).__module__ == np.__name__:
        value = value.tolist()

    is_long_list = isinstance(value, list) and len(value) > 1

    if isinstance(value, dict):
        return _print_config(value, indent_level + 1)
    elif isinstance(value, str):
        return f'"{value}"' + ",\n"
    elif is_long_list and isinstance(value[0], dict):
        temp_str = "[\n"
        for v in value:
            temp_str += "    " * (indent_level + 1) + f"{str(v)},\n"
        temp_str += "    " * indent_level + "],\n"
        return temp_str
    elif is_long_list:
        # replace it with a compact list
        is_single_value = len(set(value)) == 1

        if is_single_value:
            return f"[{value[0]}] * {len(value)}" + ",\n"
        else:
            return f"{_make_compact_string_from_list(value)}" + ",\n"
    else:
        # python basic data types string representation are valid python
        return str(value) + ",\n"


class _Chunk:
    def __init__(self):
        self._data = []
        self._accepts_different = True

    def add(self, element):
        if self._data and element == self._data[-1]:
            self._data.append(element)
            self._accepts_different = False
            return

        if self.accepts_different:
            self._data.append(element)
            return

        raise ValueError("Tried to add number to a chunk that is already uniform")

    @property
    def accepts_different(self):
        return self._accepts_different

    def __str__(self):
        if self.accepts_different:
            return str(self._data)
        return f"[{self._data[0]}] * {len(self._data)}"


def _split_list_to_chunks(list_data):
    curr_chunk = _Chunk()
    chunks = [curr_chunk]
    for idx, curr_item in enumerate(list_data):
        if idx >= 1 and curr_item != list_data[idx - 1]:
            item_equals_next = idx < len(list_data) - 1 and curr_item == list_data[idx + 1]
            if item_equals_next or not curr_chunk.accepts_different:
                curr_chunk = _Chunk()
                chunks.append(curr_chunk)

        curr_chunk.add(curr_item)
    return chunks


def _serialize_chunks(chunks):
    return " + ".join([str(chunk) for chunk in chunks])


def _make_compact_string_from_list(list_data):
    """
    Turns a multi-value list into the most compact string representation of it,
    replacing identical consecutive values by list multiplication.
    """
    chunks = _split_list_to_chunks(list_data)
    return _serialize_chunks(chunks)


class StripLocationVisitor(QuaNodeVisitor):
    """Go over all nodes and if they have a location property, we strip it"""

    def _default_enter(self, node):
        if hasattr(node, "loc"):
            node.loc = "stripped"
        return isinstance(node, betterproto.Message)

    @staticmethod
    def strip(node):
        StripLocationVisitor().visit(node)


class RenameStreamVisitor(QuaNodeVisitor):
    """This cladd standardizes the names of the streams, so when comparing two programs, the names will be the same"""

    def __init__(self):
        self._max_n = 0
        self._old_to_new_map = {}

    def _change_var_name(self, curr_s):
        if curr_s in self._old_to_new_map:
            return self._old_to_new_map[curr_s]
        non_digits = "".join([s for s in curr_s if not s.isdigit()])
        new_name = non_digits + str(self._max_n)
        self._max_n += 1
        self._old_to_new_map[curr_s] = new_name
        return new_name

    def visit_qm_grpc_qua_QuaProgramMeasureStatement(self, node: qua.QuaProgramMeasureStatement):
        if node.stream_as:
            node.stream_as = self._change_var_name(node.stream_as)
        if node.timestamp_label:
            node.timestamp_label = self._change_var_name(node.timestamp_label)

    def visit_qm_grpc_qua_QuaProgramSaveStatement(self, node: qua.QuaProgramSaveStatement):
        if node.tag:
            node.tag = self._change_var_name(node.tag)

    def _default_enter(self, node):
        """This function is for the Value of betterproto. There is a chance we can visit the object directly"""
        if hasattr(node, "string_value") and node.string_value and node.string_value in self._old_to_new_map:
            node.string_value = self._old_to_new_map[node.string_value]
        return isinstance(node, betterproto.Message)
