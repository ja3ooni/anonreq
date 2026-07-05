"""MCP message inspection with policy enforcement.

Provides:
- ``InspectionResult`` — dataclass for MCP inspection results.
- ``MCPInspector`` — inspects HTTP requests/responses for MCP content,
  parses tool calls and tool results, and integrates with the hostname
  allowlist for destination validation.

Per D-007, D-008:
- ``inspect_request``: Parses MCP messages from request bodies.
- ``inspect_response``: Inspects MCP responses for suspicious tool results.
- ``mcp_content_type_detected``: Checks Content-Type for MCP indicators.
- Integrates with ``HostnameAllowlist`` for destination provider lookup.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import structlog

from anonreq.mcp.parser import MCPParser, MCPToolCall, MCPToolResult

logger = structlog.get_logger()


@dataclass
class InspectionResult:
    """Result of MCP message inspection.

    Attributes:
        detected: Whether MCP content was detected.
        tool_calls: Extracted tool calls.
        tool_results: Extracted tool results.
        provider: Matched AI provider from hostname allowlist (if any).
        confidence: Inspection confidence.
    """

    detected: bool = False
    tool_calls: list[MCPToolCall] = field(default_factory=list)
    tool_results: list[MCPToolResult] = field(default_factory=list)
    provider: str | None = None
    confidence: float = 0.0


class MCPInspector:
    """Inspects HTTP requests and responses for MCP protocol content.

    Uses ``MCPParser`` to parse JSON-RPC 2.0 messages and extract tool
    calls and results. Integrates with ``HostnameAllowlist`` to identify
    the destination AI provider.

    Args:
        flow_analyzer: A ``FlowAnalyzer`` instance for AI traffic analysis.
        allowlist: A ``HostnameAllowlist`` instance for provider matching.
    """

    def __init__(self, flow_analyzer: Any, allowlist: Any) -> None:
        self._parser = MCPParser()
        self._flow_analyzer = flow_analyzer
        self._allowlist = allowlist

    def mcp_content_type_detected(self, content_type: str) -> bool:
        """Check if a Content-Type header indicates MCP protocol content.

        Returns ``True`` if the Content-Type explicitly references MCP
        (``x-mcp``, ``vnd.mcp``) or if it is ``application/json`` with
        JSON-RPC structure (heuristic — requires body inspection).

        Args:
            content_type: The Content-Type header value.

        Returns:
            ``True`` if the content type suggests MCP.
        """
        if not content_type:
            return False

        ct_lower = content_type.lower()

        # Explicit MCP content type
        if "x-mcp" in ct_lower or "vnd.mcp" in ct_lower:
            return True

        # application/json is ambiguous — needs body inspection
        if "application/json" in ct_lower:
            return False  # Body inspection needed

        return False

    async def inspect_request(self, request: Any) -> InspectionResult | None:
        """Inspect an HTTP request for MCP content.

        If the request body is JSON-RPC 2.0, parses it and extracts tool
        calls and results. Checks the destination against the hostname
        allowlist for provider identification.

        Args:
            request: A request-like object with ``body`` (awaitable or bytes),
                ``method``, ``url.path``, and ``headers``.

        Returns:
            ``InspectionResult`` if MCP content is detected, ``None`` otherwise.
        """
        # Get body bytes
        body: bytes | None = None
        if hasattr(request, "body") and callable(request.body):
            try:
                body = await request.body()
            except Exception:
                body = None
        elif hasattr(request, "_body"):
            body = request._body
        elif hasattr(request, "body") and isinstance(request.body, bytes):
            body = request.body

        if not body or len(body) < 10:
            return None

        # Check Content-Type
        headers = _get_headers_dict(request)
        content_type = headers.get("content-type", "")

        # MCP is always JSON
        if "application/json" not in content_type:
            return None

        # Check if it's an MCP message
        if not self._parser.is_mcp_message(body):
            return None

        # Parse MCP message
        try:
            message = self._parser.parse(body)
        except Exception as exc:
            logger.debug("MCP parse failed", error=str(exc))
            return None

        # Extract tool calls and results
        tool_calls = self._parser.extract_tool_calls(message)
        tool_results = self._parser.extract_tool_results(message)

        if not tool_calls and not tool_results:
            return None

        # Provider identification from hostname
        provider: str | None = None
        host = _get_target_host(request)
        if host and self._allowlist is not None:
            match = self._allowlist.match_hostname(host)
            if match:
                provider = match.provider

        # Calculate confidence
        confidence = 0.8
        if tool_calls:
            confidence = min(1.0, confidence + 0.1 * len(tool_calls))
        if provider:
            confidence = min(1.0, confidence + 0.1)

        return InspectionResult(
            detected=True,
            tool_calls=tool_calls,
            tool_results=tool_results,
            provider=provider,
            confidence=confidence,
        )

    async def inspect_response(
        self,
        response: Any,
        session_context: dict[str, Any],
    ) -> None:
        """Inspect an MCP response for suspicious tool results.

        Currently a placeholder for Phase 18 governance integration.
        Flags suspicious tool results and attaches inspection metadata
        for audit.

        Args:
            response: The HTTP response object.
            session_context: Session context dict for metadata attachment.
        """
        body: bytes | None = None
        if hasattr(response, "body") and callable(response.body):
            try:
                body = await response.body()
            except Exception:
                body = None
        elif hasattr(response, "_body"):
            body = response._body

        if not body or len(body) < 10:
            return

        # Parse and check if it's MCP
        if not self._parser.is_mcp_message(body):
            return

        try:
            message = self._parser.parse(body)
        except Exception:
            return

        tool_results = self._parser.extract_tool_results(message)
        if not tool_results:
            return

        # Flag suspicious results (large content, errors)
        suspicious = [
            tr for tr in tool_results
            if tr.is_error or (
                isinstance(tr.content, str) and len(tr.content) > 10000
            )
        ]

        if suspicious:
            session_context["mcp_suspicious_results"] = [
                {"name": tr.name, "is_error": tr.is_error}
                for tr in suspicious
            ]
            logger.info(
                "Suspicious MCP tool results detected",
                count=len(suspicious),
                names=[tr.name for tr in suspicious],
            )


def _get_headers_dict(request: Any) -> dict[str, str]:
    """Extract headers from a request-like object as lowercase dict."""
    headers = getattr(request, "headers", {})
    if hasattr(headers, "items"):
        return {k.lower(): str(v) for k, v in headers.items()}
    if isinstance(headers, dict):
        return {k.lower(): str(v) for k, v in headers.items()}
    return {}


def _get_target_host(request: Any) -> str | None:
    """Extract the target hostname from a request."""
    url = getattr(request, "url", None)
    if url is not None:
        host = getattr(url, "host", None)
        if host:
            return host
    # Try host header
    headers = _get_headers_dict(request)
    return headers.get("host", None)
