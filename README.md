# Mutual Fund RAG Bot

A facts-only mutual fund Q&A assistant built with a retrieval-augmented generation pipeline. The app answers objective questions from a locked set of approved Groww scheme pages and refuses non-factual or advisory requests.

## Overview

This project implements a small RAG-based assistant for mutual fund facts. It ingests a fixed corpus of Groww scheme pages, chunks and indexes the content, retrieves the most relevant passages, and generates concise answers grounded in those approved sources.

The system is intentionally narrow and policy-driven:

- It only uses approved Groww URLs as the source corpus
- It answers factual questions only
- It includes a citation URL and a source freshness footer
- It refuses advisory or recommendation-style requests

## What this project does

- Answers factual questions about mutual fund schemes
- Uses a curated source corpus sourced from Groww scheme pages only
- Returns concise answers with a citation link and a source freshness footer
- Refuses investment advice, recommendations, and non-factual queries

## Usage instructions

### 1. Create the environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start the app

```bash
uvicorn app.api:app --reload
```

Then open the app in a browser at:

- http://localhost:8000/

### 3. Query the API

Example request:

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the expense ratio of HDFC Large Cap Fund Direct Growth?"}'
```

Check the approved source list:

```bash
curl "http://localhost:8000/sources"
```

Check service health:

```bash
curl "http://localhost:8000/health"
```

### 4. Ingestion and rebuilds

If you need to refresh the approved sources or rebuild the index, use the ingestion scripts in the repository. The project is designed to validate the fixed source inventory before use.

## Approved source list

The system is intentionally restricted to these seven Groww URLs:

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
