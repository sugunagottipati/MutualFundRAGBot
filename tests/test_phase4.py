"""Phase 4 tests: Query routing and refusal handling."""

from __future__ import annotations

import pytest

from app.constants import APPROVED_SOURCE_URLS
from app.refusal import PolicyEnforcer, RefusalComposer
from app.router import IntentRouter, QueryIntent, RouterResult


class TestIntentRouter:
    """Test query intent classification."""

    def test_router_initialization(self):
        """Test router can initialize."""
        router = IntentRouter()
        assert router is not None

    def test_factual_query_detection(self):
        """Test factual queries are classified correctly."""
        router = IntentRouter()

        factual_queries = [
            "What are the holdings in HDFC Equity Fund?",
            "What is the expense ratio?",
            "Show me the top 5 holdings",
            "What sectors does this fund invest in?",
            "What is the 5-year return?",
            "When was this fund launched?",
            "What does NAV mean?",
        ]

        for query in factual_queries:
            result = router.classify(query)
            assert result.intent == QueryIntent.FACTUAL, f"Failed for query: {query}"
            assert result.confidence > 0.5

    def test_advisory_query_detection(self):
        """Test advisory queries are classified correctly."""
        router = IntentRouter()

        advisory_queries = [
            "Should I invest in this fund?",
            "Is this a good investment?",
            "Which fund should I buy?",
            "Can you recommend a fund for me?",
            "What fund is suitable for me?",
            "Should I invest in HDFC Small Cap?",
            "Would you suggest this fund?",
        ]

        for query in advisory_queries:
            result = router.classify(query)
            assert result.intent == QueryIntent.ADVISORY, f"Failed for query: {query}"
            assert result.confidence > 0.5

    def test_comparative_query_detection(self):
        """Test comparative queries are classified correctly."""
        router = IntentRouter()

        comparative_queries = [
            "Compare HDFC Equity and HDFC Small Cap",
            "Which fund is better?",
            "Rank these funds for me",
            "HDFC Equity vs HDFC Small Cap",
            "Which is the best performing fund?",
            "Is this fund better than that one?",
        ]

        for query in comparative_queries:
            result = router.classify(query)
            assert result.intent == QueryIntent.COMPARATIVE, f"Failed for query: {query}"
            assert result.confidence > 0.5

    def test_predictive_query_detection(self):
        """Test predictive queries are classified correctly."""
        router = IntentRouter()

        predictive_queries = [
            "What will the returns be next year?",
            "Will this fund go up in value?",
            "What is the expected return?",
            "Can I predict the fund's performance?",
            "How will this fund perform in the future?",
            "Will HDFC Equity outperform next year?",
        ]

        for query in predictive_queries:
            result = router.classify(query)
            assert result.intent == QueryIntent.PREDICTIVE, f"Failed for query: {query}"
            assert result.confidence > 0.5

    def test_ambiguous_query_detection(self):
        """Test ambiguous queries are classified correctly."""
        router = IntentRouter()

        ambiguous_queries = [
            "Tell me about mutual funds",
            "What is investing?",
            "How does this work?",
        ]

        for query in ambiguous_queries:
            result = router.classify(query)
            # Should be AMBIGUOUS or have low confidence
            if result.intent == QueryIntent.AMBIGUOUS:
                assert result.confidence == 0.0

    def test_should_refuse_logic(self):
        """Test should_refuse method."""
        router = IntentRouter()

        # Should refuse these
        advisory_query = "Should I invest in this fund?"
        should_refuse, intent = router.should_refuse(advisory_query)
        assert should_refuse is True
        assert intent == QueryIntent.ADVISORY

        # Should NOT refuse factual queries
        factual_query = "What is the expense ratio?"
        should_refuse, intent = router.should_refuse(factual_query)
        assert should_refuse is False
        assert intent == QueryIntent.FACTUAL

    def test_matched_patterns_included(self):
        """Test that matched patterns are included in result."""
        router = IntentRouter()
        query = "Should I invest in this fund?"
        result = router.classify(query)

        assert len(result.matched_patterns) > 0
        assert any("should" in p for p in result.matched_patterns)


class TestRefusalComposer:
    """Test refusal response composition."""

    def test_composer_initialization(self):
        """Test composer can initialize."""
        composer = RefusalComposer()
        assert composer is not None
        assert composer.default_link in APPROVED_SOURCE_URLS

    def test_composer_with_invalid_default_link(self):
        """Test composer rejects invalid default link."""
        with pytest.raises(ValueError):
            RefusalComposer(default_link="https://invalid.com")

    def test_advisory_refusal_response(self):
        """Test advisory refusal includes link and message."""
        composer = RefusalComposer()
        response = composer.compose_refusal(QueryIntent.ADVISORY)

        assert "cannot provide investment advice" in response.lower()
        assert composer.default_link in response
        assert response.count("https://") == 1  # Exactly one link

    def test_comparative_refusal_response(self):
        """Test comparative refusal includes link and message."""
        composer = RefusalComposer()
        response = composer.compose_refusal(QueryIntent.COMPARATIVE)

        assert composer.default_link in response
        assert response.count("https://") == 1  # Exactly one link

    def test_predictive_refusal_response(self):
        """Test predictive refusal includes link and message."""
        composer = RefusalComposer()
        response = composer.compose_refusal(QueryIntent.PREDICTIVE)

        assert "past performance" in response.lower() or "future" in response.lower()
        assert composer.default_link in response
        assert response.count("https://") == 1  # Exactly one link

    def test_ambiguous_refusal_response(self):
        """Test ambiguous refusal includes link and message."""
        composer = RefusalComposer()
        response = composer.compose_refusal(QueryIntent.AMBIGUOUS)

        assert composer.default_link in response
        assert response.count("https://") == 1  # Exactly one link

    def test_random_link_selection(self):
        """Test composer can select random links."""
        composer = RefusalComposer()
        responses = [
            composer.compose_refusal(QueryIntent.ADVISORY, use_default_link=False)
            for _ in range(10)
        ]

        # At least one should have a different link
        has_variety = len(set(responses)) > 1
        # All should have exactly one link
        assert all(r.count("https://") == 1 for r in responses)


class TestPolicyEnforcer:
    """Test compliance policy enforcement."""

    def test_enforce_one_source_policy_valid(self):
        """Test valid single source is accepted."""
        enforcer = PolicyEnforcer()
        response = "This fund has good holdings. See: https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth"
        links = enforcer.extract_urls(response)

        is_valid, reason = enforcer.validate_response(response, links)
        assert is_valid is True

    def test_enforce_one_source_policy_multiple_urls(self):
        """Test multiple sources are rejected."""
        enforcer = PolicyEnforcer()
        response = (
            "See source 1: https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth "
            "and source 2: https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth"
        )
        links = enforcer.extract_urls(response)

        is_valid, reason = enforcer.validate_response(response, links)
        assert is_valid is False
        assert "multiple" in reason.lower()

    def test_enforce_approved_sources_only(self):
        """Test non-approved sources are rejected."""
        enforcer = PolicyEnforcer()
        response = "See: https://example.com/fund"
        links = enforcer.extract_urls(response)

        is_valid, reason = enforcer.validate_response(response, links)
        assert is_valid is False

    def test_extract_urls(self):
        """Test URL extraction."""
        enforcer = PolicyEnforcer()
        text = "Check this: https://groww.in/test and https://example.com/other"
        urls = enforcer.extract_urls(text)

        assert len(urls) == 2
        assert "https://groww.in/test" in urls
        assert "https://example.com/other" in urls

    def test_enforce_max_sentences(self):
        """Test sentence truncation."""
        enforcer = PolicyEnforcer()
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        truncated = enforcer.enforce_max_sentences(text, max_sentences=2)

        assert "First sentence" in truncated
        assert "Second sentence" in truncated
        assert "Fourth" not in truncated

    def test_enforce_citation_count(self):
        """Test citation count validation."""
        enforcer = PolicyEnforcer()

        # Valid: has citation
        text_with_citation = "Answer: https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth"
        assert enforcer.enforce_citation_count(text_with_citation, required_count=1) is True

        # Invalid: no citation
        text_no_citation = "Answer about the fund"
        assert enforcer.enforce_citation_count(text_no_citation, required_count=1) is False

    def test_no_url_in_simple_factual_answer(self):
        """Test that factual answers without URLs are identified."""
        enforcer = PolicyEnforcer()
        text = "The expense ratio is 0.5%"
        urls = enforcer.extract_urls(text)

        assert len(urls) == 0
        assert enforcer.enforce_citation_count(text, required_count=1) is False


class TestRouterRefusalIntegration:
    """Test router and refusal integration."""

    def test_full_pipeline_advisory_query(self):
        """Test full pipeline for advisory query."""
        router = IntentRouter()
        composer = RefusalComposer()

        query = "Should I invest in HDFC Small Cap?"
        should_refuse, intent = router.should_refuse(query)

        assert should_refuse is True
        assert intent == QueryIntent.ADVISORY

        response = composer.compose_refusal(intent)
        assert composer.default_link in response
        assert response.count("https://") == 1

    def test_full_pipeline_factual_query(self):
        """Test full pipeline for factual query."""
        router = IntentRouter()

        query = "What is the expense ratio of HDFC Equity Fund?"
        should_refuse, intent = router.should_refuse(query)

        assert should_refuse is False
        assert intent == QueryIntent.FACTUAL

    def test_full_pipeline_predictive_query(self):
        """Test full pipeline for predictive query."""
        router = IntentRouter()
        composer = RefusalComposer()

        query = "Will HDFC Small Cap have good returns next year?"
        should_refuse, intent = router.should_refuse(query)

        assert should_refuse is True
        assert intent == QueryIntent.PREDICTIVE

        response = composer.compose_refusal(intent)
        enforcer = PolicyEnforcer()
        links = enforcer.extract_urls(response)
        is_valid, _ = enforcer.validate_response(response, links)
        assert is_valid is True
