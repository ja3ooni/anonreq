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

import redis.asyncio as redis


class CacheManager:
    """Async Valkey manager — HASH-based token mapping store.

    Key format: ``anonreq:{tenant_id}:{session_id}`` per D-13.
    Each key holds a HASH mapping ``token → original_value``.

    All write operations use atomic pipeline transactions to ensure
    HSET + EXPIRE execute atomically per D-14, preventing orphaned
    mappings if the gateway crashes between operations.
    """

    def __init__(self, redis_url: str, ttl: int = 300) -> None:
        """Create a new CacheManager with a Valkey connection pool.

        Args:
            redis_url: Valkey/Redis connection URL (e.g.
                ``redis://valkey:6379/0``).
            ttl: Default TTL in seconds for stored mappings. Must be
                between 60 and 3600 per CACH-02. Defaults to 300.
        """
        self._redis = redis.from_url(
            redis_url,
            decode_responses=True,
            health_check_interval=5,
            socket_connect_timeout=3,
        )
        self._ttl = ttl

    def _key(self, tenant_id: str, session_id: str) -> str:
        """Build the Valkey key for a tenant-scoped session mapping.

        Per D-13, the key format provides namespace isolation:
        ``anonreq:{tenant_id}:{session_id}``
        """
        return f"anonreq:{tenant_id}:{session_id}"

    async def store_mapping(
        self,
        tenant_id: str,
        session_id: str,
        mapping: dict[str, str],
    ) -> None:
        """Atomically store token → value mappings with TTL.

        Uses ``pipeline(transaction=True)`` to execute HSET + EXPIRE
        in a single atomic operation per D-14. This prevents orphaned
        mappings if the gateway crashes between the two commands.

        Args:
            tenant_id: Tenant namespace for the key.
            session_id: Session identifier (UUIDv7 hex).
            mapping: Dict of ``{token: original_value}`` pairs.
        """
        key = self._key(tenant_id, session_id)
        async with self._redis.pipeline(transaction=True) as pipe:
            await (
                pipe.hset(key, mapping=mapping)
                .expire(key, self._ttl)
                .execute()
            )

    async def get_mapping(
        self,
        tenant_id: str,
        session_id: str,
    ) -> dict[str, str]:
        """Retrieve all token → value pairs for a session.

        Uses HGETALL per D-15. Returns an empty dict if no mapping
        exists for the given tenant/session combination.

        Args:
            tenant_id: Tenant namespace for the key.
            session_id: Session identifier.

        Returns:
            Dict of ``{token: original_value}`` pairs, or empty dict.
        """
        key = self._key(tenant_id, session_id)
        return await self._redis.hgetall(key)

    async def delete_mapping(
        self,
        tenant_id: str,
        session_id: str,
    ) -> None:
        """Delete the mapping key for a session.

        Per CACH-04, the mapping is deleted asynchronously after the
        response is sent.  The TTL serves as a fallback cleanup
        mechanism if the DEL fails.

        Args:
            tenant_id: Tenant namespace for the key.
            session_id: Session identifier.
        """
        key = self._key(tenant_id, session_id)
        await self._redis.delete(key)

    async def close(self) -> None:
        """Close the underlying Valkey connection.

        Should be called during application shutdown to release the
        connection pool.
        """
        await self._redis.aclose()
