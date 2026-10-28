"""Admin-only anonymization preview.

Runs the gateway's detection and tokenization stages and returns the
sanitized text plus entity offsets. It does not call a provider, write
the token cache, or append audit / anonymization events.

Disabled unless ``ANONREQ_DEBUG_PREVIEW_ENABLED`` is true. A disabled
route responds 404 before authentication.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field, model_validator

from anonreq.admin.auth import require_administrator
from anonreq.config import settings
from anonreq.debug.offsets import entities_from_context
from anonreq.models.classification import ClassificationLevel
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.extraction import TextExtractor
from anonreq.pipeline.tokenization import TokenizationStage
from anonreq.policy.models import PolicyAction
from anonreq.routing.chat import _raise_for_pipeline_errors, build_preview_pipeline
from anonreq.state import get_app_state

router = APIRouter(prefix="/v1/debug", tags=["debug"])


class PreviewMessage(BaseModel):
    """One OpenAI-style chat message."""

    role: str = Field(min_length=1)
    content: str


class AnonymizePreviewRequest(BaseModel):
    """Preview body. Provide ``prompt``, ``messages``, or both."""

    prompt: str | None = None
    messages: list[PreviewMessage] | None = None
    tenant_id: str | None = None
    tenant: str | None = None
    policy: str | None = None

    @model_validator(mode="after")
    def _require_text(self) -> AnonymizePreviewRequest:
        has_prompt = bool(self.prompt and self.prompt.strip())
        has_messages = bool(self.messages)
        if not has_prompt and not has_messages:
            raise ValueError("prompt or messages is required")
        return self


class PreviewEntity(BaseModel):
    """One detected span and the token that replaced it."""

    entity_type: str
    span: str
    token: str
    score: float
    start: int
    end: int
    start_utf16: int
    end_utf16: int
    token_start: int
    token_end: int
    token_start_utf16: int
    token_end_utf16: int
    message_index: int | None = None


class AnonymizedMessage(BaseModel):
    """A chat message after tokenization."""

    role: str
    content: str
    message_index: int


class AnonymizePreviewResponse(BaseModel):
    """Side-effect-free anonymization preview.

    ``classification`` matches ``X-AnonReq-Classification`` and
    ``highest_entity`` matches ``X-AnonReq-Highest-Entity``.
    ``anonymized_text`` is set when ``prompt`` was sent.
    ``anonymized_messages`` is set when ``messages`` was sent.
    The unused field is JSON null. ``message_index`` on an entity is
    null for prompt spans and the source message index otherwise.
    """

    request_id: str
    locale: str
    classification: str
    highest_entity: str
    anonymized_text: str | None = None
    anonymized_messages: list[AnonymizedMessage] | None = None
    entities: list[PreviewEntity]


async def require_preview_admin(
    request: Request,
    authorization: str | None = Header(None),
) -> None:
    """404 when preview is off, otherwise require an administrator."""
    if not settings.DEBUG_PREVIEW_ENABLED:
        raise HTTPException(status_code=404, detail="Not Found")
    await require_administrator(request, authorization)


def _tenant_id(request: Request, body: AnonymizePreviewRequest) -> str:
    if body.tenant_id:
        return body.tenant_id
    if body.tenant:
        return body.tenant
    header_tenant = getattr(request.state, "tenant_id", None)
    if isinstance(header_tenant, str) and header_tenant:
        return header_tenant
    return "default"


async def _enforce_policy(request: Request, tenant_id: str, policy_id: str | None) -> None:
    """Read-only policy gate. Does not write audit, usage, or spend."""
    if not policy_id:
        return
    store = get_app_state(request.app).policy_store
    if store is None:
        raise HTTPException(status_code=503, detail="Policy store not available")
    rule = await store.get_policy(policy_id, tenant_id)
    if rule is None or not rule.enabled:
        raise HTTPException(status_code=404, detail="Policy not found")
    if rule.action == PolicyAction.BLOCK:
        raise HTTPException(status_code=403, detail="Request blocked by policy")
    if rule.action == PolicyAction.ROUTE_LOCAL:
        raise HTTPException(status_code=501, detail="ROUTE_LOCAL not yet implemented")


def _classification_of(ctx: ProcessingContext) -> tuple[str, str, int]:
    result = ctx.classification_result_v2
    if result is None:
        return "INTERNAL", "", ClassificationLevel.INTERNAL
    return result.highest.name, result.highest_entity or "", int(result.highest)


async def _run_preview(
    request: Request,
    chat_body: dict[str, Any],
    *,
    tenant_id: str,
    request_id: str,
    include_message_index: bool,
) -> tuple[ProcessingContext, list[dict[str, Any]]]:
    state = get_app_state(request.app)
    presidio = state.presidio_client
    if presidio is None:
        raise HTTPException(status_code=503, detail="Detection service not initialized")

    pipeline = build_preview_pipeline(
        state.cache_manager,
        presidio,
        locale_negotiator=state.locale_negotiator,
        recognizer_merger=state.recognizer_merger,
        checksum_registry=state.checksum_registry,
    )
    ctx = ProcessingContext(
        request_id=request_id,
        tenant_id=tenant_id,
        context_id=uuid4().hex,
    )
    ctx.original_request = chat_body
    ctx.text_nodes = TextExtractor.extract(chat_body)
    ctx.locale_header = request.headers.get("X-AnonReq-Locale")
    ctx.client_classification = getattr(request.state, "client_classification", None)
    ctx.model = chat_body.get("model") if isinstance(chat_body.get("model"), str) else None
    # Do not attach audit_chain. Cleanup is not in this pipeline.

    ctx = await pipeline.run(ctx)
    _raise_for_pipeline_errors(ctx)

    token_stage = next(
        (stage for stage in pipeline.stages if isinstance(stage, TokenizationStage)),
        None,
    )
    value_to_token = token_stage._tokenizer.get_mapping() if token_stage is not None else {}
    transformed = (ctx.transformed_request or {}).get("messages") or []
    entities = entities_from_context(
        ctx.text_nodes,
        ctx.detections,
        transformed,
        value_to_token,
        include_message_index=include_message_index,
    )
    return ctx, entities


def _anonymized_prompt(ctx: ProcessingContext, prompt: str) -> str:
    messages = (ctx.transformed_request or {}).get("messages") or []
    if messages and isinstance(messages[0], dict):
        content = messages[0].get("content")
        if isinstance(content, str):
            return content
    return prompt


def _anonymized_messages(
    ctx: ProcessingContext,
    messages: list[PreviewMessage],
) -> list[AnonymizedMessage]:
    transformed = (ctx.transformed_request or {}).get("messages") or []
    rendered: list[AnonymizedMessage] = []
    for index, message in enumerate(messages):
        content = message.content
        if index < len(transformed) and isinstance(transformed[index], dict):
            updated = transformed[index].get("content")
            if isinstance(updated, str):
                content = updated
        rendered.append(
            AnonymizedMessage(role=message.role, content=content, message_index=index)
        )
    return rendered


@router.post(
    "/anonymize-preview",
    response_model=AnonymizePreviewResponse,
    dependencies=[Depends(require_preview_admin)],
)
async def anonymize_preview(
    body: AnonymizePreviewRequest,
    request: Request,
    response: Response,
) -> AnonymizePreviewResponse:
    """Preview detection and tokenization without persisting anything."""
    tenant_id = _tenant_id(request, body)
    await _enforce_policy(request, tenant_id, body.policy)

    request_id = getattr(request.state, "request_id", None) or f"req_{uuid4().hex[:24]}"
    contexts: list[ProcessingContext] = []
    entities: list[PreviewEntity] = []
    anonymized_text: str | None = None
    anonymized_messages: list[AnonymizedMessage] | None = None

    if body.prompt and body.prompt.strip():
        ctx, found = await _run_preview(
            request,
            {
                "model": "preview",
                "messages": [{"role": "user", "content": body.prompt}],
            },
            tenant_id=tenant_id,
            request_id=request_id,
            include_message_index=False,
        )
        contexts.append(ctx)
        anonymized_text = _anonymized_prompt(ctx, body.prompt)
        entities.extend(PreviewEntity.model_validate(item) for item in found)

    if body.messages:
        ctx, found = await _run_preview(
            request,
            {
                "model": "preview",
                "messages": [message.model_dump() for message in body.messages],
            },
            tenant_id=tenant_id,
            request_id=request_id,
            include_message_index=True,
        )
        contexts.append(ctx)
        anonymized_messages = _anonymized_messages(ctx, body.messages)
        entities.extend(PreviewEntity.model_validate(item) for item in found)

    locale = "universal"
    classification = "INTERNAL"
    highest_entity = ""
    best_rank = -1
    for ctx in contexts:
        if locale == "universal":
            negotiated = ctx.audit_metadata.get("locale")
            if isinstance(negotiated, str) and negotiated:
                locale = negotiated
        name, entity, rank = _classification_of(ctx)
        if rank > best_rank:
            best_rank = rank
            classification = name
            highest_entity = entity

    response.headers["X-AnonReq-Request-ID"] = request_id
    response.headers["X-AnonReq-Classification"] = classification
    response.headers["X-AnonReq-Highest-Entity"] = highest_entity

    return AnonymizePreviewResponse(
        request_id=request_id,
        locale=locale,
        classification=classification,
        highest_entity=highest_entity,
        anonymized_text=anonymized_text,
        anonymized_messages=anonymized_messages,
        entities=entities,
    )
