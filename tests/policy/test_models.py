"""Tests for policy domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from anonreq.policy.models import (
    PolicyAction,
    PolicyDecision,
    PolicyRule,
    RateLimitConfig,
    ResidencyRule,
    SpendBudget,
    UsageRecord,
)


class TestPolicyAction:
    def test_has_all_expected_values(self):
        assert PolicyAction.BLOCK == "BLOCK"
        assert PolicyAction.ALLOW == "ALLOW"
        assert PolicyAction.ROUTE_LOCAL == "ROUTE_LOCAL"
        assert PolicyAction.FLAG_AND_FORWARD == "FLAG_AND_FORWARD"
        assert PolicyAction.MONITOR == "MONITOR"

    def test_contains_expected_members(self):
        values = {m.value for m in PolicyAction}
        assert values == {"BLOCK", "ALLOW", "ROUTE_LOCAL", "FLAG_AND_FORWARD", "MONITOR"}


class TestPolicyRule:
    def test_valid_minimal(self):
        rule = PolicyRule(rule_id="test-1", action=PolicyAction.BLOCK)
        assert rule.rule_id == "test-1"
        assert rule.action == PolicyAction.BLOCK
        assert rule.enabled is True
        assert rule.version == 1
        assert rule.priority == 0

    def test_valid_full(self):
        rule = PolicyRule(
            rule_id="test-2",
            enabled=True,
            version=2,
            name="Test Rule",
            description="A test rule",
            action=PolicyAction.FLAG_AND_FORWARD,
            priority=100,
            conditions={"classification_level": "Highly Restricted"},
            metadata={"owner": "security"},
            tenant_id="tenant_acme",
        )
        assert rule.rule_id == "test-2"
        assert rule.tenant_id == "tenant_acme"
        assert rule.conditions == {"classification_level": "Highly Restricted"}

    def test_rejects_empty_rule_id(self):
        with pytest.raises(ValidationError):
            PolicyRule(rule_id="", action=PolicyAction.ALLOW)

    def test_rejects_invalid_action_enum(self):
        with pytest.raises(ValidationError):
            PolicyRule(rule_id="test-3", action="INVALID_ACTION")

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            PolicyRule(rule_id="test-4", action=PolicyAction.ALLOW, unknown_field="x")

    def test_global_rule_when_tenant_id_none(self):
        rule = PolicyRule(rule_id="global-1", action=PolicyAction.ALLOW)
        assert rule.tenant_id is None


class TestPolicyDecision:
    def test_valid_minimal(self):
        now = datetime.now(timezone.utc)
        decision = PolicyDecision(
            action=PolicyAction.BLOCK,
            matched_rule_ids=["rule-1"],
            decision_ts=now,
        )
        assert decision.action == PolicyAction.BLOCK
        assert decision.matched_rule_ids == ["rule-1"]
        assert decision.ttl_seconds == 60

    def test_default_ttl_is_60(self):
        now = datetime.now(timezone.utc)
        decision = PolicyDecision(
            action=PolicyAction.ALLOW,
            matched_rule_ids=[],
            decision_ts=now,
        )
        assert decision.ttl_seconds == 60

    def test_custom_ttl(self):
        now = datetime.now(timezone.utc)
        decision = PolicyDecision(
            action=PolicyAction.ALLOW,
            matched_rule_ids=[],
            decision_ts=now,
            ttl_seconds=120,
        )
        assert decision.ttl_seconds == 120

    def test_rejects_negative_ttl(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            PolicyDecision(
                action=PolicyAction.ALLOW,
                matched_rule_ids=[],
                decision_ts=now,
                ttl_seconds=-1,
            )

    def test_rejects_extra_fields(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            PolicyDecision(
                action=PolicyAction.ALLOW,
                matched_rule_ids=[],
                decision_ts=now,
                extra_field="bad",
            )

    def test_with_reason_and_enforcement(self):
        now = datetime.now(timezone.utc)
        decision = PolicyDecision(
            action=PolicyAction.BLOCK,
            matched_rule_ids=["rate-limit-1"],
            decision_ts=now,
            reason="Rate limit exceeded: 1001/1000 RPM",
            enforcement="HARD",
        )
        assert decision.reason == "Rate limit exceeded: 1001/1000 RPM"
        assert decision.enforcement == "HARD"


class TestRateLimitConfig:
    @pytest.mark.parametrize("field,value", [("rpm", 100), ("tpm", 5000), ("concurrent", 10)])
    def test_valid_values(self, field, value):
        config = RateLimitConfig(**{field: value})
        assert getattr(config, field) == value

    def test_defaults(self):
        config = RateLimitConfig()
        assert config.rpm == 1000
        assert config.tpm == 100000
        assert config.concurrent == 50
        assert config.enabled is True

    @pytest.mark.parametrize("field", ["rpm", "tpm", "concurrent"])
    def test_rejects_zero(self, field):
        with pytest.raises(ValidationError):
            RateLimitConfig(**{field: 0})

    @pytest.mark.parametrize("field", ["rpm", "tpm", "concurrent"])
    def test_rejects_negative(self, field):
        with pytest.raises(ValidationError):
            RateLimitConfig(**{field: -5})

    @pytest.mark.parametrize("field", ["rpm", "tpm", "concurrent"])
    def test_rejects_non_integer(self, field):
        with pytest.raises(ValidationError):
            RateLimitConfig(**{field: "abc"})

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            RateLimitConfig(rpm=100, tpm=1000, concurrent=5, extra="bad")


class TestSpendBudget:
    def test_valid_with_limits(self):
        budget = SpendBudget(daily_usd=Decimal("100"), monthly_usd=Decimal("3000"))
        assert budget.daily_usd == Decimal("100")
        assert budget.monthly_usd == Decimal("3000")
        assert budget.currency == "USD"
        assert budget.enabled is True

    def test_valid_none_limits(self):
        budget = SpendBudget(daily_usd=None, monthly_usd=None)
        assert budget.daily_usd is None
        assert budget.monthly_usd is None

    def test_rejects_negative_daily(self):
        with pytest.raises(ValidationError):
            SpendBudget(daily_usd=Decimal("-10"))

    def test_rejects_negative_monthly(self):
        with pytest.raises(ValidationError):
            SpendBudget(monthly_usd=Decimal("-50"))

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            SpendBudget(daily_usd=Decimal("100"), extra="bad")

    def test_accepts_float_input(self):
        budget = SpendBudget(daily_usd=100.50, monthly_usd=3000)
        assert budget.daily_usd == Decimal("100.50")


class TestUsageRecord:
    def test_valid_full(self):
        now = datetime.now(timezone.utc)
        record = UsageRecord(
            tenant_id="tenant_acme",
            rpm_current=50,
            tpm_current=1000,
            concurrent_current=5,
            daily_spend=Decimal("25.50"),
            monthly_spend=Decimal("500.00"),
            reset_at=now,
        )
        assert record.tenant_id == "tenant_acme"
        assert record.rpm_current == 50
        assert record.daily_spend == Decimal("25.50")

    def test_zero_counts(self):
        now = datetime.now(timezone.utc)
        record = UsageRecord(
            tenant_id="tenant_test",
            rpm_current=0,
            tpm_current=0,
            concurrent_current=0,
            daily_spend=Decimal("0"),
            monthly_spend=Decimal("0"),
            reset_at=now,
        )
        assert record.rpm_current == 0

    def test_rejects_negative_counts(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            UsageRecord(
                tenant_id="tenant_test",
                rpm_current=-1,
                tpm_current=0,
                concurrent_current=0,
                daily_spend=Decimal("0"),
                monthly_spend=Decimal("0"),
                reset_at=now,
            )

    def test_rejects_empty_tenant_id(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            UsageRecord(
                tenant_id="",
                rpm_current=0,
                tpm_current=0,
                concurrent_current=0,
                daily_spend=Decimal("0"),
                monthly_spend=Decimal("0"),
                reset_at=now,
            )

    def test_rejects_extra_fields(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            UsageRecord(
                tenant_id="t1",
                rpm_current=0,
                tpm_current=0,
                concurrent_current=0,
                daily_spend=Decimal("0"),
                monthly_spend=Decimal("0"),
                reset_at=now,
                extra="bad",
            )


class TestResidencyRule:
    def test_valid_minimal(self):
        rule = ResidencyRule(allowed_regions=["us-east-1", "eu-west-1"])
        assert "us-east-1" in rule.allowed_regions
        assert rule.blocked_regions == []
        assert rule.fallback_action == PolicyAction.BLOCK
        assert rule.required is False

    def test_valid_full(self):
        rule = ResidencyRule(
            allowed_regions=["us-east-1"],
            blocked_regions=["cn-north-1"],
            fallback_action=PolicyAction.FLAG_AND_FORWARD,
            required=True,
        )
        assert rule.required is True
        assert rule.fallback_action == PolicyAction.FLAG_AND_FORWARD

    def test_mixed_regions(self):
        rule = ResidencyRule(
            allowed_regions=["eu-west-1", "eu-central-1"],
            blocked_regions=["ap-southeast-1"],
            fallback_action=PolicyAction.ROUTE_LOCAL,
        )
        assert len(rule.allowed_regions) == 2
        assert len(rule.blocked_regions) == 1

    def test_rejects_empty_allowed_regions(self):
        with pytest.raises(ValidationError):
            ResidencyRule(allowed_regions=[])

    def test_rejects_invalid_region_code(self):
        with pytest.raises(ValidationError):
            ResidencyRule(allowed_regions=["not_a_valid_region"])

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            ResidencyRule(allowed_regions=["us-east-1"], extra="bad")
