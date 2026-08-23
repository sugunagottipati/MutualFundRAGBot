"""Inspect the local Chroma store and run an example retrieval."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from app.retrieval import Retriever
from ingestion.embeddings import get_embeddings_client
from ingestion.index import ChromaIndexBuilder
from ingestion.metadata_store import ChunkMetadataStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show stored Chroma embeddings and run semantic retrieval."
    )
    parser.add_argument(
        "--query",
        default="What is the expense ratio of the mutual fund?",
        help="Factual query to run against the Chroma collection.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of retrieval results to display (default: 5).",
    )
    parser.add_argument(
        "--vector-preview",
        type=int,
        default=8,
        help="Number of values to show from each sample embedding (default: 8).",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=3,
        help="Number of stored embeddings to inspect (default: 3).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.top_k < 1 or args.sample_size < 1 or args.vector_preview < 1:
        raise SystemExit("--top-k, --sample-size, and --vector-preview must be positive")

    load_dotenv()
    vector_path = Path(os.getenv("VECTOR_DB_PATH", "./data/chroma"))
    sqlite_path = Path(os.getenv("SQLITE_PATH", "./data/processed/app.db"))
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "local")
    embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    index = ChromaIndexBuilder(
        embedding_dimension=_collection_dimension(vector_path),
        persist_path=vector_path,
    )
    collection = index.collection
    total = collection.count()
    print("Chroma collection")
    print(f"  path: {vector_path.resolve()}")
    print(f"  name: {index.collection_name}")
    print(f"  vectors: {total}")
    print(f"  dimension: {index.embedding_dimension}")

    if total == 0:
        print("\nNo vectors found. Rebuild the vector store first.")
        return

    sample = collection.get(
        limit=min(args.sample_size, total),
        include=["embeddings", "documents", "metadatas"],
    )
    print("\nStored embedding samples")
    for position, (chunk_id, embedding) in enumerate(
        zip(sample["ids"], sample["embeddings"])
    ):
        metadata = sample["metadatas"][position] or {}
        preview = ", ".join(f"{value:.5f}" for value in embedding[: args.vector_preview])
        print(f"  {chunk_id}")
        print(f"    values: [{preview}, ...]")
        print(f"    source: {metadata.get('source_url', 'unknown')}")
        print(f"    section: {metadata.get('section_header', 'unknown')}")

    embeddings = get_embeddings_client(
        provider=embedding_provider,
        model=embedding_model,
    )
    retriever = Retriever(
        embeddings_client=embeddings,
        vector_index=index,
        metadata_store=ChunkMetadataStore(db_path=sqlite_path),
    )
    results = retriever.retrieve(args.query, top_k=args.top_k)

    print("\nExample retrieval")
    print(f"  query: {args.query}")
    if not results:
        print("  no matching chunks found")
        return

    for result in results:
        metadata = result.chunk.metadata
        print(f"  [{result.rank}] distance={result.similarity_distance:.5f} "
              f"relevance={result.relevance_score:.3f}")
        print(f"      chunk: {metadata.chunk_id}")
        print(f"      source: {metadata.source_url}")
        print(f"      section: {metadata.section_header}")
        print(f"      content: {result.chunk.content[:240].replace(chr(10), ' ')}")


def _collection_dimension(vector_path: Path) -> int:
    """Read the embedding dimension without modifying the collection."""
    import chromadb

    client = chromadb.PersistentClient(path=str(vector_path))
    collection = client.get_collection(ChromaIndexBuilder.collection_name)
    sample = collection.get(limit=1, include=["embeddings"])
    if sample["embeddings"] is None or len(sample["embeddings"]) == 0:
        raise SystemExit("Chroma collection has no embeddings")
    return len(sample["embeddings"][0])


if __name__ == "__main__":
    main()
