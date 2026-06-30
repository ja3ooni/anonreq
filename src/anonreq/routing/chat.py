"""POST /v1/chat/completions route handler with pipeline orchestration.

Per PIPE-01:
- Accepts OpenAI-compatible payload
- Creates ``ProcessingContext`` from request
- Extracts text nodes via ``TextExtractor``
- Runs the full anonymization pipeline via ``PipelineManager``
- Returns the (potentially restored) response
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from structlog import get_logger

from anonreq.cache.manager import CacheManager
from anonreq.classification.engine import ClassificationEngine
from anonreq.classification.loader import ClassificationRuleLoader
from anonreq.config import settings
from anonreq.dependencies import auth_context
from anonreq.detection.exclusion_list import ExclusionList
from anonreq.detection.presidio_client import PresidioClient
from anonreq.detection.regex_detector import RegexDetector
from anonreq.detection.span_arbiter import SpanArbiter
from anonreq.exceptions import PipelineAbortError
from anonreq.models.chat import ChatCompletionResponse, ChatRequest
from anonreq.models.processing_context import ProcessingContext
from anonreq.models.request_context import RequestContext
from anonreq.pipeline.classification import ClassificationStage
from anonreq.pipeline.cleanup import CleanupStage
from anonreq.pipeline.detection import DetectionStage
from anonreq.pipeline.extraction import TextExtractor
from anonreq.pipeline.forwarding_guard import ForwardingGuard
from anonreq.pipeline.manager import PipelineManager
from anonreq.pipeline.provider import ProviderStage
from anonreq.pipeline.restoration import RestorationStage
from anonreq.pipeline.tokenization import TokenizationStage
from anonreq.tokenization.tokenizer import Tokenizer

router = APIRouter(prefix="/v1", tags=["chat"])
logger = get_logger("anonreq.routing.chat")


def build_pipeline(
    cache_manager: CacheManager,
    presidio_client: PresidioClient,
) -> PipelineManager:
    """Construct the full anonymization pipeline with all stages.

    Args:
        cache_manager: Initialised ``CacheManager`` for token mapping store.
        presidio_client: Initialised ``PresidioClient`` for NER analysis.

    Returns:
        A fully registered ``PipelineManager`` with all stages in the
        correct execution order per D-47.
    """
    # Load classification rules from YAML
    try:
        rules = ClassificationRuleLoader.from_yaml("config/classification.yaml")
    except FileNotFoundError:
        rules = []

    classification_engine = ClassificationEngine(
        rules=rules,
        default_action="PASS",
    )

    # Determine provider config
    provider_base_url = settings.PROVIDER_BASE_URL
    provider_api_key = settings.PROVIDER_API_KEY or settings.API_KEY
    provider_timeout = settings.REQUEST_TIMEOUT_SECONDS

    # Create pipeline stages
    stages = [
        ClassificationStage(engine=classification_engine),
        DetectionStage(
            regex_detector=RegexDetector(),
            presidio_client=presidio_client,
            span_arbiter=SpanArbiter(),
            exclusion_list=ExclusionList(),
        ),
        TokenizationStage(
            tokenizer=Tokenizer(),
            cache_manager=cache_manager,
        ),
        ForwardingGuard(),
        ProviderStage(
            openai_base_url=provider_base_url,
            api_key=provider_api_key,
            timeout=provider_timeout,
        ),
        RestorationStage(),
        CleanupStage(cache_manager=cache_manager),
    ]

    manager = PipelineManager()
    for stage in stages:
        manager.register(stage)

    return manager


@router.post("/chat/completions")
async def chat_completions(
    body: ChatRequest,
    request: Request,
    response: Response,
    ctx: RequestContext = Depends(auth_context),
) -> dict[str, Any]:
    """Handle a non-streaming chat completion request.

    The request flows through the full anonymization pipeline:
    1. Text extraction → 2. Classification → 3. Detection (if ANONYMIZE)
    → 4. Tokenization → 5. ForwardingGuard → 6. Provider call
    → 7. Restoration → 8. Cleanup + Audit

    Args:
        body: The parsed ``ChatRequest`` body.
        request: The FastAPI ``Request`` (used for app state access).
        response: The FastAPI ``Response`` (used for setting custom headers).
        ctx: The ``RequestContext`` from auth dependency.

    Returns:
        The response dict (either anonymized-and-restored or pass-through).

    Raises:
        HTTPException: With appropriate status code on pipeline failure.
    """
    # Access pipeline from app state
    pipeline: PipelineManager = request.app.state.pipeline

    # Create ProcessingContext
    proc_ctx = ProcessingContext(
        request_id=ctx.request_id,
        tenant_id=getattr(ctx, "tenant_id", "default"),
        context_id=uuid4().hex,
    )

    # Populate context with original request and text nodes
    proc_ctx.original_request = body.model_dump()
    proc_ctx.text_nodes = TextExtractor.extract(proc_ctx.original_request)

    # Run the pipeline
    proc_ctx = await pipeline.run(proc_ctx)

    # ── Handle errors (fail-secure) ───────────────────────────────────────
    if proc_ctx.has_errors():
        last_error = proc_ctx.errors[-1]

        if isinstance(last_error, PipelineAbortError):
            if last_error.status_code in (403, 404, 501):
                raise HTTPException(
                    status_code=last_error.status_code,
                    detail=last_error.message,
                )
            elif last_error.status_code == 504:
                raise HTTPException(
                    status_code=504,
                    detail="Upstream provider timeout",
                )
            elif last_error.status_code == 503:
                raise HTTPException(
                    status_code=503,
                    detail="Service temporarily unavailable",
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Internal gateway error",
                )
        else:
            raise HTTPException(
                status_code=500,
                detail="Internal gateway error",
            )

    # ── Determine response body ───────────────────────────────────────────
    action = proc_ctx.classification_result.get("action", "PASS") if proc_ctx.classification_result else "PASS"

    if action in ("BLOCK",):
        raise HTTPException(status_code=403, detail="Request blocked by policy")

    if action == "ROUTE_LOCAL":
        raise HTTPException(status_code=501, detail="ROUTE_LOCAL not yet implemented")

    # Determine response data
    if action == "ANONYMIZE" and proc_ctx.restored_response:
        response_data = proc_ctx.restored_response
    elif proc_ctx.provider_response:
        response_data = proc_ctx.provider_response
    elif action == "PASS" and proc_ctx.provider_response:
        response_data = proc_ctx.provider_response
    else:
        raise HTTPException(status_code=500, detail="No response produced")

    # Build response headers
    entity_count = len(proc_ctx.detections) if proc_ctx.detections else 0
    was_anonymized = action == "ANONYMIZE"

    # Set custom headers
    response.headers["X-AnonReq-Request-ID"] = proc_ctx.request_id
    response.headers["X-AnonReq-Processed"] = "true" if was_anonymized else "false"
    response.headers["X-AnonReq-Entity-Count"] = str(entity_count)

    # Serialize response
    validated = ChatCompletionResponse.model_validate(response_data)
    return validated.model_dump(exclude_none=True)
