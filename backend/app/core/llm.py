"""Shared Gemini chat model client. Never invoke this directly in tests — always mock it (rules.md)."""

from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import get_settings
from app.core.logging import get_logger

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
    )
