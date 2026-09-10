"""
Heimdall Quality File Utilities

Helper functions for file discovery, path filtering, and line counting.
"""

import fnmatch
import os
from pathlib import Path
from typing import Iterator, List, Optional, Set

CODE_EXTENSIONS: Set[str] = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".go", ".rb",
    ".php", ".scala", ".kt", ".swift", ".rs", ".c", ".cpp", ".h", ".hpp",
    ".sh", ".bash", ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg",
    ".html", ".css", ".scss", ".sass", ".less", ".sql", ".tf", ".hcl",
}

DEFAULT_EXCLUDE_DIRS: Set[str] = {
    "__pycache__", "node_modules", ".git", ".venv", "venv", "env",
    ".env", "build", "dist", ".next", "coverage", ".tox", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "htmlcov", "eggs", ".eggs",
    "*.egg-info", "migrations", "assets", "*-venv", "site-packages",
}

DEFAULT_EXCLUDE_FILES: Set[str] = {
    "*.min.js", "*.min.css", "*.pyc", "*.pyo", "*.pyd",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "*.map", "*.snap",
}


def get_file_extension(file_path: str) -> str:
    """Return the lowercase extension of a file path."""
    return Path(file_path).suffix.lower()


def is_code_file(file_path: str, include_extensions: Optional[List[str]] = None) -> bool:
    """Return True if the file is a recognised code file."""
    ext = get_file_extension(file_path)
    if include_extensions is not None:
        return ext in {e.lower() for e in include_extensions}
    return ext in CODE_EXTENSIONS


def is_excluded_path(
    file_path: str,
    exclude_patterns: Optional[List[str]] = None,
) -> bool:
    """Return True if any component of the path matches an exclusion pattern."""
    patterns = exclude_patterns if exclude_patterns is not None else list(DEFAULT_EXCLUDE_DIRS)
    path = Path(file_path)
    parts = list(path.parts) + [path.name]
    for pattern in patterns:
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
        if fnmatch.fnmatch(str(file_path), pattern):
            return True
    return False


def count_lines(file_path: str, *, strict_io: bool = False) -> int:
    """Count the total number of lines in a file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            return sum(1 for _ in fh)
    except OSError:
        if strict_io:
            raise
        return 0


def scan_directory(
    root: str,
    include_extensions: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    *,
    strict_io: bool = False,
) -> Iterator[Path]:
    """Yield absolute paths of code files under root, respecting exclusions."""
    from Asgard.Bragi.Quality.languages._confined_walk import iter_confined_regular_files

    for full_path in iter_confined_regular_files(
        Path(root), exclude_patterns=exclude_patterns, strict_io=strict_io
    ):
        if is_code_file(str(full_path), include_extensions):
            yield full_path


def discover_files(
    root: str,
    exclude_patterns: Optional[List[str]] = None,
    include_extensions: Optional[List[str]] = None,
) -> Iterator[Path]:
    """Alias for scan_directory for backward compatibility with CLI dry-run."""
    yield from scan_directory(root, include_extensions, exclude_patterns)
