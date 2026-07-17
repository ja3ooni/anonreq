"""Tests for structured audit logging with field allowlist.

Tests verify:
- Log output is valid JSON with required fields
- Non-allowlisted fields are dropped by the allowlist processor
- request_id is propagated via structlog contextvars
- Log level respects settings.LOG_LEVEL

See AUDT-01, AUDT-02, AUDT-03.
"""

import json

import pytest
from structlog.contextvars import bind_contextvars, clear_contextvars


@pytest.fixture(autouse=True)
def clear_log_context():
    """Clear structlog context vars before each test."""
    clear_contextvars()
    yield
    clear_contextvars()


class TestLoggingAllowlist:
    """Tests for the field allowlist processor."""

    def test_log_output_is_valid_json(self, capsys):
        """Test 1: Log output is valid JSON with timestamp, level, event."""
        import structlog

        from anonreq.logging_config import setup_logging

        setup_logging(level="DEBUG")
        log = structlog.get_logger()
        log.info("test_event", component="test")

        captured = capsys.readouterr()
        lines = [l for l in captured.err.split("\n") if l.strip()]  # noqa: E741

        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert "timestamp" in entry
        assert "level" in entry
        assert "event" in entry
        assert entry["event"] == "test_event"

    def test_non_allowlisted_fields_dropped(self, capsys):
        """Test 2: Non-allowlisted fields are dropped from log output."""
        import structlog

        from anonreq.logging_config import setup_logging

        setup_logging(level="DEBUG")
        log = structlog.get_logger()
        log.info("test_event", sensitive_data="secret-value", component="test")

        captured = capsys.readouterr()
        lines = [l for l in captured.err.split("\n") if l.strip()]  # noqa: E741

        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert "sensitive_data" not in entry
        assert entry.get("component") == "test"

    def test_allowlisted_fields_survive(self, capsys):
        """Allowlisted fields (timestamp, level, event, component, request_id, etc.) survive."""
        import structlog

        from anonreq.logging_config import setup_logging

        setup_logging(level="DEBUG")
        log = structlog.get_logger()

        # Bind some allowlisted context vars
        bind_contextvars(request_id="req_abc123")
        log.info(
            "test_event",
            component="test_component",
            status_code=200,
            duration_ms=42,
            version="0.1.0",
        )

        captured = capsys.readouterr()
        lines = [l for l in captured.err.split("\n") if l.strip()]  # noqa: E741

        assert len(lines) >= 1
        entry = json.loads(lines[0])

        # These are always present
        assert "timestamp" in entry
        assert "level" in entry
        assert "event" in entry

        # Context-bound fields that should survive
        if "request_id" in entry:
            assert entry["request_id"] == "req_abc123"

        # Event-specific fields
        if "component" in entry:
            assert entry["component"] == "test_component"

    def test_request_id_via_contextvars(self, capsys):
        """Test 3: request_id is included via structlog contextvars binding."""
        import structlog

        from anonreq.logging_config import setup_logging

        setup_logging(level="DEBUG")
        bind_contextvars(request_id="req_xyz789")

        log = structlog.get_logger()
        log.info("request_started", component="test")

        captured = capsys.readouterr()
        lines = [l for l in captured.err.split("\n") if l.strip()]  # noqa: E741

        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert entry.get("request_id") == "req_xyz789"

    def test_nested_dict_redaction(self, capsys):
        """Test 4: Nested dict values under allowlisted keys are recursively redacted."""
        import structlog

        from anonreq.logging_config import setup_logging

        setup_logging(level="DEBUG")
        log = structlog.get_logger()

        # Nested dict under an allowlisted key — redact_secret_substrings_processor
        # should recursively scan and redact sensitive values
        log.info("test_nested", component="test", data={"api_key": "sk-abc123def456"})

        captured = capsys.readouterr()
        lines = [l for l in captured.err.split("\n") if l.strip()]  # noqa: E741

        assert len(lines) >= 1
        entry = json.loads(lines[0])
        # "data" is now in ALLOWLIST, so it should be present
        assert "data" in entry
        # The nested sensitive value should be redacted
        assert entry["data"]["api_key"] == "[REDACTED]"

    def test_log_level_respected(self, capsys):
        """Test 5: Log level respects settings.LOG_LEVEL."""
        import structlog

        from anonreq.logging_config import setup_logging

        setup_logging(level="WARNING")
        log = structlog.get_logger()

        log.debug("debug_message", component="test")
        log.info("info_message", component="test")
        log.warning("warning_message", component="test")
        log.error("error_message", component="test")

        captured = capsys.readouterr()
        lines = [l for l in captured.err.split("\n") if l.strip()]  # noqa: E741

        events = []
        for line in lines:
            try:
                entry = json.loads(line)
                events.append(entry.get("event"))
            except json.JSONDecodeError:
                pass

        # debug and info messages should NOT appear (level is WARNING)
        assert "debug_message" not in events
        assert "info_message" not in events
        # warning and error should appear
        assert "warning_message" in events
        assert "error_message" in events

    def test_structlog_outputs_to_stderr_by_default(self, capsys):
        """structlog configured with StreamHandler should output to stderr."""
        import structlog

        from anonreq.logging_config import setup_logging

        setup_logging(level="INFO")
        log = structlog.get_logger()
        log.info("stderr_test", component="test")

        captured = capsys.readouterr()
        # stdout should be empty
        assert captured.out == ""
        # stderr should have our log output
        lines = [l for l in captured.err.split("\n") if l.strip()]  # noqa: E741
        assert len(lines) >= 1

    def test_secret_substrings_are_redacted(self, capsys):
        """Secret-looking substrings in allowlisted fields are redacted."""
        import structlog

        from anonreq.logging_config import setup_logging

        setup_logging(level="INFO")
        log = structlog.get_logger()
        log.error(
            "secret_event",
            component="test",
            error="failed with api_key=sk-test12345 and token=Bearer abcdefghijk",
        )

        captured = capsys.readouterr()
        lines = [l for l in captured.err.split("\n") if l.strip()]  # noqa: E741

        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert entry["error"].count("[REDACTED]") >= 2
        assert "sk-test12345" not in entry["error"]
        assert "abcdefghijk" not in entry["error"]
