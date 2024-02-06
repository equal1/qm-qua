# Generated by the protocol buffer compiler.  DO NOT EDIT!
# sources: qm/pb/qm_manager.proto
# plugin: python-betterproto
from dataclasses import dataclass
from typing import List

import betterproto

from .. import (
    general_messages as _general_messages__,
    qua_config as _qua_config__,
)


@dataclass(eq=False, repr=False)
class OpenQuantumMachineRequest(betterproto.Message):
    config: "_qua_config__.QuaConfig" = betterproto.message_field(1)
    never: bool = betterproto.bool_field(2, group="oneOfCloseOtherMachines")
    always: bool = betterproto.bool_field(3, group="oneOfCloseOtherMachines")
    if_needed: bool = betterproto.bool_field(4, group="oneOfCloseOtherMachines")


@dataclass(eq=False, repr=False)
class OpenQuantumMachineResponse(betterproto.Message):
    machine_id: str = betterproto.string_field(1)
    success: bool = betterproto.bool_field(2)
    config_validation_errors: List[
        "ConfigValidationMessage"
    ] = betterproto.message_field(3)
    physical_validation_errors: List[
        "PhysicalValidationMessage"
    ] = betterproto.message_field(4)
    open_qm_warnings: List["OpenQmWarning"] = betterproto.message_field(5)


@dataclass(eq=False, repr=False)
class CloseQuantumMachineRequest(betterproto.Message):
    machine_id: str = betterproto.string_field(1)


@dataclass(eq=False, repr=False)
class CloseQuantumMachineResponse(betterproto.Message):
    success: bool = betterproto.bool_field(1)
    errors: List["_general_messages__.ErrorMessage"] = betterproto.message_field(2)


@dataclass(eq=False, repr=False)
class GetQuantumMachineRequest(betterproto.Message):
    machine_id: str = betterproto.string_field(1)


@dataclass(eq=False, repr=False)
class GetQuantumMachineResponse(betterproto.Message):
    machine_id: str = betterproto.string_field(1)
    config: "_qua_config__.QuaConfig" = betterproto.message_field(2)
    success: bool = betterproto.bool_field(3)
    errors: List["_general_messages__.ErrorMessage"] = betterproto.message_field(4)


@dataclass(eq=False, repr=False)
class GetRunningJobRequest(betterproto.Message):
    machine_id: str = betterproto.string_field(1)


@dataclass(eq=False, repr=False)
class GetRunningJobResponse(betterproto.Message):
    machine_id: str = betterproto.string_field(1)
    job_id: str = betterproto.string_field(2)


@dataclass(eq=False, repr=False)
class ListOpenQuantumMachinesResponse(betterproto.Message):
    machine_i_ds: List[str] = betterproto.string_field(1)


@dataclass(eq=False, repr=False)
class CloseAllQuantumMachinesResponse(betterproto.Message):
    success: bool = betterproto.bool_field(1)
    errors: List["_general_messages__.ErrorMessage"] = betterproto.message_field(2)


@dataclass(eq=False, repr=False)
class GetControllersResponse(betterproto.Message):
    controllers: List["Controller"] = betterproto.message_field(1)


@dataclass(eq=False, repr=False)
class Controller(betterproto.Message):
    name: str = betterproto.string_field(1)


@dataclass(eq=False, repr=False)
class ConfigValidationMessage(betterproto.Message):
    message: str = betterproto.string_field(1)
    group: str = betterproto.string_field(2)
    path: str = betterproto.string_field(3)
    level: "_general_messages__.MessageLevel" = betterproto.enum_field(4)


@dataclass(eq=False, repr=False)
class PhysicalValidationMessage(betterproto.Message):
    message: str = betterproto.string_field(1)
    group: str = betterproto.string_field(2)
    path: str = betterproto.string_field(3)
    level: "_general_messages__.MessageLevel" = betterproto.enum_field(4)


@dataclass(eq=False, repr=False)
class OpenQmWarning(betterproto.Message):
    code: int = betterproto.int32_field(1)
    message: str = betterproto.string_field(2)