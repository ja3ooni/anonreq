"""Tests for AI Asset Inventory and Risk Score Engine.

Tests:
- AssetInventory: merge DNS + proxy + CASB data
- Deduplication by hostname with timeline resolution
- Cost attribution per provider/model
- RiskScoreEngine: all 6 dimensions, weighted sum, bands
- Export APIs: JSON/CSV
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from anonreq.discovery.inventory import (
    AssetInventory,
    InventoryRecord,
    InventoryFilter,
)
from anonreq.discovery.risk import (
    RiskScoreEngine,
    RiskDimension,
    DimensionScore,
    RiskBand,
)


class TestInventoryRecord:
    """Tests for InventoryRecord data model."""

    def test_inventory_record_creation(self):
        """InventoryRecord stores all required fields."""
        now = datetime.now(timezone.utc)
        record = InventoryRecord(
            service_name="api.openai.com",
            provider="openai",
            model="gpt-4",
            user_count=10,
            app_count=2,
            token_volume=1_000_000,
            estimated_cost=20.0,
            data_classification="Confidential",
            approval_status="approved",
            risk_score=18,
            last_seen=now,
            owner="team-ml",
            business_unit="Engineering",
        )
        assert record.service_name == "api.openai.com"
        assert record.provider == "openai"
        assert record.risk_score == 18

    def test_inventory_record_defaults(self):
        """InventoryRecord uses sensible defaults."""
        now = datetime.now(timezone.utc)
        record = InventoryRecord(
            service_name="test.ai",
            provider="unknown",
            last_seen=now,
        )
        assert record.user_count == 0
        assert record.risk_score == 0
        assert record.approval_status == "not_reviewed"

    def test_inventory_record_to_dict(self):
        """InventoryRecord serializes to dict."""
        now = datetime.now(timezone.utc)
        record = InventoryRecord(
            service_name="api.openai.com",
            provider="openai",
            last_seen=now,
        )
        d = record.to_dict()
        assert d["service_name"] == "api.openai.com"
        assert d["provider"] == "openai"
        assert "last_seen" in d


class TestAssetInventory:
    """Tests for AssetInventory — merge, dedup, export."""

    def setup_method(self):
        self.inventory = AssetInventory()
        self.now = datetime.now(timezone.utc)

    def test_add_record(self):
        """Add record to inventory."""
        record = InventoryRecord(
            service_name="api.openai.com",
            provider="openai",
            last_seen=self.now,
        )
        self.inventory.add_record(record)
        records = self.inventory.list_records()
        assert len(records) == 1

    def test_add_duplicate_updates(self):
        """Add duplicate service updates existing record."""
        record1 = InventoryRecord(
            service_name="api.openai.com",
            provider="openai",
            user_count=5,
            last_seen=self.now,
        )
        record2 = InventoryRecord(
            service_name="api.openai.com",
            provider="openai",
            user_count=10,
            token_volume=500_000,
            last_seen=self.now,
        )
        self.inventory.add_record(record1)
        self.inventory.add_record(record2)
        records = self.inventory.list_records()
        assert len(records) == 1  # deduped
        assert records[0].user_count == 15  # merged

    def test_add_duplicate_keeps_latest_timestamp(self):
        """Duplicate merge keeps the latest last_seen."""
        earlier = datetime(2024, 1, 1, tzinfo=timezone.utc)
        later = datetime(2024, 6, 1, tzinfo=timezone.utc)
        r1 = InventoryRecord(service_name="api.openai.com", provider="openai", last_seen=earlier)
        r2 = InventoryRecord(service_name="api.openai.com", provider="openai", last_seen=later)
        self.inventory.add_record(r1)
        self.inventory.add_record(r2)
        assert self.inventory.list_records()[0].last_seen == later

    def test_merge_from_discovery_sources(self):
        """Merge DNS + proxy discoveries into inventory."""
        from anonreq.discovery.dns_parser import DNSEntry
        from anonreq.discovery.proxy_parser import ProxyEntry

        dns_entries = [
            DNSEntry(hostname="api.openai.com", source_ip="10.0.0.1", timestamp=self.now),
        ]
        proxy_entries = [
            ProxyEntry(
                source_ip="10.0.0.2", timestamp=self.now, method="POST",
                url="https://api.openai.com/v1/chat/completions",
                status=200, bytes=5000, user_id="alice",
            ),
        ]
        self.inventory.merge_from_discovery(dns_entries, proxy_entries)
        records = self.inventory.list_records()
        assert len(records) >= 1
        # Should have openai
        openai_recs = [r for r in records if r.provider == "openai"]
        assert len(openai_recs) >= 1

    def test_filter_by_provider(self):
        """Filter records by provider."""
        self.inventory.add_record(InventoryRecord(
            service_name="api.openai.com", provider="openai", last_seen=self.now,
        ))
        self.inventory.add_record(InventoryRecord(
            service_name="api.anthropic.com", provider="anthropic", last_seen=self.now,
        ))
        filtered = self.inventory.list_records(filters=InventoryFilter(provider="openai"))
        assert len(filtered) == 1
        assert filtered[0].provider == "openai"

    def test_filter_by_risk_score_range(self):
        """Filter records by risk score range."""
        self.inventory.add_record(InventoryRecord(
            service_name="low.ai", provider="test", risk_score=15, last_seen=self.now,
        ))
        self.inventory.add_record(InventoryRecord(
            service_name="high.ai", provider="test", risk_score=85, last_seen=self.now,
        ))
        filtered = self.inventory.list_records(
            filters=InventoryFilter(risk_score_min=50),
        )
        assert len(filtered) == 1
        assert filtered[0].service_name == "high.ai"

    def test_filter_by_approval_status(self):
        """Filter records by approval status."""
        self.inventory.add_record(InventoryRecord(
            service_name="approved.ai", provider="test",
            approval_status="approved", last_seen=self.now,
        ))
        self.inventory.add_record(InventoryRecord(
            service_name="pending.ai", provider="test",
            approval_status="pending", last_seen=self.now,
        ))
        filtered = self.inventory.list_records(
            filters=InventoryFilter(approval_status="approved"),
        )
        assert len(filtered) == 1
        assert filtered[0].service_name == "approved.ai"

    def test_export_json(self):
        """Export inventory as JSON."""
        self.inventory.add_record(InventoryRecord(
            service_name="api.openai.com", provider="openai", last_seen=self.now,
        ))
        json_str = self.inventory.export_json()
        assert "api.openai.com" in json_str
        assert "openai" in json_str

    def test_export_csv(self):
        """Export inventory as CSV."""
        self.inventory.add_record(InventoryRecord(
            service_name="api.openai.com", provider="openai",
            user_count=5, last_seen=self.now,
        ))
        csv_str = self.inventory.export_csv()
        assert "api.openai.com" in csv_str
        assert "openai" in csv_str
        assert "5" in csv_str
        # CSV header
        assert "service_name" in csv_str.split("\n")[0]

    def test_cost_attribution(self):
        """Cost attribution computes cost per provider/model."""
        self.inventory.add_record(InventoryRecord(
            service_name="api.openai.com", provider="openai", model="gpt-4",
            token_volume=1_000_000, estimated_cost=20.0, last_seen=self.now,
        ))
        self.inventory.add_record(InventoryRecord(
            service_name="api.anthropic.com", provider="anthropic", model="claude-3",
            token_volume=500_000, estimated_cost=15.0, last_seen=self.now,
        ))
        costs = self.inventory.get_cost_attribution()
        assert costs["by_provider"]["openai"] == 20.0
        assert costs["by_provider"]["anthropic"] == 15.0
        assert costs["total"] == 35.0

    def test_cost_attribution_empty(self):
        """Cost attribution on empty inventory returns zeros."""
        costs = self.inventory.get_cost_attribution()
        assert costs["total"] == 0.0
        assert costs["by_provider"] == {}

    def test_remove_record(self):
        """Remove record from inventory."""
        self.inventory.add_record(InventoryRecord(
            service_name="test.ai", provider="test", last_seen=self.now,
        ))
        assert len(self.inventory.list_records()) == 1
        self.inventory.remove_record("test.ai")
        assert len(self.inventory.list_records()) == 0

    def test_get_record_by_service(self):
        """Get specific record by service name."""
        self.inventory.add_record(InventoryRecord(
            service_name="api.openai.com", provider="openai", last_seen=self.now,
        ))
        record = self.inventory.get_record("api.openai.com")
        assert record is not None
        assert record.service_name == "api.openai.com"

    def test_get_record_not_found(self):
        """Get nonexistent record returns None."""
        record = self.inventory.get_record("nonexistent")
        assert record is None

    def test_summary_stats(self):
        """Summary returns aggregate stats."""
        self.inventory.add_record(InventoryRecord(
            service_name="s1", provider="openai", user_count=10,
            token_volume=1000, estimated_cost=5.0, risk_score=20,
            last_seen=self.now,
        ))
        self.inventory.add_record(InventoryRecord(
            service_name="s2", provider="anthropic", user_count=5,
            token_volume=500, estimated_cost=2.5, risk_score=70,
            last_seen=self.now,
        ))
        summary = self.inventory.get_summary()
        assert summary["total_services"] == 2
        assert summary["total_users"] == 15
        assert summary["total_token_volume"] == 1500
        assert summary["total_estimated_cost"] == 7.5
        assert summary["average_risk_score"] == 45.0


class TestRiskScoreEngine:
    """Tests for RiskScoreEngine — dimensions, weighted sum, bands."""

    def setup_method(self):
        self.engine = RiskScoreEngine()

    def test_provider_trust_major(self):
        """Major provider gets low risk score."""
        score = self.engine.score_provider_trust("openai")
        assert score <= 30

    def test_provider_trust_unknown(self):
        """Unknown provider gets high risk score."""
        score = self.engine.score_provider_trust("unknown_startup")
        assert score >= 70

    def test_provider_trust_regional(self):
        """Regional provider gets moderate risk score."""
        score = self.engine.score_provider_trust("mistral")
        assert 20 <= score <= 60

    def test_data_sensitivity_internal(self):
        """Internal classification gets low risk score."""
        score = self.engine.score_data_sensitivity("Internal")
        assert score <= 30

    def test_data_sensitivity_highly_restricted(self):
        """Highly Restricted classification gets high risk score."""
        score = self.engine.score_data_sensitivity("Highly Restricted")
        assert score >= 80

    def test_shadow_usage_sanctioned(self):
        """Sanctioned status gets low risk score."""
        score = self.engine.score_shadow_usage("sanctioned")
        assert score == 10

    def test_shadow_usage_blocked(self):
        """Blocked status gets high risk score."""
        score = self.engine.score_shadow_usage("blocked")
        assert score == 90

    def test_approval_status_approved(self):
        """Approved status gets low risk score."""
        score = self.engine.score_approval_status("approved")
        assert score == 5

    def test_approval_status_denied(self):
        """Denied status gets high risk score."""
        score = self.engine.score_approval_status("denied")
        assert score == 100

    def test_model_location_in_region(self):
        """In-region location gets low risk score."""
        score = self.engine.score_model_location("us-east-1")
        assert score == 10

    def test_model_location_unknown(self):
        """Unknown location gets high risk score."""
        score = self.engine.score_model_location("unknown")
        assert score == 90

    def test_retention_policy_none(self):
        """No retention gets low risk score."""
        score = self.engine.score_retention_policy("none")
        assert score == 10

    def test_retention_policy_indefinite(self):
        """Indefinite retention gets high risk score."""
        score = self.engine.score_retention_policy("indefinite")
        assert score == 90

    def test_weighted_sum_default_weights(self):
        """Weighted sum with default weights produces 0-100 score."""
        scores = {
            RiskDimension.PROVIDER_TRUST: DimensionScore(score=20, weight=0.25),
            RiskDimension.DATA_SENSITIVITY: DimensionScore(score=30, weight=0.20),
            RiskDimension.SHADOW_USAGE: DimensionScore(score=10, weight=0.20),
            RiskDimension.APPROVAL_STATUS: DimensionScore(score=5, weight=0.15),
            RiskDimension.MODEL_LOCATION: DimensionScore(score=10, weight=0.10),
            RiskDimension.RETENTION_POLICY: DimensionScore(score=30, weight=0.10),
        }
        total = self.engine.compute_weighted_score(scores)
        assert 0 <= total <= 100

    def test_weighted_sum_custom_weights(self):
        """Custom weights produce different score."""
        scores = {
            RiskDimension.PROVIDER_TRUST: DimensionScore(score=100, weight=0.50),
            RiskDimension.DATA_SENSITIVITY: DimensionScore(score=0, weight=0.50),
        }
        total = self.engine.compute_weighted_score(scores)
        assert total == 50.0

    def test_risk_band_low(self):
        """0-30 maps to Low band."""
        assert self.engine.classify_band(0) == RiskBand.LOW
        assert self.engine.classify_band(15) == RiskBand.LOW
        assert self.engine.classify_band(30) == RiskBand.LOW

    def test_risk_band_medium(self):
        """31-60 maps to Medium band."""
        assert self.engine.classify_band(31) == RiskBand.MEDIUM
        assert self.engine.classify_band(45) == RiskBand.MEDIUM
        assert self.engine.classify_band(60) == RiskBand.MEDIUM

    def test_risk_band_high(self):
        """61-80 maps to High band."""
        assert self.engine.classify_band(61) == RiskBand.HIGH
        assert self.engine.classify_band(70) == RiskBand.HIGH
        assert self.engine.classify_band(80) == RiskBand.HIGH

    def test_risk_band_critical(self):
        """81-100 maps to Critical band."""
        assert self.engine.classify_band(81) == RiskBand.CRITICAL
        assert self.engine.classify_band(95) == RiskBand.CRITICAL
        assert self.engine.classify_band(100) == RiskBand.CRITICAL

    def test_compute_full_risk(self):
        """Full risk calculation from inputs."""
        result = self.engine.compute_risk(
            provider="openai",
            data_classification="Confidential",
            shadow_status="sanctioned",
            approval_status="approved",
            model_region="us-east-1",
            retention_policy="90day",
        )
        assert 0 <= result.score <= 100
        assert result.band in (RiskBand.LOW, RiskBand.MEDIUM)
        assert len(result.dimensions) == 6

    def test_compute_high_risk(self):
        """High-risk inputs produce Critical band."""
        result = self.engine.compute_risk(
            provider="unknown_startup",
            data_classification="Highly Restricted",
            shadow_status="blocked",
            approval_status="denied",
            model_region="unknown",
            retention_policy="indefinite",
        )
        assert result.band == RiskBand.CRITICAL
        assert result.score >= 80

    def test_compute_low_risk(self):
        """Low-risk inputs produce Low band."""
        result = self.engine.compute_risk(
            provider="openai",
            data_classification="Internal",
            shadow_status="sanctioned",
            approval_status="approved",
            model_region="us-east-1",
            retention_policy="none",
        )
        assert result.band == RiskBand.LOW
        assert result.score <= 30

    def test_custom_dimension_weights(self):
        """Custom weights produce different overall score."""
        weights = {
            RiskDimension.PROVIDER_TRUST: 0.50,
            RiskDimension.DATA_SENSITIVITY: 0.50,
        }
        result = self.engine.compute_risk(
            provider="openai",
            data_classification="Highly Restricted",
            shadow_status="sanctioned",
            approval_status="approved",
            model_region="us-east-1",
            retention_policy="none",
            dimension_weights=weights,
        )
        assert result.score > 30  # data sensitivity weighted more heavily

    def test_risk_result_dict(self):
        """RiskResult serializes to dict."""
        result = self.engine.compute_risk(
            provider="openai",
            data_classification="Internal",
            shadow_status="sanctioned",
            approval_status="approved",
            model_region="us-east-1",
            retention_policy="none",
        )
        d = result.to_dict()
        assert "score" in d
        assert "band" in d
        assert "dimensions" in d
        assert d["band"] == "low"

    def test_risk_score_in_range(self):
        """All risk scores are in 0-100 range regardless of inputs."""
        result = self.engine.compute_risk(
            provider="x" * 50,
            data_classification="Unknown",
            shadow_status="unknown_status",
            approval_status="weird",
            model_region="mars",
            retention_policy="forever",
        )
        assert 0 <= result.score <= 100
