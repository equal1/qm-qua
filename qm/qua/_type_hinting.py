from typing import TYPE_CHECKING, List, Type, Tuple, Union, TypeVar

import numpy as np
import numpy.typing as npt

from qm.grpc import qua

if TYPE_CHECKING:
    from _dsl import fixed, _Variable, _Expression, _ResultSource  # noqa

MessageExpressionType = qua.QuaProgramAnyScalarExpression
MessageArrayVarType = qua.QuaProgramArrayVarRefExpression
MessageVarType = qua.QuaProgramVarRefExpression
MessageVariableType = Union[MessageArrayVarType, MessageVarType]
MessageVariableOrExpression = Union[MessageExpressionType, MessageVariableType]

ArrayT = TypeVar("ArrayT")
PyArrayType = Union[List[ArrayT], npt.NDArray[ArrayT], Tuple[ArrayT, ...]]

NpTypes = Union[np.floating, np.integer, np.bool_, np.longdouble]

PyIntType = Union[int, np.integer]
PyFloatType = Union[float, np.floating, np.longdouble]
PyNumberType = Union[PyFloatType, PyIntType]
PyNumberArrayType = PyArrayType[PyNumberType]
PyBoolType = Union[bool, np.bool_]

AllPyTypes = Union[PyBoolType, PyNumberType]

QuaExpressionType = Union["_Expression", MessageExpressionType]
QuaVariableType = Union["_Variable", MessageVariableType]

QuaGenericT = TypeVar("QuaGenericT")
QuaGenericType = Union[QuaGenericT, QuaVariableType]

QuaArrayT = TypeVar("QuaArrayT")
QuaArrayType = Union[PyArrayType[QuaArrayT], QuaVariableType]

QuaIntType = QuaGenericType[PyIntType]
QuaBoolType = QuaGenericType[PyBoolType]
QuaFloatType = QuaGenericType[PyFloatType]
QuaNumberType = QuaGenericType[PyNumberType]
QuaNumberArrayType = QuaArrayType[PyNumberType]

AllQuaTypes = Union[QuaNumberType, QuaBoolType, QuaExpressionType]

VariableDeclarationType = Union[Type[int], Type[bool], Type[float], Type["fixed"]]


StreamType = Union[str, "_ResultSource"]
ChirpType = Union[
    Tuple[QuaNumberArrayType, str],
    Tuple[QuaNumberType, str],
    Tuple[QuaNumberArrayType, QuaNumberArrayType, str],
]
AmpValuesType = Tuple[
    MessageExpressionType,
    MessageExpressionType,
    MessageExpressionType,
    MessageExpressionType,
]

MeasurePulseType = Union[str, Tuple[str, AmpValuesType]]
PlayPulseType = Union[MeasurePulseType, qua.QuaProgramRampPulse]

MeasureProcessType = Union[
    "AnalogMeasureProcess.AnalogMeasureProcess",
    "DigitalMeasureProcess.DigitalMeasureProcess",
]
TimeDivisionType = Union[
    "AnalogMeasureProcess.SlicedAnalogTimeDivision",
    "AnalogMeasureProcess.AccumulatedAnalogTimeDivision",
    "AnalogMeasureProcess.MovingWindowAnalogTimeDivision",
]
AnalogProcessTargetType = Union[
    "AnalogMeasureProcess.ScalarProcessTarget",
    "AnalogMeasureProcess.VectorProcessTarget",
]

ForEachValuesType = Union[PyNumberArrayType, Tuple[PyNumberArrayType, ...]]

T = TypeVar("T")
OneOrMore = Union[T, PyArrayType[T]]

E = TypeVar("E")
TypeOrExpression = Union[E, QuaExpressionType]
