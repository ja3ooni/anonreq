"""Async Valkey-backed token mapping store.

Per D-13, D-14, D-15 and CACH-01 through CACH-06:

- Key format: ``anonreq:{tenant_id}:{session_id}`` (D-13)
- Atomic HSET + EXPIRE via pipeline(transaction=True) (D-14)
- HGETALL for retrieval (D-15)
- Async DEL post-response, TTL as fallback (CACH-04)
- Configurable TTL (CACH-02)
- Connection pool with health_check_interval (CACH-01)
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar
from urllib.parse import urlparse

import redis.asyncio as redis
from redis.asyncio.cluster import ClusterNode, RedisCluster
from redis.asyncio.sentinel import Sentinel
from tenacity import retry, retry_if_exception, stop_after_delay, wait_exponential

from anonreq.exceptions import DependencyUnavailableError

if TYPE_CHECKING:
    from anonreq.kms.base import KMSClient

T = TypeVar("T")

_RETRY_STOP_SECONDS = 30.0
_RETRY_WAIT_MIN = 0.1
_RETRY_WAIT_MAX = 2.0
_RETRY_WAIT_MULTIPLIER = 0.1
_RETRY_JITTER_LOW = 0.8
_RETRY_JITTER_HIGH = 1.2


@dataclass(frozen=True)
class _ParsedTopology:
    scheme: str
    url: str
    standalone_url: str | None = None
    sentinel_nodes: tuple[tuple[str, int], ...] = ()
    cluster_nodes: tuple[ClusterNode, ...] = ()
    service_name: str | None = None


def _is_retryable_cache_error(exc: BaseException) -> bool:
    from redis import exceptions as redis_exceptions

    retryable = (
        redis_exceptions.ConnectionError,
        redis_exceptions.TimeoutError,
        redis_exceptions.ReadOnlyError,
        redis_exceptions.ClusterDownError,
        redis_exceptions.MasterDownError,
    )
    return isinstance(exc, retryable)


def _cache_retry_wait(retry_state: Any) -> float:
    base_wait = wait_exponential(
        multiplier=_RETRY_WAIT_MULTIPLIER,
        min=_RETRY_WAIT_MIN,
        max=_RETRY_WAIT_MAX,
    )(retry_state)
    jitter = random.uniform(_RETRY_JITTER_LOW, _RETRY_JITTER_HIGH)
    bounded = base_wait * jitter
    return max(_RETRY_WAIT_MIN, min(_RETRY_WAIT_MAX, bounded))


def _parse_host_port_list(raw_authority: str) -> tuple[tuple[str, int], ...]:
    hosts: list[tuple[str, int]] = []
    for entry in raw_authority.split(","):
        node = entry.strip()
        if not node or "@" in node:
            raise ValueError("invalid cache topology")
        host, sep, port_text = node.rpartition(":")
        if not sep or not host or not port_text or ":" in host:
            raise ValueError("invalid cache topology")
        try:
            port = int(port_text)
        except ValueError as exc:
            raise ValueError("invalid cache topology") from exc
        if port < 1 or port > 65535:
            raise ValueError("invalid cache topology")
        hosts.append((host, port))
    if not hosts:
        raise ValueError("invalid cache topology")
    return tuple(hosts)


def _parse_topology(redis_url: str) -> _ParsedTopology:
    raw_url = redis_url.strip()
    if not raw_url:
        raise ValueError("cache url is required")

    parsed = urlparse(raw_url)
    scheme = parsed.scheme.lower()
    if scheme in {"redis", "rediss"}:
        return _ParsedTopology(scheme=scheme, url=raw_url, standalone_url=raw_url)

    if scheme == "redis+sentinel":
        if parsed.query or parsed.fragment or parsed.params or parsed.username or parsed.password:
            raise ValueError("invalid cache topology")
        service_name = parsed.path.lstrip("/")
        if not service_name or "/" in service_name:
            raise ValueError("invalid cache topology")
        return _ParsedTopology(
            scheme=scheme,
            url=raw_url,
            sentinel_nodes=_parse_host_port_list(parsed.netloc),
            service_name=service_name,
        )

    if scheme == "redis+cluster":
        if parsed.query or parsed.fragment or parsed.params or parsed.username or parsed.password:
            raise ValueError("invalid cache topology")
        if parsed.path:
            raise ValueError("invalid cache topology")
        return _ParsedTopology(
            scheme=scheme,
            url=raw_url,
            cluster_nodes=tuple(
                ClusterNode(host, port) for host, port in _parse_host_port_list(parsed.netloc)
            ),
        )

    raise ValueError("unsupported cache topology")


def _cache_retry_decorator(
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    return retry(
        retry=retry_if_exception(_is_retryable_cache_error),
        wait=_cache_retry_wait,
        stop=stop_after_delay(_RETRY_STOP_SECONDS),
        reraise=True,
        sleep=asyncio.sleep,
    )


class CacheManager:
    """Async Valkey manager — HASH-based token mapping store.

    Key format: ``anonreq:{tenant_id}:{session_id}`` per D-13.
    Each key holds a HASH mapping ``token → original_value``.

    All write operations use atomic pipeline transactions to ensure
    HSET + EXPIRE execute atomically per D-14, preventing orphaned
    mappings if the gateway crashes between operations.
    """

    def __init__(
        self, redis_url: str, ttl: int = 300, kms_client: KMSClient | None = None
    ) -> None:
        """Create a new CacheManager with a Valkey connection pool."""
        topology = _parse_topology(redis_url)
        self._redis = self._build_client(topology)
        self._ttl = ttl
        self._kms: KMSClient | None = kms_client

    @classmethod
    def _from_client(cls, redis_client: Any, ttl: int = 300) -> CacheManager:
        """Create a CacheManager from an existing Redis client (for testing)."""
        instance = cls.__new__(cls)
        instance._redis = redis_client
        instance._ttl = ttl
        return instance

    def _build_client(self, topology: _ParsedTopology) -> Any:
        if topology.standalone_url is not None:
            return redis.from_url(
                topology.standalone_url,
                decode_responses=True,
                health_check_interval=5,
                socket_connect_timeout=3,
            )
        if topology.sentinel_nodes:
            sentinel = Sentinel(  # type: ignore[no-untyped-call]
                list(topology.sentinel_nodes),
                decode_responses=True,
                health_check_interval=5,
                socket_connect_timeout=3,
            )
            return sentinel.master_for(
                topology.service_name or "",
                decode_responses=True,
                health_check_interval=5,
                socket_connect_timeout=3,
            )
        if topology.cluster_nodes:
            return RedisCluster(
                startup_nodes=list(topology.cluster_nodes),
                decode_responses=True,
                health_check_interval=5,
                socket_connect_timeout=3,
            )
        raise ValueError("unsupported cache topology")

    def _key(self, tenant_id: str, session_id: str) -> str:
        """Build the Valkey key for a tenant-scoped session mapping."""
        return f"anonreq:{tenant_id}:{session_id}"

    async def _execute_with_retry(self, operation: Callable[[], Awaitable[T]]) -> T:
        @_cache_retry_decorator()
        async def _run() -> T:
            return await operation()

        try:
            return await _run()
        except Exception as exc:
            if _is_retryable_cache_error(exc):
                raise DependencyUnavailableError(dependency="valkey") from None
            raise

    async def store_mapping(
        self,
        tenant_id: str,
        session_id: str,
        mapping: dict[str, str],
    ) -> None:
        """Atomically store token → value mappings with TTL.

        Per D-08, when KMS is configured, values are encrypted before
        Valkey write. Ciphertext is stored; plaintext never touches storage.
        """
        import base64

        key = self._key(tenant_id, session_id)

        # Per D-08: encrypt values before Valkey write when KMS is configured
        store_mapping = mapping
        if self._kms is not None:
            store_mapping = {}
            for token, value in mapping.items():
                ciphertext = await self._kms.encrypt(tenant_id, value.encode())
                store_mapping[token] = base64.b64encode(ciphertext).decode()

        async def _operation() -> None:
            async with self._redis.pipeline(transaction=True) as pipe:
                await pipe.hset(key, mapping=store_mapping).expire(key, self._ttl).execute()

        await self._execute_with_retry(_operation)

    async def get_mapping(
        self,
        tenant_id: str,
        session_id: str,
    ) -> dict[str, str]:
        """Retrieve all token → value pairs for a session.

        Per D-08, when KMS is configured, ciphertext is decrypted
        after Valkey read. Decryption failures raise
        DependencyUnavailableError (fail-secure).
        """
        import base64

        key = self._key(tenant_id, session_id)
        raw = await self._execute_with_retry(lambda: self._redis.hgetall(key))

        # Per D-08: decrypt values after Valkey read when KMS is configured
        if self._kms is not None and raw:
            try:
                decrypted = {}
                for token, ciphertext_b64 in raw.items():
                    ciphertext = base64.b64decode(ciphertext_b64)
                    plaintext = await self._kms.decrypt(tenant_id, ciphertext)
                    decrypted[token] = plaintext.decode()
                return decrypted
            except Exception:
                raise DependencyUnavailableError(dependency="kms") from None

        return raw

    async def delete_mapping(
        self,
        tenant_id: str,
        session_id: str,
    ) -> None:
        """Delete the mapping key for a session."""

        key = self._key(tenant_id, session_id)
        await self._execute_with_retry(lambda: self._redis.delete(key))

    async def close(self) -> None:
        """Close the underlying Valkey connection."""

        await self._redis.aclose()
