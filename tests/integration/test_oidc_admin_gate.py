"""Integration tests for OIDC-backed admin access."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from anonreq.admin.router import require_auth
from anonreq.admin.routes import admin_router as config_admin_router
from anonreq.auth.oidc import build_oidc_verifier
from anonreq.config import settings


def _b64url_encode(value: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _rsa_keypair(kid: str) -> tuple[rsa.RSAPrivateKey, dict[str, Any]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private_key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": _b64url_encode(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
        "e": _b64url_encode(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
    }
    return private_key, jwk


def _sign_jwt(
    private_key: rsa.RSAPrivateKey,
    *,
    kid: str,
    claims: dict[str, Any],
) -> str:
    import json

    header = {"alg": "RS256", "typ": "JWT", "kid": kid}
    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{header_segment}.{payload_segment}.{_b64url_encode(signature)}"


@pytest.fixture
def oidc_admin_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setattr(settings, "ADMIN_API_KEY", None)
    monkeypatch.setattr(settings, "OIDC_ISSUER", "https://issuer.example")
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", "anonreq-admin")
    monkeypatch.setattr(settings, "OIDC_JWKS_URL", "https://issuer.example/.well-known/jwks.json")
    monkeypatch.setattr(settings, "OIDC_ROLE_CLAIM", "role")
    monkeypatch.setattr(settings, "OIDC_JWKS_CACHE_SECONDS", 300)

    signing_key, jwk = _rsa_keypair("kid-1")
    jwks_state = {"keys": [jwk]}

    async def fetch_jwks(_: str) -> dict[str, Any]:
        return jwks_state

    verifier = build_oidc_verifier(
        issuer=settings.OIDC_ISSUER,
        audience=settings.OIDC_AUDIENCE,
        jwks_url=settings.OIDC_JWKS_URL,
        role_claim=settings.OIDC_ROLE_CLAIM,
        cache_ttl_seconds=settings.OIDC_JWKS_CACHE_SECONDS,
        fetch_jwks=fetch_jwks,
    )

    app = FastAPI()
    app.state.oidc_verifier = verifier
    app.state.signing_key = signing_key

    @app.get("/v1/admin/principal", dependencies=[Depends(require_auth)])
    async def principal(
        request: Request,
    ) -> dict[str, Any]:
        return request.state.role_principal

    app.include_router(config_admin_router)
    return app


def _claims(exp_delta: timedelta = timedelta(minutes=10)) -> dict[str, Any]:
    return {
        "iss": "https://issuer.example",
        "aud": "anonreq-admin",
        "sub": "user-123",
        "tenant_id": "tenant-a",
        "role": "administrator",
        "exp": int((datetime.now(UTC) + exp_delta).timestamp()),
    }


def test_valid_oidc_token_allows_admin_access(oidc_admin_app: FastAPI) -> None:
    client = TestClient(oidc_admin_app)
    token = _sign_jwt(
        oidc_admin_app.state.signing_key,
        kid="kid-1",
        claims=_claims(),
    )

    response = client.get(
        "/v1/admin/principal",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["principal_id"] == "user-123"
    assert body["role"] == "administrator"
    assert body["tenant_id"] == "tenant-a"


def test_valid_oidc_token_can_call_admin_route(oidc_admin_app: FastAPI) -> None:
    client = TestClient(oidc_admin_app)
    token = _sign_jwt(
        oidc_admin_app.state.signing_key,
        kid="kid-1",
        claims=_claims(),
    )

    response = client.post(
        "/v1/admin/config/rules",
        headers={"Authorization": f"Bearer {token}"},
        json={"custom_recognizers": []},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_invalid_signature_is_rejected(oidc_admin_app: FastAPI) -> None:
    client = TestClient(oidc_admin_app)
    bad_key, _ = _rsa_keypair("kid-1")
    token = _sign_jwt(bad_key, kid="kid-1", claims=_claims())

    response = client.get(
        "/v1/admin/principal",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_expired_token_is_rejected(oidc_admin_app: FastAPI) -> None:
    client = TestClient(oidc_admin_app)
    token = _sign_jwt(
        oidc_admin_app.state.signing_key,
        kid="kid-1",
        claims=_claims(exp_delta=timedelta(minutes=-5)),
    )

    response = client.get(
        "/v1/admin/principal",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
