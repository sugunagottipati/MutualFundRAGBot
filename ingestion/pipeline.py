"""Phase 2 ingestion pipeline: fetch, extract, normalize, and persist."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ingestion.extract import ExtractedDocument, extract_document
from ingestion.fetch import FetchResult, fetch_url
from ingestion.normalize import normalize_document_text
from ingestion.seed_urls import SourceRecord, get_active_source_inventory, validate_source_records


@dataclass(frozen=True)
class PipelineResult:
    total_sources: int
    processed: int
    deduplicated: int
    failed: int


Fetcher = Callable[..., FetchResult]


def run_ingestion(
    *,
    source_records: tuple[SourceRecord, ...] | None = None,
    enforce_exact_allowlist: bool = True,
    fetcher: Fetcher = fetch_url,
    raw_dir: Path | str = "data/raw",
    processed_dir: Path | str = "data/processed",
    timeout_seconds: int = 20,
    retries: int = 2,
) -> PipelineResult:
    """Run ingestion for source inventory and persist normalized outputs."""
    records = source_records or get_active_source_inventory()
    validate_source_records(records, enforce_exact_allowlist=enforce_exact_allowlist)

    raw_root = Path(raw_dir)
    processed_root = Path(processed_dir)
    documents_dir = processed_root / "documents"
    source_health_log = processed_root / "source_health.jsonl"
    ingestion_status_log = processed_root / "ingestion_status.jsonl"
    manifest_path = processed_root / "document_manifest.jsonl"

    raw_root.mkdir(parents=True, exist_ok=True)
    documents_dir.mkdir(parents=True, exist_ok=True)

    known_hashes = _read_existing_hashes(manifest_path)

    processed = 0
    deduplicated = 0
    failed = 0

    for record in records:
        crawl_time = _utcnow()
        result = fetcher(
            record.source_url,
            timeout_seconds=timeout_seconds,
            retries=retries,
        )

        if result.error:
            failed += 1
            _append_jsonl(
                source_health_log,
                {
                    "source_url": record.source_url,
                    "status": "fetch_error",
                    "checked_at": crawl_time,
                    "http_status": result.status_code,
                    "detail": result.error,
                },
            )
            _append_jsonl(
                ingestion_status_log,
                {
                    "source_url": record.source_url,
                    "status": "failed",
                    "stage": "fetch",
                    "crawled_at": crawl_time,
                    "detail": result.error,
                },
            )
            continue

        if result.status_code != 200:
            failed += 1
            _append_jsonl(
                source_health_log,
                {
                    "source_url": record.source_url,
                    "status": "bad_http_status",
                    "checked_at": crawl_time,
                    "http_status": result.status_code,
                    "detail": "Expected HTTP 200",
                },
            )
            _append_jsonl(
                ingestion_status_log,
                {
                    "source_url": record.source_url,
                    "status": "failed",
                    "stage": "fetch",
                    "crawled_at": crawl_time,
                    "detail": f"HTTP status {result.status_code}",
                },
            )
            continue

        raw_path = _save_raw_content(raw_root, record.source_url, result)
        extracted = extract_document(
            result.content,
            content_type=result.content_type,
            source_url=result.final_url,
        )
        normalized_text = normalize_document_text(extracted.text)

        if not normalized_text.strip():
            failed += 1
            _append_jsonl(
                source_health_log,
                {
                    "source_url": record.source_url,
                    "status": "empty_content",
                    "checked_at": crawl_time,
                    "http_status": result.status_code,
                    "detail": "No extractable text",
                },
            )
            _append_jsonl(
                ingestion_status_log,
                {
                    "source_url": record.source_url,
                    "status": "failed",
                    "stage": "extract",
                    "crawled_at": crawl_time,
                    "detail": "No extractable text",
                },
            )
            continue

        content_hash = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()

        if content_hash in known_hashes:
            deduplicated += 1
            _append_jsonl(
                source_health_log,
                {
                    "source_url": record.source_url,
                    "status": "ok",
                    "checked_at": crawl_time,
                    "http_status": result.status_code,
                    "detail": "Duplicate content hash",
                },
            )
            _append_jsonl(
                ingestion_status_log,
                {
                    "source_url": record.source_url,
                    "status": "deduplicated",
                    "stage": "dedupe",
                    "crawled_at": crawl_time,
                    "content_hash": content_hash,
                },
            )
            continue

        processed_doc_path = _save_processed_document(
            documents_dir=documents_dir,
            record=record,
            extracted=extracted,
            normalized_text=normalized_text,
            crawl_time=crawl_time,
            fetch_result=result,
            raw_path=raw_path,
            content_hash=content_hash,
        )

        _append_jsonl(
            manifest_path,
            {
                "source_url": record.source_url,
                "content_hash": content_hash,
                "crawled_at": crawl_time,
                "processed_path": str(processed_doc_path),
            },
        )
        known_hashes.add(content_hash)

        _append_jsonl(
            source_health_log,
            {
                "source_url": record.source_url,
                "status": "ok",
                "checked_at": crawl_time,
                "http_status": result.status_code,
                "detail": "Ingested",
            },
        )
        _append_jsonl(
            ingestion_status_log,
            {
                "source_url": record.source_url,
                "status": "processed",
                "stage": "complete",
                "crawled_at": crawl_time,
                "content_hash": content_hash,
                "processed_path": str(processed_doc_path),
            },
        )
        processed += 1

    return PipelineResult(
        total_sources=len(records),
        processed=processed,
        deduplicated=deduplicated,
        failed=failed,
    )


def _save_raw_content(raw_root: Path, source_url: str, fetch_result: FetchResult) -> Path:
    slug = _slugify(source_url)
    extension = _infer_extension(fetch_result)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    file_path = raw_root / f"{slug}-{timestamp}{extension}"
    file_path.write_bytes(fetch_result.content)
    return file_path


def _save_processed_document(
    *,
    documents_dir: Path,
    record: SourceRecord,
    extracted: ExtractedDocument,
    normalized_text: str,
    crawl_time: str,
    fetch_result: FetchResult,
    raw_path: Path,
    content_hash: str,
) -> Path:
    slug = _slugify(record.source_url)
    file_path = documents_dir / f"{slug}-{content_hash[:12]}.json"

    payload = {
        "metadata": {
            **asdict(record),
            "source_domain": _domain_from_url(record.source_url),
            "final_url": fetch_result.final_url,
            "http_status": fetch_result.status_code,
            "content_type": fetch_result.content_type,
            "crawled_at": crawl_time,
            "content_hash": content_hash,
            "raw_file_path": str(raw_path),
            "section_headers": list(extracted.section_headers),
            "document_type": extracted.document_type,
        },
        "text": normalized_text,
    }
    file_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return file_path


def _read_existing_hashes(manifest_path: Path) -> set[str]:
    hashes: set[str] = set()
    if not manifest_path.exists():
        return hashes

    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        content_hash = row.get("content_hash")
        if isinstance(content_hash, str):
            hashes.add(content_hash)
    return hashes


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True))
        handle.write("\n")


def _infer_extension(fetch_result: FetchResult) -> str:
    content_type = fetch_result.content_type
    if "pdf" in content_type or fetch_result.final_url.lower().endswith(".pdf"):
        return ".pdf"
    if "html" in content_type:
        return ".html"
    return ".bin"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug[:120]


def _domain_from_url(url: str) -> str:
    return url.split("/")[2].lower()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _main() -> None:
    result = run_ingestion()
    print(
        "Ingestion completed: "
        f"total={result.total_sources}, processed={result.processed}, "
        f"deduplicated={result.deduplicated}, failed={result.failed}"
    )


if __name__ == "__main__":
    _main()
