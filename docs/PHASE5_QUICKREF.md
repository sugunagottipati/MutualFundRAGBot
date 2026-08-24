# Phase 5 Quick Reference

## What Phase 5 Does

Phase 5 retrieves ranked context from the FAISS vector index, reranks results using multiple signals, and enforces **one citation per answer**. It bridges Phase 4 (routing) and Phase 6 (generation).

## Key Concepts

| Concept | Explanation |
|---------|-------------|
| **Semantic Search** | FAISS finds top-k chunks by L2 distance |
| **Reranking** | Reorders results using authority/recency/relevance |
| **One-Citation** | All context from single source URL only |
| **Quality Filter** | Validates relevance, source compliance, citation count |

## Quick Start

### 1. Run Phase 5 Tests
```bash
pytest tests/test_phase5.py -v
# Result: 25 passed ✅
```

### 2. Run Examples
```bash
python -m scripts.phase5_examples
# Shows: Retrieval, reranking, assembly, validation
```

### 3. Basic Usage
```python
from app.retrieval_phase5 import (
    RetrievalReranker,
    EnhancedContextAssembler,
    RerankerConfig,
    RerankerStrategy,
)

# Retrieve from FAISS
results = retriever.retrieve(query, top_k=10)

# Rerank using hybrid strategy
config = RerankerConfig(strategy=RerankerStrategy.HYBRID)
reranker = RetrievalReranker(metadata_store, config)
reranked = reranker.rerank(results)

# Assemble with validation
assembler = EnhancedContextAssembler()
context, source, is_valid, reason = assembler.assemble_with_validation(reranked)

# Use for generation
if is_valid:
    answer = generator.generate(query, context)
```

## Reranking Strategies

| Strategy | Use Case | Formula |
|----------|----------|---------|
| **RELEVANCE_ONLY** | Pure similarity | No reranking |
| **SOURCE_AUTHORITY** | Trust official sources | 0.6·relevance + 0.3·authority |
| **RECENCY** | Fresh content | 0.6·relevance + 0.1·recency |
| **HYBRID** (Default) | Balanced quality | 0.6·relevance + 0.3·authority + 0.1·recency |

## Quality Validation Checks

```python
validator = RetrievalQualityValidator()

# Context length (100-5000 chars)
is_valid, reason = validator.validate_context_relevance(context)

# Approved source only
is_valid, reason = validator.validate_source_compliance(source_url)

# Single citation
is_valid, reason = validator.validate_single_citation(source_url)

# Chunk coverage
is_valid, reason = validator.validate_chunk_coverage(results)

# Result quality (relevance > 0.3)
is_valid, reason = validator.validate_result_quality(result)
```

## One-Citation Policy

### How It Works
```
Input: 10 results from 3 sources
  [Source A: 4 results, score 2.8] ← SELECTED
  [Source B: 3 results, score 1.9]
  [Source C: 3 results, score 2.1]

Output: Context from Source A only + source URL
```

### Why It Matters
- Compliance: Single, authoritative source
- Clarity: User knows where info came from
- Legal: Avoids mixing sources
- Quality: Focused, consistent context

## Configuration Options

### Reranker Config
```python
config = RerankerConfig(
    strategy=RerankerStrategy.HYBRID,  # Or RELEVANCE_ONLY, SOURCE_AUTHORITY, RECENCY
    relevance_weight=0.6,  # How much to weight semantic similarity
    authority_weight=0.3,  # How much to weight source credibility
    recency_weight=0.1,    # How much to weight document freshness
)
```

### Quality Validator Config
```python
# Context length bounds
validator.validate_context_relevance(context, min_length=100, max_length=5000)

# Result quality threshold (0-1 scale)
validator.validate_result_quality(result, min_relevance_score=0.3)

# Minimum chunks required
validator.validate_chunk_coverage(results, min_chunks=1)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Empty context | Increase top_k or lower relevance threshold |
| Low relevance scores | Check query clarity; consider expansion |
| Multiple sources in output | verify EnhancedContextAssembler used |
| Non-approved URLs | Check metadata_store for bad entries |
| Slow retrieval | Switch from OpenAI to local embeddings |

## Performance

| Operation | Time | Note |
|-----------|------|------|
| FAISS search (74 chunks) | < 1ms | IndexFlatL2 |
| Reranking (top-10 results) | < 1ms | All strategies |
| Quality validation | < 1ms | Full checks |
| Assembly (multi-source) | < 1ms | Python grouping |

## Files

| File | Purpose |
|------|---------|
| `app/retrieval_phase5.py` | Reranker, validator, enhanced assembler |
| `tests/test_phase5.py` | 25 comprehensive tests |
| `scripts/phase5_examples.py` | 5 usage examples |
| `docs/phase-5-implementation.md` | Complete documentation |
| `PHASE5_SUMMARY.md` | Exit criteria & metrics |

## Exit Criteria Status

| Criterion | Status |
|-----------|--------|
| Context quality acceptable | ✅ PASS |
| One-citation enforced | ✅ PASS |
| No non-approved URLs | ✅ PASS |
| All tests passing | ✅ 25/25 |

## Next Phase

**Phase 6 (Generation)**: Takes Phase 5 output (context + source_url) and generates natural language answer.

```
Phase 4 (Router) → Phase 5 (Retrieval) → Phase 6 (Generation)
     Query              Context+Source          Answer
```

## Related Phases

- **Phase 3**: Builds FAISS index (Phase 5 reads from it)
- **Phase 4**: Routes queries (Phase 5 only runs if FACTUAL)
- **Phase 6**: Generates answers (uses Phase 5 context)
- **Phase 7**: Validates responses (checks one-citation from Phase 5)

## Common Tasks

### Task: Change reranking strategy
```python
# Before
config = RerankerConfig(strategy=RerankerStrategy.RELEVANCE_ONLY)

# After
config = RerankerConfig(strategy=RerankerStrategy.HYBRID)
reranker = RetrievalReranker(metadata_store, config)
```

### Task: Filter by section
```python
# Filter results to specific section
results = retriever.retrieve(query, top_k=10, allowed_section_headers=["Holdings"])
```

### Task: Debug low-quality results
```python
# Check individual result quality
for result in results:
    is_valid, reason = validator.validate_result_quality(result)
    print(f"Chunk {result.chunk.metadata.chunk_id}: {reason}")
```

### Task: Verify one-citation
```python
# Ensure output from single source
context, source, is_valid, _ = assembler.assemble_with_validation(results)
assert source in APPROVED_SOURCE_URLS
assert is_valid == True
```

---

**Questions?** See `docs/phase-5-implementation.md` for detailed documentation.
