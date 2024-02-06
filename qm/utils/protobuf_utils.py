import logging
import dataclasses
from typing import Dict, Union, Iterable

import betterproto

from qm.grpc.general_messages import MessageLevel
from qm.type_hinting.general import DataClassType

LOG_LEVEL_MAP = {
    MessageLevel.Message_LEVEL_ERROR: logging.ERROR,
    MessageLevel.Message_LEVEL_WARNING: logging.WARN,
    MessageLevel.Message_LEVEL_INFO: logging.INFO,
}


def list_fields(node: DataClassType) -> Dict[str, Union[betterproto.Message, Iterable[betterproto.Message]]]:
    fields = dataclasses.fields(
        node
    )  # This type warining is OK, python are idiots and has no builtin type for dataclasses.
    output = {}
    for field in fields:
        field_value = getattr(node, field.name)
        if isinstance(field_value, Iterable) or (
            isinstance(field_value, betterproto.Message) and betterproto.serialized_on_wire(field_value)
        ):
            output[field.name] = field_value
    return output
