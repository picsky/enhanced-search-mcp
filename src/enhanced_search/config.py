"""Configuration management for Enhanced Search MCP using Pydantic BaseSettings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """Validated configuration loaded from environment variables."""

    model_config = {"env_prefix": "", "case_sensitive": True}

    SEARXNG_URL: str = Field(
        default="https://search.rhscz.eu/",
        description="SearXNG instance base URL",
    )
    SEARCH_TIMEOUT: int = Field(default=30, ge=1, le=300, description="HTTP request timeout in seconds")
    DEFAULT_LIMIT: int = Field(default=10, ge=1, le=100, description="Default number of search results")
    DEEP_SEARCH_MAX_PAGES: int = Field(default=5, ge=1, le=20, description="Max pages to fetch in deep search")
    MAX_CONTENT_LENGTH: int = Field(default=10000, ge=100, le=1000000, description="Max content length per page")
    REDIS_URL: str = Field(default="", description="Redis URL for caching (empty to disable)")
    CACHE_TTL: int = Field(default=3600, ge=60, le=86400, description="Default cache TTL in seconds")
    RATE_LIMIT_RPM: int = Field(default=200, ge=1, le=10000, description="Max requests per minute")
    MAX_CONCURRENT: int = Field(default=20, ge=1, le=100, description="Max concurrent requests")
    ENABLE_DDG: bool = Field(default=False, description="Enable DuckDuckGo as a fallback engine (may timeout in China)")
    SEARXNG_DEFAULT_ENGINES: str = Field(
        default="bing,baidu,sogou,360search,mojeek,presearch",
        description="Comma-separated default engines for SearXNG general search (China-optimized)",
    )
    SEARXNG_IMAGE_ENGINES: str = Field(
        default="sogou images,unsplash,pexels,mojeek images,presearch images",
        description="Comma-separated default engines for SearXNG image search (China-optimized)",
    )
    ENABLE_PLAYWRIGHT: bool = Field(default=False, description="Enable Playwright for JS-rendered pages")

    # Timeouts per operation type
    SEARCH_OP_TIMEOUT: int = Field(default=10, ge=1, le=60)
    FETCH_OP_TIMEOUT: int = Field(default=30, ge=1, le=120)
    DEEP_SEARCH_OP_TIMEOUT: int = Field(default=60, ge=1, le=300)

    # Health check
    HEALTH_CHECK_INTERVAL: int = Field(default=300, ge=30, le=3600, description="Health check interval in seconds")


config = Config()
