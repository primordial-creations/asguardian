"""
Baseline Comparator Service

Compares current metrics against established baselines.
"""

import math
from datetime import datetime
from typing import Dict, List, Optional, Sequence, cast

from Asgard.Verdandi.Anomaly.models.anomaly_models import (
    AnomalyDetection,
    AnomalySeverity,
    AnomalyType,
    BaselineComparison,
    BaselineMetrics,
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

        # Calculate current statistics
        sorted_current = sorted(current_values)
        current_mean = sum(current_values) / len(current_values)
        current_median = self._percentile(sorted_current, 50)
        current_p99 = self._percentile(sorted_current, 99)

        # Calculate percentage changes
        mean_change = self._calculate_change_percent(baseline.mean, current_mean)
        median_change = self._calculate_change_percent(baseline.median, current_median)
        p99_change = self._calculate_change_percent(baseline.p99, current_p99)

        # Detect anomalies in current data against baseline
        anomalies = self._detect_anomalies(current_values, baseline, timestamps)

        # Determine if change is significant
        is_significant = (
            abs(mean_change) >= self.significance_threshold
            or abs(p99_change) >= self.significance_threshold
            or len(anomalies) > len(current_values) * 0.1  # >10% anomaly rate
        )

        # Determine overall status
        overall_status = self._determine_status(
            mean_change, p99_change, len(anomalies), len(current_values)
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            mean_change, median_change, p99_change, anomalies, overall_status
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

        # Z-score component
        z_score = (
            abs(value - baseline.mean) / baseline.std_dev
            if baseline.std_dev > 0
            else 0
        )

        # IQR component
        if baseline.iqr > 0:
            if value < baseline.lower_fence:
                iqr_score = (baseline.lower_fence - value) / baseline.iqr
            elif value > baseline.upper_fence:
                iqr_score = (value - baseline.upper_fence) / baseline.iqr
            else:
                iqr_score = 0
        else:
            iqr_score = 0

        # Combine scores (weighted average)
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
            return True  # Can't determine, assume OK

        # Check z-score
        z_score = (
            abs(value - baseline.mean) / baseline.std_dev
            if baseline.std_dev > 0
            else 0
        )
        if z_score > tolerance * self.z_threshold:
            return False

        # Check IQR
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

        mean_drift = self._calculate_change_percent(first.mean, last.mean)
        std_drift = self._calculate_change_percent(first.std_dev, last.std_dev)
        p99_drift = self._calculate_change_percent(first.p99, last.p99)

        # Consider drifting if significant change
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

    def _detect_anomalies(
        self,
        values: Sequence[float],
        baseline: BaselineMetrics,
        timestamps: Sequence[datetime],
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

            if abs(z_score) >= self.z_threshold or is_outlier:
                anomaly_type = (
                    AnomalyType.SPIKE if value > baseline.mean else AnomalyType.DROP
                )
                change_percent = self._calculate_change_percent(baseline.mean, value)
                severity = self._severity_from_change(change_percent)

                anomalies.append(
                    AnomalyDetection(
                        detected_at=datetime.now(),
                        data_timestamp=ts,
                        anomaly_type=anomaly_type,
                        severity=severity,
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

    def _calculate_change_percent(
        self, baseline_value: float, current_value: float
    ) -> float:
        """Calculate percentage change."""
        if baseline_value == 0:
            return 0.0 if current_value == 0 else 100.0
        return (current_value - baseline_value) / abs(baseline_value) * 100

    def _determine_status(
        self,
        mean_change: float,
        p99_change: float,
        anomaly_count: int,
        sample_count: int,
    ) -> str:
        """Determine overall comparison status."""
        anomaly_rate = anomaly_count / sample_count if sample_count > 0 else 0

        if (
            abs(mean_change) >= self.critical_change_percent
            or abs(p99_change) >= self.critical_change_percent
            or anomaly_rate > 0.25
        ):
            return "critical"
        elif (
            abs(mean_change) >= self.high_change_percent
            or abs(p99_change) >= self.high_change_percent
            or anomaly_rate > 0.1
        ):
            return "degraded"
        elif (
            abs(mean_change) >= self.significance_threshold
            or abs(p99_change) >= self.significance_threshold
        ):
            return "changed"
        else:
            return "normal"

    def _severity_from_change(self, change_percent: float) -> AnomalySeverity:
        """Determine severity from change percentage."""
        abs_change = abs(change_percent)
        if abs_change >= self.critical_change_percent:
            return AnomalySeverity.CRITICAL
        elif abs_change >= self.high_change_percent:
            return AnomalySeverity.HIGH
        elif abs_change >= self.significance_threshold:
            return AnomalySeverity.MEDIUM
        elif abs_change >= self.significance_threshold / 2:
            return AnomalySeverity.LOW
        return AnomalySeverity.INFO

    def _percentile(
        self, sorted_values: List[float], percentile: float
    ) -> float:
        """Calculate percentile from sorted values."""
        if not sorted_values:
            return 0.0

        n = len(sorted_values)
        if n == 1:
            return sorted_values[0]

        rank = (percentile / 100) * (n - 1)
        lower_idx = int(rank)
        upper_idx = min(lower_idx + 1, n - 1)
        fraction = rank - lower_idx

        return sorted_values[lower_idx] + fraction * (
            sorted_values[upper_idx] - sorted_values[lower_idx]
        )

    def _generate_recommendations(
        self,
        mean_change: float,
        median_change: float,
        p99_change: float,
        anomalies: List[AnomalyDetection],
        status: str,
    ) -> List[str]:
        """Generate recommendations based on comparison results."""
        recommendations = []

        if status == "critical":
            recommendations.append(
                "CRITICAL: Performance has degraded significantly from baseline. "
                "Investigate immediately for recent changes."
            )

        if mean_change > self.high_change_percent:
            recommendations.append(
                f"Mean latency increased by {mean_change:.1f}%. "
                "Check for resource constraints or inefficient code paths."
            )
        elif mean_change < -self.high_change_percent:
            recommendations.append(
                f"Mean latency decreased by {abs(mean_change):.1f}%. "
                "Verify this improvement is real and not due to reduced load."
            )

        if p99_change > self.critical_change_percent:
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
