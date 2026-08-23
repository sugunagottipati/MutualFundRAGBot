#!/usr/bin/env python3
"""
Build or rebuild the vector index from processed documents.

Usage:
    python -m scripts.build_index              # Incremental build
    python -m scripts.build_index --force      # Full rebuild (delete and recreate)
    python -m scripts.build_index --status     # Show index status
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from ingestion.index_builder import IndexBuilder


def main():
    parser = argparse.ArgumentParser(description="Build or rebuild the vector index")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force full rebuild (delete existing index first)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current index status",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="Override embedding provider (openai or local)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Override embedding API key",
    )

    args = parser.parse_args()

    try:
        settings = get_settings(validate=False)
    except Exception as e:
        print(f"Error loading settings: {e}")
        print("Make sure environment variables are set (see .env.example)")
        sys.exit(1)

    builder = IndexBuilder(
        settings=settings,
        embeddings_provider=args.provider,
        embeddings_api_key=args.api_key,
    )

    if args.status:
        # Just show status
        status = builder.get_index_status()
        print("\n=== Index Status ===")
        print(f"Total vectors: {status['index_stats']['total_vectors']}")
        print(f"Total chunks: {status['store_stats']['total_chunks']}")
        print(f"Total sources: {status['store_stats']['total_sources']}")
        print(f"Total schemes: {status['store_stats']['total_schemes']}")
        print(f"Embedding provider: {status['embedding_provider']}")
        print(f"Embedding dimension: {status['embedding_dimension']}")
        return 0

    # Build index
    print("\n=== Building Index ===")
    if args.force:
        print("Force rebuild enabled (deleting existing index)...")

    report = builder.build_index(force_rebuild=args.force)

    print(f"\nStatus: {report['status']}")
    if report["status"] == "error":
        print(f"Error: {report['message']}")
        return 1

    print(f"Documents processed: {len(report['documents_processed'])}")
    print(f"Total chunks created: {report['total_chunks']}")
    print(f"Total embeddings: {report['total_embeddings']}")

    if report["errors"]:
        print(f"\n{len(report['errors'])} error(s):")
        for err in report["errors"]:
            print(f"  {err['document']}: {err['error']}")

    print("\n=== Final Index Stats ===")
    stats = report["index_stats"]
    print(f"Total vectors in index: {stats['total_vectors']}")
    print(f"Embedding dimension: {stats['embedding_dimension']}")

    print("\n=== Database Stats ===")
    store_stats = report["store_stats"]
    print(f"Total chunks in DB: {store_stats['total_chunks']}")
    print(f"Sources: {store_stats['total_sources']}")
    print(f"Schemes: {store_stats['total_schemes']}")
    print(f"Sections: {store_stats['total_sections']}")
    print(f"Duplicate records: {store_stats['duplicate_records']}")

    print("\n✓ Index build complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
