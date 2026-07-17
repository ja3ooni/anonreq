"""Tests for enterprise secret detection recognizers (Phase 26, GUARD-01).

Covers AnonReqApiKeyRecognizer, AnonReqAwsAccessKeyRecognizer,
AnonReqGitHubTokenRecognizer, and AnonReqInternalHostnameRecognizer.
"""

from __future__ import annotations

import os
import tempfile
import pytest
import yaml

from anonreq.detection.recognizers.enterprise import (
    EnterpriseRecognizerConfig,
    create_enterprise_bundle,
    AnonReqApiKeyRecognizer,
    AnonReqAwsAccessKeyRecognizer,
    AnonReqGitHubTokenRecognizer,
    AnonReqInternalHostnameRecognizer,
)


@pytest.fixture
def default_api_key_config() -> EnterpriseRecognizerConfig:
    return EnterpriseRecognizerConfig(enabled=True, confidence=0.85)


@pytest.fixture
def default_aws_key_config() -> EnterpriseRecognizerConfig:
    return EnterpriseRecognizerConfig(enabled=True, confidence=0.90)


@pytest.fixture
def default_github_token_config() -> EnterpriseRecognizerConfig:
    return EnterpriseRecognizerConfig(enabled=True, confidence=0.95)


@pytest.fixture
def default_hostname_config() -> EnterpriseRecognizerConfig:
    return EnterpriseRecognizerConfig(
        enabled=True,
        confidence=0.80,
        internal_domains=["internal", "corp.local", "company.com"],
    )


class TestAPIKeyRecognizer:
    def test_api_key_valid_patterns(self, default_api_key_config):
        recognizer = AnonReqApiKeyRecognizer(default_api_key_config)
        # OpenAI style sk-
        results = recognizer.analyze("My key is sk-1234567890abcdefghijklmnopqrstuvwxyz")
        assert len(results) == 1
        assert results[0]["start"] == 10
        assert results[0]["end"] == 49

        # Project key sk-proj-
        results = recognizer.analyze("sk-proj-1234567890abcdefghijklmnopqrstuvwxyz")
        assert len(results) == 1

        # Public key pk-
        results = recognizer.analyze("pk-1234567890abcdefghijklmnopqrstuvwxyz")
        assert len(results) == 1

    def test_api_key_invalid_patterns(self, default_api_key_config):
        recognizer = AnonReqApiKeyRecognizer(default_api_key_config)
        assert len(recognizer.analyze("sk-too-short")) == 0
        assert len(recognizer.analyze("mykey-without-prefix")) == 0

    def test_api_key_confidence(self, default_api_key_config):
        recognizer = AnonReqApiKeyRecognizer(default_api_key_config)
        results = recognizer.analyze("sk-1234567890abcdefghijklmnopqrstuvwxyz")
        assert results[0]["score"] == 0.85


class TestAWSAccessKeyRecognizer:
    def test_aws_key_valid_patterns(self, default_aws_key_config):
        recognizer = AnonReqAwsAccessKeyRecognizer(default_aws_key_config)
        results = recognizer.analyze("AWS: AKIAIOSFODNN7EXAMPLE")
        assert len(results) == 1
        assert results[0]["start"] == 5
        assert results[0]["end"] == 25

    def test_aws_key_invalid_patterns(self, default_aws_key_config):
        recognizer = AnonReqAwsAccessKeyRecognizer(default_aws_key_config)
        assert len(recognizer.analyze("AKIAtoo-short")) == 0
        assert len(recognizer.analyze("BKIAIOSFODNN7EXAMPLE")) == 0

    def test_aws_key_confidence(self, default_aws_key_config):
        recognizer = AnonReqAwsAccessKeyRecognizer(default_aws_key_config)
        results = recognizer.analyze("AKIAIOSFODNN7EXAMPLE")
        assert results[0]["score"] == 0.90


class TestGitHubTokenRecognizer:
    def test_github_token_valid_patterns(self, default_github_token_config):
        recognizer = AnonReqGitHubTokenRecognizer(default_github_token_config)
        # ghp_
        assert len(recognizer.analyze("ghp_1234567890abcdefghijklmnopqrstuvwxyz")) == 1
        # ghs_
        assert len(recognizer.analyze("ghs_1234567890abcdefghijklmnopqrstuvwxyz")) == 1
        # gho_
        assert len(recognizer.analyze("gho_1234567890abcdefghijklmnopqrstuvwxyz")) == 1
        # ghu_
        assert len(recognizer.analyze("ghu_1234567890abcdefghijklmnopqrstuvwxyz")) == 1
        # ghr_
        assert len(recognizer.analyze("ghr_1234567890abcdefghijklmnopqrstuvwxyz")) == 1
        # ghb_
        assert len(recognizer.analyze("ghb_1234567890abcdefghijklmnopqrstuvwxyz")) == 1

    def test_github_token_invalid_patterns(self, default_github_token_config):
        recognizer = AnonReqGitHubTokenRecognizer(default_github_token_config)
        assert len(recognizer.analyze("ghp_too-short")) == 0
        assert len(recognizer.analyze("ghx_1234567890abcdefghijklmnopqrstuvwxyz")) == 0

    def test_github_token_confidence(self, default_github_token_config):
        recognizer = AnonReqGitHubTokenRecognizer(default_github_token_config)
        results = recognizer.analyze("ghp_1234567890abcdefghijklmnopqrstuvwxyz")
        assert results[0]["score"] == 0.95


class TestInternalHostnameRecognizer:
    def test_internal_hostname_valid(self, default_hostname_config):
        recognizer = AnonReqInternalHostnameRecognizer(default_hostname_config)
        assert len(recognizer.analyze("db.internal")) == 1
        assert len(recognizer.analyze("api.prod.corp.local")) == 1
        assert len(recognizer.analyze("app.company.com")) == 1

    def test_internal_hostname_invalid(self, default_hostname_config):
        recognizer = AnonReqInternalHostnameRecognizer(default_hostname_config)
        assert len(recognizer.analyze("google.com")) == 0
        assert len(recognizer.analyze("github.com")) == 0
        assert len(recognizer.analyze("company.com")) == 0 # requires subdomain subdomain.company.com
        assert len(recognizer.analyze("my.company.com.external")) == 0

    def test_internal_hostname_confidence(self, default_hostname_config):
        recognizer = AnonReqInternalHostnameRecognizer(default_hostname_config)
        results = recognizer.analyze("db.internal")
        assert results[0]["score"] == 0.80


class TestRecognizerGeneral:
    def test_no_false_positives_on_clean_text(
        self,
        default_api_key_config,
        default_aws_key_config,
        default_github_token_config,
        default_hostname_config,
    ):
        text = "Hello world, this is a normal sentence with no secrets and no internal hostnames."
        assert len(AnonReqApiKeyRecognizer(default_api_key_config).analyze(text)) == 0
        assert len(AnonReqAwsAccessKeyRecognizer(default_aws_key_config).analyze(text)) == 0
        assert len(AnonReqGitHubTokenRecognizer(default_github_token_config).analyze(text)) == 0
        assert len(AnonReqInternalHostnameRecognizer(default_hostname_config).analyze(text)) == 0

    def test_entity_types_match(
        self,
        default_api_key_config,
        default_aws_key_config,
        default_github_token_config,
        default_hostname_config,
    ):
        assert AnonReqApiKeyRecognizer(default_api_key_config).analyze("sk-1234567890abcdefghijklmnopqrstuvwxyz")[0]["entity_type"] == "ENTERPRISE_API_KEY"
        assert AnonReqAwsAccessKeyRecognizer(default_aws_key_config).analyze("AKIAIOSFODNN7EXAMPLE")[0]["entity_type"] == "ENTERPRISE_AWS_KEY"
        assert AnonReqGitHubTokenRecognizer(default_github_token_config).analyze("ghp_1234567890abcdefghijklmnopqrstuvwxyz")[0]["entity_type"] == "ENTERPRISE_GITHUB_TOKEN"
        assert AnonReqInternalHostnameRecognizer(default_hostname_config).analyze("db.internal")[0]["entity_type"] == "ENTERPRISE_INTERNAL_HOST"

    def test_create_bundle_from_config(self):
        config_data = {
            "enterprise_recognizers": {
                "api_key": {"enabled": True, "confidence": 0.95},
                "aws_access_key": {"enabled": False},
                "github_token": {"enabled": True},
                "internal_hostname": {
                    "enabled": True,
                    "internal_domains": ["test.local"],
                },
            }
        }
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        try:
            bundle = create_enterprise_bundle(temp_path)
            assert "api_key" in bundle
            assert "aws_access_key" not in bundle
            assert "github_token" in bundle
            assert "internal_hostname" in bundle
            assert bundle["api_key"]._config.confidence == 0.95
        finally:
            os.remove(temp_path)

    def test_create_bundle_config_not_found(self):
        from anonreq.detection.pipeline import load_enterprise_recognizers
        # Graceful fallback to empty dictionary in pipeline loader
        bundle = load_enterprise_recognizers("nonexistent_config_file_xyz.yaml")
        assert bundle == {}

    def test_disabled_recognizer_not_loaded(self):
        config_data = {
            "enterprise_recognizers": {
                "api_key": {"enabled": False},
                "aws_access_key": {"enabled": False},
                "github_token": {"enabled": False},
                "internal_hostname": {"enabled": False},
            }
        }
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        try:
            bundle = create_enterprise_bundle(temp_path)
            assert bundle == {}
        finally:
            os.remove(temp_path)
