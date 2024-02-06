import logging
from typing import Tuple, AsyncIterator

from qm.simulate import interface
from qm.api.base_api import BaseApi
from qm.utils.async_utils import run_async
from qm.program import Program, load_config
from qm.utils.protobuf_utils import LOG_LEVEL_MAP
from qm.simulate.interface import SimulationConfig
from qm.type_hinting.config_types import DictQuaConfig
from qm.api.models.server_details import ConnectionDetails
from qm.exceptions import QMSimulationError, FailedToExecuteJobException
from qm.api.models.compiler import CompilerOptionArguments, _get_request_compiler_options
from qm.grpc.results_analyser import SimulatorSamplesResponse, PullSimulatorSamplesRequest
from qm.grpc.frontend import (
    FrontendStub,
    DensityMatrix,
    InterOpxAddress,
    InterOpxChannel,
    SimulationRequest,
    InterOpxConnection,
    SimulatedResponsePart,
    ExecutionRequestSimulate,
    GetSimulatedQuantumStateRequest,
    InterOpxConnectionAddressToAddress,
    InterOpxConnectionChannelToChannel,
)

logger = logging.getLogger(__name__)


class SimulationApi(BaseApi):
    def __init__(self, connection_details: ConnectionDetails):
        super().__init__(connection_details)
        self._stub = FrontendStub(self._channel)
        self._timeout = None

    def simulate(
        self,
        config: DictQuaConfig,
        program: Program,
        simulate: SimulationConfig,
        compiler_options: CompilerOptionArguments,
    ) -> Tuple[str, SimulatedResponsePart]:
        if type(program) is not Program:
            raise Exception("program argument must be of type qm.program.Program")

        request = SimulationRequest()
        msg_config = load_config(config)
        request.config = msg_config

        if type(simulate) is SimulationConfig:
            request.simulate = ExecutionRequestSimulate(
                duration=simulate.duration,
                include_analog_waveforms=simulate.include_analog_waveforms,
                include_digital_waveforms=simulate.include_digital_waveforms,
                extra_processing_timeout_ms=simulate.extraProcessingTimeoutInMs,
            )
            request = simulate.update_simulate_request(request)

            for connection in simulate.controller_connections:
                if not isinstance(connection.source, type(connection.target)):
                    raise Exception(
                        f"Unsupported InterOpx connection. Source is "
                        f"{type(connection.source).__name__} but target is "
                        f"{type(connection.target).__name__}"
                    )

                if isinstance(connection.source, interface.InterOpxAddress) and isinstance(
                    connection.target, interface.InterOpxAddress
                ):
                    con = InterOpxConnection(
                        address_to_address=InterOpxConnectionAddressToAddress(
                            source=InterOpxAddress(
                                controller=connection.source.controller,
                                left=connection.source.is_left_connection,
                            ),
                            target=InterOpxAddress(
                                controller=connection.target.controller,
                                left=connection.target.is_left_connection,
                            ),
                        )
                    )
                elif isinstance(connection.source, interface.InterOpxChannel) and isinstance(
                    connection.target, interface.InterOpxChannel
                ):
                    con = InterOpxConnection(
                        channel_to_channel=InterOpxConnectionChannelToChannel(
                            source=InterOpxChannel(
                                controller=connection.source.controller,
                                channel_number=connection.source.channel_number,
                            ),
                            target=InterOpxChannel(
                                controller=connection.target.controller,
                                channel_number=connection.target.channel_number,
                            ),
                        )
                    )
                else:
                    raise Exception(
                        f"Unsupported InterOpx connection. Source is "
                        f"{type(connection.source).__name__}. Supported types are "
                        f"InterOpxAddress "
                        f"or InterOpxChannel"
                    )

                request.controller_connections.append(con)

        request.high_level_program = program.build(msg_config)
        request.high_level_program.compiler_options = _get_request_compiler_options(compiler_options)

        logger.info("Simulating program")

        response = run_async(self._stub.simulate(request, timeout=self._timeout))

        messages = [(LOG_LEVEL_MAP[msg.level], msg.message) for msg in response.messages]

        config_messages = [(LOG_LEVEL_MAP[msg.level], msg.message) for msg in response.config_validation_errors]

        job_id = response.job_id

        for lvl, msg in messages:
            logger.log(lvl, msg)

        for lvl, msg in config_messages:
            logger.log(lvl, msg)

        if not response.success:
            logger.error("Job " + job_id + " failed. Failed to execute program.")
            for error in response.simulated.errors:
                logger.error(f"Simulation error: {error}")
            raise FailedToExecuteJobException(job_id)

        return job_id, response.simulated

    def get_simulated_quantum_state(self, job_id: str) -> DensityMatrix:
        request = GetSimulatedQuantumStateRequest(job_id=job_id)
        response = run_async(self._stub.get_simulated_quantum_state(request, timeout=self._timeout))

        if response.ok:
            return response.state

        raise QMSimulationError("Error while pulling quantum state")

    def pull_simulator_samples(
        self, job_id: str, include_analog: bool, include_digital: bool
    ) -> AsyncIterator[SimulatorSamplesResponse]:
        request = PullSimulatorSamplesRequest(
            job_id=job_id,
            include_analog=include_analog,
            include_digital=include_digital,
            include_all_connections=True,
        )

        return self._stub.pull_simulator_samples(request)
