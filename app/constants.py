"""Central policy and compliance constants for the assistant."""

from __future__ import annotations

APPROVED_SOURCE_URLS: tuple[str, ...] = (
    "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth",
    "https://groww.in/mutual-funds/hdfc-large-and-mid-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-retirement-savings-fund-equity-plan-direct-growth",
)

ALLOWED_DOMAIN = "groww.in"
DEFAULT_REFUSAL_LINK = "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"

MAX_ANSWER_SENTENCES = 3
REQUIRED_CITATION_COUNT = 1
MANDATORY_FOOTER_PREFIX = "Last updated from sources:"

REFUSAL_MESSAGE = (
    "I can only provide factual information from approved Groww scheme pages and "
    "cannot provide investment advice or recommendations."
)
