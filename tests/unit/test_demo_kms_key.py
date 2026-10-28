"""Demo mode must refuse to start without ANONREQ_KMS_MASTER_KEY."""

import pytest

from anonreq.startup_checks import DemoKmsKeyMissingError, resolve_kms_master_key

KEY = "k" * 44


@pytest.mark.parametrize("value", [None, "", "   ", "short"])
def test_demo_mode_missing_key_fails_loudly(value):
    with pytest.raises(DemoKmsKeyMissingError, match="ANONREQ_KMS_MASTER_KEY"):
        resolve_kms_master_key("demo", value)


def test_demo_mode_case_insensitive():
    with pytest.raises(DemoKmsKeyMissingError):
        resolve_kms_master_key(" DEMO ", None)


def test_demo_mode_with_key_returns_bytes():
    assert resolve_kms_master_key("demo", KEY) == KEY.encode()


def test_development_without_key_returns_none():
    assert resolve_kms_master_key("development", None) is None


@pytest.mark.asyncio
async def test_demo_key_roundtrips_aes256gcm():
    from anonreq.kms.cache import InMemoryKeyCache
    from anonreq.kms.local import LocalAES256GCM

    kms = LocalAES256GCM(
        master_key=resolve_kms_master_key("demo", KEY),
        key_cache=InMemoryKeyCache(ttl_seconds=60),
    )
    ct = await kms.encrypt("tenant-a", b"Max Mustermann")
    assert b"Max Mustermann" not in ct
    assert await kms.decrypt("tenant-a", ct) == b"Max Mustermann"
