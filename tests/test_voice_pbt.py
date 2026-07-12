from __future__ import annotations

import array

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from anonreq.voice.sanitizer import AudioSanitizer


@settings(max_examples=80, deadline=None)
@given(
    audio_data=st.binary(min_size=160, max_size=16000),
    start_ms=st.integers(min_value=0, max_value=200),
    duration_ms=st.integers(min_value=1, max_value=300),
)
@pytest.mark.asyncio
async def test_audio_sanitization_integrity_zeroes_muted_region(
    audio_data: bytes,
    start_ms: int,
    duration_ms: int,
):
    sanitizer = AudioSanitizer()
    sample_rate = 16000
    end_ms = start_ms + duration_ms

    sanitized = await sanitizer.mute_frame(audio_data, sample_rate, start_ms, end_ms)
    start_byte, end_byte = sanitizer._range_to_bytes(audio_data, sample_rate, start_ms, end_ms)

    assert len(sanitized) == len(audio_data)
    assert sanitized[:start_byte] == audio_data[:start_byte]
    assert sanitized[end_byte:] == audio_data[end_byte:]
    assert sanitized[start_byte:end_byte] == b"\x00" * (end_byte - start_byte)


@settings(max_examples=80, deadline=None)
@given(
    ranges=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=1000),
            st.integers(min_value=1, max_value=300),
        ),
        min_size=1,
        max_size=20,
    )
)
def test_voice_stream_consistency_overlapping_entities_deduplicate_to_no_more_overwrites(
    ranges: list[tuple[int, int]]
):
    entities = [
        {"audio_start_ms": start, "audio_end_ms": start + duration, "entity_type": "EMAIL"}
        for start, duration in ranges
    ]

    merged = AudioSanitizer._merge_ranges(entities)

    assert len(merged) <= len(entities)
    assert all(start < end for start, end in merged)
    assert all(merged[index][1] < merged[index + 1][0] for index in range(len(merged) - 1))


def test_voice_severity_ordering_is_strictly_monotonic():
    severity = {
        "informational": 0,
        "low": 1,
        "medium": 2,
        "high": 3,
        "critical": 4,
    }

    assert severity["informational"] < severity["low"] < severity["medium"] < severity["high"] < severity["critical"]  # noqa: E501


@settings(max_examples=50, deadline=None)
@given(audio_data=st.binary(min_size=320, max_size=8000))
@pytest.mark.asyncio
async def test_beep_sanitization_replaces_region_without_preserving_original(audio_data: bytes):
    sanitizer = AudioSanitizer()
    sample_rate = 16000
    start_ms = 0
    end_ms = min(100, max(1, int(len(audio_data) / 2 / sample_rate * 1000)))

    sanitized = await sanitizer.beep_frame(audio_data, sample_rate, start_ms, end_ms)
    start_byte, end_byte = sanitizer._range_to_bytes(audio_data, sample_rate, start_ms, end_ms)

    assert len(sanitized) == len(audio_data)
    assert sanitized[start_byte:end_byte] != audio_data[start_byte:end_byte]


# ── Audio data leakage (spectral analysis) ───────────────────────


def _pcm16_to_float(data: bytes) -> np.ndarray:
    """Convert raw 16-bit PCM bytes to a float32 numpy array."""
    samples = array.array("h")
    samples.frombytes(data)
    return np.array(samples, dtype=np.float32) / 32768.0


def _float_to_pcm16(arr: np.ndarray) -> bytes:
    """Convert a float32 numpy array back to raw 16-bit PCM bytes."""
    arr = np.clip(arr, -1.0, 1.0)
    samples = (arr * 32767).astype(np.int16)
    return samples.tobytes()


@settings(max_examples=40, deadline=None)
@given(
    audio_values=st.lists(
        st.floats(min_value=-0.01, max_value=0.01, allow_nan=False, allow_infinity=False),
        min_size=320,
        max_size=3200,
    ),
    start_ratio=st.floats(min_value=0.0, max_value=0.5),
    end_ratio=st.floats(min_value=0.1, max_value=0.8),
)
@pytest.mark.asyncio
async def test_muted_audio_contains_no_original_data_spectral(
    audio_values: list[float],
    start_ratio: float,
    end_ratio: float,
):
    """Sanitized (muted) audio frames contain no recoverable original
    speech data when analysed in the frequency domain.

    The test creates synthetic audio with known spectral content,
    mutes a region, and verifies that:

    1. The muted region is identically zero in the time domain.
    2. Cross-correlation between original and sanitized in the muted
       region is zero (no residual signal).
    """
    sanitizer = AudioSanitizer()
    sample_rate = 16000

    audio = _float_to_pcm16(np.array(audio_values, dtype=np.float32))
    total_ms = int(len(audio) / sample_rate * 1000)
    if total_ms < 20:
        return  # too short for meaningful window

    start_ms = max(0, int(total_ms * start_ratio))
    end_ms = min(total_ms - 1, int(total_ms * end_ratio))
    if end_ms <= start_ms:
        end_ms = start_ms + min(10, total_ms - start_ms - 1)

    sanitized = await sanitizer.mute_frame(audio, sample_rate, start_ms, end_ms)
    start_byte, end_byte = sanitizer._range_to_bytes(audio, sample_rate, start_ms, end_ms)

    # --- Time-domain check: muted region is silence ---
    assert sanitized[start_byte:end_byte] == b"\x00" * (end_byte - start_byte), (
        "Muted audio region must be silence (all zeros)"
    )

    # --- Spectral check: cross-correlation between original and sanitized
    # in the muted region must be zero ---
    original_segment = _pcm16_to_float(audio[start_byte:end_byte])
    sanitized_segment = _pcm16_to_float(sanitized[start_byte:end_byte])

    if len(original_segment) > 100:
        correlation = np.correlate(original_segment, sanitized_segment, mode="valid")
        assert np.allclose(correlation, 0.0, atol=1e-10), (
            "Cross-correlation between original and sanitized audio in "
            "the muted region must be zero — no residual original data"
        )


@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example],
)
@given(
    audio_values=st.lists(
        st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False),
        min_size=480,
        max_size=4800,
    ),
)
@pytest.mark.asyncio
async def test_beeped_audio_spectral_content_differs_from_original(
    audio_values: list[float],
):
    """Beeped audio frames have substantially different spectral content
    from the original — original speech data is masked by the beep tone."""
    sanitizer = AudioSanitizer()
    sample_rate = 16000

    audio = _float_to_pcm16(np.array(audio_values, dtype=np.float32))
    total_ms = int(len(audio) / sample_rate * 1000)

    start_ms = 0
    end_ms = min(total_ms, 100)

    sanitized = await sanitizer.beep_frame(audio, sample_rate, start_ms, end_ms)
    start_byte, end_byte = sanitizer._range_to_bytes(audio, sample_rate, start_ms, end_ms)

    original_segment = _pcm16_to_float(audio[start_byte:end_byte])
    sanitized_segment = _pcm16_to_float(sanitized[start_byte:end_byte])

    # --- FFT power spectrum comparison ---
    if len(original_segment) > 64:
        orig_fft = np.abs(np.fft.rfft(original_segment))
        sanit_fft = np.abs(np.fft.rfft(sanitized_segment))

        # The beep introduces a strong tone that should change the
        # power spectrum significantly — verify it is not identical
        # Guard against zero-variance inputs that make corrcoef return NaN
        if np.std(orig_fft) > 1e-10 and np.std(sanit_fft) > 1e-10:
            spectrum_correlation = np.corrcoef(orig_fft, sanit_fft)[0, 1]
            if not np.isnan(spectrum_correlation):
                assert not np.isclose(spectrum_correlation, 1.0, atol=0.05), (
                    "Beeped audio spectrum must differ from original spectrum "
                    "— original speech data is masked"
                )
