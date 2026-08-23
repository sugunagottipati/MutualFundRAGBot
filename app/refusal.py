"""Phase 4: Refusal response composer with compliance enforcement."""

from __future__ import annotations

import random

from app.constants import APPROVED_SOURCE_URLS, DEFAULT_REFUSAL_LINK, REFUSAL_MESSAGE
from app.router import QueryIntent


class RefusalComposer:
    """
    Compose polite refusal responses with one approved Groww link.
    
    Enforces:
    - One-source policy: Only one link from approved list
    - Politeness: Professional, helpful tone
    - Clarity: Why the query is out of scope
    """

    def __init__(self, default_link: str = DEFAULT_REFUSAL_LINK):
        """
        Initialize composer.

        Args:
            default_link: Default Groww URL to include (must be approved)
        """
        if default_link not in APPROVED_SOURCE_URLS:
            raise ValueError(f"default_link must be in APPROVED_SOURCE_URLS")
        self.default_link = default_link

    def compose_refusal(
        self,
        intent: QueryIntent,
        use_default_link: bool = True,
    ) -> str:
        """
        Compose refusal response based on intent.

        Args:
            intent: Classified query intent
            use_default_link: If True, always use default_link; else random from approved

        Returns:
            Polite refusal message with one approved Groww URL
        """
        selected_link = self.default_link if use_default_link else random.choice(APPROVED_SOURCE_URLS)

        if intent == QueryIntent.ADVISORY:
            return self._compose_advisory_refusal(selected_link)
        elif intent == QueryIntent.COMPARATIVE:
            return self._compose_comparative_refusal(selected_link)
        elif intent == QueryIntent.PREDICTIVE:
            return self._compose_predictive_refusal(selected_link)
        elif intent == QueryIntent.AMBIGUOUS:
            return self._compose_ambiguous_refusal(selected_link)
        else:
            # Shouldn't reach here, but fallback
            return self._compose_general_refusal(selected_link)

    @staticmethod
    def _compose_advisory_refusal(link: str) -> str:
        """Refusal for investment advice queries."""
        return (
            f"{REFUSAL_MESSAGE}\n\n"
            f"For more information about fund options and details, "
            f"please visit: {link}"
        )

    @staticmethod
    def _compose_comparative_refusal(link: str) -> str:
        """Refusal for fund comparison queries."""
        return (
            f"{REFUSAL_MESSAGE}\n\n"
            f"To compare different funds and their characteristics, "
            f"please refer to: {link}"
        )

    @staticmethod
    def _compose_predictive_refusal(link: str) -> str:
        """Refusal for future performance queries."""
        return (
            f"{REFUSAL_MESSAGE}\n\n"
            f"Past performance does not guarantee future results. "
            f"For historical fund data and current details, visit: {link}"
        )

    @staticmethod
    def _compose_ambiguous_refusal(link: str) -> str:
        """Refusal for ambiguous queries."""
        return (
            f"{REFUSAL_MESSAGE}\n\n"
            f"I can help with factual questions about fund details. "
            f"For more information: {link}"
        )

    @staticmethod
    def _compose_general_refusal(link: str) -> str:
        """General refusal fallback."""
        return (
            f"{REFUSAL_MESSAGE}\n\n"
            f"For more details: {link}"
        )


class PolicyEnforcer:
    """
    Enforce one-source policy and compliance constraints on responses.
    """

    @staticmethod
    def validate_response(response: str, links_in_response: list[str]) -> tuple[bool, str]:
        """
        Validate response against policies.

        Args:
            response: The response to validate
            links_in_response: URLs found in the response

        Returns:
            (is_valid, reason)
        """
        # Check: Only one source URL allowed
        approved_urls_in_response = [
            url for url in links_in_response if url in APPROVED_SOURCE_URLS
        ]

        # Check: No non-approved URLs
        non_approved_urls = [
            url for url in links_in_response if url not in APPROVED_SOURCE_URLS
        ]

        if non_approved_urls:
            return False, f"Response contains non-approved source URL: {non_approved_urls[0]}"

        if len(approved_urls_in_response) > 1:
            return False, "Response contains multiple source URLs (one-source policy violated)"

        return True, "OK"

    @staticmethod
    def extract_urls(text: str) -> list[str]:
        """Extract https:// URLs from text."""
        import re

        url_pattern = r"https://[^\s\)\"\'>\]]*"
        return re.findall(url_pattern, text)

    @staticmethod
    def enforce_max_sentences(text: str, max_sentences: int = 3) -> str:
        """Truncate response to max sentences."""
        from app.constants import MAX_ANSWER_SENTENCES

        max_sentences = max_sentences or MAX_ANSWER_SENTENCES

        # Simple sentence splitting on ". "
        sentences = text.split(". ")
        if len(sentences) > max_sentences:
            truncated = ". ".join(sentences[:max_sentences]) + "."
            return truncated
        return text

    @staticmethod
    def enforce_citation_count(text: str, required_count: int = 1) -> bool:
        """Verify minimum citations present."""
        from app.constants import REQUIRED_CITATION_COUNT

        required_count = required_count or REQUIRED_CITATION_COUNT

        # Count URLs
        import re

        urls = re.findall(r"https://[^\s\)\"\'>\]]*", text)
        return len(urls) >= required_count

    @staticmethod
    def enforce_footer_prefix(text: str) -> str:
        """Ensure answer includes footer with source attribution."""
        from app.constants import MANDATORY_FOOTER_PREFIX

        if MANDATORY_FOOTER_PREFIX not in text:
            # Add footer if missing (for refusal responses)
            if text.endswith("."):
                text = text[:-1]
            text += f"\n\n{MANDATORY_FOOTER_PREFIX} [See link above]"

        return text
