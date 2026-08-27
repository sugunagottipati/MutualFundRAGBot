"""Phase 10 tests: evaluation dataset and scheduled refresh behavior."""

from __future__ import annotations

import pytest

from ingestion.pipeline import PipelineResult
from scripts import evaluate_phase10, refresh_sources


def test_evaluation_dataset_has_required_prompt_mix():
    cases = evaluate_phase10.load_cases(evaluate_phase10.DEFAULT_DATASET)

    assert len(cases) == 79
    assert sum(case["kind"] == "factual" for case in cases) == 54
    assert sum(case["kind"] == "advisory" for case in cases) == 15
    assert sum(case["kind"] == "boundary" for case in cases) == 10


def test_offline_evaluation_meets_policy_baseline():
    report = evaluate_phase10.evaluate(
        evaluate_phase10.load_cases(evaluate_phase10.DEFAULT_DATASET)
    )

    assert report["route_accuracy"] == 1.0
    assert report["refusal_precision"] == 1.0
    assert report["single_citation_adherence"] == 1.0
    assert report["citation_relevance"] is None


def test_refresh_fails_when_any_approved_source_fails(monkeypatch):
    class PassingBuilder:
        def __init__(self, **_):
            pass

        def build_index(self):
            return {"status": "success", "errors": []}

    monkeypatch.setattr(
        refresh_sources,
        "run_ingestion",
        lambda **_: PipelineResult(total_sources=7, processed=6, deduplicated=0, failed=1),
    )
    monkeypatch.setattr(refresh_sources, "IndexBuilder", PassingBuilder)

    report = refresh_sources.refresh_sources()

    assert report["warnings"] == [
        "Ingestion skipped 1 of 7 approved sources after retry; "
        "existing processed corpus was retained for indexing."
    ]


def test_refresh_fails_when_all_sources_fail_without_existing_corpus(monkeypatch, tmp_path):
    settings = refresh_sources.get_settings(validate=False)
    settings = type(settings)(
        **{
            **settings.__dict__,
            "sqlite_path": str(tmp_path / "processed" / "app.db"),
            "vector_db_path": str(tmp_path / "chroma"),
        }
    )
    monkeypatch.setattr(refresh_sources, "get_settings", lambda validate=False: settings)
    monkeypatch.setattr(
        refresh_sources,
        "run_ingestion",
        lambda **_: PipelineResult(total_sources=7, processed=0, deduplicated=0, failed=7),
    )

    with pytest.raises(RuntimeError, match="no existing corpus is available"):
        refresh_sources.refresh_sources()


def test_refresh_fails_when_index_reports_errors(monkeypatch):
    monkeypatch.setattr(
        refresh_sources,
        "run_ingestion",
        lambda **_: PipelineResult(total_sources=7, processed=7, deduplicated=0, failed=0),
    )

    class FailingBuilder:
        def __init__(self, **_):
            pass

        def build_index(self):
            return {"status": "success", "errors": [{"error": "index write failed"}]}

    monkeypatch.setattr(refresh_sources, "IndexBuilder", FailingBuilder)

    with pytest.raises(RuntimeError, match="Index refresh failed"):
        refresh_sources.refresh_sources()