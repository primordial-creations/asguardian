"""
Heimdall Security Scan Utilities

File scanning and directory traversal helpers.
"""

import fnmatch
import mimetypes
import os
from pathlib import Path
from typing import Callable, Generator, List, Optional, Set


SECURITY_SCAN_EXTENSIONS: Set[str] = {
    ".py",
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".java", ".kt", ".kts",
    ".go",
    ".rb",
    ".php",
    ".cs",
    ".c", ".h", ".cpp", ".hpp",
    ".rs",
    ".swift",
    ".sh", ".bash", ".zsh", ".ps1",
    ".sql",
    ".yaml", ".yml",
    ".json",
    ".xml",
    ".env",
    ".config",
    ".conf",
    ".ini",
    ".properties",
}

BINARY_EXTENSIONS: Set[str] = {
    ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".pyo", ".class",
    ".o", ".obj", ".a", ".lib",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".woff", ".woff2", ".ttf", ".eot",
    ".db", ".sqlite", ".sqlite3",
}

DEFAULT_EXCLUDE_DIRS: Set[str] = {
    "__pycache__",
    "node_modules",
    ".git",
    ".svn",
    ".hg",
    ".venv",
    "venv",
    "env",
    ".env",
    "build",
    "dist",
    ".next",
    "out",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "eggs",
    ".eggs",
    ".cache",
    ".idea",
    ".vscode",
    "vendor",
    "target",
    "bin",
    "obj",
    ".gradle",
}


def is_binary_file(file_path: Path) -> bool:
    """
    Check if a file is likely binary.

    Args:
        file_path: Path to the file

    Returns:
        True if the file appears to be binary
    """
    ext = file_path.suffix.lower()
    if ext in BINARY_EXTENSIONS:
        return True

    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type:
        if not mime_type.startswith("text/") and not mime_type.startswith("application/json"):
            if "xml" not in mime_type and "javascript" not in mime_type:
                return True

    return False


def is_excluded_path(path: Path, exclude_patterns: List[str]) -> bool:
    """
    Check if a path should be excluded from scanning.

    Args:
        path: Path to check
        exclude_patterns: List of glob patterns to exclude

    Returns:
        True if the path should be excluded
    """
    path_str = str(path)
    path_name = path.name
    path_str_normalized = path_str.replace("\\", "/")

    if path_name.startswith("."):
        if path_name not in {".env", ".config", ".htaccess"}:
            return True

    for pattern in exclude_patterns:
        pattern_normalized = pattern.replace("\\", "/")
        if fnmatch.fnmatch(path_name, pattern):
            return True
        if fnmatch.fnmatch(path_str_normalized, f"*/{pattern_normalized}/*"):
            return True
        if fnmatch.fnmatch(path_str_normalized, f"*/{pattern_normalized}"):
            return True
        if pattern_normalized in path_str_normalized:
            return True

    if path.is_dir() and path_name in DEFAULT_EXCLUDE_DIRS:
        return True

    return False


def is_confined_scan_path(path: Path, root: Path) -> bool:
    """True if *path* is not a symlink and resolves under *root*."""
    try:
        if path.is_symlink():
            return False
        return path.resolve().is_relative_to(root.resolve())
    except (OSError, RuntimeError, ValueError):
        return False


def iter_confined_files(
    root_path: Path,
    *,
    should_skip: Optional[Callable[[Path], bool]] = None,
    analysis_errors: Optional[list] = None,
) -> Generator[Path, None, None]:
    """Yield regular files under *root_path* without following symlinks.

    Directory and file symlinks are skipped. Resolved paths must stay
    under the resolved scan root (CH-0078).
    """
    root = Path(root_path)
    def record(path, kind):
        if analysis_errors is not None:
            analysis_errors.append({"stage": "discovery", "file_path": str(path), "error_type": kind})
    try:
        root_resolved = root.resolve()
    except (OSError, RuntimeError) as error:
        record(root, type(error).__name__)
        return

    def _walk(current: Path) -> Generator[Path, None, None]:
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        if should_skip is None or not should_skip(Path(entry.path)):
                            record(entry.path, "SymlinkSkipped")
                        continue
                    path = Path(entry.path)
                    try:
                        resolved = path.resolve()
                    except (OSError, RuntimeError) as error:
                        record(path, type(error).__name__)
                        continue
                    if not resolved.is_relative_to(root_resolved):
                        record(path, "OutsideRoot")
                        continue
                    if should_skip is not None and should_skip(path):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        yield from _walk(path)
                    elif entry.is_file(follow_symlinks=False):
                        yield path
        except OSError as error:
            if analysis_errors is None and not isinstance(error, (PermissionError, FileNotFoundError, NotADirectoryError)):
                raise
            record(current, type(error).__name__)
            return

    yield from _walk(root)


def scan_directory_for_security(
    root_path: Path,
    exclude_patterns: Optional[List[str]] = None,
    include_extensions: Optional[List[str]] = None,
    analysis_errors: Optional[list] = None,
) -> Generator[Path, None, None]:
    """
    Recursively scan a directory for files to analyze for security issues.

    Args:
        root_path: Root directory to scan
        exclude_patterns: Additional patterns to exclude
        include_extensions: File extensions to include (None = use defaults)

    Yields:
        Paths to files that should be scanned
    """
    if exclude_patterns is None:
        exclude_patterns = []

    all_exclusions = list(DEFAULT_EXCLUDE_DIRS) + exclude_patterns

    if include_extensions:
        valid_extensions = {e if e.startswith(".") else f".{e}" for e in include_extensions}
    else:
        valid_extensions = SECURITY_SCAN_EXTENSIONS

    def _should_skip(path: Path) -> bool:
        return is_excluded_path(path, all_exclusions)

    for entry in iter_confined_files(root_path, should_skip=_should_skip, analysis_errors=analysis_errors):
        ext = entry.suffix.lower()
        if ext in valid_extensions and not is_binary_file(entry):
            yield entry
        elif entry.name in {".env", ".htaccess", "Dockerfile"}:
            yield entry


def read_file_lines(file_path: Path) -> List[str]:
    """
    Read a file and return its lines.

    Args:
        file_path: Path to the file

    Returns:
        List of lines in the file
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.readlines()
    except (IOError, OSError):
        return []
