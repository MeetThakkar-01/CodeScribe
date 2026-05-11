"""State definition for the Jira ticketing subgraph."""

from typing import Any, Dict, List, Optional, TypedDict

from src.workflow.state import ReviewComment


class TicketingState(TypedDict):
    """State for the ticketing subgraph.

    Inputs are populated by the supervisor wrapper from the review substate;
    outputs accumulate as the graph runs.
    """

    # Inputs from the supervisor
    repo_owner: str
    repo_name: str
    pr_number: int
    review_comments: List[ReviewComment]

    # Pipeline outputs
    issues_to_create: List[Dict[str, Any]]
    created_issue_keys: List[str]
    error: Optional[str]
