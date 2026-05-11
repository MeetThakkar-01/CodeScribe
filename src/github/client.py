"""GitHub API client for interacting with repositories and pull requests."""

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import jwt
import structlog
from github import Github, GithubIntegration, Auth
from github.PullRequest import PullRequest
from github.Repository import Repository

from src.config import get_settings
from src.workflow.state import CodeChange, PRMetadata

logger = structlog.get_logger()

# Refresh the installation token if it has fewer than this many seconds left.
# GitHub installation tokens have a 1-hour TTL; refreshing slightly before
# expiry guarantees a slow downstream operation cannot outlive its credentials.
_TOKEN_TTL_REFRESH_THRESHOLD_SECONDS = 60


class GitHubClient:
    """Client for GitHub API operations.

    The installation token cache tracks the expiry timestamp returned by
    GitHub's ``get_access_token`` call, then proactively refreshes the token
    when fewer than :py:data:`_TOKEN_TTL_REFRESH_THRESHOLD_SECONDS` remain.
    The behavior is captured in Appendix H of the system report.
    """

    def __init__(self):
        """Initialize the GitHub client."""
        self.settings = get_settings()
        self._integration: Optional[GithubIntegration] = None
        # Per-installation cache: (Github instance, token string, expires_at UTC)
        self._token_cache: Dict[int, Tuple[Github, str, datetime]] = {}

    def _get_integration(self) -> GithubIntegration:
        """Get or create GitHub integration."""
        if self._integration is None:
            auth = Auth.AppAuth(
                self.settings.github_app_id,
                self.settings.github_private_key,
            )
            self._integration = GithubIntegration(auth=auth)
        return self._integration

    def _get_or_refresh_installation(
        self, installation_id: int
    ) -> Tuple[Github, str, datetime]:
        """Return a still-valid cached entry, or refresh the token and re-cache."""
        cached = self._token_cache.get(installation_id)
        if cached is not None:
            github, token, expires_at = cached
            ttl = (expires_at - datetime.now(timezone.utc)).total_seconds()
            if ttl > _TOKEN_TTL_REFRESH_THRESHOLD_SECONDS:
                return cached
            logger.warning(
                "GitHub installation token nearing expiration",
                installation_id=installation_id,
                ttl_seconds=int(ttl),
            )
        return self._refresh_installation_token(installation_id)

    def _refresh_installation_token(
        self, installation_id: int
    ) -> Tuple[Github, str, datetime]:
        """Issue a fresh installation token and update the cache."""
        logger.info(
            "Refreshing GitHub installation token",
            installation_id=installation_id,
        )
        start = time.perf_counter()
        integration = self._get_integration()
        auth = integration.get_access_token(installation_id)

        expires_at = auth.expires_at
        # PyGithub may return a tz-naive datetime; normalize to UTC.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        github = Github(auth.token)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "Token refreshed successfully",
            installation_id=installation_id,
            latency_ms=latency_ms,
        )

        cached = (github, auth.token, expires_at)
        self._token_cache[installation_id] = cached
        return cached

    def _get_github_for_installation(self, installation_id: int) -> Github:
        """Get an authenticated GitHub instance for an installation.

        Reuses the cached instance while the token has comfortable TTL;
        otherwise refreshes proactively.
        """
        github, _, _ = self._get_or_refresh_installation(installation_id)
        return github

    def get_installation_token(self, installation_id: int) -> str:
        """Return a still-valid installation access token for the GitHub App.

        The first call acquires a fresh token; subsequent calls return the
        cached token until its TTL drops below the refresh threshold, at
        which point a new token is fetched.
        """
        _, token, _ = self._get_or_refresh_installation(installation_id)
        return token

    def get_pr(
        self, owner: str, repo: str, pr_number: int, installation_id: int
    ) -> PullRequest:
        """Get a pull request."""
        github = self._get_github_for_installation(installation_id)
        repository = github.get_repo(f"{owner}/{repo}")
        return repository.get_pull(pr_number)

    def get_pr_diff(
        self, owner: str, repo: str, pr_number: int, installation_id: int
    ) -> List[CodeChange]:
        """Fetch the diff for a pull request."""
        pr = self.get_pr(owner, repo, pr_number, installation_id)
        changes = []

        for file in pr.get_files():
            # Determine language from file extension
            language = self._get_language_from_filename(file.filename)

            changes.append(
                CodeChange(
                    file_path=file.filename,
                    diff=file.patch or "",
                    language=language,
                    additions=file.additions,
                    deletions=file.deletions,
                )
            )

        return changes

    def post_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        installation_id: int,
        file_path: str,
        line_number: int,
        comment_body: str,
    ) -> None:
        """Post a review comment on a specific line."""
        pr = self.get_pr(owner, repo, pr_number, installation_id)
        
        # Get the latest commit
        commits = list(pr.get_commits())
        if not commits:
            raise ValueError("No commits found in PR")
        
        latest_commit = commits[-1]

        # Create review comment
        pr.create_review_comment(
            body=comment_body,
            commit=latest_commit,
            path=file_path,
            line=line_number,
        )

    def post_pr_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        installation_id: int,
        comment_body: str,
    ) -> None:
        """Post a general comment on the PR."""
        pr = self.get_pr(owner, repo, pr_number, installation_id)
        pr.create_issue_comment(comment_body)

    def add_label(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        installation_id: int,
        label: str,
    ) -> None:
        """Add a label to the PR."""
        pr = self.get_pr(owner, repo, pr_number, installation_id)
        
        # Ensure label exists in the repository
        github = self._get_github_for_installation(installation_id)
        repository = github.get_repo(f"{owner}/{repo}")
        
        try:
            repository.get_label(label)
        except:
            # Create label if it doesn't exist
            repository.create_label(
                name=label,
                color="0E8A16",  # Green color
                description="Added by AI code review agent"
            )
        
        pr.add_to_labels(label)

    def check_comment_resolution(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        installation_id: int,
    ) -> bool:
        """Check if all review comments are resolved."""
        pr = self.get_pr(owner, repo, pr_number, installation_id)
        
        # Get all review comments
        comments = pr.get_review_comments()
        
        # Check if any comments are unresolved
        # Note: GitHub doesn't have a direct "resolved" status via API
        # This is a simplified check - in production, you might track this differently
        for comment in comments:
            # If comment has replies, consider it as being addressed
            # This is a heuristic - you might want to implement more sophisticated logic
            if comment.in_reply_to_id is None:
                # Original comment with no replies might be unresolved
                # You could also check comment body for specific markers
                pass
        
        # For now, return True if there are no comments or implement your logic
        return True

    @staticmethod
    def _get_language_from_filename(filename: str) -> Optional[str]:
        """Determine programming language from filename."""
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".sh": "bash",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
            ".sql": "sql",
        }

        for ext, lang in extension_map.items():
            if filename.endswith(ext):
                return lang

        return None
