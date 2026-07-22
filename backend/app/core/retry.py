"""Shared retry-with-backoff helper for flaky external calls (yfinance, DuckDuckGo)."""

import time
from collections.abc import Callable
from typing import TypeVar

from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    func: Callable[[], T],
    *,
    max_retries: int = 3,
    backoff_seconds: float = 2.0,
    label: str = "operation",
) -> T:
    """Call `func()`, retrying on exception with linear backoff. Re-raises the last error."""
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            logger.warning("%s attempt %s/%s failed: %s", label, attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(backoff_seconds * attempt)
    logger.error("All %s attempts failed for %s", max_retries, label)
    raise last_exc
