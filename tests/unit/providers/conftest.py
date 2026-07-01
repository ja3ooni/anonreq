"""Conftest for provider adapter tests.

Sets mock API key environment variables via ``pytest_sessionstart`` hook
so ``resolve_api_key()`` does not raise ``ValueError`` during unit tests.
Individual tests can still override with ``monkeypatch.setenv`` or
``unittest.mock.patch.dict``.
"""

import os


def pytest_sessionstart() -> None:
    """Set mock API keys at session start."""
    os.environ.setdefault("ANONREQ_ANTHROPIC_API_KEY", "sk-ant-test-mock-key")
    os.environ.setdefault("ANONREQ_GEMINI_API_KEY", "test-gemini-mock-key")
    os.environ.setdefault("ANONREQ_OLLAMA_API_KEY", "test-ollama-mock-key")
