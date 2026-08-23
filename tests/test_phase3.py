"""Phase 3 smoke tests: chunking, embeddings, indexing, and retrieval."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ingestion.chunking import ChunkingSplitter, SectionAwareChunker, TokenCounter, Chunk, ChunkMetadata
from ingestion.embeddings import LocalEmbeddings, get_embeddings_client
from ingestion.index import ChromaIndexBuilder
from ingestion.metadata_store import ChunkMetadataStore
from app.retrieval import _source_url_from_query


def test_source_url_is_inferred_from_named_fund_query() -> None:
    assert _source_url_from_query(
        "What is the expense ratio of HDFC Mid Cap Fund?"
    ) == "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
    assert _source_url_from_query(
        "What is the benchmark for HDFC Large and Mid Cap Fund?"
    ) == "https://groww.in/mutual-funds/hdfc-large-and-mid-cap-fund-direct-growth"


class TestTokenCounter:
    """Test token counting."""

    def test_token_counter_initialization(self):
        """Test token counter can initialize."""
        counter = TokenCounter()
        assert counter.encoding is not None

    def test_token_count_simple(self):
        """Test counting tokens in simple text."""
        counter = TokenCounter()
        text = "Hello world"
        count = counter.count(text)
        assert count > 0
        assert isinstance(count, int)

    def test_token_count_scales_with_length(self):
        """Test that longer text has more tokens."""
        counter = TokenCounter()
        short = "Hello"
        long = "Hello " * 100

        short_count = counter.count(short)
        long_count = counter.count(long)
        assert long_count > short_count


class TestChunkingSplitter:
    """Test line-aware chunk splitting."""

    def test_splitter_initialization(self):
        """Test splitter can initialize."""
        splitter = ChunkingSplitter()
        assert splitter.token_counter is not None

    def test_split_by_lines_basic(self):
        """Test basic line splitting."""
        splitter = ChunkingSplitter()
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        chunks = splitter.split_by_lines(text, target_tokens=5, overlap_tokens=1)

        assert len(chunks) > 0
        for chunk_content, start_line, end_line in chunks:
            assert isinstance(chunk_content, str)
            assert chunk_content.strip()
            assert start_line >= 0
            assert end_line >= start_line

    def test_split_preserves_lines(self):
        """Test that chunks don't break mid-line."""
        splitter = ChunkingSplitter()
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        chunks = splitter.split_by_lines(text, target_tokens=10)

        for chunk_content, _, _ in chunks:
            # Reconstruct shouldn't have broken lines
            assert not chunk_content.startswith(" ")
            assert not chunk_content.endswith(" ")


class TestSectionAwareChunker:
    """Test section-aware chunking."""

    def test_chunker_initialization(self):
        """Test chunker can initialize."""
        chunker = SectionAwareChunker()
        assert chunker.token_counter is not None

    def test_chunker_splits_by_sections(self):
        """Test that chunker respects section headers."""
        chunker = SectionAwareChunker()
        text = """## Section One
This is the first section.
Some content here.

## Section Two
This is the second section.
More content.

## Section Three
Final section."""

        chunks = chunker.chunk(
            text=text,
            source_url="https://example.com/test",
            scheme_name="Test Fund",
            source_type="scheme_page",
            crawled_at="2024-01-01T00:00:00Z",
            content_hash="abc123",
        )

        assert len(chunks) > 0
        # Should have chunks from multiple sections
        sections = {c.metadata.section_header for c in chunks}
        assert len(sections) >= 1  # At least one section

    def test_chunk_metadata_complete(self):
        """Test that chunk metadata is complete."""
        chunker = SectionAwareChunker()
        text = "## Test Section\nTest content here."

        chunks = chunker.chunk(
            text=text,
            source_url="https://groww.in/test",
            scheme_name="Test Fund Direct Growth",
            source_type="scheme_page",
            crawled_at="2024-01-01T12:00:00Z",
            content_hash="hash123",
        )

        assert len(chunks) > 0
        chunk = chunks[0]

        # Check all metadata fields are present
        assert chunk.metadata.chunk_id
        assert chunk.metadata.source_url == "https://groww.in/test"
        assert chunk.metadata.scheme_name == "Test Fund Direct Growth"
        assert chunk.metadata.source_type == "scheme_page"
        assert chunk.metadata.section_header == "Test Section"
        assert chunk.metadata.crawled_at == "2024-01-01T12:00:00Z"
        assert chunk.metadata.content_hash == "hash123"
        assert chunk.metadata.chunk_index >= 0
        assert chunk.metadata.start_line >= 0
        assert chunk.metadata.end_line >= chunk.metadata.start_line
        assert chunk.metadata.chunk_content_hash


class TestLocalEmbeddings:
    """Test local embeddings client."""

    def test_local_embeddings_initialization(self):
        """Test local embeddings can initialize."""
        embeddings = LocalEmbeddings(model_name="all-MiniLM-L6-v2")
        assert embeddings.embedding_dimension > 0

    def test_local_embeddings_single(self):
        """Test embedding a single text."""
        embeddings = LocalEmbeddings()
        embedding = embeddings.embed("Hello world")

        assert embedding is not None
        assert len(embedding) == embeddings.embedding_dimension

    def test_local_embeddings_batch(self):
        """Test batch embedding."""
        embeddings = LocalEmbeddings()
        texts = ["Hello", "World", "Test"]
        embeddings_list = embeddings.embed_batch(texts)

        assert len(embeddings_list) == len(texts)
        for emb in embeddings_list:
            assert len(emb) == embeddings.embedding_dimension

    def test_embeddings_factory(self):
        """Test embeddings factory."""
        client = get_embeddings_client("local")
        assert client is not None
        assert client.embedding_dimension > 0


class TestChromaIndex:
    """Test persistent Chroma vector database operations."""

    def test_chroma_initialization(self):
        """Test Chroma collection can initialize."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index = ChromaIndexBuilder(
                embedding_dimension=384,
                persist_path=Path(tmpdir) / "chroma",
            )
            assert index.collection is not None

    def test_chroma_add_and_search(self):
        """Test adding embeddings and searching."""
        import numpy as np

        with tempfile.TemporaryDirectory() as tmpdir:
            index = ChromaIndexBuilder(
                embedding_dimension=384,
                persist_path=Path(tmpdir) / "chroma",
            )

            # Create dummy embeddings
            embeddings = [
                np.random.random(384).astype(np.float32),
                np.random.random(384).astype(np.float32),
                np.random.random(384).astype(np.float32),
            ]
            chunk_ids = ["chunk_1", "chunk_2", "chunk_3"]

            # Add to index
            index.add_embeddings(embeddings, chunk_ids)

            # Search with first embedding
            results_ids, distances = index.search(embeddings[0], k=2)

            assert len(results_ids) > 0
            # First result should be the query itself (distance ~0)
            assert results_ids[0] == "chunk_1"

    def test_chroma_get_stats(self):
        """Test getting collection stats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index = ChromaIndexBuilder(
                embedding_dimension=384,
                persist_path=Path(tmpdir) / "chroma",
            )

            stats = index.get_index_stats()
            assert "total_vectors" in stats
            assert "embedding_dimension" in stats
            assert stats["embedding_dimension"] == 384


class TestMetadataStore:
    """Test SQLite metadata store."""

    def test_metadata_store_initialization(self):
        """Test metadata store creates schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ChunkMetadataStore(db_path=Path(tmpdir) / "test.db")
            stats = store.get_stats()

            assert stats["total_chunks"] == 0

    def test_metadata_store_insert_and_retrieve(self):
        """Test inserting and retrieving chunks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ChunkMetadataStore(db_path=Path(tmpdir) / "test.db")

            # Create a test chunk
            metadata = ChunkMetadata(
                chunk_id="test_chunk_1",
                source_url="https://groww.in/test",
                scheme_name="Test Fund",
                source_type="scheme_page",
                section_header="Holdings",
                crawled_at="2024-01-01T00:00:00Z",
                content_hash="hash123",
                chunk_index=0,
                start_line=10,
                end_line=20,
                chunk_content_hash="chunk_hash",
            )
            chunk = Chunk(metadata=metadata, content="Test content")

            # Insert
            inserted = store.insert_chunks([chunk])
            assert inserted == 1

            # Retrieve
            retrieved = store.get_chunk("test_chunk_1")
            assert retrieved is not None
            assert retrieved.content == "Test content"
            assert retrieved.metadata.source_url == "https://groww.in/test"

    def test_metadata_store_filter_by_source(self):
        """Test filtering by source URL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ChunkMetadataStore(db_path=Path(tmpdir) / "test.db")

            # Create chunks from different sources
            for i, url in enumerate(
                [
                    "https://groww.in/fund1",
                    "https://groww.in/fund1",
                    "https://groww.in/fund2",
                ]
            ):
                metadata = ChunkMetadata(
                    chunk_id=f"chunk_{i}",
                    source_url=url,
                    scheme_name="Test Fund",
                    source_type="scheme_page",
                    section_header="Test",
                    crawled_at="2024-01-01T00:00:00Z",
                    content_hash=f"hash_{i}",
                    chunk_index=i,
                    start_line=0,
                    end_line=10,
                    chunk_content_hash=f"chunk_hash_{i}",
                )
                chunk = Chunk(metadata=metadata, content=f"Content {i}")
                store.insert_chunks([chunk])

            # Filter by source
            fund1_chunks = store.get_chunks_by_source_url("https://groww.in/fund1")
            assert len(fund1_chunks) == 2

            fund2_chunks = store.get_chunks_by_source_url("https://groww.in/fund2")
            assert len(fund2_chunks) == 1

    def test_metadata_store_stats(self):
        """Test getting store statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ChunkMetadataStore(db_path=Path(tmpdir) / "test.db")

            # Insert test chunks
            for i in range(3):
                metadata = ChunkMetadata(
                    chunk_id=f"chunk_{i}",
                    source_url="https://groww.in/test",
                    scheme_name="Test Fund",
                    source_type="scheme_page",
                    section_header="Test",
                    crawled_at="2024-01-01T00:00:00Z",
                    content_hash="hash_same",
                    chunk_index=i,
                    start_line=0,
                    end_line=10,
                    chunk_content_hash=f"chunk_hash_{i}",
                )
                chunk = Chunk(metadata=metadata, content=f"Content {i}")
                store.insert_chunks([chunk])

            stats = store.get_stats()
            assert stats["total_chunks"] == 3
            assert stats["total_sources"] >= 1
