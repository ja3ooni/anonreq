"""Tests for incident classification (D-008).

Tests severity classification rules and response time requirements.
"""

from __future__ import annotations

import pytest

from anonreq.models.fairness import IncidentSeverity, INCIDENT_RESPONSE_TIMES
from anonreq.incidents.classification import IncidentClassifier


class TestIncidentSeverityEnum:
    """Tests for IncidentSeverity enum."""

    def test_severity_ordering(self):
        """Severity levels ordered correctly by int value."""
        assert int(IncidentSeverity.LOW) < int(IncidentSeverity.MEDIUM)
        assert int(IncidentSeverity.MEDIUM) < int(IncidentSeverity.HIGH)
        assert int(IncidentSeverity.HIGH) < int(IncidentSeverity.CRITICAL)

    def test_severity_names(self):
        """Severity names match requirements."""
        assert IncidentSeverity.LOW.name == "LOW"
        assert IncidentSeverity.MEDIUM.name == "MEDIUM"
        assert IncidentSeverity.HIGH.name == "HIGH"
        assert IncidentSeverity.CRITICAL.name == "CRITICAL"


class TestIncidentClassification:
    """Tests for incident classification rules."""

    def test_data_exposure_is_critical(self):
        """Test 4: Data exposure → CRITICAL (S1)."""
        sev = IncidentClassifier.classify(
            incident_type="data_exposure",
            impact="high",
            data_exposure=True,
            slo_breach=True,
        )
        assert sev == IncidentSeverity.CRITICAL

    def test_high_impact_slo_breach_is_high(self):
        """Test 5: SLO breach + high impact → HIGH (S2)."""
        sev = IncidentClassifier.classify(
            incident_type="degradation",
            impact="high",
            data_exposure=False,
            slo_breach=True,
        )
        assert sev == IncidentSeverity.HIGH

    def test_slo_breach_is_medium(self):
        """Test 6: SLO breach → MEDIUM (S3)."""
        sev = IncidentClassifier.classify(
            incident_type="latency",
            impact="low",
            data_exposure=False,
            slo_breach=True,
        )
        assert sev == IncidentSeverity.MEDIUM

    def test_no_issues_is_low(self):
        """Test 7: No data exposure, no SLO breach → LOW."""
        sev = IncidentClassifier.classify(
            incident_type="info",
            impact="low",
            data_exposure=False,
            slo_breach=False,
        )
        assert sev == IncidentSeverity.LOW

    def test_critical_overrides_other_flags(self):
        """Data exposure is CRITICAL even without SLO breach."""
        sev = IncidentClassifier.classify(
            incident_type="leak",
            impact="low",
            data_exposure=True,
            slo_breach=False,
        )
        assert sev == IncidentSeverity.CRITICAL


class TestResponseTimes:
    """Tests for incident response time requirements."""

    def test_critical_response_time(self):
        """Test 4: CRITICAL → immediate notification."""
        sev = IncidentClassifier.get_response_time(IncidentSeverity.CRITICAL)
        assert sev == "immediate"
        assert IncidentClassifier.should_notify_immediate(IncidentSeverity.CRITICAL) is True

    def test_high_response_time(self):
        """Test 5: HIGH → 24h."""
        sev = IncidentClassifier.get_response_time(IncidentSeverity.HIGH)
        assert sev == "24h"
        assert IncidentClassifier.should_notify_immediate(IncidentSeverity.HIGH) is False

    def test_medium_response_time(self):
        """Test 6: MEDIUM → 72h."""
        sev = IncidentClassifier.get_response_time(IncidentSeverity.MEDIUM)
        assert sev == "72h"
        assert IncidentClassifier.should_notify_immediate(IncidentSeverity.MEDIUM) is False

    def test_low_response_time(self):
        """Test 7: LOW → next review cycle."""
        sev = IncidentClassifier.get_response_time(IncidentSeverity.LOW)
        assert sev == "next_review"
        assert IncidentClassifier.should_notify_immediate(IncidentSeverity.LOW) is False

    def test_response_time_matches_constants(self):
        """Response times match the requirement constants."""
        assert INCIDENT_RESPONSE_TIMES["CRITICAL"] == "immediate"
        assert INCIDENT_RESPONSE_TIMES["HIGH"] == "24h"
        assert INCIDENT_RESPONSE_TIMES["MEDIUM"] == "72h"
        assert INCIDENT_RESPONSE_TIMES["LOW"] == "next_review"


class TestIncidentRecord:
    """Tests for incident record creation."""

    def test_create_critical_incident_record(self):
        """Critical incident record has immediate notification."""
        record = IncidentClassifier.create_incident_record(
            incident_id="inc_001",
            severity=IncidentSeverity.CRITICAL,
            incident_type="data_exposure",
            entity_type="PERSON",
            drift_amount=0.15,
            baseline_recall=0.95,
            production_recall=0.80,
        )
        assert record["incident_id"] == "inc_001"
        assert record["severity"] == "CRITICAL"
        assert record["response_time"] == "immediate"
        assert record["notify_immediate"] is True
        assert record["drift_amount"] == 0.15

    def test_create_low_incident_record(self):
        """Low severity incident has next_review response."""
        record = IncidentClassifier.create_incident_record(
            incident_id="inc_002",
            severity=IncidentSeverity.LOW,
            incident_type="info",
            entity_type="EMAIL",
            drift_amount=0.01,
            baseline_recall=0.95,
            production_recall=0.94,
        )
        assert record["severity"] == "LOW"
        assert record["response_time"] == "next_review"
        assert record["notify_immediate"] is False

    def test_create_incident_with_metadata(self):
        """Incident record accepts optional metadata."""
        record = IncidentClassifier.create_incident_record(
            incident_id="inc_003",
            severity=IncidentSeverity.HIGH,
            incident_type="degradation",
            entity_type="PHONE",
            drift_amount=0.08,
            baseline_recall=0.90,
            production_recall=0.82,
            metadata={"tenant_id": "tenant_001", "region": "eu-west-1"},
        )
        assert record["metadata"]["tenant_id"] == "tenant_001"
        assert record["metadata"]["region"] == "eu-west-1"


class EdgeCaseTests:
    """Edge cases for incident classification."""

    def test_all_false_classification(self):
        """All False flags → LOW."""
        sev = IncidentClassifier.classify(
            incident_type="unknown",
            impact="low",
            data_exposure=False,
            slo_breach=False,
        )
        assert sev == IncidentSeverity.LOW
