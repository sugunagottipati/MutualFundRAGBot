"""Document text extraction for HTML and PDF sources."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import json
import re
from typing import Any

from bs4 import BeautifulSoup
from pypdf import PdfReader


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    document_type: str
    section_headers: tuple[str, ...]
    structured_facts: dict[str, Any]
    extraction_status: dict[str, str]


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
        for fact in structured_facts.get("display_lines", []):
            _append_unique(lines, fact)

    return ExtractedDocument(
        text="\n".join(lines),
        document_type="html",
        section_headers=tuple(headers),
        structured_facts=structured_facts,
        extraction_status=_extraction_status(structured_facts),
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
        structured_facts={},
        extraction_status=_extraction_status({}),
    )


def _append_unique(lines: list[str], value: str) -> None:
    if not lines or lines[-1] != value:
        lines.append(value)


_FACT_FIELDS = (
    "nav", "nav_date", "expense_ratio", "exit_load", "min_sip_investment",
    "minimum_lumpsum_investment", "riskometer", "benchmark", "investment_objective",
    "fund_house", "category", "plan_type", "aum", "returns", "category_returns",
    "category_rank", "holdings", "sector_allocation", "fund_managers", "launch_date",
    "tax_implications", "stamp_duty",
)

_EMBEDDED_FIELD_MAP = {
    "nav": "nav",
    "nav_date": "nav_date",
    "expense_ratio": "expense_ratio",
    "exit_load": "exit_load",
    "min_sip_investment": "min_sip_investment",
    "risk": "riskometer",
    "benchmark": "benchmark",
    "fund_house": "fund_house",
    "category": "category",
    "sub_category": "sub_category",
    "plan_type": "plan_type",
    "aum": "aum",
    "launch_date": "launch_date",
    "tax_impact": "tax_implications",
    "stamp_duty": "stamp_duty",
    "fund_manager_details": "fund_managers",
}


def _extract_structured_facts(content: bytes) -> dict[str, Any]:
    """Recover key fund facts embedded in page data before scripts are removed."""
    source = content.decode("utf-8", errors="ignore")
    facts: dict[str, Any] = {}
    for embedded_field, fact_field in _EMBEDDED_FIELD_MAP.items():
        value = _embedded_value(source, embedded_field)
        if value is not None:
            facts[fact_field] = value

    facts.update(_extract_returns(source))
    if "expense_ratio" in facts:
        facts["expense_ratio"] = _as_number(facts["expense_ratio"])
    if "min_sip_investment" in facts:
        facts["min_sip_investment"] = _as_number(facts["min_sip_investment"])
    facts.update(_human_readable_facts(facts))
    return facts


def _embedded_value(source: str, field: str) -> Any:
    match = re.search(rf"[\"']{re.escape(field)}[\"']\s*:\s*", source)
    if not match:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(source[match.end():].lstrip())
    except json.JSONDecodeError:
        return None
    return value if value not in (None, "") else None


def _extract_returns(source: str) -> dict[str, Any]:
    returns = {}
    category_returns = {}
    for period in ("1y", "3y", "5y", "10y"):
        value = _embedded_value(source, f"return{period}")
        if value is not None:
            returns[period] = _as_number(value)
        value = _embedded_value(source, f"cat_return{period}")
        if value is not None:
            category_returns[period] = _as_number(value)
    facts = {}
    if returns:
        facts["returns"] = returns
    if category_returns:
        facts["category_returns"] = category_returns
    return facts


def _human_readable_facts(facts: dict[str, Any]) -> dict[str, Any]:
    lines: dict[str, Any] = {}
    labels = {
        "expense_ratio": lambda value: f"Expense ratio: {value}%",
        "exit_load": lambda value: f"Exit load: {value}",
        "min_sip_investment": lambda value: f"Minimum SIP amount: Rs {value}",
        "riskometer": lambda value: f"Riskometer: {value}",
        "benchmark": lambda value: f"Benchmark: {value}",
    }
    for field, formatter in labels.items():
        if field in facts:
            lines.setdefault("display_lines", []).append(formatter(facts[field]))
    return lines


def _as_number(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return value
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return value
    return int(number) if number.is_integer() else number


def _extraction_status(facts: dict[str, Any]) -> dict[str, str]:
    return {field: "extracted" if field in facts else "missing" for field in _FACT_FIELDS}
