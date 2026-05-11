"""Stage-timing decorator for LangGraph node methods.

Wraps a node method so its completion (or failure) emits a structured
``structlog`` record with the stage name and latency in milliseconds.
This produces the ``stage_completed | latency_ms=...`` log lines used in
Appendix F of the report.
"""

import functools
import time
from typing import Any, Callable

import structlog

logger = structlog.get_logger()


def timed_stage(stage_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a graph node so its completion emits ``stage_completed`` with latency.

    Usage:

        @timed_stage("fetch_pr_changes")
        def fetch_pr_changes(self, state):
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(self, state, *args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(self, state, *args, **kwargs)
                latency_ms = round((time.perf_counter() - start) * 1000, 1)
                logger.info(
                    "stage_completed",
                    stage=stage_name,
                    latency_ms=latency_ms,
                )
                return result
            except Exception as e:
                latency_ms = round((time.perf_counter() - start) * 1000, 1)
                logger.error(
                    "stage_failed",
                    stage=stage_name,
                    latency_ms=latency_ms,
                    error=str(e),
                )
                raise

        return wrapper

    return decorator
