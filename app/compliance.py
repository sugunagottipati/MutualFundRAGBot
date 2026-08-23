"""Phase 7: Response validation and deterministic generation fallback."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.constants import APPROVED_SOURCE_URLS, MANDATORY_FOOTER_PREFIX, MAX_ANSWER_SENTENCES
from app.generator import (
    FACTUAL_SYSTEM_PROMPT,
    STRICT_FACTUAL_SYSTEM_PROMPT,
    GenerationError,
    GenerationRequest,
    GroqAnswerGenerator,
)

ADVISORY_TERMS = (
    "should i", "recommend", "suggest", "best fund", "which fund",
    "you should", "buy it", "invest in", "good investment", "guaranteed return",
    "will this fund", "predict", "outperform",
)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_PATTERN = re.compile(r"https://[^\s\)\"\'>\]]*")


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a generated answer."""

    is_valid: bool
    reasons: tuple[str, ...] = ()


class ComplianceValidator:
    """Validate all Phase 7 response constraints before delivery."""

    def validate(
        self,
        response: str,
        expected_source_url: str,
        factual_mode: bool = True,
    ) -> ValidationResult:
        reasons: list[str] = []
        urls = URL_PATTERN.findall(response)

        if len(urls) != 1:
            reasons.append(f"expected exactly one citation URL, found {len(urls)}")
        if any(url not in APPROVED_SOURCE_URLS for url in urls):
            reasons.append("citation URL is not approved")
        if len(urls) == 1 and urls[0] != expected_source_url:
            reasons.append("citation URL does not match the selected source")

        footer = response.split(MANDATORY_FOOTER_PREFIX, 1)
        if len(footer) != 2:
            reasons.append("missing source-date footer")
        elif not DATE_PATTERN.fullmatch(footer[1].strip()):
            reasons.append("source-date footer must use YYYY-MM-DD format")

        body = footer[0]
        if self._sentence_count(body) > MAX_ANSWER_SENTENCES:
            reasons.append(f"answer exceeds {MAX_ANSWER_SENTENCES} sentences")
        if factual_mode and self._contains_advisory_language(body):
            reasons.append("answer contains advisory language")

        return ValidationResult(not reasons, tuple(reasons))

    @staticmethod
    def _sentence_count(text: str) -> int:
        body = URL_PATTERN.sub("", text)
        return len(re.findall(r"[^.!?]+(?:[.!?]+|$)", body.strip()))

    @staticmethod
    def _contains_advisory_language(text: str) -> bool:
        normalized = " ".join(text.lower().split())
        return any(term in normalized for term in ADVISORY_TERMS)


class ComplianceGenerationLoop:
    """Retry invalid generated answers once, then return a safe fallback."""

    def __init__(
        self,
        generator: GroqAnswerGenerator,
        validator: ComplianceValidator | None = None,
    ) -> None:
        self.generator = generator
        self.validator = validator or ComplianceValidator()

    def generate(self, request: GenerationRequest) -> str:
        """Return a validated answer or a deterministic safe fallback."""
        for prompt in (FACTUAL_SYSTEM_PROMPT, STRICT_FACTUAL_SYSTEM_PROMPT):
            try:
                response = self.generator.generate(request, system_prompt=prompt)
            except (GenerationError, ValueError):
                continue
            if self.validator.validate(response, request.source_url).is_valid:
                return response
        return self._fallback(request)

    @staticmethod
    def _fallback(request: GenerationRequest) -> str:
        return (
            "I cannot provide a compliant factual answer from the available source context.\n\n"
            f"Source: {request.source_url}\n"
            f"{MANDATORY_FOOTER_PREFIX} {request.last_updated}"
        )