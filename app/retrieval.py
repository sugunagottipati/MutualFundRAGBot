"""Phase 3: Retrieval module with semantic search and metadata filtering."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

import numpy as np

from app.constants import APPROVED_SOURCE_URLS
from ingestion.embeddings import EmbeddingsClient
from ingestion.index import ChromaIndexBuilder
from ingestion.metadata_store import ChunkMetadataStore
from ingestion.chunking import Chunk


_FUND_QUERY_ALIASES: tuple[tuple[str, str], ...] = (
    ("hdfc gold etf fund of fund", "hdfc-gold-etf-fund-of-fund-direct-plan-growth"),
    ("hdfc retirement savings fund", "hdfc-retirement-savings-fund-equity-plan-direct-growth"),
    ("hdfc large and mid cap fund", "hdfc-large-and-mid-cap-fund-direct-growth"),
    ("hdfc small cap fund", "hdfc-small-cap-fund-direct-growth"),
    ("hdfc mid cap fund", "hdfc-mid-cap-fund-direct-growth"),
    ("hdfc large cap fund", "hdfc-large-cap-fund-direct-growth"),
    ("hdfc equity fund", "hdfc-equity-fund-direct-growth"),
)

_FACT_QUERY_ALIASES: tuple[tuple[str, str], ...] = (
    ("net asset value", "nav"),
    ("nav", "nav"),
    ("expense ratio", "expense_ratio"),
    ("exit load", "exit_load"),
    ("minimum sip", "minimum_sip"),
    ("sip amount", "minimum_sip"),
    ("riskometer", "riskometer"),
    ("benchmark", "benchmark"),
    ("investment objective", "investment_objective"),
    ("fund house", "fund_house"),
    ("asset management company", "fund_house"),
    ("tax implication", "tax_implications"),
    ("taxation", "tax_implications"),
    ("stamp duty", "stamp_duty"),
    ("category", "category"),
    ("plan type", "plan_type"),
    ("direct plan", "plan_type"),
    ("aum", "aum"),
    ("fund size", "aum"),
    ("return", "returns"),
    ("returns", "returns"),
    ("holdings", "holdings"),
    ("portfolio", "holdings"),
    ("sector", "sector_allocation"),
    ("fund manager", "fund_managers"),
    ("fund managers", "fund_managers"),
)


def _source_url_from_query(query: str) -> Optional[str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", query.lower()).strip()
    for alias, slug in _FUND_QUERY_ALIASES:
        if alias in normalized:
            return f"https://groww.in/mutual-funds/{slug}"
    return None


def _fact_type_from_query(query: str) -> Optional[str]:
    """Return the canonical factual field requested by a query, if any."""
    normalized = re.sub(r"[^a-z0-9]+", " ", query.lower()).strip()
    for alias, fact_type in _FACT_QUERY_ALIASES:
        if alias in normalized:
            return fact_type
    return None


@dataclass
class RetrievalResult:
    """A single retrieval result with full traceability."""

    chunk: Chunk
    similarity_distance: float
    rank: int

    @property
    def relevance_score(self) -> float:
        """Convert distance to relevance score (0-1, higher is better)."""
        # L2 distance: convert to similarity
        # Clamp to [0, 1]
        return max(0.0, 1.0 - (self.similarity_distance / 10.0))


class Retriever:
    """
    Semantic search retriever with metadata filtering and compliance enforcement.
    """

    def __init__(
        self,
        embeddings_client: EmbeddingsClient,
        vector_index: ChromaIndexBuilder,
        metadata_store: ChunkMetadataStore,
    ):
        self.embeddings = embeddings_client
        self.index = vector_index
        self.store = metadata_store

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        allowed_source_urls: Optional[tuple[str, ...]] = None,
        allowed_section_headers: Optional[list[str]] = None,
    ) -> list[RetrievalResult]:
        """
        Retrieve relevant chunks for a query with optional filtering.

        Args:
            query: User query
            top_k: Number of candidates to retrieve
            allowed_source_urls: Filter to these sources (None = all approved)
            allowed_section_headers: Filter to these sections (None = all)

        Returns:
            List of RetrievalResult objects, ranked by relevance
        """
        if allowed_source_urls is None:
            inferred_source = _source_url_from_query(query)
            allowed_source_urls = (
                (inferred_source,) if inferred_source else APPROVED_SOURCE_URLS
            )

        # Embed query
        query_embedding = self.embeddings.embed(query)

        # Search the configured vector database
        source_filter = allowed_source_urls[0] if len(allowed_source_urls) == 1 else None
        chunk_ids, distances = self.index.search(
            query_embedding,
            k=top_k,
            source_url=source_filter,
        )

        results = []
        for rank, (chunk_id, distance) in enumerate(zip(chunk_ids, distances)):
            chunk = self.store.get_chunk(chunk_id)
            if not chunk:
                continue

            # Apply source URL filter
            if chunk.metadata.source_url not in allowed_source_urls:
                continue

            # Apply section header filter
            if allowed_section_headers and chunk.metadata.section_header not in allowed_section_headers:
                continue

            result = RetrievalResult(
                chunk=chunk,
                similarity_distance=distance,
                rank=rank,
            )
            results.append(result)

        fact_type = _fact_type_from_query(query)
        if fact_type:
            results.sort(
                key=lambda result: (
                    result.chunk.metadata.fact_type != fact_type,
                    -result.relevance_score,
                )
            )
        return results[:top_k]

    def retrieve_by_section(
        self,
        section_header: str,
        allowed_source_urls: Optional[tuple[str, ...]] = None,
    ) -> list[Chunk]:
        """
        Retrieve all chunks from a specific section (non-semantic).
        Useful for fetching structured data like holdings, expense ratios, etc.

        Args:
            section_header: Section header to retrieve
            allowed_source_urls: Filter to these sources

        Returns:
            List of chunks
        """
        if allowed_source_urls is None:
            allowed_source_urls = APPROVED_SOURCE_URLS

        chunks = self.store.get_chunks_by_section_header(section_header)
        return [c for c in chunks if c.metadata.source_url in allowed_source_urls]

    def retrieve_by_source_url(self, source_url: str) -> list[Chunk]:
        """Retrieve all chunks from a specific source."""
        if source_url not in APPROVED_SOURCE_URLS:
            return []
        return self.store.get_chunks_by_source_url(source_url)

    def retrieve_by_scheme_name(
        self,
        scheme_name: str,
        allowed_source_urls: Optional[tuple[str, ...]] = None,
    ) -> list[Chunk]:
        """Retrieve all chunks for a specific mutual fund scheme."""
        if allowed_source_urls is None:
            allowed_source_urls = APPROVED_SOURCE_URLS

        chunks = self.store.get_chunks_by_scheme_name(scheme_name)
        return [c for c in chunks if c.metadata.source_url in allowed_source_urls]

    def batch_retrieve(
        self,
        queries: list[str],
        top_k: int = 10,
        allowed_source_urls: Optional[tuple[str, ...]] = None,
    ) -> list[list[RetrievalResult]]:
        """Batch retrieve for multiple queries."""
        results = []
        for query in queries:
            results.append(self.retrieve(query, top_k, allowed_source_urls))
        return results


class ContextAssembler:
    """
    Assemble retrieved chunks into context for answer generation.
    Enforces one-citation policy and groups by source URL.
    """

    @staticmethod
    def assemble_single_source_context(results: list[RetrievalResult]) -> tuple[str, str]:
        """
        Assemble context from results, selecting one source URL.

        Args:
            results: Retrieval results ranked by relevance

        Returns:
            (assembled_context, selected_source_url)
        """
        if not results:
            return "", ""

        # Group by source URL
        by_source = {}
        for result in results:
            source = result.chunk.metadata.source_url
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(result)

        # Select source with highest cumulative relevance
        best_source = None
        best_score = -1
        for source, source_results in by_source.items():
            total_score = sum(r.relevance_score for r in source_results)
            if total_score > best_score:
                best_score = total_score
                best_source = source

        if not best_source:
            return "", ""

        # Assemble context from best source
        source_results = by_source[best_source]
        context_parts = []

        for result in source_results:
            chunk = result.chunk
            # Include section header for context
            header = f"[{chunk.metadata.section_header}]"
            context_parts.append(f"{header}\n{chunk.content}")

        context = "\n\n".join(context_parts)
        return context, best_source

    @staticmethod
    def assemble_multi_section_context(
        results: list[RetrievalResult],
        max_sections: int = 3,
    ) -> dict:
        """
        Assemble context grouped by section headers.

        Useful when answering questions that require multiple sections
        (e.g., "Compare expense ratios and holdings").

        Args:
            results: Retrieval results
            max_sections: Maximum number of sections to include

        Returns:
            Dict with section headers as keys and context strings as values
        """
        by_section = {}
        for result in results:
            section = result.chunk.metadata.section_header
            if section not in by_section:
                by_section[section] = []
            by_section[section].append(result.chunk)

        # Sort sections by number of relevant chunks (descending)
        sorted_sections = sorted(by_section.items(), key=lambda x: len(x[1]), reverse=True)

        context_dict = {}
        for section, chunks in sorted_sections[:max_sections]:
            content_parts = [c.content for c in chunks]
            context_dict[section] = "\n\n".join(content_parts)

        return context_dict
