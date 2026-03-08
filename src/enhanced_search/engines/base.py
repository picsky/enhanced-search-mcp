"""Base class for search engines (plugin architecture)."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class SearchResult:
    """Unified search result structure."""

    def __init__(
        self,
        title: str = "",
        url: str = "",
        snippet: str = "",
        engine: str = "unknown",
        score: float = 0.0,
        published_date: Optional[str] = None,
    ):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.engine = engine
        self.score = score
        self.published_date = published_date

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "engine": self.engine,
            "score": self.score,
        }
        if self.published_date:
            d["published_date"] = self.published_date
        return d


class SearchEngine(ABC):
    """Abstract base class for all search engines."""

    name: str = "base"
    priority: int = 0  # lower = higher priority

    @abstractmethod
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
        ...

    @abstractmethod
    async def is_healthy(self) -> bool:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
