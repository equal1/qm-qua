import betterproto

from qm.grpc import qua
from qm.exceptions import QmQuaException
from qm.serialization.qua_node_visitor import QuaNodeVisitor


class ExpressionSerializingVisitor(QuaNodeVisitor):
    def __init__(self) -> None:
        self._out = ""
        super().__init__()

    def _default_visit(self, node):
        type_fullname = f"{type(node).__module__}.{type(node).__name__}"
        print(f"missing expression: {type_fullname}")
        super()._default_visit(node)

    def visit_qm_grpc_qua_QuaProgramLibFunctionExpression(self, node: qua.QuaProgramLibFunctionExpression):
        if node.library_name == "random":
            args = [ExpressionSerializingVisitor.serialize(arg) for arg in node.arguments]
            self._out = f"call_library_function('{node.library_name}', '{node.function_name}', [{','.join(args)}])"
        else:
            library_name = {
                "util": "Util",
                "math": "Math",
                "cast": "Cast",
            }.get(node.library_name, None)
            function_name = {
                "cond": "cond",
                "unsafe_cast_fixed": "unsafe_cast_fixed",
                "unsafe_cast_bool": "unsafe_cast_bool",
                "unsafe_cast_int": "unsafe_cast_int",
                "to_int": "to_int",
                "to_bool": "to_bool",
                "to_fixed": "to_fixed",
                "mul_fixed_by_int": "mul_fixed_by_int",
                "mul_int_by_fixed": "mul_int_by_fixed",
                "log": "log",
                "pow": "pow",
                "div": "div",
                "exp": "exp",
                "pow2": "pow2",
                "ln": "ln",
                "log2": "log2",
                "log10": "log10",
                "sqrt": "sqrt",
                "inv_sqrt": "inv_sqrt",
                "inv": "inv",
                "MSB": "msb",
                "elu": "elu",
                "aelu": "aelu",
                "selu": "selu",
                "relu": "relu",
                "plrelu": "plrelu",
                "lrelu": "lrelu",
                "sin2pi": "sin2pi",
                "cos2pi": "cos2pi",
                "abs": "abs",
                "sin": "sin",
                "cos": "cos",
                "sum": "sum",
                "max": "max",
                "min": "min",
                "argmax": "argmax",
                "argmin": "argmin",
                "dot": "dot",
            }.get(node.function_name, None)
            if library_name is None:
                raise Exception(f"Unsupported library name {node.library_name}")
            if function_name is None:
                raise Exception(f"Unsupported function name {node.function_name}")

            args = [ExpressionSerializingVisitor.serialize(arg) for arg in node.arguments]

            self._out = f"{library_name}.{function_name}({','.join(args)})"

    def visit_qm_grpc_qua_QuaProgramLibFunctionExpressionArgument(
        self, node: qua.QuaProgramLibFunctionExpressionArgument
    ):
        name, value = betterproto.which_one_of(node, "argument_oneof")
        if value is not None and name in ("scalar", "array"):
            self._out = ExpressionSerializingVisitor.serialize(value)
        else:
            raise QmQuaException(f"Unknown library function argument {name}")

    def visit_qm_grpc_qua_QuaProgramVarRefExpression(self, node: qua.QuaProgramVarRefExpression):
        self._out = node.name if node.name else f"IO{node.io_number}"

    def visit_qm_grpc_qua_QuaProgramArrayVarRefExpression(self, node):
        self._out = node.name

    def visit_qm_grpc_qua_QuaProgramArrayCellRefExpression(self, node):
        var = ExpressionSerializingVisitor.serialize(node.array_var)
        index = ExpressionSerializingVisitor.serialize(node.index)
        self._out = f"{var}[{index}]"

    def visit_qm_grpc_qua_QuaProgramArrayLengthExpression(self, node):
        self._out = f"{node.array.name}.length()"

    def visit_qm_grpc_qua_QuaProgramLiteralExpression(self, node):
        self._out = node.value

    def visit_qm_grpc_qua_QuaProgramAssignmentStatementTarget(self, node):
        super()._default_visit(node)

    def visit_qm_grpc_qua_QuaProgramRampPulse(self, node):
        super()._default_visit(node)

    def visit_qm_grpc_qua_QuaProgramMeasureProcess(self, node):
        super()._default_visit(node)

    def visit_qm_grpc_qua_QuaProgramAnalogMeasureProcess(self, node):
        super()._default_visit(node)

    def visit_qm_grpc_qua_QuaProgramAnalogMeasureProcessDemodIntegration(
        self, node: qua.QuaProgramAnalogMeasureProcessDemodIntegration
    ):
        name = node.integration.name
        output = node.element_output
        target_name, target_value = betterproto.which_one_of(node.target, "processTarget")

        if target_name == "scalar_process":
            target = ExpressionSerializingVisitor.serialize(target_value)
            self._out = f'demod.full("{name}", {target}, "{output}")'
        elif target_name == "vector_process":
            target_value: qua.QuaProgramAnalogProcessTargetVectorProcessTarget
            target = ExpressionSerializingVisitor.serialize(target_value.array)

            time_name, time_value = betterproto.which_one_of(target_value.time_division, "timeDivision")
            if time_name == "sliced":
                self._out = f'demod.sliced("{name}", {target}, {time_value.samples_per_chunk}, "{output}")'
            elif time_name == "accumulated":
                self._out = f'demod.accumulated("{name}", {target}, {time_value.samples_per_chunk}, "{output}")'
            elif time_name == "moving_window":
                self._out = f'demod.moving_window("{name}", {target}, {time_value.samples_per_chunk}, {time_value.chunks_per_window}, "{output}")'
            else:
                raise Exception(f"Unsupported analog process target {target_name}")
        else:
            raise Exception(f"Unsupported analog process target {target_name}")

    def visit_qm_grpc_qua_QuaProgramAnalogMeasureProcessBareIntegration(self, node):
        name = node.integration.name
        output = node.element_output
        target_name, target_value = betterproto.which_one_of(node.target, "processTarget")

        if target_name == "scalar_process":
            target = ExpressionSerializingVisitor.serialize(target_value)
            self._out = f'integration.full("{name}", {target}, "{output}")'
        elif target_name == "vector_process":
            target = ExpressionSerializingVisitor.serialize(target_value.array)

            time_name, time_value = betterproto.which_one_of(target_value.time_division, "timeDivision")
            if time_name == "sliced":
                self._out = f'integration.sliced("{name}", {target}, {time_value.samples_per_chunk}, "{output}")'
            elif time_name == "accumulated":
                self._out = f'integration.accumulated("{name}", {target}, {time_value.samples_per_chunk}, "{output}")'
            elif time_name == "moving_window":
                self._out = f'integration.moving_window("{name}", {target}, {time_value.samples_per_chunk}, {time_value.chunks_per_window}, "{output}")'
            else:
                raise Exception(f"Unsupported analog process target {target_name}")
        else:
            raise Exception(f"Unsupported analog process target {target_name}")

    def visit_qm_grpc_qua_QuaProgramAnalogMeasureProcessDualDemodIntegration(
        self, node: qua.QuaProgramAnalogMeasureProcessDualDemodIntegration
    ):
        name1 = node.integration1.name
        name2 = node.integration2.name
        output1 = node.element_output1
        output2 = node.element_output2
        target_name, target_value = betterproto.which_one_of(node.target, "processTarget")

        if target_name == "scalar_process":
            target = ExpressionSerializingVisitor.serialize(target_value)
            self._out = f'dual_demod.full("{name1}", "{output1}", "{name2}", "{output2}", {target})'
        elif target_name == "vector_process":
            target = ExpressionSerializingVisitor.serialize(target_value.array)

            time_name, time_value = betterproto.which_one_of(target_value.time_division, "timeDivision")
            if time_name == "sliced":
                self._out = f'dual_demod.sliced("{name1}", "{output1}", "{name2}", "{output2}", {time_value.samples_per_chunk}, {target})'
            elif time_name == "accumulated":
                self._out = f'dual_demod.accumulated("{name1}", "{output1}", "{name2}", "{output2}", {time_value.samples_per_chunk}, {target})'
            elif time_name == "moving_window":
                self._out = f'dual_demod.moving_window("{name1}", "{output1}", "{name2}", "{output2}", {time_value.samples_per_chunk}, {time_value.chunks_per_window}, {target})'
            else:
                raise Exception(f"Unsupported analog process target {time_name}")
        else:
            raise Exception(f"Unsupported analog process target {target_name}")

    def visit_qm_grpc_qua_QuaProgramAnalogMeasureProcessDualBareIntegration(self, node):
        name1 = node.integration1.name
        name2 = node.integration2.name
        output1 = node.element_output1
        output2 = node.element_output2
        target_name, target_value = betterproto.which_one_of(node.target, "processTarget")

        if target_name == "scalar_process":
            target = ExpressionSerializingVisitor.serialize(target_value)
            self._out = f'dual_integration.full("{name1}", "{output1}", "{name2}", "{output2}", {target})'
        elif target_name == "vector_process":
            target = ExpressionSerializingVisitor.serialize(target_value.array)

            time_name, time_value = betterproto.which_one_of(target_value.time_division, "timeDivision")
            if time_name == "sliced":
                self._out = f'dual_integration.sliced("{name1}", "{output1}", "{name2}", "{output2}", {time_value.samples_per_chunk}, {target})'
            elif time_name == "accumulated":
                self._out = f'dual_integration.accumulated("{name1}", "{output1}", "{name2}", "{output2}", {time_value.samples_per_chunk}, {target})'
            elif time_name == "moving_window":
                self._out = f'dual_integration.moving_window("{name1}", "{output1}", "{name2}", "{output2}", {time_value.samples_per_chunk}, {time_value.chunks_per_window}, {target})'
            else:
                raise Exception(f"Unsupported analog process target {time_name}")
        else:
            raise Exception(f"Unsupported analog process target {target_name}")

    def visit_qm_grpc_qua_QuaProgramAnalogMeasureProcessRawTimeTagging(
        self, node: qua.QuaProgramAnalogMeasureProcessRawTimeTagging
    ):
        target = ExpressionSerializingVisitor.serialize(node.target)
        target_len = ExpressionSerializingVisitor.serialize(node.target_len)
        max_time = node.max_time
        element_output = node.element_output
        self._out = f'time_tagging.analog({target}, {max_time}, {target_len}, "{element_output}")'

    def visit_qm_grpc_qua_QuaProgramAnalogMeasureProcessHighResTimeTagging(self, node):
        target = ExpressionSerializingVisitor.serialize(node.target)
        target_len = ExpressionSerializingVisitor.serialize(node.target_len)
        max_time = node.max_time
        element_output = node.element_output
        self._out = f'time_tagging.high_res({target}, {max_time}, {target_len}, "{element_output}")'

    def visit_qm_grpc_qua_QuaProgramDigitalMeasureProcess(self, node):
        super()._default_visit(node)

    def visit_qm_grpc_qua_QuaProgramDigitalMeasureProcessCounting(self, node):
        element_outputs = []
        for element_output in node.element_outputs:
            element_outputs.append(f'"{element_output}"')
        element_outputs_str = ",".join(element_outputs)
        target = ExpressionSerializingVisitor.serialize(node.target)
        max_time = node.max_time
        self._out = f"counting.digital({target}, {max_time}, ({element_outputs_str}))"

    def visit_qm_grpc_qua_QuaProgramDigitalMeasureProcessRawTimeTagging(self, node):
        target = ExpressionSerializingVisitor.serialize(node.target)
        target_len = ExpressionSerializingVisitor.serialize(node.target_len)
        max_time = node.max_time
        element_output = node.element_output
        self._out = f'time_tagging.digital({target}, {max_time}, {target_len}, "{element_output}")'

    def visit_qm_grpc_qua_QuaProgramAnalogProcessTargetScalarProcessTarget(self, node):
        super()._default_visit(node)

    def visit_qm_grpc_qua_QuaProgramAnalogProcessTargetTimeDivision(self, node):
        super()._default_visit(node)

    def visit_qm_grpc_qua_QuaProgramAnyScalarExpression(self, node):
        super()._default_visit(node)

    def visit_qm_grpc_qua_QuaProgramSaveStatementSource(self, node):
        super()._default_visit(node)

    def visit_qm_grpc_qua_QuaProgramBinaryExpression(self, node):
        left = ExpressionSerializingVisitor.serialize(node.left)
        right = ExpressionSerializingVisitor.serialize(node.right)
        sop = node.op
        mapping = {
            qua.QuaProgramBinaryExpressionBinaryOperator.ADD: "+",
            qua.QuaProgramBinaryExpressionBinaryOperator.SUB: "-",
            qua.QuaProgramBinaryExpressionBinaryOperator.GT: ">",
            qua.QuaProgramBinaryExpressionBinaryOperator.LT: "<",
            qua.QuaProgramBinaryExpressionBinaryOperator.LET: "<=",
            qua.QuaProgramBinaryExpressionBinaryOperator.GET: ">=",
            qua.QuaProgramBinaryExpressionBinaryOperator.EQ: "==",
            qua.QuaProgramBinaryExpressionBinaryOperator.MULT: "*",
            qua.QuaProgramBinaryExpressionBinaryOperator.DIV: "/",
            qua.QuaProgramBinaryExpressionBinaryOperator.OR: "|",
            qua.QuaProgramBinaryExpressionBinaryOperator.AND: "&",
            qua.QuaProgramBinaryExpressionBinaryOperator.XOR: "^",
            qua.QuaProgramBinaryExpressionBinaryOperator.SHL: "<<",
            qua.QuaProgramBinaryExpressionBinaryOperator.SHR: ">>",
        }
        if sop in mapping:
            op = mapping[sop]
        else:
            raise Exception(f"Unsupported operator {sop}")
        self._out = f"({left}{op}{right})"

    @staticmethod
    def serialize(node) -> str:
        visitor = ExpressionSerializingVisitor()
        visitor.visit(node)
        return visitor._out
