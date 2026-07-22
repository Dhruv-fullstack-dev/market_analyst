"""DuckDuckGo-backed web/news search tools (free, no API key)."""

from ddgs import DDGS

from app.core.cache import cached, make_ttl_cache
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.retry import retry_with_backoff

logger = get_logger(__name__)
settings = get_settings()

_news_cache = make_ttl_cache(maxsize=256, ttl=settings.search_cache_ttl_seconds)
_general_cache = make_ttl_cache(maxsize=256, ttl=settings.search_cache_ttl_seconds)


@cached(_news_cache)
def search_news(query: str, max_results: int | None = None) -> list[dict]:
    """Recent news headlines for a query. Returns [{"error": ...}] on failure."""
    max_results = max_results or settings.search_max_results
    logger.info("Searching news for '%s' (max_results=%s)", query, max_results)
    try:
        with DDGS() as ddgs:
            results = retry_with_backoff(
                lambda: list(ddgs.news(query, max_results=max_results)), label=f"search_news({query})"
            )
        normalized = [
            {
                "title": r.get("title"),
                "url": r.get("url") or r.get("link"),
                "snippet": r.get("body") or r.get("excerpt"),
                "date": r.get("date"),
                "source": r.get("source"),
            }
            for r in results
        ]
        logger.debug("Found %s news results for '%s'", len(normalized), query)
        return normalized
    except Exception as exc:
        logger.exception("News search failed for '%s'", query)
        return [{"error": str(exc)}]


@cached(_general_cache)
def search_general(query: str, max_results: int = 5) -> list[dict]:
    """General web search for a query. Returns [{"error": ...}] on failure."""
    logger.info("Searching web for '%s' (max_results=%s)", query, max_results)
    try:
        with DDGS() as ddgs:
            results = retry_with_backoff(
                lambda: list(ddgs.text(query, max_results=max_results)), label=f"search_general({query})"
            )
        normalized = [
            {"title": r.get("title"), "url": r.get("href") or r.get("link"), "snippet": r.get("body")}
            for r in results
        ]
        logger.debug("Found %s web results for '%s'", len(normalized), query)
        return normalized
    except Exception as exc:
        logger.exception("Web search failed for '%s'", query)
        return [{"error": str(exc)}]
