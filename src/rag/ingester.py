"""Walk a GitHub repo, chunk its code, embed, and upsert to Pinecone.

The ingester is run once per repository (or on-demand to refresh the index);
it does *not* run as part of the per-PR review pipeline. The PR review
pipeline only *queries* the index that this ingester has populated.
"""

from typing import Any, Dict, List, Optional

import structlog

from src.config import get_settings
from src.github.client import GitHubClient
from src.rag.chunker import CodeChunk, chunk_file, is_indexable_file
from src.rag.embedder import GeminiEmbedder
from src.rag.vector_store import PineconeVectorStore

logger = structlog.get_logger()


class RepoIngester:
    """One-shot ingestion of a repository's code into the vector store."""

    def __init__(
        self,
        github_client: Optional[GitHubClient] = None,
        embedder: Optional[GeminiEmbedder] = None,
        store: Optional[PineconeVectorStore] = None,
    ) -> None:
        self.github = github_client or GitHubClient()
        self.embedder = embedder or GeminiEmbedder()
        self.store = store or PineconeVectorStore()

    def ingest(self, owner: str, repo: str, installation_id: int) -> int:
        """Ingest a repo and return the number of chunks indexed."""
        if not self.store.is_configured:
            logger.info("rag.ingest skipped", reason="vector store not configured")
            return 0

        chunks = self._collect_chunks(owner, repo, installation_id)
        if not chunks:
            logger.info("rag.ingest no chunks", repo=f"{owner}/{repo}")
            return 0

        settings = get_settings()
        items: List[Dict[str, Any]] = []
        # Embed and upsert in batches to bound peak memory and request size.
        batch_size = max(1, settings.rag_ingest_batch_size)
        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[batch_start : batch_start + batch_size]
            texts = [c["content"] for c in batch]
            vectors = self.embedder.embed_documents(texts)
            for chunk, vector in zip(batch, vectors):
                items.append(
                    {
                        "id": f"{owner}/{repo}::{chunk['id']}",
                        "values": vector,
                        "metadata": {
                            "owner": owner,
                            "repo": repo,
                            "file_path": chunk["file_path"],
                            "start_line": chunk["start_line"],
                            "end_line": chunk["end_line"],
                            "content": chunk["content"],
                        },
                    }
                )
            # Upsert per batch so a partial failure still indexes earlier batches.
            self.store.upsert(items[batch_start : batch_start + len(batch)])

        logger.info(
            "rag.ingest complete",
            repo=f"{owner}/{repo}",
            indexed=len(items),
        )
        return len(items)

    def _collect_chunks(
        self, owner: str, repo: str, installation_id: int
    ) -> List[CodeChunk]:
        """Walk the repo and return all chunks for indexable code files."""
        settings = get_settings()
        gh = self.github._get_github_for_installation(installation_id)
        repo_obj = gh.get_repo(f"{owner}/{repo}")

        chunks: List[CodeChunk] = []
        contents = repo_obj.get_contents("")
        while contents:
            entry = contents.pop(0)
            if entry.type == "dir":
                contents.extend(repo_obj.get_contents(entry.path))
                continue
            if not is_indexable_file(entry.path):
                continue
            try:
                text = entry.decoded_content.decode("utf-8")
            except Exception as e:
                logger.warning("rag.ingest decode failed", path=entry.path, error=str(e))
                continue
            chunks.extend(
                chunk_file(
                    entry.path,
                    text,
                    chunk_size=settings.rag_chunk_size,
                    overlap=settings.rag_chunk_overlap,
                )
            )
        return chunks
