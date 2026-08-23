"""Refresh every approved source and rebuild the retrieval index.

This command exits non-zero if any approved source cannot be refreshed or if
the index update reports an error, making it safe for scheduled automation.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.config import get_settings
from ingestion.index_builder import IndexBuilder
from ingestion.pipeline import PipelineResult, run_ingestion


def refresh_sources() -> dict[str, object]:
    """Ingest the approved source set and update the persistent index."""
    settings = get_settings(validate=False)
    processed_dir = Path(settings.sqlite_path).parent
    raw_dir = Path(settings.vector_db_path).parent / "raw"
    ingestion_result: PipelineResult = run_ingestion(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
    )
    if ingestion_result.failed:
        raise RuntimeError(
            f"Ingestion failed for {ingestion_result.failed} of "
            f"{ingestion_result.total_sources} approved sources"
        )

    builder = IndexBuilder(settings=settings, processed_dir=processed_dir)
    index_result = builder.build_index()
    if index_result.get("status") != "success" or index_result.get("errors"):
        details = index_result.get("errors") or index_result.get("message", "unknown index error")
        raise RuntimeError(f"Index refresh failed: {details}")

    return {
        "ingestion": ingestion_result,
        "index": index_result,
    }


def main() -> int:
    try:
        report = refresh_sources()
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    ingestion = report["ingestion"]
    print(
        "[PASS] Source refresh completed: "
        f"processed={ingestion.processed}, deduplicated={ingestion.deduplicated}, "
        f"failed={ingestion.failed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())