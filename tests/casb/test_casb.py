"""Tests for CASB Policy Engine.

Tests:
- AI SaaS classification: sanctioned / tolerated / unsanctioned
- Per-app policies with risk scores
- Action resolver: sanctioned→allow, tolerated→alert, unsanctioned→block
- CASB enforcement on request intercept
- User group resolution and overrides
- Audit events (unsanctioned_ai_access)
- Usage monitoring telemetry aggregation
"""

from __future__ import annotations

import pytest

from anonreq.casb.classifier import (
    AppClassification,
    AppPolicy,
    CASBClassifier,
    ClassificationAction,
)
from anonreq.casb.engine import CASBEngine, CASBEvent


class TestAppPolicy:
    """Tests for AppPolicy data model."""

    def test_app_policy_creation(self):
        """AppPolicy stores all required fields."""
        policy = AppPolicy(
            app_id="chatgpt",
            classification=AppClassification.SANCTIONED,
            risk_score=18,
            allowed_groups=["engineering", "product"],
            action=ClassificationAction.ALLOW,
            notes="Enterprise contract",
        )
        assert policy.app_id == "chatgpt"
        assert policy.classification == AppClassification.SANCTIONED
        assert policy.action == ClassificationAction.ALLOW

    def test_app_policy_default_action(self):
        """AppPolicy defaults action to BLOCK for unsanctioned."""
        policy = AppPolicy(
            app_id="unknown_app",
            classification=AppClassification.UNSANCTIONED,
            risk_score=80,
            allowed_groups=[],
        )
        assert policy.action == ClassificationAction.BLOCK

    def test_app_policy_no_notes(self):
        """AppPolicy notes field is optional."""
        policy = AppPolicy(
            app_id="test",
            classification=AppClassification.TOLERATED,
            risk_score=35,
            allowed_groups=["eng"],
            action=ClassificationAction.ALERT,
        )
        assert policy.notes is None


class TestCASBClassifier:
    """Tests for CASBClassifier."""

    def setup_method(self):
        self.policies = {
            "chatgpt": AppPolicy(
                app_id="chatgpt",
                classification=AppClassification.SANCTIONED,
                risk_score=18,
                allowed_groups=["engineering", "product"],
                action=ClassificationAction.ALLOW,
                notes="Approved",
            ),
            "claude": AppPolicy(
                app_id="claude",
                classification=AppClassification.SANCTIONED,
                risk_score=18,
                allowed_groups=["engineering", "research"],
                action=ClassificationAction.ALLOW,
                notes="Approved",
            ),
            "deepseek": AppPolicy(
                app_id="deepseek",
                classification=AppClassification.UNSANCTIONED,
                risk_score=89,
                allowed_groups=[],
                action=ClassificationAction.BLOCK,
                notes="Not approved",
            ),
            "github_copilot": AppPolicy(
                app_id="github_copilot",
                classification=AppClassification.TOLERATED,
                risk_score=35,
                allowed_groups=["engineering"],
                action=ClassificationAction.ALERT,
                notes="Personal accounts",
            ),
        }
        self.classifier = CASBClassifier(self.policies)

    def test_classify_sanctioned_app(self):
        """Sanctioned app returns SANCTIONED classification."""
        result = self.classifier.classify("chatgpt")
        assert result is not None
        assert result.classification == AppClassification.SANCTIONED

    def test_classify_unsanctioned_app(self):
        """Unsanctioned app returns UNSANCTIONED classification."""
        result = self.classifier.classify("deepseek")
        assert result is not None
        assert result.classification == AppClassification.UNSANCTIONED

    def test_classify_tolerated_app(self):
        """Tolerated app returns TOLERATED classification."""
        result = self.classifier.classify("github_copilot")
        assert result is not None
        assert result.classification == AppClassification.TOLERATED

    def test_classify_unknown_app(self):
        """Unknown app returns None."""
        result = self.classifier.classify("unknown_app_service")
        assert result is None

    def test_resolve_action_sanctioned(self):
        """Sanctioned → ALLOW."""
        policy = self.policies["chatgpt"]
        assert self.classifier.resolve_action(policy) == ClassificationAction.ALLOW

    def test_resolve_action_tolerated(self):
        """Tolerated → ALERT."""
        policy = self.policies["github_copilot"]
        assert self.classifier.resolve_action(policy) == ClassificationAction.ALERT

    def test_resolve_action_unsanctioned(self):
        """Unsanctioned → BLOCK."""
        policy = self.policies["deepseek"]
        assert self.classifier.resolve_action(policy) == ClassificationAction.BLOCK

    def test_is_user_allowed_group_match(self):
        """User in allowed group returns True."""
        result = self.classifier.classify("chatgpt")
        assert result is not None
        assert self.classifier.is_user_allowed(result, "engineering") is True

    def test_is_user_allowed_no_match(self):
        """User not in allowed group returns False."""
        result = self.classifier.classify("chatgpt")
        assert result is not None
        assert self.classifier.is_user_allowed(result, "marketing") is False

    def test_is_user_allowed_unsanctioned(self):
        """Unsanctioned app with no allowed groups returns False for any user."""
        result = self.classifier.classify("deepseek")
        assert result is not None
        assert self.classifier.is_user_allowed(result, "engineering") is False

    def test_get_risk_score(self):
        """Risk score retrieved correctly."""
        score = self.classifier.get_risk_score("deepseek")
        assert score == 89

    def test_get_risk_score_unknown(self):
        """Unknown app returns None for risk score."""
        score = self.classifier.get_risk_score("unknown_app")
        assert score is None

    def test_list_apps(self):
        """List apps returns all configured policy app IDs."""
        apps = self.classifier.list_apps()
        assert len(apps) == 4
        assert "chatgpt" in apps
        assert "deepseek" in apps

    def test_classify_by_hostname(self):
        """Classify by hostname maps to app_id."""
        classifier = CASBClassifier(self.policies)
        hostname_map = {
            "chat.openai.com": "chatgpt",
            "api.openai.com": "chatgpt",
            "claude.ai": "claude",
            "api.anthropic.com": "claude",
        }
        classifier.set_hostname_mapping(hostname_map)
        result = classifier.classify_by_hostname("chat.openai.com")
        assert result is not None
        assert result.app_id == "chatgpt"

    def test_classify_by_hostname_unknown(self):
        """Classify by unknown hostname returns None."""
        classifier = CASBClassifier(self.policies)
        classifier.set_hostname_mapping({"known.ai": "known_app"})
        result = classifier.classify_by_hostname("unknown.ai")
        assert result is None


class TestCASBEngine:
    """Tests for CASB engine — enforcement, events, telemetry."""

    def setup_method(self):
        policies = {
            "chatgpt": AppPolicy(
                app_id="chatgpt",
                classification=AppClassification.SANCTIONED,
                risk_score=18,
                allowed_groups=["engineering"],
                action=ClassificationAction.ALLOW,
            ),
            "deepseek": AppPolicy(
                app_id="deepseek",
                classification=AppClassification.UNSANCTIONED,
                risk_score=89,
                allowed_groups=[],
                action=ClassificationAction.BLOCK,
            ),
            "github_copilot": AppPolicy(
                app_id="github_copilot",
                classification=AppClassification.TOLERATED,
                risk_score=35,
                allowed_groups=["engineering"],
                action=ClassificationAction.ALERT,
            ),
        }
        classifier = CASBClassifier(policies)
        overrides = {
            "executive": {"deepseek": AppPolicy(
                app_id="deepseek",
                classification=AppClassification.UNSANCTIONED,
                risk_score=89,
                allowed_groups=["executive"],
                action=ClassificationAction.ALLOW,
            )},
        }
        self.engine = CASBEngine(classifier=classifier, overrides=overrides)

    @pytest.mark.asyncio
    async def test_enforce_sanctioned_allows(self):
        """Sanctioned app with matching group → ALLOW."""
        result = await self.engine.enforce(
            app_id="chatgpt",
            user_id="alice",
            user_groups=["engineering"],
        )
        assert result.action == ClassificationAction.ALLOW
        assert result.blocked is False

    @pytest.mark.asyncio
    async def test_enforce_unsanctioned_blocks(self):
        """Unsanctioned app → BLOCK."""
        result = await self.engine.enforce(
            app_id="deepseek",
            user_id="bob",
            user_groups=["engineering"],
        )
        assert result.action == ClassificationAction.BLOCK
        assert result.blocked is True

    @pytest.mark.asyncio
    async def test_enforce_tolerated_alerts(self):
        """Tolerated app → ALERT, not blocked."""
        result = await self.engine.enforce(
            app_id="github_copilot",
            user_id="charlie",
            user_groups=["engineering"],
        )
        assert result.action == ClassificationAction.ALERT
        assert result.blocked is False

    @pytest.mark.asyncio
    async def test_enforce_override_allows_blocked_app(self):
        """Override allows executive to use deepseek."""
        result = await self.engine.enforce(
            app_id="deepseek",
            user_id="ceo",
            user_groups=["executive"],
        )
        assert result.action == ClassificationAction.ALLOW
        assert result.blocked is False

    @pytest.mark.asyncio
    async def test_enforce_unknown_app_blocks(self):
        """Unknown app defaults to BLOCK."""
        result = await self.engine.enforce(
            app_id="unknown_service",
            user_id="alice",
            user_groups=[],
        )
        assert result.blocked is True
        assert result.action == ClassificationAction.BLOCK

    @pytest.mark.asyncio
    async def test_enforce_generates_audit_event_on_block(self):
        """Blocked requests generate unsanctioned_ai_access audit event."""
        result = await self.engine.enforce(
            app_id="deepseek",
            user_id="bob",
            user_groups=["engineering"],
        )
        assert result.audit_event is not None
        assert result.audit_event.event_type == "unsanctioned_ai_access"
        assert result.audit_event.application == "deepseek"
        assert result.audit_event.user_id == "bob"

    @pytest.mark.asyncio
    async def test_enforce_no_audit_event_on_allow(self):
        """Allowed requests do not generate audit events."""
        result = await self.engine.enforce(
            app_id="chatgpt",
            user_id="alice",
            user_groups=["engineering"],
        )
        assert result.audit_event is None

    @pytest.mark.asyncio
    async def test_enforce_audit_event_on_alert(self):
        """Tolerated/alerted requests generate audit event."""
        result = await self.engine.enforce(
            app_id="github_copilot",
            user_id="charlie",
            user_groups=["engineering"],
        )
        assert result.audit_event is not None
        assert result.audit_event.event_type == "unsanctioned_ai_access"

    @pytest.mark.asyncio
    async def test_audit_event_metadata_only(self):
        """Audit events contain metadata, no raw values."""
        result = await self.engine.enforce(
            app_id="deepseek",
            user_id="bob",
            user_groups=["engineering"],
        )
        event = result.audit_event
        assert event is not None
        assert "bob" in event.user_id
        assert "deepseek" in event.application
        # No raw payload data
        assert "api_key" not in event.to_dict()

    @pytest.mark.asyncio
    async def test_telemetry_records_enforcement(self):
        """Engine records telemetry for each enforcement."""
        await self.engine.enforce("chatgpt", "alice", ["engineering"])
        await self.engine.enforce("deepseek", "bob", ["engineering"])
        await self.engine.enforce("chatgpt", "dave", ["engineering"])

        telemetry = self.engine.get_telemetry()
        assert telemetry["total_events"] == 3
        assert telemetry["apps"]["chatgpt"] == 2
        assert telemetry["apps"]["deepseek"] == 1

    @pytest.mark.asyncio
    async def test_telemetry_by_classification(self):
        """Telemetry breaks down by classification."""
        await self.engine.enforce("chatgpt", "alice", ["engineering"])
        await self.engine.enforce("deepseek", "bob", ["engineering"])

        telemetry = self.engine.get_telemetry()
        by_class = telemetry["by_classification"]
        assert AppClassification.SANCTIONED.value in by_class
        assert AppClassification.UNSANCTIONED.value in by_class
        assert by_class[AppClassification.SANCTIONED.value] == 1
        assert by_class[AppClassification.UNSANCTIONED.value] == 1

    @pytest.mark.asyncio
    async def test_activity_log_queryable(self):
        """Activity log is queryable by user_id and application."""
        await self.engine.enforce("chatgpt", "alice", ["engineering"])
        await self.engine.enforce("deepseek", "bob", ["engineering"])
        await self.engine.enforce("chatgpt", "alice", ["engineering"])

        alice_events = self.engine.query_activity(user_id="alice")
        assert len(alice_events) == 2

        deepseek_events = self.engine.query_activity(application="deepseek")
        assert len(deepseek_events) == 1

    @pytest.mark.asyncio
    async def test_casb_event_to_dict(self):
        """CASBEvent serializes to dict correctly."""
        event = CASBEvent(
            event_type="unsanctioned_ai_access",
            application="deepseek",
            user_id="bob",
            tenant_id="default",
            groups=["engineering"],
            action=ClassificationAction.BLOCK,
        )
        d = event.to_dict()
        assert d["event_type"] == "unsanctioned_ai_access"
        assert d["application"] == "deepseek"
        assert d["user_id"] == "bob"

    @pytest.mark.asyncio
    async def test_engine_init_with_empty_policies(self):
        """Engine initializes with empty classifier."""
        classifier = CASBClassifier({})
        engine = CASBEngine(classifier=classifier)
        result = await engine.enforce("anything", "u1", [])
        assert result.blocked is True

    @pytest.mark.asyncio
    async def test_group_resolution_from_request(self):
        """Engine resolves user groups through the classifier."""
        assert self.engine.resolve_user_groups("engineering_user") == []
        self.engine.set_group_resolver(lambda uid: ["engineering"] if uid == "eng_user" else [])
        assert self.engine.resolve_user_groups("eng_user") == ["engineering"]
        assert self.engine.resolve_user_groups("other") == []
