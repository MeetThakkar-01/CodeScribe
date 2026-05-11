"""CommitManager — executes write-back actions after agent reasoning completes.

The CommitManager separates the orchestrator's reasoning steps from the
actions that write back to external systems. Every output action — inline
code review comments, PR summary comments, label additions — flows through
this class so the agents themselves stay free of GitHub-API details.
"""

from typing import Optional

import structlog

from src.github.client import GitHubClient
from src.workflow.state import PRMetadata

logger = structlog.get_logger()


class CommitManager:
    """Executes the final GitHub actions (comments, labels) for a PR run."""

    def __init__(self, github_client: Optional[GitHubClient] = None) -> None:
        self.github_client = github_client or GitHubClient()

    def post_inline_comment(
        self,
        pr_meta: PRMetadata,
        file_path: str,
        line_number: int,
        body: str,
    ) -> None:
        """Post a single inline review comment on a specific line."""
        logger.info(
            "commit_manager.post_inline_comment",
            pr_number=pr_meta["pr_number"],
            file_path=file_path,
            line_number=line_number,
        )
        self.github_client.post_review_comment(
            owner=pr_meta["repo_owner"],
            repo=pr_meta["repo_name"],
            pr_number=pr_meta["pr_number"],
            installation_id=pr_meta["installation_id"],
            file_path=file_path,
            line_number=line_number,
            comment_body=body,
        )

    def post_summary(self, pr_meta: PRMetadata, body: str) -> None:
        """Post a top-level PR summary comment."""
        logger.info(
            "commit_manager.post_summary",
            pr_number=pr_meta["pr_number"],
        )
        self.github_client.post_pr_comment(
            owner=pr_meta["repo_owner"],
            repo=pr_meta["repo_name"],
            pr_number=pr_meta["pr_number"],
            installation_id=pr_meta["installation_id"],
            comment_body=body,
        )

    def add_label(self, pr_meta: PRMetadata, label: str) -> None:
        """Add a label to the PR."""
        logger.info(
            "commit_manager.add_label",
            pr_number=pr_meta["pr_number"],
            label=label,
        )
        self.github_client.add_label(
            owner=pr_meta["repo_owner"],
            repo=pr_meta["repo_name"],
            pr_number=pr_meta["pr_number"],
            installation_id=pr_meta["installation_id"],
            label=label,
        )
