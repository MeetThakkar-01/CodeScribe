"""Retrieve relevant code chunks for a query string.

The retriever is the thing the review graph calls: give it the diff (or any
text), get back the top-k most semantically similar chunks the ingester has
previously indexed for this repo.
"""

from typing import List, Optional, TypedDict

import structlog

from src.config import get_settings
from src.rag.embedder import GeminiEmbedder
from src.rag.vector_store import PineconeVectorStore

logger = structlog.get_logger()


class RetrievedChunk(TypedDict):
    """A chunk returned from semantic search, with its provenance."""

    file_path: str
    start_line: int
    end_line: int
    content: str
    score: float


class CodeRetriever:
    """Embed a query, search the vector store, return ranked code chunks."""

    def __init__(
        self,
        embedder: Optional[GeminiEmbedder] = None,
        store: Optional[PineconeVectorStore] = None,
    ) -> None:
        self.embedder = embedder or GeminiEmbedder()
        self.store = store or PineconeVectorStore()

    @property
    def is_active(self) -> bool:
        """True when retrieval is wired up end-to-end."""
        return self.store.is_configured

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[RetrievedChunk]:
        """Return the top-k chunks most similar to ``query``.

        Empty list when the store is not configured, when the query is empty,
        or when no chunks have been indexed yet. Errors are logged and
        swallowed: a failed retrieval should never block a code review.
        """
        if not self.is_active or not query:
            return []
        try:
            k = top_k if top_k is not None else get_settings().rag_top_k
            vector = self.embedder.embed_query(query)
            matches = self.store.query(vector, top_k=k)
        except Exception as e:
            logger.warning("rag.retrieve failed", error=str(e))
            return []

        results: List[RetrievedChunk] = []
        for m in matches:
            metadata = m.get("metadata") or {}
            results.append(
                RetrievedChunk(
                    file_path=metadata.get("file_path", ""),
                    start_line=int(metadata.get("start_line", 0) or 0),
                    end_line=int(metadata.get("end_line", 0) or 0),
                    content=metadata.get("content", ""),
                    score=float(m.get("score") or 0.0),
                )
            )
        return results
