"""Health check and automatic engine failover."""

import asyncio
import logging
import time
from typing import Dict

from ..engines.base import SearchEngine

logger = logging.getLogger(__name__)


class HealthChecker:
    """Periodically checks engine availability and tracks health status."""

    def __init__(self, check_interval: int = 300):
        self.check_interval = check_interval
        self._status: Dict[str, bool] = {}
        self._last_check: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    def is_healthy(self, engine_name: str) -> bool:
        """Return last known health status (True if never checked)."""
        return self._status.get(engine_name, True)

    def needs_check(self, engine_name: str) -> bool:
        last = self._last_check.get(engine_name, 0)
        return (time.monotonic() - last) > self.check_interval

    async def check(self, engine: SearchEngine) -> bool:
        """Run a health check on an engine and update status."""
        async with self._lock:
            try:
                healthy = await engine.is_healthy()
                self._status[engine.name] = healthy
                self._last_check[engine.name] = time.monotonic()
                if not healthy:
                    logger.warning("Engine %s is unhealthy", engine.name)
                else:
                    logger.debug("Engine %s is healthy", engine.name)
                return healthy
            except Exception as e:
                logger.error("Health check failed for %s: %s", engine.name, e)
                self._status[engine.name] = False
                self._last_check[engine.name] = time.monotonic()
                return False

    async def check_all(self, engines: list[SearchEngine]) -> None:
        """Check all engines that need checking."""
        tasks = []
        for engine in engines:
            if self.needs_check(engine.name):
                tasks.append(self.check(engine))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_healthy_engines(self, engines: list[SearchEngine]) -> list[SearchEngine]:
        """Return engines sorted by priority, filtering out unhealthy ones."""
        healthy = [e for e in engines if self.is_healthy(e.name)]
        if not healthy:
            logger.warning("No healthy engines, falling back to all engines")
            return sorted(engines, key=lambda e: e.priority)
        return sorted(healthy, key=lambda e: e.priority)
