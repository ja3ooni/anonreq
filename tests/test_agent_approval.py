"""Tests for agent approval flow and tool result inspection.

Tests 18-02: Human Approval Flow
- ToolApprovalQueue: approval queue for tools suspended by oversight system
- ToolResultInspector: scan tool results for sensitive data before returning
"""

from __future__ import annotations

import pytest
from anonreq.agent.approval import ToolApprovalQueue, ApprovalStatus
from anonreq.agent.inspector import ToolResultInspector, InspectionResult, SensitivityLevel


class TestToolApprovalQueue:
    @pytest.fixture
    async def queue(self):
        from anonreq.cache.manager import CacheManager
        import fakeredis.aioredis
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        manager = CacheManager.__new__(CacheManager)
        manager._redis = fake_redis
        q = ToolApprovalQueue(manager)
        yield q
        await fake_redis.aclose()

    @pytest.mark.asyncio
    async def test_create_approval(self, queue):
        approval_id = await queue.create_approval(
            tool_name="send_email",
            tool_id="call_123",
            arguments={"to": "user@example.com"},
            tenant_id="default",
            session_id="session_001",
        )
        assert approval_id is not None
        assert len(approval_id) > 0

    @pytest.mark.asyncio
    async def test_get_pending_approvals(self, queue):
        await queue.create_approval("tool_a", "c1", {}, "default", "s1")
        await queue.create_approval("tool_b", "c2", {}, "default", "s2")
        pending = await queue.list_pending()
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_get_pending_filters_by_tenant(self, queue):
        await queue.create_approval("tool_a", "c1", {}, "tenant_a", "s1")
        await queue.create_approval("tool_b", "c2", {}, "tenant_b", "s2")
        pending_a = await queue.list_pending(tenant_id="tenant_a")
        assert len(pending_a) == 1
        assert pending_a[0].tenant_id == "tenant_a"

    @pytest.mark.asyncio
    async def test_approve_suspends_tool_execution(self, queue):
        aid = await queue.create_approval("send_email", "c1", {}, "default", "s1")
        result = await queue.resolve_approval(aid, "admin_1", approved=True)
        assert result is not None
        assert result.status == ApprovalStatus.APPROVED
        assert result.resolved_by == "admin_1"

    @pytest.mark.asyncio
    async def test_reject_suspends_tool_execution(self, queue):
        aid = await queue.create_approval("delete_all", "c1", {}, "default", "s1")
        result = await queue.resolve_approval(aid, "admin_1", approved=False)
        assert result is not None
        assert result.status == ApprovalStatus.REJECTED
        assert result.resolved_by == "admin_1"

    @pytest.mark.asyncio
    async def test_get_approval_by_id(self, queue):
        aid = await queue.create_approval("tool_a", "c1", {}, "default", "s1")
        entry = await queue.get_approval(aid)
        assert entry is not None
        assert entry.approval_id == aid
        assert entry.tool_name == "tool_a"

    @pytest.mark.asyncio
    async def test_get_nonexistent_approval_returns_none(self, queue):
        entry = await queue.get_approval("nonexistent")
        assert entry is None

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_approval_raises(self, queue):
        with pytest.raises(ValueError, match="not found"):
            await queue.resolve_approval("nonexistent", "admin", approved=True)

    @pytest.mark.asyncio
    async def test_double_approve_raises(self, queue):
        aid = await queue.create_approval("tool_a", "c1", {}, "default", "s1")
        await queue.resolve_approval(aid, "admin_1", approved=True)
        with pytest.raises(ValueError, match="already resolved"):
            await queue.resolve_approval(aid, "admin_2", approved=True)

    @pytest.mark.asyncio
    async def test_approval_entry_has_correct_fields(self, queue):
        aid = await queue.create_approval(
            tool_name="db_query",
            tool_id="call_42",
            arguments={"query": "SELECT * FROM users"},
            tenant_id="acme_corp",
            session_id="session_99",
            description="Read user data",
            risk_score=0.7,
        )
        entry = await queue.get_approval(aid)
        assert entry.tool_name == "db_query"
        assert entry.tool_id == "call_42"
        assert entry.tenant_id == "acme_corp"
        assert entry.session_id == "session_99"
        assert entry.description == "Read user data"
        assert entry.risk_score == 0.7
        assert entry.status == ApprovalStatus.PENDING

    @pytest.mark.asyncio
    async def test_list_pending_empty(self, queue):
        pending = await queue.list_pending()
        assert pending == []


class TestToolResultInspector:
    def test_inspector_clean_text(self):
        inspector = ToolResultInspector()
        result = inspector.inspect("This is clean text with no sensitive data")
        assert result.sensitivity == SensitivityLevel.NONE
        assert len(result.findings) == 0

    def test_inspector_detects_email(self):
        inspector = ToolResultInspector()
        result = inspector.inspect("Contact: john@example.com")
        assert result.sensitivity == SensitivityLevel.LOW
        assert len(result.findings) >= 1
        assert result.findings[0]["type"] == "email"

    def test_inspector_detects_phone(self):
        inspector = ToolResultInspector()
        result = inspector.inspect("Phone: +1-555-123-4567")
        assert result.sensitivity == SensitivityLevel.LOW
        assert len(result.findings) >= 1
        assert result.findings[0]["type"] == "phone"

    def test_inspector_detects_credit_card(self):
        inspector = ToolResultInspector()
        result = inspector.inspect("Card: 4111-1111-1111-1111")
        assert result.sensitivity >= SensitivityLevel.MEDIUM
        assert any(f["type"] == "credit_card" for f in result.findings)

    def test_inspector_detects_ssn(self):
        inspector = ToolResultInspector()
        result = inspector.inspect("SSN: 123-45-6789")
        assert result.sensitivity >= SensitivityLevel.HIGH
        assert any(f["type"] == "ssn" for f in result.findings)

    def test_inspector_detects_ip_address(self):
        inspector = ToolResultInspector()
        result = inspector.inspect("Server: 192.168.1.1")
        assert result.sensitivity == SensitivityLevel.LOW
        assert any(f["type"] == "ip" for f in result.findings)

    def test_inspector_json_result(self):
        inspector = ToolResultInspector()
        data = {"user": {"email": "test@example.com", "name": "John"}, "id": 42}
        result = inspector.inspect_json(data)
        assert result.sensitivity == SensitivityLevel.LOW

    def test_inspector_json_nested_sensitive(self):
        inspector = ToolResultInspector()
        data = {"user": {"ssn": "123-45-6789", "name": "John"}, "card": "4111-1111-1111-1111"}
        result = inspector.inspect_json(data)
        assert result.sensitivity >= SensitivityLevel.HIGH

    def test_inspector_clean_json(self):
        inspector = ToolResultInspector()
        data = {"name": "John", "age": 30, "items": [1, 2, 3]}
        result = inspector.inspect_json(data)
        assert result.sensitivity == SensitivityLevel.NONE
        assert len(result.findings) == 0

    def test_inspector_empty_string(self):
        inspector = ToolResultInspector()
        result = inspector.inspect("")
        assert result.sensitivity == SensitivityLevel.NONE
        assert len(result.findings) == 0

    def test_inspector_mixed_content(self):
        inspector = ToolResultInspector()
        text = (
            "User: John (john@example.com). "
            "SSN: 123-45-6789. Card: 4111-1111-1111-1111."
        )
        result = inspector.inspect(text)
        types = {f["type"] for f in result.findings}
        assert "email" in types
        assert "ssn" in types
        assert "credit_card" in types
        assert result.sensitivity >= SensitivityLevel.HIGH

    def test_inspection_result_has_correct_properties(self):
        result = InspectionResult(sensitivity=SensitivityLevel.HIGH, findings=[{"type": "ssn", "value": "***"}])
        assert result.sensitivity == SensitivityLevel.HIGH
        assert len(result.findings) == 1
        assert result.has_findings()
        result2 = InspectionResult(sensitivity=SensitivityLevel.NONE, findings=[])
        assert not result2.has_findings()

    def test_custom_patterns(self):
        inspector = ToolResultInspector(additional_patterns={
            "api_key": r"sk-[a-zA-Z0-9]{32,}",
        })
        result = inspector.inspect("Key: sk-abc123def456ghi789jkl012mno345pqr")
        types = {f["type"] for f in result.findings}
        assert "api_key" in types

    def test_scan_list_of_results(self):
        inspector = ToolResultInspector()
        results = [
            {"content": [{"text": "Email: user@example.com"}]},
            {"content": [{"text": "Clean data"}]},
        ]
        findings = inspector.scan_tool_results(results)
        assert len(findings) > 0
        assert any(f["type"] == "email" for f in findings)
