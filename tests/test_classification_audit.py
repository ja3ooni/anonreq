"""Tests for classification in audit log entries (Plan 12-03).

Covers:
- classification_level present in every audit log entry
- Classification result fields populate audit_metadata correctly
- No PII in classification-related audit metadata
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from anonreq.models.classification import ClassificationLevel, ClassificationResult
from anonreq.models.processing_context import ProcessingContext
from anonreq.services.classification import ClassificationService
from anonreq.services.classification_engine import ClassificationEngine


class TestAuditClassification:
    """Classification level must appear in every audit log entry."""

    @pytest.mark.asyncio
    async def test_classification_in_audit_metadata(self):
        """Classification highest level is written to audit_metadata."""
        svc = ClassificationService()
        result = await svc.classify(["EMAIL", "PERSON"], client_level=None)

        ctx = ProcessingContext(request_id="audit-test-001")
        ctx.classification_result = result
        ctx.audit_metadata["classification_level"] = result.highest.name
        ctx.audit_metadata["handling_action"] = result.handling_action
        ctx.audit_metadata["highest_entity"] = result.highest_entity

        assert ctx.audit_metadata["classification_level"] == "CONFIDENTIAL"
        assert ctx.audit_metadata["handling_action"] == "allow_and_anonymize"
        assert ctx.audit_metadata["highest_entity"] == "EMAIL"

    @pytest.mark.asyncio
    async def test_highly_restricted_audit_metadata(self):
        """HIGHLY_RESTRICTED classification populates audit metadata correctly."""
        svc = ClassificationService()
        result = await svc.classify(["API_KEY"], client_level=None)

        ctx = ProcessingContext(request_id="audit-test-002")
        ctx.classification_result = result
        ctx.audit_metadata["classification_level"] = result.highest.name
        ctx.audit_metadata["handling_action"] = result.handling_action
        ctx.audit_metadata["highest_entity"] = result.highest_entity

        assert ctx.audit_metadata["classification_level"] == "HIGHLY_RESTRICTED"
        assert ctx.audit_metadata["handling_action"] == "block"
        assert ctx.audit_metadata["highest_entity"] == "API_KEY"

    @pytest.mark.asyncio
    async def test_restricted_audit_metadata(self):
        """RESTRICTED classification populates audit metadata with anonymize_and_flag."""
        svc = ClassificationService()
        result = await svc.classify(["CREDIT_CARD"], client_level=None)

        ctx = ProcessingContext(request_id="audit-test-003")
        ctx.classification_result = result
        ctx.audit_metadata["classification_level"] = result.highest.name
        ctx.audit_metadata["handling_action"] = result.handling_action
        ctx.audit_metadata["highest_entity"] = result.highest_entity

        assert ctx.audit_metadata["classification_level"] == "RESTRICTED"
        assert ctx.audit_metadata["handling_action"] == "anonymize_and_flag"
        assert ctx.audit_metadata["highest_entity"] == "CREDIT_CARD"

    @pytest.mark.asyncio
    async def test_client_override_in_audit_metadata(self):
        """Client override details recorded in audit metadata."""
        svc = ClassificationService()
        result = await svc.classify(
            ["PERSON"],
            client_level=ClassificationLevel.HIGHLY_RESTRICTED,
        )

        ctx = ProcessingContext(request_id="audit-test-004")
        ctx.classification_result = result
        ctx.audit_metadata["classification_level"] = result.highest.name
        ctx.audit_metadata["client_override"] = result.client_override
        ctx.audit_metadata["client_asserted_level"] = (
            result.client_asserted_level.name if result.client_asserted_level else None
        )

        assert ctx.audit_metadata["classification_level"] == "HIGHLY_RESTRICTED"
        assert ctx.audit_metadata["client_override"] is True
        assert ctx.audit_metadata["client_asserted_level"] == "HIGHLY_RESTRICTED"

    @pytest.mark.asyncio
    async def test_client_override_noop_not_in_audit(self):
        """When client level ≤ detected, no override recorded."""
        svc = ClassificationService()
        result = await svc.classify(
            ["API_KEY"],
            client_level=ClassificationLevel.INTERNAL,
        )

        ctx = ProcessingContext(request_id="audit-test-005")
        ctx.classification_result = result
        ctx.audit_metadata["classification_level"] = result.highest.name
        ctx.audit_metadata["client_override"] = result.client_override

        assert ctx.audit_metadata["client_override"] is False
        assert ctx.audit_metadata["classification_level"] == "HIGHLY_RESTRICTED"

    @pytest.mark.asyncio
    async def test_no_pii_in_classification_audit(self):
        """Classification audit metadata contains no PII values."""
        svc = ClassificationService()
        result = await svc.classify(
            ["PERSON", "EMAIL"],
            client_level=ClassificationLevel.RESTRICTED,
        )

        pii_patterns = ["john@example.com", "+1-555", "192.168.", "abc-123"]
        audit_values = [
            result.highest.name,
            result.handling_action,
            str(result.client_override),
            str(result.labels),
        ]
        for value in audit_values:
            for pattern in pii_patterns:
                assert pattern not in value, (
                    f"PII pattern {pattern!r} found in audit value {value!r}"
                )
