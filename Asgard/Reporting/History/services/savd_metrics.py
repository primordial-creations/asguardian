"""
SAVD (Severity-Adjusted Vulnerability Density) trend metrics.

Per ``_Docs/Planning/Heimdall/06_Security_Scoring_Severity.md`` §D:
"``Reporting/History`` snapshots add SAVD (findings per KLOC by severity) and
store the new score; trend rendering emphasizes normalized density direction
over absolute counts (time-series > snapshot)."

Rationale (RESEARCH_13, referenced by the plan): raw finding counts are
size-blind — 5 findings score the same in a 10k-LOC repo and a 500k-LOC repo.
Normalizing by KLOC (thousand lines of code) makes density comparable across
snapshots even as the codebase grows or shrinks, which is what makes
directional trend rendering meaningful.

This module is pure computation (no I/O): callers (typically the Security
scan orchestration layer) compute severity counts and total LOC, then use
:func:`build_savd_metrics` to turn them into
:class:`~Asgard.Reporting.History.models.history_models.MetricSnapshot`
entries that get merged into an ``AnalysisSnapshot.metrics`` list before
persisting via ``HistoryStore``.
"""
from typing import Dict, List

from Asgard.Reporting.History.models.history_models import MetricSnapshot

# Canonical severity buckets, matching the impact tiers used by the Security
# normalization engine (CRITICAL/HIGH/MEDIUM/LOW).
SAVD_SEVERITIES = ("critical", "high", "medium", "low")

# Metric-name prefix used both when building MetricSnapshot entries and when
# registering them as "lower is better" in the history schema.
SAVD_METRIC_PREFIX = "savd_"

_UNIT = "findings/KLOC"


def savd_metric_name(severity: str) -> str:
    """Return the canonical metric name for a SAVD severity bucket."""
    return f"{SAVD_METRIC_PREFIX}{severity.lower()}"


def all_savd_metric_names() -> List[str]:
    """Return all canonical SAVD metric names (one per severity bucket)."""
    return [savd_metric_name(s) for s in SAVD_SEVERITIES]


def compute_savd(findings_by_severity: Dict[str, int], total_loc: float) -> Dict[str, float]:
    """Compute findings-per-KLOC for each severity bucket.

    Args:
        findings_by_severity: mapping of severity name (case-insensitive) to
            finding count. Severities outside :data:`SAVD_SEVERITIES` are
            ignored (unknown/legacy labels should be normalized upstream by
            the Security normalization engine before reaching this layer).
        total_loc: total lines of code scanned. If ``<= 0`` (unknown/empty
            project), all densities are reported as ``0.0`` rather than
            raising or dividing by zero — a project with no measurable code
            has no meaningful density, not an error.

    Returns:
        ``{"savd_critical": density, "savd_high": density, ...}`` for every
        severity in :data:`SAVD_SEVERITIES`, defaulting missing severities
        to a count of 0.
    """
    normalized_counts = {k.lower(): v for k, v in findings_by_severity.items()}
    kloc = total_loc / 1000.0 if total_loc and total_loc > 0 else 0.0

    result: Dict[str, float] = {}
    for severity in SAVD_SEVERITIES:
        count = normalized_counts.get(severity, 0)
        density = (count / kloc) if kloc > 0 else 0.0
        result[savd_metric_name(severity)] = density
    return result


def build_savd_metrics(
    findings_by_severity: Dict[str, int], total_loc: float
) -> List[MetricSnapshot]:
    """Build :class:`MetricSnapshot` entries for SAVD, ready to merge into an
    ``AnalysisSnapshot.metrics`` list.

    Example::

        snapshot.metrics.extend(
            build_savd_metrics({"critical": 1, "high": 3}, total_loc=12000)
        )
    """
    densities = compute_savd(findings_by_severity, total_loc)
    return [
        MetricSnapshot(metric_name=name, value=value, unit=_UNIT)
        for name, value in densities.items()
    ]


def total_savd(findings_by_severity: Dict[str, int], total_loc: float) -> float:
    """Return the sum of per-severity densities — a single normalized
    "overall vulnerability density" figure for quick comparisons."""
    return sum(compute_savd(findings_by_severity, total_loc).values())
