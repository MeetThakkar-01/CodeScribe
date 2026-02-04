"""Configuration management for the GitHub PR Review Agent."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # GitHub App Configuration
    github_app_id: str = Field(..., description="GitHub App ID")
    github_private_key_path: str = Field(
        ..., description="Path to GitHub App private key (.pem file)"
    )
    github_webhook_secret: str = Field(..., description="Webhook secret for validation")

    # Google Gemini Configuration
    google_api_key: str = Field(..., description="Google Gemini API key")
    gemini_model: str = Field(
        default="gemini-1.5-flash", description="Gemini model to use"
    )

    # Server Configuration
    server_host: str = Field(default="0.0.0.0", description="Server host")
    server_port: int = Field(default=8000, description="Server port")

    # Review Configuration
    min_review_severity: str = Field(
        default="low",
        description="Minimum severity to post (low, medium, high)",
    )
    auto_label_on_complete: bool = Field(
        default=True, description="Auto-add labels when review is complete"
    )
    ready_for_approval_label: str = Field(
        default="ready-for-approval",
        description="Label to add when ready for human approval",
    )
    ai_review_complete_label: str = Field(
        default="ai-review-complete",
        description="Label to add when AI review is complete",
    )

    @property
    def github_private_key(self) -> str:
        """Load the GitHub private key from file."""
        key_path = Path(self.github_private_key_path)
        if not key_path.exists():
            raise FileNotFoundError(f"Private key not found: {key_path}")
        return key_path.read_text()


# Global settings instance
settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global settings
    if settings is None:
        settings = Settings()
    return settings
