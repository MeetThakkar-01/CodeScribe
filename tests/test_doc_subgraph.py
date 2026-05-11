"""Tests for the documentation subgraph."""

from unittest.mock import MagicMock, patch

import pytest


def _base_doc_state() -> dict:
    return {
        "repo_owner": "octo",
        "repo_name": "demo",
        "installation_id": 999,
        "cached_structure": {},
        "current_structure": {},
        "current_readme": "",
        "changes": None,
        "new_readme": None,
        "readme_updated": False,
        "error": None,
    }


@pytest.fixture
def workflow():
    from src.agents.documentation.graph import DocumentationWorkflow

    return DocumentationWorkflow()


class TestGraphCompilation:
    def test_doc_graph_compiles(self, workflow):
        assert workflow.graph is not None


class TestNeedsCommit:
    def test_skip_when_new_readme_is_none(self, workflow):
        state = _base_doc_state()
        state["new_readme"] = None
        assert workflow._needs_commit(state) == "skip"

    def test_commit_when_new_readme_is_set(self, workflow):
        state = _base_doc_state()
        state["new_readme"] = "# updated"
        assert workflow._needs_commit(state) == "commit"

    def test_skip_when_error_is_set(self, workflow):
        state = _base_doc_state()
        state["new_readme"] = "# updated"
        state["error"] = "earlier failure"
        assert workflow._needs_commit(state) == "skip"


@patch("src.agents.documentation.graph.GitHubClient")
@patch("src.agents.documentation.graph.DocumentationAgent")
class TestNodes:
    def _agent(self, mock_doc_agent):
        instance = MagicMock()
        mock_doc_agent.return_value = instance
        return instance

    def test_load_cache_populates_state(self, mock_doc_agent, mock_gh, workflow):
        agent = self._agent(mock_doc_agent)
        agent.load_cache.return_value = {"a.py": {"sha": "1", "content": "x"}}

        result = workflow.load_cache(_base_doc_state())

        assert result["cached_structure"] == {"a.py": {"sha": "1", "content": "x"}}
        assert result["error"] is None

    def test_fetch_repo_structure_populates_state(
        self, mock_doc_agent, mock_gh, workflow
    ):
        agent = self._agent(mock_doc_agent)
        agent.get_repo_structure.return_value = {"a.py": {"sha": "1", "content": "x"}}
        agent.get_current_readme.return_value = "# README"

        result = workflow.fetch_repo_structure(_base_doc_state())

        assert result["current_structure"] == {"a.py": {"sha": "1", "content": "x"}}
        assert result["current_readme"] == "# README"

    def test_generate_docs_no_update_returns_none(
        self, mock_doc_agent, mock_gh, workflow
    ):
        agent = self._agent(mock_doc_agent)
        agent.generate_documentation.return_value = None

        state = _base_doc_state()
        state["current_structure"] = {"a.py": {"sha": "1", "content": "x"}}
        result = workflow.generate_docs(state)

        assert result["new_readme"] is None
        assert workflow._needs_commit({**state, **result}) == "skip"

    def test_generate_docs_update_returns_markdown(
        self, mock_doc_agent, mock_gh, workflow
    ):
        agent = self._agent(mock_doc_agent)
        agent.generate_documentation.return_value = "# new readme"

        state = _base_doc_state()
        state["current_structure"] = {"a.py": {"sha": "1", "content": "x"}}
        result = workflow.generate_docs(state)

        assert result["new_readme"] == "# new readme"
        assert workflow._needs_commit({**state, **result}) == "commit"

    def test_commit_readme_calls_update_readme(
        self, mock_doc_agent, mock_gh, workflow
    ):
        agent = self._agent(mock_doc_agent)
        agent.update_readme.return_value = True

        state = _base_doc_state()
        state["new_readme"] = "# new readme"
        result = workflow.commit_readme(state)

        agent.update_readme.assert_called_once_with("# new readme")
        assert result["readme_updated"] is True

    def test_commit_readme_skips_when_no_new_content(
        self, mock_doc_agent, mock_gh, workflow
    ):
        agent = self._agent(mock_doc_agent)

        result = workflow.commit_readme(_base_doc_state())

        agent.update_readme.assert_not_called()
        assert result["readme_updated"] is False
