"""OIDC bearer-token verification with cached JWKS lookups."""

from __future__ import annotations

import asyncio
import base64
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.hashes import SHA256


def _b64url_decode(value: str) -> bytes:
    padding_len = (-len(value)) % 4
    return base64.urlsafe_b64decode(value + ("=" * padding_len))


def _coerce_audience(audience: Any) -> set[str]:
    if isinstance(audience, str):
        return {audience}
    if isinstance(audience, list):
        return {item for item in audience if isinstance(item, str)}
    return set()


def _public_key_from_jwk(jwk: dict[str, Any]) -> rsa.RSAPublicKey:
    if jwk.get("kty") != "RSA":
        raise ValueError("Unsupported JWK key type")
    n = int.from_bytes(_b64url_decode(jwk["n"]), "big")
    e = int.from_bytes(_b64url_decode(jwk["e"]), "big")
    numbers = rsa.RSAPublicNumbers(e=e, n=n)
    return numbers.public_key()


async def _default_fetch_jwks(jwks_url: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        return dict(response.json())


@dataclass(slots=True)
class JWKSCache:
    """Cache JWKS payloads and derived public keys."""

    jwks_url: str
    ttl_seconds: int = 300
    fetch_jwks: Callable[[str], Awaitable[dict[str, Any]]] = _default_fetch_jwks
    _keys: dict[str, rsa.RSAPublicKey] = field(default_factory=dict, init=False)
    _expires_at: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def get_key(self, kid: str) -> rsa.RSAPublicKey:
        if not kid:
            raise ValueError("Missing JWKS key id")
        if self._is_fresh() and kid in self._keys:
            return self._keys[kid]
        async with self._lock:
            if self._is_fresh() and kid in self._keys:
                return self._keys[kid]
            await self.refresh()
            if kid not in self._keys:
                raise ValueError(f"JWKS key not found for kid={kid}")
            return self._keys[kid]

    async def refresh(self) -> None:
        jwks = await self.fetch_jwks(self.jwks_url)
        keys: dict[str, rsa.RSAPublicKey] = {}
        for raw_key in jwks.get("keys", []):
            if not isinstance(raw_key, dict):
                continue
            kid = raw_key.get("kid")
            if not isinstance(kid, str) or not kid:
                continue
            keys[kid] = _public_key_from_jwk(raw_key)
        self._keys = keys
        self._expires_at = time.monotonic() + self.ttl_seconds

    def _is_fresh(self) -> bool:
        return bool(self._keys) and time.monotonic() < self._expires_at


@dataclass(slots=True)
class OIDCVerifier:
    """Verify OIDC bearer tokens against cached JWKS."""

    issuer: str
    audience: str
    jwks_cache: JWKSCache
    role_claim: str = "role"

    async def verify_authorization(self, authorization: str | None) -> dict[str, Any]:
        token = self._extract_bearer_token(authorization)
        header, payload, signing_input, signature = self._split_token(token)
        if header.get("alg") != "RS256":
            raise OIDCVerificationError("Unsupported JWT algorithm")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise OIDCVerificationError("Missing JWT key id")
        public_key = await self.jwks_cache.get_key(kid)
        try:
            public_key.verify(signature, signing_input, padding.PKCS1v15(), SHA256())
        except InvalidSignature as exc:
            raise OIDCVerificationError("Invalid JWT signature") from exc
        claims = self._validate_claims(payload)
        return self._build_principal(claims)

    def _extract_bearer_token(self, authorization: str | None) -> str:
        if authorization is None:
            raise OIDCVerificationError("Missing Authorization header")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise OIDCVerificationError("Invalid Authorization header")
        return token

    def _split_token(self, token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
        try:
            header_b64, payload_b64, signature_b64 = token.split(".")
            signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
            header = json.loads(_b64url_decode(header_b64))
            payload = json.loads(_b64url_decode(payload_b64))
            signature = _b64url_decode(signature_b64)
        except Exception as exc:
            raise OIDCVerificationError("Malformed JWT") from exc
        return header, payload, signing_input, signature

    def _validate_claims(self, claims: dict[str, Any]) -> dict[str, Any]:
        issuer = claims.get("iss")
        if issuer != self.issuer:
            raise OIDCVerificationError("Invalid issuer")
        audience = _coerce_audience(claims.get("aud"))
        if self.audience not in audience:
            raise OIDCVerificationError("Invalid audience")
        exp = claims.get("exp")
        if not isinstance(exp, int) or exp <= int(time.time()):
            raise OIDCVerificationError("Token expired")
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub:
            raise OIDCVerificationError("Missing subject")
        return claims

    def _build_principal(self, claims: dict[str, Any]) -> dict[str, Any]:
        role_value = claims.get(self.role_claim)
        if isinstance(role_value, list):
            role_value = next((item for item in role_value if isinstance(item, str)), None)
        if not isinstance(role_value, str) or not role_value:
            raise OIDCVerificationError("Missing role claim")
        tenant_id = claims.get("tenant_id")
        if not isinstance(tenant_id, str) or not tenant_id:
            tenant_id = "*"
        return {
            "principal_id": claims["sub"],
            "role": role_value,
            "tenant_id": tenant_id,
            "issuer": claims["iss"],
        }


class OIDCVerificationError(Exception):
    """Raised when OIDC authentication fails."""


def build_oidc_verifier(
    issuer: str,
    audience: str,
    jwks_url: str,
    role_claim: str = "role",
    cache_ttl_seconds: int = 300,
    fetch_jwks: Callable[[str], Awaitable[dict[str, Any]]] | None = None,
) -> OIDCVerifier:
    return OIDCVerifier(
        issuer=issuer,
        audience=audience,
        jwks_cache=JWKSCache(
            jwks_url=jwks_url,
            ttl_seconds=cache_ttl_seconds,
            fetch_jwks=fetch_jwks or _default_fetch_jwks,
        ),
        role_claim=role_claim,
    )
