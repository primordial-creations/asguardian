"""
Incremental Scanner Infrastructure

Provides caching support to skip re-analyzing unchanged files.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar

from Asgard.Heimdall.Quality.services._incremental_cache import (
    FileHashCache,
    FileHashEntry,
    IncrementalConfig,
)

R = TypeVar('R')  # Result type

# Re-export for public API compatibility
__all__ = [
    "FileHashEntry",
    "IncrementalConfig",
    "FileHashCache",
    "IncrementalScannerMixin",
]


class IncrementalScannerMixin:
    """
    Mixin class to add incremental scanning capabilities to existing scanners.

    Usage:
        class MyScanner(IncrementalScannerMixin):
            def __init__(self, config):
                self.incremental_config = IncrementalConfig(
                    enabled=config.incremental,
                    cache_path=config.cache_path,
                )
                self._init_cache(Path(config.scan_path))

            def analyze(self, path: Path):
                files = self._discover_files(path)

                if self.incremental_config.enabled:
                    files = self._filter_changed_files(files)

                for file in files:
                    result = self._analyze_file(file)
                    self._update_cache(file, result)

                self._save_cache()
    """

    incremental_config: IncrementalConfig
    _file_cache: Optional[FileHashCache] = None

    def _init_cache(self, project_path: Path) -> None:
        """Initialize the file hash cache."""
        self._file_cache = FileHashCache(project_path, self.incremental_config)
        if self.incremental_config.enabled:
            self._file_cache.load()

    def _filter_changed_files(self, files: List[Path]) -> List[Path]:
        """Filter files to only those that have changed."""
        if not self._file_cache or not self.incremental_config.enabled:
            return files
        return self._file_cache.filter_changed(files)

    def _get_cached_result(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Get cached result for a file."""
        if not self._file_cache or not self.incremental_config.enabled:
            return None
        return self._file_cache.get_cached_result(file_path)

    def _update_cache(
        self,
        file_path: Path,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update cache for a file."""
        if not self._file_cache or not self.incremental_config.enabled:
            return
        self._file_cache.update(file_path, result)

    def _save_cache(self) -> None:
        """Save the cache to disk."""
        if self._file_cache and self.incremental_config.enabled:
            self._file_cache.save()

    def _get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self._file_cache:
            return {}
        return self._file_cache.get_stats()
