"""Document text extraction for HTML and PDF sources."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import re

from bs4 import BeautifulSoup
from pypdf import PdfReader


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    document_type: str
    section_headers: tuple[str, ...]


def extract_document(content: bytes, *, content_type: str, source_url: str) -> ExtractedDocument:
    """Extract plain text while preserving useful section boundaries."""
    is_pdf = "pdf" in content_type or source_url.lower().endswith(".pdf")
    if is_pdf:
        return _extract_pdf(content)
    return _extract_html(content)


def _extract_html(content: bytes) -> ExtractedDocument:
    soup = BeautifulSoup(content, "lxml")
    structured_facts = _extract_structured_facts(content)

    for tag in soup(["script", "style", "noscript", "svg", "img"]):
        tag.decompose()

    lines: list[str] = []
    headers: list[str] = []

    for node in soup.select("h1, h2, h3, h4, p, li, td, th"):
        text = " ".join(node.get_text(" ", strip=True).split())
        if not text:
            continue

        if node.name in {"h1", "h2", "h3", "h4"}:
            heading = f"## {text}"
            headers.append(text)
            _append_unique(lines, heading)
        else:
            _append_unique(lines, text)

    if structured_facts:
        _append_unique(lines, "## Fund details")
        for fact in structured_facts:
            _append_unique(lines, fact)

    return ExtractedDocument(
        text="\n".join(lines),
        document_type="html",
        section_headers=tuple(headers),
    )


def _extract_pdf(content: bytes) -> ExtractedDocument:
    reader = PdfReader(BytesIO(content))
    lines: list[str] = []

    for page in reader.pages:
        page_text = page.extract_text() or ""
        for raw_line in page_text.splitlines():
            line = " ".join(raw_line.split())
            if line:
                _append_unique(lines, line)

    return ExtractedDocument(
        text="\n".join(lines),
        document_type="pdf",
        section_headers=tuple(),
    )


def _append_unique(lines: list[str], value: str) -> None:
    if not lines or lines[-1] != value:
        lines.append(value)


def _extract_structured_facts(content: bytes) -> tuple[str, ...]:
    """Recover key fund facts embedded in page data before scripts are removed."""
    source = content.decode("utf-8", errors="ignore")
    facts: list[str] = []
    structured_fields = (
        ("expense_ratio", r"Expense ratio: {value}%", r"[\"']?([0-9]+(?:\.[0-9]+)?)[\"']?"),
        ("exit_load", r"Exit load: {value}", r"[\"']([^\"']+)[\"']"),
        ("min_sip_investment", r"Minimum SIP amount: Rs {value}", r"([0-9]+(?:\.[0-9]+)?)"),
        ("risk", r"Riskometer: {value}", r"[\"']([^\"']+)[\"']"),
        ("benchmark", r"Benchmark: {value}", r"[\"']([^\"']+)[\"']"),
    )
    for field, label, value_pattern in structured_fields:
        match = re.search(
            rf"[\"']{field}[\"']\s*:\s*{value_pattern}",
            source,
        )
        if match:
            facts.append(label.format(value=match.group(1)))
    return tuple(facts)
