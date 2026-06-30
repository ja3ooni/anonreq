"""TokenizationStage — replaces detected spans with ``[TYPE_N]`` tokens.

Per TOKN-01 through TOKN-07:
- Replaces PII spans with ``[TYPE_N]`` tokens via the Tokenizer
- Deduplication: same value → same token (TOKN-02)
- Reverse-offset replacement prevents position drift (TOKN-04)
- No detections → request forwarded unchanged (TOKN-06/07)
- Mapping stored in Valkey via CacheManager (D-14)
- On any error: ctx.fail_secure() per D-50
"""

from __future__ import annotations

from typing import Any

import structlog
from structlog import get_logger

from anonreq.exceptions import PipelineAbortError
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.base import PipelineStage

logger = get_logger("anonreq.pipeline.tokenization")


class TokenizationStage(PipelineStage):
    """Replaces detected PII spans with ``[TYPE_N]`` tokens.

    Operates per text node: for each node in ``ctx.text_nodes``, extracts
    the detections belonging to that node (via ``node_index`` tag), calls
    ``Tokenizer.tokenize()``, and records the mapping.
    """

    def __init__(self, tokenizer: Any, cache_manager: Any) -> None:
        """Initialise with tokenizer and cache manager.

        Args:
            tokenizer: A ``Tokenizer`` instance.
            cache_manager: A ``CacheManager`` for storing token mappings
                in Valkey.
        """
        super().__init__("TokenizationStage")
        self._tokenizer = tokenizer
        self._cache_manager = cache_manager

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        """Replace detected entities with tokens.

        Steps:
        1. Skip if classification is PASS or BLOCK.
        2. If no detections: set ``transformed_request`` to a copy of
           ``original_request`` and return (TOKN-06/07).
        3. Process each text node, replacing spans with tokens.
        4. Build ``transformed_request`` dict with tokenized content.
        5. Store non-empty mapping in Valkey via ``CacheManager.store_mapping``.
        6. Set ``ctx.token_mappings``.

        Returns:
            The mutated ``ProcessingContext``.
        """
        # Skip if classification says PASS or BLOCK
        if ctx.classification_result:
            action = ctx.classification_result.get("action")
            if action in ("PASS", "BLOCK"):
                return ctx

        # No detections → forward unchanged (TOKN-06/07)
        if not ctx.detections:
            ctx.transformed_request = ctx.original_request
            ctx.token_mappings = {}
            return ctx

        try:
            # Initialize tokenizer for this session
            self._tokenizer.initialize_session()

            # Group detections by node_index
            detections_by_node: dict[int, list[dict[str, Any]]] = {}
            for d in ctx.detections:
                idx = d.get("node_index", 0)
                detections_by_node.setdefault(idx, []).append(d)

            all_mappings: dict[str, str] = {}
            tokenized_texts: dict[int, str] = {}

            for i, node in enumerate(ctx.text_nodes):
                node_value = node.get("value", "")
                node_detections = detections_by_node.get(i, [])

                if node_detections:
                    tokenized_text, node_mapping = self._tokenizer.tokenize(
                        node_value, node_detections,
                    )
                    all_mappings.update(node_mapping)
                    tokenized_texts[i] = tokenized_text
                else:
                    tokenized_texts[i] = node_value

            # Build transformed_request by replacing original content
            transformed = ctx.original_request.copy()
            messages = transformed.get("messages", [])
            for i, node in enumerate(ctx.text_nodes):
                # Extract message index and key from path
                path = node.get("path", "")
                # Path format: messages[{idx}].content or messages[{idx}].tool_calls[{tc_idx}].function.arguments
                parts = path.split(".")
                if len(parts) >= 2 and parts[0].startswith("messages["):
                    msg_idx_str = parts[0][len("messages["):-1]
                    try:
                        msg_idx = int(msg_idx_str)
                    except (ValueError, IndexError):
                        continue

                    if msg_idx < len(messages):
                        if parts[1] == "content":
                            messages[msg_idx]["content"] = tokenized_texts[i]
                        elif parts[1] == "tool_calls":
                            # tool_calls[{tc_idx}].function.arguments
                            tc_part = parts[1] if len(parts) == 2 else ".".join(parts[1:])
                            # Parse tool_call index from the path part
                            tc_idx_str = tc_part[len("tool_calls["):-len("].function.arguments")] if tc_part.startswith("tool_calls[") else None
                            if tc_idx_str:
                                try:
                                    tc_idx = int(tc_idx_str)
                                    tool_calls = messages[msg_idx].get("tool_calls", [])
                                    if tc_idx < len(tool_calls):
                                        if "function" in tool_calls[tc_idx]:
                                            tool_calls[tc_idx]["function"]["arguments"] = tokenized_texts[i]
                                except (ValueError, IndexError):
                                    continue

            ctx.transformed_request = transformed

            # Store mapping in Valkey if non-empty
            if all_mappings:
                await self._cache_manager.store_mapping(
                    ctx.tenant_id,
                    ctx.context_id,
                    all_mappings,
                )

            ctx.token_mappings = all_mappings

            logger.info(
                "tokenization.complete",
                stage=self.name,
                request_id=ctx.request_id,
                token_count=len(all_mappings),
            )

        except PipelineAbortError:
            raise
        except Exception as exc:
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=500,
                    message="Tokenization stage failed",
                    request_id=ctx.request_id,
                )
            )

        return ctx
