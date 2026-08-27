"""Refresh approved sources and rebuild the retrieval index.

This command exits non-zero only when no usable source data remains or the
index update reports an error, making scheduled automation resilient to
transient source fetch failures.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.config import get_settings
from ingestion.index_builder import IndexBuilder
from ingestion.pipeline import PipelineResult, run_ingestion


INGESTION_ATTEMPTS = 2


def refresh_sources() -> dict[str, object]:
    """Ingest the approved source set and update the persistent index."""
    settings = get_settings(validate=False)
    processed_dir = Path(settings.sqlite_path).parent
    raw_dir = Path(settings.vector_db_path).parent / "raw"
    ingestion_result: PipelineResult | None = None
    for _ in range(INGESTION_ATTEMPTS):
        ingestion_result = run_ingestion(
            raw_dir=raw_dir,
            processed_dir=processed_dir,
        )
        if ingestion_result.failed == 0:
            break

    if ingestion_result is None:
        raise RuntimeError("Ingestion did not run")

    documents_dir = processed_dir / "documents"
    has_existing_corpus = documents_dir.is_dir() and any(documents_dir.glob("*.json"))
    if ingestion_result.failed and ingestion_result.processed == 0 and not has_existing_corpus:
        raise RuntimeError(
            f"Ingestion failed for {ingestion_result.failed} of "
            f"{ingestion_result.total_sources} approved sources and no existing corpus is available"
        )

    builder = IndexBuilder(settings=settings, processed_dir=processed_dir)
    index_result = builder.build_index()
    if index_result.get("status") != "success" or index_result.get("errors"):
        details = index_result.get("errors") or index_result.get("message", "unknown index error")
        raise RuntimeError(f"Index refresh failed: {details}")

    return {
        "ingestion": ingestion_result,
        "index": index_result,
        "warnings": _build_warnings(ingestion_result),
    }


def _build_warnings(ingestion_result: PipelineResult) -> list[str]:
    if ingestion_result.failed == 0:
        return []
    return [
        f"Ingestion skipped {ingestion_result.failed} of "
        f"{ingestion_result.total_sources} approved sources after retry; "
        "existing processed corpus was retained for indexing."
    ]


def main() -> int:
    try:
        report = refresh_sources()
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    ingestion = report["ingestion"]
    for warning in report["warnings"]:
        print(f"[WARN] {warning}", file=sys.stderr)
    print(
        "[PASS] Source refresh completed: "
        f"processed={ingestion.processed}, deduplicated={ingestion.deduplicated}, "
        f"failed={ingestion.failed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())