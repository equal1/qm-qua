import re
import logging
from typing import Dict, Tuple

import httpx
from betterproto.lib.google.protobuf import Empty

logger = logging.getLogger(__name__)


class QmRedirectionError(ValueError):
    pass


async def send_redirection_check(host: str, port: int, headers: Dict[str, str], timeout: float) -> Tuple[str, int]:
    async with httpx.AsyncClient(http2=True, follow_redirects=False, http1=False, timeout=timeout) as client:
        extended_headers = {"content-type": "application/grpc", "te": "trailers", **headers}
        response = await client.post(f"http://{host}:{port}", headers=extended_headers, content=bytes(Empty()))

        if response.status_code != 302:
            return host, port

        location_header = response.headers["location"]
        match = re.match("(?P<host>[^:]*):(?P<port>[0-9]*)(/(?P<url>.*))?", location_header)
        if match is None:
            raise QmRedirectionError(
                f"Could not parse new host and port after 302 status was received (location header: {location_header})"
            )

        new_host, new_port, _, __ = match.groups()
        return new_host, int(new_port)
