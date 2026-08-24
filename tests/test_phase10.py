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
    monkeypatch.setattr(
        refresh_sources,
        "run_ingestion",
        lambda **_: PipelineResult(total_sources=7, processed=6, deduplicated=0, failed=1),
    )

    with pytest.raises(RuntimeError, match="Ingestion failed"):
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