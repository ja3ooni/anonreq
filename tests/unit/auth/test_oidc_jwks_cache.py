"""Tests for OIDC JWT verification and JWKS caching."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from anonreq.auth.oidc import OIDCVerificationError, build_oidc_verifier


def _b64url_encode(value: bytes) -> str:
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
    header = {"alg": "RS256", "typ": "JWT", "kid": kid}
    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{header_segment}.{payload_segment}.{_b64url_encode(signature)}"


@pytest.mark.asyncio
async def test_jwks_is_cached_between_verifications() -> None:
    key, jwk = _rsa_keypair("kid-1")
    calls = 0
    jwks = {"keys": [jwk]}

    async def fetch_jwks(_: str) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return jwks

    verifier = build_oidc_verifier(
        issuer="https://issuer.example",
        audience="anonreq-admin",
        jwks_url="https://issuer.example/.well-known/jwks.json",
        role_claim="role",
        cache_ttl_seconds=300,
        fetch_jwks=fetch_jwks,
    )

    claims = {
        "iss": "https://issuer.example",
        "aud": "anonreq-admin",
        "sub": "user-123",
        "tenant_id": "tenant-a",
        "role": "administrator",
        "exp": int((datetime.now(UTC) + timedelta(minutes=10)).timestamp()),
    }
    token = _sign_jwt(key, kid="kid-1", claims=claims)

    principal_1 = await verifier.verify_authorization(f"Bearer {token}")
    principal_2 = await verifier.verify_authorization(f"Bearer {token}")

    assert calls == 1
    assert principal_1 == principal_2
    assert principal_1["principal_id"] == "user-123"
    assert principal_1["role"] == "administrator"
    assert principal_1["tenant_id"] == "tenant-a"


@pytest.mark.asyncio
async def test_jwks_refreshes_after_cache_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    key_1, jwk_1 = _rsa_keypair("kid-1")
    key_2, jwk_2 = _rsa_keypair("kid-2")
    calls = 0
    jwks_state = {"keys": [jwk_1]}
    clock = {"value": 0.0}

    async def fetch_jwks(_: str) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return jwks_state

    monkeypatch.setattr("anonreq.auth.oidc.time.monotonic", lambda: clock["value"])

    verifier = build_oidc_verifier(
        issuer="https://issuer.example",
        audience="anonreq-admin",
        jwks_url="https://issuer.example/.well-known/jwks.json",
        role_claim="role",
        cache_ttl_seconds=60,
        fetch_jwks=fetch_jwks,
    )

    claims = {
        "iss": "https://issuer.example",
        "aud": "anonreq-admin",
        "sub": "user-123",
        "tenant_id": "tenant-a",
        "role": "administrator",
        "exp": int((datetime.now(UTC) + timedelta(minutes=10)).timestamp()),
    }

    token_1 = _sign_jwt(key_1, kid="kid-1", claims=claims)
    principal_1 = await verifier.verify_authorization(f"Bearer {token_1}")
    assert principal_1["principal_id"] == "user-123"
    assert calls == 1

    jwks_state["keys"] = [jwk_2]
    clock["value"] = 120.0
    token_2 = _sign_jwt(key_2, kid="kid-2", claims=claims)
    principal_2 = await verifier.verify_authorization(f"Bearer {token_2}")
    assert principal_2["principal_id"] == "user-123"
    assert calls == 2


@pytest.mark.asyncio
async def test_invalid_signature_and_expired_token_fail_closed() -> None:
    good_key, jwk = _rsa_keypair("kid-1")
    bad_key, _ = _rsa_keypair("kid-2")
    calls = 0

    async def fetch_jwks(_: str) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"keys": [jwk]}

    verifier = build_oidc_verifier(
        issuer="https://issuer.example",
        audience="anonreq-admin",
        jwks_url="https://issuer.example/.well-known/jwks.json",
        role_claim="role",
        cache_ttl_seconds=300,
        fetch_jwks=fetch_jwks,
    )

    valid_claims = {
        "iss": "https://issuer.example",
        "aud": "anonreq-admin",
        "sub": "user-123",
        "tenant_id": "tenant-a",
        "role": "administrator",
        "exp": int((datetime.now(UTC) + timedelta(minutes=10)).timestamp()),
    }
    expired_claims = {
        **valid_claims,
        "exp": int((datetime.now(UTC) - timedelta(minutes=5)).timestamp()),
    }

    invalid_signature_token = _sign_jwt(bad_key, kid="kid-1", claims=valid_claims)
    expired_token = _sign_jwt(good_key, kid="kid-1", claims=expired_claims)

    with pytest.raises(OIDCVerificationError, match="signature"):
        await verifier.verify_authorization(f"Bearer {invalid_signature_token}")

    with pytest.raises(OIDCVerificationError, match="expired"):
        await verifier.verify_authorization(f"Bearer {expired_token}")

    assert calls >= 1
