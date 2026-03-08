"""Exponential backoff retry utility."""

import asyncio
import logging
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# HTTP status codes that should NOT be retried
_NO_RETRY_CODES = {403, 429}


class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, last_error: Exception):
        self.last_error = last_error
        super().__init__(f"All retries exhausted. Last error: {last_error}")


async def with_retry(
    fn: Callable[..., Awaitable[T]],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
    **kwargs: Any,
) -> T:
    """Execute an async function with exponential backoff retry.

    Args:
        fn: Async function to call.
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay cap.

    Raises:
        RetryError: When all attempts fail.
    """
    last_error: Exception = RuntimeError("No attempts made")

    for attempt in range(max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            last_error = e

            # Check for non-retryable HTTP errors
            status = getattr(e, "status_code", None) or getattr(
                getattr(e, "response", None), "status_code", None
            )
            if status in _NO_RETRY_CODES:
                logger.warning("Non-retryable error (HTTP %s): %s", status, e)
                raise

            if attempt < max_retries:
                delay = min(base_delay * (2**attempt), max_delay)
                logger.warning(
                    "Attempt %d/%d failed: %s — retrying in %.1fs",
                    attempt + 1,
                    max_retries + 1,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)

    raise RetryError(last_error)
