from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anonreq.multimodal.models import ContentType, UnifiedDetectionResult


def _build_multipart_body(parts: list[tuple[str, str, str, dict]]) -> tuple[bytes, str]:
    boundary = "TestBoundary123"
    lines = []
    for content_type, name, body, extra_headers in parts:
        lines.append(f"--{boundary}".encode())
        lines.append(f'Content-Disposition: form-data; name="{name}"'.encode())
        if content_type:
            lines.append(f"Content-Type: {content_type}".encode())
        for k, v in extra_headers.items():
            lines.append(f"{k}: {v}".encode())
        lines.append(b"")
        lines.append(body.encode() if isinstance(body, str) else body)
    lines.append(f"--{boundary}--".encode())
    body_bytes = b"\r\n".join(lines)
    return body_bytes, boundary


def _make_json_analyzer():
    m = AsyncMock()
    m.analyze.return_value = UnifiedDetectionResult(
        content_type=ContentType.APPLICATION_JSON,
        entities=[{"entity_type": "PERSON", "value": "John", "score": 0.95}],
        risk_score=0.5,
        classification="Sensitive",
    )
    return m


class TestMultipartAnalyzer:
    @pytest.mark.asyncio
    async def test_text_parts_are_scanned(self):
        from anonreq.multimodal.multipart_analyzer import MultipartAnalyzer

        text_engine = AsyncMock()
        text_engine.analyze_text = AsyncMock(
            return_value=[{"entity_type": "PERSON", "start": 0, "end": 5, "score": 0.9}]
        )

        body, boundary = _build_multipart_body([
            ("text/plain", "name", "John Doe", {}),
        ])
        ct_header = f"multipart/form-data; boundary={boundary}"

        analyzer = MultipartAnalyzer(
            json_analyzer=_make_json_analyzer(),
            text_engine=text_engine,
        )
        result = await analyzer.analyze(body, ct_header)
        assert result.content_type == ContentType.MULTIPART_FORM_DATA
        assert len(result.entities) >= 1

    @pytest.mark.asyncio
    async def test_json_part_routed_to_json_analyzer(self):
        from anonreq.multimodal.multipart_analyzer import MultipartAnalyzer

        text_engine = AsyncMock()
        json_analyzer = _make_json_analyzer()

        body, boundary = _build_multipart_body([
            ("application/json", "metadata", '{"user": "John"}', {}),
        ])
        ct_header = f"multipart/form-data; boundary={boundary}"

        analyzer = MultipartAnalyzer(
            json_analyzer=json_analyzer,
            text_engine=text_engine,
        )
        result = await analyzer.analyze(body, ct_header)
        json_analyzer.analyze.assert_awaited()
        assert result.content_type == ContentType.MULTIPART_FORM_DATA

    @pytest.mark.asyncio
    async def test_file_metadata_scanned(self):
        from anonreq.multimodal.multipart_analyzer import MultipartAnalyzer

        text_engine = AsyncMock()
        text_engine.analyze_text = AsyncMock(return_value=[
            {"entity_type": "PERSON", "start": 0, "end": 8, "score": 0.95},
        ])

        body, boundary = _build_multipart_body([
            ("text/plain", "filename", "john_doe_resume.pdf", {}),
        ])
        ct_header = f"multipart/form-data; boundary={boundary}"

        analyzer = MultipartAnalyzer(
            json_analyzer=_make_json_analyzer(),
            text_engine=text_engine,
        )
        result = await analyzer.analyze(body, ct_header)
        assert result.content_type == ContentType.MULTIPART_FORM_DATA

    @pytest.mark.asyncio
    async def test_image_url_description_scanned(self):
        from anonreq.multimodal.multipart_analyzer import MultipartAnalyzer

        text_engine = AsyncMock()
        text_engine.analyze_text = AsyncMock(return_value=[
            {"entity_type": "LOCATION", "start": 0, "end": 11, "score": 0.85},
        ])

        body, boundary = _build_multipart_body([
            ("text/plain", "description", "Photo at 123 Main St", {}),
        ])
        ct_header = f"multipart/form-data; boundary={boundary}"

        analyzer = MultipartAnalyzer(
            json_analyzer=_make_json_analyzer(),
            text_engine=text_engine,
        )
        result = await analyzer.analyze(body, ct_header)
        assert result.content_type == ContentType.MULTIPART_FORM_DATA

    @pytest.mark.asyncio
    async def test_empty_multipart_returns_empty_result(self):
        from anonreq.multimodal.multipart_analyzer import MultipartAnalyzer

        text_engine = AsyncMock()
        body, boundary = _build_multipart_body([])
        ct_header = f"multipart/form-data; boundary={boundary}"

        analyzer = MultipartAnalyzer(
            json_analyzer=_make_json_analyzer(),
            text_engine=text_engine,
        )
        result = await analyzer.analyze(body, ct_header)
        assert result.content_type == ContentType.MULTIPART_FORM_DATA
        assert result.entities == []

    @pytest.mark.asyncio
    async def test_binary_parts_are_skipped(self):
        from anonreq.multimodal.multipart_analyzer import MultipartAnalyzer

        text_engine = AsyncMock()
        text_engine.analyze_text = AsyncMock(return_value=[])

        body, boundary = _build_multipart_body([
            ("image/png", "image", b"\x89PNG\r\n\x1a\nbinarydata", {}),
        ])
        ct_header = f"multipart/form-data; boundary={boundary}"

        analyzer = MultipartAnalyzer(
            json_analyzer=_make_json_analyzer(),
            text_engine=text_engine,
        )
        result = await analyzer.analyze(body, ct_header)
        assert result.content_type == ContentType.MULTIPART_FORM_DATA
        assert result.entities == []

    @pytest.mark.asyncio
    async def test_metadata_fields_extracted(self):
        from anonreq.multimodal.multipart_analyzer import MultipartAnalyzer

        text_engine = AsyncMock()
        text_engine.analyze_text = AsyncMock(return_value=[])

        body, boundary = _build_multipart_body([
            ("text/plain", "alt_text", "A photo of someone", {}),
            ("text/plain", "caption", "At the office on Friday", {}),
        ])
        ct_header = f"multipart/form-data; boundary={boundary}"

        analyzer = MultipartAnalyzer(
            json_analyzer=_make_json_analyzer(),
            text_engine=text_engine,
        )
        result = await analyzer.analyze(body, ct_header)
        assert result.content_type == ContentType.MULTIPART_FORM_DATA
        assert text_engine.analyze_text.call_count >= 2

    @pytest.mark.asyncio
    async def test_handles_malformed_multipart(self):
        from anonreq.multimodal.multipart_analyzer import MultipartAnalyzer

        text_engine = AsyncMock()

        analyzer = MultipartAnalyzer(
            json_analyzer=_make_json_analyzer(),
            text_engine=text_engine,
        )
        result = await analyzer.analyze(b"not multipart data", "text/plain")
        assert result is not None
