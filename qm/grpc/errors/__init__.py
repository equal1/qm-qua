# Generated by the protocol buffer compiler.  DO NOT EDIT!
# sources: qm/pb/errors.proto
# plugin: python-betterproto
from dataclasses import dataclass

import betterproto


class JobManagerErrorTypes(betterproto.Enum):
    JobManagerUnspecifiedError = 0
    MissingJobError = 1000
    InvalidJobExecutionStatusError = 1001
    InvalidOperationOnSimulatorJobError = 1002
    InvalidOperationOnRealJobError = 1003
    JobOperationSpecificError = 1004
    ConfigQueryError = 1005
    UnknownInputStreamError = 1006


class JobOperationSpecificErrorTypes(betterproto.Enum):
    JobOperationUnspecifiedError = 0
    SingleInputElementError = 3000
    InvalidCorrectionMatrixError = 3001
    ElementWithoutIntermediateFrequencyError = 3002
    InvalidDigitalInputThresholdError = 3003
    InvalidDigitalInputDeadtimeError = 3004
    InvalidDigitalInputPolarityError = 3005


class ConfigQueryErrorTypes(betterproto.Enum):
    ConfigQueryUnspecifiedError = 0
    MissingControllerError = 4000
    MissingElementError = 4001
    MissingDigitalInputError = 4002
