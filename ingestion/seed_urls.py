"""Approved source inventory and seed URL helpers for ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from app.constants import ALLOWED_DOMAIN, APPROVED_SOURCE_URLS


@dataclass(frozen=True)
class SourceRecord:
    source_url: str
    source_type: str
    scheme_name: str
    source_priority: str
    refresh_frequency: str
    status: str


SOURCE_INVENTORY: tuple[SourceRecord, ...] = (
    SourceRecord(
        source_url="https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        source_type="scheme_page",
        scheme_name="HDFC Mid Cap Fund Direct Growth",
        source_priority="high",
        refresh_frequency="weekly",
        status="active",
    ),
    SourceRecord(
        source_url="https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
        source_type="scheme_page",
        scheme_name="HDFC Flexi Cap Fund Direct Growth (formerly HDFC Equity Fund)",
        source_priority="high",
        refresh_frequency="weekly",
        status="active",
    ),
    SourceRecord(
        source_url="https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
        source_type="scheme_page",
        scheme_name="HDFC Small Cap Fund Direct Growth",
        source_priority="high",
        refresh_frequency="weekly",
        status="active",
    ),
    SourceRecord(
        source_url="https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth",
        source_type="scheme_page",
        scheme_name="HDFC Gold ETF Fund of Fund Direct Plan Growth",
        source_priority="medium",
        refresh_frequency="weekly",
        status="active",
    ),
    SourceRecord(
        source_url="https://groww.in/mutual-funds/hdfc-large-and-mid-cap-fund-direct-growth",
        source_type="scheme_page",
        scheme_name="HDFC Large and Mid Cap Fund Direct Growth",
        source_priority="high",
        refresh_frequency="weekly",
        status="active",
    ),
    SourceRecord(
        source_url="https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
        source_type="scheme_page",
        scheme_name="HDFC Large Cap Fund Direct Growth",
        source_priority="high",
        refresh_frequency="weekly",
        status="active",
    ),
    SourceRecord(
        source_url="https://groww.in/mutual-funds/hdfc-retirement-savings-fund-equity-plan-direct-growth",
        source_type="scheme_page",
        scheme_name="HDFC Retirement Savings Fund Equity Plan Direct Growth",
        source_priority="medium",
        refresh_frequency="weekly",
        status="active",
    ),
)


def get_seed_urls() -> list[str]:
    """Return ingestion seed URLs from the locked source inventory."""
    return [record.source_url for record in SOURCE_INVENTORY if record.status == "active"]


def get_active_source_inventory() -> tuple[SourceRecord, ...]:
    """Return active source records from the locked inventory."""
    return tuple(record for record in SOURCE_INVENTORY if record.status == "active")


def validate_source_records(
    records: tuple[SourceRecord, ...],
    *,
    enforce_exact_allowlist: bool = True,
) -> None:
    """Validate source records against domain and allowlist policies."""
    inventory_urls = tuple(record.source_url for record in records)

    if len(inventory_urls) != len(set(inventory_urls)):
        raise ValueError("Duplicate source URLs found in source inventory.")

    for url in inventory_urls:
        host = urlparse(url).hostname or ""
        if not (host == ALLOWED_DOMAIN or host.endswith(f".{ALLOWED_DOMAIN}")):
            raise ValueError(f"Source URL is outside allowed domain: {url}")

    approved = set(APPROVED_SOURCE_URLS)
    inventory = set(inventory_urls)
    if not inventory.issubset(approved):
        extra = sorted(inventory - approved)
        raise ValueError(f"Source inventory contains non-allowlisted URLs: {extra}")

    if enforce_exact_allowlist and inventory != approved:
        missing = sorted(approved - inventory)
        raise ValueError(
            "Source inventory must match approved allowlist exactly. "
            f"Missing: {missing or 'none'}"
        )


def validate_source_inventory() -> None:
    """Validate that source inventory matches policy rules exactly."""
    validate_source_records(get_active_source_inventory(), enforce_exact_allowlist=True)


def _main() -> None:
    validate_source_inventory()
    print("Source inventory validation passed. Approved URLs:")
    for url in get_seed_urls():
        print(f"- {url}")


if __name__ == "__main__":
    _main()
