# Mutual Fund RAG Bot

A facts-only mutual fund Q&A assistant built with a retrieval-augmented generation pipeline. The app answers objective questions from a locked set of approved Groww scheme pages and refuses non-factual or advisory requests.

## What this project does

- Answers factual questions about mutual fund schemes
- Uses a curated source corpus sourced from Groww scheme pages only
- Returns concise answers with a citation link and a source freshness footer
- Refuses investment advice, recommendations, and non-factual queries

## Approved source list

The system is intentionally restricted to these seven Groww URLs:

1. https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth
2. https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth
3. https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth
4. https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth
5. https://groww.in/mutual-funds/hdfc-large-and-mid-cap-fund-direct-growth
6. https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth
7. https://groww.in/mutual-funds/hdfc-retirement-savings-fund-equity-plan-direct-growth

## Sample Q&A

Examples of the kinds of questions the assistant is designed to answer:

- Q: What is the expense ratio of HDFC Large Cap Fund Direct Growth?
  A: The assistant can answer using the approved source page and provide a citation to the corresponding Groww fund page.

- Q: What is the minimum SIP amount for HDFC Mid Cap Fund Direct Growth?
  A: The assistant can return the factual SIP minimum from the official scheme page if it is present in the source corpus.

- Q: What is the benchmark index of HDFC Small Cap Fund Direct Growth?
  A: The assistant can answer benchmark-related factual questions using the cited approved source.

- Q: Are there any exit load charges on this fund?
  A: The assistant can provide the factual exit load details from the official Groww page when available.

- Q: Which fund should I invest in?
  A: The system is designed to refuse this kind of advisory question and respond with a factual-source-only answer.

## Disclaimer

> Facts-only. No investment advice. This assistant is intended to answer factual questions from approved Groww scheme pages only and does not provide recommendations, investment suggestions, or personalized financial guidance.

## Notes

- The corpus is restricted to Groww scheme pages only.
- Responses must include a single citation and a footer in the form: Last updated from sources: YYYY-MM-DD.
- The assistant refuses questions that go beyond factual information or ask for investment advice.
