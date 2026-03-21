"""
Helpers for BaselineComparator.

Contains private helper functions extracted from the baseline comparator.
"""

from datetime import datetime
from typing import List, Sequence

from Asgard.Verdandi.Anomaly.models.anomaly_models import (
    AnomalyDetection,
    AnomalySeverity,
    AnomalyType,
    BaselineMetrics,
)


def calculate_change_percent(baseline_value: float, current_value: float) -> float:
    """Calculate percentage change."""
    if baseline_value == 0:
        return 0.0 if current_value == 0 else 100.0
    return (current_value - baseline_value) / abs(baseline_value) * 100


def percentile(sorted_values: List[float], pct: float) -> float:
    """Calculate percentile from sorted values."""
    if not sorted_values:
        return 0.0

    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]

    rank = (pct / 100) * (n - 1)
    lower_idx = int(rank)
    upper_idx = min(lower_idx + 1, n - 1)
    fraction = rank - lower_idx

    return sorted_values[lower_idx] + fraction * (
        sorted_values[upper_idx] - sorted_values[lower_idx]
    )


def severity_from_change(
    change_percent: float,
    critical_change_percent: float,
    high_change_percent: float,
    significance_threshold: float,
) -> AnomalySeverity:
    """Determine severity from change percentage."""
    abs_change = abs(change_percent)
    if abs_change >= critical_change_percent:
        return AnomalySeverity.CRITICAL
    elif abs_change >= high_change_percent:
        return AnomalySeverity.HIGH
    elif abs_change >= significance_threshold:
        return AnomalySeverity.MEDIUM
    elif abs_change >= significance_threshold / 2:
        return AnomalySeverity.LOW
    return AnomalySeverity.INFO


def determine_comparison_status(
    mean_change: float,
    p99_change: float,
    anomaly_count: int,
    sample_count: int,
    critical_change_percent: float,
    high_change_percent: float,
    significance_threshold: float,
) -> str:
    """Determine overall comparison status."""
    anomaly_rate = anomaly_count / sample_count if sample_count > 0 else 0

    if (
        abs(mean_change) >= critical_change_percent
        or abs(p99_change) >= critical_change_percent
        or anomaly_rate > 0.25
    ):
        return "critical"
    elif (
        abs(mean_change) >= high_change_percent
        or abs(p99_change) >= high_change_percent
        or anomaly_rate > 0.1
    ):
        return "degraded"
    elif (
        abs(mean_change) >= significance_threshold
        or abs(p99_change) >= significance_threshold
    ):
        return "changed"
    else:
        return "normal"


def detect_baseline_anomalies(
    values: Sequence[float],
    baseline: BaselineMetrics,
    timestamps: Sequence[datetime],
    z_threshold: float,
    critical_change_percent: float,
    high_change_percent: float,
    significance_threshold: float,
) -> List[AnomalyDetection]:
    """Detect anomalies in values against baseline."""
    anomalies: List[AnomalyDetection] = []

    if not baseline.is_valid:
        return anomalies

    for value, ts in zip(values, timestamps):
        z_score = (
            (value - baseline.mean) / baseline.std_dev
            if baseline.std_dev > 0
            else 0
        )
        is_outlier = (
            value < baseline.lower_fence or value > baseline.upper_fence
        )

        if abs(z_score) >= z_threshold or is_outlier:
            anomaly_type = (
                AnomalyType.SPIKE if value > baseline.mean else AnomalyType.DROP
            )
            change_percent = calculate_change_percent(baseline.mean, value)
            sev = severity_from_change(
                change_percent, critical_change_percent,
                high_change_percent, significance_threshold,
            )

            anomalies.append(
                AnomalyDetection(
                    detected_at=datetime.now(),
                    data_timestamp=ts,
                    anomaly_type=anomaly_type,
                    severity=sev,
                    metric_name=baseline.metric_name,
                    actual_value=value,
                    expected_value=baseline.mean,
                    deviation=abs(value - baseline.mean),
                    deviation_percent=abs(change_percent),
                    z_score=z_score,
                    confidence=min(0.99, abs(z_score) / 5),
                    description=f"Deviation from baseline: {change_percent:+.1f}%",
                )
            )

    return anomalies


def generate_comparison_recommendations(
    mean_change: float,
    median_change: float,
    p99_change: float,
    anomalies: List[AnomalyDetection],
    status: str,
    critical_change_percent: float,
    high_change_percent: float,
) -> List[str]:
    """Generate recommendations based on comparison results."""
    recommendations = []

    if status == "critical":
        recommendations.append(
            "CRITICAL: Performance has degraded significantly from baseline. "
            "Investigate immediately for recent changes."
        )

    if mean_change > high_change_percent:
        recommendations.append(
            f"Mean latency increased by {mean_change:.1f}%. "
            "Check for resource constraints or inefficient code paths."
        )
    elif mean_change < -high_change_percent:
        recommendations.append(
            f"Mean latency decreased by {abs(mean_change):.1f}%. "
            "Verify this improvement is real and not due to reduced load."
        )

    if p99_change > critical_change_percent:
        recommendations.append(
            f"P99 latency increased by {p99_change:.1f}%. "
            "Tail latency issues indicate potential timeout problems."
        )

    if len(anomalies) > 0:
        critical_count = sum(
            1 for a in anomalies if a.severity == AnomalySeverity.CRITICAL
        )
        if critical_count > 0:
            recommendations.append(
                f"{critical_count} critical anomalies detected. "
                "Review specific timestamps for incident correlation."
            )

    return recommendations
