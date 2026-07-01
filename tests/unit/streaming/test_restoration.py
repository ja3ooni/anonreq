"""Unit tests for streaming token restoration."""

from __future__ import annotations

import pytest

from anonreq.streaming.restoration import StreamingRestorationStage


@pytest.fixture
def stage() -> StreamingRestorationStage:
    instance = StreamingRestorationStage.__new__(StreamingRestorationStage)
    instance._mappings = {
        "[EMAIL_0]": "user@example.com",
        "[PHONE_1]": "+1-555-1234",
    }
    instance._lookup = {
        token.strip("[]").casefold(): value
        for token, value in instance._mappings.items()
    }
    return instance


def test_replaces_exact_tokens(stage: StreamingRestorationStage) -> None:
    assert stage.restore_text("Contact [EMAIL_0]") == "Contact user@example.com"


def test_replaces_case_insensitive_tokens(stage: StreamingRestorationStage) -> None:
    assert stage.restore_text("[email_0]") == "user@example.com"
    assert stage.restore_text("[Email_0]") == "user@example.com"


def test_replaces_bare_tokens_at_word_boundary(stage: StreamingRestorationStage) -> None:
    assert stage.restore_text("Contact EMAIL_0 now") == "Contact user@example.com now"


def test_replaces_multiple_tokens(stage: StreamingRestorationStage) -> None:
    assert (
        stage.restore_text("[EMAIL_0] or PHONE_1")
        == "user@example.com or +1-555-1234"
    )


def test_unknown_token_left_unchanged(stage: StreamingRestorationStage) -> None:
    assert stage.restore_text("[SSN_9]") == "[SSN_9]"


def test_empty_and_token_free_text_passthrough(stage: StreamingRestorationStage) -> None:
    assert stage.restore_text("") == ""
    assert stage.restore_text("plain text") == "plain text"
