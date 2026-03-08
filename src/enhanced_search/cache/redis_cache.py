"""Optional Redis cache layer with in-memory LRU fallback."""

import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default TTL per cache prefix (seconds)
_PREFIX_TTL: Dict[str, int] = {
    "search": 1800,       # search results: 30 min
    "images": 1800,       # image results: 30 min
    "fetch": 7200,        # URL content: 2 hours (content changes less often)
    "deep_search": 1800,  # deep search: 30 min
    "extract": 3600,      # extracted data: 1 hour
}


def _cache_key(prefix: str, query: str, **kwargs: Any) -> str:
    """Generate a deterministic cache key."""
    raw = json.dumps({"q": query, **kwargs}, sort_keys=True)
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{prefix}:{h}"


class _LRUMemoryCache:
    """Simple in-memory LRU cache with TTL, used when Redis is unavailable."""

    def __init__(self, max_size: int = 200):
        self._store: OrderedDict[str, tuple] = OrderedDict()  # key -> (data, expire_ts)
        self._max_size = max_size

    def get(self, key: str) -> Optional[str]:
        if key not in self._store:
            return None
        data, expire_ts = self._store[key]
        if time.time() > expire_ts:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return data

    def set(self, key: str, value: str, ttl: int) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, time.time() + ttl)
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)


class SearchCache:
    """Redis-backed cache with in-memory LRU fallback."""

    def __init__(self, redis_url: str = "", ttl: int = 3600):
        self.default_ttl = ttl
        self._redis: Any = None
        self._redis_available = False
        self._mem = _LRUMemoryCache(max_size=200)

        if redis_url:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(
                    redis_url, decode_responses=True
                )
                self._redis_available = True
                logger.info("Redis cache enabled: %s", redis_url)
            except Exception as e:
                logger.warning("Redis unavailable, using in-memory cache: %s", e)

    @property
    def available(self) -> bool:
        return True  # always available (memory fallback)

    def _ttl_for(self, prefix: str) -> int:
        return _PREFIX_TTL.get(prefix, self.default_ttl)

    async def get(self, prefix: str, query: str, **kwargs: Any) -> Optional[List[Dict[str, Any]]]:
        """Try to retrieve cached results. Returns None on miss or error."""
        key = _cache_key(prefix, query, **kwargs)

        # Try Redis first
        if self._redis_available:
            try:
                data = await self._redis.get(key)
                if data:
                    logger.debug("Redis cache HIT: %s", key)
                    return json.loads(data)
            except Exception as e:
                logger.warning("Redis get error: %s", e)

        # Fallback to memory cache
        data = self._mem.get(key)
        if data:
            logger.debug("Memory cache HIT: %s", key)
            return json.loads(data)

        return None

    async def set(
        self,
        prefix: str,
        query: str,
        results: Any,
        **kwargs: Any,
    ) -> None:
        """Store results in cache."""
        key = _cache_key(prefix, query, **kwargs)
        ttl = self._ttl_for(prefix)
        serialized = json.dumps(results, ensure_ascii=False)

        # Always store in memory cache
        self._mem.set(key, serialized, ttl)

        # Also store in Redis if available
        if self._redis_available:
            try:
                await self._redis.set(key, serialized, ex=ttl)
                logger.debug("Redis cache SET: %s (ttl=%d)", key, ttl)
            except Exception as e:
                logger.warning("Redis set error: %s", e)

    async def close(self) -> None:
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass
