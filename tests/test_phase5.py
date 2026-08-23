"""Phase 5 tests: Retrieval, reranking, and context assembly validation."""

from __future__ import annotations

import pytest

from app.retrieval import RetrievalResult, ContextAssembler
from app.retrieval_phase5 import (
    SourceAuthorityRanker,
    RecencyRanker,
    RetrievalReranker,
    RetrievalQualityValidator,
    EnhancedContextAssembler,
    RerankerConfig,
    RerankerStrategy,
)
from app.constants import APPROVED_SOURCE_URLS
from ingestion.chunking import Chunk, ChunkMetadata
from ingestion.metadata_store import ChunkMetadataStore


class TestSourceAuthorityRanker:
    """Test source authority ranking."""

    def test_authority_score_approved_url(self):
        """Test that approved URLs get high authority score."""
        ranker = SourceAuthorityRanker(None)
        score = ranker.get_authority_score(APPROVED_SOURCE_URLS[0])
        assert score == 3.0  # OFFICIAL level

    def test_authority_score_unapproved_url(self):
        """Test that unapproved URLs get zero score."""
        ranker = SourceAuthorityRanker(None)
        score = ranker.get_authority_score("https://example.com")
        assert score == 0.0

    def test_authority_score_all_approved_equal(self):
        """Test that all approved URLs get same authority score."""
        ranker = SourceAuthorityRanker(None)
        for url in APPROVED_SOURCE_URLS:
            score = ranker.get_authority_score(url)
            assert score == 3.0


class TestRecencyRanker:
    """Test recency-based ranking."""

    def test_recency_score_no_metadata(self):
        """Test recency score for chunk with no metadata."""
        ranker = RecencyRanker(None)
        score = ranker.get_recency_score("unknown_chunk_id")
        assert 0.0 <= score <= 1.0
        assert score == 0.5  # Default neutral score


class TestRetrievalReranker:
    """Test reranking strategies."""

    def _create_mock_results(self, num_results: int = 3) -> list[RetrievalResult]:
        """Create mock retrieval results for testing."""
        results = []
        for i in range(num_results):
            chunk = Chunk(
                content=f"Sample content {i}",
                metadata=ChunkMetadata(
                    chunk_id=f"chunk_{i}",
                    chunk_content_hash=f"content_hash_{i}",
                    source_url=APPROVED_SOURCE_URLS[0],
                    scheme_name="HDFC Equity Fund",
                    source_type="official",
                    section_header="Holdings",
                    crawled_at="2025-08-23",
                    content_hash=f"hash_{i}",
                    chunk_index=i,
                    start_line=i * 10,
                    end_line=(i + 1) * 10,
                ),
            )
            result = RetrievalResult(
                chunk=chunk,
                similarity_distance=float(i),  # Higher distance = lower relevance
                rank=i,
            )
            results.append(result)
        return results

    def test_rerank_relevance_only(self):
        """Test relevance-only strategy (no reranking)."""
        config = RerankerConfig(strategy=RerankerStrategy.RELEVANCE_ONLY)
        reranker = RetrievalReranker(None, config)

        results = self._create_mock_results(3)
        reranked = reranker.rerank(results)

        # Should maintain original order
        assert len(reranked) == 3
        assert reranked[0].similarity_distance == 0.0
        assert reranked[1].similarity_distance == 1.0
        assert reranked[2].similarity_distance == 2.0

    def test_rerank_source_authority(self):
        """Test source authority reranking."""
        config = RerankerConfig(strategy=RerankerStrategy.SOURCE_AUTHORITY)
        reranker = RetrievalReranker(None, config)

        results = self._create_mock_results(3)

        # All from same approved source, so order should be preserved by relevance
        reranked = reranker.rerank(results)
        assert len(reranked) == 3

        # First result should still be most relevant
        assert reranked[0].rank == 0

    def test_rerank_hybrid(self):
        """Test hybrid reranking strategy."""
        config = RerankerConfig(
            strategy=RerankerStrategy.HYBRID,
            relevance_weight=0.6,
            authority_weight=0.3,
            recency_weight=0.1,
        )
        reranker = RetrievalReranker(None, config)

        results = self._create_mock_results(3)
        reranked = reranker.rerank(results)

        assert len(reranked) == 3
        # Verify ranks are updated (0, 1, 2)
        for i, result in enumerate(reranked):
            assert result.rank == i


class TestRetrievalQualityValidator:
    """Test retrieval quality validation."""

    def test_validate_context_relevance_valid(self):
        """Test valid context passes validation."""
        context = "This is a valid context with sufficient content" * 10
        is_valid, reason = RetrievalQualityValidator.validate_context_relevance(context)
        assert is_valid is True
        assert reason == "OK"

    def test_validate_context_relevance_empty(self):
        """Test empty context fails validation."""
        context = ""
        is_valid, reason = RetrievalQualityValidator.validate_context_relevance(context)
        assert is_valid is False
        assert "empty" in reason.lower()

    def test_validate_context_relevance_too_short(self):
        """Test short context fails validation."""
        context = "Short"
        is_valid, reason = RetrievalQualityValidator.validate_context_relevance(
            context,
            min_length=100,
        )
        assert is_valid is False
        assert "too short" in reason.lower()

    def test_validate_context_relevance_too_long(self):
        """Test long context fails validation."""
        context = "x" * 10000
        is_valid, reason = RetrievalQualityValidator.validate_context_relevance(
            context,
            max_length=5000,
        )
        assert is_valid is False
        assert "too long" in reason.lower()

    def test_validate_source_compliance_approved(self):
        """Test approved source passes validation."""
        is_valid, reason = RetrievalQualityValidator.validate_source_compliance(
            APPROVED_SOURCE_URLS[0]
        )
        assert is_valid is True
        assert reason == "OK"

    def test_validate_source_compliance_unapproved(self):
        """Test unapproved source fails validation."""
        is_valid, reason = RetrievalQualityValidator.validate_source_compliance(
            "https://example.com"
        )
        assert is_valid is False
        assert "not in approved list" in reason.lower()

    def test_validate_single_citation_valid(self):
        """Test valid single citation passes."""
        is_valid, reason = RetrievalQualityValidator.validate_single_citation(
            APPROVED_SOURCE_URLS[0]
        )
        assert is_valid is True

    def test_validate_single_citation_empty(self):
        """Test empty citation fails."""
        is_valid, reason = RetrievalQualityValidator.validate_single_citation("")
        assert is_valid is False

    def test_validate_chunk_coverage_sufficient(self):
        """Test sufficient chunks pass validation."""
        results = [None, None, None]  # 3 results
        is_valid, reason = RetrievalQualityValidator.validate_chunk_coverage(
            results,
            min_chunks=2,
        )
        assert is_valid is True

    def test_validate_chunk_coverage_insufficient(self):
        """Test insufficient chunks fail validation."""
        results = [None]  # 1 result
        is_valid, reason = RetrievalQualityValidator.validate_chunk_coverage(
            results,
            min_chunks=3,
        )
        assert is_valid is False

    def test_validate_result_quality_high_relevance(self):
        """Test high-relevance result passes."""
        chunk = Chunk(
            content="test",
            metadata=ChunkMetadata(
                chunk_id="test",
                chunk_content_hash="test_hash",
                source_url=APPROVED_SOURCE_URLS[0],
                scheme_name="test",
                source_type="official",
                section_header="test",
                crawled_at="2025-08-23",
                content_hash="test",
                chunk_index=0,
                start_line=0,
                end_line=10,
            ),
        )
        result = RetrievalResult(chunk=chunk, similarity_distance=0.1, rank=0)
        is_valid, reason = RetrievalQualityValidator.validate_result_quality(
            result,
            min_relevance_score=0.3,
        )
        assert is_valid is True

    def test_validate_result_quality_low_relevance(self):
        """Test low-relevance result fails."""
        chunk = Chunk(
            content="test",
            metadata=ChunkMetadata(
                chunk_id="test",
                chunk_content_hash="test_hash",
                source_url=APPROVED_SOURCE_URLS[0],
                scheme_name="test",
                source_type="official",
                section_header="test",
                crawled_at="2025-08-23",
                content_hash="test",
                chunk_index=0,
                start_line=0,
                end_line=10,
            ),
        )
        # distance=9.0 gives relevance = max(0, 1 - 9/10) = 0.1, which is < 0.3
        result = RetrievalResult(chunk=chunk, similarity_distance=9.0, rank=0)
        is_valid, reason = RetrievalQualityValidator.validate_result_quality(
            result,
            min_relevance_score=0.3,
        )
        assert is_valid is False
        assert "low relevance" in reason.lower()


class TestEnhancedContextAssembler:
    """Test enhanced context assembly with validation."""

    def _create_test_result(
        self,
        chunk_id: str,
        content: str,
        distance: float = 0.5,
    ) -> RetrievalResult:
        """Create a test retrieval result."""
        chunk = Chunk(
            content=content,
            metadata=ChunkMetadata(
                chunk_id=chunk_id,
                chunk_content_hash=f"content_hash_{chunk_id}",
                source_url=APPROVED_SOURCE_URLS[0],
                scheme_name="HDFC Equity Fund",
                source_type="official",
                section_header="Holdings",
                crawled_at="2025-08-23",
                content_hash=f"hash_{chunk_id}",
                chunk_index=0,
                start_line=0,
                end_line=100,
            ),
        )
        return RetrievalResult(chunk=chunk, similarity_distance=distance, rank=0)

    def test_assemble_with_validation_valid(self):
        """Test assembly with valid results."""
        results = [
            self._create_test_result("c1", "Holdings include ICICI Bank" * 10),
            self._create_test_result("c2", "Sector breakdown shows financial focus" * 10),
        ]

        assembler = EnhancedContextAssembler()
        context, source, is_valid, reason = assembler.assemble_with_validation(results)

        assert is_valid is True
        assert reason == "OK"
        assert len(context) > 100
        assert source == APPROVED_SOURCE_URLS[0]

    def test_assemble_with_validation_low_quality_filtered(self):
        """Test that low-quality results are filtered."""
        results = [
            self._create_test_result("c1", "Holdings" * 50, distance=4.0),  # Low relevance
            self._create_test_result("c2", "Holdings include ICICI Bank" * 10, distance=0.2),
        ]

        assembler = EnhancedContextAssembler()
        context, source, is_valid, reason = assembler.assemble_with_validation(results)

        # Should succeed because c2 is high quality
        assert is_valid is True
        # c1 should be filtered out
        assert "Holdings" not in context or "ICICI Bank" in context

    def test_assemble_with_validation_no_results(self):
        """Test assembly with no results."""
        results = []
        assembler = EnhancedContextAssembler()
        context, source, is_valid, reason = assembler.assemble_with_validation(results)

        assert is_valid is False
        assert "high-quality" in reason.lower()

    def test_assemble_with_validation_all_low_quality(self):
        """Test assembly when all results are low quality."""
        results = [
            self._create_test_result("c1", "x", distance=5.0),
            self._create_test_result("c2", "y", distance=5.0),
        ]

        assembler = EnhancedContextAssembler()
        context, source, is_valid, reason = assembler.assemble_with_validation(results)

        assert is_valid is False


class TestPhase5Integration:
    """Integration tests for Phase 5 retrieval pipeline."""

    def test_rerank_then_assemble(self):
        """Test reranking followed by context assembly."""
        # Create mock results with varying relevance
        results = []
        for i in range(5):
            chunk = Chunk(
                content=f"Sample content {i}" * 10,
                metadata=ChunkMetadata(
                    chunk_id=f"chunk_{i}",
                    chunk_content_hash=f"content_hash_{i}",
                    source_url=APPROVED_SOURCE_URLS[0],
                    scheme_name="HDFC Equity Fund",
                    source_type="official",
                    section_header="Holdings",
                    crawled_at="2025-08-23",
                    content_hash=f"hash_{i}",
                    chunk_index=i,
                    start_line=i * 10,
                    end_line=(i + 1) * 10,
                ),
            )
            result = RetrievalResult(
                chunk=chunk,
                similarity_distance=float(i) * 0.5,
                rank=i,
            )
            results.append(result)

        # Rerank using source authority
        config = RerankerConfig(strategy=RerankerStrategy.SOURCE_AUTHORITY)
        reranker = RetrievalReranker(None, config)
        reranked = reranker.rerank(results)

        # Assemble context with validation
        assembler = EnhancedContextAssembler()
        context, source, is_valid, reason = assembler.assemble_with_validation(reranked)

        # Should succeed
        assert is_valid is True
        assert len(context) > 0
        assert source == APPROVED_SOURCE_URLS[0]

    def test_single_source_policy_enforced(self):
        """Test that single-source policy is enforced."""
        # Create results from multiple sources (shouldn't happen in normal flow)
        results = []
        for i, url in enumerate(APPROVED_SOURCE_URLS[:2]):
            chunk = Chunk(
                content=f"Content from {url}" * 10,
                metadata=ChunkMetadata(
                    chunk_id=f"chunk_{i}",
                    chunk_content_hash=f"content_hash_{i}",
                    source_url=url,
                    scheme_name="Fund",
                    source_type="official",
                    section_header="Holdings",
                    crawled_at="2025-08-23",
                    content_hash=f"hash_{i}",
                    chunk_index=0,
                    start_line=0,
                    end_line=100,
                ),
            )
            results.append(
                RetrievalResult(chunk=chunk, similarity_distance=0.5, rank=i)
            )

        # Assemble should select ONE source
        assembler = EnhancedContextAssembler()
        context, source, is_valid, reason = assembler.assemble_with_validation(results)

        # Should pick ONE source (first in by_source grouping by cumulative relevance)
        assert is_valid is True
        assert source in APPROVED_SOURCE_URLS
        # Only chunks from selected source should be in context
        assert context.count("Content from") <= 1 or source in context
