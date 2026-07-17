"""
Baseline Comparator Service

Compares current metrics against established baselines.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple, cast

from Asgard.Verdandi.Anomaly.models.anomaly_models import (
    AnomalyDetection,
    AnomalySeverity,
    AnomalyType,
    BaselineComparison,
    BaselineMetrics,
    BaselineStrategy,
    BaselineStrategyAssessment,
    DetectionOutcome,
    DiffInDiffResult,
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

    # ------------------------------------------------------------------
    # Baseline strategy taxonomy (DEEPTHINK_07)
    # ------------------------------------------------------------------

    _STRATEGY_CONFOUNDS: Dict[BaselineStrategy, List[str]] = {
        BaselineStrategy.PRE_POST: [
            "Time-of-day / traffic-mix drift between the pre and post windows "
            "is attributed to the change.",
            "Cold-start blind spot: the first minutes post-deploy mix JIT "
            "warm-up and cold caches into the 'after' sample — exclude them "
            "(see exclude_cold_start).",
        ],
        BaselineStrategy.HISTORICAL_WEEK: [
            "Code drift: other deployments since last week contaminate the baseline.",
            "Macro drift: organic traffic growth or seasonality (campaigns, "
            "holidays) shifts the distribution independent of the change.",
        ],
        BaselineStrategy.CANARY_CONCURRENT: [
            "SUTVA violation: canary and baseline share databases, caches, and "
            "connection pools, so the treatment leaks into the control.",
            "Cache imbalance: a freshly started canary has cold caches; compare "
            "against a baseline-canary (also freshly started), not the warm fleet.",
        ],
        BaselineStrategy.DIFF_IN_DIFF: [
            "Parallel-trends assumption: the baseline period must have drifted "
            "the same way the current period would have without the change.",
            "Coarse instrument: MDES is 15-25%; small regressions are invisible.",
        ],
    }

    _STRATEGY_MDES: Dict[BaselineStrategy, str] = {
        BaselineStrategy.CANARY_CONCURRENT: "1-5%",
        BaselineStrategy.PRE_POST: "5-15%",
        BaselineStrategy.HISTORICAL_WEEK: "10-20%",
        BaselineStrategy.DIFF_IN_DIFF: "15-25%",
    }

    def assess_strategy(
        self,
        strategy: BaselineStrategy,
    ) -> BaselineStrategyAssessment:
        """
        Return confound warnings and MDES guidance for a baseline strategy.

        Args:
            strategy: The baseline comparison strategy in use

        Returns:
            BaselineStrategyAssessment with per-strategy confounds (DEEPTHINK_07)
        """
        return BaselineStrategyAssessment(
            strategy=strategy,
            confound_warnings=list(self._STRATEGY_CONFOUNDS[strategy]),
            mdes_percent_range=self._STRATEGY_MDES[strategy],
            notes=[
                "Confounds listed here are inherent to the strategy; a "
                "significant result does not rule them out."
            ],
        )

    def diff_in_diff(
        self,
        pre_now: Sequence[float],
        post_now: Sequence[float],
        pre_baseline: Sequence[float],
        post_baseline: Sequence[float],
    ) -> DiffInDiffResult:
        """
        Difference-in-Differences estimate for no-split infrastructures.

        effect = (mean(post_now) - mean(pre_now))
               - (mean(post_baseline) - mean(pre_baseline))

        The baseline period (e.g. the same window last week) absorbs shared
        seasonal/time-of-day movement; what remains is attributed to the change.

        Args:
            pre_now: Current period, before the change
            post_now: Current period, after the change
            pre_baseline: Baseline period, same phase as pre_now
            post_baseline: Baseline period, same phase as post_now

        Returns:
            DiffInDiffResult (INSUFFICIENT_DATA when any group is empty)
        """
        groups = (pre_now, post_now, pre_baseline, post_baseline)
        if any(len(g) == 0 for g in groups):
            return DiffInDiffResult(
                outcome=DetectionOutcome.INSUFFICIENT_DATA,
                warnings=["All four groups need at least one sample."],
            )

        pre_now_mean = sum(pre_now) / len(pre_now)
        post_now_mean = sum(post_now) / len(post_now)
        pre_base_mean = sum(pre_baseline) / len(pre_baseline)
        post_base_mean = sum(post_baseline) / len(post_baseline)

        effect = (post_now_mean - pre_now_mean) - (post_base_mean - pre_base_mean)
        effect_percent = (
            effect / abs(pre_now_mean) * 100 if pre_now_mean != 0 else None
        )

        warnings = list(self._STRATEGY_CONFOUNDS[BaselineStrategy.DIFF_IN_DIFF])
        return DiffInDiffResult(
            effect=round(effect, 6),
            effect_percent=round(effect_percent, 4) if effect_percent is not None else None,
            pre_now_mean=round(pre_now_mean, 6),
            post_now_mean=round(post_now_mean, 6),
            pre_baseline_mean=round(pre_base_mean, 6),
            post_baseline_mean=round(post_base_mean, 6),
            warnings=warnings,
        )

    @staticmethod
    def canary_duration_seconds(
        requests_per_second: float,
        canary_fraction: float,
        coefficient_of_variation: float,
        relative_effect: float,
    ) -> float:
        """
        Canary observation-window sizing (DEEPTHINK_07):

            T ~= 8 / (R * p * (1 - p)) * (CV / r)^2

        Args:
            requests_per_second: Total traffic rate R
            canary_fraction: Canary traffic share p (0 < p < 1)
            coefficient_of_variation: CV of the metric (sigma / mean)
            relative_effect: Smallest relative effect r to detect (e.g. 0.05)

        Returns:
            Required duration in seconds (inf when parameters are degenerate)

        Raises:
            ValueError: If canary_fraction is outside (0, 1) or
                relative_effect / requests_per_second are not positive
        """
        if not 0 < canary_fraction < 1:
            raise ValueError("canary_fraction must be in (0, 1)")
        if requests_per_second <= 0 or relative_effect <= 0:
            raise ValueError("requests_per_second and relative_effect must be > 0")
        return (
            8.0
            / (requests_per_second * canary_fraction * (1 - canary_fraction))
            * (coefficient_of_variation / relative_effect) ** 2
        )

    @staticmethod
    def exclude_cold_start(
        values: Sequence[float],
        timestamps: Sequence[datetime],
        deploy_time: datetime,
        exclusion_seconds: float = 180.0,
    ) -> Tuple[List[float], int]:
        """
        Drop samples inside the post-deploy cold-start window (DEEPTHINK_07).

        The first minutes after a deploy mix JIT warm-up, cold caches, and
        connection re-establishment into the "after" sample; including them
        biases pre/post comparisons pessimistic.

        Args:
            values: Metric values
            timestamps: Timestamp per value (same length)
            deploy_time: Deployment time
            exclusion_seconds: Cold-start window length (default 3 minutes)

        Returns:
            (filtered_values, excluded_count)
        """
        cutoff = deploy_time + timedelta(seconds=exclusion_seconds)
        kept = [
            v
            for v, ts in zip(values, timestamps)
            if not (deploy_time <= ts < cutoff)
        ]
        return kept, len(values) - len(kept)
