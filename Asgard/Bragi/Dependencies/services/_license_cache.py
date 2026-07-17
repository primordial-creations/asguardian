"""
Bragi License Disk Cache (Plan 03 Phase D)

Implements the cache the config always promised: `LicenseConfig.use_cache`
and `cache_expiry_days` were previously backed by an in-memory dict that died
with the process, so every run re-hit `pip show` per package and then
pypi.org serially.

Storage: `.asgard_cache/bragi_license_cache.json` under the scan path —
`{package: {version, license_name, license_classifier, source, fetched_at}}`.
Entries expire after `cache_expiry_days`. Corrupt or unreadable cache files
are treated as empty (caching is best-effort, never fatal).
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

CACHE_RELATIVE_PATH = Path(".asgard_cache") / "bragi_license_cache.json"
CACHE_VERSION = "1.0.0"


class LicenseDiskCache:
    """Disk-backed license lookup cache with day-granularity expiry."""

    def __init__(self, scan_path: Path, expiry_days: int = 7,
                 cache_path: Optional[Path] = None,
                 now: Optional[datetime] = None):
        self.scan_path = Path(scan_path)
        self.expiry_days = expiry_days
        self.cache_path = cache_path or (self.scan_path / CACHE_RELATIVE_PATH)
        self._now = now  # injectable clock for tests
        self._entries: Dict[str, dict] = self._load()
        self._dirty = False

    def _current_time(self) -> datetime:
        return self._now or datetime.now()

    def _load(self) -> Dict[str, dict]:
        if not self.cache_path.exists():
            return {}
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") != CACHE_VERSION:
                return {}
            entries = data.get("packages", {})
            return entries if isinstance(entries, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def get(self, package_name: str) -> Optional[dict]:
        """Return the cached record for a package, or None if absent/expired."""
        entry = self._entries.get(package_name.lower())
        if entry is None:
            return None
        try:
            fetched_at = datetime.fromisoformat(entry.get("fetched_at", ""))
        except (TypeError, ValueError):
            return None
        if self._current_time() - fetched_at > timedelta(days=self.expiry_days):
            return None
        return entry

    def put(self, package_name: str, record: dict) -> None:
        """Store a record (fetched_at stamped automatically)."""
        record = dict(record)
        record["fetched_at"] = self._current_time().isoformat()
        self._entries[package_name.lower()] = record
        self._dirty = True

    def save(self) -> None:
        """Persist the cache (best-effort; no-op when nothing changed)."""
        if not self._dirty:
            return
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"version": CACHE_VERSION, "packages": self._entries}
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=1, sort_keys=True)
            self._dirty = False
        except OSError:
            pass
