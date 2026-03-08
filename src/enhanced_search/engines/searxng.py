"""SearXNG search engine client."""

import logging
from typing import Any, Dict, List, Optional

import httpx

from .base import SearchEngine, SearchResult
from ..config import config

logger = logging.getLogger(__name__)


class SearXNGClient(SearchEngine):
    """SearXNG metasearch engine - aggregates 70+ search engines."""

    name = "searxng"
    priority = 0

    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._default_engines = config.SEARXNG_DEFAULT_ENGINES or ""
        self._image_engines = config.SEARXNG_IMAGE_ENGINES or ""

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"Accept": "application/json"},
            )
        return self._client

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
        if not self.base_url:
            logger.warning("SearXNG URL not configured, skipping")
            return []

        params: Dict[str, Any] = {
            "q": query,
            "format": "json",
            "safesearch": safesearch,
            "pageno": 1,
        }
        if categories:
            params["categories"] = categories
        if engines:
            params["engines"] = engines
        elif self._default_engines and not categories:
            params["engines"] = self._default_engines
        if language:
            params["language"] = language
        if time_range and time_range in ("day", "month", "year"):
            params["time_range"] = time_range

        try:
            resp = await self.client.get(f"{self.base_url}/search", params=params)
            resp.raise_for_status()
            data = resp.json()

            results: List[SearchResult] = []
            for item in data.get("results", [])[:limit]:
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("content", ""),
                        engine=", ".join(item.get("engines", ["searxng"])),
                        score=item.get("score", 0.0),
                        published_date=item.get("publishedDate"),
                    )
                )
            return results
        except Exception as e:
            logger.error("SearXNG search error: %s", e)
            return []

    async def search_images(
        self,
        query: str,
        limit: int = 10,
        safesearch: int = 1,
    ) -> List[Dict[str, Any]]:
        """Search images via SearXNG images category."""
        if not self.base_url:
            return []

        params: Dict[str, Any] = {
            "q": query,
            "format": "json",
            "safesearch": safesearch,
            "pageno": 1,
        }
        if self._image_engines:
            params["engines"] = self._image_engines
        else:
            params["categories"] = "images"

        try:
            resp = await self.client.get(f"{self.base_url}/search", params=params)
            resp.raise_for_status()
            data = resp.json()

            results: List[Dict[str, Any]] = []
            for item in data.get("results", [])[:limit]:
                results.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "img_src": item.get("img_src", ""),
                        "thumbnail": item.get("thumbnail", ""),
                        "engine": ", ".join(item.get("engines", ["searxng"])),
                        "source": item.get("source", ""),
                    }
                )
            return results
        except Exception as e:
            logger.error("SearXNG image search error: %s", e)
            return []

    async def is_healthy(self) -> bool:
        if not self.base_url:
            return False
        try:
            resp = await self.client.get(f"{self.base_url}/")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
