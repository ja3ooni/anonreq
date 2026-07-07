from __future__ import annotations

import array

import numpy as np
import pytest

from anonreq.voice.config import VoiceConfig
from anonreq.voice.sanitizer import AudioSanitizer, DetectionTimestamp, TextSanitizer


def pcm_samples(values: list[int]) -> bytes:
    samples = array.array("h", values)
    if samples.itemsize != 2:
        raise AssertionError("test platform must use 16-bit h arrays")
    return samples.tobytes()


def read_pcm(data: bytes) -> list[int]:
    samples = array.array("h")
    samples.frombytes(data)
    return list(samples)


@pytest.mark.asyncio
async def test_mute_frame_sets_pcm_samples_to_silence_for_entity_duration():
    sanitizer = AudioSanitizer(VoiceConfig(audio_sample_rate=8000))
    audio = pcm_samples([1000] * 8000)

    muted = await sanitizer.mute_frame(audio, sample_rate=8000, start_ms=100, end_ms=200)
    values = read_pcm(muted)

    assert values[:800] == [1000] * 800
    assert values[800:1600] == [0] * 800
    assert values[1600:1605] == [1000] * 5


@pytest.mark.asyncio
async def test_beep_frame_generates_configurable_tone_in_entity_range():
    sanitizer = AudioSanitizer(VoiceConfig(audio_sample_rate=8000))
    audio = pcm_samples([0] * 800)

    beeped = await sanitizer.beep_frame(
        audio,
        sample_rate=8000,
        start_ms=0,
        end_ms=100,
        frequency=1000,
        amplitude=0.5,
    )
    values = read_pcm(beeped)

    assert max(values[:800]) > 10000
    assert min(values[:800]) < -10000
    assert len(set(values[:16])) > 4


@pytest.mark.asyncio
async def test_sanitize_merges_overlapping_entity_ranges():
    sanitizer = AudioSanitizer(VoiceConfig(audio_sample_rate=8000))
    audio = pcm_samples([3000] * 4000)

    sanitized = await sanitizer.sanitize(
        audio,
        [
            {"audio_start_ms": 100, "audio_end_ms": 220, "entity_type": "EMAIL"},
            {"audio_start_ms": 180, "audio_end_ms": 260, "entity_type": "PHONE"},
        ],
        method="mute",
        sample_rate=8000,
    )
    values = read_pcm(sanitized)

    assert values[799] == 3000
    assert values[800:2080] == [0] * 1280
    assert values[2080] == 3000


@pytest.mark.asyncio
async def test_text_sanitizer_replaces_sensitive_spans_with_typed_tokens():
    sanitizer = TextSanitizer()
    text = "Jane Doe emailed john@example.com and Jane Doe replied"

    sanitized = await sanitizer.sanitize_text(
        text,
        [
            {"start": 0, "end": 8, "entity_type": "PERSON"},
            {"start": 17, "end": 33, "entity_type": "EMAIL"},
            {"start": 38, "end": 46, "entity_type": "PERSON"},
        ],
    )

    assert sanitized == "[PERSON_1] emailed [EMAIL_1] and [PERSON_2] replied"


def test_legacy_numpy_sanitize_chunk_path_still_masks_detection_timestamps():
    sanitizer = AudioSanitizer(sample_rate=1000, mode="mute")
    audio = np.ones(100, dtype=np.float32)

    sanitized = sanitizer.sanitize_chunk(audio, 0, [DetectionTimestamp(10, 20, "EMAIL")])

    assert np.all(sanitized[:10] == 1.0)
    assert np.all(sanitized[10:20] == 0.0)
    assert np.all(sanitized[20:] == 1.0)
