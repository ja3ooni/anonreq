"""Pre-flight dependency validation for startup.

Provides ``run_startup_checks()`` which verifies Valkey and Presidio
are reachable before the application starts accepting traffic.

Per FAIL-04: Pre-flight health check prevents startup until all
components pass. The application refuses to start if any dependency
is unreachable.

Threat model coverage:
- T-01-03-03 (Denial of Service): ``socket_connect_timeout=3`` prevents
  hung checks. ``httpx timeout=5`` for Presidio check. Fast fail on
  first dependency failure.
- T-01-03-04 (Elevation of Privilege): Pre-flight makes outbound TCP
  connections to Valkey and Presidio. Both are on the internal Docker
  network. URLs come from config, not user input. (Accept — minimal SSRF risk.)
"""

import socket
from urllib.parse import urlparse

import structlog

from anonreq.config import Settings

logger = structlog.get_logger()


async def check_valkey(url: str) -> bool:
    """Check Valkey/Redis reachability via TCP socket.

    Uses a raw socket connection with 3-second timeout to verify the
    Valkey server is accepting connections. This avoids the complexity
    of creating a full Redis client just for a health check.

    Args:
        url: Valkey connection URL (e.g., ``redis://valkey:6379/0``).

    Returns:
        ``True`` if the TCP connection succeeds, ``False`` otherwise.
    """
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379

    try:
        reader, writer = await asyncio_open_connection(host, port)
        writer.close()
        await writer.wait_closed()
        return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


async def asyncio_open_connection(host: str, port: int, timeout: float = 3.0) -> tuple:
    """Open a TCP connection with timeout.

    Uses asyncio's ``open_connection`` with a timeout wrapper. This avoids
    importing the full redis library just for a connectivity check.

    Args:
        host: Target hostname.
        port: Target port.
        timeout: Connection timeout in seconds (default: 3.0).

    Returns:
        A ``(reader, writer)`` tuple from ``asyncio.open_connection``.

    Raises:
        TimeoutError: If the connection cannot be established within ``timeout``.
        ConnectionRefusedError: If the connection is refused.
    """
    import asyncio

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        return reader, writer
    except asyncio.TimeoutError:
        raise TimeoutError(f"Connection to {host}:{port} timed out")


async def check_presidio(url: str) -> bool:
    """Check Presizio Analyzer reachability via HTTP GET.

    Sends a GET request to the Presidio health endpoint. Returns ``True``
    if the response status is lower than 500 (indicating the service is
    alive and accepting requests).

    Args:
        url: Presidio base URL (e.g., ``http://presidio:5001``).

    Returns:
        ``True`` if the service responds with status < 500, ``False`` otherwise.
    """
    import httpx

    health_url = url.rstrip("/") + "/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(health_url)
            return response.status_code < 500
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
        return False


async def run_startup_checks(settings: Settings) -> None:
    """Run all pre-flight dependency checks.

    Checks Valkey and Presidio reachability sequentially. If either check
    fails, raises ``DependencyUnavailableError`` with the name of the
    failing dependency to prevent the application from starting.

    Args:
        settings: The application settings instance providing dependency URLs.

    Raises:
        DependencyUnavailableError: If Valkey or Presidio is unreachable.
    """
    # Check Valkey
    logger.info("Checking Valkey connectivity", component="startup_checks")
    valkey_ok = await check_valkey(settings.VALKEY_URL)
    if not valkey_ok:
        logger.error("Valkey unreachable", component="startup_checks")
        from anonreq.exceptions import DependencyUnavailableError

        raise DependencyUnavailableError(dependency="valkey")

    logger.info("Valkey reachable", component="startup_checks")

    # Check Presidio
    logger.info("Checking Presidio connectivity", component="startup_checks")
    presidio_ok = await check_presidio(settings.PRESIDIO_URL)
    if not presidio_ok:
        logger.error("Presidio unreachable", component="startup_checks")
        from anonreq.exceptions import DependencyUnavailableError

        raise DependencyUnavailableError(dependency="presidio")

    logger.info("Presidio reachable", component="startup_checks")
    logger.info("All dependencies OK", component="startup_checks")
