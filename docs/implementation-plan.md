# Mutual Fund FAQ Assistant - Phase-wise Implementation Plan

## 1. Plan Objective
This plan translates the project problem statement and architecture into a practical, phase-wise execution roadmap for building a facts-only Mutual Fund FAQ Assistant.

This implementation is designed to use Groq as the LLM provider for response generation.

## 2. Core Delivery Constraints
- Facts-only responses from the approved 7 Groww URLs
- No investment advice or recommendations
- Maximum 3 sentences per response
- Exactly one citation link per response
- Mandatory footer: Last updated from sources: <date>
- Refusal required for advisory or comparative prompts
- Minimal UI with a visible disclaimer: Facts-only. No investment advice.

## 3. Groq-Centered Technical Decisions

### 3.1 LLM Provider
- Provider: Groq
- Primary use: low-latency answer generation in constrained format
- Fallback behavior: if generation fails validation twice, return safe refusal response

### 3.2 Suggested Model Strategy
- Generation model: a reliable Groq chat model suitable for instruction-following and concise output
- Temperature: low, such as 0.1, to reduce verbosity and drift
- Max tokens: capped for short answers

### 3.3 Embedding Strategy
Groq is used for answer generation. Embeddings can be handled by:
- Option A: an external embedding provider
- Option B: local embedding model for reduced cost and offline tolerance

Recommendation for MVP:
- Keep Groq for LLM generation
- Use a stable embedding provider already supported by your retrieval stack

### 3.4 Environment Variables
- LLM_PROVIDER=groq
- GROQ_API_KEY=<your-key>
- GROQ_MODEL=<selected-model>
- EMBEDDING_PROVIDER=<selected-provider>
- EMBEDDING_MODEL=<selected-model>
- VECTOR_DB_PATH=./data/chroma
- SQLITE_PATH=./data/processed/app.db
- ALLOWED_DOMAINS=groww.in
- ALLOWED_SOURCE_URLS=https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth,https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth,https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth,https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth,https://groww.in/mutual-funds/hdfc-large-and-mid-cap-fund-direct-growth,https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth,https://groww.in/mutual-funds/hdfc-retirement-savings-fund-equity-plan-direct-growth
- DEFAULT_REFUSAL_LINK=https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth

## 4. Phase-wise Implementation Plan

## Phase 0: Project Setup and Compliance Baseline
Purpose:
Establish repository structure, runtime configuration, and compliance rules before any model behavior is implemented.

Tasks:
- Create folders for app, ingestion, ui, tests, docs, and data
- Add dependency file and environment template
- Add config loader for Groq and retrieval settings
- Add central constants for response rules and refusal policy
- Add domain and URL allowlist policy (groww.in + exact 7 approved URLs)

Deliverables:
- Project skeleton ready for coding
- Environment configuration for Groq
- Compliance rule constants committed

Exit Criteria:
- App starts and loads environment without errors
- Groq API key and model config are validated at startup
- Allowlist policy is centrally defined

## Phase 1: Source Inventory and Corpus Curation
Purpose:
Build a trusted source list from official domains only.

Tasks:
- Lock scheme universe to the following 7 schemes:
  - https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth
  - https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth
  - https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth
  - https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth
  - https://groww.in/mutual-funds/hdfc-large-and-mid-cap-fund-direct-growth
  - https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth
  - https://groww.in/mutual-funds/hdfc-retirement-savings-fund-equity-plan-direct-growth
- Use only the 7 approved Groww URLs as the corpus (no additional URLs)
- Create source inventory with metadata fields:
  - source_url
  - source_type
  - scheme_name
  - source_priority
  - refresh_frequency
  - status

Deliverables:
- Curated source inventory document
- Initial approved URL seed list for ingestion

Exit Criteria:
- All URLs belong to groww.in and are present in the approved 7-URL allowlist
- No additional URLs are used outside the approved 7
- No third-party aggregators in corpus

## Phase 2: Ingestion Pipeline
Purpose:
Fetch and normalize official documents for retrieval.

Tasks:
- Implement URL seeding from inventory
- Implement HTML and PDF fetcher with retries and timeout
- Extract text from pages and PDFs
- Normalize content and preserve meaningful section headers
- Tag each document with metadata and crawl timestamp
- Deduplicate content by hash

Deliverables:
- Raw files in data/raw
- Processed normalized documents in data/processed
- Source health and ingestion status logs

Exit Criteria:
- Successful ingestion of minimum 15 official URLs
- Every indexed document has metadata and crawled timestamp
- Failed sources are logged with clear reasons

## Phase 3: Chunking, Embeddings, and Index Build
Purpose:
Create retrieval-ready knowledge representation.

Tasks:
- Implement section-aware chunking for processed JSON documents in data/processed/documents
- Use "##" heading markers from normalized text as primary chunk boundaries
- Apply adaptive chunk sizing:
  - Narrative sections: target 220 to 320 tokens, overlap 40 to 60 tokens
  - Table-dense sections (holdings/returns rows): target 120 to 180 tokens, overlap 20 to 40 tokens
- Enforce line-safe splitting so key-value/table rows are not broken mid-row
- Attach chunk metadata fields:
  - chunk_id
  - source_url
  - scheme_name
  - source_type
  - section_header
  - crawled_at
  - content_hash
  - chunk_index
  - start_line
  - end_line
- Add chunk-level deduplication hash to reduce repeated table/header fragments across snapshots
- Generate embeddings for chunks
- Build a persistent Chroma collection
- Persist chunk metadata in SQLite
- Add index rebuild and incremental upsert commands

Updated chunking strategy from current processed corpus:
- Input format assumption: each processed file contains metadata plus one normalized text field with newline-delimited content and "##" section markers.
- First split by section marker, then pack lines into token-bounded chunks.
- Keep high-signal factual fields (expense ratio, exit load, minimum sip, benchmark, riskometer) in single chunks whenever possible.
- For long holdings lists, chunk by contiguous row bands to preserve local context for retrieval.
- Preserve one-source traceability by ensuring each chunk inherits exactly one source_url and content_hash.

Deliverables:
- Working Chroma vector database
- Metadata tables for retrieval filters and section-aware chunk tracing
- Rebuild and update scripts

Exit Criteria:
- Retrieval returns relevant chunks for sample factual queries
- Chunk to source mapping is traceable end-to-end
- Section header and line-range traceability is available for every stored chunk
- Index integrity checks pass

## Phase 4: Query Routing and Refusal Handling
Purpose:
Guarantee policy-safe behavior before answer generation.

Tasks:
- Implement rule-based intent router for factual versus advisory queries
- Add advisory keyword and phrase patterns
- Implement refusal response composer with one link from the approved Groww URL list
- Add tests for advisory, comparative, predictive, and ambiguous prompts

Deliverables:
- Router module
- Refusal module
- Refusal behavior test suite

Exit Criteria:
- Advisory prompts are consistently refused
- Refusal responses are polite and include one relevant approved Groww URL
- No factual flow is triggered for clear advisory prompts

## Phase 5: Retrieval and Context Assembly
Purpose:
Retrieve only relevant, compliant context and enforce one-citation design.

Tasks:
- Build retriever for top-k semantic search using Chroma
- Apply metadata filters for source type and approved URL allowlist
- Implement reranking logic for high-authority sources
- Implement single-citation context assembler by grouping chunks by source URL
- Return only chunks tied to one selected citation URL

Deliverables:
- Retriever and reranker modules
- Context assembler with one-source enforcement
- Retrieval quality smoke tests

Exit Criteria:
- Retrieved context quality is acceptable on benchmark sample
- One-citation context policy enforced for factual answers
- No non-allowlisted URL content reaches generation

## Phase 6: Groq Answer Generation Layer
Purpose:
Generate concise factual answers using Groq with strict instruction control.

Tasks:
- Implement Groq client wrapper
- Define system and task prompt templates for facts-only mode
- Generate from retrieved context only
- Add unknown-answer behavior when evidence is insufficient
- Keep answer concise and neutral

Deliverables:
- Groq-backed generator module
- Prompt templates for factual and unknown-answer flows
- Unit tests for output shape assumptions

Exit Criteria:
- Groq responses are grounded in provided context
- Unknown-answer path works when retrieval evidence is weak
- Generated body remains concise under constraints

## Phase 7: Compliance Validator and Fallback Loop
Purpose:
Enforce non-negotiable response constraints before user delivery.

Tasks:
- Validate sentence count is less than or equal to 3
- Validate exactly one citation link
- Validate citation is from the approved 7-URL allowlist
- Validate footer with source date format
- Validate no advisory language in factual mode
- Add retry-once regeneration with stricter formatting instruction
- Add safe fallback refusal if second validation fails

Deliverables:
- Validator module
- Regenerate-and-recheck loop
- Compliance test suite

Exit Criteria:
- Constraint adherence rate is near-perfect on test set
- Invalid outputs are blocked from user view
- Fallback behavior is deterministic

## Phase 8: API Layer and Contract Stabilization
Purpose:
Expose a robust backend interface for UI and future integrations.

Tasks:
- Implement endpoint for ask flow
- Implement health and source status endpoints
- Add structured response schema:
  - answer
  - citation
  - last_updated_from_sources
  - route
- Add timeout, error handling, and clean failure responses

Deliverables:
- Production-ready API contract for MVP
- API test coverage for success and failure paths

Exit Criteria:
- End-to-end request flow works for factual and refusal routes
- Error responses are stable and actionable
- Contract passes integration tests

## Phase 9: Stitch-Based Rich UI Experience
Purpose:
Deliver the production-oriented FundFacts frontend represented by the Stitch
design export, while preserving the facts-only compliance contract.

Design direction:
- Editorial fintech utility using a warm paper-textured surface, deep charcoal
  text, forest green actions, and restrained saffron highlights
- Playfair Display for editorial headings and IBM Plex Sans for interface and
  data text
- Fine outlines, tonal layering, 8px corners, generous spacing, and restrained
  motion instead of heavy shadows or decorative card nesting
- Desktop two-column composition that becomes a fluid single-column mobile
  experience at narrow widths

Tasks:
- Build the responsive FundFacts shell with branded navigation, source status,
  welcome content, assistant panel, and source-integrity summary
- Add exactly three usable example questions tied to the approved FAQ flows
- Keep the disclaimer visible above the composer in every UI state:
  "Facts-only. No investment advice."
- Integrate the composer with `POST /ask`, including empty-input prevention,
  500-character input limit, Enter-to-send, Shift+Enter line breaks, disabled
  submission state, and focus restoration
- Render factual answers with the answer body, route label, exactly one source
  link, source freshness footer, and copy-answer action
- Render advisory, comparative, predictive, and ambiguous responses as a
  consistent facts-only guidance state without recommendation styling
- Add loading and dependency-unavailable states with clear retry-oriented copy
- Add an approved-sources drawer backed by `GET /sources`, including scheme
  names, approved status, external links, close behavior, backdrop, and Escape
  handling
- Ensure keyboard accessibility, visible focus states, reduced visual clutter,
  safe external-link behavior, and responsive text that does not overflow

Deliverables:
- Stitch-aligned responsive frontend in `ui/index.html` and `ui/styles.css`
- API-backed browser behavior in `ui/app.js`
- FastAPI static serving at `/` with assets under `/assets`
- Desktop and mobile layouts covering welcome, answer, refusal, loading, error,
  and approved-source views

Exit Criteria:
- User can submit a factual query and receive the structured `/ask` response
  without losing the single-citation or source-date presentation
- Advisory queries visibly and consistently communicate the facts-only boundary
- Exactly three example questions are present and usable
- The disclaimer remains visible above the input while the assistant is usable
- Approved sources can be opened from the source drawer and remain restricted to
  the backend allowlist
- The UI remains readable and functional on desktop and mobile widths
- `/` and `/assets/styles.css` are served successfully by FastAPI

## Phase 10: Quality Assurance and Evaluation
Purpose:
Measure correctness, policy adherence, and robustness.

Tasks:
- Build evaluation dataset:
  - 30 factual prompts
  - 15 advisory prompts
  - 10 boundary prompts
- Evaluate correctness and citation relevance
- Track compliance metrics:
  - three-sentence adherence
  - single-citation adherence
  - refusal precision
- Add regression suite for CI
- Add a GitHub Actions scheduled ingestion workflow that runs the approved Groww
  source refresh and incremental index update every day at 10:02 AM IST
  (`32 4 * * *` UTC), with manual dispatch available for operational recovery
- Make the workflow fail clearly on ingestion or index errors and retain the
  ingestion status logs as workflow artifacts

Deliverables:
- Evaluation report with baseline scores
- Regression test suite for future changes
- Daily Groww ingestion GitHub Actions workflow

Exit Criteria:
- Meets success criteria from problem statement
- No critical compliance violations in benchmark runs
- The scheduled workflow refreshes only the approved Groww pages and ingests
  the latest data at 10:02 AM IST each day

## Phase 11: Documentation and Release Readiness
Purpose:
Finalize project for handoff and reproducibility.

Tasks:
- Update README with setup and run commands
- Document Groq setup and API key instructions
- Add known limitations and scope boundaries
- Document source refresh and maintenance workflow

Deliverables:
- Complete README
- Updated docs package
- Release checklist

Exit Criteria:
- New contributor can run system from docs only
- Compliance boundaries are explicitly documented
- Operational runbook is complete

## 5. Suggested Timeline
- Week 1: Phase 0 to Phase 2
- Week 2: Phase 3 to Phase 5
- Week 3: Phase 6 to Phase 8
- Week 4: Phase 9 to Phase 11

If needed, Phase 10 can start in parallel with late Phase 8 and Phase 9 once the API contract stabilizes.

## 6. Responsibility Matrix
- Data and ingestion: source curation, fetch, extraction, chunking, indexing
- Backend and LLM: router, retriever, Groq generation, validator, API
- Frontend: minimal UI and interaction flow
- QA and compliance: benchmark suite, regression checks, policy audits

## 7. Risk Register and Mitigation

Risk: Source content changes or URLs break
- Mitigation: scheduled source health checks and weekly refresh

Risk: Model outputs violate format constraints
- Mitigation: strict validator plus retry-once plus fallback refusal

Risk: Advisory leakage
- Mitigation: deterministic routing plus phrase tests plus post-generation policy check

Risk: Multi-source citation leakage
- Mitigation: single-citation context assembly before generation

Risk: URL drift outside approved corpus
- Mitigation: hard URL allowlist filtering in retrieval and validator

## 8. Definition of Done for Entire Plan
The implementation plan is fully executed when:
- Facts-only Q and A works on curated corpus
- Advisory queries are refused politely and reliably
- Every answer includes exactly one official citation
- Every answer includes Last updated from sources footer
- UI is minimal, usable, and compliant
- Evaluation and regression checks pass
- Documentation supports complete local setup with Groq
