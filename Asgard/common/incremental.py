"""
Incremental Processing Infrastructure

Provides caching support to skip re-processing unchanged items.
Used by Heimdall for file analysis, Freya for URL testing, etc.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Union

from Asgard.common._hash_cache import FileHashCache
from Asgard.common._incremental_models import HashEntry, IncrementalConfig


class IncrementalMixin:
    """
    Mixin class to add incremental processing capabilities.

    Usage:
        class MyScanner(IncrementalMixin):
            def __init__(self, config):
                self.incremental_config = IncrementalConfig(
                    enabled=config.incremental,
                )
                self._init_cache(Path(config.path))

            def analyze(self, items):
                if self.incremental_config.enabled:
                    items = self._filter_changed(items)
                # Process items...
                self._save_cache()
    """

    incremental_config: IncrementalConfig
    _cache: Optional[FileHashCache] = None

    def _init_cache(self, project_path: Path) -> None:
        """Initialize the cache."""
        self._cache = FileHashCache(project_path, self.incremental_config)
        if self.incremental_config.enabled:
            self._cache.load()

    def _is_changed(
        self,
        item_id: str,
        content: Optional[Union[str, bytes, Path]] = None,
    ) -> bool:
        """Check if item has changed."""
        if not self._cache or not self.incremental_config.enabled:
            return True
        return self._cache.is_changed(item_id, content)

    def _get_cached(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get cached result."""
        if not self._cache or not self.incremental_config.enabled:
            return None
        return self._cache.get_cached_result(item_id)

    def _update_cache(
        self,
        item_id: str,
        content: Optional[Union[str, bytes, Path]] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update cache entry."""
        if not self._cache or not self.incremental_config.enabled:
            return
        self._cache.update(item_id, content, result)

    def _save_cache(self) -> None:
        """Save cache to disk."""
        if self._cache and self.incremental_config.enabled:
            self._cache.save()

    def _get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self._cache:
            return {}
        return self._cache.get_stats()


__all__ = [
    "FileHashCache",
    "HashEntry",
    "IncrementalConfig",
    "IncrementalMixin",
]
