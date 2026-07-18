"""In-memory key cache with bounded TTL for derived data keys.

Per D-09, data keys are cached in-memory with bounded TTL to avoid
KMS calls on every request. The cache evicts oldest entries when
at capacity and re-derives keys on TTL expiry.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


@dataclass
class CachedKey:
    """A cached data key with expiry time."""

    data_key: bytes
    expires_at: float


class InMemoryKeyCache:
    """Bounded TTL cache for tenant data keys.

    Per D-09, keys are derived via HKDF from a master key and
    cached in-memory. The cache has a maximum entry count and
    TTL-based expiry. Evicted keys are re-derived on next access.
    """

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 1000) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._cache: dict[str, CachedKey] = {}

    async def get_or_derive(self, tenant_id: str, master_key: bytes) -> bytes:
        """Get cached data key or derive a new one via HKDF.

        Per D-09, checks cache first. On miss or TTL expiry,
        derives a 256-bit data key using HKDF with SHA256.
        Evicts oldest entry if cache at capacity.
        """
        now = time.monotonic()

        # Check cache hit (not expired)
        cached = self._cache.get(tenant_id)
        if cached is not None and cached.expires_at > now:
            return cached.data_key

        # Derive new data key via HKDF
        hkdf = HKDF(
            algorithm=SHA256,
            length=32,
            salt=None,
            info=f"anonreq-tenant-{tenant_id}".encode(),
        )
        data_key = hkdf.derive(master_key)

        # Evict oldest entry if at capacity
        if len(self._cache) >= self._max_entries and tenant_id not in self._cache:
            oldest_key = min(self._cache, key=lambda k: self._cache[k].expires_at)
            del self._cache[oldest_key]

        # Store with TTL
        self._cache[tenant_id] = CachedKey(
            data_key=data_key,
            expires_at=now + self._ttl,
        )

        return data_key

    async def invalidate(self, tenant_id: str) -> None:
        """Remove cached key for a tenant (for rotation signal)."""
        self._cache.pop(tenant_id, None)

    async def clear(self) -> None:
        """Clear all cached keys (for testing)."""
        self._cache.clear()
