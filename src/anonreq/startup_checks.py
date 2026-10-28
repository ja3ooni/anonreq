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
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import structlog
import yaml

from anonreq.cache.health import check_cache_health
from anonreq.cache.manager import CacheManager
from anonreq.config import Settings
from anonreq.providers.registry import (
    provider_has_credential,
    provider_requires_api_key,
)

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


async def check_presidio_language(url: str, language: str) -> bool:
    """Return True when Presidio accepts ``language`` on ``/analyze``.

    A short fixed probe is used. The response body is not logged. HTTP 200
    means the language is loaded; anything else means it is not.
    """
    import httpx

    payload = {
        "text": "language probe",
        "language": language,
        "score_threshold": 0.99,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url.rstrip("/") + "/analyze", json=payload)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
        return False
    return response.status_code == 200


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


def configured_provider_names(
    aliases_path: str = "config/model_aliases.yaml",
) -> list[str]:
    """Return provider names referenced by the model-alias file.

    The shipped alias file is the set of providers the gateway can route
    to. A missing file is treated as the OpenAI-compatible upstream.
    """
    path = Path(aliases_path)
    if not path.is_file():
        return ["openai"]
    with path.open() as handle:
        raw: Any = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        return ["openai"]
    names: list[str] = []
    seen: set[str] = set()
    for data in (raw.get("model_aliases") or {}).values():
        if not isinstance(data, dict):
            continue
        name = str(data.get("provider") or "").strip()
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names or ["openai"]


def load_provider_key_requirements(
    providers_path: str = "config/providers.yaml",
) -> dict[str, bool]:
    """Return ``requires_api_key`` flags declared in the provider registry."""
    path = Path(providers_path)
    if not path.is_file():
        return {}
    with path.open() as handle:
        raw: Any = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        return {}
    flags: dict[str, bool] = {}
    for name, config in (raw.get("providers") or {}).items():
        if isinstance(config, dict) and "requires_api_key" in config:
            flags[str(name).casefold()] = bool(config["requires_api_key"])
    return flags


def _missing_provider_key_message(missing: list[str]) -> str:
    """Operator-facing startup error. Never includes credential values."""
    hints: list[str] = []
    for name in missing:
        upper = name.upper()
        if name.casefold() == "openai":
            hints.append(
                "openai: set PROVIDER_API_KEY or ANONREQ_OPENAI_API_KEY or OPENAI_API_KEY"
            )
        else:
            hints.append(f"{name}: set ANONREQ_{upper}_API_KEY or {upper}_API_KEY")
    names = ", ".join(missing)
    hint_text = "; ".join(hints)
    return (
        f"Provider API key missing for: {names}. {hint_text}. "
        "Mock, local, and ollama providers do not need a key. "
        "ANONREQ_API_KEY is the gateway client credential and is never sent upstream. "
        "Refusing to start."
    )


def validate_provider_credentials(settings: Settings) -> None:
    """Fail startup when a configured provider that needs a key has none.

    Runs in every environment. ``PROVIDER_API_KEY`` satisfies only the
    OpenAI-compatible upstream. The gateway client key is ignored.
    Placeholder values (``change-me*``, ``changeme``, ``<...>``,
    ``your-...-key``) count as unset, so startup fails closed instead of
    forwarding a template key and receiving HTTP 401 from the provider.
    """
    flags = load_provider_key_requirements()
    shared_key = getattr(settings, "PROVIDER_API_KEY", None)
    missing: list[str] = []
    for name in configured_provider_names():
        if not provider_requires_api_key(name, flags):
            continue
        has_key = provider_has_credential(
            name,
            provider_api_key=shared_key if name.casefold() == "openai" else None,
        )
        if not has_key:
            missing.append(name)
    if not missing:
        return
    message = _missing_provider_key_message(missing)
    logger.error(
        "provider_api_key_missing",
        component="startup_checks",
        provider=", ".join(missing),
        error="missing_provider_api_key",
    )
    raise RuntimeError(message)


async def validate_production_secrets(settings: Settings) -> None:
    """Refuse to boot in production mode with default/placeholder credentials.

    Catches compose-level default credentials (Finding 7) before serving
    traffic: unset or default MinIO / Postgres secrets when
    ``ANONREQ_ENV=production``. Provider API keys are checked for every
    environment by ``validate_provider_credentials``. The gateway client
    key is never accepted as a provider credential.
    """
    import os

    env = str(getattr(settings, "ENV", "development")).strip().lower()
    if env != "production":
        return
    problems: list[str] = []
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


class DemoKmsKeyMissingError(RuntimeError):
    """Raised when demo mode starts without ANONREQ_KMS_MASTER_KEY."""


class KmsKeyPlaceholderError(RuntimeError):
    """Raised when ANONREQ_KMS_MASTER_KEY is a literal ``<...>`` placeholder."""


def resolve_kms_master_key(env_name: str, master_key_env: str | None) -> bytes | None:
    """Return the configured KMS master key, enforcing it in demo mode.

    In ``ANONREQ_ENV=demo`` mappings must be AES-256-GCM encrypted with a
    stable, operator-supplied master key, so a missing/blank/short key is a
    hard startup failure rather than a silent ephemeral key.
    Returns ``None`` outside demo mode when unset (caller generates an
    ephemeral dev key).
    """
    key = (master_key_env or "").strip()
    # A value copied verbatim from .env.example (e.g. "<generate-...>") is a
    # public string, never a secret: refuse it in every mode, not just demo.
    if key.startswith("<") or key.endswith(">"):
        logger.error(
            "kms_master_key_placeholder",
            component="startup_checks",
            detail="ANONREQ_KMS_MASTER_KEY is a <...> placeholder; set a real key or unset it",
        )
        raise KmsKeyPlaceholderError(
            "ANONREQ_KMS_MASTER_KEY is a '<...>' placeholder (copied from "
            ".env.example?); set a random 32+ char key or leave it unset"
        )
    if str(env_name).strip().lower() == "demo" and len(key) < 32:
        logger.error(
            "demo_kms_master_key_missing",
            component="startup_checks",
            detail="ANONREQ_KMS_MASTER_KEY must be set (>=32 chars) in demo mode",
        )
        raise DemoKmsKeyMissingError(
            "ANONREQ_ENV=demo requires ANONREQ_KMS_MASTER_KEY (>=32 chars); "
            "run `make demo` or scripts/demo.sh to generate one into .env"
        )
    return key.encode("utf-8") if key else None


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
    # Last-added runs first: TenantContext must be added AFTER Policy.
    if (
        "PolicyMiddleware" in order
        and "TenantContextMiddleware" in order
        and order.index("TenantContextMiddleware") < order.index("PolicyMiddleware")
    ):
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
        RuntimeError: If a configured provider that needs an API key has none.
            The gateway client key is not accepted.
        DependencyUnavailableError: If Valkey or Presidio is unreachable.
    """
    validate_provider_credentials(settings)
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

    from anonreq.locale.presidio_language import languages_to_probe, parse_presidio_languages

    configured = parse_presidio_languages(getattr(settings, "PRESIDIO_LANGUAGES", "en"))
    for language in languages_to_probe(configured):
        logger.info(
            "Checking Presidio language",
            component="startup_checks",
            presidio_language=language,
        )
        supported = await check_presidio_language(settings.PRESIDIO_URL, language)
        if not supported:
            logger.error(
                "startup.presidio_language_unsupported",
                component="startup_checks",
                presidio_language=language,
                error_type="presidio_unsupported_language",
            )
            from anonreq.exceptions import DependencyUnavailableError

            raise DependencyUnavailableError(dependency="presidio")

    logger.info("All dependencies OK", component="startup_checks")
