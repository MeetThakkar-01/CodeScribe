"""Basic tests for the GitHub PR Review Agent."""

import hashlib
import hmac
import json

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.workflow.state import ReviewState, PRMetadata, CodeChange, ReviewComment


class TestCodeReviewer:
    """Tests for the code reviewer agent."""

    def test_build_code_context(self):
        """Test building code context from changes."""
        from src.agents.code_reviewer import CodeReviewer

        reviewer = CodeReviewer()
        changes = [
            CodeChange(
                file_path="test.py",
                diff="+ print('hello')",
                language="python",
                additions=1,
                deletions=0,
            )
        ]

        context = reviewer._build_code_context(changes)
        assert "test.py" in context
        assert "python" in context
        assert "print('hello')" in context


class TestGitHubClient:
    """Tests for the GitHub client."""

    def test_get_language_from_filename(self):
        """Test language detection from filename."""
        from src.github.client import GitHubClient

        assert GitHubClient._get_language_from_filename("test.py") == "python"
        assert GitHubClient._get_language_from_filename("app.js") == "javascript"
        assert GitHubClient._get_language_from_filename("main.go") == "go"
        assert GitHubClient._get_language_from_filename("unknown.xyz") is None


class TestWorkflow:
    """Tests for the LangGraph workflow."""

    @patch("src.workflow.review_graph.GitHubClient")
    @patch("src.workflow.review_graph.CodeReviewer")
    def test_fetch_pr_changes(self, mock_reviewer, mock_github):
        """Test fetching PR changes."""
        from src.workflow.review_graph import PRReviewWorkflow

        # Mock the GitHub client
        mock_client = Mock()
        mock_client.get_pr_diff.return_value = [
            CodeChange(
                file_path="test.py",
                diff="+ new code",
                language="python",
                additions=1,
                deletions=0,
            )
        ]
        mock_github.return_value = mock_client

        workflow = PRReviewWorkflow()
        
        state: ReviewState = {
            "pr_metadata": PRMetadata(
                repo_owner="test",
                repo_name="repo",
                pr_number=1,
                pr_title="Test PR",
                pr_author="user",
                base_branch="main",
                head_branch="feature",
                installation_id=12345,
            ),
            "changes": [],
            "retrieved_context": [],
            "review_comments": [],
            "analysis_complete": False,
            "comments_posted": False,
            "all_resolved": False,
            "ready_for_approval": False,
            "error": None,
        }

        result = workflow.fetch_pr_changes(state)
        
        assert "changes" in result
        assert len(result["changes"]) == 1
        assert result["error"] is None


@pytest.mark.asyncio
async def test_webhook_health_endpoint():
    """Test the health check endpoint."""
    from fastapi.testclient import TestClient
    from src.github.webhook_handler import app

    client = TestClient(app)
    response = client.get("/health")
    
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_webhook_root_endpoint():
    """Test the root endpoint."""
    from fastapi.testclient import TestClient
    from src.github.webhook_handler import app

    client = TestClient(app)
    response = client.get("/")
    
    assert response.status_code == 200
    assert "status" in response.json()
    assert response.json()["status"] == "ok"


def _signed_post(client, payload: dict, event: str, secret: str):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        "/webhook/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": event,
            "Content-Type": "application/json",
        },
    )


def _pr_payload(action: str, *, merged: bool = False, base_ref: str = "main") -> dict:
    return {
        "action": action,
        "pull_request": {
            "number": 42,
            "title": "demo",
            "user": {"login": "octocat"},
            "base": {"ref": base_ref},
            "head": {"ref": "feature/x"},
            "merged": merged,
        },
        "repository": {
            "name": "demo",
            "owner": {"login": "octo"},
        },
        "installation": {"id": 999},
    }


@pytest.mark.asyncio
async def test_webhook_dispatches_review_on_pr_opened():
    """A PR opened webhook should dispatch to the review agent."""
    from fastapi.testclient import TestClient

    with patch("src.github.webhook_handler.CodeScribeOrchestrator") as mock_sup:
        mock_sup.return_value.graph = MagicMock()
        from src.github.webhook_handler import app

        with TestClient(app) as client:
            response = _signed_post(
                client, _pr_payload("opened"), "pull_request", "test-secret"
            )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["agent"] == "review"
    assert "run_id" in body


@pytest.mark.asyncio
async def test_webhook_dispatches_docs_on_merged_pr():
    """A PR closed+merged into main should dispatch to the docs agent."""
    from fastapi.testclient import TestClient

    with patch("src.github.webhook_handler.CodeScribeOrchestrator") as mock_sup:
        mock_sup.return_value.graph = MagicMock()
        from src.github.webhook_handler import app

        with TestClient(app) as client:
            response = _signed_post(
                client,
                _pr_payload("closed", merged=True, base_ref="main"),
                "pull_request",
                "test-secret",
            )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["agent"] == "docs"


@pytest.mark.asyncio
async def test_webhook_ignores_closed_unmerged_pr():
    """A PR closed without merge should not dispatch anything."""
    from fastapi.testclient import TestClient

    with patch("src.github.webhook_handler.CodeScribeOrchestrator") as mock_sup:
        mock_sup.return_value.graph = MagicMock()
        from src.github.webhook_handler import app

        with TestClient(app) as client:
            response = _signed_post(
                client,
                _pr_payload("closed", merged=False),
                "pull_request",
                "test-secret",
            )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
