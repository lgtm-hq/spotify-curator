"""Retry decorator for AI calls."""

from __future__ import annotations

import functools
import random
import time
from collections.abc import Callable
from typing import Any

from app.ai.exceptions import AIAuthenticationError, AIProviderError, AIRateLimitError


def with_retry(
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Retry AI calls with exponential backoff."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except AIAuthenticationError:
                    raise
                except (AIProviderError, AIRateLimitError) as exc:
                    last_exc = exc
                    if attempt == max_retries:
                        raise
                    delay = min(base_delay * (backoff_factor**attempt), max_delay)
                    delay *= random.uniform(0.8, 1.2)
                    time.sleep(delay)
            if last_exc:
                raise last_exc
            raise AIProviderError("Retry exhausted")

        return wrapper

    return decorator
