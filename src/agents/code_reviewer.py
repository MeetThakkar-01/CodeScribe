"""Code review agent using Google Gemini."""

from typing import List

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from src.config import get_settings
from src.workflow.state import CodeChange, ReviewComment


class ReviewCommentSchema(BaseModel):
    """Schema for a single review comment."""

    file_path: str = Field(description="Path to the file")
    line_number: int = Field(description="Line number in the diff (approximate)")
    severity: str = Field(description="Severity: low, medium, or high")
    category: str = Field(
        description="Category: bug, security, performance, style, or best-practice"
    )
    message: str = Field(description="Clear explanation of the issue")
    suggestion: str = Field(description="Suggested fix or improvement")


class ReviewOutput(BaseModel):
    """Schema for the complete review output."""

    comments: List[ReviewCommentSchema] = Field(
        description="List of review comments"
    )
    summary: str = Field(description="Overall summary of the review")


class CodeReviewer:
    """AI-powered code reviewer using Google Gemini."""

    def __init__(self):
        """Initialize the code reviewer."""
        settings = get_settings()
        self.llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=0.1,  # Low temperature for consistent reviews
        )
        self.parser = JsonOutputParser(pydantic_object=ReviewOutput)

    def review_changes(self, changes: List[CodeChange]) -> ReviewOutput:
        """Review code changes and generate comments."""
        
        # Build the code context
        code_context = self._build_code_context(changes)

        # Create the review prompt
        system_prompt = """You are an expert code reviewer. Analyze the provided code changes and identify:

1. **Bugs**: Logic errors, potential crashes, edge cases
2. **Security**: Vulnerabilities, unsafe operations, data exposure
3. **Performance**: Inefficiencies, unnecessary operations, optimization opportunities
4. **Style**: Code formatting, naming conventions, readability
5. **Best Practices**: Design patterns, maintainability, code organization

For each issue found:
- Specify the exact file and approximate line number
- Classify severity (low, medium, high)
- Provide a clear explanation
- Suggest a specific fix

Focus on meaningful issues. Don't nitpick trivial style issues unless they impact readability.
Be constructive and helpful in your feedback.

Return your analysis in JSON format matching this schema:
{
  "comments": [
    {
      "file_path": "path/to/file.py",
      "line_number": 42,
      "severity": "high",
      "category": "bug",
      "message": "Clear explanation of the issue",
      "suggestion": "Specific suggestion for fixing it"
    }
  ],
  "summary": "Overall assessment of the changes"
}
"""

        user_prompt = f"""Review the following code changes:

{code_context}

Provide your review in JSON format."""

        # Call the LLM
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        response = self.llm.invoke(messages)
        
        # Parse the response
        try:
            # Extract JSON from response
            content = response.content
            
            # Handle if content is a list (Gemini sometimes returns list of content parts)
            if isinstance(content, list):
                # Extract text from content parts
                content = " ".join([part.text if hasattr(part, 'text') else str(part) for part in content])
            
            # Try to parse as JSON
            import json
            
            # Find JSON in the response (handle markdown code blocks)
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            else:
                json_str = content.strip()
            
            parsed = json.loads(json_str)
            return ReviewOutput(**parsed)
            
        except Exception as e:
            # Fallback: return empty review with error in summary
            return ReviewOutput(
                comments=[],
                summary=f"Error parsing review: {str(e)}"
            )

    def _build_code_context(self, changes: List[CodeChange]) -> str:
        """Build a formatted string of code changes for the LLM."""
        context_parts = []

        for change in changes:
            context_parts.append(f"\n{'='*60}")
            context_parts.append(f"File: {change['file_path']}")
            context_parts.append(f"Language: {change.get('language', 'unknown')}")
            context_parts.append(f"Changes: +{change['additions']} -{change['deletions']}")
            context_parts.append(f"{'='*60}\n")
            
            if change['diff']:
                context_parts.append("```diff")
                context_parts.append(change['diff'])
                context_parts.append("```\n")
            else:
                context_parts.append("(Binary file or no diff available)\n")

        return "\n".join(context_parts)

    def convert_to_review_comments(
        self, review_output: ReviewOutput
    ) -> List[ReviewComment]:
        """Convert ReviewOutput to ReviewComment format."""
        comments = []
        
        for comment in review_output.comments:
            comments.append(
                ReviewComment(
                    file_path=comment.file_path,
                    line_number=comment.line_number,
                    severity=comment.severity,
                    category=comment.category,
                    message=comment.message,
                    suggestion=comment.suggestion,
                    resolved=False,
                )
            )
        
        return comments
