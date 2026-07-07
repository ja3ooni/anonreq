from __future__ import annotations

import ssl

import pytest

from anonreq.proxy.detection import AITrafficDetector, CertPinningDetector
from anonreq.proxy.transparent_proxy import ProxyRequest, TransparentProxy


class DummyTLSInterceptor:
    def __init__(self) -> None:
        self.domains: list[str] = []

    async def generate_cert(self, domain: str) -> ssl.SSLContext:
        self.domains.append(domain)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        return context


class DummyDispatcher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bytes, object]] = []

    async def dispatch(self, content_type: str, body: bytes, ctx: object):
        self.calls.append((content_type, body, ctx))
        return b"dispatched"


@pytest.fixture
def proxy() -> TransparentProxy:
    return TransparentProxy(
        tls_interceptor=DummyTLSInterceptor(),
        traffic_detector=AITrafficDetector(),
        content_dispatcher=DummyDispatcher(),
        fail_open=False,
    )


@pytest.mark.asyncio
async def test_transparent_proxy_routes_ai_api_traffic_to_dispatcher(proxy: TransparentProxy):
    response = await proxy.handle_request(
        ProxyRequest(
            method="POST",
            host="api.openai.com",
            path="/v1/chat/completions",
            headers={"content-type": "application/json", "connection": "keep-alive"},
            body=b'{"model":"gpt-4.1"}',
            client_hello=b"api.openai.com",
        )
    )

    assert response.status_code == 200
    assert response.routed_to_dispatcher is True
    assert response.body == b"dispatched"
    assert response.headers["connection"] == "keep-alive"


@pytest.mark.asyncio
async def test_non_ai_traffic_returns_451_in_fail_closed(proxy: TransparentProxy):
    response = await proxy.handle_request(
        ProxyRequest(
            method="GET",
            host="example.com",
            path="/",
            client_hello=b"example.com",
        )
    )

    assert response.status_code == 451
    assert response.headers["x-anonreq-block-reason"] == "host_not_in_ai_registry"


@pytest.mark.asyncio
async def test_non_ai_traffic_forwarded_untouched_in_fail_open():
    proxy = TransparentProxy(
        tls_interceptor=DummyTLSInterceptor(),
        traffic_detector=AITrafficDetector(),
        content_dispatcher=DummyDispatcher(),
        fail_open=True,
    )

    response = await proxy.handle_request(
        ProxyRequest(method="GET", host="example.com", path="/", body=b"raw", client_hello=b"example.com")
    )

    assert response.status_code == 200
    assert response.forwarded_untouched is True
    assert response.body == b"raw"


def test_certificate_pinning_detector_detects_known_markers():
    detector = CertPinningDetector()

    assert detector.check_pinning(b"TLS alert: certificate pinning failure", "api.openai.com")


@pytest.mark.asyncio
async def test_pinned_traffic_blocked_in_fail_closed(proxy: TransparentProxy):
    response = await proxy.handle_request(
        ProxyRequest(
            method="POST",
            host="api.openai.com",
            path="/v1/chat/completions",
            client_hello=b"certificate pinning failure",
        )
    )

    assert response.status_code == 451
    assert response.headers["x-anonreq-block-reason"] == "certificate_pinning_detected"


@pytest.mark.asyncio
async def test_pinned_traffic_forwarded_in_fail_open():
    proxy = TransparentProxy(
        tls_interceptor=DummyTLSInterceptor(),
        traffic_detector=AITrafficDetector(),
        content_dispatcher=DummyDispatcher(),
        fail_open=True,
    )

    response = await proxy.handle_request(
        ProxyRequest(
            method="POST",
            host="api.openai.com",
            path="/v1/chat/completions",
            body=b"raw",
            client_hello=b"certificate pinning failure",
        )
    )

    assert response.status_code == 200
    assert response.forwarded_untouched is True
    assert response.headers["x-anonreq-pass-through-reason"] == "certificate_pinning"


def test_ai_traffic_detector_requires_known_host_and_path():
    detector = AITrafficDetector()

    assert detector.is_ai_traffic("api.anthropic.com", "/v1/messages")
    assert detector.classify("api.openai.com", "/not-ai", "GET") == "unknown"
    assert detector.classify("example.com", "/v1/chat/completions", "POST") == "non_ai"


def test_transparent_proxy_serialized_response_preserves_keep_alive(proxy: TransparentProxy):
    response = proxy._serialize_response(
        response=type(
            "Response",
            (),
            {
                "status_code": 200,
                "body": b"ok",
                "headers": {"connection": "keep-alive"},
            },
        )()
    )

    assert b"connection: keep-alive" in response
