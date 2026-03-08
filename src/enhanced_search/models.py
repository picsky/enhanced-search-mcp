"""Pydantic models for structured data passing across the application."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SearchResultModel(BaseModel):
    """Unified search result structure."""

    title: str = ""
    url: str = ""
    snippet: str = ""
    engine: str = "unknown"
    score: float = 0.0
    published_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = self.model_dump(exclude_none=True)
        if "published_date" not in d:
            d.pop("published_date", None)
        return d


class FetchResult(BaseModel):
    """Result from fetching a web page."""

    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    format: str = "text"
    success: bool = False
    error: Optional[str] = None


class DeepSearchSource(BaseModel):
    """A single source entry in deep search results."""

    id: int = 0
    title: str = ""
    url: str = ""
    key_excerpts: List[str] = Field(default_factory=list)
    relevance_score: float = 0.0
    recency_score: float = 0.0
    engine: str = ""
    date: Optional[str] = None
    raw_content: Optional[str] = None
    search_round: Optional[int] = None


class DeepSearchResult(BaseModel):
    """Result from deep_search or agent_search."""

    query: str
    mode: str
    total_sources: int = 0
    sources: List[DeepSearchSource] = Field(default_factory=list)
    follow_up_queries: List[str] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    # agent_search extras
    rounds_completed: Optional[int] = None
    queries_used: Optional[List[str]] = None


class ExtractedItem(BaseModel):
    """A single extracted item from extract_structured."""

    url: str
    title: Optional[str] = None
    content_summary: Optional[str] = None
    date: Optional[str] = None
    author: Optional[str] = None
    links: Optional[List[str]] = None
    extracted: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class HistoryEntry(BaseModel):
    """Search history entry."""

    id: int
    query: str
    tool: str
    result_count: int
    timestamp: str
