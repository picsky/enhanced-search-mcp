"""Comprehensive capability test for enhanced-search-mcp.
Runs directly against core logic, bypassing MCP transport to avoid hanging.
"""

import asyncio
import json
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, r"c:\Users\Report02\Downloads\enhanced-search-mcp\src")

from enhanced_search.config import config
from enhanced_search.engines.searxng import SearXNGClient
from enhanced_search.engines.duckduckgo import DuckDuckGoClient
from enhanced_search.engines.fetcher import ContentFetcher
from enhanced_search.utils.dedup import ResultDeduplicator
from enhanced_search.utils.text_analysis import (
    compute_relevance_score,
    compute_recency_score,
    extract_key_paragraphs,
    generate_follow_up_queries,
    detect_conflicts,
)
from enhanced_search.utils.rate_limit import TokenBucketRateLimiter
from enhanced_search.cache.redis_cache import SearchCache
from enhanced_search.handlers.history import SearchHistory

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"
results: List[Dict[str, Any]] = []


def record(name: str, status: str, detail: str = "", elapsed: float = 0.0) -> None:
    results.append({"name": name, "status": status, "detail": detail, "elapsed": elapsed})
    icon = PASS if status == "pass" else (FAIL if status == "fail" else WARN)
    t = f" ({elapsed:.2f}s)" if elapsed else ""
    print(f"  {icon} {name}{t} {detail}")


async def test_searxng_search() -> None:
    """Test SearXNG basic search."""
    client = SearXNGClient(config.SEARXNG_URL, timeout=15)
    try:
        start = time.time()
        res = await client.search("Python programming", limit=5)
        elapsed = time.time() - start
        if len(res) > 0:
            record("SearXNG search", "pass", f"{len(res)} results", elapsed)
        else:
            record("SearXNG search", "warn", "0 results returned", elapsed)
    except Exception as e:
        record("SearXNG search", "fail", str(e))
    finally:
        await client.close()


async def test_searxng_empty_query() -> None:
    """Test SearXNG with empty query."""
    client = SearXNGClient(config.SEARXNG_URL, timeout=10)
    try:
        start = time.time()
        res = await client.search("", limit=3)
        elapsed = time.time() - start
        record("SearXNG empty query", "pass" if len(res) == 0 else "warn",
               f"{len(res)} results (expected 0)", elapsed)
    except Exception as e:
        record("SearXNG empty query", "pass", f"raised error as expected: {type(e).__name__}")
    finally:
        await client.close()


async def test_searxng_special_chars() -> None:
    """Test SearXNG with special characters."""
    client = SearXNGClient(config.SEARXNG_URL, timeout=15)
    try:
        start = time.time()
        res = await client.search("C++ \"hello world\" <script>alert(1)</script>", limit=3)
        elapsed = time.time() - start
        record("SearXNG special chars", "pass", f"{len(res)} results", elapsed)
    except Exception as e:
        record("SearXNG special chars", "fail", str(e))
    finally:
        await client.close()


async def test_searxng_chinese_query() -> None:
    """Test SearXNG with Chinese query."""
    client = SearXNGClient(config.SEARXNG_URL, timeout=15)
    try:
        start = time.time()
        res = await client.search("人工智能最新发展", limit=5)
        elapsed = time.time() - start
        record("SearXNG Chinese query", "pass" if len(res) > 0 else "warn",
               f"{len(res)} results", elapsed)
    except Exception as e:
        record("SearXNG Chinese query", "fail", str(e))
    finally:
        await client.close()


async def test_searxng_image_search() -> None:
    """Test SearXNG image search."""
    client = SearXNGClient(config.SEARXNG_URL, timeout=15)
    try:
        start = time.time()
        res = await client.search_images("sunset landscape", limit=3)
        elapsed = time.time() - start
        has_img = all(r.get("img_src") for r in res) if res else False
        record("SearXNG image search", "pass" if has_img else "warn",
               f"{len(res)} images, img_src present={has_img}", elapsed)
    except Exception as e:
        record("SearXNG image search", "fail", str(e))
    finally:
        await client.close()


async def test_duckduckgo_search() -> None:
    """Test DuckDuckGo fallback engine."""
    client = DuckDuckGoClient()
    try:
        start = time.time()
        res = await asyncio.wait_for(client.search("Python programming", limit=5), timeout=15)
        elapsed = time.time() - start
        record("DuckDuckGo search", "pass" if len(res) > 0 else "warn",
               f"{len(res)} results", elapsed)
    except asyncio.TimeoutError:
        record("DuckDuckGo search", "warn", "timed out after 15s")
    except Exception as e:
        record("DuckDuckGo search", "fail", str(e))


async def test_duckduckgo_health() -> None:
    """Test DuckDuckGo health check."""
    client = DuckDuckGoClient()
    try:
        healthy = await asyncio.wait_for(client.is_healthy(), timeout=10)
        record("DuckDuckGo health", "pass", f"healthy={healthy}")
    except asyncio.TimeoutError:
        record("DuckDuckGo health", "warn", "timed out")
    except Exception as e:
        record("DuckDuckGo health", "fail", str(e))


async def test_fetcher_valid_url() -> None:
    """Test fetching a valid URL."""
    fetcher = ContentFetcher(timeout=15)
    try:
        start = time.time()
        res = await fetcher.fetch("https://httpbin.org/html", max_length=2000)
        elapsed = time.time() - start
        success = res.get("success", False)
        has_content = bool(res.get("content"))
        record("Fetch valid URL", "pass" if success and has_content else "fail",
               f"success={success}, content_len={len(res.get('content', '') or '')}", elapsed)
    except Exception as e:
        record("Fetch valid URL", "fail", str(e))
    finally:
        await fetcher.close()


async def test_fetcher_invalid_url() -> None:
    """Test fetching an invalid URL - should not hang."""
    fetcher = ContentFetcher(timeout=5)
    try:
        start = time.time()
        res = await asyncio.wait_for(
            fetcher.fetch("https://this-domain-does-not-exist-99999.com"),
            timeout=10,
        )
        elapsed = time.time() - start
        if not res.get("success"):
            record("Fetch invalid URL", "pass", f"graceful error: {res.get('error', '')[:60]}", elapsed)
        else:
            record("Fetch invalid URL", "warn", "unexpectedly succeeded", elapsed)
    except asyncio.TimeoutError:
        record("Fetch invalid URL", "fail", "HUNG - no timeout handling!")
    except Exception as e:
        record("Fetch invalid URL", "pass", f"raised {type(e).__name__}")
    finally:
        await fetcher.close()


async def test_fetcher_404_url() -> None:
    """Test fetching a 404 URL."""
    fetcher = ContentFetcher(timeout=10)
    try:
        start = time.time()
        res = await fetcher.fetch("https://httpbin.org/status/404")
        elapsed = time.time() - start
        if not res.get("success"):
            record("Fetch 404 URL", "pass", f"error={res.get('error', '')[:60]}", elapsed)
        else:
            record("Fetch 404 URL", "warn", "returned success for 404")
    except Exception as e:
        record("Fetch 404 URL", "pass", f"raised {type(e).__name__}")
    finally:
        await fetcher.close()


async def test_fetcher_markdown_format() -> None:
    """Test markdown output format."""
    fetcher = ContentFetcher(timeout=15)
    try:
        start = time.time()
        res = await fetcher.fetch("https://httpbin.org/html", output_format="markdown")
        elapsed = time.time() - start
        content = res.get("content", "")
        has_md = "#" in content or "**" in content or content.strip() != ""
        record("Fetch markdown format", "pass" if has_md else "warn",
               f"content_len={len(content)}", elapsed)
    except Exception as e:
        record("Fetch markdown format", "fail", str(e))
    finally:
        await fetcher.close()


def test_dedup_empty() -> None:
    """Test dedup with empty input."""
    dedup = ResultDeduplicator()
    res = dedup.deduplicate([])
    record("Dedup empty input", "pass" if res == [] else "fail", f"len={len(res)}")


def test_dedup_single() -> None:
    """Test dedup with single item."""
    dedup = ResultDeduplicator()
    items = [{"url": "https://a.com", "title": "Hello"}]
    res = dedup.deduplicate(items)
    record("Dedup single item", "pass" if len(res) == 1 else "fail", f"len={len(res)}")


def test_dedup_exact_url() -> None:
    """Test dedup removes exact URL duplicates."""
    dedup = ResultDeduplicator()
    items = [
        {"url": "https://a.com", "title": "First", "snippet": "long text"},
        {"url": "https://a.com", "title": "Second"},
    ]
    res = dedup.deduplicate(items)
    record("Dedup exact URL", "pass" if len(res) == 1 else "fail", f"len={len(res)}")


def test_dedup_large_input() -> None:
    """Test dedup performance with 500 items."""
    dedup = ResultDeduplicator()
    items = [{"url": f"https://example.com/{i}", "title": f"Article about topic {i}"} for i in range(500)]
    start = time.time()
    res = dedup.deduplicate(items)
    elapsed = time.time() - start
    record("Dedup 500 items perf", "pass" if elapsed < 1.0 else "warn",
           f"len={len(res)}", elapsed)


def test_sort_by_quality() -> None:
    """Test quality sorting."""
    dedup = ResultDeduplicator()
    items = [
        {"url": "https://a.com", "title": "Short", "snippet": ""},
        {"url": "https://b.com", "title": "Long Title Here", "snippet": "A detailed snippet with info"},
    ]
    res = dedup.sort_by_quality(items)
    first_has_snippet = bool(res[0].get("snippet"))
    record("Sort by quality", "pass" if first_has_snippet else "warn",
           f"first={res[0].get('title', '')[:30]}")


def test_relevance_score_edge_cases() -> None:
    """Test relevance scoring edge cases."""
    s1 = compute_relevance_score("", "title", "snippet", "google")
    s2 = compute_relevance_score("test", "", "", "")
    s3 = compute_relevance_score("python tutorial", "Python Tutorial Guide", "Learn Python programming", "google, bing")
    record("Relevance empty query", "pass" if s1 == 0.0 else "warn", f"score={s1}")
    record("Relevance empty result", "pass" if 0 <= s2 <= 1 else "fail", f"score={s2}")
    record("Relevance multi-engine", "pass" if s3 > 0.5 else "warn", f"score={s3:.3f}")


def test_recency_score_edge_cases() -> None:
    """Test recency scoring edge cases."""
    s1 = compute_recency_score(None)
    s2 = compute_recency_score("")
    s3 = compute_recency_score("not-a-date")
    s4 = compute_recency_score("2025-01-01")
    record("Recency None date", "pass" if s1 == 0.0 else "fail", f"score={s1}")
    record("Recency empty date", "pass" if s2 == 0.0 else "fail", f"score={s2}")
    record("Recency invalid date", "pass" if s3 == 0.0 else "warn", f"score={s3}")
    record("Recency valid date", "pass" if 0 < s4 <= 1 else "warn", f"score={s4:.3f}")


def test_extract_key_paragraphs() -> None:
    """Test key paragraph extraction."""
    content = "Python is great.\n\nPython is used in AI.\n\nJava is verbose.\n\nRust is fast."
    res = extract_key_paragraphs(content, "Python AI", top_k=2)
    record("Extract paragraphs", "pass" if len(res) <= 2 else "fail", f"count={len(res)}")

    empty = extract_key_paragraphs("", "test", top_k=3)
    record("Extract empty content", "pass" if len(empty) == 0 else "warn", f"count={len(empty)}")


def test_follow_up_queries() -> None:
    """Test follow-up query generation."""
    results_data = [
        {"title": "Python 3.12 new features", "snippet": "Pattern matching and performance"},
        {"title": "Python vs JavaScript", "snippet": "Comparison of languages"},
    ]
    fups = generate_follow_up_queries("Python", results_data, count=3)
    record("Follow-up queries", "pass" if 0 < len(fups) <= 3 else "warn", f"count={len(fups)}")

    empty_fups = generate_follow_up_queries("test", [], count=3)
    record("Follow-up empty results", "pass" if len(empty_fups) == 0 else "warn",
           f"count={len(empty_fups)}")


def test_conflict_detection() -> None:
    """Test conflict detection."""
    sources = [
        {"title": "Source A", "key_excerpts": ["The population is 100 million"]},
        {"title": "Source B", "key_excerpts": ["The population is 200 million"]},
    ]
    conflicts = detect_conflicts(sources)
    record("Conflict detection", "pass" if len(conflicts) > 0 else "warn",
           f"conflicts={len(conflicts)}")


def test_search_history() -> None:
    """Test search history operations."""
    history = SearchHistory()
    history.add("test query", "search", 5)
    history.add("another query", "deep_search", 3)
    items = history.list_all()
    record("History add+list", "pass" if len(items) == 2 else "fail", f"count={len(items)}")

    item = history.get(1)
    record("History get by id", "pass" if item and item["query"] == "test query" else "fail",
           f"query={item['query'] if item else 'None'}")

    history.clear()
    items = history.list_all()
    record("History clear", "pass" if len(items) == 0 else "fail", f"count={len(items)}")

    missing = history.get(999)
    record("History get missing", "pass" if missing is None else "fail", f"result={missing}")


async def test_rate_limiter() -> None:
    """Test rate limiter behavior."""
    limiter = TokenBucketRateLimiter(rpm=600)
    start = time.time()
    for _ in range(5):
        await limiter.acquire()
    elapsed = time.time() - start
    record("Rate limiter 5 acquires", "pass" if elapsed < 1.0 else "warn", elapsed=elapsed)


def test_cache_key_consistency() -> None:
    """Test cache key generation via module-level _cache_key."""
    from enhanced_search.cache.redis_cache import _cache_key
    k1 = _cache_key("search", "test", limit=10)
    k2 = _cache_key("search", "test", limit=10)
    k3 = _cache_key("search", "test", limit=20)
    record("Cache key same params", "pass" if k1 == k2 else "fail")
    record("Cache key diff params", "pass" if k1 != k3 else "fail")


async def test_cache_roundtrip() -> None:
    """Test cache set/get roundtrip."""
    cache = SearchCache()
    await cache.set("search", "roundtrip_test", [{"title": "cached"}], limit=5)
    hit = await cache.get("search", "roundtrip_test", limit=5)
    record("Cache roundtrip", "pass" if hit and hit[0]["title"] == "cached" else "fail",
           f"hit={hit is not None}")
    miss = await cache.get("search", "roundtrip_test", limit=99)
    record("Cache miss diff params", "pass" if miss is None else "fail")


async def test_searxng_health() -> None:
    """Test SearXNG health check."""
    client = SearXNGClient(config.SEARXNG_URL, timeout=10)
    try:
        healthy = await asyncio.wait_for(client.is_healthy(), timeout=10)
        record("SearXNG health check", "pass" if healthy else "warn", f"healthy={healthy}")
    except asyncio.TimeoutError:
        record("SearXNG health check", "fail", "timed out!")
    finally:
        await client.close()


async def test_searxng_no_url() -> None:
    """Test SearXNG with empty base_url."""
    client = SearXNGClient("", timeout=5)
    res = await client.search("test", limit=3)
    healthy = await client.is_healthy()
    record("SearXNG no URL search", "pass" if len(res) == 0 else "fail", f"len={len(res)}")
    record("SearXNG no URL health", "pass" if not healthy else "fail", f"healthy={healthy}")


async def main() -> None:
    print("=" * 60)
    print("Enhanced Search MCP - Capability & Robustness Test")
    print("=" * 60)

    print("\n--- SearXNG Engine ---")
    await test_searxng_health()
    await test_searxng_search()
    await test_searxng_empty_query()
    await test_searxng_special_chars()
    await test_searxng_chinese_query()
    await test_searxng_image_search()
    await test_searxng_no_url()

    print("\n--- DuckDuckGo Engine ---")
    await test_duckduckgo_health()
    await test_duckduckgo_search()

    print("\n--- Content Fetcher ---")
    await test_fetcher_valid_url()
    await test_fetcher_invalid_url()
    await test_fetcher_404_url()
    await test_fetcher_markdown_format()

    print("\n--- Dedup & Sorting ---")
    test_dedup_empty()
    test_dedup_single()
    test_dedup_exact_url()
    test_dedup_large_input()
    test_sort_by_quality()

    print("\n--- Text Analysis ---")
    test_relevance_score_edge_cases()
    test_recency_score_edge_cases()
    test_extract_key_paragraphs()
    test_follow_up_queries()
    test_conflict_detection()

    print("\n--- Search History ---")
    test_search_history()

    print("\n--- Rate Limiter ---")
    await test_rate_limiter()

    print("\n--- Cache ---")
    test_cache_key_consistency()
    await test_cache_roundtrip()

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r["status"] == "pass")
    warned = sum(1 for r in results if r["status"] == "warn")
    failed = sum(1 for r in results if r["status"] == "fail")
    print(f"TOTAL: {len(results)} tests | {PASS} {passed} passed | {WARN} {warned} warnings | {FAIL} {failed} failed")

    if warned + failed > 0:
        print("\n--- Issues Found ---")
        for r in results:
            if r["status"] != "pass":
                icon = WARN if r["status"] == "warn" else FAIL
                print(f"  {icon} {r['name']}: {r['detail']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
