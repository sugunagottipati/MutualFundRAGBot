"""Backfill structured facts into existing processed snapshots."""

from __future__ import annotations

import json
from pathlib import Path

from ingestion.extract import extract_document
from ingestion.normalize import normalize_document_text

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
DOCUMENTS_DIR = ROOT / "data" / "processed" / "documents"


def backfill() -> int:
    updated = 0
    raw_files = sorted(RAW_DIR.glob("*.html"))
    for document_path in sorted(DOCUMENTS_DIR.glob("*.json")):
        payload = json.loads(document_path.read_text(encoding="utf-8"))
        metadata = payload.get("metadata", {})
        if metadata.get("structured_facts"):
            continue

        source_url = metadata.get("source_url", "")
        slug = source_url.replace("https://", "https-").replace(".", "-").replace("/", "-")
        candidates = [path for path in raw_files if slug in path.name]
        if not candidates:
            continue
        raw_path = candidates[-1]
        extracted = extract_document(
            raw_path.read_bytes(),
            content_type="text/html",
            source_url=source_url,
        )
        facts = extracted.structured_facts
        display_lines = facts.pop("display_lines", [])
        if "nav" in facts:
            display_lines.append(f"NAV: {facts['nav']}")
        if "nav_date" in facts:
            display_lines.append(f"NAV date: {facts['nav_date']}")
        if display_lines:
            text = payload.get("text", "")
            if "## Fund details" not in text:
                text += "\n## Fund details"
            for line in display_lines:
                if line not in text:
                    text += f"\n{line}"
            payload["text"] = normalize_document_text(text)
        metadata["structured_facts"] = facts
        metadata["extraction_status"] = extracted.extraction_status
        payload["metadata"] = metadata
        document_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        updated += 1
    return updated


if __name__ == "__main__":
    print(f"Backfilled {backfill()} processed documents")
