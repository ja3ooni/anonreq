"""Tests for pre-flight startup checks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.fixture
def cache_manager():
    return MagicMock()


class TestStartupChecks:
    """Tests for run_startup_checks."""

    @patch("anonreq.startup_checks.check_cache_health", new_callable=AsyncMock)
    @patch("anonreq.startup_checks.check_presidio", new_callable=AsyncMock)
    @patch("anonreq.startup_checks.check_presidio_language", new_callable=AsyncMock)
    async def test_startup_checks_success(
        self,
        mock_language,
        mock_presidio,
        mock_cache_health,
        test_settings,
        cache_manager,
    ):
        """run_startup_checks succeeds when cache and Presidio are healthy."""
        from anonreq.startup_checks import run_startup_checks

        mock_cache_health.return_value = {
            "reachable": True,
            "persistence_disabled": True,
            "healthy": True,
            "status": "healthy",
        }
        mock_presidio.return_value = True
        mock_language.return_value = True

        await run_startup_checks(test_settings, cache_manager)

        mock_cache_health.assert_awaited_once_with(cache_manager)
        mock_presidio.assert_awaited_once_with(test_settings.PRESIDIO_URL)
        mock_language.assert_awaited_once_with(test_settings.PRESIDIO_URL, "en")

    @patch("anonreq.startup_checks.check_cache_health", new_callable=AsyncMock)
    @patch("anonreq.startup_checks.check_presidio", new_callable=AsyncMock)
    async def test_startup_checks_raises_when_cache_unhealthy(
        self,
        mock_presidio,
        mock_cache_health,
        test_settings,
        cache_manager,
    ):
        """run_startup_checks raises when cache health fails."""
        from anonreq.exceptions import DependencyUnavailableError
        from anonreq.startup_checks import run_startup_checks

        mock_cache_health.return_value = {
            "reachable": False,
            "persistence_disabled": False,
            "healthy": False,
            "status": "unhealthy",
        }
        mock_presidio.return_value = True

        with pytest.raises(DependencyUnavailableError) as exc_info:
            await run_startup_checks(test_settings, cache_manager)

        assert exc_info.value.dependency == "valkey"
        mock_cache_health.assert_awaited_once_with(cache_manager)
        mock_presidio.assert_not_awaited()

    @patch("anonreq.startup_checks.check_cache_health", new_callable=AsyncMock)
    @patch("anonreq.startup_checks.check_presidio", new_callable=AsyncMock)
    async def test_startup_checks_raises_when_presidio_unreachable(
        self,
        mock_presidio,
        mock_cache_health,
        test_settings,
        cache_manager,
        monkeypatch,
    ):
        """run_startup_checks raises when Presidio is unreachable."""
        from anonreq.exceptions import DependencyUnavailableError
        from anonreq.startup_checks import run_startup_checks

        mock_cache_health.return_value = {
            "reachable": True,
            "persistence_disabled": True,
            "healthy": True,
            "status": "healthy",
        }
        mock_presidio.return_value = False
        monkeypatch.setattr("asyncio.sleep", AsyncMock(return_value=None))

        with pytest.raises(DependencyUnavailableError) as exc_info:
            await run_startup_checks(test_settings, cache_manager)

        assert exc_info.value.dependency == "presidio"
        mock_cache_health.assert_awaited_once_with(cache_manager)
        assert mock_presidio.await_count == 5
        mock_presidio.assert_awaited_with(test_settings.PRESIDIO_URL)

    @patch("anonreq.startup_checks.check_cache_health", new_callable=AsyncMock)
    @patch("anonreq.startup_checks.check_presidio", new_callable=AsyncMock)
    @patch("anonreq.startup_checks.check_presidio_language", new_callable=AsyncMock)
    async def test_startup_checks_logs_results(
        self,
        mock_language,
        mock_presidio,
        mock_cache_health,
        test_settings,
        cache_manager,
        capsys,
    ):
        """run_startup_checks logs check results."""
        from anonreq.logging_config import setup_logging
        from anonreq.startup_checks import run_startup_checks

        mock_cache_health.return_value = {
            "reachable": True,
            "persistence_disabled": True,
            "healthy": True,
            "status": "healthy",
        }
        mock_presidio.return_value = True
        mock_language.return_value = True

        setup_logging(level="INFO")
        await run_startup_checks(test_settings, cache_manager)

        captured = capsys.readouterr()
        assert "cache" in captured.err.lower() or "cache" in captured.out.lower()

    @patch("anonreq.startup_checks.check_cache_health", new_callable=AsyncMock)
    @patch("anonreq.startup_checks.check_presidio", new_callable=AsyncMock)
    @patch("anonreq.startup_checks.check_presidio_language", new_callable=AsyncMock)
    async def test_startup_refuses_when_configured_language_is_missing(
        self,
        mock_language,
        mock_presidio,
        mock_cache_health,
        cache_manager,
    ):
        """de is configured, but the analyzer cannot run it."""
        from anonreq.exceptions import DependencyUnavailableError
        from anonreq.startup_checks import run_startup_checks

        settings = Settings(
            API_KEY="a" * 32,
            VALKEY_URL="redis://localhost:6379/0",
            PRESIDIO_URL="http://localhost:5001",
            PRESIDIO_LANGUAGES="en,de",
        )
        mock_cache_health.return_value = {
            "reachable": True,
            "persistence_disabled": True,
            "healthy": True,
        }
        mock_presidio.return_value = True

        async def _supports(_url: str, language: str) -> bool:
            return language != "de"

        mock_language.side_effect = _supports

        with pytest.raises(DependencyUnavailableError) as exc_info:
            await run_startup_checks(settings, cache_manager)

        assert exc_info.value.dependency == "presidio"
        checked = [call.args[1] for call in mock_language.await_args_list]
        assert checked == ["en", "de"]
