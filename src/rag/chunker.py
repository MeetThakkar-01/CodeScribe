"""Code chunking for RAG ingestion.

Sliding-window chunker over file content. Each chunk records its source file
path and the line range it covers, so retrieval results can be attributed back
to a specific location in the repository.
"""

from typing import List, TypedDict


class CodeChunk(TypedDict):
    """One chunk of source code, ready to be embedded and indexed."""

    id: str
    file_path: str
    start_line: int
    end_line: int
    content: str


def chunk_file(
    file_path: str,
    content: str,
    *,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> List[CodeChunk]:
    """Split a file's text into overlapping character-windowed chunks.

    The window slides forward by ``chunk_size - overlap`` so consecutive chunks
    share ``overlap`` characters, which keeps definitions and call sites that
    straddle a boundary recoverable by either chunk.

    A file shorter than ``chunk_size`` produces exactly one chunk.
    """
    if not content:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")

    chunks: List[CodeChunk] = []
    start = 0
    chunk_index = 0
    step = chunk_size - overlap

    while start < len(content):
        end = min(start + chunk_size, len(content))
        start_line = content.count("\n", 0, start) + 1
        end_line = content.count("\n", 0, end) + 1
        chunks.append(
            CodeChunk(
                id=f"{file_path}::chunk-{chunk_index}",
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                content=content[start:end],
            )
        )
        chunk_index += 1
        if end == len(content):
            break
        start += step

    return chunks


_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
    ".cpp", ".c", ".h", ".hpp", ".rb", ".php", ".cs", ".swift", ".kt",
}
_EXCLUDE_DIRS = {"node_modules", "venv", ".venv", "__pycache__", "dist", "build", ".git"}


def is_indexable_file(file_path: str) -> bool:
    """Decide whether a path should be embedded and indexed."""
    parts = file_path.split("/")
    if any(p in _EXCLUDE_DIRS for p in parts):
        return False
    return any(file_path.endswith(ext) for ext in _CODE_EXTENSIONS)
