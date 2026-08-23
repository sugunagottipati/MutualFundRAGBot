from app.constants import APPROVED_SOURCE_URLS
from ingestion.seed_urls import get_seed_urls, validate_source_inventory


def test_seed_urls_match_approved_allowlist() -> None:
    validate_source_inventory()
    assert set(get_seed_urls()) == set(APPROVED_SOURCE_URLS)
    assert len(get_seed_urls()) == 7
