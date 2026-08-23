# Phase 3: Chunking, Embeddings, and Index Build - Implementation Summary

## Overview
Phase 3 implements the complete vector indexing pipeline for semantic search across the curated mutual fund corpus. This includes section-aware chunking, embeddings generation, FAISS vector indexing, and SQLite metadata persistence.

## Core Components

### 1. **Chunking Module** (`ingestion/chunking.py`)

**Purpose**: Convert normalized documents into retrieval-ready chunks with full traceability.

**Key Features**:
- **Section-Aware Splitting**: Uses "##" markers as primary chunk boundaries
- **Token-Aware Sizing**:
  - Narrative sections: 220-320 tokens target, 40-60 token overlap
  - Table-dense sections: 120-180 tokens target, 20-40 token overlap
- **Line-Safe Splitting**: Never breaks mid-line (preserves table rows and key-value pairs)
- **Table Detection**: Automatically detects and adjusts chunk sizing for table-dense sections
- **Rich Metadata**:
  - `chunk_id`: Unique identifier tied to source document
  - `source_url`, `scheme_name`, `source_type`: Compliance traceability
  - `section_header`: Retrieved from "##" markers for contextual retrieval
  - `crawled_at`: ISO timestamp for source freshness
  - `content_hash`: Hash of original document for deduplication
  - `chunk_content_hash`: Hash of chunk content for chunk-level deduplication
  - `start_line`, `end_line`: Line-range traceability for source verification

**Classes**:
- `TokenCounter`: Uses tiktoken (GPT-3.5 encoding) for accurate token counting
- `ChunkingSplitter`: Line-aware chunk splitting with token bounds
- `SectionAwareChunker`: Orchestrates full chunking pipeline

**Usage Example**:
```python
from ingestion.chunking import SectionAwareChunker

chunker = SectionAwareChunker()
chunks = chunker.chunk(
    text=normalized_text,
    source_url="https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
    scheme_name="HDFC Equity Fund Direct Growth",
    source_type="scheme_page",
    crawled_at="2024-01-01T00:00:00Z",
    content_hash="abc123..."
)
```

---

### 2. **Embeddings Client** (`ingestion/embeddings.py`)

**Purpose**: Generate vector embeddings for chunks using pluggable providers.

**Supported Providers**:

1. **OpenAI (`text-embedding-3-small`)**
   - Dimension: 1536
   - Requires: `OPENAI_API_KEY` environment variable
   - Cost-effective for production

2. **Local (`sentence-transformers`)**
   - Default model: `all-MiniLM-L6-v2` (384 dims)
   - No API keys required
   - Suitable for development and offline use

**Abstract Interface** (`EmbeddingsClient`):
- `embed(text: str) -> np.ndarray`: Single text
- `embed_batch(texts: list[str]) -> list[np.ndarray]`: Batch embedding
- `embedding_dimension: int`: Vector dimensionality

**Usage Example**:
```python
from ingestion.embeddings import get_embeddings_client

# Use OpenAI
embeddings = get_embeddings_client(
    provider="openai",
    api_key="sk-...",
    model="text-embedding-3-small"
)

# Or use local (requires no API key)
embeddings = get_embeddings_client(provider="local")

vectors = embeddings.embed_batch(chunk_texts)
```

---

### 3. **FAISS Index** (`ingestion/index.py`)

**Purpose**: Build and manage a scalable vector similarity index.

**Features**:
- **Index Type**: `IndexIVFFlat` (Inverted File Index) for scalability
  - Automatically uses `IndexFlatL2` during training
  - Supports ~10,000+ chunks efficiently
- **ID Mapping**: Bidirectional mapping between FAISS internal IDs and chunk IDs
- **Search**: L2 distance-based similarity search
- **Persistence**: Automatic save/load of index and mappings
- **Statistics**: Track total vectors, embedding dimension, type

**Key Methods**:
- `add_embeddings(embeddings, chunk_ids)`: Add vectors to index
- `search(query_embedding, k)`: Find k nearest neighbors
- `search_batch(query_embeddings, k)`: Batch search
- `save()`: Explicitly persist to disk
- `get_index_stats()`: Current index statistics

**File Structure**:
- `data/faiss/index.bin`: FAISS index binary
- `data/faiss/id_mapping.json`: ID mappings and metadata

**Usage Example**:
```python
from ingestion.index import FAISSIndexBuilder
import numpy as np

index = FAISSIndexBuilder(
    embedding_dimension=1536,
    index_path="data/faiss/index.bin"
)

# Add embeddings
embeddings = [np.random.random(1536).astype(np.float32) for _ in range(100)]
chunk_ids = [f"chunk_{i}" for i in range(100)]
index.add_embeddings(embeddings, chunk_ids)

# Search
query_embedding = np.random.random(1536).astype(np.float32)
chunk_ids, distances = index.search(query_embedding, k=5)
```

---

### 4. **Metadata Store** (`ingestion/metadata_store.py`)

**Purpose**: Persist and query chunk metadata for filtering and traceability.

**Database Schema**:

**`chunks` Table**:
```sql
chunk_id (PK)
source_url (indexed)
scheme_name (indexed)
source_type
section_header (indexed)
crawled_at
content_hash (indexed)
chunk_index
start_line, end_line
chunk_content_hash (indexed)
content
created_at
```

**`chunk_dedup` Table**:
```sql
chunk_content_hash (PK)
chunk_id (FK)
first_seen_at
seen_count
```

**Key Methods**:
- `insert_chunks(chunks)`: Bulk insert chunks and track dedup
- `get_chunk(chunk_id)`: Retrieve single chunk
- `get_chunks_by_source_url(url)`: Filter by source
- `get_chunks_by_scheme_name(name)`: Filter by fund scheme
- `get_chunks_by_section_header(header)`: Filter by section
- `get_duplicate_chunks(min_seen_count)`: Find repeated chunks across versions
- `clear_chunks_by_source_url(url)`: Delete chunks for re-ingestion
- `get_stats()`: Database statistics

**File Location**: `data/processed/app.db`

**Usage Example**:
```python
from ingestion.metadata_store import ChunkMetadataStore

store = ChunkMetadataStore(db_path="data/processed/app.db")

# Retrieve by various filters
chunks_by_source = store.get_chunks_by_source_url("https://groww.in/...")
chunks_by_scheme = store.get_chunks_by_scheme_name("HDFC Equity Fund")
holdings_chunks = store.get_chunks_by_section_header("Holdings")

# Get statistics
stats = store.get_stats()
print(f"Total chunks: {stats['total_chunks']}")
print(f"Duplicate records: {stats['duplicate_records']}")
```

---

### 5. **Retrieval Module** (`app/retrieval.py`)

**Purpose**: Semantic search with compliance filtering and context assembly.

**Classes**:

#### `Retriever`
Orchestrates semantic search with metadata filtering.

**Key Methods**:
- `retrieve(query, top_k, allowed_source_urls, allowed_section_headers)`:
  - Embeds query
  - Searches FAISS index
  - Applies source URL and section header filters
  - Returns ranked `RetrievalResult` objects

- `retrieve_by_section(section_header, allowed_source_urls)`:
  - Non-semantic section-based retrieval
  - Useful for fetching holdings, expense ratios, etc.

- `retrieve_by_source_url(source_url)`:
  - Get all chunks from specific source

- `retrieve_by_scheme_name(scheme_name, allowed_source_urls)`:
  - Get all chunks for a fund scheme

- `batch_retrieve(queries, top_k, allowed_source_urls)`:
  - Batch process multiple queries

**`RetrievalResult` Dataclass**:
```python
chunk: Chunk              # Full chunk with metadata and content
similarity_distance: float
rank: int
relevance_score: float   # Computed from distance (0-1)
```

#### `ContextAssembler`
Enforces one-citation policy and structures context for generation.

**Key Methods**:
- `assemble_single_source_context(results)`:
  - Enforces **one-source constraint**
  - Selects source with highest cumulative relevance
  - Returns assembled context and selected source URL
  - Guaranteed compliance for Phase 7 validator

- `assemble_multi_section_context(results, max_sections)`:
  - Groups chunks by section headers
  - Useful for complex queries requiring multiple sections
  - Maintains traceability per section

**Usage Example**:
```python
from app.retrieval import Retriever, ContextAssembler

retriever = Retriever(embeddings, faiss_index, metadata_store)

# Retrieve
results = retriever.retrieve(
    "What is the expense ratio?",
    top_k=10,
    allowed_source_urls=APPROVED_SOURCE_URLS
)

# Assemble context (one-source enforced)
context, selected_source = ContextAssembler.assemble_single_source_context(results)
print(f"Using source: {selected_source}")
print(f"Context:\n{context}")
```

---

### 6. **Index Builder** (`ingestion/index_builder.py`)

**Purpose**: Orchestrate full index build/rebuild from processed documents.

**Key Methods**:
- `build_index(force_rebuild=False)`:
  - Loads all processed JSON documents from `data/processed/documents/`
  - Chunks each document
  - Generates embeddings (batched for efficiency)
  - Adds to FAISS index and SQLite store
  - Returns comprehensive build report

- `update_source(source_url)`:
  - Re-ingest single source (for updates)
  - Clears old chunks for that source
  - Rebuilds index entries
  - Returns update report

- `get_index_status()`:
  - Current index and store statistics

**Build Report**:
```python
{
    "status": "success|error",
    "total_documents": int,
    "total_chunks": int,
    "total_embeddings": int,
    "documents_processed": [{"document": str, "chunks": int}, ...],
    "errors": [{"document": str, "error": str}, ...],
    "index_stats": {...},
    "store_stats": {...}
}
```

---

## Scripts and Commands

### 1. **Build Index** (`scripts/build_index.py`)

Build or rebuild the complete vector index.

```bash
# Incremental build (adds new documents, preserves existing)
python -m scripts.build_index

# Full rebuild (deletes and recreates index)
python -m scripts.build_index --force

# Check index status
python -m scripts.build_index --status

# Override embedding provider
python -m scripts.build_index --provider local
python -m scripts.build_index --provider openai --api-key sk-...
```

**Output**:
```
=== Building Index ===
Documents processed: 7
Total chunks created: 1234
Total embeddings: 1234

=== Final Index Stats ===
Total vectors in index: 1234
Embedding dimension: 1536

=== Database Stats ===
Total chunks in DB: 1234
Sources: 7
Schemes: 7
Sections: 45
Duplicate records: 23
```

### 2. **Update Source** (`scripts/update_source.py`)

Update index for a specific source (useful for weekly refreshes).

```bash
python -m scripts.update_source "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth"
```

---

## Configuration Requirements

Add to `.env`:
```
# Embeddings
EMBEDDING_PROVIDER=openai  # or 'local'
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=sk-...  # Only if using OpenAI

# Paths
VECTOR_DB_PATH=./data/faiss/index.bin
SQLITE_PATH=./data/processed/app.db
```

---

## Testing

Run Phase 3 smoke tests:

```bash
pytest tests/test_phase3.py -v
```

**Test Coverage**:
- ✅ Token counting (GPT-3.5 encoding)
- ✅ Chunking (section awareness, line safety, metadata)
- ✅ Embeddings (single and batch)
- ✅ FAISS index (add, search, batch search, stats)
- ✅ Metadata store (CRUD, filtering, dedup tracking)
- ✅ Retrieval (semantic search with filtering)

---

## Deliverables Checklist

✅ **Working vector index**
- FAISS index with 1536-dim embeddings (or configurable)
- Bidirectional ID mapping
- Persistent storage

✅ **Metadata tables for retrieval filters**
- SQLite schema with indexes on source_url, scheme_name, section_header, content_hash
- Chunk deduplication tracking
- Full traceability

✅ **Section-aware chunk traceability**
- Every chunk has: chunk_id, source_url, section_header, start_line, end_line
- Enables "Show me where this came from" capability
- Line-range verification for source claims

✅ **Index integrity checks**
- Stats queries available: total vectors, total chunks, sources, schemes, sections
- Deduplication records tracked
- End-to-end from chunk ID → FAISS ID → metadata

✅ **Rebuild and update scripts**
- Full index build from processed documents
- Incremental source updates
- Status and statistics reporting

---

## Exit Criteria - Achieved ✓

✅ Retrieval returns relevant chunks for factual queries
- Semantic search with FAISS
- Metadata filtering enforced
- Results ranked by relevance

✅ Chunk-to-source mapping is traceable end-to-end
- FAISS ID → Chunk ID → SQLite record → source_url, section_header, line_range
- Every query result includes full provenance

✅ Section header and line-range traceability available
- `chunk.metadata.section_header` identifies section
- `chunk.metadata.start_line`, `end_line` enable source verification
- Section-based retrieval available for structured data

✅ Index integrity checks pass
- Database schema verified
- FAISS index persists and loads correctly
- ID mappings bidirectional and consistent
- Smoke tests verify core functionality

---

## Integration Points

**Phase 3 → Phase 4 (Query Routing & Refusal)**:
- Retriever available as dependency for intent router
- Factual queries → retriever.retrieve()
- Advisory queries → refusal response

**Phase 3 → Phase 5 (Context Assembly)**:
- ContextAssembler.assemble_single_source_context() enforces one-citation
- Ready for Phase 7 validator

**Phase 3 → Phase 6 (Groq Generation)**:
- Retrieved context passed to Groq
- One-source policy already enforced in Phase 5

---

## Known Limitations & Future Work

1. **Current FAISS config**: IVFFlat with 10 lists (suitable for ~10K chunks)
   - May need tuning for larger corpus
   - HNSW index option for even better scaling

2. **Embedding provider locked at build time**:
   - Can't switch providers without rebuild
   - Future: caching layer to support provider swapping

3. **Deduplication tracking**: Identifies duplicate chunks but doesn't auto-remove
   - Manual cleanup available via CLI
   - Could auto-prune in Phase 3 v2

4. **Line-range traceability**: Best-effort, depends on normalization quality
   - May have minor inaccuracies for heavily formatted sections
   - Good enough for compliance audit purposes
