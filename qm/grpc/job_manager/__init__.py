# Generated by the protocol buffer compiler.  DO NOT EDIT!
# sources: qm/pb/job_manager.proto
# plugin: python-betterproto
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Dict,
    List,
    Optional,
)

import betterproto
import grpclib
from betterproto.grpc.grpclib_server import ServiceBase

from .. import (
    errors as _errors__,
    general_messages as _general_messages__,
)


if TYPE_CHECKING:
    import grpclib.server
    from betterproto.grpc.grpclib_client import MetadataLike
    from grpclib.metadata import Deadline


@dataclass(eq=False, repr=False)
class GetElementCorrectionRequest(betterproto.Message):
    job_id: str = betterproto.string_field(1)
    qe_name: str = betterproto.string_field(2)
    correction: "_general_messages__.Matrix" = betterproto.message_field(3)


@dataclass(eq=False, repr=False)
class GetElementCorrectionResponse(betterproto.Message):
    job_manager_response_header: "JobManagerResponseHeader" = betterproto.message_field(
        1
    )
    correction: "_general_messages__.Matrix" = betterproto.message_field(3)


@dataclass(eq=False, repr=False)
class SetElementCorrectionRequest(betterproto.Message):
    job_id: str = betterproto.string_field(1)
    qe_name: str = betterproto.string_field(2)
    correction: "_general_messages__.Matrix" = betterproto.message_field(3)


@dataclass(eq=False, repr=False)
class SetElementCorrectionResponse(betterproto.Message):
    job_manager_response_header: "JobManagerResponseHeader" = betterproto.message_field(
        1
    )
    correction: "_general_messages__.Matrix" = betterproto.message_field(2)


@dataclass(eq=False, repr=False)
class JobManagerResponseHeader(betterproto.Message):
    success: bool = betterproto.bool_field(1)
    job_id: str = betterproto.string_field(2)
    job_manager_error_type: "_errors__.JobManagerErrorTypes" = betterproto.enum_field(
        10
    )
    job_error_details: "JobErrorDetails" = betterproto.message_field(11)


@dataclass(eq=False, repr=False)
class JobErrorDetails(betterproto.Message):
    job_operation_specific_error_type: "_errors__.JobOperationSpecificErrorTypes" = (
        betterproto.enum_field(1, group="errorType")
    )
    config_query_error_type: "_errors__.ConfigQueryErrorTypes" = betterproto.enum_field(
        2, group="errorType"
    )
    message: str = betterproto.string_field(10)


@dataclass(eq=False, repr=False)
class JobOperationSpecificError(betterproto.Message):
    type: "_errors__.JobOperationSpecificErrorTypes" = betterproto.enum_field(1)
    message: str = betterproto.string_field(2)


@dataclass(eq=False, repr=False)
class InsertInputStreamRequest(betterproto.Message):
    job_id: str = betterproto.string_field(1)
    stream_name: str = betterproto.string_field(2)
    int_stream_data: "IntStreamData" = betterproto.message_field(
        3, group="stream_data_oneof"
    )
    fixed_stream_data: "FixedStreamData" = betterproto.message_field(
        4, group="stream_data_oneof"
    )
    bool_stream_data: "BoolStreamData" = betterproto.message_field(
        5, group="stream_data_oneof"
    )


@dataclass(eq=False, repr=False)
class IntStreamData(betterproto.Message):
    data: List[int] = betterproto.int32_field(1)


@dataclass(eq=False, repr=False)
class FixedStreamData(betterproto.Message):
    data: List[float] = betterproto.double_field(1)


@dataclass(eq=False, repr=False)
class BoolStreamData(betterproto.Message):
    data: List[bool] = betterproto.bool_field(1)


@dataclass(eq=False, repr=False)
class InsertInputStreamResponse(betterproto.Message):
    job_manager_response_header: "JobManagerResponseHeader" = betterproto.message_field(
        1
    )


class JobManagerServiceStub(betterproto.ServiceStub):
    async def get_element_correction(
        self,
        get_element_correction_request: "GetElementCorrectionRequest",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "GetElementCorrectionResponse":
        return await self._unary_unary(
            "/qm.grpc.job_manager.JobManagerService/GetElementCorrection",
            get_element_correction_request,
            GetElementCorrectionResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )

    async def set_element_correction(
        self,
        set_element_correction_request: "SetElementCorrectionRequest",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "SetElementCorrectionResponse":
        return await self._unary_unary(
            "/qm.grpc.job_manager.JobManagerService/SetElementCorrection",
            set_element_correction_request,
            SetElementCorrectionResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )

    async def insert_input_stream(
        self,
        insert_input_stream_request: "InsertInputStreamRequest",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "InsertInputStreamResponse":
        return await self._unary_unary(
            "/qm.grpc.job_manager.JobManagerService/InsertInputStream",
            insert_input_stream_request,
            InsertInputStreamResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )


class JobManagerServiceBase(ServiceBase):
    async def get_element_correction(
        self, get_element_correction_request: "GetElementCorrectionRequest"
    ) -> "GetElementCorrectionResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def set_element_correction(
        self, set_element_correction_request: "SetElementCorrectionRequest"
    ) -> "SetElementCorrectionResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def insert_input_stream(
        self, insert_input_stream_request: "InsertInputStreamRequest"
    ) -> "InsertInputStreamResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def __rpc_get_element_correction(
        self,
        stream: "grpclib.server.Stream[GetElementCorrectionRequest, GetElementCorrectionResponse]",
    ) -> None:
        request = await stream.recv_message()
        response = await self.get_element_correction(request)
        await stream.send_message(response)

    async def __rpc_set_element_correction(
        self,
        stream: "grpclib.server.Stream[SetElementCorrectionRequest, SetElementCorrectionResponse]",
    ) -> None:
        request = await stream.recv_message()
        response = await self.set_element_correction(request)
        await stream.send_message(response)

    async def __rpc_insert_input_stream(
        self,
        stream: "grpclib.server.Stream[InsertInputStreamRequest, InsertInputStreamResponse]",
    ) -> None:
        request = await stream.recv_message()
        response = await self.insert_input_stream(request)
        await stream.send_message(response)

    def __mapping__(self) -> Dict[str, grpclib.const.Handler]:
        return {
            "/qm.grpc.job_manager.JobManagerService/GetElementCorrection": grpclib.const.Handler(
                self.__rpc_get_element_correction,
                grpclib.const.Cardinality.UNARY_UNARY,
                GetElementCorrectionRequest,
                GetElementCorrectionResponse,
            ),
            "/qm.grpc.job_manager.JobManagerService/SetElementCorrection": grpclib.const.Handler(
                self.__rpc_set_element_correction,
                grpclib.const.Cardinality.UNARY_UNARY,
                SetElementCorrectionRequest,
                SetElementCorrectionResponse,
            ),
            "/qm.grpc.job_manager.JobManagerService/InsertInputStream": grpclib.const.Handler(
                self.__rpc_insert_input_stream,
                grpclib.const.Cardinality.UNARY_UNARY,
                InsertInputStreamRequest,
                InsertInputStreamResponse,
            ),
        }
