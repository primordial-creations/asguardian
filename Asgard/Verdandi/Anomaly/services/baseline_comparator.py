"""
Baseline Comparator Service

Compares current metrics against established baselines.
"""

from datetime import datetime
from typing import Dict, List, Optional, Sequence, cast

from Asgard.Verdandi.Anomaly.models.anomaly_models import (
    AnomalyDetection,
    AnomalySeverity,
    AnomalyType,
    BaselineComparison,
    BaselineMetrics,
)
from Asgard.Verdandi.Anomaly.services._comparator_helpers import (
    calculate_change_percent,
    detect_baseline_anomalies,
    determine_comparison_status,
    generate_comparison_recommendations,
    percentile,
)


class BaselineComparator:
    """
    Comparator for current metrics against established baselines.

    Provides methods to compare current performance against historical
    baselines and detect significant deviations.

    Example:
        comparator = BaselineComparator()

        # Compare current data against baseline
        comparison = comparator.compare(current_values, baseline)
        if comparison.is_significant:
            print(f"Significant change: {comparison.mean_change_percent}%")
    """

    def __init__(
        self,
        significance_threshold: float = 10.0,
        z_threshold: float = 2.0,
        critical_change_percent: float = 50.0,
        high_change_percent: float = 25.0,
    ):
        """
        Initialize the baseline comparator.

        Args:
            significance_threshold: Percent change to consider significant
            z_threshold: Z-score threshold for anomaly detection
            critical_change_percent: Change percent for critical severity
            high_change_percent: Change percent for high severity
        """
        self.significance_threshold = significance_threshold
        self.z_threshold = z_threshold
        self.critical_change_percent = critical_change_percent
        self.high_change_percent = high_change_percent

    def compare(
        self,
        current_values: Sequence[float],
        baseline: BaselineMetrics,
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> BaselineComparison:
        """
        Compare current values against a baseline.

        Args:
            current_values: Current metric values
            baseline: Baseline metrics for comparison
            timestamps: Optional timestamps for each value

        Returns:
            BaselineComparison with analysis results
        """
        if not current_values:
            return BaselineComparison(
                metric_name=baseline.metric_name,
                baseline=baseline,
                overall_status="no_data",
            )

        timestamps = timestamps or [datetime.now() for _ in range(len(current_values))]

        sorted_current = sorted(current_values)
        current_mean = sum(current_values) / len(current_values)
        current_median = percentile(sorted_current, 50)
        current_p99 = percentile(sorted_current, 99)

        mean_change = calculate_change_percent(baseline.mean, current_mean)
        median_change = calculate_change_percent(baseline.median, current_median)
        p99_change = calculate_change_percent(baseline.p99, current_p99)

        anomalies = detect_baseline_anomalies(
            current_values, baseline, timestamps,
            self.z_threshold, self.critical_change_percent,
            self.high_change_percent, self.significance_threshold,
        )

        is_significant = (
            abs(mean_change) >= self.significance_threshold
            or abs(p99_change) >= self.significance_threshold
            or len(anomalies) > len(current_values) * 0.1
        )

        overall_status = determine_comparison_status(
            mean_change, p99_change, len(anomalies), len(current_values),
            self.critical_change_percent, self.high_change_percent,
            self.significance_threshold,
        )

        recommendations = generate_comparison_recommendations(
            mean_change, median_change, p99_change, anomalies, overall_status,
            self.critical_change_percent, self.high_change_percent,
        )

        return BaselineComparison(
            compared_at=datetime.now(),
            metric_name=baseline.metric_name,
            baseline=baseline,
            current_mean=current_mean,
            current_median=current_median,
            current_p99=current_p99,
            sample_count=len(current_values),
            mean_change_percent=mean_change,
            median_change_percent=median_change,
            p99_change_percent=p99_change,
            is_significant=is_significant,
            anomalies_detected=anomalies,
            overall_status=overall_status,
            recommendations=recommendations,
        )

    def compare_multiple(
        self,
        current_data: Dict[str, Sequence[float]],
        baselines: Dict[str, BaselineMetrics],
    ) -> Dict[str, BaselineComparison]:
        """
        Compare multiple metrics against their baselines.

        Args:
            current_data: Dictionary of metric_name to current values
            baselines: Dictionary of metric_name to baseline

        Returns:
            Dictionary of metric_name to comparison results
        """
        results = {}
        for metric_name, values in current_data.items():
            if metric_name in baselines:
                results[metric_name] = self.compare(values, baselines[metric_name])
        return results

    def calculate_deviation_score(
        self,
        value: float,
        baseline: BaselineMetrics,
    ) -> float:
        """
        Calculate a deviation score for a single value.

        Score ranges from 0 (exactly at baseline) to 1+ (significant deviation).

        Args:
            value: The value to score
            baseline: Baseline for comparison

        Returns:
            Deviation score
        """
        if not baseline.is_valid:
            return 0.0

        z_score = (
            abs(value - baseline.mean) / baseline.std_dev
            if baseline.std_dev > 0
            else 0
        )

        if baseline.iqr > 0:
            if value < baseline.lower_fence:
                iqr_score = (baseline.lower_fence - value) / baseline.iqr
            elif value > baseline.upper_fence:
                iqr_score = (value - baseline.upper_fence) / baseline.iqr
            else:
                iqr_score = 0
        else:
            iqr_score = 0

        return cast(float, 0.6 * z_score + 0.4 * iqr_score)

    def is_within_baseline(
        self,
        value: float,
        baseline: BaselineMetrics,
        tolerance: float = 1.0,
    ) -> bool:
        """
        Check if a value is within baseline tolerance.

        Args:
            value: Value to check
            baseline: Baseline for comparison
            tolerance: Number of standard deviations or IQRs

        Returns:
            True if value is within baseline tolerance
        """
        if not baseline.is_valid:
            return True

        z_score = (
            abs(value - baseline.mean) / baseline.std_dev
            if baseline.std_dev > 0
            else 0
        )
        if z_score > tolerance * self.z_threshold:
            return False

        expanded_lower = baseline.p25 - tolerance * baseline.iqr
        expanded_upper = baseline.p75 + tolerance * baseline.iqr
        if value < expanded_lower or value > expanded_upper:
            return False

        return True

    def track_baseline_drift(
        self,
        historical_baselines: Sequence[BaselineMetrics],
    ) -> Dict[str, float]:
        """
        Track drift in baselines over time.

        Args:
            historical_baselines: Sequence of baselines over time (oldest first)

        Returns:
            Dictionary with drift metrics
        """
        if len(historical_baselines) < 2:
            return {
                "mean_drift_percent": 0.0,
                "std_drift_percent": 0.0,
                "p99_drift_percent": 0.0,
                "is_drifting": False,
            }

        first = historical_baselines[0]
        last = historical_baselines[-1]

        mean_drift = calculate_change_percent(first.mean, last.mean)
        std_drift = calculate_change_percent(first.std_dev, last.std_dev)
        p99_drift = calculate_change_percent(first.p99, last.p99)

        is_drifting = (
            abs(mean_drift) >= self.significance_threshold
            or abs(p99_drift) >= self.significance_threshold
        )

        return {
            "mean_drift_percent": mean_drift,
            "std_drift_percent": std_drift,
            "p99_drift_percent": p99_drift,
            "is_drifting": is_drifting,
        }
