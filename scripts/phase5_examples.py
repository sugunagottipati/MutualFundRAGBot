"""Phase 5: Retrieval examples showing reranking and context assembly."""

from datetime import datetime
from ingestion.chunking import Chunk, ChunkMetadata
from app.retrieval import Retriever, RetrievalResult, ContextAssembler
from app.retrieval_phase5 import (
    RetrievalReranker,
    RerankerConfig,
    RerankerStrategy,
    RetrievalQualityValidator,
    EnhancedContextAssembler,
)
from app.constants import APPROVED_SOURCE_URLS


def example_semantic_retrieval():
    """
    Example 1: Semantic retrieval with relevance scoring.
    
    Shows how semantic search retrieves chunks ranked by relevance.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Semantic Retrieval")
    print("=" * 80)

    # Example retrieved results (simulated from FAISS search)
    results = [
        RetrievalResult(
            chunk=Chunk(
                content="HDFC Equity Fund holds 35% in financial services including ICICI Bank and Axis Bank.",
                metadata=ChunkMetadata(
                    chunk_id="chunk_1",
                    chunk_content_hash="hash_1",
                    source_url=APPROVED_SOURCE_URLS[0],
                    scheme_name="HDFC Equity Fund",
                    source_type="official",
                    section_header="Holdings",
                    crawled_at="2025-08-23",
                    content_hash="doc_hash_1",
                    chunk_index=1,
                    start_line=10,
                    end_line=20,
                ),
            ),
            similarity_distance=0.3,  # Low distance = high relevance
            rank=0,
        ),
        RetrievalResult(
            chunk=Chunk(
                content="The fund focuses on large-cap equities with 60% allocation to banking and financial services.",
                metadata=ChunkMetadata(
                    chunk_id="chunk_2",
                    chunk_content_hash="hash_2",
                    source_url=APPROVED_SOURCE_URLS[0],
                    scheme_name="HDFC Equity Fund",
                    source_type="official",
                    section_header="Fund Overview",
                    crawled_at="2025-08-23",
                    content_hash="doc_hash_1",
                    chunk_index=0,
                    start_line=0,
                    end_line=10,
                ),
            ),
            similarity_distance=0.5,
            rank=1,
        ),
    ]

    print("\nRetrieved 2 chunks for query: 'What are the main holdings in HDFC Equity Fund?'")
    print("\nRank 0 (Most relevant):")
    print(f"  - Distance: {results[0].similarity_distance}")
    print(f"  - Relevance Score: {results[0].relevance_score:.2f}")
    print(f"  - Section: {results[0].chunk.metadata.section_header}")
    print(f"  - Content: {results[0].chunk.content[:60]}...")

    print("\nRank 1:")
    print(f"  - Distance: {results[1].similarity_distance}")
    print(f"  - Relevance Score: {results[1].relevance_score:.2f}")
    print(f"  - Section: {results[1].chunk.metadata.section_header}")
    print(f"  - Content: {results[1].chunk.content[:60]}...")


def example_reranking_strategies():
    """
    Example 2: Reranking strategies.
    
    Shows how different reranking strategies prioritize results.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Reranking Strategies")
    print("=" * 80)

    # Create mock retrieval results
    results = [
        RetrievalResult(
            chunk=Chunk(
                content="Content from chunk 1" * 5,
                metadata=ChunkMetadata(
                    chunk_id="chunk_1",
                    chunk_content_hash="hash_1",
                    source_url=APPROVED_SOURCE_URLS[0],
                    scheme_name="Fund",
                    source_type="official",
                    section_header="Holdings",
                    crawled_at="2025-08-23",
                    content_hash="hash_1",
                    chunk_index=0,
                    start_line=0,
                    end_line=10,
                ),
            ),
            similarity_distance=0.5,
            rank=0,
        ),
        RetrievalResult(
            chunk=Chunk(
                content="Content from chunk 2" * 5,
                metadata=ChunkMetadata(
                    chunk_id="chunk_2",
                    chunk_content_hash="hash_2",
                    source_url=APPROVED_SOURCE_URLS[0],
                    scheme_name="Fund",
                    source_type="official",
                    section_header="Expense Ratio",
                    crawled_at="2025-08-23",
                    content_hash="hash_2",
                    chunk_index=0,
                    start_line=0,
                    end_line=10,
                ),
            ),
            similarity_distance=1.0,
            rank=1,
        ),
    ]

    # Strategy 1: Relevance only (no reranking)
    config_relevance = RerankerConfig(strategy=RerankerStrategy.RELEVANCE_ONLY)
    reranker_relevance = RetrievalReranker(None, config_relevance)
    reranked_relevance = reranker_relevance.rerank(results)

    print("\nStrategy 1: RELEVANCE_ONLY")
    print("  Result order: Unchanged (sorted by semantic relevance)")
    for r in reranked_relevance:
        print(f"    - Rank {r.rank}: {r.chunk.metadata.section_header} (distance={r.similarity_distance})")

    # Strategy 2: Source authority
    config_authority = RerankerConfig(strategy=RerankerStrategy.SOURCE_AUTHORITY)
    reranker_authority = RetrievalReranker(None, config_authority)
    reranked_authority = reranker_authority.rerank(results)

    print("\nStrategy 2: SOURCE_AUTHORITY")
    print("  All results from approved sources → similar order with authority boost")
    for r in reranked_authority:
        print(f"    - Rank {r.rank}: {r.chunk.metadata.section_header} (authority=3.0)")

    # Strategy 3: Hybrid
    config_hybrid = RerankerConfig(
        strategy=RerankerStrategy.HYBRID,
        relevance_weight=0.6,
        authority_weight=0.3,
        recency_weight=0.1,
    )
    reranker_hybrid = RetrievalReranker(None, config_hybrid)
    reranked_hybrid = reranker_hybrid.rerank(results)

    print("\nStrategy 3: HYBRID")
    print("  Combines 60% relevance + 30% authority + 10% recency")
    for r in reranked_hybrid:
        print(f"    - Rank {r.rank}: {r.chunk.metadata.section_header}")


def example_context_assembly():
    """
    Example 3: Context assembly with one-citation policy.
    
    Shows how ContextAssembler enforces single-source citations.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Context Assembly (Single-Citation Policy)")
    print("=" * 80)

    # Multiple results from same source
    results = [
        RetrievalResult(
            chunk=Chunk(
                content="Holdings: ICICI Bank (5.2%), Axis Bank (4.8%), HDFC Bank (6.1%)" * 3,
                metadata=ChunkMetadata(
                    chunk_id="chunk_1",
                    chunk_content_hash="hash_1",
                    source_url=APPROVED_SOURCE_URLS[0],
                    scheme_name="HDFC Equity Fund",
                    source_type="official",
                    section_header="Holdings",
                    crawled_at="2025-08-23",
                    content_hash="hash_1",
                    chunk_index=1,
                    start_line=10,
                    end_line=30,
                ),
            ),
            similarity_distance=0.2,
            rank=0,
        ),
        RetrievalResult(
            chunk=Chunk(
                content="Expense Ratio: 0.40% for Direct Plan, 1.25% for Regular Plan" * 3,
                metadata=ChunkMetadata(
                    chunk_id="chunk_2",
                    chunk_content_hash="hash_2",
                    source_url=APPROVED_SOURCE_URLS[0],
                    scheme_name="HDFC Equity Fund",
                    source_type="official",
                    section_header="Expense Ratio",
                    crawled_at="2025-08-23",
                    content_hash="hash_1",
                    chunk_index=5,
                    start_line=50,
                    end_line=70,
                ),
            ),
            similarity_distance=0.4,
            rank=1,
        ),
    ]

    # Assemble context
    assembler = ContextAssembler()
    context, source_url = assembler.assemble_single_source_context(results)

    print(f"\nAssembled context from single source:")
    print(f"  Source URL: {source_url}")
    print(f"  Context length: {len(context)} characters")
    print(f"\nContext preview:")
    print("  " + context[:200].replace("\n", "\n  ") + "...")


def example_quality_validation():
    """
    Example 4: Quality validation of retrieved context.
    
    Shows various quality checks applied to context.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Quality Validation")
    print("=" * 80)

    chunk = Chunk(
        content="HDFC Equity Fund is a diversified large-cap equity fund with exposure to multiple sectors. "
        "The fund focuses on financial services (35%), IT (20%), Pharma (15%), and other sectors. "
        "Direct Plan expense ratio: 0.40%, Regular Plan: 1.25%. "
        "The fund has delivered consistent returns over the past 5 years." * 2,
        metadata=ChunkMetadata(
            chunk_id="chunk_1",
            chunk_content_hash="hash_1",
            source_url=APPROVED_SOURCE_URLS[0],
            scheme_name="HDFC Equity Fund",
            source_type="official",
            section_header="Fund Overview",
            crawled_at="2025-08-23",
            content_hash="hash_1",
            chunk_index=0,
            start_line=0,
            end_line=50,
        ),
    )
    result = RetrievalResult(chunk=chunk, similarity_distance=0.3, rank=0)

    print("\n1. Relevance validation:")
    is_valid, reason = RetrievalQualityValidator.validate_context_relevance(chunk.content)
    print(f"   - {reason}")

    print("\n2. Source compliance validation:")
    is_valid, reason = RetrievalQualityValidator.validate_source_compliance(chunk.metadata.source_url)
    print(f"   - {reason}")

    print("\n3. Single citation validation:")
    is_valid, reason = RetrievalQualityValidator.validate_single_citation(chunk.metadata.source_url)
    print(f"   - {reason}")

    print("\n4. Result quality validation:")
    is_valid, reason = RetrievalQualityValidator.validate_result_quality(result, min_relevance_score=0.3)
    print(f"   - {reason}")


def example_enhanced_assembly():
    """
    Example 5: Enhanced context assembly with validation.
    
    Shows end-to-end pipeline with quality checks.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Enhanced Context Assembly with Validation")
    print("=" * 80)

    # Mix of high and low quality results
    results = [
        RetrievalResult(
            chunk=Chunk(
                content="Holdings include top financial stocks with strong track records." * 5,
                metadata=ChunkMetadata(
                    chunk_id="chunk_1",
                    chunk_content_hash="hash_1",
                    source_url=APPROVED_SOURCE_URLS[0],
                    scheme_name="Fund",
                    source_type="official",
                    section_header="Holdings",
                    crawled_at="2025-08-23",
                    content_hash="hash_1",
                    chunk_index=0,
                    start_line=0,
                    end_line=10,
                ),
            ),
            similarity_distance=0.2,  # High relevance
            rank=0,
        ),
        RetrievalResult(
            chunk=Chunk(
                content="x" * 20,  # Low quality (very short)
                metadata=ChunkMetadata(
                    chunk_id="chunk_2",
                    chunk_content_hash="hash_2",
                    source_url=APPROVED_SOURCE_URLS[0],
                    scheme_name="Fund",
                    source_type="official",
                    section_header="Fees",
                    crawled_at="2025-08-23",
                    content_hash="hash_2",
                    chunk_index=1,
                    start_line=10,
                    end_line=20,
                ),
            ),
            similarity_distance=8.0,  # Low relevance
            rank=1,
        ),
    ]

    assembler = EnhancedContextAssembler()
    context, source, is_valid, reason = assembler.assemble_with_validation(results)

    print(f"\nValidation result: {'✓ PASS' if is_valid else '✗ FAIL'}")
    print(f"  - Reason: {reason}")
    print(f"  - Context length: {len(context)} chars")
    print(f"  - Source URL: {source}")
    print(f"\nContext preview:")
    print("  " + context[:150].replace("\n", "\n  ") + "...")


def main():
    """Run all examples."""
    print("\n" + "#" * 80)
    print("# PHASE 5: RETRIEVAL WITH RERANKING AND CONTEXT ASSEMBLY")
    print("# Examples demonstrating retrieval quality and compliance")
    print("#" * 80)

    example_semantic_retrieval()
    example_reranking_strategies()
    example_context_assembly()
    example_quality_validation()
    example_enhanced_assembly()

    print("\n" + "#" * 80)
    print("# Phase 5 Examples Complete")
    print("#" * 80 + "\n")


if __name__ == "__main__":
    main()
