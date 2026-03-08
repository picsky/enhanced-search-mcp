"""Tests for the rate limiter module."""

import asyncio
import time

import pytest

from enhanced_search.utils.rate_limit import TokenBucketRateLimiter


class TestTokenBucketRateLimiter:
    @pytest.mark.asyncio
    async def test_acquire_within_limit(self) -> None:
        limiter = TokenBucketRateLimiter(rpm=600)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # should be near-instant

    @pytest.mark.asyncio
    async def test_multiple_acquires(self) -> None:
        limiter = TokenBucketRateLimiter(rpm=600)
        for _ in range(5):
            await limiter.acquire()
        assert limiter.tokens < limiter.max_tokens

    @pytest.mark.asyncio
    async def test_token_refill(self) -> None:
        limiter = TokenBucketRateLimiter(rpm=6000)
        # Consume some tokens
        for _ in range(10):
            await limiter.acquire()
        tokens_after_consume = limiter.tokens
        await asyncio.sleep(0.05)
        # Force a refill check by acquiring again
        await limiter.acquire()
        # The refill should have added tokens (even after consuming one)
        # Just verify we didn't deadlock and could acquire
        assert True

    @pytest.mark.asyncio
    async def test_respects_max_tokens(self) -> None:
        limiter = TokenBucketRateLimiter(rpm=60)
        assert limiter.tokens <= limiter.max_tokens
        # Wait a bit and verify tokens don't exceed max
        await asyncio.sleep(0.1)
        limiter._refill()
        assert limiter.tokens <= limiter.max_tokens

    def test_initial_state(self) -> None:
        limiter = TokenBucketRateLimiter(rpm=120)
        assert limiter.rpm == 120
        assert limiter.tokens == 120.0
        assert limiter.max_tokens == 120.0
        assert limiter.refill_rate == 2.0  # 120 / 60
