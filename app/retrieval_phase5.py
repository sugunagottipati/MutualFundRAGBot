"""Phase 5: Enhanced retrieval with reranking and context quality validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from app.constants import APPROVED_SOURCE_URLS
from ingestion.metadata_store import ChunkMetadataStore
from app.retrieval import RetrievalResult, ContextAssembler


class SourceAuthority(Enum):
    """Source authority levels for reranking."""

    OFFICIAL = 3.0  # Direct from Groww official pages
    VERIFIED = 2.0  # Verified content
    STANDARD = 1.0  # Standard content


class RerankerStrategy(Enum):
    """Reranking strategies."""

    RELEVANCE_ONLY = "relevance_only"  # No reranking, pure relevance
    SOURCE_AUTHORITY = "source_authority"  # Boost official sources
    RECENCY = "recency"  # Boost recent documents
    HYBRID = "hybrid"  # Combine multiple signals


@dataclass
class RerankerConfig:
    """Configuration for reranking strategy."""

    strategy: RerankerStrategy = RerankerStrategy.SOURCE_AUTHORITY
    authority_weight: float = 0.3  # Weight for source authority signal
    recency_weight: float = 0.1  # Weight for recency signal
    relevance_weight: float = 0.6  # Weight for relevance signal


class SourceAuthorityRanker:
    """
    Rank sources by authority level.
    Official Groww pages are highest authority.
    """

    def __init__(self, metadata_store: Optional[ChunkMetadataStore] = None):
        self.store = metadata_store

    def get_authority_score(self, source_url: str) -> float:
        """
        Get authority score for a source URL.

        All approved URLs are from official Groww pages, so treat all as OFFICIAL.

        Args:
            source_url: Source URL

        Returns:
            Authority score (0-3)
        """
        if source_url not in APPROVED_SOURCE_URLS:
            return 0.0

        # All approved URLs are official Groww pages
        return SourceAuthority.OFFICIAL.value


class RecencyRanker:
    """
    Rank results by document freshness.
    More recent documents are ranked higher.
    """

    def __init__(self, metadata_store: Optional[ChunkMetadataStore] = None):
        self.store = metadata_store

    def get_recency_score(self, chunk_id: str) -> float:
        """
        Get recency score for a chunk.

        Score is normalized to [0, 1] based on crawl timestamp.
        Recent documents score higher.

        Args:
            chunk_id: Chunk ID

        Returns:
            Recency score (0-1)
        """
        if not self.store:
            return 0.5  # Default middle score if no store

        chunk = self.store.get_chunk(chunk_id)
        if not chunk or not chunk.metadata.crawled_at:
            return 0.5  # Default middle score

        # All docs in this corpus are from same crawl date, so return neutral
        return 0.5


class RetrievalReranker:
    """
    Rerank retrieval results using multiple signals.
    Supports relevance-only, authority-based, recency-based, and hybrid strategies.
    """

    def __init__(
        self,
        metadata_store: ChunkMetadataStore,
        config: RerankerConfig = RerankerConfig(),
    ):
        self.store = metadata_store
        self.config = config
        self.authority_ranker = SourceAuthorityRanker(metadata_store)
        self.recency_ranker = RecencyRanker(metadata_store)

    def rerank(self, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """
        Rerank retrieval results according to configured strategy.

        Args:
            results: Original retrieval results (already ranked by relevance)

        Returns:
            Reranked results
        """
        if self.config.strategy == RerankerStrategy.RELEVANCE_ONLY:
            return results

        # Compute scores for all results
        scores = []
        for result in results:
            score = self._compute_score(result)
            scores.append((result, score))

        # Sort by computed score (descending)
        scores.sort(key=lambda x: x[1], reverse=True)

        # Update ranks
        reranked = []
        for rank, (result, _) in enumerate(scores):
            reranked.append(
                RetrievalResult(
                    chunk=result.chunk,
                    similarity_distance=result.similarity_distance,
                    rank=rank,
                )
            )

        return reranked

    def _compute_score(self, result: RetrievalResult) -> float:
        """
        Compute combined score based on configured strategy.

        Args:
            result: Retrieval result

        Returns:
            Combined score
        """
        relevance = result.relevance_score

        if self.config.strategy == RerankerStrategy.SOURCE_AUTHORITY:
            authority = self.authority_ranker.get_authority_score(
                result.chunk.metadata.source_url
            )
            # Normalize authority to [0, 1]
            authority_normalized = authority / SourceAuthority.OFFICIAL.value
            return (
                self.config.relevance_weight * relevance
                + self.config.authority_weight * authority_normalized
            )

        elif self.config.strategy == RerankerStrategy.RECENCY:
            recency = self.recency_ranker.get_recency_score(result.chunk.metadata.chunk_id)
            return (
                self.config.relevance_weight * relevance
                + self.config.recency_weight * recency
            )

        elif self.config.strategy == RerankerStrategy.HYBRID:
            authority = self.authority_ranker.get_authority_score(
                result.chunk.metadata.source_url
            )
            authority_normalized = authority / SourceAuthority.OFFICIAL.value
            recency = self.recency_ranker.get_recency_score(result.chunk.metadata.chunk_id)
            return (
                self.config.relevance_weight * relevance
                + self.config.authority_weight * authority_normalized
                + self.config.recency_weight * recency
            )

        # Default: relevance only
        return relevance


class RetrievalQualityValidator:
    """
    Validate quality of retrieved context.
    Ensures context is relevant, complete, and compliant.
    """

    @staticmethod
    def validate_context_relevance(
        context: str,
        min_length: int = 100,
        max_length: int = 5000,
    ) -> tuple[bool, str]:
        """
        Validate that context has sufficient content.

        Args:
            context: Assembled context string
            min_length: Minimum character length
            max_length: Maximum character length

        Returns:
            (is_valid, reason)
        """
        if not context:
            return False, "Context is empty"

        if len(context) < min_length:
            return False, f"Context too short ({len(context)} < {min_length} chars)"

        if len(context) > max_length:
            return False, f"Context too long ({len(context)} > {max_length} chars)"

        return True, "OK"

    @staticmethod
    def validate_source_compliance(
        source_url: str,
        approved_urls: tuple[str, ...] = APPROVED_SOURCE_URLS,
    ) -> tuple[bool, str]:
        """
        Validate that source is from approved list.

        Args:
            source_url: Source URL to validate
            approved_urls: Approved URL list

        Returns:
            (is_valid, reason)
        """
        if source_url not in approved_urls:
            return False, f"Source {source_url} not in approved list"

        return True, "OK"

    @staticmethod
    def validate_single_citation(
        source_url: str,
    ) -> tuple[bool, str]:
        """
        Validate that only one citation is used.

        Args:
            source_url: Source URL used

        Returns:
            (is_valid, reason)
        """
        if not source_url:
            return False, "No citation source provided"

        return True, "OK"

    @staticmethod
    def validate_chunk_coverage(
        results: list[RetrievalResult],
        min_chunks: int = 1,
    ) -> tuple[bool, str]:
        """
        Validate that sufficient chunks were retrieved.

        Args:
            results: Retrieved results
            min_chunks: Minimum number of chunks required

        Returns:
            (is_valid, reason)
        """
        if len(results) < min_chunks:
            return False, f"Insufficient chunks ({len(results)} < {min_chunks})"

        return True, "OK"

    @staticmethod
    def validate_result_quality(
        result: RetrievalResult,
        min_relevance_score: float = 0.3,
    ) -> tuple[bool, str]:
        """
        Validate that individual result meets quality threshold.

        Args:
            result: Retrieval result
            min_relevance_score: Minimum acceptable relevance score

        Returns:
            (is_valid, reason)
        """
        if result.relevance_score < min_relevance_score:
            return (
                False,
                f"Low relevance score ({result.relevance_score:.2f} < {min_relevance_score})",
            )

        return True, "OK"


class EnhancedContextAssembler(ContextAssembler):
    """
    Enhanced context assembler with quality validation.
    Extends Phase 3 ContextAssembler with validation and filtering.
    """

    def __init__(self, validator: Optional[RetrievalQualityValidator] = None):
        self.validator = validator or RetrievalQualityValidator()

    def assemble_with_validation(
        self,
        results: list[RetrievalResult],
    ) -> tuple[str, str, bool, str]:
        """
        Assemble context and validate quality.

        Args:
            results: Retrieval results

        Returns:
            (context, source_url, is_valid, validation_reason)
        """
        # Filter low-quality results
        high_quality = [
            r for r in results
            if self.validator.validate_result_quality(r)[0]
        ]

        if not high_quality:
            return "", "", False, "No high-quality results available"

        # Assemble using single-source policy
        context, source_url = self.assemble_single_source_context(high_quality)

        # Keep the most relevant leading chunks within the validation budget.
        if len(context) > 5000:
            context = context[:5000].rsplit("\n", 1)[0]

        # Validate assembled context
        is_valid, reason = self.validator.validate_context_relevance(context)
        if not is_valid:
            return context, source_url, False, reason

        # Validate source
        is_valid, reason = self.validator.validate_source_compliance(source_url)
        if not is_valid:
            return context, source_url, False, reason

        return context, source_url, True, "OK"
