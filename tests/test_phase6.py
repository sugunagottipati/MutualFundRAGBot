"""Phase 6 tests: Groq generation and unknown-answer behavior."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.constants import APPROVED_SOURCE_URLS, MANDATORY_FOOTER_PREFIX
from app.generator import (
    GenerationError,
    GenerationRequest,
    GroqAnswerGenerator,
    GroqClient,
    UNKNOWN_ANSWER,
)


class FakeCompletions:
    def __init__(self, content: str):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class FakeClient:
    def __init__(self, content: str):
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


def _request(context: str) -> GenerationRequest:
    return GenerationRequest(
        query="What is the expense ratio?",
        context=context,
        source_url=APPROVED_SOURCE_URLS[0],
        last_updated="2026-08-23",
    )


def test_groq_client_sends_constrained_messages():
    client = FakeClient("The expense ratio is 0.50%.")
    wrapper = GroqClient("test-key", "test-model", client=client)

    result = wrapper.complete("What is the expense ratio?", "[Fees]\nExpense ratio: 0.50%")

    assert result == "The expense ratio is 0.50%."
    call = client.chat.completions.calls[0]
    assert call["model"] == "test-model"
    assert call["temperature"] == 0.1
    assert "Source context" in call["messages"][1]["content"]
    assert "Do not include a URL" in call["messages"][0]["content"]


def test_generator_adds_one_owned_citation_and_footer():
    generator = GroqAnswerGenerator(
        GroqClient("test-key", "test-model", client=FakeClient("The expense ratio is 0.50%."))
    )

    response = generator.generate(_request("[Fees]\nExpense ratio: 0.50%"))

    assert response.count("https://") == 1
    assert APPROVED_SOURCE_URLS[0] in response
    assert f"{MANDATORY_FOOTER_PREFIX} 2026-08-23" in response


def test_empty_context_uses_unknown_path_without_provider_call():
    client = FakeClient("This must not be returned.")
    generator = GroqAnswerGenerator(GroqClient("test-key", "test-model", client=client))

    response = generator.generate(_request(""))

    assert UNKNOWN_ANSWER in response
    assert client.chat.completions.calls == []


def test_unapproved_source_is_rejected():
    generator = GroqAnswerGenerator(
        GroqClient("test-key", "test-model", client=FakeClient("answer"))
    )
    request = GenerationRequest("question", "context", "https://example.com", "2026-08-23")

    with pytest.raises(ValueError, match="approved source"):
        generator.generate(request)


def test_invalid_provider_response_raises_generation_error():
    class EmptyCompletions:
        def create(self, **kwargs):
            return SimpleNamespace(choices=[])

    client = SimpleNamespace(chat=SimpleNamespace(completions=EmptyCompletions()))
    wrapper = GroqClient("test-key", "test-model", client=client)

    with pytest.raises(GenerationError, match="invalid response"):
        wrapper.complete("question", "context")