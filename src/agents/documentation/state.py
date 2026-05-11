"""State definitions for the documentation subgraph."""

from typing import Any, Dict, List, Optional, TypedDict


class RepoChanges(TypedDict):
    """Files added/modified/deleted relative to the cached structure."""

    added: List[str]
    modified: List[str]
    deleted: List[str]


class DocState(TypedDict):
    """State for the documentation subgraph."""

    # Inputs from the supervisor
    repo_owner: str
    repo_name: str
    installation_id: int

    # Repository snapshot
    cached_structure: Dict[str, Any]
    current_structure: Dict[str, Any]
    current_readme: str

    # Outputs of analysis / generation
    changes: Optional[RepoChanges]
    new_readme: Optional[str]  # None means "NO_UPDATE_NEEDED"
    readme_updated: bool

    # Error tracking
    error: Optional[str]
