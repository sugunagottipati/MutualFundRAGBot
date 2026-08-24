# Factual Query Coverage Enhancement Plan

## Objective

Expand the Mutual Fund FAQ Assistant so that every factual field present in the seven approved Groww source pages can be reliably identified, retrieved, answered, cited, and evaluated.

The enhancement must preserve the existing constraints:

- Facts-only responses
- Approved Groww sources only
- Exactly one citation per response
- Maximum three sentences per response
- Mandatory `Last updated from sources: YYYY-MM-DD` footer
- Advisory, comparative, predictive, and ambiguous queries remain refused

## Current Gaps

The router currently covers common queries for holdings, sectors, expense ratio, exit load, SIP amount, NAV, riskometer, benchmark, returns, fund manager, launch date, and fund size. The source corpus also contains or references these factual areas:

- Investment objective
- Fund house
- Tax implications
- Stamp duty
- Fund category
- Fund managers and manager tenure
- Plan type and growth/direct-plan details
- NAV and related date variants
- One-year, three-year, five-year, and ten-year returns
- Category average and fund rank
- AUM or fund-size details when available

Some values are present only in extracted page text, while the structured extractor currently captures only a subset of fields. Router coverage alone is therefore insufficient.

## Phase 1: Define the Factual Query Catalog

### Scope

Create a canonical catalog of supported factual fields, aliases, example queries, expected source sections, and answer formats.

### Deliverables

- Field catalog covering all supported source facts
- Query aliases for each field
- Classification rules distinguishing factual queries from advisory or predictive queries
- Field availability matrix across all seven funds

### Acceptance Criteria

- Every supported field has at least five natural-language query variants
- Each field maps to one or more known source sections
- Ambiguous, advisory, comparative, and predictive boundary cases are documented
- Fields unavailable for a specific fund are marked explicitly rather than inferred

## Phase 2: Extend Structured Extraction

### Scope

Update `ingestion/extract.py` to recover normalized facts from embedded page data and visible page text.

### Target Fields

- NAV and NAV date
- Expense ratio
- Exit load
- Minimum SIP and minimum lump-sum investment
- Riskometer
- Benchmark
- Investment objective
- Fund house
- Fund category
- Plan type
- AUM or fund size
- Tax implications
- Stamp duty
- Return periods
- Category average and rank
- Fund manager names and tenure

### Deliverables

- Normalized structured facts in processed documents
- Consistent field names and value formats
- Extraction tests for present, missing, and malformed values
- Explicit extraction status for fields that cannot be verified

### Acceptance Criteria

- Extracted values match the source page text
- Missing values remain missing and are never fabricated
- Dates, percentages, rupee amounts, and return values use stable formats
- Existing ingestion tests continue to pass

## Phase 3: Add Field-Aware Retrieval Metadata

### Scope

Make retrieved chunks easier to target by associating them with factual fields and source sections.

### Deliverables

- `fact_type` or equivalent metadata on factual chunks
- Field-aware retrieval or filtering for direct fact queries
- Traceability from answer field to source URL and source chunk
- Compatibility with the existing one-source assembly policy

### Acceptance Criteria

- A query for one fact prioritizes chunks containing that fact
- Retrieved context comes from one approved source
- Source URL and crawl date remain available to response generation
- Existing retrieval and reranking behavior remains compatible

## Phase 4: Expand Factual Routing

### Scope

Extend `app/router.py` with precise patterns and aliases for the cataloged factual fields.

### Example Patterns

- `investment objective`, `objective of the fund`
- `fund house`, `asset management company`, `AMC`
- `tax`, `taxation`, `tax implications`, `capital gains`
- `stamp duty`
- `category`, `fund category`, `equity category`
- `fund manager`, `who manages`, `managed by`
- `plan type`, `direct plan`, `regular plan`, `growth plan`
- `current NAV`, `net asset value`, `NAV date`
- `1-year`, `3-year`, `5-year`, and `10-year returns`
- `category average`, `fund rank`, `ranking in category`

### Deliverables

- Factual patterns with word-boundary-aware matching
- Pattern ordering that preserves advisory and predictive refusals
- Router tests for positive and negative boundary cases

### Acceptance Criteria

- Supported factual variants route to `FACTUAL`
- Questions asking what to buy, which fund is better, or whether returns will rise remain refused
- Generic questions without a supported fact remain `AMBIGUOUS`
- No broad pattern causes advisory queries to pass through

## Phase 5: Improve Answer Generation and Fallbacks

### Scope

Make generation field-aware and safe when a requested value is unavailable or unclear.

### Deliverables

- Field-specific generation prompts or answer templates where useful
- Explicit unknown-answer response for absent or unverifiable facts
- Validation that generated values are grounded in retrieved context
- Consistent one-citation and footer enforcement

### Acceptance Criteria

- Answers contain only values supported by the selected source context
- Unsupported values produce a compliant inability-to-verify response
- Responses remain within three sentences
- Exactly one approved citation is returned

## Phase 6: Expand Automated Evaluation

### Scope

Extend `tests/data/phase10_evaluation.json` and relevant test modules to cover the full factual catalog.

### Test Coverage

For every factual field:

- Multiple wording variants
- At least two fund names where the field exists
- Missing-field behavior
- Correct route and source URL
- Expected answer terms
- One-citation compliance

Also retain boundary cases for:

- Advisory prompts
- Comparative prompts
- Predictive prompts
- Ambiguous prompts

### Acceptance Criteria

- All existing tests pass
- Every cataloged factual field has an end-to-end test
- No factual query is refused solely because of an unsupported wording variant
- No unsafe query is accidentally routed to generation

## Phase 7: Corpus and Deployment Verification

### Scope

Verify the refreshed corpus and deployed service use the same metadata and supported field behavior.

### Deliverables

- Corpus consistency check for processed JSON, manifest, ingestion logs, and raw files
- Duplicate snapshot policy for old and current crawls
- Deployment smoke tests for `/health`, `/sources`, and `/ask`
- Documentation of supported factual fields and known source limitations

### Acceptance Criteria

- Every manifest entry points to a valid processed document
- Every processed document is valid JSON and references an existing raw file
- Deployed behavior matches local evaluation behavior
- Source freshness is reflected in the response footer

## Recommended Implementation Order

1. Define the factual query catalog and field availability matrix
2. Extend structured extraction
3. Add extraction and normalization tests
4. Add field-aware retrieval metadata
5. Expand factual routing and router tests
6. Add safe generation and missing-value fallbacks
7. Expand end-to-end evaluation
8. Run corpus and deployment verification

The extraction and evaluation phases should precede broad router expansion. Routing a query as factual without reliable source fields would allow the request through but would not guarantee a grounded answer.
