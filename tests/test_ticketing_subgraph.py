"""Tests for the Jira ticketing subgraph."""

from unittest.mock import patch

import pytest

from src.agents.ticketing.graph import TicketingWorkflow
from src.workflow.state import ReviewComment


def _comment(severity: str, category: str = "bug", line: int = 1) -> ReviewComment:
    return {
        "file_path": f"src/{severity}.py",
        "line_number": line,
        "severity": severity,
        "category": category,
        "message": f"{severity} finding on line {line}",
        "suggestion": "Do the thing differently.",
        "resolved": False,
    }


def _state(comments=None) -> dict:
    return {
        "repo_owner": "octo",
        "repo_name": "demo",
        "pr_number": 7,
        "review_comments": comments or [],
        "issues_to_create": [],
        "created_issue_keys": [],
        "error": None,
    }


class TestFilter:
    def test_keeps_only_high_severity_by_default(self):
        wf = TicketingWorkflow()
        comments = [_comment("low"), _comment("medium"), _comment("high"), _comment("high", line=2)]
        result = wf.filter_comments(_state(comments))
        assert [c["severity"] for c in result["review_comments"]] == ["high", "high"]

    def test_threshold_setting_changes_filter(self, monkeypatch):
        monkeypatch.setenv("JIRA_MIN_SEVERITY", "medium")
        import src.config as config
        config.settings = None  # force reload to pick up env

        wf = TicketingWorkflow()
        comments = [_comment("low"), _comment("medium"), _comment("high")]
        result = wf.filter_comments(_state(comments))
        assert [c["severity"] for c in result["review_comments"]] == ["medium", "high"]


class TestBuildPayloads:
    def test_payload_has_expected_shape(self):
        import json

        wf = TicketingWorkflow()
        state = _state([_comment("high", category="security", line=42)])
        result = wf.build_payloads(state)
        assert len(result["issues_to_create"]) == 1

        payload = result["issues_to_create"][0]
        fields = payload["fields"]
        assert fields["project"]["key"]  # whatever the default is
        assert "[security]" in fields["summary"]
        assert "src/high.py:42" in fields["summary"]
        # Description must be ADF (a dict, not a string) for Jira REST v3.
        assert isinstance(fields["description"], dict)
        assert fields["description"]["type"] == "doc"
        # PR link + ticket text are still discoverable inside the ADF tree.
        desc_serialized = json.dumps(fields["description"])
        assert "PR #7" in desc_serialized
        assert "https://github.com/octo/demo/pull/7" in desc_serialized
        assert fields["issuetype"]["name"] == "Task"
        assert "codescribe" in fields["labels"]
        assert "high" in fields["labels"]
        assert "security" in fields["labels"]


class TestCreateIssues:
    def test_calls_client_per_payload(self):
        wf = TicketingWorkflow()
        state = _state([_comment("high"), _comment("high", line=2)])
        # Run filter+build to populate issues_to_create
        state.update(wf.filter_comments(state))
        state.update(wf.build_payloads(state))

        with patch(
            "src.agents.ticketing.graph.JiraClient"
        ) as mock_client_cls:
            mock_client_cls.return_value.create_issue.side_effect = ["CS-1", "CS-2"]
            result = wf.create_issues(state)

        assert result["created_issue_keys"] == ["CS-1", "CS-2"]
        assert mock_client_cls.return_value.create_issue.call_count == 2

    def test_empty_payloads_skips_client(self):
        wf = TicketingWorkflow()
        state = _state([])
        state.update(wf.filter_comments(state))
        state.update(wf.build_payloads(state))

        with patch("src.agents.ticketing.graph.JiraClient") as mock_client_cls:
            result = wf.create_issues(state)

        assert result == {"created_issue_keys": []}
        mock_client_cls.return_value.create_issue.assert_not_called()

    def test_http_error_surfaces_in_state_error(self):
        import httpx

        wf = TicketingWorkflow()
        state = _state([_comment("high")])
        state.update(wf.filter_comments(state))
        state.update(wf.build_payloads(state))

        with patch("src.agents.ticketing.graph.JiraClient") as mock_client_cls:
            mock_client_cls.return_value.create_issue.side_effect = httpx.HTTPError("boom")
            result = wf.create_issues(state)

        assert "create_issues" in result["error"]


class TestGraphCompilation:
    def test_graph_compiles(self):
        assert TicketingWorkflow().graph is not None
