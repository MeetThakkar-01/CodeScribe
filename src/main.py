"""Main application entry point."""

import structlog
import uvicorn

from src.config import get_settings
from src.github.webhook_handler import create_app

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()


def main():
    """Start the application server."""
    settings = get_settings()
    
    logger.info(
        "Starting GitHub PR Review Agent",
        host=settings.server_host,
        port=settings.server_port,
    )

    app = create_app()

    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
