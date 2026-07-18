"""Ingress-forwarded mTLS validation middleware."""

from __future__ import annotations

import base64
import ipaddress
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from anonreq.config import settings


def _trusted_proxy_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    cidrs = [cidr.strip() for cidr in settings.MTLS_TRUSTED_PROXY_CIDRS.split(",")]
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for cidr in cidrs:
        if not cidr:
            continue
        networks.append(ipaddress.ip_network(cidr, strict=False))
    return networks


def _request_is_from_trusted_proxy(request: Request) -> bool:
    if not settings.MTLS_ENFORCE:
        return False
    client = request.client
    if client is None or not client.host:
        return False
    try:
        host_ip = ipaddress.ip_address(client.host)
    except ValueError:
        return False
    return any(host_ip in network for network in _trusted_proxy_networks())


def _decode_forwarded_certificate(raw_value: str) -> x509.Certificate:
    value = raw_value.strip().strip('"')
    if not value:
        raise ValueError("empty certificate header")
    if "BEGIN CERTIFICATE" in value:
        return x509.load_pem_x509_certificate(value.encode("utf-8"))

    decoded: bytes | None = None
    try:
        decoded = base64.b64decode(value, validate=True)
    except Exception:
        decoded = None

    if decoded is not None:
        try:
            return x509.load_der_x509_certificate(decoded)
        except Exception:
            try:
                return x509.load_pem_x509_certificate(decoded)
            except Exception as exc:
                raise ValueError("invalid forwarded certificate") from exc

    try:
        return x509.load_pem_x509_certificate(value.encode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid forwarded certificate") from exc


def _machine_principal_from_certificate(cert: x509.Certificate) -> dict[str, Any]:
    return {
        "principal_id": cert.subject.rfc4514_string(),
        "role": "machine",
        "tenant_id": "*",
        "certificate_subject": cert.subject.rfc4514_string(),
        "certificate_issuer": cert.issuer.rfc4514_string(),
        "certificate_fingerprint_sha256": cert.fingerprint(hashes.SHA256()).hex(),
    }


class IngressMTLSMiddleware(BaseHTTPMiddleware):
    """Validate ingress-forwarded client certificates on trusted paths."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.MTLS_ENFORCE:
            return await call_next(request)

        if not _request_is_from_trusted_proxy(request):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": {
                        "error": "forbidden",
                        "reason": "untrusted_ingress_proxy",
                    }
                },
            )

        cert_header = request.headers.get(settings.MTLS_FORWARD_CERT_HEADER)
        if not cert_header:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": {
                        "error": "unauthorized",
                        "reason": "missing_forwarded_certificate",
                    }
                },
            )

        try:
            cert = _decode_forwarded_certificate(cert_header)
        except ValueError:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": {
                        "error": "unauthorized",
                        "reason": "invalid_forwarded_certificate",
                    }
                },
            )

        request.state.machine_principal = _machine_principal_from_certificate(cert)
        request.state.mtls_verified = True
        return await call_next(request)
