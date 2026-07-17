"""
Regression Detector Service

Detects performance regressions between two datasets.
"""

import math
from datetime import datetime
from typing import Dict, List, Sequence, Tuple

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
    glass_delta as _glass_delta,
    hodges_lehmann,
    mann_whitney_u as _mann_whitney_u,
    percentile,
    pseudo_median,
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

    #: Default verdict mode: Welch's t gated by Hodges-Lehmann shift and
    #: Glass's delta (RESEARCH_15 three-gate verdict).
    VERDICT_THREE_GATE = "three_gate"
    #: Pre-effect-size-gating behavior (Cohen's d + mean %-change gates).
    #: Retained for one release for callers that pinned the old semantics.
    VERDICT_LEGACY = "legacy"

    def __init__(
        self,
        significance_level: float = 0.05,
        min_effect_size: float = 0.2,
        regression_threshold_percent: float = 10.0,
        critical_threshold_percent: float = 50.0,
        verdict_mode: str = VERDICT_THREE_GATE,
        hl_absolute_threshold: float = 10.0,
        hl_relative_threshold: float = 0.05,
        glass_delta_threshold: float = 0.5,
    ):
        """
        Initialize the regression detector.

        Args:
            significance_level: P-value threshold for statistical significance
            min_effect_size: Minimum Cohen's d effect size (legacy mode only)
            regression_threshold_percent: Percent change to flag as regression
                (legacy mode only)
            critical_threshold_percent: Percent change for critical severity
            verdict_mode: "three_gate" (default) requires ALL of
                statistical (Welch p < alpha), practical (HL shift >
                hl_absolute_threshold OR relative shift >
                hl_relative_threshold) and magnitude (|Glass's delta| >
                glass_delta_threshold) gates to pass. "legacy" keeps the
                previous Cohen's-d + mean-%-change gating (deprecated,
                retained one release).
            hl_absolute_threshold: Hodges-Lehmann shift gate in metric units
                (default 10, i.e. 10 ms for latency metrics)
            hl_relative_threshold: HL shift relative to baseline
                pseudo-median gate (default 0.05 = 5%)
            glass_delta_threshold: |Glass's delta| gate (default 0.5)
        """
        self.significance_level = significance_level
        self.min_effect_size = min_effect_size
        self.regression_threshold_percent = regression_threshold_percent
        self.critical_threshold_percent = critical_threshold_percent
        self.verdict_mode = verdict_mode
        self.hl_absolute_threshold = hl_absolute_threshold
        self.hl_relative_threshold = hl_relative_threshold
        self.glass_delta_threshold = glass_delta_threshold

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
                verdict_basis="insufficient_data",
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

        hl_shift = hodges_lehmann(before, after)
        baseline_pseudo_median = pseudo_median(before)
        # Relative shift is undefined (None, not 0) for a non-positive
        # baseline pseudo-median; the practical gate then relies on the
        # absolute threshold alone.
        hl_shift_relative = (
            hl_shift / baseline_pseudo_median if baseline_pseudo_median > 0 else None
        )
        glass = _glass_delta(before_mean, before_std, after_mean)

        is_statistically_significant = p_value < self.significance_level

        if self.verdict_mode == self.VERDICT_LEGACY:
            is_practically_significant = abs(effect_size) >= self.min_effect_size
            is_positive_change = after_mean > before_mean
            is_regression = (
                is_statistically_significant
                and is_practically_significant
                and is_positive_change
                and mean_change_percent >= self.regression_threshold_percent
            )
            verdict_basis = (
                f"legacy: p={p_value:.4f} (<{self.significance_level}: "
                f"{is_statistically_significant}), |d|={abs(effect_size):.2f} "
                f"(>={self.min_effect_size}: {is_practically_significant}), "
                f"mean_change={mean_change_percent:+.1f}% "
                f"(>={self.regression_threshold_percent}%)"
            )
            severity_effect = effect_size
        else:
            practical_gate = hl_shift > self.hl_absolute_threshold or (
                hl_shift_relative is not None
                and hl_shift_relative > self.hl_relative_threshold
            )
            magnitude_gate = abs(glass) > self.glass_delta_threshold
            is_practically_significant = practical_gate and magnitude_gate
            is_regression = (
                is_statistically_significant
                and practical_gate
                and magnitude_gate
                and hl_shift > 0
            )
            rel_part = (
                f"rel={hl_shift_relative:.3%} (>{self.hl_relative_threshold:.0%})"
                if hl_shift_relative is not None
                else "rel=undefined (non-positive baseline pseudo-median; "
                "absolute gate only)"
            )
            verdict_basis = (
                f"three_gate: statistical p={p_value:.4f} "
                f"(<{self.significance_level}: {is_statistically_significant}); "
                f"practical HL={hl_shift:.3f} (>{self.hl_absolute_threshold}) "
                f"or {rel_part}: {practical_gate}; "
                f"magnitude |Glass's delta|={abs(glass):.2f} "
                f"(>{self.glass_delta_threshold}): {magnitude_gate}"
            )
            severity_effect = glass if math.isfinite(glass) else effect_size

        severity = determine_regression_severity(
            is_regression, mean_change_percent, p99_change_percent, severity_effect,
            self.critical_threshold_percent, self.regression_threshold_percent,
        )

        confidence = calculate_regression_confidence(
            is_statistically_significant,
            is_practically_significant,
            p_value,
            severity_effect,
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
            hl_shift=hl_shift,
            hl_shift_relative=hl_shift_relative,
            glass_delta=glass,
            verdict_basis=verdict_basis,
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

    def mann_whitney(
        self,
        before: Sequence[float],
        after: Sequence[float],
    ) -> Tuple[float, float]:
        """
        Mann-Whitney U test (two-sided) as an alternative judge.

        NOT the default: shape changes cause false positives and variance
        collapse causes false negatives (Kayenta failure modes, RESEARCH_15).
        Prefer detect(), which uses Welch's t gated by effect sizes.

        Returns:
            Tuple of (U statistic, two-sided p-value)
        """
        return _mann_whitney_u(before, after)

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
