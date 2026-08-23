"""Text normalization for retrieval-ready ingestion output."""

from __future__ import annotations

import re

_FIELD_REWRITES = {
    "expense ratio": "expense ratio",
    "exit load": "exit load",
    "minimum sip": "minimum sip",
    "min sip": "minimum sip",
    "riskometer": "riskometer",
    "benchmark": "benchmark",
}


def normalize_document_text(text: str) -> str:
    """Normalize whitespace and labels while preserving section header markers."""
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = _normalize_line(raw_line)
        if not line:
            continue

        if line.startswith("## "):
            lines.append(line)
            continue

        lines.append(_rewrite_field_labels(line))

    return "\n".join(_dedupe_adjacent(lines))


def _normalize_line(line: str) -> str:
    compact = re.sub(r"\s+", " ", line).strip()
    return compact


def _rewrite_field_labels(line: str) -> str:
    lowered = line.lower()
    for key, replacement in _FIELD_REWRITES.items():
        if key in lowered:
            return re.sub(re.escape(key), replacement, line, flags=re.IGNORECASE)
    return line


def _dedupe_adjacent(lines: list[str]) -> list[str]:
    deduped: list[str] = []
    for line in lines:
        if not deduped or deduped[-1] != line:
            deduped.append(line)
    return deduped
