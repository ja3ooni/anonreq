from __future__ import annotations

from typing import Any

from anonreq.multimodal.limits import PayloadLimits, validate_payload_limits
from anonreq.multimodal.models import AnalyzerResult, ContentType, UnifiedDetectionResult
from anonreq.multimodal.router import LocalRouter, RouteDecisionType


_MIME_MAP: dict[str, ContentType] = {
    "text/plain": ContentType.TEXT_PLAIN,
    "application/json": ContentType.APPLICATION_JSON,
    "multipart/form-data": ContentType.MULTIPART_FORM_DATA,
}


class ContentTypeDispatcher:
    def __init__(
        self,
        json_analyzer: Any,
        multipart_analyzer: Any,
        text_analyzer: Any | None = None,
        limits: PayloadLimits | None = None,
        local_router: LocalRouter | None = None,
    ) -> None:
        self._json_analyzer = json_analyzer
        self._multipart_analyzer = multipart_analyzer
        self._text_analyzer = text_analyzer
        self._limits = limits or PayloadLimits()
        self._local_router = local_router or LocalRouter()

    def _parse_content_type(self, header: str) -> tuple[ContentType, str]:
        if not header or not header.strip():
            return ContentType.TEXT_PLAIN, "text/plain"
        raw_type = header.split(";")[0].strip().lower()
        ct = _MIME_MAP.get(raw_type, ContentType.UNKNOWN)
        return ct, raw_type

    async def dispatch(
        self,
        content_type: str,
        body: bytes,
        ctx: Any,
    ) -> AnalyzerResult:
        ct, raw_type = self._parse_content_type(content_type)

        if ct == ContentType.UNKNOWN:
            route_decision = self._local_router.route(raw_type, body)
            return AnalyzerResult(
                source_analyzer="dispatcher",
                content_type=ContentType.UNKNOWN,
                detection_result=UnifiedDetectionResult(
                    content_type=ContentType.UNKNOWN,
                    analyzer_metadata={
                        "raw_type": raw_type,
                        "route_decision": route_decision.decision.value,
                        "route_reason": route_decision.reason,
                    },
                ),
                should_process=False,
                action=route_decision.decision.value,
            )

        limit_result = validate_payload_limits(ct, body, self._limits)
        if not limit_result.passed:
            return AnalyzerResult(
                source_analyzer="dispatcher",
                content_type=ct,
                detection_result=UnifiedDetectionResult(
                    content_type=ct,
                    analyzer_metadata={
                        "limit_check": limit_result.model_dump(),
                        "raw_type": raw_type,
                    },
                ),
                should_process=False,
                action=limit_result.action,
            )

        if ct == ContentType.TEXT_PLAIN:
            if self._text_analyzer is not None:
                dr = await self._text_analyzer.analyze(body)
            else:
                dr = UnifiedDetectionResult(
                    content_type=ContentType.TEXT_PLAIN,
                    analyzer_metadata={"raw_type": raw_type},
                )
            return AnalyzerResult(
                source_analyzer="text_analyzer",
                content_type=ContentType.TEXT_PLAIN,
                detection_result=dr,
            )

        if ct == ContentType.APPLICATION_JSON:
            dr = await self._json_analyzer.analyze(body)
            return AnalyzerResult(
                source_analyzer="json_analyzer",
                content_type=ContentType.APPLICATION_JSON,
                detection_result=dr,
            )

        if ct == ContentType.MULTIPART_FORM_DATA:
            dr = await self._multipart_analyzer.analyze(body, content_type)
            return AnalyzerResult(
                source_analyzer="multipart_analyzer",
                content_type=ContentType.MULTIPART_FORM_DATA,
                detection_result=dr,
            )

        # Fallback — should not be reachable after LocalRouter integration
        return AnalyzerResult(
            source_analyzer="dispatcher",
            content_type=ContentType.UNKNOWN,
            detection_result=UnifiedDetectionResult(
                content_type=ContentType.UNKNOWN,
                analyzer_metadata={"raw_type": raw_type},
            ),
            should_process=False,
            action="ROUTE_LOCAL",
        )
