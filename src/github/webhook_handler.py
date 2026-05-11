"""GitHub webhook handler using FastAPI."""

import hashlib
import hmac
import uuid
from typing import Any, Dict, Optional

import structlog
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.workflow.state import PRMetadata
from src.workflow.supervisor_graph import CodeScribeOrchestrator
from src.workflow.supervisor_state import SupervisorState

logger = structlog.get_logger()

app = FastAPI(title="CodeScribe Multi-Agent Server")
workflow: Optional[CodeScribeOrchestrator] = None  # initialized on startup


@app.on_event("startup")
async def startup_event():
    """Initialize the orchestrator on startup."""
    global workflow
    workflow = CodeScribeOrchestrator()
    logger.info("CodeScribe orchestrator initialized")


@app.get("/")
async def root():
    return {"status": "ok", "service": "CodeScribe Multi-Agent Server"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle GitHub webhook events and dispatch to the supervisor graph."""
    settings = get_settings()

    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing signature")

    body = await request.body()
    expected_signature = (
        "sha256="
        + hmac.new(
            settings.github_webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
    )
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event_type = request.headers.get("X-GitHub-Event")
    payload = await request.json()
    logger.info("Received webhook", event_type=event_type)

    if event_type != "pull_request":
        return JSONResponse(content={"status": "ignored", "event": event_type})

    action = payload.get("action")
    pr = payload.get("pull_request", {}) or {}
    merged = pr.get("merged", False)
    base_ref = (pr.get("base") or {}).get("ref")

    if action in ("opened", "reopened", "synchronize"):
        state = _build_supervisor_state("pr_opened", payload)
        background_tasks.add_task(run_supervisor, state)
        return JSONResponse(
            content={"status": "accepted", "agent": "review", "run_id": state["run_id"]}
        )

    if action == "closed" and merged and base_ref == "main":
        state = _build_supervisor_state("pr_merged", payload)
        background_tasks.add_task(run_supervisor, state)
        return JSONResponse(
            content={"status": "accepted", "agent": "docs", "run_id": state["run_id"]}
        )

    return JSONResponse(content={"status": "ignored", "action": action})


def _build_supervisor_state(event_type: str, payload: Dict[str, Any]) -> SupervisorState:
    """Translate a GitHub webhook payload into the supervisor's initial state."""
    pr_data = payload.get("pull_request") or {}
    repo_data = payload["repository"]
    installation_id = payload["installation"]["id"]

    pr_metadata: PRMetadata = {
        "repo_owner": repo_data["owner"]["login"],
        "repo_name": repo_data["name"],
        "pr_number": pr_data["number"],
        "pr_title": pr_data["title"],
        "pr_author": pr_data["user"]["login"],
        "base_branch": pr_data["base"]["ref"],
        "head_branch": pr_data["head"]["ref"],
        "installation_id": installation_id,
    }

    state: SupervisorState = {
        "event_type": event_type,
        "run_id": uuid.uuid4().hex,
        "repo_owner": repo_data["owner"]["login"],
        "repo_name": repo_data["name"],
        "installation_id": installation_id,
        "pr_metadata": pr_metadata,
        "review_substate": None,
        "docs_substate": None,
        "next_agent": None,
        "completed_agents": [],
        "error": None,
    }
    return state


def run_supervisor(state: SupervisorState) -> None:
    """Invoke the supervisor graph (executed in a background task)."""
    try:
        logger.info(
            "Starting supervisor run",
            run_id=state["run_id"],
            event_type=state["event_type"],
        )
        result = workflow.graph.invoke(state)

        if result.get("error"):
            logger.error(
                "Supervisor run failed",
                run_id=state["run_id"],
                error=result["error"],
                completed=result.get("completed_agents", []),
            )
        else:
            logger.info(
                "Supervisor run completed",
                run_id=state["run_id"],
                completed=result.get("completed_agents", []),
            )
    except Exception as e:
        logger.error(
            "Unexpected error in supervisor run",
            run_id=state.get("run_id"),
            error=str(e),
            exc_info=True,
        )


def create_app() -> FastAPI:
    """Create and return the FastAPI app."""
    return app
