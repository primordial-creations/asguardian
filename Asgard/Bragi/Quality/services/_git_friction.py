"""
Bragi Git Friction Collector (Plan 02 Phase D)

Offline VCS telemetry source feeding the interest/ROI model:
churn (commits touching a file in the last 90 days), author fragmentation
(distinct authors in 12 months), and bugfix density (fix/bug/hotfix commits
in 12 months) via ``git log --numstat``.

Degrades gracefully to an empty mapping (no FileFriction entries) outside a
git repository or when the ``git`` executable is unavailable - callers
should treat a missing entry as "no telemetry", never as zero friction.
"""

import re
import subprocess
from pathlib import Path
from typing import Dict, Optional

from Asgard.Bragi.Quality.models.debt_models import FileFriction

_BUGFIX_RE = re.compile(r"\b(fix|fixes|fixed|bug|hotfix|patch)\b", re.IGNORECASE)

_CHURN_WINDOW = "90.days"
_HISTORY_WINDOW = "12.months"

# Log record separator + field separator, chosen to avoid collisions with
# commit message content.
_RECORD_SEP = "\x1e"
_FIELD_SEP = "\x1f"


def _run_git_log(repo_root: Path, since: str) -> Optional[str]:
    """Run `git log --numstat` for `since`; return stdout or None on any failure."""
    try:
        result = subprocess.run(
            [
                "git", "-C", str(repo_root), "log",
                f"--since={since}",
                f"--pretty=format:{_RECORD_SEP}%H{_FIELD_SEP}%an{_FIELD_SEP}%s",
                "--numstat",
            ],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _is_git_repo(repo_root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def _parse_numstat_log(log_output: str) -> Dict[str, Dict[str, set]]:
    """
    Parse `git log --numstat` output into per-file raw signal accumulators:
    {path: {"commits": {sha, ...}, "authors": {name, ...}, "bugfix_commits": {sha, ...}}}
    """
    per_file: Dict[str, Dict[str, set]] = {}
    current_sha: Optional[str] = None
    current_author: Optional[str] = None
    is_bugfix = False

    for raw_line in log_output.split(_RECORD_SEP):
        if not raw_line.strip():
            continue
        lines = raw_line.splitlines()
        header = lines[0]
        parts = header.split(_FIELD_SEP)
        if len(parts) != 3:
            continue
        current_sha, current_author, subject = parts
        is_bugfix = bool(_BUGFIX_RE.search(subject))

        for stat_line in lines[1:]:
            stat_line = stat_line.strip()
            if not stat_line:
                continue
            stat_parts = stat_line.split("\t")
            if len(stat_parts) != 3:
                continue
            _added, _removed, path = stat_parts
            if not path or "=>" in path:
                # Skip binary (added/removed == '-') and rename-notation edge
                # cases; renames are rare enough that under-attributing them
                # is preferable to mis-parsing the "{old => new}" syntax.
                continue
            entry = per_file.setdefault(
                path, {"commits": set(), "authors": set(), "bugfix_commits": set()}
            )
            entry["commits"].add(current_sha)
            entry["authors"].add(current_author)
            if is_bugfix:
                entry["bugfix_commits"].add(current_sha)

    return per_file


def collect_friction(repo_root: Path) -> Dict[str, FileFriction]:
    """
    Collect per-file VCS friction signals for `repo_root`.

    Returns an empty dict (never raises) outside a git repo, when git is
    missing, or on any subprocess failure - callers must treat a missing
    file as "no telemetry available", not as zero friction.
    """
    repo_root = Path(repo_root)
    if not repo_root.exists() or not _is_git_repo(repo_root):
        return {}

    history_log = _run_git_log(repo_root, _HISTORY_WINDOW)
    if history_log is None:
        return {}
    history_signals = _parse_numstat_log(history_log)

    churn_log = _run_git_log(repo_root, _CHURN_WINDOW)
    churn_signals = _parse_numstat_log(churn_log) if churn_log is not None else {}

    friction: Dict[str, FileFriction] = {}
    for path, signals in history_signals.items():
        churn_commits = len(churn_signals.get(path, {}).get("commits", set()))
        friction[path] = FileFriction(
            churn_commits_90d=churn_commits,
            distinct_authors_12m=len(signals["authors"]),
            bugfix_commits_12m=len(signals["bugfix_commits"]),
        )
    return friction


def _percentile_rank(values: Dict[str, float], key: str) -> float:
    """Percentile rank of `values[key]` within `values` (0.0 when absent/degenerate)."""
    if key not in values or len(values) < 2:
        return 0.0
    target = values[key]
    ordered = sorted(values.values())
    below = sum(1 for v in ordered if v < target)
    return below / (len(ordered) - 1) if len(ordered) > 1 else 0.0


def compute_interest_scores(
    friction_by_file: Dict[str, FileFriction],
    w_churn: float = 0.4,
    w_authors: float = 0.3,
    w_bugfix: float = 0.3,
) -> Dict[str, float]:
    """
    Percentile-normalized interest score per file in [0, 1]:
    `interest = w1*churn_norm + w2*author_fragmentation + w3*bugfix_density`.

    Percentiles are computed within the supplied file set (project-relative),
    per Plan 02 Sec.3.3. Empty input yields an empty mapping.
    """
    if not friction_by_file:
        return {}
    churn = {p: float(f.churn_commits_90d) for p, f in friction_by_file.items()}
    authors = {p: float(f.distinct_authors_12m) for p, f in friction_by_file.items()}
    bugfix = {p: float(f.bugfix_commits_12m) for p, f in friction_by_file.items()}

    return {
        path: (
            w_churn * _percentile_rank(churn, path)
            + w_authors * _percentile_rank(authors, path)
            + w_bugfix * _percentile_rank(bugfix, path)
        )
        for path in friction_by_file
    }


# Sleeping Bear / Minefield thresholds (DEEPTHINK_07).
DORMANT_MONTHS_THRESHOLD = 24
SEVERITY_DOWNGRADE = {
    "critical": "high",
    "high": "medium",
    "medium": "low",
    "low": "low",
}


def is_sleeping_bear(friction: Optional[FileFriction]) -> bool:
    """
    True when a file shows no recent VCS activity at all in the collected
    window (proxy for "untouched >= 24 months" - the collector only looks
    back 12 months, so zero signal there is the strongest available
    dormancy proxy without a longer history scan).
    """
    if friction is None:
        return False
    return (
        friction.churn_commits_90d == 0
        and friction.distinct_authors_12m == 0
        and friction.bugfix_commits_12m == 0
    )


def is_minefield(friction: Optional[FileFriction], high_metric: bool) -> bool:
    """High-metric file with high churn/bugfix activity retains max severity."""
    if friction is None:
        return False
    return high_metric and (friction.churn_commits_90d >= 5 or friction.bugfix_commits_12m >= 2)
