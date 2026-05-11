"""Parent supervisor graph that routes events to the right agent subgraph."""

from typing import Any, Dict

import structlog
from langgraph.graph import END, StateGraph

from src.agents.documentation.graph import DocumentationWorkflow
from src.agents.documentation.state import DocState
from src.agents.ticketing.graph import TicketingWorkflow
from src.agents.ticketing.state import TicketingState
from src.config import get_settings
from src.workflow.review_graph import PRReviewWorkflow
from src.workflow.state import ReviewState
from src.workflow.supervisor_state import SupervisorState
from src.workflow.timing import timed_stage

logger = structlog.get_logger()


class CodeScribeOrchestrator:
    """Coordinates Code Review, Documentation Sync, and Jira agents.

    Routes incoming events to the appropriate agent subgraph. The subgraphs
    keep their own TypedDict shapes; each wrapper node translates between
    the orchestrator's shared state and the subgraph's private state.
    """

    def __init__(self) -> None:
        self.review_workflow = PRReviewWorkflow()
        self.docs_workflow = DocumentationWorkflow()
        self.ticketing_workflow = TicketingWorkflow()
        self.graph = self._build_graph()

    def _build_graph(self):
        g = StateGraph(SupervisorState)

        g.add_node("router", self.route)
        g.add_node("review_node", self.run_review)
        g.add_node("docs_node", self.run_docs)
        g.add_node("ticketing_node", self.run_ticketing)
        g.add_node("finalize", self.finalize)

        g.set_entry_point("router")
        g.add_conditional_edges(
            "router",
            lambda s: s["next_agent"],
            {
                "review": "review_node",
                "docs": "docs_node",
                "end": "finalize",
            },
        )
        # After the review subgraph, optionally chain into ticketing if any
        # qualifying high-severity comment was produced. Otherwise go straight
        # to finalize. This keeps the router unaware of ticketing.
        g.add_conditional_edges(
            "review_node",
            self._needs_ticketing,
            {"ticket": "ticketing_node", "skip": "finalize"},
        )
        g.add_edge("ticketing_node", "finalize")
        g.add_edge("docs_node", "finalize")
        g.add_edge("finalize", END)

        return g.compile()

    @timed_stage("router")
    def route(self, state: SupervisorState) -> Dict[str, Any]:
        event = state.get("event_type")
        if event == "pr_opened":
            return {"next_agent": "review"}
        if event in ("pr_merged", "manual_docs"):
            return {"next_agent": "docs"}
        return {
            "next_agent": "end",
            "error": f"Unknown event_type: {event!r}",
        }

    @timed_stage("review_node")
    def run_review(self, state: SupervisorState) -> Dict[str, Any]:
        pr_meta = state.get("pr_metadata")
        if pr_meta is None:
            return {"error": "review_node missing pr_metadata"}

        initial: ReviewState = {
            "pr_metadata": pr_meta,
            "changes": [],
            "retrieved_context": [],
            "review_comments": [],
            "analysis_complete": False,
            "comments_posted": False,
            "all_resolved": False,
            "ready_for_approval": False,
            "error": None,
        }

        logger.info(
            "supervisor.invoke_review",
            run_id=state.get("run_id"),
            pr_number=pr_meta["pr_number"],
        )
        result = self.review_workflow.graph.invoke(initial)

        return {
            "review_substate": result,
            "completed_agents": list(state.get("completed_agents", [])) + ["review"],
            "error": result.get("error"),
        }

    @timed_stage("docs_node")
    def run_docs(self, state: SupervisorState) -> Dict[str, Any]:
        initial: DocState = {
            "repo_owner": state["repo_owner"],
            "repo_name": state["repo_name"],
            "installation_id": state["installation_id"],
            "cached_structure": {},
            "current_structure": {},
            "current_readme": "",
            "changes": None,
            "new_readme": None,
            "readme_updated": False,
            "error": None,
        }

        logger.info(
            "supervisor.invoke_docs",
            run_id=state.get("run_id"),
            repo=f"{state['repo_owner']}/{state['repo_name']}",
        )
        result = self.docs_workflow.graph.invoke(initial)

        return {
            "docs_substate": result,
            "completed_agents": list(state.get("completed_agents", [])) + ["docs"],
            "error": result.get("error"),
        }

    @staticmethod
    def _needs_ticketing(state: SupervisorState) -> str:
        """Decide whether to invoke the ticketing subgraph after review."""
        if state.get("error"):
            return "skip"
        review = state.get("review_substate") or {}
        comments = review.get("review_comments") or []
        order = {"low": 0, "medium": 1, "high": 2}
        threshold = get_settings().jira_min_severity
        cutoff = order.get(threshold, 2)
        has_qualifying = any(
            order.get(c.get("severity", "low"), 0) >= cutoff for c in comments
        )
        return "ticket" if has_qualifying else "skip"

    @timed_stage("ticketing_node")
    def run_ticketing(self, state: SupervisorState) -> Dict[str, Any]:
        review = state.get("review_substate") or {}
        pr_meta = state.get("pr_metadata") or {}
        initial: TicketingState = {
            "repo_owner": state["repo_owner"],
            "repo_name": state["repo_name"],
            "pr_number": pr_meta.get("pr_number", 0),
            "review_comments": review.get("review_comments", []),
            "issues_to_create": [],
            "created_issue_keys": [],
            "error": None,
        }

        logger.info(
            "supervisor.invoke_ticketing",
            run_id=state.get("run_id"),
            pr_number=initial["pr_number"],
        )
        result = self.ticketing_workflow.graph.invoke(initial)

        return {
            "ticketing_substate": result,
            "completed_agents": list(state.get("completed_agents", [])) + ["ticketing"],
            "error": result.get("error"),
        }

    @timed_stage("finalize")
    def finalize(self, state: SupervisorState) -> Dict[str, Any]:
        logger.info(
            "supervisor.finalize",
            run_id=state.get("run_id"),
            completed=state.get("completed_agents", []),
            error=state.get("error"),
        )
        return {}
