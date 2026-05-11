"""Embedding wrapper for the RAG layer.

Uses Gemini's ``gemini-embedding-001`` model through the native ``google.genai``
SDK so we can pin the output dimensionality to 768 (matches the Pinecone
index dimension). The model supports Matryoshka truncation to 768, 1536, or
3072 dimensions; we use 768.
"""

from typing import List

from google import genai
from google.genai import types

from src.config import get_settings


class GeminiEmbedder:
    """Thin wrapper around the Gemini embedding API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = genai.Client(api_key=settings.google_api_key)
        self._model = settings.embedding_model
        self._output_dim = 768  # must match PINECONE index dimension

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        result = self._client.models.embed_content(
            model=self._model,
            contents=texts,
            config=types.EmbedContentConfig(
                output_dimensionality=self._output_dim,
            ),
        )
        return [list(e.values) for e in result.embeddings]

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query string. Used at retrieval time."""
        return self._embed_batch([text])[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed many strings at once. Used at ingestion time."""
        if not texts:
            return []
        return self._embed_batch(texts)
