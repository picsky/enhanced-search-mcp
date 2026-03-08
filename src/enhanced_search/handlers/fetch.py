"""Fetch content handler logic."""

import asyncio
import json
import logging
from typing import Any, Dict

from mcp.types import TextContent

from ..config import config
from ..engines.fetcher import ContentFetcher
from ..utils.rate_limit import TokenBucketRateLimiter
from ..utils.retry import with_retry

logger = logging.getLogger("enhanced-search")


class FetchHandler:
    """Handles fetch_content tool."""

    def __init__(
        self,
        fetcher: ContentFetcher,
        rate_limiter: TokenBucketRateLimiter,
        semaphore: asyncio.Semaphore,
    ) -> None:
        self.fetcher = fetcher
        self.rate_limiter = rate_limiter
        self.semaphore = semaphore

    async def handle_fetch(self, args: Dict[str, Any]) -> list[TextContent]:
        url = args["url"]
        max_length = args.get("max_length", config.MAX_CONTENT_LENGTH)
        output_format = args.get("output_format", "text")

        async with self.semaphore:
            await self.rate_limiter.acquire()
            result = await with_retry(
                self.fetcher.fetch, url, max_length=max_length,
                output_format=output_format, max_retries=2,
            )

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
