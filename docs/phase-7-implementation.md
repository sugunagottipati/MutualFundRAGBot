# Phase 7: Corpus and Deployment Verification

## Status

Implemented on 2026-08-24.

## Verification Added

- `scripts/validate_project.py` now validates processed-document coverage against `document_manifest.jsonl`.
- Every manifest entry must reference an approved source, an existing processed JSON document, and an existing raw source file.
- Processed metadata must match the manifest source URL and content hash.
- Conflict markers are rejected.
- The corpus must cover all seven approved sources.
- Duplicate snapshots are allowed when they are tracked in the manifest. The latest crawl is selected by the manifest and ingestion metadata; older snapshots remain traceable for auditability.
- `ingestion/index_builder.py` persists `fact_type` in rebuilt vector metadata.
- Deployment smoke tests cover `/health`, `/sources`, and `/ask` without network or provider initialization.

## Commands

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/validate_project.py --skip-retrieval --skip-tests
```

The full test suite verifies local behavior. The validation script additionally checks the live corpus and persistent index when retrieval validation is enabled.

## Known Limitations

- The existing persistent Chroma index must be rebuilt to populate `fact_type` metadata for already-indexed chunks.
- Live deployment verification requires valid environment variables and a reachable persistent index.
- The validator checks endpoint contracts offline; it does not replace a deployed-network smoke test.
