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

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tenacity import stop_after_attempt


@pytest.fixture
def cache_manager():
    """Create a CacheManager backed by fakeredis."""
    import fakeredis.aioredis
    import redis.exceptions

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    configs = {}
    async def mock_config_get(name):
        return {name: configs.get(name, "")}
    async def mock_config_set(name, value):
        configs[name] = value
        return True
    fake_redis.config_get = mock_config_get
    fake_redis.config_set = mock_config_set

    closed = False
    original_aclose = fake_redis.aclose
    async def mock_aclose():
        nonlocal closed
        closed = True
        await original_aclose()

    original_ping = fake_redis.ping
    async def mock_ping():
        if closed:
            raise redis.exceptions.ConnectionError("Connection closed")
        return await original_ping()

    fake_redis.aclose = mock_aclose
    fake_redis.ping = mock_ping

    from anonreq.cache.manager import CacheManager

    manager = CacheManager.__new__(CacheManager)
    manager._redis = fake_redis
    manager._ttl = 300
    yield manager
    import asyncio

    with contextlib.suppress(RuntimeError):
        asyncio.run(fake_redis.aclose())


class _FailOncePipeline:
    def __init__(self, inner, fail_state, exc_factory):
        self._inner = inner
        self._fail_state = fail_state
        self._exc_factory = exc_factory

    async def __aenter__(self):
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return await self._inner.__aexit__(exc_type, exc, tb)

    def hset(self, *args, **kwargs):
        self._inner.hset(*args, **kwargs)
        return self

    def expire(self, *args, **kwargs):
        self._inner.expire(*args, **kwargs)
        return self

    async def execute(self):
        if self._fail_state["remaining"] > 0:
            self._fail_state["remaining"] -= 1
            raise self._exc_factory("READONLY")
        return await self._inner.execute()


class _RetryableRedisStub:
    def __init__(self):
        import fakeredis.aioredis
        import redis.exceptions

        self._redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        self._fail_state = {"remaining": 1}
        self.pipeline_calls = 0
        self.hgetall_calls = 0
        self.delete_calls = 0
        self._connection_error = redis.exceptions.ConnectionError
        self._readonly_error = redis.exceptions.ReadOnlyError

    def pipeline(self, transaction: bool = True):  # noqa: ARG002
        self.pipeline_calls += 1
        return _FailOncePipeline(
            self._redis.pipeline(transaction=True),
            self._fail_state,
            self._readonly_error,
        )

    async def hgetall(self, key: str):
        self.hgetall_calls += 1
        if self.hgetall_calls == 1:
            raise self._connection_error("temporary connection issue")
        return await self._redis.hgetall(key)

    async def delete(self, key: str):
        self.delete_calls += 1
        if self.delete_calls == 1:
            raise self._connection_error("temporary connection issue")
        return await self._redis.delete(key)

    async def aclose(self):
        await self._redis.aclose()


class TestCacheManagerTopology:
    """CacheManager topology selection and validation."""

    @patch("anonreq.cache.manager.redis.from_url")
    def test_standalone_url_uses_from_url(self, mock_from_url):
        from anonreq.cache.manager import CacheManager

        mock_from_url.return_value = MagicMock()

        manager = CacheManager("redis://localhost:6379/0?foo=bar")

        assert manager._redis is mock_from_url.return_value
        mock_from_url.assert_called_once_with(
            "redis://localhost:6379/0?foo=bar",
            decode_responses=True,
            health_check_interval=5,
            socket_connect_timeout=3,
        )

    @patch("anonreq.cache.manager.Sentinel")
    def test_sentinel_url_uses_master_for(self, mock_sentinel):
        from anonreq.cache.manager import CacheManager

        sentinel_instance = MagicMock()
        sentinel_instance.master_for.return_value = MagicMock()
        mock_sentinel.return_value = sentinel_instance

        manager = CacheManager("redis+sentinel://sentinel-a:26379,sentinel-b:26379/mymaster")

        assert manager._redis is sentinel_instance.master_for.return_value
        mock_sentinel.assert_called_once()
        sentinel_args, sentinel_kwargs = mock_sentinel.call_args
        assert sentinel_args[0] == [("sentinel-a", 26379), ("sentinel-b", 26379)]
        assert sentinel_kwargs["decode_responses"] is True
        assert sentinel_kwargs["health_check_interval"] == 5
        assert sentinel_kwargs["socket_connect_timeout"] == 3
        sentinel_instance.master_for.assert_called_once_with(
            "mymaster",
            decode_responses=True,
            health_check_interval=5,
            socket_connect_timeout=3,
        )

    @patch("anonreq.cache.manager.RedisCluster")
    def test_cluster_url_uses_startup_nodes(self, mock_cluster):
        from anonreq.cache.manager import CacheManager

        mock_cluster.return_value = MagicMock()

        manager = CacheManager("redis+cluster://cluster-a:7000,cluster-b:7001")

        assert manager._redis is mock_cluster.return_value
        mock_cluster.assert_called_once()
        kwargs = mock_cluster.call_args.kwargs
        assert [(node.host, node.port) for node in kwargs["startup_nodes"]] == [
            ("cluster-a", 7000),
            ("cluster-b", 7001),
        ]
        assert kwargs["decode_responses"] is True
        assert kwargs["health_check_interval"] == 5
        assert kwargs["socket_connect_timeout"] == 3

    @pytest.mark.parametrize(
        "redis_url",
        [
            "redis+sentinel://sentinel-a:26379",
            "redis+sentinel://sentinel-a:26379/svc/extra",
            "redis+sentinel://sentinel-a:not-a-port/mymaster",
            "redis+cluster://cluster-a:7000/",
            "redis+cluster://cluster-a:not-a-port",
            "redis+cluster://",
            "",
        ],
    )
    @patch("anonreq.cache.manager.redis.from_url")
    @patch("anonreq.cache.manager.Sentinel")
    @patch("anonreq.cache.manager.RedisCluster")
    def test_invalid_topology_fails_locally(
        self,
        mock_cluster,
        mock_sentinel,
        mock_from_url,
        redis_url,
    ):
        from anonreq.cache.manager import CacheManager

        with pytest.raises(ValueError, match="cache"):
            CacheManager(redis_url)

        mock_from_url.assert_not_called()
        mock_sentinel.assert_not_called()
        mock_cluster.assert_not_called()


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


class TestCacheManagerRetryBoundary:
    """Tests for the shared bounded retry helper."""

    @pytest.mark.asyncio
    async def test_store_mapping_retries_transient_readonly(self, monkeypatch):
        from anonreq.cache.manager import CacheManager

        manager = CacheManager.__new__(CacheManager)
        manager._redis = _RetryableRedisStub()
        manager._ttl = 300
        monkeypatch.setattr("anonreq.cache.manager.asyncio.sleep", AsyncMock(return_value=None))

        await manager.store_mapping("tenant", "sess", {"[EMAIL_0]": "alice@example.com"})

        assert manager._redis.pipeline_calls == 2
        stored = await manager._redis._redis.hgetall("anonreq:tenant:sess")
        assert stored == {"[EMAIL_0]": "alice@example.com"}

    @pytest.mark.asyncio
    async def test_get_mapping_retries_transient_connection(self, monkeypatch):
        from anonreq.cache.manager import CacheManager

        manager = CacheManager.__new__(CacheManager)
        manager._redis = _RetryableRedisStub()
        manager._ttl = 300
        await manager._redis._redis.hset("anonreq:tenant:sess", mapping={"[EMAIL_0]": "alice"})
        monkeypatch.setattr("anonreq.cache.manager.asyncio.sleep", AsyncMock(return_value=None))

        result = await manager.get_mapping("tenant", "sess")

        assert manager._redis.hgetall_calls == 2
        assert result == {"[EMAIL_0]": "alice"}

    @pytest.mark.asyncio
    async def test_delete_mapping_retries_transient_connection(self, monkeypatch):
        from anonreq.cache.manager import CacheManager

        manager = CacheManager.__new__(CacheManager)
        manager._redis = _RetryableRedisStub()
        manager._ttl = 300
        await manager._redis._redis.set("anonreq:tenant:sess", "value")
        monkeypatch.setattr("anonreq.cache.manager.asyncio.sleep", AsyncMock(return_value=None))

        await manager.delete_mapping("tenant", "sess")

        assert manager._redis.delete_calls == 2
        assert await manager._redis._redis.exists("anonreq:tenant:sess") == 0

    @pytest.mark.asyncio
    async def test_retry_exhaustion_translates_to_dependency_unavailable(self, monkeypatch):
        import redis.exceptions

        from anonreq.cache.manager import CacheManager
        from anonreq.exceptions import DependencyUnavailableError

        manager = CacheManager.__new__(CacheManager)
        failing_redis = MagicMock()

        async def fail_hgetall(_key):
            raise redis.exceptions.ConnectionError("temporary connection issue")

        failing_redis.hgetall = fail_hgetall
        manager._redis = failing_redis
        manager._ttl = 300
        monkeypatch.setattr("anonreq.cache.manager.asyncio.sleep", AsyncMock(return_value=None))
        monkeypatch.setattr(
            "anonreq.cache.manager.stop_after_delay",
            lambda _seconds: stop_after_attempt(1),
        )

        with pytest.raises(DependencyUnavailableError) as exc_info:
            await manager.get_mapping("tenant", "sess")

        assert exc_info.value.dependency == "valkey"

    @pytest.mark.asyncio
    async def test_non_retryable_errors_do_not_retry(self, monkeypatch):
        from anonreq.cache.manager import CacheManager

        manager = CacheManager.__new__(CacheManager)
        calls = {"count": 0}

        async def fail_once(_key):
            calls["count"] += 1
            raise ValueError("bad mapping")

        manager._redis = MagicMock()
        manager._redis.hgetall = fail_once
        manager._ttl = 300
        monkeypatch.setattr("anonreq.cache.manager.asyncio.sleep", AsyncMock(return_value=None))

        with pytest.raises(ValueError, match="bad mapping"):
            await manager.get_mapping("tenant", "sess")

        assert calls["count"] == 1

    def test_retry_wait_clamps_to_bounds(self, monkeypatch):
        from anonreq.cache.manager import _cache_retry_wait

        monkeypatch.setattr("anonreq.cache.manager.random.uniform", lambda _low, _high: 0.8)
        assert _cache_retry_wait(SimpleNamespace(attempt_number=1)) == 0.1

        monkeypatch.setattr("anonreq.cache.manager.random.uniform", lambda _low, _high: 1.2)
        assert _cache_retry_wait(SimpleNamespace(attempt_number=6)) == 2.0


class TestCacheManagerHealth:
    """Tests for cache health check."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, cache_manager):
        """Test 5: health_check returns healthy when Valkey is reachable and persistence-disabled."""  # noqa: E501
        from anonreq.cache.health import check_cache_health

        # Configure fakeredis to simulate persistence-disabled state
        await cache_manager._redis.config_set("save", "")

        result = await check_cache_health(cache_manager)

        assert result["reachable"] is True
        assert result["persistence_disabled"] is True
        assert result["healthy"] is True
        assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_unreachable(self, cache_manager):
        """Test 6: health_check returns unhealthy when Valkey is unreachable."""
        from anonreq.cache.health import check_cache_health

        # Simulate unreachable by closing the connection
        await cache_manager._redis.aclose()

        result = await check_cache_health(cache_manager)

        assert result["healthy"] is False
        assert result["reachable"] is False
        assert result["status"] == "unhealthy"
        assert "error" not in result

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
        assert result["status"] == "unhealthy"
        assert "error" not in result


class TestCacheManagerClose:
    """Tests for CacheManager.close()."""

    @pytest.mark.asyncio
    async def test_close_cleans_up_connection_pool(self, cache_manager):
        """Test 8: CacheManager.close() cleans up connection pool."""
        await cache_manager.close()
        # After close, operations should fail
        with pytest.raises(Exception):  # noqa: B017, PT011
            await cache_manager._redis.ping()
