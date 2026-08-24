from datetime import datetime, timezone
import json

from ingestion.fetch import FetchResult
from ingestion.extract import extract_document
from ingestion.pipeline import run_ingestion
from ingestion.seed_urls import get_active_source_inventory


def test_extracts_key_facts_from_embedded_fund_data() -> None:
    html = (
        b'<html><script>window.__DATA__={'
        b'"expense_ratio":"0.75",'
        b'"exit_load":"Exit load of 1% if redeemed within 1 year",'
        b'"min_sip_investment":100,'
        b'"risk":"Very High",'
        b'"benchmark":"BSE 250 SmallCap TRI",'
        b'"nav":123.45,'
        b'"nav_date":"21-Aug-2026",'
        b'"aum":110736.41185,'
        b'"category":"Equity",'
        b'"plan_type":"Direct Growth",'
        b'"return1y":4.19,'
        b'"return3y":17.69,'
        b'"return5y":19.37,'
        b'"return10y":16.26'
        b'}</script></html>'
    )

    extracted = extract_document(
        html,
        content_type="text/html",
        source_url="https://groww.in/mutual-funds/example",
    )

    assert "Expense ratio: 0.75%" in extracted.text
    assert "Exit load: Exit load of 1% if redeemed within 1 year" in extracted.text
    assert "Minimum SIP amount: Rs 100" in extracted.text
    assert "Riskometer: Very High" in extracted.text
    assert "Benchmark: BSE 250 SmallCap TRI" in extracted.text
    assert extracted.structured_facts["nav"] == 123.45
    assert extracted.structured_facts["nav_date"] == "21-Aug-2026"
    assert extracted.structured_facts["aum"] == 110736.41185
    assert extracted.structured_facts["plan_type"] == "Direct Growth"
    assert extracted.structured_facts["returns"] == {
        "1y": 4.19,
        "3y": 17.69,
        "5y": 19.37,
        "10y": 16.26,
    }
    assert extracted.extraction_status["investment_objective"] == "missing"
    assert extracted.extraction_status["nav"] == "extracted"


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

    processed_paths = list((tmp_path / "processed" / "documents").glob("*.json"))
    assert len(processed_paths) == 1
    processed = json.loads(processed_paths[0].read_text(encoding="utf-8"))
    assert "structured_facts" in processed["metadata"]
    assert "extraction_status" in processed["metadata"]
