# Factual Query Catalog

## Purpose

This catalog defines the factual questions the assistant may answer from the seven approved Groww scheme pages. It is the Phase 1 contract for query aliases, source sections, answer shapes, and current corpus availability.

A field being listed as source-supported does not mean its value is already reliably structured. The `Current status` column records the implementation state that Phase 2 must improve.

## Approved Corpus

The catalog applies to these seven sources only:

| Fund | Approved source |
| --- | --- |
| HDFC Mid Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |
| HDFC Flexi Cap Fund Direct Growth (formerly HDFC Equity Fund) | https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth |
| HDFC Small Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth |
| HDFC Gold ETF Fund of Fund Direct Plan Growth | https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth |
| HDFC Large and Mid Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-large-and-mid-cap-fund-direct-growth |
| HDFC Large Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth |
| HDFC Retirement Savings Fund Equity Plan Direct Growth | https://groww.in/mutual-funds/hdfc-retirement-savings-fund-equity-plan-direct-growth |

## Field Catalog

Each field has at least five supported wording variants. Fund names may be added to any example without changing its classification.

| Field | Query aliases and examples | Expected source section | Answer shape | Current status |
| --- | --- | --- | --- | --- |
| NAV | What is the NAV?; What is the current NAV?; What is the net asset value?; What was the NAV on the latest date?; Can you tell me this fund's NAV? | Fund overview / fund details | Value plus date when available | Partially visible in extracted text; structured extraction needed |
| NAV date | What date is the NAV from?; When was this NAV recorded?; What is the NAV as of which date?; When was the NAV last updated?; What is the latest NAV date? | Fund overview / fund details | ISO date | Not consistently extracted; structured extraction needed |
| Expense ratio | What is the expense ratio?; How much is the expense ratio?; What are the fund expenses?; What percentage is charged as expenses?; Tell me the total expense ratio | Minimum investments / fund details | Percentage | Structured extraction exists |
| Exit load | What is the exit load?; Is there an exit load?; How much is the exit fee?; What is charged when I exit?; When does the exit load apply? | Exit load | Rule, percentage, or period | Source text present; structured extraction exists |
| Minimum SIP | What is the minimum SIP amount?; How much do I need to start a SIP?; What is the lowest SIP investment?; What is the minimum monthly investment?; How much is the minimum SIP? | Minimum investments | Rupee amount | Structured extraction exists |
| Minimum lump-sum investment | What is the minimum investment?; What is the minimum lump-sum amount?; How much can I invest at minimum?; What is the minimum one-time investment?; What is the initial investment amount? | Minimum investments | Rupee amount | Source section present; structured extraction needed |
| Riskometer | What is the riskometer?; What is the risk level?; How risky is this fund according to the riskometer?; What risk classification does it have?; Tell me the fund's risk rating | Fund overview / understand terms | Risk label | Structured extraction exists |
| Benchmark | What is the benchmark?; Which index is the fund benchmarked against?; What benchmark index does it track?; What is the fund's benchmark index?; Tell me the benchmark for this scheme | Fund overview / fund details | Index name | Structured extraction exists |
| Investment objective | What is the investment objective?; What does the fund aim to do?; What is this fund's objective?; How does the scheme plan to invest?; Describe the investment objective | Investment Objective | Source-grounded objective text | Section present; value extraction needed |
| Fund house | Which fund house manages this scheme?; What is the asset management company?; Which AMC is this fund from?; Who is the fund house?; What company operates this mutual fund? | Fund house | Fund-house name | Section present; value extraction needed |
| Fund category | What category is this fund in?; Which mutual fund category does it belong to?; Is this an equity or debt fund?; What is the scheme category?; What category does Groww list for this fund? | About fund / returns and rankings | Category label | Category text present; normalization needed |
| Plan type | Is this a direct or regular plan?; What is the plan type?; Is this the direct plan?; Is this a growth plan?; What option does this scheme represent? | Fund title / fund details | Direct/regular and growth/IDCW labels | Present in scheme title; structured field needed |
| Fund size or AUM | What is the fund size?; What is the AUM?; What are the assets under management?; How large is this fund?; What is the total amount managed? | Fund details | Rupee amount and date | Available when source provides it; verify before answering |
| Returns | What is the one-year return?; What was the three-year return?; What is the five-year return?; What was the ten-year return?; What are the fund's historical returns? | Returns and rankings | Period-to-value table | Period data present; field-aware extraction needed |
| Category average | What is the category average?; How did the category average perform?; What is the average return for this category?; What is the category's return?; Show the category average for the period | Returns and rankings | Period-to-value table | Source text present; field-aware extraction needed |
| Category rank | What is the fund's category rank?; What rank does the fund have?; How is it ranked in its category?; What is its ranking among similar funds?; Tell me the fund's rank for the period | Returns and rankings | Rank by period | Source text present; field-aware extraction needed |
| Holdings | What are the holdings?; What are the top holdings?; Which companies does the fund hold?; Show the fund portfolio; What stocks are in the portfolio? | Holdings | Named holdings, optionally with weights | Source section present; retrieval already supported |
| Sector allocation | Which sectors does the fund invest in?; What is the sector allocation?; Which industries are represented?; Show the fund's sector breakdown; How is the portfolio split across sectors? | Holdings | Sector names and weights | Sector text present; field-aware extraction needed |
| Fund managers | Who manages the fund?; What are the fund managers' names?; Who is the fund manager?; Which managers oversee this scheme?; How long have the managers managed it? | Fund management | Names and tenure when available | Section present; value extraction needed |
| Manager tenure | Since when has the fund manager managed the fund?; How long has the manager been in charge?; When did the current manager start?; What is the manager's tenure?; Who has managed the fund since launch? | Fund management | Manager name plus start date/tenure | Source text present; normalization needed |
| Launch or inception date | When was the fund launched?; What is the inception date?; When did this scheme start?; How old is the fund?; When was the fund introduced? | Fund details / fund overview | Date | Verify source field before answering |
| Tax implications | What are the tax implications?; How is this fund taxed?; What tax applies when I redeem?; What are the LTCG and STCG rules?; Tell me about taxation for this fund | Tax implication | Source-grounded tax text | Section present; value extraction needed |
| Stamp duty | What is the stamp duty?; Is stamp duty charged?; How much stamp duty applies?; What stamp duty is charged on investment?; Tell me the stamp duty rate | Stamp duty on investment | Percentage and effective date | Source text present; normalization needed |

## Availability Matrix

The matrix is based on the seven latest processed documents referenced by `data/processed/document_manifest.jsonl`. `Section/text` means the source material contains a matching heading or fact label. `Structured` means a normalized value is currently available for reliable field-aware answering.

| Field group | Section/text coverage | Structured coverage | Phase 2 action |
| --- | ---: | ---: | --- |
| NAV and NAV date | Partial | Partial | Extract value and as-of date; preserve missing status |
| Expense ratio | 7/7 | 7/7 | Add normalized field to document facts |
| Exit load | 7/7 | Partial | Normalize rule, period, and percentage |
| Minimum SIP | 7/7 | 7/7 | Preserve rupee amount and investment frequency |
| Minimum lump-sum investment | 7/7 | 0/7 confirmed | Add extraction and missing-value handling |
| Riskometer | 7/7 | 7/7 | Normalize risk label |
| Benchmark | 7/7 | 7/7 | Normalize index name |
| Objective and fund house | 7/7 | 0/7 confirmed | Extract section values rather than headings only |
| Category and plan type | 7/7 | Partial | Normalize category, direct/regular, and growth/IDCW |
| AUM or fund size | Available when provided | 0/7 confirmed | Detect source-specific label and date |
| Returns | 7/7 | Partial | Store period/value pairs for 1Y, 3Y, 5Y, and 10Y |
| Category average and rank | 7/7 | 0/7 confirmed | Store period/value and period/rank pairs |
| Holdings and sectors | 7/7 | Partial | Preserve names, weights, and sector grouping |
| Managers and tenure | 7/7 | Partial | Extract names and start dates |
| Launch date | Available when provided | 0/7 confirmed | Add explicit date extraction |
| Tax and stamp duty | 7/7 | 0/7 confirmed | Normalize rate, rule, and effective date |

The matrix intentionally distinguishes source presence from extraction readiness. A field with `0/7 confirmed` must not be answered from model inference until Phase 2 verifies it.

## Classification Rules

### Route to `FACTUAL`

Route to factual retrieval when the query requests a source value, description, date, list, historical period, or definition for one fund. Examples:

- “What is the investment objective of HDFC Small Cap Fund?”
- “Who manages HDFC Large Cap Fund?”
- “What was the five-year return?”
- “What tax implications are listed on the scheme page?”

### Keep Refusing as `ADVISORY`

A query remains advisory when it asks for a personal recommendation, suitability judgment, or action:

- “Which fund should I buy?”
- “Is this fund suitable for me?”
- “Should I invest based on the NAV?”
- “Is this a good investment for my goals?”

### Keep Refusing as `COMPARATIVE`

A query remains comparative when it asks to rank or choose between funds, even if it mentions a factual field:

- “Which fund has the better expense ratio?”
- “Compare the returns of these funds.”
- “Rank these funds by risk.”
- “Is HDFC Small Cap better than HDFC Mid Cap?”

### Keep Refusing as `PREDICTIVE`

A query remains predictive when it asks about future or expected performance:

- “What will the NAV be next year?”
- “Will this fund outperform?”
- “What return should I expect?”
- “Will the fund's ranking improve?”

### Keep `AMBIGUOUS`

Keep the query ambiguous when it does not identify a supported fact or intent:

- “Tell me about this fund.”
- “How does investing work?”
- “Give me information.”

## Answer Contracts

Every factual answer must:

1. Use only the selected approved source and retrieved context.
2. State the requested field and fund clearly.
3. Preserve the source's date or period for time-sensitive values.
4. Say that the fact could not be verified when the field is absent or incomplete.
5. Include exactly one approved citation.
6. End with `Last updated from sources: YYYY-MM-DD`.

## Phase 1 Exit Criteria

- The catalog covers all factual fields identified in the enhancement plan.
- Every catalog field has at least five query variants.
- Every field maps to a known source section or is marked conditional.
- The availability matrix distinguishes source presence from structured extraction readiness.
- Advisory, comparative, predictive, and ambiguous boundaries are documented.
- Phase 2 can use this catalog as the contract for extraction tests and normalized field design.
