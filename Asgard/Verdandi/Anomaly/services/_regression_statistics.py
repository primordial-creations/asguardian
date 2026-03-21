"""
Statistical helpers for RegressionDetector.

Contains statistical calculation functions extracted from the regression detector.
"""

import math
import random
from typing import Dict, List, Sequence, Tuple

from Asgard.Verdandi.Anomaly.models.anomaly_models import AnomalySeverity


def calculate_mean_std(values: Sequence[float]) -> Tuple[float, float]:
    """Calculate mean and standard deviation."""
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        return float(values[0]), 0.0

    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    std_dev = math.sqrt(variance)

    return mean, std_dev


def calculate_change_percent(before: float, after: float) -> float:
    """Calculate percentage change."""
    if before == 0:
        return 0.0 if after == 0 else 100.0
    return (after - before) / abs(before) * 100


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


def normal_cdf(x: float) -> float:
    """Approximate normal CDF using error function."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def incomplete_beta(a: float, b: float, x: float) -> float:
    """Very rough approximation of incomplete beta function."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0

    steps = 100
    total = 0.0
    dx = x / steps

    for i in range(steps):
        xi = (i + 0.5) * dx
        total += (xi ** (a - 1)) * ((1 - xi) ** (b - 1)) * dx

    beta = math.gamma(a) * math.gamma(b) / math.gamma(a + b)
    return min(1.0, total / beta)


def t_distribution_p_value(t: float, df: float) -> float:
    """
    Approximate two-tailed p-value from t-distribution.

    Uses approximation for simplicity (exact requires scipy).
    """
    if df <= 0:
        return 1.0

    if df > 30:
        return 2 * (1 - normal_cdf(abs(t)))

    x = df / (df + t * t)
    p = incomplete_beta(df / 2, 0.5, x)
    return p


def welch_t_test(
    mean1: float,
    std1: float,
    n1: int,
    mean2: float,
    std2: float,
    n2: int,
) -> Tuple[float, float]:
    """
    Perform Welch's t-test for unequal variances.

    Returns:
        Tuple of (t-statistic, p-value)
    """
    if n1 < 2 or n2 < 2:
        return 0.0, 1.0

    if std1 == 0 and std2 == 0:
        return 0.0, 1.0 if mean1 == mean2 else 0.0

    se1 = (std1 ** 2) / n1 if n1 > 0 else 0
    se2 = (std2 ** 2) / n2 if n2 > 0 else 0
    se_total = se1 + se2

    if se_total == 0:
        return 0.0, 1.0

    t_stat = (mean2 - mean1) / math.sqrt(se_total)

    df: float
    if se1 == 0 or se2 == 0:
        df = n1 + n2 - 2
    else:
        df_num = se_total ** 2
        df_denom = (se1 ** 2) / (n1 - 1) + (se2 ** 2) / (n2 - 1)
        df = df_num / df_denom if df_denom > 0 else n1 + n2 - 2

    p_value = t_distribution_p_value(abs(t_stat), df)

    return t_stat, p_value


def cohens_d(
    mean1: float,
    std1: float,
    n1: int,
    mean2: float,
    std2: float,
    n2: int,
) -> float:
    """Calculate Cohen's d effect size."""
    if n1 < 2 or n2 < 2:
        return 0.0

    pooled_var = ((n1 - 1) * std1 ** 2 + (n2 - 1) * std2 ** 2) / (n1 + n2 - 2)
    pooled_std = math.sqrt(pooled_var)

    if pooled_std == 0:
        return 0.0

    return (mean2 - mean1) / pooled_std


def determine_regression_severity(
    is_regression: bool,
    mean_change: float,
    p99_change: float,
    effect_size: float,
    critical_threshold_percent: float,
    regression_threshold_percent: float,
) -> AnomalySeverity:
    """Determine regression severity."""
    if not is_regression:
        return AnomalySeverity.INFO

    max_change = max(abs(mean_change), abs(p99_change))

    if max_change >= critical_threshold_percent or abs(effect_size) >= 1.2:
        return AnomalySeverity.CRITICAL
    elif max_change >= critical_threshold_percent / 2 or abs(effect_size) >= 0.8:
        return AnomalySeverity.HIGH
    elif max_change >= regression_threshold_percent or abs(effect_size) >= 0.5:
        return AnomalySeverity.MEDIUM
    else:
        return AnomalySeverity.LOW


def calculate_regression_confidence(
    is_stat_sig: bool,
    is_pract_sig: bool,
    p_value: float,
    effect_size: float,
) -> float:
    """Calculate confidence in regression detection."""
    if not is_stat_sig:
        return 0.0

    p_confidence = 1 - p_value
    effect_confidence = min(1.0, abs(effect_size) / 0.8)

    return 0.6 * p_confidence + 0.4 * effect_confidence


def generate_regression_description(
    is_regression: bool,
    mean_change: float,
    p99_change: float,
    p_value: float,
    effect_size: float,
) -> str:
    """Generate human-readable description."""
    if not is_regression:
        if mean_change < 0:
            return f"Performance improved by {abs(mean_change):.1f}% (mean)"
        else:
            return f"No significant regression detected (change: {mean_change:+.1f}%)"

    return (
        f"Regression detected: mean increased by {mean_change:.1f}%, "
        f"P99 changed by {p99_change:+.1f}% "
        f"(p={p_value:.4f}, d={effect_size:.2f})"
    )


def bootstrap_comparison(
    before: List[float],
    after: List[float],
    iterations: int,
) -> Dict[str, float]:
    """Bootstrap comparison for more robust regression detection."""
    n_before = len(before)
    n_after = len(after)

    differences = []

    for _ in range(iterations):
        sample_before = [random.choice(before) for _ in range(n_before)]
        sample_after = [random.choice(after) for _ in range(n_after)]

        mean_before = sum(sample_before) / n_before
        mean_after = sum(sample_after) / n_after

        differences.append(mean_after - mean_before)

    differences.sort()

    return {
        "mean_difference": sum(differences) / len(differences),
        "ci_lower_95": differences[int(0.025 * iterations)],
        "ci_upper_95": differences[int(0.975 * iterations)],
        "ci_lower_99": differences[int(0.005 * iterations)],
        "ci_upper_99": differences[int(0.995 * iterations)],
        "probability_regression": sum(1 for d in differences if d > 0) / iterations,
    }


def generate_regression_recommendations(
    is_regression: bool,
    severity: AnomalySeverity,
    mean_change: float,
    p99_change: float,
) -> List[str]:
    """Generate recommendations based on regression analysis."""
    recommendations: List[str] = []

    if not is_regression:
        return recommendations

    if severity == AnomalySeverity.CRITICAL:
        recommendations.append(
            "CRITICAL regression detected. Consider rolling back the change immediately."
        )
    elif severity == AnomalySeverity.HIGH:
        recommendations.append(
            "Significant regression detected. Investigate the root cause urgently."
        )

    if p99_change > mean_change * 2:
        recommendations.append(
            "P99 regression is larger than mean regression. "
            "Investigate tail latency issues and timeout handling."
        )

    recommendations.append(
        "Compare profiling data before and after the change to identify bottlenecks."
    )

    return recommendations
