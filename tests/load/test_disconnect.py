"""Disconnect load test."""

from __future__ import annotations

import asyncio

import pytest

from anonreq.streaming.cleanup import SessionCleanup


@pytest.mark.load
@pytest.mark.asyncio
async def test_100_concurrent_disconnects() -> None:
    import fakeredis.aioredis

    cache = fakeredis.aioredis.FakeRedis(decode_responses=True)
    sessions = [f"sess_{i}" for i in range(100)]
    for session_id in sessions:
        await cache.hset(f"anonreq:default:{session_id}", mapping={"[EMAIL_0]": "a@b.co"})
        await cache.expire(f"anonreq:default:{session_id}", 300)

    cleanups = [SessionCleanup(cache, "default", session_id) for session_id in sessions]
    await asyncio.gather(*(cleanup.cleanup("CLIENT_DISCONNECT") for cleanup in cleanups))

    assert await cache.keys("*") == []
    await asyncio.gather(*(cleanup.cleanup("FINISH") for cleanup in cleanups))
    assert await cache.keys("*") == []
    await cache.aclose()
