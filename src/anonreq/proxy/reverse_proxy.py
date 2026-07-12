"""Reverse proxy support for explicit AnonReq appliance deployments."""

from __future__ import annotations

import ssl
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin


@dataclass
class ReverseProxyRequest:
    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""


@dataclass
class ReverseProxyResponse:
    status_code: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)
    connect_tunnel: bool = False
    upstream_url: str | None = None


class ReverseProxy:
    """HTTP reverse proxy facade that routes requests through the dispatcher."""

    def __init__(self, content_dispatcher: Any, upstream_base_url: str = "https://api.openai.com") -> None:  # noqa: E501
        self.content_dispatcher = content_dispatcher
        self.upstream_base_url = upstream_base_url.rstrip("/")
        self.outbound_tls_context = ssl.create_default_context()
        self.outbound_tls_context.minimum_version = ssl.TLSVersion.TLSv1_3

    async def handle(self, request: ReverseProxyRequest) -> ReverseProxyResponse:
        if request.method.upper() == "CONNECT":
            return await self.handle_connect(request)

        headers = self._preserve_metadata(request.headers)
        content_type = headers.get("content-type", "application/json")
        if hasattr(self.content_dispatcher, "dispatch"):
            result = await self.content_dispatcher.dispatch(content_type, request.body, ctx={"path": request.path})  # noqa: E501
        elif callable(self.content_dispatcher):
            result = await self.content_dispatcher(request)
        else:
            result = request.body
        body = result if isinstance(result, bytes) else str(result).encode("utf-8")
        return ReverseProxyResponse(
            status_code=200,
            body=body,
            headers=headers,
            upstream_url=self.rewrite_url(request.path),
        )

    async def handle_connect(self, request: ReverseProxyRequest) -> ReverseProxyResponse:
        target = request.path or request.headers.get("host", "")
        return ReverseProxyResponse(
            status_code=200,
            body=b"",
            headers={"connection": "keep-alive", "x-anonreq-connect-target": target},
            connect_tunnel=True,
            upstream_url=f"https://{target}",
        )

    def rewrite_url(self, path: str) -> str:
        return urljoin(f"{self.upstream_base_url}/", path.lstrip("/"))

    @staticmethod
    def _preserve_metadata(headers: dict[str, str]) -> dict[str, str]:
        return {key.lower(): value for key, value in headers.items()}
