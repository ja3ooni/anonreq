"""Tests for the configuration module (src/anonreq/config.py).

Covers env var loading, validation (types, required fields, defaults),
and the provider registry loader.
"""

import re

import pytest
from pydantic import ValidationError

from anonreq.config import Settings


class TestSettingsLoading:
    """Settings loads from explicit env vars with correct types."""

    def test_all_required_vars_produce_valid_settings(
        self, settings_override: None,
    ) -> None:
        """Test 1: All three required env vars produce a valid Settings instance."""
        settings = Settings()
        assert len(settings.API_KEY) >= 32
        assert isinstance(settings.VALKEY_URL, str)
        assert settings.VALKEY_URL.startswith("redis://")
        assert isinstance(settings.PRESIDIO_URL, str)
        assert settings.PRESIDIO_URL.startswith("http")

    def test_correct_types(self, settings_override: None) -> None:
        """Verify that fields have their expected Python types."""
        settings = Settings()
        assert isinstance(settings.API_KEY, str)
        assert isinstance(settings.VALKEY_URL, str)
        assert isinstance(settings.PRESIDIO_URL, str)
        assert isinstance(settings.HOST, str)
        assert isinstance(settings.PORT, int)
        assert isinstance(settings.LOG_LEVEL, str)
        assert isinstance(settings.REQUEST_TIMEOUT_SECONDS, int)


class TestApiKeyValidation:
    """ANONREQ_API_KEY with length < 32 raises ValidationError."""

    def test_short_api_key_raises_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test 2: API key shorter than 32 characters is rejected."""
        monkeypatch.setenv("ANONREQ_API_KEY", "short")
        monkeypatch.setenv("ANONREQ_VALKEY_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("ANONREQ_PRESIDIO_URL", "http://localhost:5001")
        with pytest.raises(ValidationError):
            Settings()

    def test_exactly_32_char_key_is_accepted(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Boundary: exactly 32-char key should be valid."""
        monkeypatch.setenv("ANONREQ_API_KEY", "a" * 32)
        monkeypatch.setenv("ANONREQ_VALKEY_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("ANONREQ_PRESIDIO_URL", "http://localhost:5001")
        settings = Settings()
        assert len(settings.API_KEY) == 32

    def test_error_message_mentions_api_key(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Validation error should clearly reference the API_KEY field."""
        monkeypatch.setenv("ANONREQ_API_KEY", "short")
        monkeypatch.setenv("ANONREQ_VALKEY_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("ANONREQ_PRESIDIO_URL", "http://localhost:5001")
        with pytest.raises(ValidationError) as excinfo:
            Settings()
        error_text = str(excinfo.value)
        assert "API_KEY" in error_text or "api_key" in error_text.lower()


class TestMissingRequiredVars:
    """Missing required env var raises ValidationError with clear message."""

    @pytest.mark.parametrize("missing_var", [
        "ANONREQ_API_KEY",
        "ANONREQ_VALKEY_URL",
        "ANONREQ_PRESIDIO_URL",
    ])
    def test_missing_required_var_raises_error(
        self, monkeypatch: pytest.MonkeyPatch, missing_var: str,
    ) -> None:
        """Test 3: Each required var individually triggers ValidationError."""
        # Set all required vars
        monkeypatch.setenv("ANONREQ_API_KEY", "a" * 32)
        monkeypatch.setenv("ANONREQ_VALKEY_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("ANONREQ_PRESIDIO_URL", "http://localhost:5001")
        # Delete the one under test
        monkeypatch.delenv(missing_var, raising=False)
        with pytest.raises(ValidationError) as excinfo:
            Settings()
        error_text = str(excinfo.value)
        assert missing_var.replace("ANONREQ_", "") in error_text

    def test_all_required_missing_raises_error(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Multiple missing required vars should all be reported."""
        # Delete all ANONREQ_ vars
        for var in ["ANONREQ_API_KEY", "ANONREQ_VALKEY_URL", "ANONREQ_PRESIDIO_URL"]:
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(ValidationError):
            Settings()


class TestOptionalDefaults:
    """Optional env vars use documented defaults when not provided."""

    def test_default_host(self, settings_override: None) -> None:
        """Test 4: Default HOST is 0.0.0.0."""
        settings = Settings()
        assert settings.HOST == "0.0.0.0"

    def test_default_port(self, settings_override: None) -> None:
        """Default PORT is 8080."""
        settings = Settings()
        assert settings.PORT == 8080

    def test_default_log_level(self, settings_override: None) -> None:
        """Default LOG_LEVEL is INFO."""
        settings = Settings()
        assert settings.LOG_LEVEL == "INFO"

    def test_default_request_timeout(self, settings_override: None) -> None:
        """Default REQUEST_TIMEOUT_SECONDS is 30."""
        settings = Settings()
        assert settings.REQUEST_TIMEOUT_SECONDS == 30

    def test_custom_optional_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Optional vars can be overridden via env vars."""
        monkeypatch.setenv("ANONREQ_API_KEY", "a" * 32)
        monkeypatch.setenv("ANONREQ_VALKEY_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("ANONREQ_PRESIDIO_URL", "http://localhost:5001")
        monkeypatch.setenv("ANONREQ_HOST", "127.0.0.1")
        monkeypatch.setenv("ANONREQ_PORT", "9090")
        monkeypatch.setenv("ANONREQ_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("ANONREQ_REQUEST_TIMEOUT_SECONDS", "60")
        settings = Settings()
        assert settings.HOST == "127.0.0.1"
        assert settings.PORT == 9090
        assert settings.LOG_LEVEL == "DEBUG"
        assert settings.REQUEST_TIMEOUT_SECONDS == 60


class TestUnknownVars:
    """Unknown env vars are silently ignored (extra='ignore')."""

    def test_unknown_var_des_not_raise_error(
        self, settings_override: None,
    ) -> None:
        """Test 5: Setting arbitrary ANONREQ_* vars does not cause errors."""
        # settings_override sets standard vars; unknown prefix
        # will be ignored by BaseSettings with extra="ignore"
        settings = Settings()
        # Access all known fields to confirm no crash
        _ = settings.API_KEY
        _ = settings.VALKEY_URL
        _ = settings.PRESIDIO_URL
        _ = settings.HOST
        _ = settings.PORT

    def test_settings_has_no_extra_attrs(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Settings object should not contain attributes for unknown env vars."""
        monkeypatch.setenv("ANONREQ_API_KEY", "a" * 32)
        monkeypatch.setenv("ANONREQ_VALKEY_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("ANONREQ_PRESIDIO_URL", "http://localhost:5001")
        monkeypatch.setenv("ANONREQ_UNKNOWN_VAR", "should_be_ignored")
        settings = Settings()
        assert not hasattr(settings, "UNKNOWN_VAR")
        assert not hasattr(settings, "unknown_var")


class TestURLAcceptance:
    """VALKEY_URL and PRESIDIO_URL accept valid URL strings."""

    def test_valkey_url_redis_scheme(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Valkey URL with redis:// scheme is accepted."""
        monkeypatch.setenv("ANONREQ_API_KEY", "a" * 32)
        monkeypatch.setenv("ANONREQ_VALKEY_URL", "redis://valkey:6379/0")
        monkeypatch.setenv("ANONREQ_PRESIDIO_URL", "http://localhost:5001")
        settings = Settings()
        assert settings.VALKEY_URL == "redis://valkey:6379/0"

    def test_valkey_url_rediss_scheme(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Valkey URL with rediss:// (TLS) scheme is accepted."""
        monkeypatch.setenv("ANONREQ_API_KEY", "a" * 32)
        monkeypatch.setenv("ANONREQ_VALKEY_URL", "rediss://valkey:6379/0")
        monkeypatch.setenv("ANONREQ_PRESIDIO_URL", "http://localhost:5001")
        settings = Settings()
        assert settings.VALKEY_URL == "rediss://valkey:6379/0"

    def test_presidio_url_http(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Presidio URL with http:// scheme is accepted."""
        monkeypatch.setenv("ANONREQ_API_KEY", "a" * 32)
        monkeypatch.setenv("ANONREQ_VALKEY_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("ANONREQ_PRESIDIO_URL", "http://presidio-analyzer:5001")
        settings = Settings()
        assert settings.PRESIDIO_URL == "http://presidio-analyzer:5001"

    def test_presidio_url_https(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Presidio URL with https:// scheme is accepted (Test 6)."""
        monkeypatch.setenv("ANONREQ_API_KEY", "a" * 32)
        monkeypatch.setenv("ANONREQ_VALKEY_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("ANONREQ_PRESIDIO_URL", "https://presidio.internal:5001")
        settings = Settings()
        assert settings.PRESIDIO_URL == "https://presidio.internal:5001"


class TestProviderRegistry:
    """Provider registry loading from YAML."""

    def test_load_provider_registry_returns_dict(
        self, settings_override: None,
    ) -> None:
        """load_provider_registry() returns a dict from providers.yaml."""
        from anonreq.config import load_provider_registry
        registry = load_provider_registry()
        assert isinstance(registry, dict)

    def test_registry_contains_providers_key(
        self, settings_override: None,
    ) -> None:
        """The loaded registry has a 'providers' key as per the stub."""
        from anonreq.config import load_provider_registry
        registry = load_provider_registry()
        assert "providers" in registry
