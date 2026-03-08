"""Token-bucket rate limiter for controlling request frequency."""

import asyncio
import time


class TokenBucketRateLimiter:
    """Async token-bucket rate limiter.

    Args:
        rpm: Maximum requests per minute.
    """

    def __init__(self, rpm: int = 200):
        self.rpm = rpm
        self.tokens = float(rpm)
        self.max_tokens = float(rpm)
        self.refill_rate = rpm / 60.0  # tokens per second
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a token is available."""
        while True:
            async with self._lock:
                self._refill()
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
            # Wait a short interval before retrying
            await asyncio.sleep(1.0 / self.refill_rate if self.refill_rate > 0 else 0.1)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self._last_refill = now
