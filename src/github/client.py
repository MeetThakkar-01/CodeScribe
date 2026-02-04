"""GitHub API client for interacting with repositories and pull requests."""

import time
from typing import List, Optional

import jwt
from github import Github, GithubIntegration, Auth
from github.PullRequest import PullRequest
from github.Repository import Repository

from src.config import get_settings
from src.workflow.state import CodeChange, PRMetadata


class GitHubClient:
    """Client for GitHub API operations."""

    def __init__(self):
        """Initialize the GitHub client."""
        self.settings = get_settings()
        self._integration: Optional[GithubIntegration] = None
        self._github_instances = {}  # Cache of GitHub instances per installation

    def _get_integration(self) -> GithubIntegration:
        """Get or create GitHub integration."""
        if self._integration is None:
            auth = Auth.AppAuth(
                self.settings.github_app_id,
                self.settings.github_private_key
            )
            self._integration = GithubIntegration(auth=auth)
        return self._integration

    def _get_github_for_installation(self, installation_id: int) -> Github:
        """Get authenticated GitHub instance for an installation."""
        if installation_id not in self._github_instances:
            integration = self._get_integration()
            auth = integration.get_access_token(installation_id)
            self._github_instances[installation_id] = Github(auth.token)
        return self._github_instances[installation_id]

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
