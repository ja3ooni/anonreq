from __future__ import annotations

from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from anonreq.agent.config import ToolGovernanceConfig
from anonreq.agent.result_sanitizer import ToolResultSanitizer
from anonreq.agent.schema import ToolResult
from anonreq.tokenization.tokenizer import Tokenizer


class EmailDetector:
    async def detect(self, text: str):
        detections = []
        cursor = 0
        while True:
            start = text.find("@example.com", cursor)
            if start < 0:
                break
            local_start = start
            while local_start > 0 and text[local_start - 1].isalnum():
                local_start -= 1
            detections.append(
                {
                    "entity_type": "EMAIL",
                    "start": local_start,
                    "end": start + len("@example.com"),
                    "score": 0.99,
                }
            )
            cursor = start + len("@example.com")
        return detections


json_scalar = st.one_of(
    st.text(
        alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
        max_size=40,
    ),
    st.integers(min_value=-1000, max_value=1000),
    st.booleans(),
    st.none(),
)


@settings(max_examples=60, deadline=None)
@given(
    data=st.dictionaries(
        keys=st.text(
            alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00."),
            min_size=1,
            max_size=16,
        ),
        values=json_scalar,
        min_size=1,
        max_size=8,
    )
)
@pytest.mark.asyncio
async def test_tool_result_round_trip_preserves_keys_and_non_sensitive_values(data: dict[str, object]):
    sanitizer = ToolResultSanitizer(EmailDetector(), None, ToolGovernanceConfig())
    result = ToolResult(tool_name="lookup", content=data, id="call_1", type="openai")

    sanitized = await sanitizer.sanitize_result(result)
    restored = _restore_content(sanitized.content, sanitizer.token_mappings)

    assert list(sanitized.content.keys()) == list(data.keys())
    assert restored == data


@settings(max_examples=40, deadline=None)
@given(
    key=st.text(
        alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00."),
        min_size=1,
        max_size=16,
    ),
    local=st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")), min_size=1, max_size=20),
)
@pytest.mark.asyncio
async def test_tool_result_value_tokenization_never_mutates_json_keys(key: str, local: str):
    email = f"{local}@example.com"
    sanitizer = ToolResultSanitizer(EmailDetector(), None, ToolGovernanceConfig())

    sanitized = await sanitizer.sanitize_result(
        ToolResult(tool_name="lookup", content={key: email}, id="call_2", type="mcp")
    )

    assert list(sanitized.content.keys()) == [key]
    assert sanitized.content[key] != email
    assert sanitizer.token_mappings


def test_cross_request_token_randomization_for_same_value_over_1000_sessions():
    value = "alice@example.com"
    tokens: set[str] = set()

    for _ in range(1000):
        tokenizer = Tokenizer()
        tokenizer.initialize_session()
        _session_id = uuid4().hex
        _tokenized, mapping = tokenizer.tokenize(
            value,
            [{"entity_type": "EMAIL", "start": 0, "end": len(value), "score": 0.99}],
        )
        tokens.update(mapping.keys())

    assert len(tokens) == 1000


def _restore_content(value, mapping: dict[str, str]):
    if isinstance(value, dict):
        return {key: _restore_content(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_restore_content(item, mapping) for item in value]
    if isinstance(value, str):
        restored = value
        for token, original in mapping.items():
            restored = restored.replace(token, original)
        return restored
    return value
