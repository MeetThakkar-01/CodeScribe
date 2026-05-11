"""Thin wrapper around the Atlassian Jira REST API v3.

Includes exponential-backoff retry on HTTP 429 (rate limit) and 5xx transient
failures, matching the production resiliency posture documented in Appendix G
of the system report.
"""

import time
from typing import Any, Dict, Optional

import httpx
import structlog

from src.config import get_settings

logger = structlog.get_logger()

# Retry policy
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 2.0


class JiraClient:
    """Minimal Jira REST client with retry-on-transient-error.

    Tests patch :py:meth:`create_issue` directly via the ``JiraClient`` class
    name, so the retry path is invisible to the ticketing-graph unit tests.
    The retry-specific tests target this module directly.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.jira_base_url.rstrip("/")
        self.auth = (settings.jira_email, settings.jira_api_token)

    def create_issue(self, payload: Dict[str, Any]) -> str:
        """POST a Jira issue payload and return the created issue key.

        Retries on HTTP 429 and 5xx with exponential backoff (2s, 4s, 8s) up
        to a maximum of :py:data:`_MAX_ATTEMPTS` attempts. Honors the
        ``Retry-After`` response header when Jira sends one on a 429.
        """
        if not self.base_url:
            raise RuntimeError(
                "JIRA_BASE_URL is not configured; cannot create Jira issues"
            )

        url = f"{self.base_url}/rest/api/3/issue"
        last_response: Optional[httpx.Response] = None

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            attempt_start = time.perf_counter()
            try:
                response = httpx.post(
                    url, json=payload, auth=self.auth, timeout=10.0
                )
            except httpx.HTTPError as e:
                # Network-level failure (timeout, DNS, connection reset, etc.)
                if attempt == _MAX_ATTEMPTS:
                    raise
                logger.warning(
                    "Jira API network error",
                    retry_attempt=attempt,
                    error=str(e),
                )
                self._sleep_with_backoff(attempt)
                continue

            last_response = response
            if response.status_code in _RETRYABLE_STATUSES and attempt < _MAX_ATTEMPTS:
                logger.warning(
                    "Jira API rate limit encountered"
                    if response.status_code == 429
                    else "Jira API transient failure",
                    status_code=response.status_code,
                    retry_attempt=attempt,
                )
                retry_after = response.headers.get("Retry-After")
                self._sleep_with_backoff(attempt, retry_after)
                continue

            response.raise_for_status()
            if attempt > 1:
                latency_ms = round((time.perf_counter() - attempt_start) * 1000, 1)
                logger.info(
                    "Retry successful",
                    attempt=attempt,
                    latency_ms=latency_ms,
                )
            return response.json()["key"]

        # Exhausted retries while last response was retryable
        if last_response is not None:
            last_response.raise_for_status()
        raise RuntimeError("Jira request failed after exhausting retries")

    @staticmethod
    def _sleep_with_backoff(attempt: int, retry_after_header: Optional[str] = None) -> None:
        """Sleep before the next retry attempt.

        If the server sent a ``Retry-After`` header, honor it; otherwise use
        exponential backoff (2s, 4s, 8s).
        """
        delay: Optional[float] = None
        if retry_after_header:
            try:
                delay = float(retry_after_header)
            except ValueError:
                delay = None
        if delay is None:
            delay = _BASE_DELAY_SECONDS * (2 ** (attempt - 1))

        logger.info(
            "Retry scheduled",
            strategy="exponential_backoff",
            delay_ms=int(delay * 1000),
        )
        time.sleep(delay)
