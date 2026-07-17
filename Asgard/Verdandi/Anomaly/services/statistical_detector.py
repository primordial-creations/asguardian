"""
Statistical Detector Service

Provides statistical anomaly detection using z-score and IQR methods.
"""

from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from Asgard.Verdandi.Anomaly.models.anomaly_models import (
    AnomalyDetection,
    AnomalySeverity,
    AnomalyType,
    BaselineMetrics,
    BimodalityResult,
    DriftResult,
    MethodRecommendation,
    SensitivityProfile,
    StepChangeResult,
)
from Asgard.Verdandi.Anomaly.services import _batch_detectors
from Asgard.Verdandi.Anomaly.services._stat_helpers import (
    calculate_baseline_metrics,
    calculate_mean_std,
    calculate_quartiles,
    confidence_from_zscore,
    detect_anomalies_with_baseline,
    find_change_points_in_values,
    percentile,
    severity_from_iqr_distance,
    severity_from_zscore,
)


class StatisticalDetector:
    """
    Statistical anomaly detector using z-score and IQR methods.

    Provides methods to detect outliers and anomalies in performance data
    using statistical techniques.

    Example:
        detector = StatisticalDetector(z_threshold=3.0)

        # Detect anomalies using z-score
        anomalies = detector.detect_zscore(data, metric_name="latency")

        # Detect using IQR method
        anomalies = detector.detect_iqr(data, metric_name="latency")

        # Combined detection
        anomalies = detector.detect(data, metric_name="latency")
    """

    def __init__(
        self,
        z_threshold: float = 3.0,
        iqr_multiplier: float = 1.5,
        min_sample_size: int = 10,
        profile: Optional[SensitivityProfile] = None,
    ):
        """
        Initialize the statistical detector.

        Args:
            z_threshold: Z-score threshold for anomaly detection
            iqr_multiplier: IQR multiplier for fence calculation (1.5 = standard, 3.0 = extreme)
            min_sample_size: Minimum samples required for detection
            profile: Optional sensitivity profile; overrides z_threshold and
                min_sample_size with metric-class presets (DEEPTHINK_08)
        """
        self.profile = profile
        if profile is not None:
            z_threshold = profile.z_threshold
            min_sample_size = profile.min_sample_size
        self.z_threshold = z_threshold
        self.iqr_multiplier = iqr_multiplier
        self.min_sample_size = min_sample_size

    def detect(
        self,
        values: Sequence[float],
        metric_name: str = "metric",
        timestamps: Optional[Sequence[datetime]] = None,
        method: str = "combined",
    ) -> List[AnomalyDetection]:
        """
        Detect anomalies in a dataset.

        Args:
            values: Sequence of metric values
            metric_name: Name of the metric
            timestamps: Optional timestamps for each value
            method: Detection method ("zscore", "iqr", or "combined")

        Returns:
            List of detected anomalies
        """
        if len(values) < self.min_sample_size:
            return []

        timestamps = timestamps or [
            datetime.now() for _ in range(len(values))
        ]

        if method == "zscore":
            return self.detect_zscore(values, metric_name, timestamps)
        elif method == "iqr":
            return self.detect_iqr(values, metric_name, timestamps)
        else:
            zscore_anomalies = self.detect_zscore(values, metric_name, timestamps)
            iqr_anomalies = self.detect_iqr(values, metric_name, timestamps)

            seen_timestamps = set()
            combined = []
            for anomaly in zscore_anomalies + iqr_anomalies:
                if anomaly.data_timestamp not in seen_timestamps:
                    seen_timestamps.add(anomaly.data_timestamp)
                    combined.append(anomaly)

            return combined

    def detect_zscore(
        self,
        values: Sequence[float],
        metric_name: str = "metric",
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> List[AnomalyDetection]:
        """
        Detect anomalies using z-score method.

        Args:
            values: Sequence of metric values
            metric_name: Name of the metric
            timestamps: Optional timestamps for each value

        Returns:
            List of detected anomalies
        """
        if len(values) < self.min_sample_size:
            return []

        timestamps = timestamps or [datetime.now() for _ in range(len(values))]
        mean, std_dev = calculate_mean_std(values)

        if std_dev == 0:
            return []

        anomalies = []
        for i, (value, ts) in enumerate(zip(values, timestamps)):
            z_score = (value - mean) / std_dev

            if abs(z_score) >= self.z_threshold:
                anomaly_type = AnomalyType.SPIKE if z_score > 0 else AnomalyType.DROP

                anomalies.append(
                    AnomalyDetection(
                        detected_at=datetime.now(),
                        data_timestamp=ts,
                        anomaly_type=anomaly_type,
                        severity=severity_from_zscore(z_score),
                        metric_name=metric_name,
                        actual_value=value,
                        expected_value=mean,
                        deviation=abs(value - mean),
                        deviation_percent=abs(value - mean) / mean * 100 if mean != 0 else 0,
                        z_score=z_score,
                        confidence=confidence_from_zscore(z_score),
                        description=f"Z-score anomaly: {z_score:.2f} standard deviations from mean",
                    )
                )

        return anomalies

    def detect_iqr(
        self,
        values: Sequence[float],
        metric_name: str = "metric",
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> List[AnomalyDetection]:
        """
        Detect anomalies using IQR (Interquartile Range) method.

        Args:
            values: Sequence of metric values
            metric_name: Name of the metric
            timestamps: Optional timestamps for each value

        Returns:
            List of detected anomalies
        """
        if len(values) < self.min_sample_size:
            return []

        timestamps = timestamps or [datetime.now() for _ in range(len(values))]

        q1, q3 = calculate_quartiles(values)
        iqr = q3 - q1
        lower_fence = q1 - self.iqr_multiplier * iqr
        upper_fence = q3 + self.iqr_multiplier * iqr
        median = percentile(sorted(values), 50)

        anomalies = []
        for i, (value, ts) in enumerate(zip(values, timestamps)):
            if value < lower_fence or value > upper_fence:
                anomaly_type = (
                    AnomalyType.SPIKE if value > upper_fence else AnomalyType.DROP
                )

                if value > upper_fence:
                    fence_distance = (value - upper_fence) / iqr if iqr > 0 else 0
                else:
                    fence_distance = (lower_fence - value) / iqr if iqr > 0 else 0

                anomalies.append(
                    AnomalyDetection(
                        detected_at=datetime.now(),
                        data_timestamp=ts,
                        anomaly_type=anomaly_type,
                        severity=severity_from_iqr_distance(fence_distance),
                        metric_name=metric_name,
                        actual_value=value,
                        expected_value=median,
                        deviation=abs(value - median),
                        deviation_percent=abs(value - median) / median * 100 if median != 0 else 0,
                        confidence=min(0.99, 0.5 + fence_distance * 0.1),
                        context={
                            "lower_fence": lower_fence,
                            "upper_fence": upper_fence,
                            "iqr": iqr,
                            "q1": q1,
                            "q3": q3,
                        },
                        description=f"IQR outlier: {fence_distance:.1f} IQRs beyond fence",
                    )
                )

        return anomalies

    def calculate_baseline(
        self,
        values: Sequence[float],
        metric_name: str = "metric",
        period_days: int = 7,
    ) -> BaselineMetrics:
        """
        Calculate baseline metrics from historical data.

        Args:
            values: Sequence of metric values
            metric_name: Name of the metric
            period_days: Period used for baseline (informational)

        Returns:
            BaselineMetrics with statistical properties
        """
        if not values:
            return BaselineMetrics(
                metric_name=metric_name, baseline_period_days=period_days
            )

        return calculate_baseline_metrics(
            values, metric_name, period_days, self.iqr_multiplier
        )

    def detect_with_baseline(
        self,
        values: Sequence[float],
        baseline: BaselineMetrics,
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> List[AnomalyDetection]:
        """
        Detect anomalies using a pre-calculated baseline.

        Args:
            values: Sequence of metric values to check
            baseline: Pre-calculated baseline metrics
            timestamps: Optional timestamps for each value

        Returns:
            List of detected anomalies
        """
        if not baseline.is_valid:
            return []

        timestamps = timestamps or [datetime.now() for _ in range(len(values))]
        return detect_anomalies_with_baseline(values, baseline, timestamps, self.z_threshold)

    def find_change_points(
        self,
        values: Sequence[float],
        window_size: int = 10,
    ) -> List[Tuple[int, float]]:
        """
        Find potential change points in the data.

        Uses a sliding window to detect significant shifts in mean.

        Args:
            values: Sequence of metric values
            window_size: Size of comparison windows

        Returns:
            List of (index, change_magnitude) tuples
        """
        return find_change_points_in_values(values, window_size, self.z_threshold)

    def check_bimodality(
        self,
        values: Sequence[float],
        valley_threshold: float = 0.5,
    ) -> BimodalityResult:
        """
        Run the bimodality guard before Gaussian methods (DEEPTHINK_02 s4).

        A global z-score anchored to the mean of a bimodal mixture misfires;
        when this returns ``is_bimodal=True``, skip z-score/IQR and use the
        reported per-mode statistics instead. This is an annotation, not an
        alert.

        Args:
            values: Sequence of metric values
            valley_threshold: Valley height / smaller peak ratio below which
                two peaks count as separate modes

        Returns:
            BimodalityResult with per-mode stats when bimodal
        """
        return _batch_detectors.bimodality_guard(values, valley_threshold)

    def detect_step_change(
        self,
        values: Sequence[float],
        method: str = "split_window_mad",
        k: float = 3.0,
        h_sigmas: float = 5.0,
    ) -> StepChangeResult:
        """
        Detect a step change in a small batch (50-500 points).

        Args:
            values: Sequence of metric values in time order
            method: "split_window_mad" or "cusum"
            k: MAD multiplier for the split-window method
            h_sigmas: Alarm threshold in sigmas for CUSUM

        Returns:
            StepChangeResult (INSUFFICIENT_DATA outcome when starved)
        """
        if method == "cusum":
            return _batch_detectors.cusum(values, h_sigmas=h_sigmas)
        return _batch_detectors.split_window_mad(values, k=k)

    def detect_drift(
        self,
        values: Sequence[float],
        alpha: float = 0.05,
        min_relative_drift: float = 0.0,
    ) -> DriftResult:
        """
        Detect gradual drift via a global OLS trend (boiling-frog fix).

        Rolling z-scores absorb slow ramps; the full-batch OLS slope with a
        t-test on slope != 0 does not.

        Args:
            values: Sequence of metric values in time order
            alpha: Significance level for the slope t-test
            min_relative_drift: Optional practical gate — total drift over the
                batch must be at least this fraction of the batch median

        Returns:
            DriftResult (INSUFFICIENT_DATA outcome when starved)
        """
        return _batch_detectors.ols_drift(
            values, alpha=alpha, min_relative_drift=min_relative_drift
        )

    def recommend_method(
        self,
        n: int,
        cycles_observed: float = 0.0,
        deployment_marker: bool = False,
        suspected_scenario: Optional[str] = None,
    ) -> MethodRecommendation:
        """
        Recommend detection methods per DEEPTHINK_02 switching thresholds.

        Args:
            n: Number of available samples
            cycles_observed: Full seasonal cycles present in the data
            deployment_marker: Whether a deployment occurred in the window
            suspected_scenario: Optional "step_change" or "gradual_drift"

        Returns:
            MethodRecommendation with recommended/avoid lists and reasons
        """
        return _batch_detectors.recommend_method(
            n, cycles_observed, deployment_marker, suspected_scenario
        )
