"""Tests for the supervisor graph and routing logic."""

from unittest.mock import MagicMock, patch

import pytest

from src.workflow.state import PRMetadata


def _base_state(event_type: str = "pr_opened") -> dict:
    pr_meta: PRMetadata = {
        "repo_owner": "octo",
        "repo_name": "demo",
        "pr_number": 7,
        "pr_title": "Test",
        "pr_author": "octocat",
        "base_branch": "main",
        "head_branch": "feature/x",
        "installation_id": 999,
    }
    return {
        "event_type": event_type,
        "run_id": "run-abc",
        "repo_owner": "octo",
        "repo_name": "demo",
        "installation_id": 999,
        "pr_metadata": pr_meta,
        "review_substate": None,
        "docs_substate": None,
        "ticketing_substate": None,
        "next_agent": None,
        "completed_agents": [],
        "error": None,
    }


@pytest.fixture
def supervisor():
    """Build a CodeScribeOrchestrator with all subgraph constructors stubbed."""
    with patch("src.workflow.supervisor_graph.PRReviewWorkflow") as mock_review, patch(
        "src.workflow.supervisor_graph.DocumentationWorkflow"
    ) as mock_docs, patch(
        "src.workflow.supervisor_graph.TicketingWorkflow"
    ) as mock_ticketing:
        mock_review.return_value.graph = MagicMock()
        mock_docs.return_value.graph = MagicMock()
        mock_ticketing.return_value.graph = MagicMock()

        from src.workflow.supervisor_graph import CodeScribeOrchestrator

        sup = CodeScribeOrchestrator()
        yield sup


class TestRouter:
    def test_pr_opened_routes_to_review(self, supervisor):
        result = supervisor.route(_base_state("pr_opened"))
        assert result == {"next_agent": "review"}

    def test_pr_merged_routes_to_docs(self, supervisor):
        result = supervisor.route(_base_state("pr_merged"))
        assert result == {"next_agent": "docs"}

    def test_manual_docs_routes_to_docs(self, supervisor):
        result = supervisor.route(_base_state("manual_docs"))
        assert result == {"next_agent": "docs"}

    def test_unknown_event_returns_end_with_error(self, supervisor):
        result = supervisor.route(_base_state("nope"))
        assert result["next_agent"] == "end"
        assert "Unknown event_type" in result["error"]


class TestGraphCompilation:
    def test_supervisor_graph_compiles(self, supervisor):
        assert supervisor.graph is not None


class TestSubgraphWrappers:
    def test_run_review_invokes_inner_graph_and_records_completion(self, supervisor):
        fake_result = {
            "pr_metadata": _base_state()["pr_metadata"],
            "changes": [],
            "retrieved_context": [],
            "review_comments": [],
            "analysis_complete": True,
            "comments_posted": True,
            "all_resolved": False,
            "ready_for_approval": True,
            "error": None,
        }
        supervisor.review_workflow.graph.invoke.return_value = fake_result

        result = supervisor.run_review(_base_state("pr_opened"))

        supervisor.review_workflow.graph.invoke.assert_called_once()
        assert result["review_substate"] == fake_result
        assert result["completed_agents"] == ["review"]
        assert result["error"] is None

    def test_run_docs_invokes_inner_graph_and_records_completion(self, supervisor):
        fake_result = {
            "repo_owner": "octo",
            "repo_name": "demo",
            "installation_id": 999,
            "cached_structure": {},
            "current_structure": {"a.py": {"sha": "1", "content": "x"}},
            "current_readme": "# old",
            "changes": None,
            "new_readme": "# new",
            "readme_updated": True,
            "error": None,
        }
        supervisor.docs_workflow.graph.invoke.return_value = fake_result

        result = supervisor.run_docs(_base_state("pr_merged"))

        supervisor.docs_workflow.graph.invoke.assert_called_once()
        assert result["docs_substate"] == fake_result
        assert result["completed_agents"] == ["docs"]
        assert result["error"] is None

    def test_run_review_propagates_subgraph_error(self, supervisor):
        supervisor.review_workflow.graph.invoke.return_value = {
            "error": "boom",
            "pr_metadata": _base_state()["pr_metadata"],
            "changes": [],
            "retrieved_context": [],
            "review_comments": [],
            "analysis_complete": False,
            "comments_posted": False,
            "all_resolved": False,
            "ready_for_approval": False,
        }
        result = supervisor.run_review(_base_state("pr_opened"))
        assert result["error"] == "boom"
        assert result["completed_agents"] == ["review"]


def _comment(severity: str) -> dict:
    return {
        "file_path": "src/x.py",
        "line_number": 1,
        "severity": severity,
        "category": "bug",
        "message": "issue",
        "suggestion": "fix it",
        "resolved": False,
    }


class TestTicketingChain:
    """The conditional edge out of review_node into ticketing_node."""

    def test_high_sev_review_routes_to_ticketing(self, supervisor):
        state = _base_state("pr_opened")
        state["review_substate"] = {"review_comments": [_comment("high")]}
        assert supervisor._needs_ticketing(state) == "ticket"

    def test_only_low_sev_review_skips_ticketing(self, supervisor):
        state = _base_state("pr_opened")
        state["review_substate"] = {
            "review_comments": [_comment("low"), _comment("medium")]
        }
        assert supervisor._needs_ticketing(state) == "skip"

    def test_no_review_substate_skips_ticketing(self, supervisor):
        state = _base_state("pr_opened")
        # review_substate is None (default)
        assert supervisor._needs_ticketing(state) == "skip"

    def test_run_ticketing_invokes_inner_graph(self, supervisor):
        fake_result = {
            "repo_owner": "octo",
            "repo_name": "demo",
            "pr_number": 7,
            "review_comments": [_comment("high")],
            "issues_to_create": [{"fields": {}}],
            "created_issue_keys": ["CS-1"],
            "error": None,
        }
        supervisor.ticketing_workflow.graph.invoke.return_value = fake_result

        state = _base_state("pr_opened")
        state["review_substate"] = {"review_comments": [_comment("high")]}
        result = supervisor.run_ticketing(state)

        supervisor.ticketing_workflow.graph.invoke.assert_called_once()
        assert result["ticketing_substate"] == fake_result
        assert result["completed_agents"] == ["ticketing"]
        assert result["error"] is None
