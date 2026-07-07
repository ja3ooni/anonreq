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
from fastapi.responses import StreamingResponse
from structlog import get_logger

from anonreq.cache.manager import CacheManager
from anonreq.classification.engine import ClassificationEngine
from anonreq.classification.loader import ClassificationRuleLoader
from anonreq.config import settings
from anonreq.config.restricted_names import RestrictedNamesManager
from anonreq.dependencies import auth_context
from anonreq.admin.routes import registry as admin_config_registry
from anonreq.detection.exclusion_list import ExclusionList
from anonreq.detection.pipeline import load_mnpi_recognizers
from anonreq.detection.presidio_client import PresidioClient
from anonreq.detection.regex_detector import RegexDetector
from anonreq.detection.span_arbiter import SpanArbiter
from anonreq.exceptions import PipelineAbortError
from anonreq.locale.checksum import ChecksumValidatorRegistry
from anonreq.locale.merger import RecognizerMerger
from anonreq.locale.negotiator import LocaleNegotiator
from anonreq.locale.registry import LocaleRegistry
from anonreq.models.chat import ChatCompletionResponse, ChatRequest
from anonreq.models.processing_context import ProcessingContext
from anonreq.models.request_context import RequestContext
from anonreq.providers.registry import ProviderNotFoundError, ProviderRegistry
from anonreq.pipeline.classification import ClassificationStage
from anonreq.pipeline.cleanup import CleanupStage
from anonreq.pipeline.detection import DetectionStage
from anonreq.pipeline.extraction import TextExtractor
from anonreq.pipeline.forwarding_guard import ForwardingGuard
from anonreq.pipeline.manager import PipelineManager
from anonreq.pipeline.provider import ProviderStage
from anonreq.pipeline.restoration import RestorationStage
from anonreq.pipeline.stages import (
    LocaleNegotiationStage,
    SensitivityClassificationStage,
    PolicyEnforcementStage,
)
from anonreq.pipeline.tokenization import TokenizationStage
from anonreq.routing.alias_registry import AliasNotFoundError, AliasRegistry
from anonreq.streaming.cleanup import SessionCleanup
from anonreq.streaming.emitter import SSEEmitter
from anonreq.streaming.restoration import StreamingRestorationStage
from anonreq.streaming.stream_event import EventType, FinishReason, StreamEvent
from anonreq.streaming.tail_buffer import TailBuffer
from anonreq.tokenization.tokenizer import Tokenizer

router = APIRouter(prefix="/v1", tags=["chat"])
logger = get_logger("anonreq.routing.chat")


def build_pre_provider_pipeline(
    cache_manager: CacheManager,
    presidio_client: PresidioClient,
    locale_negotiator: LocaleNegotiator | None = None,
    recognizer_merger: RecognizerMerger | None = None,
    checksum_registry: ChecksumValidatorRegistry | None = None,
    app_state: Any = None,
) -> PipelineManager:
    """Construct stages shared by streaming and non-streaming requests."""
    try:
        rules = ClassificationRuleLoader.from_yaml("config/classification.yaml")
    except FileNotFoundError:
        rules = []

    classification_engine = ClassificationEngine(
        rules=rules,
        default_action="PASS",
    )

    if locale_negotiator is None or recognizer_merger is None:
        checksum_registry = checksum_registry or ChecksumValidatorRegistry()
        locale_registry = LocaleRegistry(checksum_registry=checksum_registry)
        universal = locale_registry.get("en")
        if universal is None:
            raise RuntimeError("Universal locale bundle 'en' is required")
        locale_negotiator = LocaleNegotiator(locale_registry)
        recognizer_merger = RecognizerMerger(universal)

    restricted_names_mgr = RestrictedNamesManager(
        config_path="config/restricted_names.yaml",
    )

    stages = [
        ClassificationStage(engine=classification_engine),
        LocaleNegotiationStage(
            negotiator=locale_negotiator,
            merger=recognizer_merger,
        ),
        DetectionStage(
            regex_detector=RegexDetector(),
            presidio_client=presidio_client,
            span_arbiter=SpanArbiter(),
            exclusion_list=ExclusionList(),
            checksum_registry=checksum_registry,
            config_registry=admin_config_registry,
            mnpi_recognizers=load_mnpi_recognizers(
                config_path="config/mnpi_recognizers.yaml",
                restricted_names_mgr=restricted_names_mgr,
            ),
        ),
        SensitivityClassificationStage(),
        PolicyEnforcementStage(app_state=app_state),
        TokenizationStage(
            tokenizer=Tokenizer(),
            cache_manager=cache_manager,
        ),
        ForwardingGuard(),
    ]

    manager = PipelineManager()
    for stage in stages:
        manager.register(stage)

    return manager


def build_pipeline(
    cache_manager: CacheManager,
    presidio_client: PresidioClient,
    alias_registry: Any | None = None,
    locale_negotiator: LocaleNegotiator | None = None,
    recognizer_merger: RecognizerMerger | None = None,
    checksum_registry: ChecksumValidatorRegistry | None = None,
    app_state: Any = None,
) -> PipelineManager:
    """Construct the full anonymization pipeline with all stages."""
    # Determine provider config
    provider_base_url = settings.PROVIDER_BASE_URL
    provider_api_key = settings.PROVIDER_API_KEY or settings.API_KEY
    provider_timeout = settings.REQUEST_TIMEOUT_SECONDS

    # Create pipeline stages
    stages = build_pre_provider_pipeline(
        cache_manager,
        presidio_client,
        locale_negotiator=locale_negotiator,
        recognizer_merger=recognizer_merger,
        checksum_registry=checksum_registry,
        app_state=app_state,
    ).stages + [
        ProviderStage(
            openai_base_url=provider_base_url,
            api_key=provider_api_key,
            timeout=provider_timeout,
            alias_registry=alias_registry,
        ),
        RestorationStage(),
        CleanupStage(cache_manager=cache_manager),
    ]

    manager = PipelineManager()
    for stage in stages:
        manager.register(stage)

    return manager


def _raise_for_pipeline_errors(proc_ctx: ProcessingContext) -> None:
    if not proc_ctx.has_errors():
        return

    last_error = proc_ctx.errors[-1]
    if isinstance(last_error, PipelineAbortError):
        if last_error.status_code in (400, 403, 404, 501, 451):
            raise HTTPException(
                status_code=last_error.status_code,
                detail=last_error.message,
            )
        if last_error.status_code == 504:
            raise HTTPException(status_code=504, detail="Upstream provider timeout")
        if last_error.status_code == 503:
            raise HTTPException(status_code=503, detail="Service temporarily unavailable")
        raise HTTPException(status_code=500, detail="Internal gateway error")

    raise HTTPException(status_code=500, detail="Internal gateway error")


def _new_processing_context(
    body: ChatRequest,
    ctx: RequestContext,
    request: Request | None = None,
) -> ProcessingContext:
    proc_ctx = ProcessingContext(
        request_id=ctx.request_id,
        tenant_id=getattr(ctx, "tenant_id", "default"),
        context_id=uuid4().hex,
    )
    proc_ctx.original_request = body.model_dump()
    proc_ctx.text_nodes = TextExtractor.extract(proc_ctx.original_request)
    if request is not None:
        proc_ctx.locale_header = request.headers.get("X-AnonReq-Locale")
        proc_ctx.client_classification = getattr(request.state, "client_classification", None)
        active_presets = getattr(request.app.state, "active_compliance_presets", [])
        if active_presets:
            proc_ctx.audit_metadata["compliance_preset"] = ",".join(active_presets)
    return proc_ctx


async def _stream_chat_completions(
    body: ChatRequest,
    request: Request,
    ctx: RequestContext,
) -> StreamingResponse:
    cache_manager: CacheManager = request.app.state.cache_manager
    presidio_client: PresidioClient = request.app.state.presidio_client
    alias_registry: AliasRegistry = request.app.state.alias_registry
    provider_registry: ProviderRegistry = request.app.state.provider_registry
    locale_negotiator: LocaleNegotiator = request.app.state.locale_negotiator
    recognizer_merger: RecognizerMerger = request.app.state.recognizer_merger
    checksum_registry: ChecksumValidatorRegistry = request.app.state.checksum_registry

    proc_ctx = _new_processing_context(body, ctx, request=request)
    request.state.ctx = proc_ctx
    pre_provider = build_pre_provider_pipeline(
        cache_manager,
        presidio_client,
        locale_negotiator=locale_negotiator,
        recognizer_merger=recognizer_merger,
        checksum_registry=checksum_registry,
    )
    proc_ctx = await pre_provider.run(proc_ctx)
    _raise_for_pipeline_errors(proc_ctx)

    action = proc_ctx.classification_result.get("action", "PASS") if proc_ctx.classification_result else "PASS"
    if action == "BLOCK":
        raise HTTPException(status_code=403, detail="Request blocked by policy")
    if action == "ROUTE_LOCAL":
        raise HTTPException(status_code=501, detail="ROUTE_LOCAL not yet implemented")

    provider_request_body = (
        proc_ctx.transformed_request
        if action == "ANONYMIZE" and proc_ctx.transformed_request
        else proc_ctx.original_request
    )
    provider_request_body = dict(provider_request_body or {})
    provider_request_body["stream"] = True

    try:
        alias = alias_registry.resolve(provider_request_body["model"])
        provider_request_body["model"] = alias.model
        proc_ctx.provider = alias.provider
        proc_ctx.model = alias.model

        adapter = provider_registry.get_adapter(alias.provider)
        if not adapter.capabilities.streaming:
            raise HTTPException(status_code=400, detail=f"Provider '{alias.provider}' does not support streaming")

        proc_ctx.original_request = provider_request_body
        provider_request = adapter.translate_request(proc_ctx)
    except AliasNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ProviderNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="Provider configuration error",
        )

    emitter = SSEEmitter()

    async def stream_generator():
        tail_buffer = TailBuffer()
        restoration = StreamingRestorationStage(cache_manager)
        cleanup = SessionCleanup(
            cache_manager=cache_manager,
            tenant_id=proc_ctx.tenant_id,
            session_id=proc_ctx.context_id,
            audit_logger=logger,
        )
        terminal_state = "FINISH"

        await restoration.start_session(proc_ctx.tenant_id, proc_ctx.context_id)

        try:
            async for event in adapter.stream_events(provider_request):
                if await request.is_disconnected():
                    terminal_state = "CLIENT_DISCONNECT"
                    break

                if event.event_type == EventType.REASONING_DELTA:
                    continue

                if event.event_type == EventType.FINISH:
                    remaining = tail_buffer.flush_remaining()
                    if remaining:
                        yield emitter.emit(restoration.restore_text(remaining))
                    yield emitter.emit(event)
                    yield emitter.close_frame()
                    proc_ctx.stream_finished = True
                    return

                if event.event_type == EventType.ERROR:
                    terminal_state = "PROVIDER_ERROR"
                    yield emitter.emit(StreamEvent(
                        event_type=EventType.ERROR,
                        provider=proc_ctx.provider or "unknown",
                        metadata={"message": "stream error", "type": "provider_error"},
                    ))
                    yield emitter.close_frame()
                    return

                async for chunk in tail_buffer.ingest(event):
                    restored = restoration.restore_text(chunk)
                    if restored:
                        yield emitter.emit(restored)

            remaining = tail_buffer.flush_remaining()
            if remaining and terminal_state != "CLIENT_DISCONNECT":
                yield emitter.emit(restoration.restore_text(remaining))
                yield emitter.emit(StreamEvent(
                    event_type=EventType.FINISH,
                    provider=proc_ctx.provider or "unknown",
                    finish_reason=FinishReason.STOP,
                ))
                yield emitter.close_frame()
        except PipelineAbortError as exc:
            terminal_state = "PROVIDER_ERROR"
            yield emitter.emit(StreamEvent(
                event_type=EventType.ERROR,
                provider=proc_ctx.provider or "unknown",
                metadata={"message": "stream error", "type": "provider_error"},
            ))
            yield emitter.close_frame()
        except Exception:
            terminal_state = "PROVIDER_ERROR"
            yield emitter.emit(StreamEvent(
                event_type=EventType.ERROR,
                provider=proc_ctx.provider or "unknown",
                metadata={"message": "stream error", "type": "provider_error"},
            ))
            yield emitter.close_frame()
        finally:
            tail_buffer.terminate()
            restoration.close_session()
            proc_ctx.terminal_state = terminal_state
            await cleanup.cleanup(terminal_state)

    headers = {
        **emitter.get_headers(),
        "X-AnonReq-Request-ID": proc_ctx.request_id,
        "X-AnonReq-Processed": "true" if action == "ANONYMIZE" else "false",
        "X-AnonReq-Entity-Count": str(len(proc_ctx.detections or [])),
    }
    if proc_ctx.classification_result_v2:
        headers["X-AnonReq-Classification"] = proc_ctx.classification_result_v2.highest.name
        headers["X-AnonReq-Highest-Entity"] = proc_ctx.classification_result_v2.highest_entity or ""

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers=headers,
    )


@router.post("/chat/completions", response_model=None)
async def chat_completions(
    body: ChatRequest,
    request: Request,
    response: Response,
    ctx: RequestContext = Depends(auth_context),
) -> Any:
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
    if body.stream:
        return await _stream_chat_completions(body, request, ctx)

    # Access pipeline from app state
    pipeline: PipelineManager = request.app.state.pipeline
    proc_ctx = _new_processing_context(body, ctx, request=request)
    request.state.ctx = proc_ctx

    # Run the pipeline
    proc_ctx = await pipeline.run(proc_ctx)

    # ── Handle errors (fail-secure) ───────────────────────────────────────
    _raise_for_pipeline_errors(proc_ctx)

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
    if proc_ctx.classification_result_v2:
        response.headers["X-AnonReq-Classification"] = proc_ctx.classification_result_v2.highest.name
        response.headers["X-AnonReq-Highest-Entity"] = proc_ctx.classification_result_v2.highest_entity or ""

    # Serialize response
    validated = ChatCompletionResponse.model_validate(response_data)
    return validated.model_dump(exclude_none=True)
