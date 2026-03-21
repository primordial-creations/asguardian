"""
Statistical helpers for StatisticalDetector.

Contains statistical calculation functions extracted from the statistical detector.
"""

import math
from datetime import datetime
from typing import List, Optional, Sequence, Tuple

from Asgard.Verdandi.Anomaly.models.anomaly_models import (
    AnomalyDetection,
    AnomalySeverity,
    AnomalyType,
    BaselineMetrics,
)


def calculate_mean_std(values: Sequence[float]) -> Tuple[float, float]:
    """Calculate mean and standard deviation."""
    n = len(values)
    if n == 0:
        return 0.0, 0.0

    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n
    std_dev = math.sqrt(variance)

    return mean, std_dev


def calculate_quartiles(values: Sequence[float]) -> Tuple[float, float]:
    """Calculate Q1 and Q3."""
    sorted_values = sorted(values)
    q1 = percentile(sorted_values, 25)
    q3 = percentile(sorted_values, 75)
    return q1, q3


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


def severity_from_zscore(z_score: float) -> AnomalySeverity:
    """Determine severity from z-score."""
    abs_z = abs(z_score)
    if abs_z >= 5:
        return AnomalySeverity.CRITICAL
    elif abs_z >= 4:
        return AnomalySeverity.HIGH
    elif abs_z >= 3:
        return AnomalySeverity.MEDIUM
    elif abs_z >= 2:
        return AnomalySeverity.LOW
    return AnomalySeverity.INFO


def severity_from_iqr_distance(distance: float) -> AnomalySeverity:
    """Determine severity from IQR distance."""
    if distance >= 3:
        return AnomalySeverity.CRITICAL
    elif distance >= 2:
        return AnomalySeverity.HIGH
    elif distance >= 1.5:
        return AnomalySeverity.MEDIUM
    elif distance >= 1:
        return AnomalySeverity.LOW
    return AnomalySeverity.INFO


def confidence_from_zscore(z_score: float) -> float:
    """Calculate confidence from z-score."""
    abs_z = abs(z_score)
    return min(0.99, 1.0 - math.exp(-0.5 * abs_z))


def calculate_baseline_metrics(
    values: Sequence[float],
    metric_name: str,
    period_days: int,
    iqr_multiplier: float,
) -> "BaselineMetrics":
    """Calculate baseline metrics from historical data."""
    sorted_values = sorted(values)
    mean, std_dev = calculate_mean_std(values)
    q1 = percentile(sorted_values, 25)
    q3 = percentile(sorted_values, 75)
    iqr = q3 - q1

    return BaselineMetrics(
        metric_name=metric_name,
        calculated_at=datetime.now(),
        sample_count=len(values),
        baseline_period_days=period_days,
        mean=mean,
        median=percentile(sorted_values, 50),
        std_dev=std_dev,
        min_value=sorted_values[0],
        max_value=sorted_values[-1],
        p5=percentile(sorted_values, 5),
        p25=q1,
        p75=q3,
        p95=percentile(sorted_values, 95),
        p99=percentile(sorted_values, 99),
        iqr=iqr,
        lower_fence=q1 - iqr_multiplier * iqr,
        upper_fence=q3 + iqr_multiplier * iqr,
    )


def detect_anomalies_with_baseline(
    values: Sequence[float],
    baseline: BaselineMetrics,
    timestamps: Sequence[datetime],
    z_threshold: float,
) -> List[AnomalyDetection]:
    """Detect anomalies using a pre-calculated baseline."""
    anomalies: List[AnomalyDetection] = []

    for value, ts in zip(values, timestamps):
        z_score = (
            (value - baseline.mean) / baseline.std_dev
            if baseline.std_dev > 0
            else 0
        )

        is_iqr_outlier = (
            value < baseline.lower_fence or value > baseline.upper_fence
        )

        if abs(z_score) >= z_threshold or is_iqr_outlier:
            anomaly_type = (
                AnomalyType.SPIKE if value > baseline.mean else AnomalyType.DROP
            )
            sev = max(
                severity_from_zscore(z_score),
                severity_from_iqr_distance(
                    abs(value - baseline.median) / baseline.iqr if baseline.iqr > 0 else 0
                ),
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
                    deviation_percent=(
                        abs(value - baseline.mean) / baseline.mean * 100
                        if baseline.mean != 0
                        else 0
                    ),
                    z_score=z_score,
                    confidence=confidence_from_zscore(z_score),
                    description=f"Anomaly detected against baseline (z={z_score:.2f})",
                )
            )

    return anomalies


def find_change_points_in_values(
    values: Sequence[float],
    window_size: int,
    z_threshold: float,
) -> List[Tuple[int, float]]:
    """Find potential change points using sliding window."""
    if len(values) < 2 * window_size:
        return []

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

            if change_magnitude >= z_threshold:
                change_points.append((i, change_magnitude))

    return change_points
