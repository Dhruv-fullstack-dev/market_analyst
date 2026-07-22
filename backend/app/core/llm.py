"""Shared Gemini chat model client. Never invoke this directly in tests — always mock it (rules.md)."""

from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limit import RateLimiter

logger = get_logger(__name__)


@lru_cache
def get_llm() -> ChatGoogleGenerativeAI:
    """Singleton Gemini chat model built from Settings."""
    settings = get_settings()
    logger.info("Initializing Gemini chat model '%s'", settings.gemini_model)
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=0.2,
        # Default is 6 internal retries on transient errors (incl. 429s), which can silently
        # fire many real requests per logical call against a free-tier quota. Our own
        # core/retry.py already owns retry policy for tools; keep the LLM client to a single
        # attempt so failures (and quota errors especially) surface immediately.
        max_retries=1,
    )


@lru_cache
def get_rate_limiter() -> RateLimiter:
    """Singleton limiter every LLM call site must `.acquire()` before invoking Gemini."""
    settings = get_settings()
    return RateLimiter(max_calls=settings.gemini_rpm_limit, period_seconds=60.0)
