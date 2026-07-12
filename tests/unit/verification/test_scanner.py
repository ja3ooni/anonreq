"""Tests for ResponseScanner — post-restoration token detection.

Covers:
- Token detection in plain text, JSON, mixed content
- Empty/clean text returns count=0
- Multiple distinct tokens all detected
- Scanner is stateless — independent results per call
"""

from __future__ import annotations

from anonreq.verification.scanner import TOKEN_PATTERN, ResponseScanner, ScanResult


class TestTokenPattern:
    """Verify TOKEN_PATTERN regex matches expected token formats."""

    def test_matches_standard_tokens(self) -> None:
        assert TOKEN_PATTERN.match("[NAME_1]")
        assert TOKEN_PATTERN.match("[EMAIL_0]")
        assert TOKEN_PATTERN.match("[CREDIT_CARD_42]")
        assert TOKEN_PATTERN.match("[SSN_999]")
        assert TOKEN_PATTERN.match("[IP_ADDRESS_7]")
        assert TOKEN_PATTERN.match("[PHONE_NUMBER_100]")

    def test_rejects_malformed_tokens(self) -> None:
        assert not TOKEN_PATTERN.match("NAME_1]")
        assert not TOKEN_PATTERN.match("[name_1]")
        assert not TOKEN_PATTERN.match("[NAME_]")
        assert not TOKEN_PATTERN.match("[NAME_")
        assert not TOKEN_PATTERN.match("[]")


class TestResponseScanner:
    """ResponseScanner unit tests."""

    def test_detects_tokens_in_plain_text(self) -> None:
        scanner = ResponseScanner()
        result = scanner.scan("Hello [NAME_1], your [EMAIL_0] is on file")
        assert isinstance(result, ScanResult)
        assert result.match_count == 2
        assert "[NAME_1]" in result.matches
        assert "[EMAIL_0]" in result.matches

    def test_returns_empty_for_clean_text(self) -> None:
        scanner = ResponseScanner()
        result = scanner.scan("No tokens here")
        assert result.match_count == 0
        assert result.matches == []

    def test_returns_empty_for_empty_text(self) -> None:
        scanner = ResponseScanner()
        result = scanner.scan("")
        assert result.match_count == 0

    def test_detects_multiple_tokens_correct_count(self) -> None:
        scanner = ResponseScanner()
        text = (
            "Tokens: [NAME_1] [EMAIL_2] [PHONE_3] [CREDIT_CARD_4] "
            "[SSN_5] [IP_ADDRESS_6] [URL_7] [DOB_8]"
        )
        result = scanner.scan(text)
        assert result.match_count == 8

    def test_detects_tokens_embedded_in_json(self) -> None:
        scanner = ResponseScanner()
        text = '{"content": "Hello [NAME_1]", "role": "user"}'
        result = scanner.scan(text)
        assert result.match_count == 1
        assert result.matches == ["[NAME_1]"]

    def test_detects_tokens_in_json_with_escaped_content(self) -> None:
        scanner = ResponseScanner()
        text = '{"content": "Contact [EMAIL_0] at [PHONE_1]"}'
        result = scanner.scan(text)
        assert result.match_count == 2

    def test_stateless_between_calls(self) -> None:
        scanner = ResponseScanner()
        r1 = scanner.scan("[NAME_1]")
        r2 = scanner.scan("clean")
        r3 = scanner.scan("[EMAIL_0] and [PHONE_1]")
        assert r1.match_count == 1
        assert r2.match_count == 0
        assert r3.match_count == 2

    def test_positions_are_correct(self) -> None:
        scanner = ResponseScanner()
        text = "Hello [NAME_1] here"
        result = scanner.scan(text)
        assert result.match_count == 1
        start, end = result.positions[0]
        assert text[start:end] == "[NAME_1]"

    def test_scanresult_repr(self) -> None:
        result = ScanResult(match_count=2, matches=["[A_1]", "[B_2]"])
        assert "match_count=2" in repr(result)


class TestResponseScannerEdgeCases:
    """Edge cases for the scanner."""

    def test_token_with_long_type(self) -> None:
        scanner = ResponseScanner()
        # Max 20 uppercase + underscore characters per the pattern
        long_type = "A" * 20
        result = scanner.scan(f"[{long_type}_1]")
        assert result.match_count == 1

    def test_token_with_underscore_in_type(self) -> None:
        scanner = ResponseScanner()
        result = scanner.scan("[MY_CUSTOM_TYPE_5]")
        assert result.match_count == 1

    def test_no_false_positive_on_plain_brackets(self) -> None:
        scanner = ResponseScanner()
        result = scanner.scan("[just a note] [another] [123]")
        assert result.match_count == 0

    def test_no_false_positive_on_markdown_links(self) -> None:
        scanner = ResponseScanner()
        result = scanner.scan("Click [here](https://example.com) for info")
        assert result.match_count == 0

    def test_mixed_content_with_tokens_and_brackets(self) -> None:
        scanner = ResponseScanner()
        text = "Token [NAME_1] and markdown [link](url) and [EMAIL_0]"
        result = scanner.scan(text)
        assert result.match_count == 2
        assert "[NAME_1]" in result.matches
        assert "[EMAIL_0]" in result.matches
