"""Data models for the AnonReq gateway.

Exports all core model types for convenient import:
    ``from anonreq.models import ProcessingContext, ChatRequest, ...``
"""

from anonreq.models.processing_context import ProcessingContext
from anonreq.models.chat import ChatMessage, ChatRequest, ChatCompletionChoice, ChatCompletionResponse
from anonreq.models.classification import (
    ClassificationAction,
    ClassificationLevel,
    ClassificationResult,
    ClassificationRule,
    ClassResult,
    ENTITY_CLASSIFICATION_MAP,
)
from anonreq.models.detection import TextNode, DetectionResult
from anonreq.models.tokenization import TokenMapping, TokenizationResult, TOKEN_PATTERN
from anonreq.providers.adapter import (
    ProviderAdapter,
    ProviderCapabilities,
    ProviderRequest,
    ProviderResponse,
    ProviderResult,
    RestoredResponse,
)

__all__ = [
    "ProcessingContext",
    "ChatMessage",
    "ChatRequest",
    "ChatCompletionChoice",
    "ChatCompletionResponse",
    "ClassificationAction",
    "ClassificationLevel",
    "ClassificationResult",
    "ClassificationRule",
    "ClassResult",
    "ENTITY_CLASSIFICATION_MAP",
    "TextNode",
    "DetectionResult",
    "TokenMapping",
    "TokenizationResult",
    "TOKEN_PATTERN",
    "ProviderAdapter",
    "ProviderCapabilities",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderResult",
    "RestoredResponse",
]
