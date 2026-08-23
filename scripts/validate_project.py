"""Validate the Mutual Fund FAQ Assistant through Phase 7."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

from app.compliance import ComplianceGenerationLoop, ComplianceValidator
from app.constants import APPROVED_SOURCE_URLS
from app.generator import GenerationRequest, GroqAnswerGenerator, GroqClient
from app.refusal import RefusalComposer
from app.router import IntentRouter, QueryIntent
from ingestion.seed_urls import get_seed_urls, validate_source_inventory

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUERY = "What is the expense ratio of HDFC Equity Fund?"


class FakeCompletions:
    def create(self, **kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="The expense ratio is stated in the source context.")
                )
            ]
        )


def check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise RuntimeError(f"{name} failed{': ' + detail if detail else ''}")
    print(f"[PASS] {name}")


def validate_policy_and_routing() -> None:
    validate_source_inventory()
    check("approved source inventory", set(get_seed_urls()) == set(APPROVED_SOURCE_URLS))
    check("approved URL count", len(APPROVED_SOURCE_URLS) == 7)

    router = IntentRouter()
    factual = router.classify(DEFAULT_QUERY)
    advisory = router.classify("Should I invest in this fund?")
    check("factual routing", factual.intent == QueryIntent.FACTUAL)
    check("advisory routing", advisory.intent == QueryIntent.ADVISORY)

    refusal = RefusalComposer().compose_refusal(QueryIntent.ADVISORY)
    check("refusal has one approved URL", refusal.count("https://") == 1)


def validate_index() -> None:
    vector_path = Path(os.getenv("VECTOR_DB_PATH", "./data/chroma"))
    sqlite_path = Path(os.getenv("SQLITE_PATH", "./data/processed/app.db"))
    check("vector store exists", vector_path.exists(), str(vector_path))
    check("metadata store exists", sqlite_path.exists(), str(sqlite_path))

    import chromadb

    client = chromadb.PersistentClient(path=str(vector_path))
    collection = client.get_collection("mutual_fund_chunks")
    check("indexed chunks available", collection.count() > 0)


def validate_retrieval(query: str) -> None:
    from app.retrieval import Retriever
    from ingestion.embeddings import get_embeddings_client
    from ingestion.index import ChromaIndexBuilder
    from ingestion.metadata_store import ChunkMetadataStore

    vector_path = Path(os.getenv("VECTOR_DB_PATH", "./data/chroma"))
    sqlite_path = Path(os.getenv("SQLITE_PATH", "./data/processed/app.db"))
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "local")
    embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    import chromadb

    collection = chromadb.PersistentClient(path=str(vector_path)).get_collection(
        "mutual_fund_chunks"
    )
    sample = collection.get(limit=1, include=["embeddings"])
    dimension = len(sample["embeddings"][0])
    retriever = Retriever(
        embeddings_client=get_embeddings_client(embedding_provider, embedding_model),
        vector_index=ChromaIndexBuilder(dimension, vector_path),
        metadata_store=ChunkMetadataStore(sqlite_path),
    )
    results = retriever.retrieve(query, top_k=3)
    check("retrieval smoke test", bool(results))
    check(
        "retrieval allowlist enforcement",
        all(result.chunk.metadata.source_url in APPROVED_SOURCE_URLS for result in results),
    )


def validate_generation() -> None:
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    generator = GroqAnswerGenerator(GroqClient("offline-test-key", "offline-test-model", fake_client))
    request = GenerationRequest(
        DEFAULT_QUERY,
        "[Expense Ratio]\nThe expense ratio is stated in the source context.",
        APPROVED_SOURCE_URLS[1],
        "2026-08-23",
    )
    response = generator.generate(request)
    result = ComplianceValidator().validate(response, request.source_url)
    check("generation smoke test", response.startswith("The expense ratio"))
    check("generated response compliance", result.is_valid, "; ".join(result.reasons))

    empty_request = GenerationRequest("Question", "", APPROVED_SOURCE_URLS[0], "2026-08-23")
    fallback = ComplianceGenerationLoop(generator).generate(empty_request)
    check("unknown-answer fallback", "not available" in fallback.lower())


def run_tests() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        check=False,
    )
    check("pytest regression suite", completed.returncode == 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Query used for retrieval smoke testing.")
    parser.add_argument(
        "--skip-retrieval",
        action="store_true",
        help="Skip loading the embedding model and running semantic retrieval.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip the full pytest regression suite.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    load_dotenv(ROOT / ".env")
    try:
        validate_policy_and_routing()
        validate_index()
        if not args.skip_retrieval:
            validate_retrieval(args.query)
        else:
            print("[SKIP] retrieval smoke test")
        validate_generation()
        if not args.skip_tests:
            run_tests()
        else:
            print("[SKIP] pytest regression suite")
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print("Validation completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())