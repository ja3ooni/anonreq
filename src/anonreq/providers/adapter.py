"""Provider adapter abstract base class and core data types.

Per D-66 through D-69 and ARCHITECTURE.md:
- ``ProviderAdapter(ABC)`` is the abstract base for all provider adapters
- Adapters are pure schema translators — zero policy, classification,
  detection, tokenization, restoration, or cache logic (AG-01)
- ``ProviderResult`` envelope branches pipeline exactly once:
  non-streaming -> RestorationStage, streaming -> TailBuffer
- Secrets never enter ProcessingContext — resolved only inside
  ProviderAdapter at network boundary (AG-09)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from anonreq.models.processing_context import ProcessingContext
    from anonreq.streaming.stream_event import StreamEvent


# ---------------------------------------------------------------------------
# ProviderCapabilities — capability flags per provider
# ---------------------------------------------------------------------------


class ProviderCapabilities(BaseModel):
    """Capability flags for an LLM provider.

    These flags are loaded from YAML config at startup and determine
    which features are available for each provider (e.g. streaming,
    tool calling, vision). Per D-69.
    """

    streaming: bool = False
    tool_calling: bool = False
    reasoning: bool = False
    vision: bool = False
    embeddings: bool = False
    json_mode: bool = False
    function_calling: bool = False
    max_context_window: int = 0
    max_output_tokens: int = 0


# ---------------------------------------------------------------------------
# ProviderRequest / ProviderResponse — wire-format types
# ---------------------------------------------------------------------------


@dataclass
class ProviderRequest:
    """A prepared HTTP request to send to an LLM provider.

    Created by ``ProviderAdapter.translate_request()`` from a
    ``ProcessingContext``. Contains the method, URL, headers, body,
    and timeout for the upstream HTTP call.
    """

    method: str = "POST"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)
    timeout: float = 30.0


@dataclass
class ProviderResponse:
    """A raw HTTP response from an LLM provider.

    Returned by ``ProviderAdapter.execute()`` for non-streaming calls.
    Contains the status code, parsed JSON body, and response headers.
    """

    status_code: int = 200
    body: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class RestoredResponse:
    """A response that has been restored with original token values.

    Returned by ``ProviderAdapter.translate_response()`` after the
    provider response has been normalized back to the canonical
    OpenAI-compatible format.
    """

    body: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ProviderResult — dispatch envelope
# ---------------------------------------------------------------------------


@dataclass
class ProviderResult:
    """Dispatch envelope returned after a provider call.

    The pipeline branches exactly once after reading this envelope:
    - ``streaming=True`` -> TailBuffer FSM -> RestorationStage -> SSEEmitter
    - ``streaming=False`` -> RestorationStage (full-response) -> Response

    Exactly one of ``response`` or ``stream`` is set based on the
    ``streaming`` flag.
    """

    streaming: bool
    response: ProviderResponse | None = None
    stream: AsyncIterator[StreamEvent] | None = None


# ---------------------------------------------------------------------------
# ProviderAdapter — abstract base class
# ---------------------------------------------------------------------------


class ProviderAdapter(ABC):
    """Abstract base class for all LLM provider adapters.

    Per D-66 and AG-01, adapters are pure schema translators with
    these responsibilities:
    - Translate canonical (OpenAI) requests to provider-specific format
    - Execute HTTP calls to the provider API
    - Normalize provider responses back to canonical format
    - Normalize provider streams to StreamEvent canonical model
    - Normalize provider errors to canonical error format (no keys,
      URLs, or raw content per PROV-08)

    Subclasses must implement all 6 abstract methods/properties.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the canonical provider name (e.g. 'anthropic')."""

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Return the capabilities for this provider."""

    @abstractmethod
    def translate_request(
        self, ctx: ProcessingContext
    ) -> ProviderRequest:
        """Translate a canonical (OpenAI) request to provider format.

        Args:
            ctx: The ProcessingContext containing the original request
                in ``ctx.original_request`` (OpenAI-compatible dict).

        Returns:
            A ``ProviderRequest`` with the provider-specific URL,
            headers, and body ready to send.
        """

    @abstractmethod
    async def execute(
        self, request: ProviderRequest
    ) -> ProviderResponse:
        """Execute a non-streaming HTTP call to the provider.

        Args:
            request: The prepared ``ProviderRequest`` from
                ``translate_request()``.

        Returns:
            A ``ProviderResponse`` with the provider's response.

        Raises:
            PipelineAbortError: On any HTTP/connection/timeout error,
                with a generic message per PROV-08.
        """

    @abstractmethod
    async def stream_events(
        self, request: ProviderRequest
    ) -> AsyncIterator[StreamEvent]:
        """Execute a streaming HTTP call and yield normalized events.

        Args:
            request: The prepared ``ProviderRequest`` from
                ``translate_request()``.

        Yields:
            ``StreamEvent`` instances normalized to the canonical model
            per AG-07.

        Raises:
            PipelineAbortError: On any HTTP/connection/timeout error,
                with a generic message per PROV-08.
        """

    @abstractmethod
    def translate_response(
        self,
        ctx: ProcessingContext,
        response: ProviderResponse,
    ) -> RestoredResponse:
        """Normalize a provider response back to canonical format.

        Args:
            ctx: The ProcessingContext (for context like model name).
            response: The raw ``ProviderResponse`` from ``execute()``.

        Returns:
            A ``RestoredResponse`` with the body in OpenAI-compatible
            chat completion format.
        """
