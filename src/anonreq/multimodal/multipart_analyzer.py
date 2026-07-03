from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

import structlog
from python_multipart import create_form_parser
from python_multipart.multipart import File, parse_options_header

from anonreq.multimodal.json_analyzer import JsonAnalyzer
from anonreq.multimodal.models import ContentType, UnifiedDetectionResult

logger = structlog.get_logger("anonreq.multimodal.multipart_analyzer")

_TEXT_TYPES = {"text/plain", "text/html", "text/markdown", "text/csv", "application/x-www-form-urlencoded"}

_BINARY_TYPES = {
    "image/png", "image/jpeg", "image/gif", "image/webp",
    "application/octet-stream", "application/pdf",
    "audio/mpeg", "audio/wav", "video/mp4",
}


@dataclass
class _ParsedPart:
    kind: str
    field_name: str
    content_type: str
    data: bytes
    file_name: str = ""


class MultipartAnalyzer:
    def __init__(
        self,
        json_analyzer: JsonAnalyzer,
        text_engine: Any | None = None,
    ) -> None:
        self._json_analyzer = json_analyzer
        self._text_engine = text_engine

    async def analyze(
        self,
        body: bytes,
        content_type_header: str,
    ) -> UnifiedDetectionResult:
        result = UnifiedDetectionResult(content_type=ContentType.MULTIPART_FORM_DATA)

        try:
            parts = self._parse_parts(body, content_type_header)
            if not parts:
                return result

            all_entities: list[dict] = []

            for part in parts:
                if part.kind == "field":
                    await self._process_field(part, all_entities)
                elif part.kind == "file":
                    self._process_file(part, all_entities)

            result.entities = all_entities
        except Exception as exc:
            logger.error("multipart.analyze_error", error=str(exc))
            result.analyzer_metadata = {"error": str(exc)}

        return result

    def _parse_parts(self, body: bytes, content_type_header: str) -> list[_ParsedPart]:
        parts: list[_ParsedPart] = []

        def on_field(field: Any) -> None:
            field_name = field.field_name.decode("utf-8", errors="replace") if isinstance(field.field_name, bytes) else (field.field_name or "unknown")
            content_type = field.content_type or "text/plain"
            data = field.value if isinstance(field.value, bytes) else (field.value.encode("utf-8") if field.value else b"")
            parts.append(_ParsedPart(kind="field", field_name=field_name, content_type=content_type, data=data))

        def on_file(file: File) -> None:
            field_name = file.field_name.decode("utf-8", errors="replace") if isinstance(file.field_name, bytes) else (file.field_name or "unknown")
            content_type = file.content_type or "application/octet-stream"
            file_name = file.file_name.decode("utf-8", errors="replace") if isinstance(file.file_name, bytes) else (file.file_name or "")
            data = _read_file_data(file)
            parts.append(_ParsedPart(kind="file", field_name=field_name, content_type=content_type, data=data, file_name=file_name))

        ct_header_value = content_type_header.encode("utf-8") if isinstance(content_type_header, str) else content_type_header
        headers = {"Content-Type": ct_header_value}
        parser = create_form_parser(headers, on_field, on_file)

        stream = io.BytesIO(body)
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            parser.write(chunk)
        parser.finalize()

        return parts

    async def _process_field(self, part: _ParsedPart, entities: list[dict]) -> None:
        content_type = part.content_type
        field_name = part.field_name
        data = part.data

        if content_type == "application/json":
            dr = await self._json_analyzer.analyze(data)
            for entity in dr.entities:
                entity["part_name"] = field_name
            entities.extend(dr.entities)
            return

        if content_type in _BINARY_TYPES or _is_binary_content(data):
            logger.info("multipart.skipping_binary", part_name=field_name, content_type=content_type)
            return

        if self._text_engine is not None:
            text = data.decode("utf-8", errors="replace")
            detections = await self._text_engine.analyze_text(text)
            for d in detections:
                d["part_name"] = field_name
                d["content_type"] = content_type
            entities.extend(detections)

    def _process_file(self, part: _ParsedPart, entities: list[dict]) -> None:
        content_type = part.content_type
        field_name = part.field_name
        file_name = part.file_name

        if content_type in _BINARY_TYPES:
            logger.info("multipart.skipping_binary_file", part_name=field_name, file_name=file_name, content_type=content_type)
            return

        if file_name:
            entities.append({
                "entity_type": "FILENAME",
                "value": file_name,
                "score": 0.5,
                "part_name": field_name,
                "content_type": content_type,
            })


def _read_file_data(file: File) -> bytes:
    chunks: list[bytes] = []
    if hasattr(file, "file_object") and file.file_object is not None:
        file.file_object.seek(0)
        while True:
            chunk = file.file_object.read(65536)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks)


def _is_binary_content(data: bytes) -> bool:
    if not data:
        return False
    sample = data[:1024]
    text_characters = sum(1 for byte in sample if 32 <= byte <= 126 or byte in (9, 10, 13))
    return (text_characters / len(sample)) < 0.7 if sample else False
