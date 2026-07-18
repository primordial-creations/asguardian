"""
Freya Crawler Politeness

Per-host minimum-interval enforcement ("token bucket" in the simplest
form: one token per host, refilled after min_interval_ms). Used by both
the discovery phase and the bounded-concurrency test phase so that
concurrent workers still behave like a single polite crawler from any
one host's point of view.

PROVISIONAL pending RESEARCH_06 (link-checking-at-scale): retry/backoff,
HEAD-vs-GET, and response caching are out of scope here and deferred to
that research landing.
"""

import asyncio
import time
from typing import Dict
from urllib.parse import urlparse


class HostRateLimiter:
    """Enforces a minimum interval between requests to the same host."""

    def __init__(self, min_interval_ms: int = 500):
        self.min_interval_s = max(0, min_interval_ms) / 1000.0
        self._last_request_at: Dict[str, float] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def _lock_for(self, host: str) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._locks.get(host)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[host] = lock
            return lock

    async def wait_for_turn(self, url: str) -> None:
        """Block until it is polite to request `url`'s host again."""
        host = urlparse(url).netloc or url
        if self.min_interval_s <= 0:
            return
        lock = await self._lock_for(host)
        async with lock:
            now = time.monotonic()
            last = self._last_request_at.get(host)
            if last is not None:
                elapsed = now - last
                remaining = self.min_interval_s - elapsed
                if remaining > 0:
                    await asyncio.sleep(remaining)
            self._last_request_at[host] = time.monotonic()
