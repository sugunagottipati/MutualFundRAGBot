"""Phase 3: Index build and rebuild orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.config import get_settings
from ingestion.chunking import SectionAwareChunker
from ingestion.embeddings import get_embeddings_client
from ingestion.index import ChromaIndexBuilder
from ingestion.metadata_store import ChunkMetadataStore


class IndexBuilder:
    """Build or rebuild the complete vector index and metadata store."""

    def __init__(
        self,
        settings=None,
        processed_dir: Path | str | None = None,
        embeddings_provider: Optional[str] = None,
        embeddings_api_key: Optional[str] = None,
    ):
        self.settings = settings or get_settings(validate=False)
        self.processed_dir = (
            Path(processed_dir)
            if processed_dir is not None
            else Path(self.settings.sqlite_path).parent
        )
        self.documents_dir = self.processed_dir / "documents"

        # Initialize components
        provider = embeddings_provider or self.settings.embedding_provider
        api_key = embeddings_api_key or getattr(self.settings, "embedding_api_key", None)

        self.embeddings = get_embeddings_client(
            provider=provider,
            api_key=api_key,
            model=self.settings.embedding_model,
        )

        self.index = ChromaIndexBuilder(
            embedding_dimension=self.embeddings.embedding_dimension,
            persist_path=self.settings.vector_db_path,
        )

        self.store = ChunkMetadataStore(db_path=self.settings.sqlite_path)
        self.chunker = SectionAwareChunker()

    def load_processed_document(self, doc_path: Path) -> dict:
        """Load a single processed JSON document."""
        with open(doc_path) as f:
            return json.load(f)

    def build_index(self, force_rebuild: bool = False) -> dict:
        """
        Build or rebuild the complete index from all processed documents.

        Args:
            force_rebuild: If True, delete existing index first

        Returns:
            Build report
        """
        if force_rebuild:
            # Clear existing indexes
            ChromaIndexBuilder.remove_persisted_data(self.settings.vector_db_path)

            # Reinitialize
            self.index = ChromaIndexBuilder(
                embedding_dimension=self.embeddings.embedding_dimension,
                persist_path=self.settings.vector_db_path,
            )

        # Get all processed documents
        if not self.documents_dir.exists():
            return {
                "status": "error",
                "message": f"Documents directory not found: {self.documents_dir}",
            }

        doc_files = list(self.documents_dir.glob("*.json"))
        if not doc_files:
            return {
                "status": "error",
                "message": f"No documents found in {self.documents_dir}",
            }

        report = {
            "status": "success",
            "total_documents": len(doc_files),
            "total_chunks": 0,
            "total_embeddings": 0,
            "documents_processed": [],
            "errors": [],
        }

        # Process each document
        for doc_path in sorted(doc_files):
            try:
                doc = self.load_processed_document(doc_path)
                chunks = self._process_document(doc)

                if chunks:
                    # Embed chunks
                    chunk_ids = [c.metadata.chunk_id for c in chunks]
                    chunk_contents = [c.content for c in chunks]

                    embeddings = self.embeddings.embed_batch(chunk_contents)

                    # Add to index
                    self.index.add_embeddings(
                        embeddings,
                        chunk_ids,
                        documents=chunk_contents,
                        metadatas=[
                            {
                                "source_url": c.metadata.source_url,
                                "scheme_name": c.metadata.scheme_name,
                                "section_header": c.metadata.section_header,
                                "fact_type": c.metadata.fact_type,
                            }
                            for c in chunks
                        ],
                    )

                    # Store metadata
                    self.store.insert_chunks(chunks)

                    report["documents_processed"].append(
                        {
                            "document": doc_path.name,
                            "chunks": len(chunks),
                        }
                    )
                    report["total_chunks"] += len(chunks)
                    report["total_embeddings"] += len(embeddings)

            except Exception as e:
                report["errors"].append(
                    {
                        "document": doc_path.name,
                        "error": str(e),
                    }
                )

        # Save final index
        self.index.save()

        # Add statistics
        report["index_stats"] = self.index.get_index_stats()
        report["store_stats"] = self.store.get_stats()

        return report

    def _process_document(self, doc: dict) -> list:
        """Extract and chunk a single document."""
        if "metadata" not in doc or "text" not in doc:
            return []

        meta = doc["metadata"]
        text = doc["text"]

        # Chunk the text
        chunks = self.chunker.chunk(
            text=text,
            source_url=meta.get("source_url", ""),
            scheme_name=meta.get("scheme_name", ""),
            source_type=meta.get("source_type", ""),
            crawled_at=meta.get("crawled_at", ""),
            content_hash=meta.get("content_hash", ""),
        )

        return chunks

    def update_source(self, source_url: str) -> dict:
        """
        Update index for a specific source (re-ingest one source).

        Args:
            source_url: Source URL to update

        Returns:
            Update report
        """
        # Find document for this source
        doc_files = list(self.documents_dir.glob("*.json"))
        doc_path = None

        for f in doc_files:
            try:
                doc = self.load_processed_document(f)
                if doc.get("metadata", {}).get("source_url") == source_url:
                    doc_path = f
                    break
            except Exception:
                continue

        if not doc_path:
            return {
                "status": "error",
                "message": f"Document not found for source: {source_url}",
            }

        # Clear old chunks
        self.store.clear_chunks_by_source_url(source_url)
        self.index.delete_by_source_url(source_url)

        # Reprocess
        doc = self.load_processed_document(doc_path)
        chunks = self._process_document(doc)

        if not chunks:
            return {
                "status": "warning",
                "message": f"No chunks generated for {source_url}",
            }

        # Embed and index
        chunk_ids = [c.metadata.chunk_id for c in chunks]
        chunk_contents = [c.content for c in chunks]
        embeddings = self.embeddings.embed_batch(chunk_contents)

        self.index.add_embeddings(
            embeddings,
            chunk_ids,
            documents=chunk_contents,
            metadatas=[
                {
                    "source_url": c.metadata.source_url,
                    "scheme_name": c.metadata.scheme_name,
                    "section_header": c.metadata.section_header,
                }
                for c in chunks
            ],
        )
        self.store.insert_chunks(chunks)
        self.index.save()

        return {
            "status": "success",
            "source_url": source_url,
            "chunks_created": len(chunks),
            "index_stats": self.index.get_index_stats(),
        }

    def get_index_status(self) -> dict:
        """Get current index status."""
        return {
            "index_stats": self.index.get_index_stats(),
            "store_stats": self.store.get_stats(),
            "embedding_dimension": self.embeddings.embedding_dimension,
            "embedding_provider": self.settings.embedding_provider,
        }
