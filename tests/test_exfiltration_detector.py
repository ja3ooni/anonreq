"""Unit tests for hybrid exfiltration encoding detection (Plan 13-03, Task 2).

Tests cover:
- Base64-encoded content detection
- Hex-encoded content detection
- JWT token detection
- PEM-encoded content detection
- High-entropy (Shannon entropy > threshold) detection
- Normal text NOT flagged (false positive reduction)
- Short strings (< 20 chars) NOT flagged
- Both inbound and outbound gates supported
- Multiple encoding methods in single text
"""

from __future__ import annotations

import pytest

from anonreq.services.exfiltration_detector import ExfiltrationDetector, ExfiltrationResult


@pytest.fixture
def exfiltration_config():
    """Minimal exfiltration detection config matching dlp.yaml structure."""
    return {
        "exfiltration": {
            "detection": {
                "enabled": True,
                "methods": {
                    "base64": {
                        "enabled": True,
                        "min_length": 20,
                        "pattern": r"[A-Za-z0-9+/]{20,}={0,2}",
                        "entropy_threshold": 4.5,
                    },
                    "hex": {
                        "enabled": True,
                        "min_length": 20,
                        "pattern": r"[0-9a-fA-F]{20,}",
                    },
                    "jwt": {
                        "enabled": True,
                        "pattern": r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
                    },
                    "pem": {
                        "enabled": True,
                        "pattern": r"-----BEGIN [A-Z ]+-----",
                    },
                },
                "entropy": {
                    "enabled": True,
                    "threshold": 6.0,
                    "min_length": 30,
                },
                "heuristics": {
                    "enabled": True,
                    "bigru_block": True,
                },
            },
            "default_action": "block",
        },
    }


@pytest.fixture
def detector(exfiltration_config):
    return ExfiltrationDetector(exfiltration_config)


def test_exfiltration_result_dataclass():
    """ExfiltrationResult has all required fields."""
    result = ExfiltrationResult(
        detected=True,
        method="base64",
        confidence=0.75,
        shannon_entropy=5.5,
        match_text="SGVsbG8gV29ybGQ=",
        start=0,
        end=15,
    )
    assert result.detected is True
    assert result.method == "base64"
    assert result.confidence == 0.75
    assert result.shannon_entropy == 5.5
    assert result.match_text == "SGVsbG8gV29ybGQ="
    assert result.start == 0
    assert result.end == 15


@pytest.mark.asyncio
async def test_base64_detection(detector):
    """Base64-encoded content is detected."""
    text = "SGVsbG8gV29ybGQgVGhpcyBpcyBhIHRlc3QgbWVzc2FnZQ=="
    results = await detector.detect(text)
    base64_results = [r for r in results if r.method == "base64"]
    assert len(base64_results) >= 1
    assert base64_results[0].detected is True
    assert base64_results[0].confidence >= 0.7


@pytest.mark.asyncio
async def test_hex_detection(detector):
    """Hex-encoded content is detected."""
    text = "48656c6c6f20576f726c64205468697320697320612074657374"
    results = await detector.detect(text)
    hex_results = [r for r in results if r.method == "hex"]
    assert len(hex_results) >= 1
    assert hex_results[0].detected is True


@pytest.mark.asyncio
async def test_jwt_detection(detector):
    """JWT tokens are detected as exfiltration-like patterns."""
    text = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNvrPmhg"
    results = await detector.detect(text)
    jwt_results = [r for r in results if r.method == "jwt"]
    assert len(jwt_results) >= 1
    assert jwt_results[0].detected is True
    assert jwt_results[0].confidence >= 0.8


@pytest.mark.asyncio
async def test_pem_detection(detector):
    """PEM-encoded content is detected."""
    text = "-----BEGIN CERTIFICATE-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA"
    results = await detector.detect(text)
    pem_results = [r for r in results if r.method == "pem"]
    assert len(pem_results) >= 1
    assert pem_results[0].detected is True
    assert pem_results[0].confidence >= 0.8


@pytest.mark.asyncio
async def test_high_entropy_detection(detector):
    """High-entropy strings (Shannon entropy > 6.0) are detected."""
    # Build a string with entropy > 6.0 using diverse byte values.
    # To exceed 6.0 bits/byte, we need > 64 unique byte values in the encoding.
    # Using mixed printable ASCII (0x21-0x7E = 94 possible values) with
    # a uniform-ish distribution on a 60-char string achieves ~5.7-6.3 bits/byte.
    text = (
        "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUV"
        "WXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
    )  # 94 unique printable ASCII chars, entropy > 6.0
    results = await detector.detect(text)
    entropy_results = [r for r in results if r.method == "high_entropy"]
    assert len(entropy_results) >= 1
    assert entropy_results[0].detected is True
    assert entropy_results[0].shannon_entropy is not None
    assert entropy_results[0].shannon_entropy > 6.0


@pytest.mark.asyncio
async def test_normal_text_not_flagged(detector):
    """Normal English text (low entropy) is NOT flagged."""
    text = "The quick brown fox jumps over the lazy dog"
    results = await detector.detect(text)
    # No exfiltration should be detected
    assert len(results) == 0


@pytest.mark.asyncio
async def test_short_strings_not_flagged(detector):
    """Strings shorter than min_length (20 chars) are NOT flagged."""
    text = "abc123"  # Too short for any method
    results = await detector.detect(text)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_multiple_encoding_methods(detector):
    """Multiple encoding methods detected in a single text."""
    text = (
        "Base64: SGVsbG8gV29ybGQgVGhpcyBpcyBhIHRlc3QgbWVzc2FnZQ== "
        "Hex: 48656c6c6f20576f726c64205468697320697320612074657374 "
        "JWT: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNvrPmhg "
        "PEM: -----BEGIN CERTIFICATE-----"
    )
    results = await detector.detect(text)
    methods = set(r.method for r in results)
    assert len(methods) >= 3  # Should detect multiple methods


@pytest.mark.asyncio
async def test_detect_in_text_summary(detector):
    """detect_in_text() returns a summary of exfiltration detection."""
    text = "SGVsbG8gV29ybGQgVGhpcyBpcyBhIHRlc3QgbWVzc2FnZQ=="
    summary = await detector.detect_in_text(text)
    assert summary.detected is True
    assert len(summary.methods) >= 1
    assert summary.max_confidence >= 0.7
    assert summary.detection_count >= 1


@pytest.mark.asyncio
async def test_shannon_entropy_empty_string(detector):
    """Shannon entropy returns 0.0 for empty string."""
    entropy = detector._shannon_entropy("")
    assert entropy == 0.0


@pytest.mark.asyncio
async def test_shannon_entropy_single_char(detector):
    """Shannon entropy returns 0.0 for single repeated character."""
    entropy = detector._shannon_entropy("AAAA")
    assert entropy == 0.0


@pytest.mark.asyncio
async def test_gate_support_inbound_outbound(detector):
    """detect() works for both inbound (prompt) and outbound (response) gates."""
    # Inbound: exfiltration attempt in prompt (base64 >= 20 chars)
    inbound_text = "Here is the data encoded: SGVsbG9Xb3JsZFNvbWV0aGluZ01vcmU="
    inbound_results = await detector.detect(inbound_text)
    assert len(inbound_results) >= 1

    # Outbound: exfiltrated data in response (hex >= 20 chars)
    outbound_text = "The leaked data is: 48656c6c6f20576f726c64"
    outbound_results = await detector.detect(outbound_text)
    assert len(outbound_results) >= 1
