"""LangGraph subgraph wrapping the legacy DocumentationAgent."""

import os
from typing import Any, Dict

import structlog
from langgraph.graph import END, StateGraph

from src.agents.documentation.legacy_agent import DocumentationAgent
from src.agents.documentation.state import DocState
from src.config import get_settings
from src.github.client import GitHubClient
from src.workflow.timing import timed_stage

logger = structlog.get_logger()


def _cache_path(state: DocState) -> str:
    """Per-repo cache path under the configured cache directory."""
    settings = get_settings()
    os.makedirs(settings.doc_cache_dir, exist_ok=True)
    safe = f"{state['repo_owner']}-{state['repo_name']}.json"
    return os.path.join(settings.doc_cache_dir, safe)


def _build_doc_agent(state: DocState) -> DocumentationAgent:
    """Construct a DocumentationAgent using the GitHub App installation token.

    The token is short-lived (1 hour). Each node calls this fresh so a slow
    generation step doesn't outlive its credentials.
    """
    settings = get_settings()
    token = GitHubClient().get_installation_token(state["installation_id"])
    agent = DocumentationAgent(
        repo_name=f"{state['repo_owner']}/{state['repo_name']}",
        github_token=token,
        gemini_api_key=settings.google_api_key,
    )
    agent.cache_file = _cache_path(state)
    agent.model_name = settings.gemini_docs_model
    return agent


class DocumentationWorkflow:
    """Documentation subgraph: cache → fetch → detect → generate → commit → save."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self):
        g = StateGraph(DocState)

        g.add_node("load_cache", self.load_cache)
        g.add_node("fetch_repo_structure", self.fetch_repo_structure)
        g.add_node("detect_changes", self.detect_changes)
        g.add_node("generate_docs", self.generate_docs)
        g.add_node("commit_readme", self.commit_readme)
        g.add_node("save_cache", self.save_cache)

        g.set_entry_point("load_cache")
        g.add_edge("load_cache", "fetch_repo_structure")
        g.add_edge("fetch_repo_structure", "detect_changes")
        g.add_edge("detect_changes", "generate_docs")

        g.add_conditional_edges(
            "generate_docs",
            self._needs_commit,
            {"commit": "commit_readme", "skip": "save_cache"},
        )
        g.add_edge("commit_readme", "save_cache")
        g.add_edge("save_cache", END)

        return g.compile()

    @staticmethod
    def _needs_commit(state: DocState) -> str:
        if state.get("error"):
            return "skip"
        return "commit" if state.get("new_readme") else "skip"

    @timed_stage("load_cache")
    def load_cache(self, state: DocState) -> Dict[str, Any]:
        try:
            agent = _build_doc_agent(state)
            return {"cached_structure": agent.load_cache(), "error": None}
        except Exception as e:
            logger.error("doc.load_cache failed", error=str(e))
            return {"cached_structure": {}, "error": f"load_cache: {e}"}

    @timed_stage("fetch_repo_structure")
    def fetch_repo_structure(self, state: DocState) -> Dict[str, Any]:
        if state.get("error"):
            return {}
        try:
            agent = _build_doc_agent(state)
            return {
                "current_structure": agent.get_repo_structure(),
                "current_readme": agent.get_current_readme(),
            }
        except Exception as e:
            logger.error("doc.fetch_repo_structure failed", error=str(e))
            return {"error": f"fetch_repo_structure: {e}"}

    @timed_stage("detect_changes")
    def detect_changes(self, state: DocState) -> Dict[str, Any]:
        if state.get("error"):
            return {}
        try:
            agent = _build_doc_agent(state)
            cached = state.get("cached_structure") or {}
            current = state.get("current_structure") or {}
            if not cached:
                return {"changes": None}
            changes = agent.analyze_changes(cached, current)
            return {"changes": changes}
        except Exception as e:
            logger.error("doc.detect_changes failed", error=str(e))
            return {"error": f"detect_changes: {e}"}

    @timed_stage("generate_docs")
    def generate_docs(self, state: DocState) -> Dict[str, Any]:
        if state.get("error"):
            return {}
        try:
            agent = _build_doc_agent(state)
            new_readme = agent.generate_documentation(
                state.get("current_structure") or {},
                state.get("current_readme") or "",
                state.get("changes"),
            )
            return {"new_readme": new_readme}
        except Exception as e:
            logger.error("doc.generate_docs failed", error=str(e))
            return {"error": f"generate_docs: {e}", "new_readme": None}

    @timed_stage("commit_readme")
    def commit_readme(self, state: DocState) -> Dict[str, Any]:
        if state.get("error") or not state.get("new_readme"):
            return {"readme_updated": False}
        try:
            agent = _build_doc_agent(state)  # fresh installation token
            ok = agent.update_readme(state["new_readme"])
            return {"readme_updated": bool(ok)}
        except Exception as e:
            logger.error("doc.commit_readme failed", error=str(e))
            return {"error": f"commit_readme: {e}", "readme_updated": False}

    @timed_stage("save_cache")
    def save_cache(self, state: DocState) -> Dict[str, Any]:
        try:
            agent = _build_doc_agent(state)
            agent.save_cache(state.get("current_structure") or {})
            return {}
        except Exception as e:
            logger.error("doc.save_cache failed", error=str(e))
            return {"error": f"save_cache: {e}"}
