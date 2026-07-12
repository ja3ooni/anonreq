"""Performance optimizations for proxy-only mode.

Provides latency measurement, Prometheus metrics registration, middleware
chain optimization, connection pooling configuration, and a request body
fast-path for proxy-only mode.

Per D-014, D-015:
- Proxy-only mode targets: P50 < 2ms, P95 < 5ms, P99 < 10ms
- Measured: gateway-internal timing (request receipt to ForwardingGuard
  decision)
- Use ``time.perf_counter_ns()`` for sub-microsecond precision
- All measurements are internal to the gateway process
"""

from __future__ import annotations

import dataclasses
import time
from typing import Any

import structlog
from prometheus_client import Histogram

from anonreq.proxy.modes import ProxyMode

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Prometheus histograms for per-stage latency
# ---------------------------------------------------------------------------

PROXY_LATENCY_HISTOGRAM = Histogram(
    "anonreq_proxy_latency_ms",
    "Per-stage latency in milliseconds for proxy pipeline stages",
    labelnames=["stage", "mode"],
    buckets=(
        0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0,
        7.5, 10.0, 15.0, 20.0, 30.0, 50.0, 100.0,
    ),
)
"""Prometheus histogram recording per-stage latency with stage and mode labels."""


# ---------------------------------------------------------------------------
# LatencyTimer context manager
# ---------------------------------------------------------------------------


class LatencyTimer:
    """Context manager that measures elapsed time with nanosecond precision.

    Records the wall-clock time spent inside the context using
    ``time.perf_counter_ns()`` and exposes it via the ``elapsed_ms``
    property. Optionally registers the measurement as a Prometheus
    histogram observation.

    Usage::

        with LatencyTimer("auth") as timer:
            await authenticate(request)
        logger.info("Auth completed", elapsed_ms=timer.elapsed_ms)

    Args:
        stage: Name of the pipeline stage being measured.
        mode: Proxy mode string for Prometheus labels.
        register_metric: If ``True``, record in Prometheus histogram.
    """

    def __init__(
        self,
        stage: str,
        mode: str = "proxy-only",
        register_metric: bool = False,
    ) -> None:
        self._stage = stage
        self._mode = mode
        self._register_metric = register_metric
        self._start_ns: int | None = None
        self._elapsed_ms: float | None = None

    def __enter__(self) -> LatencyTimer:
        self._start_ns = time.perf_counter_ns()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        if self._start_ns is not None:
            elapsed_ns = time.perf_counter_ns() - self._start_ns
            self._elapsed_ms = elapsed_ns / 1_000_000.0
            if self._register_metric:
                PROXY_LATENCY_HISTOGRAM.labels(
                    stage=self._stage,
                    mode=self._mode,
                ).observe(self._elapsed_ms)

    @property
    def elapsed_ms(self) -> float:
        """Return the elapsed time in milliseconds.

        Raises:
            RuntimeError: If the timer has not been started (used outside
                a ``with`` block).
        """
        if self._elapsed_ms is None:
            raise RuntimeError("LatencyTimer not yet measured")
        return self._elapsed_ms


def register_latency_metric(stage: str, elapsed_ms: float, mode: str = "proxy-only") -> None:
    """Register a latency observation in the Prometheus histogram.

    Args:
        stage: Name of the pipeline stage.
        elapsed_ms: Measured latency in milliseconds.
        mode: Proxy mode string for labels.
    """
    PROXY_LATENCY_HISTOGRAM.labels(stage=stage, mode=mode).observe(elapsed_ms)


# ---------------------------------------------------------------------------
# Middleware chain optimization
# ---------------------------------------------------------------------------


def _optimize_middleware_chain(mode: ProxyMode) -> list[str]:
    """Return the minimal middleware chain for the given mode.

    In proxy-only mode, only essential middleware is included — no CORS,
    no compression, no content-type inspection. Each middleware in the
    chain is expected to be instrumented with ``LatencyTimer``.

    Args:
        mode: The operating mode.

    Returns:
        List of middleware class names in execution order.
    """
    if mode == ProxyMode.PROXY_ONLY:
        return [
            "MetricsMiddleware",  # request timing
            "set_request_context",  # request_id binding
            "AuthMiddleware",  # auth check
            "proxy_middleware",  # MITM/forwarding
            "ForwardingGuard",  # policy decision
        ]
    # Full / transparent mode: include classification and policy middleware
    return [
        "MetricsMiddleware",
        "set_request_context",
        "ClassificationMiddleware",
        "PolicyMiddleware",
        "ClassificationResponseMiddleware",
        "AuthMiddleware",
        "proxy_middleware",
        "ForwardingGuard",
    ]


# ---------------------------------------------------------------------------
# Connection pooling configuration
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ConnectionPoolConfig:
    """Configuration for upstream provider connection pooling.

    Attributes:
        max_connections: Maximum number of pooled connections.
        max_keepalive_connections: Maximum number of keepalive connections.
        keepalive_timeout: Idle timeout in seconds for keepalive connections.
        enable_http2: Whether to enable HTTP/2 for upstream connections.
        timeout: Default request timeout in seconds.
    """

    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_timeout: int = 30
    enable_http2: bool = True
    timeout: int = 30


def configure_httpx_client(
    pool_config: ConnectionPoolConfig | None = None,
) -> dict[str, Any]:
    """Return kwargs for ``httpx.AsyncClient`` with connection pooling.

    Args:
        pool_config: Connection pool configuration. Uses defaults if
            ``None``.

    Returns:
        A dict of kwargs suitable for ``httpx.AsyncClient(**kwargs)``.
    """
    if pool_config is None:
        pool_config = ConnectionPoolConfig()

    try:
        import httpx

        limits = httpx.Limits(
            max_connections=pool_config.max_connections,
            max_keepalive_connections=pool_config.max_keepalive_connections,
            keepalive_expiry=pool_config.keepalive_timeout,
        )
        kwargs: dict[str, Any] = {
            "limits": limits,
            "timeout": httpx.Timeout(pool_config.timeout),
        }
        if pool_config.enable_http2:
            kwargs["http2"] = True
    except ImportError:
        kwargs = {}
        logger.warning(
            "httpx not available — cannot configure connection pooling",
            component="optimizations",
        )

    return kwargs


# ---------------------------------------------------------------------------
# Request body fast-path for proxy-only mode
# ---------------------------------------------------------------------------


class RequestFastPath:
    """Fast-path request handler that bypasses body parsing.

    In proxy-only mode, the request body is never inspected for PII.
    This handler streams raw bytes without parsing JSON, avoiding
    deserialization overhead. For full inspection mode, the body is
    parsed once and cached for all pipeline stages.
    """

    def __init__(self, mode: ProxyMode) -> None:
        self._mode = mode
        self._cached_body: bytes | None = None

    @property
    def is_proxy_only(self) -> bool:
        """``True`` when running in proxy-only mode."""
        return self._mode == ProxyMode.PROXY_ONLY

    async def get_body(self, request: Any) -> bytes:
        """Read the request body, potentially caching it.

        In proxy-only mode, the body is streamed without parsing.
        In full/transparent modes, the body is cached after first read
        for reuse across pipeline stages.

        Args:
            request: The FastAPI ``Request`` object.

        Returns:
            The raw request body as bytes.
        """
        body = await request.body()
        if not self.is_proxy_only:
            self._cached_body = body
        return body

    def get_cached_body(self) -> bytes | None:
        """Return the cached body, if any.

        Returns:
            The cached body bytes, or ``None`` if not yet read.
        """
        return self._cached_body
