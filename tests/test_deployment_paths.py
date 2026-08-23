"""Regression tests for persistent deployment storage paths."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

from ingestion.index_builder import IndexBuilder


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
    assert "git add data/processed/documents/ data/processed/app.db data/chroma/" in workflow
    assert 'git commit -m "chore(ingest): daily corpus refresh' in workflow