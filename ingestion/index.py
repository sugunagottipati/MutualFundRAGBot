"""Phase 3: FAISS index builder and vector storage."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Optional

import numpy as np


class FAISSIndexBuilder:
    """Build and manage FAISS vector index for semantic search."""

    def __init__(self, embedding_dimension: int, index_path: Path | str = "data/faiss/index.bin"):
        try:
            import faiss
        except ImportError:
            raise ImportError("faiss-cpu required: pip install faiss-cpu")

        self.faiss = faiss
        self.embedding_dimension = embedding_dimension
        self.index_path = Path(index_path)
        self.id_map_path = self.index_path.parent / "id_mapping.json"

        # Initialize or load index
        self.index = None
        self.id_to_chunk_id = {}  # Maps FAISS internal IDs to chunk IDs
        self.chunk_id_to_index_id = {}  # Reverse mapping

        self._load_or_create_index()

    def _load_or_create_index(self):
        """Load existing index or create new one."""
        if self.index_path.exists():
            self.index = self.faiss.read_index(str(self.index_path))
            if self.id_map_path.exists():
                with open(self.id_map_path) as f:
                    mapping = json.load(f)
                    self.id_to_chunk_id = {int(k): v for k, v in mapping["id_to_chunk_id"].items()}
                    self.chunk_id_to_index_id = mapping["chunk_id_to_index_id"]
        else:
            # Use simple flat index for MVP (suitable for up to ~10K chunks)
            # Can upgrade to IVF for larger scales later
            self.index = self.faiss.IndexFlatL2(self.embedding_dimension)
            self.id_to_chunk_id = {}
            self.chunk_id_to_index_id = {}

    def add_embeddings(
        self,
        embeddings: list[np.ndarray],
        chunk_ids: list[str],
    ) -> None:
        """Add embeddings to index.

        Args:
            embeddings: List of embedding vectors
            chunk_ids: Corresponding chunk IDs
        """
        if len(embeddings) != len(chunk_ids):
            raise ValueError("embeddings and chunk_ids must have same length")

        if not embeddings:
            return

        # Stack embeddings into matrix
        embedding_matrix = np.stack(embeddings, axis=0).astype(np.float32)

        # Get starting ID (continuous indexing)
        starting_id = self.index.ntotal

        # Add to FAISS
        self.index.add(embedding_matrix)

        # Update mappings
        for i, chunk_id in enumerate(chunk_ids):
            index_id = starting_id + i
            self.id_to_chunk_id[index_id] = chunk_id
            self.chunk_id_to_index_id[chunk_id] = index_id

        self._save_index()

    def search(self, query_embedding: np.ndarray, k: int = 5) -> tuple[list[str], list[float]]:
        """
        Search for similar embeddings.

        Args:
            query_embedding: Query vector
            k: Number of results

        Returns:
            (chunk_ids, distances)
        """
        query_embedding = query_embedding.astype(np.float32).reshape(1, -1)
        distances, indices = self.index.search(query_embedding, k)

        chunk_ids = []
        result_distances = []

        for idx, distance in zip(indices[0], distances[0]):
            if idx == -1:  # Sentinel value for "not found"
                continue
            if idx in self.id_to_chunk_id:
                chunk_ids.append(self.id_to_chunk_id[idx])
                result_distances.append(float(distance))

        return chunk_ids, result_distances

    def search_batch(
        self, query_embeddings: list[np.ndarray], k: int = 5
    ) -> list[tuple[list[str], list[float]]]:
        """
        Batch search multiple queries.

        Args:
            query_embeddings: List of query vectors
            k: Number of results per query

        Returns:
            List of (chunk_ids, distances) tuples
        """
        query_matrix = np.stack(query_embeddings, axis=0).astype(np.float32)
        distances, indices = self.index.search(query_matrix, k)

        results = []
        for idx_row, dist_row in zip(indices, distances):
            chunk_ids = []
            result_distances = []
            for idx, distance in zip(idx_row, dist_row):
                if idx == -1:
                    continue
                if idx in self.id_to_chunk_id:
                    chunk_ids.append(self.id_to_chunk_id[idx])
                    result_distances.append(float(distance))
            results.append((chunk_ids, result_distances))

        return results

    def _save_index(self):
        """Persist index and mappings to disk."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.faiss.write_index(self.index, str(self.index_path))

        mapping = {
            "id_to_chunk_id": {str(k): v for k, v in self.id_to_chunk_id.items()},
            "chunk_id_to_index_id": self.chunk_id_to_index_id,
        }
        with open(self.id_map_path, "w") as f:
            json.dump(mapping, f, indent=2)

    def save(self):
        """Explicit save."""
        self._save_index()

    def get_index_stats(self) -> dict:
        """Get index statistics."""
        return {
            "total_vectors": self.index.ntotal,
            "embedding_dimension": self.embedding_dimension,
            "index_type": type(self.index).__name__,
            "total_chunks_mapped": len(self.id_to_chunk_id),
        }


class ChromaIndexBuilder:
    """Build and manage a persistent Chroma collection for semantic search."""

    collection_name = "mutual_fund_chunks"

    def __init__(self, embedding_dimension: int, persist_path: Path | str = "data/chroma"):
        try:
            import chromadb
        except ImportError:
            raise ImportError("chromadb required: pip install chromadb")

        self.embedding_dimension = embedding_dimension
        self.persist_path = Path(persist_path)
        self.client = chromadb.PersistentClient(path=str(self.persist_path))
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            configuration={"hnsw": {"space": "l2"}},
        )

    def add_embeddings(
        self,
        embeddings: list[np.ndarray],
        chunk_ids: list[str],
        documents: Optional[list[str]] = None,
        metadatas: Optional[list[dict]] = None,
    ) -> None:
        """Upsert vectors and optional document metadata into the collection."""
        if len(embeddings) != len(chunk_ids):
            raise ValueError("embeddings and chunk_ids must have same length")
        if documents is not None and len(documents) != len(chunk_ids):
            raise ValueError("documents and chunk_ids must have same length")
        if metadatas is not None and len(metadatas) != len(chunk_ids):
            raise ValueError("metadatas and chunk_ids must have same length")
        if not embeddings:
            return

        vectors = [embedding.astype(np.float32).tolist() for embedding in embeddings]
        if any(len(vector) != self.embedding_dimension for vector in vectors):
            raise ValueError("embedding dimension does not match the collection")

        payload = {
            "ids": chunk_ids,
            "embeddings": vectors,
        }
        if documents is not None:
            payload["documents"] = documents
        if metadatas is not None:
            payload["metadatas"] = metadatas
        self.collection.upsert(**payload)

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        source_url: Optional[str] = None,
    ) -> tuple[list[str], list[float]]:
        """Search the collection, optionally restricted to one source URL."""
        total = self.collection.count()
        if total == 0:
            return [], []

        where = {"source_url": source_url} if source_url else None
        result = self.collection.query(
            query_embeddings=[query_embedding.astype(np.float32).tolist()],
            n_results=min(k, total),
            include=["distances"],
            **({"where": where} if where else {}),
        )
        return (
            result["ids"][0],
            [float(distance) for distance in result["distances"][0]],
        )

    def delete_by_source_url(self, source_url: str) -> None:
        """Remove indexed chunks belonging to a source URL."""
        self.collection.delete(where={"source_url": source_url})

    def save(self) -> None:
        """Persist changes; PersistentClient writes changes automatically."""

    def get_index_stats(self) -> dict:
        """Get collection statistics using the legacy index stats shape."""
        return {
            "total_vectors": self.collection.count(),
            "embedding_dimension": self.embedding_dimension,
            "index_type": "ChromaHNSW",
            "total_chunks_mapped": self.collection.count(),
        }

    @classmethod
    def remove_persisted_data(cls, persist_path: Path | str) -> None:
        """Remove a local Chroma database before a full rebuild."""
        from chromadb.api.shared_system_client import SharedSystemClient

        SharedSystemClient.clear_system_cache()
        path = Path(persist_path)
        if path.exists():
            shutil.rmtree(path)
