"""GitHub webhook handler using FastAPI."""

import hashlib
import hmac
import structlog
from typing import Any, Dict

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.workflow.review_graph import PRReviewWorkflow
from src.workflow.state import PRMetadata

logger = structlog.get_logger()

app = FastAPI(title="GitHub PR Review Agent")
workflow = None  # Will be initialized on startup


@app.on_event("startup")
async def startup_event():
    """Initialize the workflow on startup."""
    global workflow
    workflow = PRReviewWorkflow()
    logger.info("Workflow initialized")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "GitHub PR Review Agent"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle GitHub webhook events."""
    settings = get_settings()

    # Verify webhook signature
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

    # Parse the event
    event_type = request.headers.get("X-GitHub-Event")
    payload = await request.json()

    logger.info("Received webhook", event_type=event_type)

    # Handle pull request events
    if event_type == "pull_request":
        action = payload.get("action")
        
        # Only process when PR is opened or reopened
        if action in ["opened", "reopened", "synchronize"]:
            pr_data = payload["pull_request"]
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

            # Run the workflow in the background
            background_tasks.add_task(run_review_workflow, pr_metadata)

            return JSONResponse(
                content={"status": "accepted", "message": "Review workflow started"}
            )

    return JSONResponse(content={"status": "ignored", "event": event_type})


def run_review_workflow(pr_metadata: PRMetadata):
    """Run the review workflow (executed in background)."""
    try:
        logger.info("Starting background review", pr_number=pr_metadata["pr_number"])
        result = workflow.run(pr_metadata)
        
        if result.get("error"):
            logger.error("Workflow failed", error=result["error"])
        else:
            logger.info("Review completed successfully")
            
    except Exception as e:
        logger.error("Unexpected error in workflow", error=str(e), exc_info=True)


def create_app() -> FastAPI:
    """Create and return the FastAPI app."""
    return app
