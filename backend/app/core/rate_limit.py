"""Thread-safe sliding-window rate limiter, used to keep Gemini calls under the free-tier RPM cap.

The analyst/router/master nodes run concurrently (LangGraph's Send()-based fan-out), so a single
portfolio/compare query can fire 6-8 Gemini calls at once — comfortably over a 5 requests/minute
free-tier limit. Every LLM call site acquires this limiter first so calls queue and wait their
turn instead of bursting past the cap and getting rejected with 429s.
"""

import threading
import time
from collections import deque

from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Blocks callers so no more than `max_calls` occur within any rolling `period_seconds` window."""

    def __init__(self, max_calls: int, period_seconds: float):
        self.max_calls = max_calls
        self.period_seconds = period_seconds
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        while self._calls and now - self._calls[0] >= self.period_seconds:
            self._calls.popleft()

    def acquire(self) -> None:
        """Block until a call is permitted, then record it. Serializes all callers by design."""
        with self._lock:
            now = time.monotonic()
            self._prune(now)

            if len(self._calls) >= self.max_calls:
                wait_seconds = self.period_seconds - (now - self._calls[0])
                if wait_seconds > 0:
                    logger.info(
                        "Gemini rate limit (%s/%.0fs) reached; waiting %.1fs",
                        self.max_calls,
                        self.period_seconds,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)
                self._prune(time.monotonic())

            self._calls.append(time.monotonic())
