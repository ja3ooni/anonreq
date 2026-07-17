"""Unit tests for ingress-forwarded mTLS validation."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from anonreq.middleware.mtls import (
    IngressMTLSMiddleware,
    _decode_forwarded_certificate,
)


def _self_signed_cert(common_name: str = "svc.example") -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, common_name)]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.DER)


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(IngressMTLSMiddleware)

    @app.get("/ingress")
    async def ingress(request: Request) -> dict[str, Any]:
        return request.state.machine_principal

    return app


@pytest.mark.asyncio
async def test_forwarded_certificate_is_parsed() -> None:
    cert_der = _self_signed_cert()
    cert = _decode_forwarded_certificate(base64.b64encode(cert_der).decode("ascii"))
    assert cert.subject.rfc4514_string() == "CN=svc.example"


@pytest.mark.asyncio
async def test_trusted_proxy_populates_machine_principal(monkeypatch) -> None:
    from anonreq.config import settings

    monkeypatch.setattr(settings, "MTLS_ENFORCE", True)
    monkeypatch.setattr(settings, "MTLS_TRUSTED_PROXY_CIDRS", "127.0.0.1/32")
    monkeypatch.setattr(settings, "MTLS_FORWARD_CERT_HEADER", "X-Forwarded-Client-Cert")

    cert_der = _self_signed_cert()
    transport = ASGITransport(app=_app(), client=("127.0.0.1", 1234))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/ingress",
            headers={"X-Forwarded-Client-Cert": base64.b64encode(cert_der).decode("ascii")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["principal_id"] == "CN=svc.example"
    assert body["role"] == "machine"
    assert body["tenant_id"] == "*"


@pytest.mark.asyncio
async def test_malformed_certificate_is_rejected(monkeypatch) -> None:
    from anonreq.config import settings

    monkeypatch.setattr(settings, "MTLS_ENFORCE", True)
    monkeypatch.setattr(settings, "MTLS_TRUSTED_PROXY_CIDRS", "127.0.0.1/32")
    monkeypatch.setattr(settings, "MTLS_FORWARD_CERT_HEADER", "X-Forwarded-Client-Cert")

    transport = ASGITransport(app=_app(), client=("127.0.0.1", 1234))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/ingress",
            headers={"X-Forwarded-Client-Cert": "not-a-certificate"},
        )

    assert response.status_code == 401
