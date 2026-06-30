"""Cache management module for the AnonReq gateway.

Provides:
- ``CacheManager``: Async Valkey-backed token mapping store with atomic
  HSET+EXPIRE via pipeline, HGETALL retrieval, async DEL, and TTL-based
  eviction.
- ``check_cache_health()``: Verifies Valkey reachability and
  persistence-disabled state per CACH-06.

All operations use ``redis.asyncio`` with RESP3 (verified compatible with
Valkey 8 per RESEARCH A3).
"""
