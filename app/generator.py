"""Phase 6: Groq-backed answer generation from retrieved context."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Optional

from app.constants import APPROVED_SOURCE_URLS, MANDATORY_FOOTER_PREFIX


FACTUAL_SYSTEM_PROMPT = """You are a facts-only mutual fund FAQ assistant.
Answer the user's question using only the supplied source context.
If the context does not contain enough evidence, say that the information is not available in the approved source.
Do not infer, calculate, recommend, compare, rank, predict, or give investment advice.
Return only the answer body in at most three short sentences.
Do not include a URL or a source-date footer; the application adds those deterministically.
"""

STRICT_FACTUAL_SYSTEM_PROMPT = """You are a strict facts-only mutual fund FAQ assistant.
Use only the supplied source context and answer only what it explicitly supports.
If evidence is insufficient, state that the information is not available in the approved source.
Never provide advice, recommendations, rankings, comparisons, predictions, or inferred calculations.
Return only up to three short factual sentences with no URL, citation, or footer.
"""

UNKNOWN_ANSWER = "The requested information is not available in the approved source context."

_FACT_CONTEXT_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("nav", ("nav", "net asset value")),
    ("expense_ratio", ("expense ratio",)),
    ("exit_load", ("exit load",)),
    ("minimum_sip", ("minimum sip", "sip amount")),
    ("riskometer", ("riskometer",)),
    ("benchmark", ("benchmark",)),
    ("investment_objective", ("investment objective",)),
    ("fund_house", ("fund house", "asset management company")),
    ("tax_implications", ("tax implication", "taxation", "capital gains")),
    ("stamp_duty", ("stamp duty",)),
    ("category", ("category",)),
    ("plan_type", ("plan type", "direct plan", "regular plan", "growth plan")),
    ("aum", ("aum", "assets under management", "fund size")),
    ("returns", ("return", "returns")),
    ("holdings", ("holding", "portfolio")),
    ("sector_allocation", ("sector", "industry")),
    ("fund_managers", ("fund manager", "fund management", "managed by")),
)


class GenerationError(RuntimeError):
    """Raised when the provider cannot return a usable answer."""


@dataclass(frozen=True)
class GenerationRequest:
    """Inputs required to generate an answer."""

    query: str
    context: str
    source_url: str
    last_updated: str = "unknown"


class GroqClient:
    """Small provider wrapper so the generator can be tested without a network call."""

    def __init__(
        self,
        api_key: str,
        model: str,
        client: Optional[Any] = None,
        temperature: float = 0.1,
        max_tokens: int = 180,
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key is required")
        if not model.strip():
            raise ValueError("model is required")

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        if client is None:
            try:
                from groq import Groq
            except ImportError as exc:
                raise GenerationError(
                    "The groq package is required for Groq answer generation."
                ) from exc
            client = Groq(api_key=api_key)
        self.client = client

    def complete(
        self,
        query: str,
        context: str,
        system_prompt: str = FACTUAL_SYSTEM_PROMPT,
    ) -> str:
        """Generate an answer body from the supplied context only."""
        if not query.strip():
            raise ValueError("query cannot be empty")
        if not context.strip():
            raise ValueError("context cannot be empty")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Question:\n{query.strip()}\n\nSource context:\n{context.strip()}",
                    },
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError, KeyError) as exc:
            raise GenerationError("Groq returned an invalid response.") from exc
        except Exception as exc:
            raise GenerationError("Groq request failed.") from exc

        if not isinstance(content, str) or not content.strip():
            raise GenerationError("Groq returned an empty response.")
        return content.strip()


class GroqAnswerGenerator:
    """Generate and format a factual answer from one assembled source."""

    def __init__(self, client: GroqClient):
        self.client = client

    def generate(
        self,
        request: GenerationRequest,
        system_prompt: str = FACTUAL_SYSTEM_PROMPT,
    ) -> str:
        """Generate an answer, using a deterministic unknown path for weak evidence."""
        self._validate_request(request)
        if not request.context.strip():
            return self._format(UNKNOWN_ANSWER, request)
        if not _context_supports_query(request.query, request.context):
            return self._format(UNKNOWN_ANSWER, request)

        body = self.client.complete(request.query, request.context, system_prompt=system_prompt)
        return self._format(body, request)

    @staticmethod
    def _validate_request(request: GenerationRequest) -> None:
        if not request.query.strip():
            raise ValueError("query cannot be empty")
        if request.source_url not in APPROVED_SOURCE_URLS:
            raise ValueError("source_url must be an approved source URL")
        if not request.last_updated.strip():
            raise ValueError("last_updated cannot be empty")

    @staticmethod
    def _format(body: str, request: GenerationRequest) -> str:
        # Citation and freshness metadata are application-owned, not model-owned.
        clean_body = body.strip()
        return (
            f"{clean_body}\n\nSource: {request.source_url}\n"
            f"{MANDATORY_FOOTER_PREFIX} {request.last_updated}"
        )


def _context_supports_query(query: str, context: str) -> bool:
    """Require the selected context to mention the requested factual field."""
    normalized_query = " ".join(query.lower().split())
    normalized_context = " ".join(context.lower().split())
    for _, terms in _FACT_CONTEXT_TERMS:
        if any(term in normalized_query for term in terms):
            return any(term in normalized_context for term in terms)
    return True