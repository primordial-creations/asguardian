"""
On-disk TTL cache for live vulnerability-database lookups (OSV/NVD).

Purely a performance/politeness layer for the opt-in network path (Plan
03 Phase E / Plan 07.10): repeat runs against the same dependency set do
not need to re-hit api.osv.dev or NVD within the TTL window. This module
is never imported or touched by the default (no-network) path -- it is
only exercised from inside `VulnerabilityChecker._check_network` /
`_check_nvd`, which themselves require `enable_network=True`.

Cache location: `<cwd>/.asgard_cache/vulnerability/<sha256>.json` by
default, overridable via `cache_dir`. Set `ASGARD_NO_CACHE=1` in the
environment to bypass the cache entirely (always re-fetch, never write) --
useful for CI or when the caller wants a guaranteed-fresh answer.

The cache stores exactly what was returned by the remote API (already
serialised to plain dict/list/str data by the caller) plus a timestamp;
it never stores secrets or credentials, and the cache key is a hash of
the query content, not a raw file path, so it cannot be used for path
traversal.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24h
NO_CACHE_ENV_VAR = "ASGARD_NO_CACHE"


def _cache_disabled() -> bool:
    return os.environ.get(NO_CACHE_ENV_VAR, "").strip().lower() in ("1", "true", "yes")


def cache_key(namespace: str, payload: str) -> str:
    """Deterministic cache key: namespace-prefixed sha256 of the payload."""
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{namespace}_{digest}"


class VulnCache:
    """Small on-disk TTL cache. One JSON file per cache key."""

    def __init__(self, cache_dir: Optional[Path] = None,
                 ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.cache_dir = Path(cache_dir) if cache_dir else Path(".asgard_cache") / "vulnerability"
        self.ttl_seconds = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        """Return the cached value for `key`, or None on miss/expiry/disabled/corrupt."""
        if _cache_disabled():
            return None
        path = self.cache_dir / f"{key}.json"
        try:
            with open(path, "r", encoding="utf-8") as f:
                envelope = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None
        cached_at = envelope.get("cached_at")
        if not isinstance(cached_at, (int, float)):
            return None
        if time.time() - cached_at > self.ttl_seconds:
            return None
        return envelope.get("value")

    def set(self, key: str, value: Any) -> None:
        """Write `value` to the cache under `key`. Best-effort -- a failure
        to write the cache must never break the caller's scan."""
        if _cache_disabled():
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            path = self.cache_dir / f"{key}.json"
            envelope = {"cached_at": time.time(), "value": value}
            tmp_path = path.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(envelope, f)
            tmp_path.replace(path)
        except OSError:
            pass
