"""Tests for RAG Retrieval Pipeline and Retrieval Policy Engine.

Tests:
- Retrieval Policy Engine with all 4 rules
- Chunk metadata extraction
- User context resolution
- Policy evaluation: DENY wins, ALLOW by default
- Retrieval-time detection/anonymization
- RAG restoration
- Audit events
"""

from __future__ import annotations

import pytest

from anonreq.rag.policy import (
    ChunkContext,
    RetrievalPolicyEngine,
    UserContext,
)
from anonreq.rag.retrieval import RetrievalService


class TestChunkContext:
    """Tests for ChunkContext model."""

    def test_chunk_context_creation(self):
        """ChunkContext stores all required metadata fields."""
        ctx = ChunkContext(
            chunk_id="chunk_001",
            content="Some retrieved text with PII.",
            classification_level="Confidential",
            entity_types_present=["EMAIL", "PHONE"],
            source_app_id="salesforce_app",
            business_unit="Sales",
            allowed_roles=["admin", "manager"],
        )
        assert ctx.chunk_id == "chunk_001"
        assert ctx.classification_level == "Confidential"
        assert "EMAIL" in ctx.entity_types_present

    def test_chunk_context_default_classification(self):
        """ChunkContext defaults classification to Internal."""
        ctx = ChunkContext(
            chunk_id="chunk_002",
            content="Generic text.",
            source_app_id="app1",
        )
        assert ctx.classification_level == "Internal"

    def test_chunk_context_default_entity_types(self):
        """ChunkContext defaults entity_types to empty list."""
        ctx = ChunkContext(
            chunk_id="chunk_003",
            content="Text.",
            source_app_id="app1",
        )
        assert ctx.entity_types_present == []


class TestUserContext:
    """Tests for UserContext model."""

    def test_user_context_creation(self):
        """UserContext stores all required fields."""
        ctx = UserContext(
            user_id="user_001",
            roles=["admin"],
            clearance="Confidential",
            applications=["app1"],
            business_unit="Engineering",
        )
        assert ctx.user_id == "user_001"
        assert ctx.clearance == "Confidential"

    def test_user_context_default_clearance(self):
        """UserContext defaults clearance to Internal."""
        ctx = UserContext(user_id="u1", roles=[], applications=[])
        assert ctx.clearance == "Internal"


class TestRetrievalPolicyEngine:
    """Test suite for RetrievalPolicyEngine and its 4 rules."""

    def setup_method(self):
        self.engine = RetrievalPolicyEngine()
        self.internal_user = UserContext(
            user_id="u1", roles=["viewer"], clearance="Internal",
            applications=["app1"], business_unit="Engineering",
        )
        self.confidential_user = UserContext(
            user_id="u2", roles=["admin"], clearance="Confidential",
            applications=["app1", "app2"], business_unit="Engineering",
        )
        self.hr_user = UserContext(
            user_id="u3", roles=["hr_admin"], clearance="Highly Restricted",
            applications=["hr_app"], business_unit="HR",
        )

    def test_rule_001_classification_clearance_denies(self):
        """RULE-001: deny if chunk classification > user clearance."""
        chunk = ChunkContext(
            chunk_id="c1", content="Highly sensitive data.",
            classification_level="Highly Restricted",
            source_app_id="app1",
        )
        result = self.engine.evaluate(chunk, self.confidential_user)
        assert result.allowed is False
        assert any("classification_clearance" in r.rule_id for r in result.denied_rules)

    def test_rule_001_allows_when_clearance_sufficient(self):
        """RULE-001: allow if user clearance >= chunk classification."""
        chunk = ChunkContext(
            chunk_id="c2", content="Confidential data.",
            classification_level="Confidential",
            source_app_id="app1",
        )
        result = self.engine.evaluate(chunk, self.confidential_user)
        assert result.allowed is True

    def test_rule_002_entity_type_restriction_denies(self):
        """RULE-002: deny if user roles exclude chunk entity types."""
        chunk = ChunkContext(
            chunk_id="c3", content="HR data with names.",
            classification_level="Confidential",
            entity_types_present=["PERSON", "SSN"],
            source_app_id="hr_app",
            allowed_roles=["hr_admin"],
        )
        result = self.engine.evaluate(chunk, self.internal_user)
        assert result.allowed is False
        assert any("entity_type_restriction" in r.rule_id for r in result.denied_rules)

    def test_rule_002_allows_when_role_included(self):
        """RULE-002: allow if user role is in allowed_roles."""
        chunk = ChunkContext(
            chunk_id="c4", content="HR data.",
            classification_level="Confidential",
            entity_types_present=["PERSON"],
            source_app_id="hr_app",
            allowed_roles=["hr_admin"],
        )
        result = self.engine.evaluate(chunk, self.hr_user)
        assert result.allowed is True

    def test_rule_003_cross_app_isolation_denies(self):
        """RULE-003: deny if chunk source_app not in user's applications."""
        chunk = ChunkContext(
            chunk_id="c5", content="Sales data.",
            classification_level="Internal",
            source_app_id="sales_app",
        )
        result = self.engine.evaluate(chunk, self.internal_user)
        assert result.allowed is False
        assert any("cross_app_isolation" in r.rule_id for r in result.denied_rules)

    def test_rule_003_allows_when_app_in_user_apps(self):
        """RULE-003: allow if chunk source_app is in user's applications."""
        chunk = ChunkContext(
            chunk_id="c6", content="App1 data.",
            classification_level="Internal",
            source_app_id="app1",
        )
        result = self.engine.evaluate(chunk, self.internal_user)
        assert result.allowed is True

    def test_rule_004_bu_isolation_denies_cross_bu_confidential(self):
        """RULE-004: deny cross-BU access for >= Confidential chunks."""
        chunk = ChunkContext(
            chunk_id="c7", content="Engineering confidential.",
            classification_level="Confidential",
            source_app_id="eng_app",
            business_unit="Engineering",
        )
        eng_user = UserContext(
            user_id="u_eng", roles=["engineer"], clearance="Confidential",
            applications=["eng_app"], business_unit="Engineering",
        )
        result = self.engine.evaluate(chunk, eng_user)
        assert result.allowed is True

        hr_user = UserContext(
            user_id="u_hr", roles=["hr"], clearance="Confidential",
            applications=["hr_app"], business_unit="HR",
        )
        result2 = self.engine.evaluate(chunk, hr_user)
        assert result2.allowed is False
        assert any("business_unit_isolation" in r.rule_id for r in result2.denied_rules)

    def test_rule_004_allows_cross_bu_internal(self):
        """RULE-004: allow cross-BU access for Internal chunks."""
        chunk = ChunkContext(
            chunk_id="c8", content="General info.",
            classification_level="Internal",
            source_app_id="eng_app",
            business_unit="Engineering",
        )
        hr_user = UserContext(
            user_id="u_hr", roles=["hr"], clearance="Internal",
            applications=["hr_app", "eng_app"], business_unit="HR",
        )
        result = self.engine.evaluate(chunk, hr_user)
        assert result.allowed is True

    def test_deny_wins_multiple_rules(self):
        """DENY wins when multiple rules match."""
        chunk = ChunkContext(
            chunk_id="c9", content="Cross-BU highly restricted.",
            classification_level="Highly Restricted",
            entity_types_present=["SSN"],
            source_app_id="hr_app",
            business_unit="HR",
            allowed_roles=["hr_admin"],
        )
        user = UserContext(
            user_id="u_eng", roles=["engineer"], clearance="Confidential",
            applications=["eng_app"], business_unit="Engineering",
        )
        result = self.engine.evaluate(chunk, user)
        assert result.allowed is False
        assert len(result.denied_rules) >= 1

    def test_default_allow_when_no_rule_matches(self):
        """ALLOW when no rule matches."""
        chunk = ChunkContext(
            chunk_id="c10", content="Simple text.",
            classification_level="Internal",
            source_app_id="app1",
        )
        user = UserContext(
            user_id="u1", roles=["viewer"], clearance="Internal",
            applications=["app1"], business_unit="Engineering",
        )
        result = self.engine.evaluate(chunk, user)
        assert result.allowed is True

    def test_policy_result_has_rule_details(self):
        """PolicyRuleResult contains rule_id and reason for each denied rule."""
        chunk = ChunkContext(
            chunk_id="c11", content="HR secret.",
            classification_level="Highly Restricted",
            source_app_id="hr_app",
        )
        user = UserContext(
            user_id="u1", roles=[], clearance="Internal",
            applications=["eng_app"], business_unit="Engineering",
        )
        result = self.engine.evaluate(chunk, user)
        for rule in result.denied_rules:
            assert rule.rule_id
            assert rule.reason

    def test_chunk_filtering_by_engine(self):
        """Engine filters out denied chunks, keeps allowed ones."""
        chunks = [
            ChunkContext("c1", "Allowed.", "Internal", [], "app1", "Engineering", []),
            ChunkContext("c2", "Denied.", "Highly Restricted", [], "app1", "Engineering", []),
            ChunkContext("c3", "Allowed too.", "Internal", [], "app1", "Engineering", []),
        ]
        user = UserContext(
            user_id="u1", roles=[], clearance="Internal",
            applications=["app1"], business_unit="Engineering",
        )
        allowed, denied = self.engine.filter_chunks(chunks, user)
        assert len(allowed) == 2
        assert len(denied) == 1
        assert denied[0].chunk_id == "c2"

    def test_yaml_config_loading(self):
        """Engine loads rules from YAML config."""
        config = {
            "enabled_rules": [
                "classification_clearance",
                "entity_type_restriction",
            ],
        }
        engine = RetrievalPolicyEngine(config=config)
        assert "classification_clearance" in engine._enabled_rules
        assert "entity_type_restriction" in engine._enabled_rules
        assert "cross_app_isolation" not in engine._enabled_rules

    def test_disabled_rule_not_evaluated(self):
        """Disabled rules are not evaluated."""
        config = {"enabled_rules": ["classification_clearance"]}
        engine = RetrievalPolicyEngine(config=config)
        chunk = ChunkContext(
            chunk_id="c12", content="Cross-app test.",
            classification_level="Internal",
            source_app_id="sales_app",
        )
        user = UserContext(
            user_id="u1", roles=[], clearance="Internal",
            applications=["app1"], business_unit="Engineering",
        )
        # cross_app_isolation is disabled, so this should be allowed
        result = engine.evaluate(chunk, user)
        assert result.allowed is True


class TestRetrievalService:
    """Tests for retrieval-time detection, anonymization, and restoration."""

    @pytest.mark.asyncio
    async def test_retrieval_service_creation(self):
        """RetrievalService can be created with an engine."""
        engine = RetrievalPolicyEngine()
        service = RetrievalService(policy_engine=engine)
        assert service is not None

    @pytest.mark.asyncio
    async def test_process_retrieved_chunks(self):
        """Retrieved chunks are inspected, filtered, and returned."""
        engine = RetrievalPolicyEngine()
        service = RetrievalService(policy_engine=engine)

        chunks = [
            ChunkContext(
                chunk_id="r1", content="Public info.",
                classification_level="Internal",
                source_app_id="app1",
                business_unit="Engineering",
            ),
            ChunkContext(
                chunk_id="r2", content="Secret.", classification_level="Highly Restricted",
                source_app_id="app1",
                business_unit="Engineering",
            ),
        ]
        user = UserContext(
            user_id="u1", roles=[], clearance="Internal",
            applications=["app1"], business_unit="Engineering",
        )
        result = await service.process_chunks(chunks, user)
        assert len(result["allowed"]) == 1
        assert len(result["denied"]) == 1
        assert result["allowed"][0].chunk_id == "r1"

    @pytest.mark.asyncio
    async def test_audit_events_for_denied_chunks(self):
        """Denied chunks produce rag_chunk_filtered audit events."""
        engine = RetrievalPolicyEngine()
        service = RetrievalService(policy_engine=engine)

        chunks = [
            ChunkContext(
                chunk_id="r3", content="Secret.", classification_level="Highly Restricted",
                source_app_id="app1",
                business_unit="Engineering",
            ),
        ]
        user = UserContext(
            user_id="u1", roles=[], clearance="Internal",
            applications=["app1"], business_unit="Engineering",
        )
        result = await service.process_chunks(chunks, user)
        assert len(result["audit_events"]) == 1
        event = result["audit_events"][0]
        assert event["event_type"] == "rag_chunk_filtered"
        assert event["chunk_id"] == "r3"

    @pytest.mark.asyncio
    async def test_no_audit_events_for_allowed_chunks(self):
        """Allowed chunks do not produce rag_chunk_filtered events."""
        engine = RetrievalPolicyEngine()
        service = RetrievalService(policy_engine=engine)

        chunks = [
            ChunkContext(
                chunk_id="r4", content="Public.", classification_level="Internal",
                source_app_id="app1",
                business_unit="Engineering",
            ),
        ]
        user = UserContext(
            user_id="u1", roles=[], clearance="Internal",
            applications=["app1"], business_unit="Engineering",
        )
        result = await service.process_chunks(chunks, user)
        assert len(result["audit_events"]) == 0

    @pytest.mark.asyncio
    async def test_audit_events_metadata_only(self):
        """Audit events contain metadata, no raw content."""
        engine = RetrievalPolicyEngine()
        service = RetrievalService(policy_engine=engine)

        chunks = [
            ChunkContext(
                chunk_id="r5", content="SSN: 123-45-6789",
                classification_level="Highly Restricted",
                source_app_id="app1",
                business_unit="Engineering",
            ),
        ]
        user = UserContext(
            user_id="u1", roles=[], clearance="Internal",
            applications=["app1"], business_unit="Engineering",
        )
        result = await service.process_chunks(chunks, user)
        event_str = str(result["audit_events"])
        assert "123-45-6789" not in event_str
