"""Pinecone-backed vector store wrapper.

Hides the Pinecone SDK behind a small interface so the retriever and ingester
can be unit-tested without a live Pinecone account. When
``settings.pinecone_api_key`` is empty the store is "not configured" and all
operations are no-ops; the rest of the system gracefully falls back to
operating without retrieval.
"""

from typing import Any, Dict, Iterable, List, Optional

import structlog

from src.config import get_settings

logger = structlog.get_logger()


class PineconeVectorStore:
    """Minimal Pinecone client used by the retriever and ingester."""

    def __init__(self) -> None:
        settings = get_settings()
        self._index_name = settings.pinecone_index_name
        self._index: Optional[Any] = None

        if not settings.pinecone_api_key or not self._index_name:
            logger.info(
                "rag.vector_store disabled",
                reason="pinecone_api_key or pinecone_index_name not configured",
            )
            return

        try:
            from pinecone import Pinecone

            self._client = Pinecone(api_key=settings.pinecone_api_key)
            self._index = self._client.Index(self._index_name)
        except Exception as e:  # pragma: no cover - exercised at runtime only
            logger.warning("rag.vector_store init failed", error=str(e))
            self._index = None

    @property
    def is_configured(self) -> bool:
        """True iff this store can read from / write to Pinecone."""
        return self._index is not None

    def upsert(self, items: Iterable[Dict[str, Any]]) -> int:
        """Upsert vectors. Each item is ``{id, values, metadata}``.

        Returns the number of items submitted (zero when not configured).
        """
        if not self.is_configured:
            return 0
        items_list = list(items)
        if not items_list:
            return 0
        self._index.upsert(vectors=items_list)
        return len(items_list)

    def query(self, vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Query for top-k nearest neighbours.

        Returns a list of dicts with ``id``, ``score``, and ``metadata`` keys.
        Pinecone responses can be either object-style or dict-style depending
        on SDK version; this method normalises to dicts so the retriever has
        a stable shape to work with.
        """
        if not self.is_configured:
            return []
        result = self._index.query(
            vector=vector, top_k=top_k, include_metadata=True
        )
        matches = getattr(result, "matches", None)
        if matches is None:
            matches = result.get("matches", []) if isinstance(result, dict) else []

        out: List[Dict[str, Any]] = []
        for m in matches:
            out.append(
                {
                    "id": getattr(m, "id", None) or m.get("id"),
                    "score": getattr(m, "score", None) or m.get("score"),
                    "metadata": getattr(m, "metadata", None) or m.get("metadata", {}),
                }
            )
        return out
