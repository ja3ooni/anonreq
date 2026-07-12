"""Transparent AI traffic proxy primitives.

The production deployment attaches this class behind DNS, iptables, or eBPF
redirection. The implementation keeps network operations small and testable:
classification, pinning policy, protocol preservation, and dispatcher routing
are explicit methods; ``start`` owns only the asyncio listener lifecycle.
"""

from __future__ import annotations

import asyncio
import ssl
from dataclasses import dataclass, field
from typing import Any

import structlog

from anonreq.firewall.config import FIREWALL_DECISIONS
from anonreq.proxy.detection import AITrafficDetector, CertPinningDetector, TrafficDecision
from anonreq.proxy.metrics import (
    fail_closed_total,
    proxy_cert_pinning_detected_total,
    proxy_non_ai_blocked_total,
    proxy_tls_intercepted_total,
)
from anonreq.proxy.tls_interceptor import TLSInterceptor

log = structlog.get_logger(__name__)


@dataclass
class ProxyRequest:
    method: str
    host: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    client_hello: bytes = b""


@dataclass
class ProxyResponse:
    status_code: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)
    forwarded_untouched: bool = False
    routed_to_dispatcher: bool = False
    classification: str = "unknown"


class TransparentProxy:
    """Transparent proxy with TLS interception and fail-closed policy."""

    def __init__(
        self,
        tls_interceptor: TLSInterceptor,
        traffic_detector: AITrafficDetector,
        content_dispatcher: Any,
        fail_open: bool = False,
        pinning_detector: CertPinningDetector | None = None,
        firewall_pipeline: Any | None = None,
        connection_timeout_s: float = 30.0,
    ) -> None:
        self.tls_interceptor = tls_interceptor
        self.traffic_detector = traffic_detector
        self.content_dispatcher = content_dispatcher
        self.fail_open = fail_open
        self.pinning_detector = pinning_detector or CertPinningDetector()
        self.firewall_pipeline = firewall_pipeline
        self.connection_timeout_s = connection_timeout_s
        self._server: asyncio.AbstractServer | None = None

    async def start(self, host: str = "0.0.0.0", port: int = 8443) -> None:
        if self._server is not None:
            return
        self._server = await asyncio.start_server(self._handle_connection, host, port)

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def handle_request(self, request: ProxyRequest) -> ProxyResponse:
        firewall_response = await self._evaluate_firewall(request)
        if firewall_response is not None:
            return firewall_response

        if self.pinning_detector.check_pinning(request.client_hello, request.host):
            if not self.fail_open:
                proxy_cert_pinning_detected_total.labels(domain=request.host, action="block").inc()
                return self._blocked("certificate_pinning_detected", request, status_code=451)
            proxy_cert_pinning_detected_total.labels(domain=request.host, action="log").inc()
            log.warning(
                "Certificate pinning detected; forwarding untouched due to fail-open policy",
                component="transparent_proxy",
                host=request.host,
            )
            return await self._forward_untouched_request(request, reason="certificate_pinning")

        decision = self.traffic_detector.classify_request(
            host=request.host,
            path=request.path,
            method=request.method,
        )
        if not decision.is_ai:
            if self.fail_open:
                return await self._forward_untouched_request(request, reason=decision.reason)
            proxy_non_ai_blocked_total.labels(policy="fail-closed").inc()
            return self._blocked(decision.reason, request, status_code=451, decision=decision)

        try:
            await self.tls_interceptor.generate_cert(request.host)
            proxy_tls_intercepted_total.labels(domain=request.host, tenant_id="default").inc()
            return await self._route_to_dispatcher(request, decision)
        except Exception:
            fail_closed_total.labels(component="transparent_proxy", failure_reason="interception_error").inc()  # noqa: E501
            return ProxyResponse(
                status_code=500,
                body=b"Transparent proxy failed closed.",
                headers={"connection": "close", "x-anonreq-block-reason": "interception_error"},
                classification=decision.classification,
            )

    async def _evaluate_firewall(self, request: ProxyRequest) -> ProxyResponse | None:
        if self.firewall_pipeline is None:
            return None
        try:
            request_text = request.body.decode("utf-8", errors="replace")
            decision = await self.firewall_pipeline.evaluate(request_text)
        except Exception:
            fail_closed_total.labels(component="firewall", failure_reason="evaluation_error").inc()
            return ProxyResponse(
                status_code=500,
                body=b"Security firewall failed closed.",
                headers={"connection": "close", "x-anonreq-block-reason": "firewall_error"},
            )
        if decision.action == FIREWALL_DECISIONS.BLOCK:
            return ProxyResponse(
                status_code=403,
                body=b"Security policy violation. Request blocked.",
                headers={
                    "connection": "close",
                    "x-anonreq-block-reason": "ai_firewall",
                    "x-anonreq-mitre-atlas-id": decision.mitre_atlas_id or "",
                },
                classification=decision.detection_type or "ai_firewall",
            )
        return None

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            data = await asyncio.wait_for(reader.read(65536), timeout=self.connection_timeout_s)
            request = self._parse_http_request(data)
            response = await self.handle_request(request)
            writer.write(self._serialize_response(response))
            await writer.drain()
        except Exception as exc:
            log.error("Transparent proxy connection failed", component="transparent_proxy", error=str(exc))  # noqa: E501
            writer.write(b"HTTP/1.1 500 Internal Server Error\r\nConnection: close\r\n\r\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def _route_to_dispatcher(
        self,
        request: ProxyRequest,
        decision: TrafficDecision,
    ) -> ProxyResponse:
        headers = self._preserve_headers(request.headers)
        content_type = headers.get("content-type", "application/json")
        if hasattr(self.content_dispatcher, "dispatch"):
            result = await self.content_dispatcher.dispatch(content_type, request.body, ctx={"host": request.host})  # noqa: E501
        elif callable(self.content_dispatcher):
            result = await self.content_dispatcher(request)
        else:
            result = {"status": "routed"}
        body = result if isinstance(result, bytes) else str(result).encode("utf-8")
        return ProxyResponse(
            status_code=200,
            body=body,
            headers=headers,
            routed_to_dispatcher=True,
            classification=decision.classification,
        )

    async def _forward_untouched_request(self, request: ProxyRequest, reason: str) -> ProxyResponse:
        headers = self._preserve_headers(request.headers)
        headers["x-anonreq-pass-through-reason"] = reason
        return ProxyResponse(
            status_code=200,
            body=request.body,
            headers=headers,
            forwarded_untouched=True,
            classification="non_ai",
        )

    async def _forward_untouched(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        host: str,
        port: int,
    ) -> None:
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        upstream_reader, upstream_writer = await asyncio.open_connection(host, port, ssl=context)
        try:
            while data := await reader.read(65536):
                upstream_writer.write(data)
                await upstream_writer.drain()
                writer.write(await upstream_reader.read(65536))
                await writer.drain()
        finally:
            upstream_writer.close()
            await upstream_writer.wait_closed()

    def _blocked(
        self,
        reason: str,
        _request: ProxyRequest,
        status_code: int,
        decision: TrafficDecision | None = None,
    ) -> ProxyResponse:
        return ProxyResponse(
            status_code=status_code,
            body=f"Blocked by AnonReq transparent proxy: {reason}".encode(),
            headers={"connection": "close", "x-anonreq-block-reason": reason},
            classification=decision.classification if decision else "unknown",
        )

    @staticmethod
    def _preserve_headers(headers: dict[str, str]) -> dict[str, str]:
        preserved = {k.lower(): v for k, v in headers.items()}
        for name in ("connection", "keep-alive", "host"):
            if name in preserved:
                preserved[name] = headers.get(name, preserved[name])
        return preserved

    @staticmethod
    def _parse_http_request(data: bytes) -> ProxyRequest:
        head, _, body = data.partition(b"\r\n\r\n")
        lines = head.decode("iso-8859-1", errors="replace").splitlines()
        method, path, _version = ([*lines[0].split(" ", 2), "", ""])[:3]
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        return ProxyRequest(
            method=method,
            host=headers.get("host", ""),
            path=path or "/",
            headers=headers,
            body=body,
            client_hello=data[:512],
        )

    @staticmethod
    def _serialize_response(response: ProxyResponse) -> bytes:
        reason = {
            200: "OK",
            403: "Forbidden",
            451: "Unavailable For Legal Reasons",
            500: "Internal Server Error",
        }.get(response.status_code, "OK")
        headers = {"content-length": str(len(response.body)), **response.headers}
        header_blob = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
        return f"HTTP/1.1 {response.status_code} {reason}\r\n{header_blob}\r\n".encode("ascii") + response.body  # noqa: E501
