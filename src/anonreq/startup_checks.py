"""Pre-flight dependency validation for startup.

Provides ``run_startup_checks()`` which verifies cache health and
Presidio reachability before the application starts accepting traffic.

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

from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

import structlog

from anonreq.cache.health import check_cache_health
from anonreq.cache.manager import CacheManager
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
        _reader, writer = await asyncio_open_connection(host, port)
        writer.close()
        await writer.wait_closed()
        return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


async def asyncio_open_connection(host: str, port: int, timeout: float = 3.0) -> tuple[Any, Any]:
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
    except TimeoutError:
        raise TimeoutError(f"Connection to {host}:{port} timed out")  # noqa: B904


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
            is_healthy: bool = response.status_code < 500
            return is_healthy
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
        return False


async def _check_with_retry(
    name: str,
    check_fn: Callable[[], Awaitable[bool]],
    max_retries: int = 5,
    delay: float = 3.0,
) -> bool:
    """Run a health check with retries.

    Args:
        name: Human-readable dependency name for logging.
        check_fn: An async callable returning ``True`` if reachable.
        max_retries: Number of retry attempts (default 5).
        delay: Seconds between retries (default 3.0).

    Returns:
        ``True`` if the check passes within retry budget.
    """
    import asyncio

    for attempt in range(max_retries):
        ok = await check_fn()
        if ok:
            return True
        if attempt < max_retries - 1:
            logger.warning(
                "%s unreachable (attempt %d/%d), retrying in %.0fs",
                name, attempt + 1, max_retries, delay,
                component="startup_checks",
            )
            await asyncio.sleep(delay)
    return False


async def validate_single_tenant_mode(settings: Settings) -> None:
    """Validate that single-tenant fallback is a conscious deployment choice.

    Logs the effective tenancy mode at startup so a fail-open tenant
    fallback can never be a silent accident (Finding 3).
    """
    single = str(getattr(settings, "SINGLE_TENANT", False)).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "True",
    } if isinstance(getattr(settings, "SINGLE_TENANT", False), str) else bool(
        getattr(settings, "SINGLE_TENANT", False)
    )
    if single:
        logger.warning(
            "single_tenant_mode_enabled",
            component="startup_checks",
            detail="PolicyMiddleware may fall back to tenant 'default'",
        )
    else:
        logger.info(
            "multi_tenant_mode_enforced",
            component="startup_checks",
            detail="missing tenant context fails secure with 503",
        )


async def validate_production_secrets(settings: Settings) -> None:
    """Refuse to boot in production mode with default/placeholder credentials.

    Catches compose-level default credentials (Finding 7) before serving
    traffic: empty provider keys, placeholder API keys, and unset MinIO /
    Postgres secrets when ``ANONREQ_ENV=production``.
    """
    import os

    env = str(getattr(settings, "ENV", "development")).strip().lower()
    if env != "production":
        return
    problems: list[str] = []
    if not getattr(settings, "PROVIDER_API_KEY", None):
        problems.append("PROVIDER_API_KEY is unset")
    for var in ("MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD", "POSTGRES_PASSWORD"):
        if not os.environ.get(var):
            problems.append(f"{var} is unset")
    for var in ("MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD", "POSTGRES_PASSWORD"):
        val = os.environ.get(var, "")
        if val.strip().lower() in {"minioadmin", "anonreq", "password", "changeme"}:
            problems.append(f"{var} uses a default credential")
    if problems:
        logger.error(
            "production_secrets_invalid",
            component="startup_checks",
            problems=problems,
        )
        from anonreq.exceptions import DependencyUnavailableError

        raise DependencyUnavailableError(dependency="production-secrets")


def assert_middleware_ordering(app: Any) -> None:
    """Assert TenantContextMiddleware runs before PolicyMiddleware.

    Starlette executes the last-added middleware outermost (first on
    request). ``create_app`` adds PolicyMiddleware before
    TenantContextMiddleware so Tenant is outer and sets
    ``request.state.tenant_id`` before Policy reads it. If a future
    refactor reorders them, fail fast at startup instead of silently
    evaluating every request under the wrong tenant.
    """
    try:
        stack = getattr(getattr(app, "user_middleware", None), "_stack", None) or []
    except Exception:
        return
    order = [getattr(m, "cls", None) and m.cls.__name__ for m in stack]
    if "PolicyMiddleware" in order and "TenantContextMiddleware" in order:
        # Last-added runs first: TenantContext must be added AFTER Policy.
        if order.index("TenantContextMiddleware") < order.index("PolicyMiddleware"):
            logger.error(
                "middleware_ordering_invalid",
                component="startup_checks",
                order=order,
            )
            raise RuntimeError(
                "TenantContextMiddleware must be added after PolicyMiddleware "
                "so it runs first on requests"
            )
    logger.info("middleware_ordering_ok", component="startup_checks", order=order)


async def run_startup_checks(settings: Settings, cache_manager: CacheManager) -> None:
    """Run all pre-flight dependency checks with retries.

    Checks cache health and Presidio reachability sequentially with
    retries to handle container startup races in Docker Compose. If
    either check exhausts its retry budget, raises
    ``DependencyUnavailableError``.

    Args:
        settings: The application settings instance providing dependency URLs.
        cache_manager: Lifespan-created cache manager for topology-aware
            health checks.

    Raises:
        DependencyUnavailableError: If Valkey or Presidio is unreachable.
    """
    await validate_single_tenant_mode(settings)
    await validate_production_secrets(settings)
    # Check cache health via the lifespan-owned CacheManager instance.
    logger.info("Checking cache health", component="startup_checks")
    try:
        cache_health = await check_cache_health(cache_manager)
    except Exception:
        cache_health = {
            "reachable": False,
            "persistence_disabled": False,
            "healthy": False,
        }
    if not cache_health.get("healthy", False):
        logger.error(
            "Cache unhealthy",
            component="startup_checks",
            reachable=cache_health.get("reachable", False),
            persistence_disabled=cache_health.get("persistence_disabled", False),
        )
        from anonreq.exceptions import DependencyUnavailableError

        raise DependencyUnavailableError(dependency="valkey")

    logger.info("Cache healthy", component="startup_checks")

    # Check Presidio
    logger.info("Checking Presidio connectivity", component="startup_checks")
    presidio_ok = await _check_with_retry(
        "Presidio",
        lambda: check_presidio(settings.PRESIDIO_URL),
    )
    if not presidio_ok:
        logger.error("Presidio unreachable", component="startup_checks")
        from anonreq.exceptions import DependencyUnavailableError

        raise DependencyUnavailableError(dependency="presidio")

    logger.info("Presidio reachable", component="startup_checks")
    logger.info("All dependencies OK", component="startup_checks")
