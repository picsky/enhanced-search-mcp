"""DuckDuckGo search engine client - no API key required."""

import asyncio
import logging
from typing import List, Optional

from ddgs import DDGS

from .base import SearchEngine, SearchResult

logger = logging.getLogger(__name__)

# Mapping from our time_range to DDG timelimit
_TIME_MAP = {
    "day": "d",
    "week": "w",
    "month": "m",
    "year": "y",
}

_SAFE_MAP = {
    0: "off",
    1: "moderate",
    2: "on",
}


class DuckDuckGoClient(SearchEngine):
    """DuckDuckGo search engine - free, no API key needed."""

    name = "duckduckgo"
    priority = 1

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    async def search(
        self,
        query: str,
        limit: int = 10,
        categories: Optional[str] = None,
        engines: Optional[str] = None,
        language: Optional[str] = None,
        time_range: Optional[str] = None,
        safesearch: int = 1,
    ) -> List[SearchResult]:
        timelimit = _TIME_MAP.get(time_range) if time_range else None
        safe = _SAFE_MAP.get(safesearch, "moderate")
        region = "wt-wt"

        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(
                    self._sync_search,
                    query=query,
                    max_results=limit,
                    region=region,
                    safesearch=safe,
                    timelimit=timelimit,
                ),
                timeout=self.timeout,
            )
            results: List[SearchResult] = []
            for item in raw:
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("href", ""),
                        snippet=item.get("body", ""),
                        engine="duckduckgo",
                        score=0.0,
                    )
                )
            return results
        except Exception as e:
            logger.error("DuckDuckGo search error: %s", e)
            return []

    @staticmethod
    def _sync_search(
        query: str,
        max_results: int,
        region: str,
        safesearch: str,
        timelimit: Optional[str],
    ) -> list:
        with DDGS() as ddgs:
            return list(
                ddgs.text(
                    query,
                    region=region,
                    safesearch=safesearch,
                    timelimit=timelimit,
                    max_results=max_results,
                )
            )

    async def is_healthy(self) -> bool:
        try:
            results = await asyncio.wait_for(
                asyncio.to_thread(
                    self._sync_search,
                    query="test",
                    max_results=1,
                    region="wt-wt",
                    safesearch="moderate",
                    timelimit=None,
                ),
                timeout=self.timeout,
            )
            return len(results) > 0
        except (asyncio.TimeoutError, Exception):
            return False

    async def close(self) -> None:
        pass
