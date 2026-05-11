"""LangGraph subgraph for creating Jira issues from review findings."""

from typing import Any, Dict, List

import structlog
from langgraph.graph import END, StateGraph

from src.agents.ticketing.client import JiraClient
from src.agents.ticketing.state import TicketingState
from src.config import get_settings
from src.workflow.state import ReviewComment
from src.workflow.timing import timed_stage

logger = structlog.get_logger()

_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


def _summary_for(c: ReviewComment) -> str:
    """Build a short, single-line Jira summary from a review comment."""
    message = (c.get("message") or "").strip().splitlines()[0] if c.get("message") else ""
    if len(message) > 120:
        message = message[:117] + "..."
    category = c.get("category", "issue")
    file_path = c.get("file_path", "?")
    line_number = c.get("line_number", 0)
    return f"[{category}] {file_path}:{line_number} - {message}"


def _description_for(c: ReviewComment, state: TicketingState) -> Dict[str, Any]:
    """Build an Atlassian Document Format (ADF) description for the issue.

    Jira REST API v3 requires descriptions to be ADF; a plain string returns 400.
    """
    pr_url = (
        f"https://github.com/{state['repo_owner']}/{state['repo_name']}"
        f"/pull/{state['pr_number']}"
    )
    suggestion = c.get("suggestion") or "No suggestion provided."
    location = f"{c.get('file_path', '?')}:{c.get('line_number', 0)}"

    return {
        "type": "doc",
        "version": 1,
        "content": [
            # Meta block: severity / category / location / source PR
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Severity: ", "marks": [{"type": "strong"}]},
                    {"type": "text", "text": c.get("severity", "unknown")},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "Category: ", "marks": [{"type": "strong"}]},
                    {"type": "text", "text": c.get("category", "unknown")},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "Location: ", "marks": [{"type": "strong"}]},
                    {"type": "text", "text": location, "marks": [{"type": "code"}]},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "Source: ", "marks": [{"type": "strong"}]},
                    {
                        "type": "text",
                        "text": f"PR #{state['pr_number']}",
                        "marks": [{"type": "link", "attrs": {"href": pr_url}}],
                    },
                ],
            },
            # Finding
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "Finding"}],
            },
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": c.get("message", "")}],
            },
            # Suggestion
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "Suggestion"}],
            },
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": suggestion}],
            },
        ],
    }


class TicketingWorkflow:
    """Ticketing subgraph: filter -> build -> create."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self):
        g = StateGraph(TicketingState)

        g.add_node("filter_comments", self.filter_comments)
        g.add_node("build_payloads", self.build_payloads)
        g.add_node("create_issues", self.create_issues)

        g.set_entry_point("filter_comments")
        g.add_edge("filter_comments", "build_payloads")
        g.add_edge("build_payloads", "create_issues")
        g.add_edge("create_issues", END)

        return g.compile()

    @staticmethod
    def _qualifying(comments: List[ReviewComment], threshold: str) -> List[ReviewComment]:
        cutoff = _SEVERITY_ORDER.get(threshold, 2)
        return [
            c
            for c in comments
            if _SEVERITY_ORDER.get(c.get("severity", "low"), 0) >= cutoff
        ]

    @timed_stage("filter_comments")
    def filter_comments(self, state: TicketingState) -> Dict[str, Any]:
        if state.get("error"):
            return {}
        try:
            threshold = get_settings().jira_min_severity
            kept = self._qualifying(state.get("review_comments") or [], threshold)
            logger.info(
                "ticketing.filter",
                input=len(state.get("review_comments") or []),
                kept=len(kept),
                threshold=threshold,
            )
            return {"review_comments": kept}
        except Exception as e:
            logger.error("ticketing.filter failed", error=str(e))
            return {"error": f"filter_comments: {e}"}

    @timed_stage("build_payloads")
    def build_payloads(self, state: TicketingState) -> Dict[str, Any]:
        if state.get("error"):
            return {}
        try:
            settings = get_settings()
            payloads = [
                {
                    "fields": {
                        "project": {"key": settings.jira_project_key},
                        "summary": _summary_for(c),
                        "description": _description_for(c, state),
                        "issuetype": {"name": "Task"},
                        "labels": [
                            "codescribe",
                            c.get("severity", "unknown"),
                            c.get("category", "unknown"),
                        ],
                    }
                }
                for c in state.get("review_comments") or []
            ]
            return {"issues_to_create": payloads}
        except Exception as e:
            logger.error("ticketing.build_payloads failed", error=str(e))
            return {"error": f"build_payloads: {e}"}

    @timed_stage("create_issues")
    def create_issues(self, state: TicketingState) -> Dict[str, Any]:
        if state.get("error"):
            return {}
        payloads = state.get("issues_to_create") or []
        if not payloads:
            logger.info("ticketing.create_issues skipped (no payloads)")
            return {"created_issue_keys": []}
        try:
            client = JiraClient()
            keys: List[str] = []
            for payload in payloads:
                keys.append(client.create_issue(payload))
            logger.info("ticketing.create_issues created", count=len(keys))
            return {"created_issue_keys": keys}
        except Exception as e:
            logger.error("ticketing.create_issues failed", error=str(e))
            return {"error": f"create_issues: {e}"}
