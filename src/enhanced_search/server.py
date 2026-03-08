"""Enhanced Search MCP Server - main entry point."""

import asyncio
import json
import logging
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .cache.redis_cache import SearchCache
from .config import config
from .engines.base import SearchEngine
from .engines.duckduckgo import DuckDuckGoClient
from .engines.fetcher import ContentFetcher
from .engines.searxng import SearXNGClient
from .handlers.extract import ExtractHandler
from .handlers.fetch import FetchHandler
from .handlers.history import HistoryHandler, SearchHistory
from .handlers.search import SearchHandler
from .utils.dedup import ResultDeduplicator
from .utils.health_check import HealthChecker
from .utils.rate_limit import TokenBucketRateLimiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("enhanced-search")


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

class EnhancedSearchMCP:
    def __init__(self) -> None:
        self.server = Server("enhanced-search")

        # Engines
        self.searxng = SearXNGClient(config.SEARXNG_URL, timeout=config.SEARCH_OP_TIMEOUT)
        self.engines: List[SearchEngine] = [self.searxng]
        if config.ENABLE_DDG:
            self.ddg = DuckDuckGoClient(timeout=config.SEARCH_OP_TIMEOUT)
            self.engines.append(self.ddg)
            logger.info("DuckDuckGo engine enabled")
        else:
            self.ddg = None

        # Fetcher
        self.fetcher = ContentFetcher(timeout=config.FETCH_OP_TIMEOUT, max_length=config.MAX_CONTENT_LENGTH)

        # Enhancement layer
        self.dedup = ResultDeduplicator()
        self.cache = SearchCache(redis_url=config.REDIS_URL, ttl=config.CACHE_TTL)
        self.rate_limiter = TokenBucketRateLimiter(rpm=config.RATE_LIMIT_RPM)
        self.health = HealthChecker(check_interval=config.HEALTH_CHECK_INTERVAL)
        self.semaphore = asyncio.Semaphore(config.MAX_CONCURRENT)

        # History
        self.history = SearchHistory()

        # Handlers
        self.search_handler = SearchHandler(
            engines=self.engines,
            fetcher=self.fetcher,
            dedup=self.dedup,
            cache=self.cache,
            rate_limiter=self.rate_limiter,
            health=self.health,
            semaphore=self.semaphore,
        )
        self.fetch_handler = FetchHandler(
            fetcher=self.fetcher,
            rate_limiter=self.rate_limiter,
            semaphore=self.semaphore,
        )
        self.extract_handler = ExtractHandler(
            fetcher=self.fetcher,
            rate_limiter=self.rate_limiter,
            semaphore=self.semaphore,
        )
        self.history_handler = HistoryHandler(history=self.history)

        self._register_tools()

    # ------------------------------------------------------------------
    # Tool definitions
    # ------------------------------------------------------------------

    def _register_tools(self) -> None:
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="search",
                    description=(
                        "Execute an enhanced web search aggregating results from multiple engines "
                        "(SearXNG + DuckDuckGo). Supports categories, engines, language, time range, "
                        "topic optimization, domain filtering, and precise date ranges. "
                        "Returns structured results with title, URL, snippet, and source engine."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query string"},
                            "limit": {
                                "type": "integer",
                                "description": "Number of results to return (1-50)",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 50,
                            },
                            "topic": {
                                "type": "string",
                                "enum": ["general", "news", "finance", "science", "it"],
                                "description": "Topic optimization: general, news, finance, science, it",
                                "default": "general",
                            },
                            "categories": {
                                "type": "string",
                                "description": "Search categories: general, images, videos, news, it, science, etc.",
                            },
                            "engines": {
                                "type": "string",
                                "description": "Specify engines, e.g. 'google,bing,duckduckgo'",
                            },
                            "language": {
                                "type": "string",
                                "description": "Language code, e.g. 'zh-CN', 'en-US'",
                            },
                            "time_range": {
                                "type": "string",
                                "enum": ["day", "week", "month", "year"],
                                "description": "Time range filter",
                            },
                            "include_domains": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Only include results from these domains, e.g. ['arxiv.org', 'github.com']",
                            },
                            "exclude_domains": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Exclude results from these domains, e.g. ['pinterest.com']",
                            },
                            "start_date": {
                                "type": "string",
                                "description": "Only return results published after this date (YYYY-MM-DD)",
                            },
                            "end_date": {
                                "type": "string",
                                "description": "Only return results published before this date (YYYY-MM-DD)",
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="search_images",
                    description="Search for images via SearXNG images category.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query string"},
                            "limit": {
                                "type": "integer",
                                "description": "Number of results to return",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 50,
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="fetch_content",
                    description=(
                        "Fetch the main content of a web page URL, automatically cleaning ads and navigation. "
                        "Supports plain text and markdown output formats."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "The page URL to fetch"},
                            "max_length": {
                                "type": "integer",
                                "description": "Maximum content length in characters",
                                "default": 10000,
                            },
                            "output_format": {
                                "type": "string",
                                "enum": ["text", "markdown"],
                                "description": "Output format: 'text' (plain text) or 'markdown' (structured markdown)",
                                "default": "text",
                            },
                        },
                        "required": ["url"],
                    },
                ),
                Tool(
                    name="deep_search",
                    description=(
                        "Deep search: execute a search and return structured results with key excerpts, "
                        "citation IDs, relevance scores, and recency scores. "
                        "Supports 'quick' (snippets only) and 'deep' (fetch key paragraphs) modes. "
                        "Returns: {sources: [{id, title, url, key_excerpts[], relevance_score, recency_score}], "
                        "follow_up_queries: [...], conflicts: [...]}. "
                        "Use [1], [2] etc. citation IDs to reference sources."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query string"},
                            "mode": {
                                "type": "string",
                                "enum": ["quick", "deep"],
                                "description": "Search mode: 'quick' returns snippets only, 'deep' fetches key paragraphs",
                                "default": "deep",
                            },
                            "fetch_limit": {
                                "type": "integer",
                                "description": "Number of results to fetch full content for (deep mode only)",
                                "default": 3,
                                "minimum": 1,
                                "maximum": 10,
                            },
                            "search_limit": {
                                "type": "integer",
                                "description": "Number of results in search phase",
                                "default": 10,
                            },
                            "include_raw_content": {
                                "type": "boolean",
                                "description": "If true, include full raw content for fetched pages (deep mode). Increases token usage.",
                                "default": False,
                            },
                            "include_domains": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Only include results from these domains",
                            },
                            "exclude_domains": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Exclude results from these domains",
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="extract_structured",
                    description=(
                        "Extract structured information from a list of URLs. "
                        "Supports custom schema to define extraction field types. "
                        "Built-in fields: title, content_summary, date, author, links. "
                        "Custom schema example: {\"price\": \"number\", \"rating\": \"string\"}. "
                        "Supports batch concurrent extraction of multiple URLs."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "urls": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of URLs to analyze",
                            },
                            "fields": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Built-in field names to extract: 'title', 'content_summary', 'date', 'author', 'links'",
                                "default": ["title", "content_summary"],
                            },
                            "schema": {
                                "type": "object",
                                "description": "Custom extraction schema, e.g. {\"price\": \"number\", \"rating\": \"string\"}. Uses rule-based matching to extract fields from page content.",
                            },
                        },
                        "required": ["urls"],
                    },
                ),
                Tool(
                    name="agent_search",
                    description=(
                        "Agent mode search: automatically discovers sub-topics and initiates follow-up searches, "
                        "merging multi-round search results. Ideal for complex questions requiring multi-angle "
                        "in-depth research. Performs automatic query expansion and sub-topic exploration. "
                        "Returns same format as deep_search but with merged results from multiple rounds."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query string"},
                            "max_rounds": {
                                "type": "integer",
                                "description": "Maximum number of search rounds (including initial search)",
                                "default": 2,
                                "minimum": 1,
                                "maximum": 3,
                            },
                            "fetch_limit": {
                                "type": "integer",
                                "description": "Number of results to fetch full content per round",
                                "default": 2,
                                "minimum": 1,
                                "maximum": 5,
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="search_history",
                    description="Manage search history: list, re-execute, or clear history records.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["list", "execute", "clear"],
                                "description": "Action type",
                            },
                            "query_id": {
                                "type": "integer",
                                "description": "History query ID (required for 'execute' action)",
                            },
                        },
                        "required": ["action"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            result = await self._dispatch(name, arguments)
            # Track in history
            query = arguments.get("query", arguments.get("url", ""))
            if name != "search_history" and query:
                count = 0
                try:
                    data = json.loads(result[0].text)
                    if isinstance(data, list):
                        count = len(data)
                    elif isinstance(data, dict):
                        count = data.get("total_sources", 1 if data.get("success") else 0)
                except (json.JSONDecodeError, IndexError):
                    pass
                self.history.add(query, name, count)
            return result

    async def _dispatch(self, name: str, arguments: Dict[str, Any]) -> list[TextContent]:
        """Route tool calls to the appropriate handler."""
        try:
            if name == "search":
                return await self.search_handler.handle_search(arguments)
            elif name == "search_images":
                return await self.search_handler.handle_search_images(arguments, self.searxng)
            elif name == "fetch_content":
                return await self.fetch_handler.handle_fetch(arguments)
            elif name == "deep_search":
                return await self.search_handler.handle_deep_search(arguments)
            elif name == "extract_structured":
                return await self.extract_handler.handle_extract(arguments)
            elif name == "agent_search":
                return await self.search_handler.handle_agent_search(arguments)
            elif name == "search_history":
                return await self.history_handler.handle_history(
                    arguments,
                    search_callback=self._get_history_callback(),
                )
            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
        except Exception as e:
            logger.error("Tool %s failed: %s", name, e, exc_info=True)
            return [TextContent(type="text", text=json.dumps({"error": f"Tool '{name}' failed: {str(e)}"}))]

    def _get_history_callback(self) -> Dict[str, Any]:
        """Return a dispatch map for history re-execute."""
        return {
            "search": self.search_handler.handle_search,
            "deep_search": self.search_handler.handle_deep_search,
            "agent_search": self.search_handler.handle_agent_search,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def run(self) -> None:
        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options(),
                )
        finally:
            await self._cleanup()

    async def _cleanup(self) -> None:
        await self.searxng.close()
        await self.fetcher.close()
        await self.cache.close()


def main() -> None:
    mcp = EnhancedSearchMCP()
    try:
        asyncio.run(mcp.run())
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
