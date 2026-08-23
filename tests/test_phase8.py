"""Phase 8 tests: API contract and service orchestration."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api import AskRequest, AssistantService, ask, source_status
from app.constants import APPROVED_SOURCE_URLS
from app.router import QueryIntent


class FakeRouter:
    def __init__(self, should_refuse: bool = False):
        self.should_refuse_value = should_refuse

    def should_refuse(self, query):
        intent = QueryIntent.ADVISORY if self.should_refuse_value else QueryIntent.FACTUAL
        return self.should_refuse_value, intent


class FakeRetriever:
    def __init__(self):
        self.queries = []

    def retrieve(self, query, top_k):
        self.queries.append((query, top_k))
        return [
            SimpleNamespace(
                chunk=SimpleNamespace(
                    metadata=SimpleNamespace(
                        source_url=APPROVED_SOURCE_URLS[0], crawled_at="2026-08-23"
                    )
                )
            )
        ]


class FakeReranker:
    def rerank(self, results):
        return results


class FakeAssembler:
    def assemble_with_validation(self, results):
        return "Expense ratio: 0.50%", APPROVED_SOURCE_URLS[0], True, "OK"


class FakeGenerator:
    def __init__(self):
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return f"The expense ratio is 0.50%. Source: {request.source_url}"


def service(router=None):
    return AssistantService(
        FakeRetriever(),
        FakeReranker(),
        FakeAssembler(),
        FakeGenerator(),
        router=router or FakeRouter(),
    )


def test_factual_ask_returns_structured_contract():
    response = service().ask("What is the expense ratio?")

    assert response.route == "factual"
    assert response.citation == APPROVED_SOURCE_URLS[0]
    assert response.last_updated_from_sources == "2026-08-23"
    assert response.answer.startswith("The expense ratio")


def test_factual_ask_normalizes_timestamp_footer():
    assistant = service()
    assistant.retriever.retrieve = lambda query, top_k: [
        SimpleNamespace(
            chunk=SimpleNamespace(
                metadata=SimpleNamespace(
                    source_url=APPROVED_SOURCE_URLS[0],
                    crawled_at="2026-08-23T12:58:51+00:00",
                )
            )
        )
    ]

    response = assistant.ask("What is the expense ratio?")

    assert response.last_updated_from_sources == "2026-08-23"


def test_advisory_ask_does_not_retrieve():
    assistant = service(FakeRouter(should_refuse=True))

    response = assistant.ask("Should I invest in this fund?")

    assert response.route == "advisory"
    assert response.citation in APPROVED_SOURCE_URLS
    assert response.answer.count("https://") == 1
    assert "cannot provide investment advice" in response.answer.lower()


def test_empty_query_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        service().ask("   ")


def test_source_status_exposes_all_approved_sources():
    from app import api

    original = api._service
    api._service = service()
    try:
        payload = source_status()
    finally:
        api._service = original

    assert len(payload["sources"]) == 7
    assert {item["source_url"] for item in payload["sources"]} == set(APPROVED_SOURCE_URLS)


def test_ask_route_uses_request_schema():
    from app import api

    original = api._service
    api._service = service()
    try:
        response = ask(AskRequest(query="What is the expense ratio?"))
    finally:
        api._service = original

    assert response.route == "factual"