"""Phase 7 tests: compliance validation and retry/fallback behavior."""

from __future__ import annotations

from types import SimpleNamespace

from app.compliance import ComplianceGenerationLoop, ComplianceValidator
from app.constants import APPROVED_SOURCE_URLS
from app.generator import GenerationRequest, GroqAnswerGenerator, GroqClient

SOURCE = APPROVED_SOURCE_URLS[0]


def _response(body: str, source: str = SOURCE, date: str = "2026-08-23") -> str:
    return f"{body}\n\nSource: {source}\nLast updated from sources: {date}"


def test_validator_accepts_compliant_response():
    result = ComplianceValidator().validate(_response("The expense ratio is 0.50%."), SOURCE)

    assert result.is_valid is True
    assert result.reasons == ()


def test_validator_rejects_policy_violations():
    response = (
        "You should invest because this may outperform. Second sentence. Third sentence. Fourth sentence.\n\n"
        f"Source: {SOURCE}\nLast updated from sources: 23-08-2026"
    )

    result = ComplianceValidator().validate(response, SOURCE)

    assert result.is_valid is False
    assert any("sentences" in reason for reason in result.reasons)
    assert any("advisory" in reason for reason in result.reasons)
    assert any("YYYY-MM-DD" in reason for reason in result.reasons)


def test_validator_requires_exactly_one_matching_approved_url():
    response = _response("The fund has an expense ratio.\nSee https://example.com/details.")

    result = ComplianceValidator().validate(response, SOURCE)

    assert result.is_valid is False
    assert any("exactly one" in reason for reason in result.reasons)
    assert any("not approved" in reason for reason in result.reasons)


class SequenceCompletions:
    def __init__(self, contents: list[str]):
        self.contents = iter(contents)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        content = next(self.contents)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


def test_loop_retries_once_with_stricter_prompt():
    completions = SequenceCompletions(
        ["Too many. Sentences. Here. Four.", "The expense ratio is 0.50%."]
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    loop = ComplianceGenerationLoop(
        GroqAnswerGenerator(GroqClient("key", "model", client=client))
    )

    result = loop.generate(
        GenerationRequest("What is the expense ratio?", "Expense ratio: 0.50%", SOURCE, "2026-08-23")
    )

    assert "0.50%" in result
    assert completions.calls == 2


def test_loop_returns_safe_fallback_after_two_invalid_answers():
    completions = SequenceCompletions(["Advice. Buy it.", "Still advice. Buy it."])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    loop = ComplianceGenerationLoop(
        GroqAnswerGenerator(GroqClient("key", "model", client=client))
    )

    result = loop.generate(GenerationRequest("Question", "Context", SOURCE, "2026-08-23"))

    assert "cannot provide a compliant factual answer" in result
    assert result.count("https://") == 1
    assert completions.calls == 2