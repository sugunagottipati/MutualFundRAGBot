"""Regression tests for persistent deployment storage paths."""

from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import AskResponse, app
from app.constants import APPROVED_SOURCE_URLS
from ingestion.index_builder import IndexBuilder
from scripts.validate_project import validate_corpus


def test_index_builder_derives_documents_directory_from_sqlite_path(monkeypatch):
    class FakeEmbeddings:
        embedding_dimension = 384

    monkeypatch.setattr("ingestion.index_builder.get_embeddings_client", lambda **_: FakeEmbeddings())
    monkeypatch.setattr("ingestion.index_builder.ChromaIndexBuilder", lambda **_: object())
    monkeypatch.setattr("ingestion.index_builder.ChunkMetadataStore", lambda **_: object())

    settings = SimpleNamespace(
        embedding_provider="local",
        embedding_model="all-MiniLM-L6-v2",
        vector_db_path="/data/chroma",
        sqlite_path="/data/processed/app.db",
    )

    builder = IndexBuilder(settings=settings)

    assert builder.processed_dir.as_posix() == "/data/processed"
    assert builder.documents_dir.as_posix() == "/data/processed/documents"


def test_daily_workflow_promotes_validated_data_to_git():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "daily-ingestion.yml"
    ).read_text(encoding="utf-8")

    assert "contents: write" in workflow
    assert "Validate refreshed corpus" in workflow
    assert "Commit promoted corpus and index" in workflow
    assert "data/processed/documents/" in workflow
    assert "data/processed/document_manifest.jsonl" in workflow
    assert "data/processed/ingestion_status.jsonl" in workflow
    assert "data/processed/source_health.jsonl" in workflow
    assert "data/processed/app.db" in workflow
    assert "data/chroma/" in workflow
    assert 'git commit -m "chore(ingest): daily corpus refresh' in workflow


def test_validate_corpus_accepts_current_processed_corpus():
    validate_corpus(check_raw_files=False)


def test_validate_corpus_can_skip_untracked_raw_files(tmp_path):
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir(parents=True)
    manifest_rows = []
    for index, source in enumerate(APPROVED_SOURCE_URLS):
        document = documents_dir / f"fund-{index}.json"
        document.write_text(
            json.dumps({
                "metadata": {
                    "source_url": source,
                    "content_hash": f"hash-{index}",
                    "raw_file_path": str(tmp_path / f"missing-{index}.html"),
                },
                "text": "facts",
            }),
            encoding="utf-8",
        )
        manifest_rows.append({
            "source_url": source,
            "content_hash": f"hash-{index}",
            "processed_path": str(document),
        })
    (tmp_path / "document_manifest.jsonl").write_text(
        "\n".join(json.dumps(row) for row in manifest_rows) + "\n",
        encoding="utf-8",
    )

    validate_corpus(tmp_path, check_raw_files=False)


def test_validate_corpus_rejects_manifest_document_mismatch(tmp_path):
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir(parents=True)
    document = documents_dir / "fund.json"
    raw = tmp_path / "fund.html"
    raw.write_text("<html></html>", encoding="utf-8")
    document.write_text(
        '{"metadata":{"source_url":"https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",'
        '"content_hash":"hash","raw_file_path":"' + str(raw) + '"},"text":"facts"}',
        encoding="utf-8",
    )
    (tmp_path / "document_manifest.jsonl").write_text(
        '{"source_url":"https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",'
        '"content_hash":"different","processed_path":"' + str(document) + '"}\n',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="Content hash mismatch"):
        validate_corpus(tmp_path)


def test_deployment_endpoints_smoke(monkeypatch):
    settings = SimpleNamespace(app_env="test", llm_provider="groq")
    response = AskResponse(
        answer="The expense ratio is 0.75%.",
        citation=APPROVED_SOURCE_URLS[0],
        last_updated_from_sources="2026-08-23",
        route="factual",
    )

    class FakeService:
        def ask(self, query):
            return response

        def source_status(self):
            return [
                {"source_url": url, "status": "approved", "last_indexed": "2026-08-25"}
                for url in APPROVED_SOURCE_URLS
            ]

    monkeypatch.setattr("app.api.get_settings", lambda validate=True: settings)
    monkeypatch.setattr("app.api.get_service", lambda: FakeService())

    client = TestClient(app)
    assert client.get("/health").json() == {
        "status": "ok",
        "environment": "test",
        "provider": "groq",
    }
    sources = client.get("/sources")
    assert sources.status_code == 200
    assert len(sources.json()["sources"]) == 7
    assert sources.json()["last_indexed"] == "2026-08-25"
    ask = client.post("/ask", json={"query": "What is the expense ratio?"})
    assert ask.status_code == 200
    assert ask.json()["route"] == "factual"
