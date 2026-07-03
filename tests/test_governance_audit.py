"""Tests for tool governance audit events.

Covers:
- All 7 event types produce correct serialized output
- Audit events contain metadata only — no tool arguments, raw PII, or tokens
- emit_tool_audit_event calls audit_logger with correct event
- Forbidden keys never appear in serialized output
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from anonreq.governance.audit import (
    FORBIDDEN_AUDIT_KEYS,
    ToolAuditEvent,
    ToolAuditEventType,
    emit_tool_audit_event,
    tool_audit_event_to_dict,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def make_event(
    event_type: ToolAuditEventType = ToolAuditEventType.TOOL_ALLOWED,
    **overrides,
) -> ToolAuditEvent:
    """Create a ToolAuditEvent with defaults for testing."""
    kwargs = {
        "event_type": event_type,
        "tool_name": "code_interpreter",
        "provider": "openai",
        "domain": "model",
        "permission": "allow",
        "tenant_id": "test_tenant",
        "session_id": "sess_test",
        "timestamp": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    }
    kwargs.update(overrides)
    return ToolAuditEvent(**kwargs)


# ── Tests ──────────────────────────────────────────────────────────────────


class TestToolAuditEventType:
    """ToolAuditEventType enum values match expected event names."""

    def test_event_type_values(self) -> None:
        """All 7 event types have correct values."""
        assert ToolAuditEventType.TOOL_ALLOWED.value == "allowed"
        assert ToolAuditEventType.TOOL_BLOCKED.value == "blocked"
        assert ToolAuditEventType.TOOL_APPROVAL_REQUIRED.value == "approval_required"
        assert ToolAuditEventType.TOOL_APPROVAL_GRANTED.value == "approval_granted"
        assert ToolAuditEventType.TOOL_APPROVAL_DENIED.value == "approval_denied"
        assert ToolAuditEventType.TOOL_RESULT_PII_DETECTED.value == "result_pii_detected"
        assert ToolAuditEventType.TOOL_RESULT_RECONSTRUCTION_DETECTED.value == "result_reconstruction_detected"

    def test_all_seven_types_exist(self) -> None:
        """Exactly 7 event type members exist."""
        members = list(ToolAuditEventType)
        assert len(members) == 7


class TestToolAuditEvent:
    """ToolAuditEvent dataclass fields and defaults."""

    def test_required_fields(self) -> None:
        """Required fields are present in the dataclass."""
        event = make_event()
        assert event.event_type == ToolAuditEventType.TOOL_ALLOWED
        assert event.tool_name == "code_interpreter"
        assert event.provider == "openai"

    def test_default_timestamp_is_utc(self) -> None:
        """Default timestamp is timezone-aware UTC."""
        event = ToolAuditEvent(
            event_type=ToolAuditEventType.TOOL_ALLOWED,
            tool_name="test",
            provider="test",
        )
        assert event.timestamp.tzinfo is not None
        assert event.timestamp.tzinfo.utcoffset(event.timestamp) is not None

    def test_optional_fields_default_to_none(self) -> None:
        """Optional fields default to None."""
        event = make_event()
        assert event.risk_level is None
        assert event.reconstruction_confidence is None
        assert event.decision_reason is None
        assert event.approved_by is None
        assert event.approval_note is None

    def test_forbidden_keys_defined(self) -> None:
        """Forbidden keys set is defined for property test use."""
        assert "tool_arguments" in FORBIDDEN_AUDIT_KEYS
        assert "raw_content" in FORBIDDEN_AUDIT_KEYS
        assert "pii_value" in FORBIDDEN_AUDIT_KEYS
        assert "token_value" in FORBIDDEN_AUDIT_KEYS


class TestToolAuditEventToDict:
    """Serialization tests."""

    def test_event_key_prefixed_with_tool(self) -> None:
        """The 'event' key is prefixed with 'tool_'."""
        for event_type in ToolAuditEventType:
            event = make_event(event_type=event_type)
            d = tool_audit_event_to_dict(event)
            assert d["event"] == f"tool_{event_type.value}"

    def test_required_fields_present(self) -> None:
        """All required metadata fields are in the serialized output."""
        event = make_event(
            session_id="sess_abc123",
            permission="block",
            risk_level="critical",
            decision_reason="Tool is blocked by policy",
        )
        d = tool_audit_event_to_dict(event)

        assert d["tool_name"] == "code_interpreter"
        assert d["provider"] == "openai"
        assert d["domain"] == "model"
        assert d["permission"] == "block"
        assert d["tenant_id"] == "test_tenant"
        assert d["session_id"] == "sess_abc123"
        assert d["risk_level"] == "critical"
        assert d["decision_reason"] == "Tool is blocked by policy"
        assert "timestamp" in d

    def test_none_fields_excluded(self) -> None:
        """Fields with None values are excluded from serialization."""
        event = make_event()
        d = tool_audit_event_to_dict(event)
        assert "risk_level" not in d
        assert "reconstruction_confidence" not in d
        assert "decision_reason" not in d
        assert "approved_by" not in d
        assert "approval_note" not in d

    def test_no_raw_tool_arguments(self) -> None:
        """Serialized output never contains tool arguments."""
        event = make_event()
        d = tool_audit_event_to_dict(event)
        for key in d:
            assert "argument" not in key.lower()

    def test_no_pii_values(self) -> None:
        """Serialized output never contains raw PII values."""
        event = make_event()
        d = tool_audit_event_to_dict(event)
        forbidden_values = [
            "[EMAIL_0]",
            "[PHONE_1]",
            "john@example.com",
        ]
        for v in d.values():
            if isinstance(v, str):
                for fv in forbidden_values:
                    assert fv not in v

    def test_no_token_patterns(self) -> None:
        """No token placeholder patterns [TYPE_N] in output."""
        import re

        event = make_event()
        d = tool_audit_event_to_dict(event)
        token_pattern = re.compile(r"\[[A-Z_]+_\d+\]")
        for v in d.values():
            if isinstance(v, str):
                assert not token_pattern.search(v)

    def test_reconstruction_fields_included(self) -> None:
        """Reconstruction detection events include confidence."""
        event = make_event(
            event_type=ToolAuditEventType.TOOL_RESULT_RECONSTRUCTION_DETECTED,
            reconstruction_confidence=0.85,
        )
        d = tool_audit_event_to_dict(event)
        assert d["reconstruction_confidence"] == 0.85

    def test_approval_fields_included(self) -> None:
        """Approval events include operator info."""
        event = make_event(
            event_type=ToolAuditEventType.TOOL_APPROVAL_GRANTED,
            approved_by="operator@example.com",
            approval_note="Approved after review",
        )
        d = tool_audit_event_to_dict(event)
        assert d["approved_by"] == "operator@example.com"
        assert d["approval_note"] == "Approved after review"


class TestEmitToolAuditEvent:
    """emit_tool_audit_event integration tests."""

    def test_calls_audit_logger(self) -> None:
        """emit_tool_audit_event calls audit_logger.info with correct args."""
        logger = MagicMock()
        event = make_event(
            event_type=ToolAuditEventType.TOOL_BLOCKED,
            tool_name="code_interpreter",
            risk_level="critical",
        )

        emit_tool_audit_event(event, logger)

        logger.info.assert_called_once()
        args, kwargs = logger.info.call_args
        # First positional arg is the event name (structlog sets event from this)
        assert args[0] == "tool_blocked"
        # event should NOT be in kwargs (it's set by structlog from first arg)
        assert "event" not in kwargs
        assert kwargs.get("tool_name") == "code_interpreter"
        assert kwargs.get("risk_level") == "critical"

    def test_all_event_types_emitted_correctly(self) -> None:
        """All 7 event types are emitted with correct 'event' field."""
        logger = MagicMock()

        for event_type in ToolAuditEventType:
            event = make_event(event_type=event_type)
            emit_tool_audit_event(event, logger)

        assert logger.info.call_count == 7

        expected_names = [
            "tool_allowed",
            "tool_blocked",
            "tool_approval_required",
            "tool_approval_granted",
            "tool_approval_denied",
            "tool_result_pii_detected",
            "tool_result_reconstruction_detected",
        ]
        actual_names = [call[0][0] for call in logger.info.call_args_list]
        for expected in expected_names:
            assert expected in actual_names, f"Missing event: {expected}"

    def test_emits_with_correct_event_name(self) -> None:
        """emit_tool_audit_event uses the correct event name as first arg."""
        logger = MagicMock()

        for event_type in ToolAuditEventType:
            if event_type == ToolAuditEventType.TOOL_ALLOWED:
                event = make_event(event_type=event_type, permission="allow")
                emit_tool_audit_event(event, logger)
                args, _ = logger.info.call_args
                assert args[0] == "tool_allowed"
                logger.reset_mock()

            elif event_type == ToolAuditEventType.TOOL_BLOCKED:
                event = make_event(event_type=event_type, permission="block")
                emit_tool_audit_event(event, logger)
                args, _ = logger.info.call_args
                assert args[0] == "tool_blocked"
                logger.reset_mock()

    def test_emits_no_forbidden_field_names(self) -> None:
        """Verify field names in emitted event do not match forbidden keys."""
        logger = MagicMock()

        for event_type in ToolAuditEventType:
            event = make_event(event_type=event_type)
            emit_tool_audit_event(event, logger)
            _, kwargs = logger.info.call_args
            for key in kwargs:
                assert key not in FORBIDDEN_AUDIT_KEYS, (
                    f"Forbidden field '{key}' found in event {event_type}"
                )
            logger.reset_mock()


