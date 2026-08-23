#!/usr/bin/env python3
"""
Update index for a specific source (re-ingest one source).

Usage:
    python -m scripts.update_source <source_url>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.constants import APPROVED_SOURCE_URLS
from ingestion.index_builder import IndexBuilder


def main():
    parser = argparse.ArgumentParser(description="Update index for a specific source")
    parser.add_argument(
        "source_url",
        help="Source URL to update (must be in approved list)",
    )

    args = parser.parse_args()

    # Validate source URL
    if args.source_url not in APPROVED_SOURCE_URLS:
        print(f"Error: {args.source_url} is not in approved source list")
        print("\nApproved sources:")
        for url in APPROVED_SOURCE_URLS:
            print(f"  {url}")
        return 1

    try:
        settings = get_settings(validate=False)
    except Exception as e:
        print(f"Error loading settings: {e}")
        return 1

    builder = IndexBuilder(settings=settings)

    print(f"\n=== Updating Index for Source ===")
    print(f"Source: {args.source_url}")

    report = builder.update_source(args.source_url)

    print(f"\nStatus: {report['status']}")

    if report["status"] != "error":
        if "chunks_created" in report:
            print(f"Chunks created: {report['chunks_created']}")
        if "index_stats" in report:
            print(f"Total vectors now: {report['index_stats']['total_vectors']}")

    else:
        print(f"Error: {report['message']}")
        return 1

    print("\n✓ Index update complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
