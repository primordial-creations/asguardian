"""
Git Diff Engine (Plan Bragi-06 Phase C) — new-code detection base machinery.

Parses `git diff --unified=0 base...head` output into per-file changed line
ranges, the substrate for `--mode=diff` gate evaluation:

    - which files a PR touched (changed-files scan scope),
    - which LINES were added/modified (legacy-touched partition,
      small-change threshold),
    - total changed-line count (small_change_threshold_lines wiring).

Pure text parsing plus one subprocess call; no library dependencies. Rename
detection is delegated to git itself; binary files contribute no line ranges.
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

_HUNK_RE = re.compile(
    r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,(?P<count>\d+))? @@"
)
_FILE_RE = re.compile(r"^\+\+\+ (?:b/)?(?P<path>.+)$")

GIT_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class LineRange:
    """A contiguous range of changed lines in the NEW (head) file, 1-based."""
    start: int
    count: int

    @property
    def end(self) -> int:
        """Last line in the range (start itself when count is 0)."""
        return self.start + max(self.count - 1, 0)

    def contains(self, line: int) -> bool:
        """Whether a 1-based line number falls inside this range."""
        return self.count > 0 and self.start <= line <= self.end


def parse_unified_diff(diff_text: str) -> Dict[str, List[LineRange]]:
    """
    Parse `git diff --unified=0` output into {new_path: [LineRange, ...]}.

    Only additions/modifications on the head side are recorded (a pure
    deletion hunk has count 0 and contributes no coverable lines, but the
    file still appears with an empty-range marker removed).
    """
    changes: Dict[str, List[LineRange]] = {}
    current: Optional[str] = None
    for line in diff_text.splitlines():
        file_match = _FILE_RE.match(line)
        if file_match:
            path = file_match.group("path").strip()
            current = None if path == "/dev/null" else path
            if current is not None:
                changes.setdefault(current, [])
            continue
        hunk_match = _HUNK_RE.match(line)
        if hunk_match and current is not None:
            start = int(hunk_match.group("start"))
            count_raw = hunk_match.group("count")
            count = int(count_raw) if count_raw is not None else 1
            if count > 0:
                changes[current].append(LineRange(start=start, count=count))
    # Drop files with no added/modified lines (pure deletions).
    return {path: ranges for path, ranges in changes.items() if ranges}


def total_changed_lines(changed: Dict[str, List[LineRange]]) -> int:
    """Total number of added/modified lines across all files."""
    return sum(r.count for ranges in changed.values() for r in ranges)


def line_in_changes(
    changed: Dict[str, List[LineRange]], file_path: str, line: Optional[int]
) -> bool:
    """Whether (file, line) falls on a changed line. File-level match when
    the finding has no line number."""
    from Asgard.Bragi.QualityGate.fingerprint import normalize_path

    normalized = normalize_path(file_path)
    for path, ranges in changed.items():
        candidate = normalize_path(path)
        if candidate != normalized and not (
            normalized.endswith("/" + candidate) or
            candidate.endswith("/" + normalized)
        ):
            continue
        if line is None:
            return True
        return any(r.contains(line) for r in ranges)
    return False


def git_changed_lines(
    repo_path: Path,
    base: str = "main",
    head: str = "HEAD",
) -> Dict[str, List[LineRange]]:
    """
    Run `git diff --unified=0 base...head` and parse the result.

    Raises RuntimeError when git fails (missing repo, unknown ref) — a diff
    that cannot be computed must surface, not silently gate nothing.
    """
    command = [
        "git", "-C", str(repo_path), "diff", "--unified=0",
        "--no-color", "--find-renames", f"{base}...{head}",
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=GIT_TIMEOUT_SECONDS, check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as error:
        raise RuntimeError(f"git diff failed: {error}") from error
    if completed.returncode != 0:
        raise RuntimeError(
            f"git diff {base}...{head} failed: {completed.stderr.strip()}"
        )
    return parse_unified_diff(completed.stdout)
