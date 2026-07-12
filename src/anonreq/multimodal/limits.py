from __future__ import annotations

from pydantic import BaseModel

from anonreq.multimodal.models import ContentType


class PayloadLimits(BaseModel):
    json_max_size_mb: int = 5
    multipart_max_size_mb: int = 50
    max_depth: int = 50
    max_parts: int = 100


class LimitCheckResult(BaseModel):
    passed: bool
    action: str = "ANONYMIZE"
    reason: str | None = None
    limit_type: str | None = None
    current_value: int | None = None
    limit_value: int | None = None


def validate_payload_limits(
    content_type: ContentType,
    body: bytes | str,
    limits: PayloadLimits,
    depth: int = 0,
) -> LimitCheckResult:
    body_bytes = body if isinstance(body, bytes) else body.encode("utf-8")
    body_size = len(body_bytes)

    if content_type == ContentType.APPLICATION_JSON:
        max_json_bytes = limits.json_max_size_mb * 1024 * 1024
        if body_size > max_json_bytes:
            return LimitCheckResult(
                passed=False,
                action="BLOCK",
                reason=f"JSON payload exceeds {limits.json_max_size_mb}MB limit",
                limit_type="size",
                current_value=body_size,
                limit_value=max_json_bytes,
            )

        if depth > limits.max_depth:
            return LimitCheckResult(
                passed=False,
                action="ROUTE_LOCAL",
                reason=f"JSON depth {depth} exceeds max depth {limits.max_depth}",
                limit_type="depth",
                current_value=depth,
                limit_value=limits.max_depth,
            )

    elif content_type == ContentType.MULTIPART_FORM_DATA:
        max_mp_bytes = limits.multipart_max_size_mb * 1024 * 1024
        if body_size > max_mp_bytes:
            return LimitCheckResult(
                passed=False,
                action="BLOCK",
                reason=f"Multipart payload exceeds {limits.multipart_max_size_mb}MB limit",
                limit_type="size",
                current_value=body_size,
                limit_value=max_mp_bytes,
            )

    return LimitCheckResult(passed=True)
