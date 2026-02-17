"""AMZ_Designy - Retry decorator with exponential backoff."""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 5,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable:
    """Decorator that retries an async function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        initial_delay: Delay in seconds before the first retry.
        backoff_factor: Multiplier applied to the delay after each retry.
        exceptions: Tuple of exception types that trigger a retry.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = initial_delay
            last_exc: BaseException | None = None

            for attempt in range(1, max_retries + 1):
                try:
                    return await fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == max_retries:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            fn.__name__,
                            max_retries,
                            exc,
                        )
                        raise
                    logger.warning(
                        "%s attempt %d/%d failed (%s), retrying in %.1fs…",
                        fn.__name__,
                        attempt,
                        max_retries,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff_factor

            raise last_exc  # type: ignore[misc]  # unreachable, satisfies type checker

        return wrapper

    return decorator
