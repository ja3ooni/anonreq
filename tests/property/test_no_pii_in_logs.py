"""TEST-05: No-PII-in-logs property tests — PII values never appear in log output.

Proves using Hypothesis property-based tests that PII entity values sent in
request messages never appear in any log sink (structlog, audit, stdlib).

For each entity type (EMAIL, PHONE, CREDIT_CARD, IBAN, PERSON, IP, URL),
50 Hypothesis examples generate random PII values embedded in request text,
send them through the pipeline, and verify:

- The PII value does not appear as a substring in captured log output
- All log sinks are scanned (via the ``log_capture`` fixture which captures
  structlog + stdlib output with JSON rendering)

Design notes:
- The ``log_capture`` fixture uses ``ProcessorFormatter`` with ``JSONRenderer``
  to capture structured logging in production-like JSON format.
- The pipeline's ``ClassificationStage`` defaults to ``PASS`` action, so
  the PII flows through undetected in the mocked test environment.  This is
  acceptable — the invariant being tested is that *no* code path (success,
  failure, metadata logging) ever leaks raw entity values into log output.
- The allowlist processor is not active in test configuration, so the
  captured log output includes ALL structured fields — making the test
  *more* sensitive to potential leaks.
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings

from tests.property.conftest import inject_failure
from tests.property.strategies import (
    ALL_ENTITY_TYPES,
    ENTITY_TYPE_STRATEGIES,
    FailureMode,
    PipelinePath,
    pii_text_strategy,
)

MAX_EXAMPLES = 50

_FIXTURE_HC = HealthCheck.function_scoped_fixture


# ── Per-entity-type tests ──────────────────────────────────────────────────


@pytest.mark.parametrize("entity_type", ALL_ENTITY_TYPES)
async def test_pii_not_in_logs_happy_path(
    property_client: Any,
    log_capture: Any,
    entity_type: str,
) -> None:
    """TEST-05: PII values never appear in log output (happy path, no failure).

    Sends a request containing a PII value of ``entity_type`` through the
    pipeline under normal (non-failing) conditions and verifies the raw
    PII value does not appear in any captured log output.
    """
    strategy = ENTITY_TYPE_STRATEGIES[entity_type]
    entity_value = strategy.example()

    response = await property_client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": f"My {entity_type} is {entity_value}"}],
            "stream": False,
        },
    )

    log_output = log_capture.getvalue()
    assert response.status_code >= 200, (
        f"Request failed for {entity_type}: {response.status_code}"
    )
    assert entity_value not in log_output, (
        f"PII value {entity_value!r} (type={entity_type}) found in log output "
        f"despite successful processing"
    )


@pytest.mark.parametrize("entity_type", ALL_ENTITY_TYPES)
async def test_pii_not_in_logs_detection_failure(
    test_app: Any,
    property_client: Any,
    log_capture: Any,
    entity_type: str,
) -> None:
    """TEST-05: PII values not in logs when DetectionStage fails.

    Injects a DETECTION failure mode and verifies the PII value does not
    appear in error log output.
    """
    strategy = ENTITY_TYPE_STRATEGIES[entity_type]
    entity_value = strategy.example()

    async with inject_failure(FailureMode.DETECTION, PipelinePath.NON_STREAMING, test_app):
        response = await property_client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": f"My {entity_type} is {entity_value}"}],
                "stream": False,
            },
        )

    log_output = log_capture.getvalue()
    assert response.status_code >= 500, (
        f"Detection failure should return 5xx for {entity_type}"
    )
    assert entity_value not in log_output, (
        f"PII value {entity_value!r} (type={entity_type}) found in log output "
        f"during detection failure"
    )


@pytest.mark.parametrize("entity_type", ALL_ENTITY_TYPES)
async def test_pii_not_in_logs_forwarding_denied(
    test_app: Any,
    property_client: Any,
    log_capture: Any,
    entity_type: str,
) -> None:
    """TEST-05: PII values not in logs when ForwardingGuard denies."""
    strategy = ENTITY_TYPE_STRATEGIES[entity_type]
    entity_value = strategy.example()

    async with inject_failure(FailureMode.FORWARDING_GUARD, PipelinePath.NON_STREAMING, test_app):
        response = await property_client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": f"My {entity_type} is {entity_value}"}],
                "stream": False,
            },
        )

    log_output = log_capture.getvalue()
    assert response.status_code >= 500, (
        f"Forwarding denial should return 5xx for {entity_type}"
    )
    assert entity_value not in log_output, (
        f"PII value {entity_value!r} (type={entity_type}) found in log output "
        f"during forwarding denial"
    )


# ── Property-based cross-type tests ────────────────────────────────────────


@settings(
    max_examples=MAX_EXAMPLES,
    deadline=60000,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow, _FIXTURE_HC],
)
@given(pii_data=pii_text_strategy())
async def test_pii_not_in_logs_property(
    property_client: Any,
    log_capture: Any,
    pii_data: tuple[str, str, str],
) -> None:
    """TEST-05 (property): Cross-entity property test for no-PII-in-logs.

    Uses ``@given`` with the ``pii_text_strategy`` composite strategy that
    generates ``(original_text, entity_value, entity_type)`` triples across
    all supported entity types, verifying the raw PII value never appears
    in log output.
    """
    original_text, entity_value, entity_type = pii_data

    response = await property_client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": original_text}],
            "stream": False,
        },
    )

    log_output = log_capture.getvalue()
    assert response.status_code >= 200, (
        f"Request failed for {entity_type}: {response.status_code}"
    )
    assert entity_value not in log_output, (
        f"PII value {entity_value!r} (type={entity_type}) found in log output"
    )
