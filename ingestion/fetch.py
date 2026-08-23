"""HTTP fetch utilities for ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx


@dataclass(frozen=True)
class FetchResult:
    source_url: str
    final_url: str
    status_code: int
    content_type: str
    content: bytes
    fetched_at: str
    error: str | None = None


DEFAULT_USER_AGENT = "MutualFundRAGBot/0.1 (+facts-only-ingestion)"


def fetch_url(
    url: str,
    *,
    timeout_seconds: int = 20,
    retries: int = 2,
    user_agent: str = DEFAULT_USER_AGENT,
) -> FetchResult:
    """Fetch URL content with retry support and return structured metadata."""
    headers = {"User-Agent": user_agent}
    last_error: str | None = None

    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout_seconds, follow_redirects=True, headers=headers) as client:
                response = client.get(url)
                content_type = response.headers.get("content-type", "application/octet-stream")
                return FetchResult(
                    source_url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type.split(";")[0].strip().lower(),
                    content=response.content,
                    fetched_at=_utcnow(),
                    error=None,
                )
        except httpx.HTTPError as exc:
            last_error = str(exc)
            if attempt == retries:
                break

    return FetchResult(
        source_url=url,
        final_url=url,
        status_code=0,
        content_type="",
        content=b"",
        fetched_at=_utcnow(),
        error=last_error or "Unknown fetch error",
    )


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
