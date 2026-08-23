"""Phase 4: Intent router for policy-safe query classification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class QueryIntent(Enum):
    """Query intent classification."""

    FACTUAL = "factual"  # Can be answered from indexed knowledge
    ADVISORY = "advisory"  # Asks for personal/investment advice
    COMPARATIVE = "comparative"  # Asks to rank/compare funds
    PREDICTIVE = "predictive"  # Asks for future performance or predictions
    AMBIGUOUS = "ambiguous"  # Unclear intent


@dataclass
class RouterResult:
    """Router classification result."""

    intent: QueryIntent
    confidence: float  # 0.0 to 1.0
    matched_patterns: list[str]  # Which patterns matched


class IntentRouter:
    """
    Rule-based router for query intent classification.
    
    Distinguishes:
    - Factual queries: Can answer from current indexed data
    - Advisory/recommendation queries: Should refuse
    - Predictive queries: Should refuse
    - Comparative queries: Risky, should refuse
    """

    def __init__(self):
        # Patterns for factual queries (SAFE)
        self.factual_patterns = [
            r"what.*holdings?",
            r"holdings?.*in",
            r"what.*does.*fund.*invest",
            r"show.*portfolio",
            r"what.*sectors?.*does.*invest",
            r"what.*sectors?.*invest",
            r"what.*expense.*ratio",
            r"what.*exit.*load",
            r"exit.*load.*(?:for|of|in)",
            r"what.*minimum.*investment",
            r"what.*minimum.*sip",
            r"minimum.*sip.*(?:amount|investment)",
            r"what.*riskometer",
            r"riskometer.*(?:classification|rating|level)",
            r"what.*benchmark(?: index)?",
            r"what.*returns?.*last.*year",
            r"what.*is.*return",
            r"1.?year.*return",
            r"5.?year.*return",
            r"10.?year.*return",
            r"top.*holdings?",
            r"what.*is.*the.*fund.*manager",
            r"when.*was.*fund.*launched",
            r"what.*is.*the.*fund.*size",
            r"what.*does.*mean",  # Glossary queries
            r"define\s",
            r"explain.*term",
            r"describe.*fund",
        ]

        # Patterns for advisory queries (UNSAFE - REFUSE)
        self.advisory_patterns = [
            r"should.*invest",
            r"should.*buy",
            r"is.*good.*investment",
            r"best.*fund.*for.*me",
            r"recommend.*fund",
            r"which.*fund.*should",
            r"would.*you.*suggest",
            r"is.*this.*fund.*worth",
            r"what.*fund.*should.*i.*buy",
            r"help.*me.*choose",
            r"suitable.*for.*me",
            r"right.*choice.*for",
            r"which.*fund.*is.*better.*for",
            r"is.*it.*safe.*to.*invest",
            r"can.*i.*make.*money",
            r"will.*i.*profit",
        ]

        # Patterns for comparative/ranking queries (UNSAFE - REFUSE)
        self.comparative_patterns = [
            r"compare",
            r"which.*is.*better",
            r"rank\s",
            r"best.*performing",
            r"top.*fund",
            r"outperform",
            r"better.*than",
            r"worse.*than",
            r"versus",
            r"\bvs\.?\b",
        ]

        # Patterns for predictive queries (UNSAFE - REFUSE)
        self.predictive_patterns = [
            r"will.*return",
            r"predict",
            r"forecast",
            r"expected.*return",
            r"future.*performance",
            r"when.*will.*price",
            r"will.*go.*up",
            r"will.*go.*down",
            r"what.*will.*happen",
            r"how.*will.*perform",
            r"next.*year",
        ]

    def classify(self, query: str) -> RouterResult:
        """
        Classify query intent.

        Args:
            query: User query

        Returns:
            RouterResult with intent and confidence
        """
        query_lower = query.lower().strip()

        # Check advisory patterns
        advisory_matches = self._match_patterns(query_lower, self.advisory_patterns)
        if advisory_matches:
            return RouterResult(
                intent=QueryIntent.ADVISORY,
                confidence=self._confidence_from_matches(advisory_matches),
                matched_patterns=advisory_matches,
            )

        # Check predictive patterns BEFORE comparative (more urgent to refuse)
        predictive_matches = self._match_patterns(query_lower, self.predictive_patterns)
        if predictive_matches:
            return RouterResult(
                intent=QueryIntent.PREDICTIVE,
                confidence=self._confidence_from_matches(predictive_matches),
                matched_patterns=predictive_matches,
            )

        # Check comparative patterns
        comparative_matches = self._match_patterns(query_lower, self.comparative_patterns)
        if comparative_matches:
            return RouterResult(
                intent=QueryIntent.COMPARATIVE,
                confidence=self._confidence_from_matches(comparative_matches),
                matched_patterns=comparative_matches,
            )

        # Check factual patterns
        factual_matches = self._match_patterns(query_lower, self.factual_patterns)
        if factual_matches:
            return RouterResult(
                intent=QueryIntent.FACTUAL,
                confidence=self._confidence_from_matches(factual_matches),
                matched_patterns=factual_matches,
            )

        # Default to ambiguous if no patterns matched
        return RouterResult(
            intent=QueryIntent.AMBIGUOUS,
            confidence=0.0,
            matched_patterns=[],
        )

    @staticmethod
    def _match_patterns(text: str, patterns: list[str]) -> list[str]:
        """Find which patterns match the text."""
        matches = []
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                matches.append(pattern)
        return matches

    @staticmethod
    def _confidence_from_matches(matches: list[str]) -> float:
        """Compute confidence from number of matching patterns."""
        # More matches = higher confidence
        if not matches:
            return 0.0
        if len(matches) == 1:
            return 0.7
        if len(matches) <= 3:
            return 0.85
        return 0.95

    def should_refuse(self, query: str) -> tuple[bool, QueryIntent]:
        """
        Determine if query should be refused.

        Returns:
            (should_refuse, intent)
        """
        result = self.classify(query)

        # Refuse advisory, comparative, and predictive
        should_refuse = result.intent in (
            QueryIntent.ADVISORY,
            QueryIntent.COMPARATIVE,
            QueryIntent.PREDICTIVE,
            QueryIntent.AMBIGUOUS,
        )

        return should_refuse, result.intent
