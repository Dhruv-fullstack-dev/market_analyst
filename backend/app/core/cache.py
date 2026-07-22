from collections.abc import Callable
from functools import wraps

from cachetools import TTLCache, keys

from app.core.logging import get_logger

logger = get_logger(__name__)


def make_ttl_cache(maxsize: int, ttl: int) -> TTLCache:
    return TTLCache(maxsize=maxsize, ttl=ttl)


def cached(cache: TTLCache) -> Callable:
    """Decorator that memoizes a function's result in the given TTLCache."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = keys.hashkey(*args, **kwargs)
            if key in cache:
                logger.debug("Cache hit for %s%s", func.__name__, args)
                return cache[key]

            logger.debug("Cache miss for %s%s", func.__name__, args)
            result = func(*args, **kwargs)
            cache[key] = result
            return result

        return wrapper

    return decorator
