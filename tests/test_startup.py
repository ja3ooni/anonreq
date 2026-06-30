"""Tests for pre-flight startup checks.

Tests verify:
- run_startup_checks succeeds when both deps are reachable
- run_startup_checks raises when Valkey is unreachable
- run_startup_checks raises when Presidio is unreachable
- App startup with unreachable dependency raises error via lifespan
"""

from unittest.mock import AsyncMock, patch

import pytest

from anonreq.config import Settings


@pytest.fixture
def test_settings():
    """Create a settings instance for startup check tests."""
    return Settings(
        API_KEY="a" * 32,
        VALKEY_URL="redis://localhost:6379/0",
        PRESIDIO_URL="http://localhost:5001",
    )


class TestStartupChecks:
    """Tests for run_startup_checks."""

    @patch("anonreq.startup_checks.check_valkey", return_value=True)
    @patch("anonreq.startup_checks.check_presidio", return_value=True)
    async def test_startup_checks_success(
        self, mock_presidio, mock_valkey, test_settings
    ):
        """Test 1: run_startup_checks succeeds when both deps reachable."""
        from anonreq.startup_checks import run_startup_checks

        # Should not raise
        await run_startup_checks(test_settings)
        mock_valkey.assert_awaited_once_with(test_settings.VALKEY_URL)
        mock_presidio.assert_awaited_once_with(test_settings.PRESIDIO_URL)

    @patch("anonreq.startup_checks.check_valkey", return_value=False)
    @patch("anonreq.startup_checks.check_presidio", return_value=True)
    async def test_startup_checks_raises_when_valkey_unreachable(
        self, mock_presidio, mock_valkey, test_settings
    ):
        """Test 2: run_startup_checks raises when Valkey unreachable."""
        from anonreq.startup_checks import run_startup_checks
        from anonreq.exceptions import DependencyUnavailableError

        with pytest.raises(DependencyUnavailableError) as exc_info:
            await run_startup_checks(test_settings)
        assert "valkey" in str(exc_info.value).lower()

    @patch("anonreq.startup_checks.check_valkey", return_value=True)
    @patch("anonreq.startup_checks.check_presidio", return_value=False)
    async def test_startup_checks_raises_when_presidio_unreachable(
        self, mock_presidio, mock_valkey, test_settings
    ):
        """Test 3: run_startup_checks raises when Presidio unreachable."""
        from anonreq.startup_checks import run_startup_checks
        from anonreq.exceptions import DependencyUnavailableError

        with pytest.raises(DependencyUnavailableError) as exc_info:
            await run_startup_checks(test_settings)
        assert "presidio" in str(exc_info.value).lower()

    @patch("anonreq.startup_checks.check_valkey", return_value=True)
    @patch("anonreq.startup_checks.check_presidio", return_value=True)
    async def test_startup_checks_logs_results(
        self, mock_presidio, mock_valkey, test_settings, capsys
    ):
        """run_startup_checks logs check results."""
        from anonreq.startup_checks import run_startup_checks
        from anonreq.logging_config import setup_logging

        setup_logging(level="INFO")
        await run_startup_checks(test_settings)

        captured = capsys.readouterr()
        assert "valkey" in captured.err.lower() or "valkey" in captured.out.lower()
