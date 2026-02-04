"""State definitions for the LangGraph workflow."""

from typing import Annotated, List, Optional, TypedDict

from langgraph.graph import add_messages


class CodeChange(TypedDict):
    """Represents a code change in a file."""

    file_path: str
    diff: str
    language: Optional[str]
    additions: int
    deletions: int


class ReviewComment(TypedDict):
    """Represents a review comment on code."""

    file_path: str
    line_number: int
    severity: str  # "low", "medium", "high"
    category: str  # "bug", "security", "performance", "style", "best-practice"
    message: str
    suggestion: Optional[str]
    resolved: bool


class PRMetadata(TypedDict):
    """Metadata about the pull request."""

    repo_owner: str
    repo_name: str
    pr_number: int
    pr_title: str
    pr_author: str
    base_branch: str
    head_branch: str
    installation_id: int  # GitHub App installation ID


class ReviewState(TypedDict):
    """Main state for the review workflow."""

    # PR Information
    pr_metadata: PRMetadata
    
    # Code changes
    changes: List[CodeChange]
    
    # Review comments
    review_comments: List[ReviewComment]
    
    # Status tracking
    analysis_complete: bool
    comments_posted: bool
    all_resolved: bool
    ready_for_approval: bool
    
    # Error tracking
    error: Optional[str]
