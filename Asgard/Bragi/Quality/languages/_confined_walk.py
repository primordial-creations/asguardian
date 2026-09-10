"""Confined file walk for language analyzers (CH-0042).

Does not follow directory or file symlinks. Applies advertised exclude
patterns, extension allowlists, and line/finding caps before regex.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Callable,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Set,
)

DEFAULT_MAX_LINE_CHARS = 4096
_LINE_DRAIN_CHUNK = 65536

ALLOWED_LANGUAGE_EXTENSIONS: Set[str] = {
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".sh",
    ".bash",
    ".zsh",
    ".ksh",
    ".java",
    ".go",
    ".rb",
    ".rake",
    ".gemspec",
    ".php",
    ".php3",
    ".php4",
    ".php5",
    ".phtml",
    ".cs",
    ".cpp",
    ".cc",
    ".cxx",
    ".c",
    ".h",
    ".hpp",
    ".hxx",
    ".rs",
}

JS_EXTENSIONS = frozenset({".js", ".jsx", ".mjs", ".cjs"})
TS_EXTENSIONS = frozenset({".ts", ".tsx"})
SHELL_EXTENSIONS = frozenset({".sh", ".bash", ".zsh", ".ksh"})
JAVA_EXTENSIONS = frozenset({".java"})
GO_EXTENSIONS = frozenset({".go"})
RUBY_EXTENSIONS = frozenset({".rb", ".rake", ".gemspec"})
PHP_EXTENSIONS = frozenset({".php", ".php3", ".php4", ".php5", ".phtml"})
CSHARP_EXTENSIONS = frozenset({".cs"})
CPP_EXTENSIONS = frozenset({".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".hxx"})
RUST_EXTENSIONS = frozenset({".rs"})


@dataclass(frozen=True)
class CappedSource:
    """Source lines after max_file_lines / max_line_chars caps."""

    lines: List[str]
    exceeded_line_limit: bool


def normalize_extensions(
    requested: Iterable[str],
    allowed: Iterable[str] = ALLOWED_LANGUAGE_EXTENSIONS,
) -> Set[str]:
    """Return requested extensions that are in the allowlist.

    Drops empty values, wildcards, and path separators so include_extensions
    cannot widen the walk.
    """
    allowed_set = {
        _normalize_ext(item) for item in allowed if _normalize_ext(item)
    }
    result: Set[str] = set()
    for item in requested:
        ext = _normalize_ext(item)
        if ext and ext in allowed_set:
            result.add(ext)
    return result


def _normalize_ext(value: str) -> Optional[str]:
    if not value:
        return None
    ext = value.lower()
    if not ext.startswith("."):
        ext = f".{ext}"
    if any(char in ext for char in ("*", "?", "[", "]", "/", "\\")):
        return None
    if ext == ".":
        return None
    return ext


def matches_exclude(path: Path, exclude_patterns: Sequence[str]) -> bool:
    """True if *path* matches any advertised exclude pattern."""
    if not exclude_patterns:
        return False
    path_str = str(path).replace("\\", "/")
    name = path.name
    parts = path.parts
    for pattern in exclude_patterns:
        pat = pattern.replace("\\", "/")
        if not pat:
            continue
        if fnmatch.fnmatch(name, pat):
            return True
        if fnmatch.fnmatch(path_str, pat):
            return True
        if fnmatch.fnmatch(path_str, f"*/{pat}"):
            return True
        if fnmatch.fnmatch(path_str, f"*/{pat}/*"):
            return True
        for part in parts:
            if fnmatch.fnmatch(part, pat):
                return True
    return False


def _is_confined(path: Path, root_resolved: Path) -> bool:
    try:
        if path.is_symlink():
            return False
        return path.resolve().is_relative_to(root_resolved)
    except (OSError, RuntimeError, ValueError):
        return False


def iter_confined_regular_files(
    root: Path,
    *,
    exclude_patterns: Optional[Sequence[str]] = None,
    strict_io: bool = False,
) -> Iterator[Path]:
    """Yield regular files under *root* without following symlinks."""
    patterns = list(exclude_patterns or ())
    start = Path(root)
    try:
        root_resolved = start.resolve()
    except (OSError, RuntimeError):
        if strict_io:
            raise
        return

    if start.is_symlink():
        if strict_io:
            raise OSError("Scan root is a symlink")
        return
    if start.is_file():
        if _is_confined(start, root_resolved) and not matches_exclude(start, patterns):
            yield start
        return
    if not start.is_dir():
        if strict_io:
            raise OSError("Scan root is not a directory or regular file")
        return

    def on_error(error: OSError) -> None:
        if strict_io:
            raise error

    for dirpath, dirnames, filenames in os.walk(start, followlinks=False, onerror=on_error):
        current = Path(dirpath)
        keep: List[str] = []
        for name in dirnames:
            child = current / name
            if matches_exclude(child, patterns):
                continue
            if child.is_symlink():
                if strict_io:
                    raise OSError("Scan includes a directory symlink")
                continue
            if not _is_confined(child, root_resolved):
                if strict_io:
                    raise OSError("Directory confinement could not be established")
                continue
            keep.append(name)
        dirnames[:] = keep

        for name in filenames:
            path = current / name
            if matches_exclude(path, patterns):
                continue
            if path.is_symlink():
                if strict_io:
                    raise OSError("Scan includes a file symlink")
                continue
            if not _is_confined(path, root_resolved):
                if strict_io:
                    raise OSError("File confinement could not be established")
                continue
            if not path.is_file():
                if strict_io:
                    raise OSError("Scan entry is not a regular file")
                continue
            yield path


def iter_language_files(
    root: Path,
    *,
    include_extensions: Iterable[str],
    exclude_patterns: Optional[Sequence[str]] = None,
    allowed_extensions: Iterable[str] = ALLOWED_LANGUAGE_EXTENSIONS,
) -> Iterator[Path]:
    """Yield confined source files whose suffix is in the allowlist."""
    allowed = normalize_extensions(include_extensions, allowed_extensions)
    if not allowed:
        return
    for path in iter_confined_regular_files(root, exclude_patterns=exclude_patterns):
        if path.suffix.lower() in allowed:
            yield path


def _read_capped_line(handle: Any, max_line_chars: int) -> Optional[str]:
    chunk = handle.readline(max_line_chars + 1)
    if chunk == "":
        return None
    overflow = len(chunk) > max_line_chars and not chunk.endswith(("\n", "\r"))
    if overflow:
        while True:
            more = handle.readline(_LINE_DRAIN_CHUNK)
            if more == "" or more.endswith(("\n", "\r")):
                break
    if chunk.endswith("\n"):
        chunk = chunk[:-1]
        if chunk.endswith("\r"):
            chunk = chunk[:-1]
    elif chunk.endswith("\r"):
        chunk = chunk[:-1]
    return chunk[:max_line_chars]


def read_capped_source(
    path: Path,
    *,
    max_file_lines: Optional[int] = None,
    max_line_chars: int = DEFAULT_MAX_LINE_CHARS,
) -> Optional[CappedSource]:
    """Read a regular file, truncating line count and line length.

    Symlinks are not opened. Lines beyond *max_file_lines* are not read.
    """
    if path.is_symlink() or not path.is_file():
        return None
    limit = max_file_lines if max_file_lines and max_file_lines > 0 else None
    lines: List[str] = []
    exceeded = False
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            while True:
                if limit is not None and len(lines) >= limit:
                    leftover = handle.readline(1)
                    exceeded = leftover != ""
                    break
                line = _read_capped_line(handle, max_line_chars)
                if line is None:
                    break
                lines.append(line)
    except OSError:
        return None
    return CappedSource(lines=lines, exceeded_line_limit=exceeded)


def iter_capped_sources(
    root: Path,
    *,
    include_extensions: Iterable[str],
    exclude_patterns: Optional[Sequence[str]] = None,
    allowed_extensions: Iterable[str] = ALLOWED_LANGUAGE_EXTENSIONS,
    max_file_lines: Optional[int] = None,
    max_line_chars: int = DEFAULT_MAX_LINE_CHARS,
) -> Iterator[tuple[Path, List[str]]]:
    """Yield (path, capped lines) for confined language files."""
    for path in iter_language_files(
        root,
        include_extensions=include_extensions,
        exclude_patterns=exclude_patterns,
        allowed_extensions=allowed_extensions,
    ):
        source = read_capped_source(
            path,
            max_file_lines=max_file_lines,
            max_line_chars=max_line_chars,
        )
        if source is None:
            continue
        yield path, source.lines


def extend_capped(
    dest: List[Any],
    additions: Sequence[Any],
    max_findings: Optional[int],
) -> bool:
    """Append *additions* until *max_findings*. Return True if the cap is hit."""
    if max_findings is None:
        dest.extend(additions)
        return False
    if max_findings <= 0:
        return True
    room = max_findings - len(dest)
    if room <= 0:
        return True
    dest.extend(additions[:room])
    return len(dest) >= max_findings


def collect_regex_findings(
    scan_path: Path,
    *,
    include_extensions: Iterable[str],
    exclude_patterns: Optional[Sequence[str]],
    allowed_extensions: Iterable[str],
    max_file_lines: Optional[int],
    max_findings: Optional[int],
    rules: Sequence[Callable[..., List[Any]]],
    enabled_for: Callable[[str], bool],
) -> List[Any]:
    """Run regex rules over confined, size-capped sources."""
    findings: List[Any] = []
    for src_file, lines in iter_capped_sources(
        scan_path,
        include_extensions=include_extensions,
        exclude_patterns=exclude_patterns,
        allowed_extensions=allowed_extensions,
        max_file_lines=max_file_lines,
    ):
        for rule_fn in rules:
            if max_findings is not None and len(findings) >= max_findings:
                return findings
            rule_id = (
                rule_fn.__doc__.split(":")[0].strip() if rule_fn.__doc__ else ""
            )
            batch = rule_fn(str(src_file), lines, enabled=enabled_for(rule_id))
            if extend_capped(findings, batch, max_findings):
                return findings
    return findings
