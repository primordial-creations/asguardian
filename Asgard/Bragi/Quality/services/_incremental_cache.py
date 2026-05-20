import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class FileHashEntry:
    """Cache entry for a single file."""
    file_path: str
    hash: str
    last_modified: float
    size: int
    last_analyzed: str
    result: Optional[Dict[str, Any]] = None


@dataclass
class IncrementalConfig:
    """Configuration for incremental scanning."""
    enabled: bool = False
    cache_path: str = ".asgard-cache.json"
    store_results: bool = True
    max_cache_age_days: int = 30


class FileHashCache:
    """
    Manages file hash cache for incremental scanning.

    Stores SHA-256 hashes of files along with their analysis results,
    allowing scanners to skip unchanged files.

    Usage:
        cache = FileHashCache(project_path)
        cache.load()

        for file in files:
            if cache.is_changed(file):
                result = analyze(file)
                cache.update(file, result)
            else:
                result = cache.get_cached_result(file)

        cache.save()
    """

    def __init__(
        self,
        project_path: Path,
        config: Optional[IncrementalConfig] = None,
    ):
        """
        Initialize the file hash cache.

        Args:
            project_path: Root path of the project
            config: Incremental scanning configuration
        """
        self.project_path = project_path
        self.config = config or IncrementalConfig()
        self.cache_file = project_path / self.config.cache_path
        self._entries: Dict[str, FileHashEntry] = {}
        self._dirty = False

    def load(self) -> bool:
        """
        Load cache from disk.

        Returns:
            True if cache was loaded successfully
        """
        if not self.cache_file.exists():
            return False

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            entries = data.get('entries', {})
            for path, entry_data in entries.items():
                self._entries[path] = FileHashEntry(**entry_data)

            self._dirty = False
            return True

        except (json.JSONDecodeError, KeyError, TypeError):
            self._entries = {}
            return False

    def save(self) -> None:
        """Save cache to disk."""
        if not self._dirty and self.cache_file.exists():
            return

        data = {
            'version': '1.0.0',
            'created_at': datetime.now().isoformat(),
            'project_path': str(self.project_path),
            'entries': {
                path: {
                    'file_path': entry.file_path,
                    'hash': entry.hash,
                    'last_modified': entry.last_modified,
                    'size': entry.size,
                    'last_analyzed': entry.last_analyzed,
                    'result': entry.result,
                }
                for path, entry in self._entries.items()
            }
        }

        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        self._dirty = False

    def is_changed(self, file_path: Path) -> bool:
        """
        Check if a file has changed since last analysis.

        Args:
            file_path: Path to the file

        Returns:
            True if file has changed or is not in cache
        """
        rel_path = self._relative_path(file_path)

        if rel_path not in self._entries:
            return True

        entry = self._entries[rel_path]

        if not file_path.exists():
            return True

        stat = file_path.stat()
        if stat.st_mtime != entry.last_modified or stat.st_size != entry.size:
            current_hash = self._compute_hash(file_path)
            return current_hash != entry.hash

        return False

    def get_cached_result(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Get cached analysis result for a file.

        Args:
            file_path: Path to the file

        Returns:
            Cached result dictionary or None if not cached
        """
        rel_path = self._relative_path(file_path)
        entry = self._entries.get(rel_path)

        if entry and entry.result:
            return entry.result

        return None

    def update(
        self,
        file_path: Path,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update cache entry for a file.

        Args:
            file_path: Path to the file
            result: Analysis result to cache (optional)
        """
        if not file_path.exists():
            return

        rel_path = self._relative_path(file_path)
        stat = file_path.stat()

        entry = FileHashEntry(
            file_path=rel_path,
            hash=self._compute_hash(file_path),
            last_modified=stat.st_mtime,
            size=stat.st_size,
            last_analyzed=datetime.now().isoformat(),
            result=result if self.config.store_results else None,
        )

        self._entries[rel_path] = entry
        self._dirty = True

    def invalidate(self, file_path: Path) -> bool:
        """
        Remove a file from the cache.

        Args:
            file_path: Path to invalidate

        Returns:
            True if entry was removed
        """
        rel_path = self._relative_path(file_path)
        if rel_path in self._entries:
            del self._entries[rel_path]
            self._dirty = True
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        self._entries = {}
        self._dirty = True

    def clean_stale(self) -> int:
        """
        Remove entries for files that no longer exist.

        Returns:
            Number of entries removed
        """
        stale_paths = []

        for rel_path in self._entries:
            full_path = self.project_path / rel_path
            if not full_path.exists():
                stale_paths.append(rel_path)

        for path in stale_paths:
            del self._entries[path]

        if stale_paths:
            self._dirty = True

        return len(stale_paths)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = len(self._entries)
        with_results = sum(1 for e in self._entries.values() if e.result)

        return {
            'total_entries': total,
            'entries_with_results': with_results,
            'cache_file': str(self.cache_file),
            'cache_exists': self.cache_file.exists(),
        }

    def filter_changed(self, files) -> list:
        """
        Filter a list of files to only those that have changed.

        Args:
            files: List of file paths

        Returns:
            List of files that have changed since last analysis
        """
        return [f for f in files if self.is_changed(f)]

    def _relative_path(self, path: Path) -> str:
        """Convert to relative path for cache key."""
        try:
            return str(path.relative_to(self.project_path))
        except ValueError:
            return str(path)

    def _compute_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file contents."""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
