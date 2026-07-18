"""
Freya Performance Budget Evaluator

Pure functions evaluating lab-proxy metrics against per-archetype
soft/hard budgets (DEEPTHINK_02). Warn (soft) findings are mergeable
and acknowledged; fail (hard) findings are catastrophic ceilings.
Binary gates drive metric-gaming, so both levels are always reported.

Severity mapping (Plan 01): fail -> "critical" (universal CRITICAL),
warn -> "serious" (universal MAJOR). Lab data can never justify a
Blocker (DEEPTHINK_03 weak-evidence stance).
"""

from typing import Any, Dict, List, Optional

from Asgard.Freya.Performance.models._budget_models import (
    BudgetEvaluation,
    RouteBudget,
)
from Asgard.Freya.Performance.models._performance_report_models import (
    PerformanceIssue,
)

#: Human-readable names for budget metric keys.
METRIC_LABELS: Dict[str, str] = {
    "lcp_ms": "Largest Contentful Paint",
    "cls": "Cumulative Layout Shift",
    "tbt_ms": "Total Blocking Time",
    "js_bytes": "Total JavaScript payload",
    "image_bytes": "Total image payload",
    "font_bytes": "Total font payload",
    "render_blocking_count": "Render-blocking resources",
}


def collect_metric_values(
    metrics: Optional[Any] = None,
    resource_report: Optional[Any] = None,
) -> Dict[str, float]:
    """
    Collect budgetable metric values from a PageLoadMetrics and/or
    ResourceTimingReport. Missing metrics are simply absent (the
    evaluator skips them rather than guessing).
    """
    values: Dict[str, float] = {}
    if metrics is not None:
        lcp = getattr(metrics, "largest_contentful_paint", None)
        if lcp is not None:
            values["lcp_ms"] = float(lcp)
        cls = getattr(metrics, "cumulative_layout_shift", None)
        if cls is not None:
            values["cls"] = float(cls)
        tbt = getattr(metrics, "total_blocking_time", None)
        if tbt is not None:
            values["tbt_ms"] = float(tbt)
    if resource_report is not None:
        values["js_bytes"] = float(getattr(resource_report, "script_size", 0) or 0)
        values["image_bytes"] = float(getattr(resource_report, "image_size", 0) or 0)
        values["font_bytes"] = float(getattr(resource_report, "font_size", 0) or 0)
        values["render_blocking_count"] = float(
            getattr(resource_report, "render_blocking_count", 0) or 0
        )
    return values


def evaluate_budget(
    values: Dict[str, float],
    budget: RouteBudget,
) -> List[BudgetEvaluation]:
    """
    Evaluate measured values against a RouteBudget.

    Status per metric:
        exempt: metric formally exempted (pass-with-note)
        fail:   value > hard threshold
        warn:   value > soft threshold
        pass:   otherwise
    Metrics without a measured value are skipped (no bluffing).
    """
    evaluations: List[BudgetEvaluation] = []
    for threshold in budget.thresholds:
        metric = threshold.metric
        if metric not in values:
            continue
        value = values[metric]
        if metric in budget.exemptions:
            evaluations.append(BudgetEvaluation(
                metric=metric,
                value=value,
                soft=threshold.soft,
                hard=threshold.hard,
                status="exempt",
                note=budget.exemption_reasons.get(
                    metric, "formally exempted (business-accepted tradeoff)"
                ),
            ))
            continue
        if threshold.hard is not None and value > threshold.hard:
            status = "fail"
        elif threshold.soft is not None and value > threshold.soft:
            status = "warn"
        else:
            status = "pass"
        evaluations.append(BudgetEvaluation(
            metric=metric,
            value=value,
            soft=threshold.soft,
            hard=threshold.hard,
            status=status,
        ))
    return evaluations


def budget_score(evaluations: List[BudgetEvaluation]) -> float:
    """
    Archetype-normalized 0-100 score from budget headroom:
    100 * mean(clamp(1 - (value - soft) / (hard - soft))) over budgeted
    metrics. Exempt metrics count as full headroom. Metrics missing a
    usable soft/hard pair contribute pass=1.0 / warn=0.5 / fail=0.0.
    """
    if not evaluations:
        return 0.0
    headrooms: List[float] = []
    for ev in evaluations:
        if ev.status == "exempt":
            headrooms.append(1.0)
            continue
        soft, hard = ev.soft, ev.hard
        if soft is not None and hard is not None and hard > soft:
            headroom = 1.0 - (ev.value - soft) / (hard - soft)
            headrooms.append(max(0.0, min(1.0, headroom)))
        else:
            headrooms.append({"pass": 1.0, "warn": 0.5, "fail": 0.0}[ev.status])
    return 100.0 * sum(headrooms) / len(headrooms)


def budget_evaluations_to_issues(
    evaluations: List[BudgetEvaluation],
    archetype_label: str = "",
) -> List[PerformanceIssue]:
    """
    Convert warn/fail budget evaluations into PerformanceIssues.

    Severity strings follow the universal mapping (Plan 01):
    fail -> "critical" (CRITICAL), warn -> "serious" (MAJOR).
    """
    issues: List[PerformanceIssue] = []
    suffix = f" [archetype: {archetype_label}]" if archetype_label else ""
    for ev in evaluations:
        if ev.status not in ("warn", "fail"):
            continue
        label = METRIC_LABELS.get(ev.metric, ev.metric)
        threshold = ev.hard if ev.status == "fail" else ev.soft
        level = "hard" if ev.status == "fail" else "soft"
        issues.append(PerformanceIssue(
            issue_type=f"budget_{ev.status}",
            severity="critical" if ev.status == "fail" else "serious",
            metric_name=label,
            actual_value=ev.value,
            threshold_value=float(threshold if threshold is not None else 0),
            description=(
                f"{label} ({ev.metric}) = {ev.value:g} exceeds the {level} "
                f"budget of {threshold:g}{suffix}. Lab Data — synthetic "
                "baseline; treat as regression evidence, not field truth."
            ),
            suggested_fix=(
                "Reduce the budgeted input or, for a business-accepted "
                "tradeoff, add a formal exemption for this metric in the "
                "route budget (with a reason) instead of gaming the metric."
            ),
        ))
    return issues
