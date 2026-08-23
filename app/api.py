"""FastAPI entrypoint for the Mutual Fund FAQ Assistant."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.compliance import ComplianceGenerationLoop
from app.config import ConfigError, Settings, get_settings
from app.constants import APPROVED_SOURCE_URLS, DEFAULT_REFUSAL_LINK
from app.generator import GenerationRequest, GroqAnswerGenerator, GroqClient
from app.refusal import RefusalComposer
from app.retrieval import Retriever
from app.retrieval_phase5 import EnhancedContextAssembler, RetrievalReranker
from app.router import IntentRouter, QueryIntent
from ingestion.embeddings import get_embeddings_client
from ingestion.index import ChromaIndexBuilder
from ingestion.metadata_store import ChunkMetadataStore

app = FastAPI(title="Mutual Fund FAQ Assistant", version="0.1.0")
_service: Optional["AssistantService"] = None
_ui_path = Path(__file__).resolve().parent.parent / "ui"
app.mount("/assets", StaticFiles(directory=str(_ui_path)), name="assets")


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(_ui_path / "index.html")


class AskRequest(BaseModel):
    """Request payload for the FAQ flow."""

    query: str = Field(..., min_length=1, max_length=500)


class AskResponse(BaseModel):
    """Stable response contract for UI and future integrations."""

    answer: str
    citation: str
    last_updated_from_sources: str
    route: str


class AssistantService:
    """Orchestrate routing, retrieval, generation, and response shaping."""

    def __init__(
        self,
        retriever: Retriever,
        reranker: RetrievalReranker,
        assembler: EnhancedContextAssembler,
        generator: ComplianceGenerationLoop,
        router: Optional[IntentRouter] = None,
        refusal_composer: Optional[RefusalComposer] = None,
    ) -> None:
        self.retriever = retriever
        self.reranker = reranker
        self.assembler = assembler
        self.generator = generator
        self.router = router or IntentRouter()
        self.refusal_composer = refusal_composer or RefusalComposer()

    def ask(self, query: str) -> AskResponse:
        query = query.strip()
        if not query:
            raise ValueError("query cannot be empty")

        should_refuse, intent = self.router.should_refuse(query)
        if should_refuse:
            return self._refusal_response(intent)

        results = self.retriever.retrieve(query, top_k=10)
        reranked = self.reranker.rerank(results)
        context, source_url, valid, _ = self.assembler.assemble_with_validation(reranked)
        if not valid:
            source_url = DEFAULT_REFUSAL_LINK
            context = ""

        updated = self._latest_crawl_date(reranked, source_url)
        answer = self.generator.generate(
            GenerationRequest(query, context, source_url, updated)
        )
        return AskResponse(
            answer=answer,
            citation=source_url,
            last_updated_from_sources=updated,
            route=QueryIntent.FACTUAL.value,
        )

    def source_status(self) -> list[dict[str, str]]:
        return [{"source_url": url, "status": "approved"} for url in APPROVED_SOURCE_URLS]

    def _refusal_response(self, intent: QueryIntent) -> AskResponse:
        citation = self.refusal_composer.default_link
        updated = date.today().isoformat()
        answer = self.refusal_composer.compose_refusal(intent)
        answer = f"{answer}\n\nLast updated from sources: {updated}"
        return AskResponse(
            answer=answer,
            citation=citation,
            last_updated_from_sources=updated,
            route=intent.value,
        )

    @staticmethod
    def _latest_crawl_date(results, source_url: str) -> str:
        dates = [
            result.chunk.metadata.crawled_at
            for result in results
            if result.chunk.metadata.source_url == source_url
            and result.chunk.metadata.crawled_at
        ]
        return max(dates) if dates else date.today().isoformat()


def build_service(settings: Settings) -> AssistantService:
    """Build production dependencies after startup configuration is valid."""
    vector_path = Path(settings.vector_db_path)
    sqlite_path = Path(settings.sqlite_path)
    import chromadb

    collection = chromadb.PersistentClient(path=str(vector_path)).get_collection(
        ChromaIndexBuilder.collection_name
    )
    sample = collection.get(limit=1, include=["embeddings"])
    embeddings_sample = sample.get("embeddings")
    if embeddings_sample is None or len(embeddings_sample) == 0:
        raise RuntimeError("vector collection contains no embeddings")

    embeddings = get_embeddings_client(
        provider=settings.embedding_provider,
        api_key=os.getenv("EMBEDDING_API_KEY"),
        model=settings.embedding_model,
    )
    index = ChromaIndexBuilder(len(sample["embeddings"][0]), vector_path)
    store = ChunkMetadataStore(sqlite_path)
    groq = GroqClient(settings.groq_api_key, settings.groq_model)
    return AssistantService(
        retriever=Retriever(embeddings, index, store),
        reranker=RetrievalReranker(store),
        assembler=EnhancedContextAssembler(),
        generator=ComplianceGenerationLoop(GroqAnswerGenerator(groq)),
    )


def get_service() -> AssistantService:
    global _service
    if _service is None:
        _service = build_service(get_settings(validate=True))
    return _service


@app.on_event("startup")
def validate_startup_configuration() -> None:
    # Fail fast during startup if policy-critical configuration is invalid.
    get_settings(validate=True)


@app.get("/health")
def health_check() -> dict[str, str]:
    settings = get_settings(validate=True)
    return {
        "status": "ok",
        "environment": settings.app_env,
        "provider": settings.llm_provider,
    }


@app.get("/sources")
def source_status() -> dict[str, list[dict[str, str]]]:
    return {"sources": get_service().source_status()}


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    try:
        return get_service().ask(request.query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ConfigError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="Assistant dependencies are unavailable") from exc


@app.exception_handler(ConfigError)
async def config_error_handler(_, exc: ConfigError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})
