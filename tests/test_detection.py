"""Tests for RegexDetector and ExclusionList.

Per D-32 through D-41:
- RegexDetector runs pre-compiled patterns on text
- Luhn validation for credit card detection
- Entity specificity dictionary for span arbitration
- ExclusionList for suppressing false positives
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from anonreq.detection.regex_detector import RegexDetector
from anonreq.detection.regex_patterns import PATTERNS, luhn_checksum, ENTITY_SPECIFICITY, TIER_1_ENTITIES
from anonreq.detection.exclusion_list import ExclusionList


# ---------------------------------------------------------------------------
# Luhn checksum tests
# ---------------------------------------------------------------------------


class TestLuhnChecksum:
    """Test suite for Luhn checksum validation."""

    def test_valid_credit_card(self):
        """Valid Visa card number passes Luhn checksum."""
        assert luhn_checksum("4111111111111111") is True

    def test_valid_mastercard(self):
        """Valid Mastercard number passes Luhn checksum."""
        assert luhn_checksum("5500000000000004") is True

    def test_valid_amex(self):
        """Valid Amex number passes Luhn checksum."""
        assert luhn_checksum("378282246310005") is True

    def test_invalid_credit_card(self):
        """Invalid card number fails Luhn checksum."""
        assert luhn_checksum("1234567890123456") is False

    def test_luhn_with_dashes(self):
        """Luhn handles card numbers with non-digit characters (strips them)."""
        assert luhn_checksum("4111-1111-1111-1111") is True

    def test_luhn_too_short(self):
        """Card number shorter than 13 digits fails."""
        assert luhn_checksum("411111") is False

    def test_luhn_too_long(self):
        """Card number longer than 19 digits fails."""
        assert luhn_checksum("411111111111111111111111111") is False

    def test_luhn_empty(self):
        """Empty string returns False."""
        assert luhn_checksum("") is False

    def test_luhn_non_digit_characters(self):
        """Non-digit characters are stripped before validation."""
        assert luhn_checksum("4111 1111 1111 1111") is True


# ---------------------------------------------------------------------------
# Regex patterns tests
# ---------------------------------------------------------------------------


class TestRegexPatterns:
    """Test suite for pre-compiled regex patterns."""

    def test_required_tier1_entities_present(self):
        """All required Tier 1 entities are defined."""
        required = {"EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "IBAN_CODE", "IP_ADDRESS", "URL"}
        for entity in required:
            assert entity in PATTERNS, f"Missing pattern: {entity}"

    def test_tier1_entities_constant(self):
        """TIER_1_ENTITIES constant lists expected entity types."""
        assert "EMAIL_ADDRESS" in TIER_1_ENTITIES
        assert "PHONE_NUMBER" in TIER_1_ENTITIES
        assert "CREDIT_CARD" in TIER_1_ENTITIES

    def test_entity_specificity_api_key_highest(self):
        """API_KEY has highest specificity (100)."""
        assert ENTITY_SPECIFICITY.get("API_KEY", 0) == 100
        assert ENTITY_SPECIFICITY["API_KEY"] > ENTITY_SPECIFICITY["EMAIL_ADDRESS"]

    def test_entity_specificity_ranking_order(self):
        """Specificity ranking matches D-41: API_KEY > EMAIL > PHONE > CC > IBAN > SSN > URL > IP."""
        order = ["API_KEY", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "IBAN_CODE", "US_SSN", "URL", "IP_ADDRESS"]
        for i in range(len(order) - 1):
            assert ENTITY_SPECIFICITY[order[i]] >= ENTITY_SPECIFICITY[order[i + 1]], \
                f"{order[i]} should have >= specificity than {order[i+1]}"

    def test_email_pattern_matches(self):
        """EMAIL_ADDRESS pattern matches standard emails."""
        match = PATTERNS["EMAIL_ADDRESS"].search("contact me at john.doe@example.com")
        assert match is not None
        assert match.group() == "john.doe@example.com"

    def test_email_pattern_no_match_without_domain(self):
        """EMAIL_ADDRESS pattern does not match strings without domain."""
        match = PATTERNS["EMAIL_ADDRESS"].search("not an email")
        assert match is None

    def test_phone_pattern_matches_us(self):
        """PHONE_NUMBER pattern matches US phone with dashes."""
        match = PATTERNS["PHONE_NUMBER"].search("call +1-555-123-4567")
        assert match is not None

    def test_phone_pattern_matches_international(self):
        """PHONE_NUMBER pattern matches international format."""
        match = PATTERNS["PHONE_NUMBER"].search("call +44 20 7946 0958")
        assert match is not None

    def test_ip_pattern_matches_ipv4(self):
        """IP_ADDRESS pattern matches standard IPv4."""
        match = PATTERNS["IP_ADDRESS"].search("server at 192.168.1.1")
        assert match is not None
        assert match.group() == "192.168.1.1"

    def test_url_pattern_matches_https(self):
        """URL pattern matches https URLs."""
        match = PATTERNS["URL"].search("visit https://example.com/path")
        assert match is not None

    def test_url_pattern_matches_http(self):
        """URL pattern matches http URLs."""
        match = PATTERNS["URL"].search("visit http://example.com")
        assert match is not None

    def test_ssn_pattern_matches_valid(self):
        """US_SSN pattern matches valid SSN format."""
        match = PATTERNS["US_SSN"].search("My SSN is 123-45-6789")
        assert match is not None
        assert match.group() == "123-45-6789"

    def test_ssn_pattern_excludes_000_area(self):
        """US_SSN pattern excludes area 000."""
        assert PATTERNS["US_SSN"].search("000-45-6789") is None

    def test_ssn_pattern_excludes_666_area(self):
        """US_SSN pattern excludes area 666."""
        assert PATTERNS["US_SSN"].search("666-45-6789") is None

    def test_ssn_pattern_excludes_900_999_area(self):
        """US_SSN pattern excludes area 900-999."""
        assert PATTERNS["US_SSN"].search("912-45-6789") is None

    def test_iban_pattern_matches(self):
        """IBAN_CODE pattern matches standard IBAN."""
        match = PATTERNS["IBAN_CODE"].search("GB82 WEST 1234 5698 7654 32")
        assert match is not None, "IBAN pattern should match GB82 WEST 1234 5698 7654 32"


# ---------------------------------------------------------------------------
# RegexDetector tests
# ---------------------------------------------------------------------------


class TestRegexDetector:
    """Test suite for RegexDetector."""

    def test_detect_email(self):
        """Detect EMAIL_ADDRESS with correct span positions."""
        detector = RegexDetector()
        results = detector.detect("My email is user@example.com here")
        assert len(results) >= 1
        email_result = next(r for r in results if r["entity_type"] == "EMAIL_ADDRESS")
        assert email_result["start"] == 12
        assert email_result["end"] == 28
        assert email_result["score"] == 1.0
        assert email_result["source"] == "regex"

    def test_detect_phone(self):
        """Detect PHONE_NUMBER in text."""
        detector = RegexDetector()
        results = detector.detect("Call +1-555-123-4567 now")
        assert any(r["entity_type"] == "PHONE_NUMBER" for r in results), f"No phone in {results}"

    def test_detect_credit_card_with_luhn(self):
        """CREDIT_CARD detected only when Luhn checksum passes."""
        detector = RegexDetector()
        # Valid Visa test number
        results = detector.detect("My card is 4111111111111111")
        cc_results = [r for r in results if r["entity_type"] == "CREDIT_CARD"]
        assert len(cc_results) == 1

    def test_credit_card_invalid_luhn_skipped(self):
        """Credit card without valid Luhn checksum is NOT detected."""
        detector = RegexDetector()
        results = detector.detect("My card is 1234567890123456")
        cc_results = [r for r in results if r["entity_type"] == "CREDIT_CARD"]
        assert len(cc_results) == 0

    def test_detect_ip_address(self):
        """Detect IP_ADDRESS in text."""
        detector = RegexDetector()
        results = detector.detect("Server: 10.0.0.1")
        assert any(r["entity_type"] == "IP_ADDRESS" for r in results)

    def test_detect_url(self):
        """Detect URL in text."""
        detector = RegexDetector()
        results = detector.detect("Visit https://example.com/path?q=1")
        assert any(r["entity_type"] == "URL" for r in results)

    def test_detect_ssn(self):
        """Detect US_SSN in text."""
        detector = RegexDetector()
        results = detector.detect("SSN: 123-45-6789")
        assert any(r["entity_type"] == "US_SSN" for r in results)

    def test_empty_text_returns_empty_list(self):
        """Empty text returns empty list."""
        detector = RegexDetector()
        assert detector.detect("") == []

    def test_no_pii_returns_empty(self):
        """Text with no PII returns empty list."""
        detector = RegexDetector()
        results = detector.detect("Hello, this is a normal message with no sensitive data.")
        assert results == []

    def test_multiple_detections(self):
        """Text with multiple PII types returns all detections."""
        detector = RegexDetector()
        results = detector.detect("Email: user@test.com, Phone: +1-555-123-4567")
        types = {r["entity_type"] for r in results}
        assert "EMAIL_ADDRESS" in types, f"Expected EMAIL in {types}"
        assert "PHONE_NUMBER" in types, f"Expected PHONE in {types}"

    def test_detect_results_have_all_required_fields(self):
        """Each detection result has entity_type, start, end, score, source."""
        detector = RegexDetector()
        results = detector.detect("Email: user@test.com")
        for r in results:
            assert "entity_type" in r
            assert "start" in r
            assert "end" in r
            assert "score" in r
            assert "source" in r
            assert r["source"] == "regex"
            assert r["score"] == 1.0

    def test_iban_detection(self):
        """Detect IBAN_CODE in text."""
        detector = RegexDetector()
        results = detector.detect("IBAN: GB82 WEST 1234 5698 7654 32")
        assert any(r["entity_type"] == "IBAN_CODE" for r in results), f"No IBAN found in {results}"


# ---------------------------------------------------------------------------
# ExclusionList tests
# ---------------------------------------------------------------------------


class TestExclusionList:
    """Test suite for ExclusionList."""

    def test_exact_match_suppresses(self):
        """Exclusion with exact match suppresses matching value."""
        ex = ExclusionList(exclusions=["john@example.com"])
        assert ex.is_excluded("john@example.com") is True

    def test_exact_match_no_suppression_for_different(self):
        """Exclusion does not suppress non-matching values."""
        ex = ExclusionList(exclusions=["john@example.com"])
        assert ex.is_excluded("jane@example.com") is False

    def test_wildcard_match_suppresses(self):
        """Wildcard pattern (*) suppresses matching values."""
        ex = ExclusionList(exclusions=["test-*"])
        assert ex.is_excluded("test-123") is True
        assert ex.is_excluded("test-abc") is True
        assert ex.is_excluded("real-value") is False

    def test_wildcard_at_end(self):
        """Wildcard at end of pattern matches prefix."""
        ex = ExclusionList(exclusions=["*@example.com"])
        assert ex.is_excluded("user@example.com") is True
        assert ex.is_excluded("user@other.com") is False

    def test_multiple_exclusions(self):
        """Multiple exclusion patterns all checked."""
        ex = ExclusionList(exclusions=["user1@test.com", "user2@test.com", "test-*"])
        assert ex.is_excluded("user1@test.com") is True
        assert ex.is_excluded("user2@test.com") is True
        assert ex.is_excluded("test-value") is True
        assert ex.is_excluded("other@test.com") is False

    def test_filter_detections(self):
        """filter_detections removes matching detections from a list."""
        ex = ExclusionList(exclusions=["safe@example.com"])
        detections = [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 16, "score": 1.0, "source": "regex"},
        ]
        # filter_detections needs the original text value to check exclusions
        # We'll test this once the integration is wired
        filtered = ex.filter_detections(detections, original_text="safe@example.com")
        assert len(filtered) == 0

    def test_filter_detections_preserves_non_matching(self):
        """filter_detections preserves non-matching detections."""
        ex = ExclusionList(exclusions=["safe@example.com"])
        detections = [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 17, "score": 1.0, "source": "regex"},
        ]
        filtered = ex.filter_detections(detections, original_text="risk@example.com")
        assert len(filtered) == 1

    def test_from_yaml_loading(self):
        """ExclusionList loaded from YAML."""
        yaml_content = """
exclusions:
  - value: "test@example.com"
  - value: "safe-*"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            tmp_path = f.name
        try:
            ex = ExclusionList.from_yaml(tmp_path)
            assert ex.is_excluded("test@example.com") is True
            assert ex.is_excluded("safe-value") is True
            assert ex.is_excluded("other@test.com") is False
        finally:
            Path(tmp_path).unlink()

    def test_empty_exclusion_list(self):
        """Empty exclusion list does not suppress anything."""
        ex = ExclusionList(exclusions=[])
        assert ex.is_excluded("anything") is False
        assert ex.filter_detections([{"entity_type": "EMAIL"}], "test") == [{"entity_type": "EMAIL"}]

    def test_exclusion_case_sensitive(self):
        """Exclusion match is case-sensitive (exact match on detected value)."""
        ex = ExclusionList(exclusions=["Test@Example.com"])
        assert ex.is_excluded("Test@Example.com") is True
        assert ex.is_excluded("test@example.com") is False
