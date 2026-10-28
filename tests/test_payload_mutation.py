"""Regression: anonymize and restore must not mutate caller-owned payloads.

Tokenization used to shallow-copy the incoming request, and restoration
used to shallow-copy response choices. Nested message and tool-call
updates then rewrote the originals in place.
"""

from __future__ import annotations

import copy
from unittest.mock import MagicMock

import pytest

from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.tokenization import TokenizationStage
from anonreq.tokenization import Tokenizer
from anonreq.tokenization.restorer import Restorer


@pytest.mark.asyncio
async def test_anonymize_and_restore_leave_original_payloads_unchanged() -> None:
    """Original request and provider response stay byte-for-byte intact."""
    original_request = {
        "model": "gpt-4",
        "messages": [
            {
                "role": "user",
                "content": "My email is john@example.com",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "lookup",
                            "arguments": '{"note": "keep me"}',
                        },
                    }
                ],
            }
        ],
    }
    request_before = copy.deepcopy(original_request)

    ctx = ProcessingContext(request_id="req_mutation", tenant_id="tenant-a")
    ctx.original_request = original_request
    ctx.classification_result = {"action": "ANONYMIZE"}
    ctx.text_nodes = [
        {
            "path": "messages[0].content",
            "role": "user",
            "value": "My email is john@example.com",
        },
    ]
    # "My email is john@example.com" — span is the address at [12:28].
    ctx.detections = [
        {
            "entity_type": "EMAIL_ADDRESS",
            "start": 12,
            "end": 28,
            "score": 1.0,
            "source": "regex",
            "node_index": 0,
        },
    ]

    stage = TokenizationStage(tokenizer=Tokenizer(), cache_manager=MagicMock())
    result = await stage.execute(ctx)

    assert original_request == request_before
    assert result.transformed_request is not original_request
    assert result.transformed_request["messages"] is not original_request["messages"]
    assert result.transformed_request["messages"][0] is not original_request["messages"][0]
    tokenized_content = result.transformed_request["messages"][0]["content"]
    assert tokenized_content != original_request["messages"][0]["content"]
    assert "john@example.com" not in tokenized_content
    assert original_request["messages"][0]["content"] == "My email is john@example.com"

    token = next(iter(result.token_mappings))
    provider_response = {
        "id": "chatcmpl-1",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"Contact {token}",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {
                                "name": "send_email",
                                "arguments": '{"to": "' + token + '"}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
    }
    response_before = copy.deepcopy(provider_response)

    restored = Restorer.restore_response(provider_response, result.token_mappings)

    assert provider_response == response_before
    assert restored is not provider_response
    assert restored["choices"][0] is not provider_response["choices"][0]
    assert restored["choices"][0]["message"] is not provider_response["choices"][0]["message"]
    assert provider_response["choices"][0]["message"]["content"] == f"Contact {token}"
    assert "john@example.com" in restored["choices"][0]["message"]["content"]
    restored_args = (
        restored["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    )
    original_args = (
        provider_response["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    )
    assert "john@example.com" in restored_args
    assert token in original_args
