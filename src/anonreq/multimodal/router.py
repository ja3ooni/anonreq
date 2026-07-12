"""LocalRouter — content-type based routing decisions for unsupported types.

Routes incoming payloads based on their MIME type to either:
- ``FORWARD`` — send to the LLM provider as-is (text types, known types)
- ``ROUTE_LOCAL`` — process locally instead of forwarding (binary, media)
- ``BLOCK`` — reject the payload entirely

Default rules classify all ``image/*``, ``audio/*``, ``video/*``,
``application/octet-stream``, ``application/pdf``, and
``application/xml`` as ``ROUTE_LOCAL``.  Custom rules can override
any type.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RouteDecisionType(StrEnum):
    """Possible routing outcomes."""

    FORWARD = "FORWARD"
    """Send the payload to the remote LLM provider."""

    ROUTE_LOCAL = "ROUTE_LOCAL"
    """Process the payload locally (on-prem / local inference)."""

    BLOCK = "BLOCK"
    """Reject the payload entirely."""


@dataclass
class RouteDecision:
    """Decision produced by :class:`LocalRouter.route`.

    Attributes:
        decision: The routing outcome.
        reason: Human-readable explanation of the decision.
        content_type: The content type that was evaluated.
    """

    decision: RouteDecisionType
    reason: str | None = None
    content_type: str = ""


# Default rule table: content-type prefix wildcard → decision
_DEFAULT_RULES: list[tuple[str, RouteDecisionType, str]] = [
    # Text types — always forward
    ("text/", RouteDecisionType.FORWARD, "Text content type"),
    ("application/json", RouteDecisionType.FORWARD, "JSON content type"),
    ("multipart/", RouteDecisionType.FORWARD, "Multipart content type"),
    ("application/x-www-form-urlencoded", RouteDecisionType.FORWARD, "Form content type"),
    # Binary / media types — route locally
    ("image/", RouteDecisionType.ROUTE_LOCAL, "Binary image content type"),
    ("audio/", RouteDecisionType.ROUTE_LOCAL, "Binary audio content type"),
    ("video/", RouteDecisionType.ROUTE_LOCAL, "Binary video content type"),
    ("application/octet-stream", RouteDecisionType.ROUTE_LOCAL, "Binary octet-stream content type"),
    ("application/pdf", RouteDecisionType.ROUTE_LOCAL, "PDF content type"),
    ("application/xml", RouteDecisionType.ROUTE_LOCAL, "XML content type"),
]

_DEFAULT_FALLBACK = RouteDecisionType.ROUTE_LOCAL
"""Fallback for completely unknown content types."""


class LocalRouter:
    """Routes payloads based on MIME type.

    Uses a prefix-matching strategy so that ``image/*`` catches all
    image subtypes.  Custom rules can override any type.

    Usage::

        router = LocalRouter()
        decision = router.route("image/png", b"binary data")
        # → RouteDecision(decision=ROUTE_LOCAL, reason="...", content_type="image/png")

        # With custom overrides:
        router = LocalRouter({"application/xml": "FORWARD"})
    """

    def __init__(
        self,
        config: dict[str, str] | None = None,
    ) -> None:
        """Initialize the router.

        Args:
            config: Optional dict of content_type → decision overrides.
                Values must be one of ``"FORWARD"``, ``"ROUTE_LOCAL"``,
                or ``"BLOCK"``.
        """
        self._rules: list[tuple[str, RouteDecisionType, str]] = list(_DEFAULT_RULES)
        self._exact_overrides: dict[str, RouteDecisionType] = {}

        if config:
            for ct, decision_str in config.items():
                try:
                    decision = RouteDecisionType(decision_str.upper())
                except ValueError:
                    continue
                self._exact_overrides[ct.lower()] = decision

    def route(
        self,
        content_type: str | None,
        _payload: bytes,
    ) -> RouteDecision:
        """Decide what to do with a payload of the given *content_type*.

        Args:
            content_type: The MIME type string (e.g. ``"image/png"``).
                ``None`` or empty is treated as ``"text/plain"``.
            payload: The raw payload bytes (used for potential content
                sniffing in the future).

        Returns:
            A :class:`RouteDecision` with the outcome.
        """
        if not content_type or not content_type.strip():
            return RouteDecision(
                decision=RouteDecisionType.FORWARD,
                reason="Missing content type, defaulting to FORWARD",
                content_type=content_type or "",
            )

        # Strip parameters (charset, boundary, etc.)
        raw_type = content_type.split(";")[0].strip().lower()

        # Check exact overrides first
        if raw_type in self._exact_overrides:
            decision = self._exact_overrides[raw_type]
            return RouteDecision(
                decision=decision,
                reason=f"Custom rule: {raw_type} → {decision.value}",
                content_type=raw_type,
            )

        # Prefix match against default rules
        for prefix, decision, reason in self._rules:
            if raw_type.startswith(prefix):
                return RouteDecision(
                    decision=decision,
                    reason=reason,
                    content_type=raw_type,
                )

        # Fallback for completely unknown types
        return RouteDecision(
            decision=_DEFAULT_FALLBACK,
            reason=f"Unknown content type '{raw_type}', defaulting to ROUTE_LOCAL",
            content_type=raw_type,
        )
