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

import copy
import inspect
import re
from typing import Any

from structlog import get_logger

from anonreq.exceptions import DependencyUnavailableError, PipelineAbortError
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.base import PipelineStage

logger = get_logger("anonreq.pipeline.tokenization")

_PATH_PART = re.compile(r"([^.\[\]]+)((?:\[\d+\])*)")
_INDEX = re.compile(r"\[(\d+)\]")


def _parse_path(path: str) -> list[str | int] | None:
    """Split ``messages[0].tool_calls[1].function.arguments`` into keys.

    Returns ``None`` when the path is malformed.
    """
    keys: list[str | int] = []
    for part in path.split("."):
        match = _PATH_PART.fullmatch(part)
        if match is None:
            return None
        keys.append(match.group(1))
        keys.extend(int(index) for index in _INDEX.findall(match.group(2)))
    return keys or None


def _write_path(document: Any, path: str, value: str) -> bool:
    """Set ``value`` at ``path`` inside ``document``. Return True on success.

    Handles indexed parts such as ``tool_calls[0]`` and nested indices
    generally, instead of comparing path parts to fixed names.
    """
    keys = _parse_path(path)
    if keys is None:
        return False
    target = document
    for key in keys[:-1]:
        if isinstance(key, int):
            if not isinstance(target, list) or key >= len(target):
                return False
        elif not isinstance(target, dict) or key not in target:
            return False
        target = target[key]
    last = keys[-1]
    if isinstance(last, int):
        if not isinstance(target, list) or last >= len(target):
            return False
    elif not isinstance(target, dict) or last not in target:
        return False
    target[last] = value
    return True


class TokenizationStage(PipelineStage):
    """Replaces detected PII spans with ``[TYPE_N]`` tokens.

    Operates per text node: for each node in ``ctx.text_nodes``, extracts
    the detections belonging to that node (via ``node_index`` tag), calls
    ``Tokenizer.tokenize()``, and records the mapping.
    """

    def __init__(
        self,
        tokenizer: Any,
        cache_manager: Any,
        *,
        persist_mappings: bool = True,
        run_when_pass: bool = False,
    ) -> None:
        """Initialise with tokenizer and cache manager.

        Args:
            tokenizer: A ``Tokenizer`` instance.
            cache_manager: A ``CacheManager`` for storing token mappings
                in Valkey. Ignored when ``persist_mappings`` is false.
            persist_mappings: When false, tokens are generated in memory
                and ``store_mapping`` is not called.
            run_when_pass: When true, PASS classification still tokenizes.
                BLOCK still skips.
        """
        super().__init__("TokenizationStage")
        self._tokenizer = tokenizer
        self._cache_manager = cache_manager
        self._persist_mappings = persist_mappings
        self._run_when_pass = run_when_pass

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
        # Skip only for BLOCK: detection and tokenization always run otherwise
        if ctx.classification_result:
            action = ctx.classification_result.get("action")
            if action == "BLOCK":
                return ctx

        # No detections → forward an unchanged copy (TOKN-06/07)
        if not ctx.detections:
            ctx.transformed_request = copy.deepcopy(ctx.original_request or {})
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

            for i, node in enumerate(ctx.text_nodes or []):
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

            # Deep-copy so nested message/tool-call edits never mutate the
            # caller-owned request. A shallow copy shares the messages list.
            transformed = copy.deepcopy(ctx.original_request or {})
            for i, node in enumerate(ctx.text_nodes or []):
                path = node.get("path", "")
                written = _write_path(transformed, path, tokenized_texts[i])
                # A detected node that cannot be written back would be
                # forwarded in clear text. Fail closed.
                if not written and detections_by_node.get(i):
                    raise ValueError("unwritable text node path")

            ctx.transformed_request = transformed

            # Store mapping in Valkey if non-empty. Debug preview sets
            # persist_mappings=False and must not touch the token cache.
            if all_mappings and self._persist_mappings:
                store_result = self._cache_manager.store_mapping(
                    ctx.tenant_id,
                    ctx.context_id,
                    all_mappings,
                )
                if inspect.iscoroutine(store_result):
                    await store_result

            ctx.token_mappings = all_mappings

            logger.info(
                "tokenization.complete",
                stage=self.name,
                request_id=ctx.request_id,
                token_count=len(all_mappings),
            )

        except PipelineAbortError:
            raise
        except DependencyUnavailableError:
            raise
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=500,
                    message=f"Tokenization stage failed: {type(exc).__name__}",
                    request_id=ctx.request_id,
                )
            )
        except Exception as exc:
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=500,
                    message=f"Tokenization stage failed: {type(exc).__name__}",
                    request_id=ctx.request_id,
                )
            )

        return ctx
