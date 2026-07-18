"""
SZZ Bug-Inducing-Commit Trace (Plan 05 Sec.3.3, Stage 2).

Pure `git` subprocess implementation (argv-list only, no `shell=True`),
fully offline against the repository's own history - no tracker/issue-API
integration.

Pipeline:
    1. Identify bug-fix commits via commit-message heuristics (fix/bug/
       patch/hotfix/CVE keywords, optionally strengthened by an issue
       reference like `#123` or `JIRA-123`). Merge commits are excluded -
       classic SZZ blames single-parent diffs only.
    2. For each fix commit, diff it against its parent with `-U0` to get
       the exact old-file line ranges the fix touched (pure additions -
       `@@ -a,0 +c,d @@` - carry no prior line to blame and are skipped).
    3. `git blame -w -C` those line ranges *at the parent revision* to find
       the commit(s) that last touched them - the bug-inducing commits.
       `-w` ignores whitespace-only changes and `-C` follows copied/moved
       lines, which is how this module satisfies the "filter out cosmetic
       changes" requirement: blame walks straight past pure reformatting
       to the substantive change underneath.

Known, documented limitation: classic SZZ also filters inducing commits
that post-date the *bug report* (not the fix) - meaningful triage requires
an issue tracker this module deliberately does not integrate with (offline
mandate). Every inducing commit found here is guaranteed to be a genuine
ancestor of the fix commit (an ordering `git blame` enforces structurally),
which is a weaker but sound substitute: it cannot be wrong about causality
direction, only imprecise about exactly how early the "true" origin is.

Repos with too few identifiable fix commits return a typed
`SZZStatus.INSUFFICIENT_DATA` result - never a fabricated trace.
"""

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from Asgard.Bragi.Calibration.models.calibration_models import (
    BugFixCommit,
    SZZResult,
    SZZStatus,
)

MIN_FIX_COMMITS = 5
MAX_FIX_COMMITS_SCANNED = 500  # deterministic cap so runtime stays bounded on huge histories

_RECORD_SEP = "\x1e"
_FIELD_SEP = "\x1f"

_FIX_KEYWORD_RE = re.compile(
    r"\b(fix|fixes|fixed|bug|bugfix|hotfix|patch|patched|cve)\b", re.IGNORECASE
)
_ISSUE_REF_RE = re.compile(r"(#\d+|\b[A-Z][A-Z0-9]+-\d+\b|CVE-\d{4}-\d+)")


def _run_git(repo_root: Path, args: List[str], timeout: int = 60) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root)] + args,
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _is_git_repo(repo_root: Path) -> bool:
    out = _run_git(repo_root, ["rev-parse", "--is-inside-work-tree"], timeout=10)
    return out is not None and out.strip() == "true"


def is_bugfix_subject(subject: str) -> bool:
    """
    True when a commit subject matches the bug-fix heuristics: a fix
    keyword alone is sufficient (the common case); an issue reference alone
    is not (too many refactor/feature commits cite tickets), but strengthens
    a keyword match's confidence - this module does not track confidence
    separately, only membership, so keyword-match remains the gate.
    """
    return bool(_FIX_KEYWORD_RE.search(subject))


def identify_bugfix_commits(
    repo_root: Path, max_commits: int = MAX_FIX_COMMITS_SCANNED
) -> List[BugFixCommit]:
    """
    Scan full history for single-parent commits whose subject line matches
    the bug-fix heuristics. Deterministic: `git log` order is already a
    stable (committer-date-then-topological) ordering; capped at
    `max_commits` (most recent first) for bounded runtime on large repos.
    """
    repo_root = Path(repo_root)
    if not repo_root.exists() or not _is_git_repo(repo_root):
        return []

    log = _run_git(
        repo_root,
        [
            "log",
            f"--pretty=format:{_RECORD_SEP}%H{_FIELD_SEP}%P{_FIELD_SEP}%ct{_FIELD_SEP}%s",
        ],
        timeout=120,
    )
    if log is None:
        return []

    commits: List[BugFixCommit] = []
    for raw in log.split(_RECORD_SEP):
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split(_FIELD_SEP)
        if len(parts) != 4:
            continue
        sha, parents, ts, subject = parts
        parent_list = parents.split()
        if len(parent_list) != 1:
            continue  # merge commit or root commit - classic SZZ skips both
        if not is_bugfix_subject(subject):
            continue
        try:
            timestamp = int(ts)
        except ValueError:
            continue
        commits.append(
            BugFixCommit(sha=sha, parent_sha=parent_list[0], timestamp=timestamp, subject=subject)
        )
        if len(commits) >= max_commits:
            break
    return commits


def _parse_unified_diff_hunks(diff_text: str) -> List[Tuple[str, int, int]]:
    """
    Parse `git diff -U0` output into `(old_file_path, old_start, old_count)`
    tuples - one per hunk that removed/modified at least one old-side line.
    Pure additions (`old_count == 0`) are skipped: there is no prior line
    to blame.
    """
    hunks: List[Tuple[str, int, int]] = []
    current_path: Optional[str] = None
    hunk_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current_path = None
        elif line.startswith("--- "):
            path = line[4:].strip()
            if path.startswith("a/"):
                path = path[2:]
            current_path = None if path == "/dev/null" else path
        elif line.startswith("@@ ") and current_path:
            m = hunk_re.match(line)
            if not m:
                continue
            old_start = int(m.group(1))
            old_count = int(m.group(2)) if m.group(2) is not None else 1
            if old_count > 0:
                hunks.append((current_path, old_start, old_count))
    return hunks


def _fix_commit_hunks(repo_root: Path, commit: BugFixCommit) -> List[Tuple[str, int, int]]:
    diff = _run_git(
        repo_root,
        ["diff", "-U0", "--no-color", commit.parent_sha, commit.sha],
        timeout=60,
    )
    if diff is None:
        return []
    return _parse_unified_diff_hunks(diff)


_BLAME_SHA_RE = re.compile(r"^([0-9a-f]{40})\s")


def _blame_inducing_commits(
    repo_root: Path, parent_sha: str, path: str, start: int, count: int
) -> Set[str]:
    out = _run_git(
        repo_root,
        [
            "blame", "-w", "-C", "--porcelain",
            "-L", f"{start},{start + count - 1}",
            parent_sha, "--", path,
        ],
        timeout=30,
    )
    if out is None:
        return set()
    shas: Set[str] = set()
    for line in out.splitlines():
        m = _BLAME_SHA_RE.match(line)
        if m:
            shas.add(m.group(1))
    return shas


def compute_szz(
    repo_root,
    min_fix_commits: int = MIN_FIX_COMMITS,
    max_commits: int = MAX_FIX_COMMITS_SCANNED,
) -> SZZResult:
    """
    Run the full SZZ trace over `repo_root`'s own history.

    Returns `SZZStatus.INSUFFICIENT_DATA` (never a fabricated/empty-but-OK
    result) when fewer than `min_fix_commits` bug-fix commits can be
    identified - the plan's documented gate for "too few fix commits to
    trust the trace".
    """
    repo_root = Path(repo_root)
    bugfix_commits = identify_bugfix_commits(repo_root, max_commits=max_commits)
    if len(bugfix_commits) < min_fix_commits:
        return SZZResult(
            status=SZZStatus.INSUFFICIENT_DATA,
            fix_commit_count=len(bugfix_commits),
            min_fix_commits=min_fix_commits,
            note=(
                f"only {len(bugfix_commits)} bug-fix commit(s) identified; "
                f"SZZ requires >= {min_fix_commits} to trace a trustworthy signal "
                "(the full DEEPTHINK_10 burn-in is 200-300 traceable fixes; this "
                "module's floor is a much lower practical minimum below which "
                "even a coarse trace is not attempted)"
            ),
        )

    induced_by_file: Dict[str, Set[str]] = {}
    for commit in bugfix_commits:
        for path, start, count in _fix_commit_hunks(repo_root, commit):
            inducing = _blame_inducing_commits(repo_root, commit.parent_sha, path, start, count)
            if not inducing:
                continue
            induced_by_file.setdefault(path, set()).update(inducing)

    return SZZResult(
        status=SZZStatus.OK,
        fix_commit_count=len(bugfix_commits),
        min_fix_commits=min_fix_commits,
        induced_commit_counts={path: len(shas) for path, shas in induced_by_file.items()},
        note=f"traced {len(bugfix_commits)} bug-fix commit(s) across {len(induced_by_file)} file(s)",
    )
