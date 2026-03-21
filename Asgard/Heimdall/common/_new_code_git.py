"""
Heimdall New Code Period - git and mtime detection helpers.

Standalone functions for running git commands and parsing their output
to identify new/modified files relative to a reference point.
"""

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from Asgard.Heimdall.common._new_code_models import (
    NewCodePeriodConfig,
    NewCodePeriodResult,
    NewCodePeriodType,
)


def git_available(scan_path: str) -> bool:
    """Check whether git is available and the path is inside a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            cwd=scan_path,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def run_git(args: List[str], cwd: str) -> Optional[str]:
    """
    Run a git command and return stdout.

    Args:
        args: Git arguments (without the leading "git").
        cwd: Working directory for the command.

    Returns:
        Stdout text or None if the command failed.
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def parse_file_list(output: Optional[str]) -> List[str]:
    """Parse a newline-separated list of file paths from git output."""
    if not output:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def count_new_lines(scan_path: str, files: List[str]) -> int:
    """
    Count new/changed lines using git diff --numstat.

    Returns a best-effort total of added lines across the listed files.
    """
    if not files:
        return 0

    try:
        result = subprocess.run(
            ["git", "diff", "--numstat", "HEAD"],
            capture_output=True,
            text=True,
            cwd=scan_path,
            timeout=30,
        )
        if result.returncode != 0:
            return 0

        total = 0
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 1:
                try:
                    total += int(parts[0])
                except (ValueError, IndexError):
                    pass
        return total
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return 0


def build_result(
    period_type: str,
    new_files: List[str],
    modified_files: List[str],
    reference_point: str,
    new_lines_count: int = 0,
) -> NewCodePeriodResult:
    """Construct a NewCodePeriodResult from collected file lists."""
    return NewCodePeriodResult(
        period_type=NewCodePeriodType(period_type),
        new_files=new_files,
        modified_files=modified_files,
        new_lines_count=new_lines_count,
        total_new_code_files=len(new_files) + len(modified_files),
        reference_point=reference_point,
        detected_at=datetime.now(),
    )


def parse_name_status(output: Optional[str]) -> Tuple[List[str], List[str]]:
    """
    Parse git diff --name-status output into new_files and modified_files.

    Status codes: A = added, M = modified, D = deleted, R = renamed, C = copied.
    Added files go to new_files; all others (M, R, C) go to modified_files.
    Deleted files are excluded.

    Returns:
        Tuple of (new_files, modified_files).
    """
    new_files: List[str] = []
    modified_files: List[str] = []

    if not output:
        return new_files, modified_files

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0].upper()
        file_path = parts[-1]

        if status.startswith("A"):
            new_files.append(file_path)
        elif status.startswith("D"):
            pass
        else:
            modified_files.append(file_path)

    return new_files, modified_files


def detect_since_last_analysis(
    scan_path: str, config: NewCodePeriodConfig
) -> NewCodePeriodResult:
    """
    Detect new code since the last stored analysis baseline commit.

    If a baseline_path is configured and contains a stored commit hash,
    uses git diff between that commit and HEAD. Otherwise, uses the last
    commit as the reference point.
    """
    reference_commit: Optional[str] = None

    if config.baseline_path and config.baseline_path.exists():
        try:
            with open(config.baseline_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            reference_commit = data.get("git_commit")
        except (OSError, ValueError, KeyError):
            reference_commit = None

    if reference_commit:
        output = run_git(
            ["diff", "--name-status", f"{reference_commit}...HEAD"],
            scan_path,
        )
        reference_point = f"Since last analysis (commit {reference_commit[:8]})"
    else:
        output = run_git(
            ["diff", "--name-status", "HEAD~1", "HEAD"],
            scan_path,
        )
        reference_point = "Since last commit (no baseline found)"

    new_files, modified_files = parse_name_status(output)
    lines = count_new_lines(scan_path, modified_files + new_files)

    return build_result(
        NewCodePeriodType.SINCE_LAST_ANALYSIS.value,
        new_files,
        modified_files,
        reference_point,
        lines,
    )


def detect_since_date(
    scan_path: str, config: NewCodePeriodConfig
) -> NewCodePeriodResult:
    """Detect new code since a specific date using git log."""
    if not config.reference_date:
        return build_result(
            NewCodePeriodType.SINCE_DATE.value,
            [],
            [],
            "Since date: (no date configured)",
        )

    date_str = config.reference_date.strftime("%Y-%m-%d")
    output = run_git(
        ["log", f"--since={date_str}", "--name-only", "--pretty=format:"],
        scan_path,
    )
    all_files = parse_file_list(output)
    unique_files = list(dict.fromkeys(all_files))
    reference_point = f"Since {date_str}"

    return build_result(
        NewCodePeriodType.SINCE_DATE.value,
        [],
        unique_files,
        reference_point,
    )


def detect_since_branch_point(
    scan_path: str, config: NewCodePeriodConfig
) -> NewCodePeriodResult:
    """Detect new code since the branch diverged from a base branch."""
    base_branch = config.reference_branch

    output = run_git(
        ["diff", "--name-status", f"{base_branch}...HEAD"],
        scan_path,
    )
    new_files, modified_files = parse_name_status(output)
    reference_point = f"Since branch point from '{base_branch}'"

    return build_result(
        NewCodePeriodType.SINCE_BRANCH_POINT.value,
        new_files,
        modified_files,
        reference_point,
    )


def detect_since_version(
    scan_path: str, config: NewCodePeriodConfig
) -> NewCodePeriodResult:
    """Detect new code since a tagged version."""
    if not config.reference_version:
        return build_result(
            NewCodePeriodType.SINCE_VERSION.value,
            [],
            [],
            "Since version: (no version configured)",
        )

    version = config.reference_version
    output = run_git(
        ["diff", "--name-status", f"{version}...HEAD"],
        scan_path,
    )
    new_files, modified_files = parse_name_status(output)
    reference_point = f"Since version '{version}'"

    return build_result(
        NewCodePeriodType.SINCE_VERSION.value,
        new_files,
        modified_files,
        reference_point,
    )


def detect_by_mtime(
    scan_path: str, config: NewCodePeriodConfig
) -> NewCodePeriodResult:
    """
    Fall back to file modification time when git is not available.

    For SINCE_DATE, uses the configured reference_date.
    For all other period types, uses files modified in the last 24 hours.
    """
    cutoff: Optional[datetime] = None

    period_type: str = (
        config.period_type.value
        if isinstance(config.period_type, NewCodePeriodType)
        else config.period_type
    )

    if period_type == NewCodePeriodType.SINCE_DATE.value and config.reference_date:
        cutoff = config.reference_date
        reference_point = f"Since {cutoff.strftime('%Y-%m-%d')} (mtime fallback)"
    else:
        cutoff = datetime.now() - timedelta(hours=24)
        reference_point = "Files modified in last 24 hours (git unavailable)"

    modified_files: List[str] = []
    root = Path(scan_path)

    for fpath in root.rglob("*.py"):
        try:
            mtime = datetime.fromtimestamp(fpath.stat().st_mtime)
            if mtime >= cutoff:
                modified_files.append(str(fpath.relative_to(root)))
        except OSError:
            pass

    return build_result(
        period_type,
        [],
        modified_files,
        reference_point,
    )
