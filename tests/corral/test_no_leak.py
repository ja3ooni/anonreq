"""No-leak suite: canaries must never reach the provider, and must be restored for the caller.

Needs the real stack:  PRESIDIO_IMAGE=... docker compose -f docker-compose.corral-test.yml up -d --wait
Skipped automatically when the stack is not running.
"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest

GATEWAY = "http://127.0.0.1:18080"
STUB = "http://127.0.0.1:18081"
CHAT = {"Authorization": "Bearer corral-test-chat-key-0123456789abcdef0123456789"}
ADMIN = {"Authorization": "Bearer corral-test-admin-key-0123456789abcdef012345"}

# Values the detectors are expected to recognise in English text.
CANARIES = ["jane.doe@example.com", "Max Mustermann"]


def _stack_up() -> bool:
    try:
        return httpx.get(f"{GATEWAY}/health", headers=CHAT, timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(not _stack_up(), reason="corral-test stack is not running")


@pytest.fixture
def tenant() -> str:
    tenant_id = f"t-{uuid.uuid4().hex[:10]}"
    resp = httpx.put(
        f"{GATEWAY}/v1/admin/tenants/{tenant_id}", headers=ADMIN, timeout=10,
        json={"display_name": "test", "allowed_models": ["fast"]},
    )
    assert resp.status_code == 201
    httpx.post(f"{STUB}/__reset", timeout=5)
    return tenant_id


def _chat(tenant_id: str, text: str, *, model: str = "fast", stream: bool = False) -> httpx.Response:
    return httpx.post(
        f"{GATEWAY}/v1/chat/completions", timeout=60,
        headers={**CHAT, "X-AnonReq-Tenant-ID": tenant_id},
        json={"model": model, "stream": stream, "messages": [{"role": "user", "content": text}]},
    )


def _provider_saw() -> str:
    return json.dumps(httpx.get(f"{STUB}/__received", timeout=5).json())


def test_provider_never_sees_canaries_and_caller_gets_originals(tenant: str) -> None:
    text = f"Write to {CANARIES[0]} about {CANARIES[1]}"
    resp = _chat(tenant, text)
    assert resp.status_code == 200
    assert resp.headers["x-anonreq-processed"] == "true"
    seen = _provider_saw()
    for canary in CANARIES:
        assert canary not in seen, f"{canary!r} reached the provider"
    assert resp.json()["choices"][0]["message"]["content"] == f"Echo: {text}"


def test_streaming_restores_tokens_split_across_chunks(tenant: str) -> None:
    text = f"Please email {CANARIES[0]} today"
    with httpx.stream(
        "POST", f"{GATEWAY}/v1/chat/completions", timeout=60,
        headers={**CHAT, "X-AnonReq-Tenant-ID": tenant},
        json={"model": "fast", "stream": True, "messages": [{"role": "user", "content": text}]},
    ) as resp:
        assert resp.status_code == 200
        out = ""
        for line in resp.iter_lines():
            if line.startswith("data:") and "[DONE]" not in line:
                out += (json.loads(line[5:])["choices"][0]["delta"].get("content") or "")
    assert CANARIES[0] not in _provider_saw()
    assert out == f"Echo: {text}"


def test_control_text_without_personal_data_passes_unchanged(tenant: str) -> None:
    resp = _chat(tenant, "Suggest three hooks for a coffee reel")
    assert resp.status_code == 200
    assert "Suggest three hooks for a coffee reel" in _provider_saw()  # proves the assertion helper can see text


def test_model_outside_allow_list_is_rejected_before_the_provider(tenant: str) -> None:
    resp = _chat(tenant, "hi", model="smart")
    assert resp.status_code == 403
    assert httpx.get(f"{STUB}/__received", timeout=5).json() == []


def test_unknown_and_disabled_tenants_are_rejected(tenant: str) -> None:
    assert _chat("nobody-here", "hi").status_code == 400
    assert httpx.post(f"{GATEWAY}/v1/admin/tenants/{tenant}/disable", headers=ADMIN, timeout=10).status_code == 200
    assert _chat(tenant, "hi").status_code == 403
    assert httpx.get(f"{STUB}/__received", timeout=5).json() == []


def test_chat_key_cannot_manage_tenants() -> None:
    assert httpx.get(f"{GATEWAY}/v1/admin/tenants", headers=CHAT, timeout=5).status_code == 401


def _compose(*args: str) -> None:
    import os
    import subprocess

    subprocess.run(
        ["docker", "compose", "-f", "docker-compose.corral-test.yml", *args],
        check=True, capture_output=True, timeout=120,
        env={**os.environ, "PRESIDIO_IMAGE": os.environ.get("PRESIDIO_IMAGE", "mcr.microsoft.com/presidio-analyzer:latest")},
    )


def _wait_ready() -> None:
    import time

    for _ in range(60):
        try:
            if httpx.get(f"{GATEWAY}/health/ready", headers=CHAT, timeout=3).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise AssertionError("gateway did not become ready again")


@pytest.mark.parametrize("dependency", ["presidio-analyzer", "valkey"])
def test_fails_closed_when_a_dependency_is_down(tenant: str, dependency: str) -> None:
    """If detection or the cache is unavailable, nothing may be forwarded to the provider."""
    _compose("stop", dependency)
    try:
        resp = _chat(tenant, f"Write to {CANARIES[0]} about {CANARIES[1]}")
        assert resp.status_code >= 500, f"expected a 5xx, got {resp.status_code}"
        assert httpx.get(f"{STUB}/__received", timeout=5).json() == []
    finally:
        _compose("start", dependency)
        _wait_ready()
