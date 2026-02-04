"""Basic tests for the GitHub PR Review Agent."""

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
