"""Tests for the PR-summary markdown template."""

from src.agents.review_summary import build_clean_summary, build_review_summary
from src.workflow.state import ReviewComment


def _comment(severity, category="bug", file_path="src/x.py", line=1) -> ReviewComment:
    return {
        "file_path": file_path,
        "line_number": line,
        "severity": severity,
        "category": category,
        "message": "issue text",
        "suggestion": "fix it",
        "resolved": False,
    }


class TestCleanSummary:
    def test_no_comments_returns_clean_summary(self):
        out = build_review_summary([])
        assert out == build_clean_summary()
        assert "No issues found" in out
        assert "ready for human approval" in out

    def test_clean_summary_has_branding(self):
        out = build_clean_summary()
        assert "CodeScribe" in out


class TestSeverityCallout:
    def test_high_severity_triggers_action_required_callout(self):
        out = build_review_summary([_comment("high")])
        assert "Action required" in out
        assert "1 high-severity finding" in out

    def test_no_high_severity_omits_callout(self):
        out = build_review_summary([_comment("medium"), _comment("low")])
        assert "Action required" not in out

    def test_multiple_high_severity_pluralizes(self):
        out = build_review_summary([_comment("high"), _comment("high", line=2)])
        assert "2 high-severity findings" in out


class TestSeverityTable:
    def test_only_includes_severities_with_findings(self):
        out = build_review_summary([_comment("high"), _comment("low")])
        assert "🚨 High | 1" in out
        assert "ℹ️ Low | 1" in out
        assert "Medium" not in out  # no medium findings; row omitted

    def test_counts_are_correct(self):
        comments = [
            _comment("high"),
            _comment("medium"),
            _comment("medium", line=2),
            _comment("low"),
            _comment("low", line=3),
            _comment("low", line=4),
        ]
        out = build_review_summary(comments)
        assert "🚨 High | 1" in out
        assert "⚠️ Medium | 2" in out
        assert "ℹ️ Low | 3" in out


class TestCategoryBreakdown:
    def test_categories_listed_with_emojis(self):
        comments = [
            _comment("high", category="security"),
            _comment("low", category="style"),
            _comment("medium", category="bug"),
        ]
        out = build_review_summary(comments)
        assert "🔒 Security" in out
        assert "🎨 Style" in out
        assert "🐛 Bug" in out

    def test_categories_ordered_by_count(self):
        comments = [
            _comment("low", category="style"),
            _comment("low", category="style", line=2),
            _comment("medium", category="bug"),
        ]
        out = build_review_summary(comments)
        # The "Style" line must appear before "Bug" since 2 > 1
        style_idx = out.index("Style: 2")
        bug_idx = out.index("Bug: 1")
        assert style_idx < bug_idx


class TestTopFiles:
    def test_section_omitted_when_only_one_file(self):
        comments = [
            _comment("high", file_path="src/auth.py"),
            _comment("low", file_path="src/auth.py", line=2),
        ]
        out = build_review_summary(comments)
        assert "Files with the most findings" not in out

    def test_section_present_when_multiple_files(self):
        comments = [
            _comment("high", file_path="src/auth.py"),
            _comment("low", file_path="src/auth.py", line=2),
            _comment("medium", file_path="src/api.py"),
        ]
        out = build_review_summary(comments)
        assert "Files with the most findings" in out
        assert "`src/auth.py`" in out
        assert "`src/api.py`" in out

    def test_caps_at_three_files(self):
        comments = [
            _comment("low", file_path=f"src/file{i}.py") for i in range(5)
        ]
        out = build_review_summary(comments)
        # Section header present, but only three files listed.
        assert "Files with the most findings" in out
        rendered_files = sum(1 for line in out.splitlines() if line.startswith("- `src/file"))
        assert rendered_files == 3


class TestPluralization:
    def test_singular_when_one_issue_one_file(self):
        out = build_review_summary([_comment("low")])
        assert "1 issue across 1 file" in out

    def test_plural_when_multiple(self):
        out = build_review_summary([
            _comment("low", file_path="a.py"),
            _comment("low", file_path="b.py"),
            _comment("low", file_path="c.py"),
        ])
        assert "3 issues across 3 files" in out
