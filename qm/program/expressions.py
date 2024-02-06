from typing import Union, Optional

import qm.grpc.qua as _qua
from qm._loc import _get_loc
from qm.exceptions import QmQuaException

_ScalarExpressionType = _qua.QuaProgramAnyScalarExpression
_VariableRefType = _qua.QuaProgramVarRefExpression


def var(name: str) -> _VariableRefType:
    """A reference to a variable

    Args:
        name

    Returns:

    """
    exp = _qua.QuaProgramVarRefExpression(name=name, loc=_get_loc())
    return exp


def binary(left: _ScalarExpressionType, sop: str, right: _ScalarExpressionType) -> _ScalarExpressionType:
    """A binary operation

    Args:
        left
        sop
        right

    Returns:

    """
    if sop == "+":
        op = _qua.QuaProgramBinaryExpressionBinaryOperator.ADD
    elif sop == "-":
        op = _qua.QuaProgramBinaryExpressionBinaryOperator.SUB
    elif sop == ">":
        op = _qua.QuaProgramBinaryExpressionBinaryOperator.GT
    elif sop == "<":
        op = _qua.QuaProgramBinaryExpressionBinaryOperator.LT
    elif sop == "<=":
        op = _qua.QuaProgramBinaryExpressionBinaryOperator.LET
    elif sop == ">=":
        op = _qua.QuaProgramBinaryExpressionBinaryOperator.GET
    elif sop == "==":
        op = _qua.QuaProgramBinaryExpressionBinaryOperator.EQ
    elif sop == "*":
        op = _qua.QuaProgramBinaryExpressionBinaryOperator.MULT
    elif sop == "/":
        op = _qua.QuaProgramBinaryExpressionBinaryOperator.DIV
    elif sop == "|":
        op = _qua.QuaProgramBinaryExpressionBinaryOperator.OR
    elif sop == "&":
        op = _qua.QuaProgramBinaryExpressionBinaryOperator.AND
    elif sop == "^":
        op = _qua.QuaProgramBinaryExpressionBinaryOperator.XOR
    elif sop == "<<":
        op = _qua.QuaProgramBinaryExpressionBinaryOperator.SHL
    elif sop == ">>":
        op = _qua.QuaProgramBinaryExpressionBinaryOperator.SHR
    else:
        raise QmQuaException("Unsupported operator " + sop)

    exp = _qua.QuaProgramAnyScalarExpression(
        binary_operation=_qua.QuaProgramBinaryExpression(loc=_get_loc(), left=left, right=right, op=op)
    )
    return exp


def literal_int(value: int) -> _ScalarExpressionType:
    exp = _qua.QuaProgramAnyScalarExpression(
        literal=_qua.QuaProgramLiteralExpression(value=str(value), type=_qua.QuaProgramType.INT, loc=_get_loc())
    )
    return exp


def literal_bool(value: bool) -> _ScalarExpressionType:
    exp = _qua.QuaProgramAnyScalarExpression(
        literal=_qua.QuaProgramLiteralExpression(value=str(value), type=_qua.QuaProgramType.BOOL, loc=_get_loc())
    )
    return exp


def literal_real(value: float) -> _ScalarExpressionType:
    exp = _qua.QuaProgramAnyScalarExpression(
        literal=_qua.QuaProgramLiteralExpression(value=str(value), type=_qua.QuaProgramType.REAL, loc=_get_loc())
    )
    return exp


def io1() -> _ScalarExpressionType:
    exp = _qua.QuaProgramAnyScalarExpression(variable=_qua.QuaProgramVarRefExpression(io_number=1, loc=_get_loc()))
    return exp


def io2() -> _ScalarExpressionType:
    exp = _qua.QuaProgramAnyScalarExpression(variable=_qua.QuaProgramVarRefExpression(io_number=2, loc=_get_loc()))
    return exp


def array(
    value: Union[_qua.QuaProgramArrayVarRefExpression, _ScalarExpressionType],
    index_exp: Optional[_ScalarExpressionType],
) -> Union[_qua.QuaProgramArrayVarRefExpression, _ScalarExpressionType]:
    if index_exp is None:
        return value
    else:
        loc = _get_loc()
        value.loc = loc
        exp = _qua.QuaProgramAnyScalarExpression(
            array_cell=_qua.QuaProgramArrayCellRefExpression(array_var=value, index=index_exp, loc=loc)
        )
        return exp


def var_ref(value: str, index_exp: Optional[_ScalarExpressionType]) -> _ScalarExpressionType:
    exp = _qua.QuaProgramAnyScalarExpression()

    loc = _get_loc()
    if index_exp is None:
        exp.variable = _qua.QuaProgramVarRefExpression(name=value, loc=loc)
    else:
        exp.array_cell = _qua.QuaProgramArrayCellRefExpression(
            array_var=_qua.QuaProgramArrayVarRefExpression(name=value, loc=loc),
            index=index_exp,
            loc=loc,
        )
    return exp


def lib_func(
    lib_name: str,
    func_name: str,
    *args: Union[_ScalarExpressionType, _qua.QuaProgramArrayVarRefExpression],
) -> _ScalarExpressionType:
    exp = _qua.QuaProgramAnyScalarExpression(
        lib_function=_qua.QuaProgramLibFunctionExpression(
            loc=_get_loc(), function_name=func_name, library_name=lib_name
        )
    )

    for arg in args:
        if isinstance(arg, _qua.QuaProgramArrayVarRefExpression):
            element = _qua.QuaProgramLibFunctionExpressionArgument(array=arg)
            exp.lib_function.arguments.append(element)
        else:
            element = _qua.QuaProgramLibFunctionExpressionArgument(scalar=arg)
            exp.lib_function.arguments.append(element)

    return exp
