"""Markdown summary template for the AI code-review PR comment.

This is the top-level summary that appears once per PR (alongside the inline
comments). Kept in its own module so the formatting logic is testable in
isolation from the LangGraph workflow and the GitHub-posting layer.
"""

from typing import Dict, List

from src.workflow.state import ReviewComment


_CATEGORY_EMOJI = {
    "bug": "🐛",
    "security": "🔒",
    "performance": "⚡",
    "style": "🎨",
    "best-practice": "✨",
}


def build_clean_summary() -> str:
    """Summary posted when no findings were produced."""
    return (
        "## ✅ CodeScribe AI Review\n"
        "\n"
        "**No issues found.** The Code Review Agent analyzed all changes and did "
        "not flag any bugs, security issues, performance problems, or style concerns.\n"
        "\n"
        "This PR is ready for human approval.\n"
        "\n"
        "---\n"
        "*Reviewed by CodeScribe.*"
    )


def build_review_summary(comments: List[ReviewComment]) -> str:
    """Summary posted when at least one finding was produced.

    The shape:
      - branded heading
      - explicit callout if any high-severity findings exist
      - one-line totals
      - severity breakdown table
      - category breakdown
      - top-N files by finding count (only when more than one file is affected)
      - footer prompting the developer to address the inline comments
    """
    if not comments:
        return build_clean_summary()

    counts_by_severity: Dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    files: Dict[str, int] = {}
    categories: Dict[str, int] = {}
    for c in comments:
        counts_by_severity[c["severity"]] = counts_by_severity.get(c["severity"], 0) + 1
        files[c["file_path"]] = files.get(c["file_path"], 0) + 1
        categories[c["category"]] = categories.get(c["category"], 0) + 1

    lines: List[str] = ["## 🤖 CodeScribe AI Review", ""]

    high = counts_by_severity.get("high", 0)
    if high:
        word = "finding" if high == 1 else "findings"
        lines.append(
            f"> ⚠️ **Action required:** {high} high-severity {word}. "
            "See inline comments below."
        )
        lines.append("")

    issue_word = "issue" if len(comments) == 1 else "issues"
    file_word = "file" if len(files) == 1 else "files"
    lines.append(f"**Summary:** {len(comments)} {issue_word} across {len(files)} {file_word}.")
    lines.append("")

    # Severity table — only include rows that have at least one finding.
    lines.append("| Severity | Count |")
    lines.append("|:---------|:------|")
    if counts_by_severity.get("high"):
        lines.append(f"| 🚨 High | {counts_by_severity['high']} |")
    if counts_by_severity.get("medium"):
        lines.append(f"| ⚠️ Medium | {counts_by_severity['medium']} |")
    if counts_by_severity.get("low"):
        lines.append(f"| ℹ️ Low | {counts_by_severity['low']} |")
    lines.append("")

    # Category breakdown, ordered by count descending.
    if categories:
        lines.append("**By category:**")
        for cat, count in sorted(categories.items(), key=lambda kv: -kv[1]):
            emoji = _CATEGORY_EMOJI.get(cat, "📝")
            label = cat.replace("-", " ").title()
            lines.append(f"- {emoji} {label}: {count}")
        lines.append("")

    # Top files — only show this section when more than one file has findings.
    if len(files) > 1:
        lines.append("**Files with the most findings:**")
        top = sorted(files.items(), key=lambda kv: -kv[1])[:3]
        for fp, count in top:
            iw = "issue" if count == 1 else "issues"
            lines.append(f"- `{fp}` — {count} {iw}")
        lines.append("")

    lines.append("---")
    lines.append(
        "*Inline comments above contain the specific findings and suggested fixes. "
        "Address the items, push a fix, and CodeScribe will re-review automatically.*"
    )

    return "\n".join(lines)
