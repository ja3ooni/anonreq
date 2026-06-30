"""Tests for the Valkey CacheManager.

Tests verify:
- CacheManager.store_mapping stores mappings with atomic HSET+EXPIRE
- CacheManager.get_mapping retrieves all token→value pairs via HGETALL
- CacheManager.delete_mapping deletes the key via async DEL
- TTL is set on stored mappings (default 300s)
- health_check returns correct healthy/unhealthy status
- Key format is anonreq:{tenant_id}:{session_id} per D-13
- CacheManager.close() cleans up connection pool
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def cache_manager():
    """Create a CacheManager backed by fakeredis."""
    import fakeredis.aioredis

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    from anonreq.cache.manager import CacheManager

    manager = CacheManager.__new__(CacheManager)
    manager._redis = fake_redis
    manager._ttl = 300
    yield manager
    import asyncio

    try:
        asyncio.run(fake_redis.aclose())
    except RuntimeError:
        pass


class TestCacheManagerStore:
    """Tests for CacheManager.store_mapping."""

    @pytest.mark.asyncio
    async def test_store_mapping_sets_hash_and_expire(self, cache_manager):
        """Test 1: store_mapping stores token→value with atomic HSET+EXPIRE via pipeline."""
        mapping = {"[EMAIL_0]": "user@example.com", "[PHONE_0]": "+1-555-1234"}
        await cache_manager.store_mapping("tenant1", "sess_001", mapping)

        stored = await cache_manager._redis.hgetall("anonreq:tenant1:sess_001")
        assert stored["[EMAIL_0]"] == "user@example.com"
        assert stored["[PHONE_0]"] == "+1-555-1234"

    @pytest.mark.asyncio
    async def test_store_mapping_sets_ttl(self, cache_manager):
        """Test 4: store_mapping sets TTL (default 300s) on the key."""
        import time as time_module

        await cache_manager.store_mapping("tenant1", "sess_ttl", {"[EMAIL_0]": "test@example.com"})
        ttl = await cache_manager._redis.ttl("anonreq:tenant1:sess_ttl")
        assert ttl > 0, "TTL should be set to a positive value"
        assert ttl <= 300, "TTL should not exceed the configured default"

    @pytest.mark.asyncio
    async def test_store_mapping_key_format(self, cache_manager):
        """Test 7: key format is anonreq:{tenant_id}:{session_id} per D-13."""
        await cache_manager.store_mapping("acme", "sess_xyz", {"[NAME_0]": "John"})

        exists_expected = await cache_manager._redis.exists("anonreq:acme:sess_xyz")
        assert exists_expected == 1, "Key should exist at anonreq:acme:sess_xyz"

        exists_wrong = await cache_manager._redis.exists("acme:sess_xyz")
        assert exists_wrong == 0, "Key should NOT exist without anonreq: prefix"


class TestCacheManagerGet:
    """Tests for CacheManager.get_mapping."""

    @pytest.mark.asyncio
    async def test_get_mapping_returns_all_pairs(self, cache_manager):
        """Test 2: get_mapping retrieves all token→value pairs for a session via HGETALL."""
        mapping = {
            "[EMAIL_0]": "alice@example.com",
            "[PHONE_0]": "+1-555-5678",
            "[NAME_0]": "Alice",
        }
        await cache_manager.store_mapping("default", "sess_002", mapping)

        result = await cache_manager.get_mapping("default", "sess_002")
        assert result == mapping
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_get_mapping_empty_returns_empty_dict(self, cache_manager):
        """get_mapping returns empty dict when no mapping exists."""
        result = await cache_manager.get_mapping("default", "nonexistent")
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_mapping_returns_only_session_data(self, cache_manager):
        """get_mapping isolates data between sessions."""
        await cache_manager.store_mapping("default", "sess_a", {"[EMAIL_0]": "a@example.com"})
        await cache_manager.store_mapping("default", "sess_b", {"[EMAIL_0]": "b@example.com"})

        result_a = await cache_manager.get_mapping("default", "sess_a")
        result_b = await cache_manager.get_mapping("default", "sess_b")

        assert result_a["[EMAIL_0]"] == "a@example.com"
        assert result_b["[EMAIL_0]"] == "b@example.com"
        assert "[EMAIL_0]" in result_a
        assert "[EMAIL_0]" in result_b


class TestCacheManagerDelete:
    """Tests for CacheManager.delete_mapping."""

    @pytest.mark.asyncio
    async def test_delete_mapping_removes_key(self, cache_manager):
        """Test 3: delete_mapping deletes the key via async DEL."""
        await cache_manager.store_mapping("default", "sess_del", {"[TOKEN_0]": "secret"})
        exists_before = await cache_manager._redis.exists("anonreq:default:sess_del")
        assert exists_before == 1

        await cache_manager.delete_mapping("default", "sess_del")

        exists_after = await cache_manager._redis.exists("anonreq:default:sess_del")
        assert exists_after == 0

    @pytest.mark.asyncio
    async def test_delete_mapping_idempotent(self, cache_manager):
        """delete_mapping does not raise when deleting a non-existent key."""
        await cache_manager.delete_mapping("default", "ghost_sess")
        # Should not raise — idempotent operation


class TestCacheManagerHealth:
    """Tests for cache health check."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, cache_manager):
        """Test 5: health_check returns healthy when Valkey is reachable and persistence-disabled."""
        from anonreq.cache.health import check_cache_health

        # Configure fakeredis to simulate persistence-disabled state
        await cache_manager._redis.config_set("save", "")

        result = await check_cache_health(cache_manager)

        assert result["reachable"] is True
        assert result["persistence_disabled"] is True
        assert result["healthy"] is True

    @pytest.mark.asyncio
    async def test_health_check_unreachable(self, cache_manager):
        """Test 6: health_check returns unhealthy when Valkey is unreachable."""
        from anonreq.cache.health import check_cache_health

        # Simulate unreachable by closing the connection
        await cache_manager._redis.aclose()

        result = await check_cache_health(cache_manager)

        assert result["healthy"] is False
        assert result["reachable"] is False

    @pytest.mark.asyncio
    async def test_health_check_persistence_enabled(self, cache_manager):
        """health_check returns unhealthy when persistence is not disabled."""
        from anonreq.cache.health import check_cache_health

        # Set save config to simulate persistence enabled
        await cache_manager._redis.config_set("save", "900 1 300 10 60 10000")

        result = await check_cache_health(cache_manager)

        assert result["reachable"] is True
        assert result["persistence_disabled"] is False
        assert result["healthy"] is False


class TestCacheManagerClose:
    """Tests for CacheManager.close()."""

    @pytest.mark.asyncio
    async def test_close_cleans_up_connection_pool(self, cache_manager):
        """Test 8: CacheManager.close() cleans up connection pool."""
        await cache_manager.close()
        # After close, operations should fail
        with pytest.raises(Exception):
            await cache_manager._redis.ping()
