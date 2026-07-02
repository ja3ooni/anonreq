"""ProviderStage — async HTTP passthrough to OpenAI-compatible upstream.

Per PROV-01 and PROV-06:
- Sends sanitised request body to the configured upstream endpoint
- For ANONYMIZE: sends ``ctx.transformed_request`` (tokenised)
- For PASS: sends ``ctx.original_request`` (unchanged)
- API key injected at network boundary via ``Authorization: Bearer`` header
- On timeout: 504 error; on HTTP error: 502 error; on connection error: 503
- Error messages are generic per T-02-04-05 and T-02-04-08 (no internals leak)
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from structlog import get_logger

from anonreq.exceptions import PipelineAbortError
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.base import PipelineStage
from anonreq.routing.alias_registry import AliasNotFoundError, AliasRegistry

logger = get_logger("anonreq.pipeline.provider")


class ProviderStage(PipelineStage):
    """Forwards the (sanitised) request to the upstream LLM provider.

    Uses a shared ``httpx.AsyncClient`` with connection pooling for
    efficiency across concurrent requests.
    """

    def __init__(
        self,
        openai_base_url: str,
        api_key: str,
        timeout: float = 30.0,
        alias_registry: AliasRegistry | None = None,
    ) -> None:
        """Initialise the provider stage.

        Args:
            openai_base_url: Base URL of the upstream OpenAI-compatible
                endpoint (e.g. ``"https://api.openai.com"``).
            api_key: API key for the upstream provider.
            timeout: Request timeout in seconds.
        """
        super().__init__("ProviderStage")
        self._openai_base_url = openai_base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._http_client: httpx.AsyncClient | None = None
        self._alias_registry = alias_registry

    @property
    def _client(self) -> httpx.AsyncClient:
        """Lazy-initialised shared HTTP client with connection pooling."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self._timeout)
        return self._http_client

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        """Forward the request to the upstream provider.

        Determines the request body:
        - ANONYMIZE: ``ctx.transformed_request`` (sanitised)
        - PASS: ``ctx.original_request`` (unchanged)

        Returns:
            The mutated ``ProcessingContext`` with ``ctx.provider_response``
            set on success.
        """
        # Determine which body to send
        action = ctx.classification_result.get("action") if ctx.classification_result else None

        if action == "ANONYMIZE":
            request_body = ctx.transformed_request
        else:
            request_body = ctx.original_request

        if request_body is None:
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=500,
                    message="No request body available for provider",
                    request_id=ctx.request_id,
                )
            )
            return ctx

        if self._alias_registry is not None:
            alias_name = str(request_body.get("model", ""))
            try:
                model_alias = self._alias_registry.resolve(alias_name)
            except AliasNotFoundError as exc:
                ctx.fail_secure(
                    PipelineAbortError(
                        status_code=400,
                        message=str(exc),
                        request_id=ctx.request_id,
                    )
                )
                return ctx
            ctx.provider = model_alias.provider
            ctx.model = model_alias.model
            request_body = dict(request_body)
            request_body["model"] = model_alias.model

        url = f"{self._openai_base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = await self._client.post(
                url,
                json=request_body,
                headers=headers,
            )

            if response.is_error:
                ctx.fail_secure(
                    PipelineAbortError(
                        status_code=502,
                        message="Provider returned an error",
                        request_id=ctx.request_id,
                    )
                )
                return ctx

            ctx.provider_response = response.json()

            logger.info(
                "provider.complete",
                stage=self.name,
                request_id=ctx.request_id,
                status_code=response.status_code,
                action=action,
            )

        except httpx.TimeoutException:
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=504,
                    message="Upstream provider timeout",
                    request_id=ctx.request_id,
                )
            )
        except httpx.ConnectError:
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=503,
                    message="Provider unavailable",
                    request_id=ctx.request_id,
                )
            )
        except PipelineAbortError:
            raise
        except Exception as exc:
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=502,
                    message="Provider request failed",
                    request_id=ctx.request_id,
                )
            )

        return ctx

    async def close(self) -> None:
        """Close the underlying HTTP client connection pool."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
