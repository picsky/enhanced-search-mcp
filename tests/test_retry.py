"""Tests for the retry module."""

import pytest

from enhanced_search.utils.retry import RetryError, with_retry


class TestWithRetry:
    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self) -> None:
        call_count = 0

        async def succeed() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await with_retry(succeed, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retries(self) -> None:
        call_count = 0

        async def fail_then_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temporary failure")
            return "recovered"

        result = await with_retry(fail_then_succeed, max_retries=3, base_delay=0.01)
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self) -> None:
        async def always_fail() -> str:
            raise ConnectionError("persistent failure")

        with pytest.raises(RetryError) as exc_info:
            await with_retry(always_fail, max_retries=2, base_delay=0.01)
        assert "persistent failure" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_retry_on_403(self) -> None:
        call_count = 0

        class Http403Error(Exception):
            status_code = 403

        async def forbidden() -> str:
            nonlocal call_count
            call_count += 1
            raise Http403Error("Forbidden")

        with pytest.raises(Http403Error):
            await with_retry(forbidden, max_retries=3, base_delay=0.01)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_429(self) -> None:
        call_count = 0

        class Http429Error(Exception):
            status_code = 429

        async def rate_limited() -> str:
            nonlocal call_count
            call_count += 1
            raise Http429Error("Too Many Requests")

        with pytest.raises(Http429Error):
            await with_retry(rate_limited, max_retries=3, base_delay=0.01)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_passes_args_and_kwargs(self) -> None:
        async def echo(a: int, b: str, c: bool = False) -> dict:
            return {"a": a, "b": b, "c": c}

        result = await with_retry(echo, 1, b="hello", c=True, max_retries=0)
        assert result == {"a": 1, "b": "hello", "c": True}
