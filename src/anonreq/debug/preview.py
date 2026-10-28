"""Admin-only anonymization preview.

Runs the gateway's detection and tokenization stages and returns the
sanitized text plus entity offsets. It does not call a provider, write
the token cache, or append audit / anonymization events.

Disabled unless ``ANONREQ_DEBUG_PREVIEW_ENABLED`` is true. A disabled
route responds 404 before authentication.
"""

from __future__ import annotations

import time
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
from anonreq.services.tenant_scope import resolve_scoped_tenant
from anonreq.state import get_app_state

_NO_STORE_HEADERS = {"Cache-Control": "no-store"}

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


class PreviewRateLimiter:
    """In-memory per-admin preview limit. Does not touch the token cache."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}

    def reset(self) -> None:
        self._hits.clear()

    def check(self, principal_id: str) -> None:
        limit = settings.DEBUG_PREVIEW_RPM
        if limit <= 0:
            return
        now = time.monotonic()
        recent = [stamp for stamp in self._hits.get(principal_id, []) if now - stamp < 60.0]
        if len(recent) >= limit:
            raise HTTPException(
                429,
                detail="Preview rate limit exceeded",
                headers=_NO_STORE_HEADERS,
            )
        recent.append(now)
        self._hits[principal_id] = recent


preview_rate_limiter = PreviewRateLimiter()


async def require_preview_admin(
    request: Request,
    authorization: str | None = Header(None),
) -> None:
    """404 when preview is off, otherwise require an administrator."""
    if not settings.DEBUG_PREVIEW_ENABLED:
        raise HTTPException(404, detail="Not Found", headers=_NO_STORE_HEADERS)
    try:
        await require_administrator(request, authorization)
    except HTTPException as exc:
        # Auth failures (401/403) on the preview are never cached either.
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers={**(exc.headers or {}), **_NO_STORE_HEADERS},
        ) from None


def _scoped_tenant(request: Request, body: AnonymizePreviewRequest) -> str:
    """Bind the preview to the caller tenant. A mismatch is HTTP 403."""
    if (
        body.tenant_id
        and body.tenant
        and body.tenant_id.strip() != body.tenant.strip()
    ):
        raise HTTPException(
            status_code=403,
            detail="tenant_id does not match the caller tenant",
            headers=_NO_STORE_HEADERS,
        )
    requested = body.tenant_id if body.tenant_id is not None else body.tenant
    try:
        return resolve_scoped_tenant(request, requested)
    except HTTPException as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers={**(exc.headers or {}), **_NO_STORE_HEADERS},
        ) from None


def _principal_id(request: Request) -> str:
    principal = getattr(request.state, "role_principal", None)
    if isinstance(principal, dict):
        principal_id = principal.get("principal_id")
        if isinstance(principal_id, str) and principal_id:
            return principal_id
    return "admin"


async def _enforce_policy(request: Request, tenant_id: str, policy_id: str | None) -> None:
    """Read-only policy gate. Does not write audit, usage, or spend."""
    if not policy_id:
        return
    store = get_app_state(request.app).policy_store
    if store is None:
        raise HTTPException(503, detail="Policy store not available", headers=_NO_STORE_HEADERS)
    rule = await store.get_policy(policy_id, tenant_id)
    if rule is None or not rule.enabled:
        raise HTTPException(404, detail="Policy not found", headers=_NO_STORE_HEADERS)
    if rule.action == PolicyAction.BLOCK:
        raise HTTPException(403, detail="Request blocked by policy", headers=_NO_STORE_HEADERS)
    if rule.action == PolicyAction.ROUTE_LOCAL:
        raise HTTPException(
            501,
            detail="ROUTE_LOCAL not yet implemented",
            headers=_NO_STORE_HEADERS,
        )


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
        raise HTTPException(
            503,
            detail="Detection service not initialized",
            headers=_NO_STORE_HEADERS,
        )

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
    """Preview detection and tokenization without persisting anything.

    The request body is not logged.
    """
    preview_rate_limiter.check(_principal_id(request))
    tenant_id = _scoped_tenant(request, body)
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

    response.headers["Cache-Control"] = "no-store"
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
