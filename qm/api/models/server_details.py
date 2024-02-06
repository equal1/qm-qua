import ssl
import warnings
import dataclasses
from typing import Dict, Optional

from qm.utils import deprecation_message
from qm.api.models.info import QuaMachineInfo
from qm.api.models.debug_data import DebugData
from qm.api.models.capabilities import ServerCapabilities

MAX_MESSAGE_SIZE = 1024 * 1024 * 100  # 100 mb in bytes
BASE_TIMEOUT = 60


@dataclasses.dataclass
class ConnectionDetails:
    host: str
    port: int
    user_token: Optional[str]
    ssl_context: Optional[ssl.SSLContext]
    max_message_size: int = dataclasses.field(default=MAX_MESSAGE_SIZE)
    headers: Dict[str, str] = dataclasses.field(default_factory=dict)
    timeout: float = dataclasses.field(default=BASE_TIMEOUT)
    debug_data: Optional[DebugData] = dataclasses.field(default=None)


@dataclasses.dataclass
class ServerDetails:
    port: int
    host: str
    server_version: str
    connection_details: ConnectionDetails

    # does it implement the QUA service
    qua_implementation: Optional[QuaMachineInfo]
    capabilities: ServerCapabilities = dataclasses.field(default_factory=ServerCapabilities.build)

    @property
    def qop_version(self) -> str:
        warnings.warn(
            deprecation_message(
                method="ServerDetails.qop_version",
                deprecated_in="1.1.4",
                removed_in="1.2.0",
                details="Use ServerDetails.server_version instead.",
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        return self.server_version

    def __post_init__(self) -> None:
        self.capabilities = ServerCapabilities.build(qua_implementation=self.qua_implementation)
