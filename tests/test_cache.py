"""Tests for the cache module."""

import asyncio
import time

import pytest

from enhanced_search.cache.redis_cache import SearchCache, _LRUMemoryCache, _cache_key


class TestCacheKey:
    def test_deterministic(self) -> None:
        k1 = _cache_key("search", "python", limit=10)
        k2 = _cache_key("search", "python", limit=10)
        assert k1 == k2

    def test_different_queries_different_keys(self) -> None:
        k1 = _cache_key("search", "python", limit=10)
        k2 = _cache_key("search", "java", limit=10)
        assert k1 != k2

    def test_different_params_different_keys(self) -> None:
        k1 = _cache_key("search", "python", limit=10)
        k2 = _cache_key("search", "python", limit=20)
        assert k1 != k2

    def test_prefix_in_key(self) -> None:
        k = _cache_key("images", "cats")
        assert k.startswith("images:")


class TestLRUMemoryCache:
    def test_get_miss(self) -> None:
        cache = _LRUMemoryCache(max_size=10)
        assert cache.get("nonexistent") is None

    def test_set_and_get(self) -> None:
        cache = _LRUMemoryCache(max_size=10)
        cache.set("key1", '{"data": 1}', ttl=3600)
        assert cache.get("key1") == '{"data": 1}'

    def test_ttl_expiry(self) -> None:
        cache = _LRUMemoryCache(max_size=10)
        cache.set("key1", "value", ttl=0)
        time.sleep(0.01)
        assert cache.get("key1") is None

    def test_lru_eviction(self) -> None:
        cache = _LRUMemoryCache(max_size=2)
        cache.set("a", "1", ttl=3600)
        cache.set("b", "2", ttl=3600)
        cache.set("c", "3", ttl=3600)
        assert cache.get("a") is None
        assert cache.get("b") == "2"
        assert cache.get("c") == "3"

    def test_access_updates_lru_order(self) -> None:
        cache = _LRUMemoryCache(max_size=2)
        cache.set("a", "1", ttl=3600)
        cache.set("b", "2", ttl=3600)
        cache.get("a")  # access 'a' to make it most recent
        cache.set("c", "3", ttl=3600)  # evicts 'b' (least recent)
        assert cache.get("a") == "1"
        assert cache.get("b") is None
        assert cache.get("c") == "3"


class TestSearchCache:
    """Test SearchCache with in-memory fallback (no Redis)."""

    def test_init_without_redis(self) -> None:
        cache = SearchCache(redis_url="", ttl=3600)
        assert cache.available is True
        assert cache._redis_available is False

    @pytest.mark.asyncio
    async def test_get_miss(self) -> None:
        cache = SearchCache(redis_url="", ttl=3600)
        result = await cache.get("search", "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get(self) -> None:
        cache = SearchCache(redis_url="", ttl=3600)
        data = [{"title": "test", "url": "https://example.com"}]
        await cache.set("search", "python", data)
        result = await cache.get("search", "python")
        assert result == data

    @pytest.mark.asyncio
    async def test_different_prefixes_isolated(self) -> None:
        cache = SearchCache(redis_url="", ttl=3600)
        await cache.set("search", "query", [{"type": "search"}])
        await cache.set("images", "query", [{"type": "images"}])
        search_result = await cache.get("search", "query")
        images_result = await cache.get("images", "query")
        assert search_result != images_result

    @pytest.mark.asyncio
    async def test_close_without_error(self) -> None:
        cache = SearchCache(redis_url="", ttl=3600)
        await cache.close()
