"""
Regression Detector Service

Detects performance regressions between two datasets.
"""

import math
import random
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from Asgard.Verdandi.Anomaly.models.anomaly_models import (
    AnomalySeverity,
    RegressionResult,
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

        # Calculate basic statistics
        before_mean, before_std = self._calculate_mean_std(before)
        after_mean, after_std = self._calculate_mean_std(after)

        sorted_before = sorted(before)
        sorted_after = sorted(after)
        before_p99 = self._percentile(sorted_before, 99)
        after_p99 = self._percentile(sorted_after, 99)

        # Calculate changes
        mean_change_percent = self._calculate_change_percent(before_mean, after_mean)
        p99_change_percent = self._calculate_change_percent(before_p99, after_p99)

        # Perform Welch's t-test
        t_stat, p_value = self._welch_t_test(
            before_mean, before_std, len(before), after_mean, after_std, len(after)
        )

        # Calculate effect size (Cohen's d)
        effect_size = self._cohens_d(
            before_mean, before_std, len(before), after_mean, after_std, len(after)
        )

        # Determine if this is a regression
        # Regression = statistically significant increase in latency/degradation
        is_statistically_significant = p_value < self.significance_level
        is_practically_significant = abs(effect_size) >= self.min_effect_size
        is_positive_change = after_mean > before_mean  # Higher latency = regression

        is_regression = (
            is_statistically_significant
            and is_practically_significant
            and is_positive_change
            and mean_change_percent >= self.regression_threshold_percent
        )

        # Determine severity
        severity = self._determine_severity(
            is_regression, mean_change_percent, p99_change_percent, effect_size
        )

        # Calculate confidence
        confidence = self._calculate_confidence(
            is_statistically_significant,
            is_practically_significant,
            p_value,
            effect_size,
        )

        # Generate description and recommendations
        description = self._generate_description(
            is_regression, mean_change_percent, p99_change_percent, p_value, effect_size
        )
        recommendations = self._generate_recommendations(
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

        before_mean, before_std = self._calculate_mean_std(before)
        after_mean, after_std = self._calculate_mean_std(after)

        sorted_before = sorted(before)
        sorted_after = sorted(after)

        return {
            "before_mean": before_mean,
            "after_mean": after_mean,
            "mean_change_percent": self._calculate_change_percent(
                before_mean, after_mean
            ),
            "before_std": before_std,
            "after_std": after_std,
            "std_change_percent": self._calculate_change_percent(before_std, after_std),
            "before_p50": self._percentile(sorted_before, 50),
            "after_p50": self._percentile(sorted_after, 50),
            "before_p90": self._percentile(sorted_before, 90),
            "after_p90": self._percentile(sorted_after, 90),
            "before_p99": self._percentile(sorted_before, 99),
            "after_p99": self._percentile(sorted_after, 99),
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

        before_list = list(before)
        after_list = list(after)
        n_before = len(before_list)
        n_after = len(after_list)

        differences = []

        for _ in range(iterations):
            # Resample with replacement
            sample_before = [random.choice(before_list) for _ in range(n_before)]
            sample_after = [random.choice(after_list) for _ in range(n_after)]

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

    def _calculate_mean_std(
        self, values: Sequence[float]
    ) -> Tuple[float, float]:
        """Calculate mean and standard deviation."""
        n = len(values)
        if n == 0:
            return 0.0, 0.0
        if n == 1:
            return float(values[0]), 0.0

        mean = sum(values) / n
        # Use sample std (n-1) for unbiased estimate
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        std_dev = math.sqrt(variance)

        return mean, std_dev

    def _calculate_change_percent(
        self, before: float, after: float
    ) -> float:
        """Calculate percentage change."""
        if before == 0:
            return 0.0 if after == 0 else 100.0
        return (after - before) / abs(before) * 100

    def _welch_t_test(
        self,
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
            # No variance, can't compute
            return 0.0, 1.0 if mean1 == mean2 else 0.0

        # Welch's t-statistic
        se1 = (std1 ** 2) / n1 if n1 > 0 else 0
        se2 = (std2 ** 2) / n2 if n2 > 0 else 0
        se_total = se1 + se2

        if se_total == 0:
            return 0.0, 1.0

        t_stat = (mean2 - mean1) / math.sqrt(se_total)

        # Welch-Satterthwaite degrees of freedom
        df: float
        if se1 == 0 or se2 == 0:
            df = n1 + n2 - 2
        else:
            df_num = se_total ** 2
            df_denom = (se1 ** 2) / (n1 - 1) + (se2 ** 2) / (n2 - 1)
            df = df_num / df_denom if df_denom > 0 else n1 + n2 - 2

        # Approximate p-value using t-distribution
        # For simplicity, use approximation for large df
        p_value = self._t_distribution_p_value(abs(t_stat), df)

        return t_stat, p_value

    def _t_distribution_p_value(self, t: float, df: float) -> float:
        """
        Approximate two-tailed p-value from t-distribution.

        Uses approximation for simplicity (exact requires scipy).
        """
        if df <= 0:
            return 1.0

        # Approximation using normal distribution for large df
        if df > 30:
            # Use standard normal approximation
            return 2 * (1 - self._normal_cdf(abs(t)))

        # For smaller df, use a rough approximation
        # This is not exact but sufficient for our purposes
        x = df / (df + t * t)
        p = self._incomplete_beta(df / 2, 0.5, x)
        return p

    def _normal_cdf(self, x: float) -> float:
        """Approximate normal CDF using error function."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _incomplete_beta(self, a: float, b: float, x: float) -> float:
        """Very rough approximation of incomplete beta function."""
        # This is a simplified approximation
        # For production use, scipy.special.betainc would be better
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0

        # Simple approximation using integration
        steps = 100
        total = 0.0
        dx = x / steps

        for i in range(steps):
            xi = (i + 0.5) * dx
            total += (xi ** (a - 1)) * ((1 - xi) ** (b - 1)) * dx

        # Normalize (very rough)
        beta = math.gamma(a) * math.gamma(b) / math.gamma(a + b)
        return min(1.0, total / beta)

    def _cohens_d(
        self,
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

        # Pooled standard deviation
        pooled_var = ((n1 - 1) * std1 ** 2 + (n2 - 1) * std2 ** 2) / (n1 + n2 - 2)
        pooled_std = math.sqrt(pooled_var)

        if pooled_std == 0:
            return 0.0

        return (mean2 - mean1) / pooled_std

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

    def _determine_severity(
        self,
        is_regression: bool,
        mean_change: float,
        p99_change: float,
        effect_size: float,
    ) -> AnomalySeverity:
        """Determine regression severity."""
        if not is_regression:
            return AnomalySeverity.INFO

        max_change = max(abs(mean_change), abs(p99_change))

        if max_change >= self.critical_threshold_percent or abs(effect_size) >= 1.2:
            return AnomalySeverity.CRITICAL
        elif max_change >= self.critical_threshold_percent / 2 or abs(effect_size) >= 0.8:
            return AnomalySeverity.HIGH
        elif max_change >= self.regression_threshold_percent or abs(effect_size) >= 0.5:
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW

    def _calculate_confidence(
        self,
        is_stat_sig: bool,
        is_pract_sig: bool,
        p_value: float,
        effect_size: float,
    ) -> float:
        """Calculate confidence in regression detection."""
        if not is_stat_sig:
            return 0.0

        # Base confidence on p-value
        p_confidence = 1 - p_value

        # Adjust for effect size
        effect_confidence = min(1.0, abs(effect_size) / 0.8)

        # Combined confidence
        return 0.6 * p_confidence + 0.4 * effect_confidence

    def _generate_description(
        self,
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

    def _generate_recommendations(
        self,
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
