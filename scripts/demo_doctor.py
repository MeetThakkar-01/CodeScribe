"""Pre-check for the CodeScribe demo

It tells you which environment variables are set, 
which are missing, and which optional integrations
are wired up.

Usage:
    .venv/bin/python scripts/demo_doctor.py
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
DIM = "\033[2m"
RESET = "\033[0m"

REQUIRED = [
    ("GITHUB_APP_ID", "GitHub App authentication"),
    ("GITHUB_PRIVATE_KEY_PATH", "Path to GitHub App .pem file"),
    ("GITHUB_WEBHOOK_SECRET", "Verifies incoming webhooks"),
    ("GOOGLE_API_KEY", "Powers Gemini-based agents"),
]

OPTIONAL = [
    ("PINECONE_API_KEY", "Vector retrieval (RAG)"),
    ("PINECONE_INDEX_NAME", "Vector retrieval (RAG)"),
    ("JIRA_BASE_URL", "Jira ticketing demo"),
    ("JIRA_EMAIL", "Jira ticketing demo"),
    ("JIRA_API_TOKEN", "Jira ticketing demo"),
    ("JIRA_PROJECT_KEY", "Jira ticketing demo"),
    ("LANGSMITH_API_KEY", "LangSmith tracing"),
    ("LANGCHAIN_TRACING_V2", "LangSmith tracing"),
    ("LANGSMITH_PROJECT", "LangSmith tracing"),
    ("GITHUB_PAT", "Required by scripts/demo_seed.py to open the buggy PR"),
    ("DEMO_REPO", "Required by scripts/demo_seed.py — owner/name of the demo repo"),
]


def _ok(label: str, note: str = "") -> None:
    print(f"  {GREEN}[OK]{RESET} {label}{DIM}  {note}{RESET}".rstrip())


def _miss(label: str, note: str = "") -> None:
    print(f"  {RED}[MISSING]{RESET} {label}{DIM}  {note}{RESET}".rstrip())


def _warn(label: str, note: str = "") -> None:
    print(f"  {YELLOW}[OPTIONAL]{RESET} {label}{DIM}  {note}{RESET}".rstrip())


def check_env() -> bool:
    print(f"\n{DIM}===== Environment variables ====={RESET}")
    all_required_ok = True
    for name, desc in REQUIRED:
        value = os.getenv(name)
        if value:
            _ok(name, f"({desc})")
        else:
            _miss(name, f"({desc})")
            all_required_ok = False

    print()
    for name, desc in OPTIONAL:
        value = os.getenv(name)
        if value:
            _ok(name, f"({desc})")
        else:
            _warn(name, f"not set — {desc} will be skipped")
    return all_required_ok


def check_imports() -> bool:
    print(f"\n{DIM}===== Required Python packages ====={RESET}")
    required = [
        ("langgraph", "Workflow orchestration"),
        ("langchain_google_genai", "Gemini integration"),
        ("github", "GitHub API client"),
        ("structlog", "Structured logging"),
        ("fastapi", "Webhook server"),
        ("httpx", "Jira HTTP client"),
    ]
    optional = [
        ("pinecone", "Vector store — install if doing RAG demo"),
    ]
    all_ok = True
    for mod, desc in required:
        try:
            __import__(mod)
            _ok(mod, f"({desc})")
        except ImportError:
            _miss(mod, f"({desc}) — install with `pip install {mod.replace('_', '-')}`")
            all_ok = False

    print()
    for mod, desc in optional:
        try:
            __import__(mod)
            _ok(mod, f"({desc})")
        except ImportError:
            _warn(mod, f"not installed — {desc}")
    return all_ok


def check_private_key() -> bool:
    print(f"\n{DIM}===== GitHub App private key ====={RESET}")
    path = os.getenv("GITHUB_PRIVATE_KEY_PATH")
    if not path:
        _miss("GITHUB_PRIVATE_KEY_PATH not set; skipping file check")
        return False
    if not os.path.exists(path):
        _miss(f"file does not exist at {path}")
        return False
    if not os.path.isfile(path):
        _miss(f"{path} is not a regular file")
        return False
    _ok(f"{path} exists and is readable")
    return True


def main() -> int:
    print(f"\n{GREEN}CodeScribe demo doctor{RESET}\n")
    load_dotenv()

    env_ok = check_env()
    pkg_ok = check_imports()
    key_ok = check_private_key()

    print(f"\n{DIM}===== Summary ====={RESET}")
    if env_ok and pkg_ok and key_ok:
        print(f"  {GREEN}Ready to demo.{RESET}")
        return 0
    print(f"  {YELLOW}Some required items are missing — fix before demo.{RESET}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
