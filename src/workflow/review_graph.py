"""LangGraph workflow for PR code review."""

import structlog
from typing import Dict, Any

from langgraph.graph import StateGraph, END

from src.workflow.state import ReviewState
from src.github.client import GitHubClient
from src.github.commit_manager import CommitManager
from src.agents.code_reviewer import CodeReviewer
from src.agents.review_summary import build_clean_summary, build_review_summary
from src.config import get_settings
from src.rag.retriever import CodeRetriever
from src.workflow.timing import timed_stage

logger = structlog.get_logger()


class PRReviewWorkflow:
    """LangGraph workflow for reviewing pull requests."""

    def __init__(self):
        """Initialize the workflow."""
        self.github_client = GitHubClient()
        self.commit_manager = CommitManager(self.github_client)
        self.code_reviewer = CodeReviewer()
        self.retriever = CodeRetriever()
        self.settings = get_settings()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""
        workflow = StateGraph(ReviewState)

        # Add nodes
        workflow.add_node("fetch_pr_changes", self.fetch_pr_changes)
        workflow.add_node("retrieve_context", self.retrieve_context)
        workflow.add_node("analyze_code", self.analyze_code)
        workflow.add_node("post_reviews", self.post_reviews)
        workflow.add_node("update_status", self.update_status)

        # Define the flow
        workflow.set_entry_point("fetch_pr_changes")
        workflow.add_edge("fetch_pr_changes", "retrieve_context")
        workflow.add_edge("retrieve_context", "analyze_code")
        workflow.add_edge("analyze_code", "post_reviews")
        workflow.add_edge("post_reviews", "update_status")
        workflow.add_edge("update_status", END)

        return workflow.compile()

    @timed_stage("retrieve_context")
    def retrieve_context(self, state: ReviewState) -> Dict[str, Any]:
        """Embed the diff and pull semantically related code from the index.

        Failures here are non-fatal: the review proceeds without retrieved
        context if Pinecone is misconfigured or unreachable.
        """
        if state.get("error"):
            return {}

        if not self.retriever.is_active:
            logger.info("rag.retrieve skipped (retriever inactive)")
            return {"retrieved_context": []}

        # Build a query that captures both the files touched and a sample of
        # what changed. Concatenating file paths plus the first ~500 chars of
        # each diff keeps the embedded query bounded but specific.
        parts = []
        for change in state.get("changes") or []:
            parts.append(change.get("file_path", ""))
            diff = change.get("diff") or ""
            if diff:
                parts.append(diff[:500])
        query = "\n".join(p for p in parts if p)

        chunks = self.retriever.retrieve(query)
        logger.info("rag.retrieve", retrieved=len(chunks))
        return {"retrieved_context": chunks}

    @timed_stage("fetch_pr_changes")
    def fetch_pr_changes(self, state: ReviewState) -> Dict[str, Any]:
        """Fetch PR changes from GitHub."""
        logger.info("Fetching PR changes", pr_number=state["pr_metadata"]["pr_number"])

        try:
            pr_meta = state["pr_metadata"]
            changes = self.github_client.get_pr_diff(
                owner=pr_meta["repo_owner"],
                repo=pr_meta["repo_name"],
                pr_number=pr_meta["pr_number"],
                installation_id=pr_meta["installation_id"],
            )

            logger.info("Fetched changes", num_files=len(changes))

            return {
                "changes": changes,
                "error": None,
            }

        except Exception as e:
            logger.error("Error fetching PR changes", error=str(e))
            return {
                "error": f"Failed to fetch PR changes: {str(e)}",
            }

    @timed_stage("analyze_code")
    def analyze_code(self, state: ReviewState) -> Dict[str, Any]:
        """Analyze code changes using AI."""
        logger.info("Analyzing code changes")

        try:
            if state.get("error"):
                return {}

            changes = state["changes"]
            if not changes:
                logger.info("No changes to review")
                return {
                    "analysis_complete": True,
                    "review_comments": [],
                }

            # Use AI to review the code, grounded in any retrieved context
            review_output = self.code_reviewer.review_changes(
                changes,
                retrieved_context=state.get("retrieved_context") or [],
            )
            review_comments = self.code_reviewer.convert_to_review_comments(
                review_output
            )

            logger.info(
                "Analysis complete",
                num_comments=len(review_comments),
                summary=review_output.summary,
            )

            return {
                "review_comments": review_comments,
                "analysis_complete": True,
            }

        except Exception as e:
            logger.error("Error analyzing code", error=str(e))
            return {
                "error": f"Failed to analyze code: {str(e)}",
                "analysis_complete": False,
            }

    @timed_stage("post_reviews")
    def post_reviews(self, state: ReviewState) -> Dict[str, Any]:
        """Post review comments to GitHub."""
        logger.info("Posting review comments")

        try:
            if state.get("error"):
                return {}

            pr_meta = state["pr_metadata"]
            review_comments = state.get("review_comments", [])

            if not review_comments:
                logger.info("No comments to post")

                # Post the "no issues found" summary via the CommitManager
                self.commit_manager.post_summary(pr_meta, build_clean_summary())

                return {"comments_posted": True}

            # Filter by severity if configured
            min_severity = self.settings.min_review_severity
            severity_order = {"low": 0, "medium": 1, "high": 2}
            min_level = severity_order.get(min_severity, 0)

            filtered_comments = [
                c
                for c in review_comments
                if severity_order.get(c["severity"], 0) >= min_level
            ]

            logger.info(
                "Filtered comments",
                total=len(review_comments),
                filtered=len(filtered_comments),
            )

            # Post each comment
            posted_count = 0
            for comment in filtered_comments:
                try:
                    # Format the comment body
                    severity_emoji = {
                        "low": "ℹ️",
                        "medium": "⚠️",
                        "high": "🚨",
                    }
                    category_emoji = {
                        "bug": "🐛",
                        "security": "🔒",
                        "performance": "⚡",
                        "style": "🎨",
                        "best-practice": "✨",
                    }

                    emoji = severity_emoji.get(comment["severity"], "💡")
                    cat_emoji = category_emoji.get(comment["category"], "📝")

                    comment_body = f"""{emoji} **{comment['severity'].upper()}** {cat_emoji} **{comment['category'].replace('-', ' ').title()}**

{comment['message']}

**Suggestion:**
{comment.get('suggestion', 'N/A')}

---
*Generated by AI Code Review Agent*
"""

                    self.commit_manager.post_inline_comment(
                        pr_meta,
                        file_path=comment["file_path"],
                        line_number=comment["line_number"],
                        body=comment_body,
                    )
                    posted_count += 1

                except Exception as e:
                    logger.warning(
                        "Failed to post comment",
                        file=comment["file_path"],
                        line=comment["line_number"],
                        error=str(e),
                    )

            # Post a polished summary comment
            self.commit_manager.post_summary(
                pr_meta, build_review_summary(filtered_comments)
            )

            logger.info("Posted comments", count=posted_count)

            return {"comments_posted": True}

        except Exception as e:
            logger.error("Error posting reviews", error=str(e))
            return {
                "error": f"Failed to post reviews: {str(e)}",
                "comments_posted": False,
            }

    @timed_stage("update_status")
    def update_status(self, state: ReviewState) -> Dict[str, Any]:
        """Update PR status with labels."""
        logger.info("Updating PR status")

        try:
            if state.get("error"):
                return {}

            pr_meta = state["pr_metadata"]

            # Add "AI review complete" label via the CommitManager
            if self.settings.auto_label_on_complete:
                self.commit_manager.add_label(
                    pr_meta, self.settings.ai_review_complete_label
                )

                # If no comments or all low severity, add "ready for approval"
                review_comments = state.get("review_comments", [])
                has_high_severity = any(
                    c["severity"] == "high" for c in review_comments
                )

                if not has_high_severity:
                    self.commit_manager.add_label(
                        pr_meta, self.settings.ready_for_approval_label
                    )
                    logger.info("Added ready-for-approval label")

            return {"ready_for_approval": True}

        except Exception as e:
            logger.error("Error updating status", error=str(e))
            return {"error": f"Failed to update status: {str(e)}"}

    def run(self, pr_metadata: Dict[str, Any]) -> ReviewState:
        """Run the workflow for a PR."""
        logger.info("Starting review workflow", pr_metadata=pr_metadata)

        initial_state: ReviewState = {
            "pr_metadata": pr_metadata,
            "changes": [],
            "retrieved_context": [],
            "review_comments": [],
            "analysis_complete": False,
            "comments_posted": False,
            "all_resolved": False,
            "ready_for_approval": False,
            "error": None,
        }

        result = self.graph.invoke(initial_state)
        
        logger.info("Workflow complete", has_error=bool(result.get("error")))
        
        return result
