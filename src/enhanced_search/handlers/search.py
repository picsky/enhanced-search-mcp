"""Search and deep search handler logic."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from mcp.types import TextContent

from ..cache.redis_cache import SearchCache
from ..config import config
from ..engines.base import SearchEngine, SearchResult
from ..engines.fetcher import ContentFetcher
from ..models import DeepSearchResult, DeepSearchSource
from ..utils.dedup import ResultDeduplicator
from ..utils.health_check import HealthChecker
from ..utils.rate_limit import TokenBucketRateLimiter
from ..utils.retry import with_retry
from ..utils.text_analysis import (
    compute_recency_score,
    compute_relevance_score,
    detect_conflicts,
    extract_key_paragraphs,
    generate_follow_up_queries,
)

logger = logging.getLogger("enhanced-search")


class SearchHandler:
    """Handles search, deep_search, and agent_search tools."""

    def __init__(
        self,
        engines: List[SearchEngine],
        fetcher: ContentFetcher,
        dedup: ResultDeduplicator,
        cache: SearchCache,
        rate_limiter: TokenBucketRateLimiter,
        health: HealthChecker,
        semaphore: asyncio.Semaphore,
    ) -> None:
        self.engines = engines
        self.fetcher = fetcher
        self.dedup = dedup
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.health = health
        self.semaphore = semaphore

    async def handle_search(self, args: Dict[str, Any]) -> list[TextContent]:
        query = args["query"]
        limit = args.get("limit", config.DEFAULT_LIMIT)
        categories = args.get("categories")
        engines_param = args.get("engines")
        language = args.get("language")
        time_range = args.get("time_range")
        topic = args.get("topic", "general")
        include_domains: Optional[List[str]] = args.get("include_domains")
        exclude_domains: Optional[List[str]] = args.get("exclude_domains")
        start_date: Optional[str] = args.get("start_date")
        end_date: Optional[str] = args.get("end_date")

        # Topic -> category mapping
        if not categories and topic != "general":
            _topic_to_category = {"news": "news", "finance": "news", "science": "science", "it": "it"}
            categories = _topic_to_category.get(topic)

        # Check cache
        cached = await self.cache.get(
            "search", query, limit=limit, categories=categories,
            engines=engines_param, language=language, time_range=time_range,
            include_domains=include_domains, exclude_domains=exclude_domains,
            start_date=start_date, end_date=end_date,
        )
        if cached is not None:
            return [TextContent(type="text", text=json.dumps(cached, ensure_ascii=False, indent=2))]

        # Fetch extra results when domain filtering is active
        search_limit = limit * 3 if (include_domains or exclude_domains) else limit

        # Health check
        await self.health.check_all(self.engines)
        healthy_engines = self.health.get_healthy_engines(self.engines)

        # Parallel search with rate limiting and concurrency control
        async def _engine_search(engine: SearchEngine) -> List[SearchResult]:
            async with self.semaphore:
                await self.rate_limiter.acquire()
                return await with_retry(
                    engine.search,
                    query=query,
                    limit=search_limit,
                    categories=categories,
                    engines=engines_param,
                    language=language,
                    time_range=time_range,
                    max_retries=2,
                )

        tasks = [_engine_search(e) for e in healthy_engines]
        results_per_engine = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge
        all_results: List[Dict[str, Any]] = []
        for r in results_per_engine:
            if isinstance(r, list):
                all_results.extend([sr.to_dict() for sr in r])

        # Dedup & sort
        unique = self.dedup.deduplicate(all_results)
        sorted_results = self.dedup.sort_by_quality(unique)

        # Domain filtering
        if include_domains:
            inc = [d.lower().lstrip("www.") for d in include_domains]
            sorted_results = [
                r for r in sorted_results
                if any(d in r.get("url", "").lower() for d in inc)
            ]
        if exclude_domains:
            exc = [d.lower().lstrip("www.") for d in exclude_domains]
            sorted_results = [
                r for r in sorted_results
                if not any(d in r.get("url", "").lower() for d in exc)
            ]

        # Date range filtering
        if start_date or end_date:
            sorted_results = _filter_by_date_range(sorted_results, start_date, end_date)

        sorted_results = sorted_results[:limit]

        # Cache
        await self.cache.set(
            "search", query, sorted_results, limit=limit,
            categories=categories, engines=engines_param,
            language=language, time_range=time_range,
            include_domains=include_domains, exclude_domains=exclude_domains,
            start_date=start_date, end_date=end_date,
        )

        return [TextContent(type="text", text=json.dumps(sorted_results, ensure_ascii=False, indent=2))]

    async def handle_deep_search(self, args: Dict[str, Any]) -> list[TextContent]:
        query = args["query"]
        mode = args.get("mode", "deep")
        fetch_limit = min(args.get("fetch_limit", 3), config.DEEP_SEARCH_MAX_PAGES)
        search_limit = args.get("search_limit", config.DEFAULT_LIMIT)
        include_raw_content = args.get("include_raw_content", False)
        include_domains = args.get("include_domains")
        exclude_domains = args.get("exclude_domains")

        # Step 1: search
        search_args: Dict[str, Any] = {"query": query, "limit": search_limit}
        if include_domains:
            search_args["include_domains"] = include_domains
        if exclude_domains:
            search_args["exclude_domains"] = exclude_domains
        search_text = await self.handle_search(search_args)
        search_results: List[Dict[str, Any]] = json.loads(search_text[0].text)

        # Step 2: build structured sources with citation IDs
        sources: List[DeepSearchSource] = []
        contents_map: Dict[int, str] = {}

        if mode == "deep":
            top_urls = [r["url"] for r in search_results[:fetch_limit] if r.get("url")]

            async def _fetch_one(url: str) -> Dict[str, Any]:
                async with self.semaphore:
                    await self.rate_limiter.acquire()
                    return await self.fetcher.fetch(url)

            fetch_tasks = [_fetch_one(u) for u in top_urls]
            contents = await asyncio.gather(*fetch_tasks, return_exceptions=True)

            for i, c in enumerate(contents):
                if isinstance(c, dict) and c.get("success") and c.get("content"):
                    contents_map[i] = c["content"]

        # Step 3: assemble sources with scoring
        for i, sr in enumerate(search_results):
            relevance = compute_relevance_score(
                query=query,
                title=sr.get("title", ""),
                snippet=sr.get("snippet", ""),
                engine=sr.get("engine", ""),
            )
            recency = compute_recency_score(sr.get("published_date"))

            key_excerpts: List[str] = []
            if mode == "deep" and i in contents_map:
                key_excerpts = extract_key_paragraphs(contents_map[i], query, top_k=3)
            elif sr.get("snippet"):
                key_excerpts = [sr["snippet"]]

            source = DeepSearchSource(
                id=i + 1,
                title=sr.get("title", ""),
                url=sr.get("url", ""),
                key_excerpts=key_excerpts,
                relevance_score=relevance,
                recency_score=recency,
                engine=sr.get("engine", ""),
                date=sr.get("published_date"),
                raw_content=contents_map.get(i) if include_raw_content else None,
            )
            sources.append(source)

        # Sort by combined score
        sources.sort(
            key=lambda s: s.relevance_score * 0.7 + s.recency_score * 0.3,
            reverse=True,
        )
        for i, src in enumerate(sources):
            src.id = i + 1

        # Step 4: follow-up suggestions
        follow_ups = generate_follow_up_queries(query, search_results, count=3)

        # Step 5: conflict detection
        conflicts: List[Dict[str, Any]] = []
        if mode == "deep":
            conflicts = detect_conflicts([s.model_dump(exclude_none=True) for s in sources])

        result = DeepSearchResult(
            query=query,
            mode=mode,
            total_sources=len(sources),
            sources=sources,
            follow_up_queries=follow_ups,
            conflicts=conflicts,
        )

        return [TextContent(type="text", text=result.model_dump_json(exclude_none=True, indent=2))]

    async def handle_agent_search(self, args: Dict[str, Any]) -> list[TextContent]:
        """Agent mode: multi-round search with automatic follow-up queries."""
        query = args["query"]
        max_rounds = min(args.get("max_rounds", 2), 3)
        fetch_limit = min(args.get("fetch_limit", 2), 5)

        all_sources: List[Dict[str, Any]] = []
        seen_urls: set[str] = set()
        queries_used: List[str] = [query]

        # Overall timeout to prevent hanging
        overall_timeout = config.SEARCH_TIMEOUT * max_rounds

        async with asyncio.timeout(overall_timeout):
            for round_num in range(max_rounds):
                current_query = queries_used[-1] if round_num > 0 else query

                try:
                    deep_result_text = await asyncio.wait_for(
                        self.handle_deep_search({
                            "query": current_query,
                            "mode": "deep",
                            "fetch_limit": fetch_limit,
                            "search_limit": 8,
                        }),
                        timeout=config.SEARCH_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.warning("Agent search round %d timed out", round_num + 1)
                    break

                round_data = json.loads(deep_result_text[0].text)

                for src in round_data.get("sources", []):
                    url = src.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        src["search_round"] = round_num + 1
                        all_sources.append(src)

                follow_ups = round_data.get("follow_up_queries", [])
                if round_num < max_rounds - 1 and follow_ups:
                    queries_used.append(follow_ups[0])
                else:
                    break

        # Re-sort and re-assign IDs
        all_sources.sort(
            key=lambda s: s.get("relevance_score", 0) * 0.7 + s.get("recency_score", 0) * 0.3,
            reverse=True,
        )
        for i, src in enumerate(all_sources):
            src["id"] = i + 1

        conflicts = detect_conflicts(all_sources)
        final_follow_ups = generate_follow_up_queries(
            query,
            [{"title": s.get("title", ""), "snippet": " ".join(s.get("key_excerpts", []))} for s in all_sources],
            count=3,
        )

        result = DeepSearchResult(
            query=query,
            mode="agent",
            total_sources=len(all_sources),
            sources=[DeepSearchSource(**s) for s in all_sources],
            follow_up_queries=final_follow_ups,
            conflicts=conflicts,
            rounds_completed=len(queries_used),
            queries_used=queries_used,
        )

        return [TextContent(type="text", text=result.model_dump_json(exclude_none=True, indent=2))]

    async def handle_search_images(self, args: Dict[str, Any], searxng_client: Any) -> list[TextContent]:
        query = args["query"]
        limit = args.get("limit", 10)

        cached = await self.cache.get("images", query, limit=limit)
        if cached is not None:
            return [TextContent(type="text", text=json.dumps(cached, ensure_ascii=False, indent=2))]

        await self.rate_limiter.acquire()
        results = await searxng_client.search_images(query=query, limit=limit)

        await self.cache.set("images", query, results, limit=limit)
        return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]


def _filter_by_date_range(
    results: List[Dict[str, Any]],
    start_date: Optional[str],
    end_date: Optional[str],
) -> List[Dict[str, Any]]:
    """Filter results by published_date within [start_date, end_date]."""
    filtered: List[Dict[str, Any]] = []
    for r in results:
        pub = r.get("published_date")
        if not pub:
            filtered.append(r)
            continue
        date_str = pub[:10] if len(pub) >= 10 else pub
        if start_date and date_str < start_date:
            continue
        if end_date and date_str > end_date:
            continue
        filtered.append(r)
    return filtered
