# Phase 5: Retrieval with Reranking and Context Assembly

## Overview

Phase 5 implements semantic retrieval with reranking capabilities and enforces the **one-citation policy**. It retrieves top-k chunks from the persistent Chroma collection, reranks them using multiple signals, and assembles context from a single source URL.

**Key Constraint**: All answers must cite only ONE approved source (one-citation policy).

## Architecture

### 1. Retrieval Flow

```
User Query (from Phase 4 Router)
    ↓
    [Intent Check: FACTUAL? → Proceed, else REFUSE]
    ↓
Embed Query (using FAISS embeddings provider)
    ↓
FAISS Search (top-k semantic search, L2 distance)
    ↓
Filter Results (by source URL, section, metadata)
    ↓
Rerank Results (by authority, recency, relevance combo)
    ↓
Quality Validate (relevance score, chunk coverage)
    ↓
Context Assembly (select single best source, group chunks)
    ↓
Return (context + source_url) to Phase 6 Generation
```

### 2. Reranking Strategies

Phase 5 implements four reranking strategies:

#### 2.1 RELEVANCE_ONLY
- No reranking; pure semantic relevance
- Results ordered by FAISS distance (ascending)
- Use when: Pure similarity is most important
- Score formula: `relevance = max(0, 1 - distance/10)`

#### 2.2 SOURCE_AUTHORITY
- Boosts results from high-authority sources
- All approved Groww URLs are OFFICIAL authority
- Hybrid score: `0.6 * relevance + 0.3 * authority`
- Use when: Source credibility matters

#### 2.3 RECENCY
- Prioritizes newer documents
- Normalized recency score: [0, 1] based on crawl_at timestamp
- Hybrid score: `0.6 * relevance + 0.1 * recency`
- Use when: Content freshness is critical

#### 2.4 HYBRID (Recommended)
- Combines all three signals: relevance, authority, recency
- Score: `0.6 * relevance + 0.3 * authority + 0.1 * recency`
- Weights configurable via `RerankerConfig`
- Use when: Balanced quality across multiple dimensions

### 3. Quality Validation

#### 3.1 Context-Level Validation
- **Relevance**: Context length between 100-5000 characters
- **Source Compliance**: Single source from `APPROVED_SOURCE_URLS`
- **Citation Count**: Exactly one citation required
- **Chunk Coverage**: Minimum chunks from source (default: 1)

#### 3.2 Result-Level Validation
- **Relevance Score Threshold**: `min_relevance_score` (default: 0.3)
- **Low-quality Results**: Filtered before assembly
- **Coverage Check**: Sufficient chunks available

### 4. One-Citation Policy Enforcement

The ContextAssembler enforces single-source citations:

1. **Group** retrieved chunks by `source_url`
2. **Score** each source by cumulative relevance
3. **Select** source with highest total relevance
4. **Assemble** context only from selected source
5. **Return** (context, selected_source_url)

Example:
```
Results from Sources:
  - Source A (3 chunks): total_relevance = 2.8 ← SELECTED
  - Source B (2 chunks): total_relevance = 1.9

Output: Context + "https://groww.in/..." (only Source A)
```

## API Reference

### RetrievalReranker

```python
from app.retrieval_phase5 import (
    RetrievalReranker,
    RerankerConfig,
    RerankerStrategy,
)

# Create config
config = RerankerConfig(
    strategy=RerankerStrategy.HYBRID,
    relevance_weight=0.6,
    authority_weight=0.3,
    recency_weight=0.1,
)

# Create reranker
reranker = RetrievalReranker(metadata_store, config)

# Rerank results
reranked = reranker.rerank(initial_results)
```

**Methods**:
- `rerank(results: list[RetrievalResult]) → list[RetrievalResult]`
  - Reranks results according to configured strategy
  - Returns reranked results with updated ranks

### RetrievalQualityValidator

```python
from app.retrieval_phase5 import RetrievalQualityValidator

# Validate context relevance
is_valid, reason = RetrievalQualityValidator.validate_context_relevance(
    context,
    min_length=100,
    max_length=5000,
)

# Validate source compliance
is_valid, reason = RetrievalQualityValidator.validate_source_compliance(
    source_url,
    approved_urls=APPROVED_SOURCE_URLS,
)

# Validate single citation
is_valid, reason = RetrievalQualityValidator.validate_single_citation(source_url)

# Validate result quality
is_valid, reason = RetrievalQualityValidator.validate_result_quality(
    result,
    min_relevance_score=0.3,
)
```

### EnhancedContextAssembler

```python
from app.retrieval_phase5 import EnhancedContextAssembler

assembler = EnhancedContextAssembler()

# Assemble with validation
context, source, is_valid, reason = assembler.assemble_with_validation(results)

# Returns:
#   context: Assembled text from single source (or empty if invalid)
#   source: Selected source URL (or empty if invalid)
#   is_valid: Boolean validation result
#   reason: Validation reason ("OK" or error message)
```

## Integration with Other Phases

### From Phase 4 (Router)
```python
from app.router import IntentRouter

router = IntentRouter()
should_refuse, intent = router.should_refuse(query)

if not should_refuse:
    # Proceed to Phase 5 retrieval
    results = retriever.retrieve(query)
else:
    # Return Phase 4 refusal response
    return refusal_composer.compose_refusal(intent)
```

### To Phase 6 (Generation)
```python
# Phase 5 output
context, source_url, is_valid, reason = assembler.assemble_with_validation(results)

if is_valid:
    # Phase 6: Generate answer using context + source_url
    answer = generator.generate(query, context)
    answer_with_citation = f"{answer}\n\nSource: {source_url}"
else:
    # Fall back to refusal
    return refusal_composer.compose_refusal(IntentRouter.AMBIGUOUS)
```

## Configuration

### Reranker Configuration

```python
from app.retrieval_phase5 import RerankerConfig, RerankerStrategy

# Balanced configuration (default)
config = RerankerConfig(
    strategy=RerankerStrategy.HYBRID,
    relevance_weight=0.6,
    authority_weight=0.3,
    recency_weight=0.1,
)

# Authority-heavy (trust official sources)
config = RerankerConfig(
    strategy=RerankerStrategy.SOURCE_AUTHORITY,
    authority_weight=0.5,
    relevance_weight=0.5,
)

# Relevance-only (pure similarity)
config = RerankerConfig(
    strategy=RerankerStrategy.RELEVANCE_ONLY,
)
```

## Examples

### Example 1: Basic Semantic Retrieval

```python
from app.retrieval import Retriever
from ingestion.chunking import Chunk, ChunkMetadata
from ingestion.metadata_store import ChunkMetadataStore
from ingestion.index import FAISSIndex
from ingestion.embeddings import get_embeddings_client

# Load components
embeddings = get_embeddings_client("local")
vector_index = ChromaIndexBuilder(embeddings.embedding_dimension, "data/chroma")
metadata_store = ChunkMetadataStore("data/processed/app.db")

# Create retriever
retriever = Retriever(embeddings, faiss_index, metadata_store)

# Retrieve top-5 chunks
query = "What are the main holdings in HDFC Equity Fund?"
results = retriever.retrieve(query, top_k=5)

# Print results
for result in results:
    print(f"Rank {result.rank}:")
    print(f"  Relevance: {result.relevance_score:.2f}")
    print(f"  Section: {result.chunk.metadata.section_header}")
    print(f"  Source: {result.chunk.metadata.source_url}")
```

### Example 2: Reranking and Assembly

```python
from app.retrieval_phase5 import (
    RetrievalReranker,
    RerankerConfig,
    RerankerStrategy,
    EnhancedContextAssembler,
)

# Retrieve results
results = retriever.retrieve(query, top_k=10)

# Rerank using hybrid strategy
config = RerankerConfig(strategy=RerankerStrategy.HYBRID)
reranker = RetrievalReranker(metadata_store, config)
reranked = reranker.rerank(results)

# Assemble context with validation
assembler = EnhancedContextAssembler()
context, source, is_valid, reason = assembler.assemble_with_validation(reranked)

if is_valid:
    print(f"Context assembled from: {source}")
    print(context)
else:
    print(f"Assembly failed: {reason}")
```

### Example 3: Quality Validation Pipeline

```python
from app.retrieval_phase5 import RetrievalQualityValidator

validator = RetrievalQualityValidator()

# Validate context
is_valid, reason = validator.validate_context_relevance(context)
print(f"Context relevance: {reason}")

# Validate source
is_valid, reason = validator.validate_source_compliance(source_url)
print(f"Source compliance: {reason}")

# Validate citation count
is_valid, reason = validator.validate_single_citation(source_url)
print(f"Citation policy: {reason}")

# Validate chunk coverage
is_valid, reason = validator.validate_chunk_coverage(results)
print(f"Coverage: {reason}")
```

## Testing

### Run Phase 5 Tests

```bash
# All Phase 5 tests (25 tests)
pytest tests/test_phase5.py -v

# Specific test class
pytest tests/test_phase5.py::TestSourceAuthorityRanker -v

# With coverage
pytest tests/test_phase5.py --cov=app.retrieval_phase5
```

### Test Coverage

- **SourceAuthorityRanker** (3 tests): Authority scoring for approved/unapproved URLs
- **RecencyRanker** (1 test): Recency score calculation
- **RetrievalReranker** (3 tests): Reranking strategies (relevance-only, authority, hybrid)
- **RetrievalQualityValidator** (8 tests): Context relevance, source compliance, citations, coverage
- **EnhancedContextAssembler** (4 tests): Assembly with validation, filtering, edge cases
- **Phase 5 Integration** (2 tests): End-to-end reranking → assembly pipeline

## Exit Criteria

✅ **Retrieved context quality is acceptable on benchmark sample**
- Relevance scores > 0.3 for top-k results
- Assembled context > 100 chars, < 5000 chars
- Information density adequate for generation

✅ **One-citation context policy enforced for factual answers**
- ContextAssembler groups by source_url
- Selects single source with highest cumulative relevance
- All context from that single source only

✅ **No non-allowlisted URL content reaches generation**
- All chunks filtered by APPROVED_SOURCE_URLS
- Metadata validation confirms source compliance
- RetrievalQualityValidator.validate_source_compliance() passes

## Performance Notes

### Retrieval Speed
- FAISS search: O(log n) to O(n/k) for L2 distance
- 74 chunks indexed: < 1ms search time (IndexFlatL2)
- Reranking: O(k) where k = top_k results

### Memory Usage
- FAISS index: ~30 KB (74 vectors × 384 dims × 4 bytes/float)
- Metadata store: ~1 MB (SQLite with 74 rows + indices)
- Embeddings client: ~150 MB (all-MiniLM-L6-v2 model)

### Scaling Considerations
- IndexFlatL2 stable up to ~10K chunks
- For larger indices, consider IndexIVF or HNSW
- Batch embeddings for better throughput (implemented)

## Known Limitations

1. **Authority Scoring**: All approved URLs treated as OFFICIAL. Refinement possible with URL metadata hierarchy.
2. **Recency Scoring**: All documents from same crawl batch. Score is neutral (0.5) for all. Improves with live updates.
3. **Section-Based Prioritization**: Currently only uses relevance scores. Could weight by section importance (Holdings > Fees).
4. **Multi-Source Answers**: One-citation policy prevents comparative answers. By design for compliance.

## Future Enhancements

1. **Reranking**: Add semantic similarity boost, query expansion
2. **Filtering**: Support section/scheme filters in retrieval
3. **Ranking**: Fine-tune weights based on user feedback
4. **Caching**: LRU cache for repeated queries
5. **Monitoring**: Track retrieval quality metrics over time

## Compliance Notes

- **One-Citation Policy**: Enforced at ContextAssembler level
- **Approved Sources Only**: Validated at metadata filter + quality check
- **Refusal Handling**: Phase 4 gates Phase 5 execution
- **Audit Trail**: chunk_id → source_url mappings fully traceable
