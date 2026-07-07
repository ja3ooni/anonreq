from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from anonreq.agent.config import ToolGovernanceConfig
from anonreq.agent.result_sanitizer import REDACTED_ERROR, ToolResultSanitizer
from anonreq.agent.schema import ToolResult


@dataclass
class FakeDetection:
    entity_type: str
    start: int
    end: int
    score: float = 0.99


class FakeDetectionEngine:
    async def detect(self, text: str) -> list[Any]:
        detections = []
        for value, entity_type in [
            ("alice@example.com", "EMAIL"),
            ("555-0100", "PHONE"),
        ]:
            start = text.find(value)
            if start >= 0:
                detections.append(FakeDetection(entity_type, start, start + len(value)))
        return detections


@pytest.mark.asyncio
async def test_tool_result_forced_through_detection_engine_and_tokenized():
    sanitizer = ToolResultSanitizer(
        detection_engine=FakeDetectionEngine(),
        tokenization_engine=None,
        config=ToolGovernanceConfig(),
    )

    result = await sanitizer.sanitize_result(ToolResult(
        tool_name="lookup_user",
        content={"email": "alice@example.com"},
        id="call_1",
        type="openai",
    ))

    assert result.content["email"].startswith("[EMAIL_")
    assert "alice@example.com" not in str(result.content)


@pytest.mark.asyncio
async def test_sensitive_values_tokenized_with_placeholders_and_keys_preserved():
    sanitizer = ToolResultSanitizer(
        detection_engine=FakeDetectionEngine(),
        tokenization_engine=None,
        config=ToolGovernanceConfig(),
    )
    content = {
        "columns": ["email", "phone"],
        "rows": [{"email": "alice@example.com", "phone": "555-0100"}],
    }

    result = await sanitizer.sanitize_result(ToolResult(
        tool_name="query_db",
        content=content,
        id="call_2",
        type="mcp",
    ))

    assert list(result.content.keys()) == ["columns", "rows"]
    assert result.content["columns"] == ["email", "phone"]
    assert result.content["rows"][0]["email"].startswith("[EMAIL_")
    assert result.content["rows"][0]["phone"].startswith("[PHONE_")


@pytest.mark.asyncio
async def test_stack_traces_in_tool_result_redacted():
    sanitizer = ToolResultSanitizer(None, None, ToolGovernanceConfig())
    value = 'Traceback (most recent call last):\n  File "/srv/app.py", line 7, in run'

    result = await sanitizer.sanitize_result(ToolResult(
        tool_name="tool",
        content={"error": value},
        id="call_3",
        type="openai",
    ))

    assert result.content["error"] == REDACTED_ERROR


@pytest.mark.asyncio
async def test_internal_ips_detected_and_redacted():
    sanitizer = ToolResultSanitizer(None, None, ToolGovernanceConfig())

    result = await sanitizer.sanitize_result(ToolResult(
        tool_name="tool",
        content={"error": "database host 10.1.2.3 refused connection"},
        id="call_4",
        type="anthropic",
    ))

    assert result.content["error"] == f"database host {REDACTED_ERROR} refused connection"


@pytest.mark.asyncio
async def test_environment_variable_patterns_detected_and_redacted():
    sanitizer = ToolResultSanitizer(None, None, ToolGovernanceConfig())

    result = await sanitizer.sanitize_result(ToolResult(
        tool_name="tool",
        content={"error": "missing $AWS_SECRET_ACCESS_KEY and %DB_PASSWORD%"},
        id="call_5",
        type="mcp",
    ))

    assert result.content["error"] == f"missing {REDACTED_ERROR} and {REDACTED_ERROR}"


@pytest.mark.asyncio
async def test_audit_events_record_sanitization_and_redaction():
    sanitizer = ToolResultSanitizer(
        detection_engine=FakeDetectionEngine(),
        tokenization_engine=None,
        config=ToolGovernanceConfig(),
    )

    result = await sanitizer.sanitize_result(ToolResult(
        tool_name="tool",
        content={"email": "alice@example.com", "error": "host 192.168.1.2 failed"},
        id="call_6",
        type="mcp",
    ))

    events = sanitizer.audit_events
    assert "agent_tool_result_sanitized" in events
    assert "agent_tool_error_redacted" in events
    assert "_anonreq_audit_events" not in result.content
