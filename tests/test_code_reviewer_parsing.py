"""Tests for the CodeReviewer's response-parsing path.

Gemini wraps its review response in a ```json ... ``` fence, AND often embeds
a ```python ... ``` code block inside one of the suggestion strings. The
parser must extract the outermost JSON object correctly even when the response
contains multiple triple-backtick markers.
"""

from unittest.mock import MagicMock

from src.workflow.state import CodeChange


def _reviewer_with_canned_response(content):
    """Build a CodeReviewer that returns `content` from its LLM call."""
    from src.agents.code_reviewer import CodeReviewer

    reviewer = CodeReviewer.__new__(CodeReviewer)
    reviewer.llm = MagicMock()
    reviewer.llm.invoke.return_value = MagicMock(content=content)
    reviewer.parser = MagicMock()
    return reviewer


def _one_change():
    return [
        CodeChange(
            file_path="x.py",
            diff="+def f(): pass",
            language="python",
            additions=1,
            deletions=0,
        )
    ]


class TestJsonExtraction:
    def test_parses_response_with_code_fence_and_inner_backticks(self):
        """The exact failure mode we saw in production."""
        content = '''```json
{
  "comments": [
    {
      "file_path": "x.py",
      "line_number": 1,
      "severity": "high",
      "category": "bug",
      "message": "Uses ^ instead of **",
      "suggestion": "Replace with:\\n```python\\nbase ** exp\\n```\\nNot XOR."
    }
  ],
  "summary": "One operator bug."
}
```'''
        reviewer = _reviewer_with_canned_response(content)
        out = reviewer.review_changes(_one_change())
        assert len(out.comments) == 1
        assert out.comments[0].severity == "high"
        assert out.summary == "One operator bug."

    def test_parses_bare_json_response(self):
        content = '{"comments": [], "summary": "Looks fine."}'
        reviewer = _reviewer_with_canned_response(content)
        out = reviewer.review_changes(_one_change())
        assert out.comments == []
        assert out.summary == "Looks fine."

    def test_parses_json_with_no_language_tag(self):
        content = '''```
{"comments": [], "summary": "ok"}
```'''
        reviewer = _reviewer_with_canned_response(content)
        out = reviewer.review_changes(_one_change())
        assert out.summary == "ok"

    def test_parses_json_with_text_around_it(self):
        content = '''Here is my review:

```json
{"comments": [], "summary": "All good."}
```

Hope that helps!'''
        reviewer = _reviewer_with_canned_response(content)
        out = reviewer.review_changes(_one_change())
        assert out.summary == "All good."

    def test_invalid_response_falls_back_to_empty_review(self):
        """When no JSON can be extracted, do not crash — summarize the error."""
        content = "I cannot help with that request."
        reviewer = _reviewer_with_canned_response(content)
        out = reviewer.review_changes(_one_change())
        assert out.comments == []
        assert "Error parsing review" in out.summary

    def test_handles_list_content_from_gemini(self):
        """Gemini sometimes returns content as a list of parts."""
        part = MagicMock()
        part.text = '{"comments": [], "summary": "list-content"}'
        reviewer = _reviewer_with_canned_response([part])
        out = reviewer.review_changes(_one_change())
        assert out.summary == "list-content"
