"""Tests for Policy Decision Audit Publisher."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from prometheus_client import CollectorRegistry

from anonreq.models.processing_context import ProcessingContext
from anonreq.policy.audit import DecisionAuditPublisher, PolicyAuditEvent
from anonreq.policy.metrics import PolicyMetrics
from anonreq.policy.models import PolicyAction, PolicyDecision


class MockLogger:
    def __init__(self) -> None:
        self.emitted: list[tuple[str, dict]] = []

    def info(self, event: str, **kwargs: Any) -> None:
        self.emitted.append((event, kwargs))


@pytest.fixture
def mock_logger() -> MockLogger:
    return MockLogger()


@pytest.fixture
def test_registry() -> CollectorRegistry:
    return CollectorRegistry()


@pytest.fixture
def audit_publisher(mock_logger) -> DecisionAuditPublisher:
    return DecisionAuditPublisher(mock_logger)


def test_policy_decision_recorded(mock_logger, audit_publisher, test_registry, monkeypatch):
    # Set up test metrics on a custom registry so it doesn't pollute the global registry
    metrics = PolicyMetrics(test_registry)
    monkeypatch.setattr("anonreq.policy.audit.register_policy_metrics", lambda: metrics)

    ctx = ProcessingContext(request_id="session_123", tenant_id="tenant_abc")
    decision = PolicyDecision(
        action=PolicyAction.BLOCK,
        matched_rule_ids=["rule_001"],
        decision_ts=datetime.now(timezone.utc),
        enforcement="403",
    )

    import asyncio
    asyncio.run(audit_publisher.publish_decision(ctx, decision))

    assert len(mock_logger.emitted) == 1
    event_type, kwargs = mock_logger.emitted[0]
    assert event_type == "policy_decision_recorded"
    assert kwargs["tenant_id"] == "tenant_abc"
    assert kwargs["session_id"] == "session_123"
    assert kwargs["action"] == "BLOCK"
    assert kwargs["matched_rule_ids"] == ["rule_001"]
    assert kwargs["decision_id"] == "403"


def test_rate_limit_exceeded(mock_logger, audit_publisher, test_registry, monkeypatch):
    metrics = PolicyMetrics(test_registry)
    monkeypatch.setattr("anonreq.policy.audit.register_policy_metrics", lambda: metrics)

    import asyncio
    asyncio.run(audit_publisher.publish_rate_limit("tenant_abc", "RPM", 1005, 1000))

    assert len(mock_logger.emitted) == 1
    event_type, kwargs = mock_logger.emitted[0]
    assert event_type == "rate_limit_exceeded"
    assert kwargs["tenant_id"] == "tenant_abc"
    assert kwargs["limit_type"] == "RPM"
    assert kwargs["current_value"] == 1005
    assert kwargs["limit"] == 1000


def test_spend_limit_exceeded(mock_logger, audit_publisher, test_registry, monkeypatch):
    metrics = PolicyMetrics(test_registry)
    monkeypatch.setattr("anonreq.policy.audit.register_policy_metrics", lambda: metrics)

    import asyncio
    asyncio.run(audit_publisher.publish_spend_limit("tenant_abc", "daily", Decimal("50.25"), Decimal("50.00"), "USD"))

    assert len(mock_logger.emitted) == 1
    event_type, kwargs = mock_logger.emitted[0]
    assert event_type == "spend_limit_exceeded"
    assert kwargs["tenant_id"] == "tenant_abc"
    assert kwargs["budget_type"] == "daily"
    assert kwargs["current_spend"] == 50.25
    assert kwargs["budget_limit"] == 50.00
    assert kwargs["currency"] == "USD"


def test_routing_policy_violation(mock_logger, audit_publisher):
    import asyncio
    asyncio.run(audit_publisher.publish_routing_violation("tenant_abc", "openai", "eu-west-1", ["us-east-1"]))

    assert len(mock_logger.emitted) == 1
    event_type, kwargs = mock_logger.emitted[0]
    assert event_type == "routing_policy_violation"
    assert kwargs["tenant_id"] == "tenant_abc"
    assert kwargs["provider"] == "openai"
    assert kwargs["region"] == "eu-west-1"
    assert kwargs["allowed_regions"] == ["us-east-1"]


def test_classification_block(mock_logger, audit_publisher):
    import asyncio
    asyncio.run(audit_publisher.publish_classification_block("tenant_abc", "Confidential", "rule_class_01"))

    assert len(mock_logger.emitted) == 1
    event_type, kwargs = mock_logger.emitted[0]
    assert event_type == "classification_block"
    assert kwargs["tenant_id"] == "tenant_abc"
    assert kwargs["classification_level"] == "Confidential"
    assert kwargs["matched_rule_id"] == "rule_class_01"


def test_budget_reset(mock_logger, audit_publisher):
    import asyncio
    asyncio.run(audit_publisher.publish_budget_reset("tenant_abc", "monthly"))

    assert len(mock_logger.emitted) == 1
    event_type, kwargs = mock_logger.emitted[0]
    assert event_type == "budget_reset"
    assert kwargs["tenant_id"] == "tenant_abc"
    assert kwargs["budget_type"] == "monthly"
    assert "reset_at" in kwargs


def test_metadata_only_allowlist_enforcement(mock_logger, audit_publisher):
    # Pass some raw values and internal secret keys (not in allowlist)
    event = audit_publisher._build_event(
        "policy_decision_recorded",
        tenant_id="tenant_abc",
        session_id="session_123",
        raw_payload="Sensitive raw text John Doe",
        secret_key="abc123secret",
        token_value="[EMAIL_0]",
        allowed_regions=["us-east-1"],
    )

    assert "raw_payload" not in event.metadata
    assert "secret_key" not in event.metadata
    assert "token_value" not in event.metadata
    assert event.metadata["allowed_regions"] == ["us-east-1"]


def test_no_sensitive_values_in_any_event(mock_logger, audit_publisher):
    # Ensure standard forbidden terms like payload, secret, token, pii, key are strictly blocked
    # unless explicitly allowed.
    event = audit_publisher._build_event(
        "policy_decision_recorded",
        tenant_id="tenant_abc",
        payload_content="raw text",
        token="[PHONE_0]",
        pii_value="Bob Smith",
        api_secret="sk-12345",
    )
    assert not any(k in event.metadata for k in ("payload_content", "token", "pii_value", "api_secret"))
