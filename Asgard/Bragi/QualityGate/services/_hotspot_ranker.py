"""
Hotspot Ranker (Plan Bragi-06 Phase D) — Tier-2 async-tier prioritization.

DEEPTHINK_09's dashboard formula:

    Priority = severity_weight x churn_multiplier x reachability

- severity_weight: normalized ladder over the finding's severity.
- churn_multiplier: from git history (commit touches per file); files nobody
  changes rank below files under active churn.
- reachability: afferent-coupling percentile from Plan 03's
  DependencyGraphService centrality provider (1.0 + percentile, so unknown
  files still rank).

Root-cause grouping: findings sharing an origin symbol (or file) collapse
into one group ("fixing signature of core.auth.validate resolves N
downstream findings") ranked by aggregate priority.

Deterministic: ties broken by (file, line, rule).
"""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from Asgard.Bragi.QualityGate.models.quality_gate_models import GateFinding

SEVERITY_WEIGHTS: Dict[str, float] = {
    "critical": 10.0,
    "high": 5.0,
    "medium": 2.0,
    "low": 1.0,
    "info": 0.5,
}

GIT_TIMEOUT_SECONDS = 60

#: Churn multiplier = 1 + min(commits, CHURN_CAP) / CHURN_SCALE.
CHURN_CAP = 50
CHURN_SCALE = 10.0


@dataclass
class Hotspot:
    """One finding with its computed priority."""
    finding: GateFinding
    severity_weight: float
    churn_multiplier: float
    reachability: float
    priority: float


@dataclass
class RootCauseGroup:
    """Findings sharing an origin symbol, ranked as a unit."""
    origin: str
    hotspots: List[Hotspot] = field(default_factory=list)

    @property
    def finding_count(self) -> int:
        return len(self.hotspots)

    @property
    def total_priority(self) -> float:
        return sum(h.priority for h in self.hotspots)

    @property
    def summary(self) -> str:
        return (
            f"Fixing '{self.origin}' resolves {self.finding_count} "
            f"finding(s) (priority {self.total_priority:.1f})"
        )


def git_churn(repo_path: Path, since: str = "90.days") -> Dict[str, int]:
    """
    Commits-touching-file counts from `git log --since=<since> --name-only`.

    Returns {} when the path is not a git repository (churn multiplier then
    stays 1.0 for every file — degraded, not broken).
    """
    command = [
        "git", "-C", str(repo_path), "log", f"--since={since}",
        "--name-only", "--pretty=format:",
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=GIT_TIMEOUT_SECONDS, check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {}
    if completed.returncode != 0:
        return {}
    churn: Dict[str, int] = {}
    for line in completed.stdout.splitlines():
        name = line.strip()
        if name:
            churn[name] = churn.get(name, 0) + 1
    return churn


class HotspotRanker:
    """
    Ranks findings by severity x churn x reachability and groups them by
    root-cause origin symbol.

    Args:
        churn: {file_path: commit_count} (e.g. from git_churn()).
        reachability_provider: CentralityProvider-shaped callable mapping a
            file path/module to its afferent percentile in [0, 1] (None
            unknown). From DependencyGraphService.centrality_provider().
        origin_key: optional callable extracting the root-cause origin from
            a finding (defaults to `<file>:<rule>` grouping; findings that
            carry an `origin_symbol`-style message keep file grouping).
    """

    def __init__(
        self,
        churn: Optional[Dict[str, int]] = None,
        reachability_provider: Optional[Callable[[str], Optional[float]]] = None,
        origin_key: Optional[Callable[[GateFinding], str]] = None,
    ):
        self.churn = churn or {}
        self.reachability_provider = reachability_provider
        self.origin_key = origin_key or self._default_origin

    # ------------------------------------------------------------ components

    def churn_multiplier(self, file_path: str) -> float:
        commits = 0
        from Asgard.Bragi.QualityGate.fingerprint import normalize_path
        normalized = normalize_path(file_path)
        for path, count in self.churn.items():
            candidate = normalize_path(path)
            if candidate == normalized or normalized.endswith("/" + candidate) \
                    or candidate.endswith("/" + normalized):
                commits = count
                break
        return 1.0 + min(commits, CHURN_CAP) / CHURN_SCALE

    def reachability(self, file_path: str) -> float:
        if self.reachability_provider is None:
            return 1.0
        percentile = self.reachability_provider(file_path)
        if percentile is None:
            return 1.0
        return 1.0 + min(max(percentile, 0.0), 1.0)

    @staticmethod
    def _default_origin(finding: GateFinding) -> str:
        return f"{finding.file_path}:{finding.rule_id}"

    # ------------------------------------------------------------------ rank

    def rank(self, findings: Sequence[GateFinding]) -> List[Hotspot]:
        """Compute priorities, highest first (deterministic tie-break)."""
        hotspots: List[Hotspot] = []
        for finding in findings:
            severity_weight = SEVERITY_WEIGHTS.get(
                str(finding.severity).lower(), 1.0)
            churn_multiplier = self.churn_multiplier(finding.file_path)
            reachability = self.reachability(finding.file_path)
            hotspots.append(Hotspot(
                finding=finding,
                severity_weight=severity_weight,
                churn_multiplier=churn_multiplier,
                reachability=reachability,
                priority=severity_weight * churn_multiplier * reachability,
            ))
        hotspots.sort(key=lambda h: (
            -h.priority,
            h.finding.file_path,
            h.finding.line if h.finding.line is not None else 0,
            h.finding.rule_id,
        ))
        return hotspots

    def group_by_root_cause(
        self, findings: Sequence[GateFinding]
    ) -> List[RootCauseGroup]:
        """Group ranked findings by shared origin, highest-impact group first."""
        groups: Dict[str, RootCauseGroup] = {}
        for hotspot in self.rank(findings):
            origin = self.origin_key(hotspot.finding)
            groups.setdefault(origin, RootCauseGroup(origin=origin))
            groups[origin].hotspots.append(hotspot)
        ordered = sorted(
            groups.values(),
            key=lambda g: (-g.total_priority, g.origin),
        )
        return ordered
