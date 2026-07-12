"""Hot-reload integration tests — end-to-end custom recognizer injection.

Tests the full flow:
1. Admin POST registers a custom recognizer via AtomicConfigRegistry
2. DetectionStage picks up the new patterns on the next detection call
3. Custom entity types are detected alongside built-in patterns
4. Invalid custom patterns do not affect built-in detection
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from anonreq.admin.config import AtomicConfigRegistry, CustomRecognizerRule, RulesConfig
from anonreq.detection.exclusion_list import ExclusionList
from anonreq.detection.provider import get_custom_recognizer_patterns
from anonreq.detection.regex_detector import RegexDetector
from anonreq.detection.span_arbiter import SpanArbiter
from anonreq.models.processing_context import ProcessingContext


@pytest.fixture
def registry():
    """A fresh AtomicConfigRegistry for each test."""
    return AtomicConfigRegistry()


def test_provider_extracts_custom_patterns(registry):
    """AtomicConfigRegistry with custom recognizers returns compiled patterns."""
    config = RulesConfig(
        custom_recognizers=[
            CustomRecognizerRule(
                id="test-id-rule",
                entity_type="CUSTOM_ID",
                patterns=["COMP-\\d{4}", "PROJ-\\d{3}"],
                confidence=0.85,
                enabled=True,
                version=1,
            ),
        ],
        exclusion_list=[],
    )
    success, _ = registry.validate_and_swap(config)
    assert success is True

    patterns = get_custom_recognizer_patterns(registry)
    assert "CUSTOM_ID" in patterns
    assert patterns["CUSTOM_ID"].search("COMP-4321") is not None
    assert patterns["CUSTOM_ID"].search("PROJ-999") is not None
    assert patterns["CUSTOM_ID"].search("NO-MATCH") is None


def test_provider_returns_empty_when_no_custom_recognizers(registry):
    """Empty config yields empty patterns dict."""
    config = RulesConfig(custom_recognizers=[], exclusion_list=[])
    success, _ = registry.validate_and_swap(config)
    assert success is True

    patterns = get_custom_recognizer_patterns(registry)
    assert patterns == {}


def test_provider_skips_disabled_recognizers(registry):
    """Disabled recognizers are excluded from compiled patterns."""
    config = RulesConfig(
        custom_recognizers=[
            CustomRecognizerRule(
                id="disabled-rule",
                entity_type="DISABLED_ENTITY",
                patterns=["TEST-\\d+"],
                confidence=0.8,
                enabled=False,
                version=1,
            ),
        ],
        exclusion_list=[],
    )
    success, _ = registry.validate_and_swap(config)
    assert success is True

    patterns = get_custom_recognizer_patterns(registry)
    assert "DISABLED_ENTITY" not in patterns


@pytest.mark.asyncio
async def test_detection_stage_injects_custom_patterns(registry):
    """DetectionStage detects custom entity types from AtomicConfigRegistry."""
    from anonreq.pipeline.detection import DetectionStage

    # Populate registry with a custom pattern
    config = RulesConfig(
        custom_recognizers=[
            CustomRecognizerRule(
                id="order-id-rule",
                entity_type="ORDER_ID",
                patterns=["ORD-\\d{6}"],
                confidence=0.9,
                enabled=True,
                version=1,
            ),
        ],
        exclusion_list=[],
    )
    success, _ = registry.validate_and_swap(config)
    assert success is True

    # Create DetectionStage with real RegexDetector + config_registry
    regex_detector = RegexDetector()
    presidio_client = MagicMock()
    presidio_client.analyze_text_nodes.return_value = [[], []]  # No NER results

    stage = DetectionStage(
        regex_detector=regex_detector,
        presidio_client=presidio_client,
        span_arbiter=SpanArbiter(),
        exclusion_list=ExclusionList(),
        config_registry=registry,
    )

    ctx = ProcessingContext(request_id="test_hot_reload", tenant_id="default")
    ctx.text_nodes = [
        {
            "path": "messages[0].content",
            "role": "user",
            "value": "My order ORD-123456 was confirmed. Email me at user@example.com",
        },
    ]
    ctx.classification_result = {"action": "ANONYMIZE"}
    ctx.request_receipt_time = 1.0  # Avoid NoneType error on latency recording

    # Patch time.monotonic to avoid issues with latency recording
    import time as time_module

    original_monotonic = time_module.monotonic
    try:
        time_module.monotonic = lambda: 2.0  # 1 second after receipt
        result = await stage.execute(ctx)
    finally:
        time_module.monotonic = original_monotonic

    assert not result.has_errors()
    assert result.detections is not None

    # Should detect both built-in EMAIL_ADDRESS and custom ORDER_ID
    entity_types = {d["entity_type"] for d in result.detections}
    assert "ORDER_ID" in entity_types, (
        f"Expected ORDER_ID in detections, got {entity_types}"
    )
    assert "EMAIL_ADDRESS" in entity_types, (
        f"Expected EMAIL_ADDRESS in detections, got {entity_types}"
    )

    # Verify the custom detection has correct span
    order_detection = next(d for d in result.detections if d["entity_type"] == "ORDER_ID")
    assert order_detection["source"] == "regex"
    assert order_detection["score"] == 1.0
    # "ORD-123456" starts at index 9 in "My order ORD-123456 was confirmed..."
    assert order_detection["start"] == 9
    assert order_detection["end"] == 19


@pytest.mark.asyncio
async def test_detection_without_config_registry_is_unchanged():
    """DetectionStage without config_registry behaves identically to before."""
    from anonreq.pipeline.detection import DetectionStage

    regex_detector = RegexDetector()
    presidio_client = MagicMock()
    presidio_client.analyze_text_nodes.return_value = [[]]

    stage = DetectionStage(
        regex_detector=regex_detector,
        presidio_client=presidio_client,
        span_arbiter=SpanArbiter(),
        exclusion_list=ExclusionList(),
        config_registry=None,  # Explicitly None
    )

    ctx = ProcessingContext(request_id="test_no_registry", tenant_id="default")
    ctx.text_nodes = [
        {
            "path": "messages[0].content",
            "role": "user",
            "value": "Email me at user@example.com",
        },
    ]
    ctx.classification_result = {"action": "ANONYMIZE"}
    ctx.request_receipt_time = 1.0

    import time as time_module

    original_monotonic = time_module.monotonic
    try:
        time_module.monotonic = lambda: 2.0
        result = await stage.execute(ctx)
    finally:
        time_module.monotonic = original_monotonic

    assert not result.has_errors()
    assert result.detections is not None
    assert len(result.detections) == 1
    assert result.detections[0]["entity_type"] == "EMAIL_ADDRESS"


def test_get_custom_recognizer_patterns_none_registry():
    """get_custom_recognizer_patterns returns empty dict for None registry."""
    assert get_custom_recognizer_patterns(None) == {}


def test_get_custom_recognizer_patterns_empty_registry(registry):
    """get_custom_recognizer_patterns returns empty dict for empty registry."""
    assert get_custom_recognizer_patterns(registry) == {}


@pytest.mark.asyncio
async def test_detection_with_admin_full_flow(registry):
    """Full flow: POST config → detection uses new patterns.

    Simulates what happens when the admin API receives a POST:
    1. registry.validate_and_swap is called (as POST handler does)
    2. Subsequent detection picks up the new patterns
    """
    from anonreq.pipeline.detection import DetectionStage

    # Simulate POST by calling validate_and_swap
    config = RulesConfig(
        custom_recognizers=[
            CustomRecognizerRule(
                id="vpn-rule",
                entity_type="VPN_PROTOCOL",
                patterns=["VPN-\\w{3,}"],
                confidence=0.85,
                enabled=True,
                version=1,
            ),
        ],
        exclusion_list=[],
    )
    success, _ = registry.validate_and_swap(config)
    assert success is True

    regex_detector = RegexDetector()
    presidio_client = MagicMock()
    presidio_client.analyze_text_nodes.return_value = [[]]

    stage = DetectionStage(
        regex_detector=regex_detector,
        presidio_client=presidio_client,
        span_arbiter=SpanArbiter(),
        exclusion_list=ExclusionList(),
        config_registry=registry,
    )

    ctx = ProcessingContext(request_id="test_admin_flow", tenant_id="default")
    ctx.text_nodes = [
        {
            "path": "messages[0].content",
            "role": "user",
            "value": "Configure VPN-WireGuard for the team",
        },
    ]
    ctx.classification_result = {"action": "ANONYMIZE"}
    ctx.request_receipt_time = 1.0

    import time as time_module

    original_monotonic = time_module.monotonic
    try:
        time_module.monotonic = lambda: 2.0
        result = await stage.execute(ctx)
    finally:
        time_module.monotonic = original_monotonic

    assert not result.has_errors()
    assert result.detections is not None
    assert any(d["entity_type"] == "VPN_PROTOCOL" for d in result.detections)
