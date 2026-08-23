"""Evaluate Phase 10 routing, refusal, and optional live-answer quality."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.constants import APPROVED_SOURCE_URLS
from app.refusal import PolicyEnforcer, RefusalComposer
from app.router import IntentRouter, QueryIntent

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "tests" / "data" / "phase10_evaluation.json"


def load_cases(path: Path) -> list[dict[str, Any]]:
    """Load and validate the fixed Phase 10 evaluation dataset."""
    cases = json.loads(path.read_text(encoding="utf-8"))
    kinds = {"factual": 0, "advisory": 0, "boundary": 0}
    for case in cases:
        kind = case.get("kind")
        if kind not in kinds or not case.get("query") or not case.get("expected_route"):
            raise ValueError("Each evaluation case needs kind, query, and expected_route")
        kinds[kind] += 1
    if kinds != {"factual": 30, "advisory": 15, "boundary": 10}:
        raise ValueError(f"Unexpected evaluation dataset composition: {kinds}")
    return cases


def evaluate(cases: list[dict[str, Any]], live: bool = False) -> dict[str, Any]:
    """Measure deterministic policy routing and optional live factual answers."""
    router = IntentRouter()
    composer = RefusalComposer()
    enforcer = PolicyEnforcer()
    route_matches = 0
    refusal_checks = 0
    refusal_passes = 0
    citation_checks = 0
    citation_passes = 0
    answer_checks = 0
    answer_passes = 0
    service = None

    if live:
        from app.api import get_service

        service = get_service()

    for case in cases:
        expected_route = QueryIntent(case["expected_route"])
        result = router.classify(case["query"])
        route_matches += result.intent == expected_route
        should_refuse, _ = router.should_refuse(case["query"])

        if expected_route != QueryIntent.FACTUAL:
            refusal_checks += 1
            response = composer.compose_refusal(expected_route)
            urls = enforcer.extract_urls(response)
            policy_valid, _ = enforcer.validate_response(response, urls)
            refusal_passes += should_refuse and policy_valid and len(urls) == 1
            continue

        if live and service is not None:
            response = service.ask(case["query"])
            citation_checks += 1
            citation_passes += response.citation in case["expected_sources"]
            answer_checks += 1
            expected_terms = case.get("expected_terms", [])
            answer = response.answer.lower()
            answer_passes += all(term.lower() in answer for term in expected_terms)

    return {
        "total_cases": len(cases),
        "route_accuracy": route_matches / len(cases),
        "refusal_precision": refusal_passes / refusal_checks if refusal_checks else 1.0,
        "single_citation_adherence": refusal_passes / refusal_checks if refusal_checks else 1.0,
        "citation_relevance": citation_passes / citation_checks if citation_checks else None,
        "factual_term_match": answer_passes / answer_checks if answer_checks else None,
        "live": live,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--live", action="store_true", help="Call the configured assistant for factual cases.")
    parser.add_argument("--output", type=Path, help="Write the JSON report to this path.")
    args = parser.parse_args()

    try:
        report = evaluate(load_cases(args.dataset), live=args.live)
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1

    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["route_accuracy"] == 1.0 and report["refusal_precision"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())