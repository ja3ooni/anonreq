"""Unit tests for idempotent stream session cleanup."""

from __future__ import annotations

import pytest

from anonreq.streaming.cleanup import SessionCleanup


@pytest.mark.asyncio
async def test_cleanup_deletes_mapping_once(cache_manager) -> None:
    await cache_manager.store_mapping("default", "sess_1", {"[EMAIL_0]": "a@b.co"})
    cleanup = SessionCleanup(cache_manager, "default", "sess_1")

    await cleanup.cleanup("CLIENT_DISCONNECT")
    await cleanup.cleanup("FINISH")

    assert cleanup._cleaned is True
    assert cleanup.terminal_state == "CLIENT_DISCONNECT"
    assert await cache_manager.get_mapping("default", "sess_1") == {}


@pytest.mark.asyncio
async def test_cleanup_accepts_raw_redis(cache_manager) -> None:
    await cache_manager.store_mapping("default", "sess_2", {"[EMAIL_0]": "a@b.co"})
    cleanup = SessionCleanup(cache_manager._redis, "default", "sess_2")

    await cleanup.cleanup("FINISH")

    assert await cache_manager.get_mapping("default", "sess_2") == {}
