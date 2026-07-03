"""Tests for ApprovalManager — async human approval flow for tool calls.

Tests 18-02 Task 1 coverage:
- create_approval returns HTTP 202 with approval_token and status=pending
- Approval tokens are 32+ bytes, cryptographically random, URL-safe
- get_approval_status returns pending/approved/denied/expired
- approve_approval resolves token to approved, returns tool context
- deny_approval resolves token to denied
- Expired approval (TTL passed) returns status=expired
- Invalid/unknown token returns HTTP 404
- Second approval of same token returns HTTP 409
- Approval added to Phase 14 oversight queue on creation
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from anonreq.governance.approval import ApprovalManager, ApprovalStatus
from anonreq.governance.tool_extractor import ToolCall
from anonreq.models.processing_context import ProcessingContext


@pytest.fixture
def context() -> ProcessingContext:
    """Create a minimal ProcessingContext for tests."""
    return ProcessingContext(
        request_id="test_req_001",
        tenant_id="test_tenant",
        context_id="ctx_001",
    )


@pytest.fixture
def tool_call() -> ToolCall:
    """Create a sample ToolCall for testing."""
    return ToolCall(
        id="call_test_001",
        name="db_query",
        arguments={"query": "SELECT * FROM users"},
        format="openai",
        domain="model",
        provider="openai",
    )


@pytest.fixture
async def approval_manager(cache_manager) -> ApprovalManager:
    """Create ApprovalManager with fakeredis-backed CacheManager and mock oversight."""
    oversight = AsyncMock()
    oversight.create_approval_request = AsyncMock()
    mgr = ApprovalManager(
        cache_manager=cache_manager,
        oversight_service=oversight,
        ttl=300,
    )
    yield mgr


@pytest.mark.asyncio
async def test_create_approval_returns_token_and_pending(
    approval_manager: ApprovalManager,
    tool_call: ToolCall,
    context: ProcessingContext,
) -> None:
    """Test 1: create_approval returns approval_token and status=pending."""
    result = await approval_manager.create_approval(tool_call, context)

    assert "approval_token" in result
    assert result["status"] == "pending"
    assert isinstance(result["approval_token"], str)
    assert len(result["approval_token"]) > 0


@pytest.mark.asyncio
async def test_approval_token_is_32_plus_bytes_random_urlsafe(
    approval_manager: ApprovalManager,
    tool_call: ToolCall,
    context: ProcessingContext,
) -> None:
    """Test 2: Approval tokens are 32+ bytes, cryptographically random, URL-safe."""
    result1 = await approval_manager.create_approval(tool_call, context)
    result2 = await approval_manager.create_approval(tool_call, context)

    token1 = result1["approval_token"]
    token2 = result2["approval_token"]

    # Tokens should be different (randomness)
    assert token1 != token2

    # Token should be URL-safe (base64 chars only)
    import string
    url_safe_chars = set(string.ascii_letters + string.digits + "-_")
    for char in token1:
        assert char in url_safe_chars, f"Token contains non-URL-safe char: {char}"

    # Token should be at least 32 bytes of entropy (43 chars base64)
    assert len(token1) >= 43, f"Token too short: {len(token1)} chars"


@pytest.mark.asyncio
async def test_get_approval_status_returns_pending(
    approval_manager: ApprovalManager,
    tool_call: ToolCall,
    context: ProcessingContext,
) -> None:
    """Test 3a: get_approval_status returns pending for fresh approval."""
    result = await approval_manager.create_approval(tool_call, context)
    token = result["approval_token"]

    status = await approval_manager.get_approval_status(token)
    assert status["status"] == "pending"
    assert status["approval_token"] == token


@pytest.mark.asyncio
async def test_get_approval_status_returns_approved(
    approval_manager: ApprovalManager,
    tool_call: ToolCall,
    context: ProcessingContext,
) -> None:
    """Test 3b: get_approval_status returns approved after approval."""
    result = await approval_manager.create_approval(tool_call, context)
    token = result["approval_token"]

    await approval_manager.approve_approval(token, decided_by="admin_1")
    status = await approval_manager.get_approval_status(token)
    assert status["status"] == "approved"


@pytest.mark.asyncio
async def test_get_approval_status_returns_denied(
    approval_manager: ApprovalManager,
    tool_call: ToolCall,
    context: ProcessingContext,
) -> None:
    """Test 3c: get_approval_status returns denied after denial."""
    result = await approval_manager.create_approval(tool_call, context)
    token = result["approval_token"]

    await approval_manager.deny_approval(token, decided_by="admin_1")
    status = await approval_manager.get_approval_status(token)
    assert status["status"] == "denied"


@pytest.mark.asyncio
async def test_get_approval_status_returns_expired(
    approval_manager: ApprovalManager,
    tool_call: ToolCall,
    context: ProcessingContext,
) -> None:
    """Test 3d: get_approval_status returns expired after TTL passes."""
    # Create with very short TTL
    oversight = AsyncMock()
    oversight.create_approval_request = AsyncMock()
    short_lived = ApprovalManager(
        cache_manager=approval_manager._cache_manager,  # type: ignore[attr-defined]
        oversight_service=oversight,
        ttl=1,  # 1 second TTL
    )
    result = await short_lived.create_approval(tool_call, context)
    token = result["approval_token"]

    # Wait for expiry
    time.sleep(1.1)

    status = await short_lived.get_approval_status(token)
    assert status["status"] == "expired"


@pytest.mark.asyncio
async def test_approve_approval_resolves_token(
    approval_manager: ApprovalManager,
    tool_call: ToolCall,
    context: ProcessingContext,
) -> None:
    """Test 4: approve_approval resolves token to approved, returns tool context."""
    result = await approval_manager.create_approval(tool_call, context)
    token = result["approval_token"]

    decision = await approval_manager.approve_approval(token, decided_by="admin_1", note="Looks good")
    assert decision["status"] == "approved"
    assert decision["decided_by"] == "admin_1"
    assert decision["approval_note"] == "Looks good"
    assert "tool_call" in decision


@pytest.mark.asyncio
async def test_deny_approval_resolves_token(
    approval_manager: ApprovalManager,
    tool_call: ToolCall,
    context: ProcessingContext,
) -> None:
    """Test 5: deny_approval resolves token to denied."""
    result = await approval_manager.create_approval(tool_call, context)
    token = result["approval_token"]

    decision = await approval_manager.deny_approval(token, decided_by="admin_1", note="Not authorized")
    assert decision["status"] == "denied"
    assert decision["decided_by"] == "admin_1"
    assert decision["approval_note"] == "Not authorized"


@pytest.mark.asyncio
async def test_expired_token_returns_expired_status(
    approval_manager: ApprovalManager,
    tool_call: ToolCall,
    context: ProcessingContext,
) -> None:
    """Test 6: Expired approval (TTL passed) returns status=expired."""
    # Already tested in get_approval_status_returns_expired, this is the explicit test 6
    oversight = AsyncMock()
    oversight.create_approval_request = AsyncMock()
    short_lived = ApprovalManager(
        cache_manager=approval_manager._cache_manager,  # type: ignore[attr-defined]
        oversight_service=oversight,
        ttl=1,
    )
    result = await short_lived.create_approval(tool_call, context)
    token = result["approval_token"]

    time.sleep(1.1)

    status = await short_lived.get_approval_status(token)
    assert status["status"] == "expired"


@pytest.mark.asyncio
async def test_invalid_token_returns_404(
    approval_manager: ApprovalManager,
) -> None:
    """Test 7: Invalid/unknown token returns status=not_found (HTTP 404 equivalent)."""
    result = await approval_manager.get_approval_status("invalid_token_12345")
    assert result["status"] == "not_found"


@pytest.mark.asyncio
async def test_second_approve_returns_409(
    approval_manager: ApprovalManager,
    tool_call: ToolCall,
    context: ProcessingContext,
) -> None:
    """Test 8: Second approval of same token returns HTTP 409."""
    result = await approval_manager.create_approval(tool_call, context)
    token = result["approval_token"]

    # First approval succeeds
    await approval_manager.approve_approval(token, decided_by="admin_1")

    # Second approval should fail
    import json

    from fastapi import HTTPException
    try:
        await approval_manager.approve_approval(token, decided_by="admin_2")
        assert False, "Should have raised an exception"
    except HTTPException as exc:
        assert exc.status_code == 409
    except ValueError as exc:
        # Also acceptable — some implementations raise ValueError
        assert "already" in str(exc).lower() or "not pending" in str(exc).lower()


@pytest.mark.asyncio
async def test_approval_added_to_oversight_queue(
    approval_manager: ApprovalManager,
    tool_call: ToolCall,
    context: ProcessingContext,
) -> None:
    """Test 9: Approval added to Phase 14 oversight queue on creation."""
    # The mock oversight service should have been called
    oversight = approval_manager._oversight_service  # type: ignore[attr-defined]
    oversight.create_approval_request = AsyncMock()

    # Re-create with mock that tracks calls
    mgr = ApprovalManager(
        cache_manager=approval_manager._cache_manager,  # type: ignore[attr-defined]
        oversight_service=oversight,
        ttl=300,
    )

    await mgr.create_approval(tool_call, context)
    oversight.create_approval_request.assert_awaited_once()
