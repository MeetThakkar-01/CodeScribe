"""Pre-stage a demo pull request for the CodeScribe recording.

Creates a fresh branch on a target repository, adds a ``more_calc_ops`` Python
module containing several intentional bugs and code smells, and opens a pull
request. The Code Review Agent should flag the issues across multiple severity
levels; the Ticketing Agent escalates high-severity findings to Jira.

Bugs intentionally seeded into the new module, one per severity level:
    HIGH    ``compute_average()`` crashes on an empty list (ZeroDivisionError)
    MEDIUM  ``add_one_percent()`` adds literal 1 instead of 1% of x
    LOW     ``half()`` uses integer division and truncates fractions

Usage:
    .venv/bin/python scripts/demo_seed.py

Required env vars (add to .env):
    GITHUB_PAT      Personal Access Token with `repo` scope
    DEMO_REPO       Target repository in `owner/name`

Optional env vars:
    DEMO_PR_TITLE   PR title; defaults to "Add more calculator operations"
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from github import Auth, Github
from github.GithubException import GithubException


DEFAULT_PR_TITLE = "Add more calculator operations"

BUGGY_CODE = '''"""More calculator operations: averaging, percent adjustment, halving."""


def compute_average(numbers):
    """Return the arithmetic mean of a list of numbers."""
    return sum(numbers) / len(numbers)


def add_one_percent(x):
    """Add one percent to x."""
    return x + 1


def half(x):
    """Return half of x."""
    return x // 2
'''


def _err(msg: str) -> None:
    print(f"\033[91m[ERROR]\033[0m {msg}")


def _info(msg: str) -> None:
    print(f"\033[92m[OK]\033[0m {msg}")


def _step(msg: str) -> None:
    print(f"  {msg}")


def main() -> int:
    load_dotenv()

    pat = os.getenv("GITHUB_PAT")
    repo_name = os.getenv("DEMO_REPO")
    pr_title = os.getenv("DEMO_PR_TITLE", DEFAULT_PR_TITLE)

    if not pat:
        _err("GITHUB_PAT is not set in .env")
        _err("Create a token at https://github.com/settings/tokens with `repo` scope.")
        return 1
    if not repo_name or "/" not in repo_name:
        _err("DEMO_REPO must be set to `owner/name` (e.g. `acme/codescribe-demo`)")
        return 1

    suffix = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"feature/more-calc-ops-{suffix}"
    file_path = f"more_calc_ops_{suffix}.py"

    print()
    print(f"Seeding demo PR on \033[1m{repo_name}\033[0m...")
    print(f"  branch : {branch_name}")
    print(f"  file   : {file_path}")
    print(f"  title  : {pr_title}")
    print()

    try:
        github = Github(auth=Auth.Token(pat))
        repo = github.get_repo(repo_name)
    except GithubException as e:
        _err(f"Could not access repo {repo_name}: {e.data.get('message', e)}")
        return 1

    default_branch = repo.default_branch
    _info(f"Connected as PAT owner; default branch = {default_branch}")

    try:
        base_ref = repo.get_git_ref(f"heads/{default_branch}")
        base_sha = base_ref.object.sha
        _step(f"Base SHA on {default_branch}: {base_sha[:7]}")
    except GithubException as e:
        _err(f"Could not read default branch ref: {e}")
        return 1

    try:
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)
        _info(f"Created branch {branch_name}")
    except GithubException as e:
        _err(f"Could not create branch: {e.data.get('message', e)}")
        return 1

    pr_body = (
        "Demo pull request for the CodeScribe multi-agent system.\n\n"
        "Adds a new `more_calc_ops` module extending the calculator with "
        "averaging, percent adjustment, and halving operations. Three bugs are "
        "intentionally seeded — one each at high, medium, and low severity — "
        "for the Code Review Agent to flag. High-severity findings will be "
        "filed as new Jira tickets by the Ticketing Agent."
    )

    try:
        repo.create_file(
            path=file_path,
            message="Add more calculator operations module",
            content=BUGGY_CODE,
            branch=branch_name,
        )
        _info(f"Committed {file_path} on {branch_name}")
    except GithubException as e:
        _err(f"Could not create file: {e.data.get('message', e)}")
        return 1

    try:
        pr = repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=branch_name,
            base=default_branch,
        )
        _info(f"Opened PR #{pr.number}: {pr.html_url}")
    except GithubException as e:
        _err(f"Could not open PR: {e.data.get('message', e)}")
        return 1

    print()
    print(f"\033[92mDemo PR is live.\033[0m")
    print(f"  {pr.html_url}")
    print()
    print("Watch your CodeScribe webhook handler — the supervisor should fire within seconds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
