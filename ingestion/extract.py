"""Document text extraction for HTML and PDF sources."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

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
