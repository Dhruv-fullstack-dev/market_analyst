"""Decorator to log a graph node's execution latency for debuggability."""

import time
from collections.abc import Callable
from functools import wraps

from app.core.logging import get_logger

logger = get_logger(__name__)


def log_node_duration(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info("%s completed in %.1fms", func.__name__, elapsed_ms)

    return wrapper
