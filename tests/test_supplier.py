"""Tests for supplier governance service.

Uses fakeredis-backed cache matching conftest patterns.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from anonreq.services.supplier import SupplierRecord, SupplierService


@pytest.fixture
async def supplier_service(cache_manager):
    svc = SupplierService(cache_manager)
    keys = await svc._redis.keys("anonreq:supplier:*")
    for k in keys:
        await svc._redis.delete(k)
    yield svc


def sample_provider(name="openai") -> SupplierRecord:
    return SupplierRecord(
        provider_name=name,
        legal_entity="OpenAI, LLC",
        jurisdiction="US",
        data_residency_regions=["us-east-1", "eu-west-1"],
        risk_classification="High",
        contract_status="Active",
        last_risk_review_date=datetime.now(timezone.utc) - timedelta(days=30),
        review_cycle_days=365,
    )


class TestSupplierRegistration:
    async def test_register_provider(self, supplier_service):
        provider = sample_provider()
        result = await supplier_service.register_provider(provider)
        assert result.provider_name == "openai"
        assert result.legal_entity == "OpenAI, LLC"
        assert result.contract_status == "Active"

    async def test_get_provider(self, supplier_service):
        await supplier_service.register_provider(sample_provider())
        fetched = await supplier_service.get_provider("openai")
        assert fetched is not None
        assert fetched.jurisdiction == "US"

    async def test_get_nonexistent_provider(self, supplier_service):
        fetched = await supplier_service.get_provider("no-such")
        assert fetched is None

    async def test_register_duplicate_updates(self, supplier_service):
        await supplier_service.register_provider(sample_provider())
        p2 = sample_provider()
        p2.legal_entity = "OpenAI Updated"
        result = await supplier_service.register_provider(p2)
        assert result.legal_entity == "OpenAI Updated"


class TestSupplierList:
    async def test_list_providers(self, supplier_service):
        for name in ["openai", "anthropic", "google"]:
            await supplier_service.register_provider(sample_provider(name=name))
        providers = await supplier_service.list_providers()
        assert len(providers) == 3

    async def test_list_empty(self, supplier_service):
        assert await supplier_service.list_providers() == []


class TestSupplierUpdate:
    async def test_update_provider(self, supplier_service):
        await supplier_service.register_provider(sample_provider())
        result = await supplier_service.update_provider(
            "openai",
            risk_classification="Critical",
            contract_status="Suspended",
        )
        assert result.risk_classification == "Critical"
        assert result.contract_status == "Suspended"

    async def test_update_nonexistent_raises(self, supplier_service):
        with pytest.raises(ValueError, match="Provider not found"):
            await supplier_service.update_provider("no-such", jurisdiction="EU")

    async def test_update_preserves_other_fields(self, supplier_service):
        await supplier_service.register_provider(sample_provider())
        result = await supplier_service.update_provider("openai", jurisdiction="EU")
        assert result.jurisdiction == "EU"
        assert result.provider_name == "openai"
        assert result.legal_entity == "OpenAI, LLC"


class TestSupplierSuspend:
    async def test_suspend_provider(self, supplier_service):
        await supplier_service.register_provider(sample_provider())
        result = await supplier_service.suspend_provider(
            "openai", suspended_by="admin@acme.com"
        )
        assert result.contract_status == "Suspended"

    async def test_suspend_nonexistent_raises(self, supplier_service):
        with pytest.raises(ValueError, match="Provider not found"):
            await supplier_service.suspend_provider(
                "no-such", suspended_by="admin@acme.com"
            )

    async def test_suspend_sets_suspended_by(self, supplier_service):
        await supplier_service.register_provider(sample_provider())
        result = await supplier_service.suspend_provider(
            "openai", suspended_by="admin@acme.com"
        )
        assert result.suspended_by == "admin@acme.com"
        assert result.suspended_at is not None


class TestSupplierOverdue:
    async def test_overdue_provider_review(self, supplier_service):
        p = sample_provider()
        p.last_risk_review_date = datetime.now(timezone.utc) - timedelta(days=400)
        await supplier_service.register_provider(p)
        overdue = await supplier_service.get_overdue_providers()
        assert len(overdue) == 1
        assert overdue[0].provider_name == "openai"

    async def test_no_overdue_when_review_recent(self, supplier_service):
        p = sample_provider()
        p.last_risk_review_date = datetime.now(timezone.utc) - timedelta(days=30)
        await supplier_service.register_provider(p)
        overdue = await supplier_service.get_overdue_providers()
        assert len(overdue) == 0

    async def test_overdue_empty_list(self, supplier_service):
        assert await supplier_service.get_overdue_providers() == []

    async def test_overdue_with_no_review_date(self, supplier_service):
        p = sample_provider()
        p.last_risk_review_date = None
        await supplier_service.register_provider(p)
        overdue = await supplier_service.get_overdue_providers()
        assert len(overdue) == 1


class TestSupplierRiskClassification:
    async def test_critical_risk_flag(self, supplier_service):
        p = sample_provider()
        p.risk_classification = "Critical"
        await supplier_service.register_provider(p)
        critical = await supplier_service.get_critical_providers()
        assert len(critical) == 1

    async def test_non_critical_not_flagged(self, supplier_service):
        p = sample_provider()
        p.risk_classification = "Low"
        await supplier_service.register_provider(p)
        critical = await supplier_service.get_critical_providers()
        assert len(critical) == 0

    async def test_ict_concentration_risk(self, supplier_service):
        p = sample_provider()
        p.ict_concentration_risk = True
        await supplier_service.register_provider(p)
        concentrated = await supplier_service.get_concentration_risk_providers()
        assert len(concentrated) == 1
        assert concentrated[0].ict_concentration_risk is True


class TestSupplierExport:
    async def test_export_providers_as_json(self, supplier_service):
        await supplier_service.register_provider(sample_provider("openai"))
        await supplier_service.register_provider(sample_provider("anthropic"))
        exported = await supplier_service.export_providers()
        assert len(exported) == 2
        names = {e["provider_name"] for e in exported}
        assert names == {"openai", "anthropic"}
