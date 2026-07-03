from __future__ import annotations

from anonreq.multimodal.limits import (
    LimitCheckResult,
    PayloadLimits,
    validate_payload_limits,
)
from anonreq.multimodal.models import ContentType


class TestPayloadLimits:
    def test_default_values(self):
        limits = PayloadLimits()
        assert limits.json_max_size_mb == 5
        assert limits.multipart_max_size_mb == 50
        assert limits.max_depth == 50
        assert limits.max_parts == 100

    def test_custom_values(self):
        limits = PayloadLimits(json_max_size_mb=10, max_depth=25)
        assert limits.json_max_size_mb == 10
        assert limits.max_depth == 25


class TestLimitCheckResult:
    def test_passed_result(self):
        r = LimitCheckResult(passed=True)
        assert r.passed is True
        assert r.action == "ANONYMIZE"
        assert r.reason is None

    def test_failed_result(self):
        r = LimitCheckResult(
            passed=False,
            action="BLOCK",
            reason="Payload exceeds size limit",
            limit_type="size",
            current_value=6000000,
            limit_value=5000000,
        )
        assert r.passed is False
        assert r.action == "BLOCK"
        assert r.reason is not None


class TestValidatePayloadLimits:
    def test_under_size_limit_passes(self):
        body = b"x" * 100
        result = validate_payload_limits(
            ContentType.APPLICATION_JSON, body, PayloadLimits(json_max_size_mb=5)
        )
        assert result.passed is True

    def test_exceeding_json_size_blocks(self):
        body = b"x" * (6 * 1024 * 1024)
        result = validate_payload_limits(
            ContentType.APPLICATION_JSON, body, PayloadLimits(json_max_size_mb=5)
        )
        assert result.passed is False
        assert result.action == "BLOCK"
        assert result.limit_type == "size"

    def test_exceeding_multipart_size_blocks(self):
        body = b"x" * (51 * 1024 * 1024)
        result = validate_payload_limits(
            ContentType.MULTIPART_FORM_DATA,
            body,
            PayloadLimits(multipart_max_size_mb=50),
        )
        assert result.passed is False
        assert result.action == "BLOCK"

    def test_exceeding_depth_returns_route_local(self):
        result = validate_payload_limits(
            ContentType.APPLICATION_JSON,
            b"{}",
            PayloadLimits(max_depth=50),
            depth=60,
        )
        assert result.passed is False
        assert result.action == "ROUTE_LOCAL"
        assert result.limit_type == "depth"

    def test_zero_byte_payload_passes(self):
        result = validate_payload_limits(
            ContentType.TEXT_PLAIN, b"", PayloadLimits()
        )
        assert result.passed is True

    def test_depth_on_non_json_ignored(self):
        result = validate_payload_limits(
            ContentType.TEXT_PLAIN,
            b"hello",
            PayloadLimits(max_depth=50),
            depth=100,
        )
        assert result.passed is True

    def test_json_size_at_limit_passes(self):
        body = b"x" * (5 * 1024 * 1024)
        result = validate_payload_limits(
            ContentType.APPLICATION_JSON, body, PayloadLimits(json_max_size_mb=5)
        )
        assert result.passed is True

    def test_unknown_type_size_limit_not_applied(self):
        body = b"x" * (100 * 1024 * 1024)
        result = validate_payload_limits(
            ContentType.UNKNOWN, body, PayloadLimits()
        )
        assert result.passed is True

    def test_structured_result_on_failure(self):
        body = b"x" * (10 * 1024 * 1024)
        result = validate_payload_limits(
            ContentType.APPLICATION_JSON, body, PayloadLimits(json_max_size_mb=5)
        )
        assert result.reason is not None
        assert result.current_value is not None
        assert result.limit_value is not None
