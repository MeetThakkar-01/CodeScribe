"""State definition for the supervisor (parent) graph."""

from typing import List, Optional, TypedDict

from src.agents.documentation.state import DocState
from src.agents.ticketing.state import TicketingState
from src.workflow.state import PRMetadata, ReviewState


class SupervisorState(TypedDict):
    """Shared state passed through the supervisor graph.

    Per-agent substate slots are populated by the corresponding subgraph
    wrapper. Only one slot is populated per run (review or docs), but the
    schema is forward-compatible with adding a third agent.
    """

    # Shared context populated by the webhook handler
    event_type: str  # "pr_opened" | "pr_merged" | "manual_docs"
    run_id: str
    repo_owner: str
    repo_name: str
    installation_id: int
    pr_metadata: Optional[PRMetadata]

    # Per-agent substate slots
    review_substate: Optional[ReviewState]
    docs_substate: Optional[DocState]
    ticketing_substate: Optional[TicketingState]

    # Routing decision and bookkeeping
    next_agent: Optional[str]  # "review" | "docs" | "end"
    completed_agents: List[str]
    error: Optional[str]
