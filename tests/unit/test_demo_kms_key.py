"""Demo mode must refuse to start without ANONREQ_KMS_MASTER_KEY."""

import pytest

from anonreq.startup_checks import (
    DemoKmsKeyMissingError,
    KmsKeyPlaceholderError,
    resolve_kms_master_key,
)

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


PLACEHOLDERS = [
    "<generate-32+-char-random-key>",
    "<base64-encoded-32-byte-key>",
    "  <generate-32+-char-random-key-padded-to-be-long-enough>  ",
    "<x>",
]


@pytest.mark.parametrize("env", ["development", "demo", "staging", "production"])
@pytest.mark.parametrize("value", PLACEHOLDERS)
def test_placeholder_key_rejected_in_every_mode(env, value):
    with pytest.raises(KmsKeyPlaceholderError, match="placeholder"):
        resolve_kms_master_key(env, value)


def test_placeholder_error_is_runtime_error_so_lifespan_aborts():
    assert issubclass(KmsKeyPlaceholderError, RuntimeError)


def test_development_with_real_key_returns_bytes():
    assert resolve_kms_master_key("development", KEY) == KEY.encode()
