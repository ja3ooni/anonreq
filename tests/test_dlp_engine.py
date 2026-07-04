"""Unit tests for DLPEngine (Plan 13-01)."""

from __future__ import annotations

import yaml
import pytest

from anonreq.models.dlp import DLPCategory, DLPAction, DLPResult, DLPDetection
from anonreq.services.dlp_engine import DLPEngine
from anonreq.models.processing_context import ProcessingContext


@pytest.fixture
def dlp_config():
    with open("config/dlp.yaml", "r") as f:
        data = yaml.safe_load(f)
    return data["dlp"]


@pytest.fixture
def dlp_engine(dlp_config):
    return DLPEngine(dlp_config)


def test_dlp_categories_and_actions_exist():
    assert len(DLPCategory) == 9
    assert len(DLPAction) == 5
    assert DLPCategory.PII == "PII"
    assert DLPCategory.EXFILTRATION == "Exfiltration"
    assert DLPAction.BLOCK == "block"


@pytest.mark.asyncio
async def test_dlp_engine_detects_pii(dlp_engine):
    # Test Email
    res = await dlp_engine.inspect("Contact john.doe@example.com for info")
    emails = [d for d in res.detections if d.category == DLPCategory.PII and d.pattern_id == "pii_email"]
    assert len(emails) == 1
    assert emails[0].action == DLPAction.BLOCK
    assert res.max_action == DLPAction.BLOCK
    assert res.is_blocked is True

    # Test Phone
    res = await dlp_engine.inspect("Call me at +15551234567")
    phones = [d for d in res.detections if d.category == DLPCategory.PII and d.pattern_id == "pii_phone"]
    assert len(phones) == 1

    # Test SSN
    res = await dlp_engine.inspect("My SSN is 123-45-6789")
    ssns = [d for d in res.detections if d.category == DLPCategory.PII and d.pattern_id == "pii_ssn"]
    assert len(ssns) == 1


@pytest.mark.asyncio
async def test_dlp_engine_detects_financial(dlp_engine):
    # Test Credit Card
    res = await dlp_engine.inspect("Card number: 1234-5678-9012-3456")
    cards = [d for d in res.detections if d.category == DLPCategory.FINANCIAL and d.pattern_id == "fin_credit_card"]
    assert len(cards) == 1
    assert res.max_action == DLPAction.BLOCK

    # Test IBAN
    res = await dlp_engine.inspect("My IBAN is DE89370400440532013000")
    ibans = [d for d in res.detections if d.category == DLPCategory.FINANCIAL and d.pattern_id == "fin_iban"]
    assert len(ibans) == 1

    # Test SWIFT
    res = await dlp_engine.inspect("SWIFT code is AAAABBCC")
    swifts = [d for d in res.detections if d.category == DLPCategory.FINANCIAL and d.pattern_id == "fin_swift"]
    assert len(swifts) == 1


@pytest.mark.asyncio
async def test_dlp_engine_detects_health(dlp_engine):
    res = await dlp_engine.inspect("Contains Protected Health Information (PHI) logs")
    health = [d for d in res.detections if d.category == DLPCategory.HEALTH]
    assert len(health) >= 1
    assert health[0].pattern_id == "health_hipaa"
    assert res.max_action == DLPAction.BLOCK


@pytest.mark.asyncio
async def test_dlp_engine_detects_source_code(dlp_engine):
    res = await dlp_engine.inspect("Set api-key: 'sk_abcdefghijklmnop'")
    keys = [d for d in res.detections if d.category == DLPCategory.SOURCE_CODE]
    assert len(keys) == 1
    assert keys[0].pattern_id == "sc_api_key"
    assert res.max_action == DLPAction.ANONYMIZE


@pytest.mark.asyncio
async def test_dlp_engine_detects_credentials(dlp_engine):
    res = await dlp_engine.inspect("password: 'supersecret123'")
    creds = [d for d in res.detections if d.category == DLPCategory.CREDENTIALS]
    assert len(creds) == 1
    assert creds[0].pattern_id == "cred_password"
    assert res.max_action == DLPAction.BLOCK


@pytest.mark.asyncio
async def test_dlp_engine_detects_legal(dlp_engine):
    res = await dlp_engine.inspect("This document is subject to attorney-client privilege")
    legal = [d for d in res.detections if d.category == DLPCategory.LEGAL]
    assert len(legal) == 1
    assert res.max_action == DLPAction.ANONYMIZE


@pytest.mark.asyncio
async def test_dlp_engine_detects_export_controlled(dlp_engine):
    res = await dlp_engine.inspect("This falls under ITAR regulations")
    export = [d for d in res.detections if d.category == DLPCategory.EXPORT_CONTROLLED]
    assert len(export) == 1
    assert res.max_action == DLPAction.BLOCK


@pytest.mark.asyncio
async def test_dlp_engine_detects_intellectual_property(dlp_engine):
    res = await dlp_engine.inspect("Contains trade secret recipes")
    ip = [d for d in res.detections if d.category == DLPCategory.INTELLECTUAL_PROPERTY]
    assert len(ip) == 1
    assert res.max_action == DLPAction.QUARANTINE
    assert res.is_blocked is True
    assert res.is_quarantined is True


@pytest.mark.asyncio
async def test_dlp_engine_action_precedence(dlp_engine):
    # Test that BLOCK (from PII) wins over ANONYMIZE (from Source Code)
    text = "Set api-key: 'sk_abcdefghijklmnop' for john.doe@example.com"
    res = await dlp_engine.inspect(text)
    assert res.max_action == DLPAction.BLOCK
    assert res.is_blocked is True


@pytest.mark.asyncio
async def test_dlp_engine_no_match(dlp_engine):
    res = await dlp_engine.inspect("Hello, how can I help you today?")
    assert len(res.detections) == 0
    assert res.max_action == DLPAction.ALLOW
    assert res.is_blocked is False
    assert res.is_quarantined is False


@pytest.mark.asyncio
async def test_dlp_engine_tenant_custom_categories():
    # Instantiate empty engine to avoid core category matches
    engine = DLPEngine({"core_categories": {}})
    tenant_config = {
        "patterns": [
            {
                "id": "custom_internal_code",
                "regex": "PROJECT-[A-Z]{3}-\\d{4}",
                "category": "Intellectual Property",
                "action": "quarantine"
            }
        ]
    }
    engine.load_tenant_patterns("tenant_a", tenant_config)

    # Test match for tenant_a
    res = await engine.inspect("Refer to PROJECT-ABC-1234 design docs", tenant_id="tenant_a")
    custom = [d for d in res.detections if d.is_custom_category]
    assert len(custom) == 1
    assert custom[0].pattern_id == "custom_internal_code"
    assert custom[0].category == DLPCategory.INTELLECTUAL_PROPERTY
    assert res.max_action == DLPAction.QUARANTINE

    # Test isolation: tenant_b should NOT match the same text with custom category
    res_b = await engine.inspect("Refer to PROJECT-ABC-1234 design docs", tenant_id="tenant_b")
    custom_b = [d for d in res_b.detections if d.is_custom_category]
    assert len(custom_b) == 0


@pytest.mark.asyncio
async def test_dlp_engine_inspect_request(dlp_engine):
    ctx = ProcessingContext(request_id="dlp-test-001", tenant_id="default")
    ctx.text_nodes = [
        {"value": "Contact john.doe@example.com"},
        {"value": "No secrets here"},
    ]
    res = await dlp_engine.inspect_request(ctx)
    emails = [d for d in res.detections if d.category == DLPCategory.PII and d.pattern_id == "pii_email"]
    assert len(emails) == 1
