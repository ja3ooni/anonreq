"""Integration tests for KMS encryption with CacheManager.

Per D-08, verifies that CacheManager transparently encrypts before
Valkey write and decrypts after read using the KMS backend.
"""

import pytest

from anonreq.cache.manager import CacheManager
from anonreq.kms.cache import InMemoryKeyCache
from anonreq.kms.local import LocalAES256GCM


@pytest.fixture
def fake_redis():
    """Create a FakeRedis instance for testing."""
    fakeredis = pytest.importorskip("fakeredis.aioredis")
    return fakeredis.FakeRedis()


@pytest.fixture
def kms_client() -> LocalAES256GCM:
    master_key = LocalAES256GCM.generate_master_key()
    key_cache = InMemoryKeyCache(ttl_seconds=300, max_entries=1000)
    return LocalAES256GCM(master_key=master_key, key_cache=key_cache)


@pytest.fixture
def cache_with_kms(fake_redis, kms_client: LocalAES256GCM) -> CacheManager:
    cache = CacheManager._from_client(fake_redis, ttl=300)
    cache._kms = kms_client
    return cache


@pytest.fixture
def cache_without_kms(fake_redis) -> CacheManager:
    return CacheManager._from_client(fake_redis, ttl=300)


@pytest.mark.integration
class TestKMSEncryptionIntegration:
    """Integration tests for KMS + CacheManager."""

    @pytest.mark.anyio
    async def test_store_mapping_encrypts(
        self, fake_redis, cache_with_kms: CacheManager
    ) -> None:
        """D-08: store_mapping encrypts values before Valkey write."""
        mapping = {"TOKEN_1": "secret value"}
        await cache_with_kms.store_mapping("tenant-1", "session-1", mapping)

        # Read directly from fake Redis (bypass CacheManager decryption)
        raw = await fake_redis.hgetall("anonreq:tenant-1:session-1")
        # Value should be base64-encoded ciphertext, not plaintext
        assert raw["TOKEN_1"] != "secret value"
        assert len(raw["TOKEN_1"]) > 0

    @pytest.mark.anyio
    async def test_get_mapping_decrypts(
        self, cache_with_kms: CacheManager
    ) -> None:
        """D-08: get_mapping decrypts ciphertext after Valkey read."""
        mapping = {"TOKEN_2": "another secret"}
        await cache_with_kms.store_mapping("tenant-1", "session-2", mapping)
        retrieved = await cache_with_kms.get_mapping("tenant-1", "session-2")
        assert retrieved == mapping

    @pytest.mark.anyio
    async def test_roundtrip_with_key_format(
        self, cache_with_kms: CacheManager
    ) -> None:
        """Verify key format is anonreq:{tenant_id}:{session_id}."""
        mapping = {"TOKEN_3": "test"}
        await cache_with_kms.store_mapping("tenant-abc", "session-xyz", mapping)
        retrieved = await cache_with_kms.get_mapping("tenant-abc", "session-xyz")
        assert retrieved == mapping

    @pytest.mark.anyio
    async def test_different_tenants_different_ciphertexts(
        self, fake_redis, cache_with_kms: CacheManager
    ) -> None:
        """Different tenants produce different ciphertexts in Valkey."""
        mapping = {"TOKEN_4": "same value"}
        await cache_with_kms.store_mapping("tenant-x", "session-1", mapping)
        await cache_with_kms.store_mapping("tenant-y", "session-1", mapping)

        raw_x = await fake_redis.hgetall("anonreq:tenant-x:session-1")
        raw_y = await fake_redis.hgetall("anonreq:tenant-y:session-1")
        assert raw_x["TOKEN_4"] != raw_y["TOKEN_4"]

    @pytest.mark.anyio
    async def test_backward_compatibility_no_kms(
        self, cache_without_kms: CacheManager
    ) -> None:
        """CacheManager without KMS stores/retrieves plaintext."""
        mapping = {"TOKEN_5": "plaintext value"}
        await cache_without_kms.store_mapping("tenant-1", "session-5", mapping)
        retrieved = await cache_without_kms.get_mapping("tenant-1", "session-5")
        assert retrieved == mapping

    @pytest.mark.anyio
    async def test_decryption_failure_raises(
        self, fake_redis, cache_with_kms: CacheManager
    ) -> None:
        """Corrupted ciphertext raises DependencyUnavailableError."""
        from anonreq.exceptions import DependencyUnavailableError

        # Store a valid mapping first
        mapping = {"TOKEN_6": "valid"}
        await cache_with_kms.store_mapping("tenant-1", "session-6", mapping)

        # Corrupt the stored value
        await fake_redis.hset(
            "anonreq:tenant-1:session-6", "TOKEN_6", "corrupted_data"
        )

        with pytest.raises(DependencyUnavailableError):
            await cache_with_kms.get_mapping("tenant-1", "session-6")
