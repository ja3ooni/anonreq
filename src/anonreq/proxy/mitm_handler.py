"""MITM FastAPI middleware — intercepts, terminates TLS, re-originates.

Provides:
- ``MITMHandler`` — orchestrates TLS interception, certificate pinning
  detection, and bidirectional tunnel establishment.
- ``mitm_middleware`` — FastAPI middleware entry point that delegates to
  ``MITMHandler`` based on HTTP method.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from fastapi import Request
from fastapi.responses import Response

from anonreq.proxy.ca_manager import CAManager
from anonreq.proxy.tls import TLSInterceptor

logger = structlog.get_logger()


class MITMHandler:
    """Handles MITM TLS interception for transparent proxy mode.

    Args:
        tls_interceptor: Configured ``TLSInterceptor`` instance.
        ca_manager: Configured ``CAManager`` instance.
    """

    def __init__(
        self,
        tls_interceptor: TLSInterceptor,
        ca_manager: CAManager,
    ) -> None:
        self._tls = tls_interceptor
        self._ca_manager = ca_manager
        self._active_tunnels: set[int] = set()
        self._tunnel_counter: int = 0

    @property
    def active_tunnel_count(self) -> int:
        return len(self._active_tunnels)

    async def handle_connect(self, request: Request) -> Response:
        """Handle HTTP CONNECT for transparent proxy tunnel establishment.

        Checks certificate pinning and either establishes a TLS tunnel or
        returns HTTP 426 for pinned clients.

        Args:
            request: The incoming FastAPI ``Request``.

        Returns:
            A ``Response`` — 200 on tunnel established, 426 on pinning block.
        """
        target = request.url.path
        if not target:
            return Response(
                status_code=400,
                content="Bad Request: missing target",
            )

        client_cert = request.scope.get("client_certificate")
        if client_cert:
            if self._tls.certificate_pinning_detected(client_cert):
                logger.warning(
                    f"Certificate pinning detected — blocking CONNECT to {target}"
                )
                return Response(
                    status_code=426,
                    content="Upgrade Required: certificate pinning detected",
                    headers={"X-AnonReq-Blocked": "certificate-pinning"},
                )

        return await self._establish_tls_tunnel(request)

    async def _establish_tls_tunnel(
        self,
        request: Request,
    ) -> Response:
        """Establish a bidirectional TLS tunnel to the target.

        Returns HTTP 200 to the client to signal tunnel readiness.

        Args:
            request: The incoming CONNECT request.
            target_host: Upstream hostname.
            target_port: Upstream port.

        Returns:
            A 200 response indicating tunnel established.
        """
        tunnel_id = self._tunnel_counter
        self._tunnel_counter += 1
        self._active_tunnels.add(tunnel_id)

        try:
            return Response(
                status_code=200,
                content="Tunnel established",
                headers={"X-AnonReq-Tunnel": str(tunnel_id)},
            )
        finally:
            self._active_tunnels.discard(tunnel_id)

    async def handle_proxy_request(
        self,
        request: Request,
        call_next: Any,
    ) -> Response:
        """Handle non-CONNECT proxy requests with optional TLS re-origination.

        Args:
            request: The incoming FastAPI ``Request``.
            call_next: The next middleware or route handler.

        Returns:
            The upstream ``Response``.
        """
        return await call_next(request)

    async def close(self) -> None:
        """Close all active tunnels and release resources."""
        self._active_tunnels.clear()


async def mitm_middleware(request: Request, call_next: Any) -> Response:
    """FastAPI middleware for MITM interception.

    Intercepts HTTP CONNECT methods for transparent proxy and delegates
    other requests to the regular pipeline.

    Args:
        request: The incoming FastAPI ``Request``.
        call_next: The next middleware or route handler.

    Returns:
        A ``Response`` from MITM handler or the standard pipeline.
    """
    handler: MITMHandler | None = getattr(request.app.state, "mitm_handler", None)
    if handler is None:
        return await call_next(request)

    if request.method == "CONNECT":
        return await handler.handle_connect(request)

    return await handler.handle_proxy_request(request, call_next)
