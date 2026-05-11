"""Tests for the RAG layer: chunker, embedder, vector store, retriever."""

from unittest.mock import MagicMock, patch

import pytest

from src.rag.chunker import chunk_file, is_indexable_file


class TestChunker:
    def test_short_file_produces_single_chunk(self):
        content = "def hello():\n    return 42\n"
        chunks = chunk_file("hello.py", content, chunk_size=1000, overlap=100)
        assert len(chunks) == 1
        assert chunks[0]["file_path"] == "hello.py"
        assert chunks[0]["content"] == content
        assert chunks[0]["start_line"] == 1
        assert chunks[0]["end_line"] == 3

    def test_long_file_produces_overlapping_chunks(self):
        # Build a file longer than chunk_size with predictable line breaks.
        content = "\n".join([f"line {i}" for i in range(1, 401)]) + "\n"
        chunks = chunk_file("big.py", content, chunk_size=500, overlap=100)
        assert len(chunks) > 1
        # Consecutive chunks share the configured overlap.
        for prev, nxt in zip(chunks, chunks[1:]):
            tail = prev["content"][-100:]
            head = nxt["content"][:100]
            assert tail == head

    def test_each_chunk_has_unique_id(self):
        content = "x" * 5000
        chunks = chunk_file("x.py", content, chunk_size=1000, overlap=100)
        ids = [c["id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_invalid_overlap_raises(self):
        with pytest.raises(ValueError):
            chunk_file("x.py", "abc", chunk_size=10, overlap=10)

    def test_empty_content_returns_empty(self):
        assert chunk_file("x.py", "") == []


class TestIsIndexable:
    def test_python_files_are_indexable(self):
        assert is_indexable_file("src/foo.py")

    def test_markdown_is_not_indexable(self):
        assert not is_indexable_file("README.md")

    def test_excluded_dirs_are_skipped(self):
        assert not is_indexable_file("node_modules/foo.js")
        assert not is_indexable_file("src/__pycache__/cached.py")
        assert not is_indexable_file(".venv/site-packages/x.py")


class TestVectorStoreNotConfigured:
    """The store must be a safe no-op when Pinecone isn't configured."""

    def test_disabled_when_no_api_key(self, monkeypatch):
        # Explicit override — `.env` may carry real Pinecone values, but this
        # test is for the "not configured" code path.
        monkeypatch.setenv("PINECONE_API_KEY", "")
        monkeypatch.setenv("PINECONE_INDEX_NAME", "")
        import src.config

        src.config.settings = None

        from src.rag.vector_store import PineconeVectorStore

        store = PineconeVectorStore()
        assert store.is_configured is False
        assert store.upsert([{"id": "x", "values": [0.0], "metadata": {}}]) == 0
        assert store.query([0.1, 0.2]) == []


class TestRetriever:
    def test_inactive_store_returns_empty_list(self):
        from src.rag.retriever import CodeRetriever

        embedder = MagicMock()
        store = MagicMock()
        store.is_configured = False
        retriever = CodeRetriever(embedder=embedder, store=store)

        assert retriever.is_active is False
        assert retriever.retrieve("anything") == []
        embedder.embed_query.assert_not_called()

    def test_retrieves_and_normalises_chunks(self):
        from src.rag.retriever import CodeRetriever

        embedder = MagicMock()
        embedder.embed_query.return_value = [0.1] * 8
        store = MagicMock()
        store.is_configured = True
        store.query.return_value = [
            {
                "id": "owner/repo::src/x.py::chunk-0",
                "score": 0.92,
                "metadata": {
                    "file_path": "src/x.py",
                    "start_line": 1,
                    "end_line": 12,
                    "content": "def x(): pass",
                },
            },
            {
                "id": "owner/repo::src/y.py::chunk-2",
                "score": 0.81,
                "metadata": {
                    "file_path": "src/y.py",
                    "start_line": 30,
                    "end_line": 42,
                    "content": "def y(): pass",
                },
            },
        ]
        retriever = CodeRetriever(embedder=embedder, store=store)
        results = retriever.retrieve("query", top_k=2)

        assert [r["file_path"] for r in results] == ["src/x.py", "src/y.py"]
        assert results[0]["score"] == pytest.approx(0.92)
        assert results[1]["start_line"] == 30

    def test_swallows_exceptions(self):
        from src.rag.retriever import CodeRetriever

        embedder = MagicMock()
        embedder.embed_query.side_effect = RuntimeError("network down")
        store = MagicMock()
        store.is_configured = True
        retriever = CodeRetriever(embedder=embedder, store=store)
        assert retriever.retrieve("query") == []


class TestPromptInjection:
    """The CodeReviewer should fold retrieved chunks into the prompt."""

    def test_review_changes_includes_retrieved_chunks_in_prompt(self):
        from src.agents.code_reviewer import CodeReviewer
        from src.workflow.state import CodeChange, RetrievedChunk

        reviewer = CodeReviewer.__new__(CodeReviewer)  # bypass __init__
        # Capture the rendered user prompt.
        captured = {}

        class FakeResp:
            content = '{"comments": [], "summary": "ok"}'

        class FakeLLM:
            def invoke(self, messages):
                # messages = [SystemMessage, HumanMessage]
                captured["user"] = messages[1].content
                return FakeResp()

        reviewer.llm = FakeLLM()
        reviewer.parser = MagicMock()

        changes = [
            CodeChange(
                file_path="src/auth.py",
                diff="@@ -1 +1 @@\n-def login(): ...\n+def login(user): ...\n",
                language="python",
                additions=1,
                deletions=1,
            )
        ]
        retrieved = [
            RetrievedChunk(
                file_path="src/helpers.py",
                start_line=10,
                end_line=20,
                content="def validate(user): ...",
                score=0.91,
            )
        ]
        reviewer.review_changes(changes, retrieved_context=retrieved)

        prompt = captured["user"]
        assert "Retrieved repository context" in prompt
        assert "src/helpers.py:10-20" in prompt
        assert "def validate(user)" in prompt

    def test_review_changes_without_context_omits_block(self):
        from src.agents.code_reviewer import CodeReviewer
        from src.workflow.state import CodeChange

        reviewer = CodeReviewer.__new__(CodeReviewer)
        captured = {}

        class FakeResp:
            content = '{"comments": [], "summary": "ok"}'

        class FakeLLM:
            def invoke(self, messages):
                captured["user"] = messages[1].content
                return FakeResp()

        reviewer.llm = FakeLLM()
        reviewer.parser = MagicMock()

        reviewer.review_changes(
            [
                CodeChange(
                    file_path="x.py",
                    diff="@@ -1 +1 @@\n-old\n+new\n",
                    language="python",
                    additions=1,
                    deletions=1,
                )
            ]
        )

        assert "Retrieved repository context" not in captured["user"]


class TestRetrieveContextNode:
    """The review graph's retrieve_context node should populate state."""

    def test_inactive_retriever_writes_empty_list(self):
        from src.workflow.review_graph import PRReviewWorkflow

        wf = PRReviewWorkflow.__new__(PRReviewWorkflow)
        wf.retriever = MagicMock()
        wf.retriever.is_active = False
        result = wf.retrieve_context({"changes": [], "error": None})
        assert result == {"retrieved_context": []}

    def test_active_retriever_calls_retrieve_with_diff_query(self):
        from src.workflow.review_graph import PRReviewWorkflow

        wf = PRReviewWorkflow.__new__(PRReviewWorkflow)
        wf.retriever = MagicMock()
        wf.retriever.is_active = True
        wf.retriever.retrieve.return_value = [
            {"file_path": "a.py", "start_line": 1, "end_line": 2,
             "content": "def a(): pass", "score": 0.7}
        ]
        state = {
            "changes": [
                {"file_path": "src/auth.py",
                 "diff": "@@ -1 +1 @@\n-old\n+new",
                 "language": "python",
                 "additions": 1, "deletions": 1},
            ],
            "error": None,
        }
        result = wf.retrieve_context(state)
        assert len(result["retrieved_context"]) == 1
        wf.retriever.retrieve.assert_called_once()
        # The query string should mention the file path the PR touched.
        called_query = wf.retriever.retrieve.call_args[0][0]
        assert "src/auth.py" in called_query
