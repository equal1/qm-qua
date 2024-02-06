import dataclasses
from typing import List, Optional

from qm.grpc.qua_config import QuaConfig
from qm.program._ResultAnalysis import _ResultAnalysis
from qm.program.StatementsCollection import StatementsCollection
from qm.grpc.qua import (
    QuaProgram,
    QuaProgramType,
    QuaProgramScript,
    QuaResultAnalysis,
    QuaProgramVarDeclaration,
    QuaProgramLiteralExpression,
    QuaProgramStatementsCollection,
)


@dataclasses.dataclass
class ProgramMetadata:
    uses_command_timestamps: bool
    uses_fast_frame_rotation: bool


class Program:
    def __init__(
        self,
        config: Optional[QuaConfig] = None,
        program: Optional[QuaProgram] = None,
    ):
        if program is None:
            program = QuaProgram(
                script=QuaProgramScript(variables=[], body=QuaProgramStatementsCollection(statements=[])),
                result_analysis=QuaResultAnalysis(model=[]),
            )

        self._program = program
        self._qua_config = config
        self._result_analysis = _ResultAnalysis(self._program.result_analysis)
        self._is_in_scope = False
        self._metadata = ProgramMetadata(uses_command_timestamps=False, uses_fast_frame_rotation=False)

    def _declare_var(
        self,
        name: str,
        var_type: QuaProgramType,
        size: int,
        value: Optional[List[QuaProgramLiteralExpression]],
        dim: int,
        is_input_stream: bool,
    ):
        declaration = QuaProgramVarDeclaration(
            name=name,
            type=var_type,
            size=size,
            dim=dim,
            is_input_stream=is_input_stream,
        )

        if value is None:
            pass
        elif type(value) is list:
            for i in value:
                declaration.value.append(i)
        else:
            declaration.value.append(value)
        self._program.script.variables.append(declaration)

    def declare_int(
        self,
        name: str,
        size: int,
        value: Optional[List[QuaProgramLiteralExpression]],
        dim: int,
        is_input_stream: bool,
    ):
        self._declare_var(name, QuaProgramType.INT, size, value, dim, is_input_stream)

    def declare_real(
        self,
        name: str,
        size: int,
        value: Optional[List[QuaProgramLiteralExpression]],
        dim: int,
        is_input_stream: bool,
    ):
        self._declare_var(name, QuaProgramType.REAL, size, value, dim, is_input_stream)

    def declare_bool(
        self,
        name: str,
        size: int,
        value: Optional[List[QuaProgramLiteralExpression]],
        dim: int,
        is_input_stream: bool,
    ):
        self._declare_var(name, QuaProgramType.BOOL, size, value, dim, is_input_stream)

    @property
    def body(self) -> StatementsCollection:
        return StatementsCollection(self._program.script.body)

    @property
    def result_analysis(self) -> _ResultAnalysis:
        return self._result_analysis

    def build(self, config: QuaConfig) -> QuaProgram:
        copy = QuaProgram().from_dict(self._program.to_dict())
        copy.config = QuaConfig().from_dict(config.to_dict())
        return copy

    def set_in_scope(self):
        self._is_in_scope = True

    def set_exit_scope(self):
        self._is_in_scope = False

    def is_in_scope(self) -> bool:
        return self._is_in_scope

    @property
    def metadata(self) -> ProgramMetadata:
        return self._metadata

    def set_metadata(
        self,
        uses_command_timestamps: bool = None,
        uses_fast_frame_rotation: bool = None,
    ):
        if uses_command_timestamps is not None:
            self._metadata.uses_command_timestamps = uses_command_timestamps
        if uses_fast_frame_rotation is not None:
            self.metadata.uses_fast_frame_rotation = uses_fast_frame_rotation
