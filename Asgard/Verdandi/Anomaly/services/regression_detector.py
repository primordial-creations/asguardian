"""
Regression Detector Service

Detects performance regressions between two datasets.
"""

from datetime import datetime
from typing import Dict, List, Sequence

from Asgard.Verdandi.Anomaly.models.anomaly_models import (
    AnomalySeverity,
    RegressionResult,
)
from Asgard.Verdandi.Anomaly.services._regression_statistics import (
    bootstrap_comparison as _bootstrap_comparison,
    calculate_change_percent,
    calculate_mean_std,
    calculate_regression_confidence,
    cohens_d,
    determine_regression_severity,
    generate_regression_description,
    generate_regression_recommendations,
    percentile,
    welch_t_test,
)


class RegressionDetector:
    """
    Detector for performance regressions between datasets.

    Compares "before" and "after" datasets to detect statistically
    significant performance regressions.

    Example:
        detector = RegressionDetector()

        # Compare before and after deployment
        result = detector.detect(before_latencies, after_latencies, "api_latency")
        if result.is_regression:
            print(f"Regression detected: {result.mean_change_percent}%")
    """

    def __init__(
        self,
        significance_level: float = 0.05,
        min_effect_size: float = 0.2,
        regression_threshold_percent: float = 10.0,
        critical_threshold_percent: float = 50.0,
    ):
        """
        Initialize the regression detector.

        Args:
            significance_level: P-value threshold for statistical significance
            min_effect_size: Minimum Cohen's d effect size to consider
            regression_threshold_percent: Percent change to flag as regression
            critical_threshold_percent: Percent change for critical severity
        """
        self.significance_level = significance_level
        self.min_effect_size = min_effect_size
        self.regression_threshold_percent = regression_threshold_percent
        self.critical_threshold_percent = critical_threshold_percent

    def detect(
        self,
        before: Sequence[float],
        after: Sequence[float],
        metric_name: str = "metric",
    ) -> RegressionResult:
        """
        Detect regression between before and after datasets.

        Args:
            before: Values before potential change
            after: Values after potential change
            metric_name: Name of the metric being compared

        Returns:
            RegressionResult with analysis
        """
        if not before or not after:
            return RegressionResult(
                metric_name=metric_name,
                description="Insufficient data for comparison",
            )

        before_mean, before_std = calculate_mean_std(before)
        after_mean, after_std = calculate_mean_std(after)

        sorted_before = sorted(before)
        sorted_after = sorted(after)
        before_p99 = percentile(sorted_before, 99)
        after_p99 = percentile(sorted_after, 99)

        mean_change_percent = calculate_change_percent(before_mean, after_mean)
        p99_change_percent = calculate_change_percent(before_p99, after_p99)

        t_stat, p_value = welch_t_test(
            before_mean, before_std, len(before), after_mean, after_std, len(after)
        )

        effect_size = cohens_d(
            before_mean, before_std, len(before), after_mean, after_std, len(after)
        )

        is_statistically_significant = p_value < self.significance_level
        is_practically_significant = abs(effect_size) >= self.min_effect_size
        is_positive_change = after_mean > before_mean

        is_regression = (
            is_statistically_significant
            and is_practically_significant
            and is_positive_change
            and mean_change_percent >= self.regression_threshold_percent
        )

        severity = determine_regression_severity(
            is_regression, mean_change_percent, p99_change_percent, effect_size,
            self.critical_threshold_percent, self.regression_threshold_percent,
        )

        confidence = calculate_regression_confidence(
            is_statistically_significant,
            is_practically_significant,
            p_value,
            effect_size,
        )

        description = generate_regression_description(
            is_regression, mean_change_percent, p99_change_percent, p_value, effect_size
        )
        recommendations = generate_regression_recommendations(
            is_regression, severity, mean_change_percent, p99_change_percent
        )

        return RegressionResult(
            detected_at=datetime.now(),
            metric_name=metric_name,
            before_mean=before_mean,
            after_mean=after_mean,
            before_p99=before_p99,
            after_p99=after_p99,
            before_sample_count=len(before),
            after_sample_count=len(after),
            mean_change_percent=mean_change_percent,
            p99_change_percent=p99_change_percent,
            is_regression=is_regression,
            regression_severity=severity,
            confidence=confidence,
            t_statistic=t_stat,
            p_value=p_value,
            effect_size=effect_size,
            description=description,
            recommendations=recommendations,
        )

    def detect_multiple(
        self,
        before_data: Dict[str, Sequence[float]],
        after_data: Dict[str, Sequence[float]],
    ) -> Dict[str, RegressionResult]:
        """
        Detect regressions in multiple metrics.

        Args:
            before_data: Dictionary of metric_name to before values
            after_data: Dictionary of metric_name to after values

        Returns:
            Dictionary of metric_name to regression results
        """
        results = {}
        for metric_name in before_data:
            if metric_name in after_data:
                results[metric_name] = self.detect(
                    before_data[metric_name], after_data[metric_name], metric_name
                )
        return results

    def quick_check(
        self,
        before: Sequence[float],
        after: Sequence[float],
        threshold_percent: float = 10.0,
    ) -> bool:
        """
        Quick check for potential regression.

        Uses simple mean comparison without full statistical analysis.

        Args:
            before: Values before potential change
            after: Values after potential change
            threshold_percent: Percent increase to flag

        Returns:
            True if potential regression detected
        """
        if not before or not after:
            return False

        before_mean = sum(before) / len(before)
        after_mean = sum(after) / len(after)

        if before_mean == 0:
            return after_mean > 0

        change_percent = (after_mean - before_mean) / abs(before_mean) * 100
        return change_percent >= threshold_percent

    def compare_distributions(
        self,
        before: Sequence[float],
        after: Sequence[float],
    ) -> Dict[str, float]:
        """
        Compare statistical distributions of before and after.

        Args:
            before: Values before potential change
            after: Values after potential change

        Returns:
            Dictionary with distribution comparison metrics
        """
        if not before or not after:
            return {}

        before_mean, before_std = calculate_mean_std(before)
        after_mean, after_std = calculate_mean_std(after)

        sorted_before = sorted(before)
        sorted_after = sorted(after)

        return {
            "before_mean": before_mean,
            "after_mean": after_mean,
            "mean_change_percent": calculate_change_percent(before_mean, after_mean),
            "before_std": before_std,
            "after_std": after_std,
            "std_change_percent": calculate_change_percent(before_std, after_std),
            "before_p50": percentile(sorted_before, 50),
            "after_p50": percentile(sorted_after, 50),
            "before_p90": percentile(sorted_before, 90),
            "after_p90": percentile(sorted_after, 90),
            "before_p99": percentile(sorted_before, 99),
            "after_p99": percentile(sorted_after, 99),
            "before_min": sorted_before[0],
            "after_min": sorted_after[0],
            "before_max": sorted_before[-1],
            "after_max": sorted_after[-1],
        }

    def bootstrap_comparison(
        self,
        before: Sequence[float],
        after: Sequence[float],
        iterations: int = 1000,
    ) -> Dict[str, float]:
        """
        Bootstrap comparison for more robust regression detection.

        Args:
            before: Values before potential change
            after: Values after potential change
            iterations: Number of bootstrap iterations

        Returns:
            Dictionary with bootstrap confidence intervals
        """
        if not before or not after:
            return {}

        return _bootstrap_comparison(list(before), list(after), iterations)
