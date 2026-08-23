"""Phase 3: Embeddings client for generating vector representations of chunks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


class EmbeddingsClient(ABC):
    """Abstract base for embeddings providers."""

    @abstractmethod
    def embed(self, text: str) -> np.ndarray:
        """Embed a single text string into vector space."""
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Embed multiple texts. May batch for efficiency."""
        pass

    @property
    @abstractmethod
    def embedding_dimension(self) -> int:
        """Dimension of embedding vectors."""
        pass


class OpenAIEmbeddings(EmbeddingsClient):
    """OpenAI text-embedding-3-small embeddings."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required: pip install openai")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self._dimension = 1536  # text-embedding-3-small dimension

    def embed(self, text: str) -> np.ndarray:
        """Embed single text."""
        response = self.client.embeddings.create(input=[text], model=self.model)
        return np.array(response.data[0].embedding, dtype=np.float32)

    def embed_batch(self, texts: list[str], batch_size: int = 100) -> list[np.ndarray]:
        """Embed texts in batches (OpenAI allows up to 2048 per request)."""
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self.client.embeddings.create(input=batch, model=self.model)
            # Sort by index to ensure order matches input
            response.data.sort(key=lambda x: x.index)
            embeddings.extend([np.array(item.embedding, dtype=np.float32) for item in response.data])
        return embeddings

    @property
    def embedding_dimension(self) -> int:
        return self._dimension


class LocalEmbeddings(EmbeddingsClient):
    """Fallback: local SentenceTransformer embeddings (for offline/cost-sensitive use)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers package required: pip install sentence-transformers"
            )

        self.model = SentenceTransformer(model_name)
        # Determine dimension by embedding a dummy text
        dummy_embedding = self.model.encode(["dummy"])[0]
        self._dimension = len(dummy_embedding)

    def embed(self, text: str) -> np.ndarray:
        """Embed single text."""
        return self.model.encode(text, convert_to_numpy=True).astype(np.float32)

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Embed texts in batch."""
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return [e.astype(np.float32) for e in embeddings]

    @property
    def embedding_dimension(self) -> int:
        return self._dimension


def get_embeddings_client(
    provider: str, api_key: Optional[str] = None, model: Optional[str] = None
) -> EmbeddingsClient:
    """
    Factory for embeddings clients.

    Args:
        provider: 'openai' or 'local'
        api_key: API key if needed
        model: Model name/ID

    Returns:
        EmbeddingsClient instance
    """
    if provider == "openai":
        if not api_key:
            raise ValueError("api_key required for OpenAI embeddings")
        model = model or "text-embedding-3-small"
        return OpenAIEmbeddings(api_key=api_key, model=model)
    elif provider == "local":
        model = model or "all-MiniLM-L6-v2"
        return LocalEmbeddings(model_name=model)
    else:
        raise ValueError(f"Unknown embeddings provider: {provider}")
