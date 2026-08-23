from datetime import datetime, timezone
import json

from ingestion.fetch import FetchResult
from ingestion.pipeline import run_ingestion
from ingestion.seed_urls import get_active_source_inventory


def test_pipeline_deduplicates_and_writes_logs(tmp_path) -> None:
    records = get_active_source_inventory()[:2]

    def fake_fetcher(url: str, **_) -> FetchResult:
        html = b"<html><body><h1>Scheme Facts</h1><p>Expense ratio is 1.2%.</p></body></html>"
        return FetchResult(
            source_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            content=html,
            fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            error=None,
        )

    result = run_ingestion(
        source_records=records,
        enforce_exact_allowlist=False,
        fetcher=fake_fetcher,
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
    )

    assert result.total_sources == 2
    assert result.processed == 1
    assert result.deduplicated == 1
    assert result.failed == 0

    health_log = tmp_path / "processed" / "source_health.jsonl"
    status_log = tmp_path / "processed" / "ingestion_status.jsonl"
    manifest = tmp_path / "processed" / "document_manifest.jsonl"

    assert health_log.exists()
    assert status_log.exists()
    assert manifest.exists()

    manifest_lines = manifest.read_text(encoding="utf-8").splitlines()
    assert len(manifest_lines) == 1
    row = json.loads(manifest_lines[0])
    assert row["source_url"] in {records[0].source_url, records[1].source_url}
