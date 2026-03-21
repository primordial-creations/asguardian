"""
Helpers for TrendAnalyzer.

Contains private helper functions extracted from the trend analyzer.
"""

import math
from datetime import datetime
from typing import Dict, List, Sequence, Tuple

from Asgard.Verdandi.Trend.models.trend_models import (
    TrendAnalysis,
    TrendData,
    TrendDirection,
)


def linear_regression(
    x: Sequence[float],
    y: Sequence[float],
) -> Tuple[float, float, float]:
    """Calculate linear regression (slope, intercept, r_squared)."""
    n = len(x)
    if n < 2:
        return 0.0, y[0] if y else 0.0, 0.0

    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi * xi for xi in x)
    sum_y2 = sum(yi * yi for yi in y)

    denom = n * sum_x2 - sum_x * sum_x
    if denom == 0:
        return 0.0, sum_y / n, 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    mean_y = sum_y / n
    ss_tot = sum((yi - mean_y) ** 2 for yi in y)
    ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))

    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    r_squared = max(0.0, min(1.0, r_squared))

    return slope, intercept, r_squared


def determine_direction(
    slope: float,
    change_percent: float,
    r_squared: float,
    metric_name: str,
    r_squared_threshold: float,
    significance_threshold: float,
) -> TrendDirection:
    """Determine trend direction."""
    if r_squared < r_squared_threshold:
        if abs(change_percent) < significance_threshold:
            return TrendDirection.STABLE
        return TrendDirection.UNKNOWN

    if abs(change_percent) < significance_threshold:
        return TrendDirection.STABLE

    is_latency_metric = any(
        term in metric_name.lower()
        for term in ["latency", "duration", "time", "delay", "response"]
    )

    if is_latency_metric:
        return TrendDirection.DEGRADING if slope > 0 else TrendDirection.IMPROVING
    else:
        return TrendDirection.IMPROVING if slope > 0 else TrendDirection.DEGRADING


def calculate_trend_confidence(
    r_squared: float,
    data_points: int,
    slope: float,
) -> float:
    """Calculate confidence in trend detection."""
    r_confidence = r_squared
    data_confidence = min(1.0, data_points / 30)
    return (0.7 * r_confidence + 0.3 * data_confidence)


def generate_trend_description(
    direction: TrendDirection,
    change_percent: float,
    slope_per_day: float,
    r_squared: float,
) -> str:
    """Generate human-readable trend description."""
    if direction == TrendDirection.STABLE:
        return f"Metric is stable (R2={r_squared:.2f})"
    elif direction == TrendDirection.UNKNOWN:
        return (
            f"Trend unclear due to high variability "
            f"(change={change_percent:+.1f}%, R2={r_squared:.2f})"
        )
    else:
        dir_word = "improving" if direction == TrendDirection.IMPROVING else "degrading"
        return (
            f"Metric is {dir_word}: {change_percent:+.1f}% change, "
            f"{abs(slope_per_day):.2f}/day (R2={r_squared:.2f})"
        )


def detect_change_points_in_data(
    data: List[TrendData],
    window_size: int,
    threshold: float,
) -> List[Tuple[datetime, float]]:
    """Detect significant change points in trend data."""
    if len(data) < 2 * window_size:
        return []

    sorted_data = sorted(data, key=lambda d: d.timestamp)
    values = [d.value for d in sorted_data]
    timestamps = [d.timestamp for d in sorted_data]

    change_points = []

    for i in range(window_size, len(values) - window_size):
        before = values[i - window_size : i]
        after = values[i : i + window_size]

        before_mean = sum(before) / len(before)
        after_mean = sum(after) / len(after)

        before_var = sum((x - before_mean) ** 2 for x in before) / len(before)
        after_var = sum((x - after_mean) ** 2 for x in after) / len(after)
        pooled_std = math.sqrt((before_var + after_var) / 2)

        if pooled_std > 0:
            change_magnitude = abs(after_mean - before_mean) / pooled_std
            if change_magnitude >= threshold:
                change_points.append((timestamps[i], change_magnitude))

    return change_points


def generate_report_recommendations(
    analyses: Dict[str, TrendAnalysis],
) -> List[str]:
    """Generate recommendations for trend report."""
    recommendations = []

    degrading = [
        (name, a) for name, a in analyses.items()
        if a.direction == TrendDirection.DEGRADING
    ]
    if degrading:
        worst = max(degrading, key=lambda x: abs(x[1].change_percent))
        recommendations.append(
            f"Investigate '{worst[0]}': degrading by {abs(worst[1].change_percent):.1f}% "
            f"over the analysis period."
        )

    critical_count = sum(
        1 for a in analyses.values()
        if a.is_significant and a.direction == TrendDirection.DEGRADING
    )
    if critical_count > 0:
        recommendations.append(
            f"{critical_count} metric(s) showing significant degradation. "
            f"Review recent changes and resource utilization."
        )

    volatile = [
        name for name, a in analyses.items()
        if a.volatility > 0.5
    ]
    if volatile:
        recommendations.append(
            f"High volatility in: {', '.join(volatile[:3])}. "
            f"Consider investigating inconsistent performance."
        )

    return recommendations
